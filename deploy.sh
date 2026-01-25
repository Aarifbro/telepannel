#!/bin/bash

# Deployment script for TSHOP Bot
SERVER_IP="13.63.48.32"
SERVER_USER="ubuntu"
PEM_KEY="ttshope.pem"
REMOTE_DIR="/home/ubuntu/telepannel"
LOCAL_DIR="./TSHOP/telepannel-main"

echo "🚀 Starting deployment to $SERVER_IP..."

# Step 1: Create remote directory
echo "📁 Creating remote directory..."
ssh -i "$PEM_KEY" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" "mkdir -p $REMOTE_DIR"

# Step 2: Copy files to server
echo "📤 Uploading bot files..."
rsync -avz --progress -e "ssh -i $PEM_KEY -o StrictHostKeyChecking=no" \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.git' \
  --exclude='*.log' \
  --exclude='.venv' \
  "$LOCAL_DIR/" "$SERVER_USER@$SERVER_IP:$REMOTE_DIR/"

# Step 3: Install dependencies and setup on server
echo "⚙️ Installing dependencies on server..."
ssh -i "$PEM_KEY" "$SERVER_USER@$SERVER_IP" bash << 'ENDSSH'
cd /home/ubuntu/telepannel

# Install Python and pip
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install --upgrade pip
pip install -r requirements.txt

# Make scripts executable
chmod +x start.sh restart.sh

echo "✅ Dependencies installed"
ENDSSH

# Step 4: Create systemd service
echo "🔧 Creating systemd service..."
ssh -i "$PEM_KEY" "$SERVER_USER@$SERVER_IP" bash << 'ENDSSH'
sudo tee /etc/systemd/system/tshop-bot.service > /dev/null << 'EOF'
[Unit]
Description=TSHOP Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/telepannel
ExecStart=/home/ubuntu/telepannel/venv/bin/python3 /home/ubuntu/telepannel/main.py
Restart=always
RestartSec=10
StandardOutput=append:/home/ubuntu/telepannel/bot.log
StandardError=append:/home/ubuntu/telepannel/bot_error.log

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload
sudo systemctl enable tshop-bot.service

echo "✅ Service created"
ENDSSH

# Step 5: Start the bot
echo "🚀 Starting bot service..."
ssh -i "$PEM_KEY" "$SERVER_USER@$SERVER_IP" bash << 'ENDSSH'
sudo systemctl restart tshop-bot.service
sleep 3
sudo systemctl status tshop-bot.service --no-pager
ENDSSH

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Useful commands:"
echo "   Check status: ssh -i $PEM_KEY $SERVER_USER@$SERVER_IP 'sudo systemctl status tshop-bot'"
echo "   View logs: ssh -i $PEM_KEY $SERVER_USER@$SERVER_IP 'tail -f /home/ubuntu/telepannel/bot.log'"
echo "   Restart: ssh -i $PEM_KEY $SERVER_USER@$SERVER_IP 'sudo systemctl restart tshop-bot'"
echo "   Stop: ssh -i $PEM_KEY $SERVER_USER@$SERVER_IP 'sudo systemctl stop tshop-bot'"
echo ""
