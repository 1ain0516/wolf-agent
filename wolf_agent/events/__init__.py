from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Optional


EVENT_TYPES = [
    "game_started",
    "role_assigned",
    "phase_started",
    "message_posted",
    "action_submitted",
    "vote_cast",
    "vote_resolved",
    "player_eliminated",
    "phase_resolved",
    "game_ended",
]


@dataclass
class GameEvent:
    event_id: str
    game_id: str
    timestamp: str
    type: str
    channel: str
    visibility: str
    from_player: Optional[int] = None
    content: Optional[str] = None
    strategy_summary: Optional[str] = None
    metadata: Optional[dict] = None

    def to_json(self) -> str:
        d = asdict(self)
        return json.dumps({k: v for k, v in d.items() if v is not None}, ensure_ascii=False)


class EventLog:
    """Append-only canonical event log. Open multiple times safely — each open appends."""

    def __init__(self, game_id: str, path: str):
        self.game_id = game_id
        self.path = path
        self._devnull = path == os.devnull
        if not self._devnull:
            self._counter = 0
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for _ in f:
                        self._counter += 1
            except FileNotFoundError:
                pass
            self._file = open(path, "a", encoding="utf-8")
        else:
            self._counter = 0
            self._file = None

    def _next_id(self) -> str:
        self._counter += 1
        return f"evt-{self._counter:04d}"

    def _ts(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def append(self, type: str, channel: str, visibility: str, **kwargs) -> GameEvent:
        evt = GameEvent(
            event_id=self._next_id(),
            game_id=self.game_id,
            timestamp=self._ts(),
            type=type,
            channel=channel,
            visibility=visibility,
            **kwargs,
        )
        if not self._devnull:
            self._file.write(evt.to_json() + "\n")
            self._file.flush()
        return evt

    def close(self):
        if not self._devnull:
            self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
