"""
Servicio CHATBOT: el "modelo de IA externo" de la propuesta.

Recibe exactamente lo que la tienda decide enviarle (texto crudo en modo
inseguro, solo marcadores en modo seguro) y el historial de esa
conversación. No conoce la bóveda ni el guardián, y no tiene ninguna
llave: aunque quisiera, no podría convertir [CORREO_1] en el correo real.

Proveedores: Andi entrenado localmente (por defecto), Claude, GPT o mock.
"""
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from chatbot.config import settings
from chatbot.training import REPORT_FILENAME
from common.auth import require_token

SYSTEM_PROMPT = (
    "Eres Andi, el asistente virtual de Andes Market, una tienda en línea colombiana. Responde en español, "
    "breve y amable, solo sobre pedidos, envíos, devoluciones, garantías, pagos y actualización de datos. "
    "Los datos personales del usuario pueden aparecer como marcadores como [NOMBRE_1], [CORREO_1], "
    "[CEDULA_1], [TELEFONO_1] o [DIRECCION_1]: úsalos tal cual, nunca intentes adivinar el valor real y "
    "nunca inventes datos personales. Si el usuario pregunta por el estado de un pedido y te da un correo, "
    "cédula o número de pedido (AM-xxxxx), incluye exactamente el texto {{consultar_pedido:<dato>}} en tu "
    "respuesta (por ejemplo {{consultar_pedido:[CORREO_1]}}); si no da ningún dato, usa "
    "{{consultar_pedido:mi_cuenta}}. El sistema lo reemplazará por el estado real."
)


def active_provider() -> str:
    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        return "anthropic"
    if settings.llm_provider == "openai" and settings.openai_api_key:
        return "openai"
    if settings.llm_provider == "mock":
        return "mock"
    return "local"


def complete(message: str, history: list[dict]) -> str:
    provider = active_provider()
    if provider == "mock":
        # Determinístico: repite el mensaje para probar la fuga por reflejo (T03).
        return f"[MOCK-LLM] Recibí tu mensaje: \"{message[:200]}\""
    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        resp = client.messages.create(
            model=settings.llm_model, max_tokens=512, system=SYSTEM_PROMPT,
            messages=[*history, {"role": "user", "content": message}],
        )
        return "".join(b.text for b in resp.content if b.type == "text")
    if provider == "openai":
        from openai import OpenAI

        resp = OpenAI(api_key=settings.openai_api_key).chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, *history, {"role": "user", "content": message}],
        )
        return resp.choices[0].message.content
    from chatbot.assistant import get_assistant

    return get_assistant().reply(message, history)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if active_provider() == "local":
        from chatbot.assistant import get_assistant

        get_assistant().reply("hola")  # entrena si hace falta y calienta el modelo
    yield


app = FastAPI(title="Chatbot Andi — FDSI-GP-04", version="1.0.0", lifespan=lifespan, docs_url=None, redoc_url=None)
auth = Depends(require_token(lambda: settings.token))


class ChatIn(BaseModel):
    message: str
    history: list[dict] = []


@app.post("/chat", dependencies=[auth])
def chat(body: ChatIn) -> dict:
    return {"reply": complete(body.message, body.history), "provider": active_provider()}


@app.get("/info", dependencies=[auth])
def info() -> dict:
    path = Path(settings.model_dir) / REPORT_FILENAME
    report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    report.pop("reporte_por_intencion", None)
    return {"proveedor_activo": active_provider(), "entrenamiento": report}


@app.get("/health")
def health() -> dict:
    return {"servicio": "chatbot", "proveedor": active_provider()}
