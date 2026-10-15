"""
Autenticación de usuarios de la tienda.

- Contraseñas: hash scrypt (N=2^14, r=8, p=1) con sal aleatoria de 16 bytes.
  Nunca se guarda ni se registra la contraseña.
- Sesiones: token aleatorio de 32 bytes en una cookie HttpOnly +
  SameSite=Lax (JavaScript no puede leerla y no viaja en peticiones de
  otros sitios). En la base solo se guarda su hash SHA-256, así que una
  copia de la base no sirve para suplantar a nadie. Expiran a las 8 horas.
- Fuerza bruta: 5 intentos fallidos por correo en 15 minutos bloquean
  temporalmente ese correo (HTTP 429).
"""
import hashlib
import hmac
import secrets
import threading
import time

from fastapi import HTTPException, Request, Response

from app import db
from app.config import settings

COOKIE_NAME = "am_session"
SESSION_SECONDS = 8 * 3600
MAX_FAILED = 5
FAILED_WINDOW = 15 * 60

_failed: dict[str, list[float]] = {}
_failed_lock = threading.Lock()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=32)
    return hmac.compare_digest(digest.hex(), digest_hex)


def validate_new_password(password: str) -> None:
    if len(password) < 8 or not any(c.isdigit() for c in password) or not any(c.isalpha() for c in password):
        raise HTTPException(status_code=422, detail="La contraseña debe tener al menos 8 caracteres, con letras y números.")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def check_rate_limit(email: str) -> None:
    now = time.time()
    with _failed_lock:
        attempts = [t for t in _failed.get(email.lower(), []) if now - t < FAILED_WINDOW]
        _failed[email.lower()] = attempts
        if len(attempts) >= MAX_FAILED:
            raise HTTPException(status_code=429, detail="Demasiados intentos fallidos. Intenta de nuevo en 15 minutos.")


def register_failure(email: str) -> None:
    with _failed_lock:
        _failed.setdefault(email.lower(), []).append(time.time())


def clear_failures(email: str) -> None:
    with _failed_lock:
        _failed.pop(email.lower(), None)


def start_session(response: Response, user_id: int) -> None:
    token = secrets.token_urlsafe(32)
    db.execute("DELETE FROM sesiones WHERE expira < ?", (time.time(),))
    db.execute("INSERT INTO sesiones VALUES (?,?,?)", (_token_hash(token), user_id, time.time() + SESSION_SECONDS))
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True, samesite="lax",
                        secure=settings.cookie_secure, path="/")


def end_session(request: Request, response: Response) -> None:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        db.execute("DELETE FROM sesiones WHERE token_hash = ?", (_token_hash(token),))
    response.delete_cookie(COOKIE_NAME, path="/")


PUBLIC_USER_FIELDS = "u.id, u.email, u.nombre, u.cedula, u.telefono, u.direccion, u.ciudad, u.rol"


def current_user(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return db.one(
        f"SELECT {PUBLIC_USER_FIELDS} FROM sesiones s JOIN usuarios u ON u.id = s.usuario_id "
        "WHERE s.token_hash = ? AND s.expira > ?",
        (_token_hash(token), time.time()),
    )


def require_user(request: Request) -> dict:
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar.")
    return user


def require_admin(request: Request) -> dict:
    user = require_user(request)
    if user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Solo el equipo de seguridad puede ver esta sección.")
    return user
