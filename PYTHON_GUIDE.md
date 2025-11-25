# Python Escrow Bot - Complete Guide

## 🐍 Python Implementation

This bot is built using **python-telegram-bot** library (v20.7), which provides a pure Python interface for the Telegram Bot API.

## Project Structure

```
telegram-escrow-bot/
├── bot.py                      # Main bot entry point
├── requirements.txt            # Python dependencies
├── .env.example               # Environment variables template
├── .env                       # Your configuration (create this)
├── setup.sh                   # Automated setup script
│
└── src/
    ├── config.py              # Configuration management
    ├── database.py            # Database operations (SQLite)
    │
    └── handlers/
        ├── start_handler.py      # /start and /help commands
        ├── transaction_handler.py # Transaction creation & viewing
        ├── callback_handler.py    # Button callbacks & actions
        └── admin_handler.py       # Admin panel & statistics
```

## Installation

### Method 1: Using Setup Script (Recommended)
```bash
chmod +x setup.sh
./setup.sh
```

### Method 2: Manual Installation
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your credentials
```

## Configuration

Create `.env` file with:
```env
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_ID=123456789
DB_PATH=escrow_bot.db
```

### Getting Bot Token
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` command
3. Follow the instructions
4. Copy the token

### Getting Your User ID
1. Message [@userinfobot](https://t.me/userinfobot)
2. It will reply with your ID

## Running the Bot

```bash
# Activate virtual environment
source venv/bin/activate

# Run bot
python3 bot.py
```

## Dependencies

### Core Dependencies
- **python-telegram-bot** (20.7): Telegram Bot API wrapper
- **python-dotenv** (1.0.0): Environment variable management
- **aiosqlite** (0.19.0): Async SQLite database

### Why These Libraries?

**python-telegram-bot v20+**
- Fully async/await support
- Type hints throughout
- Conversation handlers for multi-step flows
- Inline keyboard support
- Actively maintained

**aiosqlite**
- Async database operations
- No blocking during DB queries
- Perfect for async bot architecture

## Code Architecture

### 1. Main Bot (bot.py)
```python
# Sets up the Application
# Registers all handlers
# Initializes database
# Starts polling
```

### 2. Configuration (src/config.py)
```python
# Loads environment variables
# Validates configuration
# Provides config access
```

### 3. Database (src/database.py)
```python
# All database operations
# Async SQLite queries
# Transaction management
# User management
# Statistics
```

### 4. Handlers
Each handler manages specific bot functionality:
- **start_handler**: Welcome & help
- **transaction_handler**: Create & view transactions
- **callback_handler**: Button interactions
- **admin_handler**: Admin panel & stats

## Conversation Handlers

The bot uses ConversationHandler for multi-step interactions:

### New Transaction Flow
```python
SELLER_ID → PRODUCT_DESC → AMOUNT → DELIVERY_TIME → Complete
```

### Shipping Flow
```python
Button Click → SHIPPING_INFO → Update Status
```

### Dispute Flow
```python
Button Click → DISPUTE_REASON → Notify Admin
```

## Database Schema

### users table
```sql
telegram_id (PK)
username
first_name
last_name
created_at
```

### transactions table
```sql
id (PK)
buyer_id (FK)
seller_id (FK)
product_description
amount
delivery_time
status (PENDING/APPROVED/SHIPPED/COMPLETED/REJECTED/DISPUTED)
shipping_info
dispute_reason
created_at
updated_at
```

## Transaction States

```
PENDING    → Admin needs to approve
APPROVED   → Approved, seller can ship
SHIPPED    → Product shipped, buyer confirms
COMPLETED  → Transaction complete, funds released
REJECTED   → Admin rejected transaction
DISPUTED   → Issue reported, admin reviewing
```

## Commands

### User Commands
- `/start` - Register and see welcome message
- `/help` - Show help information
- `/newtransaction` - Create new transaction (buyer)
- `/mytransactions` - View purchases (buyer)
- `/mysales` - View sales (seller)
- `/stats` - View bot statistics
- `/cancel` - Cancel current operation

### Admin Commands
- `/admin` - Admin panel with pending transactions

## Features

### For Buyers
- Create transactions with form-based input
- View active purchases
- Confirm delivery
- Report issues/disputes

### For Sellers
- View pending sales
- Mark items as shipped with tracking
- Receive payment notifications

### For Admins
- Review and approve/reject transactions
- View comprehensive statistics
- Handle disputes
- Monitor all activity

## Error Handling

The bot includes comprehensive error handling:
```python
try:
    # Bot operation
except Exception as e:
    logger.error(f'Error: {e}')
    await ctx.reply('Error message')
```

## Logging

Configured in bot.py:
```python
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
```

## Async/Await Pattern

All functions use async/await:
```python
async def my_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hello')
```

## Testing

### Manual Testing
1. Create test transactions
2. Test all user flows
3. Test admin functions
4. Test error scenarios

### Automated Testing (Future)
```bash
pip install pytest pytest-asyncio
pytest tests/
```

## Deployment

### Option 1: Local/VPS
```bash
# Use PM2 or systemd to keep bot running
pip install pm2
pm2 start bot.py --name escrow-bot --interpreter python3
```

### Option 2: Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python3", "bot.py"]
```

### Option 3: Cloud Platforms
- Heroku
- Railway
- DigitalOcean App Platform
- AWS Lambda (with modifications)

## Performance Optimization

### Database Indexes
Already included in database.py:
```python
await db.execute("CREATE INDEX IF NOT EXISTS idx_buyer ON transactions(buyer_id)")
await db.execute("CREATE INDEX IF NOT EXISTS idx_seller ON transactions(seller_id)")
await db.execute("CREATE INDEX IF NOT EXISTS idx_status ON transactions(status)")
```

### Connection Pooling
For production, consider using connection pooling:
```python
# Example with asyncpg for PostgreSQL
from asyncpg import create_pool
pool = await create_pool(database='escrow')
```

## Security Best Practices

1. **Never commit .env file**
2. **Validate all user input**
3. **Use prepared statements** (already implemented)
4. **Restrict admin commands**
5. **Log security events**

## Troubleshooting

### Bot not responding
```bash
# Check if bot is running
ps aux | grep bot.py

# Check logs
tail -f bot.log
```

### Database errors
```bash
# Check database file
ls -la escrow_bot.db

# Test database connection
python3 -c "import aiosqlite; import asyncio; asyncio.run(aiosqlite.connect('escrow_bot.db'))"
```

### Import errors
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

## Extending the Bot

### Adding New Commands
```python
# In appropriate handler file
async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Response')

# In bot.py
application.add_handler(CommandHandler("mycommand", my_command))
```

### Adding New Database Tables
```python
# In src/database.py, add to initialize():
await db.execute("""
    CREATE TABLE IF NOT EXISTS my_table (
        id INTEGER PRIMARY KEY,
        field TEXT
    )
""")
```

## Resources

- [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [aiosqlite Documentation](https://aiosqlite.omnilib.dev/)
- [Python asyncio](https://docs.python.org/3/library/asyncio.html)

## Support

For issues or questions:
1. Check the documentation
2. Review TROUBLESHOOTING.md
3. Check GitHub issues
4. Open a new issue with details

## License

MIT License - See LICENSE file
