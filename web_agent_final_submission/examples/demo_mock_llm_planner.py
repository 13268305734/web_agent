from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

from web_agent.agent.llm_planner import LLMPlanner
from web_agent.models.mock_client import MockModelClient
from web_agent.browser.env import WebBrowserEnv


def now_id() -> str:
    # Include microseconds to avoid trace directory collisions when running
    # search/noisy/malformed_once quickly or in parallel.
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def make_unique_dir(path: Path) -> Path:
    """Return a path that does not already exist."""
    if not path.exists():
        return path
    for i in range(1, 1000):
        candidate = Path(f"{path}_{i:03d}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not create a unique trace directory for {path}")


def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(record)
    record.setdefault("timestamp", dt.datetime.now().isoformat(timespec="microseconds"))
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def load_tasks(tasks_path: Path) -> List[Dict[str, Any]]:
    if not tasks_path.exists():
        raise FileNotFoundError(f"tasks file not found: {tasks_path}")

    text = tasks_path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text)
    else:
        raise RuntimeError("PyYAML is required. Please run: pip install pyyaml")

    if isinstance(data, dict) and "tasks" in data:
        data = data["tasks"]
    if not isinstance(data, list):
        raise ValueError("tasks.yaml should be a list or a dict containing key 'tasks'")
    return data


def find_task(tasks: List[Dict[str, Any]], task_id: str) -> Dict[str, Any]:
    for task in tasks:
        if str(task.get("id")) == task_id:
            return task
    available = ", ".join(str(t.get("id")) for t in tasks[:20])
    raise KeyError(f"task_id {task_id!r} not found. Available examples: {available}")


def fallback_success_check(observation: Dict[str, Any], condition: Dict[str, Any]) -> Dict[str, Any]:
    condition = condition or {}
    condition_type = condition.get("type")
    value = str(condition.get("value", ""))

    url = str(observation.get("url", ""))
    title = str(observation.get("title", ""))
    dom_text = str(observation.get("dom_text", ""))

    if condition_type == "url_contains":
        ok = value in url
        return {"success": ok, "reason": f"url_contains {value!r}: {ok}", "condition": condition}
    if condition_type == "title_contains":
        ok = value.lower() in title.lower()
        return {"success": ok, "reason": f"title_contains {value!r}: {ok}", "condition": condition}
    if condition_type == "text_contains":
        ok = value.lower() in dom_text.lower()
        return {"success": ok, "reason": f"text_contains {value!r}: {ok}", "condition": condition}
    if condition_type == "manual_check":
        return {"success": False, "reason": "manual_check requires human review", "condition": condition}

    return {"success": False, "reason": f"unsupported success condition: {condition_type}", "condition": condition}


