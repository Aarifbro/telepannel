# monetization/skins.py

"""
Central skin registry for the entire bot.
All banners (games, shop previews, profile headers) come from here.
"""

SKINS = {
    # =========================
    # FREE / DEFAULT
    # =========================
    "default_naval": {
        "name": "Classic Naval Radar",
        "description": "Standard military radar interface.",
        "price": 0,
        "type": "photo",  # photo | animation
        "file_id": "AgACAgIAAxkBAAIBsmcDEFAULTNAVAL",  # fake placeholder
        "rarity": "common",
    },

    # =========================
    # PREMIUM SKINS
    # =========================
    "cyber_neon": {
        "name": "Cyber Neon Tactical",
        "description": "Pulsing neon HUD with cyber warfare vibes.",
        "price": 150,
        "type": "animation",
        "file_id": "CgACAgIAAxkBAAIBsmcCYBERNEON",
        "rarity": "epic",
    },

    "deep_abyss_kraken": {
        "name": "Deep Abyss Kraken",
        "description": "Dark ocean depths with glowing kraken tentacles.",
        "price": 180,
        "type": "animation",
        "file_id": "CgACAgIAAxkBAAIBsmcABYSSKRAKEN",
        "rarity": "legendary",
    },

    "space_fleet": {
        "name": "Space Fleet Command",
        "description": "Sci-fi starship bridge with holographic panels.",
        "price": 220,
        "type": "animation",
        "file_id": "CgACAgIAAxkBAAIBsmcSPACEFLEET",
        "rarity": "legendary",
    },
}

