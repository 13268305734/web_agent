from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make the project importable when running from examples/.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from web_agent.browser import WebBrowserEnv
from web_agent.config.settings import DEFAULT_TRACE_DIR
from web_agent.utils.file_utils import ensure_dir, utc_timestamp_for_filename


def find_wikipedia_search_box(elements: List[Dict[str, Any]]) -> Optional[int]:
    """Find the most likely Wikipedia search input from extracted elements."""
    best_id = None
    best_score = -1

    for el in elements:
        tag = (el.get("tag") or "").lower()
        text = (el.get("text") or "").lower()
        aria = (el.get("aria_label") or "").lower()
        placeholder = (el.get("placeholder") or "").lower()
        input_type = (el.get("input_type") or "").lower()
        selector = (el.get("selector") or "").lower()

        score = 0
        if tag in {"input", "textarea"}:
            score += 4
        if input_type in {"search", "text"}:
            score += 3
        if "search" in placeholder:
            score += 4
        if "search" in aria:
            score += 4
        if "search" in selector:
            score += 2
        if "wikipedia" in placeholder or "wikipedia" in aria:
            score += 1
        if "search" in text:
            score += 1

        if score > best_score:
            best_score = score
            best_id = int(el["element_id"])

    if best_score <= 0:
        return None
    return best_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 1 demo: search Wikipedia with Playwright.")
    parser.add_argument("--headless", action="store_true", help="Run Chromium in headless mode.")
    parser.add_argument("--query", default="Web agent", help="Search query.")
    parser.add_argument("--url", default="https://www.wikipedia.org/", help="Start URL.")
    args = parser.parse_args()

    trace_dir = ensure_dir(DEFAULT_TRACE_DIR / f"demo_search_{utc_timestamp_for_filename()}")

    env = WebBrowserEnv(trace_dir=trace_dir, headless=args.headless, slow_mo_ms=150)

    try:
        env.start()
        open_result = env.open_url(args.url)
        if not open_result.get("success"):
            print(f"Failed to open URL: {open_result}")
            return 1

        observation = env.get_observation()
        search_box_id = find_wikipedia_search_box(observation["clickable_elements"])

        if search_box_id is None:
            print("Could not find a search input. First extracted elements:")
            for el in observation["clickable_elements"][:20]:
                print(el)
            return 2

        steps = [
            {"action": "click", "element_id": search_box_id},
            {"action": "type", "text": args.query},
            {"action": "press", "key": "Enter"},
            {"action": "wait", "seconds": 3},
        ]

        for action in steps:
            result = env.execute_action(action)
            print(f"Action: {action} -> {result}")
            if not result.get("success"):
                print("Stopping because an action failed.")
                return 3

        final_path = trace_dir / "final.png"
        env.get_screenshot(final_path)

        print("\nDemo finished.")
        print(f"Trace directory: {trace_dir}")
        print(f"Log file: {env.log_path}")
        print(f"Final screenshot: {final_path}")
        print(f"Current URL: {env.current_url(safe=True)}")
        return 0

    finally:
        env.close()


if __name__ == "__main__":
    raise SystemExit(main())
