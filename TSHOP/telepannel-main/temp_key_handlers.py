"""
Temporary Key System Handlers
Separate file to handle temp key functionality with proper bot instance access
"""

import sqlite3
from datetime import datetime
from telebot import types
from temp_key_system import generate_temp_key, claim_temp_key, get_active_keys, cleanup_expired_keys, get_user_claims
from config import ADMIN_ID
import random

def register_temp_key_handlers(bot_instance):
    """Register all temporary key related handlers"""
    
    # --- OWNER TEMP KEY MANAGER ---
    @bot_instance.callback_query_handler(func=lambda call: call.data == "temp_key_manager")
    def temp_key_manager_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot_instance.answer_callback_query(call.id, "❌ Owner only access", show_alert=True)
            return
        
        # Get active keys count
        active_keys = get_active_keys()
        active_count = len(active_keys)
        
        manager_text = f"""🔑 <b>Temporary Key Manager</b>

📊 <b>Statistics:</b>
• Active Keys: {active_count}
• Expiry Time: 20 minutes
• Auto Cleanup: Enabled

⚡ <b>Quick Actions:</b>"""

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔄 Generate New Key", callback_data="generate_temp_key"),
            types.InlineKeyboardButton("📋 View All Keys", callback_data="view_all_temp_keys")
        )
        markup.add(
            types.InlineKeyboardButton("🧹 Cleanup Expired", callback_data="cleanup_expired_keys"),
            types.InlineKeyboardButton("📊 Key Statistics", callback_data="temp_key_stats")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Owner Panel", callback_data="owner_panel"))
        
        try:
            bot_instance.edit_message_text(manager_text, call.message.chat.id, call.message.message_id,
                                         reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            bot_instance.send_message(call.message.chat.id, manager_text, reply_markup=markup, parse_mode="HTML")

    # --- GENERATE KEY SELECTOR ---
    @bot_instance.callback_query_handler(func=lambda call: call.data == "generate_temp_key")
    def generate_temp_key_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot_instance.answer_callback_query(call.id, "❌ Owner only access", show_alert=True)
            return
        
        generate_text = """🔑 <b>Generate Temporary Key</b>

Select the type of reward for this key:

🎁 <b>Available Rewards:</b>"""

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("💳 CC Shop", callback_data="gen_key_cc_shop"),
            types.InlineKeyboardButton("🔧 Method & BINs", callback_data="gen_key_method_bins")
        )
        markup.add(
            types.InlineKeyboardButton("🎁 Gift Cards", callback_data="gen_key_gift_cards"),
            types.InlineKeyboardButton("🔧 Hacks", callback_data="gen_key_hacks")
        )
        markup.add(
            types.InlineKeyboardButton("💾 Dumps", callback_data="gen_key_dumps"),
            types.InlineKeyboardButton("🖥️ RDP", callback_data="gen_key_rdp")
        )
        markup.add(
            types.InlineKeyboardButton("💰 Free Credits", callback_data="gen_key_credits"),
            types.InlineKeyboardButton("🎲 Random Item", callback_data="gen_key_random")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Key Manager", callback_data="temp_key_manager"))
        
        bot_instance.edit_message_text(generate_text, call.message.chat.id, call.message.message_id,
                                     reply_markup=markup, parse_mode="HTML")

    # --- KEY GENERATION HANDLERS ---
    @bot_instance.callback_query_handler(func=lambda call: call.data.startswith("gen_key_"))
    def handle_key_generation_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot_instance.answer_callback_query(call.id, "❌ Owner only access", show_alert=True)
            return
        
        key_type = call.data.replace("gen_key_", "")
        
        # Define product data based on key type
        if key_type == "credits":
            product_data = {
                "type": "credits",
                "amount": "100",  # Default amount
                "description": "100 Free Credits"
            }
        elif key_type == "cc_shop":
            product_data = {
                "type": "cc_shop",
                "item": "Credit Card",
                "description": "Premium CC"
            }
        elif key_type == "method_bins":
            product_data = {
                "type": "method_bins",
                "item": "Method & BIN",
                "description": "Payment method and BIN data"
            }
        elif key_type == "gift_cards":
            product_data = {
                "type": "gift_cards",
                "item": "Gift Card",
                "description": "Digital gift card"
            }
        elif key_type == "random":
            # Random item
            types_list = ["credits", "cc_shop", "method_bins", "gift_cards"]
            random_type = random.choice(types_list)
            # Recursive call with random type
            call.data = f"gen_key_{random_type}"
            return handle_key_generation_callback(call)
        else:
            product_data = {
                "type": key_type,
                "item": f"{key_type.title()} Item",
                "description": f"Premium {key_type} product"
            }
        
        # Generate the key
        key_code = generate_temp_key(product_data["type"], product_data, 20)
        
        if key_code:
            success_text = f"""✅ <b>Key Generated Successfully!</b>

🔑 <b>Key Code:</b> <code>{key_code}</code>
🎁 <b>Type:</b> {product_data['description']}
⏰ <b>Expires:</b> 20 minutes
🎲 <b>Random:</b> {"Yes" if key_type == "random" else "No"}

<b>Share this key with users to claim!</b>"""

            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("📋 Copy Key", callback_data=f"copy_key_{key_code}"),
                types.InlineKeyboardButton("🔄 Generate Another", callback_data="generate_temp_key")
            )
            markup.add(types.InlineKeyboardButton("⬅️ Back to Manager", callback_data="temp_key_manager"))
            
            bot_instance.edit_message_text(success_text, call.message.chat.id, call.message.message_id,
                                         reply_markup=markup, parse_mode="HTML")
        else:
            bot_instance.answer_callback_query(call.id, "❌ Failed to generate key!", show_alert=True)

    # --- VIEW ALL KEYS ---
    @bot_instance.callback_query_handler(func=lambda call: call.data == "view_all_temp_keys")
    def view_all_temp_keys_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot_instance.answer_callback_query(call.id, "❌ Owner only access", show_alert=True)
            return
        
        active_keys = get_active_keys()
        
        if not active_keys:
            keys_text = """📋 <b>Active Temporary Keys</b>

❌ <b>No active keys found!</b>

Generate some keys to see them here."""
        else:
            keys_text = f"""📋 <b>Active Temporary Keys</b>

🔢 <b>Total:</b> {len(active_keys)} keys

<b>📝 Key List:</b>
"""
            for i, key in enumerate(active_keys[:10], 1):  # Show first 10
                key_code, key_type, expires_at, reward_text = key
                keys_text += f"\n{i}. <code>{key_code}</code>\n   🎁 {reward_text}\n   ⏰ Expires: {expires_at}\n"
            
            if len(active_keys) > 10:
                keys_text += f"\n<i>... and {len(active_keys) - 10} more keys</i>"

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔄 Refresh", callback_data="view_all_temp_keys"),
            types.InlineKeyboardButton("🧹 Cleanup", callback_data="cleanup_expired_keys")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Manager", callback_data="temp_key_manager"))
        
        bot_instance.edit_message_text(keys_text, call.message.chat.id, call.message.message_id,
                                     reply_markup=markup, parse_mode="HTML")

    # --- CLEANUP EXPIRED KEYS ---
    @bot_instance.callback_query_handler(func=lambda call: call.data == "cleanup_expired_keys")
    def cleanup_expired_keys_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot_instance.answer_callback_query(call.id, "❌ Owner only access", show_alert=True)
            return
        
        cleaned_count = cleanup_expired_keys()
        
        cleanup_text = f"""🧹 <b>Cleanup Complete!</b>

✅ <b>Removed:</b> {cleaned_count} expired keys
🔄 <b>Status:</b> Database optimized

Keys are automatically cleaned every 5 minutes, but you can manually trigger cleanup anytime."""

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("📋 View Active Keys", callback_data="view_all_temp_keys"),
            types.InlineKeyboardButton("📊 Statistics", callback_data="temp_key_stats")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Manager", callback_data="temp_key_manager"))
        
        bot_instance.edit_message_text(cleanup_text, call.message.chat.id, call.message.message_id,
                                     reply_markup=markup, parse_mode="HTML")

    # --- KEY STATISTICS ---
    @bot_instance.callback_query_handler(func=lambda call: call.data == "temp_key_stats")
    def temp_key_stats_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot_instance.answer_callback_query(call.id, "❌ Owner only access", show_alert=True)
            return
        
        try:
            conn = sqlite3.connect('temp_keys.db')
            cursor = conn.cursor()
            
            # Get total stats
            cursor.execute("SELECT COUNT(*) FROM temp_keys")
            total_generated = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM key_claims")
            total_claimed = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM temp_keys WHERE expires_at > datetime('now')")
            active_keys = cursor.fetchone()[0]
            
            # Get top key types
            cursor.execute("""
                SELECT key_type, COUNT(*) as count 
                FROM temp_keys 
                GROUP BY key_type 
                ORDER BY count DESC 
                LIMIT 5
            """)
            top_types = cursor.fetchall()
            
            conn.close()
            
            stats_text = f"""📊 <b>Temporary Key Statistics</b>

🔢 <b>Overall Stats:</b>
• Total Generated: {total_generated}
• Total Claimed: {total_claimed}
• Currently Active: {active_keys}
• Claim Rate: {(total_claimed/max(total_generated,1)*100):.1f}%

🏆 <b>Popular Types:</b>
"""

            for i, (key_type, count) in enumerate(top_types, 1):
                stats_text += f"{i}. {key_type.title()}: {count} keys\n"

            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🔄 Refresh Stats", callback_data="temp_key_stats"),
                types.InlineKeyboardButton("📋 View Keys", callback_data="view_all_temp_keys")
            )
            markup.add(types.InlineKeyboardButton("⬅️ Back to Manager", callback_data="temp_key_manager"))
            
            bot_instance.edit_message_text(stats_text, call.message.chat.id, call.message.message_id,
                                         reply_markup=markup, parse_mode="HTML")
            
        except Exception as e:
            bot_instance.answer_callback_query(call.id, f"❌ Stats error: {str(e)[:50]}", show_alert=True)

    # --- COPY KEY HANDLER ---
    @bot_instance.callback_query_handler(func=lambda call: call.data.startswith("copy_key_"))
    def copy_key_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot_instance.answer_callback_query(call.id, "❌ Owner only access", show_alert=True)
            return
        
        key_code = call.data.replace("copy_key_", "")
        bot_instance.answer_callback_query(
            call.id,
            f"📋 Key copied!\n{key_code}",
            show_alert=True
        )

    print("✅ Temporary key handlers registered successfully!")