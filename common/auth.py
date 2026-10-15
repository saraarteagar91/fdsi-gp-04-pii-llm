"""
Autenticación entre servicios: cada servicio interno solo atiende
peticiones que traen su token (Authorization: Bearer <token>). Así, aunque
alguien llegue a la red interna, no puede pedirle a la bóveda que
descifre ni usar el guardián o el chatbot sin ser la tienda.
"""
import hmac
from typing import Callable

from fastapi import Header, HTTPException


def require_token(get_expected: Callable[[], str]):
    def dependency(authorization: str = Header(default="")) -> None:
        expected = get_expected()
        given = authorization.removeprefix("Bearer ").strip()
        if not expected or not hmac.compare_digest(given, expected):
            raise HTTPException(status_code=401, detail="Token de servicio inválido")

    return dependency
