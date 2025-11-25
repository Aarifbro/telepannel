from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from src.database import Database
from src.config import Config

# Conversation states
SHIPPING_INFO, DISPUTE_REASON = range(2)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # View transaction details
    if data.startswith('view_tx_'):
        tx_id = int(data.split('_')[2])
        await show_transaction_details(query, context, tx_id, as_buyer=True)
    
    # View sale details
    elif data.startswith('view_sale_'):
        tx_id = int(data.split('_')[2])
        await show_transaction_details(query, context, tx_id, as_buyer=False)
    
    # Admin actions
    elif data.startswith('admin_approve_'):
        tx_id = int(data.split('_')[2])
        await approve_transaction(query, context, tx_id)
    
    elif data.startswith('admin_reject_'):
        tx_id = int(data.split('_')[2])
        await reject_transaction(query, context, tx_id)
    
    # Buyer actions
    elif data.startswith('confirm_delivery_'):
        tx_id = int(data.split('_')[2])
        await confirm_delivery(query, context, tx_id)
    
    elif data.startswith('report_issue_'):
        tx_id = int(data.split('_')[2])
        context.user_data['dispute_tx_id'] = tx_id
        await query.edit_message_text(
            "⚠️ **Report Issue**\n\n"
            "Please describe the issue with this transaction:\n"
            "(What went wrong? Product issues? Delivery problems?)",
            parse_mode='Markdown'
        )
        return DISPUTE_REASON
    
    # Seller actions
    elif data.startswith('mark_shipped_'):
        tx_id = int(data.split('_')[2])
        context.user_data['shipping_tx_id'] = tx_id
        await query.edit_message_text(
            "📦 **Deliver Digital Product**\n\n"
            "Provide the product details to the buyer:\n\n"
            "For accounts: Username, Password, Email, 2FA codes\n"
            "For codes/keys: The activation code or license key\n"
            "For subscriptions: Login credentials and instructions\n\n"
            "⚠️ Make sure all details are accurate and working!\n"
            "Buyer will confirm receipt after checking.",
            parse_mode='Markdown'
        )
        return SHIPPING_INFO

