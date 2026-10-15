"""
Configuración común de las pruebas: secretos y base de datos nuevos en
una carpeta temporal (no se tocan los de la demo), chatbot "mock" por
defecto y los cuatro servicios conectados en memoria.

Clientes HTTP disponibles:
  admin    -> equipo de seguridad (puede usar el modo inseguro)
  customer -> Juan Carlos Pérez (cliente con pedidos)
  anon     -> sin sesión
"""
import pytest

from common.wiring import configure_env

ROOT = configure_env()

ADMIN_EMAIL = "admin@andesmarket.co"
CUSTOMER_EMAIL = "juan.perez@gmail.com"


@pytest.fixture(scope="session")
def services():
    from common.wiring import wire_in_process

    return wire_in_process()


@pytest.fixture(scope="session")
def admin(services):
    from common.wiring import logged_client

    return logged_client(ADMIN_EMAIL)


@pytest.fixture(scope="session")
def customer(services):
    from common.wiring import logged_client

    return logged_client(CUSTOMER_EMAIL)


@pytest.fixture
def anon(services):
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def client(admin):
    """Por defecto las pruebas de flujo usan el administrador."""
    return admin


@pytest.fixture
def local_llm(monkeypatch):
    """Usa el asistente Andi entrenado en vez del mock."""
    from chatbot.config import settings

    monkeypatch.setattr(settings, "llm_provider", "local")
