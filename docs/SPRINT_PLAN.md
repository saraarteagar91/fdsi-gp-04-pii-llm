# Plan de trabajo — FDSI-GP-04 (2 sprints)

## Contexto
- Hito 1 (Propuesta Estructurada) ya fue avalado — checklist de aprobación del 05/09 completo.
- Alcance declarado en la propuesta: "realizable antes del 26/09/2026".
- Objetivo de estos dos sprints: llegar a **algo funcional de punta a punta**, aunque no se alcancen a pulir todos los criterios de evaluación. Es preferible tener Unsecure + Secure corriendo con 2-3 pruebas sólidas, que tener 5 pruebas a medio hacer.

## Sprint 1 — Infraestructura + flujo Unsecure (línea base)
**Objetivo:** tener el escenario "Unsecure" de la propuesta corriendo de punta a punta: mensaje del usuario → LLM sin ninguna transformación → log en texto plano. Este escenario es la línea base contra la que se compara todo en Sprint 2, así que conviene dejarlo firme primero.

Entregables de este sprint (ya generados en este scaffold):
1. Estructura del proyecto: FastAPI + Docker + `requirements.txt`.
2. Endpoint `POST /unsecure/chat`: recibe el mensaje, lo reenvía tal cual al LLM (o a un mock si no hay API key configurada) y registra la conversación completa —incluyendo el PII— en `logs/unsecure_raw.jsonl`.
3. Dataset `data/pii_test_cases.csv` con 24 casos de PII colombiano en formatos variados (cédulas, teléfonos, correos, nombres, direcciones) — esto sirve para T04 y también como insumo para evaluar el detector en Sprint 2.
4. Pruebas `pytest` que documentan el comportamiento actual de Unsecure (el mensaje llega intacto al "LLM" y el log queda en texto plano) — esto es la evidencia de línea base para T01 y T02.

## Sprint 2 — Módulo Secure (detección + anonimización) y evaluación ✅
**Objetivo:** implementar el módulo de detección/anonimización de PII y comparar Secure vs Unsecure con las pruebas y métricas de la propuesta.

Completado:
1. ✅ Presidio (Analyzer + Anonymizer) con spaCy en español (`es_core_news_md`) + reconocedores custom por regex para cédula y teléfono colombianos, más un reconocedor extra para nombres en MAYÚSCULAS SOSTENIDAS (el NER de spaCy los pasaba por alto — ver `app/pii/recognizers.py`).
2. ✅ Endpoint `POST /secure/chat`: anonimiza antes de llamar al LLM, guarda solo la versión anonimizada en `logs/secure_anon.jsonl`, guarda el mapeo token→PII cifrado (Fernet) y aparte en `data/secure_mapping.enc.jsonl`, y reidentifica la respuesta SOLO para el usuario legítimo antes de devolverla (nunca en el log ni en lo enviado al LLM).
3. ✅ T01, T02, T03 automatizados en `tests/test_secure_flow.py` (9/9 pruebas pasan, incluyendo las 4 de Sprint 1).
4. ✅ T04 y T05 + las 5 métricas de la propuesta en `scripts/evaluate.py`, con gráfica (`data/evaluation_metrics.png`).
5. ⬜ Redactar el reporte narrativo del Hito 2 (este documento + el README ya traen los resultados numéricos; falta el documento de entrega formal si el formato del seminario lo pide aparte).

### Resultados obtenidos (ver README para la tabla completa)
Recall 1.00, falsos positivos 0.00, fuga residual 0, latencia añadida ~41ms — los 4 dentro del umbral de la propuesta. La "similitud semántica" (1.00) es un proxy textual porque se corrió con el LLM mock; queda documentado como limitación a resolver si se prueba con un LLM real.

### Limitaciones que quedaron pendientes (ver README, sección "Limitaciones conocidas")
- Direcciones (DIRECCION) no se detectan todavía — 3 casos del dataset (T19-T21) quedan como falla conocida, no oculta.
- La métrica de utilidad/similitud semántica necesita reemplazarse por embeddings reales si se usa un LLM de verdad en vez del mock.

## Si el tiempo aprieta (plan de contingencia)
Prioriza en este orden:
1. Unsecure funcional (Sprint 1) — ✅ cubierto.
2. Detección PII con Presidio + reglas propias — ✅ cubierto (recall 1.00 en el dataset de prueba).
3. Al menos T01, T02 y T04 con las métricas de recall y fuga residual — ✅ cubierto, junto con T03 y T05.
4. Si aún falta tiempo: implementar DIRECCION y cambiar el proxy de similitud semántica por embeddings reales — quedan como siguientes pasos, no bloquean la sustentación.

## Reparto sugerido entre los 3 integrantes (para pulir antes de sustentar)
- Persona A: reconocedor de DIRECCION (patrón Calle/Cra/Diagonal + número, siguiendo el esquema de `recognizers.py`) y revisar más formatos de cédula/teléfono.
- Persona B: reemplazar el proxy de similitud semántica por `sentence-transformers` en `scripts/evaluate.py`, y probar el flujo completo con un LLM real (`LLM_PROVIDER=anthropic`).
- Persona C: preparar la sustentación — correr `scripts/evaluate.py`, revisar `data/evaluation_results.csv` caso por caso, y armar la narrativa problema → prueba → control → métrica con los resultados reales.
