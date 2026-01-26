import json
from telebot import types

# Status messages for different section statuses
STATUS_MESSAGES = {
    "coming_soon": "🟡 **Coming Soon!**\n\nThis section is under construction and will be available shortly. Stay tuned for updates!",
    "maintenance": "🔴 **Under Maintenance**\n\nThis section is temporarily unavailable as we're making improvements. Please check back later."
}

def get_section_status(section_key):
    """
    Loads the status for a given section from the JSON file.
    Returns 'available' by default if the file or section is not found.
    """
    try:
        with open('section_status.json', 'r') as f:
            statuses = json.load(f)
        return statuses.get(section_key, "available")
    except FileNotFoundError:
        return "available"

def handle_unavailable_section(bot, call, section_key):
    """
    Checks the status of a section. If it's not available, it sends an appropriate
    message to the user and returns True. Otherwise, it returns False.
    """
    status = get_section_status(section_key)
    if status in STATUS_MESSAGES:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        
        try:
            bot.edit_message_text(
                STATUS_MESSAGES[status],
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        except Exception as e:
            if "message is not modified" not in str(e):
                print(f"Error in handle_unavailable_section: {e}")

        bot.answer_callback_query(call.id)
        return True  # Indicates the section is unavailable
    return False  # Indicates the section is available
