from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def extract_summary(stdout: str):
    decoder = json.JSONDecoder()
    for i, ch in enumerate(stdout):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(stdout[i:])
        except Exception:
            continue
        if isinstance(obj, dict) and "task_id" in obj:
            return obj
    return None


def main():
    parser = argparse.ArgumentParser(description="Run multiple Stage 3B1 local LLM tasks.")
    parser.add_argument(
        "--tasks",
        nargs="+",
        default=[
            "wiki_search_web_agent",
            "wiki_search_playwright",
            "wiki_search_selenium",
        ],
    )
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--tasks-path", default="eval/tasks.yaml")
    parser.add_argument("--model", default="Qwen/Qwen2.5-3B-Instruct")
    parser.add_argument("--gpu", default="3")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--max-new-tokens", type=int, default=80)
    parser.add_argument("--max-elements", type=int, default=20)
    parser.add_argument("--max-dom-chars", type=int, default=1200)
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--post-action-sleep", type=float, default=2.0)
    parser.add_argument("--output-root", default="traces")
    args = parser.parse_args()

    batch_id = datetime.now().strftime("stage3b1_batch_%Y%m%d_%H%M%S")
    out_dir = Path(args.output_root) / batch_id
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []

    for task_id in args.tasks:
        for repeat in range(args.repeats):
            print("=" * 100)
            print(f"Running task={task_id}, repeat={repeat + 1}/{args.repeats}")

            cmd = [
                sys.executable,
                "examples/demo_local_llm_planner.py",
                "--task-id",
                task_id,
                "--tasks-path",
                args.tasks_path,
                "--model",
                args.model,
                "--max-new-tokens",
                str(args.max_new_tokens),
                "--max-elements",
                str(args.max_elements),
                "--max-dom-chars",
                str(args.max_dom_chars),
                "--max-steps",
                str(args.max_steps),
                "--post-action-sleep",
                str(args.post_action_sleep),
            ]

            if args.headless:
                cmd.append("--headless")

            env = os.environ.copy()
            if args.gpu:
                env["CUDA_VISIBLE_DEVICES"] = args.gpu

            proc = subprocess.run(
                cmd,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
            )

            run_log = out_dir / f"{task_id}_repeat{repeat + 1}.log"
            run_log.write_text(proc.stdout, encoding="utf-8")

            summary = extract_summary(proc.stdout)
            if summary is None:
                summary = {
                    "task_id": task_id,
                    "success": False,
                    "failure_reason": "Could not parse summary JSON from subprocess output",
                    "returncode": proc.returncode,
                    "log_path": str(run_log),
                }
            else:
                summary["returncode"] = proc.returncode
                summary["repeat"] = repeat + 1
                summary["log_path"] = str(run_log)

            results.append(summary)

            print(json.dumps(summary, ensure_ascii=False, indent=2))

    total = len(results)
    success_count = sum(1 for r in results if r.get("success") is True)

    batch_summary = {
        "batch_id": batch_id,
        "model": args.model,
        "gpu": args.gpu,
        "tasks": args.tasks,
        "repeats": args.repeats,
        "total_runs": total,
        "success_runs": success_count,
        "success_rate": success_count / total if total else 0,
        "results": results,
    }

    out_path = out_dir / "batch_summary.json"
    out_path.write_text(
        json.dumps(batch_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 100)
    print("Batch finished.")
    print(f"Summary: {out_path}")
    print(f"Success rate: {success_count}/{total} = {batch_summary['success_rate']:.2%}")


if __name__ == "__main__":
    main()
