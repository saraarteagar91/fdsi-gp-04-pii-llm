"""
Reconocedores del guardián: el modelo entrenado (TrainedNerRecognizer) y
las reglas de validación para formatos colombianos.

El modelo aprende los formatos a partir de ejemplos sintéticos; las
reglas son una red de seguridad determinística para los formatos que ya
conocemos (sección 8 de la propuesta: "expresiones regulares/reglas de
validación para cédulas, teléfonos y correos en formato colombiano").
Presidio combina ambos y resuelve los solapamientos.
"""
import re
from typing import List, Optional

from presidio_analyzer import EntityRecognizer, Pattern, PatternRecognizer, RecognizerResult

# --- Cédula de ciudadanía colombiana ---
# Acepta: 1.020.304.050 | 1020304050 | 1,020,304,050 | 52-345-678
# con o sin prefijo CC / C.C. / cedula / documento. El prefijo se recorta
# después en engine.py para que el marcador reemplace solo el número.
CEDULA_PATTERNS = [
    Pattern(
        name="cedula_con_prefijo",
        regex=r"(?i)\b(?:c\.?c\.?|c[eé]dula(?:\s+de\s+ciudadan[ií]a)?|documento(?:\s+de\s+identidad)?|identificaci[oó]n|n[uú]mero\s+de\s+(?:documento|identificaci[oó]n))\s*(?:es\s+)?(?:no\.?|n[uú]mero|:)?\s*[\d][\d.,\-\s]{5,15}\d\b",
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
        regex=r"(?<!\d)(?:\+?57[\s\-.]?)?(?:\(?3\d{2}\)?[\s\-.]?)\d{3}[\s\-.]?\d{4}\b",
        score=0.75,
    ),
    Pattern(
        name="fijo_co",
        regex=r"(?<!\d)(?:\+?57[\s\-.]?)?\(?60[1-8]\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b",
        score=0.7,
    ),
]

# --- Dirección colombiana (nomenclatura urbana) ---
# Calle 123 # 45-67 | Cra 7 #10-20 Apto 301, Medellín | Cl 26 Sur 30-15
# Diagonal 45 Sur # 12-34, Int 5, Bogotá D.C. | Av. Boyacá # 64C-23 Sur
_VIA = (
    r"(?:(?:avenida|av\.?)\s+(?:calle|carrera|cra|cl)|calle|cll|cl|carrera|cra|kra|kr|cr|"
    r"avenida|av|ak|ac|diagonal|dg|transversal|tv|trans|autopista|circular|circunvalar)\.?"
)
_NUM_VIA = r"(?:\d{1,3}\s?[a-z]?(?:\s?bis)?(?:\s?[a-z](?![a-z]))?|[a-záéíóúñ]{3,}(?:\s[a-záéíóúñ]{3,})?)"
_CARDINAL = r"(?:\s+(?:sur|norte|este|oeste))?"
_SEP = r"\s*(?:#|no\.?|n°|nº|nro\.?|n[uú]mero)?\s*"
_PLACA = r"\d{1,3}\s?[a-z]?\s?-\s?\d{1,3}"
_COMPLEMENTO = (
    r"(?:\s*,?\s*(?:apto|apartamento|apt|int|interior|casa|torre|bloque|bl|oficina|of|piso|local)\.?\s*[\w-]+)*"
)
_CIUDAD = (
    r"(?:,\s*(?:bogot[aá](?:\s*d\.?\s*c\.?)?|medell[ií]n|cali|barranquilla|cartagena|bucaramanga|"
    r"pereira|manizales|c[uú]cuta|ibagu[eé]|santa\s+marta|villavicencio|pasto|tunja|neiva|armenia))?"
)
DIRECCION_PATTERNS = [
    Pattern(
        name="direccion_co",
        regex=rf"\b{_VIA}\s+{_NUM_VIA}{_CARDINAL}{_SEP}{_PLACA}{_CARDINAL}{_COMPLEMENTO}{_CIUDAD}",
        score=0.7,
    ),
]

