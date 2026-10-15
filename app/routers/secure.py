import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app import clients, sessions
from app.logging_config import log_secure_interaction
from app.security import require_user
from app.services.tools import resolve_tool_calls
from common.tokens import LABEL_TO_ENTITY

router = APIRouter(prefix="/secure", tags=["secure"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    log_id: str
    latency_ms: float
    entities_detected: list[str]
    audit: dict


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user: dict = Depends(require_user)) -> ChatResponse:
    """Arquitectura Secure con servicios separados:

    1. GUARDIÁN: detecta los datos personales y los cifra con la llave
       pública. Devuelve posiciones + cifrados, nunca el valor.
    2. BÓVEDA: guarda los cifrados y asigna marcadores consistentes por
       conversación ([CORREO_1] siempre es el mismo correo).
    3. La tienda reemplaza cada dato por su marcador.
    4. CHATBOT externo: recibe solo marcadores (mensaje e historial).
    5. GUARDIÁN otra vez: guardia de salida sobre la respuesta.
    6. Herramientas: la bóveda descifra un marcador solo para consultar
       el pedido (propósito autorizado, queda en su bitácora).
    7. Log solo con marcadores.
    8. BÓVEDA: reidentifica la respuesta final, solo con los marcadores
       de ESTA conversación, que pertenece al usuario autenticado.
    """
    start = time.perf_counter()
    session = sessions.get_or_create("secure", req.session_id, user["id"])

    # (1) detectar y cifrar
    t0 = time.perf_counter()
    found = clients.call("guardian", "/protect", {"text": req.message})["entities"]
    guardian_ms = (time.perf_counter() - t0) * 1000

    # (2) marcadores desde la bóveda
    tokens = []
    if found:
        tokens = clients.call("vault", "/tokens", {
            "session_id": session.id,
            "entities": [{"label": e["label"], "ciphertext": e["ciphertext"], "blind_index": e["blind_index"]} for e in found],
        })["tokens"]

    # (3) reemplazo (de atrás hacia adelante para no mover las posiciones)
    anonymized = req.message
    for e, token in sorted(zip(found, tokens), key=lambda p: p[0]["start"], reverse=True):
        anonymized = anonymized[: e["start"]] + token + anonymized[e["end"] :]

    # (4) el chatbot externo solo ve marcadores
    history_sent = list(session.history)
    t0 = time.perf_counter()
    bot = clients.call("chatbot", "/chat", {"message": anonymized, "history": history_sent})
    llm_ms = (time.perf_counter() - t0) * 1000
    llm_output = bot["reply"]

    # (5) guardia de salida
    guarded = clients.call("guardian", "/redact", {"text": llm_output})

    # (6) herramientas internas
    def resolver(token: str) -> str | None:
        return clients.call("vault", "/resolve", {"session_id": session.id, "token": token, "purpose": "consultar_pedido"})["value"]

    anon_response, tool_calls = resolve_tool_calls(guarded["text"], resolver, user)
    session.add_turn(anonymized, guarded["text"])

    # (8) respuesta completa solo para el usuario de esta conversación
    final_response = clients.call("vault", "/reidentify", {"session_id": session.id, "text": anon_response})["text"]
    latency_ms = (time.perf_counter() - start) * 1000

    entity_types = [LABEL_TO_ENTITY[e["label"]] for e in found]
    tools = [vars(t) for t in tool_calls]

    # (7) log sin datos personales
    log_id = log_secure_interaction(
        user_id=str(user["id"]),
        anonymized_message=anonymized,
        anonymized_response=anon_response,
        entities_found=entity_types,
        latency_ms=latency_ms,
        reid_request_id=session.id,
        extra={"session_id": session.id, "llm_ms": llm_ms, "guardian_ms": guardian_ms,
               "output_guard_redactions": guarded["redactions"], "tool_calls": tools},
    )

    return ChatResponse(
        response=final_response,
        session_id=session.id,
        log_id=log_id,
        latency_ms=latency_ms,
        entities_detected=entity_types,
        audit={
            "scenario": "secure",
            "llm_provider": bot.get("provider"),
            "llm_input": anonymized,
            "llm_history_turns": len(history_sent) // 2,
            "llm_output": llm_output,
            "logged_message": anonymized,
            "logged_response": anon_response,
            "entities": [{"tipo": e["label"], "marcador": t, "cifrado": e["ciphertext"][:24] + "…"} for e, t in zip(found, tokens)],
            "output_guard_redactions": guarded["redactions"],
            "tool_calls": tools,
            "llm_ms": llm_ms,
            "guardian_ms": guardian_ms,
            "servicios": ["tienda", "guardian", "vault", "chatbot"],
        },
    )

