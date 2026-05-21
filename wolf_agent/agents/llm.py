from __future__ import annotations

import json
import os
import re
from typing import Optional

import httpx

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"


class LLMClient:
    """OpenAI-compatible LLM client."""

    def __init__(self):
        self.api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        base_url = os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)
        self.base_url = base_url.rstrip("/")
        self.model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    def _call(self, messages: list[dict], temperature: float, max_tokens: int) -> str:
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stop": ["\n\n"],
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def speak(self, messages: list[dict]) -> tuple[str, str]:
        """Returns (content, strategy_summary)."""
        text = self._call(messages, temperature=0.8, max_tokens=300)
        # Try to parse JSON; fall back to plain text
        if text.startswith("{"):
            try:
                data = json.loads(text)
                return data.get("content", text), data.get("strategy_summary", "")
            except json.JSONDecodeError:
                pass
        return text[:200], ""

    def vote(self, messages: list[dict]) -> int:
        text = self._call(messages, temperature=0.3, max_tokens=20)
        nums = re.findall(r"\d+", text)
        return int(nums[0]) if nums else 0

    def act(self, messages: list[dict]) -> dict:
        """For structured night actions (kill, investigate, witch)."""
        text = self._call(messages, temperature=0.3, max_tokens=100)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}
