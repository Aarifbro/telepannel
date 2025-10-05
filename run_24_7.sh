#!/bin/bash

set -euo pipefail

# Enhanced 24/7 bot runner with auto-restart functionality
# This script ensures the bot keeps running even if it crashes

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
LOG_FILE="${DIR}/bot.log"
ERROR_LOG="${DIR}/bot_errors.log"
VENV_DIR="${DIR}/.venv"
PID_FILE="${DIR}/bot.pid"
MAX_RESTARTS=10
RESTART_DELAY=5

echo "[telepannel-24/7] Enhanced 24/7 Bot Runner"
echo "[telepannel-24/7] Working dir: ${DIR}"

# Function to log with timestamp
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

# Function to cleanup on exit
cleanup() {
    log_message "Cleaning up..."
    if [ -f "${PID_FILE}" ]; then
        rm -f "${PID_FILE}"
    fi
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Stop any existing bot process
log_message "Stopping any existing bot processes..."
pkill -f "python[[:digit:]]* ${DIR}/main.py" || true
sleep 2

# Ensure Python and venv
if ! command -v python3 >/dev/null 2>&1; then
    log_message "ERROR: python3 not found. Please install Python 3.10+"
    exit 1
fi

if [ ! -d "${VENV_DIR}" ]; then
    log_message "Creating virtual environment..."
    python3 -m venv "${VENV_DIR}"
fi

log_message "Activating virtual environment..."
source "${VENV_DIR}/bin/activate"

PY_BIN="${VENV_DIR}/bin/python"
PIP_BIN="${VENV_DIR}/bin/pip"

log_message "Using Python: $(${PY_BIN} -V)"

# Install dependencies
if [ -f "${DIR}/requirements.txt" ]; then
    log_message "Installing/upgrading dependencies..."
    ${PIP_BIN} install --upgrade pip >/dev/null 2>&1
    ${PIP_BIN} install -r "${DIR}/requirements.txt" >/dev/null 2>&1
fi

# Main loop - keeps restarting the bot if it crashes
restart_count=0
while [ $restart_count -lt $MAX_RESTARTS ]; do
    log_message "Starting bot (attempt $((restart_count + 1))/$MAX_RESTARTS)..."
    
    # Start the bot and capture its PID
    ${PY_BIN} "${DIR}/main.py" >> "${LOG_FILE}" 2>> "${ERROR_LOG}" &
    BOT_PID=$!
    echo $BOT_PID > "${PID_FILE}"
    
    log_message "Bot started with PID: ${BOT_PID}"
    
    # Wait for the bot process to finish
    wait $BOT_PID
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        log_message "Bot exited gracefully (exit code 0)"
        break
    else
        log_message "Bot crashed with exit code: ${EXIT_CODE}"
        restart_count=$((restart_count + 1))
        
        if [ $restart_count -lt $MAX_RESTARTS ]; then
            log_message "Restarting in ${RESTART_DELAY} seconds..."
            sleep $RESTART_DELAY
        else
            log_message "Maximum restart attempts reached. Stopping."
            break
        fi
    fi
done

cleanup