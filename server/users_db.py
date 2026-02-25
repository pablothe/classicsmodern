"""
User profile management for multi-user audiobook server.

Stores user profiles in a JSON file (users_db.json) alongside playback_db.json.
No authentication — profiles are just for family members sharing a LAN server.
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

USERS_DB = Path(__file__).parent / "users_db.json"

DEFAULT_SETTINGS = {
    "dark_mode": "light",
    "preferred_language": "en",
    "target_translation_language": "Modern English",
    "reader_prefs": {
        "fontSize": 18,
        "fontFamily": "Georgia, serif",
        "lineHeight": 1.8,
        "theme": "light",
        "audioSync": False
    }
}


def load_users_db() -> Dict:
    """Load users database from JSON file."""
    if not USERS_DB.exists():
        return {"users": []}
    try:
        with open(USERS_DB, 'r') as f:
            data = json.load(f)
        if "users" not in data:
            data["users"] = []
        return data
    except (json.JSONDecodeError, IOError):
        return {"users": []}


def save_users_db(db: Dict) -> None:
    """Save users database to JSON file."""
    with open(USERS_DB, 'w') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def _generate_user_id(name: str) -> str:
    """Generate a unique user ID from name + timestamp."""
    slug = re.sub(r'[^a-z0-9]', '', name.lower())[:12] or 'user'
    return f"user_{slug}_{int(time.time() * 1000)}"


def get_all_users() -> List[Dict]:
    """Return list of all user profiles (public fields only)."""
    db = load_users_db()
    return [
        {"user_id": u["user_id"], "name": u["name"], "avatar_emoji": u["avatar_emoji"]}
        for u in db["users"]
    ]


def get_user(user_id: str) -> Optional[Dict]:
    """Return full user profile including settings, or None."""
    db = load_users_db()
    for u in db["users"]:
        if u["user_id"] == user_id:
            return u
    return None


def create_user(name: str, avatar_emoji: str) -> Dict:
    """Create a new user profile. Returns the created user."""
    db = load_users_db()
    user = {
        "user_id": _generate_user_id(name),
        "name": name.strip()[:20],
        "avatar_emoji": avatar_emoji,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "settings": json.loads(json.dumps(DEFAULT_SETTINGS))  # deep copy
    }
    db["users"].append(user)
    save_users_db(db)
    return user


def update_user(user_id: str, updates: Dict) -> Optional[Dict]:
    """Update user profile fields. Returns updated user or None if not found."""
    db = load_users_db()
    for u in db["users"]:
        if u["user_id"] == user_id:
            if "name" in updates:
                u["name"] = str(updates["name"]).strip()[:20]
            if "avatar_emoji" in updates:
                u["avatar_emoji"] = updates["avatar_emoji"]
            if "settings" in updates:
                # Merge settings (partial update)
                for key, val in updates["settings"].items():
                    if key == "reader_prefs" and isinstance(val, dict):
                        u["settings"].setdefault("reader_prefs", {}).update(val)
                    else:
                        u["settings"][key] = val
            save_users_db(db)
            return u
    return None


def delete_user(user_id: str, playback_db: Dict = None) -> Optional[Dict]:
    """Delete user profile. Returns deleted user info or None.
    Also removes their playback data from playback_db if provided.
    Returns None if user not found. Raises ValueError if last user."""
    db = load_users_db()
    if len(db["users"]) <= 1:
        raise ValueError("Cannot delete the only profile")
    for i, u in enumerate(db["users"]):
        if u["user_id"] == user_id:
            deleted = db["users"].pop(i)
            save_users_db(db)
            # Clean up playback data
            entries_deleted = 0
            if playback_db is not None and user_id in playback_db:
                entries_deleted = len(playback_db[user_id])
                del playback_db[user_id]
            return {"user_id": user_id, "name": deleted["name"], "entries_deleted": entries_deleted}
    return None


def migrate_device_playback(playback_db: Dict, user_id: str) -> int:
    """Copy all device_* playback entries to a user profile key.
    Returns the number of entries migrated."""
    migrated = 0
    user_data = {}
    for key, entries in playback_db.items():
        if key.startswith("device_") and isinstance(entries, dict):
            for book_key, position in entries.items():
                if book_key not in user_data:
                    user_data[book_key] = position
                    migrated += 1
    if user_data:
        playback_db[user_id] = user_data
    return migrated


def ensure_initialized(playback_db: Dict) -> bool:
    """Ensure users_db has at least one user. Creates Guest + migrates if empty.
    Returns True if initialization was performed."""
    db = load_users_db()
    if db["users"]:
        return False

    # Create Guest profile
    guest = create_user("Guest", "👤")
    # Migrate existing device playback to Guest
    count = migrate_device_playback(playback_db, guest["user_id"])
    if count > 0:
        print(f"  Migrated {count} playback entries to Guest profile")
    return True
