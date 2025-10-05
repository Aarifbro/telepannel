#!/bin/bash
# Bot Status Checker - Fixed Multiple Instance Issue

echo "🤖 ========================================"
echo "    TELEPANNEL BOT - STATUS CHECK"
echo "======================================== 🤖"
echo ""

# Check for running bot processes
echo "🔍 Checking for running bot processes..."
BOT_PROCESSES=$(pgrep -f "^python main.py$" | wc -l)

if [ $BOT_PROCESSES -eq 0 ]; then
    echo "❌ No bot processes running"
    echo ""
    echo "💡 To start the bot:"
    echo "   ./launch.sh (recommended - 24/7 operation)"
    echo "   OR"
    echo "   python main.py (direct start)"
elif [ $BOT_PROCESSES -eq 1 ]; then
    echo "✅ Bot is running (1 process - GOOD)"
    
    # Get process details
    ps aux | grep "python main.py" | grep -v grep | while read line; do
        echo "   Process: $line"
    done
    
    # Check screen sessions
    echo ""
    echo "📺 Screen sessions:"
    if screen -ls | grep telepannel > /dev/null; then
        echo "   ✅ Bot running in screen session"
        echo "   🔗 To connect: screen -r telepannel-bot"
        echo "   🔌 To detach: Ctrl+A then D"
    else
        echo "   ⚠️  Bot not in screen session (running directly)"
    fi
    
else
    echo "🚨 MULTIPLE BOT INSTANCES DETECTED ($BOT_PROCESSES processes)"
    echo ""
    echo "This causes Telegram API 409 conflicts!"
    echo ""
    echo "🛠️  To fix:"
    echo "   1. pkill -f \"python.*main.py\"  # Stop all bots"
    echo "   2. sleep 5                      # Wait for API"
    echo "   3. ./launch.sh                  # Start fresh"
    echo ""
    echo "Running processes:"
    ps aux | grep "python main.py" | grep -v grep
fi

echo ""
echo "📊 Quick Actions:"
echo "   🚀 Start: ./launch.sh"
echo "   🛑 Stop:  pkill -f \"python.*main.py\""
echo "   📜 Logs:  screen -r telepannel-bot"
echo ""

# Test if products.json is healthy
echo "🏪 Shop Status:"
if python3 -c "import json; products = json.load(open('products.json')); print(f'✅ {len(products)} categories loaded')" 2>/dev/null; then
    echo "   ✅ Products loaded successfully"
else
    echo "   ❌ Products.json has issues"
fi

echo ""
echo "🎯 Enhanced CC Shop Management: ACTIVE"
echo "   💳 Ready CCs and BINs have specialized wizards"
echo "   ⚡ Quick Add, 📋 Full Details, 📦 Bulk Add available"