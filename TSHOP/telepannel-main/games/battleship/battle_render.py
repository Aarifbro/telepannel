# games/battleship/battle_render.py

GRID_SIZE = 5
LETTERS = ["A", "B", "C", "D", "E"]

# ============================
# SYMBOLS
# ============================
EMPTY = "□"
HIT = "💥"
MISS = "🌊"


# ============================
# GRID RENDER
# ============================
def render_grid(grid):
    """
    Renders a 5x5 grid using monospace alignment
    """
    lines = ["<pre>  A B C D E"]
    for i, row in enumerate(grid, start=1):
        lines.append(f"{i} " + " ".join(row))
    lines.append("</pre>")
    return "\n".join(lines)


# ============================
# LOBBY SCREEN
# ============================
def render_lobby(host_name):
    return (
        "<b>⚓ BATTLESHIP HUNT</b>\n\n"
        f"> 👤 Host: <code>@{host_name}</code>\n"
        "> 👥 Opponent: <i>Waiting…</i>\n\n"
        "Invite a friend and ask them to press <b>Join Game</b>."
    )


# ============================
# BATTLE SCREEN
# ============================
def render_battle(enemy_grid, is_my_turn):
    status = "🎯 <b>YOUR TURN</b>" if is_my_turn else "⏳ <b>ENEMY TURN</b>"

    return (
        "<b>⚓ BATTLESHIP HUNT</b>\n\n"
        f"{status}\n\n"
        "<b>Enemy Grid</b>\n"
        f"{render_grid(enemy_grid)}"
    )


# ============================
# END SCREENS
# ============================
def render_victory():
    return (
        "<b>🏆 VICTORY</b>\n\n"
        "All enemy ships destroyed.\n"
        "Excellent command, Captain ⚓"
    )


def render_defeat():
    return (
        "<b>☠️ DEFEAT</b>\n\n"
        "Your fleet has been eliminated.\n"
        "Regroup and strike back."
    )

