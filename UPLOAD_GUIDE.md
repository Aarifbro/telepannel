# Quick Upload to Server Guide

This guide shows you how to quickly upload and deploy your Telegram bot to a server.

## Prerequisites
- A server with SSH access (VPS, dedicated server, etc.)
- Python 3.8+ installed on the server
- Basic SSH knowledge

## Method 1: Using the Upload Script (Recommended)

### Step 1: Upload Files
From your local machine where you have the bot code:

```bash
./upload-to-server.sh user@your-server-ip
```

Example:
```bash
./upload-to-server.sh root@192.168.1.100
# or
./upload-to-server.sh ubuntu@myserver.com
```

### Step 2: Connect to Server
```bash
ssh user@your-server-ip
```

### Step 3: Navigate to Bot Directory
```bash
cd /opt/telepannel
```

### Step 4: Create Configuration
```bash
nano .env
```

Add your bot configuration:
```env
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_ID=123456789
DB_PATH=/opt/telepannel/escrow_bot.db
```

Save with `Ctrl+X`, then `Y`, then `Enter`.

### Step 5: Run Setup
```bash
sudo ./setup.sh
```

### Step 6: Deploy as Service
```bash
sudo ./deploy.sh
```

**Done!** Your bot is now running 24/7 and will auto-start on server reboot.

### Check Status
```bash
sudo systemctl status escrow-bot
```

### View Logs
```bash
sudo journalctl -u escrow-bot -f
```

## Method 2: Manual Upload with SCP

### Upload Files
```bash
scp -r . user@your-server-ip:/opt/telepannel
```

Then follow steps 2-6 from Method 1.

## Method 3: Using Git (if your repo is pushed)

### On the Server
```bash
cd /opt
sudo git clone https://github.com/Aarifbro/telepannel.git
cd telepannel
```

Then follow steps 4-6 from Method 1.

## Updating the Bot

When you make changes and want to update the server:

### Option A: Using Upload Script
```bash
./upload-to-server.sh user@your-server-ip
ssh user@your-server-ip "sudo systemctl restart escrow-bot"
```

### Option B: Using Git
On the server:
```bash
cd /opt/telepannel
git pull
sudo systemctl restart escrow-bot
```

## Common Commands

| Action | Command |
|--------|---------|
| Start bot | `sudo systemctl start escrow-bot` |
| Stop bot | `sudo systemctl stop escrow-bot` |
| Restart bot | `sudo systemctl restart escrow-bot` |
| Check status | `sudo systemctl status escrow-bot` |
| View logs | `sudo journalctl -u escrow-bot -f` |
| View last 50 logs | `sudo journalctl -u escrow-bot -n 50` |

## Troubleshooting

### Bot not starting?
```bash
# Check the logs for errors
sudo journalctl -u escrow-bot -n 50

# Try running manually to see the error
cd /opt/telepannel
source venv/bin/activate
python3 bot.py
```

### Permission denied?
```bash
# Fix permissions
sudo chown -R $USER:$USER /opt/telepannel
```

### Changes not reflecting?
```bash
# Make sure to restart after uploading
sudo systemctl restart escrow-bot
```

## Security Tips

1. **Use SSH keys** instead of passwords
2. **Don't commit .env file** to git (it's already in .gitignore)
3. **Regularly update** your server:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```
4. **Backup your database** regularly:
   ```bash
   cp /opt/telepannel/escrow_bot.db ~/backup/
   ```

## Need More Help?

- Full deployment guide: [DEPLOYMENT.md](DEPLOYMENT.md)
- Docker deployment: See `Dockerfile` and `docker-compose.yml`
- Cloud platforms: See [RAILWAY.md](RAILWAY.md)
- Main documentation: [README.md](README.md)

---

**Pro Tip:** Set up automatic deployments with a git hook or CI/CD pipeline for seamless updates!
