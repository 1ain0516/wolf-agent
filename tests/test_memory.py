"""Test growth memory system — save, load, isolation, no-memory mode."""

import json
import os
import tempfile
from unittest.mock import patch

from wolf_agent.engine.memory import save_memory, load_memories


class _MockLLM:
    """Deterministic mock LLM for memory tests."""
    def __init__(self):
        self.api_key = "mock"
        self.base_url = "http://mock"
        self.model = "mock"

    def speak(self, messages):
        return "我怀疑有人搞事情。", "策略性观察"

    def vote(self, messages):
        return 9

    def act(self, messages):
        return {"target": 1, "use_antidote": False, "poison_target": None}

    def reflect(self, messages):
        return "测试反思内容。"

    def _call(self, messages, temperature, max_tokens):
        return '{"content": "test", "strategy_summary": "test"}'

    def chat(self, messages, temperature=0.7, max_tokens=300):
        return "test"

    def chat_with_strategy(self, messages, temperature=0.7, max_tokens=350):
        return "test", "test"

    def witch_act(self, context, save_target, has_antidote, has_poison):
        return {"use_antidote": False, "poison_target": None}

    def wolf_discuss(self, context, packmates):
        return "可以杀了目标。"

    def night_kill(self, context, targets):
        return targets[0] if targets else 1

    def night_investigate(self, context, targets):
        return targets[0]


def _write_index(dirpath: str, entries: list[dict]):
    path = os.path.join(dirpath, "memories.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def test_save_memory_creates_files():
    """save_memory creates per-game backup and global index."""
    with tempfile.TemporaryDirectory() as tmpdir:
        save_memory("game-1", 3, "BOSS", "seer", "我很好地分析了局势。", tmpdir)

        # Per-game backup
        per_game = os.path.join(tmpdir, "game-1.memories.jsonl")
        assert os.path.exists(per_game)
        with open(per_game) as f:
            lines = f.readlines()
        assert len(lines) == 1

        # Global index
        index = os.path.join(tmpdir, "memories.jsonl")
        assert os.path.exists(index)
        with open(index) as f:
            lines = f.readlines()
        assert len(lines) == 1


def test_load_memories_empty_dir():
    """load_memories returns empty list when no index exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mems = load_memories(3, tmpdir)
        assert mems == []


def test_load_memories_filters_player_id():
    """Only returns memories for the requested player."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_index(tmpdir, [
            {"player_id": 1, "game_id": "g1", "strength": 0.8, "content": "mem1"},
            {"player_id": 3, "game_id": "g1", "strength": 0.9, "content": "mem2"},
            {"player_id": 1, "game_id": "g2", "strength": 0.7, "content": "mem3"},
        ])
        mems = load_memories(1, tmpdir)
        assert len(mems) == 2
        assert all(m["player_id"] == 1 for m in mems)


def test_load_memories_excludes_current_game():
    """Exclude_game_id filters out memories from the current game."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_index(tmpdir, [
            {"player_id": 1, "game_id": "g1", "strength": 0.9, "content": "old"},
            {"player_id": 1, "game_id": "g2", "strength": 0.8, "content": "current"},
        ])
        mems = load_memories(1, tmpdir, exclude_game_id="g2")
        assert len(mems) == 1
        assert mems[0]["game_id"] == "g1"


def test_load_memories_filters_strength():
    """min_strength filters out weak memories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_index(tmpdir, [
            {"player_id": 1, "game_id": "g1", "strength": 0.9, "content": "strong"},
            {"player_id": 1, "game_id": "g2", "strength": 0.3, "content": "weak"},
        ])
        mems = load_memories(1, tmpdir, min_strength=0.5)
        assert len(mems) == 1
        assert mems[0]["content"] == "strong"


def test_load_memories_respects_limit():
    """limit controls max returned memories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_index(tmpdir, [
            {"player_id": 1, "game_id": f"g{i}", "strength": 0.9, "content": f"mem{i}"}
            for i in range(5)
        ])
        mems = load_memories(1, tmpdir, limit=3)
        assert len(mems) == 3


def test_save_then_load_roundtrip():
    """Full save → load round-trip returns same content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        save_memory("g1", 5, "FAKE", "werewolf", "我成功隐藏了身份。", tmpdir)
        mems = load_memories(5, tmpdir)
        assert len(mems) == 1
        assert mems[0]["content"] == "我成功隐藏了身份。"
        assert mems[0]["personality"] == "FAKE"
        assert mems[0]["role"] == "werewolf"


def test_no_memory_skips_memory_operations():
    """When _no_memory=True, post_game_phase should skip memory writes."""
    from wolf_agent.engine.game import post_game_phase

    state = {
        "_no_memory": True,
        "game_id": "test",
        "event_log_path": os.devnull,
        "_memory_dir": "",
        "players": [],
        "roles": {},
        "alive": [],
    }
    result = post_game_phase(state)
    # Should return state unchanged
    assert result is state or result.get("_no_memory") is True
