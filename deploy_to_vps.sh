#!/bin/bash
# ============================================================
# Deploy Telepannel Bot to VPS
# Target: root@203.57.85.72
# Usage: chmod +x deploy_to_vps.sh && ./deploy_to_vps.sh
# ============================================================
set -e

VPS_HOST="203.57.85.72"
VPS_USER="root"
VPS_DIR="/opt/telepannel"
BOT_SRC="TSHOP/telepannel-main"
SSH_KEY="ttbot.pem"

# SSH options (skip host-key check for first-time connections)
SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=15"
if [ -f "$SSH_KEY" ]; then
    SSH_OPTS="$SSH_OPTS -i $SSH_KEY"
fi

SSH_CMD="ssh $SSH_OPTS $VPS_USER@$VPS_HOST"
SCP_CMD="scp $SSH_OPTS"

echo "======================================"
echo "  Deploying Telepannel to VPS"
echo "  Host: $VPS_USER@$VPS_HOST"
echo "  Path: $VPS_DIR"
echo "======================================"

# --- 1. Verify SSH connection ---
echo ""
echo "[1/5] Verifying SSH connection..."
$SSH_CMD "echo '  Connection OK'" || {
    echo ""
    echo "ERROR: Cannot connect to $VPS_USER@$VPS_HOST"
    echo "  - Make sure the VPS is reachable"
    if [ -f "$SSH_KEY" ]; then
        echo "  - Check that $SSH_KEY has correct permissions (chmod 600 $SSH_KEY)"
    else
        echo "  - You will be prompted for the root password"
    fi
    exit 1
}

# --- 2. Create remote directory ---
echo "[2/5] Creating remote directory $VPS_DIR..."
$SSH_CMD "mkdir -p $VPS_DIR"

# --- 3. Transfer bot files ---
echo "[3/5] Transferring bot files..."
# Use rsync if available, otherwise fall back to scp
if command -v rsync &>/dev/null; then
    if [ -f "$SSH_KEY" ]; then
        RSYNC_E="ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new"
    else
        RSYNC_E="ssh -o StrictHostKeyChecking=accept-new"
    fi
    rsync -az --delete -e "$RSYNC_E" \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude '.venv' \
        --exclude 'venv' \
        --exclude '*.db' \
        --exclude '*.db-shm' \
        --exclude '*.db-wal' \
        --exclude '.env' \
        "$BOT_SRC/" \
        "$VPS_USER@$VPS_HOST:$VPS_DIR/"
else
    # Tar + ssh pipe (works without rsync)
    tar -czf - \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.venv' \
        --exclude='venv' \
        --exclude='*.db' \
        --exclude='*.db-shm' \
        --exclude='*.db-wal' \
        --exclude='.env' \
        -C "$BOT_SRC" . | \
        $SSH_CMD "tar -xzf - -C $VPS_DIR"
fi

# --- 4. Transfer setup script ---
echo "[4/5] Uploading setup script..."
$SCP_CMD vps_setup.sh "$VPS_USER@$VPS_HOST:$VPS_DIR/vps_setup.sh"
$SSH_CMD "chmod +x $VPS_DIR/vps_setup.sh"

# --- 5. Run setup on VPS ---
echo "[5/5] Running setup on VPS..."
$SSH_CMD "bash $VPS_DIR/vps_setup.sh"

echo ""
echo "======================================"
echo "  Deployment Complete!"
echo "======================================"
echo ""
echo "Connect to your VPS:"
if [ -f "$SSH_KEY" ]; then
    echo "  ssh -i $SSH_KEY $VPS_USER@$VPS_HOST"
else
    echo "  ssh $VPS_USER@$VPS_HOST"
fi
echo ""
echo "Manage the bot:"
echo "  Status : systemctl status telepannel"
echo "  Logs   : journalctl -u telepannel -f"
echo "  Restart: systemctl restart telepannel"
echo "  Stop   : systemctl stop telepannel"
echo ""
