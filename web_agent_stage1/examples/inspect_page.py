from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from web_agent.browser import WebBrowserEnv
from web_agent.config.settings import DEFAULT_TRACE_DIR
from web_agent.utils.file_utils import ensure_dir, utc_timestamp_for_filename


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect clickable elements on a web page.")
    parser.add_argument("url", help="URL to inspect.")
    parser.add_argument("--headless", action="store_true", help="Run Chromium in headless mode.")
    parser.add_argument("--limit", type=int, default=30, help="Number of elements to print.")
    args = parser.parse_args()

    trace_dir = ensure_dir(DEFAULT_TRACE_DIR / f"inspect_page_{utc_timestamp_for_filename()}")
    env = WebBrowserEnv(trace_dir=trace_dir, headless=args.headless)

    try:
        env.start()
        result = env.open_url(args.url)
        if not result.get("success"):
            print(result)
            return 1

        obs = env.get_observation()
        print(f"Title: {obs['title']}")
        print(f"URL: {obs['url']}")
        print(f"Screenshot: {obs['screenshot_path']}")
        print(f"Clickable elements: {len(obs['clickable_elements'])}")
        print()

        for el in obs["clickable_elements"][: args.limit]:
            print(json.dumps(el, ensure_ascii=False, indent=2))

        print(f"\nTrace directory: {trace_dir}")
        print(f"Log file: {env.log_path}")
        return 0
    finally:
        env.close()


if __name__ == "__main__":
    raise SystemExit(main())
