import json
from telebot import types
from database import load_products

def blur_bin(bin_number):
    """
    Blurs a BIN number for security, showing only the first 2 digits.
    Example: 456789 -> 45••••
    """
    if not isinstance(bin_number, str) or len(bin_number) < 3:
        return "••••••"
    return bin_number[:2] + '•' * (len(bin_number) - 2)

def register_bin_handlers(bot):
    """
    Registers all callback handlers for the BIN section.
    """

    @bot.callback_query_handler(func=lambda call: call.data == "bin_menu")
    def bin_menu(call):
        user_id = call.message.chat.id
        bot.send_chat_action(user_id, 'typing')
        try:
            # Clean up the chat by deleting the previous menu
            bot.delete_message(user_id, call.message.message_id)
        except Exception as e:
            print(f"Error while deleting message: {e}")

        # Load all products and get the 'bins' category
        products = load_products()
        bins = products.get("bins", [])
        
        if not bins:
            bot.send_message(user_id, "🙁 No BINs are available at the moment.")
            # Import locally to avoid circular import issues
            from main import send_main_menu
            send_main_menu(user_id, "👇 Please choose an option from the menu.")
            return

        bot.send_message(user_id, "📦 **Available BINs**\nClick 'Buy' on any BIN from the list below to purchase.")

        # Loop through each BIN and send it as a separate message
        for index, bin_data in enumerate(bins):
            bot.send_chat_action(user_id, 'typing')
            
            # Blur the BIN for security before displaying it
            blurred_bin = blur_bin(bin_data.get("bin", ""))
            
            # Get the new description field
            description = bin_data.get("description", "N/A")
            
            message_text = f"""**BIN:** `{blurred_bin}`
**Description:** `{description}`
**Status:** `{bin_data.get("status", "N/A")}`
**Country:** `{bin_data.get("country", "N/A")}`
**Info:** `{bin_data.get("info", "N/A")}`
**Bank:** `{bin_data.get("bank", "N/A")}`"""
            
            markup = types.InlineKeyboardMarkup()
            price = bin_data.get("price")
            # THE FIX: Use a short, index-based callback to avoid data limit errors
            callback_data = f"buy_idx_bins_{index}"
            markup.add(types.InlineKeyboardButton(f"💵 Buy - ${price}", callback_data=callback_data))
            
            bot.send_message(user_id, message_text, parse_mode="Markdown", reply_markup=markup)

        # After sending all BINs, send a button to return to the main menu
        main_menu_markup = types.InlineKeyboardMarkup()
        main_menu_markup.add(types.InlineKeyboardButton("🏠 Back to Main Menu", callback_data="go_to_main_menu"))
        bot.send_message(user_id, "↩️ Return to the main menu.", reply_markup=main_menu_markup)

    @bot.callback_query_handler(func=lambda call: call.data == "go_to_main_menu")
    def go_to_main_menu_callback(call):
        try:
            # Clean up the "Back" button message
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        # Import locally to avoid circular import issues
        from main import send_main_menu
        send_main_menu(call.message.chat.id, "👇 Please choose an option from the menu.")

