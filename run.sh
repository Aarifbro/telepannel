#!/bin/bash

# This script is designed to run your Telegram bot 24/7 on a server.

# Find the directory where the script is located. This allows the script to be run from anywhere.
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# --- Stop any existing bot process ---
# This is important to prevent multiple instances of the bot from running.
# It finds any process running 'python3 main.py' and stops it.
echo "Attempting to stop any existing bot process..."
pkill -f "python3 ${DIR}/main.py"
sleep 2 # Give it a moment to shut down

# --- Activate Virtual Environment ---
# This command loads the Python environment that has all your packages (like py-telegram-bot-api) installed.
echo "Activating virtual environment..."
source "${DIR}/.venv/bin/activate"

# --- Start the bot in the background ---
# 'nohup' ensures the bot keeps running even if you close your terminal.
# '>' redirects the standard output to 'bot.log'.
# '2>&1' redirects standard error to the same place as standard output.
# '&' runs the command in the background.
echo "Starting the bot in the background..."
nohup python3 "${DIR}/main.py" > "${DIR}/bot.log" 2>&1 &

echo "✅ Bot has been started successfully."
echo "Logs are being written to ${DIR}/bot.log"
echo "To view logs in real-time, use: tail -f ${DIR}/bot.log"
echo "To stop the bot, use the stop.sh script."
