"""LLM errors. Messages must never include credentials."""


class LlmError(Exception):
    """Base LLM error."""


class LlmUnavailable(LlmError):
    """Provider missing, timed out, or returned an unusable response."""
