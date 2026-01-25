# games/battleship/battle_ship_game.py

import uuid
import random
from telebot import types

from monetization.user_store import add_coins, record_game_result
from monetization.game_renderer import render_game_message

GRID_SIZE = 5
LETTERS = ["A", "B", "C", "D", "E"]
MAX_ATTEMPTS = 10

# Ship definitions
SHIP_SIZES = [3, 2, 1]

battleship_games = {}

BOT_USERNAME = "tshopybot"  # without @

def handle_battleship_deeplink(bot, user_id, game_id):
    game = battleship_games.get(game_id)

    if not game:
        bot.send_message(user_id, "❌ This Battleship game no longer exists.")
        return

    if game.get("ai"):
        bot.send_message(user_id, "❌ This is a solo game.")
        return

    if game.get("defender"):
        bot.send_message(user_id, "❌ This game is already full.")
        return

    game["defender"] = user_id
    game["phase"] = "placement"
    game["placed_cells"] = set()

    _render_placement(bot, game)


def register_battleship_handlers(bot):

    # =========================
    # GAME MODE SELECTION
    # =========================
    @bot.callback_query_handler(func=lambda call: call.data == "bs_create")
    def bs_create(call):
        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("🤖 Solo vs AI", callback_data="bs_solo"),
            types.InlineKeyboardButton("👥 Play vs Friend", callback_data="bs_multi"),
        )

        render_game_message(
            bot,
            call.from_user.id,
            "menu",
            (
                "<b>⚓ BATTLESHIP HUNT</b>\n\n"
                "Choose your battle mode:\n\n"
                "🤖 <b>Solo</b> — Attack AI ships\n"
                "👥 <b>Multiplayer</b> — Invite a friend"
            ),
            kb,
        )

    # =========================
    # SOLO MODE
    # =========================
    @bot.callback_query_handler(func=lambda call: call.data == "bs_solo")
    def bs_solo(call):
        game_id = uuid.uuid4().hex[:8]

        ships = _generate_ai_ships()

        battleship_games[game_id] = {
            "game_id": game_id,
            "attacker": call.from_user.id,
            "defender": "AI",
            "ships": ships,
            "hits": set(),
            "shots": set(),
            "attempts_left": MAX_ATTEMPTS,
            "phase": "battle",
            "ai": True,
        }

        _render_battle(bot, game_id)

    # =========================
    # MULTI MODE (FRIEND)
    # =========================
    @bot.callback_query_handler(func=lambda call: call.data == "bs_multi")
    def bs_multi(call):
        game_id = uuid.uuid4().hex[:8]

        battleship_games[game_id] = {
            "game_id": game_id,
            "attacker": call.from_user.id,
            "defender": None,
            "ships": [],
            "hits": set(),
            "shots": set(),
            "attempts_left": MAX_ATTEMPTS,
            "phase": "placement",
            "ai": False,
        }

        invite = f"https://t.me/{BOT_USERNAME}?start=bs_{game_id}"

        render_game_message(
            bot,
            call.from_user.id,
            game_id,
            (
                "<b>⚓ BATTLESHIP HUNT</b>\n\n"
                "👥 Waiting for defender…\n\n"
                "<b>Invite Link</b>\n"
                f"<code>{invite}</code>"
            ),
        )

    # =========================
    # ATTACK
    # =========================
    @bot.callback_query_handler(func=lambda call: call.data.startswith("bs_attack|"))
    def bs_attack(call):
        _, game_id, coord = call.data.split("|")
        game = battleship_games.get(game_id)

        if not game or game["phase"] != "battle":
            return

        r = LETTERS.index(coord[0])
        c = int(coord[1]) - 1

        if (r, c) in game["shots"]:
            return

        game["shots"].add((r, c))
        game["attempts_left"] -= 1

        hit = False
        for ship in game["ships"]:
            if (r, c) in ship:
                game["hits"].add((r, c))
                hit = True
                break

        if len(game["hits"]) == sum(len(s) for s in game["ships"]):
            _end_game(bot, game_id, True)
            return

        if game["attempts_left"] <= 0:
            _end_game(bot, game_id, False)
            return

        _render_battle(bot, game_id)


    @bot.callback_query_handler(func=lambda call: call.data.startswith("bs_place|"))
    def bs_place(call):
        _, game_id, coord = call.data.split("|")
        game = battleship_games.get(game_id)

        if not game or game["phase"] != "placement":
            return

        if call.from_user.id != game["defender"]:
            return

        r = LETTERS.index(coord[0])
        c = int(coord[1]) - 1

        if (r, c) in game["placed_cells"]:
            return

        game["placed_cells"].add((r, c))

    # If placement complete → start battle
        if len(game["placed_cells"]) >= 6:
            game["ships"] = [
             set(game["placed_cells"])
            ]
            game["hits"] = set()
            game["shots"] = set()
            game["attempts_left"] = MAX_ATTEMPTS
            game["phase"] = "battle"

            render_game_message(
            bot,
            game["attacker"],
            game_id,
            "🛡️ Defender finished placement.\n<b>Battle started!</b>",
            )

            _render_battle(bot, game_id)
            return

        _render_placement(bot, game)
 
