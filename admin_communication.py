"""
Enhanced Admin Communication System
- Owner-only user chat with ID search
- Payment screenshot validation
- Admin remarks system for responses
"""

from telebot import types
import sqlite3
import json
from datetime import datetime, UTC
from config import DB_NAME, ADMIN_ID
from helpers import send_random_animation

# Store active admin chats
active_admin_chats = {}
admin_chat_sessions = {}
user_states = {}

def init_admin_communication_db():
    """Initialize database tables for admin communication system"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # Admin-User chat sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_chat_sessions (
                session_id TEXT PRIMARY KEY,
                admin_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                last_message_at TEXT
            )
        ''')
        
        # Chat messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_chat_messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                sender_id INTEGER NOT NULL,
                sender_type TEXT NOT NULL,  -- 'admin' or 'user'
                message_text TEXT,
                message_type TEXT DEFAULT 'text',  -- 'text', 'photo', 'document', etc.
                sent_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES admin_chat_sessions(session_id)
            )
        ''')
        
        # Payment decisions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_decisions (
                decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id TEXT NOT NULL,
                admin_id INTEGER NOT NULL,
                decision TEXT NOT NULL,  -- 'approved' or 'rejected'
                remarks TEXT,
                decision_at TEXT NOT NULL
            )
        ''')
        
        # Payment rejection reasons table (predefined options)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rejection_reasons (
                reason_id INTEGER PRIMARY KEY AUTOINCREMENT,
                reason_text TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default rejection reasons if none exist
        cursor.execute("SELECT COUNT(*) FROM rejection_reasons")
        if cursor.fetchone()[0] == 0:
            default_reasons = [
                "Payment amount doesn't match order total",
                "Invalid payment screenshot or proof",
                "Payment not received in our wallet",
                "Duplicate payment submission",
                "Suspicious transaction activity",
                "Payment ID not included in transaction memo",
                "Insufficient payment amount",
                "Payment from unauthorized source",
                "Order expired or cancelled",
                "Technical verification failed"
            ]
            
            for reason in default_reasons:
                cursor.execute(
                    "INSERT INTO rejection_reasons (reason_text) VALUES (?)",
                    (reason,)
                )
        
        conn.commit()

def get_all_users_for_admin():
    """Get list of all users for admin selection"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.user_id, u.username, u.join_date, u.is_active,
                   COUNT(o.order_id) as total_orders
            FROM users u
            LEFT JOIN orders o ON u.user_id = o.user_id
            GROUP BY u.user_id
            ORDER BY u.join_date DESC
        """)
        return cursor.fetchall()

def create_chat_session(admin_id, user_id):
    """Create a new admin-user chat session"""
    session_id = f"chat_{admin_id}_{user_id}_{int(datetime.now(UTC).timestamp())}"
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO admin_chat_sessions (session_id, admin_id, user_id, created_at, last_message_at)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, admin_id, user_id, datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat()))
        conn.commit()
    
    return session_id

def log_chat_message(session_id, sender_id, sender_type, message_text, message_type='text'):
    """Log a chat message to database"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO admin_chat_messages 
            (session_id, sender_id, sender_type, message_text, message_type, sent_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, sender_id, sender_type, message_text, message_type, datetime.now(UTC).isoformat()))
        
        # Update session last message time
        cursor.execute("""
            UPDATE admin_chat_sessions 
            SET last_message_at = ? 
            WHERE session_id = ?
        """, (datetime.now(UTC).isoformat(), session_id))
        
        conn.commit()

