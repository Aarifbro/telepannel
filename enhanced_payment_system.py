"""
Enhanced Payment Approval System
===============================
Complete payment workflow with admin remarks, screenshot validation, and direct communication
"""

from telebot import types
import sqlite3
import json
from datetime import datetime, UTC
from config import DB_NAME, ADMIN_ID
from helpers import send_random_animation

# Store payment states and admin remarks
payment_states = {}
admin_remarks_states = {}

def init_enhanced_payment_db():
    """Initialize enhanced payment system database tables"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # Enhanced payment tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS enhanced_payments (
                payment_id TEXT PRIMARY KEY,
                user_id INTEGER,
                order_id TEXT,
                screenshot_file_id TEXT,
                admin_request_remarks TEXT,
                admin_response_remarks TEXT,
                status TEXT DEFAULT 'awaiting_screenshot',
                created_at TEXT,
                updated_at TEXT,
                processed_by INTEGER
            )
        ''')
        
        # Payment communication log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_communications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id TEXT,
                sender_type TEXT,
                sender_id INTEGER,
                message_type TEXT,
                message_content TEXT,
                sent_at TEXT,
                FOREIGN KEY (payment_id) REFERENCES enhanced_payments(payment_id)
            )
        ''')
        
        conn.commit()

def register_enhanced_payment_handlers(bot):
    """Register all enhanced payment approval handlers"""
    
    init_enhanced_payment_db()
    
    # --- SCREENSHOT REQUEST WITH ADMIN REMARKS ---
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("enhanced_pay_"))
    def start_enhanced_payment(call):
        """Start enhanced payment process with admin remarks"""
        payment_id = call.data.replace("enhanced_pay_", "")
        user_id = call.from_user.id
        
        # Store payment in enhanced system
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO enhanced_payments 
                (payment_id, user_id, status, created_at, updated_at)
                VALUES (?, ?, 'requesting_screenshot', ?, ?)
            ''', (payment_id, user_id, datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat()))
            conn.commit()
        
        # Request screenshot with professional message
        text = (
            f"📷 <b>Payment Verification Required</b>\n\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n\n"
            f"To process your payment, please provide proof of transaction:\n\n"
            f"📸 <b>Required Screenshot Should Include:</b>\n"
            f"• ✅ Transaction confirmation\n"
            f"• ✅ Payment amount clearly visible\n"
            f"• ✅ Payment ID in memo/reference\n"
            f"• ✅ Transaction date and time\n"
            f"• ✅ Clear and readable image\n\n"
            f"<b>Next Steps:</b>\n"
            f"1️⃣ Take a clear screenshot of your transaction\n"
            f"2️⃣ Upload the image here\n"
            f"3️⃣ Wait for admin verification\n\n"
            f"<i>Our admin will review your payment within minutes!</i>"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📷 Upload Screenshot", callback_data=f"upload_enhanced_ss_{payment_id}"),
            types.InlineKeyboardButton("❓ Need Help?", callback_data=f"payment_help_{payment_id}"),
            types.InlineKeyboardButton("❌ Cancel Payment", callback_data="main_menu")
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("upload_enhanced_ss_"))
    def request_enhanced_screenshot(call):
        """Handle enhanced screenshot upload request"""
        payment_id = call.data.replace("upload_enhanced_ss_", "")
        
        # Set user state for screenshot upload
        if not hasattr(bot, '_enhanced_awaiting_ss'):
            bot._enhanced_awaiting_ss = {}
        bot._enhanced_awaiting_ss[call.from_user.id] = payment_id
        
        text = (
            f"📱 <b>Upload Your Payment Screenshot</b>\n\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n\n"
            f"📸 <b>Please send your screenshot as a photo</b>\n\n"
            f"✅ <b>Good Screenshot Examples:</b>\n"
            f"• Bank app confirmation screen\n"
            f"• Wallet transaction details\n"
            f"• Receipt with transaction ID\n"
            f"• Exchange confirmation page\n\n"
            f"❌ <b>Avoid These:</b>\n"
            f"• Blurry or unclear images\n"
            f"• Partial screenshots\n"
            f"• Screenshots without payment ID\n"
            f"• Old or unrelated transactions\n\n"
            f"<i>After uploading, you'll be able to submit for review!</i>"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=f"enhanced_pay_{payment_id}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")
    
    @bot.message_handler(content_types=['photo'])
    def capture_enhanced_screenshot(message):
        """Capture enhanced payment screenshot"""
        pending = getattr(bot, '_enhanced_awaiting_ss', {})
        payment_id = pending.get(message.from_user.id)
        if not payment_id:
            return
            
        file_id = message.photo[-1].file_id
        
        # Store screenshot in enhanced system
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE enhanced_payments 
                SET screenshot_file_id = ?, status = 'screenshot_uploaded', updated_at = ?
                WHERE payment_id = ? AND user_id = ?
            ''', (file_id, datetime.now(UTC).isoformat(), payment_id, message.from_user.id))
            
            # Log the screenshot upload
            cursor.execute('''
                INSERT INTO payment_communications 
                (payment_id, sender_type, sender_id, message_type, message_content, sent_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (payment_id, 'user', message.from_user.id, 'screenshot', file_id, datetime.now(UTC).isoformat()))
            
            conn.commit()
        
        # Clear waiting state
        del bot._enhanced_awaiting_ss[message.from_user.id]
        
        # Show submission options
        text = (
            f"✅ <b>Screenshot Uploaded Successfully!</b>\n\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n\n"
            f"📸 Your screenshot has been received and is ready for review.\n\n"
            f"<b>What happens next:</b>\n"
            f"1️⃣ Click 'Submit for Review' below\n"
            f"2️⃣ Admin will verify your payment\n"
            f"3️⃣ You'll receive approval/feedback\n"
            f"4️⃣ Your order will be processed\n\n"
            f"<i>Ready to submit for admin review?</i>"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🚀 Submit for Review", callback_data=f"submit_enhanced_{payment_id}"),
            types.InlineKeyboardButton("📷 Upload Different Screenshot", callback_data=f"upload_enhanced_ss_{payment_id}"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="main_menu")
        )
        
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")
    
    # --- ADMIN REVIEW SYSTEM ---
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("submit_enhanced_"))
    def submit_for_enhanced_review(call):
        """Submit payment for enhanced admin review"""
        payment_id = call.data.replace("submit_enhanced_", "")
        user_id = call.from_user.id
        
        # Update status to pending review
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE enhanced_payments 
                SET status = 'pending_review', updated_at = ?
                WHERE payment_id = ? AND user_id = ?
            ''', (datetime.now(UTC).isoformat(), payment_id, user_id))
            
            # Get payment details
            payment_data = cursor.execute('''
                SELECT ep.*, o.item_name, o.price_usd 
                FROM enhanced_payments ep
                LEFT JOIN orders o ON ep.payment_id = o.order_id
                WHERE ep.payment_id = ?
            ''', (payment_id,)).fetchone()
            
            conn.commit()
        
        if not payment_data:
            bot.answer_callback_query(call.id, "Payment not found", show_alert=True)
            return
        
        # Get user info
        try:
            user_info = bot.get_chat(user_id)
            user_name = f"{user_info.first_name or 'Unknown'} {user_info.last_name or ''}".strip()
            username = f"@{user_info.username}" if user_info.username else "No username"
        except:
            user_name = "Unknown User"
            username = "No username"
        
        # Send enhanced admin notification
        admin_text = (
            f"💳 <b>Enhanced Payment Review Required</b>\n\n"
            f"👤 <b>User:</b> {user_name} ({username})\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
            f"📄 <b>Payment ID:</b> <code>{payment_id}</code>\n"
            f"🛍️ <b>Item:</b> {payment_data[9] or 'Unknown'}\n"
            f"💰 <b>Amount:</b> ${payment_data[10] or 'Unknown'}\n"
            f"⏰ <b>Submitted:</b> {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            f"📸 <b>Screenshot provided - ready for verification</b>\n\n"
            f"Please review the payment and choose an action:"
        )
        
        admin_markup = types.InlineKeyboardMarkup(row_width=2)
        admin_markup.add(
            types.InlineKeyboardButton("✅ Quick Approve", callback_data=f"quick_approve_{payment_id}"),
            types.InlineKeyboardButton("❌ Quick Reject", callback_data=f"quick_reject_enhanced_{payment_id}")
        )
        admin_markup.add(
            types.InlineKeyboardButton("💬 Approve with Message", callback_data=f"approve_with_remarks_{payment_id}"),
            types.InlineKeyboardButton("📝 Reject with Reason", callback_data=f"reject_with_remarks_{payment_id}")
        )
        admin_markup.add(
            types.InlineKeyboardButton("💬 Chat with User", callback_data=f"admin_chat_user_{user_id}"),
            types.InlineKeyboardButton("🔍 View Details", callback_data=f"view_payment_details_{payment_id}")
        )
        
        # Send screenshot with admin controls
        screenshot_file_id = payment_data[3]  # screenshot_file_id
        try:
            bot.send_photo(ADMIN_ID, screenshot_file_id, 
                          caption=admin_text, reply_markup=admin_markup, parse_mode="HTML")
        except Exception as e:
            bot.send_message(ADMIN_ID, 
                           admin_text + f"\n\n❌ <b>Screenshot failed to load:</b> {str(e)}", 
                           reply_markup=admin_markup, parse_mode="HTML")
        
        # Confirm to user
        user_text = (
            f"🚀 <b>Payment Submitted for Review</b>\n\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n\n"
            f"✅ Your payment screenshot has been submitted to our admin team.\n\n"
            f"<b>What's Next:</b>\n"
            f"• Admin will review within minutes\n"
            f"• You'll get instant notification\n"
            f"• Approved payments are processed immediately\n"
            f"• Any questions will be communicated directly\n\n"
            f"<b>Status:</b> 🔄 Under Review\n\n"
            f"<i>Thank you for your patience!</i>"
        )
        
        bot.edit_message_text(user_text, call.message.chat.id, call.message.message_id, parse_mode="HTML")

    # --- APPROVAL WITH REMARKS SYSTEM ---
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("approve_with_remarks_"))
    def approve_with_remarks_prompt(call):
        """Prompt admin for approval remarks"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Admin access only", show_alert=True)
            return
            
        payment_id = call.data.replace("approve_with_remarks_", "")
        admin_remarks_states[call.from_user.id] = f"approval_remarks_{payment_id}"
        
        text = (
            f"✅ <b>Approve Payment with Custom Message</b>\n\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n\n"
            f"Enter your approval message for the user:\n\n"
            f"💡 <b>Suggested Messages:</b>\n"
            f"• Thank you for your trust! Payment verified ✅\n"
            f"• Payment confirmed! Thank you for choosing us 🙏\n"
            f"• Verified and approved! Welcome to our service ⭐\n"
            f"• Payment successful! Your order is being processed 🚀\n"
            f"• Thank you for your purchase! Enjoy your order 🎉\n\n"
            f"<i>Type your custom approval message:</i>"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_payment_menu_{payment_id}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")
    
    @bot.message_handler(func=lambda message: admin_remarks_states.get(message.from_user.id, "").startswith("approval_remarks_"))
    def handle_approval_remarks(message):
        """Handle admin approval remarks input"""
        if message.from_user.id != ADMIN_ID:
            return
            
        state = admin_remarks_states[message.from_user.id]
        payment_id = state.replace("approval_remarks_", "")
        approval_message = message.text.strip()
        
        if len(approval_message) < 3:
            bot.reply_to(message, "❌ Approval message too short. Please provide at least 3 characters.")
            return
        
        # Process approval with custom message
        process_enhanced_approval(bot, message, payment_id, approval_message)
        
        # Clear state
        del admin_remarks_states[message.from_user.id]
    
    # --- REJECTION WITH REASONS SYSTEM ---
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("reject_with_remarks_"))
    def reject_with_remarks_menu(call):
        """Show rejection reasons menu"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Admin access only", show_alert=True)
            return
            
        payment_id = call.data.replace("reject_with_remarks_", "")
        
        text = (
            f"❌ <b>Reject Payment with Reason</b>\n\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n\n"
            f"Choose a rejection reason or provide custom feedback:\n\n"
            f"Select the most appropriate reason:"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        # Common rejection reasons
        reasons = [
            ("📷 Screenshot unclear/invalid", "Screenshot is unclear, invalid, or doesn't show payment details"),
            ("💰 Payment amount mismatch", "Payment amount doesn't match the required amount"),
            ("🆔 Payment ID not found", "Payment ID not found in transaction memo/reference"),
            ("⏰ Transaction too old", "Transaction is too old or doesn't match timeline"),
            ("🔍 Cannot verify transaction", "Unable to verify this transaction in our system"),
            ("🚫 Suspicious activity", "Transaction appears suspicious and requires further verification"),
        ]
        
        for reason_short, reason_full in reasons:
            markup.add(types.InlineKeyboardButton(
                reason_short, 
                callback_data=f"reject_reason_{payment_id}_{reason_full.replace(' ', '_')[:50]}"
            ))
        
        markup.add(
            types.InlineKeyboardButton("✏️ Custom Reason", callback_data=f"custom_reject_reason_{payment_id}"),
            types.InlineKeyboardButton("⬅️ Back", callback_data=f"admin_payment_menu_{payment_id}")
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("reject_reason_"))
    def process_predefined_rejection(call):
        """Process predefined rejection reason"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Admin access only", show_alert=True)
            return
            
        # Parse callback data
        data_parts = call.data.split('_', 3)  # reject_reason_{payment_id}_{reason}
        payment_id = data_parts[2]
        reason = data_parts[3].replace('_', ' ') if len(data_parts) > 3 else "Invalid payment"
        
        # Process rejection
        process_enhanced_rejection(bot, call, payment_id, reason)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("custom_reject_reason_"))
    def custom_reject_reason_prompt(call):
        """Prompt for custom rejection reason"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Admin access only", show_alert=True)
            return
            
        payment_id = call.data.replace("custom_reject_reason_", "")
        admin_remarks_states[call.from_user.id] = f"rejection_remarks_{payment_id}"
        
        text = (
            f"✏️ <b>Custom Rejection Reason</b>\n\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n\n"
            f"Please provide a detailed reason for rejecting this payment:\n\n"
            f"<b>Be specific and helpful:</b>\n"
            f"• Explain what's wrong with the screenshot\n"
            f"• Provide guidance on how to fix it\n"
            f"• Be professional and constructive\n\n"
            f"<i>Type your custom rejection reason:</i>"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=f"reject_with_remarks_{payment_id}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")
    
    @bot.message_handler(func=lambda message: admin_remarks_states.get(message.from_user.id, "").startswith("rejection_remarks_"))
    def handle_rejection_remarks(message):
        """Handle custom rejection remarks"""
        if message.from_user.id != ADMIN_ID:
            return
            
        state = admin_remarks_states[message.from_user.id]
        payment_id = state.replace("rejection_remarks_", "")
        rejection_reason = message.text.strip()
        
        if len(rejection_reason) < 5:
            bot.reply_to(message, "❌ Rejection reason too short. Please provide at least 5 characters.")
            return
        
        # Process rejection
        process_enhanced_rejection(bot, message, payment_id, rejection_reason)
        
        # Clear state
        del admin_remarks_states[message.from_user.id]

def process_enhanced_approval(bot, context, payment_id, approval_message):
    """Process enhanced payment approval with custom message"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            
            # Get payment details
            payment_data = cursor.execute('''
                SELECT ep.user_id, ep.screenshot_file_id, o.item_name, o.item_details
                FROM enhanced_payments ep
                LEFT JOIN orders o ON ep.payment_id = o.order_id
                WHERE ep.payment_id = ?
            ''', (payment_id,)).fetchone()
            
            if not payment_data:
                bot.reply_to(context, f"❌ Payment {payment_id} not found.")
                return
            
            user_id, screenshot_file_id, item_name, item_details_str = payment_data
            
            # Update payment status
            cursor.execute('''
                UPDATE enhanced_payments 
                SET status = 'approved', admin_response_remarks = ?, processed_by = ?, updated_at = ?
                WHERE payment_id = ?
            ''', (approval_message, context.from_user.id, datetime.now(UTC).isoformat(), payment_id))
            
            # Update order status
            cursor.execute('''
                UPDATE orders SET payment_status = 'COMPLETED' WHERE order_id = ?
            ''', (payment_id,))
            
            # Log approval
            cursor.execute('''
                INSERT INTO payment_communications 
                (payment_id, sender_type, sender_id, message_type, message_content, sent_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (payment_id, 'admin', context.from_user.id, 'approval', approval_message, datetime.now(UTC).isoformat()))
            
            conn.commit()
        
        # Send approval message to user
        user_msg = (
            f"🎉 <b>Payment Approved!</b>\n\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n\n"
            f"✅ <b>Admin Message:</b>\n"
            f"<i>{approval_message}</i>\n\n"
            f"<b>What happens next:</b>\n"
            f"• Your order is being processed immediately\n"
            f"• You'll receive your item shortly\n"
            f"• Order details will be delivered to you\n\n"
            f"<b>Status:</b> ✅ Approved & Processing\n"
            f"<b>Approved by:</b> Admin Team\n"
            f"<b>Time:</b> {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            f"Thank you for choosing our service! 🙏"
        )
        
        send_random_animation(bot, user_id, kind="success", caption=user_msg, parse_mode="HTML")
        
        # Deliver the product if item details exist
        if item_details_str:
            try:
                from payment_handler import deliver_product
                item_details = json.loads(item_details_str)
                deliver_product(bot, user_id, payment_id, item_details)
            except Exception as e:
                print(f"Error delivering product: {e}")
        
        # Confirm to admin
        admin_confirmation = (
            f"✅ <b>Payment Approved Successfully</b>\n\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n"
            f"<b>User ID:</b> <code>{user_id}</code>\n"
            f"<b>Your Message:</b> {approval_message}\n\n"
            f"The user has been notified and order is being processed."
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💬 Chat with User", callback_data=f"admin_chat_user_{user_id}"))
        
        chat_id = context.chat.id if hasattr(context, 'chat') else context.message.chat.id
        bot.send_message(chat_id, admin_confirmation, reply_markup=markup, parse_mode="HTML")
        
    except Exception as e:
        print(f"Error approving payment: {e}")
        error_msg = f"❌ Error approving payment: {str(e)}"
        if hasattr(context, 'reply_to'):
            bot.reply_to(context, error_msg)
        else:
            bot.answer_callback_query(context.id, "Error processing approval", show_alert=True)

def process_enhanced_rejection(bot, context, payment_id, rejection_reason):
    """Process enhanced payment rejection with detailed reason"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            
            # Get payment details
            payment_data = cursor.execute('''
                SELECT user_id FROM enhanced_payments WHERE payment_id = ?
            ''', (payment_id,)).fetchone()
            
            if not payment_data:
                if hasattr(context, 'reply_to'):
                    bot.reply_to(context, f"❌ Payment {payment_id} not found.")
                else:
                    bot.answer_callback_query(context.id, "Payment not found", show_alert=True)
                return
            
            user_id = payment_data[0]
            admin_id = context.from_user.id if hasattr(context, 'from_user') else ADMIN_ID
            
            # Update payment status
            cursor.execute('''
                UPDATE enhanced_payments 
                SET status = 'rejected', admin_response_remarks = ?, processed_by = ?, updated_at = ?
                WHERE payment_id = ?
            ''', (rejection_reason, admin_id, datetime.now(UTC).isoformat(), payment_id))
            
            # Update order status
            cursor.execute('''
                UPDATE orders SET payment_status = 'REJECTED' WHERE order_id = ?
            ''', (payment_id,))
            
            # Log rejection
            cursor.execute('''
                INSERT INTO payment_communications 
                (payment_id, sender_type, sender_id, message_type, message_content, sent_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (payment_id, 'admin', admin_id, 'rejection', rejection_reason, datetime.now(UTC).isoformat()))
            
            conn.commit()
        
        # Send detailed rejection message to user
        user_msg = (
            f"❌ <b>Payment Verification Failed</b>\n\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n\n"
            f"📋 <b>Reason for Rejection:</b>\n"
            f"{rejection_reason}\n\n"
            f"🔄 <b>What you can do:</b>\n"
            f"• Review the reason above carefully\n"
            f"• Take a new, clearer screenshot if needed\n"
            f"• Ensure all payment details are visible\n"
            f"• Include the Payment ID in transaction memo\n"
            f"• Try submitting again with correct information\n\n"
            f"💬 <b>Need Help?</b>\n"
            f"Contact our support team for assistance.\n\n"
            f"<b>Reviewed by:</b> Admin Team\n"
            f"<b>Time:</b> {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔄 Try Again", callback_data=f"enhanced_pay_{payment_id}"),
            types.InlineKeyboardButton("💬 Contact Support", callback_data="support_menu"),
            types.InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
        )
        
        send_random_animation(bot, user_id, kind="reject", caption=user_msg, parse_mode="HTML")
        bot.send_message(user_id, "Choose an option:", reply_markup=markup)
        
        # Confirm to admin
        admin_confirmation = (
            f"❌ <b>Payment Rejected Successfully</b>\n\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n"
            f"<b>User ID:</b> <code>{user_id}</code>\n"
            f"<b>Rejection Reason:</b> {rejection_reason}\n\n"
            f"The user has been notified with detailed feedback."
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💬 Chat with User", callback_data=f"admin_chat_user_{user_id}"))
        
        chat_id = context.chat.id if hasattr(context, 'chat') else context.message.chat.id
        bot.send_message(chat_id, admin_confirmation, reply_markup=markup, parse_mode="HTML")
        
    except Exception as e:
        print(f"Error rejecting payment: {e}")
        error_msg = f"❌ Error rejecting payment: {str(e)}"
        if hasattr(context, 'reply_to'):
            bot.reply_to(context, error_msg)
        else:
            bot.answer_callback_query(context.id, "Error processing rejection", show_alert=True)

    # --- QUICK ACTIONS ---
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("quick_approve_"))
    def quick_approve_payment(call):
        """Quick approval with default message"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Admin access only", show_alert=True)
            return
            
        payment_id = call.data.replace("quick_approve_", "")
        default_message = "✅ Payment verified and approved! Thank you for your trust. Your order is being processed."
        
        process_enhanced_approval(bot, call, payment_id, default_message)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("quick_reject_enhanced_"))
    def quick_reject_payment(call):
        """Quick rejection with default message"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Admin access only", show_alert=True)
            return
            
        payment_id = call.data.replace("quick_reject_enhanced_", "")
        default_reason = "Screenshot unclear or payment details cannot be verified. Please upload a clearer screenshot."
        
        process_enhanced_rejection(bot, call, payment_id, default_reason)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("payment_help_"))
    def payment_help_menu(call):
        """Show payment help options"""
        payment_id = call.data.replace("payment_help_", "")
        
        text = (
            f"❓ <b>Payment Help & Support</b>\n\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n\n"
            f"<b>Common Questions:</b>\n\n"
            f"📸 <b>Screenshot Guidelines:</b>\n"
            f"• Use your banking app or wallet\n"
            f"• Show transaction confirmation\n"
            f"• Include payment amount and date\n"
            f"• Ensure Payment ID is in memo\n\n"
            f"💰 <b>Payment Issues:</b>\n"
            f"• Double-check the payment amount\n"
            f"• Verify you sent to correct address\n"
            f"• Include Payment ID in transaction\n\n"
            f"🔄 <b>What if rejected?</b>\n"
            f"• Read the rejection reason carefully\n"
            f"• Take a new, clearer screenshot\n"
            f"• Try submitting again\n\n"
            f"Need direct help? Contact our support team!"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("💬 Contact Support", callback_data="support_menu"),
            types.InlineKeyboardButton("📷 Upload Screenshot", callback_data=f"upload_enhanced_ss_{payment_id}"),
            types.InlineKeyboardButton("⬅️ Back to Payment", callback_data=f"enhanced_pay_{payment_id}")
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("view_payment_details_"))
    def view_payment_details(call):
        """Show detailed payment information to admin"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Admin access only", show_alert=True)
            return
            
        payment_id = call.data.replace("view_payment_details_", "")
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            
            # Get comprehensive payment details
            payment_info = cursor.execute('''
                SELECT 
                    ep.*,
                    o.item_name,
                    o.price_usd,
                    o.creation_date,
                    COUNT(pc.id) as communication_count
                FROM enhanced_payments ep
                LEFT JOIN orders o ON ep.payment_id = o.order_id
                LEFT JOIN payment_communications pc ON ep.payment_id = pc.payment_id
                WHERE ep.payment_id = ?
                GROUP BY ep.payment_id
            ''', (payment_id,)).fetchone()
            
            if not payment_info:
                bot.answer_callback_query(call.id, "Payment not found", show_alert=True)
                return
            
            # Get user info
            try:
                user_info = bot.get_chat(payment_info[1])  # user_id
                user_name = f"{user_info.first_name or 'Unknown'} {user_info.last_name or ''}".strip()
                username = f"@{user_info.username}" if user_info.username else "No username"
            except:
                user_name = "Unknown User"
                username = "No username"
        
        text = (
            f"🔍 <b>Payment Details</b>\n\n"
            f"📄 <b>Payment ID:</b> <code>{payment_id}</code>\n"
            f"👤 <b>User:</b> {user_name} ({username})\n"
            f"🆔 <b>User ID:</b> <code>{payment_info[1]}</code>\n"
            f"🛍️ <b>Item:</b> {payment_info[10] or 'Unknown'}\n"
            f"💰 <b>Amount:</b> ${payment_info[11] or 'Unknown'}\n"
            f"📅 <b>Created:</b> {payment_info[7] or 'Unknown'}\n"
            f"🔄 <b>Status:</b> {payment_info[6] or 'Unknown'}\n"
            f"📱 <b>Communications:</b> {payment_info[13]} messages\n"
            f"⏰ <b>Last Update:</b> {payment_info[8] or 'Unknown'}\n\n"
            f"📸 <b>Screenshot:</b> {'✅ Provided' if payment_info[3] else '❌ Missing'}\n"
            f"💬 <b>Admin Request:</b> {payment_info[4] or 'None'}\n"
            f"📝 <b>Admin Response:</b> {payment_info[5] or 'Pending'}"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_with_remarks_{payment_id}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_with_remarks_{payment_id}")
        )
        markup.add(
            types.InlineKeyboardButton("💬 Chat", callback_data=f"admin_chat_user_{payment_info[1]}"),
            types.InlineKeyboardButton("⬅️ Back", callback_data=f"admin_payment_menu_{payment_id}")
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")