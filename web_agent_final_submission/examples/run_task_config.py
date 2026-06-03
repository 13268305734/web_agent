from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from web_agent.eval.task_loader import load_tasks


def main() -> int:
    parser = argparse.ArgumentParser(description="Load and validate task YAML.")
    parser.add_argument("--tasks", default="eval/tasks.yaml", help="Path to tasks.yaml")
    parser.add_argument("--task-id", default=None, help="Optional task id to show")
    args = parser.parse_args()

    tasks = load_tasks(PROJECT_ROOT / args.tasks, task_id=args.task_id)
    print(f"Loaded {len(tasks)} task(s).")
    for task in tasks:
        print(json.dumps(task.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
