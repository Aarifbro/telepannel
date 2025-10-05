#!/bin/bash

# Start bot in a screen session for 24/7 operation
# Screen allows you to reconnect to the running bot session anytime

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
SESSION_NAME="telepannel-bot"

echo "🚀 Starting Telepannel Bot in Screen Session..."

# Check if screen is installed
if ! command -v screen >/dev/null 2>&1; then
    echo "Installing screen..."
    sudo apt-get update && sudo apt-get install -y screen
fi

# Kill existing screen session if it exists
screen -S "${SESSION_NAME}" -X quit 2>/dev/null || true
sleep 1

# Stop any existing bot processes
pkill -f "python[[:digit:]]* ${DIR}/main.py" || true
sleep 2

# Setup virtual environment
if [ ! -d "${DIR}/.venv" ]; then
    python3 -m venv "${DIR}/.venv"
fi

source "${DIR}/.venv/bin/activate"
pip install -r "${DIR}/requirements.txt" >/dev/null 2>&1

# Create a startup script for screen
cat > "${DIR}/screen_startup.sh" << EOF
#!/bin/bash
cd "${DIR}"
source .venv/bin/activate
echo "🤖 Starting Telepannel Bot..."
echo "📅 Started at: \$(date)"
echo "📁 Working directory: \$(pwd)"
echo "🐍 Python version: \$(python --version)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
python main.py
EOF

chmod +x "${DIR}/screen_startup.sh"

# Start screen session
screen -dmS "${SESSION_NAME}" bash "${DIR}/screen_startup.sh"

echo "✅ Bot started successfully in screen session!"
echo ""
echo "📊 Session name: ${SESSION_NAME}"
echo "🔗 To attach to session: screen -r ${SESSION_NAME}"
echo "🔌 To detach from session: Ctrl+A then D"
echo "📜 To view sessions: screen -ls"
echo "⏹️  To stop bot: screen -S ${SESSION_NAME} -X quit"
echo ""
echo "🎯 Bot is now running 24/7!"
echo "   You can safely close this window and reconnect anytime with:"
echo "   screen -r ${SESSION_NAME}"