from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from src.database import Database
from src.config import Config

# Conversation states
SELLER_ID, PRODUCT_DESC, AMOUNT, DELIVERY_TIME = range(4)

async def new_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start new transaction conversation"""
    await update.message.reply_text(
        "🛒 **Create New Transaction**\n\n"
        "Please enter the seller's Telegram ID or username:\n"
        "(You can find their ID by forwarding their message to @userinfobot)\n\n"
        "Send /cancel to abort.",
        parse_mode='Markdown'
    )
    return SELLER_ID

async def get_seller_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get seller ID"""
    seller_input = update.message.text.strip()
    
    # Remove @ if present
    if seller_input.startswith('@'):
        seller_input = seller_input[1:]
    
    # Try to convert to int if it's a numeric ID
    try:
        seller_id = int(seller_input)
    except ValueError:
        await update.message.reply_text(
            "❌ Please provide a valid numeric Telegram ID.\n"
            "You can get the seller's ID by forwarding their message to @userinfobot"
        )
        return SELLER_ID
    
    # Validate seller exists and is not the buyer
    if seller_id == update.effective_user.id:
        await update.message.reply_text("❌ You cannot create a transaction with yourself!")
        return SELLER_ID
    
    context.user_data['seller_id'] = seller_id
    
    await update.message.reply_text(
        "📦 **Product Description**\n\n"
        "Please describe what you're purchasing:\n"
        "(Be detailed - include model, specifications, condition, etc.)",
        parse_mode='Markdown'
    )
    return PRODUCT_DESC

async def get_product_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get product description"""
    description = update.message.text.strip()
    
    if len(description) < 10:
        await update.message.reply_text(
            "❌ Please provide a more detailed description (at least 10 characters)."
        )
        return PRODUCT_DESC
    
    context.user_data['product_description'] = description
    
    await update.message.reply_text(
        "💰 **Transaction Amount**\n\n"
        "Enter the amount (numeric value only):\n"
        "Example: 150 or 99.99",
        parse_mode='Markdown'
    )
    return AMOUNT

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get transaction amount"""
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except ValueError:
        await update.message.reply_text(
            "❌ Please enter a valid positive number.\n"
            "Example: 150 or 99.99"
        )
        return AMOUNT
    
    context.user_data['amount'] = amount
    
    await update.message.reply_text(
        "⏱️ **Expected Delivery Time**\n\n"
        "When should the product be delivered?\n"
        "Example: 3 days, 1 week, 2-3 business days",
        parse_mode='Markdown'
    )
    return DELIVERY_TIME

async def get_delivery_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get delivery time and create transaction"""
    delivery_time = update.message.text.strip()
    
    if len(delivery_time) < 3:
        await update.message.reply_text("❌ Please provide a valid delivery timeframe.")
        return DELIVERY_TIME
    
    # Create transaction
    db = Database()
    transaction_id = await db.create_transaction(
        buyer_id=update.effective_user.id,
        seller_id=context.user_data['seller_id'],
        product_description=context.user_data['product_description'],
        amount=context.user_data['amount'],
        delivery_time=delivery_time
    )
    
    # Prepare summary
    summary = f"""
✅ **Transaction Created Successfully!**

**Transaction ID:** #{transaction_id}
**Seller ID:** {context.user_data['seller_id']}
**Product:** {context.user_data['product_description']}
**Amount:** ${context.user_data['amount']:.2f}
**Expected Delivery:** {delivery_time}
**Status:** 🟡 PENDING (Awaiting admin approval)

An admin will review your transaction shortly.
You'll be notified once it's approved! 🔔
"""
    
    await update.message.reply_text(summary, parse_mode='Markdown')
    
    # Notify admin
    try:
        admin_message = f"""
🔔 **New Transaction Created**

**ID:** #{transaction_id}
**Buyer:** {update.effective_user.first_name} (ID: {update.effective_user.id})
**Seller ID:** {context.user_data['seller_id']}
**Product:** {context.user_data['product_description']}
**Amount:** ${context.user_data['amount']:.2f}
**Delivery:** {delivery_time}

Use /admin to review and approve.
"""
        await context.bot.send_message(
            chat_id=Config.ADMIN_ID,
            text=admin_message,
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Failed to notify admin: {e}")
    
    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel transaction creation"""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Transaction creation cancelled.",
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def my_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's transactions as buyer"""
    db = Database()
    transactions = await db.get_user_transactions(update.effective_user.id, as_buyer=True)
    
    if not transactions:
        await update.message.reply_text(
            "📭 You don't have any active transactions.\n\n"
            "Use /newtransaction to create one!"
        )
        return
    
    await update.message.reply_text(
        f"🛒 **Your Active Transactions** ({len(transactions)})\n\n"
        "Select a transaction to view details:",
        parse_mode='Markdown'
    )
    
    for tx in transactions:
        status_emoji = {
            'PENDING': '🟡',
            'APPROVED': '🟢',
            'SHIPPED': '📦',
            'DISPUTED': '⚠️'
        }.get(tx['status'], '⚪')
        
        keyboard = [[
            InlineKeyboardButton(
                f"{status_emoji} Transaction #{tx['id']} - ${tx['amount']:.2f}",
                callback_data=f"view_tx_{tx['id']}"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"**Product:** {tx['product_description'][:50]}...",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def my_sales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's transactions as seller"""
    db = Database()
    transactions = await db.get_user_transactions(update.effective_user.id, as_buyer=False)
    
    if not transactions:
        await update.message.reply_text(
            "📭 You don't have any active sales.\n\n"
            "Waiting for buyers to create transactions with you!"
        )
        return
    
    await update.message.reply_text(
        f"💼 **Your Active Sales** ({len(transactions)})\n\n"
        "Select a sale to view details:",
        parse_mode='Markdown'
    )
    
    for tx in transactions:
        status_emoji = {
            'PENDING': '🟡',
            'APPROVED': '🟢',
            'SHIPPED': '📦',
            'DISPUTED': '⚠️'
        }.get(tx['status'], '⚪')
        
        keyboard = [[
            InlineKeyboardButton(
                f"{status_emoji} Sale #{tx['id']} - ${tx['amount']:.2f}",
                callback_data=f"view_sale_{tx['id']}"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"**Product:** {tx['product_description'][:50]}...",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
