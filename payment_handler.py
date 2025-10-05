import json
import sqlite3
import uuid
from datetime import datetime, UTC
from telebot import types
from config import DB_NAME, ADMIN_ID, CRYPTO_ADDRESS
from helpers import send_random_animation
from helpers import generate_fake_details # NOTE: Assuming notify_admin is handled by the direct message below
from database import load_products, get_user_balance, update_user_balance

# Store user states for multi-step interactions
user_states = {}

# Placeholder for the deliver_product function, as its definition was not provided.
# This function should contain the logic for sending the purchased item to the user.
def deliver_product(bot, user_id, order_id, item_details):
    """
    Delivers the purchased product to the user based on the item's 'delivery_type'.
    - 'link': Forwards a Telegram message.
    - 'file': Sends a file from the server.
    - Default: Sends the item details as a JSON object.
    """
    print(f"INFO: Delivering product for order {order_id} to user {user_id}.")
    try:
        delivery_type = item_details.get("delivery_type")

        if delivery_type == "link":
            link = item_details.get("delivery_content")
            if not link or "t.me" not in link:
                raise ValueError("Invalid or missing Telegram message link in delivery_content.")
            
            # Parse the link: https://t.me/c/1234567890/123 -> ('-1001234567890', '123')
            parts = link.split('/')
            from_chat_id = int(f"-100{parts[-2]}")
            message_id = int(parts[-1])
            
            bot.send_message(user_id, f"✅ Your order `{order_id}` is complete! Here is your content:", parse_mode="Markdown")
            bot.copy_message(chat_id=user_id, from_chat_id=from_chat_id, message_id=message_id)

        elif delivery_type == "text":
            text_content = item_details.get("delivery_content")
            if not text_content:
                raise ValueError("Missing text content in delivery_content.")
            
            bot.send_message(user_id, f"✅ Your order `{order_id}` is complete! Here is your item:", parse_mode="Markdown")
            bot.send_message(user_id, text_content, parse_mode="HTML") # Assuming content might have HTML formatting

        elif delivery_type == "generate":
            # For items like Custom CC, generate details on the fly.
            generated_details = generate_fake_details(item_details.get("custom_specs"))
            details_text = json.dumps(generated_details, indent=2)
            bot.send_message(user_id, f"✅ Your order `{order_id}` is complete!\n\nHere are your generated item details:\n```json\n{details_text}\n```", parse_mode="Markdown")

        elif delivery_type == "file":
            file_path = item_details.get("delivery_content")
            if not file_path:
                raise ValueError("Missing file path in delivery_content.")
            
            bot.send_message(user_id, f"✅ Your order `{order_id}` is complete! Here is your file:", parse_mode="Markdown")
            with open(file_path, 'rb') as f:
                bot.send_document(user_id, f)

        elif delivery_type == "tg_document":
            file_id = item_details.get("delivery_content")
            bot.send_message(user_id, f"✅ Your order `{order_id}` is complete! Document:", parse_mode="Markdown")
            bot.send_document(user_id, file_id)

        elif delivery_type == "tg_photo":
            file_id = item_details.get("delivery_content")
            bot.send_message(user_id, f"✅ Your order `{order_id}` is complete! Photo:", parse_mode="Markdown")
            bot.send_photo(user_id, file_id)

        elif delivery_type == "tg_video":
            file_id = item_details.get("delivery_content")
            bot.send_message(user_id, f"✅ Your order `{order_id}` is complete! Video:", parse_mode="Markdown")
            bot.send_video(user_id, file_id)

        elif delivery_type == "tg_animation":
            file_id = item_details.get("delivery_content")
            bot.send_message(user_id, f"✅ Your order `{order_id}` is complete! Animation:", parse_mode="Markdown")
            bot.send_animation(user_id, file_id)

        else:
            # Default behavior: send item details as text
            details_text = json.dumps(item_details, indent=2)
            bot.send_message(user_id, f"✅ Your order `{order_id}` is complete!\n\nHere are your item details:\n```json\n{details_text}\n```", parse_mode="Markdown")

    except Exception as e:
        print(f"ERROR: Could not deliver product for order {order_id}. Error: {e}")
        bot.send_message(user_id, f"There was an issue delivering your item for order `{order_id}`. Please contact support.", parse_mode="Markdown")


