"""
Reconocedores custom por regex/checksum para PII en formato colombiano.

spaCy + el NER de Presidio cubren bien NOMBRE (PERSON) y, parcialmente,
CORREO. Pero cédula y teléfono colombianos tienen formatos muy variados
(con puntos, comas, guiones, con o sin indicativo) que un modelo de NER
genérico no reconoce de forma confiable — para eso sirven estos
reconocedores basados en patrones, tal como describe la sección 8 de la
propuesta ("expresiones regulares/reglas de validación (checksum) para
cédulas, teléfonos y correos en formato colombiano").
"""
import re

from presidio_analyzer import Pattern, PatternRecognizer

# --- Cédula de ciudadanía colombiana ---
# Acepta: 1.020.304.050 | 1020304050 | 1,020,304,050 | 52-345-678
# con o sin prefijo CC / C.C. / cedula / documento.
CEDULA_PATTERNS = [
    Pattern(
        name="cedula_con_prefijo",
        regex=r"(?i)\b(?:c\.?c\.?|c[eé]dula|documento(?:\s+de\s+identidad)?)\s*(?:no\.?|n[uú]mero|:)?\s*[\d][\d.,\-\s]{5,15}\d\b",
        score=0.85,
    ),
    Pattern(
        name="cedula_sin_prefijo_formateada",
        # solo con separadores (puntos, comas o guiones) para no atrapar
        # cualquier número suelto de 6-10 dígitos sin contexto.
        regex=r"\b\d{1,3}[.,\-]\d{3}[.,\-]\d{3}(?:[.,\-]\d{3})?\b",
        score=0.6,
    ),
]

# --- Teléfono colombiano ---
# Celular: 3XXXXXXXXX (10 dígitos, empieza en 3). Fijo con indicativo de
# área: 60X XXX XXXX. Acepta +57, paréntesis, espacios, puntos y guiones.
TELEFONO_PATTERNS = [
    Pattern(
        name="celular_co",
        regex=r"(?:\+?57[\s\-.]?)?(?:\(?3\d{2}\)?[\s\-.]?)\d{3}[\s\-.]?\d{4}\b",
        score=0.75,
    ),
    Pattern(
        name="fijo_co",
        regex=r"(?:\+?57[\s\-.]?)?\(?60[1-8]\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b",
        score=0.7,
    ),
]


# --- Nombre en MAYÚSCULAS SOSTENIDAS ---
# El NER de spaCy (entrenado sobre todo con texto en minúsculas/capitalizado
# normal) falla con frecuencia al reconocer nombres escritos completamente
# en mayúsculas (p. ej. "ANDRES CAMILO VIVAS BAQUERO"), un formato común en
# formularios y documentos de identidad. Este recognizer complementa al NER
# para ese caso específico.
NOMBRE_MAYUSCULAS_PATTERNS = [
    Pattern(
        name="nombre_mayusculas_sostenidas",
        regex=r"\b[A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){1,4}\b",
        score=0.5,
    ),
]


def build_nombre_mayusculas_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="PERSON",
        patterns=NOMBRE_MAYUSCULAS_PATTERNS,
        supported_language="es",
        # OJO: Presidio aplica re.IGNORECASE a los patrones por defecto
        # (global_regex_flags), lo que volvería este regex de "MAYÚSCULAS"
        # inútil (matchearía cualquier texto en minúsculas también). Hay
        # que forzar explícitamente que NO sea case-insensitive.
        global_regex_flags=re.DOTALL | re.MULTILINE,
        # el contexto sube bastante el score (ver context_similarity_factor
        # de Presidio), así que un score base moderado + contexto cercano
        # de "soy/nombre/habla/llamo" evita marcar cualquier sigla en
        # mayúsculas como si fuera una persona.
        context=["soy", "nombre", "habla", "llamo", "llama", "sr", "sra"],
    )


def build_cedula_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="CEDULA_CO",
        patterns=CEDULA_PATTERNS,
        supported_language="es",
        context=["cedula", "cédula", "cc", "documento", "identificación", "identidad"],
    )


def build_telefono_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="TELEFONO_CO",
        patterns=TELEFONO_PATTERNS,
        supported_language="es",
        context=["tel", "telefono", "teléfono", "celular", "whatsapp", "llamar", "contactar", "línea", "fijo"],
    )
