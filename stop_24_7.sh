#!/bin/bash

# Enhanced stop script for 24/7 bot operations

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PID_FILE="${DIR}/bot.pid"
SESSION_NAME="telepannel-bot"

echo "🛑 Stopping Telepannel Bot..."

# Method 1: Stop via PID file
if [ -f "${PID_FILE}" ]; then
    PID=$(cat "${PID_FILE}")
    if ps -p $PID > /dev/null 2>&1; then
        echo "📋 Found bot process with PID: ${PID}"
        kill -TERM $PID
        sleep 3
        
        if ps -p $PID > /dev/null 2>&1; then
            echo "⚠️  Process still running, using SIGKILL..."
            kill -KILL $PID
        fi
        
        rm -f "${PID_FILE}"
        echo "✅ Bot stopped via PID file"
    else
        echo "🔍 PID file exists but process not running"
        rm -f "${PID_FILE}"
    fi
fi

# Method 2: Stop via process search
PIDS=$(pgrep -f "python.*main.py" || true)
if [ ! -z "$PIDS" ]; then
    echo "🔍 Found running bot processes: ${PIDS}"
    for pid in $PIDS; do
        kill -TERM $pid
        echo "   Stopped PID: $pid"
    done
    sleep 2
fi

# Method 3: Stop screen session
if command -v screen >/dev/null 2>&1; then
    if screen -ls | grep -q "${SESSION_NAME}"; then
        screen -S "${SESSION_NAME}" -X quit
        echo "📺 Stopped screen session: ${SESSION_NAME}"
    fi
fi

# Verify all processes are stopped
REMAINING=$(pgrep -f "python.*main.py" || true)
if [ ! -z "$REMAINING" ]; then
    echo "⚠️  Some processes still running: ${REMAINING}"
    echo "   Force killing..."
    pkill -9 -f "python.*main.py"
fi

echo "✅ All bot processes stopped successfully!"