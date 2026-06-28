"""Production LLM-as-Judge clients.

`AnthropicJudgeClient` implements the `JudgeClient` protocol (a `complete(prompt)
-> str` method, see `evaluators/llm.py`) by calling the Anthropic Messages API
via the official `anthropic` SDK.

Per the PRD, the judge model is `claude-haiku-4-5` (cost control for the
high-volume scoring path) at temperature 0.2 for scoring stability. Haiku 4.5
accepts `temperature` but does not support the `effort` / adaptive-thinking
parameters, so those are deliberately not sent.

The SDK client is injectable so the evaluator chain stays fully testable
offline; the real SDK is imported lazily only when no client is supplied.
"""
from __future__ import annotations

from typing import Any, Optional


def _default_client() -> Any:
    # Lazy import so the package works (and tests run) without the SDK installed
    # or an API key present. Resolves credentials from ANTHROPIC_API_KEY etc.
    import anthropic

    return anthropic.Anthropic()


class AnthropicJudgeClient:
    """LLM-as-Judge backed by the Anthropic Messages API."""

    DEFAULT_MODEL = "claude-haiku-4-5"  # PRD §8: cost-controlled judge model

    def __init__(
        self,
        client: Optional[Any] = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ):
        self._client = client
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def _resolve_client(self) -> Any:
        if self._client is None:
            self._client = _default_client()
        return self._client

    def complete(self, prompt: str) -> str:
        client = self._resolve_client()
        resp = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,  # Haiku 4.5 accepts temperature
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
