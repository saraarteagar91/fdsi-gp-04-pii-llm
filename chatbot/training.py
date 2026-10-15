"""
Entrenamiento del clasificador de intenciones del asistente Andi.

Modelo: TF-IDF (palabras 1-2 + caracteres 2-5) + Regresión Logística,
entrenado con el corpus data/bot/intents.json. Los ejemplos con llaves
({correo}, {cedula}...) se aumentan dos veces: con datos SINTÉTICOS
(como los vería el modelo en el flujo Unsecure) y con marcadores
([CORREO_1], como los ve en el flujo Secure). Así el asistente entiende
igual de bien un mensaje anonimizado que uno crudo, que es justo lo que
mide el criterio de "utilidad" de la propuesta.
"""
import json
import random
import re
import time
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

from chatbot.config import settings

MODEL_FILENAME = "intent_classifier.joblib"
REPORT_FILENAME = "training_report.json"
CORPUS_PATH = Path(settings.corpus_path)

_TOKEN_RE = re.compile(r"\[(NOMBRE|CEDULA|TELEFONO|CORREO|DIRECCION|DATO_REDACTADO)(?:_\d+)?\]")

# Valores 100 % sintéticos (no corresponden a personas reales).
SYNTHETIC = {
    "nombre": ["Laura Gómez", "Carlos Andrés Ruiz", "MARÍA FERNANDA SOTO", "Pedro Pablo Díaz", "Ana Lucía Torres", "Jorge Iván Mejía"],
    "correo": ["laura.gomez@mail.com", "cruiz88@correo.co", "MFSOTO@EMPRESA.COM.CO", "pedro_diaz@hotmail.com", "ana.t+compras@gmail.com"],
    "cedula": ["1.023.456.789", "52.345.678", "79876543", "1,019,234,567", "80-123-456"],
    "telefono": ["310 555 1234", "3205559876", "+57 315 555 0000", "(301) 555 4321", "601 555 1200"],
    "direccion": ["Calle 80 # 12-34", "Cra 45 #26-10 Apto 502", "Diagonal 12 Sur # 3-21, Bogotá", "Av. Boyacá # 64C-23", "Transversal 5 # 8-12"],
    "pedido": ["AM-10231", "AM-20458", "AM-99812", "AM-50001"],
}
TOKENS = {
    "nombre": ["[NOMBRE_1]", "[NOMBRE_2]"],
    "correo": ["[CORREO_1]", "[CORREO_2]"],
    "cedula": ["[CEDULA_1]"],
    "telefono": ["[TELEFONO_1]", "[TELEFONO_2]"],
    "direccion": ["[DIRECCION_1]"],
    "pedido": ["AM-10231", "AM-77120"],  # el número de pedido no es dato personal
}


def normalize_for_intent(text: str) -> str:
    """Preprocesamiento común: minúsculas y marcadores convertidos en la
    palabra de su tipo ([CORREO_1] -> "correo")."""
    text = _TOKEN_RE.sub(lambda m: f" {m.group(1).lower()} ", text)
    return text.lower()


def _fill(template: str, pool: dict, rng: random.Random) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: rng.choice(pool[m.group(1)]), template)


def load_training_data(corpus_path: Path = CORPUS_PATH, seed: int = 42) -> tuple[list[str], list[str]]:
    rng = random.Random(seed)
    corpus = json.loads(Path(corpus_path).read_text(encoding="utf-8"))
    texts, labels = [], []
    for intent in corpus["intents"]:
        for example in intent["examples"]:
            if "{" in example:
                variants = [_fill(example, SYNTHETIC, rng) for _ in range(2)]
                variants += [_fill(example, TOKENS, rng) for _ in range(2)]
            else:
                variants = [example]
            for v in variants:
                texts.append(v)
                labels.append(intent["tag"])
    return texts, labels


def build_pipeline() -> Pipeline:
    features = FeatureUnion([
        ("palabras", TfidfVectorizer(preprocessor=normalize_for_intent, ngram_range=(1, 2), strip_accents="unicode", sublinear_tf=True)),
        ("caracteres", TfidfVectorizer(preprocessor=normalize_for_intent, analyzer="char_wb", ngram_range=(2, 5), strip_accents="unicode", sublinear_tf=True)),
    ])
    return Pipeline([
        ("features", features),
        ("clf", LogisticRegression(C=12.0, max_iter=3000, class_weight="balanced")),
    ])


def train(model_dir: str | Path | None = None, verbose: bool = True) -> dict:
    """Entrena, evalúa (hold-out 20 % + validación cruzada 5-fold) y
    guarda el modelo final entrenado con todo el corpus."""
    model_dir = Path(model_dir or settings.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    texts, labels = load_training_data()

    start = time.perf_counter()
    x_train, x_test, y_train, y_test = train_test_split(texts, labels, test_size=0.2, random_state=42, stratify=labels)
    holdout_model = build_pipeline().fit(x_train, y_train)
    y_pred = holdout_model.predict(x_test)
    holdout_acc = accuracy_score(y_test, y_pred)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(build_pipeline(), texts, labels, cv=cv)

    final_model = build_pipeline().fit(texts, labels)
    joblib.dump(final_model, model_dir / MODEL_FILENAME)

    report = {
        "modelo": "TF-IDF (palabras 1-2 + caracteres 2-5) + LogisticRegression",
        "ejemplos_entrenamiento": len(texts),
        "intenciones": sorted(set(labels)),
        "exactitud_holdout_20pct": round(holdout_acc, 4),
        "exactitud_validacion_cruzada_5fold": round(float(cv_scores.mean()), 4),
        "desviacion_validacion_cruzada": round(float(cv_scores.std()), 4),
        "segundos_entrenamiento": round(time.perf_counter() - start, 2),
        "reporte_por_intencion": classification_report(y_test, y_pred, output_dict=True, zero_division=0),
    }
    (model_dir / REPORT_FILENAME).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if verbose:
        print(f"Ejemplos: {len(texts)} | intenciones: {len(set(labels))}")
        print(f"Exactitud hold-out: {holdout_acc:.3f} | validación cruzada: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
        print(classification_report(y_test, y_pred, zero_division=0))
        print(f"Modelo guardado en {model_dir / MODEL_FILENAME}")
    return report
