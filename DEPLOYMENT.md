# Deployment Guide

This guide explains how to deploy the Telegram Escrow Bot to a server for 24/7 operation.

## Deployment Options

### Option 1: Direct Server Deployment (Recommended for VPS)

This method deploys the bot directly on a Linux server using systemd for process management.

#### Prerequisites
- A Linux server (Ubuntu 20.04+ or similar)
- SSH access to the server
- Python 3.8 or higher installed
- Root or sudo access

#### Step-by-Step Instructions

1. **Connect to your server via SSH:**
   ```bash
   ssh user@your-server-ip
   ```

2. **Clone or upload the repository:**
   ```bash
   cd /opt
   sudo git clone https://github.com/Aarifbro/telepannel.git
   cd telepannel
   ```
   
   Or if you're uploading files manually:
   ```bash
   # On your local machine
   scp -r . user@your-server-ip:/opt/telepannel
   ```

3. **Run the setup script:**
   ```bash
   sudo chmod +x setup.sh
   sudo ./setup.sh
   ```

4. **Configure environment variables:**
   ```bash
   sudo nano .env
   ```
   
   Add your bot configuration:
   ```env
   BOT_TOKEN=your_bot_token_from_botfather
   ADMIN_ID=your_telegram_user_id
   DB_PATH=/opt/telepannel/escrow_bot.db
   ```

5. **Install as a system service:**
   ```bash
   sudo chmod +x deploy.sh
   sudo ./deploy.sh
   ```

6. **Start the bot service:**
   ```bash
   sudo systemctl start escrow-bot
   sudo systemctl enable escrow-bot  # Auto-start on boot
   ```

7. **Check status:**
   ```bash
   sudo systemctl status escrow-bot
   ```

8. **View logs:**
   ```bash
   sudo journalctl -u escrow-bot -f
   ```

#### Managing the Service

- **Stop the bot:**
  ```bash
  sudo systemctl stop escrow-bot
  ```

- **Restart the bot:**
  ```bash
  sudo systemctl restart escrow-bot
  ```

- **Check logs:**
  ```bash
  sudo journalctl -u escrow-bot -n 100
  ```

- **Update the bot:**
  ```bash
  cd /opt/telepannel
  sudo git pull
  sudo systemctl restart escrow-bot
  ```

### Option 2: Docker Deployment

Deploy using Docker for isolated and portable deployment.

#### Prerequisites
- Docker installed on your server
- Docker Compose (optional but recommended)

#### Instructions

1. **Build the Docker image:**
   ```bash
   docker build -t escrow-bot .
   ```

2. **Run the container:**
   ```bash
   docker run -d \
     --name escrow-bot \
     --restart unless-stopped \
     -v $(pwd)/.env:/app/.env \
     -v $(pwd)/data:/app/data \
     escrow-bot
   ```

3. **Using Docker Compose:**
   ```bash
   docker-compose up -d
   ```

4. **View logs:**
   ```bash
   docker logs -f escrow-bot
   ```

5. **Stop the container:**
   ```bash
   docker stop escrow-bot
   ```

6. **Update and restart:**
   ```bash
   docker-compose down
   docker-compose pull
   docker-compose up -d
   ```

### Option 3: Cloud Platform Deployment

#### Heroku

1. **Install Heroku CLI:**
   ```bash
   curl https://cli-assets.heroku.com/install.sh | sh
   ```

2. **Login and create app:**
   ```bash
   heroku login
   heroku create your-bot-name
   ```

3. **Set environment variables:**
   ```bash
   heroku config:set BOT_TOKEN=your_bot_token
   heroku config:set ADMIN_ID=your_user_id
   ```

4. **Deploy:**
   ```bash
   git push heroku main
   ```

5. **Scale up:**
   ```bash
   heroku ps:scale worker=1
   ```

#### Railway.app

1. **Connect your GitHub repository to Railway**
2. **Add environment variables in Railway dashboard**
3. **Deploy automatically on push**

#### DigitalOcean App Platform

