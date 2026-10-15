from pydantic_settings import BaseSettings, SettingsConfigDict


class GuardianSettings(BaseSettings):
    """Lo ÚNICO que recibe el guardián: su modelo, la llave PÚBLICA, la
    pimienta del índice ciego y su token. No recibe la llave privada, ni
    carpetas de datos, ni logs."""

    model_config = SettingsConfigDict(env_prefix="GUARDIAN_", extra="ignore")

    model_path: str = "models/guardian_ner"
    public_key_path: str = "secrets/guardian/public.key"
    pepper_path: str = "secrets/guardian/pepper.key"
    token: str = ""
    # hibrido = modelo entrenado + reglas de validación; modelo; reglas
    mode: str = "hibrido"


settings = GuardianSettings()
