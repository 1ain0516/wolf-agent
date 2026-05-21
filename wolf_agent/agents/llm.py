from __future__ import annotations

import json
import os
import re
import time

import httpx

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
MAX_RETRIES = 3
RETRY_DELAY = 5


class LLMClient:
    """OpenAI-compatible LLM client with retry logic."""

    def __init__(self):
        self.api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        base_url = os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)
        self.base_url = base_url.rstrip("/")
        self.model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    def _call(self, messages: list[dict], temperature: float, max_tokens: int) -> str:
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = httpx.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                    timeout=120,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
            except (httpx.TimeoutException, httpx.ReadTimeout) as e:
                last_exc = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                    continue
            except httpx.HTTPStatusError as e:
                last_exc = e
                if attempt < MAX_RETRIES - 1 and e.response.status_code >= 500:
                    time.sleep(RETRY_DELAY)
                    continue
                raise
        raise last_exc  # type: ignore

    def speak(self, messages: list[dict]) -> tuple[str, str]:
        text = self._call(messages, temperature=0.0, max_tokens=300)
        if text.startswith("{"):
            try:
                data = json.loads(text)
                return data.get("content", text)[:200], data.get("strategy_summary", "")[:80]
            except json.JSONDecodeError:
                pass
        return text[:200], ""

    def vote(self, messages: list[dict]) -> int:
        text = self._call(messages, temperature=0.0, max_tokens=20)
        nums = re.findall(r"\d+", text)
        return int(nums[0]) if nums else 0

    def act(self, messages: list[dict]) -> dict:
        text = self._call(messages, temperature=0.0, max_tokens=100)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}
