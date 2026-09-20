"""
Almacenamiento cifrado y separado del mapeo token -> PII real.

Sección 5 de la propuesta: "el mapeo entre los marcadores y los datos
reales ... se guarda cifrado y por separado, gestionado por un módulo de
reidentificación controlada."

Implementación simple para el alcance del seminario: cada entrada se
cifra individualmente con Fernet (AES128 + HMAC, de la librería
`cryptography`) y se guarda en un archivo JSONL separado del log de
conversación (logs/secure_anon.jsonl). La llave de cifrado NUNCA debe
compartirse con el módulo de logging ni con el cliente del LLM.
"""
import json
import time
import uuid
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet

from app.config import settings

MAPPING_STORE_FILENAME = "secure_mapping.enc.jsonl"
KEY_FILENAME = ".reid_key"  # NO debe subirse al repo (agregar a .gitignore)


def _data_dir() -> Path:
    path = Path("data")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get_or_create_key() -> bytes:
    key_path = _data_dir() / KEY_FILENAME
    if key_path.exists():
        return key_path.read_bytes()
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    return key


def _fernet() -> Fernet:
    return Fernet(_get_or_create_key())


def _store_path() -> Path:
    return _data_dir() / MAPPING_STORE_FILENAME


def store_mapping(mapping: dict[str, str]) -> str:
    """Cifra y guarda el mapping. Devuelve un request_id para recuperarlo
    después (el módulo de reidentificación controlada es el único que
    debería llamar a `load_mapping` con ese id)."""
    request_id = str(uuid.uuid4())
    payload = json.dumps({"mapping": mapping}).encode("utf-8")
    token = _fernet().encrypt(payload)

    record = {
        "request_id": request_id,
        "timestamp": time.time(),
        "ciphertext": token.decode("utf-8"),
    }
    with open(_store_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    return request_id


def load_mapping(request_id: str) -> Optional[dict[str, str]]:
    """Recupera y descifra el mapping asociado a un request_id. Devuelve
    None si no existe."""
    path = _store_path()
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            if record["request_id"] == request_id:
                payload = _fernet().decrypt(record["ciphertext"].encode("utf-8"))
                return json.loads(payload)["mapping"]
    return None
