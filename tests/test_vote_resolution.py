"""Test vote resolution and tie-breaking."""

import os

from wolf_agent.engine.game import _run_vote
from wolf_agent.events import EventLog
from wolf_agent.agents import LLMClient


class PredictableMockLLM(LLMClient):
    """Always votes for player 1."""

    def __init__(self):
        self.api_key = "mock"
        self.base_url = "http://mock"
        self.model = "mock"

    def vote(self, messages: list[dict]) -> int:
        return 1


def test_vote_majority():
    """Simple majority vote."""
    state = {
        "alive": [1, 2, 3, 4, 5],
        "round_num": 1,
        "public_messages": [],
        "players": [{"id": i, "personality": "BOSS", "role": "villager"} for i in range(1, 10)],
        "game_id": "test",
        "event_log_path": os.devnull,
    }
    evtlog = EventLog("test", os.devnull)
    llm = PredictableMockLLM()

    votes, eliminated = _run_vote(state, llm, evtlog)
    evtlog.close()

    assert eliminated == 1, f"Expected 1, got {eliminated}"
    assert len(votes) == 4  # Player 1 can't self-vote, so 4 votes


def test_tie_revote_returns_none():
    """Tie results in None (triggers revote in vote_phase)."""
    state = {
        "alive": [1, 2],
        "round_num": 1,
        "public_messages": [],
        "players": [{"id": i, "personality": "BOSS", "role": "villager"} for i in range(1, 10)],
        "game_id": "test",
        "event_log_path": os.devnull,
    }
    evtlog = EventLog("test", os.devnull)

    class TieMockLLM(LLMClient):
        def __init__(self):
            self.api_key = "mock"
            self.base_url = "http://mock"
            self.model = "mock"
            self.call_count = 0

        def vote(self, messages: list[dict]) -> int:
            self.call_count += 1
            return 2 if self.call_count == 1 else 1

    llm = TieMockLLM()
    votes, eliminated = _run_vote(state, llm, evtlog)
    evtlog.close()

    assert eliminated is None, f"Expected None for tie, got {eliminated}"


def test_vote_self_not_counted():
    """Self-votes are excluded so no valid votes = no elimination."""
    state = {
        "alive": [1, 2, 3, 4, 5],
        "round_num": 1,
        "public_messages": [],
        "players": [{"id": i, "personality": "BOSS", "role": "villager"} for i in range(1, 10)],
        "game_id": "test",
        "event_log_path": os.devnull,
    }
    evtlog = EventLog("test", os.devnull)

    class SelfVoteLLM(LLMClient):
        def __init__(self):
            self.api_key = "mock"
            self.base_url = "http://mock"
            self.model = "mock"
            self.pid = 0

        def vote(self, messages: list[dict]) -> int:
            return self.pid

    llm = SelfVoteLLM()
    votes, eliminated = _run_vote(state, llm, evtlog)
    evtlog.close()

    assert eliminated is None
