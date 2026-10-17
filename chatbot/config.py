from pydantic_settings import BaseSettings, SettingsConfigDict


class ChatbotSettings(BaseSettings):
    """El chatbot no recibe ninguna llave de cifrado ni acceso a datos: solo
    su modelo, su token y (opcional) la API key de un LLM comercial."""

    model_config = SettingsConfigDict(env_prefix="CHATBOT_", extra="ignore")

    # "local"     -> asistente Andi entrenado (por defecto, sin API key)
    # "anthropic" -> Claude vía API (requiere CHATBOT_ANTHROPIC_API_KEY)
    # "openai"    -> GPT vía API (requiere CHATBOT_OPENAI_API_KEY y `pip install openai`),
    #                o cualquier API compatible con OpenAI (p. ej. Gemini) con CHATBOT_OPENAI_BASE_URL
    # "mock"      -> eco determinístico, solo para pruebas
    llm_provider: str = "local"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_model: str = "claude-haiku-5-5"
    openai_model: str = "gpt-4o-mini"
    # Vacío -> la API de OpenAI. Otra dirección -> un proveedor compatible con OpenAI.
    openai_base_url: str = ""

    model_dir: str = "models"
    corpus_path: str = "data/bot/intents.json"
    token: str = ""


settings = ChatbotSettings()
