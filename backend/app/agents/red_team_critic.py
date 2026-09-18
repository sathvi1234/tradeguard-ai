"""Red Team Critic — advisory challenge before Risk Guardian."""

from typing import Any, Dict, List, Optional

from app.llm.service import get_llm_service
from app.models.schemas import LLM_UNAVAILABLE, RedTeamResult, Severity
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RedTeamCritic:
    """Looks for failure modes. Cannot override Risk Guardian."""

    async def critique(
        self,
        *,
        symbol: str,
        decision: Optional[Dict[str, Any]] = None,
        confidence: float = 0.0,
        scenarios: Optional[List] = None,
        missing_data: Optional[List[str]] = None,
        data_stale: bool = False,
        contract: Optional[Dict[str, Any]] = None,
        current_positions: int = 0,
        proposed_size: float = 0.0,
        portfolio_value: Optional[float] = None,
        risk_reward: Optional[float] = None,
    ) -> RedTeamResult:
        flags: List[str] = []
        objections: List[str] = []
        missing = list(missing_data or [])
        severity = Severity.LOW

        decision = decision or {}
        if not decision:
            missing.append("decision")
            objections.append("No decision payload to challenge")
            severity = Severity.HIGH

        if missing:
            flags.append("missing_information")
            objections.append("Mandatory information missing")
            severity = Severity.HIGH

        if data_stale:
            flags.append("stale_data")
            objections.append("Quotes or context may be stale")
            severity = Severity.CRITICAL

        if confidence >= 0.9 and (missing or not scenarios):
            flags.append("excessive_confidence")
            objections.append("Confidence is high relative to available evidence")
            severity = Severity.HIGH

        evidence_ok = True
        for scenario in scenarios or []:
            if hasattr(scenario, "evidence_available") and not scenario.evidence_available:
                evidence_ok = False
        if not evidence_ok:
            flags.append("weak_evidence")
            objections.append("StrategyBrain marked evidence unavailable")
            severity = Severity.HIGH

        if risk_reward is not None and risk_reward < 1.0:
            flags.append("unfavorable_risk_reward")
            objections.append("Risk/reward below 1.0")
            if severity == Severity.LOW:
                severity = Severity.MEDIUM

        if contract is None and decision.get("decision") not in (None, "no_trade"):
            flags.append("invalid_option_contract")
            objections.append("No contract attached to a trade proposal")
            missing.append("contract")
            severity = Severity.CRITICAL

        if current_positions >= 8:
            flags.append("portfolio_concentration")
            objections.append("High open-position count")
            if severity == Severity.LOW:
                severity = Severity.MEDIUM

        if portfolio_value and proposed_size and proposed_size / portfolio_value > 0.20:
            flags.append("excessive_exposure")
            objections.append("Proposed size is a large fraction of portfolio")
            severity = Severity.HIGH

        vol_note = None
        for scenario in scenarios or []:
            risks = getattr(scenario, "risks", None) or []
            if any("enough data" in str(item).lower() or "not available" in str(item).lower() for item in risks):
                vol_note = "Volatility could not be fully confirmed from available bars."
        if vol_note:
            flags.append("volatility_risk")
            objections.append(vol_note)

        if not objections:
            objections.append("No material objection identified.")

        approved = severity not in (Severity.HIGH, Severity.CRITICAL) and not missing
        advisory = await get_llm_service().advise(
            role="red_team_critic",
            facts={
                "symbol": symbol,
                "decision": (decision or {}).get("decision"),
                "confidence": confidence,
                "missing_data": missing,
                "data_stale": data_stale,
                "flags": flags,
                "objections": objections,
                "contract_present": contract is not None,
            },
        )
        extra_objections = [f"LLM advisory: {p}" for p in advisory.points]
        extra_summary = advisory.summary
        return RedTeamResult(
            approved_for_review=approved,
            risk_flags=list(dict.fromkeys(flags)),
            objections=list(dict.fromkeys(objections + extra_objections)),
            missing_information=list(dict.fromkeys(missing)),
            severity=severity,
            confidence=min(confidence, 0.5 if missing else confidence),
            advisory_only=True,
            llm_status=advisory.status if advisory else LLM_UNAVAILABLE,
            llm_advisory=extra_summary,
        )
