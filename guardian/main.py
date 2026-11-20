"""
Servicio GUARDIÁN: detecta datos personales y los cifra con la llave
pública. Corre aparte de la tienda, en una red interna sin salida a
internet, con disco de solo lectura y sin logs de contenido.

Garantías de diseño (verificadas en tests/test_isolation.py):
- Nunca devuelve el valor detectado en claro: solo posición, tipo,
  cifrado e índice ciego.
- No guarda nada (sin base de datos, sin archivos, sin memoria entre
  peticiones).
- No puede descifrar: solo tiene la llave pública.
- Solo atiende a la tienda (token de servicio).
"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

from common.auth import require_token
from common.tokens import ENTITY_LABELS, REDACTION_TOKEN
from guardian import crypto
from guardian.config import settings
from guardian.engine import analyze


@asynccontextmanager
async def lifespan(app: FastAPI):
    analyze("Hola, soy Ana Pérez, cédula 1.020.304.050")  # carga y calienta los modelos
    crypto.seal("calentamiento")
    yield


app = FastAPI(title="Guardián PII — FDSI-GP-04", version="1.0.0", lifespan=lifespan, docs_url=None, redoc_url=None)
auth = Depends(require_token(lambda: settings.token))


# Lab. 06 (F-11, CWE-770): tamaño máximo para no procesar cuerpos sin límite.
class TextIn(BaseModel):
    text: str = Field(max_length=20000)


class ProtectedEntity(BaseModel):
    label: str        # NOMBRE, CEDULA, ...
    start: int
    end: int
    score: float
    ciphertext: str   # cifrado con la llave pública (solo la bóveda lo abre)
    blind_index: str  # HMAC con pimienta: mismo dato -> mismo índice


class ProtectOut(BaseModel):
    entities: list[ProtectedEntity]


class RedactOut(BaseModel):
    text: str
    redactions: list[str]


@app.post("/protect", response_model=ProtectOut, dependencies=[auth])
def protect(body: TextIn) -> ProtectOut:
    entities = []
    for r in analyze(body.text):
        value = body.text[r.start:r.end]
        entities.append(ProtectedEntity(
            label=ENTITY_LABELS[r.entity_type],
            start=r.start,
            end=r.end,
            score=round(r.score, 3),
            ciphertext=crypto.seal(value),
            blind_index=crypto.blind_index(value),
        ))
        del value
    return ProtectOut(entities=entities)


def _relevant_for_output(text: str, r) -> bool:
    """En texto generado por el chatbot, una palabra suelta con mayúscula al
    inicio de una oración ("Registré", "Perfecto") no es un nombre: para la
    guardia de salida solo cuenta un nombre de al menos dos palabras."""
    if r.entity_type != "PERSON":
        return True
    words = text[r.start:r.end].split()
    return len(words) >= 2 and all(w[0].isupper() for w in words)


@app.post("/redact", response_model=RedactOut, dependencies=[auth])
def redact(body: TextIn) -> RedactOut:
    """Guardia de salida: borra datos personales que el chatbot haya
    generado por su cuenta (los marcadores se respetan)."""
    results = [r for r in analyze(body.text) if _relevant_for_output(body.text, r)]
    text = body.text
    for r in sorted(results, key=lambda r: r.start, reverse=True):
        text = text[: r.start] + REDACTION_TOKEN + text[r.end :]
    return RedactOut(text=text, redactions=[ENTITY_LABELS[r.entity_type] for r in results])


@app.get("/health")
def health() -> dict:
    return {
        "servicio": "guardian",
        "modo": settings.mode,
        "modelo": settings.model_path,
        "tiene_llave_publica": True,
        "puede_descifrar": crypto.can_decrypt(),
    }
