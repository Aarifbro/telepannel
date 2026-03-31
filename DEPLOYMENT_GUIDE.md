# Telepannel Bot Deployment Guide

## Server Information

### Current VPS (root access)
- **Server IP**: 203.57.85.72
- **User**: root
- **Remote Path**: /opt/telepannel
- **SSH Key**: ttbot.pem (or password auth)
- **Service name**: telepannel

### Legacy server
- **Server IP**: 13.63.29.233
- **User**: ubuntu
- **Remote Path**: /home/ubuntu/TTbot

## Initial Deployment to VPS (203.57.85.72)

### Step 1: Set correct permissions on SSH key (if using key auth)
```bash
chmod 600 ttbot.pem
```

### Step 2: Run the deployment script
```bash
chmod +x deploy_to_vps.sh
./deploy_to_vps.sh
```

This script will:
1. ✓ Verify SSH connection to root@203.57.85.72
2. ✓ Create `/opt/telepannel` on the VPS
3. ✓ Transfer all bot files
4. ✓ Upload and run `vps_setup.sh` which:
   - Installs Python 3, pip, venv, screen
   - Creates a Python virtual environment
   - Installs all dependencies from `requirements.txt`
   - Installs and enables the `telepannel` systemd service
   - Starts the bot automatically

### Step 3: SSH into the VPS and verify
```bash
ssh root@203.57.85.72
systemctl status telepannel
journalctl -u telepannel -f
```

## Quick Updates

After initial setup, re-run the deploy script to push code changes:
```bash
./deploy_to_vps.sh
```

Or manually sync only the bot files (requires rsync):
```bash
rsync -az --exclude '__pycache__' --exclude '*.pyc' --exclude '.venv' \
    TSHOP/telepannel-main/ root@203.57.85.72:/opt/telepannel/
ssh root@203.57.85.72 "systemctl restart telepannel"
```

## Manual VPS Setup (without deploy script)

If you prefer to set up the VPS manually:

```bash
# 1. SSH in
ssh root@203.57.85.72

# 2. Install prerequisites
apt-get update && apt-get install -y python3 python3-pip python3-venv git screen

# 3. Create directory and upload files (from local machine)
mkdir -p /opt/telepannel
# (run scp or rsync from your local machine to copy TSHOP/telepannel-main/* to /opt/telepannel/)

# 4. Set up virtual environment and install deps
cd /opt/telepannel
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 5. Copy and enable systemd service
cp telepannel.service.example /etc/systemd/system/telepannel.service
systemctl daemon-reload
systemctl enable telepannel
systemctl start telepannel
```

## Bot Management on VPS

### SSH into the VPS
```bash
# Using SSH key
ssh -i ttbot.pem root@203.57.85.72

# Using password
ssh root@203.57.85.72
```

### Navigate to bot directory
```bash
cd /opt/telepannel
```

### Systemd Service Commands
```bash
# Check status
systemctl status telepannel

# Start bot
systemctl start telepannel

# Stop bot
systemctl stop telepannel

# Restart bot
systemctl restart telepannel

# Enable auto-start on boot
systemctl enable telepannel

# Disable auto-start
systemctl disable telepannel

# View logs (live)
journalctl -u telepannel -f

# View last 100 lines
journalctl -u telepannel -n 100
```

### Manual Start (without systemd)
```bash
cd /opt/telepannel
source .venv/bin/activate
python3 main.py
```

### Screen Session Commands
```bash
# Start in screen
screen -dmS telepannel bash -c 'cd /opt/telepannel && source .venv/bin/activate && python3 main.py'

# Attach to session
screen -r telepannel

# Detach from session (while inside)
# Press: Ctrl+A, then D

# List all sessions
screen -ls

# Kill session
screen -X -S telepannel quit
```

## Troubleshooting

### Bot not starting
1. Check logs:
   ```bash
   journalctl -u telepannel -n 50
   ```

2. Test manually to see full error output:
   ```bash
   cd /opt/telepannel
   source .venv/bin/activate
   python3 main.py
   ```

3. Check config:
   ```bash
   cat /opt/telepannel/config.py
   ```

### Permission issues
```bash
# Fix permissions (running as root so no sudo needed)
chmod -R 755 /opt/telepannel
```

### Dependencies issues
```bash
cd /opt/telepannel
source .venv/bin/activate
pip install -r requirements.txt --force-reinstall
```

### SSH connection issues
```bash
# Verify key permissions
chmod 600 ttbot.pem

# Test connection verbosely
ssh -i ttbot.pem -v root@203.57.85.72
```

## Environment Variables

Override config values without editing `config.py` by setting env vars in the systemd service:

1. Edit the service file:
   ```bash
   nano /etc/systemd/system/telepannel.service
   ```

2. Add environment variables in the `[Service]` section:
   ```ini
   Environment="API_ID=your_api_id"
   Environment="API_HASH=your_api_hash"
   Environment="MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/db"
   ```

3. Reload and restart:
   ```bash
   systemctl daemon-reload
   systemctl restart telepannel
   ```

## Monitoring

### Check if bot is running
```bash
# Using systemd
systemctl is-active telepannel

# Using ps
ps aux | grep main.py
```

### Monitor resource usage
```bash
# CPU and memory
top
htop
```

## Backup

### Backup bot data from VPS
```bash
# From your local machine
rsync -avz root@203.57.85.72:/opt/telepannel/accounts/ ./backup/accounts/
```

## Security Notes

1. Keep `ttbot.pem` secure (never commit to git)
2. Use environment variables for sensitive data instead of editing `config.py`
3. Regularly update the VPS:
   ```bash
   apt-get update && apt-get upgrade
   ```
4. Monitor logs for suspicious activity

## Support

For issues or questions:
1. Check logs first: `journalctl -u telepannel -f`
2. Verify all dependencies are installed
3. Ensure config files are properly set up
4. Test manually before using systemd service
