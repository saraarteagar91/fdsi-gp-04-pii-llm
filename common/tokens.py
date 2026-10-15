"""Formato de los marcadores que reemplazan a los datos personales."""
import re

# Tipo interno del detector -> etiqueta del marcador
ENTITY_LABELS = {
    "PERSON": "NOMBRE",
    "EMAIL_ADDRESS": "CORREO",
    "CEDULA_CO": "CEDULA",
    "TELEFONO_CO": "TELEFONO",
    "DIRECCION_CO": "DIRECCION",
}
LABEL_TO_ENTITY = {v: k for k, v in ENTITY_LABELS.items()}

TOKEN_RE = re.compile(r"\[(?:NOMBRE|CEDULA|TELEFONO|CORREO|DIRECCION)_\d+\]")
REDACTION_TOKEN = "[DATO_REDACTADO]"
ANY_MARKER_RE = re.compile(r"\[(?:NOMBRE|CEDULA|TELEFONO|CORREO|DIRECCION|DATO_REDACTADO)(?:_\d+)?\]")


def normalize_value(value: str) -> str:
    """Forma canónica para reconocer el mismo dato escrito distinto
    (300 123 4567 == 3001234567, JUAN@X.COM == juan@x.com)."""
    return re.sub(r"[^0-9a-záéíóúñü@]", "", value.lower())
