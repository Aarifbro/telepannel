from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from src.database import Database
from src.config import Config

# Conversation states for creating listing
LISTING_TITLE, LISTING_DESC, LISTING_CATEGORY, LISTING_PRICE, LISTING_DELIVERY = range(5)

# Categories
CATEGORIES = [
    "🎮 Game Accounts",
    "🎯 Game IDs & Codes",
    "📺 Streaming Subscriptions",
    "💳 Premium Accounts",
    "🔐 Software Licenses",
    "📱 App Subscriptions",
    "🎵 Music & Entertainment",
    "💰 Payment Methods",
    "🌐 VPN & Security",
    "📚 Educational Accounts"
]

async def browse_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Browse available digital products"""
    query = update.callback_query
    if query:
        await query.answer()
        message = query.message
    else:
        message = update.message
    
    # Category selection keyboard
    keyboard = []
    for i in range(0, len(CATEGORIES), 2):
        row = [InlineKeyboardButton(CATEGORIES[i], callback_data=f"category_{i}")]
        if i + 1 < len(CATEGORIES):
            row.append(InlineKeyboardButton(CATEGORIES[i+1], callback_data=f"category_{i+1}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("📋 View All Products", callback_data="category_all")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """
🛒 **Digital Products Marketplace**

Browse our secure escrow marketplace for digital products:

🎮 Game accounts, IDs, and in-game items
📺 Premium subscriptions (Netflix, Spotify, etc.)
💳 Verified accounts and payment methods
🔐 Software licenses and digital keys
📱 App subscriptions and premium features

**✨ All transactions are protected by escrow!**
Your payment is held securely until you confirm receipt of the digital product.

