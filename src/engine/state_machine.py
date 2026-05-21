"""LangGraph werewolf state machine - v1"""

from enum import Enum, auto


class GamePhase(Enum):
    INIT = auto()
    ASSIGN_ROLES = auto()
    NIGHT_WOLF_DEN = auto()
    NIGHT_SEER = auto()
    NIGHT_WITCH = auto()
    NIGHT_RESOLVE = auto()
    DAY_DISCUSSION = auto()
    VOTE = auto()
    VOTE_RESOLVE = auto()
    EXECUTION = auto()
    CHECK_WINNER = auto()
    GAME_END = auto()


class GameStateMachine:
    """LangGraph state machine for 9-player standard game"""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.phase = GamePhase.INIT
        self.players = []
        self.round = 0

    @classmethod
    def build_graph(cls):
        """Build LangGraph state graph"""
        raise NotImplementedError
