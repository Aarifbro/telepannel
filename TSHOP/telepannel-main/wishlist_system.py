"""
Wishlist System
Users can save products and get notifications about price changes
"""

import sqlite3
import json
from datetime import datetime
from telebot import types
from config import DB_NAME, ADMIN_IDS


def init_wishlist_db():
    """Initialize wishlist database"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wishlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                product_category TEXT NOT NULL,
                product_name TEXT,
                added_price INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notified_price_drop BOOLEAN DEFAULT 0,
                UNIQUE(user_id, product_id, product_category)
            )
        ''')
        
        # Index for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_user_wishlist 
            ON wishlists(user_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_product_wishlist 
            ON wishlists(product_id, product_category)
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Wishlist database initialized")
    except Exception as e:
        print(f"❌ Error initializing wishlist DB: {e}")


def add_to_wishlist(user_id, product_id, category, product_name, price=None):
    """
    Add product to user's wishlist
    Returns (success, message)
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Check if already in wishlist
        cursor.execute(
            "SELECT id FROM wishlists WHERE user_id = ? AND product_id = ? AND product_category = ?",
            (user_id, product_id, category)
        )
        
        if cursor.fetchone():
            conn.close()
            return False, "❌ This product is already in your wishlist!"
        
        # Check wishlist limit (max 50 items per user)
        cursor.execute("SELECT COUNT(*) FROM wishlists WHERE user_id = ?", (user_id,))
        count = cursor.fetchone()[0]
        
        if count >= 50:
            conn.close()
            return False, "❌ Wishlist is full! Maximum 50 items allowed. Remove some items first."
        
        # Add to wishlist
        cursor.execute('''
            INSERT INTO wishlists (user_id, product_id, product_category, product_name, added_price)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, product_id, category, product_name, price))
        
        conn.commit()
        conn.close()
        
        return True, "✅ Added to wishlist!"
        
    except Exception as e:
        print(f"Error adding to wishlist: {e}")
        return False, f"❌ Error: {str(e)}"


def remove_from_wishlist(user_id, wishlist_id):
    """
    Remove product from wishlist
    Returns (success, message)
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM wishlists WHERE id = ? AND user_id = ?",
            (wishlist_id, user_id)
        )
        
        if cursor.rowcount == 0:
            conn.close()
            return False, "❌ Item not found in your wishlist!"
        
        conn.commit()
        conn.close()
        
        return True, "✅ Removed from wishlist!"
        
    except Exception as e:
        print(f"Error removing from wishlist: {e}")
        return False, f"❌ Error: {str(e)}"


def get_user_wishlist(user_id):
    """Get all wishlist items for a user"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, product_id, product_category, product_name, added_price, added_at
            FROM wishlists
            WHERE user_id = ?
            ORDER BY added_at DESC
        ''', (user_id,))
        
        items = cursor.fetchall()
        conn.close()
        
        return items
        
    except Exception as e:
        print(f"Error getting wishlist: {e}")
        return []


def get_wishlist_count(user_id):
    """Get count of items in user's wishlist"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM wishlists WHERE user_id = ?", (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
        
    except Exception as e:
        print(f"Error getting wishlist count: {e}")
        return 0


def check_product_in_wishlist(user_id, product_id, category):
    """Check if product is in user's wishlist"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id FROM wishlists WHERE user_id = ? AND product_id = ? AND product_category = ?",
            (user_id, product_id, category)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        return result is not None
        
    except Exception as e:
        print(f"Error checking wishlist: {e}")
        return False


