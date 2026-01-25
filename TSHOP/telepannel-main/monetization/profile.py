# monetization/profile.py

from monetization.user_store import get_or_create_user
from monetization.banner_sender import send_banner_message


def register_profile(bot):

    @bot.message_handler(commands=["profile"])
    def profile_cmd(message):
        user = get_or_create_user(message.from_user.id, message.from_user.username)

        owned = "\n".join(
            f"> 🎨 <code>{sid}</code>" for sid in user["owned_skins"]
        )

        text = (
            "<b>👤 COMMANDER PROFILE</b>\n\n"
            f"> 👤 Username: <code>@{user['username']}</code>\n"
            f"> 💰 Coins: <code>{user['coins']}</code>\n"
            f"> 💎 Premium: {'✅ YES' if user['is_premium'] else '❌ NO'}\n"
            f"> 🖼 Equipped Skin: <code>{user['equipped_skin']}</code>\n\n"
            "<b>🎒 Owned Skins</b>\n"
            f"{owned}"
        )

        send_banner_message(bot, message.from_user.id, text)