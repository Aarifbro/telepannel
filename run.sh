#!/usr/bin/env bash
# Keep the multi-bot service running with auto-restart and simple logs.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
PY="$ROOT_DIR/.venv/bin/python"
APP="$ROOT_DIR/main.py"
mkdir -p "$LOG_DIR"

# Prefer local venv; fallback to system python
if [ ! -x "$PY" ]; then
  PY="python3"
fi

echo "[run.sh] Starting supervisor loop..."
while true; do
  start_ts=$(date '+%Y-%m-%d %H:%M:%S')
  echo "[run.sh] [$start_ts] Launching app..." | tee -a "$LOG_DIR/app.log"
  "$PY" "$APP" >> "$LOG_DIR/app.log" 2>> "$LOG_DIR/app.err" || true
  end_ts=$(date '+%Y-%m-%d %H:%M:%S')
  echo "[run.sh] [$end_ts] App exited. Restarting in 5s..." | tee -a "$LOG_DIR/app.log"
  sleep 5
done
