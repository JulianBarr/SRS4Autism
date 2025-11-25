import json
from typing import Any, Dict, Optional

from .config import MEMORY_FILE


class AgentMemory:
    """
    Simple JSON-backed memory store.

    This is intentionally lightweight so that it can coexist with the
    existing system. Later, it can be swapped for a vector database without
    changing the agent interface.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if MEMORY_FILE.exists():
            try:
                self._cache = json.loads(MEMORY_FILE.read_text())
            except json.JSONDecodeError:
                self._cache = {}
        else:
            self._cache = {}

    def _save(self) -> None:
        MEMORY_FILE.write_text(json.dumps(self._cache, indent=2, ensure_ascii=False))

    def get_profile(self, user_id: str) -> Dict[str, Any]:
        return self._cache.get(user_id, {})

    def update_profile(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        profile = self._cache.get(user_id, {})
        profile.update(updates)
        self._cache[user_id] = profile
        self._save()
        return profile

    def append_history(self, user_id: str, entry: Dict[str, Any]) -> None:
        profile = self._cache.setdefault(user_id, {})
        history = profile.setdefault("history", [])
        history.append(entry)
        self._save()

    def get_last_interaction(self, user_id: str) -> Optional[Dict[str, Any]]:
        profile = self._cache.get(user_id, {})
        history = profile.get("history") or []
        return history[-1] if history else None