def check_success(observation: Dict[str, Any], condition: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from web_agent.eval.success_checker import check_success as project_check_success

        return project_check_success(observation, condition)
    except Exception:
        return fallback_success_check(observation, condition)


def create_env(headless: bool, trace_dir: Path) -> WebBrowserEnv:
    """Create WebBrowserEnv while tolerating small constructor differences."""
    attempts = [
        lambda: WebBrowserEnv(headless=headless, trace_dir=str(trace_dir)),
        lambda: WebBrowserEnv(trace_dir=str(trace_dir)),
        lambda: WebBrowserEnv(headless=headless),
        lambda: WebBrowserEnv(),
    ]

    last_error: Optional[Exception] = None
    for factory in attempts:
        try:
            env = factory()
            return env
        except TypeError as exc:
            last_error = exc

    raise RuntimeError(f"Could not construct WebBrowserEnv: {last_error}")


def start_env(env: WebBrowserEnv, headless: bool) -> None:
    try:
        env.start(headless=headless)
    except TypeError:
        env.start()


def save_step_screenshot(env: WebBrowserEnv, screenshots_dir: Path, step_id: int) -> Optional[str]:
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    path = screenshots_dir / f"step_{step_id:03d}.png"
    try:
        return env.get_screenshot(str(path))
    except TypeError:
        try:
            env.get_screenshot(path=str(path))
            return str(path)
        except Exception:
            return None
    except Exception:
        return None


def open_url_checked(env: WebBrowserEnv, url: str) -> Dict[str, Any]:
    """Open URL and normalize the result.

    Some Stage 1 WebBrowserEnv.open_url implementations return None on success,
    while others return a dict. Treat None as success. Treat explicit
    {"success": false} as failure and stop the demo before planning.
    """
    try:
        result = env.open_url(url)
    except Exception as exc:
        return {
            "success": False,
            "message": "open_url raised exception",
            "error": str(exc),
        }

    if result is None:
        return {
            "success": True,
            "message": "open_url returned None; treated as success for compatibility",
            "raw_result": None,
        }

    if isinstance(result, dict):
        if result.get("success") is False:
            return result
        return {
            "success": True,
            "message": "open_url completed",
            "raw_result": result,
        }

    return {
        "success": True,
        "message": "open_url completed",
        "raw_result": result,
    }


def run_mock_llm_task(args: argparse.Namespace) -> Dict[str, Any]:
    tasks = load_tasks(Path(args.tasks_path))
    task = find_task(tasks, args.task_id)

    trace_dir = make_unique_dir(
        Path(args.trace_root) / f"stage3a_mock_{args.task_id}_{args.mock_mode}_{now_id()}"
    )
    screenshots_dir = trace_dir / "screenshots"
    events_path = trace_dir / "events.jsonl"
    summary_path = trace_dir / "summary.json"
    trace_dir.mkdir(parents=True, exist_ok=False)

    planner = LLMPlanner(
        model_client=MockModelClient(mode=args.mock_mode),
        include_dom=not args.no_dom,
        use_screenshot=args.use_screenshot,
        max_dom_chars=args.max_dom_chars,
        max_elements=args.max_elements,
    )

    env = create_env(args.headless, trace_dir)
    history: List[Dict[str, Any]] = []
    final_success = False
    failure_reason = ""
    total_steps = 0

    try:
        start_env(env, args.headless)

        open_result = open_url_checked(env, task["url"])
        append_jsonl(events_path, {
            "event": "open_url",
            "url": task["url"],
            "result": open_result,
        })

        if not open_result.get("success"):
            failure_reason = f"open_url failed: {open_result.get('error') or open_result.get('message')}"
            summary = {
                "task_id": task.get("id"),
                "instruction": task.get("instruction"),
                "success": False,
                "total_steps": 0,
                "trace_dir": str(trace_dir),
                "events_path": str(events_path),
                "failure_reason": failure_reason,
                "mock_mode": args.mock_mode,
            }
            summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            return summary

        max_steps = int(args.max_steps or task.get("max_steps", 12))
        success_condition = task.get("success_condition", {})

        for step_id in range(1, max_steps + 1):
            total_steps = step_id

            observation = env.get_observation()
            screenshot_path = save_step_screenshot(env, screenshots_dir, step_id)
            if screenshot_path:
                observation["screenshot_path"] = screenshot_path

            success = check_success(observation, success_condition)
            append_jsonl(events_path, {
                "event": "observe",
                "step_id": step_id,
                "url": observation.get("url"),
                "title": observation.get("title"),
                "screenshot_path": observation.get("screenshot_path"),
                "num_clickable_elements": len(observation.get("clickable_elements", []) or []),
                "success_check": success,
            })

            if success.get("success"):
                final_success = True
                failure_reason = ""
                break

            action = planner.plan(task, observation, history)
            append_jsonl(events_path, {
                "event": "plan",
                "step_id": step_id,
                "prompt_preview": planner.last_prompt[:1200],
                "raw_model_output": planner.last_raw_output,
                "parsed_action": action,
            })

            if action.get("action") == "finish":
                failure_reason = action.get("answer") or "planner finished before success condition was met"
                append_jsonl(events_path, {
                    "event": "finish",
                    "step_id": step_id,
                    "action": action,
                    "success": False,
                    "reason": failure_reason,
                })
                break

            try:
                result = env.execute_action(action)
            except Exception as exc:
                result = {"success": False, "message": "execute_action raised exception", "error": str(exc)}

            history_item = {
                "step": step_id,
                "url": observation.get("url"),
                "action": action,
                "result": result,
                "success_check": success,
            }
            history.append(history_item)

            append_jsonl(events_path, {
                "event": "act",
                "step_id": step_id,
                "action": action,
                "result": result,
            })

            # Give dynamic pages a small chance to settle after each operation.
            if action.get("action") in {"press", "click", "click_xy"}:
                time.sleep(args.post_action_sleep)

        else:
            failure_reason = f"Reached max_steps={max_steps}"

        # Final observation and final screenshot.
        try:
            final_observation = env.get_observation()
            final_screenshot = save_step_screenshot(env, screenshots_dir, total_steps + 1)
            if final_screenshot:
                final_observation["screenshot_path"] = final_screenshot
            final_check = check_success(final_observation, success_condition)
            if final_check.get("success"):
                final_success = True
                failure_reason = ""
            append_jsonl(events_path, {
                "event": "final_check",
                "url": final_observation.get("url"),
                "title": final_observation.get("title"),
                "screenshot_path": final_observation.get("screenshot_path"),
                "success_check": final_check,
            })
        except Exception as exc:
            append_jsonl(events_path, {"event": "final_check_error", "error": str(exc)})

    finally:
        try:
            env.close()
        except Exception:
            pass

    summary = {
        "task_id": task.get("id"),
        "instruction": task.get("instruction"),
        "success": final_success,
        "total_steps": total_steps,
        "trace_dir": str(trace_dir),
        "events_path": str(events_path),
        "failure_reason": failure_reason,
        "mock_mode": args.mock_mode,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage 3A demo: mock LLM planner + existing browser loop")
    parser.add_argument("--task-id", default="wiki_search_web_agent_results", help="Task id from tasks yaml")
    parser.add_argument("--tasks-path", default="eval/tasks.yaml", help="Path to tasks yaml")
    parser.add_argument("--headless", action="store_true", help="Run Chromium in headless mode")
    parser.add_argument("--trace-root", default="traces", help="Root folder for traces")
    parser.add_argument("--max-steps", type=int, default=None, help="Override task.max_steps")
    parser.add_argument("--mock-mode", default="search", choices=["search", "noisy", "malformed_once"])
    parser.add_argument("--use-screenshot", action="store_true", help="Pass screenshot path to model client")
    parser.add_argument("--no-dom", action="store_true", help="Omit DOM text from prompt")
    parser.add_argument("--max-dom-chars", type=int, default=3500)
    parser.add_argument("--max-elements", type=int, default=60)
    parser.add_argument("--post-action-sleep", type=float, default=1.0)
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    summary = run_mock_llm_task(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\nStage 3A mock planner demo finished.")
    print(f"Trace dir: {summary['trace_dir']}")
    print(f"Events:    {summary['events_path']}")


if __name__ == "__main__":
    main()
