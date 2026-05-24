import pytest

from wolf_agent.agents.llm import LLMClient
from wolf_agent.web import app
import wolf_agent.web as web_module


def test_llm_client_rejects_blank_api_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "  \n")
    client = LLMClient()

    with pytest.raises(ValueError, match="Real mode requires"):
        client._call([{"role": "user", "content": "hi"}], temperature=0, max_tokens=1)


def test_live_real_mode_requires_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    client = app.test_client()

    response = client.post(
        "/api/games/live",
        json={"mode": "real", "api_key": "  \n", "memory_enabled": False},
    )

    assert response.status_code == 400
    assert "API Key" in response.get_json()["error"]


def test_live_real_mode_strips_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    started_threads = []

    class DummyThread:
        def __init__(self, *args, **kwargs):
            self.args = kwargs.get("args", ())
            started_threads.append(self)

        def start(self):
            pass

    monkeypatch.setattr(web_module.threading, "Thread", DummyThread)
    client = app.test_client()

    response = client.post(
        "/api/games/live",
        json={"mode": "real", "api_key": " sk-test \n", "memory_enabled": False},
    )

    assert response.status_code == 201
    assert started_threads[0].args[4] == "sk-test"
