import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

_DEFAULT_PATH = PROJECT_ROOT / "scripts" / "data_extraction" / "21_heep_hong_language_ontology.json"


class HHHAdapter:
    """Transforms parallel ontology JSON into cognition-macro-structure shape."""

    def __init__(self, data_path: Optional[Path] = None) -> None:
        self.data_path = Path(data_path) if data_path else _DEFAULT_PATH
        self._data: Optional[List[Dict[str, Any]]] = None

    def _load_data(self) -> List[Dict[str, Any]]:
        if self._data is None:
            try:
                with self.data_path.open("r", encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.info("Ontology adapter loaded JSON from %s", self.data_path)
            except FileNotFoundError:
                logger.error("Ontology JSON not found: %s", self.data_path)
                self._data = []
            except json.JSONDecodeError as e:
                logger.error("Ontology JSON invalid at %s: %s", self.data_path, e)
                self._data = []
        return self._data or []

    def get_macro_structure(self) -> Dict[str, Any]:
        raw_data = self._load_data()
        transformed: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = {}

        for item in raw_data:
            age_bracket = item.get("age_bracket", "未知年龄段")
            module_name = item.get("module", "未知模块")
            macro_label = item.get("label", "未知目标")
            tasks = item.get("tasks", []) or []

            if age_bracket not in transformed:
                transformed[age_bracket] = {}
            if module_name not in transformed[age_bracket]:
                transformed[age_bracket][module_name] = {}

            if macro_label not in transformed[age_bracket][module_name]:
                transformed[age_bracket][module_name][macro_label] = {
                    "macroLabel": macro_label,
                    "tasks": [],
                }

            bucket = transformed[age_bracket][module_name][macro_label]["tasks"]
            for task in tasks:
                task_title = task.get("title", "未知任务")
                if not any(t.get("title") == task_title for t in bucket):
                    bucket.append({"title": task_title})

        result_data: List[Dict[str, Any]] = []
        for age, modules_dict in transformed.items():
            modules_list = []
            for module, macros_dict in modules_dict.items():
                macros_list = list(macros_dict.values())
                modules_list.append({"moduleName": module, "macros": macros_list})
            result_data.append({"ageBracket": age, "modules": modules_list})

        return {"data": result_data, "source": "hhh"}
