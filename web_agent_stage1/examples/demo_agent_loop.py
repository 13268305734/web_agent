from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from web_agent.agent import AgentRunner, RuleBasedPlanner
from web_agent.eval.task_loader import load_tasks


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Stage 2 rule-based Agent Loop.")
    parser.add_argument("--tasks", default="eval/tasks.yaml", help="Path to tasks.yaml")
    parser.add_argument("--task-id", default="wiki_search_web_agent", help="Task id to run")
    parser.add_argument("--headless", action="store_true", help="Run Chromium in headless mode")
    parser.add_argument("--slow-mo-ms", type=int, default=120, help="Browser slow motion in ms")
    args = parser.parse_args()

    task_path = PROJECT_ROOT / args.tasks
    tasks = load_tasks(task_path, task_id=args.task_id)
    task = tasks[0]

    runner = AgentRunner(
        planner=RuleBasedPlanner(),
        headless=args.headless,
        base_trace_dir=PROJECT_ROOT / "traces",
        slow_mo_ms=args.slow_mo_ms,
    )
    result = runner.run_task(task)

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    print(f"\nTrace directory: {result.trace_dir}")
    return 0 if result.success else 2


if __name__ == "__main__":
    raise SystemExit(main())
