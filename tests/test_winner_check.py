"""Test win condition logic (屠边规则)."""

from wolf_agent.engine.game import _check_winner_condition


def make_state(alive: list[int], wolves: list[int]):
    return {
        "alive": alive,
        "_wolves": wolves,
        "_seer_id": None,
        "_witch_id": None,
    }


def test_no_winner_midgame():
    """3 wolves vs 6 villagers — game continues."""
    s = make_state([1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3])
    assert _check_winner_condition(s) is None


def test_wolf_win_numerical():
    """Wolf win: wolves >= non-wolves."""
    s = make_state([1, 2, 3, 4], [1, 2, 3])
    assert _check_winner_condition(s) == "werewolf"


def test_wolf_win_tie():
    """Wolf win: 2 wolves vs 2 villagers = tie = wolf win."""
    s = make_state([1, 2, 3, 4], [1, 2])
    assert _check_winner_condition(s) == "werewolf"


def test_villager_win_all_wolves_dead():
    """Villager win: all wolves eliminated."""
    s = make_state([4, 5, 6, 7, 8, 9], [])
    assert _check_winner_condition(s) == "villager"


def test_single_wolf_remaining():
    """Single wolf vs 5 villagers — still wolf win if wolves >= non-wolves."""
    # 1 wolf vs 5 villagers: 1 < 5, so village should win if wolf alone
    s = make_state([1, 4, 5, 6, 7, 8], [1])
    assert _check_winner_condition(s) is None


def test_two_wolves_vs_two_villagers():
    """2 wolves vs 2 villagers = wolf win (tie condition)."""
    s = make_state([1, 2, 3, 4], [1, 2])
    assert _check_winner_condition(s) == "werewolf"
