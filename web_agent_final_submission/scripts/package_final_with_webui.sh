#!/usr/bin/env bash
set -euo pipefail

# Run this script from the project root after applying the Web UI patch.
OUT="${1:-web_agent_final_webui.zip}"
ROOT_NAME="$(basename "$(pwd)")"
cd ..
zip -r "$OUT" "$ROOT_NAME" \
  -x "*/__pycache__/*" "*.pyc" "*/.ipynb_checkpoints/*" \
  -x "*/traces/raw/*" "*/results/webui_runs/run_*/step_*.png" \
  -x "*/.git/*"
echo "Created: $(pwd)/$OUT"
