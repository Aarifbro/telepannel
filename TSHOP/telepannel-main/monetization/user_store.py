# monetization/user_store.py

import time

# =========================
# IN-MEMORY USER STORAGE
# =========================
users = {}

# Default starting coins
START_COINS = 1000


# =========================
# USER CREATION / FETCH
# =========================
def get_or_create_user(user_id, username=None):
    """
    Fetches user profile or creates it if not exists
    """
    if user_id not in users:
        users[user_id] = {
            "user_id": user_id,
            "username": username or "Unknown",
            "coins": START_COINS,
            "owned_skins": ["default_naval"],
            "equipped_skin": "default_naval",
            "is_premium": False,
            "created_at": int(time.time()),
            "stats": {
                "games_played": 0,
                "games_won": 0,
                "games_lost": 0,
            },
        }
    else:
        # Update username if changed
        if username and users[user_id]["username"] != username:
            users[user_id]["username"] = username

    return users[user_id]


# =========================
# COIN MANAGEMENT
# =========================
def add_coins(user_id, amount, reason=None):
    """
    Adds or subtracts coins safely.
    Coins will never go below 0.
    """
    user = get_or_create_user(user_id)

    old_balance = user["coins"]
    new_balance = old_balance + amount

    if new_balance < 0:
        new_balance = 0

    user["coins"] = new_balance

    # Optional logging (safe to remove later)
    print(
        f"💰 Coins update | User: {user_id} | "
        f"{old_balance} → {new_balance} | "
        f"Change: {amount} | Reason: {reason}"
    )

    return new_balance


def get_coins(user_id):
    user = get_or_create_user(user_id)
    return user["coins"]


def has_enough_coins(user_id, amount):
    return get_coins(user_id) >= amount


# =========================
# GAME STATS
# =========================
def record_game_result(user_id, won: bool):
    user = get_or_create_user(user_id)

    user["stats"]["games_played"] += 1

    if won:
        user["stats"]["games_won"] += 1
    else:
        user["stats"]["games_lost"] += 1


# =========================
# SKIN MANAGEMENT
# =========================
def owns_skin(user_id, skin_id):
    user = get_or_create_user(user_id)
    return skin_id in user["owned_skins"]


def give_skin(user_id, skin_id):
    user = get_or_create_user(user_id)

    if skin_id not in user["owned_skins"]:
        user["owned_skins"].append(skin_id)

    return True


def equip_skin(user_id, skin_id):
    user = get_or_create_user(user_id)

    if skin_id not in user["owned_skins"]:
        return False

    user["equipped_skin"] = skin_id
    return True


def get_equipped_skin(user_id):
    user = get_or_create_user(user_id)
    return user["equipped_skin"]


# =========================
# PREMIUM STATUS
# =========================
def set_premium(user_id, value: bool):
    user = get_or_create_user(user_id)
    user["is_premium"] = bool(value)


def is_premium(user_id):
    user = get_or_create_user(user_id)
    return user["is_premium"]


# =========================
# DEBUG / ADMIN
# =========================
def get_all_users():
    return users

