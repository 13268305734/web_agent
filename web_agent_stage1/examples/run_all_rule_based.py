from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from web_agent.agent import AgentRunner, RuleBasedPlanner
from web_agent.eval.task_loader import load_tasks
from web_agent.utils.file_utils import ensure_dir, utc_timestamp_for_filename


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all configured tasks with the rule-based planner.")
    parser.add_argument("--tasks", default="eval/tasks.yaml", help="Path to tasks.yaml")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--slow-mo-ms", type=int, default=80)
    args = parser.parse_args()

    tasks = load_tasks(PROJECT_ROOT / args.tasks)
    run_dir = ensure_dir(PROJECT_ROOT / "traces" / f"batch_rule_based_{utc_timestamp_for_filename()}")

    rows = []
    for task in tasks:
        print(f"\n=== Running {task.id} ===")
        runner = AgentRunner(
            planner=RuleBasedPlanner(),
            headless=args.headless,
            base_trace_dir=run_dir,
            slow_mo_ms=args.slow_mo_ms,
        )
        result = runner.run_task(task)
        row = {
            "task_id": result.task_id,
            "success": result.success,
            "total_steps": result.total_steps,
            "final_url": result.final_url,
            "failure_reason": result.failure_reason,
            "trace_dir": result.trace_dir,
        }
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False, indent=2))

    summary_path = run_dir / "batch_summary.json"
    csv_path = run_dir / "batch_summary.csv"

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    success_count = sum(1 for row in rows if row["success"])
    print(f"\nBatch finished: {success_count}/{len(rows)} succeeded.")
    print(f"Batch summary JSON: {summary_path}")
    print(f"Batch summary CSV: {csv_path}")
    return 0 if success_count == len(rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