# --- Correo ofuscado ("juan(arroba)gmail(punto)com") ---
CORREO_OFUSCADO_PATTERNS = [
    Pattern(
        name="correo_ofuscado",
        regex=(
            # parte local, que puede venir dictada: "luis punto ospina"
            r"\b[\w.+-]+(?:\s+(?:punto|gui[oó]n\s+bajo)\s+[\w-]+)*"
            r"\s*[\(\[]?\s*(?:arroba|at)\s*[\)\]]?\s*[\w-]+"
            r"(?:\s*[\(\[]?\s*(?:punto|dot)\s*[\)\]]?\s*[a-z]{2,})+\b"
        ),
        score=0.8,
    ),
]

# --- Nombre en MAYÚSCULAS SOSTENIDAS ---
# El NER de spaCy falla con frecuencia con nombres escritos completamente
# en mayúsculas ("ANDRES CAMILO VIVAS BAQUERO"), común en formularios. El
# score base (0.3) queda POR DEBAJO del umbral del analizador (0.4): solo
# pasa si hay una palabra de contexto cerca ("soy", "nombre", ...), que le
# suma ~0.35. Así "GRACIAS POR LA ATENCIÓN" no se marca como persona.
NOMBRE_MAYUSCULAS_PATTERNS = [
    Pattern(
        name="nombre_mayusculas_sostenidas",
        regex=r"\b[A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){1,4}\b",
        score=0.3,
    ),
]


def build_nombre_mayusculas_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="PERSON",
        patterns=NOMBRE_MAYUSCULAS_PATTERNS,
        supported_language="es",
        name="NombreMayusculasRecognizer",
        # OJO: Presidio aplica re.IGNORECASE a los patrones por defecto
        # (global_regex_flags), lo que volvería este regex de "MAYÚSCULAS"
        # inútil. Hay que forzar explícitamente que NO sea case-insensitive.
        global_regex_flags=re.DOTALL | re.MULTILINE,
        context=["soy", "nombre", "habla", "llamo", "llama", "sr", "sra", "señor", "señora", "titular"],
    )


def build_cedula_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="CEDULA_CO",
        patterns=CEDULA_PATTERNS,
        supported_language="es",
        name="CedulaCoRecognizer",
        context=["cedula", "cédula", "cc", "documento", "identificación", "identidad"],
    )


def build_telefono_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="TELEFONO_CO",
        patterns=TELEFONO_PATTERNS,
        supported_language="es",
        name="TelefonoCoRecognizer",
        context=["tel", "telefono", "teléfono", "celular", "whatsapp", "llamar", "contactar", "línea", "fijo"],
    )


def build_direccion_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="DIRECCION_CO",
        patterns=DIRECCION_PATTERNS,
        supported_language="es",
        name="DireccionCoRecognizer",
        context=["vivo", "dirección", "direccion", "domicilio", "residencia", "envíen", "envien", "queda", "envío"],
    )


def build_correo_ofuscado_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="EMAIL_ADDRESS",
        patterns=CORREO_OFUSCADO_PATTERNS,
        supported_language="es",
        name="CorreoOfuscadoRecognizer",
    )


