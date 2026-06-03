#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Command-line natural-language WebAgent demo entry.

This is a safe wrapper for demos. By default it uses the lightweight browser
fallback implemented in webui/browser_demo_agent.py. Use --mode project_agent_cli
when your original examples/demo_local_llm_planner.py supports --task.
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from webui.browser_demo_agent import run_browser_demo_agent


def run_project_cli(args: argparse.Namespace) -> int:
    script = PROJECT_ROOT / "examples" / "demo_local_llm_planner.py"
    if not script.exists():
        print(f"ERROR: original entry not found: {script}", file=sys.stderr)
        return 2
    cmd = [
        sys.executable,
        str(script),
        "--task",
        args.task,
        "--model",
        args.model,
        "--use-screenshot",
        "--max-steps",
        str(args.max_steps),
        "--max-new-tokens",
        str(args.max_new_tokens),
        "--max-dom-chars",
        str(args.max_dom_chars),
        "--max-elements",
        str(args.max_elements),
        "--post-action-sleep",
        str(args.post_action_sleep),
    ]
    if args.headless:
        cmd.append("--headless")
    env = os.environ.copy()
    if args.gpu_id:
        env["CUDA_VISIBLE_DEVICES"] = args.gpu_id
    if args.model:
        env["VLM_MODEL_PATH"] = args.model
    print("Running:")
    print(" ".join(shlex.quote(x) for x in cmd))
    return subprocess.call(cmd, cwd=str(PROJECT_ROOT), env=env)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a natural-language WebAgent browser demo.")
    parser.add_argument("--task", required=True, help="Natural language task")
    parser.add_argument("--mode", choices=["browser_demo_fallback", "project_agent_cli"], default="browser_demo_fallback")
    parser.add_argument("--model", default=os.environ.get("VLM_MODEL_PATH", "/data1/xiangkun/MODELS/Qwen2.5-VL-7B-Instruct"))
    parser.add_argument("--gpu-id", default=os.environ.get("CUDA_VISIBLE_DEVICES", "1"))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--headed", dest="headless", action="store_false")
    parser.set_defaults(headless=False)
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--max-dom-chars", type=int, default=3000)
    parser.add_argument("--max-elements", type=int, default=20)
    parser.add_argument("--post-action-sleep", type=float, default=1.0)
    args = parser.parse_args()

    if args.mode == "project_agent_cli":
        raise SystemExit(run_project_cli(args))

    result = run_browser_demo_agent(
        args.task,
        headless=args.headless,
        slow_mo_ms=int(max(0, args.post_action_sleep * 1000)),
    )
    print(result.to_markdown())
    raise SystemExit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
