# monetization/battle_ship_game/integration.py

from monetization.banner_sender import send_banner_message
from monetization.battle_ship_game.rewards import reward_winner, reward_loser

def send_game_message(bot, user_id, text, reply_markup=None):
    """
    Wrapper used ONLY by battleship game
    """
    send_banner_message(bot, user_id, text, reply_markup)


def handle_game_end(bot, winner_id, loser_id):
    reward_winner(winner_id)
    reward_loser(loser_id)

    send_banner_message(
        bot,
        winner_id,
        "<b>🏆 VICTORY</b>\n\n> +120 💰 Coins",
    )
    send_banner_message(
        bot,
        loser_id,
        "<b>☠️ DEFEAT</b>\n\n> +40 💰 Coins",
    )