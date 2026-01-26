# monetization/game_renderer.py

from monetization.banner_sender import send_banner_message

# Stores last message per (user, game)
last_game_messages = {}


def render_game_message(bot, user_id, game_id, text, reply_markup=None):
    """
    Edits existing game message if possible,
    otherwise sends a new one.
    """
    key = (user_id, game_id)

    try:
        if key in last_game_messages:
            msg_id = last_game_messages[key]
            bot.edit_message_caption(
                chat_id=user_id,
                message_id=msg_id,
                caption=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
            return
    except Exception:
        pass

    msg = send_banner_message(
        bot,
        user_id,
        text,
        reply_markup,
#        return_message=True,  # banner_sender should support this
    )

    if msg:
        last_game_messages[key] = msg.message_id

