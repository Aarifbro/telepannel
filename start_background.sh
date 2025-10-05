#!/bin/bash

# Simple 24/7 runner using nohup - runs in background even when terminal closes

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
LOG_FILE="${DIR}/bot.log"
PID_FILE="${DIR}/bot.pid"
VENV_DIR="${DIR}/.venv"

echo "🚀 Starting Telepannel Bot 24/7..."

# Stop existing processes
pkill -f "python[[:digit:]]* ${DIR}/main.py" || true
sleep 2

# Setup virtual environment
if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"
pip install -r requirements.txt >/dev/null 2>&1

# Start with nohup (continues running even if terminal closes)
nohup python "${DIR}/main.py" > "${LOG_FILE}" 2>&1 &
PID=$!
echo $PID > "${PID_FILE}"

echo "✅ Bot started successfully!"
echo "📊 PID: ${PID}"
echo "📝 Logs: ${LOG_FILE}"
echo "⏹️  To stop: ./stop_24_7.sh"
echo "📜 View logs: tail -f ${LOG_FILE}"

echo ""
echo "🎯 Bot is now running 24/7 in the background!"
echo "   You can safely close this terminal window."