from __future__ import annotations

import json
from decimal import Decimal
from datetime import datetime, timezone
from datetime import date as dt_date
from pathlib import Path
from threading import Lock
from typing import Any


class MemoryStore:
    def __init__(self, max_turns: int = 30, file_path: str | None = None) -> None:
        self.max_turns = max_turns
        self._lock = Lock()
        self._sessions: dict[str, list[dict[str, Any]]] = {}
        default_path = Path(__file__).resolve().parents[1] / "data" / "session_memory.json"
        self._file_path = Path(file_path) if file_path else default_path
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _to_json_safe(self, value: Any) -> Any:
        if isinstance(value, (datetime, dt_date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, dict):
            return {k: self._to_json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._to_json_safe(v) for v in value]
        if isinstance(value, tuple):
            return [self._to_json_safe(v) for v in value]
        return value

    def _load(self) -> None:
        if not self._file_path.exists():
            return
        try:
            data = json.loads(self._file_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._sessions = data
        except json.JSONDecodeError:
            self._sessions = {}

    def _save(self) -> None:
        payload = self._to_json_safe(self._sessions)
        self._file_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def append(self, session_id: str, turn: dict[str, Any]) -> None:
        turn_copy = dict(turn)
        turn_copy.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        with self._lock:
            history = self._sessions.setdefault(session_id, [])
            history.append(turn_copy)
            if len(history) > self.max_turns:
                del history[:-self.max_turns]
            self._save()

    def get(self, session_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            history = list(self._sessions.get(session_id, []))
        if limit is not None and limit > 0:
            return history[-limit:]
        return history

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
            self._save()

    def clear_all(self) -> None:
        with self._lock:
            self._sessions = {}
            self._save()

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            items: list[dict[str, Any]] = []
            for session_id, history in self._sessions.items():
                if not history:
                    continue
                last = history[-1]
                items.append(
                    {
                        "session_id": session_id,
                        "turns": len(history),
                        "last_question": str(last.get("question", "")),
                        "last_created_at": str(last.get("created_at", "")),
                    }
                )
        items.sort(key=lambda i: i.get("last_created_at", ""), reverse=True)
        return items
