# 🤖 Telepannel Bot - 24/7 Operation Guide

## 🚀 Quick Start (Recommended)

### Option 1: Screen Session (Best for Dev Containers)
```bash
./start_screen.sh
```
- ✅ Runs in detached screen session
- ✅ Survives terminal closure
- ✅ Easy to reconnect anytime
- ✅ Can view real-time logs

**To reconnect to your bot:**
```bash
screen -r telepannel-bot
```

**To stop the bot:**
```bash
./stop_24_7.sh
```

---

### Option 2: Background Process (Simple)
```bash
./start_background.sh
```
- ✅ Runs with nohup in background
- ✅ Continues after terminal closes
- ✅ Logs to bot.log file

---

### Option 3: Auto-Restart Manager (Production)
```bash
./bot_manager.sh start
```
- ✅ Automatic crash recovery
- ✅ Memory monitoring & restart
- ✅ Daily health restarts
- ✅ Comprehensive logging

---

## 📊 Monitoring Your Bot

### View Real-Time Logs
```bash
# If using screen
screen -r telepannel-bot

# If using background/manager
tail -f bot.log
tail -f logs/bot.log  # for manager
```

### Check Bot Status
```bash
# Check if running
ps aux | grep python | grep main.py

# Using manager
./bot_manager.sh status

# View all screen sessions
screen -ls
```

---

## 🛑 Stopping Your Bot

### Universal Stop Command
```bash
./stop_24_7.sh
```

### Individual Methods
```bash
# Stop screen session
screen -S telepannel-bot -X quit

# Stop manager
./bot_manager.sh stop

# Kill all bot processes
pkill -f "python.*main.py"
```

---

## 🔧 Advanced Usage

### Bot Process Manager Commands
```bash
./bot_manager.sh start     # Start with monitoring
./bot_manager.sh stop      # Stop gracefully
./bot_manager.sh restart   # Restart bot
./bot_manager.sh status    # Check status
```

### Auto-Restart Script (24/7)
```bash
./run_24_7.sh
```
- Auto-restarts on crash (up to 10 times)
- Detailed logging with timestamps
- Handles virtual environment setup

---

## 📁 Log Files

| File | Description |
|------|-------------|
| `bot.log` | Main bot output |
| `bot_errors.log` | Error messages only |
| `logs/manager.log` | Process manager logs |
| `logs/bot.log` | Bot output (manager mode) |
| `logs/bot_error.log` | Bot errors (manager mode) |

---

## 🎯 Best Practices

### For Development
1. Use **screen session**: `./start_screen.sh`
2. Easy to reconnect and debug
3. View real-time logs

### For Production
1. Use **process manager**: `./bot_manager.sh start`
2. Automatic crash recovery
3. Resource monitoring
4. Health checks

### For Simple Background
1. Use **background runner**: `./start_background.sh`
2. Set and forget operation
3. Check logs when needed

---

## 🔍 Troubleshooting

### Bot Not Starting
```bash
# Check Python environment
python3 --version
source .venv/bin/activate
pip install -r requirements.txt

# Check bot directly
python main.py
```

### Bot Keeps Crashing
```bash
# Check error logs
tail -20 bot_errors.log
tail -20 logs/bot_error.log

# Run with manager for auto-restart
./bot_manager.sh start
```

### Can't Connect to Screen
```bash
# List all sessions
screen -ls

# Force detach if stuck
screen -d telepannel-bot
screen -r telepannel-bot
```

### High Memory Usage
The bot manager automatically restarts if memory > 500MB.
Adjust in `bot_manager.sh` if needed:
```bash
MAX_MEMORY_MB=500  # Change this value
```

---

## 🎉 Success! Your Bot is Now 24/7

After running any of the start scripts, your bot will:
- ✅ Run continuously in the background
- ✅ Survive terminal/window closure
- ✅ Automatically handle crashes (with manager)
- ✅ Log all activity for monitoring
- ✅ Be easily manageable with provided scripts

**You can now safely close your terminal window!**

---

## 📱 Quick Commands Reference

```bash
# Start (choose one)
./start_screen.sh        # Screen session (recommended)
./start_background.sh    # Background process
./bot_manager.sh start   # Managed process

# Monitor
screen -r telepannel-bot # Reconnect to screen
tail -f bot.log         # View logs

# Stop
./stop_24_7.sh          # Universal stop

# Status
./bot_manager.sh status # Check if running
screen -ls              # List screen sessions
```