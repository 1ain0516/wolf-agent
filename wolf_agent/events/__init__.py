from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, asdict
from queue import Queue
from typing import Optional, Protocol


EVENT_TYPES = [
    "game_started",
    "role_assigned",
    "phase_started",
    "progress",
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


class EventObserver(Protocol):
    """观察者协议：接收事件通知"""
    def on_event(self, event: GameEvent) -> None: ...


class BroadcastObserver:
    """多客户端广播：每个 SSE 连接 subscribe() 获得独立队列"""

    MAX_HISTORY = 2000

    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers: list[Queue] = []
        self._history: list[GameEvent] = []
        self._finished = False
        self._terminal_error: str | None = None

    def on_event(self, event: GameEvent) -> None:
        with self._lock:
            if len(self._history) < self.MAX_HISTORY:
                self._history.append(event)
            dead = []
            for q in self._subscribers:
                try:
                    q.put_nowait(event)
                except Exception:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)

    def subscribe(self, last_event_id: str | None = None) -> Queue:
        q: Queue[GameEvent | tuple[str, str] | None] = Queue(maxsize=500)
        with self._lock:
            start_idx = 0
            if last_event_id:
                for i, evt in enumerate(self._history):
                    if evt.event_id == last_event_id:
                        start_idx = i + 1
                        break
            for evt in self._history[start_idx:]:
                q.put(evt)
            if self._finished:
                if self._terminal_error:
                    q.put(("error", self._terminal_error))
                q.put(None)
            else:
                self._subscribers.append(q)
        return q

    def unsubscribe(self, q: Queue) -> None:
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def error(self, message: str) -> None:
        with self._lock:
            self._terminal_error = message
            for q in self._subscribers:
                q.put(("error", message))

    def finish(self) -> None:
        with self._lock:
            self._finished = True
            for q in self._subscribers:
                q.put(None)
            self._subscribers.clear()


class EventLog:
    """Canonical event log. First open creates/truncates; subsequent opens append."""

    def __init__(self, game_id: str, path: str):
        self.game_id = game_id
        self.path = path
        self._devnull = path == os.devnull
        self._observers: list[EventObserver] = []
        if not self._devnull:
            self._counter = 0
            exists = os.path.exists(path)
            mode = "w" if not exists else "a"
            if exists:
                with open(path, "r", encoding="utf-8") as f:
                    for _ in f:
                        self._counter += 1
            self._file = open(path, mode, encoding="utf-8")
        else:
            self._counter = 0
            self._file = None

    def _next_id(self) -> str:
        self._counter += 1
        return f"evt-{self._counter:04d}"

    def _ts(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def add_observer(self, observer: EventObserver) -> None:
        self._observers.append(observer)

    def remove_observer(self, observer: EventObserver) -> None:
        self._observers.remove(observer)

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
        for obs in self._observers:
            obs.on_event(evt)
        return evt

    def close(self):
        if not self._devnull:
            self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
