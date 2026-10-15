"""
Motor de detección del guardián (Presidio como orquestador).

Tres modos, para poder compararlos en la evaluación:
- "modelo":  solo el modelo NER entrenado por el equipo.
- "reglas":  solo reglas de validación (regex + contexto).
- "hibrido": modelo + reglas (modo por defecto del servicio).

spaCy es_core_news_md se usa solo como motor de lenguaje de Presidio
(tokenización y lemas para las palabras de contexto); su NER genérico NO
participa en la detección: los nombres los detecta el modelo propio.
"""
import re
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider

from common.tokens import ANY_MARKER_RE
from guardian.config import settings
from guardian.recognizers import (
    NombrePorContextoRecognizer,
    TrainedNerRecognizer,
    build_cedula_recognizer,
    build_correo_ofuscado_recognizer,
    build_direccion_recognizer,
    build_email_recognizer,
    build_nombre_mayusculas_recognizer,
    build_telefono_recognizer,
)

LANGUAGE_MODEL = "es_core_news_md"
MODES = ("hibrido", "modelo", "reglas")

SUPPORTED_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "CEDULA_CO", "TELEFONO_CO", "DIRECCION_CO"]

# Puntaje mínimo para aceptar una detección. Deja por fuera los patrones
# "débiles" (p. ej. MAYÚSCULAS sin contexto, score 0.3).
SCORE_THRESHOLD = 0.4

# Términos que suelen confundirse con nombres de persona: los propios del
# sitio (el asistente se llama "Andi"), ciudades colombianas con nombre de
# persona ("Santa Marta") y marcas comunes de medios de pago y productos.
ALLOW_LIST = [
    "Andi", "Andes Market", "Andes", "Market",
    "Santa Marta", "San Andrés", "Santa Rosa", "San Gil", "Bogotá", "Medellín", "Cali", "Barranquilla",
    "Cartagena", "Bucaramanga", "Pereira", "Manizales", "Cúcuta", "Ibagué", "Villavicencio", "Pasto",
    "Tunja", "Neiva", "Armenia", "Montería", "Valledupar", "Popayán", "Sincelejo", "Riohacha",
    "PSE", "Nequi", "Daviplata", "Visa", "Mastercard", "American Express", "Diners", "Bancolombia",
    "Davivienda", "Servientrega", "Coordinadora", "Interrapidísimo", "Envía",
    "iPhone", "Samsung", "Xiaomi", "Motorola", "Huawei", "Lenovo", "Apple",
]


@lru_cache(maxsize=1)
def _nlp_engine():
    provider = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "es", "model_name": LANGUAGE_MODEL}],
    })
    return provider.create_engine()


@lru_cache(maxsize=1)
def _model_recognizer() -> TrainedNerRecognizer:
    return TrainedNerRecognizer(settings.model_path)


def _rule_recognizers() -> list:
    return [
        build_email_recognizer(),
        build_cedula_recognizer(),
        build_telefono_recognizer(),
        build_direccion_recognizer(),
        build_correo_ofuscado_recognizer(),
        build_nombre_mayusculas_recognizer(),
        NombrePorContextoRecognizer(),
    ]


@lru_cache(maxsize=len(MODES))
def get_analyzer(mode: str | None = None) -> AnalyzerEngine:
    mode = mode or settings.mode
    if mode not in MODES:
        raise ValueError(f"Modo desconocido: {mode}")
    recognizers = []
    if mode in ("hibrido", "modelo"):
        recognizers.append(_model_recognizer())
    if mode in ("hibrido", "reglas"):
        recognizers.extend(_rule_recognizers())
    registry = RecognizerRegistry(recognizers=recognizers, supported_languages=["es"])
    return AnalyzerEngine(registry=registry, nlp_engine=_nlp_engine(), supported_languages=["es"])


def analyze(text: str, mode: str | None = None):
    """Detecciones filtradas: sin solapamientos y sin tocar marcadores ya
    anonimizados."""
    results = get_analyzer(mode).analyze(
        text=text,
        language="es",
        entities=SUPPORTED_ENTITIES,
        score_threshold=SCORE_THRESHOLD,
        allow_list=ALLOW_LIST,
    )
    results = [_trim(text, r) for r in results]
    if (mode or settings.mode) == "hibrido":
        results = [r for r in results if _valid(text[r.start:r.end], r.entity_type) and _name_case_ok(text, r)]
    marker_spans = [m.span() for m in ANY_MARKER_RE.finditer(text)]
    results = [
        r for r in results
        if r.end > r.start
        and not any(r.start < me and r.end > ms for ms, me in marker_spans)
        # un dato personal siempre tiene letras o números (descarta "}" sueltos)
        and re.search(r"\w", text[r.start:r.end])
        # un nombre nunca lleva dígitos (evita marcar "AM-10231" como persona)
        and not (r.entity_type == "PERSON" and re.search(r"\d", text[r.start:r.end]))
    ]
    return _resolve_overlaps(results)


