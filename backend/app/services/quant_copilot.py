"""Quant Copilot — answers from actual backend state. LLM is explanatory only. Never executes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from inspect import isawaitable

from app.config import settings
from app.llm.service import get_llm_service
from app.models.schemas import DATA_UNAVAILABLE, LLM_UNAVAILABLE, CopilotResponse
from app.risk.risk_bodyguard import RiskBodyguard
from app.services.market_intelligence import MarketIntelligenceService
from app.services.portfolio_greeks import PortfolioGreeksService

_greeks_svc = PortfolioGreeksService()
_intel_svc = MarketIntelligenceService()
_bodyguard = RiskBodyguard()

INTENTS = (
    "portfolio",
    "positions",
    "delta",
    "proposed",
    "rejected",
    "risks",
    "volatility",
    "protection",
    "critical",
    "debate",
    "red_team",
    "orders",
)


def classify_intent(question: str) -> str:
    q = (question or "").strip().lower()
    if "delta" in q:
        return "delta"
    if "red team" in q or "red-team" in q or "objection" in q:
        return "red_team"
    if "debate" in q:
        return "debate"
    if "position" in q:
        return "positions"
    if "order" in q:
        return "orders"
    if "portfolio" in q or "account" in q:
        return "portfolio"
    if "reject" in q:
        return "rejected"
    if "propos" in q:
        return "proposed"
    if "protection" in q:
        return "protection"
    if "critical" in q:
        return "critical"
    if "volatil" in q:
        return "volatility"
    if "risk" in q:
        return "risks"
    return "unknown"


def _val(value: Any, unavailable: List[str], key: str) -> str:
    if value is None or value == "" or value == DATA_UNAVAILABLE:
        unavailable.append(key)
        return DATA_UNAVAILABLE
    return str(value)


async def _maybe_await(value: Any) -> Any:
    if isawaitable(value):
        return await value
    return value


def _serialize(item: Any) -> Any:
    if item is None:
        return None
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    if hasattr(item, "to_dict"):
        return item.to_dict()
    if isinstance(item, dict):
        return item
    return str(item)


async def collect_copilot_state(engine: Any) -> Dict[str, Any]:
    """Assemble live backend state. Missing sources stay None / DATA_UNAVAILABLE."""
    unavailable: List[str] = []
    account = None
    try:
        account = await engine.alpaca_service.get_account()
    except Exception:
        account = None
    from app.services.demo_ledger import demo_portfolio, get_demo_ledger

    demo = None
    try:
        demo = await demo_portfolio(engine)
    except Exception:
        demo = None
    account = demo or account
    if not account:
        unavailable.append("alpaca_account")

    raw_positions = []
    if demo:
        positions = list(demo.get("positions") or [])
        orders = get_demo_ledger().list_trades()
    else:
        positions = []
        try:
            raw_positions = await _maybe_await(engine.position_manager.get_open_positions())
            positions = [_serialize(p) for p in (raw_positions or [])]
        except Exception:
            unavailable.append("positions")
            raw_positions = []
        orders = []
        try:
            raw_orders = await _maybe_await(engine.order_tracker.get_all_tracked_orders())
            orders = [_serialize(o) for o in (raw_orders or [])]
        except Exception:
            unavailable.append("orders")

    snaps = []
    for position in raw_positions or []:
        occ = getattr(position, "symbol", None)
        if not occ:
            continue
        try:
            snap = await engine.alpaca_service.get_option_snapshot(occ)
        except Exception:
            snap = None
        if snap:
            snaps.append(snap)
    greeks = _greeks_svc.snapshot(
        positions=raw_positions or [],
        option_snapshots=snaps,
    ).model_dump()

    symbol = None
    decision = engine.last_decision or {}
    if isinstance(decision, dict):
        symbol = decision.get("symbol") or (decision.get("selected_contracts") or {}).get("symbol")
    symbol = symbol or (settings.watchlist[0] if settings.watchlist else "SPY")

    market: Dict[str, Any] = {}
    try:
        quote = await engine.alpaca_service.get_latest_quote(symbol)
        market["quote"] = quote.model_dump(mode="json")
        intel_real = {}
        if quote.bid is not None and quote.ask is not None:
            intel_real["bid_ask_spread"] = str(round(quote.ask - quote.bid, 6))
        clock = await engine.alpaca_service.get_market_clock()
        if clock.is_open is not None:
            intel_real["market_session"] = "open" if clock.is_open else "closed"
        intel = _intel_svc.snapshot(symbol, real_data=intel_real or None)
        market["intelligence"] = intel.model_dump()
        market["symbol"] = symbol
    except Exception:
        unavailable.append("market_data")
        market = {"symbol": symbol, "quote": None, "intelligence": None}

    dd = engine.drawdown_guardian.state
    bodyguard = _bodyguard.assess(
        raw_positions or [],
        trading_mode=dd.current_mode if dd else None,
        drawdown=dd.drawdown_percentage if dd else 0.0,
    )

    memory = []
    try:
        memory = [r.model_dump(mode="json") for r in engine.trade_memory.list_records(limit=5)]
    except Exception:
        unavailable.append("post_trade_memory")

    latest_debate = engine.last_debate
    if not latest_debate:
        debates = await _maybe_await(engine.debate_engine.get_all_debates())
        if debates:
            latest_debate = debates[-1].to_dict()

    return {
        "account": account,
        "portfolio": demo,
        "positions": positions,
        "orders": orders,
        "greeks": greeks,
        "market": market,
        "market_intelligence": market.get("intelligence"),
        "last_decision": engine.last_decision,
        "last_rejection_reasons": list(engine.last_rejection_reasons or []),
        "last_red_team": engine.last_red_team,
        "last_debate": latest_debate,
        "last_bodyguard": engine.last_bodyguard or bodyguard.model_dump(),
        "bodyguard": bodyguard.model_dump(),
        "current_mode": dd.current_mode.value if dd else None,
        "current_drawdown": dd.drawdown_percentage if dd else None,
        "drawdown_state": dd.to_dict() if dd else None,
        "memory": memory,
        "dry_run": True,
        "paper_trading": True,
        "can_execute": False,
        "collect_unavailable": unavailable,
    }


class QuantCopilot:
    """Rule-based copilot over engine/portfolio/risk state, with optional LLM narration."""

    def answer(self, question: str, state: Dict[str, Any]) -> CopilotResponse:
        return self._deterministic(question, state)

    async def answer_async(self, question: str, state: Dict[str, Any]) -> CopilotResponse:
        base = self._deterministic(question, state)
        facts = {
            "question": question,
            "intent": base.intent,
            "deterministic_answer": base.answer,
            "unavailable": base.unavailable,
            "can_execute": False,
            "account_present": bool(state.get("account")),
            "positions_count": len(state.get("positions") or []),
            "current_mode": state.get("current_mode"),
            "current_drawdown": state.get("current_drawdown"),
            "greeks_availability": (state.get("greeks") or {}).get("availability"),
            "decision": (state.get("last_decision") or {}).get("decision") if isinstance(state.get("last_decision"), dict) else None,
        }
        advisory = await get_llm_service().advise(role="quant_copilot", facts=facts)
        if advisory.status == LLM_UNAVAILABLE:
            return base.model_copy(
                update={
                    "llm_status": LLM_UNAVAILABLE,
                    "llm_provider": LLM_UNAVAILABLE,
                    "can_execute": False,
                }
            )
        answer = base.answer
        if advisory.summary:
            answer = f"{base.answer} LLM explanation (advisory only, not an order): {advisory.summary}"
        return CopilotResponse(
            question=question,
            answer=answer,
            used_actual_state=True,
            unavailable=base.unavailable,
            llm_provider=advisory.provider,
            llm_status=advisory.status,
            intent=base.intent,
            can_execute=False,
            sources=base.sources,
        )

    def _deterministic(self, question: str, state: Dict[str, Any]) -> CopilotResponse:
        intent = classify_intent(question)
        handlers = {
            "portfolio": self._portfolio,
            "positions": self._positions,
            "delta": self._delta,
            "proposed": self._proposed,
            "rejected": self._rejected,
            "risks": self._risks,
            "volatility": self._volatility,
            "protection": self._protection,
            "critical": self._critical,
            "debate": self._debate,
            "red_team": self._red_team,
            "orders": self._orders,
        }
        handler = handlers.get(intent, self._unknown)
        answer, unavailable, sources = handler(state)
        unavailable = list(dict.fromkeys(list(state.get("collect_unavailable") or []) + unavailable))
        return CopilotResponse(
            question=question,
            answer=answer,
            used_actual_state=True,
            unavailable=unavailable,
            llm_provider=LLM_UNAVAILABLE,
            llm_status=LLM_UNAVAILABLE,
            intent=intent,
            can_execute=False,
            sources=sources,
        )

    def _portfolio(self, state: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
        unavailable: List[str] = []
        account = state.get("account") or {}
        snapshot = state.get("portfolio") or {}
        cash = account.get("cash") if account else snapshot.get("cash")
        equity = account.get("equity") if account else snapshot.get("current_equity")
        pv = account.get("portfolio_value") if account else snapshot.get("portfolio_value")
        bp = account.get("buying_power") if account else snapshot.get("buying_power")
        if not account and not snapshot:
            return f"Current portfolio is {DATA_UNAVAILABLE}.", ["alpaca_account"], []
        parts = [
            f"Cash: {_val(cash, unavailable, 'cash')}.",
            f"Equity: {_val(equity, unavailable, 'equity')}.",
            f"Portfolio value: {_val(pv, unavailable, 'portfolio_value')}.",
            f"Buying power: {_val(bp, unavailable, 'buying_power')}.",
            "Paper trading only. Copilot cannot execute trades.",
        ]
        return " ".join(parts), unavailable, ["alpaca_account"]

    def _positions(self, state: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
        positions = state.get("positions")
        if positions is None:
            return f"Positions are {DATA_UNAVAILABLE}.", ["positions"], []
        if not positions:
            return "You have 0 open positions.", [], ["positions"]
        lines = []
        for pos in positions[:20]:
            if pos.get("option_type") or pos.get("strike"):
                lines.append(
                    f"{pos.get('symbol')} {pos.get('option_type')} strike={pos.get('strike')} "
                    f"qty={pos.get('quantity')} expiry={pos.get('expiration')}"
                )
            else:
                lines.append(
                    f"{pos.get('symbol')} qty={pos.get('quantity')} avg={pos.get('avg_entry')} "
                    f"pnl={pos.get('unrealized_pnl')}"
                )
        return f"Open positions ({len(positions)}): " + "; ".join(lines) + ".", [], ["positions"]

    def _orders(self, state: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
        orders = state.get("orders")
        if orders is None:
            return f"Orders are {DATA_UNAVAILABLE}.", ["orders"], []
        if not orders:
            return "There are 0 tracked orders in this session.", [], ["orders"]
        return (
            f"Tracked orders ({len(orders)}). Latest status: {orders[-1].get('status')}. "
            "Copilot cannot place, cancel, or modify orders."
        ), [], ["orders"]

    def _delta(self, state: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
        greeks = state.get("greeks") or {}
        if greeks.get("availability") == "AVAILABLE" and greeks.get("portfolio_delta") is not None:
            quality = greeks.get("quality") or "REAL"
            return (
                f"Current portfolio delta is {greeks.get('portfolio_delta')} ({quality})."
            ), [], ["greeks"]
        return (
            f"Portfolio delta is {DATA_UNAVAILABLE}. No real option Greek feed was supplied for open positions."
        ), ["portfolio_delta"], ["greeks"]

    def _proposed(self, state: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
        decision = state.get("last_decision") or {}
        if not decision:
            return "No trade has been proposed in the current session.", ["last_decision"], []
        reasoning = decision.get("reasoning") or DATA_UNAVAILABLE
        unavailable = [] if decision.get("reasoning") else ["decision_reasoning"]
        return (
            f"The last proposal was {decision.get('decision', DATA_UNAVAILABLE)}. "
            f"Reasoning: {reasoning}. Proposed size: {decision.get('proposed_size', DATA_UNAVAILABLE)}. "
            "This is not an execution instruction."
        ), unavailable, ["last_decision"]

    def _rejected(self, state: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
        reasons = state.get("last_rejection_reasons") or []
        if reasons:
            return (
                "The trade was rejected by Risk Guardian: " + "; ".join(str(r) for r in reasons) + "."
            ), [], ["last_rejection_reasons"]
        return "No Risk Guardian rejection is on record for this session.", ["rejection_reasons"], []

    def _risks(self, state: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
        unavailable: List[str] = []
        mode = _val(state.get("current_mode"), unavailable, "current_mode")
        dd = state.get("current_drawdown")
        dd_txt = f"{dd:.2%}" if isinstance(dd, (int, float)) else DATA_UNAVAILABLE
        if dd is None:
            unavailable.append("current_drawdown")
        red = state.get("last_red_team") or {}
        flags = red.get("risk_flags") or state.get("red_team_flags") or []
        objections = red.get("objections") or []
        body = state.get("bodyguard") or {}
        parts = [
            f"Risk mode is {mode}. Drawdown is {dd_txt}.",
            f"Red Team flags: {flags or DATA_UNAVAILABLE}.",
            f"Bodyguard action: {body.get('action', DATA_UNAVAILABLE)} (advisory only).",
            "Deterministic Risk Guardian remains the final authority. Copilot cannot execute.",
        ]
        if objections:
            parts.append("Red Team objections: " + "; ".join(str(o) for o in objections[:5]) + ".")
        if not flags:
            unavailable.append("red_team_flags")
        return " ".join(parts), unavailable, ["drawdown_guardian", "red_team", "risk_bodyguard"]

    def _volatility(self, state: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
        unavailable: List[str] = []
        greeks = state.get("greeks") or {}
        intel = state.get("market_intelligence") or {}
        iv = intel.get("iv", DATA_UNAVAILABLE)
        vega = greeks.get("portfolio_vega")
        if iv == DATA_UNAVAILABLE or iv is None:
            unavailable.append("iv")
        if vega is None or greeks.get("availability") != "AVAILABLE":
            unavailable.append("portfolio_vega")
            vega_txt = DATA_UNAVAILABLE
        else:
            vega_txt = str(vega)
        return (
            f"IV is {iv}. Portfolio vega is {vega_txt}. "
            "No invented P&L path is applied. If vega were known and positive, IV expansion would tend to help; "
            "if negative, it would tend to hurt. That is not a live forecast without real vega."
        ), unavailable, ["greeks", "market_intelligence"]

    def _protection(self, state: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
        unavailable: List[str] = []
        mode = _val(state.get("current_mode"), unavailable, "current_mode")
        dd = state.get("current_drawdown")
        dd_txt = f"{dd:.2%}" if isinstance(dd, (int, float)) else DATA_UNAVAILABLE
        if dd is None:
            unavailable.append("current_drawdown")
        in_protection = str(mode).lower() == "protection"
        return (
            f"Current mode is {mode}. Drawdown is {dd_txt}. "
            f"You are {'in' if in_protection else 'not in'} PROTECTION mode. "
            "Drawdown Guardian enters PROTECTION near 10% drawdown and tightens confidence requirements. "
            "Mode is calculated, not set by the Copilot or LLM."
        ), unavailable, ["drawdown_guardian"]

    def _critical(self, state: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
        unavailable: List[str] = []
        mode = _val(state.get("current_mode"), unavailable, "current_mode")
        dd = state.get("current_drawdown")
        dd_txt = f"{dd:.2%}" if isinstance(dd, (int, float)) else DATA_UNAVAILABLE
        if dd is None:
            unavailable.append("current_drawdown")
        freeze = str(mode).lower() == "critical"
        return (
            f"Current mode is {mode}. Drawdown is {dd_txt}. "
            f"CRITICAL blocks new trades: {freeze}. "
            "Drawdown Guardian enters CRITICAL near 15% drawdown. Copilot cannot override this."
        ), unavailable, ["drawdown_guardian"]

    def _debate(self, state: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
        debate = state.get("last_debate") or {}
        decision = state.get("last_decision") or {}
        if not debate and not decision:
            return f"Latest AI debate is {DATA_UNAVAILABLE}.", ["last_debate"], []
        outputs = debate.get("agent_outputs") or {}
        names = list(outputs.keys()) if outputs else []
        final = debate.get("final_decision") or decision
        dec = (final or {}).get("decision", DATA_UNAVAILABLE) if isinstance(final, dict) else DATA_UNAVAILABLE
        rg = debate.get("risk_guardian_result") or {}
        return (
            f"Latest debate agents: {names or DATA_UNAVAILABLE}. "
            f"Decision agent output: {dec}. "
            f"Risk Guardian: {(rg or {}).get('decision', DATA_UNAVAILABLE)}. "
            "LLM did not authorize this outcome."
        ), ([] if debate else ["last_debate"]), ["last_debate", "last_decision"]

    def _red_team(self, state: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
        red = state.get("last_red_team")
        if not red:
            return f"Red Team objections are {DATA_UNAVAILABLE}.", ["last_red_team"], []
        objections = red.get("objections") or []
        flags = red.get("risk_flags") or []
        severity = red.get("severity", DATA_UNAVAILABLE)
        if not objections:
            return (
                f"Red Team ran (severity {severity}) with flags {flags or DATA_UNAVAILABLE} "
                "and no stored objections."
            ), ["red_team_objections"], ["last_red_team"]
        return (
            f"Red Team severity {severity}. Flags: {flags}. "
            f"Objections: {'; '.join(str(o) for o in objections)}. "
            "Red Team is advisory only and cannot bypass Risk Guardian."
        ), [], ["last_red_team"]

    def _unknown(self, state: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
        return (
            "I can answer from actual backend state about portfolio, positions, orders, delta, "
            "proposed trades, rejections, risks, volatility, PROTECTION/CRITICAL mode, the latest debate, "
            "and Red Team objections. I cannot execute trades."
        ), ["unmatched_intent"], []