def notify_price_drop(bot, product_id, category, old_price, new_price):
    """
    Notify all users who have this product in wishlist about price drop
    Should be called when product price changes
    """
    try:
        if new_price >= old_price:
            return  # Not a price drop
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, product_name, added_price
            FROM wishlists
            WHERE product_id = ? AND product_category = ? AND notified_price_drop = 0
        ''', (product_id, category))
        
        users = cursor.fetchall()
        
        # Mark as notified
        cursor.execute('''
            UPDATE wishlists
            SET notified_price_drop = 1
            WHERE product_id = ? AND product_category = ?
        ''', (product_id, category))
        
        conn.commit()
        conn.close()
        
        # Send notifications
        discount_percent = int(((old_price - new_price) / old_price) * 100)
        
        for user_id, product_name, added_price in users:
            try:
                text = f"""🔔 <b>Price Drop Alert!</b>

📦 <b>{product_name}</b>

💰 Price dropped by <b>{discount_percent}%</b>!
• Was: <code>{old_price}</code> credits
• Now: <code>{new_price}</code> credits

💾 You save: <b>{old_price - new_price}</b> credits!

Don't miss this deal!"""
                
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("🛒 Buy Now", callback_data=f"buy_{category}_{product_id}"),
                    types.InlineKeyboardButton("💝 View Wishlist", callback_data="wishlist_menu")
                )
                
                bot.send_message(user_id, text, reply_markup=markup, parse_mode="HTML")
                
            except Exception as e:
                print(f"Failed to notify user {user_id}: {e}")
        
    except Exception as e:
        print(f"Error notifying price drop: {e}")


def register_wishlist_handlers(bot):
    """Register wishlist handlers"""
    
    # Initialize DB
    init_wishlist_db()
    
    @bot.callback_query_handler(func=lambda call: call.data == "wishlist_menu")
    def wishlist_menu(call):
        """Show wishlist menu"""
        user_id = call.from_user.id
        items = get_user_wishlist(user_id)
        
        if not items:
            text = """💝 <b>Your Wishlist</b>

Your wishlist is empty!

Add products to your wishlist to:
• Track your favorite items
• Get price drop notifications
• Quick access to products you want

Browse products and click the ⭐ button to add them to your wishlist!"""
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
            
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="HTML"
            )
            return
        
        text = f"""💝 <b>Your Wishlist</b>

You have <b>{len(items)}</b> saved items:

"""
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        # Show first 10 items
        for item in items[:10]:
            wishlist_id, product_id, category, name, price, added_at = item
            
            # Format date
            date_str = added_at[:10] if added_at else "Unknown"
            
            # Create button
            button_text = f"📦 {name[:30]}"
            if price:
                button_text += f" • {price}💰"
            
            markup.add(types.InlineKeyboardButton(
                button_text,
                callback_data=f"wishlist_item_{wishlist_id}"
            ))
        
        if len(items) > 10:
            text += f"\n<i>Showing 10 of {len(items)} items</i>\n"
        
        text += "\n💡 Click an item to view details or remove it."
        
        markup.add(
            types.InlineKeyboardButton("🗑️ Clear All", callback_data="wishlist_clear_confirm"),
            types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")
        )
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("wishlist_item_"))
    def wishlist_item_details(call):
        """Show wishlist item details"""
        try:
            wishlist_id = int(call.data.replace("wishlist_item_", ""))
            user_id = call.from_user.id
            
            # Get item details
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT product_id, product_category, product_name, added_price, added_at
                FROM wishlists
                WHERE id = ? AND user_id = ?
            ''', (wishlist_id, user_id))
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                bot.answer_callback_query(call.id, "❌ Item not found!", show_alert=True)
                return
            
            product_id, category, name, price, added_at = result
            
            text = f"""📦 <b>Wishlist Item Details</b>

<b>Product:</b> {name}
<b>Category:</b> {category.replace('_', ' ').title()}
<b>Price When Added:</b> {price or 'N/A'} credits
<b>Added:</b> {added_at[:10] if added_at else 'Unknown'}

What would you like to do?"""
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🛒 Buy Now", callback_data=f"buy_{category}_{product_id}"),
                types.InlineKeyboardButton("🗑️ Remove from Wishlist", callback_data=f"wishlist_remove_{wishlist_id}"),
                types.InlineKeyboardButton("⬅️ Back to Wishlist", callback_data="wishlist_menu")
            )
            
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="HTML"
            )
            
        except Exception as e:
            print(f"Error showing wishlist item: {e}")
            bot.answer_callback_query(call.id, "❌ Error loading item", show_alert=True)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("wishlist_remove_"))
    def remove_wishlist_item(call):
        """Remove item from wishlist"""
        try:
            wishlist_id = int(call.data.replace("wishlist_remove_", ""))
            user_id = call.from_user.id
            
            success, message = remove_from_wishlist(user_id, wishlist_id)
            
            bot.answer_callback_query(call.id, message, show_alert=True)
            
            if success:
                # Refresh wishlist
                wishlist_menu(call)
            
        except Exception as e:
            print(f"Error removing wishlist item: {e}")
            bot.answer_callback_query(call.id, "❌ Error removing item", show_alert=True)
    
    @bot.callback_query_handler(func=lambda call: call.data == "wishlist_clear_confirm")
    def confirm_clear_wishlist(call):
        """Confirm clearing entire wishlist"""
        user_id = call.from_user.id
        count = get_wishlist_count(user_id)
        
        text = f"""⚠️ <b>Clear Wishlist</b>

Are you sure you want to remove all <b>{count} items</b> from your wishlist?

This action cannot be undone!"""
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Yes, Clear All", callback_data="wishlist_clear_confirmed"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="wishlist_menu")
        )
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "wishlist_clear_confirmed")
    def clear_wishlist(call):
        """Clear entire wishlist"""
        try:
            user_id = call.from_user.id
            
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM wishlists WHERE user_id = ?", (user_id,))
            count = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            bot.answer_callback_query(call.id, f"✅ Removed {count} items from wishlist!", show_alert=True)
            
            # Refresh menu
            wishlist_menu(call)
            
        except Exception as e:
            print(f"Error clearing wishlist: {e}")
            bot.answer_callback_query(call.id, "❌ Error clearing wishlist", show_alert=True)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("wishlist_add_"))
    def add_wishlist_item(call):
        """Add item to wishlist from product view"""
        try:
            # Parse: wishlist_add_category_productid_name_price
            parts = call.data.split("_", 3)
            category = parts[2]
            product_id = parts[3]
            
            # You'll need to get product details from your products system
            # This is a placeholder
            product_name = f"Product {product_id}"
            price = 0
            
            user_id = call.from_user.id
            success, message = add_to_wishlist(user_id, product_id, category, product_name, price)
            
            bot.answer_callback_query(call.id, message, show_alert=True)
            
        except Exception as e:
            print(f"Error adding to wishlist: {e}")
            bot.answer_callback_query(call.id, "❌ Error adding to wishlist", show_alert=True)
    
    # Admin command to view wishlist stats
    @bot.message_handler(commands=['wishlist_stats'])
    def admin_wishlist_stats(message):
        """Show wishlist statistics (admin only)"""
        if message.from_user.id not in ADMIN_IDS:
            return
        
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            # Overall stats
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT user_id) as total_users,
                    COUNT(*) as total_items,
                    product_category,
                    COUNT(*) as category_count
                FROM wishlists
                GROUP BY product_category
                ORDER BY category_count DESC
            """)
            
            category_stats = cursor.fetchall()
            
            # Get total counts
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT user_id) as users,
                    COUNT(*) as items
                FROM wishlists
            """)
            
            total_users, total_items = cursor.fetchone()
            
            # Most wishlisted products
            cursor.execute("""
                SELECT product_name, product_category, COUNT(*) as count
                FROM wishlists
                GROUP BY product_id, product_category
                ORDER BY count DESC
                LIMIT 5
            """)
            
            top_products = cursor.fetchall()
            conn.close()
            
            text = f"""💝 <b>Wishlist Statistics</b>

<b>📊 Overall Stats:</b>
• Users with wishlists: {total_users or 0}
• Total items: {total_items or 0}
• Average per user: {(total_items / total_users) if total_users else 0:.1f}

<b>📦 By Category:</b>
"""
            
            for _, _, category, count in category_stats[:5]:
                text += f"• {category}: {count} items\n"
            
            text += "\n<b>🌟 Most Wishlisted Products:</b>\n"
            
            for idx, (name, cat, count) in enumerate(top_products, 1):
                text += f"{idx}. {name} ({cat}): {count} users\n"
            
            bot.reply_to(message, text, parse_mode="HTML")
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}")

    print("✅ Wishlist system handlers registered")


# Helper function to add wishlist button to product displays
def get_wishlist_button(user_id, product_id, category, product_name):
    """
    Generate wishlist button for product displays
    Returns InlineKeyboardButton
    """
    is_in_wishlist = check_product_in_wishlist(user_id, product_id, category)
    
    if is_in_wishlist:
        return types.InlineKeyboardButton(
            "⭐ In Wishlist",
            callback_data=f"wishlist_remove_{product_id}_{category}"
        )
    else:
        return types.InlineKeyboardButton(
            "🤍 Add to Wishlist",
            callback_data=f"wishlist_add_{category}_{product_id}"
        )
