from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .file_utils import ensure_dir


class JsonlLogger:
    """Append-only JSONL logger.

    Each record gets an ISO timestamp automatically. This is intentionally simple
    so later stages can parse logs for trajectory visualization and evaluation.
    """

    def __init__(self, log_path: str | Path):
        self.log_path = Path(log_path)
        ensure_dir(self.log_path.parent)
        self.log_path.touch(exist_ok=True)

    def append(self, record: Dict[str, Any]) -> None:
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **record,
        }
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def event(
        self,
        *,
        step_id: int,
        event: str,
        url: Optional[str] = None,
        title: Optional[str] = None,
        action: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
        screenshot_path: Optional[str] = None,
        error: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        record: Dict[str, Any] = {
            "step_id": step_id,
            "event": event,
            "url": url,
            "title": title,
            "action": action,
            "result": result,
            "screenshot_path": screenshot_path,
            "error": error,
        }
        if extra:
            record.update(extra)
        self.append(record)
