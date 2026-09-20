"""
Anonimización con marcadores (tokens) por entidad, más el mapeo
token -> valor original que necesita el módulo de reidentificación.

Sección 5 de la propuesta: "identifica entidades sensibles ... y las
reemplaza por marcadores o pseudónimos".
"""
import itertools
from dataclasses import dataclass, field

from app.pii.engine import analyze


@dataclass
class AnonymizationResult:
    anonymized_text: str
    mapping: dict[str, str] = field(default_factory=dict)  # token -> valor original
    entities_found: list[str] = field(default_factory=list)  # tipos detectados, para métricas


def anonymize(text: str) -> AnonymizationResult:
    results = analyze(text)

    if not results:
        return AnonymizationResult(anonymized_text=text, mapping={}, entities_found=[])

    # Contadores por tipo de entidad para nombrar los tokens: [NOMBRE_1],
    # [NOMBRE_2], [CEDULA_1], etc. — así se distinguen varias entidades del
    # mismo tipo dentro de un mismo mensaje (ver caso T25 del dataset).
    counters: dict[str, itertools.count] = {}
    mapping: dict[str, str] = {}
    entities_found: list[str] = []

    # Reemplazar de atrás hacia adelante para no invalidar los índices
    # (start/end) de las detecciones anteriores al mensaje.
    anonymized_text = text
    for r in sorted(results, key=lambda r: r.start, reverse=True):
        entity_label = _friendly_label(r.entity_type)
        counters.setdefault(entity_label, itertools.count(1))
        token = f"[{entity_label}_{next(counters[entity_label])}]"

        original_value = text[r.start : r.end]
        mapping[token] = original_value
        entities_found.append(r.entity_type)

        anonymized_text = anonymized_text[: r.start] + token + anonymized_text[r.end :]

    return AnonymizationResult(
        anonymized_text=anonymized_text,
        mapping=mapping,
        entities_found=list(reversed(entities_found)),
    )


def reidentify(text: str, mapping: dict[str, str]) -> str:
    """Reemplaza los tokens por sus valores originales. USO EXCLUSIVO del
    módulo de reidentificación controlada, para devolverle al usuario
    legítimo una respuesta completa — nunca se aplica antes del log ni
    antes de enviar el mensaje al LLM."""
    result = text
    for token, original_value in mapping.items():
        result = result.replace(token, original_value)
    return result


_ENTITY_LABELS = {
    "PERSON": "NOMBRE",
    "EMAIL_ADDRESS": "CORREO",
    "CEDULA_CO": "CEDULA",
    "TELEFONO_CO": "TELEFONO",
}


def _friendly_label(entity_type: str) -> str:
    return _ENTITY_LABELS.get(entity_type, entity_type)
