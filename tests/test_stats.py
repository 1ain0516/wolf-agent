"""Test stats computation and summary collection."""

import json
import os
import tempfile

from wolf_agent.cli.main import _compute_stats, _collect_summaries


def _write_summary(dirpath: str, fname: str, data: dict):
    with open(os.path.join(dirpath, fname), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def test_collect_summaries_finds_json():
    """Collects .summary.json files from directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_summary(tmpdir, "g1.summary.json", {"winner": "werewolf", "rounds": 5, "players": []})
        _write_summary(tmpdir, "g2.summary.json", {"winner": "villager", "rounds": 7, "players": []})
        _write_summary(tmpdir, "other.txt", {"winner": "werewolf"})
        results = _collect_summaries(tmpdir)
        assert len(results) == 2


def test_collect_summaries_skips_bad_files():
    """Malformed summary files are skipped with stderr warning."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_summary(tmpdir, "bad.summary.json", {"no_winner": True})  # missing winner
        _write_summary(tmpdir, "good.summary.json", {"winner": "werewolf", "rounds": 3, "players": []})
        results = _collect_summaries(tmpdir)
        assert len(results) == 1


def test_collect_summaries_nonexistent_dir():
    """Non-existent dir returns empty list."""
    results = _collect_summaries("C:/nonexistent_path_xyz")
    assert results == []


def test_compute_stats_empty():
    """Empty summaries produce empty stats."""
    stats = _compute_stats([])
    assert stats["batch"]["total_games"] == 0


def test_compute_stats_single():
    """Single game stats."""
    summaries = [
        {"winner": "werewolf", "rounds": 5, "players": [
            {"role": "werewolf", "alive": True},
            {"role": "villager", "alive": False},
        ]},
    ]
    stats = _compute_stats(summaries)
    assert stats["winner_stats"]["werewolf"]["wins"] == 1
    assert stats["winner_stats"]["werewolf"]["win_rate"] == 1.0
    assert stats["round_stats"]["min"] == 5
    assert stats["round_stats"]["max"] == 5


def test_compute_stats_multiple():
    """Multiple games produce correct aggregate stats."""
    summaries = [
        {"winner": "werewolf", "rounds": 4, "players": []},
        {"winner": "villager", "rounds": 6, "players": []},
        {"winner": "werewolf", "rounds": 8, "players": []},
        {"winner": "werewolf", "rounds": 5, "players": []},
    ]
    stats = _compute_stats(summaries)
    assert stats["winner_stats"]["werewolf"]["wins"] == 3
    assert stats["winner_stats"]["werewolf"]["win_rate"] == 0.75
    assert stats["winner_stats"]["villager"]["wins"] == 1
    assert stats["round_stats"]["min"] == 4
    assert stats["round_stats"]["max"] == 8
    assert stats["round_stats"]["mean"] == 5.75
