"""
Pruebas del flujo Secure con servicios separados — T01, T02 y T03.
"""
import json

import pytest

from app.logging_config import _secure_log_path

PII_MESSAGE = (
    "Mi nombre es Juan Carlos Pérez Gómez, cédula 1.020.304.050, "
    "correo juan.perez@gmail.com, celular 3001234567"
)
PII_VALUES = ("Juan Carlos Pérez Gómez", "1.020.304.050", "juan.perez@gmail.com", "3001234567")


@pytest.fixture(autouse=True)
def clean_log():
    if _secure_log_path().exists():
        _secure_log_path().unlink()
    yield


def test_secure_chat_returns_useful_response(client):
    body = client.post("/secure/chat", json={"user_id": "u1", "message": PII_MESSAGE}).json()
    for value in PII_VALUES:
        assert value in body["response"]  # el usuario legítimo ve sus datos
    assert set(body["entities_detected"]) == {"PERSON", "CEDULA_CO", "EMAIL_ADDRESS", "TELEFONO_CO"}


def test_chatbot_never_receives_raw_pii(client, monkeypatch):
    """T01: lo que efectivamente llega al servicio chatbot son marcadores."""
    import chatbot.main

    captured = {}
    original = chatbot.main.complete

    def spy(message, history):
        captured["message"], captured["history"] = message, history
        return original(message, history)

    monkeypatch.setattr(chatbot.main, "complete", spy)
    client.post("/secure/chat", json={"user_id": "u1", "message": PII_MESSAGE})
    sent = json.dumps(captured, ensure_ascii=False)
    for value in PII_VALUES:
        assert value not in sent
    assert "[NOMBRE_1]" in captured["message"]


def test_secure_logs_never_contain_raw_pii(client):
    """T02: el log solo tiene la versión con marcadores."""
    client.post("/secure/chat", json={"user_id": "u1", "message": PII_MESSAGE})
    with open(_secure_log_path(), encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    assert len(lines) == 1
    text = json.dumps(lines[0], ensure_ascii=False)
    for value in PII_VALUES:
        assert value not in text
    assert "[NOMBRE_1]" in lines[0]["anonymized_message"]


def test_reflection_uses_tokens_not_real_pii(client):
    """T03: lo que el chatbot repite y lo que queda en el log son marcadores."""
    resp = client.post("/secure/chat", json={"user_id": "u2", "message": PII_MESSAGE}).json()
    assert "[NOMBRE_1]" in resp["audit"]["llm_output"]
    assert "Juan Carlos Pérez Gómez" not in resp["audit"]["llm_output"]
    assert "Juan Carlos Pérez Gómez" not in resp["audit"]["logged_response"]
    assert "Juan Carlos Pérez Gómez" in resp["response"]


def test_vault_store_on_disk_is_encrypted(client):
    from vault.store import get_store

    client.post("/secure/chat", json={"user_id": "u1", "message": PII_MESSAGE})
    raw = get_store().path.read_text(encoding="utf-8")
    for value in PII_VALUES:
        assert value not in raw
    assert "ciphertext" in raw


def test_tokens_are_consistent_across_the_conversation(client):
    first = client.post("/secure/chat", json={"message": "Mi correo es juan.perez@gmail.com"}).json()
    second = client.post("/secure/chat", json={
        "message": "Repito: JUAN.PEREZ@GMAIL.COM y el de mi esposa ana@x.co",
        "session_id": first["session_id"],
    }).json()
    assert "[CORREO_1]" in second["audit"]["llm_input"]
    assert "[CORREO_2]" in second["audit"]["llm_input"]
