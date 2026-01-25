#!/bin/bash

# Deployment script for Telegram Escrow Bot
# This script sets up the bot as a systemd service for 24/7 operation

set -e  # Exit on error

echo "🚀 Telegram Escrow Bot - Deployment Script"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  This script must be run as root (use sudo)"
    exit 1
fi

# Get the directory where script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BOT_DIR="$SCRIPT_DIR"

echo "📁 Bot directory: $BOT_DIR"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✅ Python found: $(python3 --version)"
echo ""

# Check if virtual environment exists
if [ ! -d "$BOT_DIR/venv" ]; then
    echo "⚠️  Virtual environment not found. Running setup first..."
    if [ -f "$BOT_DIR/setup.sh" ]; then
        sudo -u $SUDO_USER bash "$BOT_DIR/setup.sh"
    else
        echo "❌ setup.sh not found. Please run setup.sh first."
        exit 1
    fi
fi

# Check if .env file exists
if [ ! -f "$BOT_DIR/.env" ]; then
    echo "❌ .env file not found!"
    echo ""
    echo "Please create .env file with the following variables:"
    echo "  BOT_TOKEN=your_bot_token_here"
    echo "  ADMIN_ID=your_telegram_user_id"
    echo "  DB_PATH=escrow_bot.db"
    echo ""
    exit 1
fi

echo "✅ Configuration file found"
echo ""

# Get the user who invoked sudo (or current user if not sudo)
DEPLOY_USER="${SUDO_USER:-$USER}"

# Create systemd service file
echo "📝 Creating systemd service file..."

cat > /etc/systemd/system/escrow-bot.service << EOF
[Unit]
Description=Telegram Escrow Bot
After=network.target

[Service]
Type=simple
User=$DEPLOY_USER
WorkingDirectory=$BOT_DIR
Environment="PATH=$BOT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$BOT_DIR/venv/bin/python3 $BOT_DIR/bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Service file created: /etc/systemd/system/escrow-bot.service"
echo ""

# Set correct permissions
echo "🔐 Setting permissions..."
chown -R $DEPLOY_USER:$DEPLOY_USER "$BOT_DIR"
chmod 755 "$BOT_DIR"
chmod 600 "$BOT_DIR/.env"

echo "✅ Permissions set"
echo ""

# Reload systemd
echo "🔄 Reloading systemd..."
systemctl daemon-reload

echo "✅ Systemd reloaded"
echo ""

# Enable service to start on boot
echo "🔌 Enabling service to start on boot..."
systemctl enable escrow-bot.service

echo "✅ Service enabled"
echo ""

# Start the service
echo "▶️  Starting the bot service..."
systemctl start escrow-bot.service

# Wait a moment for service to start
sleep 2

# Check status
echo ""
echo "📊 Service Status:"
echo "=================="
systemctl status escrow-bot.service --no-pager || true

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "Useful commands:"
echo "  Start:   sudo systemctl start escrow-bot"
echo "  Stop:    sudo systemctl stop escrow-bot"
echo "  Restart: sudo systemctl restart escrow-bot"
echo "  Status:  sudo systemctl status escrow-bot"
echo "  Logs:    sudo journalctl -u escrow-bot -f"
echo ""
echo "The bot will now run 24/7 and auto-start on system reboot."
echo ""
