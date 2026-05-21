"""Wolf agent - MBTI personality wrapper"""

from enum import Enum


class MBTIPersonality(Enum):
    ENTJ = "ENTJ"
    INTP = "INTP"
    ESFJ = "ESFJ"
    INFJ = "INFJ"


class WolfAgent:
    def __init__(self, player_id: int, name: str, personality: MBTIPersonality):
        self.player_id = player_id
        self.name = name
        self.personality = personality
        self.role = None
        self.alive = True

    def get_system_prompt(self) -> str:
        raise NotImplementedError

    def generate_speech(self, game_state: dict, channel: str) -> str:
        raise NotImplementedError
