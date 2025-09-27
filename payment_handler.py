import json
import sqlite3
import uuid
from datetime import datetime, UTC
from telebot import types
from config import DB_NAME, ADMIN_ID, CRYPTO_ADDRESS # NOTE: Removed PAYMENTIO_API_KEY, added ADMIN_ID and CRYPTO_ADDRESS
from helpers import generate_fake_details # NOTE: Assuming notify_admin is handled by the direct message below
from database import load_products
from other_handlers import CATEGORY_NAMES

# Placeholder for the deliver_product function, as its definition was not provided.
# This function should contain the logic for sending the purchased item to the user.
def deliver_product(bot, user_id, order_id, item_details):
    """
    Delivers the purchased product to the user.
    """
    print(f"INFO: Delivering product for order {order_id} to user {user_id}.")
    try:
        details_text = json.dumps(item_details, indent=2)
        bot.send_message(user_id, f"✅ Your order `{order_id}` is complete!\n\nHere are your item details:\n```json\n{details_text}\n```", parse_mode="Markdown")
        # Add your actual delivery logic here (e.g., sending a file, generating details, etc.)
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
    text = f"<b>� Order Summary</b>\n\n<b>Item:</b> {item}\n<b>Price:</b> ${price}\n\nPress <b>Proceed</b> to get payment details."
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
    markup.add(types.InlineKeyboardButton("➡️ Proceed", callback_data=callback_data))
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

            text = (
                f"<b>💰 Manual Payment</b>\n\n"
                f"Please make a payment of <b>${price_usd}</b> to the address below.\n\n"
                f"<b>IMPORTANT:</b> You must include the <b>Payment ID</b> in the memo/note of your transaction for verification.\n\n"
                f"<b>Address:</b> <code>{CRYPTO_ADDRESS}</code>\n"
                f"<b>Payment ID:</b> <code>{payment_id}</code>\n\n"
                f"After sending the payment, click the button below."
            )
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("✅ I Have Paid", callback_data=f"paid_confirm_{payment_id}"))
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
                types.InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{payment_id}")
            )
            bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_markup, parse_mode="Markdown")
            
            user_text = f"""
⏳ **Waiting for Approval**

Thank you! We have received your confirmation for Payment ID `{payment_id}`.

An administrator will now verify your transaction. You will be notified once it is approved.
"""
            bot.edit_message_text(user_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

        except Exception as e:
            print(f"Error confirming payment: {e}")
            bot.answer_callback_query(call.id, "An error occurred.", show_alert=True)

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
                order_data = cursor.execute("SELECT user_id, item_details, payment_status FROM orders WHERE order_id = ?", (payment_id,)).fetchone()
                
                if not order_data:
                    bot.edit_message_text(f"Order `{payment_id}` not found.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
                    return
                if order_data[2] != "PENDING_APPROVAL":
                    bot.answer_callback_query(call.id, "This order has already been processed.", show_alert=True)
                    return
                
                user_id, item_details_str, _ = order_data
                item_details = json.loads(item_details_str)
                cursor.execute("UPDATE orders SET payment_status = ? WHERE order_id = ?", ("COMPLETED", payment_id))
                conn.commit()

            bot.send_chat_action(user_id, 'typing')
            deliver_product(bot, user_id, payment_id, item_details)
            # Generate a formatted receipt
            receipt = f"<b>🧾 Payment Receipt</b>\n"
            receipt += f"<b>Order ID:</b> <code>{payment_id}</code>\n"
            receipt += f"<b>User ID:</b> <code>{user_id}</code>\n"
            receipt += f"<b>Item:</b> {item_details.get('name', 'N/A')}\n"
            receipt += f"<b>Price:</b> ${item_details.get('price', 'N/A')}\n"
            receipt += f"<b>Date:</b> {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}\n"
            receipt += f"<b>Details:</b> <code>{json.dumps(item_details, indent=2)}</code>\n"
            receipt += "\n<b>Status:</b> <b>Paid & Delivered ✅</b>\n"
            bot.send_message(user_id, receipt, parse_mode="HTML")
            bot.edit_message_text(call.message.text + f"\n\n<b>Action:</b> Approved by {call.from_user.first_name} ✅", call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode="HTML")

        except Exception as e:
            print(f"Error approving payment: {e}")
            bot.answer_callback_query(call.id, "An error occurred.", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_reject_"))
    def admin_rejects_payment(call):
        """Handles the admin's 'Reject' action."""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "You are not authorized.", show_alert=True)
            return

        try:
            payment_id = call.data.split('_')[2]
            bot.answer_callback_query(call.id, f"Rejecting payment {payment_id}...")

            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                order_data = cursor.execute("SELECT user_id, payment_status FROM orders WHERE order_id = ?", (payment_id,)).fetchone()

                if not order_data:
                    bot.edit_message_text(f"Order `{payment_id}` not found.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
                    return
                if order_data[1] != "PENDING_APPROVAL":
                    bot.answer_callback_query(call.id, "This order has already been processed.", show_alert=True)
                    return

                user_id, _ = order_data
                cursor.execute("UPDATE orders SET payment_status = ? WHERE order_id = ?", ("REJECTED", payment_id))
                conn.commit()

            user_msg = f"⚠️ **Payment Rejected**\n\nYour payment with ID `{payment_id}` could not be confirmed. Please contact support for assistance."
            bot.send_message(user_id, user_msg, parse_mode="Markdown")
            
            bot.edit_message_text(call.message.text + f"\n\n**Action: Rejected by {call.from_user.first_name}** ❌", call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode="Markdown")

        except Exception as e:
            print(f"Error rejecting payment: {e}")
            bot.answer_callback_query(call.id, "An error occurred.", show_alert=True)
