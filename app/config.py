from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración centralizada, leída desde variables de entorno / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    llm_provider: str = "mock"  # "anthropic" | "openai" | "mock"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_model: str = "claude-3-5-haiku-latest"
    log_dir: str = "logs"


settings = Settings()