def get_rejection_reasons():
    """Get all active rejection reasons"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT reason_id, reason_text FROM rejection_reasons WHERE is_active = 1")
        return cursor.fetchall()

def log_payment_decision(payment_id, admin_id, decision, remarks=None):
    """Log payment approval/rejection decision"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO payment_decisions (payment_id, admin_id, decision, remarks, decision_at)
            VALUES (?, ?, ?, ?, ?)
        """, (payment_id, admin_id, decision, remarks, datetime.now(UTC).isoformat()))
        conn.commit()

def register_admin_communication_handlers(bot):
    """Register all admin communication handlers"""
    
    # Initialize the database when handlers are registered
    init_admin_communication_db()
    
    @bot.callback_query_handler(func=lambda call: call.data == "admin_user_chat")
    def show_user_search_interface(call):
        """Show user search interface for admin instead of user list"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        
        try:
            text = (
                "👨‍💼 <b>Admin - User Chat</b>\n\n"
                "🔍 <b>Search and connect with users:</b>\n\n"
                "Choose how you want to find the user:\n\n"
                "📱 <b>Search by User ID</b> - If you know their Telegram ID\n"
                "👤 <b>Search by Username</b> - Search by @username or name\n"
                "⏰ <b>Recent Users</b> - Users who made recent orders\n"
                "� <b>Active Chats</b> - Currently ongoing conversations\n\n"
                "<i>Select an option below:</i>"
            )
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🆔 Search by User ID", callback_data="admin_search_user_id"),
                types.InlineKeyboardButton("� Search by Username", callback_data="admin_search_username"),
                types.InlineKeyboardButton("⏰ Recent Users", callback_data="admin_recent_users"),
                types.InlineKeyboardButton("� Active Chats", callback_data="admin_active_chats"),
                types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel")
            )
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                reply_markup=markup, parse_mode="HTML")
            
        except Exception as e:
            print(f"Error showing user search interface: {e}")
            bot.answer_callback_query(call.id, "Error loading interface", show_alert=True)
    
    @bot.callback_query_handler(func=lambda call: call.data == "admin_search_user_id")
    def admin_search_user_id_prompt(call):
        """Prompt admin to enter user ID"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
            
        user_states[call.from_user.id] = "admin_awaiting_user_id_search"
        
        text = (
            "🔍 <b>Search User by ID</b>\n\n"
            "Enter the User ID you want to chat with:\n\n"
            "<i>Example: 123456789</i>\n\n"
            "💡 <b>Tips:</b>\n"
            "• User ID is their Telegram user ID\n"
            "• You can find it in orders or user logs\n"
            "• Make sure the user exists in your system"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="admin_user_chat"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data == "admin_search_username")
    def admin_search_username_prompt(call):
        """Prompt admin to enter username to search"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
            
        user_states[call.from_user.id] = "admin_awaiting_username_search"
        
        text = (
            "👤 <b>Search User by Username</b>\n\n"
            "Enter the username or name to search for:\n\n"
            "<i>Examples:</i>\n"
            "• @john_doe (with @)\n"
            "• john_doe (without @)\n"
            "• John Smith (first name)\n"
            "• john (partial username)\n\n"
            "💡 <b>Tips:</b>\n"
            "• Search will find matching usernames and names\n"
            "• Results show users who have used the bot\n"
            "• Use partial names for broader search"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="admin_user_chat"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data == "admin_recent_users")
    def show_admin_recent_users(call):
        """Show recent users for admin to select"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
            
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            recent_users = cursor.execute('''
                SELECT DISTINCT user_id, MAX(creation_date) as last_order
                FROM orders 
                GROUP BY user_id 
                ORDER BY last_order DESC 
                LIMIT 10
            ''').fetchall()
        
        if not recent_users:
            text = "📭 <b>No Recent Users</b>\n\nNo users found in the system."
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_user_chat"))
        else:
            text = "👥 <b>Recent Users</b>\n\nSelect a user to chat with:\n\n"
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            for user_id, last_order in recent_users:
                # Get user info
                try:
                    user_info = bot.get_chat(user_id)
                    name = user_info.first_name or "Unknown"
                    username = f"@{user_info.username}" if user_info.username else ""
                except:
                    name = "Unknown User"
                    username = ""
                
                button_text = f"👤 {name} {username} - ID: {user_id}"
                markup.add(types.InlineKeyboardButton(
                    button_text, callback_data=f"select_user_{user_id}")
                )
            
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_user_chat"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data == "admin_active_chats")
    def show_admin_active_chats(call):
        """Show active admin chat sessions"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
            
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            active_chats = cursor.execute('''
                SELECT session_id, user_id, created_at, last_message_at
                FROM admin_chat_sessions 
                WHERE status = 'active' AND admin_id = ?
                ORDER BY last_message_at DESC 
                LIMIT 5
            ''', (ADMIN_ID,)).fetchall()
        
        if not active_chats:
            text = "💬 <b>No Active Chats</b>\n\nYou have no active chat sessions."
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_user_chat"))
        else:
            text = "💬 <b>Active Chat Sessions</b>\n\nSelect a chat to resume:\n\n"
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            for session_id, user_id, created_at, last_message_at in active_chats:
                try:
                    user_info = bot.get_chat(user_id)
                    name = user_info.first_name or "Unknown"
                    username = f"@{user_info.username}" if user_info.username else ""
                except:
                    name = "Unknown User"
                    username = ""
                
                button_text = f"💬 {name} {username} - {session_id[:8]}"
                markup.add(types.InlineKeyboardButton(
                    button_text, callback_data=f"resume_chat_{session_id}")
                )
            
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_user_chat"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")
    
    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "admin_awaiting_username_search")
    def handle_admin_username_search(message):
        """Handle username search and show results"""
        if message.from_user.id != ADMIN_ID:
            return
            
        search_term = message.text.strip().lower()
        if search_term.startswith('@'):
            search_term = search_term[1:]  # Remove @ if present
        
        if len(search_term) < 2:
            bot.reply_to(message, "❌ Search term too short. Please enter at least 2 characters.")
            return
        
        # Get users from orders and try to match usernames
        matching_users = []
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            # Get unique user IDs who have made orders
            user_ids = cursor.execute(
                "SELECT DISTINCT user_id FROM orders ORDER BY creation_date DESC LIMIT 100"
            ).fetchall()
        
        # Search through users to find matches
        for (user_id,) in user_ids:
            try:
                user_info = bot.get_chat(user_id)
                
                # Check username match
                username_match = False
                if user_info.username and search_term in user_info.username.lower():
                    username_match = True
                
                # Check first name match
                name_match = False
                if user_info.first_name and search_term in user_info.first_name.lower():
                    name_match = True
                
                # Check last name match  
                last_name_match = False
                if user_info.last_name and search_term in user_info.last_name.lower():
                    last_name_match = True
                
                if username_match or name_match or last_name_match:
                    matching_users.append({
                        'user_id': user_id,
                        'first_name': user_info.first_name or "Unknown",
                        'last_name': user_info.last_name or "",
                        'username': user_info.username or "",
                    })
                
                # Limit results to prevent spam
                if len(matching_users) >= 10:
                    break
                    
            except Exception:
                # Skip users we can't get info for
                continue
        
        # Clear search state
        del user_states[message.from_user.id]
        
        # Show results
        if not matching_users:
            text = (
                f"🔍 <b>No Users Found</b>\n\n"
                f"No users found matching: <code>{search_term}</code>\n\n"
                f"• Try a different search term\n"
                f"• Check spelling\n"
                f"• Use partial names for broader search\n"
                f"• Make sure the user has used the bot before"
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Search Again", callback_data="admin_search_username"))
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_user_chat"))
            
        else:
            text = f"👥 <b>Search Results</b>\n\nFound {len(matching_users)} user(s) matching: <code>{search_term}</code>\n\nSelect a user to chat with:\n\n"
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            for user in matching_users:
                full_name = f"{user['first_name']} {user['last_name']}".strip()
                username_display = f"@{user['username']}" if user['username'] else "No username"
                
                button_text = f"👤 {full_name} ({username_display}) - ID: {user['user_id']}"
                
                # Truncate button text if too long
                if len(button_text) > 60:
                    button_text = button_text[:57] + "..."
                
                markup.add(types.InlineKeyboardButton(
                    button_text, callback_data=f"select_user_{user['user_id']}")
                )
            
            markup.add(types.InlineKeyboardButton("🔄 Search Again", callback_data="admin_search_username"))
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_user_chat"))
        
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")
    
    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "admin_awaiting_user_id_search")
    def handle_admin_user_id_search(message):
        """Handle user ID search input"""
        if message.from_user.id != ADMIN_ID:
            return
            
        try:
            target_user_id = int(message.text.strip())
        except ValueError:
            bot.reply_to(message, "❌ Invalid User ID. Please enter a valid number.")
            return
            
        # Check if user exists in database
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            user_exists = cursor.execute(
                "SELECT COUNT(*) FROM orders WHERE user_id = ? LIMIT 1", 
                (target_user_id,)
            ).fetchone()[0]
        
        if not user_exists:
            bot.reply_to(message, 
                        f"❌ User ID {target_user_id} not found in system.\n"
                        f"Make sure the user has interacted with the bot before.")
            return
        
        # Clear state
        del user_states[message.from_user.id]
        
        # Start chat with user using existing function
        start_direct_admin_chat(bot, message.from_user.id, target_user_id, message.chat.id, message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("select_user_"))
    def start_chat_with_user(call):
        """Start chat session with selected user"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        
        try:
            target_user_id = int(call.data.split('_')[2])
            start_direct_admin_chat(bot, call.from_user.id, target_user_id, call.message.chat.id, call.message.message_id)
            
        except Exception as e:
            print(f"Error starting chat: {e}")
            bot.answer_callback_query(call.id, "Error starting chat", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("resume_chat_"))
    def resume_chat_session(call):
        """Resume existing chat session"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        
        try:
            session_id = call.data.split('_')[2]
            
            # Get session info
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                session_info = cursor.execute(
                    "SELECT user_id FROM admin_chat_sessions WHERE session_id = ? AND admin_id = ?", 
                    (session_id, ADMIN_ID)
                ).fetchone()
            
            if not session_info:
                bot.answer_callback_query(call.id, "Session not found", show_alert=True)
                return
            
            target_user_id = session_info[0]
            
            # Resume the existing session
            admin_chat_sessions[ADMIN_ID] = {
                'session_id': session_id,
                'target_user_id': target_user_id,
                'active': True
            }
            
            # Get user info for display
            try:
                user_info = bot.get_chat(target_user_id)
                name = user_info.first_name or "Unknown"
                username = f"@{user_info.username}" if user_info.username else ""
            except:
                name = "Unknown User"
                username = ""
            
            text = (
                f"💬 <b>Resumed Chat Session</b>\n\n"
                f"<b>Chatting with:</b> {name} {username} (ID: {target_user_id})\n"
                f"<b>Session ID:</b> <code>{session_id}</code>\n\n"
                f"You can now continue sending messages to this user.\n"
                f"Type your message and it will be forwarded to them.\n\n"
                f"<i>Session was resumed from previous conversation.</i>"
            )
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("📜 Chat History", callback_data=f"chat_history_{session_id}"),
                types.InlineKeyboardButton("🚫 End Chat", callback_data=f"end_chat_{session_id}")
            )
            markup.add(types.InlineKeyboardButton("⬅️ Back to Users", callback_data="admin_user_chat"))
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                reply_markup=markup, parse_mode="HTML")
            
        except Exception as e:
            print(f"Error resuming chat: {e}")
            bot.answer_callback_query(call.id, "Error resuming chat", show_alert=True)
    
    # Enhanced payment rejection with remarks system
    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_reject_"))
    def show_rejection_options(call):
        """Show rejection options with remarks"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        
        try:
            payment_id = call.data.split('_')[2]
            
            text = (
                f"❌ <b>Reject Payment: {payment_id}</b>\n\n"
                f"Please select a reason for rejection or provide custom remarks:\n\n"
                f"<i>This will be sent to the user along with the rejection notice.</i>"
            )
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            # Get predefined rejection reasons
            reasons = get_rejection_reasons()
            for reason_id, reason_text in reasons[:8]:  # Show first 8 reasons
                markup.add(types.InlineKeyboardButton(
                    f"📝 {reason_text}",
                    callback_data=f"reject_reason_{payment_id}_{reason_id}"
                ))
            
            markup.add(
                types.InlineKeyboardButton("✏️ Custom Reason", callback_data=f"reject_custom_{payment_id}"),
                types.InlineKeyboardButton("🚫 Quick Reject (No Reason)", callback_data=f"reject_quick_{payment_id}")
            )
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=f"admin_approve_{payment_id}"))
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                reply_markup=markup, parse_mode="HTML")
            
        except Exception as e:
            print(f"Error showing rejection options: {e}")
            bot.answer_callback_query(call.id, "Error loading rejection options", show_alert=True)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("reject_reason_"))
    def reject_with_predefined_reason(call):
        """Reject payment with predefined reason"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        
        try:
            parts = call.data.split('_')
            payment_id = parts[2]
            reason_id = int(parts[3])
            
            # Get reason text
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                reason_text = cursor.execute(
                    "SELECT reason_text FROM rejection_reasons WHERE reason_id = ?", 
                    (reason_id,)
                ).fetchone()
            
            if not reason_text:
                bot.answer_callback_query(call.id, "Reason not found", show_alert=True)
                return
            
            reason_text = reason_text[0]
            
            # Process rejection with reason
            process_payment_rejection(bot, call, payment_id, reason_text)
            
        except Exception as e:
            print(f"Error processing predefined rejection: {e}")
            bot.answer_callback_query(call.id, "Error processing rejection", show_alert=True)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("reject_custom_"))
    def request_custom_reason(call):
        """Request custom rejection reason from admin"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        
        payment_id = call.data.split('_')[2]
        user_states[ADMIN_ID] = f"awaiting_rejection_reason_{payment_id}"
        
        text = (
            f"✏️ <b>Custom Rejection Reason</b>\n\n"
            f"<b>Payment ID:</b> {payment_id}\n\n"
            f"Please type your custom rejection reason:\n\n"
            f"<i>This message will be sent directly to the user, "
            f"so please be professional and helpful.</i>"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_reject_{payment_id}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode="HTML")
    
    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id, "").startswith("awaiting_rejection_reason_"))
    def handle_custom_rejection_reason(message):
        """Handle custom rejection reason input"""
        if message.from_user.id != ADMIN_ID:
            return
        
        try:
            state = user_states[message.from_user.id]
            payment_id = state.split('_')[3]
            custom_reason = message.text.strip()
            
            if len(custom_reason) < 5:
                bot.reply_to(message, "Please provide a more detailed reason (at least 5 characters).")
                return
            
            # Clear state
            del user_states[message.from_user.id]
            
            # Create a temporary call object for process_payment_rejection
            class TempCall:
                def __init__(self, user_id, chat_id, message_id):
                    self.from_user = type('obj', (object,), {'id': user_id, 'first_name': 'Admin'})
                    self.message = type('obj', (object,), {'chat': type('obj', (object,), {'id': chat_id}), 'message_id': message_id})
                    
            temp_call = TempCall(message.from_user.id, message.chat.id, message.message_id)
            
            # Process rejection with custom reason
            process_payment_rejection(bot, temp_call, payment_id, custom_reason, is_custom=True)
            
        except Exception as e:
            print(f"Error handling custom rejection reason: {e}")
            bot.reply_to(message, "Error processing rejection. Please try again.")
    
    # Handle admin chat messages
    @bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and ADMIN_ID in admin_chat_sessions)
    def handle_admin_chat_message(message):
        """Handle messages from admin in active chat session"""
        try:
            session = admin_chat_sessions[ADMIN_ID]
            if not session['active']:
                return
            
            session_id = session['session_id']
            target_user_id = session['target_user_id']
            
            # Log the message
            log_chat_message(session_id, ADMIN_ID, 'admin', message.text)
            
            # Forward message to user
            forwarded_text = (
                f"💬 <b>Message from Admin</b>\n\n"
                f"{message.text}\n\n"
                f"<i>Reply to this message to respond to the admin.</i>"
            )
            
            try:
                sent_msg = bot.send_message(target_user_id, forwarded_text, parse_mode="HTML")
                
                # Confirm to admin
                bot.reply_to(
                    message,
                    f"✅ Message sent to user {target_user_id}",
                    reply_to_message_id=message.message_id
                )
                
                # Store message mapping for replies
                user_states[target_user_id] = f"replying_to_admin_{session_id}"
                
            except Exception as e:
                bot.reply_to(message, f"❌ Could not send message to user: {str(e)}")
                print(f"Could not forward message to user {target_user_id}: {e}")
            
        except Exception as e:
            print(f"Error handling admin chat message: {e}")
    
    # Handle user replies to admin messages
    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id, "").startswith("replying_to_admin_"))
    def handle_user_reply_to_admin(message):
        """Handle user replies to admin messages"""
        try:
            state = user_states[message.from_user.id]
            session_id = state.split('_')[3]
            user_id = message.from_user.id
            
            # Log the user's reply
            log_chat_message(session_id, user_id, 'user', message.text)
            
            # Forward reply to admin
            reply_text = (
                f"💬 <b>User Reply</b>\n\n"
                f"<b>From:</b> {message.from_user.first_name} (ID: {user_id})\n"
                f"<b>Message:</b>\n{message.text}\n\n"
                f"<i>Reply to continue the conversation.</i>"
            )
            
            try:
                bot.send_message(ADMIN_ID, reply_text, parse_mode="HTML")
                
                # Confirm to user
                bot.reply_to(
                    message,
                    "✅ Your message has been sent to the admin. They will respond shortly.",
                    reply_to_message_id=message.message_id
                )
                
            except Exception as e:
                bot.reply_to(message, "❌ Could not send your message to admin. Please try again.")
                print(f"Could not forward user reply to admin: {e}")
            
        except Exception as e:
            print(f"Error handling user reply: {e}")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("end_chat_"))
    def end_admin_chat(call):
        """End admin chat session"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        
        try:
            session_id = call.data.split('_')[2]
            
            # Update session status
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE admin_chat_sessions 
                    SET status = 'ended' 
                    WHERE session_id = ? AND admin_id = ?
                """, (session_id, ADMIN_ID))
                
                # Get user_id for notification
                user_id = cursor.execute("""
                    SELECT user_id FROM admin_chat_sessions 
                    WHERE session_id = ?
                """, (session_id,)).fetchone()
                
                conn.commit()
            
            # Clear admin session
            if ADMIN_ID in admin_chat_sessions:
                admin_chat_sessions[ADMIN_ID]['active'] = False
            
            # Notify user that chat ended
            if user_id:
                try:
                    bot.send_message(
                        user_id[0],
                        "📞 <b>Admin Chat Ended</b>\n\n"
                        "The administrator has ended the chat session. "
                        "Thank you for your time!\n\n"
                        "If you need further assistance, please use the support system.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass  # User might have blocked bot
            
            text = (
                f"✅ <b>Chat Session Ended</b>\n\n"
                f"<b>Session ID:</b> <code>{session_id}</code>\n\n"
                f"The chat session has been terminated successfully."
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("💬 Start New Chat", callback_data="admin_user_chat"))
            markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                reply_markup=markup, parse_mode="HTML")
            
            bot.answer_callback_query(call.id, "Chat session ended")
            
        except Exception as e:
            print(f"Error ending chat: {e}")
            bot.answer_callback_query(call.id, "Error ending chat", show_alert=True)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("chat_history_"))
    def show_chat_history(call):
        """Show chat history for a session"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        
        try:
            session_id = call.data.split('_')[2]
            
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                
                # Get session info
                session_info = cursor.execute("""
                    SELECT admin_id, user_id, created_at, status 
                    FROM admin_chat_sessions 
                    WHERE session_id = ?
                """, (session_id,)).fetchone()
                
                if not session_info:
                    bot.answer_callback_query(call.id, "Session not found", show_alert=True)
                    return
                
                # Get messages
                messages = cursor.execute("""
                    SELECT sender_id, sender_type, message_text, sent_at
                    FROM admin_chat_messages 
                    WHERE session_id = ?
                    ORDER BY sent_at ASC
                    LIMIT 20
                """, (session_id,)).fetchall()
            
            admin_id, user_id, created_at, status = session_info
            
            text = (
                f"📜 <b>Chat History</b>\n\n"
                f"<b>Session:</b> <code>{session_id}</code>\n"
                f"<b>User:</b> {user_id}\n"
                f"<b>Started:</b> {created_at[:19]}\n"
                f"<b>Status:</b> {status}\n\n"
                f"<b>Messages:</b>\n"
            )
            
            if not messages:
                text += "<i>No messages yet.</i>"
            else:
                for sender_id, sender_type, message_text, sent_at in messages[-10:]:  # Last 10 messages
                    sender_name = "👑 Admin" if sender_type == "admin" else f"👤 User {sender_id}"
                    time_str = sent_at[11:16]  # HH:MM
                    text += f"\n<b>{time_str} {sender_name}:</b>\n{message_text[:100]}\n"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data=f"chat_history_{session_id}"))
            markup.add(types.InlineKeyboardButton("⬅️ Back to Chat", callback_data=f"select_user_{user_id}"))
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                reply_markup=markup, parse_mode="HTML")
            
        except Exception as e:
            print(f"Error showing chat history: {e}")
            bot.answer_callback_query(call.id, "Error loading history", show_alert=True)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("show_more_users_"))
    def show_more_users(call):
        """Show more users with pagination"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        
        try:
            offset = int(call.data.split('_')[3])
            users = get_all_users_for_admin()
            
            text = f"👥 <b>Users List (Showing {offset + 1}-{min(offset + 10, len(users))} of {len(users)})</b>\n\n"
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            # Show next 10 users
            for user in users[offset:offset + 10]:
                user_id, username, join_date, is_active, total_orders = user
                display_name = username if username else f"User {user_id}"
                status_emoji = "🟢" if is_active else "🔴"
                
                user_info = f"{status_emoji} {display_name} | Orders: {total_orders}"
                markup.add(types.InlineKeyboardButton(
                    user_info,
                    callback_data=f"select_user_{user_id}"
                ))
            
            # Pagination controls
            nav_buttons = []
            if offset > 0:
                nav_buttons.append(types.InlineKeyboardButton(
                    "⬅️ Previous", 
                    callback_data=f"show_more_users_{offset - 10}"
                ))
            
            if offset + 10 < len(users):
                nav_buttons.append(types.InlineKeyboardButton(
                    "Next ➡️", 
                    callback_data=f"show_more_users_{offset + 10}"
                ))
            
            if nav_buttons:
                if len(nav_buttons) == 2:
                    markup.row(*nav_buttons)
                else:
                    markup.add(*nav_buttons)
            
            markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                reply_markup=markup, parse_mode="HTML")
            
        except Exception as e:
            print(f"Error showing more users: {e}")
            bot.answer_callback_query(call.id, "Error loading users", show_alert=True)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("reject_quick_"))
    def quick_reject_payment(call):
        """Quick reject payment without reason"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        
        payment_id = call.data.split('_')[2]
        process_payment_rejection(bot, call, payment_id, "Payment rejected by admin.")

