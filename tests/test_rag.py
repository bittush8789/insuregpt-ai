"""
Automated Test Suite for InsureGPT Phase 1.
Tests FastAPI endpoints, MySQL persistence, Conversation CRUD, and SSE streaming chat.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.mysql import init_db

# Initialize database schema before running tests
init_db()

client = TestClient(app)


def test_health_check():
    """Verify that /api/health reports server operational status and healthy database."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "InsureGPT"
    assert data["database"] == "healthy"
    assert "timestamp" in data


def test_conversation_lifecycle():
    """Verify full CRUD lifecycle for chat conversations."""
    # 1. Create Conversation
    create_res = client.post("/api/conversations", json={"title": "Test Health Policy Inquiry"})
    assert create_res.status_code == 201
    created_conv = create_res.json()
    conv_id = created_conv["id"]
    assert created_conv["title"] == "Test Health Policy Inquiry"

    # 2. List Conversations
    list_res = client.get("/api/conversations")
    assert list_res.status_code == 200
    conversations = list_res.json()
    assert any(c["id"] == conv_id for c in conversations)

    # 3. Retrieve Single Conversation
    get_res = client.get(f"/api/conversations/{conv_id}")
    assert get_res.status_code == 200
    detail = get_res.json()
    assert detail["id"] == conv_id
    assert detail["title"] == "Test Health Policy Inquiry"
    assert isinstance(detail["messages"], list)

    # 4. Update Conversation Title
    patch_res = client.patch(f"/api/conversations/{conv_id}", json={"title": "Updated Policy Inquiry"})
    assert patch_res.status_code == 200
    updated_conv = patch_res.json()
    assert updated_conv["title"] == "Updated Policy Inquiry"

    # 5. Delete Conversation
    del_res = client.delete(f"/api/conversations/{conv_id}")
    assert del_res.status_code == 200

    # 6. Verify Deletion
    verify_get = client.get(f"/api/conversations/{conv_id}")
    assert verify_get.status_code == 404


def test_chat_streaming_endpoint():
    """Verify POST /api/chat persists user/assistant messages and streams SSE tokens."""
    # 1. Create a conversation
    create_res = client.post("/api/conversations", json={"title": "Hospitalization Stream Test"})
    conv_id = create_res.json()["id"]

    # 2. Send Chat Query with SSE stream
    with client.stream(
        "POST",
        "/api/chat",
        json={"conversation_id": conv_id, "message": "Is hospitalization covered under this policy?"}
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        content = ""
        for line in response.iter_lines():
            if line:
                content += line + "\n"

        assert "event: metadata" in content
        assert "event: token" in content
        assert "event: done" in content

    # 3. Verify messages are saved in MySQL database
    conv_res = client.get(f"/api/conversations/{conv_id}")
    assert conv_res.status_code == 200
    conv_data = conv_res.json()
    assert len(conv_data["messages"]) >= 2

    roles = [m["role"] for m in conv_data["messages"]]
    assert "user" in roles
    assert "assistant" in roles

    # Clean up test conversation
    client.delete(f"/api/conversations/{conv_id}")


def test_document_upload_skeleton():
    """Verify document upload skeleton endpoint in Phase 1."""
    fake_file = ("sample_policy.txt", b"Sample insurance policy terms and conditions", "text/plain")
    response = client.post(
        "/api/documents/upload",
        files={"file": fake_file},
        data={"document_type": "policy", "version": "2026.1"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "sample_policy.txt"
    assert data["status"] == "ready_for_phase2"
