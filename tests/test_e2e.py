"""End-to-end test with deterministic mocked LLM."""

import os
import tempfile
from unittest.mock import patch


class SmartMockLLM:
    """Deterministic mock that makes valid game moves."""

    def __init__(self):
        self.api_key = "mock"
        self.base_url = "http://mock"
        self.model = "mock"
        self._vote_targets = [9, 8, 7, 6, 5, 4, 3, 2, 1]  # Vote in this order
        self._vote_idx = 0
        self._kill_targets = [1, 2, 3, 4, 5, 6, 7, 8, 9]  # Kill in this order
        self._kill_idx = 0

    def speak(self, messages):
        return "我怀疑有人搞事情。", "策略性观察"

    def vote(self, messages):
        target = self._vote_targets[self._vote_idx % len(self._vote_targets)]
        self._vote_idx += 1
        return target

    def act(self, messages):
        target = self._kill_targets[self._kill_idx % len(self._kill_targets)]
        self._kill_idx += 1
        return {"target": target, "use_antidote": False, "poison_target": None}

    def _call(self, messages, temperature, max_tokens):
        return '{"content": "test", "strategy_summary": "test"}'

    def chat(self, messages, temperature=0.7, max_tokens=300):
        return "test"

    def chat_with_strategy(self, messages, temperature=0.7, max_tokens=350):
        return "test", "test"

    def witch_act(self, context, save_target, has_antidote, has_poison):
        return {"use_antidote": False, "poison_target": None}

    def wolf_discuss(self, context, packmates):
        return "杀谁？"

    def night_kill(self, context, targets):
        t = self._kill_targets[self._kill_idx % len(self._kill_targets)]
        self._kill_idx += 1
        return t if t in targets else targets[0]

    def night_investigate(self, context, targets):
        return targets[0]


@patch("wolf_agent.engine.game.LLMClient", SmartMockLLM)
def test_e2e_deterministic_seed():
    """Same seed produces same game_id."""
    from wolf_agent.engine.game import create_game

    with patch("wolf_agent.engine.game.GAMES_DIR", tempfile.mkdtemp()):
        final1, _ = create_game(seed=42)

    with patch("wolf_agent.engine.game.GAMES_DIR", tempfile.mkdtemp()):
        final2, _ = create_game(seed=42)

    assert final1["game_id"] == final2["game_id"]


@patch("wolf_agent.engine.game.LLMClient", SmartMockLLM)
def test_e2e_game_completes():
    """Game finishes with a winner."""
    from wolf_agent.engine.game import create_game

    with patch("wolf_agent.engine.game.GAMES_DIR", tempfile.mkdtemp()):
        final, _ = create_game(seed=42)

    assert final.get("winner") is not None, "Game should have a winner"
    assert final["winner"] in ("werewolf", "villager")


@patch("wolf_agent.engine.game.LLMClient", SmartMockLLM)
def test_e2e_event_log_created():
    """Game creates an events.jsonl file with content."""
    from wolf_agent.engine.game import create_game

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("wolf_agent.engine.game.GAMES_DIR", tmpdir):
            final, _ = create_game(seed=42)
            log_path = final["event_log_path"]
            assert os.path.exists(log_path), f"Event log not found: {log_path}"
            with open(log_path) as f:
                lines = f.readlines()
            assert len(lines) > 0


@patch("wolf_agent.engine.game.LLMClient", SmartMockLLM)
def test_e2e_summary_json():
    """Game creates a summary.json file."""
    from wolf_agent.engine.game import create_game

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("wolf_agent.engine.game.GAMES_DIR", tmpdir):
            final, _ = create_game(seed=42)
            summary_path = final["event_log_path"].replace(".events.jsonl", ".summary.json")
            assert os.path.exists(summary_path), f"Summary not found: {summary_path}"
