#!/usr/bin/env bash
set -euo pipefail

# Optional helper for cloud servers without a desktop.
# It starts Xvfb + a lightweight window manager + x11vnc/noVNC when available,
# then launches the Gradio WebAgent UI. Install commands vary by server image:
#   sudo apt-get update
#   sudo apt-get install -y xvfb fluxbox x11vnc novnc websockify

export DISPLAY="${DISPLAY:-:99}"
export GEOMETRY="${GEOMETRY:-1366x820x24}"

if ! pgrep -f "Xvfb ${DISPLAY}" >/dev/null 2>&1; then
  echo "[INFO] Starting Xvfb on ${DISPLAY} (${GEOMETRY})"
  Xvfb "$DISPLAY" -screen 0 "$GEOMETRY" >/tmp/webagent_xvfb.log 2>&1 &
  sleep 1
fi

if command -v fluxbox >/dev/null 2>&1 && ! pgrep -f "fluxbox" >/dev/null 2>&1; then
  echo "[INFO] Starting fluxbox"
  fluxbox >/tmp/webagent_fluxbox.log 2>&1 &
fi

if command -v x11vnc >/dev/null 2>&1 && ! pgrep -f "x11vnc.*${DISPLAY}" >/dev/null 2>&1; then
  echo "[INFO] Starting x11vnc on :5900"
  x11vnc -display "$DISPLAY" -forever -shared -nopw -rfbport 5900 >/tmp/webagent_x11vnc.log 2>&1 &
fi

if command -v websockify >/dev/null 2>&1 && [ -d /usr/share/novnc ]; then
  if ! pgrep -f "websockify.*6080" >/dev/null 2>&1; then
    echo "[INFO] Starting noVNC on :6080"
    websockify --web=/usr/share/novnc/ 6080 localhost:5900 >/tmp/webagent_novnc.log 2>&1 &
  fi
else
  echo "[WARN] noVNC/websockify not found. Browser window still runs on ${DISPLAY}; install noVNC to view it remotely."
fi

echo "[INFO] Gradio UI: http://SERVER_IP:7860"
echo "[INFO] noVNC view: http://SERVER_IP:6080/vnc.html"
"$(dirname "$0")/run_demo_webui.sh"
