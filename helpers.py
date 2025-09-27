import random
from config import FORCE_CHANNEL_IDS, ADMIN_ID

def check_force_join(bot, user_id):
    """
    Checks if a user is a member of ALL force-join channels/groups in FORCE_CHANNEL_IDS.
    Returns True only if they are a member of every channel/group.
    """
    try:
        for channel_id in FORCE_CHANNEL_IDS:
            member = bot.get_chat_member(channel_id, user_id)
            if member.status in ["left", "kicked"]:
                return False
        return True
    except Exception as e:
        print(f"Force join check failed: {e}")
        return False

def notify_admin(bot, message, markup=None):
    """
    Sends a notification message to the admin, with an optional keyboard.
    This is used for startup notifications, crash alerts, and new orders.
    """
    try:
        bot.send_message(ADMIN_ID, message, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Failed to notify admin: {e}")

def get_country_list():
    """
    Returns a comprehensive list of countries with their corresponding flag emojis.
    This list is used in the 'Customize CC' section.
    """
    return {
        # Asia & Middle East
        "Afghanistan": "🇦🇫", "Bahrain": "🇧🇭", "Bangladesh": "🇧🇩", "Bhutan": "🇧🇹", 
        "Brunei": "🇧🇳", "Cambodia": "🇰🇭", "China": "🇨🇳", "India": "🇮🇳", 
        "Indonesia": "🇮🇩", "Iran": "🇮🇷", "Iraq": "🇮🇶", "Israel": "🇮🇱", 
        "Japan": "🇯🇵", "Jordan": "🇯🇴", "Kazakhstan": "🇰🇿", "Kuwait": "🇰🇼", 
        "Kyrgyzstan": "🇰🇬", "Laos": "🇱🇦", "Lebanon": "🇱🇧", "Malaysia": "🇲🇾", 
        "Maldives": "🇲🇻", "Mongolia": "🇲🇳", "Nepal": "🇳🇵", "Oman": "🇴🇲", 
        "Pakistan": "🇵🇰", "Philippines": "🇵🇭", "Qatar": "🇶🇦", "Saudi Arabia": "🇸🇦", 
        "Singapore": "🇸🇬", "South Korea": "🇰🇷", "Sri Lanka": "🇱🇰", "Syria": "🇸🇾", 
        "Taiwan": "🇹🇼", "Thailand": "🇹🇭", "Turkey": "🇹🇷", "Turkmenistan": "🇹🇲", 
        "United Arab Emirates": "🇦🇪", "Uzbekistan": "🇺🇿", "Vietnam": "🇻🇳", "Yemen": "🇾🇪",

        # Europe
        "Albania": "🇦🇱", "Andorra": "🇦🇩", "Austria": "🇦🇹", "Belarus": "🇧🇾", 
        "Belgium": "🇧🇪", "Bosnia & Herzegovina": "🇧🇦", "Bulgaria": "🇧🇬", 
        "Croatia": "🇭🇷", "Cyprus": "🇨🇾", "Czech Republic": "🇨🇿", "Denmark": "🇩🇰", 
        "Estonia": "🇪🇪", "Finland": "🇫🇮", "France": "🇫🇷", "Germany": "🇩🇪", 
        "Greece": "🇬🇷", "Hungary": "🇭🇺", "Iceland": "🇮🇸", "Ireland": "🇮🇪", 
        "Italy": "🇮🇹", "Latvia": "🇱🇻", "Liechtenstein": "🇱🇮", "Lithuania": "🇱🇹", 
        "Luxembourg": "🇱🇺", "Malta": "🇲🇹", "Moldova": "🇲🇩", "Monaco": "🇲🇨", 
        "Montenegro": "🇲🇪", "Netherlands": "🇳🇱", "North Macedonia": "🇲🇰", 
        "Norway": "🇳🇴", "Poland": "🇵🇱", "Portugal": "🇵🇹", "Romania": "🇷🇴", 
        "Russia": "🇷🇺", "San Marino": "🇸🇲", "Serbia": "🇷🇸", "Slovakia": "🇸🇰", 
        "Slovenia": "🇸🇮", "Spain": "🇪🇸", "Sweden": "🇸🇪", "Switzerland": "🇨🇭", 
        "Ukraine": "🇺🇦", "United Kingdom": "🇬🇧", "Vatican City": "🇻🇦",

        # North & South America
        "Antigua & Barbuda": "🇦🇬", "Argentina": "🇦🇷", "Bahamas": "🇧🇸", "Barbados": "🇧🇧", 
        "Belize": "🇧🇿", "Bolivia": "🇧🇴", "Brazil": "🇧🇷", "Canada": "🇨🇦", 
        "Chile": "🇨🇱", "Colombia": "🇨🇴", "Costa Rica": "🇨🇷", "Cuba": "🇨🇺", 
        "Dominica": "🇩🇲", "Dominican Republic": "🇩🇴", "Ecuador": "🇪🇨", 
        "El Salvador": "🇸🇻", "Grenada": "🇬🇩", "Guatemala": "🇬🇹", "Guyana": "🇬🇾", 
        "Haiti": "🇭🇹", "Honduras": "🇭🇳", "Jamaica": "🇯🇲", "Mexico": "🇲🇽", 
        "Nicaragua": "🇳🇮", "Panama": "🇵🇦", "Paraguay": "🇵🇾", "Peru": "🇵🇪", 
        "St. Kitts & Nevis": "🇰🇳", "St. Lucia": "🇱🇨", "St. Vincent & Grenadines": "🇻🇨", 
        "Suriname": "🇸🇷", "Trinidad & Tobago": "🇹🇹", "United States": "🇺🇸", 
        "Uruguay": "🇺🇾", "Venezuela": "🇻🇪",

        # Africa
        "Algeria": "🇩🇿", "Angola": "🇦🇴", "Benin": "🇧🇯", "Botswana": "🇧🇼", 
        "Burkina Faso": "🇧🇫", "Cameroon": "🇨🇲", "Chad": "🇹🇩", "Congo": "🇨🇬", 
        "Egypt": "🇪🇬", "Ethiopia": "🇪🇹", "Gabon": "🇬🇦", "Ghana": "🇬🇭", 
        "Kenya": "🇰🇪", "Libya": "🇱🇾", "Madagascar": "🇲🇬", "Mali": "🇲🇱", 
        "Morocco": "🇲🇦", "Mozambique": "🇲🇿", "Namibia": "🇳🇦", "Nigeria": "🇳🇬", 
        "Senegal": "🇸🇳", "Somalia": "🇸🇴", "South Africa": "🇿🇦", "Sudan": "🇸🇩", 
        "Tanzania": "🇹🇿", "Tunisia": "🇹🇳", "Uganda": "🇺🇬", "Zambia": "🇿🇲", 
        "Zimbabwe": "🇿🇼",

        # Oceania
        "Australia": "🇦🇺", "Fiji": "🇫🇯", "New Zealand": "🇳🇿", "Papua New Guinea": "🇵🇬",
        "Samoa": "🇼🇸", "Solomon Islands": "🇸🇧", "Tonga": "🇹🇴", "Vanuatu": "🇻🇺"
    }

def generate_fake_details():
    """
    Generates fake name details for an order to be displayed after a successful payment.
    This adds a layer of realism to the product delivery message.
    """
    first_names = ["John", "Michael", "David", "James", "Robert", "William"]
    last_names = ["Smith", "Jones", "Williams", "Brown", "Davis", "Miller"]
    return {"name": f"{random.choice(first_names)} {random.choice(last_names)}"}

def update_state(state_str, index, value):
    """
    Updates a state string used in the multi-step 'Customize CC' flow.
    Example: "VISA~None~None~None" -> "VISA~Credit~None~None"
    """
    parts = state_str.split('~')
    parts[index] = str(value) if value is not None else "None"
    return '~'.join(parts)

def get_state_summary(state_str):
    """
    Creates a user-friendly summary from the CC customization state string.
    This is shown to the user at each step of the customization process.
    """
    parts = state_str.split('~')
    brand, mode, country, level = parts[0], parts[1], parts[2], parts[3]
    summary = ""
    if brand != "None": summary += f"**Brand:** `{brand}`\n"
    if mode != "None": summary += f"**Mode:** `{mode}`\n"
    if country != "None": summary += f"**Country:** `{country}`\n"
    if level != "None": summary += f"**Level:** `{level}`\n"
    return summary if summary else "No selections made yet.\n"

