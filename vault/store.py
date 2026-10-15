"""
Registro de marcadores de la bóveda.

Por cada conversación guarda: marcador ([CORREO_1]) -> tipo, índice ciego y
el dato CIFRADO tal como llegó del guardián. Los datos quedan cifrados
también en disco (vault_tokens.jsonl); solo se descifran en memoria, en el
momento de reidentificar o de una consulta interna autorizada.
"""
import base64
import json
import threading
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from nacl.public import PrivateKey, SealedBox

from vault.config import settings

STORE_FILENAME = "vault_tokens.jsonl"
ACCESS_LOG_FILENAME = "vault_access.jsonl"


@dataclass
class SessionTokens:
    tokens: dict[str, dict] = field(default_factory=dict)       # marcador -> registro
    by_index: dict[str, str] = field(default_factory=dict)      # índice ciego -> marcador
    counters: dict[str, int] = field(default_factory=dict)      # etiqueta -> último número


class TokenStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, SessionTokens] = {}
        self._dir = Path(settings.store_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._load()

    @property
    def path(self) -> Path:
        return self._dir / STORE_FILENAME

    def _load(self) -> None:
        if not self.path.exists():
            return
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    self._index(json.loads(line))

    def _index(self, rec: dict) -> None:
        s = self._sessions.setdefault(rec["session_id"], SessionTokens())
        s.tokens[rec["token"]] = rec
        s.by_index[rec["blind_index"]] = rec["token"]
        n = int(rec["token"].rsplit("_", 1)[1].rstrip("]"))
        s.counters[rec["label"]] = max(s.counters.get(rec["label"], 0), n)

    def assign(self, session_id: str, label: str, ciphertext: str, blind_index: str) -> str:
        """Devuelve el marcador del dato: el mismo si ya apareció en la
        conversación (mismo índice ciego), uno nuevo si no."""
        with self._lock:
            s = self._sessions.setdefault(session_id, SessionTokens())
            if blind_index in s.by_index:
                return s.by_index[blind_index]
            n = s.counters.get(label, 0) + 1
            rec = {
                "session_id": session_id,
                "token": f"[{label}_{n}]",
                "label": label,
                "blind_index": blind_index,
                "ciphertext": ciphertext,
                "timestamp": time.time(),
            }
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            self._index(rec)
            return rec["token"]

    def decrypt(self, session_id: str, token: str) -> str | None:
        rec = self._sessions.get(session_id, SessionTokens()).tokens.get(token)
        if rec is None:
            return None
        return _box().decrypt(base64.b64decode(rec["ciphertext"])).decode("utf-8")

    def tokens_of(self, session_id: str) -> list[str]:
        return list(self._sessions.get(session_id, SessionTokens()).tokens)

    def log_access(self, session_id: str, token: str, purpose: str) -> None:
        """Bitácora de cada descifrado (sin el valor), para auditoría."""
        with open(self._dir / ACCESS_LOG_FILENAME, "a", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": time.time(), "session_id": session_id, "token": token, "proposito": purpose}) + "\n")


@lru_cache(maxsize=1)
def _box() -> SealedBox:
    key = base64.b64decode(Path(settings.private_key_path).read_text().strip())
    return SealedBox(PrivateKey(key))


@lru_cache(maxsize=1)
def get_store() -> TokenStore:
    return TokenStore()
