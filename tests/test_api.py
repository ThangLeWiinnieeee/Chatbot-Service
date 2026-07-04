"""Test tầng HTTP (FastAPI) với engine đã override (AI giả)."""
from __future__ import annotations


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_chat_greeting(client):
    resp = client.post("/api/chat", json={"message": "xin chào"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "greeting"
    assert body["answer"]
    assert "confidence" in body


def test_chat_intent_register(client):
    resp = client.post("/api/chat", json={"message": "làm sao để đăng ký tài khoản"})
    assert resp.status_code == 200
    assert resp.json()["intent"] in ("register", "register_account")


def test_chat_with_history(client):
    resp = client.post(
        "/api/chat",
        json={
            "message": "học phí như thế nào",
            "history": [
                {"role": "user", "content": "chào bạn"},
                {"role": "assistant", "content": "Chào bạn!"},
            ],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["answer"]


def test_chat_rejects_empty_message(client):
    resp = client.post("/api/chat", json={"message": ""})
    assert resp.status_code == 422
