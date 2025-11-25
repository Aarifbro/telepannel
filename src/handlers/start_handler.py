from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from src.database import Database

def get_main_keyboard(is_admin=False):
    """Get main menu keyboard"""
    keyboard = [
        [KeyboardButton("🛒 Browse Products"), KeyboardButton("🆕 Sell Digital Product")],
        [KeyboardButton("💼 My Purchases"), KeyboardButton("📦 My Sales")],
        [KeyboardButton("📋 My Listings"), KeyboardButton("👤 My Profile")],
        [KeyboardButton("📊 Statistics"), KeyboardButton("ℹ️ Help")]
    ]
    
    if is_admin:
        keyboard.append([KeyboardButton("⚙️ Admin Panel")])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    db = Database()
    
    # Register user
    await db.add_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    from src.config import Config
    is_admin = user.id == Config.ADMIN_ID
    
    welcome_message = f"""
🤝 **Welcome to Digital Escrow Marketplace, {user.first_name}!**

Your trusted platform for secure digital product transactions.

**💎 What We Offer:**
🎮 Game Accounts & IDs (Fortnite, PUBG, COD, etc.)
📺 Premium Subscriptions (Netflix, Spotify, YouTube)
💳 Verified Accounts & Payment Methods
🔐 Software Licenses & Product Keys
📱 App Subscriptions & Premium Features
🌐 VPN & Security Tools
📚 Educational Platform Accounts

**🔐 100% Escrow Protected:**
1️⃣ Seller lists digital product
2️⃣ Buyer purchases through escrow
3️⃣ Admin verifies transaction
4️⃣ Seller delivers product details
5️⃣ Buyer confirms receipt
6️⃣ Payment released to seller

**Why Choose Us:**
✅ Secure escrow holds your payment
✅ Verified sellers with ratings
✅ Instant to 24hr delivery
✅ Dispute resolution support
✅ Refund guarantee if not delivered

Use the menu buttons below to get started! 👇
"""
    
    await update.message.reply_text(
        welcome_message, 
        parse_mode='Markdown',
        reply_markup=get_main_keyboard(is_admin)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    from src.config import Config
    is_admin = update.effective_user.id == Config.ADMIN_ID
    
    help_text = """
📚 **Digital Escrow Marketplace - Help Guide**

**🛒 For Buyers:**
• Browse digital products by category
• Purchase with escrow protection
• Receive product details from seller
• Confirm receipt to release payment
• Rate sellers after transaction
• Report issues for refunds

**💼 For Sellers:**
• List your digital products (accounts, subscriptions, keys)
• Set competitive prices
• Deliver instantly or within timeframe
• Get paid after buyer confirms
• Build reputation with ratings

**📋 Product Categories:**
🎮 Game Accounts & IDs
📺 Streaming Subscriptions (Netflix, Spotify, etc.)
💳 Premium Accounts
🔐 Software Licenses
📱 App Subscriptions
🌐 VPN & Security
📚 Educational Accounts
💰 Payment Methods (verified accounts)

**🔄 Transaction Process:**
🟡 PENDING - Awaiting admin approval
🟢 APPROVED - Payment in escrow, seller can deliver
📦 DELIVERED - Seller provided product details
✅ COMPLETED - Buyer confirmed, payment released
⚠️ DISPUTED - Issue under admin review
❌ REJECTED - Transaction cancelled

**🛡️ Escrow Protection:**
Your payment is held securely until you confirm receiving the digital product exactly as described. If not satisfied, dispute for refund.

**⚠️ Important Rules:**
• Never share payment/banking info directly
• Only transact through the bot
• Provide accurate product descriptions
• Deliver within promised timeframe
• Be honest in reviews

**Need Support?**
Use buttons below or contact admin through bot.
"""
    
    await update.message.reply_text(
        help_text, 
        parse_mode='Markdown',
        reply_markup=get_main_keyboard(is_admin)
    )
