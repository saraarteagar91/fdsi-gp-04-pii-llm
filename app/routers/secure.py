import time

from fastapi import APIRouter
from pydantic import BaseModel

from app.llm_client import llm_client
from app.logging_config import log_secure_interaction
from app.pii.anonymizer import anonymize, reidentify
from app.pii.reid_store import store_mapping

router = APIRouter(prefix="/secure", tags=["secure"])


class ChatRequest(BaseModel):
    user_id: str
    message: str


class ChatResponse(BaseModel):
    response: str
    log_id: str
    latency_ms: float
    entities_detected: list[str]


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Arquitectura Secure de la propuesta (sección 5):

    1. Se anonimiza el mensaje ANTES de que salga hacia el LLM.
    2. El LLM y el log solo ven la versión anonimizada (con marcadores).
    3. El mapeo token -> PII real se guarda cifrado y por separado
       (reid_store), nunca junto al log de la conversación.
    4. Solo al devolver la respuesta al usuario legítimo se reidentifica
       (módulo de reidentificación controlada) — el LLM y los logs nunca
       ven el dato real.
    """
    start = time.perf_counter()

    anon_result = anonymize(req.message)

    # (1) y (2): el LLM solo recibe el mensaje anonimizado.
    llm_response_anon = llm_client.complete(anon_result.anonymized_text)

    # (3): el mapping se cifra y se guarda aparte del log.
    reid_request_id = store_mapping(anon_result.mapping)

    # (4): reidentificación controlada, solo para la respuesta final al
    # usuario legítimo — nunca se aplica al texto que se loguea ni al que
    # se envió al LLM.
    final_response = reidentify(llm_response_anon, anon_result.mapping)

    latency_ms = (time.perf_counter() - start) * 1000

    log_id = log_secure_interaction(
        user_id=req.user_id,
        anonymized_message=anon_result.anonymized_text,
        anonymized_response=llm_response_anon,
        entities_found=anon_result.entities_found,
        latency_ms=latency_ms,
        reid_request_id=reid_request_id,
    )

    return ChatResponse(
        response=final_response,
        log_id=log_id,
        latency_ms=latency_ms,
        entities_detected=anon_result.entities_found,
    )
