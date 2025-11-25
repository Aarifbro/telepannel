from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database import Database
from src.config import Config

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id == Config.ADMIN_ID

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin panel"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You don't have admin permissions.")
        return
    
    db = Database()
    stats = await db.get_statistics()
    pending = await db.get_pending_transactions()
    
    panel_text = f"""
🔐 **Admin Panel**

📊 **Statistics:**
• Total Transactions: {stats['total_transactions']}
• Total Users: {stats['total_users']}
• Completed Amount: ${stats['total_amount']:.2f}

**Status Breakdown:**
"""
    
    for status, count in stats['status_counts'].items():
        emoji = {
            'PENDING': '🟡',
            'APPROVED': '🟢',
            'SHIPPED': '📦',
            'COMPLETED': '✅',
            'REJECTED': '❌',
            'DISPUTED': '⚠️'
        }.get(status, '⚪')
        panel_text += f"• {emoji} {status}: {count}\n"
    
    panel_text += f"\n🟡 **Pending Transactions:** {len(pending)}"
    
    await update.message.reply_text(panel_text, parse_mode='Markdown')
    
    # Show pending transactions
    if pending:
        await update.message.reply_text(
            "📋 **Pending Transactions (Require Review):**",
            parse_mode='Markdown'
        )
        
        for tx in pending:
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{tx['id']}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{tx['id']}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            tx_details = f"""
🟡 **Transaction #{tx['id']}**

**Buyer ID:** {tx['buyer_id']}
**Seller ID:** {tx['seller_id']}
**Product:** {tx['product_description']}
**Amount:** ${tx['amount']:.2f}
**Delivery:** {tx['delivery_time']}
**Created:** {tx['created_at']}
"""
            
            await update.message.reply_text(
                tx_details,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show statistics (available to all users)"""
    db = Database()
    stats = await db.get_statistics()
    
    stats_text = f"""
📊 **Escrow Bot Statistics**

**Overall:**
• 🔢 Total Transactions: {stats['total_transactions']}
• 👥 Total Users: {stats['total_users']}
• 💰 Total Volume: ${stats['total_amount']:.2f}

**By Status:**
"""
    
    for status, count in sorted(stats['status_counts'].items()):
        emoji = {
            'PENDING': '🟡',
            'APPROVED': '🟢',
            'SHIPPED': '📦',
            'COMPLETED': '✅',
            'REJECTED': '❌',
            'DISPUTED': '⚠️'
        }.get(status, '⚪')
        stats_text += f"• {emoji} {status}: {count}\n"
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')
