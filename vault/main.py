"""
Servicio BÓVEDA: el único componente con la llave privada.

- /tokens:     recibe del guardián (vía la tienda) los datos CIFRADOS y
               asigna marcadores consistentes por conversación.
- /reidentify: cambia los marcadores por los datos reales, SOLO los de la
               conversación indicada (respuesta final al usuario).
- /resolve:    descifra UN marcador para un propósito interno autorizado
               (consultar un pedido). Cada uso queda en la bitácora.
- DELETE /session/{id}: borra una conversación al cerrarla.

Es efímera: todo vive en memoria y cada conversación vence por
inactividad (VAULT_SESSION_TTL_SECONDS). Una conversación vencida ya no
se puede reidentificar ni resolver.

No habla con el chatbot ni con el guardián; solo atiende a la tienda.
"""
import re

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from common.auth import require_token
from common.tokens import TOKEN_RE
from vault.config import settings
from vault.store import _box, get_store

ALLOWED_PURPOSES = {"consultar_pedido"}

app = FastAPI(title="Bóveda de reidentificación — FDSI-GP-04", version="1.0.0", docs_url=None, redoc_url=None)
auth = Depends(require_token(lambda: settings.token))


class EncryptedEntity(BaseModel):
    label: str
    ciphertext: str
    blind_index: str


class TokensIn(BaseModel):
    session_id: str
    entities: list[EncryptedEntity]


class ReidentifyIn(BaseModel):
    session_id: str
    text: str


class ResolveIn(BaseModel):
    session_id: str
    token: str
    purpose: str


@app.post("/tokens", dependencies=[auth])
def tokens(body: TokensIn) -> dict:
    store = get_store()
    return {"tokens": [store.assign(body.session_id, e.label, e.ciphertext, e.blind_index) for e in body.entities]}


@app.post("/reidentify", dependencies=[auth])
def reidentify(body: ReidentifyIn) -> dict:
    store = get_store()
    own = set(store.tokens_of(body.session_id))

    def _swap(m: re.Match) -> str:
        token = m.group(0)
        if token not in own:  # marcador de otra conversación (o vencida): no se revela
            return token
        return store.decrypt(body.session_id, token) or token

    return {"text": TOKEN_RE.sub(_swap, body.text)}


@app.post("/resolve", dependencies=[auth])
def resolve(body: ResolveIn) -> dict:
    if body.purpose not in ALLOWED_PURPOSES:
        raise HTTPException(status_code=403, detail="Propósito no autorizado")
    store = get_store()
    value = store.decrypt(body.session_id, body.token)
    if value is None:
        raise HTTPException(status_code=404, detail="Marcador desconocido en esta conversación")
    store.log_access(body.session_id, body.token, body.purpose)
    return {"value": value}


@app.delete("/session/{session_id}", dependencies=[auth])
def forget_session(session_id: str) -> dict:
    return {"borrada": get_store().forget(session_id)}


@app.get("/health")
def health() -> dict:
    _box()  # falla si no tiene la llave privada
    return {"servicio": "vault", "tiene_llave_privada": True}
