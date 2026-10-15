"""
Pruebas del flujo Unsecure (línea base, sección 4 de la propuesta):
T01 (el PII llega intacto al chatbot) y T02 (el log guarda el PII).
"""
import json

import pytest

from app.logging_config import _log_path


@pytest.fixture(autouse=True)
def clean_log_file():
    path = _log_path()
    if path.exists():
        path.unlink()
    yield


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["servicios"] == {"guardian": True, "vault": True, "chatbot": True}


def test_unsecure_chat_returns_response(client):
    resp = client.post("/unsecure/chat", json={"user_id": "u1", "message": "Hola, ¿cómo estás?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["response"] and body["log_id"] and body["latency_ms"] >= 0


def test_unsecure_forwards_pii_without_filtering(client):
    """T01: el chatbot (mock, que hace eco) recibe el mensaje intacto."""
    pii_message = "Mi nombre es Juan Pérez, cédula 1020304050, correo juan@test.com"
    body = client.post("/unsecure/chat", json={"user_id": "u2", "message": pii_message}).json()
    assert body["audit"]["llm_input"] == pii_message
    for value in ("Juan Pérez", "1020304050", "juan@test.com"):
        assert value in body["response"]


def test_unsecure_logs_store_raw_pii(client):
    """T02: el log queda con el PII en texto plano."""
    client.post("/unsecure/chat", json={"user_id": "u3", "message": "Soy María López, tel 3001234567, correo maria@test.com"})
    with open(_log_path(), encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    assert len(lines) == 1
    assert lines[0]["scenario"] == "unsecure"
    for value in ("María López", "3001234567", "maria@test.com"):
        assert value in lines[0]["user_message"]
