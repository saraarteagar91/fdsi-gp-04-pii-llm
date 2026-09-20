"""
Script de evaluación Unsecure vs Secure — cubre T04, T05 y las 5 métricas
de la sección 7 de la propuesta del Hito 1.

Uso:
    python -m scripts.evaluate

Genera:
    data/evaluation_results.csv    (detalle por caso de prueba)
    data/evaluation_summary.json   (las 5 métricas agregadas)
    data/evaluation_metrics.png    (gráfica de barras vs. umbral esperado)

Nota de alcance (ver docs/SPRINT_PLAN.md, "plan de contingencia"):
- La entidad DIRECCION del dataset NO está cubierta todavía por el
  reconocedor (Sprint 2 se enfocó en NOMBRE, CEDULA, TELEFONO, CORREO,
  que son los 4 tipos con más peso en las pruebas T01-T03). Se reporta
  por separado para ser honestos sobre esta limitación.
- La métrica de "utilidad / similitud semántica" usa un proxy de
  similitud textual (difflib) en vez de embeddings, porque el LLM en
  este entorno de demostración es un mock que hace eco del mensaje; con
  un LLM real, basta con reemplazar `_similarity()` por embeddings
  (p. ej. sentence-transformers) sin tocar el resto del script.
"""
import csv
import difflib
import json
import re
import statistics
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

DATA_DIR = Path("data")
DATASET_PATH = DATA_DIR / "pii_test_cases.csv"

