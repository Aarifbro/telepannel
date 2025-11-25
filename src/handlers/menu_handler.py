from telegram import Update
from telegram.ext import ContextTypes
from src.database import Database
from src.config import Config
from src.handlers.start_handler import get_main_keyboard

async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu button presses"""
    text = update.message.text
    user_id = update.effective_user.id
    is_admin = user_id == Config.ADMIN_ID
    
    if text in ["🛒 Browse Products", "🛒 Browse Services"]:
        from src.handlers.listing_handler import browse_services
        await browse_services(update, context)
    
    elif text in ["🆕 Sell Digital Product", "🆕 Create Listing"]:
        from src.handlers.listing_handler import create_listing_start
        await create_listing_start(update, context)
    
    elif text == "💼 My Purchases":
        from src.handlers.transaction_handler import my_transactions
        await my_transactions(update, context)
    
    elif text == "📦 My Sales":
        from src.handlers.transaction_handler import my_sales
        await my_sales(update, context)
    
    elif text == "📋 My Listings":
        from src.handlers.listing_handler import my_listings
        await my_listings(update, context)
    
    elif text == "👤 My Profile":
        await show_profile(update, context)
    
    elif text == "📊 Statistics":
        from src.handlers.admin_handler import stats_command
        await stats_command(update, context)
    
    elif text == "⚙️ Admin Panel" and is_admin:
        from src.handlers.admin_handler import admin_panel
        await admin_panel(update, context)
    
    elif text == "ℹ️ Help":
        from src.handlers.start_handler import help_command
        await help_command(update, context)
    
    else:
        await update.message.reply_text(
            "Please use the menu buttons below 👇",
            reply_markup=get_main_keyboard(is_admin)
        )

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user profile"""
    user = update.effective_user
    db = Database()
    
    profile = await db.get_user_profile(user.id)
    
    if not profile:
        await update.message.reply_text("❌ Profile not found. Use /start to register.")
        return
    
    rating_stars = "⭐" * int(profile['rating']) if profile['rating'] > 0 else "🆕 New User"
    
    profile_text = f"""
👤 **Your Profile**

**Name:** {profile['first_name']} {profile['last_name'] or ''}
**Username:** @{profile['username'] or 'Not set'}
**User ID:** `{profile['telegram_id']}`

**📊 Statistics:**
• Rating: {rating_stars} ({profile['rating']:.1f}/5)
• Total Sales: {profile['total_sales']}
• Total Purchases: {profile['total_purchases']}
• Member Since: {profile['created_at'][:10]}

**🏆 Status:** {'Admin' if user.id == Config.ADMIN_ID else 'Verified User'}
"""
    
    await update.message.reply_text(profile_text, parse_mode='Markdown')
