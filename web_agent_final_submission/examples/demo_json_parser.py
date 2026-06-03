from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from web_agent.models.json_parser import parse_model_action


def main() -> None:
    clickable = [{"element_id": 3, "tag": "input"}]
    samples = [
        '{"thought":"click search","action":"click","element_id":3}',
        '```json\n{"thought":"type query","action":"type","value":"Web agent"}\n```',
        'Here is the action: {"thought":"submit","action":"press","key":"Enter"}',
        'not json at all',
        '{"action":"click","element_id":999}',
    ]

    for raw in samples:
        parsed = parse_model_action(raw, clickable)
        print("RAW:", raw)
        print("PARSED:", json.dumps(parsed, ensure_ascii=False))
        print("-" * 60)


if __name__ == "__main__":
    main()
