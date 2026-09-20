"""
Construye el AnalyzerEngine de Presidio en español, con spaCy como motor
de NLP (para detectar nombres de persona vía NER) más los reconocedores
custom de cédula y teléfono colombianos.

Se construye una sola vez (patrón singleton) porque cargar el modelo de
spaCy toma un par de segundos — no queremos hacerlo en cada petición.
"""
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

from app.pii.recognizers import (
    build_cedula_recognizer,
    build_nombre_mayusculas_recognizer,
    build_telefono_recognizer,
)

SPACY_MODEL = "es_core_news_md"

# Entidades que nos interesan para esta propuesta (evita ruido de otras
# entidades que Presidio detecta por defecto, como URL o LOCATION, que no
# son el foco de la sección 5 de la propuesta).
SUPPORTED_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "CEDULA_CO",
    "TELEFONO_CO",
]


@lru_cache(maxsize=1)
def get_analyzer() -> AnalyzerEngine:
    nlp_configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "es", "model_name": SPACY_MODEL}],
    }
    provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
    nlp_engine = provider.create_engine()

    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["es"])
    analyzer.registry.add_recognizer(build_cedula_recognizer())
    analyzer.registry.add_recognizer(build_telefono_recognizer())
    analyzer.registry.add_recognizer(build_nombre_mayusculas_recognizer())
    return analyzer


def analyze(text: str):
    """Devuelve los resultados de Presidio, filtrados a las entidades de
    interés de esta propuesta y sin resultados solapados/duplicados."""
    analyzer = get_analyzer()
    results = analyzer.analyze(text=text, language="es", entities=SUPPORTED_ENTITIES)
    return _remove_overlaps(results)


def _remove_overlaps(results):
    """Si dos detecciones se solapan (p. ej. NER y regex sobre el mismo
    tramo de texto), nos quedamos con la de mayor score."""
    results = sorted(results, key=lambda r: (r.start, -r.score))
    kept = []
    last_end = -1
    for r in results:
        if r.start >= last_end:
            kept.append(r)
            last_end = r.end
        elif r.end > last_end:
            # se solapa parcialmente: preferimos mantener el primero ya
            # aceptado (mayor score por el orden de sort) y descartar este.
            continue
    return kept
