"""In-process thread-safe event store for WebSocket streaming (Fase A).

Workers (daemon threads) append events here; the WS consumer polls
every 300 ms and streams new entries to connected clients.
"""
import threading
from collections import defaultdict

_events: dict[str, list[dict]] = defaultdict(list)
_lock = threading.Lock()
_MAX = 10_000


def append_event(project_id: str, event: dict) -> None:
    with _lock:
        store = _events[project_id]
        store.append(event)
        if len(store) > _MAX:
            _events[project_id] = store[-_MAX:]


def get_events_since(project_id: str, since_idx: int) -> list[dict]:
    with _lock:
        return list(_events[project_id][since_idx:])


def current_index(project_id: str) -> int:
    with _lock:
        return len(_events[project_id])
