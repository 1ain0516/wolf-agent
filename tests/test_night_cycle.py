"""Test night cycle logic — role interactions."""

from wolf_agent.engine.game import default_state, init_game, assign_roles


def test_night_structure():
    """Verify night state setup is correct (wolves, seer, witch assigned)."""
    state = default_state(42)
    state = init_game(state)
    state = assign_roles(state)

    assert len(state["_wolves"]) == 3
    assert state["_seer_id"] is not None
    assert state["_witch_id"] is not None

    # All roles are distinct players
    all_special = set(state["_wolves"]) | {state["_seer_id"], state["_witch_id"]}
    assert len(all_special) == 5, "5 unique players should have special roles"

    # 9 players total, all alive
    assert len(state["players"]) == 9
    assert len(state["alive"]) == 9
