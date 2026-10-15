import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app import clients, sessions
from app.logging_config import log_unsecure_interaction
from app.security import require_admin
from app.services.tools import resolve_tool_calls

router = APIRouter(prefix="/unsecure", tags=["unsecure"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    log_id: str
    latency_ms: float
    audit: dict


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user: dict = Depends(require_admin)) -> ChatResponse:
    """Arquitectura Unsecure de la propuesta (sección 4): el mensaje y todo
    el historial viajan crudos hasta el chatbot externo, y la conversación
    completa (con los datos personales) queda en el log.

    Es la línea base de la demostración: solo la puede usar el equipo de
    seguridad (rol admin) desde el Centro de seguridad."""
    start = time.perf_counter()
    session = sessions.get_or_create("unsecure", req.session_id, user["id"])
    history_sent = list(session.history)

    llm_start = time.perf_counter()
    bot = clients.call("chatbot", "/chat", {"message": req.message, "history": history_sent})
    llm_ms = (time.perf_counter() - llm_start) * 1000
    llm_output = bot["reply"]

    final_response, tool_calls = resolve_tool_calls(llm_output, None, user)
    session.add_turn(req.message, llm_output)
    latency_ms = (time.perf_counter() - start) * 1000

    tools = [vars(t) for t in tool_calls]
    log_id = log_unsecure_interaction(
        user_id=str(user["id"]),
        user_message=req.message,
        llm_response=final_response,
        latency_ms=latency_ms,
        extra={"session_id": session.id, "llm_ms": llm_ms, "tool_calls": tools},
    )

    return ChatResponse(
        response=final_response,
        session_id=session.id,
        log_id=log_id,
        latency_ms=latency_ms,
        audit={
            "scenario": "unsecure",
            "llm_provider": bot.get("provider"),
            "llm_input": req.message,
            "llm_history_turns": len(history_sent) // 2,
            "llm_output": llm_output,
            "logged_message": req.message,
            "logged_response": final_response,
            "entities": [],
            "output_guard_redactions": [],
            "tool_calls": tools,
            "llm_ms": llm_ms,
            "servicios": ["tienda", "chatbot"],
        },
    )
