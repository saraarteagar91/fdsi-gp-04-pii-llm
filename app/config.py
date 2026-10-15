from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la TIENDA (el monolito). Conoce la dirección y el
    token de cada servicio, pero no tiene ninguna llave de cifrado: no
    puede descifrar nada por su cuenta, tiene que pedírselo a la bóveda."""

    model_config = SettingsConfigDict(env_prefix="APP_", extra="ignore")

    guardian_url: str = "http://127.0.0.1:8101"
    vault_url: str = "http://127.0.0.1:8102"
    chatbot_url: str = "http://127.0.0.1:8103"
    guardian_token: str = ""
    vault_token: str = ""
    chatbot_token: str = ""
    service_timeout_s: float = 30.0

    db_path: str = "data/db/andes_market.db"
    # True si se sirve por HTTPS (la cookie de sesión solo viajaría cifrada)
    cookie_secure: bool = False

    log_dir: str = "logs"
    data_dir: str = "data"
    model_dir: str = "models"


settings = Settings()
