from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


ALLOWED_SUCCESS_TYPES = {
    "url_contains",
    "text_contains",
    "title_contains",
    "element_text_contains",
    "manual_check",
}


@dataclass
class TaskConfig:
    """A single web task configuration."""

    id: str
    site: str
    url: str
    instruction: str
    success_condition: Dict[str, Any]
    max_steps: int = 12
    search_query: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, item: Dict[str, Any]) -> "TaskConfig":
        required = ["id", "site", "url", "instruction", "success_condition"]
        missing = [key for key in required if key not in item]
        if missing:
            raise ValueError(f"Task is missing required fields: {missing}. Raw task: {item}")

        condition = item["success_condition"]
        if not isinstance(condition, dict):
            raise ValueError(f"success_condition must be a dict for task {item.get('id')}")

        condition_type = condition.get("type")
        if condition_type not in ALLOWED_SUCCESS_TYPES:
            raise ValueError(
                f"Unsupported success_condition.type={condition_type!r} for task {item.get('id')}. "
                f"Allowed types: {sorted(ALLOWED_SUCCESS_TYPES)}"
            )

        if condition_type != "manual_check" and "value" not in condition:
            raise ValueError(f"success_condition.value is required for task {item.get('id')}")

        max_steps = int(item.get("max_steps", 12))
        if max_steps <= 0:
            raise ValueError(f"max_steps must be positive for task {item.get('id')}")

        known_keys = {
            "id",
            "site",
            "url",
            "instruction",
            "success_condition",
            "max_steps",
            "search_query",
        }
        metadata = {k: v for k, v in item.items() if k not in known_keys}

        return cls(
            id=str(item["id"]),
            site=str(item["site"]),
            url=str(item["url"]),
            instruction=str(item["instruction"]),
            success_condition=condition,
            max_steps=max_steps,
            search_query=item.get("search_query"),
            metadata=metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "site": self.site,
            "url": self.url,
            "instruction": self.instruction,
            "search_query": self.search_query,
            "success_condition": self.success_condition,
            "max_steps": self.max_steps,
        }
        data.update(self.metadata)
        return data


def load_tasks(path: str | Path, task_id: Optional[str] = None) -> List[TaskConfig]:
    """Load and validate tasks from a YAML file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Task file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"Task file must contain a list of tasks: {path}")

    tasks = [TaskConfig.from_dict(item) for item in raw]

    if task_id:
        tasks = [task for task in tasks if task.id == task_id]
        if not tasks:
            raise ValueError(f"No task found with id={task_id!r} in {path}")

    seen = set()
    duplicates = []
    for task in tasks:
        if task.id in seen:
            duplicates.append(task.id)
        seen.add(task.id)
    if duplicates:
        raise ValueError(f"Duplicate task ids: {duplicates}")

    return tasks


def list_task_ids(path: str | Path) -> List[str]:
    return [task.id for task in load_tasks(path)]