class NombrePorContextoRecognizer(EntityRecognizer):
    """Detecta el nombre que sigue a frases como "me llamo", "mi nombre es",
    "Nombre:" o "soy/habla" — incluso en minúsculas ("me llamo laura
    martínez"), donde el NER de spaCy casi nunca acierta.

    Para "soy"/"habla" se exige que la primera palabra empiece en
    mayúscula, para no marcar frases como "soy cliente de ustedes".
    """

    PREFIX_RE = re.compile(
        r"(?i)\b(me\s+llamo|mi\s+nombre\s+es|mi\s+nombre\s*:|nombre\s+completo\s*:?|nombre\s*:|soy|habla)\s+"
    )
    WORD_RE = re.compile(r"[A-Za-zÁÉÍÓÚÑÜáéíóúñü][A-Za-zÁÉÍÓÚÑÜáéíóúñü'.]*")
    CONNECTORS = {"de", "del", "la", "los"}
    STOP = {
        "y", "e", "o", "quiero", "necesito", "para", "con", "mi", "el", "un", "una", "por",
        "que", "me", "le", "les", "les", "tengo", "y,", "es", "cliente", "nuevo", "nueva",
        "usuario", "usuaria", "su", "sus", "a", "al", "en", "favor", "gracias", "hola",
    }

    def __init__(self) -> None:
        super().__init__(
            supported_entities=["PERSON"],
            supported_language="es",
            name="NombrePorContextoRecognizer",
        )

    def load(self) -> None:  # nada que cargar
        pass

    def analyze(self, text: str, entities: List[str], nlp_artifacts=None) -> List[RecognizerResult]:
        results: List[RecognizerResult] = []
        if "PERSON" not in entities:
            return results

        for prefix in self.PREFIX_RE.finditer(text):
            strict = prefix.group(1).lower() in ("soy", "habla")
            pos = prefix.end()
            start = end = None
            words = 0
            while words < 5:
                m = self.WORD_RE.match(text, pos)
                if not m:
                    break
                word = m.group(0)
                lw = word.lower()
                if lw in self.CONNECTORS and words > 0:
                    # "María de la Cruz": el conector solo cuenta si le sigue otra palabra del nombre
                    nxt = self.WORD_RE.match(text, self._skip_spaces(text, m.end()))
                    if nxt and nxt.group(0)[0].isupper():
                        pos = self._skip_spaces(text, m.end())
                        continue
                    break
                if lw in self.STOP:
                    break
                if words == 0 and strict and not word[0].isupper():
                    break
                if start is None:
                    start = m.start()
                end = m.end()
                words += 1
                nxt_pos = m.end()
                # una coma, "¿", "?" o fin de texto cierran el nombre
                if nxt_pos >= len(text) or text[nxt_pos] in ",;:¿?!\n":
                    break
                pos = self._skip_spaces(text, nxt_pos)
                if pos == nxt_pos:
                    break
            if start is not None and words >= (2 if strict else 1):
                results.append(
                    RecognizerResult(
                        entity_type="PERSON",
                        start=start,
                        end=end,
                        score=0.6 if strict else 0.7,
                    )
                )
        return results

    @staticmethod
    def _skip_spaces(text: str, pos: int) -> int:
        while pos < len(text) and text[pos] == " ":
            pos += 1
        return pos


def build_email_recognizer() -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity="EMAIL_ADDRESS",
        patterns=[Pattern(name="correo", regex=r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\b", score=0.9)],
        supported_language="es",
        name="CorreoRecognizer",
    )


class TrainedNerRecognizer(EntityRecognizer):
    """El modelo guardián entrenado por el equipo (spaCy NER, datos
    sintéticos) envuelto como reconocedor de Presidio."""

    LABEL_MAP = {
        "NOMBRE": "PERSON",
        "CEDULA": "CEDULA_CO",
        "TELEFONO": "TELEFONO_CO",
        "CORREO": "EMAIL_ADDRESS",
        "DIRECCION": "DIRECCION_CO",
    }

    def __init__(self, model_path: str) -> None:
        self.model_path = model_path
        super().__init__(
            supported_entities=list(self.LABEL_MAP.values()),
            supported_language="es",
            name="GuardianNerModel",
        )

    def load(self) -> None:
        import spacy

        self.nlp = spacy.load(self.model_path)

    def analyze(self, text: str, entities: List[str], nlp_artifacts=None) -> List[RecognizerResult]:
        results = []
        for ent in self.nlp(text).ents:
            entity_type = self.LABEL_MAP.get(ent.label_)
            if entity_type in entities:
                results.append(RecognizerResult(entity_type=entity_type, start=ent.start_char, end=ent.end_char, score=0.85))
        return results
