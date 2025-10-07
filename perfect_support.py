import json
import sqlite3
import time
from datetime import datetime, UTC, timedelta
import threading
from telebot import types
from config import DB_NAME, ADMIN_ID
from helpers import send_random_animation

# Support Categories
SUPPORT_CATEGORIES = {
    'payment': '💳 Payment Issues',
    'order': '📦 Order Problems', 
    'technical': '🔧 Technical Support',
    'account': '👤 Account Issues',
    'billing': '💰 Billing Questions',
    'general': '❓ General Questions'
}

# Priority Levels
PRIORITY_LEVELS = {
    1: '🟢 Low',
    2: '🟡 Medium', 
    3: '🟠 High',
    4: '🔴 Critical'
}

# Auto-responses for common issues
AUTO_RESPONSES = {
    'payment': {
        'keywords': ['payment', 'paid', 'transaction', 'crypto', 'bitcoin', 'approve', 'pending'],
        'response': ''''🤖 **Payment Support**

I see you're having payment-related issues. Here's what I can help with:

• **Payment Status**: All crypto payments are processed manually by our admins
• **Verification Time**: Usually 5-30 minutes after clicking "I Have Paid"
• **Requirements**: Must upload payment screenshot and include Payment ID in memo

**Common Solutions:**
✅ Ensure you uploaded a clear payment screenshot
✅ Check you included the Payment ID in transaction memo
✅ Wait for admin verification (they get notified automatically)

If your payment is still pending after 30 minutes, please continue with live chat below.'''
    },
    'order': {
        'keywords': ['order', 'delivery', 'received', 'item', 'product', 'download'],
        'response': ''''🤖 **Order Support**

I can help with order-related questions:

• **Order Status**: Check your order history in Personal Area
• **Delivery**: Most items are delivered instantly after payment approval
• **Missing Items**: Items are sent automatically once payment is confirmed

**Common Solutions:**
✅ Check your Personal Area → Order History
✅ Verify payment was approved (you'll get a confirmation message)
✅ Look for delivery messages in this chat

If you still can't find your order, please continue with live chat.'''
    },
    'technical': {
        'keywords': ['error', 'bug', 'broken', 'not working', 'issue', 'problem', 'crash'],
        'response': ''''🤖 **Technical Support**

I can help troubleshoot technical issues:

**Common Solutions:**
✅ Restart the bot with /start command
✅ Clear your browser cache if using web Telegram
✅ Check your internet connection
✅ Try using a different device/app

**If problems persist:**
• Screenshot the error
• Note what you were doing when it happened
• Continue with live chat for personalized help'''
    },
    'account': {
        'keywords': ['account', 'login', 'username', 'profile', 'banned', 'suspended'],
        'response': ''''🤖 **Account Support**

Account-related assistance:

• **Account Status**: Active accounts can access all features
• **Referral Code**: Found in Personal Area
• **Credits**: Check balance in Personal Area

**Common Issues:**
✅ Use /start to refresh your account
✅ Check if you're banned (you'll see a message)
✅ Verify you joined all required channels

For account restrictions or bans, please use live chat.'''
    }
}

# -------------------------------
# Global Settings & Template Helpers
# -------------------------------
SETTINGS_FILE = "support_settings.json"
TEMPLATES_FILE = "support_templates.json"

def load_support_settings():
    defaults = {
        "auto_assign": False,
        "notify_all_admins": True,
        "auto_close_hours": 72
    }
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            defaults.update(data or {})
    except Exception:
        pass
    return defaults

def save_support_settings(data):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Could not save support settings: {e}")

def load_chat_templates():
    try:
        with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def save_chat_templates(templates):
    try:
        with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(templates, f, indent=2)
    except Exception as e:
        print(f"Could not save templates: {e}")

def get_support_analytics(admin_id=None, days=7):
    """Get support analytics for dashboard"""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        
        # Basic stats
        c.execute("SELECT COUNT(*) FROM support_sessions WHERE datetime(started_at) > datetime('now', '-{} days')".format(days))
        total_sessions = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM support_tickets WHERE datetime(created_at) > datetime('now', '-{} days')".format(days))
        total_tickets = c.fetchone()[0]
        
        # Average response time
        c.execute("SELECT AVG(first_response_time) FROM support_sessions WHERE first_response_time IS NOT NULL AND datetime(started_at) > datetime('now', '-{} days')".format(days))
        avg_response = c.fetchone()[0] or 0
        
        # Satisfaction rating
        c.execute("SELECT AVG(CAST(user_rating as FLOAT)) FROM support_sessions WHERE user_rating IS NOT NULL AND datetime(started_at) > datetime('now', '-{} days')".format(days))
        satisfaction = c.fetchone()[0] or 0
        
        # Active sessions
        c.execute("SELECT COUNT(*) FROM support_sessions WHERE status IN ('open', 'assigned')")
        active_sessions = c.fetchone()[0]
        
        # Most common categories
        c.execute("SELECT category, COUNT(*) as count FROM support_sessions WHERE datetime(started_at) > datetime('now', '-{} days') GROUP BY category ORDER BY count DESC LIMIT 3".format(days))
        top_categories = c.fetchall()
        
        return {
            'total_sessions': total_sessions,
            'total_tickets': total_tickets,
            'avg_response_time': int(avg_response),
            'satisfaction_score': round(satisfaction, 2),
            'active_sessions': active_sessions,
            'top_categories': top_categories
        }

def create_support_message(session_id, sender_id, sender_type, message_text, message_type='text', file_id=None):
    """Create a support message record"""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO support_messages 
            (session_id, sender_id, sender_type, message_text, message_type, file_id, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (session_id, sender_id, sender_type, message_text, message_type, file_id, datetime.now(UTC).isoformat()))
        
        # Update session last message time
        c.execute("UPDATE support_sessions SET last_message_at = ?, updated_at = ? WHERE session_id = ?", 
                 (datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat(), session_id))
        conn.commit()

def get_chat_history(session_id, limit=50):
    """Get chat history for a support session"""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT sender_id, sender_type, message_text, message_type, file_id, timestamp 
            FROM support_messages 
            WHERE session_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (session_id, limit))
        return c.fetchall()

def auto_respond(message_text):
    """Check if message matches any auto-response patterns"""
    message_lower = message_text.lower()
    
    for category, data in AUTO_RESPONSES.items():
        if any(keyword in message_lower for keyword in data['keywords']):
            return data['response']
    
    return None

