"""
Conversaciones del chat, ligadas al usuario que inició sesión.

- El id de conversación SIEMPRE lo genera el servidor (uuid4 aleatorio).
  Si el cliente manda un id que no existe o que pertenece a otro usuario,
  se ignora y se abre una conversación nueva: nadie puede "adivinar" o
  reutilizar la conversación de otra persona para que la bóveda le
  reidentifique sus datos.
- El historial guarda exactamente lo que el chatbot ya vio: texto crudo
  en Unsecure y solo marcadores en Secure.
"""
import threading
import uuid
from dataclasses import dataclass, field

MAX_HISTORY_MESSAGES = 20


@dataclass
class Session:
    id: str
    scenario: str
    user_id: int
    history: list[dict] = field(default_factory=list)

    def add_turn(self, user_text: str, assistant_text: str) -> None:
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": assistant_text})
        del self.history[:-MAX_HISTORY_MESSAGES]


_sessions: dict[tuple[str, str], Session] = {}
_lock = threading.Lock()


def get_or_create(scenario: str, session_id: str | None, user_id: int) -> Session:
    with _lock:
        existing = _sessions.get((scenario, session_id or ""))
        if existing is not None and existing.user_id == user_id:
            return existing
        session = Session(id=str(uuid.uuid4()), scenario=scenario, user_id=user_id)
        _sessions[(scenario, session.id)] = session
        return session


def close_user_sessions(scenario: str, user_id: int) -> list[str]:
    """Cierra las conversaciones de un usuario y devuelve sus ids."""
    with _lock:
        keys = [k for k, s in _sessions.items() if s.scenario == scenario and s.user_id == user_id]
        for k in keys:
            del _sessions[k]
        return [sid for _, sid in keys]


def reset() -> None:
    with _lock:
        _sessions.clear()
