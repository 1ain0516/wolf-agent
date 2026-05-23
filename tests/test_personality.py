"""Test SBTI personality templates — completeness and parameter ranges."""

from wolf_agent.agents.personality import (
    PERSONALITY_LIST,
    PERSONALITY_TEMPLATES,
    PARAM_NAMES,
)


def test_all_16_personalities_present():
    """Exactly 16 SBTI personalities."""
    assert len(PERSONALITY_LIST) == 16
    assert len(PERSONALITY_TEMPLATES) == 16


def test_personality_required_fields():
    """Each personality has title, description, style, strategy, params."""
    for name in PERSONALITY_LIST:
        tpl = PERSONALITY_TEMPLATES[name]
        assert "title" in tpl, f"{name} missing title"
        assert "description" in tpl, f"{name} missing description"
        assert "style" in tpl, f"{name} missing style"
        assert "strategy" in tpl, f"{name} missing strategy"
        assert "params" in tpl, f"{name} missing params"


def test_params_in_range():
    """All behavioral parameters are in [0.0, 1.0]."""
    for name in PERSONALITY_LIST:
        params = PERSONALITY_TEMPLATES[name]["params"]
        assert len(params) == 5, f"{name} should have 5 params, got {len(params)}"
        for key in PARAM_NAMES:
            val = params[key]
            assert 0.0 <= val <= 1.0, (
                f"{name}.{key} = {val} out of range [0, 1]"
            )


def test_personality_list_matches_templates():
    """PERSONALITY_LIST keys match PERSONALITY_TEMPLATES keys."""
    assert set(PERSONALITY_LIST) == set(PERSONALITY_TEMPLATES.keys())


def test_specific_personalities():
    """Spot-check a few known personalities."""
    boss = PERSONALITY_TEMPLATES["BOSS"]
    assert boss["title"] == "掌控者"
    assert boss["params"]["talkativeness"] > 0.8

    ojbk = PERSONALITY_TEMPLATES["OJBK"]
    assert ojbk["title"] == "无所谓人"
    assert ojbk["params"]["talkativeness"] < 0.2
    assert ojbk["params"]["vote_independence"] < 0.1

    fake = PERSONALITY_TEMPLATES["FAKE"]
    assert fake["params"]["lie_comfort"] > 0.9
