# monetization/shop.py

from telebot import types

from monetization.skins import SKINS
from monetization.user_store import (
    get_or_create_user,
    has_enough_coins,
    add_coins,
    give_skin,
    equip_skin,
    get_equipped_skin,
)
from monetization.banner_sender import send_banner_message


def register_shop(bot):
    """
    Registers all shop-related handlers.
    Shop is fully button-driven.
    """

    # =========================
    # OPEN SHOP (FROM MENU)
    # =========================
    @bot.callback_query_handler(func=lambda call: call.data == "open_shop")
    def open_shop(call):
        user = get_or_create_user(call.from_user.id, call.from_user.username)

        text = (
            "<b>🛒 SKIN SHOP</b>\n\n"
            f"> 💰 <b>Your Coins:</b> <code>{user['coins']}</code>\n\n"
            "Select a skin pack below.\n"
            "Skins change how your games look."
        )

        kb = types.InlineKeyboardMarkup(row_width=1)

        for skin_id, skin in SKINS.items():
            price = skin["price"]
            name = skin["name"]

            if price == 0:
                label = f"🎖️ {name} (Free)"
            else:
                label = f"🎨 {name} — {price}💰"

            kb.add(
                types.InlineKeyboardButton(
                    label,
                    callback_data=f"shop_view|{skin_id}",
                )
            )

        kb.add(
            types.InlineKeyboardButton(
                "⬅️ Back",
                callback_data="back_to_main",
            )
        )

        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=kb,
        )

    # =========================
    # VIEW SKIN DETAILS
    # =========================
    @bot.callback_query_handler(func=lambda call: call.data.startswith("shop_view|"))
    def view_skin(call):
        _, skin_id = call.data.split("|")
        skin = SKINS.get(skin_id)

        if not skin:
            bot.answer_callback_query(call.id, "Skin not found", show_alert=True)
            return

        user = get_or_create_user(call.from_user.id, call.from_user.username)

        owned = skin_id in user["owned_skins"]
        equipped = skin_id == user["equipped_skin"]

        text = (
            f"<b>{skin['name']}</b>\n\n"
            f"{skin['description']}\n\n"
            f"> 💰 <b>Price:</b> <code>{skin['price']}</code>\n"
            f"> 🎨 <b>Type:</b> <code>{skin['type']}</code>\n"
        )

        kb = types.InlineKeyboardMarkup(row_width=2)

        if owned:
            if equipped:
                kb.add(
                    types.InlineKeyboardButton(
                        "✅ Equipped",
                        callback_data="noop",
                    )
                )
            else:
                kb.add(
                    types.InlineKeyboardButton(
                        "🎯 Equip",
                        callback_data=f"shop_equip|{skin_id}",
                    )
                )
        else:
            kb.add(
                types.InlineKeyboardButton(
                    f"🛒 Buy ({skin['price']}💰)",
                    callback_data=f"shop_buy|{skin_id}",
                )
            )

        kb.add(
            types.InlineKeyboardButton(
                "⬅️ Back to Shop",
                callback_data="open_shop",
            )
        )

        # Send banner preview (no spam, replaces content)
        send_banner_message(
            bot,
            call.from_user.id,
            text,
            reply_markup=kb,
        )

    # =========================
    # BUY SKIN
    # =========================
    @bot.callback_query_handler(func=lambda call: call.data.startswith("shop_buy|"))
    def buy_skin(call):
        _, skin_id = call.data.split("|")
        skin = SKINS.get(skin_id)

        if not skin:
            bot.answer_callback_query(call.id, "Skin not found", show_alert=True)
            return

        user = get_or_create_user(call.from_user.id, call.from_user.username)

        if skin_id in user["owned_skins"]:
            bot.answer_callback_query(call.id, "Already owned", show_alert=True)
            return

        price = skin["price"]

        if not has_enough_coins(user["user_id"], price):
            bot.answer_callback_query(
                call.id,
                "❌ Not enough coins",
                show_alert=True,
            )
            return

        # Deduct coins & grant skin
        add_coins(user["user_id"], -price, "Skin purchase")
        give_skin(user["user_id"], skin_id)
        equip_skin(user["user_id"], skin_id)

        bot.answer_callback_query(
            call.id,
            "✅ Skin purchased & equipped!",
            show_alert=True,
        )

        # Refresh view
        view_skin(call)

    # =========================
    # EQUIP SKIN
    # =========================
    @bot.callback_query_handler(func=lambda call: call.data.startswith("shop_equip|"))
    def equip_skin_handler(call):
        _, skin_id = call.data.split("|")
        user = get_or_create_user(call.from_user.id, call.from_user.username)

        if skin_id not in user["owned_skins"]:
            bot.answer_callback_query(call.id, "You don't own this skin", show_alert=True)
            return

        equip_skin(user["user_id"], skin_id)

        bot.answer_callback_query(
            call.id,
            "🎨 Skin equipped!",
            show_alert=False,
        )

        view_skin(call)

    # =========================
    # NO-OP BUTTON
    # =========================
    @bot.callback_query_handler(func=lambda call: call.data == "noop")
    def noop(call):
        bot.answer_callback_query(call.id)

