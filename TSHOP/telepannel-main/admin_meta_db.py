import sqlite3
import json
from typing import Dict, List, Tuple

DB_FILE = 'admin_meta.db'

SECTION_STATUS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS section_status (
  section_key TEXT PRIMARY KEY,
  status_key TEXT NOT NULL,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

def init_admin_meta():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(SECTION_STATUS_TABLE_SQL)
        conn.commit()
    # Perform one-time alias normalization for legacy keys
    try:
        normalize_legacy_section_keys()
    except Exception as e:
        print(f"Legacy section key normalization failed: {e}")

def migrate_from_json(json_path: str):
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {}
    if not data:
        return
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        for k, v in data.items():
            c.execute("INSERT OR REPLACE INTO section_status (section_key, status_key) VALUES (?, ?)", (k, v))
        conn.commit()

def get_section_status(section_key: str, default: str = 'coming_soon') -> str:
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor(); c.execute("SELECT status_key FROM section_status WHERE section_key = ?", (section_key,))
        row = c.fetchone()
        return row[0] if row else default

def set_section_status(section_key: str, status_key: str):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor(); c.execute(
            "INSERT OR REPLACE INTO section_status (section_key, status_key, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (section_key, status_key)
        ); conn.commit()

def list_all_statuses() -> List[Tuple[str, str]]:
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor(); c.execute("SELECT section_key, status_key FROM section_status ORDER BY section_key")
        return c.fetchall()

# --- Legacy Key Normalization ---
LEGACY_BUNDLE_KEYS = ["bins", "methods", "bin_methods", "bins_methods"]
UNIFIED_BUNDLE_KEY = "bins_methods"  # We retain this key for status gating; products use 'method_bins'

def normalize_legacy_section_keys():
    """Ensure only unified bundle key is stored; migrate any legacy keys to UNIFIED_BUNDLE_KEY.
    If multiple legacy keys exist, prefer first non-coming_soon status, else keep existing unified key.
    """
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        # Fetch existing entries
        c.execute("SELECT section_key, status_key FROM section_status")
        rows = c.fetchall()
        legacy_found = {k: v for k, v in rows if k in LEGACY_BUNDLE_KEYS}
        if not legacy_found:
            return
        # Determine final status to keep
        priority_order = ["available", "maintenance", "error", "coming_soon"]
        chosen = None
        for status in priority_order:
            for k, v in legacy_found.items():
                if v == status:
                    chosen = v; break
            if chosen:
                break
        if chosen is None:
            chosen = "coming_soon"
        # Upsert unified key
        c.execute("INSERT OR REPLACE INTO section_status (section_key, status_key, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (UNIFIED_BUNDLE_KEY, chosen))
        # Delete old keys except unified
        for lk in LEGACY_BUNDLE_KEYS:
            if lk != UNIFIED_BUNDLE_KEY:
                c.execute("DELETE FROM section_status WHERE section_key = ?", (lk,))
        conn.commit()
        print(f"[migration] Normalized legacy bundle section keys -> {UNIFIED_BUNDLE_KEY}={chosen}")
