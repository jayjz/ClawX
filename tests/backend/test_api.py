import uuid
import pytest
from httpx import AsyncClient

# All tests in this file are async and will be run by pytest-asyncio
pytestmark = pytest.mark.asyncio


def _unique_handle() -> str:
    """Generates a unique handle for creating new bots to avoid collisions."""
    return f"bot_{uuid.uuid4().hex[:8]}"


# --- Auth ---

async def test_auth_token_valid(client: AsyncClient, bot_and_token):
    """Tests that a valid bot_id and api_key pair successfully returns a token."""
    resp = await client.post(
        "/auth/token",
        json={"bot_id": bot_and_token["bot_id"], "api_key": bot_and_token["api_key"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_auth_token_invalid_key(client: AsyncClient, bot_and_token):
    """Tests that an invalid api_key for a valid bot_id is rejected."""
    resp = await client.post(
        "/auth/token",
        json={"bot_id": bot_and_token["bot_id"], "api_key": "wrong_key"},
    )
    assert resp.status_code == 401


async def test_auth_token_bot_not_found(client: AsyncClient):
    """Tests that a request for a non-existent bot_id is rejected."""
    resp = await client.post("/auth/token", json={"bot_id": 999999, "api_key": "test"})
    assert resp.status_code == 404


# --- Bots ---

async def test_create_bot(client: AsyncClient):
    """Tests successful creation of a new bot."""
    handle = _unique_handle()
    resp = await client.post(
        "/bots",
        json={
            "handle": handle,
            "persona_yaml": "persona: new bot",
            "api_key": "new_bot_secret",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["handle"] == handle
    assert "id" in data
    assert data["balance"] == 1000.0  # Check for genesis grant


async def test_create_bot_duplicate_handle(client: AsyncClient):
    """Tests that creating a bot with a duplicate handle is rejected."""
    handle = _unique_handle()
    json_payload = {
        "handle": handle,
        "persona_yaml": "persona: first",
        "api_key": "a_secret",
    }
    resp1 = await client.post("/bots", json=json_payload)
    assert resp1.status_code == 201

    resp2 = await client.post("/bots", json=json_payload)
    assert resp2.status_code == 409


async def test_get_bot_by_id(client: AsyncClient, bot_and_token):
    """Tests fetching a bot by its ID."""
    bot_id = bot_and_token["bot_id"]
    resp = await client.get(f"/bots/{bot_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == bot_id


async def test_get_bot_by_handle(client: AsyncClient, bot_and_token):
    """Tests fetching a bot by its unique handle."""
    bot_id = bot_and_token["bot_id"]
    resp = await client.get(f"/bots/{bot_id}")
    handle = resp.json()["handle"]

    resp = await client.get(f"/bots/{handle}")
    assert resp.status_code == 200
    assert resp.json()["handle"] == handle


async def test_get_bot_not_found(client: AsyncClient):
    """Tests that fetching a non-existent bot returns 404."""
    resp = await client.get("/bots/999999")
    assert resp.status_code == 404


# --- Posts ---

async def test_create_post(client: AsyncClient, bot_and_token):
    """Tests creating a simple, top-level post."""
    headers = bot_and_token["headers"]
    resp = await client.post(
        "/posts", json={"content": "Hello #world"}, headers=headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "Hello #world"
    assert data["parent_id"] is None


async def test_create_post_unauthorized(client: AsyncClient):
    """Tests that posting without a valid token is rejected."""
    resp = await client.post("/posts", json={"content": "No auth here"})
    assert resp.status_code == 401


async def test_create_post_reply(client: AsyncClient, bot_and_token):
    """Tests creating a reply to an existing post."""
    headers = bot_and_token["headers"]
    resp1 = await client.post(
        "/posts", json={"content": "This is the parent post"}, headers=headers
    )
    assert resp1.status_code == 201
    parent_id = resp1.json()["id"]

    resp2 = await client.post(
        "/posts",
        json={"content": "This is the reply", "parent_id": parent_id},
        headers=headers,
    )
    assert resp2.status_code == 201
    assert resp2.json()["parent_id"] == parent_id


# --- Feed ---

async def test_get_feed(client: AsyncClient, bot_and_token):
    """Tests that the global feed returns a list of posts."""
    headers = bot_and_token["headers"]
    await client.post("/posts", json={"content": "A post for the feed"}, headers=headers)
    resp = await client.get("/posts/feed")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "content" in data[0]


# --- Thread ---

async def test_get_thread(client: AsyncClient, bot_and_token):
    """Tests fetching a post and its replies."""
    headers = bot_and_token["headers"]
    resp1 = await client.post(
        "/posts", json={"content": "The root of a new thread"}, headers=headers
    )
    assert resp1.status_code == 201
    root_id = resp1.json()["id"]

    await client.post(
        "/posts",
        json={"content": "A reply in the thread", "parent_id": root_id},
        headers=headers,
    )

    resp = await client.get(f"/posts/{root_id}/thread")
    assert resp.status_code == 200
    data = resp.json()
    assert data["post"]["id"] == root_id
    assert len(data["replies"]) == 1
    assert data["replies"][0]["content"] == "A reply in the thread"


# --- Follows ---

async def test_follow(client: AsyncClient, bot_and_token):
    """Tests the follow functionality between two bots."""
    bot_id = bot_and_token["bot_id"]
    headers = bot_and_token["headers"]

    # Create a second bot to be followed
    handle = _unique_handle()
    resp = await client.post(
        "/bots",
        json={"handle": handle, "persona_yaml": "persona: target", "api_key": "secret"},
    )
    assert resp.status_code == 201
    target_id = resp.json()["id"]

    # First bot follows the second
    resp = await client.post(
        "/follows", json={"followee_bot_id": target_id}, headers=headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["follower_bot_id"] == bot_id
    assert data["followee_bot_id"] == target_id


async def test_follow_duplicate(client: AsyncClient, bot_and_token):
    """Tests that following the same bot twice results in a conflict."""
    headers = bot_and_token["headers"]
    handle = _unique_handle()
    resp = await client.post(
        "/bots",
        json={"handle": handle, "persona_yaml": "persona: target", "api_key": "secret"},
    )
    assert resp.status_code == 201
    target_id = resp.json()["id"]

    # First follow should succeed
    resp1 = await client.post(
        "/follows", json={"followee_bot_id": target_id}, headers=headers
    )
    assert resp1.status_code == 201

    # Second follow should fail
    resp2 = await client.post(
        "/follows", json={"followee_bot_id": target_id}, headers=headers
    )
    assert resp2.status_code == 409


async def test_follow_self(client: AsyncClient, bot_and_token):
    """Tests that a bot cannot follow itself."""
    bot_id = bot_and_token["bot_id"]
    headers = bot_and_token["headers"]
    resp = await client.post(
        "/follows", json={"followee_bot_id": bot_id}, headers=headers
    )
    assert resp.status_code == 400
