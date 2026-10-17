from pydantic_settings import BaseSettings, SettingsConfigDict


class VaultSettings(BaseSettings):
    """La bóveda es el ÚNICO componente con la llave privada. Es efímera:
    no escribe nada en disco, todo vive en memoria y vence por inactividad."""

    model_config = SettingsConfigDict(env_prefix="VAULT_", extra="ignore")

    private_key_path: str = "secrets/vault/private.key"
    # Una conversación sin actividad durante este tiempo se borra de memoria.
    session_ttl_seconds: int = 1800
    # Tope de conversaciones simultáneas: al llegar, se borra la menos reciente.
    max_sessions: int = 1000
    token: str = ""


settings = VaultSettings()
