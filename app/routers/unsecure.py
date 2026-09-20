import time

from fastapi import APIRouter
from pydantic import BaseModel

from app.llm_client import llm_client
from app.logging_config import log_unsecure_interaction

router = APIRouter(prefix="/unsecure", tags=["unsecure"])


class ChatRequest(BaseModel):
    user_id: str
    message: str


class ChatResponse(BaseModel):
    response: str
    log_id: str
    latency_ms: float


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Arquitectura Unsecure de la propuesta (sección 4):

    El mensaje viaja sin ninguna transformación desde el "frontend" hasta
    el LLM, y se registra la conversación completa (incluyendo el PII) en
    los logs. No hay ningún límite de confianza entre la aplicación y el
    proveedor del modelo.
    """
    start = time.perf_counter()
    llm_response = llm_client.complete(req.message)
    latency_ms = (time.perf_counter() - start) * 1000

    log_id = log_unsecure_interaction(
        user_id=req.user_id,
        user_message=req.message,
        llm_response=llm_response,
        latency_ms=latency_ms,
    )

    return ChatResponse(response=llm_response, log_id=log_id, latency_ms=latency_ms)
