import json
from typing import List, Tuple

# Centralized configuration for section status management

SECTION_STATUS_FILE = "section_status.json"

# (key, human-readable label)
SECTION_STATUS_OPTIONS: List[Tuple[str, str]] = [
    ("coming_soon", "🟡 Coming Soon"),
    ("error", "🔴 Error"),
    ("maintenance", "🛠️ Under Maintenance"),
    ("available", "🟢 Available"),
]

# (section_key, display name) – used by the owner Status panel
SECTION_KEYS: List[Tuple[str, str]] = [
    ("gift_cards", "Gift Cards"),
    ("dumps", "Dumps"),
    ("hacks", "Hacks"),
    ("cc", "Credit Cards"),
    ("bins", "BINs"),
    ("rdp", "RDP"),
    ("methods", "Methods"),
    ("custom_ccs", "Custom CCs"),
    ("phishing_kits", "Phishing Kits"),
    ("other", "Other"),
]


def set_section_status(section_key: str, status_key: str) -> None:
    """Persist a section's status to disk."""
    try:
        with open(SECTION_STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    data[section_key] = status_key
    with open(SECTION_STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)


def get_section_status(section_key: str) -> str:
    """Get a section's status; default to 'coming_soon' if missing or file absent."""
    try:
        with open(SECTION_STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Normalize legacy/mistyped keys
            if section_key == "gift_cards":
                # Some older files used a wrong key/value like {'gift': 'cards_maintenance'}
                if "gift_cards" not in data and "gift" in data and isinstance(data["gift"], str) and data["gift"].startswith("cards_"):
                    val = data["gift"].split("_", 1)[-1]
                    data["gift_cards"] = val
            raw = data.get(section_key, "coming_soon")
            # Normalize legacy status values
            norm = str(raw).strip().lower().replace(" ", "_")
            if norm in {"undermaintenance", "under_maintenance"}:
                norm = "maintenance"
            if norm in {"coming", "comingsoon"}:
                norm = "coming_soon"
            if norm == "cards_maintenance":
                norm = "maintenance"
            # Ensure it's one of the known keys
            valid_keys = {k for k, _ in SECTION_STATUS_OPTIONS}
            return norm if norm in valid_keys else "coming_soon"
    except Exception:
        return "coming_soon"


def get_section_status_label(section_key: str) -> str:
    """Return the human-readable label for a section's current status."""
    status_key = get_section_status(section_key)
    return next((label for key, label in SECTION_STATUS_OPTIONS if key == status_key), "🟡 Coming Soon")
