#!/usr/bin/env python3
"""Integration tests for user profile API routes."""

import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

try:
    import server.users_db as users_db_module
    from server.users_db import create_user, get_all_users, load_users_db
    USERS_DB_AVAILABLE = True
except ImportError:
    USERS_DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not FASTAPI_AVAILABLE or not USERS_DB_AVAILABLE,
    reason="FastAPI or users_db not available"
)


@pytest.fixture
def users_app(temp_dir, monkeypatch):
    """Create a minimal FastAPI app with user routes for testing."""
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse

    db_path = temp_dir / "users_db.json"
    monkeypatch.setattr(users_db_module, "USERS_DB", db_path)

    app = FastAPI()

    @app.get("/api/users")
    def list_users():
        return get_all_users()

    @app.post("/api/users")
    def create_new_user(body: dict):
        name = body.get("name", "Guest")
        emoji = body.get("avatar_emoji", "G")
        user = create_user(name, emoji)
        return user

    @app.get("/api/users/{user_id}")
    def get_user_detail(user_id: str):
        from server.users_db import get_user
        user = get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    @app.patch("/api/users/{user_id}")
    def update_user_detail(user_id: str, body: dict):
        from server.users_db import update_user
        result = update_user(user_id, body)
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        return result

    @app.delete("/api/users/{user_id}")
    def delete_user_route(user_id: str):
        from server.users_db import delete_user
        try:
            result = delete_user(user_id)
            if not result:
                raise HTTPException(status_code=404, detail="User not found")
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    return TestClient(app)


class TestListUsers:
    def test_empty_initially(self, users_app):
        resp = users_app.get("/api/users")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_lists_created_users(self, users_app):
        users_app.post("/api/users", json={"name": "Alice", "avatar_emoji": "A"})
        users_app.post("/api/users", json={"name": "Bob", "avatar_emoji": "B"})
        resp = users_app.get("/api/users")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestCreateUser:
    def test_create_user(self, users_app):
        resp = users_app.post("/api/users", json={"name": "Charlie", "avatar_emoji": "C"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Charlie"
        assert "user_id" in data

    def test_created_user_retrievable(self, users_app):
        resp = users_app.post("/api/users", json={"name": "Dave", "avatar_emoji": "D"})
        user_id = resp.json()["user_id"]
        resp2 = users_app.get(f"/api/users/{user_id}")
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "Dave"


class TestGetUser:
    def test_nonexistent_returns_404(self, users_app):
        resp = users_app.get("/api/users/nonexistent_id")
        assert resp.status_code == 404


class TestUpdateUser:
    def test_update_name(self, users_app):
        resp = users_app.post("/api/users", json={"name": "Eve", "avatar_emoji": "E"})
        user_id = resp.json()["user_id"]
        resp2 = users_app.patch(f"/api/users/{user_id}", json={"name": "Eve Updated"})
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "Eve Updated"

    def test_update_nonexistent_returns_404(self, users_app):
        resp = users_app.patch("/api/users/nonexistent", json={"name": "test"})
        assert resp.status_code == 404


class TestDeleteUser:
    def test_delete_user(self, users_app):
        users_app.post("/api/users", json={"name": "User1", "avatar_emoji": "1"})
        resp2 = users_app.post("/api/users", json={"name": "User2", "avatar_emoji": "2"})
        user2_id = resp2.json()["user_id"]
        resp = users_app.delete(f"/api/users/{user2_id}")
        assert resp.status_code == 200

    def test_delete_last_user_returns_400(self, users_app):
        resp = users_app.post("/api/users", json={"name": "OnlyUser", "avatar_emoji": "O"})
        user_id = resp.json()["user_id"]
        resp2 = users_app.delete(f"/api/users/{user_id}")
        assert resp2.status_code == 400

    def test_delete_nonexistent_returns_404(self, users_app):
        users_app.post("/api/users", json={"name": "Filler1", "avatar_emoji": "F"})
        users_app.post("/api/users", json={"name": "Filler2", "avatar_emoji": "G"})
        resp = users_app.delete("/api/users/nonexistent")
        assert resp.status_code == 404
