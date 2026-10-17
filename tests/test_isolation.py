"""
Pruebas de AISLAMIENTO entre servicios — el requisito del profesor:
"el modelo que cifra tampoco puede tener acceso a la información".

Se verifica que:
1. El guardián solo tiene la llave pública: no puede descifrar.
2. El guardián no escribe nada en disco mientras procesa.
3. Solo la bóveda (llave privada) puede abrir lo que cifró el guardián.
4. Ningún servicio atiende sin su token.
5. La bóveda solo revela marcadores de la conversación indicada y solo
   para propósitos autorizados. Es efímera: no escribe en disco y las
   conversaciones vencen por inactividad.
6. La tienda no tiene ninguna llave.
7. docker-compose aísla las redes: el guardián no tiene salida a
   internet ni disco escribible, y el chatbot no alcanza a la bóveda.
"""
import base64
import builtins
import importlib
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from nacl.exceptions import TypeError as NaclTypeError
from nacl.public import PublicKey, SealedBox


def test_guardian_cannot_decrypt_what_it_encrypts(services):
    from guardian import crypto
    from guardian.config import settings

    assert services["guardian"].get("/health").json()["puede_descifrar"] is False
    assert not any("private" in name for name in settings.model_dump())
    entity = services["guardian"].post("/protect", json={"text": "mi correo es ana@x.co"}).json()["entities"][0]
    box = SealedBox(PublicKey(base64.b64decode(Path(settings.public_key_path).read_text())))
    with pytest.raises((NaclTypeError, TypeError)):
        box.decrypt(base64.b64decode(entity["ciphertext"]))
    assert crypto.can_decrypt() is False


def test_only_the_vault_can_open_guardian_ciphertext(services):
    from vault.store import _box

    entity = services["guardian"].post("/protect", json={"text": "mi correo es ana@x.co"}).json()["entities"][0]
    assert _box().decrypt(base64.b64decode(entity["ciphertext"])).decode() == "ana@x.co"


def test_guardian_writes_nothing_to_disk(services, monkeypatch):
    real_open = builtins.open

    def guarded_open(file, mode="r", *args, **kwargs):
        if any(m in mode for m in ("w", "a", "x", "+")):
            raise AssertionError(f"El guardián intentó escribir en {file}")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    resp = services["guardian"].post("/protect", json={"text": "Soy Laura Gómez, cédula 52.345.678, cel 3104567890"})
    assert resp.status_code == 200 and len(resp.json()["entities"]) == 3


@pytest.mark.parametrize("module, path, payload", [
    ("guardian.main", "/protect", {"text": "hola"}),
    ("vault.main", "/reidentify", {"session_id": "x", "text": "[CORREO_1]"}),
    ("chatbot.main", "/chat", {"message": "hola"}),
])
def test_services_reject_requests_without_token(module, path, payload):
    import importlib

    app = importlib.import_module(module).app
    assert TestClient(app).post(path, json=payload).status_code == 401
    assert TestClient(app, headers={"Authorization": "Bearer otro"}).post(path, json=payload).status_code == 401


def test_vault_only_reveals_tokens_of_the_same_conversation(client, services):
    a = client.post("/secure/chat", json={"message": "Mi correo es juan.perez@gmail.com"}).json()
    other = services["vault"].post("/reidentify", json={"session_id": "otra-sesion", "text": "Tu correo es [CORREO_1]"}).json()
    own = services["vault"].post("/reidentify", json={"session_id": a["session_id"], "text": "Tu correo es [CORREO_1]"}).json()
    assert other["text"] == "Tu correo es [CORREO_1]"
    assert own["text"] == "Tu correo es juan.perez@gmail.com"


def test_vault_resolve_requires_authorized_purpose(client, services):
    a = client.post("/secure/chat", json={"message": "Mi correo es juan.perez@gmail.com"}).json()
    body = {"session_id": a["session_id"], "token": "[CORREO_1]"}
    assert services["vault"].post("/resolve", json={**body, "purpose": "marketing"}).status_code == 403
    assert services["vault"].post("/resolve", json={**body, "purpose": "consultar_pedido"}).json()["value"] == "juan.perez@gmail.com"


def _forbid_disk_writes(monkeypatch, who: str) -> None:
    real_open = builtins.open

    def guarded_open(file, mode="r", *args, **kwargs):
        if any(m in mode for m in ("w", "a", "x", "+")):
            raise AssertionError(f"{who} intentó escribir en {file}")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(Path, "write_text", lambda *a, **k: (_ for _ in ()).throw(AssertionError(f"{who} escribió en disco")))
    monkeypatch.setattr(Path, "write_bytes", lambda *a, **k: (_ for _ in ()).throw(AssertionError(f"{who} escribió en disco")))


def test_vault_writes_nothing_to_disk(services, monkeypatch):
    entities = services["guardian"].post("/protect", json={"text": "Soy Laura Gómez, correo laura@x.co"}).json()["entities"]
    _forbid_disk_writes(monkeypatch, "La bóveda")
    vault = services["vault"]
    payload = [{k: e[k] for k in ("label", "ciphertext", "blind_index")} for e in entities]
    tokens = vault.post("/tokens", json={"session_id": "s-disco", "entities": payload}).json()["tokens"]
    assert tokens == ["[NOMBRE_1]", "[CORREO_1]"]
    assert vault.post("/reidentify", json={"session_id": "s-disco", "text": "Hola [NOMBRE_1]"}).json()["text"] == "Hola Laura Gómez"
    body = {"session_id": "s-disco", "token": "[CORREO_1]", "purpose": "consultar_pedido"}
    assert vault.post("/resolve", json=body).json()["value"] == "laura@x.co"


