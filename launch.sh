#!/bin/bash

# 🚀 Telepannel Bot - Quick 24/7 Launcher
# This script provides an easy menu to start your bot 24/7

clear
echo "🤖 ======================================"
echo "   TELEPANNEL BOT - 24/7 LAUNCHER"
echo "====================================== 🤖"
echo ""
echo "Choose your 24/7 method:"
echo ""
echo "1) 📺 Screen Session (Recommended)"
echo "   → Easy reconnect, view logs, debug"
echo ""
echo "2) 🔄 Auto-Restart Manager (Production)"  
echo "   → Crash recovery, health monitoring"
echo ""
echo "3) 🎯 Simple Background (Set & Forget)"
echo "   → Basic background operation"
echo ""
echo "4) 📊 Check Status"
echo "   → See if bot is running"
echo ""
echo "5) 🛑 Stop All Bots"
echo "   → Stop any running instances"
echo ""
echo "6) 📖 View Logs"
echo "   → Show recent bot logs"
echo ""

read -p "Enter your choice (1-6): " choice

case $choice in
    1)
        echo ""
        echo "🚀 Starting bot in screen session..."
        ./start_screen.sh
        echo ""
        echo "✅ Bot is now running 24/7!"
        echo "💡 To reconnect: screen -r telepannel-bot"
        ;;
    2)
        echo ""
        echo "🚀 Starting bot with auto-restart manager..."
        nohup ./bot_manager.sh start > manager.log 2>&1 &
        sleep 2
        echo "✅ Bot manager started!"
        echo "📊 Status: $(./bot_manager.sh status)"
        echo "📝 Logs: tail -f logs/manager.log"
        ;;
    3)
        echo ""
        echo "🚀 Starting bot in background..."
        ./start_background.sh
        ;;
    4)
        echo ""
        echo "📊 Bot Status:"
        echo "────────────────"
        
        if screen -ls | grep -q telepannel-bot; then
            echo "📺 Screen session: ✅ RUNNING"
        else
            echo "📺 Screen session: ❌ NOT RUNNING"
        fi
        
        if [ -f bot.pid ]; then
            pid=$(cat bot.pid)
            if ps -p $pid > /dev/null 2>&1; then
                echo "🔄 Background bot: ✅ RUNNING (PID: $pid)"
            else
                echo "🔄 Background bot: ❌ NOT RUNNING"
            fi
        else
            echo "🔄 Background bot: ❌ NOT RUNNING"
        fi
        
        if ./bot_manager.sh status >/dev/null 2>&1; then
            echo "🎯 Managed bot: ✅ RUNNING"
        else
            echo "🎯 Managed bot: ❌ NOT RUNNING"
        fi
        
        echo ""
        processes=$(ps aux | grep "python.*main.py" | grep -v grep | wc -l)
        echo "🤖 Total bot processes: $processes"
        ;;
    5)
        echo ""
        echo "🛑 Stopping all bot instances..."
        ./stop_24_7.sh
        echo "✅ All bots stopped!"
        ;;
    6)
        echo ""
        echo "📖 Recent Bot Logs:"
        echo "──────────────────────"
        
        if [ -f bot.log ]; then
            echo "📝 Last 20 lines from bot.log:"
            tail -20 bot.log
        elif [ -f logs/bot.log ]; then
            echo "📝 Last 20 lines from logs/bot.log:"
            tail -20 logs/bot.log
        else
            echo "❌ No log files found"
        fi
        ;;
    *)
        echo ""
        echo "❌ Invalid choice. Please run the script again."
        exit 1
        ;;
esac

echo ""
echo "📚 For full documentation: cat 24_7_GUIDE.md"
echo "🔧 Need help? Read the guide above!"