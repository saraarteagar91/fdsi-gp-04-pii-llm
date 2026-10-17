import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app import clients, db, security, sessions

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Hash de relleno: si el correo no existe se verifica contra él igual, para
# que el tiempo de respuesta no revele qué correos están registrados.
_DUMMY_HASH = security.hash_password("contraseña-de-relleno-0")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LoginIn(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


class RegisterIn(BaseModel):
    nombre: str = Field(min_length=3, max_length=120)
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)
    telefono: str | None = Field(default=None, max_length=30)
    direccion: str | None = Field(default=None, max_length=200)
    ciudad: str | None = Field(default=None, max_length=80)


@router.post("/login")
def login(body: LoginIn, response: Response) -> dict:
    email = body.email.strip().lower()
    security.check_rate_limit(email)
    row = db.one("SELECT id, password_hash FROM usuarios WHERE email = ?", (email,))
    ok = security.verify_password(body.password, row["password_hash"] if row else _DUMMY_HASH)
    if not row or not ok:
        security.register_failure(email)
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")
    security.clear_failures(email)
    security.start_session(response, row["id"])
    return {"ok": True}


@router.post("/register", status_code=201)
def register(body: RegisterIn, response: Response) -> dict:
    email = body.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="El correo no es válido.")
    security.validate_new_password(body.password)
    try:
        user_id = db.execute(
            "INSERT INTO usuarios (email, password_hash, nombre, telefono, direccion, ciudad) VALUES (?,?,?,?,?,?)",
            (email, security.hash_password(body.password), body.nombre.strip(), body.telefono, body.direccion, body.ciudad),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo.")
    security.start_session(response, user_id)
    return {"ok": True}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    user = security.current_user(request)
    if user:
        # la bóveda olvida de inmediato los datos de sus conversaciones seguras
        for session_id in sessions.close_user_sessions("secure", user["id"]):
            clients.delete("vault", f"/session/{session_id}")
    security.end_session(request, response)
    return {"ok": True}


@router.get("/me")
def me(request: Request) -> dict:
    user = security.current_user(request)
    return {"usuario": user}


class ProfileIn(BaseModel):
    nombre: str = Field(min_length=3, max_length=120)
    telefono: str | None = Field(default=None, max_length=30)
    direccion: str | None = Field(default=None, max_length=200)
    ciudad: str | None = Field(default=None, max_length=80)


@router.put("/me")
def update_me(body: ProfileIn, user: dict = Depends(security.require_user)) -> dict:
    db.execute(
        "UPDATE usuarios SET nombre = ?, telefono = ?, direccion = ?, ciudad = ? WHERE id = ?",
        (body.nombre.strip(), body.telefono, body.direccion, body.ciudad, user["id"]),
    )
    return {"ok": True}


class PasswordIn(BaseModel):
    actual: str = Field(max_length=200)
    nueva: str = Field(max_length=200)


@router.put("/password")
def change_password(body: PasswordIn, request: Request, response: Response, user: dict = Depends(security.require_user)) -> dict:
    row = db.one("SELECT password_hash FROM usuarios WHERE id = ?", (user["id"],))
    if not security.verify_password(body.actual, row["password_hash"]):
        raise HTTPException(status_code=401, detail="La contraseña actual no es correcta.")
    security.validate_new_password(body.nueva)
    db.execute("UPDATE usuarios SET password_hash = ? WHERE id = ?", (security.hash_password(body.nueva), user["id"]))
    # cerrar las demás sesiones abiertas y abrir una nueva
    db.execute("DELETE FROM sesiones WHERE usuario_id = ?", (user["id"],))
    security.start_session(response, user["id"])
    return {"ok": True}
