from wolf_agent.events import BroadcastObserver, GameEvent


def _event(event_id: str) -> GameEvent:
    return GameEvent(
        event_id=event_id,
        game_id="game-1",
        timestamp="2026-05-24T00:00:00Z",
        type="progress",
        channel="system",
        visibility="public",
        content="Player 1 is thinking...",
    )


def test_finished_subscriber_receives_terminal_error_before_game_end():
    observer = BroadcastObserver()
    observer.on_event(_event("evt-0001"))
    observer.error("RuntimeError: boom")
    observer.finish()

    q = observer.subscribe()

    assert q.get_nowait().event_id == "evt-0001"
    assert q.get_nowait() == ("error", "RuntimeError: boom")
    assert q.get_nowait() is None


def test_finished_subscriber_receives_history_after_last_event_id_then_end():
    observer = BroadcastObserver()
    observer.on_event(_event("evt-0001"))
    observer.on_event(_event("evt-0002"))
    observer.finish()

    q = observer.subscribe(last_event_id="evt-0001")

    assert q.get_nowait().event_id == "evt-0002"
    assert q.get_nowait() is None