FRIENDLY_TO_COLUMN = {
    "PERSON": "NOMBRE",
    "EMAIL_ADDRESS": "CORREO",
    "CEDULA_CO": "CEDULA",
    "TELEFONO_CO": "TELEFONO",
}
IMPLEMENTED_ENTITY_TYPES = {"NOMBRE", "CEDULA", "TELEFONO", "CORREO"}


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def load_dataset() -> list[dict]:
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def evaluate() -> None:
    client = TestClient(app)
    rows = load_dataset()

    per_case_results = []
    vp = fn = 0  # para recall (solo entidades implementadas)
    direccion_misses = 0
    fp_detections = 0
    control_cases = 0
    residual_leaks = 0
    unsecure_latencies = []
    secure_latencies = []
    similarities = []

    for row in rows:
        message = row["message"]
        entity_type = row["entity_type"]
        entity_value = row["entity_value"]

        unsecure_resp = client.post(
            "/unsecure/chat", json={"user_id": "eval", "message": message}
        ).json()
        secure_resp = client.post(
            "/secure/chat", json={"user_id": "eval", "message": message}
        ).json()

        unsecure_latencies.append(unsecure_resp["latency_ms"])
        secure_latencies.append(secure_resp["latency_ms"])

        detected_friendly = {
            FRIENDLY_TO_COLUMN.get(e, e) for e in secure_resp["entities_detected"]
        }

        case_result = {
            "id": row["id"],
            "entity_type": entity_type,
            "format_variant": row["format_variant"],
            "detected_entities": ";".join(sorted(detected_friendly)),
            "hit": None,
        }

        if entity_type == "NINGUNO":
            control_cases += 1
            fp_detections += len(detected_friendly)
            case_result["hit"] = len(detected_friendly) == 0
        elif entity_type == "DIRECCION":
            direccion_misses += 1
            case_result["hit"] = False
            case_result["note"] = "DIRECCION no implementada en Sprint 2"
        elif entity_type == "MULTIPLE":
            # Varias entidades en un solo mensaje (caso 25 del dataset):
            # cada una cuenta por separado para el recall. Verificamos
            # contra la respuesta REIDENTIFICADA (que sí trae los valores
            # reales de vuelta para el usuario legítimo).
            reidentified_norm = _normalize(secure_resp["response"])
            for exp_val in entity_value.split(";"):
                if _normalize(exp_val) in reidentified_norm:
                    vp += 1
                else:
                    fn += 1
            case_result["hit"] = "parcial"
        else:
            exp_norm = _normalize(entity_value)
            reidentified_norm = _normalize(secure_resp["response"])
            hit = entity_type in detected_friendly and exp_norm in reidentified_norm
            if hit:
                vp += 1
            else:
                fn += 1
            case_result["hit"] = hit

        per_case_results.append(case_result)

        # Utilidad: comparar la respuesta final Unsecure vs Secure para el
        # mismo mensaje (con el mock, deberían ser casi idénticas una vez
        # reidentificadas -> similitud alta = utilidad preservada).
        similarities.append(_similarity(unsecure_resp["response"], secure_resp["response"]))

    # --- Fuga residual real: leer el log Secure y confirmar 0 coincidencias ---
    from app.logging_config import read_all_secure_logs

    secure_logs = read_all_secure_logs()
    all_expected_values = [
        v for row in rows for v in row["entity_value"].split(";") if v and row["entity_type"] not in ("NINGUNO", "DIRECCION")
    ]
    anonymized_texts_norm = _normalize(
        " ".join(rec["anonymized_message"] for rec in secure_logs)
    )
    for exp_val in all_expected_values:
        if _normalize(exp_val) in anonymized_texts_norm:
            residual_leaks += 1

    # --- Métricas agregadas ---
    recall = vp / (vp + fn) if (vp + fn) else None
    fp_rate = fp_detections / control_cases if control_cases else None
    avg_latency_added = (
        statistics.mean(secure_latencies) - statistics.mean(unsecure_latencies)
        if secure_latencies and unsecure_latencies
        else None
    )
    avg_similarity = statistics.mean(similarities) if similarities else None

    summary = {
        "recall_deteccion_pii": recall,
        "recall_umbral_esperado": 0.90,
        "tasa_falsos_positivos": fp_rate,
        "fp_umbral_esperado": 0.10,
        "fuga_residual_hacia_llm": residual_leaks,
        "fuga_residual_umbral_esperado": 0,
        "latencia_anadida_ms": avg_latency_added,
        "latencia_umbral_esperado_ms": 500,
        "similitud_semantica_promedio": avg_similarity,
        "similitud_umbral_esperado": 0.80,
        "casos_direccion_no_implementados": direccion_misses,
        "nota_metodologica": (
            "similitud_semantica_promedio usa un proxy de similitud textual "
            "(difflib) porque el LLM de este entorno de demostración es un "
            "mock; con un LLM/API real, reemplazar por embeddings "
            "(sentence-transformers) para una medición más rigurosa."
        ),
    }

    DATA_DIR.mkdir(exist_ok=True)
    with open(DATA_DIR / "evaluation_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    with open(DATA_DIR / "evaluation_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["id", "entity_type", "format_variant", "detected_entities", "hit", "note"]
        )
        writer.writeheader()
        for r in per_case_results:
            writer.writerow({**{"note": ""}, **r})

    _plot_summary(summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("\nArchivos generados: data/evaluation_results.csv, "
          "data/evaluation_summary.json, data/evaluation_metrics.png")


def _plot_summary(summary: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    metrics = [
        ("Recall detección\nPII", summary["recall_deteccion_pii"], summary["recall_umbral_esperado"], "≥"),
        ("Tasa de falsos\npositivos", summary["tasa_falsos_positivos"], summary["fp_umbral_esperado"], "≤"),
        ("Similitud\nsemántica", summary["similitud_semantica_promedio"], summary["similitud_umbral_esperado"], "≥"),
    ]

    labels = [m[0] for m in metrics]
    values = [m[1] or 0 for m in metrics]
    thresholds = [m[2] for m in metrics]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = range(len(labels))
    bars = ax.bar(x, values, color="#4C72B0", width=0.5, label="Resultado obtenido")
    ax.scatter(x, thresholds, color="#C44E52", zorder=5, label="Umbral esperado (propuesta)")

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Proporción")
    ax.set_title("FDSI-GP-04 — Secure vs. umbrales de la propuesta (Hito 1)")
    ax.legend(loc="lower right")

    for i, v in enumerate(values):
        ax.text(i, v + 0.02, f"{v:.2f}", ha="center")

    fig.tight_layout()
    fig.savefig(DATA_DIR / "evaluation_metrics.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    evaluate()
