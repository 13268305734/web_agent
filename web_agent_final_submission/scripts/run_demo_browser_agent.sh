#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

TASK="${1:-在百度搜索 Qwen2.5-VL，并打开第一个可信结果}"
python examples/demo_web_task.py --task "$TASK" --mode browser_demo_fallback --headed --post-action-sleep 1
