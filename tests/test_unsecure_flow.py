"""
Pruebas del flujo Unsecure (Sprint 1).

Estas pruebas documentan, de forma automatizada, el comportamiento
INSEGURO descrito en la sección 4 de la propuesta: sirven como línea base
para T01 (envío de PII sin filtro) y T02 (persistencia de PII en logs).
Cuando exista /secure/chat (Sprint 2), se agregarán las pruebas
equivalentes que deben mostrar el comportamiento contrario.
"""
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["LLM_PROVIDER"] = "mock"

from app.main import app  # noqa: E402
from app.logging_config import _log_path  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_log_file():
    """Aísla cada prueba borrando el log antes de correr."""
    path = _log_path()
    if path.exists():
        path.unlink()
    yield
    if path.exists():
        path.unlink()


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_unsecure_chat_returns_response():
    resp = client.post(
        "/unsecure/chat",
        json={"user_id": "u1", "message": "Hola, ¿cómo estás?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "response" in body
    assert "log_id" in body
    assert body["latency_ms"] >= 0


def test_unsecure_forwards_pii_without_filtering():
    """T01: el mensaje con PII debe llegar intacto a la 'respuesta' del LLM
    mock (que hace eco del mensaje), demostrando que no hay ningún filtro."""
    pii_message = "Mi nombre es Juan Pérez, cédula 1020304050, correo juan@test.com"
    resp = client.post(
        "/unsecure/chat",
        json={"user_id": "u2", "message": pii_message},
    )
    assert resp.status_code == 200
    llm_response = resp.json()["response"]
    # El PII debe seguir presente: no hay ninguna transformación (Unsecure).
    assert "Juan Pérez" in llm_response
    assert "1020304050" in llm_response
    assert "juan@test.com" in llm_response


def test_unsecure_logs_store_raw_pii():
    """T02: los logs deben contener el PII en texto plano (comportamiento
    inseguro esperado en este escenario, que se corrige en Sprint 2)."""
    pii_message = "Soy María López, tel 3001234567, correo maria@test.com"
    client.post("/unsecure/chat", json={"user_id": "u3", "message": pii_message})

    log_path = _log_path()
    assert log_path.exists()

    with open(log_path, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    assert len(lines) == 1
    record = lines[0]
    assert record["scenario"] == "unsecure"
    assert "María López" in record["user_message"]
    assert "3001234567" in record["user_message"]
    assert "maria@test.com" in record["user_message"]
