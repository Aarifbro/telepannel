# Telepannel Bot Deployment Guide

## Server Information
- **Server IP**: 13.63.29.233
- **User**: ubuntu
- **Remote Path**: /home/ubuntu/TTbot
- **SSH Key**: ttbot.pem

## Initial Deployment

### Step 1: Run the deployment script
```bash
chmod +x deploy_to_server.sh
./deploy_to_server.sh
```

This script will:
1. ✓ Verify SSH connection
2. ✓ Create remote directory structure
3. ✓ Transfer all bot files
4. ✓ Install Python and dependencies
5. ✓ Set up systemd service
6. ✓ Start the bot

### Step 2: Choose startup method
When prompted, select:
- **Option 1**: Systemd service (recommended) - Auto-restarts on failure
- **Option 2**: Screen session - Manual control
- **Option 3**: Manual start - You'll start it yourself

## Quick Updates

After initial setup, use the quick deploy script to update files:
```bash
chmod +x quick_deploy.sh
./quick_deploy.sh
```

## Bot Management

Use the management script for common tasks:
```bash
chmod +x manage_bot.sh
./manage_bot.sh
```

Available options:
1. Check bot status
2. View live logs
3. Start bot
4. Stop bot
5. Restart bot
6. SSH into server
7. Update bot files
8. View error logs

## Manual Commands

### SSH into the server
```bash
ssh -i ttbot.pem ubuntu@13.63.29.233
```

### Navigate to bot directory
```bash
cd /home/ubuntu/TTbot
```

### Systemd Service Commands
```bash
# Check status
sudo systemctl status ttbot

# Start bot
sudo systemctl start ttbot

# Stop bot
sudo systemctl stop ttbot

# Restart bot
sudo systemctl restart ttbot

# Enable auto-start on boot
sudo systemctl enable ttbot

# Disable auto-start
sudo systemctl disable ttbot

# View logs (live)
sudo journalctl -u ttbot -f

# View last 100 lines
sudo journalctl -u ttbot -n 100
```

### Manual Start (without systemd)
```bash
cd /home/ubuntu/TTbot
source venv/bin/activate
python3 main.py
```

### Screen Session Commands
```bash
# Start in screen
screen -dmS ttbot bash -c 'cd /home/ubuntu/TTbot && source venv/bin/activate && python3 main.py'

# Attach to session
screen -r ttbot

# Detach from session (while inside)
Ctrl+A, then D

# List all sessions
screen -ls

# Kill session
screen -X -S ttbot quit
```

## Troubleshooting

### Bot not starting
1. Check logs:
   ```bash
   sudo journalctl -u ttbot -n 50
   ```

2. Check if config/environment variables are set:
   ```bash
   cd /home/ubuntu/TTbot
   cat config.py
   ```

3. Test manually:
   ```bash
   cd /home/ubuntu/TTbot
   source venv/bin/activate
   python3 main.py
   ```

### Permission issues
```bash
# Fix ownership
sudo chown -R ubuntu:ubuntu /home/ubuntu/TTbot

# Fix permissions
chmod -R 755 /home/ubuntu/TTbot
```

### Dependencies issues
```bash
cd /home/ubuntu/TTbot
source venv/bin/activate
pip install -r requirements.txt --force-reinstall
```

### SSH connection issues
```bash
# Verify key permissions
chmod 400 ttbot.pem

# Test connection
ssh -i ttbot.pem -v ubuntu@13.63.29.233
```

## Environment Variables

If your bot requires environment variables (API tokens, etc.), set them in the systemd service:

1. Edit the service file:
   ```bash
   sudo nano /etc/systemd/system/ttbot.service
   ```

2. Add environment variables in the `[Service]` section:
   ```ini
   Environment="BOT_TOKEN=your_token_here"
   Environment="DATABASE_URL=your_db_url"
   ```

3. Reload and restart:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart ttbot
   ```

## Monitoring

### Check if bot is running
```bash
# Using systemd
sudo systemctl is-active ttbot

# Using ps
ps aux | grep main.py
```

### Monitor resource usage
```bash
# CPU and memory
top -p $(pgrep -f main.py)

# Detailed stats
htop
```

## Backup

### Backup bot data
```bash
# From your local machine
rsync -avz -e "ssh -i ttbot.pem" ubuntu@13.63.29.233:/home/ubuntu/TTbot/accounts/ ./backup/accounts/
```

## Security Notes

1. Keep `ttbot.pem` secure (never commit to git)
2. Use environment variables for sensitive data
3. Regularly update the server:
   ```bash
   sudo apt-get update && sudo apt-get upgrade
   ```
4. Monitor logs for suspicious activity

## Support

For issues or questions:
1. Check logs first: `sudo journalctl -u ttbot -f`
2. Verify all dependencies are installed
3. Ensure config files are properly set up
4. Test manually before using systemd service
