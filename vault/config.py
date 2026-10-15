from pydantic_settings import BaseSettings, SettingsConfigDict


class VaultSettings(BaseSettings):
    """La bóveda es el ÚNICO componente con la llave privada."""

    model_config = SettingsConfigDict(env_prefix="VAULT_", extra="ignore")

    private_key_path: str = "secrets/vault/private.key"
    store_dir: str = "data/vault"
    token: str = ""


settings = VaultSettings()
