"""
TIENDA Andes Market (el monolito): página web, usuarios, catálogo, carrito,
pedidos y logs, sobre una base de datos SQLite (app/db.py).

No contiene ningún modelo de IA ni ninguna llave. Para el modo seguro
coordina tres servicios externos por HTTP:
  - guardian (detector entrenado + cifrado con llave pública)
  - vault    (bóveda con la llave privada)
  - chatbot  (Andi, el modelo conversacional)
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import clients, db
from app.routers import auth, demo, secure, store, unsecure

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.conn()  # crea y llena la base de datos si está vacía
    yield


app = FastAPI(
    title="FDSI-GP-04 — Andes Market",
    description="Tienda simulada con chatbot externo y los escenarios Unsecure y Secure de la propuesta.",
    version="3.0.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(store.router)
app.include_router(unsecure.router)
app.include_router(secure.router)
app.include_router(demo.router)


@app.middleware("http")
async def no_cache(request, call_next):
    # la página cambia con cada versión del proyecto: que el navegador
    # siempre revalide en vez de mostrar una copia vieja durante la demo
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "servicios": {s: "error" not in clients.health(s) for s in ("guardian", "vault", "chatbot")}}


# La página web (al final para no tapar la API).
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="web")
