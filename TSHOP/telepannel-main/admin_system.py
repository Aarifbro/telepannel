"""
Complete Admin Panel System - Optimized and Fixed
This module handles all admin panel functionality with proper organization
"""

from telebot import types
import sqlite3
from datetime import datetime
from config import ADMIN_ID, DB_NAME


def is_owner(user_id):
    """Check if user is the owner"""
    return user_id == ADMIN_ID


def is_global_admin(user_id):
    """Check if user is a global admin or owner"""
    if user_id == ADMIN_ID:
        return True
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            return c.fetchone() is not None
    except:
        return False


def get_section_admins(user_id):
    """Get list of sections user is admin for"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT section FROM section_admins WHERE user_id = ?", (user_id,))
            return [row[0] for row in c.fetchall()]
    except:
        return []


def has_admin_access(user_id):
    """Check if user has any admin access"""
    return is_owner(user_id) or is_global_admin(user_id) or len(get_section_admins(user_id)) > 0


def register_complete_admin_system(bot, user_states, get_products_from_cache, save_products_to_file_and_reload):
    """Register all admin panel handlers"""
    
    # ============================================================
    # OWNER PANEL - Complete Control
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "owner_panel")
    def owner_panel_handler(call):
        """Owner panel - full system control"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner access only!", show_alert=True)
            return
        
        # Get statistics
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM users")
                user_count = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM admins")
                admin_count = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM orders")
                order_count = c.fetchone()[0]
        except:
            user_count = admin_count = order_count = 0
        
        text = (
            "╔════════════════════════╗\n"
            "       👑 <b>OWNER PANEL</b>\n"
            "╚════════════════════════╝\n\n"
            f"<b>📊 Quick Stats</b>\n"
            f"├ 👥 Users: <code>{user_count}</code>\n"
            f"├ 🛡️ Admins: <code>{admin_count}</code>\n"
            f"└ 📦 Orders: <code>{order_count}</code>\n\n"
            f"<i>💼 Complete system control access</i>"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # Row 1: Admin & User Management
        markup.add(
            types.InlineKeyboardButton("👥 Admin Management", callback_data="owner_admin_management"),
            types.InlineKeyboardButton("👤 User Management", callback_data="admin_users_menu")
        )
        
        # Row 2: Products & Orders
        markup.add(
            types.InlineKeyboardButton("📦 Products", callback_data="admin_products_menu"),
            types.InlineKeyboardButton("📋 Orders", callback_data="admin_orders_menu")
        )
        
        # Row 3: Payments & Analytics
        markup.add(
            types.InlineKeyboardButton("💰 Payments", callback_data="admin_payments_menu"),
            types.InlineKeyboardButton("📈 Analytics", callback_data="admin_analytics_menu")
        )
        
        # Row 4: Communication & Support
        markup.add(
            types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
            types.InlineKeyboardButton("💬 Support", callback_data="admin_support_dashboard")
        )
        
        # Row 5: Content & Media
        markup.add(
            types.InlineKeyboardButton("🖼️ Media Manager", callback_data="admin_media_menu"),
            types.InlineKeyboardButton("📊 Section Status", callback_data="section_status_manager")
        )
        
        # Row 6: Rewards & Keys
        markup.add(
            types.InlineKeyboardButton("🎁 Keys & Giveaways", callback_data="admin_keys_menu")
        )
        
        # Row 7: System Settings
        markup.add(
            types.InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings_menu"),
            types.InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    # ============================================================
    # ADMIN PANEL - For Global & Section Admins
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
    def admin_panel_handler(call):
        """Admin panel for global and section admins"""
        user_id = call.from_user.id
        
        # If owner, redirect to owner panel
        if is_owner(user_id):
            owner_panel_handler(call)
            return
        
        if not has_admin_access(user_id):
            bot.answer_callback_query(call.id, "❌ Admin access required!", show_alert=True)
            return
        
        owner = False
        global_admin = is_global_admin(user_id)
        sections = get_section_admins(user_id)
        
        # Build role text
        if global_admin:
            role = "🛡️ Global Admin"
        else:
            role = f"🔧 Section Admin ({', '.join(sections)})"
        
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "    ⚙️ <b>ADMIN CONTROL PANEL</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👋 Welcome, <b>{call.from_user.first_name}</b>\n"
            f"🎭 Your Role: <b>{role}</b>\n\n"
            f"<i>⚡ Your management tools:</i>"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        if global_admin:
            # Global admin has full access
            markup.add(
                types.InlineKeyboardButton("📦 Products", callback_data="admin_products_menu"),
                types.InlineKeyboardButton("📋 Orders", callback_data="admin_orders_menu")
            )
            markup.add(
                types.InlineKeyboardButton("👥 Users", callback_data="admin_users_menu"),
                types.InlineKeyboardButton("🔎 Lookup", callback_data="admin_lookup_menu")
            )
            markup.add(
                types.InlineKeyboardButton("💰 Payments", callback_data="admin_payments_menu"),
                types.InlineKeyboardButton("💬 Support", callback_data="admin_support_dashboard")
            )
            markup.add(
                types.InlineKeyboardButton("📈 Analytics", callback_data="admin_analytics_menu"),
                types.InlineKeyboardButton("🎁 Keys", callback_data="admin_keys_menu")
            )
        else:
            # Section admin - limited access
            for section in sections:
                section_name = section.replace("_", " ").title()
                markup.add(
                    types.InlineKeyboardButton(f"📦 {section_name} Products", 
                                             callback_data=f"admin_cat_menu_{section}")
                )
                markup.add(
                    types.InlineKeyboardButton(f"📋 {section_name} Orders",
                                             callback_data=f"admin_orders_{section}")
                )
        
        # Back
        markup.add(types.InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    # ============================================================
    # ADMIN PRODUCTS MENU
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "admin_products_menu")
    def admin_products_menu_handler(call):
        """Products management menu"""
        if not is_global_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Global admin required!", show_alert=True)
            return
        
        text = (
            "📦 <b>Products Management</b>\n\n"
            "Select a category to manage:\n\n"
            "• Add new products\n"
            "• Edit existing items\n"
            "• Delete products\n"
            "• Bulk operations"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # Product categories
        markup.add(
            types.InlineKeyboardButton("💳 CC Shop", callback_data="admin_cat_menu_custom_ccs"),
            types.InlineKeyboardButton("💎 BINs", callback_data="admin_cat_menu_bins")
        )
        markup.add(
            types.InlineKeyboardButton("📦 Methods", callback_data="admin_cat_menu_methods"),
            types.InlineKeyboardButton("🎁 Bundles", callback_data="admin_cat_menu_method_bins")
        )
        markup.add(
            types.InlineKeyboardButton("📄 Live Dumps", callback_data="admin_cat_menu_dumps_live"),
            types.InlineKeyboardButton("⚡ Charged Dumps", callback_data="admin_cat_menu_dumps_charged")
        )
        markup.add(
            types.InlineKeyboardButton("🖥️ RDP", callback_data="admin_cat_menu_rdp"),
            types.InlineKeyboardButton("🎁 Gift Cards", callback_data="admin_cat_menu_gift_cards")
        )
        markup.add(
            types.InlineKeyboardButton("👤 Accounts", callback_data="admin_cat_menu_accounts"),
            types.InlineKeyboardButton("📦 Other", callback_data="admin_cat_menu_other")
        )
        
        # Back button
        back_data = "owner_panel" if is_owner(call.from_user.id) else "admin_panel"
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=back_data))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    # ============================================================
    # ADMIN SETTINGS MENU  
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "admin_settings_menu")
    def admin_settings_menu_handler(call):
        """System settings menu - owner only"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
        
        text = (
            "⚙️ <b>System Settings</b>\n\n"
            "Configure bot behavior and features:\n\n"
            "• Section Status\n"
            "• Force Join Channels\n"
            "• Payment Methods\n"
            "• Bot Configuration"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("📊 Section Status", callback_data="admin_section_status"),
            types.InlineKeyboardButton("🔗 Force Join", callback_data="admin_force_join")
        )
        markup.add(
            types.InlineKeyboardButton("💳 Payment Config", callback_data="admin_payment_config"),
            types.InlineKeyboardButton("🤖 Bot Config", callback_data="admin_bot_config")
        )
        
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_panel"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    # ============================================================
    # ADMIN MEDIA MENU
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "admin_media_menu")
    def admin_media_menu_handler(call):
        """Media management menu"""
        if not is_global_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Admin access required!", show_alert=True)
            return
        
        text = (
            "🖼️ <b>Media Management</b>\n\n"
            "Manage bot animations and media:\n\n"
            "• Welcome GIFs\n"
            "• Success animations\n"
            "• Error animations\n"
            "• Custom media pool"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("📤 Upload Media", callback_data="admin_upload_media"),
            types.InlineKeyboardButton("📊 View Pool", callback_data="admin_view_media")
        )
        markup.add(
            types.InlineKeyboardButton("🗑️ Clear Pool", callback_data="admin_clear_media")
        )
        
        back_data = "owner_panel" if is_owner(call.from_user.id) else "admin_panel"
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=back_data))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    # ============================================================
    # ADMIN KEYS MENU
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "admin_keys_menu")
    def admin_keys_menu_handler(call):
        """Pro keys and giveaway management"""
        if not is_global_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Admin access required!", show_alert=True)
            return
        
        text = (
            "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "┃  🎁 <b>KEYS & GIVEAWAYS</b>   ┃\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            "╭─ 🔑 <b>Pro Keys</b> ──────────╮\n"
            "│\n"
            "│ • Generate premium keys\n"
            "│ • View all keys\n"
            "│ • Check usage status\n"
            "│\n"
            "╰────────────────────────────╯\n\n"
            "╭─ 🎁 <b>Giveaways</b> ─────────╮\n"
            "│\n"
            "│ • Pick random winners\n"
            "│ • Run contests\n"
            "│ • Reward users\n"
            "│\n"
            "╰────────────────────────────╯"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        # Pro Keys Section
        markup.add(types.InlineKeyboardButton("═══ 🔑 PRO KEYS ═══", callback_data="noop_admin"))
        markup.add(
            types.InlineKeyboardButton("➕ Generate Key", callback_data="generate_pro_key"),
            types.InlineKeyboardButton("📋 View Keys", callback_data="view_pro_keys")
        )
        
        # Giveaway Section
        markup.add(types.InlineKeyboardButton("═══ 🎁 GIVEAWAYS ═══", callback_data="noop_admin"))
        markup.add(
            types.InlineKeyboardButton("🏆 Pick Winner", callback_data="admin_pick_winner"),
            types.InlineKeyboardButton("🎪 New Contest", callback_data="admin_new_contest")
        )
        
        back_data = "owner_panel" if is_owner(call.from_user.id) else "admin_panel"
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=back_data))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    # Pro Keys Handlers
    @bot.callback_query_handler(func=lambda call: call.data == "generate_pro_key")
    def generate_pro_key_handler(call):
        """Generate new pro key"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
        
        try:
            from pro_key_system import generate_pro_key
            new_key = generate_pro_key(call.from_user.id)
            
            text = (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃  ✅ <b>KEY GENERATED!</b>    ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "╭─ 🔑 <b>Pro Key Details</b> ────╮\n"
                "│\n"
                f"│ <code>{new_key}</code>\n"
                "│\n"
                "│ <b>Status:</b> ✅ Active\n"
                "│ <b>Type:</b> Premium Access\n"
                "│ <b>Uses:</b> Single Use\n"
                "│\n"
                "╰────────────────────────────╯\n\n"
                "<i>💡 Share this key with users for premium access!</i>"
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Generate Another", callback_data="generate_pro_key"))
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_keys_menu"))
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}", show_alert=True)
    
    @bot.callback_query_handler(func=lambda call: call.data == "view_pro_keys")
    def view_pro_keys_handler(call):
        """View all pro keys"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
        
        try:
            from pro_key_system import get_all_pro_keys
            keys = get_all_pro_keys()
            
            if not keys:
                text = (
                    "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                    "┃  ℹ️ <b>NO KEYS FOUND</b>     ┃\n"
                    "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                    "╭────────────────────────────╮\n"
                    "│\n"
                    "│ No pro keys have been\n"
                    "│ generated yet.\n"
                    "│\n"
                    "╰────────────────────────────╯"
                )
            else:
                text = (
                    "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                    "┃  📋 <b>ALL PRO KEYS</b>      ┃\n"
                    "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                )
                
                used_keys = [k for k in keys if k[1]]  # is_used = True
                unused_keys = [k for k in keys if not k[1]]
                
                if unused_keys:
                    text += f"╭─ ✅ <b>Active Keys</b> ({len(unused_keys)}) ──╮\n│\n"
                    for key, _, _, _ in unused_keys[:10]:
                        text += f"│ <code>{key}</code>\n"
                    if len(unused_keys) > 10:
                        text += f"│ ... and {len(unused_keys) - 10} more\n"
                    text += "│\n╰────────────────────────────╯\n\n"
                
                if used_keys:
                    text += f"╭─ 🔒 <b>Used Keys</b> ({len(used_keys)}) ────╮\n│\n"
                    for key, _, used_by, used_at in used_keys[:5]:
                        text += f"│ <code>{key[:8]}...</code>\n"
                        if used_by:
                            text += f"│ └─ by <code>{used_by}</code>\n│\n"
                    if len(used_keys) > 5:
                        text += f"│ ... and {len(used_keys) - 5} more\n"
                    text += "╰────────────────────────────╯"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="view_pro_keys"))
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_keys_menu"))
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}", show_alert=True)
    
    # Giveaway Handlers (moved from other_handlers.py)
    @bot.callback_query_handler(func=lambda call: call.data == "admin_pick_winner")
    def admin_pick_winner_handler(call):
        """Pick a random winner from all users"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
        
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, username FROM users ORDER BY RANDOM() LIMIT 1")
                winner = cursor.fetchone()
            
            if winner:
                winner_id, winner_name = winner
                text = (
                    "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                    "┃  🏆 <b>WINNER SELECTED!</b>  ┃\n"
                    "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                    "╭─ 🎉 <b>Congratulations!</b> ──╮\n"
                    "│\n"
                    f"│ <b>Winner:</b> {winner_name or 'Unknown'}\n"
                    f"│ <b>User ID:</b> <code>{winner_id}</code>\n"
                    "│\n"
                    "╰────────────────────────────╯\n\n"
                    "<i>💡 You can now send them a prize!</i>"
                )
            else:
                text = (
                    "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                    "┃  ℹ️ <b>NO USERS FOUND</b>    ┃\n"
                    "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                    "No users in database to pick from."
                )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Pick Another", callback_data="admin_pick_winner"))
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_keys_menu"))
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}", show_alert=True)
    
    @bot.callback_query_handler(func=lambda call: call.data == "admin_new_contest")
    def admin_new_contest_handler(call):
        """Start a new contest"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
        
        user_states[call.from_user.id] = "awaiting_contest_message"
        
        text = (
            "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "┃  🎪 <b>NEW CONTEST</b>       ┃\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            "╭─ 📝 <b>Instructions</b> ────────╮\n"
            "│\n"
            "│ Send the contest announcement\n"
            "│ message. It will be broadcast\n"
            "│ to all users.\n"
            "│\n"
            "│ <b>Include:</b>\n"
            "│ • Contest rules\n"
            "│ • Prizes\n"
            "│ • Deadline\n"
            "│\n"
            "╰────────────────────────────╯"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Cancel", callback_data="admin_keys_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    print("✅ Complete admin system registered")
    
    # ============================================================
    # OWNER ADMIN MANAGEMENT - Professional System
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "owner_admin_management")
    def owner_admin_management_handler(call):
        """Professional admin management system"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner access only!", show_alert=True)
            return
        
        # Get current admin counts
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM admins")
                global_count = c.fetchone()[0]
                c.execute("SELECT COUNT(DISTINCT user_id) FROM section_admins")
                section_count = c.fetchone()[0]
        except:
            global_count = 0
            section_count = 0
        
        text = (
            "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "┃  👥 <b>ADMIN MANAGEMENT</b>   ┃\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            "╭─ 📊 <b>Current Team Status</b> ────╮\n"
            "│\n"
            f"│ 🌟 <b>Global Admins:</b> {global_count}\n"
            "│    └─ Full system control\n"
            "│\n"
            f"│ ⚡ <b>Section Admins:</b> {section_count}\n"
            "│    └─ Section-specific access\n"
            "│\n"
            f"│ 👑 <b>Owner:</b> You\n"
            "│\n"
            "╰────────────────────────────╯\n\n"
            "<b>⚙️ Management Actions:</b>"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        # Global Admins Section
        markup.add(types.InlineKeyboardButton("═══ 🌟 GLOBAL ADMINS ═══", callback_data="noop_admin"))
        markup.add(
            types.InlineKeyboardButton("➕ Add Global Admin", callback_data="add_global_admin"),
            types.InlineKeyboardButton("➖ Remove Global Admin", callback_data="remove_global_admin")
        )
        
        # Section Admins Section  
        markup.add(types.InlineKeyboardButton("═══ ⚡ SECTION ADMINS ═══", callback_data="noop_admin"))
        markup.add(
            types.InlineKeyboardButton("➕ Add Section Admin", callback_data="add_section_admin_start"),
            types.InlineKeyboardButton("➖ Remove Section Admin", callback_data="remove_section_admin_start")
        )
        
        # Overview Section
        markup.add(types.InlineKeyboardButton("═══ 📊 OVERVIEW ═══", callback_data="noop_admin"))
        markup.add(
            types.InlineKeyboardButton("📋 View All Admins", callback_data="view_all_admins")
        )
        markup.add(
            types.InlineKeyboardButton("📈 Admin Statistics", callback_data="admin_activity_stats")
        )
        
        # Back to owner panel
        markup.add(types.InlineKeyboardButton("⬅️ Back to Owner Panel", callback_data="owner_panel"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    # ADD GLOBAL ADMIN
    @bot.callback_query_handler(func=lambda call: call.data == "add_global_admin")
    def add_global_admin_handler(call):
        """Initiate adding a global admin"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
        
        text = (
            "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "┃  ➕ <b>ADD GLOBAL ADMIN</b>   ┃\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            "╭─ 🌟 <b>Permissions Granted</b> ────╮\n"
            "│\n"
            "│ ✅ User Management\n"
            "│ ✅ All Products & Categories\n"
            "│ ✅ Order Processing\n"
            "│ ✅ Payment Approval\n"
            "│ ✅ Support Dashboard\n"
            "│ ✅ Analytics & Reports\n"
            "│ ✅ Broadcast Messages\n"
            "│\n"
            "╰────────────────────────────╯\n\n"
            "╭─ 📝 <b>How to Add</b> ─────────╮\n"
            "│\n"
            "│ Send the User ID of the person\n"
            "│ you want to promote to Global Admin\n"
            "│\n"
            "│ <i>💡 Example: 123456789</i>\n"
            "│\n"
            "╰────────────────────────────╯"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="owner_admin_management"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
        user_states[call.from_user.id] = "waiting_add_global_admin"
    
    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "waiting_add_global_admin")
    def process_add_global_admin(message):
        """Process adding a global admin"""
        if message.from_user.id != ADMIN_ID:
            return
        
        try:
            new_admin_id = int(message.text.strip())
            
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (new_admin_id,))
                if c.fetchone():
                    bot.send_message(message.chat.id, 
                                   "⚠️ Already a global admin!",
                                   reply_markup=types.InlineKeyboardMarkup().add(
                                       types.InlineKeyboardButton("⬅️ Back", callback_data="owner_admin_management")
                                   ))
                    user_states.pop(message.from_user.id, None)
                    return
                
                c.execute("INSERT INTO admins (user_id, added_by, added_at) VALUES (?, ?, ?)",
                         (new_admin_id, ADMIN_ID, datetime.now().isoformat()))
                conn.commit()
            
            success_text = (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃  ✅ <b>ADMIN ADDED!</b>       ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "╭─ 👤 <b>Admin Details</b> ──────╮\n"
                "│\n"
                f"│ <b>User ID:</b> <code>{new_admin_id}</code>\n"
                f"│ <b>Role:</b> 🌟 Global Admin\n"
                f"│ <b>Added:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                "│ <b>Status:</b> ✅ Active\n"
                "│\n"
                "╰────────────────────────────╯\n\n"
                "🎉 <i>They now have full admin access!</i>"
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_admin_management"))
            
            bot.send_message(message.chat.id, success_text, reply_markup=markup, parse_mode="HTML")
            
            try:
                bot.send_message(new_admin_id,
                               "🎉 <b>Promoted to Global Admin!</b>\n\nUse /admin to access the panel.",
                               parse_mode="HTML")
            except:
                pass
            
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid User ID!")
            return
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {str(e)}")
        
        user_states.pop(message.from_user.id, None)
    
    # REMOVE GLOBAL ADMIN
    @bot.callback_query_handler(func=lambda call: call.data == "remove_global_admin")
    def remove_global_admin_handler(call):
        """Show list of global admins to remove"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
        
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT user_id FROM admins")
                admins = c.fetchall()
        except:
            admins = []
        
        if not admins:
            text = (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃  ℹ️ <b>NO ADMINS FOUND</b>   ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "╭────────────────────────────╮\n"
                "│\n"
                "│ There are currently no\n"
                "│ global admins to remove.\n"
                "│\n"
                "╰────────────────────────────╯"
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_admin_management"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                reply_markup=markup, parse_mode="HTML")
            return
        
        text = (
            "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "┃  ➖ <b>REMOVE GLOBAL ADMIN</b> ┃\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            "╭─ 👥 <b>Current Admins</b> ─────╮\n"
            f"│ Total: <b>{len(admins)}</b> admin(s)\n"
            "╰────────────────────────────╯\n\n"
            "<b>Select an admin to demote:</b>"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        for (admin_id,) in admins:
            markup.add(types.InlineKeyboardButton(
                f"👤 {admin_id}",
                callback_data=f"confirm_remove_admin_{admin_id}"
            ))
        
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_admin_management"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_remove_admin_"))
    def confirm_remove_admin_handler(call):
        """Confirm removal of global admin"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
        
        admin_id = int(call.data.split("_")[-1])
        
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("DELETE FROM admins WHERE user_id = ?", (admin_id,))
                conn.commit()
            
            success_text = (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃  ✅ <b>ADMIN REMOVED!</b>     ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "╭─ 👤 <b>Removed Admin</b> ──────╮\n"
                "│\n"
                f"│ <b>User ID:</b> <code>{admin_id}</code>\n"
                "│ <b>Previous Role:</b> 🌟 Global Admin\n"
                "│ <b>Status:</b> ⬇️ Demoted\n"
                f"│ <b>Removed:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                "│\n"
                "╰────────────────────────────╯"
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_admin_management"))
            
            bot.edit_message_text(success_text, call.message.chat.id, call.message.message_id,
                                reply_markup=markup, parse_mode="HTML")
            
            try:
                bot.send_message(admin_id, "ℹ️ Removed from Global Admin role.", parse_mode="HTML")
            except:
                pass
                
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}", show_alert=True)
    
    # VIEW ALL ADMINS
    @bot.callback_query_handler(func=lambda call: call.data == "view_all_admins")
    def view_all_admins_handler(call):
        """Display all admins"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
        
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT user_id FROM admins")
                global_admins = c.fetchall()
                c.execute("SELECT user_id, section FROM section_admins")
                section_admins_raw = c.fetchall()
        except:
            global_admins = []
            section_admins_raw = []
        
        # Group section admins
        section_admins = {}
        for user_id, section in section_admins_raw:
            if user_id not in section_admins:
                section_admins[user_id] = []
            section_admins[user_id].append(section)
        
        text = (
            "╔════════════════════════╗\n"
            "║  📋 𝗔𝗟𝗟 𝗔𝗗𝗠𝗜𝗡𝗦  ║\n"
            "╚════════════════════════╝\n\n"
        )
        
        text += f"🌟 <b>Global Admins ({len(global_admins)}):</b>\n"
        if global_admins:
            for (user_id,) in global_admins:
                text += f"• <code>{user_id}</code>\n"
        else:
            text += "<i>None</i>\n"
        
        text += f"\n⚡ <b>Section Admins ({len(section_admins)}):</b>\n"
        if section_admins:
            for user_id, sections in section_admins.items():
                text += f"• <code>{user_id}</code> - {', '.join(sections)}\n"
        else:
            text += "<i>None</i>\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="view_all_admins"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_admin_management"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    # ADMIN STATS
    @bot.callback_query_handler(func=lambda call: call.data == "admin_activity_stats")
    def admin_activity_stats_handler(call):
        """Show admin statistics"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
        
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM admins")
                global_count = c.fetchone()[0]
                c.execute("SELECT COUNT(DISTINCT user_id) FROM section_admins")
                section_count = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM users")
                total_users = c.fetchone()[0]
        except:
            global_count = section_count = total_users = 0
        
        text = (
            "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "┃  📊 <b>ADMIN STATISTICS</b>   ┃\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            "╭─ 👥 <b>Team Overview</b> ──────╮\n"
            "│\n"
            f"│ 🌟 <b>Global Admins:</b> {global_count}\n"
            f"│ ⚡ <b>Section Admins:</b> {section_count}\n"
            "│ 👑 <b>Owner:</b> 1 (You)\n"
            f"│ 📊 <b>Total Staff:</b> {global_count + section_count + 1}\n"
            "│\n"
            "╰────────────────────────────╯\n\n"
            "╭─ 📈 <b>Bot Statistics</b> ─────╮\n"
            "│\n"
            f"│ 👤 <b>Total Users:</b> {total_users}\n"
            f"│ 📊 <b>Users per Admin:</b> {total_users // max(1, global_count + section_count + 1)}\n"
            "│\n"
            "╰────────────────────────────╯\n\n"
            "╭─ ✅ <b>System Status</b> ──────╮\n"
            "│\n"
            "│ • Support: <b>✅ Active</b>\n"
            "│ • Monitoring: <b>🟢 Running</b>\n"
            "│ • Security: <b>🔒 Protected</b>\n"
            "│\n"
            "╰────────────────────────────╯"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="admin_activity_stats"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_admin_management"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    # MAIN MENU HANDLER
    @bot.callback_query_handler(func=lambda call: call.data == "main_menu")
    def main_menu_handler(call):
        """Return to main menu"""
        from helpers import send_main_menu, get_welcome_message
        send_main_menu(bot, call.message.chat.id, get_welcome_message(), call.message.message_id)
    
    # ============================================================
    # SECTION ADMIN SYSTEM - Professional Permission Management
    # ============================================================
    
    # Available sections with display names
    AVAILABLE_SECTIONS = {
        "cc_shop": "💳 CC Shop",
        "bins_methods": "💎 BINs & Methods",
        "dumps_live": "📄 Live Dumps",
        "dumps_charged": "⚡ Charged Dumps",
        "rdp": "🖥️ RDP",
        "accounts": "📦 Accounts",
        "gift_cards": "🎁 Gift Cards"
    }
    
    @bot.callback_query_handler(func=lambda call: call.data == "add_section_admin_start")
    def add_section_admin_start_handler(call):
        """Start section admin creation process"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
        
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "    ➕ <b>ADD SECTION ADMIN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>⚡ Section Admin Permissions:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ Manage assigned sections only\n"
            "✅ Add/edit/delete products\n"
            "✅ View section orders\n"
            "✅ Limited system access\n"
            "❌ No user management\n"
            "❌ No global control\n\n"
            "<b>📝 Step 1:</b>\n"
            "Send the User ID to promote\n\n"
            "<i>💡 Example: 987654321</i>"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="owner_admin_management"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
        user_states[call.from_user.id] = "waiting_section_admin_id"
    
    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "waiting_section_admin_id")
    def process_section_admin_id(message):
        """Process section admin ID and show section selection"""
        if message.from_user.id != ADMIN_ID:
            return
        
        try:
            new_admin_id = int(message.text.strip())
            
            # Store the ID temporarily
            if not hasattr(bot, 'temp_section_admin_data'):
                bot.temp_section_admin_data = {}
            bot.temp_section_admin_data[message.from_user.id] = new_admin_id
            
            # Show section selection
            text = (
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "    📋 <b>SELECT SECTIONS</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 User ID: <code>{new_admin_id}</code>\n\n"
                "<b>Available Sections:</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "Select which sections this admin\n"
                "can manage:\n\n"
                "<i>💡 You can assign multiple sections</i>"
            )
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            
            # Add section buttons
            for section_key, section_name in AVAILABLE_SECTIONS.items():
                markup.add(
                    types.InlineKeyboardButton(
                        section_name,
                        callback_data=f"assign_section_{section_key}"
                    )
                )
            
            # View assigned and finish
            markup.add(
                types.InlineKeyboardButton("📋 View Assigned", callback_data="view_assigned_sections"),
                types.InlineKeyboardButton("✅ Finish", callback_data="finish_section_admin")
            )
            markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="owner_admin_management"))
            
            bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")
            user_states[message.from_user.id] = "assigning_sections"
            
            # Initialize assigned sections list
            if not hasattr(bot, 'temp_assigned_sections'):
                bot.temp_assigned_sections = {}
            bot.temp_assigned_sections[message.from_user.id] = []
            
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid User ID! Please send a number.")
            return
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {str(e)}")
            user_states.pop(message.from_user.id, None)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("assign_section_"))
    def assign_section_handler(call):
        """Assign a section to the new admin"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
        
        section_key = call.data.replace("assign_section_", "")
        
        # Get or initialize assigned sections
        if not hasattr(bot, 'temp_assigned_sections'):
            bot.temp_assigned_sections = {}
        if call.from_user.id not in bot.temp_assigned_sections:
            bot.temp_assigned_sections[call.from_user.id] = []
        
        assigned = bot.temp_assigned_sections[call.from_user.id]
        
        # Toggle section
        if section_key in assigned:
            assigned.remove(section_key)
            bot.answer_callback_query(call.id, f"❌ Removed {AVAILABLE_SECTIONS[section_key]}")
        else:
            assigned.append(section_key)
            bot.answer_callback_query(call.id, f"✅ Added {AVAILABLE_SECTIONS[section_key]}")
        
        # Update the message to show checkmarks
        admin_id = bot.temp_section_admin_data.get(call.from_user.id, 0)
        
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "    📋 <b>SELECT SECTIONS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 User ID: <code>{admin_id}</code>\n\n"
            f"<b>Assigned: {len(assigned)} section(s)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Click sections to assign/unassign:\n\n"
            "<i>💡 Selected sections marked with ✅</i>"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # Add section buttons with checkmarks
        for section_key, section_name in AVAILABLE_SECTIONS.items():
            checkmark = "✅ " if section_key in assigned else ""
            markup.add(
                types.InlineKeyboardButton(
                    f"{checkmark}{section_name}",
                    callback_data=f"assign_section_{section_key}"
                )
            )
        
        markup.add(
            types.InlineKeyboardButton("📋 View Summary", callback_data="view_assigned_sections"),
            types.InlineKeyboardButton("✅ Finish Setup", callback_data="finish_section_admin")
        )
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="owner_admin_management"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data == "view_assigned_sections")
    def view_assigned_sections_handler(call):
        """Show summary of assigned sections"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
        
        admin_id = bot.temp_section_admin_data.get(call.from_user.id, 0)
        assigned = bot.temp_assigned_sections.get(call.from_user.id, [])
        
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "    📋 <b>ASSIGNMENT SUMMARY</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 Admin ID: <code>{admin_id}</code>\n"
            f"📊 Sections: <code>{len(assigned)}</code>\n\n"
            "<b>Assigned Sections:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        
        if assigned:
            for section in assigned:
                text += f"✅ {AVAILABLE_SECTIONS.get(section, section)}\n"
        else:
            text += "<i>No sections assigned yet</i>\n"
        
        text += "\n<i>💡 Click Finish to save or go back to modify</i>"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("⬅️ Back to Selection", callback_data="back_to_section_selection"),
            types.InlineKeyboardButton("✅ Finish Setup", callback_data="finish_section_admin")
        )
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="owner_admin_management"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data == "back_to_section_selection")
    def back_to_section_selection_handler(call):
        """Go back to section selection"""
        if not is_owner(call.from_user.id):
            return
        
        admin_id = bot.temp_section_admin_data.get(call.from_user.id, 0)
        assigned = bot.temp_assigned_sections.get(call.from_user.id, [])
        
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "    📋 <b>SELECT SECTIONS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 User ID: <code>{admin_id}</code>\n\n"
            f"<b>Assigned: {len(assigned)} section(s)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Click sections to assign/unassign:\n\n"
            "<i>💡 Selected sections marked with ✅</i>"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        for section_key, section_name in AVAILABLE_SECTIONS.items():
            checkmark = "✅ " if section_key in assigned else ""
            markup.add(
                types.InlineKeyboardButton(
                    f"{checkmark}{section_name}",
                    callback_data=f"assign_section_{section_key}"
                )
            )
        
        markup.add(
            types.InlineKeyboardButton("📋 View Summary", callback_data="view_assigned_sections"),
            types.InlineKeyboardButton("✅ Finish Setup", callback_data="finish_section_admin")
        )
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="owner_admin_management"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data == "finish_section_admin")
    def finish_section_admin_handler(call):
        """Finalize section admin creation"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
        
        admin_id = bot.temp_section_admin_data.get(call.from_user.id, 0)
        assigned = bot.temp_assigned_sections.get(call.from_user.id, [])
        
        if not assigned:
            bot.answer_callback_query(call.id, "⚠️ Please assign at least one section!", show_alert=True)
            return
        
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                
                # Insert each section assignment
                for section in assigned:
                    c.execute(
                        "INSERT INTO section_admins (user_id, section, added_by, added_at) VALUES (?, ?, ?, ?)",
                        (admin_id, section, ADMIN_ID, datetime.now().isoformat())
                    )
                conn.commit()
            
            sections_list = "\n".join([f"✅ {AVAILABLE_SECTIONS.get(s, s)}" for s in assigned])
            
            success_text = (
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "    ✅ <b>ADMIN CREATED!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 User ID: <code>{admin_id}</code>\n"
                f"⚡ Role: <b>Section Admin</b>\n"
                f"📊 Sections: <code>{len(assigned)}</code>\n\n"
                "<b>Assigned Sections:</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{sections_list}\n\n"
                f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                "<i>✨ Setup complete!</i>"
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Admin Management", callback_data="owner_admin_management"))
            
            bot.edit_message_text(success_text, call.message.chat.id, call.message.message_id,
                                reply_markup=markup, parse_mode="HTML")
            
            # Notify the new admin
            try:
                bot.send_message(admin_id,
                               f"🎉 <b>You're now a Section Admin!</b>\n\n"
                               f"You can manage these sections:\n{sections_list}\n\n"
                               f"Use /admin to access your panel.",
                               parse_mode="HTML")
            except:
                pass
            
            # Cleanup
            user_states.pop(call.from_user.id, None)
            bot.temp_section_admin_data.pop(call.from_user.id, None)
            bot.temp_assigned_sections.pop(call.from_user.id, None)
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}", show_alert=True)
    
    @bot.callback_query_handler(func=lambda call: call.data == "remove_section_admin_start")
    def remove_section_admin_start_handler(call):
        """Show list of section admins to remove"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
        
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT DISTINCT user_id FROM section_admins")
                admins = c.fetchall()
        except:
            admins = []
        
        if not admins:
            text = (
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "    ℹ️ <b>NO SECTION ADMINS</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "There are no section admins to remove."
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_admin_management"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                reply_markup=markup, parse_mode="HTML")
            return
        
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "    ➖ <b>REMOVE SECTION ADMIN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Total: {len(admins)} admin(s)</b>\n\n"
            "Select an admin to view/remove:"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        for (admin_id,) in admins:
            # Get sections for this admin
            try:
                with sqlite3.connect(DB_NAME) as conn:
                    c = conn.cursor()
                    c.execute("SELECT section FROM section_admins WHERE user_id = ?", (admin_id,))
                    sections = [row[0] for row in c.fetchall()]
                    sections_text = f" ({len(sections)} sections)"
            except:
                sections_text = ""
            
            markup.add(types.InlineKeyboardButton(
                f"👤 {admin_id}{sections_text}",
                callback_data=f"confirm_remove_section_admin_{admin_id}"
            ))
        
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_admin_management"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_remove_section_admin_"))
    def confirm_remove_section_admin_handler(call):
        """Confirm removal of section admin"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
        
        admin_id = int(call.data.split("_")[-1])
        
        try:
            # Get sections before removal
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT section FROM section_admins WHERE user_id = ?", (admin_id,))
                sections = [row[0] for row in c.fetchall()]
                
                # Remove all sections for this admin
                c.execute("DELETE FROM section_admins WHERE user_id = ?", (admin_id,))
                conn.commit()
            
            sections_list = "\n".join([f"• {AVAILABLE_SECTIONS.get(s, s)}" for s in sections])
            
            success_text = (
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "    ✅ <b>ADMIN REMOVED!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 User ID: <code>{admin_id}</code>\n"
                f"⬇️ Removed from: <b>Section Admin</b>\n"
                f"📊 Sections: <code>{len(sections)}</code>\n\n"
                "<b>Removed Sections:</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{sections_list}\n\n"
                f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Admin Management", callback_data="owner_admin_management"))
            
            bot.edit_message_text(success_text, call.message.chat.id, call.message.message_id,
                                reply_markup=markup, parse_mode="HTML")
            
            # Notify the removed admin
            try:
                bot.send_message(admin_id,
                               "ℹ️ <b>Role Update</b>\n\n"
                               "You have been removed from the Section Admin role.",
                               parse_mode="HTML")
            except:
                pass
                
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}", show_alert=True)
    
    # ============================================================
    # SECTION STATUS MANAGER - Control availability of sections
    # ============================================================
    
    @bot.callback_query_handler(func=lambda call: call.data == "section_status_manager")
    def section_status_manager_handler(call):
        """Manage section availability status"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
        
        # Import section status functions
        try:
            from admin_meta_db import get_section_status, list_all_statuses
            statuses = list_all_statuses()
        except:
            statuses = {}
        
        # Section definitions
        sections_config = {
            "cc_shop": "💳 CC Shop",
            "bins_methods": "💎 BINs & Methods",
            "dumps_live": "📄 Live Dumps",
            "dumps_charged": "⚡ Charged Dumps",
            "rdp": "🖥️ RDP",
            "accounts": "📦 Accounts",
            "gift_cards": "🎁 Gift Cards",
            "hacks": "🔥 Hacks",
            "support": "💬 Support"
        }
        
        status_icons = {
            "available": "🟢",
            "maintenance": "🟡",
            "coming_soon": "🔵",
            "disabled": "🔴"
        }
        
        status_names = {
            "available": "Available",
            "maintenance": "Maintenance",
            "coming_soon": "Coming Soon",
            "disabled": "Disabled"
        }
        
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "    📊 <b>SECTION STATUS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Control Section Availability</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🟢 Available - Section is active\n"
            "🟡 Maintenance - Temporarily offline\n"
            "🔵 Coming Soon - Not yet available\n"
            "🔴 Disabled - Completely hidden\n\n"
            "<i>Click a section to change status:</i>"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        for key, label in sections_config.items():
            status = statuses.get(key, "available")
            icon = status_icons.get(status, "⚪")
            status_name = status_names.get(status, status)
            
            markup.add(types.InlineKeyboardButton(
                f"{label} {icon} {status_name}",
                callback_data=f"toggle_section_{key}"
            ))
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Owner Panel", callback_data="owner_panel"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("toggle_section_"))
    def toggle_section_handler(call):
        """Toggle section status"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
        
        section_key = call.data.replace("toggle_section_", "")
        
        # Import section status functions
        try:
            from admin_meta_db import get_section_status, set_section_status
        except:
            bot.answer_callback_query(call.id, "❌ Status system not available!", show_alert=True)
            return
        
        # Section display name
        sections_config = {
            "cc_shop": "💳 CC Shop",
            "bins_methods": "💎 BINs & Methods",
            "dumps_live": "📄 Live Dumps",
            "dumps_charged": "⚡ Charged Dumps",
            "rdp": "🖥️ RDP",
            "accounts": "📦 Accounts",
            "gift_cards": "🎁 Gift Cards",
            "hacks": "🔥 Hacks",
            "support": "💬 Support"
        }
        
        section_name = sections_config.get(section_key, section_key)
        
        # Get current status
        current_status = get_section_status(section_key)
        
        # Status cycle
        status_cycle = ["available", "maintenance", "coming_soon", "disabled"]
        try:
            current_index = status_cycle.index(current_status)
            next_index = (current_index + 1) % len(status_cycle)
            new_status = status_cycle[next_index]
        except:
            new_status = "available"
        
        # Set new status
        set_section_status(section_key, new_status)
        
        status_names = {
            "available": "🟢 Available",
            "maintenance": "🟡 Maintenance",
            "coming_soon": "🔵 Coming Soon",
            "disabled": "🔴 Disabled"
        }
        
        bot.answer_callback_query(
            call.id,
            f"{section_name}\n→ {status_names.get(new_status, new_status)}",
            show_alert=False
        )
        
        # Refresh the display
        section_status_manager_handler(call)
    
    # ============================================================
    # PLACEHOLDER HANDLERS FOR MISSING MENUS
    # ============================================================
    
    @bot.callback_query_handler(func=lambda call: call.data == "admin_analytics_menu")
    def admin_analytics_menu_handler(call):
        """Analytics and statistics menu"""
        if not is_global_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Admin access required!", show_alert=True)
            return
        
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM users")
                total_users = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM orders")
                total_orders = c.fetchone()[0]
                c.execute("SELECT SUM(price_usd) FROM orders WHERE payment_status = 'completed'")
                total_revenue = c.fetchone()[0] or 0
        except:
            total_users = total_orders = total_revenue = 0
        
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "    📈 <b>ANALYTICS DASHBOARD</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>📊 Key Metrics:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Total Users: <code>{total_users}</code>\n"
            f"📦 Total Orders: <code>{total_orders}</code>\n"
            f"💰 Total Revenue: <code>${total_revenue:.2f}</code>\n\n"
            f"<i>⚡ More analytics coming soon...</i>"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="admin_analytics_menu"))
        back_data = "owner_panel" if is_owner(call.from_user.id) else "admin_panel"
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=back_data))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data == "admin_payments_menu")
    def admin_payments_menu_handler(call):
        """Payment management menu"""
        if not is_global_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Admin access required!", show_alert=True)
            return
        
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "    💰 <b>PAYMENT MANAGEMENT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Payment Options:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• View pending payments\n"
            "• Approve deposits\n"
            "• Payment history\n"
            "• Configure methods\n\n"
            "<i>⚡ Feature in development...</i>"
        )
        
        markup = types.InlineKeyboardMarkup()
        back_data = "owner_panel" if is_owner(call.from_user.id) else "admin_panel"
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=back_data))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
    def admin_broadcast_handler(call):
        """Broadcast message to users"""
        if not is_global_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Admin access required!", show_alert=True)
            return
        
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "    📢 <b>BROADCAST SYSTEM</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Broadcast Options:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• Send to all users\n"
            "• Send to active users\n"
            "• Send to premium users\n"
            "• Schedule broadcasts\n\n"
            "<i>📝 Send your message to broadcast\n"
            "to all users...</i>\n\n"
            "<i>⚠️ Use responsibly!</i>"
        )
        
        markup = types.InlineKeyboardMarkup()
        back_data = "owner_panel" if is_owner(call.from_user.id) else "admin_panel"
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=back_data))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
        
        user_states[call.from_user.id] = "waiting_broadcast_message"
    
    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "waiting_broadcast_message")
    def process_broadcast_message(message):
        """Process broadcast message"""
        if not is_global_admin(message.from_user.id):
            return
        
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT user_id FROM users")
                users = c.fetchall()
            
            success = 0
            failed = 0
            
            for (user_id,) in users:
                try:
                    bot.send_message(user_id, f"📢 <b>Announcement:</b>\n\n{message.text}", parse_mode="HTML")
                    success += 1
                except:
                    failed += 1
            
            result_text = (
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "    ✅ <b>BROADCAST COMPLETE!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📊 Results:\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ Sent: <code>{success}</code>\n"
                f"❌ Failed: <code>{failed}</code>\n"
                f"📊 Total: <code>{success + failed}</code>"
            )
            
            markup = types.InlineKeyboardMarkup()
            back_data = "owner_panel" if is_owner(message.from_user.id) else "admin_panel"
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=back_data))
            
            bot.send_message(message.chat.id, result_text, reply_markup=markup, parse_mode="HTML")
            
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {str(e)}")
        
        user_states.pop(message.from_user.id, None)
    
    @bot.callback_query_handler(func=lambda call: call.data == "admin_support_dashboard")
    def admin_support_dashboard_handler(call):
        """Support dashboard for admins"""
        if not is_global_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Admin access required!", show_alert=True)
            return
        
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "    💬 <b>SUPPORT DASHBOARD</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Support Options:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• View open tickets\n"
            "• Respond to users\n"
            "• Support statistics\n"
            "• Chat history\n\n"
            "<i>⚡ Advanced support system\n"
            "coming soon...</i>"
        )
        
        markup = types.InlineKeyboardMarkup()
        back_data = "owner_panel" if is_owner(call.from_user.id) else "admin_panel"
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=back_data))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    # Noop handler for separator buttons
    @bot.callback_query_handler(func=lambda call: call.data == "noop_admin")
    def noop_admin_handler(call):
        """Handle clicks on separator buttons"""
        bot.answer_callback_query(call.id)
    
    # ============================================================
    # USER MANAGEMENT MENU
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "admin_users_menu")
    def admin_users_menu_handler(call):
        """User management menu"""
        if not is_global_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Admin access required!", show_alert=True)
            return
        
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM users")
                total_users = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM users WHERE credits > 0")
                active_users = c.fetchone()[0]
        except:
            total_users = active_users = 0
        
        text = (
            "╔════════════════════════╗\n"
            "      👥 <b>USER MANAGEMENT</b>\n"
            "╚════════════════════════╝\n\n"
            f"<b>📊 Overview</b>\n"
            f"├ 👤 Total Users: <code>{total_users}</code>\n"
            f"├ ✅ Active Users: <code>{active_users}</code>\n"
            f"└ 📈 Growth: Coming soon\n\n"
            "<i>💼 Manage your user base</i>"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🔍 Search User", callback_data="admin_search_user"),
            types.InlineKeyboardButton("📊 User Stats", callback_data="admin_user_stats")
        )
        markup.add(
            types.InlineKeyboardButton("💰 Add Credits", callback_data="admin_add_credits"),
            types.InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban_user")
        )
        
        back_data = "owner_panel" if is_owner(call.from_user.id) else "admin_panel"
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=back_data))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    # ============================================================
    # ORDERS MANAGEMENT MENU
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "admin_orders_menu")
    def admin_orders_menu_handler(call):
        """Orders management menu"""
        if not is_global_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Admin access required!", show_alert=True)
            return
        
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM orders")
                total_orders = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM orders WHERE payment_status = 'completed'")
                completed = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM orders WHERE payment_status = 'pending'")
                pending = c.fetchone()[0]
        except:
            total_orders = completed = pending = 0
        
        text = (
            "╔════════════════════════╗\n"
            "      📋 <b>ORDER MANAGEMENT</b>\n"
            "╚════════════════════════╝\n\n"
            f"<b>📊 Order Statistics</b>\n"
            f"├ 📦 Total: <code>{total_orders}</code>\n"
            f"├ ✅ Completed: <code>{completed}</code>\n"
            f"└ ⏳ Pending: <code>{pending}</code>\n\n"
            "<i>💼 Track and manage orders</i>"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📊 Recent Orders", callback_data="admin_recent_orders"),
            types.InlineKeyboardButton("🔍 Search Order", callback_data="admin_search_order")
        )
        
        back_data = "owner_panel" if is_owner(call.from_user.id) else "admin_panel"
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=back_data))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode="HTML")

# Export functions for use in other modules
__all__ = [
    'register_complete_admin_system',
    'is_owner',
    'is_global_admin',
    'get_section_admins',
    'has_admin_access'
]
