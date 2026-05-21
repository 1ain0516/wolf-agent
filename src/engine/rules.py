"""v1 fixed game rules - 9-player standard"""

from enum import Enum, auto


class Role(Enum):
    WEREWOLF = auto()
    VILLAGER = auto()
    SEER = auto()
    WITCH = auto()


class GameRules:
    PLAYER_COUNT = 9
    ROLES = [
        Role.WEREWOLF, Role.WEREWOLF, Role.WEREWOLF,
        Role.SEER, Role.WITCH,
        Role.VILLAGER, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER,
    ]

    @staticmethod
    def check_winner(alive_players):
        raise NotImplementedError

    @staticmethod
    def resolve_vote(votes):
        raise NotImplementedError
