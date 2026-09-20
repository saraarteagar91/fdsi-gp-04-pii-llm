"""
Módulo de detección y anonimización de PII (Sprint 2).

- engine.py       -> AnalyzerEngine de Presidio + spaCy en español,
                      con reconocedores custom para cédula/teléfono CO.
- recognizers.py  -> PatternRecognizers custom (cédula, teléfono).
- anonymizer.py   -> anonymize()/reidentify(): reemplaza PII por tokens
                      y permite revertir el reemplazo solo para el
                      usuario legítimo.
- reid_store.py   -> guarda el mapping token->PII cifrado (Fernet) y
                      separado del log de conversación.
"""
