# monetization/battle_ship_game/rewards.py

from monetization.user_store import get_or_create_user

WIN_REWARD = 120
LOSS_REWARD = 40

def reward_winner(user_id):
    user = get_or_create_user(user_id)
    user["coins"] += WIN_REWARD

def reward_loser(user_id):
    user = get_or_create_user(user_id)
    user["coins"] += LOSS_REWARD