"""
Registro de marcadores de la bóveda — EFÍMERO, solo en memoria.

Por cada conversación guarda: marcador ([CORREO_1]) -> tipo, índice ciego y
el dato CIFRADO tal como llegó del guardián. No se escribe nada en disco:
un archivo con los datos cifrados sería un blanco de robo y además los
dejaría vivos más allá de la conversación.

- Cada conversación vence tras VAULT_SESSION_TTL_SECONDS sin actividad.
  La limpieza es perezosa: se hace en cada operación.
- Hay un tope de conversaciones simultáneas (VAULT_MAX_SESSIONS); al
  llegar, se descarta la de actividad más antigua.
- Al reiniciar el servicio se pierde todo.

Mientras la conversación está abierta, los cifrados siguen en la memoria
del proceso; solo se descifran en el momento de reidentificar o de una
consulta interna autorizada.
"""
import base64
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from nacl.public import PrivateKey, SealedBox

from vault.config import settings

ACCESS_LOG_MAX = 1000


def _now() -> float:
    return time.monotonic()


@dataclass
class SessionTokens:
    last_used: float
    tokens: dict[str, dict] = field(default_factory=dict)       # marcador -> registro
    by_index: dict[str, str] = field(default_factory=dict)      # índice ciego -> marcador
    counters: dict[str, int] = field(default_factory=dict)      # etiqueta -> último número


class TokenStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Ordenado por actividad: la primera es la menos reciente.
        self._sessions: OrderedDict[str, SessionTokens] = OrderedDict()
        # Bitácora de descifrados: solo marcador y propósito, nunca el valor.
        self.access_log: deque[dict] = deque(maxlen=ACCESS_LOG_MAX)

    def _purge_expired(self, now: float) -> None:
        ttl = settings.session_ttl_seconds
        while self._sessions:
            sid, s = next(iter(self._sessions.items()))
            if now - s.last_used < ttl:
                break
            del self._sessions[sid]

    def _get(self, session_id: str, create: bool = False) -> SessionTokens | None:
        """Devuelve la conversación (vigente) y renueva su vencimiento."""
        now = _now()
        self._purge_expired(now)
        s = self._sessions.get(session_id)
        if s is None:
            if not create:
                return None
            while len(self._sessions) >= settings.max_sessions:
                self._sessions.popitem(last=False)
            s = self._sessions[session_id] = SessionTokens(last_used=now)
        s.last_used = now
        self._sessions.move_to_end(session_id)
        return s

    def assign(self, session_id: str, label: str, ciphertext: str, blind_index: str) -> str:
        """Devuelve el marcador del dato: el mismo si ya apareció en la
        conversación (mismo índice ciego), uno nuevo si no."""
        with self._lock:
            s = self._get(session_id, create=True)
            if blind_index in s.by_index:
                return s.by_index[blind_index]
            n = s.counters.get(label, 0) + 1
            s.counters[label] = n
            token = f"[{label}_{n}]"
            s.tokens[token] = {"label": label, "blind_index": blind_index, "ciphertext": ciphertext}
            s.by_index[blind_index] = token
            return token

    def decrypt(self, session_id: str, token: str) -> str | None:
        """None si la conversación venció o el marcador no es de ella."""
        with self._lock:
            s = self._get(session_id)
            rec = s.tokens.get(token) if s else None
        if rec is None:
            return None
        return _box().decrypt(base64.b64decode(rec["ciphertext"])).decode("utf-8")

    def tokens_of(self, session_id: str) -> list[str]:
        with self._lock:
            s = self._get(session_id)
            return list(s.tokens) if s else []

    def forget(self, session_id: str) -> bool:
        """Borra una conversación (al cerrarla). True si existía."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def active_sessions(self) -> int:
        with self._lock:
            self._purge_expired(_now())
            return len(self._sessions)

    def log_access(self, session_id: str, token: str, purpose: str) -> None:
        """Bitácora de cada descifrado, en memoria: solo marcador y
        propósito (ni el valor ni la conversación)."""
        self.access_log.append({"timestamp": time.time(), "token": token, "proposito": purpose})


@lru_cache(maxsize=1)
def _box() -> SealedBox:
    key = base64.b64decode(Path(settings.private_key_path).read_text().strip())
    return SealedBox(PrivateKey(key))


@lru_cache(maxsize=1)
def get_store() -> TokenStore:
    return TokenStore()
