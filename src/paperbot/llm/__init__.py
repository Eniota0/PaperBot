"""LLM provider interface."""
from __future__ import annotations

from typing import Protocol


class LLMError(Exception):
    """The model answered, but the answer was unusable."""


class LLMUnavailable(LLMError):
    """The model server cannot be used at all; the pipeline must abort."""


class LLMProvider(Protocol):
    def complete_json(self, prompt: str, schema: dict) -> dict: ...
