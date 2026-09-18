"""Default test fixtures. LLM is disabled unless a test injects a fake provider."""

import pytest

from app.llm.service import LlmService, reset_llm_service


@pytest.fixture(autouse=True)
def _disable_live_llm():
    reset_llm_service(LlmService(provider=None))
    yield
    reset_llm_service(None)
