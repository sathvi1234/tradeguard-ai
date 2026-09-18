"""Restricted LLM reviewer. Never executes, never approves, never raises size."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.config import settings
from app.llm.exceptions import LlmUnavailable
from app.llm.models import LLMReview, LLMReviewAction
from app.llm.service import get_llm_service
from app.models.schemas import LLM_UNAVAILABLE
from app.utils.logging import get_logger

logger = get_logger(__name__)

MAX_REDUCTION_PCT = 0.50
ALLOWED_ACTIONS = {LLMReviewAction.VETO.value, LLMReviewAction.SHRINK.value, LLMReviewAction.NO_CHANGE.value}

REVIEW_SYSTEM = (
    "You are a restricted risk reviewer. Output JSON only with keys: "
    "action (VETO|SHRINK|NO_CHANGE), reason (string), risk_flags (string array), "
    "suggested_reduction_pct (number 0 to 0.5), confidence (number 0 to 1). "
    "You cannot approve trades, increase size, execute orders, or override Risk Guardian. "
    "You cannot override stale data, MARKET_CLOSED, or CRITICAL drawdown. "
    "If unsure, return NO_CHANGE. advisory_only implied."
)

_SECRET_FRAGMENTS = (
    "api_key",
    "secret",
    "password",
    "token",
    "authorization",
    "database_url",
    "dsn",
    "alpaca_api",
    "alpaca_secret",
    "credential",
    "bearer",
)


def sanitize_for_llm(value: Any) -> Any:
    """Strip secrets, credentials, and order endpoints before any LLM call."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in _SECRET_FRAGMENTS):
                continue
            if "alpaca" in lowered and "order" in lowered:
                continue
            out[str(key)] = sanitize_for_llm(item)
        return out
    if isinstance(value, list):
        return [sanitize_for_llm(item) for item in value]
    if isinstance(value, str):
        lowered = value.lower()
        if "sk-" in value or "postgresql" in lowered or "/v2/orders" in lowered:
            return "[redacted]"
        return value
    return value


def _fail_safe(reason: str, model: str = LLM_UNAVAILABLE) -> LLMReview:
    return LLMReview(
        action=LLMReviewAction.NO_CHANGE.value,
        reason=reason,
        risk_flags=["llm_fail_safe"],
        suggested_reduction_pct=0.0,
        confidence=0.0,
        model=model,
        timestamp=datetime.now(timezone.utc).isoformat(),
        fail_safe=True,
        status=LLM_UNAVAILABLE,
    )


def _cap_reduction(raw: Any) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if value < 0:
        return 0.0
    return min(value, MAX_REDUCTION_PCT)


class RestrictedLLMReviewer:
    """LLM may only VETO, SHRINK, or NO_CHANGE after Risk Guardian approval."""

    max_reduction_pct = MAX_REDUCTION_PCT

    async def review(self, *, proposal: Dict[str, Any], first_risk: Dict[str, Any]) -> LLMReview:
        facts = sanitize_for_llm(
            {
                "proposal": proposal,
                "risk_guardian": first_risk,
                "constraints": {
                    "allowed_actions": sorted(ALLOWED_ACTIONS),
                    "max_reduction_pct": MAX_REDUCTION_PCT,
                    "cannot_approve": True,
                    "cannot_increase_size": True,
                    "cannot_execute": True,
                    "cannot_override_risk_guardian": True,
                },
            }
        )
        blob = json.dumps(facts, default=str)
        for banned in ("alpaca_api_key", "alpaca_secret", "database_url", settings.alpaca_api_key, settings.llm_api_key):
            if banned and isinstance(banned, str) and banned.strip() and banned.strip() in blob:
                return _fail_safe("Refused to send secrets to the LLM.")
        service = get_llm_service()
        if not service.available or service.provider is None:
            return _fail_safe("LLM unavailable. Fail safe: NO_CHANGE. Risk Guardian remains final.")
        user = f"Review this risk-approved proposal. JSON facts:\n{blob[:3500]}"
        try:
            raw = await service.provider.complete_json(system=REVIEW_SYSTEM, user=user, model=settings.llm_model)
        except LlmUnavailable:
            return _fail_safe("LLM timed out or API unavailable. Fail safe: NO_CHANGE.")
        except Exception:
            logger.error("Restricted LLM reviewer failed")
            return _fail_safe("LLM error. Fail safe: NO_CHANGE.")
        if not isinstance(raw, dict):
            return _fail_safe("Invalid LLM output. Fail safe: NO_CHANGE.")
        action = str(raw.get("action") or "").upper().replace(" ", "_")
        if action in {"APPROVE", "ALLOW", "INCREASE", "EXECUTE"}:
            return _fail_safe("LLM attempted a forbidden action. Ignored. Fail safe: NO_CHANGE.")
        if action not in ALLOWED_ACTIONS:
            return _fail_safe("Invalid LLM action. Fail safe: NO_CHANGE.")
        reduction = _cap_reduction(raw.get("suggested_reduction_pct"))
        if action == LLMReviewAction.SHRINK.value and reduction <= 0:
            action = LLMReviewAction.NO_CHANGE.value
        flags = raw.get("risk_flags") if isinstance(raw.get("risk_flags"), list) else []
        try:
            confidence = min(max(float(raw.get("confidence") or 0), 0.0), 1.0)
        except (TypeError, ValueError):
            confidence = 0.0
        model_name = settings.llm_model or (service.provider.name if service.provider else LLM_UNAVAILABLE)
        return LLMReview(
            action=action,
            reason=str(raw.get("reason") or "Restricted reviewer response."),
            risk_flags=[str(item) for item in flags[:12]],
            suggested_reduction_pct=reduction if action == LLMReviewAction.SHRINK.value else 0.0,
            confidence=confidence,
            model=str(model_name),
            timestamp=datetime.now(timezone.utc).isoformat(),
            fail_safe=False,
            status="AVAILABLE",
        )
