from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from web_agent.browser import WebBrowserEnv
from web_agent.eval.success_checker import check_success
from web_agent.utils.file_utils import ensure_dir, utc_timestamp_for_filename


def main() -> int:
    parser = argparse.ArgumentParser(description="Demo success checker on a live page.")
    parser.add_argument("--url", default="https://www.wikipedia.org/", help="URL to open")
    parser.add_argument("--condition-type", default="title_contains", help="url_contains/text_contains/title_contains/element_text_contains")
    parser.add_argument("--value", default="Wikipedia", help="Expected value")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    trace_dir = ensure_dir(PROJECT_ROOT / "traces" / f"success_check_{utc_timestamp_for_filename()}")
    env = WebBrowserEnv(trace_dir=trace_dir, headless=args.headless)

    try:
        env.start()
        env.open_url(args.url)
        observation = env.get_observation()
        condition = {"type": args.condition_type, "value": args.value}
        result = check_success(observation, condition)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"Trace directory: {trace_dir}")
        return 0
    finally:
        env.close()


if __name__ == "__main__":
    raise SystemExit(main())
