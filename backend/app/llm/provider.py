"""LLM provider interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class LlmProvider(ABC):
    """External chat-completion provider. Implementations must not log secrets."""

    name: str = "none"

    @abstractmethod
    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return a JSON object. Raise LlmUnavailable on failure."""