def register_perfect_support_handlers(bot):
    """Register enhanced support system handlers"""
    
    # Enhanced support menu
    @bot.callback_query_handler(func=lambda call: call.data == "support")
    def enhanced_support_menu(call):
        """Enhanced support menu with better options"""
        text = (
            "🎯 **Advanced Support Center**\n\n"
            "Welcome to our enhanced support system! Choose how you'd like to get help:\n\n"
            "🤖 **AI Assistant**: Get instant answers\n"
            "💬 **Live Chat**: Talk to human support\n"
            "🎫 **Support Ticket**: Create formal request\n"
            "📊 **Support History**: View past conversations"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🤖 AI Support Assistant", callback_data="support_ai"),
            types.InlineKeyboardButton("💬 Start Live Chat", callback_data="support_chat_new"),
            types.InlineKeyboardButton("🎫 Create Support Ticket", callback_data="support_ticket_new"),
            types.InlineKeyboardButton("📊 My Support History", callback_data="support_history")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="Markdown")

    # AI Support Assistant
    @bot.callback_query_handler(func=lambda call: call.data == "support_ai")
    def ai_support_assistant(call):
        """Enhanced AI support with category selection"""
        text = (
            "🤖 **AI Support Assistant**\n\n"
            "I can provide instant help with common issues. Select your issue category or describe your problem:"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        for key, name in SUPPORT_CATEGORIES.items():
            markup.add(types.InlineKeyboardButton(name, callback_data=f"ai_category_{key}"))
        
        markup.add(types.InlineKeyboardButton("✍️ Describe My Issue", callback_data="ai_custom"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="support"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="Markdown")

    # Handle AI category selection
    @bot.callback_query_handler(func=lambda call: call.data.startswith("ai_category_"))
    def handle_ai_category(call):
        category = call.data.split('_')[2]
        
        if category in AUTO_RESPONSES:
            response = AUTO_RESPONSES[category]['response']
        else:
            response = f"🤖 **{SUPPORT_CATEGORIES.get(category, 'Support')}**\n\nI can help with {category} related questions. Please describe your specific issue and I'll do my best to assist you."
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("💬 Need Human Support", callback_data="support_chat_new"),
            types.InlineKeyboardButton("🎫 Create Ticket", callback_data="support_ticket_new"),
            types.InlineKeyboardButton("⬅️ Back to Support", callback_data="support")
        )
        
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="Markdown")

    # Enhanced Live Chat
    @bot.callback_query_handler(func=lambda call: call.data == "support_chat_new")
    def start_enhanced_chat(call):
        """Start enhanced live chat with category selection"""
        text = (
            "💬 **Live Chat Setup**\n\n"
            "Please select the category that best describes your issue. This helps us route you to the right specialist:"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        for key, name in SUPPORT_CATEGORIES.items():
            markup.add(types.InlineKeyboardButton(name, callback_data=f"chat_cat_{key}"))
        
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="support"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="Markdown")

    # Handle chat category selection and start chat
    @bot.callback_query_handler(func=lambda call: call.data.startswith("chat_cat_"))
    def start_categorized_chat(call):
        category = call.data.split('_')[2]
        user_id = call.from_user.id
        
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            
            # Check for existing open session
            c.execute("SELECT session_id FROM support_sessions WHERE user_id = ? AND status IN ('open','assigned') ORDER BY session_id DESC LIMIT 1", (user_id,))
            existing = c.fetchone()
            
            if existing:
                session_id = existing[0]
            else:
                # Create new session with category
                c.execute("INSERT INTO support_sessions (user_id, status, category, subject) VALUES (?, 'open', ?, ?)", 
                         (user_id, category, f"{SUPPORT_CATEGORIES[category]} - {call.from_user.first_name}"))
                session_id = c.lastrowid
                conn.commit()
                
                # Send initial auto-response if available
                if category in AUTO_RESPONSES:
                    auto_response = AUTO_RESPONSES[category]['response']
                    create_support_message(session_id, 0, 'system', auto_response, 'auto_response')
                    bot.send_message(user_id, f"🤖 **Quick Help**\n\n{auto_response}", parse_mode="Markdown")

                # Auto-assign if setting enabled
                try:
                    settings = load_support_settings()
                    if settings.get('auto_assign'):
                        _auto_assign_session(bot, session_id, category)
                except Exception as e:
                    print(f"Auto-assign failed: {e}")
        
        # Set user state for chat
        if not hasattr(bot, '_user_states'):
            bot._user_states = {}
        bot._user_states[user_id] = f"support_chat_user_{session_id}"
        
        text = (
            f"💬 **Live Chat Started**\n"
            f"**Category**: {SUPPORT_CATEGORIES[category]}\n"
            f"**Session ID**: #{session_id}\n\n"
            f"An admin will be notified. You can start typing your message now."
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔚 End Chat", callback_data=f"support_end_{session_id}"))
        markup.add(types.InlineKeyboardButton("📊 Chat Info", callback_data=f"chat_info_{session_id}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="Markdown")
        
        # Notify admins
        notify_admins_new_chat(bot, session_id, user_id, category, call.from_user.first_name)

    # Support History
    @bot.callback_query_handler(func=lambda call: call.data == "support_history")
    def show_support_history(call):
        """Show user's support history"""
        user_id = call.from_user.id
        
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT session_id, category, status, started_at, ended_at, user_rating
                FROM support_sessions 
                WHERE user_id = ? 
                ORDER BY started_at DESC 
                LIMIT 10
            """, (user_id,))
            sessions = c.fetchall()
            
            c.execute("SELECT COUNT(*) FROM support_sessions WHERE user_id = ?", (user_id,))
            total_sessions = c.fetchone()[0]
        
        if not sessions:
            text = "📊 **Support History**\n\nYou haven't had any support sessions yet."
        else:
            text = f"📊 **Support History** (Last 10 of {total_sessions})\n\n"
            
            for session in sessions:
                session_id, category, status, started, ended, rating = session
                status_icon = "✅" if status == "closed" else "🟡" if status == "assigned" else "🔴"
                category_name = SUPPORT_CATEGORIES.get(category, category)
                
                rating_text = f" ⭐{rating}" if rating else ""
                text += f"{status_icon} **#{session_id}** - {category_name}{rating_text}\n"
                text += f"   Started: {started[:16]}\n"
                if ended:
                    text += f"   Ended: {ended[:16]}\n"
                text += "\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Support", callback_data="support"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="Markdown")

    # Admin Support Dashboard
    @bot.callback_query_handler(func=lambda call: call.data == "admin_support_dashboard")
    def admin_support_dashboard(call):
        """Enhanced admin support dashboard"""
        if call.from_user.id != ADMIN_ID:
            # Check if user is admin
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if not c.fetchone():
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return
        
        stats = get_support_analytics()
        
        text = (
            "🎯 **Support Dashboard**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 **Today's Stats**\n"
            f"• Active Chats: **{stats['active_sessions']}**\n"
            f"• Total Sessions (7d): **{stats['total_sessions']}**\n"
            f"• Avg Response: **{stats['avg_response_time']}s**\n"
            f"• Satisfaction: **{stats['satisfaction_score']}/5** ⭐\n\n"
        )
        
        if stats['top_categories']:
            text += "🔥 **Top Issues**\n"
            for cat, count in stats['top_categories'][:3]:
                text += f"• {SUPPORT_CATEGORIES.get(cat, cat)}: {count}\n"
            text += "\n"
        
        text += "Choose an action:"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton(f"💬 Active Chats ({stats['active_sessions']})", callback_data="admin_active_chats"),
            types.InlineKeyboardButton("📊 Full Analytics", callback_data="admin_support_analytics")
        )
        markup.add(
            types.InlineKeyboardButton("🎫 Pending Tickets", callback_data="admin_pending_tickets"),
            types.InlineKeyboardButton("👥 Support Agents", callback_data="admin_support_agents")
        )
        markup.add(
            types.InlineKeyboardButton("⚙️ Support Settings", callback_data="admin_support_settings"),
            types.InlineKeyboardButton("📝 Chat Templates", callback_data="admin_chat_templates")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="Markdown")

    # Active Chats Management
    @bot.callback_query_handler(func=lambda call: call.data == "admin_active_chats")
    def show_active_chats(call):
        """Show active support chats"""
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT s.session_id, s.user_id, s.category, s.started_at, s.admin_id, u.username
                FROM support_sessions s
                LEFT JOIN users u ON s.user_id = u.user_id
                WHERE s.status IN ('open', 'assigned')
                ORDER BY s.started_at ASC
            """)
            active_chats = c.fetchall()
        
        if not active_chats:
            text = "💬 **Active Chats**\n\nNo active support chats at the moment."
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_support_dashboard"))
        else:
            text = f"💬 **Active Chats** ({len(active_chats)})\n\n"
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            for chat in active_chats[:10]:  # Show max 10
                session_id, user_id, category, started, admin_id, username = chat
                status = "🟡 Assigned" if admin_id else "🔴 Waiting"
                category_name = SUPPORT_CATEGORIES.get(category, category)
                username_text = f"@{username}" if username else f"ID:{user_id}"
                
                elapsed = int((datetime.now(UTC) - datetime.fromisoformat(started.replace('Z', '+00:00'))).total_seconds() / 60)
                
                button_text = f"{status} #{session_id} - {username_text} ({category_name}) - {elapsed}m"
                markup.add(types.InlineKeyboardButton(button_text, callback_data=f"admin_chat_{session_id}"))
            
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_support_dashboard"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="Markdown")

    # =============================
    # Additional Admin Ticket & Settings Functionality
    # =============================


    # -------- Auto Assign & Auto Close Helpers --------
    def _auto_assign_session(bot_obj, session_id, category):
        """Assign a session to the least-loaded admin if unassigned."""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT admin_id FROM support_sessions WHERE session_id=?", (session_id,))
                row = c.fetchone()
                if not row or row[0]:
                    return  # Already assigned or missing
                # Get admins load
                c.execute(
                    """
                    SELECT a.user_id, COUNT(s.session_id) as load
                    FROM admins a
                    LEFT JOIN support_sessions s ON s.admin_id = a.user_id AND s.status IN ('open','assigned','in_progress')
                    GROUP BY a.user_id
                    ORDER BY load ASC, a.user_id ASC
                    LIMIT 1
                    """
                )
                target = c.fetchone()
                if not target:
                    return
                target_admin = target[0]
                c.execute("UPDATE support_sessions SET admin_id=?, status='assigned', updated_at=CURRENT_TIMESTAMP WHERE session_id=? AND (admin_id IS NULL)", (target_admin, session_id))
                conn.commit()
            # Notify admin & user
            try:
                bot_obj.send_message(target_admin, f"🤖 Auto-assigned to support chat #{session_id} (Category: {SUPPORT_CATEGORIES.get(category, category)})")
            except Exception:
                pass
            try:
                with sqlite3.connect(DB_NAME) as conn:
                    c = conn.cursor(); c.execute("SELECT user_id FROM support_sessions WHERE session_id=?", (session_id,)); urow = c.fetchone()
                if urow:
                    bot_obj.send_message(urow[0], "🟢 A support admin has been automatically assigned to your chat.")
            except Exception:
                pass
        except Exception as e:
            print(f"_auto_assign_session error: {e}")

    def _auto_close_worker():
        """Periodic worker to auto-close stale chats based on settings."""
        while True:
            try:
                settings = load_support_settings()
                hours = int(settings.get('auto_close_hours', 72) or 72)
                cutoff = datetime.now(UTC) - timedelta(hours=hours)
                with sqlite3.connect(DB_NAME) as conn:
                    c = conn.cursor()
                    # Close stale sessions
                    c.execute(
                        """
                        UPDATE support_sessions
                        SET status='closed', ended_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                        WHERE status IN ('open','assigned','in_progress')
                          AND COALESCE(last_message_at, started_at) < ?
                        """,
                        (cutoff.isoformat(),)
                    )
                    closed = c.rowcount
                    conn.commit()
                if closed:
                    print(f"Auto-close: closed {closed} stale sessions older than {hours}h")
            except Exception as e:
                print(f"Auto-close worker error: {e}")
            # Sleep one hour
            time.sleep(3600)

    # Start background worker only once
    if not hasattr(bot, '_support_auto_close_started'):
        bot._support_auto_close_started = True
        threading.Thread(target=_auto_close_worker, daemon=True).start()

    # ----- Pending Tickets (Admin) -----
    @bot.callback_query_handler(func=lambda call: call.data == "admin_pending_tickets")
    def admin_pending_tickets(call):
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor(); c.execute("SELECT 1 FROM admins WHERE user_id=?", (call.from_user.id,))
                if not c.fetchone():
                    bot.answer_callback_query(call.id, "❌ Access denied", show_alert=True)
                    return
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT ticket_id, title, category, priority, status, created_at, assigned_admin
                FROM support_tickets
                WHERE status IN ('open','assigned','in_progress')
                ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'assigned' THEN 1 ELSE 2 END, priority DESC, created_at ASC
                LIMIT 25
            """)
            rows = c.fetchall()
        text = "🎫 **Pending Tickets**\n\n"
        if not rows:
            text += "No pending tickets."
        markup = types.InlineKeyboardMarkup(row_width=1)
        status_icon_map = { 'open':'🟡', 'assigned':'🔵', 'in_progress':'🛠️' }
        prio_icon = lambda p: '🔴' if p>=3 else '🟡' if p==2 else '🟢'
        for row in rows:
            tid, title, cat, pri, status, created, assigned_admin = row
            icon = status_icon_map.get(status,'❔') + prio_icon(pri)
            short = (title[:32] + '…') if len(title)>35 else title
            assigned_flag = ' 👤' if assigned_admin else ''
            markup.add(types.InlineKeyboardButton(f"{icon} #{tid} {short}{assigned_flag}", callback_data=f"admin_ticket_{tid}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_support_dashboard"))
        safe_edit = False
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            safe_edit = True
        except Exception:
            pass
        if not safe_edit:
            bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

    # ----- View / Manage Single Ticket -----
    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_ticket_"))
    def admin_view_ticket(call):
        try:
            ticket_id = int(call.data.split('_')[-1])
        except Exception:
            return
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT ticket_id, user_id, assigned_admin, title, description, category, priority, status, created_at, updated_at
                FROM support_tickets WHERE ticket_id=?
            """, (ticket_id,))
            t = c.fetchone()
        if not t:
            bot.answer_callback_query(call.id, "Ticket not found", show_alert=True)
            return
        (tid, user_id, assigned_admin, title, description, category, priority, status, created_at, updated_at) = t
        cat_name = SUPPORT_CATEGORIES.get(category, category)
        prio_name = PRIORITY_LEVELS.get(priority, str(priority))
        status_icons = {'open':'🟡 Open','assigned':'🔵 Assigned','in_progress':'🛠️ In Progress','resolved':'✅ Resolved','closed':'⚫ Closed'}
        status_label = status_icons.get(status, status)
        desc_short = description[:600] + ('…' if len(description)>600 else '')
        text = (
            f"🎫 **Ticket #{tid}**\n"
            f"**Title:** {title}\n"
            f"**User:** `{user_id}`\n"
            f"**Category:** {cat_name}\n"
            f"**Priority:** {prio_name}\n"
            f"**Status:** {status_label}\n"
            f"**Created:** {created_at[:16]}\n"
            f"**Updated:** {updated_at[:16]}\n\n"
            f"**Description:**\n{desc_short}"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        if status in ('open','assigned','in_progress'):
            if not assigned_admin:
                markup.add(types.InlineKeyboardButton("🧑‍💻 Assign to Me", callback_data=f"ticket_assign_{tid}"))
            elif assigned_admin == call.from_user.id and status == 'assigned':
                markup.add(types.InlineKeyboardButton("🛠️ Mark In Progress", callback_data=f"ticket_progress_{tid}"))
            if assigned_admin == call.from_user.id and status in ('in_progress','assigned'):
                markup.add(types.InlineKeyboardButton("✅ Resolve", callback_data=f"ticket_resolve_{tid}"))
        if status == 'resolved':
            markup.add(types.InlineKeyboardButton("🔒 Close", callback_data=f"ticket_close_{tid}"))
        if status not in ('closed',):
            markup.add(types.InlineKeyboardButton("📝 Add Note", callback_data=f"ticket_note_{tid}"))
        markup.add(types.InlineKeyboardButton("💬 Start Chat", callback_data="support_chat_new"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_pending_tickets"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    # Ticket actions
    @bot.callback_query_handler(func=lambda call: call.data.startswith("ticket_assign_"))
    def ticket_assign(call):
        tid = int(call.data.split('_')[-1])
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor(); c.execute("UPDATE support_tickets SET assigned_admin=?, status='assigned', updated_at=CURRENT_TIMESTAMP WHERE ticket_id=? AND (assigned_admin IS NULL OR assigned_admin=?)", (call.from_user.id, tid, call.from_user.id)); conn.commit()
        bot.answer_callback_query(call.id, "Assigned")
        admin_view_ticket(call)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("ticket_progress_"))
    def ticket_progress(call):
        tid = int(call.data.split('_')[-1])
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor(); c.execute("UPDATE support_tickets SET status='in_progress', updated_at=CURRENT_TIMESTAMP WHERE ticket_id=?", (tid,)); conn.commit()
        bot.answer_callback_query(call.id, "In Progress")
        admin_view_ticket(call)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("ticket_resolve_"))
    def ticket_resolve(call):
        tid = int(call.data.split('_')[-1])
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor(); c.execute("UPDATE support_tickets SET status='resolved', updated_at=CURRENT_TIMESTAMP, resolved_at=CURRENT_TIMESTAMP WHERE ticket_id=?", (tid,)); conn.commit()
        bot.answer_callback_query(call.id, "Resolved")
        admin_view_ticket(call)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("ticket_close_"))
    def ticket_close(call):
        tid = int(call.data.split('_')[-1])
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor(); c.execute("UPDATE support_tickets SET status='closed', updated_at=CURRENT_TIMESTAMP WHERE ticket_id=?", (tid,)); conn.commit()
        bot.answer_callback_query(call.id, "Closed")
        admin_view_ticket(call)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("ticket_note_"))
    def ticket_note_prompt(call):
        tid = int(call.data.split('_')[-1])
        if not hasattr(bot, '_user_states'): bot._user_states = {}
        bot._user_states[call.from_user.id] = f"awaiting_ticket_note_{tid}"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"📝 Send the note text for ticket #{tid}.", parse_mode="Markdown")

    @bot.message_handler(func=lambda m: hasattr(bot, '_user_states') and isinstance(bot._user_states.get(m.from_user.id,''), str) and bot._user_states.get(m.from_user.id,'').startswith('awaiting_ticket_note_'))
    def handle_ticket_note(message):
        state = bot._user_states.get(message.from_user.id)
        tid = int(state.split('_')[-1])
        note = message.text.strip()[:500]
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor(); c.execute("UPDATE support_tickets SET admin_notes = COALESCE(admin_notes,'') || ? , updated_at=CURRENT_TIMESTAMP WHERE ticket_id=?", ("\n"+note, tid)); conn.commit()
        bot._user_states.pop(message.from_user.id, None)
        bot.reply_to(message, "✅ Note added.")
        # Re-render ticket - create mock call-like object
        call_like = types.CallbackQuery(id=None, from_user=message.from_user, data=f"admin_ticket_{tid}", chat_instance=None, message=message, json_string=None)
        admin_view_ticket(call_like)

    # ----- Support Agents Overview -----
    @bot.callback_query_handler(func=lambda call: call.data == "admin_support_agents")
    def admin_support_agents(call):
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT a.user_id, u.username,
                       COUNT(DISTINCT s.session_id) as sessions,
                       SUM(CASE WHEN s.user_rating IS NOT NULL THEN 1 ELSE 0 END) as rated,
                       AVG(CAST(s.user_rating as FLOAT)) as avg_rating,
                       COUNT(DISTINCT t.ticket_id) as tickets
                FROM admins a
                LEFT JOIN users u ON a.user_id = u.user_id
                LEFT JOIN support_sessions s ON s.admin_id = a.user_id
                LEFT JOIN support_tickets t ON t.assigned_admin = a.user_id
                GROUP BY a.user_id
                ORDER BY sessions DESC
            """)
            rows = c.fetchall()
        text = "👥 **Support Agents**\n\n"
        if not rows:
            text += "No agents found."
        else:
            for r in rows:
                uid, uname, sessions, rated, avg_rating, tickets = r
                text += f"• `{uid}` {('@'+uname) if uname else ''} – Chats: {sessions or 0} | Tickets: {tickets or 0} | Rating: {(avg_rating or 0):.1f}\n"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_support_dashboard"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    # ----- Chat Templates Management -----
    @bot.callback_query_handler(func=lambda call: call.data == "admin_chat_templates")
    def admin_chat_templates(call):
        templates = load_chat_templates()
        text = "📝 **Chat Templates**\n\n"
        if not templates:
            text += "No templates yet."
        else:
            for idx, tpl in enumerate(templates, start=1):
                preview = tpl[:60] + ('…' if len(tpl)>60 else '')
                text += f"{idx}. {preview}\n"
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("➕ Add", callback_data="template_add"), types.InlineKeyboardButton("➖ Delete", callback_data="template_delete"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_support_dashboard"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    # Inline template menu for a specific chat
    @bot.callback_query_handler(func=lambda call: call.data.startswith("tpl_menu_"))
    def tpl_menu_for_chat(call):
        try:
            session_id = int(call.data.split('_')[-1])
        except Exception:
            return
        templates = load_chat_templates()
        if not templates:
            bot.answer_callback_query(call.id, "No templates", show_alert=True)
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        for idx, tpl in enumerate(templates, start=1):
            label = (tpl[:45] + '…') if len(tpl) > 48 else tpl
            markup.add(types.InlineKeyboardButton(f"{idx}. {label}", callback_data=f"tpl_send_{session_id}_{idx}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=f"admin_chat_{session_id}"))
        bot.edit_message_text("📝 Select a template to send:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("tpl_send_"))
    def tpl_send_to_chat(call):
        try:
            parts = call.data.split('_')
            session_id = int(parts[2])
            idx = int(parts[3])
        except Exception:
            return
        templates = load_chat_templates()
        if idx < 1 or idx > len(templates):
            bot.answer_callback_query(call.id, "Invalid template", show_alert=True)
            return
        text = templates[idx-1]
        # Determine user and send
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT user_id FROM support_sessions WHERE session_id=?", (session_id,))
            row = c.fetchone()
        if not row:
            bot.answer_callback_query(call.id, "Session missing", show_alert=True)
            return
        user_id = row[0]
        create_support_message(session_id, call.from_user.id, 'admin', text, 'text')
        try:
            bot.send_message(user_id, text)
        except Exception:
            pass
        bot.answer_callback_query(call.id, "Sent")
        # Trigger existing admin_chat_{session_id} handler by editing message to have that callback (simulate button press)
        try:
            # Reuse admin_chat_view via crafted callback only if defined later; fallback to minimal notice
            from telebot.types import CallbackQuery as _CQ
            fake = _CQ(id='0', from_user=call.from_user, data=f"admin_chat_{session_id}", chat_instance=None, message=call.message, json_string=None)
            try:
                admin_chat_view(fake)  # type: ignore
            except NameError:
                bot.send_message(call.message.chat.id, f"Template sent to chat #{session_id}.")
        except Exception:
            pass

    @bot.callback_query_handler(func=lambda call: call.data == "template_add")
    def template_add(call):
        if not hasattr(bot, '_user_states'): bot._user_states = {}
        bot._user_states[call.from_user.id] = 'awaiting_new_template'
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "✍️ Send the template text (max 500 chars).", parse_mode="Markdown")

    @bot.message_handler(func=lambda m: hasattr(bot,'_user_states') and bot._user_states.get(m.from_user.id)=='awaiting_new_template')
    def handle_new_template(message):
        templates = load_chat_templates()
        text = message.text.strip()[:500]
        templates.append(text)
        save_chat_templates(templates)
        bot._user_states.pop(message.from_user.id, None)
        bot.reply_to(message, "✅ Template added.")
        call_like = types.CallbackQuery(id=None, from_user=message.from_user, data="admin_chat_templates", chat_instance=None, message=message, json_string=None)
        admin_chat_templates(call_like)

    @bot.callback_query_handler(func=lambda call: call.data == "template_delete")
    def template_delete(call):
        templates = load_chat_templates()
        if not templates:
            bot.answer_callback_query(call.id, "No templates", show_alert=True)
            return
        if not hasattr(bot,'_user_states'): bot._user_states = {}
        bot._user_states[call.from_user.id] = 'awaiting_delete_template'
        bot.send_message(call.message.chat.id, "Send the template number to delete (e.g., 1).", parse_mode="Markdown")

    @bot.message_handler(func=lambda m: hasattr(bot,'_user_states') and bot._user_states.get(m.from_user.id)=='awaiting_delete_template')
    def handle_delete_template(message):
        templates = load_chat_templates()
        try:
            idx = int(message.text.strip()) - 1
            if idx < 0 or idx >= len(templates):
                raise ValueError
        except Exception:
            bot.reply_to(message, "❌ Invalid number.")
            return
        removed = templates.pop(idx)
        save_chat_templates(templates)
        bot._user_states.pop(message.from_user.id, None)
        bot.reply_to(message, f"✅ Deleted template #{idx+1}.")
        call_like = types.CallbackQuery(id=None, from_user=message.from_user, data="admin_chat_templates", chat_instance=None, message=message, json_string=None)
        admin_chat_templates(call_like)

    # ----- Support Settings Toggles -----
    @bot.callback_query_handler(func=lambda call: call.data.startswith("settings_"))
    def support_settings_actions(call):
        action = call.data
        settings = load_support_settings()
        # Helper render to avoid forward reference complaints
        def _render_settings(call_obj):
            text = (
                "⚙️ **Support Settings**\n\n"
                f"Auto-Assign: {'ON' if settings.get('auto_assign') else 'OFF'}\n"
                f"Notify All Admins: {'ON' if settings.get('notify_all_admins') else 'OFF'}\n"
                f"Auto-Close Hours: {settings.get('auto_close_hours')}\n\n"
                "Configure various aspects of the support system:"
            )
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🤖 Toggle Auto-Assign", callback_data="settings_toggle_auto_assign"),
                types.InlineKeyboardButton("🤖 Auto-Response Info", callback_data="settings_auto_response"),
                types.InlineKeyboardButton("⏰ Response Time Targets", callback_data="settings_response_time"),
                types.InlineKeyboardButton("📝 Chat Templates", callback_data="admin_chat_templates"),
                types.InlineKeyboardButton("🔔 Toggle Notifications", callback_data="settings_notifications")
            )
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_support_dashboard"))
            try:
                bot.edit_message_text(text, call_obj.message.chat.id, call_obj.message.message_id, reply_markup=markup, parse_mode="Markdown")
            except Exception:
                bot.send_message(call_obj.message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

        if action == 'settings_auto_response':
            bot.answer_callback_query(call.id, "Auto-responses are code-defined in code (edit AUTO_RESPONSES dict).", show_alert=True)
            return _render_settings(call)
        if action == 'settings_response_time':
            if not hasattr(bot,'_user_states'): bot._user_states = {}
            bot._user_states[call.from_user.id] = 'awaiting_auto_close_hours'
            bot.answer_callback_query(call.id)
            return bot.send_message(call.message.chat.id, f"Current auto-close hours: {settings['auto_close_hours']}\nSend new number (1-240):")
        if action == 'settings_notifications':
            settings['notify_all_admins'] = not settings.get('notify_all_admins', True)
            save_support_settings(settings)
            bot.answer_callback_query(call.id, f"notify_all_admins => {settings['notify_all_admins']}")
            return _render_settings(call)
        if action == 'settings_toggle_auto_assign':
            settings['auto_assign'] = not settings.get('auto_assign', False)
            save_support_settings(settings)
            bot.answer_callback_query(call.id, f"auto_assign => {settings['auto_assign']}")
            return _render_settings(call)
        # Fallback
        return _render_settings(call)

    @bot.message_handler(func=lambda m: hasattr(bot,'_user_states') and bot._user_states.get(m.from_user.id)=='awaiting_auto_close_hours')
    def handle_auto_close_hours(message):
        settings = load_support_settings()
        try:
            hours = int(message.text.strip())
            if hours < 1 or hours > 240:
                raise ValueError
            settings['auto_close_hours'] = hours
            save_support_settings(settings)
            bot.reply_to(message, f"✅ Updated auto-close hours to {hours}.")
        except Exception:
            bot.reply_to(message, "❌ Invalid number (1-240).")
        bot._user_states.pop(message.from_user.id, None)
        # Present updated snippet
        bot.send_message(message.chat.id, "⚙️ Setting saved. Open Support Settings again from dashboard.")

    # ----- Export Analytics (simple text) -----
    @bot.callback_query_handler(func=lambda call: call.data == 'export_analytics')
    def export_analytics(call):
        stats = get_support_analytics()
        text = (
            "📤 *Support Analytics Export*\n\n"
            f"Total Sessions (7d): {stats['total_sessions']}\n"
            f"Active Sessions Now: {stats['active_sessions']}\n"
            f"Avg Response Time: {stats['avg_response_time']}s\n"
            f"Satisfaction: {stats['satisfaction_score']}/5\n"
        )
        if stats['top_categories']:
            text += "Top Categories:\n" + "\n".join([f"- {SUPPORT_CATEGORIES.get(c,c)}: {cnt}" for c,cnt in stats['top_categories']])
        bot.answer_callback_query(call.id, "Export generated")
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')


def notify_admins_new_chat(bot, session_id, user_id, category, username):
    """Notify all admins about new chat with enhanced info"""
    admin_ids = [ADMIN_ID]
    
    # Get additional admins
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT user_id FROM admins")
            admin_ids.extend([row[0] for row in c.fetchall()])
    except:
        pass
    
    category_name = SUPPORT_CATEGORIES.get(category, category)
    
    text = (
        f"🆕 **New Support Chat**\n\n"
        f"**Session**: #{session_id}\n"
        f"**User**: {username} (`{user_id}`)\n"
        f"**Category**: {category_name}\n"
        f"**Time**: {datetime.now(UTC).strftime('%H:%M UTC')}\n\n"
        f"Click to join this chat:"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("👋 Join Chat", callback_data=f"support_admin_join_{session_id}"))
    markup.add(types.InlineKeyboardButton("📊 Dashboard", callback_data="admin_support_dashboard"))
    
    for admin_id in set(admin_ids):
        try:
            bot.send_message(admin_id, text, parse_mode="Markdown", reply_markup=markup)
        except:
            pass

    # Support Ticket System
    @bot.callback_query_handler(func=lambda call: call.data == "support_ticket_new")
    def create_support_ticket(call):
        """Start creating a new support ticket"""
        text = (
            "🎫 **Create Support Ticket**\n\n"
            "Support tickets are perfect for non-urgent issues that need detailed documentation. "
            "Select your issue category:"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        for key, name in SUPPORT_CATEGORIES.items():
            markup.add(types.InlineKeyboardButton(name, callback_data=f"ticket_cat_{key}"))
        
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="support"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("ticket_cat_"))
    def set_ticket_category(call):
        """Set ticket category and ask for priority"""
        category = call.data.split('_')[2]
        
        if not hasattr(bot, '_ticket_temp'):
            bot._ticket_temp = {}
        bot._ticket_temp[call.from_user.id] = {'category': category}
        
        text = (
            f"🎫 **Support Ticket**\n\n"
            f"**Category**: {SUPPORT_CATEGORIES[category]}\n\n"
            f"Select the priority level for your issue:"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        for level, name in PRIORITY_LEVELS.items():
            markup.add(types.InlineKeyboardButton(name, callback_data=f"ticket_pri_{level}"))
        
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="support_ticket_new"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("ticket_pri_"))
    def set_ticket_priority(call):
        """Set ticket priority and ask for title"""
        priority = int(call.data.split('_')[2])
        
        if not hasattr(bot, '_ticket_temp'):
            bot._ticket_temp = {}
        if call.from_user.id not in bot._ticket_temp:
            bot.answer_callback_query(call.id, "Session expired. Please start over.", show_alert=True)
            return
            
        bot._ticket_temp[call.from_user.id]['priority'] = priority
        
        # Set user state to await title
        if not hasattr(bot, '_user_states'):
            bot._user_states = {}
        bot._user_states[call.from_user.id] = "awaiting_ticket_title"
        
        category = bot._ticket_temp[call.from_user.id]['category']
        
        text = (
            f"🎫 **Support Ticket**\n\n"
            f"**Category**: {SUPPORT_CATEGORIES[category]}\n"
            f"**Priority**: {PRIORITY_LEVELS[priority]}\n\n"
            f"Please send a **short title** for your ticket (max 100 characters):"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="support"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="Markdown")

    @bot.message_handler(func=lambda message: hasattr(bot, '_user_states') and bot._user_states.get(message.from_user.id) == "awaiting_ticket_title")
    def handle_ticket_title(message):
        """Handle ticket title input"""
        title = message.text.strip()[:100]  # Limit to 100 chars
        
        if not hasattr(bot, '_ticket_temp') or message.from_user.id not in bot._ticket_temp:
            bot.reply_to(message, "❌ Session expired. Please start over with /start")
            return
            
        bot._ticket_temp[message.from_user.id]['title'] = title
        bot._user_states[message.from_user.id] = "awaiting_ticket_description"
        
        bot.reply_to(message, 
            f"✅ **Title Set**: {title}\n\n"
            f"Now please send a **detailed description** of your issue. Include as much information as possible to help us assist you better:",
            parse_mode="Markdown")

    @bot.message_handler(func=lambda message: hasattr(bot, '_user_states') and bot._user_states.get(message.from_user.id) == "awaiting_ticket_description")
    def handle_ticket_description(message):
        """Handle ticket description and create ticket"""
        description = message.text.strip()
        user_id = message.from_user.id
        
        if not hasattr(bot, '_ticket_temp') or user_id not in bot._ticket_temp:
            bot.reply_to(message, "❌ Session expired. Please start over with /start")
            return
            
        ticket_data = bot._ticket_temp[user_id]
        
        # Create the ticket
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO support_tickets 
                (user_id, title, description, category, priority, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'open', ?)
            """, (user_id, ticket_data['title'], description, ticket_data['category'], 
                 ticket_data['priority'], datetime.now(UTC).isoformat()))
            
            ticket_id = c.lastrowid
            conn.commit()
        
        # Clean up temp data and states
        del bot._ticket_temp[user_id]
        del bot._user_states[user_id]
        
        # Send confirmation to user
        category_name = SUPPORT_CATEGORIES[ticket_data['category']]
        priority_name = PRIORITY_LEVELS[ticket_data['priority']]
        
        confirmation_text = (
            f"🎫 **Ticket Created Successfully**\n\n"
            f"**Ticket ID**: #{ticket_id}\n"
            f"**Title**: {ticket_data['title']}\n"
            f"**Category**: {category_name}\n"
            f"**Priority**: {priority_name}\n\n"
            f"Your ticket has been submitted and will be reviewed by our support team. "
            f"You'll receive updates on the progress.\n\n"
            f"**Estimated Response Time**:\n"
            f"• Critical: Within 1 hour\n"
            f"• High: Within 4 hours\n"
            f"• Medium: Within 24 hours\n"
            f"• Low: Within 48 hours"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💬 Start Chat Instead", callback_data="support_chat_new"))
        markup.add(types.InlineKeyboardButton("📊 My Tickets", callback_data="user_tickets"))
        markup.add(types.InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
        
        bot.reply_to(message, confirmation_text, reply_markup=markup, parse_mode="Markdown")
        
        # Notify admins about new ticket
        notify_admins_new_ticket(bot, ticket_id, user_id, ticket_data, description)

    # User Tickets View
    @bot.callback_query_handler(func=lambda call: call.data == "user_tickets")
    def show_user_tickets(call):
        """Show user's support tickets"""
        user_id = call.from_user.id
        
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT ticket_id, title, category, priority, status, created_at, updated_at
                FROM support_tickets 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT 10
            """, (user_id,))
            tickets = c.fetchall()
        
        if not tickets:
            text = "🎫 **My Support Tickets**\n\nYou haven't created any support tickets yet."
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🎫 Create New Ticket", callback_data="support_ticket_new"))
        else:
            text = f"🎫 **My Support Tickets** ({len(tickets)})\n\n"
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            for ticket in tickets:
                ticket_id, title, category, priority, status, created, updated = ticket
                
                status_icons = {
                    'open': '🟡',
                    'assigned': '🔵', 
                    'in_progress': '🟠',
                    'resolved': '✅',
                    'closed': '⚫'
                }
                
                status_icon = status_icons.get(status, '❓')
                priority_icon = '🔴' if priority >= 3 else '🟡' if priority == 2 else '🟢'
                
                button_text = f"{status_icon}{priority_icon} #{ticket_id}: {title[:30]}..."
                markup.add(types.InlineKeyboardButton(button_text, callback_data=f"ticket_view_{ticket_id}"))
            
            markup.add(types.InlineKeyboardButton("🎫 Create New Ticket", callback_data="support_ticket_new"))
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Support", callback_data="support"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="Markdown")

def notify_admins_new_ticket(bot, ticket_id, user_id, ticket_data, description):
    """Notify admins about new support ticket"""
    admin_ids = [ADMIN_ID]
    
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT user_id FROM admins")
            admin_ids.extend([row[0] for row in c.fetchall()])
    except:
        pass
    
    category_name = SUPPORT_CATEGORIES[ticket_data['category']]
    priority_name = PRIORITY_LEVELS[ticket_data['priority']]
    priority_emoji = '🔴' if ticket_data['priority'] >= 3 else '🟡' if ticket_data['priority'] == 2 else '🟢'
    
    text = (
        f"🎫 **New Support Ticket** {priority_emoji}\n\n"
        f"**Ticket ID**: #{ticket_id}\n"
        f"**User**: ID {user_id}\n"
        f"**Title**: {ticket_data['title']}\n"
        f"**Category**: {category_name}\n"
        f"**Priority**: {priority_name}\n\n"
        f"**Description**:\n{description[:200]}{'...' if len(description) > 200 else ''}"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📋 View Ticket", callback_data=f"admin_ticket_{ticket_id}"))
    markup.add(types.InlineKeyboardButton("🎫 All Tickets", callback_data="admin_pending_tickets"))
    
    for admin_id in set(admin_ids):
        try:
            bot.send_message(admin_id, text, parse_mode="Markdown", reply_markup=markup)
        except:
            pass

    # Enhanced Chat Features
    @bot.callback_query_handler(func=lambda call: call.data.startswith("chat_info_"))
    def show_chat_info(call):
        """Show detailed chat information"""
        try:
            session_id = int(call.data.split('_')[2])
        except:
            return
            
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT s.user_id, s.admin_id, s.category, s.status, s.started_at, 
                       s.first_response_time, u.username, a.username as admin_name
                FROM support_sessions s
                LEFT JOIN users u ON s.user_id = u.user_id
                LEFT JOIN users a ON s.admin_id = a.user_id
                WHERE s.session_id = ?
            """, (session_id,))
            session_info = c.fetchone()
            
            if not session_info:
                bot.answer_callback_query(call.id, "Session not found", show_alert=True)
                return
                
            c.execute("SELECT COUNT(*) FROM support_messages WHERE session_id = ?", (session_id,))
            message_count = c.fetchone()[0]
        
        user_id, admin_id, category, status, started, response_time, username, admin_name = session_info
        
        text = (
            f"📊 **Chat Information**\n\n"
            f"**Session ID**: #{session_id}\n"
            f"**Category**: {SUPPORT_CATEGORIES.get(category, category)}\n"
            f"**Status**: {status.title()}\n"
            f"**Started**: {started[:16]}\n"
            f"**Messages**: {message_count}\n"
        )
        
        if admin_id:
            admin_display = admin_name if admin_name else f"ID:{admin_id}"
            text += f"**Assigned Admin**: {admin_display}\n"
            
        if response_time:
            text += f"**First Response**: {response_time}s\n"
            
        elapsed = int((datetime.now(UTC) - datetime.fromisoformat(started.replace('Z', '+00:00'))).total_seconds() / 60)
        text += f"**Duration**: {elapsed} minutes"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📜 View History", callback_data=f"chat_history_{session_id}"))
        markup.add(types.InlineKeyboardButton("⭐ Rate Chat", callback_data=f"rate_chat_{session_id}"))
        markup.add(types.InlineKeyboardButton("🔚 End Chat", callback_data=f"support_end_{session_id}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="support"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("chat_history_"))
    def show_chat_history(call):
        """Show chat message history"""
        try:
            session_id = int(call.data.split('_')[2])
        except:
            return
            
        history = get_chat_history(session_id, 20)
        
        if not history:
            text = "📜 **Chat History**\n\nNo messages yet in this chat."
        else:
            text = f"📜 **Chat History** (Last 20 messages)\n\n"
            
            for msg in reversed(history):  # Show oldest first
                sender_id, sender_type, msg_text, msg_type, file_id, timestamp = msg
                
                time_str = timestamp[11:16]  # HH:MM
                sender_icon = "👤" if sender_type == "user" else "👨‍💼" if sender_type == "admin" else "🤖"
                
                if msg_type == 'auto_response':
                    text += f"{sender_icon} **System** ({time_str}):\n"
                elif sender_type == "user":
                    text += f"{sender_icon} **You** ({time_str}):\n"
                else:
                    text += f"{sender_icon} **Admin** ({time_str}):\n"
                
                if msg_text:
                    # Truncate long messages
                    display_text = msg_text[:100] + "..." if len(msg_text) > 100 else msg_text
                    text += f"{display_text}\n\n"
                elif file_id:
                    text += f"[File: {msg_type}]\n\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Chat Info", callback_data=f"chat_info_{session_id}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("rate_chat_"))
    def rate_chat_prompt(call):
        """Prompt user to rate their chat experience"""
        try:
            session_id = int(call.data.split('_')[2])
        except:
            return
            
        text = (
            f"⭐ **Rate Your Experience**\n\n"
            f"How would you rate the support you received in this chat?\n"
            f"Your feedback helps us improve our service."
        )
        
        markup = types.InlineKeyboardMarkup(row_width=5)
        for rating in range(1, 6):
            markup.add(types.InlineKeyboardButton(f"{rating}⭐", callback_data=f"set_rating_{session_id}_{rating}"))
        
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=f"chat_info_{session_id}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("set_rating_"))
    def set_chat_rating(call):
        """Set chat rating"""
        try:
            parts = call.data.split('_')
            session_id = int(parts[2])
            rating = int(parts[3])
        except:
            return
            
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("UPDATE support_sessions SET user_rating = ? WHERE session_id = ? AND user_id = ?", 
                     (rating, session_id, call.from_user.id))
            conn.commit()
        
        bot.answer_callback_query(call.id, f"Thank you for your {rating}⭐ rating!")
        
        text = (
            f"⭐ **Rating Submitted**\n\n"
            f"Thank you for rating your chat experience: **{rating}/5 stars**\n\n"
            f"Your feedback helps us improve our support service."
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💬 New Support Chat", callback_data="support_chat_new"))
        markup.add(types.InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="Markdown")

    # Support Analytics
    @bot.callback_query_handler(func=lambda call: call.data == "admin_support_analytics")
    def show_support_analytics(call):
        """Show detailed support analytics"""
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if not c.fetchone():
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return
        
        # Get comprehensive analytics
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            
            # Sessions today
            c.execute("SELECT COUNT(*) FROM support_sessions WHERE date(started_at) = date('now')")
            sessions_today = c.fetchone()[0]
            
            # Average rating
            c.execute("SELECT AVG(CAST(user_rating as FLOAT)) FROM support_sessions WHERE user_rating IS NOT NULL AND datetime(started_at) > datetime('now', '-30 days')")
            avg_rating = c.fetchone()[0] or 0
            
            # Resolution time
            c.execute("SELECT AVG(resolution_time) FROM support_sessions WHERE resolution_time IS NOT NULL AND datetime(started_at) > datetime('now', '-7 days')")
            avg_resolution = c.fetchone()[0] or 0
            
            # Category breakdown
            c.execute("SELECT category, COUNT(*) FROM support_sessions WHERE datetime(started_at) > datetime('now', '-7 days') GROUP BY category ORDER BY COUNT(*) DESC")
            categories = c.fetchall()
            
            # Admin performance
            c.execute("""
                SELECT u.username, COUNT(*) as handled, AVG(s.user_rating) as avg_rating
                FROM support_sessions s 
                JOIN users u ON s.admin_id = u.user_id 
                WHERE s.admin_id IS NOT NULL AND datetime(s.started_at) > datetime('now', '-7 days')
                GROUP BY s.admin_id 
                ORDER BY handled DESC
            """)
            admin_stats = c.fetchall()
        
        text = (
            f"📊 **Support Analytics** (Last 7 days)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📈 **Performance Metrics**\n"
            f"• Sessions Today: **{sessions_today}**\n"
            f"• Average Rating: **{avg_rating:.1f}/5** ⭐\n"
            f"• Avg Resolution: **{int(avg_resolution/60) if avg_resolution else 0}** minutes\n\n"
        )
        
        if categories:
            text += "🔥 **Popular Categories**\n"
            for cat, count in categories[:5]:
                cat_name = SUPPORT_CATEGORIES.get(cat, cat)
                text += f"• {cat_name}: **{count}**\n"
            text += "\n"
        
        if admin_stats:
            text += "👨‍💼 **Admin Performance**\n"
            for username, handled, rating in admin_stats[:3]:
                username_display = username or "Unknown"
                rating_display = f"{rating:.1f}⭐" if rating else "N/A"
                text += f"• {username_display}: {handled} chats, {rating_display}\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📊 Export Report", callback_data="export_analytics"))
        markup.add(types.InlineKeyboardButton("⚙️ Settings", callback_data="admin_support_settings"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_support_dashboard"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="Markdown")

    # Support Settings
    @bot.callback_query_handler(func=lambda call: call.data == "admin_support_settings")
    def support_settings_menu(call):
        """Support system settings"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only!", show_alert=True)
            return
            
        text = (
            "⚙️ **Support Settings**\n\n"
            "Configure various aspects of the support system:"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🤖 Auto-Response Settings", callback_data="settings_auto_response"),
            types.InlineKeyboardButton("⏰ Response Time Targets", callback_data="settings_response_time"),
            types.InlineKeyboardButton("📝 Chat Templates", callback_data="admin_chat_templates"),
            types.InlineKeyboardButton("🔔 Notification Settings", callback_data="settings_notifications")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_support_dashboard"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="Markdown")

    # Admin chat view (from active chats list)
    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_chat_"))
    def admin_chat_view(call):
        try:
            session_id = int(call.data.split('_')[-1])
        except Exception:
            return
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT user_id, admin_id, category, status, started_at FROM support_sessions WHERE session_id=?", (session_id,))
            row = c.fetchone()
        if not row:
            bot.answer_callback_query(getattr(call,'id',None), "Session missing", show_alert=True)
            return
        user_id, admin_id, category, status, started_at = row
        last_msgs = get_chat_history(session_id, 5)
        transcript = ""
        for m in reversed(last_msgs):
            sender_id, sender_type, message_text, message_type, file_id, ts = m
            who = 'U' if sender_type=='user' else 'A' if sender_type=='admin' else 'S'
            snippet = (message_text or message_type or '')
            if len(snippet) > 40:
                snippet = snippet[:37] + '…'
            transcript += f"{who}: {snippet}\n"
        if not transcript:
            transcript = "(no messages yet)"
        category_name = SUPPORT_CATEGORIES.get(category, category)
        text = (
            f"💬 **Chat #{session_id}**\n"
            f"User: `{user_id}` | Category: {category_name}\n"
            f"Status: {status}\n"
            f"Started: {started_at[:16] if started_at else '-'}\n\n"
            f"Last messages:\n{transcript}"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        if not admin_id:
            markup.add(types.InlineKeyboardButton("👋 Join", callback_data=f"support_admin_join_{session_id}"))
        markup.add(types.InlineKeyboardButton("📝 Templates", callback_data=f"tpl_menu_{session_id}"))
        markup.add(types.InlineKeyboardButton("📜 History", callback_data=f"chat_history_{session_id}"))
        markup.add(types.InlineKeyboardButton("ℹ️ Info", callback_data=f"chat_info_{session_id}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_active_chats"))
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode='Markdown')

    # /tpl command inside admin chat state
    @bot.message_handler(commands=['tpl'])
    def tpl_command(message):  # noqa: F811
        try:
            if not hasattr(bot, '_user_states'):
                return
            state = bot._user_states.get(message.from_user.id, '')
            if not (isinstance(state, str) and state.startswith('support_chat_admin_')):
                return
            session_id = int(state.split('_')[-1])
            templates_local = load_chat_templates()
            if not templates_local:
                bot.reply_to(message, "No templates defined.")
                return
            markup = types.InlineKeyboardMarkup(row_width=2)
            for idx, tpl in enumerate(templates_local, start=1):
                label = (tpl[:20] + '…') if len(tpl) > 23 else tpl
                markup.add(types.InlineKeyboardButton(f"{idx}. {label}", callback_data=f"tpl_send_{session_id}_{idx}"))
            bot.reply_to(message, "Select a template:", reply_markup=markup)
        except Exception as e:
            print(f"/tpl command error: {e}")

    # Enhanced message handler with auto-responses and logging
    @bot.message_handler(func=lambda m: hasattr(bot, '_user_states') and isinstance(bot._user_states.get(m.from_user.id, ''), str) and bot._user_states.get(m.from_user.id, '').startswith("support_chat_user_"))
    def enhanced_user_chat_handler(message):
        """Enhanced user chat handler with auto-responses and logging"""
        user_id = message.from_user.id
        state = bot._user_states.get(user_id, '')
        
        try:
            session_id = int(state.split('_')[-1])
        except:
            return
        
        # Log the message
        message_text = message.text or f"[{message.content_type}]"
        file_id = None
        
        if hasattr(message, 'photo') and message.photo:
            file_id = message.photo[-1].file_id
        elif hasattr(message, 'document') and message.document:
            file_id = message.document.file_id
        elif hasattr(message, 'video') and message.video:
            file_id = message.video.file_id
        
        create_support_message(session_id, user_id, 'user', message_text, message.content_type, file_id)
        
        # Check for auto-response
        if message.text and not file_id:
            auto_response = auto_respond(message.text)
            if auto_response:
                create_support_message(session_id, 0, 'system', auto_response, 'auto_response')
                bot.send_message(user_id, auto_response, parse_mode="Markdown")
        
        # Update response time tracking
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT admin_id, started_at FROM support_sessions WHERE session_id = ?", (session_id,))
            session_data = c.fetchone()
            
            if session_data:
                admin_id, started_at = session_data
                
                if not admin_id:
                    # Notify admins if no one assigned yet
                    from other_handlers import notify_admins_new_chat
                    try:
                        notify_admins_new_chat(bot, session_id, user_id, 'general', message.from_user.first_name)
                    except:
                        pass
                else:
                    # Forward to assigned admin
                    try:
                        bot.copy_message(admin_id, from_chat_id=message.chat.id, message_id=message.message_id)
                    except:
                        pass

    # Enhanced admin chat handler
    @bot.message_handler(func=lambda m: hasattr(bot, '_user_states') and isinstance(bot._user_states.get(m.from_user.id, ''), str) and bot._user_states.get(m.from_user.id, '').startswith("support_chat_admin_"))
    def enhanced_admin_chat_handler(message):
        """Enhanced admin chat handler with logging and metrics"""
        admin_id = message.from_user.id
        
        try:
            session_id = int(bot._user_states[admin_id].split('_')[-1])
        except:
            return
        
        # Log the message
        message_text = message.text or f"[{message.content_type}]"
        file_id = None
        
        if hasattr(message, 'photo') and message.photo:
            file_id = message.photo[-1].file_id
        elif hasattr(message, 'document') and message.document:
            file_id = message.document.file_id
        
        create_support_message(session_id, admin_id, 'admin', message_text, message.content_type, file_id)
        
        # Update first response time if this is the first admin message
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT user_id, started_at, first_response_time FROM support_sessions WHERE session_id = ?", (session_id,))
            session_data = c.fetchone()
            
            if session_data:
                user_id, started_at, first_response = session_data
                
                if not first_response:
                    # Calculate and set first response time
                    start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                    response_time = int((datetime.now(UTC) - start_time).total_seconds())
                    c.execute("UPDATE support_sessions SET first_response_time = ? WHERE session_id = ?", 
                             (response_time, session_id))
                    conn.commit()
                
                # Forward message to user
                try:
                    bot.copy_message(user_id, from_chat_id=message.chat.id, message_id=message.message_id)
                except:
                    pass

        # If admin sent /tpl accidentally, ignore (handled by separate handler)
        if message.text and message.text.strip().lower() == '/tpl':
            return

# Export the registration function
__all__ = ['register_perfect_support_handlers']
