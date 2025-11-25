from typing import Any, Dict, List

import yaml

from .config import PRINCIPLES_FILE


DEFAULT_RULES = {
    "scaffolding": {
        "high_load": {
            "novice": "mcq",
            "intermediate": "cloze",
            "advanced": "free_response",
        },
        "default": "mcq",
    }
}


class PrincipleStore:
    """
    Lightweight principle repository backed by YAML.

    The file can be edited without changing code, and it forms the
    knowledge base that the agent consults before taking action.
    """

    def __init__(self) -> None:
        if PRINCIPLES_FILE.exists():
            self._rules = self._load()
        else:
            self._rules = DEFAULT_RULES
            self._save(DEFAULT_RULES)

    def _load(self) -> Dict[str, Any]:
        try:
            with open(PRINCIPLES_FILE, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError:
            data = {}
        if not data:
            data = DEFAULT_RULES
            self._save(data)
        return data

    def _save(self, data: Dict[str, Any]) -> None:
        with open(PRINCIPLES_FILE, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    @property
    def rules(self) -> Dict[str, Any]:
        return self._rules

    def select_scaffold(self, topic_complexity: str, learner_level: str) -> str:
        scaffolding = self._rules.get("scaffolding", {})
        high_load_rules = scaffolding.get("high_load", {})
        if topic_complexity == "high":
            return high_load_rules.get(learner_level) or high_load_rules.get("default") or scaffolding.get("default", "mcq")
        return scaffolding.get("default", "mcq")

    def debug_summary(self) -> List[str]:
        summary = []
        scaffolding = self._rules.get("scaffolding", {})
        summary.append("Scaffolding rules:")
        for key, value in scaffolding.items():
            summary.append(f"- {key}: {value}")
        return summary

