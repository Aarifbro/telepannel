#!/bin/bash

# Quick upload/sync script to server
# Usage: ./upload-to-server.sh user@server-ip

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 user@server-ip"
    echo ""
    echo "Example: $0 root@192.168.1.100"
    echo "         $0 ubuntu@myserver.com"
    exit 1
fi

SERVER="$1"
REMOTE_DIR="/opt/telepannel"

echo "🚀 Uploading to server: $SERVER"
echo "================================"
echo ""

# Check if .env exists locally
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found locally"
    echo "   You'll need to create it on the server"
    echo ""
fi

echo "⚠️  Security Note: .env file is NOT uploaded (contains sensitive credentials)"
echo "   You will need to create it manually on the server"
echo ""

# Sync files to server (excluding sensitive and unnecessary files)
echo "📤 Syncing files to server..."
echo "   Excluding: .git, venv, node_modules, __pycache__, *.db, *.log, .env"
echo ""
rsync -avz --progress \
    --exclude='.git' \
    --exclude='venv' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.db' \
    --exclude='*.log' \
    --exclude='.env' \
    --exclude='data/' \
    ./ "$SERVER:$REMOTE_DIR/"

echo ""
echo "✅ Files uploaded successfully!"
echo ""
echo "⚠️  IMPORTANT: .env file was NOT uploaded for security reasons"
echo ""
echo "Next steps on the server:"
echo "1. SSH into the server: ssh $SERVER"
echo "2. Navigate to the bot directory: cd $REMOTE_DIR"
echo "3. Create .env file with your credentials:"
echo "   nano .env"
echo "   Add the following:"
echo "     BOT_TOKEN=your_bot_token_from_botfather"
echo "     ADMIN_ID=your_telegram_user_id"
echo "     DB_PATH=$REMOTE_DIR/escrow_bot.db"
echo "4. Run setup: sudo ./setup.sh"
echo "5. Deploy as service: sudo ./deploy.sh"
echo ""
echo "For detailed instructions, see DEPLOYMENT.md"
echo ""
