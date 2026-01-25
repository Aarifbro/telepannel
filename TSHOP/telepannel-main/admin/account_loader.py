# admin/account_loader.py

import json
import os
from telebot import types

ACCOUNTS_DB = "accounts/accounts_db.json"


def _load_accounts():
    if not os.path.exists(ACCOUNTS_DB):
        return {"crunchyroll": []}
    try:
        with open(ACCOUNTS_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"crunchyroll": []}


def _save_accounts(data):
    with open(ACCOUNTS_DB, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def register_account_loader(bot, ADMIN_IDS):

    # =========================
    # ADMIN → ADD ACCOUNTS MENU
    # =========================
    @bot.callback_query_handler(func=lambda c: c.data == "admin_add_accounts")
    def admin_add_accounts(call):
        if call.from_user.id not in ADMIN_IDS:
            return

        text = (
            "<b>➕ ADD CRUNCHYROLL ACCOUNTS</b>\n\n"
            "Send accounts in this format:\n\n"
            "<code>email:password|YYYY-MM-DD</code>\n\n"
            "You can send multiple lines at once.\n\n"
            "<b>Example:</b>\n"
            "<code>test@mail.com:pass123|2026-01-01</code>"
        )

        msg = bot.send_message(
            call.from_user.id,
            text,
            parse_mode="HTML"
        )

        bot.register_next_step_handler(msg, _save_accounts_step)


def _save_accounts_step(message):
    try:
        lines = message.text.strip().splitlines()
        data = _load_accounts()

        added = 0

        for line in lines:
            if ":" not in line or "|" not in line:
                continue

            creds, expiry = line.split("|", 1)
            login, password = creds.split(":", 1)

            data.setdefault("crunchyroll", []).append(
                {
                    "login": login.strip(),
                    "password": password.strip(),
                    "premium_until": expiry.strip(),
                }
            )
            added += 1

        _save_accounts(data)

        message.reply_text(
            f"✅ <b>{added}</b> Crunchyroll accounts added successfully.",
            parse_mode="HTML"
        )

    except Exception as e:
        message.reply_text(
            "❌ Failed to add accounts.\n"
            "Please check the format and try again."
        )
        print(f"Account loader error: {e}")


