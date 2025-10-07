#!/bin/bash
# Simple watchdog to ensure the bot process stays alive.
# Cron example (every 2 minutes): */2 * * * * /opt/telepannel/watchdog.sh >> /opt/telepannel/watchdog.log 2>&1

set -euo pipefail
cd "$(dirname "$0")"

TARGET="main.py"
VENV=".venv/bin/python"

if pgrep -f "$TARGET" >/dev/null 2>&1; then
  echo "[$(date -Iseconds)] Bot running"
  exit 0
fi

echo "[$(date -Iseconds)] Bot not running - starting"
nohup $VENV main.py >/dev/null 2>&1 &
