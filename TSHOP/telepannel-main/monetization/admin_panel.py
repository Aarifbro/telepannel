# monetization/admin_panel.py

from telebot import types
from config import ADMIN_ID

# If you use multiple admins, convert ADMIN_ID to ADMIN_IDS list
ADMIN_IDS = [6127646960,1513264586]



def register_admin(bot):

    # =========================
    # OPEN ADMIN PANEL
    # =========================
    @bot.callback_query_handler(func=lambda c: c.data == "open_admin")
    def open_admin_panel(call):
        if call.from_user.id not in ADMIN_IDS:
            bot.answer_callback_query(
                call.id,
                "❌ You are not authorized.",
                show_alert=True
            )
            return

        kb = types.InlineKeyboardMarkup(row_width=1)

        kb.add(
            types.InlineKeyboardButton(
                "➕ Load Accounts",
                callback_data="admin_add_accounts"
            ),
            types.InlineKeyboardButton(
                "➕ Add Coins",
                callback_data="admin_add_coins"
            ),
            types.InlineKeyboardButton(
                "🎁 Give Skin",
                callback_data="admin_give_skin"
            ),
            types.InlineKeyboardButton(
                "⬅️ Back",
                callback_data="back_to_main"
            )
        )

        bot.edit_message_text(
            "<b>🛠️ ADMIN PANEL</b>\n\nSelect an action:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb,
            parse_mode="HTML"
        )

    # =========================
    # FALLBACK (OPTIONAL SAFETY)
    # =========================
    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_"))
    def admin_fallback(call):
        if call.from_user.id not in ADMIN_IDS:
            bot.answer_callback_query(
                call.id,
                "❌ Unauthorized admin action.",
                show_alert=True
            )