Select a category below:
"""
    
    if query:
        await message.edit_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def show_category_listings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show listings in a category"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    category_idx = data.split('_')[1]
    
    db = Database()
    
    if category_idx == 'all':
        listings = await db.get_active_listings()
        category_name = "All Categories"
    else:
        category_name = CATEGORIES[int(category_idx)]
        listings = await db.get_active_listings(category=category_name)
    
    if not listings:
        await query.message.edit_text(
            f"📭 No listings found in **{category_name}**\n\nCheck back later or browse other categories!",
            parse_mode='Markdown'
        )
        await browse_services(update, context)
        return
    
    text = f"📋 **{category_name}** ({len(listings)} listings)\n\n"
    text += "Select a listing to view details:\n"
    
    keyboard = []
    for listing in listings[:10]:  # Show first 10
        seller_rating = "⭐" * int(listing['rating']) if listing['rating'] > 0 else "🆕"
        button_text = f"{listing['title'][:30]} - ${listing['price']:.2f}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"view_listing_{listing['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="browse_services")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def view_listing_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View detailed listing information"""
    query = update.callback_query
    await query.answer()
    
    listing_id = int(query.data.split('_')[2])
    
    db = Database()
    listing = await db.get_listing(listing_id)
    
    if not listing:
        await query.message.edit_text("❌ Listing not found or has been removed.")
        return
    
    # Increment view count
    await db.increment_listing_views(listing_id)
    
    # Build listing details
    rating_stars = "⭐" * int(listing['rating']) if listing['rating'] > 0 else "🆕 New Seller"
    
    details = f"""
📦 **{listing['title']}**

**Category:** {listing['category']}
**Price:** ${listing['price']:.2f} USD
**Delivery Time:** {listing['delivery_time']}
**Views:** {listing['views']} 👀

**📋 Product Details:**
{listing['description']}

━━━━━━━━━━━━━━━━━━━━
**👤 Seller Information:**
• Name: {listing['first_name']}
• Rating: {rating_stars} ({listing['rating']:.1f}/5)
• Completed Sales: {listing['total_sales']}
• Username: @{listing['username'] or 'Private'}

**🛡️ Escrow Protection:**
✅ Payment held securely until delivery confirmed
✅ Full refund if product not as described
✅ Dispute resolution available
"""
    
    keyboard = []
    
    # Don't allow buying own listing
    if query.from_user.id != listing['seller_id']:
        keyboard.append([InlineKeyboardButton("💳 Buy Now - Escrow Protected", callback_data=f"buy_listing_{listing_id}")])
        if listing['username']:
            keyboard.append([InlineKeyboardButton("💬 Contact Seller", url=f"https://t.me/{listing['username']}")])
    else:
        keyboard.append([InlineKeyboardButton("📝 This is Your Listing", callback_data="noop")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Category", callback_data=f"category_{CATEGORIES.index(listing['category']) if listing['category'] in CATEGORIES else 'all'}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(details, parse_mode='Markdown', reply_markup=reply_markup)

async def create_listing_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start creating a new listing"""
    await update.message.reply_text(
        "🆕 **List Your Digital Product**\n\n"
        "Let's create your product listing!\n\n"
        "**Step 1/5:** Enter a clear title for your product\n\n"
        "Examples:\n"
        "• 'Fortnite Account Level 150 - Rare Skins'\n"
        "• 'Netflix Premium 1 Year Subscription'\n"
        "• 'Steam Account with GTA V + 50 Games'\n"
        "• 'Verified PayPal Account - USA'\n\n"
        "(Max 100 characters)\n\n"
        "Send /cancel to abort.",
        parse_mode='Markdown'
    )
    return LISTING_TITLE

async def get_listing_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get listing title"""
    title = update.message.text.strip()
    
    if len(title) < 5:
        await update.message.reply_text("❌ Title too short. Please enter at least 5 characters.")
        return LISTING_TITLE
    
    if len(title) > 100:
        await update.message.reply_text("❌ Title too long. Maximum 100 characters.")
        return LISTING_TITLE
    
    context.user_data['listing_title'] = title
    
    await update.message.reply_text(
        "📝 **Step 2/5:** Describe your digital product\n\n"
        "Include important details:\n"
        "• What's included (account details, credentials, etc.)\n"
        "• Account level/features/subscription duration\n"
        "• Region/Platform compatibility\n"
        "• Any warranties or guarantees\n"
        "• Instant delivery or waiting time\n\n"
        "Example:\n"
        "'Netflix Premium 4K account, works worldwide, 1 year warranty. "
        "Instant delivery of credentials via DM. Change password allowed.'\n\n"
        "(Max 1000 characters)",
        parse_mode='Markdown'
    )
    return LISTING_DESC

async def get_listing_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get listing description"""
    description = update.message.text.strip()
    
    if len(description) < 20:
        await update.message.reply_text("❌ Description too short. Please provide at least 20 characters.")
        return LISTING_DESC
    
    if len(description) > 1000:
        await update.message.reply_text("❌ Description too long. Maximum 1000 characters.")
        return LISTING_DESC
    
    context.user_data['listing_description'] = description
    
    # Category selection
    keyboard = []
    for i, category in enumerate(CATEGORIES):
        keyboard.append([InlineKeyboardButton(category, callback_data=f"set_category_{i}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🏷️ **Step 3/5:** Select a category",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return LISTING_CATEGORY

async def get_listing_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get listing category"""
    query = update.callback_query
    await query.answer()
    
    category_idx = int(query.data.split('_')[2])
    context.user_data['listing_category'] = CATEGORIES[category_idx]
    
    await query.message.edit_text(
        f"✅ Category: **{CATEGORIES[category_idx]}**\n\n"
        f"💰 **Step 4/5:** Set your price (USD)\n\n"
        f"Enter the price in dollars:\n"
        f"Examples: 5, 10.99, 25, 49.99\n\n"
        f"💡 Price your product competitively based on market rates.\n"
        f"Popular digital products range from $5 to $100.",
        parse_mode='Markdown'
    )
    return LISTING_PRICE

async def get_listing_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get listing price"""
    try:
        price = float(update.message.text.strip())
        if price <= 0:
            raise ValueError("Price must be positive")
        if price > 100000:
            raise ValueError("Price too high")
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid positive number (e.g., 50 or 99.99)")
        return LISTING_PRICE
    
    context.user_data['listing_price'] = price
    
    await update.message.reply_text(
        f"✅ Price: **${price:.2f}**\n\n"
        f"⏱️ **Step 5/5:** Delivery timeframe\n\n"
        f"How quickly can you deliver the digital product?\n\n"
        f"Examples:\n"
        f"• 'Instant' - Automated delivery\n"
        f"• '5-10 minutes' - Manual delivery during online hours\n"
        f"• '1-2 hours' - Need to process/verify\n"
        f"• '24 hours' - Within a day\n\n"
        f"⚡ Faster delivery = more sales!",
        parse_mode='Markdown'
    )
    return LISTING_DELIVERY

async def get_listing_delivery_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get delivery time and create listing"""
    delivery_time = update.message.text.strip()
    
    if len(delivery_time) < 3:
        await update.message.reply_text("❌ Please provide delivery time (e.g., 'Instant' or '1 hour')")
        return LISTING_DELIVERY
    
    # Create listing
    db = Database()
    listing_id = await db.create_listing(
        seller_id=update.effective_user.id,
        title=context.user_data['listing_title'],
        description=context.user_data['listing_description'],
        category=context.user_data['listing_category'],
        price=context.user_data['listing_price'],
        delivery_time=delivery_time
    )
    
    summary = f"""
✅ **Digital Product Listed Successfully!**

**Listing ID:** #{listing_id}
**Title:** {context.user_data['listing_title']}
**Category:** {context.user_data['listing_category']}
**Price:** ${context.user_data['listing_price']:.2f}
**Delivery:** {delivery_time}

🎉 Your product is now live in the marketplace!

**Next Steps:**
• Buyers can now see and purchase your product
• You'll receive notification when someone buys
• Deliver the product details to buyer via chat
• Funds released after buyer confirms

**Important Reminders:**
⚠️ Always deliver exactly what's advertised
⚠️ Respond quickly to buyers for good ratings
⚠️ Never share personal banking/payment info directly

Manage your listings anytime from the main menu! 💼
"""
    
    await update.message.reply_text(summary, parse_mode='Markdown')
    
    context.user_data.clear()
    return ConversationHandler.END

async def my_listings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View user's own listings"""
    query = update.callback_query
    message = query.message if query else update.message
    user_id = query.from_user.id if query else update.effective_user.id
    
    if query:
        await query.answer()
    
    db = Database()
    listings = await db.get_user_listings(user_id)
    
    if not listings:
        text = "📭 You don't have any listings yet.\n\nUse '🆕 Sell Digital Product' button to create one!"
        if query:
            await query.message.edit_text(text)
        else:
            await message.reply_text(text)
        return
    
    text = f"📋 **Your Listings** ({len(listings)})\n\nManage your digital product listings:"
    
    keyboard = []
    for listing in listings:
        status = "✅ Active" if listing['is_active'] else "❌ Inactive"
        button_text = f"{listing['title'][:30]} - {status}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"manage_listing_{listing['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.message.edit_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def manage_listing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage a specific listing"""
    query = update.callback_query
    await query.answer()
    
    listing_id = int(query.data.split('_')[2])
    
    db = Database()
    listing = await db.get_listing(listing_id)
    
    if not listing or listing['seller_id'] != query.from_user.id:
        await query.message.edit_text("❌ Listing not found or unauthorized.")
        return
    
    status_text = "✅ Active" if listing['is_active'] else "❌ Inactive"
    
    details = f"""
📋 **Manage Listing #{listing_id}**

**Title:** {listing['title']}
**Category:** {listing['category']}
**Price:** ${listing['price']:.2f}
**Status:** {status_text}
**Views:** {listing['views']}
**Created:** {listing['created_at'][:10]}

**Description:**
{listing['description']}
"""
    
    keyboard = []
    if listing['is_active']:
        keyboard.append([InlineKeyboardButton("🚫 Deactivate", callback_data=f"deactivate_{listing_id}")])
    else:
        keyboard.append([InlineKeyboardButton("✅ Activate", callback_data=f"activate_{listing_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to My Listings", callback_data="my_listings_back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(details, parse_mode='Markdown', reply_markup=reply_markup)

async def toggle_listing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Activate or deactivate listing"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split('_')
    action = parts[0]
    listing_id = int(parts[1])
    
    db = Database()
    await db.toggle_listing_status(listing_id, action == 'activate')
    
    status = "activated" if action == 'activate' else "deactivated"
    await query.answer(f"✅ Listing {status}!", show_alert=True)
    
    # Refresh the listing view
    context.matches = [{'data': f'manage_listing_{listing_id}'}]
    query.data = f'manage_listing_{listing_id}'
    await manage_listing(update, context)
