"""
Registro estructurado (JSON) del flujo Unsecure.

En el escenario Unsecure, el log se queda con el texto CRUDO (incluye PII)
a propósito: esa es justamente la línea base insegura que se compara contra
el log anonimizado del escenario Secure en el Sprint 2.

IMPORTANTE: esto solo debe correr en un ambiente de pruebas propio y
controlado (nunca contra datos reales de usuarios), tal como se aclara en
la propuesta del Hito 1.
"""
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict

from app.config import settings

RAW_LOG_FILENAME = "unsecure_raw.jsonl"
SECURE_LOG_FILENAME = "secure_anon.jsonl"


def _log_dir() -> Path:
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _log_path() -> Path:
    return _log_dir() / RAW_LOG_FILENAME


def _secure_log_path() -> Path:
    return _log_dir() / SECURE_LOG_FILENAME


def log_unsecure_interaction(
    user_id: str,
    user_message: str,
    llm_response: str,
    latency_ms: float,
    extra: Dict[str, Any] | None = None,
) -> str:
    """Escribe una línea JSON con la interacción completa, sin anonimizar.

    Devuelve el id de la entrada de log, útil para pruebas.
    """
    entry_id = str(uuid.uuid4())
    record = {
        "log_id": entry_id,
        "timestamp": time.time(),
        "scenario": "unsecure",
        "user_id": user_id,
        "user_message": user_message,  # texto crudo, PII incluido a propósito
        "llm_response": llm_response,
        "latency_ms": latency_ms,
    }
    if extra:
        record.update(extra)

    with open(_log_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return entry_id


def read_all_unsecure_logs() -> list[Dict[str, Any]]:
    path = _log_path()
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def log_secure_interaction(
    user_id: str,
    anonymized_message: str,
    anonymized_response: str,
    entities_found: list[str],
    latency_ms: float,
    reid_request_id: str,
    extra: Dict[str, Any] | None = None,
) -> str:
    """Escribe una línea JSON con la interacción del escenario Secure.

    A propósito, esta función NUNCA recibe el texto original con PII: solo
    la versión ya anonimizada, tal como exige la sección 5 de la
    propuesta ("los logs almacenan únicamente la versión anonimizada").
    `reid_request_id` permite auditar qué mapping (guardado aparte y
    cifrado) corresponde a esta interacción, sin que el log mismo
    contenga ningún dato personal.
    """
    entry_id = str(uuid.uuid4())
    record = {
        "log_id": entry_id,
        "timestamp": time.time(),
        "scenario": "secure",
        "user_id": user_id,
        "anonymized_message": anonymized_message,
        "anonymized_response": anonymized_response,
        "entities_found": entities_found,
        "reid_request_id": reid_request_id,
        "latency_ms": latency_ms,
    }
    if extra:
        record.update(extra)

    with open(_secure_log_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return entry_id


def read_all_secure_logs() -> list[Dict[str, Any]]:
    path = _secure_log_path()
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
