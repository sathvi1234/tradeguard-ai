"""Master Orchestrator — single trading-cycle coordinator."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from app.agents.macro_hedge import MacroHedgeAgent
from app.agents.red_team_critic import RedTeamCritic
from app.agents.strategy_brain import StrategyBrain
from app.alpaca.iex_stream import overlay_snapshot
from app.config import settings
from app.models.enums import TradingMode
from app.models.market_data import FreshnessStatus
from app.models.schemas import (
    CycleHaltReason,
    TradeMemoryRecord,
    TradeOutcome,
    TradingCycleContext,
)
from app.risk.risk_bodyguard import RiskBodyguard
from app.services.contract_selector import ContractSelector
from app.services.market_intelligence import MarketIntelligenceService
from app.services.market_snapshot import DEFAULT_WATCHLIST, classify_session
from app.services.portfolio_greeks import PortfolioGreeksService
from app.trading.audit_logger import AuditEventType, AuditSeverity
from app.utils.logging import get_logger, log_risk_event

logger = get_logger(__name__)


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _intel_payload(snap: Dict[str, Any], clock: Any, selected: Any, bars: Any) -> Dict[str, Any]:
    real: Dict[str, Any] = {}
    price = _num(snap.get("price") or snap.get("last_trade_price"))
    bid = _num(snap.get("bid"))
    ask = _num(snap.get("ask"))
    if price is not None:
        real["price"] = f"{price:.4f}"
    if bid is not None:
        real["bid"] = f"{bid:.4f}"
    if ask is not None:
        real["ask"] = f"{ask:.4f}"
    if bid is not None and ask is not None:
        real["bid_ask_spread"] = str(round(ask - bid, 6))
        real["spread"] = str(round(ask - bid, 6))
    volume = snap.get("volume")
    if volume is None and bars:
        last = bars[-1]
        volume = getattr(last, "volume", None)
    if volume is not None:
        real["volume"] = str(volume)
    prev = _num(snap.get("previous_close"))
    if prev is not None:
        real["previous_close"] = f"{prev:.4f}"
    change = _num(snap.get("day_change"))
    if change is not None:
        real["day_change"] = f"{change:.4f}"
    change_pct = _num(snap.get("day_change_pct"))
    if change_pct is not None:
        real["day_change_pct"] = f"{change_pct:.6f}"
    ts = snap.get("last_update") or snap.get("timestamp") or snap.get("quote_timestamp")
    if ts:
        real["quote_timestamp"] = str(ts)
    session = snap.get("session") or getattr(clock, "session", None)
    if session:
        real["market_session"] = str(session)
        real["session"] = str(session)
    if clock.is_open is False:
        real["market_status"] = "CLOSED"
    elif clock.is_open is True:
        real["market_status"] = "OPEN"
    elif session:
        real["market_status"] = str(session)
    freshness = snap.get("freshness")
    if freshness:
        real["freshness"] = str(freshness)
    if snap.get("quote_available") is not None:
        real["quote_available"] = snap.get("quote_available")
    closes = [b.close for b in (bars or []) if getattr(b, "close", None)]
    if len(closes) >= 3:
        rets = []
        for i in range(1, len(closes)):
            if closes[i - 1]:
                rets.append(abs(closes[i] - closes[i - 1]) / closes[i - 1])
        if rets:
            real["volatility"] = str(round(sum(rets) / len(rets), 6))
    if selected is not None:
        real["option_chain_structure"] = selected.occ_symbol
    if snap.get("vwap") is not None:
        real["vwap"] = str(snap.get("vwap"))
    return real


class MasterOrchestrator:
    """Coordinates agents around a single cycle context. Risk Guardian stays final authority."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine
        self.logger = logger
        self._lock = asyncio.Lock()
        self.strategy_brain = StrategyBrain(
            bull_agent=engine.debate_engine.bull_agent,
            bear_agent=engine.debate_engine.bear_agent,
        )
        self.red_team = RedTeamCritic()
        self.macro_hedge = MacroHedgeAgent()
        self.market_intelligence = MarketIntelligenceService()
        self.greeks = PortfolioGreeksService()
        self.bodyguard = RiskBodyguard()
        self.memory = engine.trade_memory
        self.audit = engine.audit_logger
        self.contract_selector = ContractSelector(engine.alpaca_service)

    async def run_cycle(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        if self._lock.locked():
            return {
                "cycle_id": None,
                "cycle_number": self.engine.cycle_count,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "duplicate_blocked",
                "decision": None,
                "order": None,
                "errors": ["Another cycle is already running"],
                "halt_reason": CycleHaltReason.DUPLICATE_CYCLE.value,
            }

        async with self._lock:
            return await self._run_cycle_locked(symbol)

    async def _run_cycle_locked(self, symbol: str) -> Dict[str, Any]:
        engine = self.engine
        engine.cycle_count += 1
        cycle_start = datetime.utcnow()
        ctx = TradingCycleContext(
            cycle_id=str(uuid4()),
            timestamp=cycle_start,
            symbol=symbol,
            dry_run=True,
            paper_trading=bool(settings.alpaca_paper_trade),
            live_trading_blocked=True,
        )
        result: Dict[str, Any] = {
            "cycle_id": ctx.cycle_id,
            "cycle_number": engine.cycle_count,
            "timestamp": cycle_start.isoformat(),
            "status": "unknown",
            "decision": None,
            "order": None,
            "errors": [],
            "stages": ctx.stages,
        }

        engine.last_market_intelligence = None
        engine.last_strategy_brain = None
        engine.last_debate = None
        engine.last_red_team = None
        engine.last_decision = None
        engine.last_rejection_reasons = []
        engine.last_cycle_status = None
        engine.last_cycle_message = None
        engine.last_halt_reason = None
        engine.last_risk_guardian = None

        def persist_cycle_view() -> None:
            if ctx.market_intelligence is not None:
                engine.last_market_intelligence = ctx.market_intelligence.model_dump()
            if ctx.scenarios:
                engine.last_strategy_brain = [
                    s.model_dump() if hasattr(s, "model_dump") else s for s in ctx.scenarios
                ]
            if ctx.risk_guardian_result:
                engine.last_risk_guardian = ctx.risk_guardian_result
                if ctx.debate and isinstance(ctx.debate, dict):
                    ctx.debate = dict(ctx.debate)
                    ctx.debate["risk_guardian_result"] = ctx.risk_guardian_result
            if ctx.debate:
                engine.last_debate = ctx.debate
            if ctx.red_team is not None:
                dumped = ctx.red_team.model_dump() if hasattr(ctx.red_team, "model_dump") else ctx.red_team
                engine.last_red_team = dumped
            if ctx.decision:
                engine.last_decision = ctx.decision
            engine.last_cycle_status = result.get("status")
            engine.last_cycle_message = result.get("message")
            engine.last_halt_reason = result.get("halt_reason")
            engine.last_cycle = cycle_start

        def halt(status: str, reason: CycleHaltReason, message: str) -> Dict[str, Any]:
            ctx.halt_reason = reason
            result["status"] = status
            result["halt_reason"] = reason.value
            result["message"] = message
            result["errors"].append(message)
            result["stages"] = ctx.stages
            result["decision"] = ctx.decision
            persist_cycle_view()
            self._persist_memory(ctx, TradeOutcome.BLOCKED if status != "no_trade" else TradeOutcome.NO_TRADE)
            return result

        try:
            if not settings.alpaca_paper_trade or not settings.is_paper_url():
                return halt("live_blocked", CycleHaltReason.LIVE_TRADING_BLOCKED, "Live trading is blocked")
            if settings.dry_run is False:
                return halt("live_blocked", CycleHaltReason.LIVE_TRADING_BLOCKED, "DRY_RUN must remain true")
            ctx.record_stage("safety_gates")

            healthy, error = await engine.check_system_health()
            if not healthy:
                return halt("system_error", CycleHaltReason.MISSING_DATA, error or "System unhealthy")

            from app.services.demo_ledger import demo_portfolio

            try:
                demo = await demo_portfolio(engine)
            except Exception:
                demo = None
            account = await engine.alpaca_service.get_account()
            if demo:
                ctx.portfolio_value = float(demo.get("equity") or 0)
                ctx.cash = float(demo.get("cash") or 0)
                ctx.buying_power = float(demo.get("buying_power") or 0)
                ctx.current_positions = int(demo.get("positions_count") or 0)
            elif account:
                ctx.portfolio_value = float(account.get("portfolio_value") or account.get("equity") or 0)
                ctx.cash = float(account.get("cash") or 0)
                ctx.buying_power = float(account.get("buying_power") or 0)
                ctx.current_positions = len(engine.position_manager.get_open_positions())
            else:
                return halt("portfolio_error", CycleHaltReason.MISSING_DATA, "Failed to get account")
            ctx.record_stage("account")

            if engine.drawdown_guardian.state is None:
                engine.drawdown_guardian.initialize(ctx.portfolio_value or 0)
            await engine.drawdown_guardian.update(
                current_equity=ctx.portfolio_value or 0,
                daily_pnl=0,
            )
            ctx.trading_mode = engine.drawdown_guardian.state.current_mode
            ctx.drawdown = engine.drawdown_guardian.state.drawdown_percentage
            result["mode"] = ctx.trading_mode.value
            result["drawdown"] = f"{ctx.drawdown:.2%}"
            ctx.record_stage("drawdown_guardian")

            if ctx.trading_mode == TradingMode.CRITICAL:
                assessment = self.bodyguard.assess(
                    engine.position_manager.get_open_positions(),
                    trading_mode=ctx.trading_mode,
                    drawdown=ctx.drawdown,
                    volatility_unavailable=False,
                )
                ctx.bodyguard = assessment
                result["bodyguard"] = assessment.model_dump()
                ctx.risk_guardian_result = {
                    "decision": "block",
                    "display_decision": "BLOCK",
                    "reason": "CRITICAL_MODE",
                    "rejection_reasons": ["CRITICAL_MODE"],
                    "mode": ctx.trading_mode.value,
                }
                engine.last_rejection_reasons = ["CRITICAL_MODE"]
                return halt(
                    "critical_mode",
                    CycleHaltReason.CRITICAL_MODE,
                    "Trading blocked - portfolio in CRITICAL mode",
                )

            clock = await engine.alpaca_service.get_market_clock()
            ctx.record_stage("market_clock")
            result["market_clock"] = clock.model_dump(mode="json")
            market_closed = clock.is_open is False
            result["market_status"] = "CLOSED" if market_closed else ("OPEN" if clock.is_open else "UNKNOWN")
            result["market_session"] = classify_session(clock)

            selected = None
            try:
                selected = await self.contract_selector.select(
                    watchlist=[symbol] if symbol else None,
                )
            except Exception as exc:
                logger.warning("Option contract selection skipped: %s", type(exc).__name__)
            ctx.record_stage("contract_selection")
            if selected:
                result["selected_contract"] = selected.model_dump()
                symbol = selected.underlying
            else:
                symbol = (symbol or DEFAULT_WATCHLIST[0]).upper()
            ctx.symbol = symbol
            result["symbol"] = symbol

            snap: Dict[str, Any] = {}
            try:
                snap = overlay_snapshot(await engine.alpaca_service.snapshot_symbol(symbol, clock=clock))
            except Exception as exc:
                logger.warning("snapshot_symbol failed for %s: %s", symbol, type(exc).__name__)
            ctx.record_stage("underlying_quote")
            freshness = str(snap.get("freshness") or "")
            if freshness == FreshnessStatus.STALE.value:
                ctx.data_stale = True

            bars = []
            try:
                bars = await engine.alpaca_service.get_bars(symbol, timeframe="1Day", limit=10)
            except Exception:
                bars = []

            option_snap = None
            if selected:
                try:
                    option_snap = await engine.alpaca_service.get_option_snapshot(selected.occ_symbol)
                except Exception:
                    option_snap = None
            snapshots = [option_snap] if option_snap else []
            ctx.record_stage("option_snapshots")

            greeks_snap = self.greeks.snapshot(
                positions=engine.position_manager.get_open_positions(),
                option_snapshots=snapshots,
            )
            result["greeks"] = greeks_snap.model_dump()

            real_intel = _intel_payload(snap, clock, selected, bars)
            if option_snap and option_snap.open_interest is not None:
                real_intel["open_interest"] = str(option_snap.open_interest)
            if option_snap and option_snap.implied_volatility is not None:
                real_intel["iv"] = str(option_snap.implied_volatility)
            ctx.market_intelligence = self.market_intelligence.snapshot(
                symbol, real_data=real_intel or None
            )
            ctx.record_stage("market_intelligence")

            ctx.macro = await self.macro_hedge.analyze(
                current_positions=ctx.current_positions,
                portfolio_value=ctx.portfolio_value,
            )
            ctx.record_stage("macro_hedge")

            market_analysis = None
            try:
                scout = await engine.debate_engine.market_scout.analyze(symbol=symbol)
                market_analysis = scout.to_dict()
                if scout.errors and not (scout.data or {}).get("current_price"):
                    ctx.missing_data.append("market_scout_price")
            except Exception as exc:
                ctx.missing_data.append("market_scout")
                self.audit.log_system_error(str(exc), {"stage": "market_scout"})
            ctx.record_stage("market_scout")

            ctx.scenarios = await self.strategy_brain.evaluate(
                symbol=symbol,
                market_analysis=market_analysis,
            )
            ctx.record_stage("strategy_brain")

            debate_result = None
            try:
                debate_result = await engine.debate_engine.run_debate(
                    symbol=symbol,
                    option_type=selected.option_type if selected else "call",
                    strike=selected.strike if selected else None,
                    expiration=selected.expiration if selected else None,
                    portfolio_value=ctx.portfolio_value or 0,
                    current_equity=ctx.portfolio_value or 0,
                    current_positions=ctx.current_positions,
                    current_drawdown=ctx.drawdown,
                )
                ctx.debate = debate_result.to_dict()
                ctx.decision = debate_result.final_decision
                ctx.risk_guardian_result = debate_result.risk_guardian_result
                result["decision"] = ctx.decision
                result["llm_review"] = debate_result.llm_review
                result["review_pipeline"] = debate_result.review_pipeline
                engine.last_debate = debate_result.to_dict()
            except Exception as exc:
                logger.warning("Debate engine failed: %s", type(exc).__name__)
                ctx.debate = {
                    "symbol": symbol,
                    "completed": False,
                    "agent_outputs": {"market_scout": market_analysis} if market_analysis else {},
                    "agent_errors": {"debate_engine": [str(exc)]},
                }
            ctx.record_stage("debate_engine")

            decision = ctx.decision or {}
            contract = decision.get("selected_contracts")
            if not contract and selected:
                contract = {
                    "symbol": selected.underlying,
                    "occ_symbol": selected.occ_symbol,
                    "strike": selected.strike,
                    "expiration": selected.expiration,
                    "bid": selected.bid,
                    "ask": selected.ask,
                    "entry_price": selected.last_price
                    or (
                        ((selected.bid or 0) + (selected.ask or 0)) / 2
                        if selected.bid and selected.ask
                        else None
                    ),
                }
            proposed_size = float(decision.get("proposed_size") or 0)
            confidence = float(decision.get("confidence") or 0)

            ctx.red_team = await self.red_team.critique(
                symbol=symbol,
                decision=decision or {"decision": "no_trade", "reason": "Analysis only"},
                confidence=confidence,
                scenarios=ctx.scenarios,
                missing_data=list(ctx.missing_data),
                data_stale=False,
                contract=contract or None,
                current_positions=ctx.current_positions,
                proposed_size=proposed_size,
                portfolio_value=ctx.portfolio_value,
            )
            result["red_team"] = ctx.red_team.model_dump()
            engine.last_red_team = result["red_team"]
            ctx.record_stage("red_team_critic")
            self.audit.log_event(
                AuditEventType.DECISION,
                AuditSeverity.WARNING if ctx.red_team.severity.value in ("HIGH", "CRITICAL") else AuditSeverity.INFO,
                symbol,
                "Red team critique (advisory)",
                {"severity": ctx.red_team.severity.value, "flags": ctx.red_team.risk_flags},
            )

            ctx.record_stage("decision_agent")
            analysis_note = "Bull/Bear analysis completed." if ctx.debate else "Analysis incomplete."

            if market_closed:
                ctx.decision = {
                    **(decision if isinstance(decision, dict) else {}),
                    "decision": "no_trade",
                    "analysis": analysis_note,
                    "reason": "Market closed.",
                    "execution_decision": "NO TRADE",
                    "execution_reason": "MARKET_CLOSED",
                    "confidence": decision.get("confidence") if isinstance(decision, dict) else None,
                    "strategy_recommendation": decision.get("strategy")
                    or decision.get("strategy_recommendation")
                    if isinstance(decision, dict)
                    else None,
                    "symbol": symbol,
                }
                ctx.risk_guardian_result = {
                    "decision": "block",
                    "display_decision": "BLOCK",
                    "reason": "MARKET_CLOSED",
                    "rejection_reasons": ["MARKET_CLOSED"],
                    "mode": ctx.trading_mode.value,
                    "analysis_completed": True,
                }
                engine.last_rejection_reasons = ["MARKET_CLOSED"]
                result["decision"] = ctx.decision
                ctx.record_stage("risk_guardian")
                return halt("no_trade", CycleHaltReason.MARKET_CLOSED, "NO TRADE — MARKET CLOSED")

            if decision.get("decision") == "no_trade":
                ctx.decision = {
                    **decision,
                    "analysis": analysis_note,
                    "execution_decision": "NO TRADE",
                    "execution_reason": decision.get("reasoning") or "No trade recommended",
                }
                ctx.risk_guardian_result = ctx.risk_guardian_result or {
                    "decision": "hold",
                    "display_decision": "HOLD",
                    "reason": "NO_TRADE_RECOMMENDED",
                    "rejection_reasons": ["NO_TRADE_RECOMMENDED"],
                    "mode": ctx.trading_mode.value,
                    "analysis_completed": True,
                }
                result["decision"] = ctx.decision
                ctx.record_stage("risk_guardian")
                return halt(
                    "no_trade",
                    CycleHaltReason.NO_TRADE,
                    decision.get("reasoning", "No trade recommended"),
                )

            risk_result = ctx.risk_guardian_result or {}
            ctx.record_stage("risk_guardian")
            rg_decision = str(risk_result.get("decision") or "").lower()
            if rg_decision not in ("approved", "allow"):
                reasons = risk_result.get("rejection_reasons") or [risk_result.get("reason") or "Risk Guardian rejected"]
                engine.last_rejection_reasons = reasons
                risk_result = {
                    **risk_result,
                    "display_decision": risk_result.get("display_decision") or "BLOCK",
                    "decision": risk_result.get("decision") or "block",
                }
                ctx.risk_guardian_result = risk_result
                self.audit.log_risk_rejection(symbol, [str(r) for r in reasons])
                return halt(
                    "risk_rejected",
                    CycleHaltReason.RISK_GUARDIAN_REJECTED,
                    "Risk Guardian rejected — no execution",
                )

            ctx.bodyguard = self.bodyguard.assess(
                engine.position_manager.get_open_positions(),
                trading_mode=ctx.trading_mode,
                drawdown=ctx.drawdown,
                volatility_unavailable=False,
            )
            result["bodyguard"] = ctx.bodyguard.model_dump()
            engine.last_bodyguard = result["bodyguard"]
            ctx.record_stage("risk_bodyguard")

            if isinstance(ctx.risk_guardian_result, dict):
                ctx.risk_guardian_result = {
                    **ctx.risk_guardian_result,
                    "display_decision": "ALLOW",
                }

            engine.last_decision = decision
            engine.last_cycle = cycle_start
            result["order"] = None
            result["status"] = "halted_after_risk_guardian"
            result["halt_reason"] = CycleHaltReason.DRY_RUN_ONLY.value
            result["message"] = (
                "Phase 3 data-only cycle: Risk Guardian completed; DRY_RUN remains true; no order submission"
            )
            result["stages"] = ctx.stages
            result["duration_seconds"] = (datetime.utcnow() - cycle_start).total_seconds()
            persist_cycle_view()
            self._persist_memory(ctx, TradeOutcome.NO_TRADE)
            log_risk_event(
                "autonomous_cycle_complete",
                "low",
                {
                    "cycle_id": ctx.cycle_id,
                    "status": result["status"],
                    "symbol": symbol,
                    "dry_run": True,
                    "execution": False,
                },
            )
            return result

        except Exception as exc:
            logger.error("Orchestrator cycle failed: %s", exc, exc_info=True)
            result["status"] = "cycle_error"
            result["errors"].append(str(exc))
            result["message"] = str(exc)
            result["stages"] = ctx.stages
            persist_cycle_view()
            return result

    def _persist_memory(self, ctx: TradingCycleContext, outcome: TradeOutcome) -> None:
        summaries = {}
        if ctx.decision:
            summaries["decision"] = str(ctx.decision.get("reasoning") or ctx.decision.get("decision") or "")[:500]
        record = TradeMemoryRecord(
            timestamp=ctx.timestamp,
            symbol=ctx.symbol,
            contract=(ctx.decision or {}).get("selected_contracts") if ctx.decision else None,
            strategy=(ctx.decision or {}).get("strategy") if ctx.decision else None,
            decision=(ctx.decision or {}).get("decision") if ctx.decision else None,
            risk_mode=ctx.trading_mode.value,
            confidence=(ctx.decision or {}).get("confidence") if ctx.decision else None,
            agent_reasoning_summaries=summaries,
            red_team_objections=list(ctx.red_team.objections) if ctx.red_team else [],
            risk_guardian_result=ctx.risk_guardian_result,
            outcome=outcome,
            lessons=list(ctx.missing_data),
            dry_run=True,
            cycle_id=ctx.cycle_id,
        )
        try:
            self.memory.record(record)
        except Exception as exc:
            logger.error("Failed to persist trade memory: %s", type(exc).__name__)
        try:
            self.audit.log_event(
                AuditEventType.DECISION,
                AuditSeverity.INFO,
                ctx.symbol,
                f"Cycle outcome {outcome.value}",
                {"cycle_id": ctx.cycle_id, "dry_run": True},
            )
        except Exception:
            pass
