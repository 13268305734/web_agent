#!/usr/bin/env bash
set -euo pipefail

# Run from project root no matter where the script is invoked.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

export VLM_MODEL_PATH="${VLM_MODEL_PATH:-/data1/xiangkun/MODELS/Qwen2.5-VL-7B-Instruct}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-1}"
export GRADIO_SERVER_NAME="${GRADIO_SERVER_NAME:-0.0.0.0}"
export GRADIO_SERVER_PORT="${GRADIO_SERVER_PORT:-7860}"

python - <<'PY'
missing = []
for pkg in ["gradio", "playwright"]:
    try:
        __import__(pkg)
    except Exception:
        missing.append(pkg)
if missing:
    print("[WARN] Missing packages:", ", ".join(missing))
    print("Install with:")
    print("  pip install -r requirements_webui.txt")
    print("  python -m playwright install chromium")
PY

python -m webui.app --server-name "$GRADIO_SERVER_NAME" --server-port "$GRADIO_SERVER_PORT"
