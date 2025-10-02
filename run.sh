#!/bin/bash

set -euo pipefail

# This script is designed to run your Telegram bot 24/7 on a server.

# Find the directory where the script is located. This allows the script to be run from anywhere.
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

LOG_FILE="${DIR}/bot.log"
VENV_DIR="${DIR}/.venv"

echo "[telepannel] Working dir: ${DIR}"

# --- Stop any existing bot process ---
echo "[telepannel] Attempting to stop any existing bot process..."
pkill -f "python[[:digit:]]* ${DIR}/main.py" || true
sleep 2 # Give it a moment to shut down

# --- Ensure Python and venv ---
if ! command -v python3 >/dev/null 2>&1; then
	echo "[telepannel] python3 not found on PATH. Please install Python 3.10+ and re-run."
	exit 1
fi

if [ ! -d "${VENV_DIR}" ]; then
	echo "[telepannel] Creating virtual environment at ${VENV_DIR}..."
	python3 -m venv "${VENV_DIR}"
fi

echo "[telepannel] Activating virtual environment..."
source "${VENV_DIR}/bin/activate"

PY_BIN="${VENV_DIR}/bin/python"
PIP_BIN="${VENV_DIR}/bin/pip"

echo "[telepannel] Using Python: $(${PY_BIN} -V)"

# --- Install dependencies ---
if [ -f "${DIR}/requirements.txt" ]; then
	echo "[telepannel] Installing/upgrading dependencies from requirements.txt..."
	${PIP_BIN} install --upgrade pip >/dev/null
	${PIP_BIN} install -r "${DIR}/requirements.txt"
else
	echo "[telepannel] requirements.txt not found. Skipping dependency installation."
fi

# --- Start the bot in the background ---
echo "[telepannel] Starting the bot in the background..."
nohup ${PY_BIN} "${DIR}/main.py" > "${LOG_FILE}" 2>&1 &
PID=$!

echo "✅ Bot has been started successfully. (PID: ${PID})"
echo "Logs are being written to ${LOG_FILE}"
echo "To view logs in real-time, use: tail -f ${LOG_FILE}"
echo "To stop the bot, use the stop.sh script."
