"""
Pruebas del flujo Secure (Sprint 2) — versión automatizada de T01, T02 y T03.

Se comparan directamente contra el comportamiento documentado en
test_unsecure_flow.py: donde Unsecure deja pasar el PII, Secure debe
bloquearlo en el log y en lo que efectivamente llega al LLM, pero seguir
devolviendo una respuesta útil (con el dato real) al usuario legítimo.
"""
import json
import os

import pytest
from fastapi.testclient import TestClient

os.environ["LLM_PROVIDER"] = "mock"

from app.main import app, secure_available  # noqa: E402
from app.logging_config import _secure_log_path  # noqa: E402
from app.pii import reid_store  # noqa: E402

client = TestClient(app)

pytestmark = pytest.mark.skipif(
    not secure_available,
    reason="Presidio/spaCy no están instalados en este entorno (usa requirements.txt en Python 3.11/3.12)",
)

PII_MESSAGE = (
    "Mi nombre es Juan Carlos Pérez Gómez, cédula 1.020.304.050, "
    "correo juan.perez@gmail.com, celular 3001234567"
)


@pytest.fixture(autouse=True)
def clean_state():
    for path in [_secure_log_path(), reid_store._store_path()]:
        if path.exists():
            path.unlink()
    yield


def test_secure_chat_returns_useful_response():
    """La respuesta final al usuario legítimo debe seguir siendo útil:
    debe contener el dato real (reidentificado), no el marcador."""
    resp = client.post("/secure/chat", json={"user_id": "u1", "message": PII_MESSAGE})
    assert resp.status_code == 200
    body = resp.json()
    assert "Juan Carlos Pérez Gómez" in body["response"]
    assert "1.020.304.050" in body["response"]
    assert "juan.perez@gmail.com" in body["response"]
    assert set(body["entities_detected"]) == {
        "PERSON",
        "CEDULA_CO",
        "EMAIL_ADDRESS",
        "TELEFONO_CO",
    }


def test_secure_llm_never_receives_raw_pii(monkeypatch):
    """T01 (versión Secure): lo que efectivamente llega al 'LLM' no debe
    contener ningún dato personal, solo marcadores."""
    captured = {}

    from app.llm_client import llm_client

    original_complete = llm_client.complete

    def spy_complete(message: str) -> str:
        captured["message_sent_to_llm"] = message
        return original_complete(message)

    monkeypatch.setattr(llm_client, "complete", spy_complete)

    client.post("/secure/chat", json={"user_id": "u1", "message": PII_MESSAGE})

    sent = captured["message_sent_to_llm"]
    assert "Juan Carlos Pérez Gómez" not in sent
    assert "1.020.304.050" not in sent
    assert "juan.perez@gmail.com" not in sent
    assert "3001234567" not in sent
    assert "[NOMBRE_1]" in sent


def test_secure_logs_never_contain_raw_pii():
    """T02 (versión Secure): el log solo debe contener la versión
    anonimizada, nunca el dato real."""
    client.post("/secure/chat", json={"user_id": "u1", "message": PII_MESSAGE})

    log_path = _secure_log_path()
    assert log_path.exists()

    with open(log_path, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    assert len(lines) == 1
    record = lines[0]
    assert record["scenario"] == "secure"
    full_record_text = json.dumps(record, ensure_ascii=False)
    assert "Juan Carlos Pérez Gómez" not in full_record_text
    assert "1.020.304.050" not in full_record_text
    assert "juan.perez@gmail.com" not in full_record_text
    assert "3001234567" not in full_record_text
    assert "[NOMBRE_1]" in record["anonymized_message"]


def test_secure_reflection_leak_uses_tokens_not_real_pii():
    """T03: si se le pide al asistente que repita el mensaje, el 'reflejo'
    (lo que efectivamente pasó por el LLM y quedó en el log) debe usar los
    marcadores, no el dato real — la fuga por reflejo queda contenida."""
    resp = client.post("/secure/chat", json={"user_id": "u2", "message": PII_MESSAGE})
    log_path = _secure_log_path()
    with open(log_path, "r", encoding="utf-8") as f:
        record = json.loads(f.readline())

    # El mock hace eco del mensaje anonimizado -> el "reflejo" logueado
    # debe tener el marcador, no el dato real.
    assert "[NOMBRE_1]" in record["anonymized_response"]
    assert "Juan Carlos Pérez Gómez" not in record["anonymized_response"]

    # Pero el usuario legítimo sí recibe el dato real reidentificado.
    assert "Juan Carlos Pérez Gómez" in resp.json()["response"]


def test_mapping_is_stored_encrypted_and_separately():
    """El mapping token->PII debe existir en su propio archivo (separado
    del log) y no debe ser legible como JSON plano (está cifrado)."""
    client.post("/secure/chat", json={"user_id": "u1", "message": PII_MESSAGE})

    mapping_path = reid_store._store_path()
    assert mapping_path.exists()

    raw_content = mapping_path.read_text(encoding="utf-8")
    assert "Juan Carlos Pérez Gómez" not in raw_content
    assert "1.020.304.050" not in raw_content

    record = json.loads(raw_content.splitlines()[0])
    assert "ciphertext" in record

    mapping = reid_store.load_mapping(record["request_id"])
    assert any("Juan Carlos Pérez Gómez" in v for v in mapping.values())
