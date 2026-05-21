"""Canonical Event Log - single source of truth, append-only JSONL"""

from enum import Enum
from typing import Optional
from datetime import datetime


class EventType(str, Enum):
    GAME_STARTED = "game_started"
    ROLE_ASSIGNED = "role_assigned"
    PHASE_STARTED = "phase_started"
    MESSAGE_POSTED = "message_posted"
    ACTION_SUBMITTED = "action_submitted"
    VOTE_CAST = "vote_cast"
    VOTE_RESOLVED = "vote_resolved"
    PLAYER_ELIMINATED = "player_eliminated"
    PHASE_RESOLVED = "phase_resolved"
    GAME_ENDED = "game_ended"


class Visibility(str, Enum):
    PUBLIC = "public"
    WOLF_DEN = "wolf_den"
    ROLE_PRIVATE = "role_private"
    JUDGE_ONLY = "judge_only"


class EventLog:
    def __init__(self, game_id: str, output_dir: str = "games"):
        self.game_id = game_id
        self.output_dir = output_dir
        self.events = []
        self._counter = 0

    def append(self, event_type, **kwargs):
        raise NotImplementedError

    def flush(self):
        raise NotImplementedError