def _store_tokens(services, session_id: str, text: str) -> list[str]:
    entities = services["guardian"].post("/protect", json={"text": text}).json()["entities"]
    payload = [{k: e[k] for k in ("label", "ciphertext", "blind_index")} for e in entities]
    return services["vault"].post("/tokens", json={"session_id": session_id, "entities": payload}).json()["tokens"]


def test_vault_expired_conversation_cannot_be_reidentified_or_resolved(services, monkeypatch):
    import vault.store
    from vault.config import settings

    clock = [vault.store._now()]
    monkeypatch.setattr(vault.store, "_now", lambda: clock[0])
    assert _store_tokens(services, "s-vence", "mi correo es ana@x.co") == ["[CORREO_1]"]
    vault_client = services["vault"]
    reid = {"session_id": "s-vence", "text": "Tu correo es [CORREO_1]"}
    resolve = {"session_id": "s-vence", "token": "[CORREO_1]", "purpose": "consultar_pedido"}

    clock[0] += settings.session_ttl_seconds - 1  # la actividad renueva el plazo
    assert vault_client.post("/reidentify", json=reid).json()["text"] == "Tu correo es ana@x.co"

    clock[0] += settings.session_ttl_seconds
    assert vault_client.post("/reidentify", json=reid).json()["text"] == "Tu correo es [CORREO_1]"
    assert vault_client.post("/resolve", json=resolve).status_code == 404
    assert vault.store.get_store().decrypt("s-vence", "[CORREO_1]") is None


def test_vault_same_value_gets_same_token_within_a_conversation(services):
    first = _store_tokens(services, "s-mismo", "correo juan.perez@gmail.com, cel 300 123 4567")
    again = _store_tokens(services, "s-mismo", "repito JUAN.PEREZ@GMAIL.COM y 3001234567, y otro: ana@x.co")
    assert first == ["[CORREO_1]", "[TELEFONO_1]"]
    assert again == ["[CORREO_1]", "[TELEFONO_1]", "[CORREO_2]"]
    assert _store_tokens(services, "s-otra", "mi cel es 3001234567") == ["[TELEFONO_1]"]


def test_vault_forgets_a_closed_conversation(services):
    _store_tokens(services, "s-cerrar", "mi correo es ana@x.co")
    assert services["vault"].delete("/session/s-cerrar").json() == {"borrada": True}
    assert services["vault"].post("/reidentify", json={"session_id": "s-cerrar", "text": "[CORREO_1]"}).json()["text"] == "[CORREO_1]"
    assert TestClient(importlib.import_module("vault.main").app).delete("/session/s-cerrar").status_code == 401


def test_vault_caps_simultaneous_conversations(services, monkeypatch):
    from vault.config import settings
    from vault.store import get_store

    monkeypatch.setattr(settings, "max_sessions", 3)
    for i in range(5):
        _store_tokens(services, f"s-tope-{i}", "mi correo es ana@x.co")
    assert get_store().active_sessions() <= 3
    assert get_store().tokens_of("s-tope-0") == []
    assert get_store().tokens_of("s-tope-4") == ["[CORREO_1]"]


def test_logout_makes_the_vault_forget_the_user_conversations(services):
    from common.wiring import logged_client
    from vault.store import get_store

    user = logged_client("sara.arteaga@correo.edu.co")
    sid = user.post("/secure/chat", json={"message": "Mi correo es sara.arteaga@correo.edu.co"}).json()["session_id"]
    assert get_store().tokens_of(sid) == ["[CORREO_1]"]
    user.post("/api/auth/logout")
    assert get_store().tokens_of(sid) == []


def test_shop_has_no_keys():
    from app.config import settings

    assert not any("key" in name for name in settings.model_dump())


def test_docker_compose_isolates_the_services():
    compose = yaml.safe_load(Path("docker-compose.yml").read_text(encoding="utf-8"))
    svc, nets = compose["services"], compose["networks"]

    guardian = svc["guardian"]
    assert guardian["read_only"] is True
    assert set(guardian["networks"]) == {"red_guardian"} and nets["red_guardian"]["internal"] is True
    assert not any("vault" in str(v) for v in guardian.get("volumes", []))
    assert "ports" not in guardian

    vault = svc["vault"]
    assert set(vault["networks"]) == {"red_boveda"} and nets["red_boveda"]["internal"] is True
    assert "ports" not in vault

    chatbot = svc["chatbot"]
    assert "red_boveda" not in chatbot["networks"] and "red_guardian" not in chatbot["networks"]
    assert not any("secrets/vault" in str(v) or "secrets/guardian" in str(v) for v in chatbot.get("volumes", []))

    shop = svc["tienda"]
    assert not any("secrets/vault" in str(v) or "secrets/guardian" in str(v) for v in shop.get("volumes", []))
