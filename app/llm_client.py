"""
Wrapper mínimo sobre el LLM para poder intercambiar de proveedor (o usar un
mock sin costo) sin tocar los routers.

Sprint 1: solo necesitamos que esto funcione de punta a punta. El modo
"mock" existe para que el equipo pueda correr y demostrar todo el flujo
(incluyendo los logs y las pruebas) sin necesitar una API key real.
"""
from app.config import settings


class LLMClient:
    def __init__(self) -> None:
        self.provider = settings.llm_provider

    def complete(self, message: str) -> str:
        if self.provider == "anthropic" and settings.anthropic_api_key:
            return self._complete_anthropic(message)
        if self.provider == "openai" and settings.openai_api_key:
            return self._complete_openai(message)
        return self._complete_mock(message)

    def _complete_mock(self, message: str) -> str:
        # Respuesta determinística y barata, útil para pruebas automatizadas.
        # Repite parte del mensaje para poder probar "fuga por reflejo" (T03).
        return f"[MOCK-LLM] Recibí tu mensaje: \"{message[:200]}\""

    def _complete_anthropic(self, message: str) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        resp = client.messages.create(
            model=settings.llm_model,
            max_tokens=512,
            messages=[{"role": "user", "content": message}],
        )
        return resp.content[0].text

    def _complete_openai(self, message: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model=settings.llm_model or "gpt-4o-mini",
            messages=[{"role": "user", "content": message}],
        )
        return resp.choices[0].message.content


llm_client = LLMClient()