1. **Connect your GitHub repository**
2. **Configure as a Worker**
3. **Add environment variables**
4. **Deploy**

## Security Best Practices

1. **Never commit `.env` file** - It contains sensitive credentials
2. **Use strong bot tokens** - Generate new tokens if compromised
3. **Restrict server access** - Use SSH keys, disable password auth
4. **Keep system updated:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```
5. **Setup firewall:**
   ```bash
   sudo ufw enable
   sudo ufw allow ssh
   ```
6. **Regular backups** - Backup your database regularly:
   ```bash
   cp /opt/telepannel/escrow_bot.db /backup/escrow_bot.db.$(date +%Y%m%d)
   ```

## Monitoring

### Check if bot is running:
```bash
sudo systemctl status escrow-bot
```

### Monitor resource usage:
```bash
htop  # or
top
```

### Check disk space:
```bash
df -h
```

### Monitor logs in real-time:
```bash
sudo journalctl -u escrow-bot -f
```

## Troubleshooting

### Bot not starting
1. Check logs: `sudo journalctl -u escrow-bot -n 50`
2. Verify `.env` file has correct values
3. Check Python dependencies: `source venv/bin/activate && pip list`
4. Test manually: `cd /opt/telepannel && source venv/bin/activate && python3 bot.py`

### Database errors
1. Check file permissions: `ls -la escrow_bot.db`
2. Verify database path in `.env`
3. Recreate database if corrupted (backup first!)

### Bot stops responding
1. Restart the service: `sudo systemctl restart escrow-bot`
2. Check system resources: `htop`
3. Review logs for errors

### Connection issues
1. Verify internet connectivity: `ping 8.8.8.8`
2. Check if Telegram API is accessible: `curl -I https://api.telegram.org`
3. Verify bot token is valid

## Updating the Bot

### Manual Update
```bash
cd /opt/telepannel
sudo systemctl stop escrow-bot
sudo git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl start escrow-bot
```

### Automated Updates (Optional)
Create a cron job to auto-update:
```bash
sudo crontab -e
```

Add (updates daily at 3 AM):
```
0 3 * * * cd /opt/telepannel && git pull && systemctl restart escrow-bot
```

## Backup Strategy

### Database Backup Script
Create `/opt/telepannel/backup.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/backup/escrow-bot"
mkdir -p $BACKUP_DIR
cp /opt/telepannel/escrow_bot.db "$BACKUP_DIR/escrow_bot.db.$(date +\%Y\%m\%d_\%H\%M\%S)"
# Keep only last 7 days of backups
find $BACKUP_DIR -name "escrow_bot.db.*" -mtime +7 -delete
```

Make it executable and add to cron:
```bash
sudo chmod +x /opt/telepannel/backup.sh
sudo crontab -e
```

Add (backs up every 6 hours):
```
0 */6 * * * /opt/telepannel/backup.sh
```

## Performance Optimization

1. **Use a dedicated database** - For high traffic, consider PostgreSQL
2. **Enable caching** - Cache frequently accessed data
3. **Monitor memory usage** - Adjust Python memory limits if needed
4. **Load balancing** - For very high traffic, run multiple instances

## Support

For issues during deployment:
1. Check the main README.md
2. Review logs carefully
3. Verify all prerequisites are met
4. Test the bot locally first
5. Check firewall and network settings

## Quick Reference

| Task | Command |
|------|---------|
| Start bot | `sudo systemctl start escrow-bot` |
| Stop bot | `sudo systemctl stop escrow-bot` |
| Restart bot | `sudo systemctl restart escrow-bot` |
| Check status | `sudo systemctl status escrow-bot` |
| View logs | `sudo journalctl -u escrow-bot -f` |
| Update bot | `cd /opt/telepannel && git pull && systemctl restart escrow-bot` |
| Backup DB | `cp escrow_bot.db backup/escrow_bot.db.$(date +%Y%m%d)` |

---

**Note:** This is a production deployment guide. Always test changes in a development environment first.
