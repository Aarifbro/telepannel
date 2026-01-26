# games/menu.py

from telebot import types
from helpers import safe_edit_message


def register_games_menu(bot):

    @bot.callback_query_handler(func=lambda call: call.data == "games_menu")
    def games_menu(call):
        markup = types.InlineKeyboardMarkup(row_width=1)

        markup.add(
            types.InlineKeyboardButton(
                "🚢 Battleship Hunt",
                callback_data="bs_create"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "🎮 BGMI Accounts",
                callback_data="bgmi_menu"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "⬅️ Back",
                callback_data="main_menu"
            )
        )

        safe_edit_message(
            bot,
            call,
            "<b>🎮 GAMES</b>\n\nSelect a game:",
            reply_markup=markup
        )


