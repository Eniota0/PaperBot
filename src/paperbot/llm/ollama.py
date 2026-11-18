"""Ollama implementation of LLMProvider (local models)."""
from __future__ import annotations

import json

import httpx

from paperbot.llm import LLMError, LLMUnavailable


class OllamaProvider:
    def __init__(self, url: str, model: str, timeout_s: float = 180, client: httpx.Client | None = None):
        self.url = url.rstrip("/")
        self.model = model
        self.client = client or httpx.Client(timeout=timeout_s)

    def complete_json(self, prompt: str, schema: dict) -> dict:
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "format": schema,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        try:
            resp = self.client.post(f"{self.url}/api/chat", json=body)
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise LLMUnavailable(f"Cannot reach Ollama at {self.url}. Is Ollama running? ({e})") from e
        except httpx.HTTPError as e:
            raise LLMError(f"Ollama request failed: {e}") from e
        if resp.status_code == 404:
            raise LLMUnavailable(
                f"Ollama model '{self.model}' not found. Run: ollama pull {self.model}"
            )
        if resp.status_code >= 400:
            raise LLMError(f"Ollama error {resp.status_code}: {resp.text[:200]}")
        try:
            content = resp.json()["message"]["content"]
            data = json.loads(content)
        except (ValueError, KeyError, TypeError) as e:
            raise LLMError(f"Ollama returned invalid JSON: {e}") from e
        if not isinstance(data, dict):
            raise LLMError("Ollama returned JSON that is not an object")
        return data