def register_payment_handlers(bot):
    """
    Registers all callback handlers for the manual payment and admin approval process.
    """

    # Handler for items stored in products.json (No changes here)
    @bot.callback_query_handler(func=lambda call: call.data.startswith("buy_idx_"))
    def buy_indexed_item_callback(call):
        """Handles 'Buy' clicks for items stored in products.json using an index."""
        try:
            parts = call.data.split('_')
            index = int(parts[-1])
            category = '_'.join(parts[2:-1])
            
            products = load_products().get(category, [])
            if index >= len(products):
                bot.answer_callback_query(call.id, "Error: Item not found.", show_alert=True)
                return
                
            item_details = products[index]
            price = item_details.get("price")
            item_name = item_details.get("name")

            back_callback = f"{category}_menu"
            show_payment_options(bot, call, item_name, price, item_details, back_callback)
        except Exception as e:
            print(f"Error parsing indexed buy callback: {e}")
            bot.answer_callback_query(call.id, "An error occurred.", show_alert=True)

    # Handler for dynamically generated items (No changes here)
    @bot.callback_query_handler(func=lambda call: call.data.startswith("buy_dyn_"))
    def buy_dynamic_item_callback(call):
        """Handles 'Buy' clicks for dynamically generated items like Custom CCs."""
        try:
            parts = call.data.split('_', 3)
            category = parts[2]
            data = parts[3]
            
            price = 0
            item_name = ""
            item_details = {}

            if category == "frombin":
                price = 40
                item_name = f"CC from BIN {data}"
                item_details = {"source_bin": data}
            
            elif category == "customcc":
                price_str, state_str = data.split('~', 1)
                price = int(price_str)
                state_parts = state_str.split('~')
                name_parts = ["Custom CC"]
                if state_parts[0] != "None": name_parts.append(state_parts[0])
                if state_parts[1] != "None": name_parts.append(state_parts[1])
                if state_parts[2] != "None": name_parts.append(state_parts[2])
                if state_parts[3] != "None": name_parts.append(state_parts[3])
                item_name = " ".join(name_parts)
                item_details = {"custom_specs": state_str}

            show_payment_options(bot, call, item_name, price, item_details, "cc_menu")
        except Exception as e:
            print(f"Error parsing dynamic buy callback: {e}")
            bot.answer_callback_query(call.id, "An error occurred.", show_alert=True)

    # --- NEW PAYMENT FLOW ---


