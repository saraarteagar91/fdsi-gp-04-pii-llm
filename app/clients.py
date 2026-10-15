"""
Clientes HTTP de la tienda hacia los tres servicios externos.

Cada llamada lleva el token de ese servicio. En las pruebas, `override()`
reemplaza el cliente real por un TestClient del servicio, sin red.
"""
import httpx
from fastapi import HTTPException

from app.config import settings

_overrides: dict[str, httpx.Client] = {}
_clients: dict[str, httpx.Client] = {}


def _config(service: str) -> tuple[str, str]:
    return {
        "guardian": (settings.guardian_url, settings.guardian_token),
        "vault": (settings.vault_url, settings.vault_token),
        "chatbot": (settings.chatbot_url, settings.chatbot_token),
    }[service]


def override(service: str, client: httpx.Client | None) -> None:
    if client is None:
        _overrides.pop(service, None)
    else:
        _overrides[service] = client


def _client(service: str) -> httpx.Client:
    if service in _overrides:
        return _overrides[service]
    if service not in _clients:
        url, token = _config(service)
        _clients[service] = httpx.Client(base_url=url, timeout=settings.service_timeout_s,
                                         headers={"Authorization": f"Bearer {token}"})
    return _clients[service]


def call(service: str, path: str, payload: dict) -> dict:
    try:
        resp = _client(service).post(path, json=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"El servicio '{service}' no responde: {exc.__class__.__name__}")
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"El servicio '{service}' respondió {resp.status_code}")
    return resp.json()


def health(service: str) -> dict:
    try:
        resp = _client(service).get("/health")
        return resp.json() if resp.status_code == 200 else {"error": resp.status_code}
    except httpx.HTTPError as exc:
        return {"error": exc.__class__.__name__}


def get(service: str, path: str) -> dict:
    try:
        resp = _client(service).get(path)
        return resp.json() if resp.status_code == 200 else {}
    except httpx.HTTPError:
        return {}