def start_direct_admin_chat(bot, admin_id, target_user_id, chat_id, message_id):
    """Start direct admin chat with user"""
    try:
        # Create chat session
        session_id = create_chat_session(admin_id, target_user_id)
        admin_chat_sessions[admin_id] = {
            'session_id': session_id,
            'target_user_id': target_user_id,
            'active': True
        }
        
        # Get user info for display
        try:
            user_info = bot.get_chat(target_user_id)
            name = user_info.first_name or "Unknown"
            username = f"@{user_info.username}" if user_info.username else ""
        except:
            name = "Unknown User"
            username = ""
        
        text = (
            f"💬 <b>Admin Chat Session Started</b>\n\n"
            f"<b>Chatting with:</b> {name} {username} (ID: {target_user_id})\n"
            f"<b>Session ID:</b> <code>{session_id}</code>\n\n"
            f"You can now send messages directly to this user. "
            f"Type your message and it will be forwarded to them.\n\n"
            f"<i>Commands:</i>\n"
            f"• Send any message to forward to user\n"
            f"• Use buttons below to end chat or view history"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📜 Chat History", callback_data=f"chat_history_{session_id}"),
            types.InlineKeyboardButton("🚫 End Chat", callback_data=f"end_chat_{session_id}")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Users", callback_data="admin_user_chat"))
        
        bot.edit_message_text(text, chat_id, message_id, 
                            reply_markup=markup, parse_mode="HTML")
        
        # Notify user about incoming admin chat
        try:
            bot.send_message(
                target_user_id,
                "📞 <b>Admin Contact</b>\n\n"
                "An administrator wants to chat with you. "
                "You will receive their messages here and can reply directly.\n\n"
                "This is a direct line to support - please be respectful! 🙏",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Could not notify user {target_user_id}: {e}")
            
    except Exception as e:
        print(f"Error starting direct chat: {e}")
        bot.send_message(chat_id, f"❌ Error starting chat with user {target_user_id}: {str(e)}")

def process_payment_rejection(bot, call, payment_id, reason, is_custom=False):
    """Process payment rejection with detailed reason"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            
            # Get order details
            order_data = cursor.execute(
                "SELECT user_id, payment_status, item_name FROM orders WHERE order_id = ?", 
                (payment_id,)
            ).fetchone()
            
            if not order_data:
                if not is_custom:
                    bot.edit_message_text(
                        f"Order `{payment_id}` not found.", 
                        call.message.chat.id, 
                        call.message.message_id, 
                        parse_mode="Markdown"
                    )
                else:
                    bot.send_message(call.message.chat.id, f"Order `{payment_id}` not found.")
                return
            
            user_id, payment_status, item_name = order_data
            
            if payment_status != "PENDING_APPROVAL":
                if not is_custom:
                    bot.answer_callback_query(call.id, "This order has already been processed.", show_alert=True)
                else:
                    bot.send_message(call.message.chat.id, "This order has already been processed.")
                return
            
            # Update order status
            cursor.execute("UPDATE orders SET payment_status = ? WHERE order_id = ?", ("REJECTED", payment_id))
            
            # Log the decision
            log_payment_decision(payment_id, ADMIN_ID, "rejected", reason)
            
            conn.commit()
        
        # Send detailed rejection to user
        user_msg = (
            f"❌ <b>Payment Rejected</b>\n\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n"
            f"<b>Item:</b> {item_name}\n\n"
            f"<b>Reason for rejection:</b>\n{reason}\n\n"
            f"If you believe this is an error or need assistance, "
            f"please contact support with your Payment ID.\n\n"
            f"<i>You can make a new order if needed.</i>"
        )
        
        send_random_animation(bot, user_id, kind="reject", caption=user_msg, parse_mode="HTML")
        
        # Update admin message
        admin_update = (
            f"<b>Action:</b> Rejected by {call.from_user.first_name} ❌\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Time:</b> {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}"
        )
        
        if not is_custom:
            # For callback queries, edit the existing message
            original_text = call.message.text or call.message.caption
            bot.edit_message_text(
                original_text + f"\n\n{admin_update}", 
                call.message.chat.id, 
                call.message.message_id, 
                reply_markup=None, 
                parse_mode="HTML"
            )
            bot.answer_callback_query(call.id, f"Payment {payment_id} rejected with reason.")
        else:
            # For text messages, send new message
            bot.send_message(
                call.message.chat.id,
                f"✅ Payment {payment_id} has been rejected.\n\n{admin_update}",
                parse_mode="HTML"
            )
        
    except Exception as e:
        print(f"Error processing payment rejection: {e}")
        if not is_custom:
            bot.answer_callback_query(call.id, "Error processing rejection", show_alert=True)
        else:
            bot.send_message(call.message.chat.id, "Error processing rejection.")

def init_admin_communication_db():
    """Initialize database tables for admin communication"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # Admin-user chat sessions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_chat_sessions (
                session_id TEXT PRIMARY KEY,
                admin_id INTEGER,
                user_id INTEGER,
                started_at TEXT,
                last_activity TEXT,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        # Chat messages history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                sender_id INTEGER,
                sender_type TEXT,
                message_text TEXT,
                sent_at TEXT,
                FOREIGN KEY (session_id) REFERENCES admin_chat_sessions(session_id)
            )
        ''')
        
        # Payment remarks and responses
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id TEXT,
                admin_id INTEGER,
                response_type TEXT,
                remarks TEXT,
                responded_at TEXT
            )
        ''')
        
        conn.commit()

