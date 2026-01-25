# Railway.app Configuration

This bot can be easily deployed to Railway.app

## Deployment Steps

1. **Connect Repository**
   - Go to [railway.app](https://railway.app)
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose this repository

2. **Configure Environment Variables**
   Add the following variables in Railway dashboard:
   - `BOT_TOKEN` - Your bot token from @BotFather
   - `ADMIN_ID` - Your Telegram user ID
   - `DB_PATH` - Set to `/app/data/escrow_bot.db`

3. **Configure Start Command**
   Railway should auto-detect the start command, but if needed:
   ```
   python3 bot.py
   ```

4. **Deploy**
   - Click "Deploy"
   - Railway will automatically build and deploy your bot
   - The bot will restart automatically on crashes

## Advantages of Railway
- ✅ Free tier available
- ✅ Automatic deployments on git push
- ✅ Easy environment variable management
- ✅ Built-in logging
- ✅ Persistent volumes for database

## Monitoring
View logs in Railway dashboard under your project.
