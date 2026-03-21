#!/bin/bash
# ============================================================
# VPS Setup Script - Runs ON the VPS (root@203.57.85.72)
# This script is uploaded and executed automatically by
# deploy_to_vps.sh, but you can also run it manually:
#   bash /opt/telepannel/vps_setup.sh
# ============================================================
set -e

BOT_DIR="/opt/telepannel"
SERVICE_NAME="telepannel"
PYTHON_BIN="python3"

echo "======================================"
echo "  Telepannel VPS Setup"
echo "======================================"

# --- 1. System packages ---
echo "[1/6] Installing system packages..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git curl screen

# --- 2. Bot directory ---
echo "[2/6] Setting up bot directory at $BOT_DIR..."
mkdir -p "$BOT_DIR"
cd "$BOT_DIR"

# --- 3. Python virtual environment ---
echo "[3/6] Creating Python virtual environment..."
if [ ! -d "$BOT_DIR/.venv" ]; then
    $PYTHON_BIN -m venv "$BOT_DIR/.venv"
fi
source "$BOT_DIR/.venv/bin/activate"

# --- 4. Python dependencies ---
echo "[4/6] Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r "$BOT_DIR/requirements.txt"

# --- 5. Systemd service ---
echo "[5/6] Installing systemd service..."
cat > /etc/systemd/system/${SERVICE_NAME}.service << 'EOF'
[Unit]
Description=Telepannel Telegram Bot
After=network.target network-online.target
Wants=network-online.target
StartLimitIntervalSec=400
StartLimitBurst=3

[Service]
Type=simple
WorkingDirectory=/opt/telepannel
ExecStart=/opt/telepannel/.venv/bin/python /opt/telepannel/main.py
Restart=on-failure
RestartSec=15
User=root
Group=root
StandardOutput=journal
StandardError=journal
# Hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ${SERVICE_NAME}

# --- 6. Start the bot ---
echo "[6/6] Starting the bot..."
systemctl restart ${SERVICE_NAME}
sleep 3
systemctl status ${SERVICE_NAME} --no-pager

echo ""
echo "======================================"
echo "  Setup Complete!"
echo "======================================"
echo ""
echo "Useful commands:"
echo "  Status : systemctl status ${SERVICE_NAME}"
echo "  Logs   : journalctl -u ${SERVICE_NAME} -f"
echo "  Restart: systemctl restart ${SERVICE_NAME}"
echo "  Stop   : systemctl stop ${SERVICE_NAME}"
echo ""
