# Quick Start Guide

## Step-by-Step Setup (5 minutes)

### 1. Get Your Bot Token
1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot`
3. Follow instructions to create your bot
4. Copy the bot token (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Get Your User ID (to become admin)
1. Search for [@userinfobot](https://t.me/userinfobot) on Telegram
2. Start the bot
3. Copy your user ID (a number like: `123456789`)

### 3. Install Dependencies
```bash
npm install
```

### 4. Create Configuration File
```bash
cp .env.example .env
```

Then edit `.env` file and paste your:
- Bot token from step 1
- User ID from step 2

Example `.env`:
```env
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_IDS=123456789
DB_PATH=./data/escrow.db
BOT_USERNAME=MyEscrowBot
```

### 5. Initialize Database
```bash
npm run init-db
```

### 6. Start the Bot
```bash
npm start
```

You should see: `✅ Bot is running!`

### 7. Test Your Bot
1. Open Telegram
2. Search for your bot (the username you created with BotFather)
3. Send `/start`
4. You should see the welcome message with buttons!

## Common Issues

**"Unauthorized" error:**
- Check if your BOT_TOKEN is correct in `.env`
- Make sure there are no extra spaces

**Admin panel not showing:**
- Verify your user ID is correct in ADMIN_IDS
- Restart the bot after changing `.env`

**Database error:**
- Run `npm run init-db` again
- Check if `data/` folder has write permissions

## Testing the Escrow Flow

### As a Seller:
1. Click "➕ List Product"
2. Enter: "Test Item"
3. Enter: "This is a test product"
4. Enter: "10"

### As a Buyer (use another account):
1. Click "📦 Browse Products"
2. Click "🛒 Buy Now" on the test product
3. Type "confirm"
4. Click "✅ Confirm Payment"

### As Admin (your account):
1. Check "💼 My Sales" to see the purchase
2. Click "📋 Details"
3. Click "📦 Confirm Delivery"
4. Go to "⚙️ Admin Panel"
5. Click "⏳ Pending Transactions"
6. Click "✅ Approve" to release funds

## Next Steps

- Customize messages in handler files
- Add your own payment instructions
- Set up proper payment processing
- Deploy to a server for 24/7 operation

## Need Help?

Check the main README.md for detailed documentation.