async def show_transaction_details(query, context: ContextTypes.DEFAULT_TYPE, 
                                    tx_id: int, as_buyer: bool):
    """Show detailed transaction information"""
    db = Database()
    tx = await db.get_transaction(tx_id)
    
    if not tx:
        await query.edit_message_text("❌ Transaction not found.")
        return
    
    status_emoji = {
        'PENDING': '🟡',
        'APPROVED': '🟢',
        'DELIVERED': '📦',
        'COMPLETED': '✅',
        'REJECTED': '❌',
        'DISPUTED': '⚠️'
    }.get(tx['status'], '⚪')
    
    details = f"""
{status_emoji} **Transaction #{tx['id']}**

**Status:** {tx['status']}
**Digital Product:** {tx['product_description']}
**Amount:** ${tx['amount']:.2f} USD
**Delivery Time:** {tx['delivery_time']}
**Buyer ID:** {tx['buyer_id']}
**Seller ID:** {tx['seller_id']}
**Created:** {tx['created_at'][:16]}
"""
    
    if tx['shipping_info']:
        details += f"\n📦 **Product Details Delivered:**\n{tx['shipping_info']}\n"
    
    if tx['dispute_reason']:
        details += f"\n⚠️ **Dispute Reason:**\n{tx['dispute_reason']}\n"
    
    # Add action buttons based on role and status
    keyboard = []
    
    if as_buyer:
        if tx['status'] == 'DELIVERED':
            keyboard.append([
                InlineKeyboardButton("✅ Confirm Receipt", callback_data=f"confirm_delivery_{tx_id}"),
                InlineKeyboardButton("⚠️ Report Issue", callback_data=f"report_issue_{tx_id}")
            ])
    else:  # Seller
        if tx['status'] == 'APPROVED':
            keyboard.append([
                InlineKeyboardButton("📦 Deliver Product", callback_data=f"mark_shipped_{tx_id}")
            ])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    await query.edit_message_text(
        details,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def approve_transaction(query, context: ContextTypes.DEFAULT_TYPE, tx_id: int):
    """Admin approves transaction"""
    if query.from_user.id != Config.ADMIN_ID:
        await query.answer("❌ You're not authorized to perform this action.", show_alert=True)
        return
    
    db = Database()
    tx = await db.get_transaction(tx_id)
    
    if not tx:
        await query.answer("Transaction not found.", show_alert=True)
        return
    
    await db.update_transaction_status(tx_id, 'APPROVED')
    
    await query.edit_message_text(
        f"✅ Transaction #{tx_id} has been approved!",
        parse_mode='Markdown'
    )
    
    # Notify buyer
    try:
        await context.bot.send_message(
            chat_id=tx['buyer_id'],
            text=f"🟢 Your transaction #{tx_id} has been **APPROVED** by admin!\n\n"
                 f"The seller can now ship the product.",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Failed to notify buyer: {e}")
    
    # Notify seller
    try:
        await context.bot.send_message(
            chat_id=tx['seller_id'],
            text=f"🟢 New sale approved! Transaction #{tx_id}\n\n"
                 f"**Product:** {tx['product_description']}\n"
                 f"**Amount:** ${tx['amount']:.2f}\n\n"
                 f"Use /mysales to ship the product.",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Failed to notify seller: {e}")

async def reject_transaction(query, context: ContextTypes.DEFAULT_TYPE, tx_id: int):
    """Admin rejects transaction"""
    if query.from_user.id != Config.ADMIN_ID:
        await query.answer("❌ You're not authorized to perform this action.", show_alert=True)
        return
    
    db = Database()
    tx = await db.get_transaction(tx_id)
    
    if not tx:
        await query.answer("Transaction not found.", show_alert=True)
        return
    
    await db.update_transaction_status(tx_id, 'REJECTED')
    
    await query.edit_message_text(
        f"❌ Transaction #{tx_id} has been rejected.",
        parse_mode='Markdown'
    )
    
    # Notify buyer
    try:
        await context.bot.send_message(
            chat_id=tx['buyer_id'],
            text=f"❌ Your transaction #{tx_id} has been **REJECTED** by admin.\n\n"
                 f"Please contact support if you have questions.",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Failed to notify buyer: {e}")

async def confirm_delivery(query, context: ContextTypes.DEFAULT_TYPE, tx_id: int):
    """Buyer confirms delivery"""
    db = Database()
    tx = await db.get_transaction(tx_id)
    
    if not tx or tx['buyer_id'] != query.from_user.id:
        await query.answer("❌ Not authorized or transaction not found.", show_alert=True)
        return
    
    if tx['status'] != 'DELIVERED':
        await query.answer("❌ Product must be delivered first!", show_alert=True)
        return
    
    await db.update_transaction_status(tx_id, 'COMPLETED')
    
    # Update seller stats
    await db.increment_sales(tx['seller_id'])
    
    await query.edit_message_text(
        f"✅ **Transaction #{tx_id} Completed!**\n\n"
        f"💰 Funds Released: ${tx['amount']:.2f}\n"
        f"Seller has received payment.\n\n"
        f"Thank you for using Escrow Bot! 🎉\n\n"
        f"💡 Consider leaving a review for the seller!",
        parse_mode='Markdown'
    )
    
    # Notify seller
    try:
        await context.bot.send_message(
            chat_id=tx['seller_id'],
            text=f"💰 **Payment Released!**\n\n"
                 f"Transaction #{tx_id} is complete.\n"
                 f"Amount: ${tx['amount']:.2f}\n\n"
                 f"✅ Buyer confirmed delivery successfully.\n"
                 f"Congratulations on your sale! 🎉\n\n"
                 f"Keep up the good work to build your reputation!",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Failed to notify seller: {e}")

async def get_dispute_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get dispute reason from buyer"""
    reason = update.message.text.strip()
    tx_id = context.user_data.get('dispute_tx_id')
    
    if not tx_id:
        return ConversationHandler.END
    
    db = Database()
    await db.add_dispute(tx_id, reason)
    
    await update.message.reply_text(
        f"⚠️ **Issue Reported**\n\n"
        f"Your dispute for transaction #{tx_id} has been submitted.\n"
        f"An admin will review and contact you shortly.",
        parse_mode='Markdown'
    )
    
    # Notify admin
    try:
        tx = await db.get_transaction(tx_id)
        await context.bot.send_message(
            chat_id=Config.ADMIN_ID,
            text=f"⚠️ **DISPUTE REPORTED**\n\n"
                 f"**Transaction:** #{tx_id}\n"
                 f"**Buyer:** {update.effective_user.first_name} (ID: {update.effective_user.id})\n"
                 f"**Product:** {tx['product_description']}\n"
                 f"**Amount:** ${tx['amount']:.2f}\n\n"
                 f"**Issue:**\n{reason}\n\n"
                 f"Please review immediately!",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Failed to notify admin: {e}")
    
    context.user_data.clear()
    return ConversationHandler.END

async def get_shipping_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get shipping info from seller"""
    shipping_info = update.message.text.strip()
    tx_id = context.user_data.get('shipping_tx_id')
    
    if not tx_id:
        return ConversationHandler.END
    
    db = Database()
    tx = await db.get_transaction(tx_id)
    
    if not tx or tx['seller_id'] != update.effective_user.id:
        await update.message.reply_text("❌ Not authorized or transaction not found.")
        return ConversationHandler.END
    
    await db.update_shipping_info(tx_id, shipping_info)
    await db.update_transaction_status(tx_id, 'DELIVERED')
    
    await update.message.reply_text(
        f"📦 **Digital Product Delivered!**\n\n"
        f"Transaction #{tx_id} status updated to DELIVERED.\n"
        f"The buyer has been notified and will verify the product.\n\n"
        f"✅ Payment will be released once buyer confirms receipt.",
        parse_mode='Markdown'
    )
    
    # Notify buyer
    try:
        await context.bot.send_message(
            chat_id=tx['buyer_id'],
            text=f"📦 **Digital Product Delivered!**\n\n"
                 f"Transaction #{tx_id}\n"
                 f"**Product:** {tx['product_description']}\n\n"
                 f"**Product Details from Seller:**\n{shipping_info}\n\n"
                 f"━━━━━━━━━━━━━━━━━━━━\n"
                 f"⚠️ **Please verify the product immediately:**\n"
                 f"• Check if credentials/code work\n"
                 f"• Verify it matches the description\n"
                 f"• Test access/functionality\n\n"
                 f"Use /mytransactions to:\n"
                 f"✅ Confirm receipt (if all good)\n"
                 f"⚠️ Report issue (if problem found)",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Failed to notify buyer: {e}")
    
    context.user_data.clear()
    return ConversationHandler.END
