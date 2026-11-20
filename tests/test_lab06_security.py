"""
Pruebas de regresión de los hallazgos del Lab. 06 (docs/REPORTE_HALLAZGOS_LAB06.md).
"""
import json
import os
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

# Contraseña de admin que estuvo publicada en el repositorio (commit 14be53a).
# Se deja aquí solo para comprobar que ya no sirve.
PUBLISHED_ADMIN_PASSWORD = "Seguridad#2026"  # nosec B105  # gitleaks:allow


def _register(app_client: TestClient) -> TestClient:
    email = f"lab06-{uuid.uuid4().hex[:8]}@test.co"
    r = app_client.post("/api/auth/register", json={"nombre": "Prueba Lab Seis", "email": email, "password": "Prueba#2026"})
    assert r.status_code == 201
    return app_client


def test_f07_seed_has_no_admin_password():
    users = json.loads(Path("data/seed/usuarios_demo.json").read_text(encoding="utf-8"))["usuarios"]
    admins = [u for u in users if u["rol"] == "admin"]
    assert admins and all("password" not in u for u in admins)


def test_f07_published_admin_password_no_longer_works(services):
    from app.main import app

    r = TestClient(app).post("/api/auth/login", json={"email": "admin@andesmarket.co", "password": PUBLISHED_ADMIN_PASSWORD})
    assert r.status_code == 401


def test_f07_admin_password_comes_from_secrets(services):
    from app.main import app

    secret = os.environ["APP_ADMIN_PASSWORD"]
    assert len(secret) >= 20 and secret != PUBLISHED_ADMIN_PASSWORD
    r = TestClient(app).post("/api/auth/login", json={"email": "admin@andesmarket.co", "password": secret})
    assert r.status_code == 200


def test_f07_existing_database_rotates_old_admin_hash(admin):
    from app import db
    from app.security import hash_password, verify_password

    db.execute("UPDATE usuarios SET password_hash = ? WHERE rol = 'admin'", (hash_password(PUBLISHED_ADMIN_PASSWORD),))
    db._sync_admin_password(db.conn())
    row = db.one("SELECT password_hash FROM usuarios WHERE rol = 'admin'")
    assert not verify_password(PUBLISHED_ADMIN_PASSWORD, row["password_hash"])
    assert verify_password(os.environ["APP_ADMIN_PASSWORD"], row["password_hash"])
    # la rotación cierra las sesiones del admin: se vuelve a iniciar para las demás pruebas
    admin.post("/api/auth/login", json={"email": "admin@andesmarket.co", "password": os.environ["APP_ADMIN_PASSWORD"]}).raise_for_status()


def test_f08_audit_panel_does_not_trust_text_that_looks_like_html():
    js = Path("static/app.js").read_text(encoding="utf-8")
    assert 'startsWith("<div")' not in js
    assert "trusted(" in js


def test_f09_change_password_is_rate_limited(services):
    from app.main import app

    client = _register(TestClient(app))
    codes = [client.put("/api/auth/password", json={"actual": f"mala{i}xx1", "nueva": "Nueva#12345"}).status_code
             for i in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_f10_order_codes_use_secrets_module():
    src = Path("app/services/orders.py").read_text(encoding="utf-8")
    assert "secrets.randbelow" in src and "random.randint" not in src


def test_f11_internal_services_reject_huge_bodies(services):
    big = "a" * 20001
    assert services["guardian"].post("/protect", json={"text": big}).status_code == 422
    assert services["chatbot"].post("/chat", json={"message": big}).status_code == 422
    assert services["vault"].post("/reidentify", json={"session_id": "x", "text": big}).status_code == 422


def test_zap_90004_cross_origin_isolation_headers(anon):
    h = anon.get("/").headers
    assert h["cross-origin-resource-policy"] == "same-origin"
    assert h["cross-origin-embedder-policy"] == "require-corp"
