"""
Conecta los cuatro servicios EN MEMORIA (sin red) para las pruebas y la
evaluación: cada servicio sigue siendo una aplicación FastAPI separada,
con sus propios secretos y su token, pero la tienda les habla a través de
un TestClient en vez de HTTP real.

Importante: hay que llamar a `configure_env()` ANTES de importar los
módulos de configuración de los servicios.
"""
import os
import tempfile
from pathlib import Path


def configure_env(root: Path | None = None, chatbot_provider: str = "mock") -> Path:
    from scripts.setup_secrets import read_env, setup

    root = Path(root or tempfile.mkdtemp(prefix="fdsi_"))
    secrets_root = root / "secrets"
    setup(secrets_root)
    env = {}
    for name in ("app", "guardian", "vault", "chatbot"):
        env.update(read_env(secrets_root / "env" / f"{name}.env"))
    env.update({
        "GUARDIAN_PUBLIC_KEY_PATH": str(secrets_root / "guardian" / "public.key"),
        "GUARDIAN_PEPPER_PATH": str(secrets_root / "guardian" / "pepper.key"),
        "VAULT_PRIVATE_KEY_PATH": str(secrets_root / "vault" / "private.key"),
        "VAULT_STORE_DIR": str(root / "vault"),
        "APP_LOG_DIR": str(root / "logs"),
        "APP_DB_PATH": str(root / "db" / "andes_market.db"),
        "CHATBOT_LLM_PROVIDER": chatbot_provider,
    })
    os.environ.update(env)
    return root


def wire_in_process() -> dict:
    """Devuelve {"tienda": TestClient, "guardian": ..., "vault": ..., "chatbot": ...}
    con la tienda ya apuntando a los otros tres."""
    from fastapi.testclient import TestClient

    from app import clients
    from app.main import app as shop_app
    from chatbot.main import app as chatbot_app
    from guardian.main import app as guardian_app
    from vault.main import app as vault_app

    services = {}
    for name, svc_app, token_var in (
        ("guardian", guardian_app, "APP_GUARDIAN_TOKEN"),
        ("vault", vault_app, "APP_VAULT_TOKEN"),
        ("chatbot", chatbot_app, "APP_CHATBOT_TOKEN"),
    ):
        client = TestClient(svc_app, headers={"Authorization": f"Bearer {os.environ[token_var]}"})
        clients.override(name, client)
        services[name] = client
    services["tienda"] = TestClient(shop_app)
    return services


def demo_password(email: str) -> str:
    """Contraseña de un usuario de prueba (data/seed/usuarios_demo.json)."""
    import json

    users = json.loads(Path("data/seed/usuarios_demo.json").read_text(encoding="utf-8"))["usuarios"]
    return next(u["password"] for u in users if u["email"] == email)


def logged_client(email: str):
    """Un cliente HTTP de la tienda con la sesión de ese usuario iniciada."""
    from fastapi.testclient import TestClient

    from app.main import app as shop_app

    client = TestClient(shop_app)
    resp = client.post("/api/auth/login", json={"email": email, "password": demo_password(email)})
    resp.raise_for_status()
    return client
