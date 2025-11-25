# Telegram Escrow Bot 🤝

An advanced Telegram bot that provides secure escrow services, acting as a trusted mediator between buyers and sellers for safe online transactions.

## Features ✨

### For Buyers 🛒
- Browse available products
- Initiate secure purchases
- Confirm payments
- Track delivery status
- Confirm receipt of goods
- Open disputes if issues arise

### For Sellers 💼
- List products with detailed descriptions
- Receive purchase notifications
- Confirm shipments
- Track sales
- Receive funds after admin approval

### For Admins ⚙️
- Monitor all transactions
- Approve fund releases
- Handle disputes
- View comprehensive statistics
- Manage users

### Security Features 🔒
- **Escrow Protection**: Funds held until delivery confirmed
- **Multi-Step Verification**: Payment, delivery, and admin approval required
- **Dispute Resolution**: Admin mediation for conflicts
- **Transaction Tracking**: Complete audit trail
- **User Authentication**: Secure user management

## How It Works 📋

1. **Seller Lists Product**: Seller creates a product listing with title, description, and price
2. **Buyer Initiates Purchase**: Buyer browses and selects a product to buy
3. **Payment Confirmation**: Buyer makes payment and confirms in the bot
4. **Delivery**: Seller ships product and confirms shipment
5. **Receipt Confirmation**: Buyer confirms receipt of product
6. **Fund Release**: Admin reviews and approves fund release to seller
7. **Completion**: Transaction marked complete, both parties notified

## Installation 🚀

### Prerequisites
- Python 3.8 or higher
- pip3
- A Telegram Bot Token (from [@BotFather](https://t.me/botfather))

### Setup Steps

1. **Clone or download this project**
```bash
cd telegram-escrow-bot
```

2. **Run the setup script**
```bash
chmod +x setup.sh
./setup.sh
```

Or manually install:
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

3. **Configure environment variables**

Create `.env` file:
```bash
cp .env.example .env
```

Edit `.env` and add your configuration:
```env
# Get this from @BotFather on Telegram
BOT_TOKEN=your_bot_token_here

# Your Telegram user ID (admin)
ADMIN_ID=123456789

# Database file path (will be created automatically)
DB_PATH=escrow_bot.db
```

**How to get your Telegram User ID:**
- Message [@userinfobot](https://t.me/userinfobot) on Telegram
- It will reply with your user ID

4. **Start the bot**
```bash
# Activate virtual environment (if not already active)
source venv/bin/activate

# Run the bot
python3 bot.py
```

## Usage Guide 📖

### Getting Started

1. Start a chat with your bot on Telegram
2. Send `/start` to see the welcome message
3. Use the commands to navigate

### For Sellers

**Listing a Product:**
1. Click "➕ List Product"
2. Enter product title
3. Enter description (or skip)
4. Enter price
5. Product is now visible to buyers

**Managing Sales:**
1. Click "💼 My Sales"
2. View all your sales transactions
3. Click "📋 Details" on any transaction
4. Confirm shipment when ready

### For Buyers

**Making a Purchase:**
1. Click "📦 Browse Products"
2. Click "🛒 Buy Now" on desired product
3. Review details and type "confirm"
4. Make payment to seller
5. Click "✅ Confirm Payment"
6. Wait for delivery
7. Click "✅ Confirm Receipt" when received

**Tracking Purchases:**
1. Click "🛒 My Purchases"
2. View all your purchase transactions
3. Click "📋 Details" for more info

### For Admins

**Accessing Admin Panel:**
1. Click "⚙️ Admin Panel" (only visible to admins)
2. View statistics and pending transactions
3. Review transactions requiring approval
4. Click "✅ Approve" to release funds
5. Click "❌ Reject" to cancel transaction

**Handling Disputes:**
1. Receive notification when dispute opened
2. Review transaction details
3. Contact both parties if needed
4. Make decision to approve or reject

## Transaction Statuses 📊

- **⏳ Pending**: Transaction initiated, waiting for payment confirmation
- **💰 Paid**: Payment confirmed by buyer, waiting for shipment
- **📦 Shipped**: Seller confirmed shipment, waiting for delivery
- **✅ Delivered**: Buyer confirmed receipt, waiting for admin approval
- **🎉 Completed**: Admin approved, funds released, transaction complete
- **❌ Cancelled**: Transaction cancelled by admin
- **⚠️ Disputed**: Dispute opened, admin review required

## Database Schema 🗄️

The bot uses SQLite with the following tables:

- **users**: User profiles and admin status
- **products**: Product listings by sellers
- **transactions**: All escrow transactions
- **session_states**: Form handling states
- **notifications**: User notifications

## Commands 💬

- `/start` - Start the bot and show main menu
- `/help` - Display help information
- `/cancel` - Cancel current operation

## Security Considerations 🔐

1. **Never share your `.env` file** - Contains sensitive bot token
2. **Keep admin IDs secure** - Only trusted users should be admins
3. **Regular backups** - Backup `data/escrow.db` regularly
4. **Monitor disputes** - Review disputed transactions promptly
5. **User verification** - Consider requiring additional verification for high-value transactions

## Troubleshooting 🔧

### Bot not responding
- Check if bot token is correct in `.env`
- Verify bot is running with `npm start`
- Check console for error messages

### Database errors
- Ensure `data/` directory exists
- Check file permissions
- Try deleting `escrow.db` and running `npm run init-db`

### Admin panel not showing
- Verify your user ID is in `ADMIN_IDS` in `.env`
- Restart the bot after changing `.env`
- Send `/start` to refresh the menu

## File Structure 📁

```
telegram-escrow-bot/
├── src/
│   ├── bot.js                    # Main bot file
│   ├── config/
│   │   └── config.js            # Configuration loader
│   ├── database/
│   │   └── database.js          # Database manager
│   └── handlers/
│       ├── formHandler.js       # Form handling logic
│       ├── transactionHandler.js # Transaction logic
│       └── adminHandler.js      # Admin panel logic
├── data/
│   └── escrow.db               # SQLite database (auto-created)
├── .env                        # Environment variables (create from .env.example)
├── .env.example               # Example environment file
├── .gitignore                 # Git ignore rules
├── package.json               # Node.js dependencies
└── README.md                  # This file
```

## Customization 🎨

### Changing Currency
Edit transaction messages in `transactionHandler.js` and `adminHandler.js` to use your preferred currency symbol.

### Adding Payment Methods
Extend the form handler to collect payment method details during purchase.

### Custom Notifications
Modify notification messages in handler files to match your brand voice.

### Adding Features
- Product categories
- Image uploads
- Rating system
- Automated payment processing
- Multi-currency support

## Development 👨‍💻

### Running in Development Mode
```bash
npm run dev
```

This uses nodemon for auto-reload on file changes.

### Adding New Commands
1. Add command handler in `src/bot.js`
2. Update help text in `/help` command
3. Test thoroughly before deployment

## Support 💬

For issues or questions:
1. Check this README thoroughly
2. Review console error messages
3. Check Telegram bot logs
4. Verify all configuration settings

## License 📄

MIT License - feel free to modify and use for your projects.

## Contributing 🤝

Contributions are welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests
- Improve documentation

## Disclaimer ⚠️

This bot is a demonstration of escrow functionality. For production use:
- Implement proper payment gateway integration
- Add comprehensive error handling
- Implement rate limiting
- Add data encryption
- Consult legal requirements in your jurisdiction
- Consider security audits

---

**Built with ❤️ using [Telegraf](https://telegraf.js.org/)**
