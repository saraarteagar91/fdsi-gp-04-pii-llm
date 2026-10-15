"""
Entrena el modelo guardián: un NER de spaCy (red neuronal con capa
tok2vec + parser de transiciones) que etiqueta NOMBRE, CEDULA, TELEFONO,
CORREO y DIRECCION en español colombiano.

Se entrena desde cero (spacy.blank("es")) SOLO con datos sintéticos de
synth.py, sin datos reales de usuarios y sin reentrenarse nunca con lo
que la gente escribe en el chat: el modelo aprende formatos, no personas.
"""
import json
import random
import time
from pathlib import Path

import spacy
from spacy.training import Example
from spacy.util import compounding, minibatch

from guardian.training.synth import LABELS, generate

DEFAULT_OUTPUT = Path("models/guardian_ner")


def _to_example(nlp, text: str, ents: list[tuple[int, int, str]]) -> Example | None:
    doc = nlp.make_doc(text)
    spans = []
    for start, end, label in ents:
        span = doc.char_span(start, end, label=label, alignment_mode="expand")
        if span is None:
            return None
        spans.append(span)
    # descartar ejemplos con spans solapados tras la alineación
    spans = sorted(spans, key=lambda s: s.start)
    for a, b in zip(spans, spans[1:]):
        if b.start < a.end:
            return None
    ref = nlp.make_doc(text)
    ref.ents = [ref.char_span(s.start_char, s.end_char, label=s.label_) for s in spans]
    return Example(doc, ref)


def train(output_dir: Path = DEFAULT_OUTPUT, n_train: int = 6000, n_dev: int = 1000, epochs: int = 14, verbose: bool = True) -> dict:
    random.seed(0)
    spacy.util.fix_random_seed(0)
    nlp = spacy.blank("es")
    ner = nlp.add_pipe("ner")
    for label in LABELS:
        ner.add_label(label)

    train_data = [ex for t, e in generate(n_train, seed=13) if (ex := _to_example(nlp, t, e))]
    dev_data = [ex for t, e in generate(n_dev, seed=99) if (ex := _to_example(nlp, t, e))]

    start = time.perf_counter()
    optimizer = nlp.initialize(lambda: train_data)
    best_f, best_scores, history = -1.0, {}, []
    for epoch in range(1, epochs + 1):
        random.shuffle(train_data)
        losses: dict = {}
        for batch in minibatch(train_data, size=compounding(8.0, 64.0, 1.5)):
            nlp.update(batch, sgd=optimizer, drop=0.25, losses=losses)
        scores = nlp.evaluate(dev_data)
        history.append({"epoca": epoch, "perdida": round(float(losses.get("ner", 0.0)), 2), "f1_dev": round(float(scores["ents_f"]), 4)})
        if verbose:
            print(f"época {epoch:2d}  pérdida {losses.get('ner', 0):9.2f}  P {scores['ents_p']:.3f}  R {scores['ents_r']:.3f}  F1 {scores['ents_f']:.3f}")
        if scores["ents_f"] > best_f:
            best_f, best_scores = scores["ents_f"], scores
            output_dir.mkdir(parents=True, exist_ok=True)
            nlp.to_disk(output_dir)

    report = {
        "modelo": "spaCy NER (tok2vec + transition-based parser), entrenado desde cero",
        "datos": "100 % sintéticos (guardian/training/synth.py); ninguno de los conjuntos de evaluación",
        "ejemplos_entrenamiento": len(train_data),
        "ejemplos_validacion": len(dev_data),
        "epocas": epochs,
        "segundos_entrenamiento": round(time.perf_counter() - start, 1),
        "dev_precision": round(float(best_scores["ents_p"]), 4),
        "dev_recall": round(float(best_scores["ents_r"]), 4),
        "dev_f1": round(float(best_scores["ents_f"]), 4),
        "dev_por_etiqueta": {k: {m: round(float(v), 4) for m, v in d.items()} for k, d in best_scores["ents_per_type"].items()},
        "historial": history,
    }
    (output_dir.parent / "guardian_training_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if verbose:
        print(f"Mejor F1 en validación sintética: {best_f:.3f}. Modelo guardado en {output_dir}")
    return report
