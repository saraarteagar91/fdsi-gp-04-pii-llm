"""
Cifrado del guardián con LLAVE PÚBLICA (X25519 + XSalsa20-Poly1305,
"sealed box" de libsodium/PyNaCl).

Con la llave pública cualquiera puede CIFRAR, pero solo quien tiene la
llave privada (la bóveda) puede DESCIFRAR. El guardián ve el dato un
instante para detectarlo, lo cifra y lo olvida: a partir de ese momento
ni él mismo puede recuperarlo.

Además calcula un "índice ciego" (HMAC-SHA256 con una pimienta secreta)
para que la bóveda reconozca que dos mensajes traen el mismo dato y les
asigne el mismo marcador, sin ver el dato. Sin la pimienta no se puede
probar por fuerza bruta (una cédula tiene solo ~10^10 opciones, así que
un hash sin secreto sería reversible).
"""
import base64
import hashlib
import hmac
from functools import lru_cache
from pathlib import Path

from nacl.public import PublicKey, SealedBox

from common.tokens import normalize_value
from guardian.config import settings


@lru_cache(maxsize=1)
def _sealed_box() -> SealedBox:
    key = base64.b64decode(Path(settings.public_key_path).read_text().strip())
    return SealedBox(PublicKey(key))


@lru_cache(maxsize=1)
def _pepper() -> bytes:
    return base64.b64decode(Path(settings.pepper_path).read_text().strip())


def seal(value: str) -> str:
    return base64.b64encode(_sealed_box().encrypt(value.encode("utf-8"))).decode("ascii")


def blind_index(value: str) -> str:
    return hmac.new(_pepper(), normalize_value(value).encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def can_decrypt() -> bool:
    """El guardián no tiene forma de descifrar: SealedBox con solo la
    llave pública no expone decrypt() utilizable. Se reporta en /health."""
    try:
        _sealed_box().decrypt(b"\x00" * 80)
        return True
    except Exception:
        return False
