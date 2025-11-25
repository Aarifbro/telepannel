from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database import Database
from src.config import Config

async def buy_listing_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle buying a listing directly"""
    query = update.callback_query
    await query.answer()
    
    listing_id = int(query.data.split('_')[2])
    
    db = Database()
    listing = await db.get_listing(listing_id)
    
    if not listing:
        await query.message.edit_text("❌ This listing is no longer available.")
        return
    
    if query.from_user.id == listing['seller_id']:
        await query.answer("❌ You cannot buy your own listing!", show_alert=True)
        return
    
    # Create transaction automatically
    tx_id = await db.create_transaction(
        buyer_id=query.from_user.id,
        seller_id=listing['seller_id'],
        product_description=f"{listing['title']} - {listing['description'][:100]}",
        amount=listing['price'],
        delivery_time=listing['delivery_time']
    )
    
    # Notify admin
    try:
        admin_message = f"""
🔔 **New Purchase - Digital Product**

**Transaction ID:** #{tx_id}
**Listing:** {listing['title']}
**Buyer:** {query.from_user.first_name} (ID: {query.from_user.id})
**Seller:** {listing['first_name']} (ID: {listing['seller_id']})
**Amount:** ${listing['price']:.2f}
**Expected Delivery:** {listing['delivery_time']}

Use /admin to review and approve this transaction.
"""
        await context.bot.send_message(
            chat_id=Config.ADMIN_ID,
            text=admin_message,
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Failed to notify admin: {e}")
    
    # Notify seller
    try:
        await context.bot.send_message(
            chat_id=listing['seller_id'],
            text=f"🎉 **New Sale!**\n\n"
                 f"Someone purchased your product:\n"
                 f"**{listing['title']}**\n\n"
                 f"Transaction #{tx_id}\n"
                 f"Amount: ${listing['price']:.2f}\n\n"
                 f"⏳ Waiting for admin approval...\n"
                 f"You'll be notified when you can deliver the product.",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Failed to notify seller: {e}")
    
    success_message = f"""
✅ **Purchase Initiated Successfully!**

**Transaction ID:** #{tx_id}
**Product:** {listing['title']}
**Seller:** {listing['first_name']}
**Amount:** ${listing['price']:.2f}
**Expected Delivery:** {listing['delivery_time']}

**🔐 Escrow Protection Active:**
Your payment of ${listing['price']:.2f} is now held in secure escrow.

**📋 What Happens Next:**
1️⃣ Admin reviews and approves transaction (few minutes)
2️⃣ Seller delivers product details to you
3️⃣ You verify the product works
4️⃣ Confirm receipt to release payment
5️⃣ Rate the seller

**⏳ Current Status:** 🟡 PENDING
Waiting for admin approval...

You'll be notified at each step. Track progress with /mytransactions
"""
    
    await query.message.edit_text(success_message, parse_mode='Markdown')
