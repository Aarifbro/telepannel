# accounts/crunchyroll.py

import json
import os
from telebot import types

from helpers import check_force_join

ACCOUNTS_DB = "accounts/accounts_db.json"
REFERRALS_DB = "accounts/referrals_db.json"
REQUIRED_REFERRALS = 4
BOT_USERNAME = "tshopybot"


# =========================
# JSON HELPERS
# =========================
def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# =========================
# REWARD LOGIC (RESET AFTER)
# =========================
def _try_reward(bot, referrer_id):
    referrals = _load_json(REFERRALS_DB, {})
    accounts = _load_json(ACCOUNTS_DB, {})

    user_ref = referrals.get(referrer_id)
    if not user_ref:
        return

    if len(user_ref["referrals"]) < REQUIRED_REFERRALS:
        return

    cr_accounts = accounts.get("crunchyroll", [])
    if not cr_accounts:
        bot.send_message(
            int(referrer_id),
            "❌ No Crunchyroll accounts available right now.",
        )
        return

    # Take first available account
    account = cr_accounts.pop(0)
    accounts["crunchyroll"] = cr_accounts
    _save_json(ACCOUNTS_DB, accounts)

    # 🔄 RESET REFERRALS AFTER REWARD
    user_ref["referrals"] = []
    referrals[referrer_id] = user_ref
    _save_json(REFERRALS_DB, referrals)

    bot.send_message(
        int(referrer_id),
        (
            "<b>🎉 CONGRATULATIONS!</b>\n\n"
            "<b>🍥 Crunchyroll Premium Account</b>\n\n"
            f"👤 <b>Login:</b> <code>{account['login']}</code>\n"
            f"🔑 <b>Password:</b> <code>{account['password']}</code>\n"
            f"⏳ <b>Premium Until:</b> <code>{account['premium_until']}</code>\n\n"
            "🔁 <i>Your referrals have been reset.</i>\n"
            "Invite 4 more friends to earn again.\n\n"
            "⚠️ <i>Do not share this account.</i>"
        ),
        parse_mode="HTML",
    )


# =========================
# REFERRAL PROCESSOR (CALLED FROM /START)
# =========================
def process_referral(bot, message, referrer_id):
    user_id = str(message.from_user.id)

    # Prevent self-referral
    if user_id == referrer_id:
        return

    # Force join check
    if not check_force_join(bot, message.from_user.id):
        return

    referrals = _load_json(REFERRALS_DB, {})
    ref_data = referrals.setdefault(referrer_id, {"referrals": []})

    # Prevent duplicate referral
    if user_id in ref_data["referrals"]:
        return

    ref_data["referrals"].append(user_id)
    referrals[referrer_id] = ref_data
    _save_json(REFERRALS_DB, referrals)

    # 🔔 Notify referrer
    try:
        bot.send_message(
            int(referrer_id),
            (
                "🔔 <b>New Referral!</b>\n\n"
                f"👤 User <code>{user_id}</code> started the bot using your referral link.\n\n"
                f"📊 Progress: <b>{len(ref_data['referrals'])}/{REQUIRED_REFERRALS}</b>"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass

    _try_reward(bot, referrer_id)


# =========================
# REGISTER CALLBACK HANDLERS
# =========================
def register_crunchyroll(bot):

    @bot.callback_query_handler(func=lambda c: c.data == "accounts_crunchyroll")
    def open_crunchyroll(call):
        user_id = str(call.from_user.id)

        referrals = _load_json(REFERRALS_DB, {})
        user_ref = referrals.get(user_id, {"referrals": []})

        count = len(user_ref["referrals"])
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

        text = (
            "<b>🍥 CRUNCHYROLL PREMIUM GIVEAWAY</b>\n\n"
            "🎁 Get <b>1 Crunchyroll Premium Account</b>\n"
            "👥 Invite <b>4 friends</b>\n\n"
            f"> 🔢 Referrals: <code>{count}/{REQUIRED_REFERRALS}</code>\n\n"
            "<b>Your Referral Link</b>\n"
            f"<code>{ref_link}</code>\n\n"
            "📌 <b>Rules</b>\n"
            "• Friend must start the bot\n"
            "• Friend must join required channels\n"
            "• One referral per user\n"
            "• Self-referrals ignored\n"
            "• Referrals reset after reward"
        )

        bot.send_message(call.from_user.id, text, parse_mode="HTML")
