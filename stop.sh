#!/bin/bash

# This script safely stops the running Telegram bot.

# Find the directory where the script is located.
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

echo "Searching for the bot process..."
# Find the process ID (PID) of the bot.
PID=$(pgrep -f "python3 ${DIR}/main.py")

if [ -z "$PID" ]; then
  echo "Bot is not currently running."
else
  echo "Found bot process with PID: $PID. Stopping it now..."
  # Kill the process by its PID.
  kill $PID
  sleep 1
  echo "✅ Bot has been stopped."
fi
