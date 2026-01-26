# monetization/battle_ship_game/banners.py

def should_show_banner(game_phase):
    """
    You may later disable banners for some phases
    """
    return game_phase in ("lobby", "placement", "battle", "end")