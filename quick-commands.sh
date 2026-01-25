#!/bin/bash
# Quick management commands for the bot

PEM_KEY="ttshope.pem"
SERVER="ubuntu@13.63.48.32"

case "$1" in
    logs)
        echo "📋 Viewing bot logs..."
        ssh -i "$PEM_KEY" "$SERVER" "tail -f /home/ubuntu/telepannel/bot.log"
        ;;
    errors)
        echo "❌ Viewing error logs..."
        ssh -i "$PEM_KEY" "$SERVER" "tail -f /home/ubuntu/telepannel/bot_error.log"
        ;;
    status)
        echo "📊 Checking bot status..."
        ssh -i "$PEM_KEY" "$SERVER" "sudo systemctl status tshop-bot.service"
        ;;
    restart)
        echo "🔄 Restarting bot..."
        ssh -i "$PEM_KEY" "$SERVER" "sudo systemctl restart tshop-bot.service"
        echo "✅ Bot restarted"
        ;;
    stop)
        echo "🛑 Stopping bot..."
        ssh -i "$PEM_KEY" "$SERVER" "sudo systemctl stop tshop-bot.service"
        echo "✅ Bot stopped"
        ;;
    start)
        echo "▶️ Starting bot..."
        ssh -i "$PEM_KEY" "$SERVER" "sudo systemctl start tshop-bot.service"
        echo "✅ Bot started"
        ;;
    ssh)
        echo "🔐 Connecting to server..."
        ssh -i "$PEM_KEY" "$SERVER"
        ;;
    update)
        echo "📤 Updating bot files..."
        rsync -avz --progress -e "ssh -i $PEM_KEY -o StrictHostKeyChecking=no" \
          --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' --exclude='*.log' --exclude='.venv' \
          ./TSHOP/telepannel-main/ "$SERVER:/home/ubuntu/telepannel/"
        echo "🔄 Restarting bot..."
        ssh -i "$PEM_KEY" "$SERVER" "sudo systemctl restart tshop-bot.service"
        echo "✅ Update complete"
        ;;
    *)
        echo "Usage: $0 {logs|errors|status|restart|stop|start|ssh|update}"
        echo ""
        echo "Commands:"
        echo "  logs     - View bot logs"
        echo "  errors   - View error logs"
        echo "  status   - Check bot status"
        echo "  restart  - Restart the bot"
        echo "  stop     - Stop the bot"
        echo "  start    - Start the bot"
        echo "  ssh      - Connect to server"
        echo "  update   - Upload files and restart"
        exit 1
        ;;
esac