# =========================
# CORE RENDER
# =========================
def _render_battle(bot, game_id):
    game = battleship_games[game_id]
    user_id = game["attacker"]

    grid = [["□"] * GRID_SIZE for _ in range(GRID_SIZE)]
    for r, c in game["shots"]:
        grid[r][c] = "🌊"
    for r, c in game["hits"]:
        grid[r][c] = "💥"

    kb = types.InlineKeyboardMarkup(row_width=5)
    for r in range(GRID_SIZE):
        row = []
        for c in range(GRID_SIZE):
            if (r, c) not in game["shots"]:
                coord = f"{LETTERS[r]}{c+1}"
                row.append(
                    types.InlineKeyboardButton(
                        coord,
                        callback_data=f"bs_attack|{game_id}|{coord}",
                    )
                )
        kb.add(*row)

    text = (
        "╔══ ⚓ <b>BATTLESHIP HUNT</b> ══╗\n"
        f"🎯 <b>Attempts Left:</b> <code>{game['attempts_left']}</code>\n\n"
        "<b>Enemy Grid</b>\n"
        f"{_grid_to_text(grid)}"
    )

    render_game_message(bot, user_id, game_id, text, kb)

def _render_placement(bot, game):
    defender = game["defender"]
    game_id = game["game_id"]

    grid = [["□"] * GRID_SIZE for _ in range(GRID_SIZE)]
    for r, c in game["placed_cells"]:
        grid[r][c] = "🚢"

    remaining = 6 - len(game["placed_cells"])

    text = (
        "╔══ 🛡️ <b>SHIP PLACEMENT</b> ══╗\n\n"
        f"> Tap cells to place ships\n"
        f"> Remaining cells: <code>{remaining}</code>\n\n"
        "<b>Your Grid</b>\n"
        f"{_grid_to_text(grid)}"
    )

    kb = types.InlineKeyboardMarkup(row_width=5)
    for r in range(GRID_SIZE):
        row = []
        for c in range(GRID_SIZE):
            if (r, c) not in game["placed_cells"]:
                coord = f"{LETTERS[r]}{c+1}"
                row.append(
                    types.InlineKeyboardButton(
                        coord,
                        callback_data=f"bs_place|{game_id}|{coord}",
                    )
                )
        kb.add(*row)

    render_game_message(bot, defender, game_id, text, kb)


# =========================
# END GAME
# =========================
def _end_game(bot, game_id, victory):
    game = battleship_games.pop(game_id)
    user = game["attacker"]

    if victory:
        add_coins(user, 140, "Battleship win")
        record_game_result(user, True)
        result = "🏆 <b>VICTORY</b>\n\nYou destroyed all ships!"
    else:
        add_coins(user, -40, "Battleship loss")
        record_game_result(user, False)
        result = "☠️ <b>DEFEAT</b>\n\nYou ran out of attempts."

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔁 Rematch", callback_data="bs_create"))

    render_game_message(bot, user, "end", result, kb)


# =========================
# UTILITIES
# =========================
def _generate_ai_ships():
    ships = []
    occupied = set()

    for size in SHIP_SIZES:
        placed = False
        while not placed:
            r = random.randint(0, 4)
            c = random.randint(0, 4)
            horizontal = random.choice([True, False])

            coords = []
            for i in range(size):
                nr = r
                nc = c + i if horizontal else c
                nr = r + i if not horizontal else r
                if nr > 4 or nc > 4:
                    break
                coords.append((nr, nc))

            if len(coords) == size and not any(p in occupied for p in coords):
                ships.append(set(coords))
                occupied.update(coords)
                placed = True

    return ships


def _grid_to_text(grid):
    lines = ["<pre>  A B C D E"]
    for i, row in enumerate(grid, start=1):
        lines.append(f"{i} " + " ".join(row))
    lines.append("</pre>")
    return "\n".join(lines)