def _valid(span: str, entity_type: str) -> bool:
    """Reglas de VALIDACIÓN del modo híbrido: el modelo propone y las reglas
    confirman que el tramo tenga la forma mínima de ese tipo de dato
    (sección 8 de la propuesta). Así se descartan propuestas como
    "Ley 1480" (teléfono) o "Calle Real" (dirección sin placa)."""
    digits = re.sub(r"\D", "", span)
    if entity_type == "CEDULA_CO":
        return 6 <= len(digits) <= 10 and not re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", span)
    if entity_type == "TELEFONO_CO":
        if len(digits) == 12 and digits.startswith("57"):
            digits = digits[2:]
        return len(digits) == 10 and (digits.startswith("3") or digits.startswith("60")) and not re.search(r"[A-Za-z]", span)
    if entity_type == "DIRECCION_CO":
        return bool(digits)
    if entity_type == "EMAIL_ADDRESS":
        return "@" in span or "arroba" in span.lower()
    if entity_type == "PERSON":
        return bool(re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{2}", span)) and not re.search(r"[«»()/<>{}\[\]%$]", span)
    return True


_NAME_CONNECTORS = {"de", "del", "la", "las", "los", "y"}
_PRESENTATION_RE = re.compile(r"(?i)(me\s+llamo|mi\s+nombre\s+es|nombre\s*:|nombre\s+completo\s*:?|soy|habla|les?\s+escribe|te\s+saluda|atentamente,?|cordialmente,?)\s*$")


def _name_case_ok(text: str, r) -> bool:
    """Un nombre con palabras en minúscula ("laura martínez") solo se acepta
    si viene justo después de una presentación ("me llamo", "soy"...).
    Evita marcar frases como "semana pasada" o "Solo puedo ayudarte"."""
    if r.entity_type != "PERSON":
        return True
    words = [w for w in text[r.start:r.end].split() if w.lower() not in _NAME_CONNECTORS]
    if all(w[0].isupper() for w in words):
        return True
    return bool(_PRESENTATION_RE.search(text[max(0, r.start - 30):r.start]))


def _trim(text: str, r):
    """A la cédula se le quita el prefijo ("cédula", "C.C.") para
    reemplazar solo el número, y a todo se le quitan espacios/puntuación
    sobrante en los bordes."""
    if r.entity_type == "CEDULA_CO":
        first_digit = re.search(r"\d", text[r.start:r.end])
        if first_digit:
            r.start += first_digit.start()
    while r.start < r.end and text[r.start] in " ,;:\n«»¿?¡!\"'":
        r.start += 1
    while r.end > r.start and text[r.end - 1] in " ,;:.\n«»¿?¡!\"'":
        r.end -= 1
    # el punto final solo se quita si no es parte de una inicial ("G.")
    if text[r.start:r.end + 1].endswith(".") and re.search(r"\b[A-ZÁÉÍÓÚÑ]$", text[r.start:r.end]):
        r.end += 1
    return r


def _resolve_overlaps(results):
    """Agrupa detecciones que se solapan y deja una sola por grupo, cuyo
    tramo es la UNIÓN de todas (si el modelo detecta "Juan Carlos Pérez" y
    una regla "Juan Carlos Pérez Gómez", se protege el nombre completo).
    Si una detección cubre todo el grupo, su tipo manda; si no, el de
    mayor score."""
    if not results:
        return []
    results = sorted(results, key=lambda r: r.start)
    clusters = [[results[0]]]
    cluster_end = results[0].end
    for r in results[1:]:
        if r.start < cluster_end:
            clusters[-1].append(r)
            cluster_end = max(cluster_end, r.end)
        else:
            clusters.append([r])
            cluster_end = r.end

    resolved = []
    for cluster in clusters:
        start = min(r.start for r in cluster)
        end = max(r.end for r in cluster)
        best = max(cluster, key=lambda r: (r.start == start and r.end == end, r.score, r.end - r.start))
        best.start, best.end = start, end
        resolved.append(best)
    return resolved
