#!/usr/bin/env python3
"""Unit tests for server/users_db.py"""

import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import server.users_db as users_db_module
from server.users_db import (
    create_user, get_user, get_all_users, update_user, delete_user,
    _generate_user_id, ensure_initialized, migrate_device_playback,
    load_users_db, DEFAULT_SETTINGS,
)


@pytest.fixture(autouse=True)
def patch_users_db_path(temp_dir, monkeypatch):
    """Redirect USERS_DB to temp dir for all tests in this module."""
    db_path = temp_dir / "users_db.json"
    monkeypatch.setattr(users_db_module, "USERS_DB", db_path)
    return db_path


class TestLoadUsersDB:
    def test_empty_db_returns_default(self):
        db = load_users_db()
        assert db == {"users": []}

    def test_loads_existing_db(self, patch_users_db_path):
        data = {"users": [{"user_id": "test", "name": "Test", "avatar_emoji": "X"}]}
        patch_users_db_path.write_text(json.dumps(data))
        db = load_users_db()
        assert len(db["users"]) == 1


class TestCreateUser:
    def test_create_user(self):
        user = create_user("Alice", "🐰")
        assert user["name"] == "Alice"
        assert user["avatar_emoji"] == "🐰"
        assert "user_id" in user
        assert "settings" in user

    def test_name_truncated(self):
        user = create_user("A" * 50, "X")
        assert len(user["name"]) <= 20

    def test_settings_inherited_from_defaults(self):
        user = create_user("Bob", "🎩")
        assert user["settings"]["dark_mode"] == DEFAULT_SETTINGS["dark_mode"]
        assert "reader_prefs" in user["settings"]


class TestGetUser:
    def test_get_existing_user(self):
        user = create_user("Charlie", "🎭")
        found = get_user(user["user_id"])
        assert found is not None
        assert found["name"] == "Charlie"

    def test_get_nonexistent_returns_none(self):
        assert get_user("nonexistent_id") is None


class TestGetAllUsers:
    def test_public_fields_only(self):
        create_user("Dave", "🌟")
        users = get_all_users()
        assert len(users) == 1
        assert "user_id" in users[0]
        assert "name" in users[0]
        assert "settings" not in users[0]  # Private field excluded


class TestUpdateUser:
    def test_update_name(self):
        user = create_user("Eve", "🔮")
        updated = update_user(user["user_id"], {"name": "Eve Updated"})
        assert updated["name"] == "Eve Updated"

    def test_update_settings_merge(self):
        user = create_user("Frank", "🎸")
        update_user(user["user_id"], {"settings": {"dark_mode": "dark"}})
        found = get_user(user["user_id"])
        assert found["settings"]["dark_mode"] == "dark"
        # Other settings should still be present
        assert "reader_prefs" in found["settings"]

    def test_update_nonexistent_returns_none(self):
        assert update_user("nonexistent", {"name": "test"}) is None


class TestDeleteUser:
    def test_delete_success(self):
        user1 = create_user("Grace", "👩")
        user2 = create_user("Hank", "👨")
        result = delete_user(user2["user_id"])
        assert result is not None
        assert result["name"] == "Hank"
        assert get_user(user2["user_id"]) is None

    def test_delete_last_user_raises(self):
        user = create_user("Ivan", "🎯")
        with pytest.raises(ValueError, match="Cannot delete"):
            delete_user(user["user_id"])

    def test_delete_cleans_playback(self):
        user1 = create_user("Judy", "🎵")
        user2 = create_user("Karl", "🎹")
        playback_db = {user2["user_id"]: {"book1": {"position": 10}}}
        result = delete_user(user2["user_id"], playback_db)
        assert result["entries_deleted"] == 1
        assert user2["user_id"] not in playback_db

    def test_delete_nonexistent_returns_none(self):
        create_user("Filler1", "A")
        create_user("Filler2", "B")
        assert delete_user("nonexistent") is None


class TestGenerateUserId:
    def test_format(self):
        uid = _generate_user_id("Test User")
        assert uid.startswith("user_")
        assert "testuser" in uid

    def test_special_chars_stripped(self):
        uid = _generate_user_id("Test! @#$ User")
        assert "!" not in uid
        assert "@" not in uid


class TestEnsureInitialized:
    def test_creates_guest(self):
        playback_db = {}
        result = ensure_initialized(playback_db)
        assert result is True
        users = get_all_users()
        assert len(users) == 1
        assert users[0]["name"] == "Guest"

    def test_noop_when_users_exist(self):
        create_user("Existing", "🎯")
        result = ensure_initialized({})
        assert result is False


class TestMigrateDevicePlayback:
    def test_migrates_device_entries(self):
        playback_db = {
            "device_abc": {"book1": {"position": 10}},
            "device_xyz": {"book2": {"position": 20}},
        }
        count = migrate_device_playback(playback_db, "user_test")
        assert count == 2
        assert "user_test" in playback_db
