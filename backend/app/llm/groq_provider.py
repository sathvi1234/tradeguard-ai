"""Groq OpenAI-compatible chat completions via httpx."""

import json
from typing import Any, Dict, Optional

import httpx

from app.llm.exceptions import LlmUnavailable
from app.llm.provider import LlmProvider
from app.utils.logging import get_logger

logger = get_logger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(LlmProvider):
    name = "groq"

    def __init__(self, api_key: str, model: str, timeout: float = 8.0) -> None:
        self._api_key = api_key.strip()
        self._model = model
        self._timeout = timeout
        if not self._api_key:
            raise LlmUnavailable("LLM_UNAVAILABLE")

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model or self._model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(GROQ_CHAT_URL, headers=headers, json=payload)
        except httpx.RequestError:
            logger.error("Groq request failed")
            raise LlmUnavailable("LLM_UNAVAILABLE") from None

        if response.status_code in (401, 403):
            raise LlmUnavailable("LLM_UNAVAILABLE")
        if response.status_code == 429:
            raise LlmUnavailable("LLM_UNAVAILABLE")
        if response.status_code >= 400:
            logger.error("Groq returned HTTP %s", response.status_code)
            raise LlmUnavailable("LLM_UNAVAILABLE")

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except (ValueError, KeyError, IndexError, TypeError):
            raise LlmUnavailable("LLM_UNAVAILABLE") from None
        if not isinstance(parsed, dict):
            raise LlmUnavailable("LLM_UNAVAILABLE")
        return parsed
