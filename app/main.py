import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import unsecure

logger = logging.getLogger("uvicorn.error")

# El router Secure depende de spaCy/Presidio (requirements.txt completo),
# que en versiones de Python muy nuevas (p. ej. 3.14) todavía no instalan.
# Si no están disponibles, la app sigue funcionando solo con /unsecure/chat
# en vez de fallar por completo al arrancar — así el Sprint 1 nunca se
# rompe por trabajo del Sprint 2.
secure_available = False
try:
    from app.routers import secure

    secure_available = True
except ImportError as exc:  # pragma: no cover - depende del entorno
    logger.warning(
        "No se pudo cargar /secure/chat (faltan dependencias de Presidio/spaCy: %s). "
        "Instala requirements.txt en un entorno con Python 3.11/3.12 para habilitarlo.",
        exc,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Precarga el modelo de spaCy/Presidio al arrancar, no en la primera
    # petición — así la métrica de latencia añadida (Sprint 2) no queda
    # inflada por la carga del modelo.
    if secure_available:
        from app.pii.engine import get_analyzer

        get_analyzer()
    yield


app = FastAPI(
    title="FDSI-GP-04 — Protección de datos personales enviados a un LLM",
    description=(
        "API de demostración con los escenarios Unsecure y Secure descritos "
        "en la propuesta del Hito 1."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(unsecure.router)
if secure_available:
    app.include_router(secure.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "secure_available": secure_available}