# Make show_payment_options globally importable
def show_payment_options(bot, call, item, price, item_details, back_callback):
    """Displays the initial payment screen with the price and a button to proceed."""
    bot.send_chat_action(call.message.chat.id, 'typing')
    user_id = call.from_user.id
    balance = 0.0
    try:
        balance = float(get_user_balance(user_id))
    except Exception:
        balance = 0.0
    text = (
        f"<b>🧾 Order Summary</b>\n\n"
        f"<b>Item:</b> {item}\n"
        f"<b>Price:</b> ${price}\n"
        f"<b>Your Wallet:</b> ${balance:.2f}\n\n"
        f"Choose a payment option:"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    details_str = json.dumps(item_details)
    callback_data = f"start_manual_{price}_{item}_{details_str}"
    # Prevent Telegram callback data limits
    if len(callback_data.encode('utf-8')) > 64:
        from uuid import uuid4
        key = str(uuid4())[:8]
        if not hasattr(bot, '_dumps_temp'): bot._dumps_temp = {}
        bot._dumps_temp[key] = {'item': item, 'price': price, 'item_details': item_details, 'back_callback': back_callback}
        callback_data = f"start_manual_short_{key}"
    # Manual crypto payment
    markup.add(types.InlineKeyboardButton("💱 Pay Manually (Crypto)", callback_data=callback_data))
    # Wallet payment option if sufficient balance
    if balance >= float(price):
        # For wallet pay, we need a compact payload too
        wallet_key = str(uuid.uuid4())[:8]
        if not hasattr(bot, '_wallet_temp'): bot._wallet_temp = {}
        bot._wallet_temp[wallet_key] = {'item': item, 'price': float(price), 'item_details': item_details, 'back_callback': back_callback}
        markup.add(types.InlineKeyboardButton("💳 Pay with Wallet", callback_data=f"pay_wallet_{wallet_key}"))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=back_callback))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")


    @bot.callback_query_handler(func=lambda call: call.data.startswith("start_manual_"))
    def start_manual_payment(call):
        """Generates a Payment ID, saves the order, and shows payment instructions to the user."""
        try:
            if call.data.startswith("start_manual_short_"):
                key = call.data.split('_')[-1]
                temp = getattr(bot, '_dumps_temp', {}).get(key)
                if not temp:
                    bot.answer_callback_query(call.id, "Session expired. Please try again.", show_alert=True)
                    return
                item = temp['item']
                price_usd = int(temp['price'])
                details_str = json.dumps(temp['item_details'])
                back_callback = temp['back_callback']
            else:
                _, _, price_str, item, details_str = call.data.split('_', 4)
                price_usd = int(price_str)
                back_callback = "main_menu"
            payment_id = str(uuid.uuid4()).split('-')[1].upper() # A shorter, more user-friendly ID

            bot.send_chat_action(call.message.chat.id, 'typing')
            bot.answer_callback_query(call.id, "Generating your payment ID...")

            with sqlite3.connect(DB_NAME) as conn:
                conn.cursor().execute(
                    "INSERT INTO orders (order_id, user_id, item_name, price_usd, payment_method, payment_status, creation_date, item_details) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (payment_id, call.from_user.id, item, price_usd, "MANUAL_CRYPTO", "PENDING_PAYMENT", datetime.now(UTC).isoformat(), details_str)
                )
                conn.commit()

            # Use enhanced payment system for better user experience
            text = (
                f"💳 <b>Payment Instructions</b>\n\n"
                f"<b>Item:</b> {item}\n"
                f"<b>Amount:</b> ${price_usd}\n"
                f"<b>Payment ID:</b> <code>{payment_id}</code>\n\n"
                f"🔄 <b>Next Steps:</b>\n"
                f"1️⃣ Send <b>${price_usd}</b> to: <code>{CRYPTO_ADDRESS}</code>\n"
                f"2️⃣ Include Payment ID in memo: <code>{payment_id}</code>\n"
                f"3️⃣ Click 'Start Payment Process' below\n\n"
                f"✨ <b>Enhanced verification system with instant approval!</b>"
            )
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("💰 Start Payment Process", callback_data=f"enhanced_pay_{payment_id}"))
            markup.add(types.InlineKeyboardButton("❌ Cancel Order", callback_data=back_callback))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

        except Exception as e:
            print(f"Error starting manual payment: {e}")
            bot.answer_callback_query(call.id, "An error occurred while generating payment details.", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("paid_confirm_"))
    def user_confirms_payment(call):
        """Handles the user's confirmation of payment and notifies the admin."""
        try:
            payment_id = call.data.split('_')[2]
            # Check if screenshot is required
            ss_map = getattr(bot, '_payment_screenshots', {})
            has_screenshot = ss_map.get(payment_id) is not None
            
            # Get order details to check if this is a manual crypto payment
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                row = c.execute("SELECT payment_method, payment_status FROM orders WHERE order_id = ?", (payment_id,)).fetchone()
            
            if row and row[0] == 'MANUAL_CRYPTO' and row[1] in ('PENDING_PAYMENT', 'PENDING_APPROVAL'):
                if not has_screenshot:
                    # Offer to proceed without screenshot but warn user
                    text = (
                        f"⚠️ <b>No Screenshot Uploaded</b>\n\n"
                        f"You haven't uploaded a payment screenshot yet. While this is not strictly required, "
                        f"it helps our admin verify your payment faster.\n\n"
                        f"Would you like to:"
                    )
                    markup = types.InlineKeyboardMarkup(row_width=1)
                    markup.add(types.InlineKeyboardButton("📷 Upload Screenshot First", callback_data=f"upload_ss_{payment_id}"))
                    markup.add(types.InlineKeyboardButton("✅ Continue Without Screenshot", callback_data=f"confirm_no_ss_{payment_id}"))
                    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"back_to_payment_{payment_id}"))
                    
                    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                        reply_markup=markup, parse_mode="HTML")
                    return
            
            # Use the shared payment confirmation logic
            process_payment_confirmation(call, payment_id)
            
        except Exception as e:
            print(f"Error in payment confirmation: {e}")
            bot.answer_callback_query(call.id, "An error occurred.", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("upload_ss_"))
    def request_screenshot_upload(call):
        payment_id = call.data.split('_')[-1]
        if not hasattr(bot, '_awaiting_ss'):
            bot._awaiting_ss = {}
        bot._awaiting_ss[call.from_user.id] = payment_id
        
        text = (
            f"📷 <b>Upload Payment Screenshot</b>\n\n"
            f"Please send a <b>photo or image</b> of your payment transaction for Payment ID <code>{payment_id}</code>.\n\n"
            f"💡 <b>Tips for a good screenshot:</b>\n"
            f"• Include transaction ID/hash\n"
            f"• Show payment amount\n"
            f"• Include Payment ID in memo\n"
            f"• Make sure image is clear and readable\n\n"
            f"After uploading, you'll be able to click 'I Have Paid' to complete the process."
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel Upload", callback_data=f"back_to_payment_{payment_id}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(content_types=['photo'])
    def capture_payment_screenshot(message):
        try:
            pending = getattr(bot, '_awaiting_ss', {})
            payment_id = pending.get(message.from_user.id)
            if not payment_id:
                return
            file_id = message.photo[-1].file_id
            if not hasattr(bot, '_payment_screenshots'):
                bot._payment_screenshots = {}
            bot._payment_screenshots[payment_id] = file_id
            del bot._awaiting_ss[message.from_user.id]
            
            # Send screenshot to admin immediately
            try:
                bot.send_photo(ADMIN_ID, file_id, caption=f"📷 Payment Screenshot - ID: {payment_id}\nUser: {message.from_user.first_name} ({message.from_user.id})")
            except:
                pass
                
            # Send confirmation with payment buttons restored
            text = (
                f"✅ <b>Screenshot Uploaded Successfully!</b>\n\n"
                f"📷 Your payment screenshot for Payment ID <code>{payment_id}</code> has been saved and sent to admin for verification.\n\n"
                f"Now click <b>'I Have Paid'</b> to notify the admin and complete your payment confirmation."
            )
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("✅ I Have Paid", callback_data=f"paid_confirm_{payment_id}"))
            markup.add(types.InlineKeyboardButton("📷 Upload Different Screenshot", callback_data=f"upload_ss_{payment_id}"))
            markup.add(types.InlineKeyboardButton("❌ Cancel Order", callback_data="main_menu"))
            
            bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            bot.reply_to(message, f"❌ Could not save screenshot: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("back_to_payment_"))
    def back_to_payment_screen(call):
        """Return user to payment screen from screenshot upload"""
        payment_id = call.data.split('_')[-1]
        user_id = call.from_user.id
        
        # Clear screenshot awaiting state
        if hasattr(bot, '_awaiting_ss') and user_id in bot._awaiting_ss:
            del bot._awaiting_ss[user_id]
        
        # Get payment details from database
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                order = cursor.execute("SELECT item_name, price_usd FROM orders WHERE order_id = ? AND user_id = ?", 
                                     (payment_id, user_id)).fetchone()
                
                if not order:
                    bot.answer_callback_query(call.id, "Order not found", show_alert=True)
                    return
                    
                item_name, price_usd = order
        except Exception as e:
            bot.answer_callback_query(call.id, "Error loading order", show_alert=True)
            return
        
        # Show payment screen again
        text = (
            f"<b>💰 Manual Payment</b>\n\n"
            f"Please make a payment of <b>${price_usd}</b> to the address below.\n\n"
            f"<b>IMPORTANT:</b> You must include the <b>Payment ID</b> in the memo/note of your transaction for verification.\n\n"
            f"<b>Address:</b> <code>{CRYPTO_ADDRESS}</code>\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n\n"
            f"After sending the payment, upload a payment screenshot here, then click the confirmation button."
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📷 Upload Screenshot", callback_data=f"upload_ss_{payment_id}"))
        markup.add(types.InlineKeyboardButton("✅ I Have Paid", callback_data=f"paid_confirm_{payment_id}"))
        markup.add(types.InlineKeyboardButton("❌ Cancel Order", callback_data="main_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_no_ss_"))
    def confirm_payment_without_screenshot(call):
        """Handle payment confirmation without screenshot"""
        payment_id = call.data.split('_')[-1]
        
        # Proceed with the normal payment confirmation flow
        process_payment_confirmation(call, payment_id)

    def process_payment_confirmation(call, payment_id):
        """Process the actual payment confirmation logic"""
        try:
            # REQUIRE screenshot before processing
            screenshot_file_id = getattr(bot, '_payment_screenshots', {}).get(payment_id)
            if not screenshot_file_id:
                bot.answer_callback_query(call.id, "❌ Screenshot required!", show_alert=True)
                
                text = (
                    f"📷 <b>Screenshot Required</b>\n\n"
                    f"❌ <b>Cannot process payment without screenshot.</b>\n\n"
                    f"You must upload a payment screenshot before the admin can review your payment.\n\n"
                    f"This helps verify your transaction and prevents fraud.\n\n"
                    f"Please upload your payment screenshot first."
                )
                
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(types.InlineKeyboardButton("📷 Upload Screenshot", callback_data=f"upload_ss_{payment_id}"))
                markup.add(types.InlineKeyboardButton("❌ Cancel Order", callback_data=f"back_to_payment_{payment_id}"))
                
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                    reply_markup=markup, parse_mode="HTML")
                return
                
            bot.answer_callback_query(call.id, "Confirmation received. Notifying admin...")

            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE orders SET payment_status = ? WHERE order_id = ?", ("PENDING_APPROVAL", payment_id))
                conn.commit()
                order = cursor.execute("SELECT item_name, price_usd, user_id FROM orders WHERE order_id = ?", (payment_id,)).fetchone()

            if not order:
                bot.edit_message_text("Error: Could not find your order.", call.message.chat.id, call.message.message_id)
                return

            item_name, price_usd, user_id = order

            admin_text = f"""
🔔 **Payment Confirmation**
A user has confirmed their payment and is awaiting approval.

**User:** `{user_id}` (`{call.from_user.first_name}`)
**Item:** `{item_name}`
**Price:** `${price_usd}`
**Payment ID:** `{payment_id}`

Please verify the transaction and approve or reject it.
"""
            admin_markup = types.InlineKeyboardMarkup(row_width=2)
            admin_markup.add(
                types.InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{payment_id}"),
                types.InlineKeyboardButton("❌ Reject with Remarks", callback_data=f"admin_reject_remarks_{payment_id}")
            )
            admin_markup.add(
                types.InlineKeyboardButton("💬 Chat with User", callback_data=f"admin_chat_user_{user_id}")
            )
            # Attach screenshot if provided
            screenshot_file_id = getattr(bot, '_payment_screenshots', {}).get(payment_id)
            if screenshot_file_id:
                try:
                    bot.send_photo(ADMIN_ID, screenshot_file_id, caption=admin_text, reply_markup=admin_markup, parse_mode="Markdown")
                except Exception:
                    bot.send_message(ADMIN_ID, admin_text + "\n(Note: Screenshot attached but failed to send)", reply_markup=admin_markup, parse_mode="Markdown")
            else:
                bot.send_message(ADMIN_ID, admin_text + "\n(Note: No screenshot uploaded)", reply_markup=admin_markup, parse_mode="Markdown")
            
            user_text = f"""
⏳ **Waiting for Approval**

Thank you! We have received your confirmation for Payment ID `{payment_id}`.

An administrator will now verify your transaction. You will be notified once it is approved.
"""
            bot.edit_message_text(user_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

        except Exception as e:
            print(f"Error confirming payment: {e}")
            bot.answer_callback_query(call.id, "An error occurred.", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("pay_wallet_"))
    def pay_with_wallet(call):
        """Instantly complete purchase using internal wallet balance."""
        user_id = call.from_user.id
        key = call.data.split('_')[-1]
        temp = getattr(bot, '_wallet_temp', {}).get(key)
        if not temp:
            bot.answer_callback_query(call.id, "Session expired. Please try again.", show_alert=True)
            return
        item = temp['item']
        price = float(temp['price'])
        item_details = temp['item_details']
        try:
            balance = float(get_user_balance(user_id))
        except Exception:
            balance = 0.0
        try:
            balance = float(get_user_balance(user_id))
        except Exception:
            balance = 0.0
        try:
            bal = float(get_user_balance(user_id))
            if bal < price:
                bot.answer_callback_query(call.id, "Insufficient wallet balance.", show_alert=True)
                return
            # Deduct and create completed order
            new_bal = update_user_balance(user_id, -price)
            payment_id = str(uuid.uuid4()).split('-')[1].upper()
            with sqlite3.connect(DB_NAME) as conn:
                conn.cursor().execute(
                    "INSERT INTO orders (order_id, user_id, item_name, price_usd, payment_method, payment_status, creation_date, item_details) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (payment_id, user_id, item, price, "WALLET", "COMPLETED", datetime.now(UTC).isoformat(), json.dumps(item_details))
                )
                conn.commit()
            # Deliver
            bot.send_chat_action(user_id, 'typing')
            deliver_product(bot, user_id, payment_id, item_details)
            receipt = (
                f"<b>🧾 Payment Receipt</b>\n"
                f"<b>Order ID:</b> <code>{payment_id}</code>\n"
                f"<b>Payment Method:</b> Wallet\n"
                f"<b>Item:</b> {item}\n"
                f"<b>Price:</b> ${price:.2f}\n"
                f"<b>New Balance:</b> ${new_bal:.2f}\n"
                f"<b>Date:</b> {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"<b>Status:</b> <b>Paid & Delivered ✅</b>\n"
            )
            send_random_animation(bot, user_id, kind="success", caption=receipt, parse_mode="HTML")
            bot.edit_message_text("✅ Payment completed with wallet.", call.message.chat.id, call.message.message_id)
        except Exception as e:
            print(f"Wallet pay error: {e}")
            bot.answer_callback_query(call.id, "Failed to complete wallet payment.", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_approve_"))
    def admin_approves_payment(call):
        """Handles the admin's 'Approve' action."""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "You are not authorized.", show_alert=True)
            return

        try:
            payment_id = call.data.split('_')[2]
            bot.answer_callback_query(call.id, f"Approving payment {payment_id}...")

            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                order_data = cursor.execute("SELECT user_id, item_name, item_details, price_usd, payment_status FROM orders WHERE order_id = ?", (payment_id,)).fetchone()
                
                if not order_data:
                    bot.edit_message_text(f"Order `{payment_id}` not found.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
                    return
                if order_data[4] != "PENDING_APPROVAL":
                    bot.answer_callback_query(call.id, "This order has already been processed.", show_alert=True)
                    return
                
                user_id, item_name, item_details_str, price_usd, _ = order_data
                item_details = json.loads(item_details_str or '{}')
                cursor.execute("UPDATE orders SET payment_status = ? WHERE order_id = ?", ("COMPLETED", payment_id))
                conn.commit()

            # If this was a wallet deposit, credit user's balance instead of delivering item
            if item_name == "Wallet Deposit":
                amount = item_details.get("deposit_amount") or price_usd or 0
                try:
                    amount = float(amount)
                except Exception:
                    amount = float(price_usd or 0)
                new_bal = update_user_balance(user_id, amount)
                msg = (
                    f"<b>✅ Deposit Approved</b>\n\n"
                    f"<b>Payment ID:</b> <code>{payment_id}</code>\n"
                    f"<b>Amount:</b> ${amount:.2f}\n"
                    f"<b>New Balance:</b> ${new_bal:.2f}\n"
                )
                send_random_animation(bot, user_id, kind="success", caption=msg, parse_mode="HTML")
                bot.edit_message_text(call.message.text + f"\n\n<b>Action:</b> Approved (Deposit) by {call.from_user.first_name} ✅", call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode="HTML")
            else:
                # Normal product delivery
                bot.send_chat_action(user_id, 'typing')
                deliver_product(bot, user_id, payment_id, item_details)
                receipt = f"<b>🧾 Payment Receipt</b>\n"
                receipt += f"<b>Order ID:</b> <code>{payment_id}</code>\n"
                receipt += f"<b>User ID:</b> <code>{user_id}</code>\n"
                receipt += f"<b>Item:</b> {item_details.get('name', 'N/A')}\n"
                receipt += f"<b>Price:</b> ${item_details.get('price', 'N/A')}\n"
                receipt += f"<b>Date:</b> {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}\n"
                receipt += f"<b>Details:</b> <code>{json.dumps(item_details, indent=2)}</code>\n"
                receipt += "\n<b>Status:</b> <b>Paid & Delivered ✅</b>\n"
                send_random_animation(bot, user_id, kind="success", caption=receipt, parse_mode="HTML")
                bot.edit_message_text(call.message.text + f"\n\n<b>Action:</b> Approved by {call.from_user.first_name} ✅", call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode="HTML")

        except Exception as e:
            print(f"Error approving payment: {e}")
            bot.answer_callback_query(call.id, "An error occurred.", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_reject_remarks_"))
    def admin_reject_with_remarks(call):
        """Handle payment rejection with admin remarks"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "You are not authorized.", show_alert=True)
            return

        payment_id = call.data.replace("admin_reject_remarks_", "")
        
        # Set user state to await rejection remarks
        user_states[call.from_user.id] = f"awaiting_rejection_remarks_{payment_id}"
        
        text = (
            f"❌ <b>Reject Payment with Remarks</b>\n\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n\n"
            f"Please enter the reason for rejecting this payment:\n\n"
            f"<b>Common reasons:</b>\n"
            f"• Invalid payment amount\n"
            f"• Payment ID not found in memo\n"
            f"• Screenshot unclear or invalid\n"
            f"• Transaction not confirmed\n"
            f"• Suspicious activity detected\n\n"
            f"Type your custom rejection reason:"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("⚡ Invalid Amount", callback_data=f"quick_reject_{payment_id}_Invalid payment amount"),
            types.InlineKeyboardButton("📷 Screenshot Issue", callback_data=f"quick_reject_{payment_id}_Screenshot unclear or invalid"),
            types.InlineKeyboardButton("🔍 Payment ID Missing", callback_data=f"quick_reject_{payment_id}_Payment ID not found in transaction memo"),
            types.InlineKeyboardButton("⏱️ Transaction Not Found", callback_data=f"quick_reject_{payment_id}_Transaction not confirmed in our system"),
            types.InlineKeyboardButton("✏️ Custom Reason", callback_data=f"custom_reject_{payment_id}")
        )
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_approve_{payment_id}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("quick_reject_"))
    def quick_reject_payment(call):
        """Handle quick rejection with predefined reasons"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "You are not authorized.", show_alert=True)
            return

        parts = call.data.split('_', 2)  # quick_reject_{payment_id}_{reason}
        if len(parts) < 3:
            bot.answer_callback_query(call.id, "Invalid rejection data", show_alert=True)
            return
            
        payment_id = parts[2].split('_')[0]
        reason = '_'.join(parts[2].split('_')[1:])
        
        # Process the rejection directly
        process_rejection_with_reason(bot, call, payment_id, reason)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("custom_reject_"))
    def custom_reject_payment(call):
        """Handle custom rejection reason input"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "You are not authorized.", show_alert=True)
            return

        payment_id = call.data.replace("custom_reject_", "")
        
        # Set user state to await custom rejection remarks
        user_states[call.from_user.id] = f"awaiting_rejection_remarks_{payment_id}"
        
        text = (
            f"✏️ <b>Custom Rejection Reason</b>\n\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n\n"
            f"Please type your custom rejection reason:\n\n"
            f"<i>Be specific and professional. The user will see this message.</i>"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_reject_remarks_{payment_id}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id, "").startswith("awaiting_rejection_remarks_"))
    def handle_rejection_remarks(message):
        """Handle admin's rejection remarks input"""
        if message.from_user.id != ADMIN_ID:
            return
            
        state = user_states[message.from_user.id]
        payment_id = state.replace("awaiting_rejection_remarks_", "")
        remarks = message.text.strip()
        
        if len(remarks) < 5:
            bot.reply_to(message, "❌ Rejection reason too short. Please provide at least 5 characters.")
            return

        # Process the rejection
        process_rejection_with_reason(bot, message, payment_id, remarks)
        
        # Clear user state
        if message.from_user.id in user_states:
            del user_states[message.from_user.id]

def process_rejection_with_reason(bot, context, payment_id, remarks):
    """Process payment rejection with given reason"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            
            # Create payment_responses table if it doesn't exist
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
            
            order_data = cursor.execute("SELECT user_id, payment_status FROM orders WHERE order_id = ?", (payment_id,)).fetchone()

            if not order_data:
                if hasattr(context, 'reply_to'):
                    bot.reply_to(context, f"❌ Order `{payment_id}` not found.")
                else:
                    bot.answer_callback_query(context.id, f"Order {payment_id} not found", show_alert=True)
                return
            if order_data[1] != "PENDING_APPROVAL":
                if hasattr(context, 'reply_to'):
                    bot.reply_to(context, "❌ This order has already been processed.")
                else:
                    bot.answer_callback_query(context.id, "Order already processed", show_alert=True)
                return

            user_id, _ = order_data
            cursor.execute("UPDATE orders SET payment_status = ? WHERE order_id = ?", ("REJECTED", payment_id))
            
            # Save rejection remarks - get admin_id properly
            admin_id = context.from_user.id if hasattr(context, 'from_user') else ADMIN_ID
            cursor.execute('''
                INSERT INTO payment_responses (payment_id, admin_id, response_type, remarks, responded_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (payment_id, admin_id, 'rejected', remarks, datetime.now(UTC).isoformat()))
            
            conn.commit()

        # Send detailed rejection message to user
        user_msg = (
            f"❌ <b>Payment Rejected</b>\n\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n\n"
            f"<b>Reason:</b> {remarks}\n\n"
            f"<b>What to do next:</b>\n"
            f"• Check the reason above\n"
            f"• Contact support if you need help\n"
            f"• You can try placing a new order\n\n"
            f"<i>Rejected by admin on {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}</i>"
        )
        send_random_animation(bot, user_id, kind="reject", caption=user_msg, parse_mode="HTML")
        
        # Update admin message
        admin_confirmation = (
            f"✅ <b>Payment Rejected with Remarks</b>\n\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n"
            f"<b>User ID:</b> <code>{user_id}</code>\n"
            f"<b>Rejection Reason:</b> {remarks}\n\n"
            f"The user has been notified of the rejection and reason."
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💬 Chat with User", callback_data=f"admin_chat_user_{user_id}"))
        
        # Send confirmation to admin
        chat_id = context.chat.id if hasattr(context, 'chat') else context.message.chat.id
        bot.send_message(chat_id, admin_confirmation, reply_markup=markup, parse_mode="HTML")
        
    except Exception as e:
        print(f"Error rejecting payment with remarks: {e}")
        if hasattr(context, 'reply_to'):
            bot.reply_to(context, f"❌ An error occurred while processing rejection: {str(e)}")
        else:
            bot.answer_callback_query(context.id, "Error processing rejection", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_chat_user_"))
    def start_admin_user_chat_from_payment(call):
        """Start chat with user from payment screen"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "You are not authorized.", show_alert=True)
            return
            
        user_id = int(call.data.split('_')[3])
        
        # Import and use admin communication system
        try:
            from admin_communication import start_admin_user_chat
            start_admin_user_chat(bot, call.from_user.id, user_id, call.message.chat.id)
            bot.answer_callback_query(call.id, f"Started chat with user {user_id}")
        except Exception as e:
            print(f"Error starting chat: {e}")
            bot.answer_callback_query(call.id, "Failed to start chat", show_alert=True)