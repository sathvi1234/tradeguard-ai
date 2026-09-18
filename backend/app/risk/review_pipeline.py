"""RG → restricted LLM reviewer → RG. Only the final Risk Guardian may reach execution."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.llm.models import LLMReview, LLMReviewAction
from app.llm.reviewer import MAX_REDUCTION_PCT, RestrictedLLMReviewer, sanitize_for_llm
from app.risk.risk_guardian import RiskGuardian, RiskGuardianDecision, RiskGuardianResult
from app.trading.audit_logger import AuditEventType, AuditLogger, AuditSeverity

_LAST_PIPELINE: Optional[Dict[str, Any]] = None


def last_review_pipeline() -> Optional[Dict[str, Any]]:
    return _LAST_PIPELINE


def _audit(audit: Optional[AuditLogger], event_type: AuditEventType, symbol: str, message: str, metadata: Dict[str, Any]) -> None:
    if audit is None:
        return
    severity = AuditSeverity.HIGH if event_type in {AuditEventType.RISK_REJECTION, AuditEventType.FINAL_RISK_GUARDIAN} else AuditSeverity.INFO
    audit.log_event(event_type, severity, symbol, message, sanitize_for_llm(metadata))


async def run_review_pipeline(
    *,
    guardian: RiskGuardian,
    symbol: str,
    proposed_size: float,
    rg_kwargs: Dict[str, Any],
    proposal: Optional[Dict[str, Any]] = None,
    first_result: Optional[RiskGuardianResult] = None,
    audit: Optional[AuditLogger] = None,
    quantity: Optional[int] = None,
) -> Dict[str, Any]:
    """First RG, optional LLM (only if approved), then final RG. LLM cannot execute."""
    global _LAST_PIPELINE
    original_size = float(proposed_size)
    original_qty = int(quantity) if isinstance(quantity, int) else None
    proposal_payload = sanitize_for_llm(
        proposal
        or {
            "symbol": symbol,
            "proposed_size": original_size,
            "quantity": original_qty,
        }
    )
    _audit(
        audit,
        AuditEventType.TRADE_PROPOSAL,
        symbol,
        f"Proposal size={original_size}",
        {"proposal": proposal_payload, "live_trading": False},
    )
    first = first_result or await guardian.evaluate_trade(symbol=symbol, proposed_size=original_size, **rg_kwargs)
    first_dict = first.to_dict()
    _audit(
        audit,
        AuditEventType.RISK_APPROVAL if first.decision == RiskGuardianDecision.APPROVED else AuditEventType.RISK_REJECTION,
        symbol,
        f"Risk Guardian first pass {first.decision.value}",
        {"risk_guardian": first_dict, "pass": "first", "live_trading": False},
    )

    skipped_llm = first.decision != RiskGuardianDecision.APPROVED
    reviewer = RestrictedLLMReviewer()
    if skipped_llm:
        review = LLMReview(
            action=LLMReviewAction.NO_CHANGE.value,
            reason="LLM reviewer not invoked. Risk Guardian already blocked the proposal.",
            risk_flags=["risk_guardian_blocked"],
            suggested_reduction_pct=0.0,
            confidence=0.0,
            model="not_invoked",
            timestamp=first_dict.get("timestamp") or "",
            fail_safe=False,
            status="SKIPPED",
        )
    else:
        review = await reviewer.review(proposal=proposal_payload, first_risk=first_dict)

    _audit(
        audit,
        AuditEventType.LLM_REVIEW,
        symbol,
        f"LLM review {review.action}",
        {"llm_review": review.model_dump(), "live_trading": False, "can_execute": False},
    )

    applied_size = original_size
    applied_qty = original_qty
    llm_veto = False
    if not skipped_llm and review.action == LLMReviewAction.VETO.value:
        llm_veto = True
    elif not skipped_llm and review.action == LLMReviewAction.SHRINK.value:
        reduction = min(max(review.suggested_reduction_pct, 0.0), MAX_REDUCTION_PCT)
        applied_size = original_size * (1.0 - reduction)
        if applied_qty is not None:
            applied_qty = max(0, int(applied_qty * (1.0 - reduction)))
        if applied_size > original_size:
            applied_size = original_size
            applied_qty = original_qty

    second_kwargs = dict(rg_kwargs)
    second_kwargs["llm_veto"] = llm_veto
    final = await guardian.evaluate_trade(symbol=symbol, proposed_size=applied_size, **second_kwargs)
    allowed = final.decision == RiskGuardianDecision.APPROVED and applied_size > 0 and not llm_veto
    final_dict = final.to_dict()
    _audit(
        audit,
        AuditEventType.FINAL_RISK_GUARDIAN,
        symbol,
        f"Final Risk Guardian {final.decision.value} allowed_to_execute={allowed}",
        {
            "risk_guardian": final_dict,
            "pass": "final",
            "applied_size": applied_size,
            "allowed_to_execute": allowed,
            "live_trading": False,
            "llm_is_final_authority": False,
        },
    )
    payload = {
        "proposal": proposal_payload,
        "original_size": original_size,
        "applied_size": applied_size,
        "original_quantity": original_qty,
        "applied_quantity": applied_qty,
        "first_risk_guardian": first_dict,
        "llm_review": review.model_dump(),
        "final_risk_guardian": final_dict,
        "allowed_to_execute": allowed,
        "llm_is_final_authority": False,
        "can_approve_trades": False,
        "live_trading": False,
        "max_reduction_pct": MAX_REDUCTION_PCT,
        "risk_guardian_is_final_authority": True,
    }
    _LAST_PIPELINE = payload
    return payload
