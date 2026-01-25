#!/bin/bash
set -e

echo "🚀 Auto-deploying TSHOP Bot to 13.63.48.32..."

# Variables
PEM="ttshope.pem"
SERVER="ubuntu@13.63.48.32"
REMOTE="/home/ubuntu/telepannel"
LOCAL="./TSHOP/telepannel-main"

# Step 1: Test connection
echo "🔐 Testing SSH connection..."
ssh -i "$PEM" -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$SERVER" "echo '✅ Connected'" || {
    echo "❌ SSH connection failed!"
    exit 1
}

# Step 2: Create directory
echo "📁 Creating remote directory..."
ssh -i "$PEM" "$SERVER" "mkdir -p $REMOTE"

# Step 3: Upload files
echo "📤 Uploading files (this may take a minute)..."
rsync -avz --progress --delete \
    -e "ssh -i $PEM -o StrictHostKeyChecking=no" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='*.log' \
    --exclude='.venv' \
    --exclude='venv' \
    --exclude='*.db' \
    "$LOCAL/" "$SERVER:$REMOTE/" 2>&1 | grep -v "^sending incremental" | tail -20

# Step 4: Setup server
echo "⚙️ Setting up server..."
ssh -i "$PEM" "$SERVER" bash << 'EOF'
cd /home/ubuntu/telepannel

# Update system
sudo apt-get update -qq
sudo apt-get install -y python3 python3-pip python3-venv -qq

# Create venv
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "✅ Setup complete"
EOF

# Step 5: Create systemd service
echo "🔧 Creating systemd service..."
ssh -i "$PEM" "$SERVER" 'sudo tee /etc/systemd/system/tshop-bot.service > /dev/null' << 'EOF'
[Unit]
Description=TSHOP Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/telepannel
ExecStart=/home/ubuntu/telepannel/venv/bin/python3 main.py
Restart=always
RestartSec=10
StandardOutput=append:/home/ubuntu/telepannel/bot.log
StandardError=append:/home/ubuntu/telepannel/bot_error.log

[Install]
WantedBy=multi-user.target
EOF

# Step 6: Start service
echo "🚀 Starting bot service..."
ssh -i "$PEM" "$SERVER" bash << 'EOF'
sudo systemctl daemon-reload
sudo systemctl enable tshop-bot.service
sudo systemctl restart tshop-bot.service
sleep 2
sudo systemctl status tshop-bot.service --no-pager -l
EOF

echo ""
echo "✅ DEPLOYMENT COMPLETE!"
echo ""
echo "📋 Management commands:"
echo "   Status:  ssh -i $PEM $SERVER 'sudo systemctl status tshop-bot'"
echo "   Logs:    ssh -i $PEM $SERVER 'tail -f /home/ubuntu/telepannel/bot.log'"
echo "   Restart: ssh -i $PEM $SERVER 'sudo systemctl restart tshop-bot'"
echo ""
