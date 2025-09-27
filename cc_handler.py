from telebot import types
import json
from helpers import get_country_list, get_state_summary, update_state
from database import load_products

def register_cc_handlers(bot, user_states):
    """
    Registers all callback handlers for the entire CC (Credit Card) section.
    This includes ready-made CCs, generating CCs from a user-provided BIN,
    and the full multi-step customization flow.
    """

    # ===========================
    # ====== CC Main Menu =======
    # ===========================
    @bot.callback_query_handler(func=lambda call: call.data == "cc_menu")
    def cc_menu(call):
        bot.send_chat_action(call.message.chat.id, 'typing')
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🛍️ Select CC", callback_data="ready_cc_menu"),
            types.InlineKeyboardButton("🔍 Your Bin", callback_data="enter_bin_menu"),
            types.InlineKeyboardButton("⚙️ Customize", callback_data="custom_cc_start")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        bot.edit_message_text(
            "💳 **CC Section**\n\nPlease choose how you would like to get a CC:",
            call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown"
        )

    # =================================
    # ====== 1. Ready CC Section ======
    # =================================
    @bot.callback_query_handler(func=lambda call: call.data == "ready_cc_menu")
    def ready_cc_menu(call):
        bot.send_chat_action(call.message.chat.id, 'typing')
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        products = load_products()
        ready_ccs = products.get("ready_ccs", [])
        
        if not ready_ccs:
            bot.answer_callback_query(call.id, "No Ready CCs are available at the moment.", show_alert=True)
            return

        for index, item in enumerate(ready_ccs):
            name = item.get("name")
            price = item.get("price")
            # THE FIX: Use a short, index-based callback
            callback_data = f"buy_idx_ready_ccs_{index}"
            description = f"Description: {item.get('description', name)}"
            markup.add(types.InlineKeyboardButton(f"🛒 {description} - ${price}", callback_data=callback_data))

        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="cc_menu"))
        bot.edit_message_text(
            "🛍️ **Select from the following**\n\nThese CCs are pre-configured and ready for use.",
            call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown"
        )

    # ===================================
    # ====== 2. Enter BIN Section ======
    # ===================================
    @bot.callback_query_handler(func=lambda call: call.data == "enter_bin_menu")
    def enter_bin_menu(call):
        user_id = call.from_user.id
        user_states[user_id] = "awaiting_bin"
        bot.edit_message_text(
            "**🔍 Enter Your Bin**\n\nPlease send the 6 to 8 digit BIN you want to use.",
            call.message.chat.id, call.message.message_id,
            parse_mode="Markdown"
        )

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_bin")
    def handle_bin_input(message):
        user_id = message.from_user.id
        bin_input = message.text.strip()

        if not (bin_input.isdigit() and 6 <= len(bin_input) <= 8):
            bot.send_message(user_id, "❌ Invalid BIN. Please send a valid 6-8 digit BIN.")
            return

        del user_states[user_id]

        price = 40
        # THE FIX: Use a short, dynamic callback format
        callback_data = f"buy_dyn_frombin_{bin_input}"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f"💳 Generate CC - ${price}", callback_data=callback_data))
        
        bot.send_message(
            user_id,
            f"✅ **Bin Entered:** `{bin_input}`\n\nClick the button below to generate a full CC and proceed to payment.",
            reply_markup=markup,
            parse_mode="Markdown"
        )

    # ===================================
    # ====== 3. Customize CC Section ======
    # ===================================
    @bot.callback_query_handler(func=lambda call: call.data == "custom_cc_start")
    def custom_cc_brand(call):
        bot.send_chat_action(call.message.chat.id, 'typing')
        state = "None~None~None~None"
        brands = ["VISA", "MasterCard", "AMEX", "DISCO"]
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [types.InlineKeyboardButton(f"{b}", callback_data=f"cc_type_{b}_{state}") for b in brands]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("➡️ Skip", callback_data=f"cc_type_None_{state}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="cc_menu"))
        text = "⚙️ **Choose your card**\n\n" + get_state_summary(state)
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("cc_type_"))
    def custom_cc_type(call):
        _, _, brand, state = call.data.split('_', 3)
        new_state = update_state(state, 0, brand)
        types_list = ["Debit", "Credit"]
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [types.InlineKeyboardButton(f"{t}", callback_data=f"cc_country_{t}_{new_state}_0") for t in types_list]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("➡️ Skip", callback_data=f"cc_country_None_{new_state}_0"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="custom_cc_start"))
        text = "⚙️ **Now choose type**\n\n" + get_state_summary(new_state)
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("cc_country_"))
    def custom_cc_country(call):
        _, _, type_val, state, page_str = call.data.split('_', 4)
        page = int(page_str)
        new_state = update_state(state, 1, type_val)
        countries = list(get_country_list().items())
        items_per_page = 21 
        total_pages = (len(countries) + items_per_page - 1) // items_per_page
        
        markup = types.InlineKeyboardMarkup(row_width=3)
        start_index = page * items_per_page
        end_index = start_index + items_per_page
        buttons = [types.InlineKeyboardButton(f"{flag} {name}", callback_data=f"cc_level_{name}_{new_state}") for name, flag in countries[start_index:end_index]]
        markup.add(*buttons)
        
        nav_buttons = []
        if page > 0:
            nav_buttons.append(types.InlineKeyboardButton("⬅️ Prev", callback_data=f"cc_country_{type_val}_{state}_{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"cc_country_{type_val}_{state}_{page+1}"))
        
        if nav_buttons:
            markup.row(*nav_buttons)

        markup.row(types.InlineKeyboardButton("⬅️ Back", callback_data=f"cc_type_{new_state.split('~')[0]}_{state}"))

        text = f"🌍 **Select country (Page {page+1}/{total_pages})**\n\n" + get_state_summary(new_state)
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("cc_level_"))
    def custom_cc_level(call):
        _, _, country, state = call.data.split('_', 3)
        new_state = update_state(state, 2, country)
        levels = ["Classic", "Black", "Gift", "Prepaid", "Personal", "Platinum", "Business", "World Elite", "Enhanced", "Gold", "Corporate", "Diamond", "Professional", "Titanium", "Signature"]
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(level, callback_data=f"cc_pricing_{level}_{new_state}") for level in levels]
        markup.add(*buttons)
        
        markup.add(
            types.InlineKeyboardButton("➡️ Skip", callback_data=f"cc_pricing_None_{new_state}"),
            types.InlineKeyboardButton("⬅️ Back", callback_data=f"cc_country_None_{state}_0")
        )
        text = "⚙️ **Choose Level of CCs**\n\n" + get_state_summary(new_state)
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("cc_pricing_"))
    def custom_cc_pricing(call):
        _, _, level, state = call.data.split('_', 3)
        final_state_str = update_state(state, 3, level)
        
        if all(s == "None" for s in final_state_str.split('~')):
            bot.answer_callback_query(call.id, "⚠️ You must select at least ONE option!", show_alert=True)
            return
            
        prices = [25, 35, 40]
        markup = types.InlineKeyboardMarkup(row_width=3)
        price_buttons = []
        for price in prices:
            # THE FIX: Use a short, dynamic callback format
            # Format: buy_dyn_{category}_{price}~{state_string}
            callback_data = f"buy_dyn_customcc_{price}~{final_state_str}"
            price_buttons.append(types.InlineKeyboardButton(f"${price}", callback_data=callback_data))
        markup.add(*price_buttons)
        
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=f"cc_level_None_{state}"))

        summary = "✅ **Review Your Custom CC**\n\n" + get_state_summary(final_state_str) + "\nPlease choose a price:"
        bot.edit_message_text(summary, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

