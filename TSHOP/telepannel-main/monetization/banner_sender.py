from monetization.user_store import get_equipped_skin
from monetization.skins import SKINS

def get_user_banner(user_id):
    skin_id = get_equipped_skin(user_id)
    skin = SKINS.get(skin_id)

    if not skin:
        return None

    return {
        "type": skin["type"],        # "photo" or "animation"
        "file_id": skin["file_id"],
    }

def send_banner_message(bot, user_id, text, reply_markup=None):
    banner = get_user_banner(user_id)

    try:
        if banner:
            if banner["type"] == "animation":
                msg = bot.send_animation(
                    user_id,
                    banner["file_id"],
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
            else:
                msg = bot.send_photo(
                    user_id,
                    banner["file_id"],
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
        else:
            msg = bot.send_message(
                user_id,
                text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
    except Exception:
        msg = bot.send_message(
            user_id,
            text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )

    return msg

