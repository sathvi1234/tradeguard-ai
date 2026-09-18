"""Central LLM service. Advisory only. Never holds Alpaca credentials in prompts."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from app.config import settings
from app.llm.exceptions import LlmUnavailable
from app.llm.groq_provider import GroqProvider
from app.llm.models import LlmAdvisory
from app.llm.provider import LlmProvider
from app.models.schemas import LLM_UNAVAILABLE
from app.utils.logging import get_logger

logger = get_logger(__name__)

SYSTEM_RULES = (
    "You are an advisory reasoning assistant for a paper-trading options system. "
    "Output JSON only with keys: summary (string), points (array of strings), advisory_only (true). "
    "You MUST NOT execute orders, request live trading, or override RiskGuardian, "
    "DrawdownGuardian, CRITICAL mode, stale-data blocks, or DRY_RUN. "
    "Use only the facts provided. Do not invent quotes, option contracts, Greeks, IV, news, or prices. "
    "If a field is missing, say it is unavailable. advisory_only must be true."
)

_FORBIDDEN = (
    "execute_order",
    "live_trading",
    "bypass_risk",
    "override_critical",
    "submit_order",
    "place_order",
)

_service: Optional["LlmService"] = None


class LlmService:
    def __init__(self, provider: Optional[LlmProvider] = None) -> None:
        self.provider = provider

    @classmethod
    def from_settings(cls) -> "LlmService":
        if not settings.llm_configured():
            return cls(provider=None)
        try:
            provider = GroqProvider(settings.llm_api_key, settings.llm_model)
        except LlmUnavailable:
            return cls(provider=None)
        return cls(provider=provider)

    @property
    def available(self) -> bool:
        return self.provider is not None

    async def advise(self, *, role: str, facts: Dict[str, Any]) -> LlmAdvisory:
        if self.provider is None:
            return LlmAdvisory(status=LLM_UNAVAILABLE, provider=LLM_UNAVAILABLE, error=LLM_UNAVAILABLE)
        user = (
            f"Role: {role}. Advisory only.\n"
            f"Facts (do not invent beyond this JSON):\n{json.dumps(facts, default=str)[:4000]}"
        )
        try:
            raw = await self.provider.complete_json(system=SYSTEM_RULES, user=user, model=settings.llm_model)
        except LlmUnavailable:
            return LlmAdvisory(status=LLM_UNAVAILABLE, provider=LLM_UNAVAILABLE, error=LLM_UNAVAILABLE)
        except Exception:
            logger.error("LLM advise failed for role=%s", role)
            return LlmAdvisory(status=LLM_UNAVAILABLE, provider=LLM_UNAVAILABLE, error=LLM_UNAVAILABLE)

        if any(k in raw for k in _FORBIDDEN):
            raw = {k: v for k, v in raw.items() if k not in _FORBIDDEN}

        summary = raw.get("summary")
        points = raw.get("points") if isinstance(raw.get("points"), list) else []
        points = [str(p) for p in points[:8]]
        return LlmAdvisory(
            status="AVAILABLE",
            provider=self.provider.name,
            model=settings.llm_model,
            advisory_only=True,
            summary=str(summary) if summary is not None else None,
            points=points,
            cannot_override_risk=True,
        )


def get_llm_service() -> LlmService:
    global _service
    if _service is None:
        _service = LlmService.from_settings()
    return _service


def reset_llm_service(service: Optional[LlmService] = None) -> None:
    global _service
    _service = service