def register_enhanced_admin_handlers(bot):
    """Register all enhanced admin communication handlers"""
    
    init_admin_communication_db()
    
    @bot.callback_query_handler(func=lambda call: call.data == "owner_user_chat")
    def owner_user_chat_menu(call):
        """Owner-only user chat interface"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner access only", show_alert=True)
            return
            
        text = (
            "👨‍💼 <b>Owner - User Communication</b>\n\n"
            "Search and connect with users:\n\n"
            "🔍 <b>Search Options:</b>\n"
            "• Search by Username/Name\n"
            "• Search by User ID\n"
            "• Active chat sessions\n\n"
            "Choose an option below:"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("� Search Username", callback_data="search_username"),
            types.InlineKeyboardButton("� Search User ID", callback_data="search_user_id"),
            types.InlineKeyboardButton("💬 Active Chats", callback_data="active_chats"),
            types.InlineKeyboardButton("⬅️ Back to Owner Panel", callback_data="owner_panel")
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data == "search_user_id")
    def search_user_id_prompt(call):
        """Prompt owner to enter user ID"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner access only", show_alert=True)
            return
            
        user_states[call.from_user.id] = "awaiting_user_id_search"
        
        text = (
            "🔍 <b>Search User by ID</b>\n\n"
            "Enter the User ID you want to chat with:\n\n"
            "<i>Example: 123456789</i>\n\n"
            "💡 <b>Tips:</b>\n"
            "• User ID is their Telegram user ID\n"
            "• You can find it in orders or user logs\n"
            "• Make sure the user exists in your system"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="owner_user_chat"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data == "search_username")
    def search_username_prompt(call):
        """Prompt owner to enter username to search"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner access only", show_alert=True)
            return
            
        user_states[call.from_user.id] = "awaiting_username_search"
        
        text = (
            "👤 <b>Search User by Username</b>\n\n"
            "Enter the username or name to search for:\n\n"
            "<i>Examples:</i>\n"
            "• @john_doe (with @)\n"
            "• john_doe (without @)\n"
            "• John Smith (first name)\n"
            "• john (partial username)\n\n"
            "💡 <b>Tips:</b>\n"
            "• Search will find matching usernames and names\n"
            "• Results show users who have used the bot\n"
            "• Use partial names for broader search"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="owner_user_chat"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")
    
    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_username_search")
    def handle_username_search(message):
        """Handle username search and show results"""
        if not is_owner(message.from_user.id):
            return
            
        search_term = message.text.strip().lower()
        if search_term.startswith('@'):
            search_term = search_term[1:]  # Remove @ if present
        
        if len(search_term) < 2:
            bot.reply_to(message, "❌ Search term too short. Please enter at least 2 characters.")
            return
        
        # Get users from orders and try to match usernames
        matching_users = []
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            # Get unique user IDs who have made orders
            user_ids = cursor.execute(
                "SELECT DISTINCT user_id FROM orders ORDER BY creation_date DESC LIMIT 100"
            ).fetchall()
        
        # Search through users to find matches
        for (user_id,) in user_ids:
            try:
                user_info = bot.get_chat(user_id)
                
                # Check username match
                username_match = False
                if user_info.username and search_term in user_info.username.lower():
                    username_match = True
                
                # Check first name match
                name_match = False
                if user_info.first_name and search_term in user_info.first_name.lower():
                    name_match = True
                
                # Check last name match  
                last_name_match = False
                if user_info.last_name and search_term in user_info.last_name.lower():
                    last_name_match = True
                
                if username_match or name_match or last_name_match:
                    matching_users.append({
                        'user_id': user_id,
                        'first_name': user_info.first_name or "Unknown",
                        'last_name': user_info.last_name or "",
                        'username': user_info.username or "",
                    })
                
                # Limit results to prevent spam
                if len(matching_users) >= 10:
                    break
                    
            except Exception:
                # Skip users we can't get info for
                continue
        
        # Clear search state
        del user_states[message.from_user.id]
        
        # Show results
        if not matching_users:
            text = (
                f"🔍 <b>No Users Found</b>\n\n"
                f"No users found matching: <code>{search_term}</code>\n\n"
                f"• Try a different search term\n"
                f"• Check spelling\n"
                f"• Use partial names for broader search\n"
                f"• Make sure the user has used the bot before"
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Search Again", callback_data="search_username"))
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_user_chat"))
            
        else:
            text = f"👥 <b>Search Results</b>\n\nFound {len(matching_users)} user(s) matching: <code>{search_term}</code>\n\nSelect a user to chat with:\n\n"
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            for user in matching_users:
                full_name = f"{user['first_name']} {user['last_name']}".strip()
                username_display = f"@{user['username']}" if user['username'] else "No username"
                
                button_text = f"👤 {full_name} ({username_display}) - ID: {user['user_id']}"
                
                # Truncate button text if too long
                if len(button_text) > 60:
                    button_text = button_text[:57] + "..."
                
                markup.add(types.InlineKeyboardButton(
                    button_text, callback_data=f"chat_user_{user['user_id']}")
                )
            
            markup.add(types.InlineKeyboardButton("🔄 Search Again", callback_data="search_username"))
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_user_chat"))
        
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")
    
    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_user_id_search")
    def handle_user_id_search(message):
        """Handle user ID search input"""
        if not is_owner(message.from_user.id):
            return
            
        try:
            target_user_id = int(message.text.strip())
        except ValueError:
            bot.reply_to(message, "❌ Invalid User ID. Please enter a valid number.")
            return
            
        # Check if user exists in database
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            user_exists = cursor.execute(
                "SELECT COUNT(*) FROM orders WHERE user_id = ? LIMIT 1", 
                (target_user_id,)
            ).fetchone()[0]
        
        if not user_exists:
            bot.reply_to(message, 
                        f"❌ User ID {target_user_id} not found in system.\n"
                        f"Make sure the user has interacted with the bot before.")
            return
        
        # Start chat session
        start_admin_user_chat(bot, message.from_user.id, target_user_id, message.chat.id)
        
        # Clear state
        del user_states[message.from_user.id]
    
    @bot.callback_query_handler(func=lambda call: call.data == "recent_users")
    def show_recent_users(call):
        """Show recent users for owner to select"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner access only", show_alert=True)
            return
            
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            recent_users = cursor.execute('''
                SELECT DISTINCT user_id, MAX(creation_date) as last_order
                FROM orders 
                GROUP BY user_id 
                ORDER BY last_order DESC 
                LIMIT 10
            ''').fetchall()
        
        if not recent_users:
            text = "📭 <b>No Recent Users</b>\n\nNo users found in the system."
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_user_chat"))
        else:
            text = "👥 <b>Recent Users</b>\n\nSelect a user to chat with:\n\n"
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            for user_id, last_order in recent_users:
                # Get user info
                try:
                    user_info = bot.get_chat(user_id)
                    name = user_info.first_name or "Unknown"
                    username = f"@{user_info.username}" if user_info.username else ""
                except:
                    name = "Unknown User"
                    username = ""
                
                button_text = f"👤 {name} {username} - ID: {user_id}"
                markup.add(types.InlineKeyboardButton(
                    button_text, callback_data=f"chat_user_{user_id}")
                )
            
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_user_chat"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("chat_user_"))
    def start_user_chat(call):
        """Start chat with selected user"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner access only", show_alert=True)
            return
            
        user_id = int(call.data.split('_')[2])
        start_admin_user_chat(bot, call.from_user.id, user_id, call.message.chat.id)

def is_owner(user_id):
    """Check if user is the owner (main admin)"""
    return user_id == ADMIN_ID

def start_admin_user_chat(bot, admin_id, user_id, admin_chat_id):
    """Start or resume admin-user chat session"""
    import uuid
    
    session_id = str(uuid.uuid4())[:8]
    
    # Create session in database
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO admin_chat_sessions (session_id, admin_id, user_id, started_at, last_activity)
            VALUES (?, ?, ?, ?, ?)
        ''', (session_id, admin_id, user_id, datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat()))
        conn.commit()
    
    # Store active chat
    active_admin_chats[admin_id] = {
        'session_id': session_id,
        'user_id': user_id,
        'admin_chat_id': admin_chat_id
    }
    
    # Get user info
    try:
        user_info = bot.get_chat(user_id)
        name = user_info.first_name or "Unknown"
        username = f"@{user_info.username}" if user_info.username else ""
    except:
        name = "Unknown User"
        username = ""
    
    # Notify admin
    admin_text = (
        f"💬 <b>Chat Session Started</b>\n\n"
        f"👤 <b>User:</b> {name} {username}\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"🔗 <b>Session ID:</b> <code>{session_id}</code>\n\n"
        f"You can now send messages directly to this user.\n"
        f"Type your message and it will be forwarded to them.\n\n"
        f"Use the buttons below to manage the chat:"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("❌ End Chat", callback_data=f"end_chat_{session_id}"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="owner_user_chat")
    )
    
    bot.send_message(admin_chat_id, admin_text, reply_markup=markup, parse_mode="HTML")
    
    # Notify user
    user_text = (
        f"📞 <b>Admin Contact</b>\n\n"
        f"An administrator wants to chat with you.\n"
        f"You can reply to this conversation.\n\n"
        f"Session started: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    
    try:
        bot.send_message(user_id, user_text, parse_mode="HTML")
    except:
        bot.send_message(admin_chat_id, f"⚠️ Could not notify user {user_id} (blocked or invalid)")

def register_admin_message_handlers(bot):
    """Register handlers for admin messaging"""
    
    @bot.message_handler(func=lambda message: message.from_user.id in active_admin_chats)
    def handle_admin_message(message):
        """Handle messages from admin in active chat"""
        if not is_owner(message.from_user.id):
            return
            
        chat_info = active_admin_chats[message.from_user.id]
        session_id = chat_info['session_id']
        user_id = chat_info['user_id']
        
        # Save message to database
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO admin_chat_messages (session_id, sender_id, sender_type, message_text, sent_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (session_id, message.from_user.id, 'admin', message.text, datetime.now(UTC).isoformat()))
            
            # Update last activity
            cursor.execute('''
                UPDATE admin_chat_sessions SET last_activity = ? WHERE session_id = ?
            ''', (datetime.now(UTC).isoformat(), session_id))
            conn.commit()
        
        # Forward message to user
        try:
            user_msg = (
                f"📨 <b>Message from Admin</b>\n\n"
                f"{message.text}\n\n"
                f"<i>Reply to this message to respond to the admin.</i>"
            )
            bot.send_message(user_id, user_msg, parse_mode="HTML")
            
            # Confirm to admin
            bot.reply_to(message, f"✅ Message sent to user {user_id}")
            
        except Exception as e:
            bot.reply_to(message, f"❌ Failed to send message: {str(e)}")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("end_chat_"))
    def end_chat_session(call):
        """End active chat session"""
        if not is_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Owner access only", show_alert=True)
            return
            
        session_id = call.data.split('_')[2]
        
        # Update session status
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE admin_chat_sessions SET status = 'ended' WHERE session_id = ?
            ''', (session_id,))
            conn.commit()
        
        # Remove from active chats
        if call.from_user.id in active_admin_chats:
            del active_admin_chats[call.from_user.id]
        
        bot.answer_callback_query(call.id, "Chat session ended")
        
        text = (
            f"❌ <b>Chat Session Ended</b>\n\n"
            f"Session ID: <code>{session_id}</code>\n"
            f"Ended at: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to User Chat", callback_data="owner_user_chat"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")