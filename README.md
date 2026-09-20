# FDSI-GP-04 — Protección de datos personales enviados a un LLM

Proyecto del Seminario Aplicado de Ciberseguridad en IA (2026-2). Compara
dos formas de manejar los mensajes de un usuario antes de mandarlos a un
LLM, tal como describe la propuesta del Hito 1:

- **Unsecure**: el mensaje se envía tal cual, sin ningún filtro, y se
  guarda completo en un log.
- **Secure**: antes de enviar el mensaje, un módulo detecta los datos
  personales (nombre, cédula, teléfono, correo) y los reemplaza por
  marcadores (por ejemplo `[NOMBRE_1]`). Así, ni el LLM ni el log ven el
  dato real. Al usuario sí se le devuelve su respuesta completa.

El plan de trabajo completo (qué se hizo en cada sprint) está en
[`docs/SPRINT_PLAN.md`](docs/SPRINT_PLAN.md).

## Estado del proyecto

- **Sprint 1 (listo):** el flujo Unsecure funcionando, con su log y sus pruebas.
- **Sprint 2 (listo):** el flujo Secure funcionando (detección + anonimización + devolución de la respuesta real solo al usuario), con pruebas y una evaluación con métricas.

### Resultados de la evaluación

Se probó con 28 mensajes de ejemplo (`data/pii_test_cases.csv`), comparando lo que pide la propuesta contra lo que obtuvimos:

| Métrica | Qué mide | Resultado | Lo que pedía la propuesta |
|---|---|---|---|
| Recall de detección | Cuántos datos personales detecta correctamente | 1.00 | ≥ 0.90 |
| Falsos positivos | Cuánto texto normal se marca como PII por error | 0.00 | ≤ 0.10 |
| Fuga hacia el LLM | Datos reales que igual llegan al LLM | 0 | 0 |
| Latencia añadida | Cuánto más tarda el flujo Secure vs. el Unsecure | ~41 ms | ≤ 500 ms |
| Utilidad de la respuesta | Qué tan parecida es la respuesta final | 1.00 | ≥ 0.80 |

El detalle de cada caso está en `data/evaluation_results.csv` y la gráfica en `data/evaluation_metrics.png`.

## Cómo correrlo

**Requisito:** Python 3.11 o 3.12 (versiones más nuevas todavía no son compatibles con las librerías de detección de PII).

```bash
python -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download es_core_news_md
cp .env.example .env             # en Windows: copy .env.example .env
uvicorn app.main:app --reload
```

Con eso arriba, entra a `http://127.0.0.1:8000/docs` para probar los dos endpoints: `POST /unsecure/chat` y `POST /secure/chat`. Manda el mismo mensaje a los dos y compara la respuesta.

Después revisa los logs:
- `logs/unsecure_raw.jsonl` → el dato personal completo, sin filtrar.
- `logs/secure_anon.jsonl` → solo los marcadores, nunca el dato real.

### Correr las pruebas automatizadas

```bash
pytest -v
```

### Correr la evaluación completa (genera la tabla y la gráfica de arriba)

```bash
python -m scripts.evaluate
```

### Probar solo Unsecure, sin instalar nada de detección de PII

Si solo quieres levantar el flujo Unsecure (por ejemplo, para probar rápido sin instalar spaCy), usa en su lugar `pip install -r requirements-sprint1.txt`. El servidor detecta automáticamente que falta el módulo de detección y solo activa `/unsecure/chat`.

### Usar un LLM real (opcional)

Por defecto el proyecto usa un LLM simulado (`LLM_PROVIDER=mock` en el `.env`), así que todo corre sin gastar ninguna API key. Para probar con un modelo real, cambia en `.env`:
```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=tu-clave
```

## Qué falta / limitaciones que sabemos que tiene

- **No detectamos direcciones todavía.** Solo nombres, cédulas, teléfonos y correos. El dataset de prueba trae 3 casos de direcciones que hoy no se detectan; quedó pendiente para una siguiente entrega.
- **La métrica de "utilidad" es una aproximación**, no la medición exacta que describe la propuesta, porque se probó con el LLM simulado en vez de uno real. Si se corre con un LLM real, este número puede cambiar.

## Estructura del proyecto

```
app/
  main.py           # La aplicación (API)
  routers/
    unsecure.py       # Endpoint /unsecure/chat
    secure.py         # Endpoint /secure/chat
  pii/                # Módulo de detección y anonimización de datos personales
scripts/
  evaluate.py         # Corre la evaluación y genera la tabla/gráfica de resultados
data/
  pii_test_cases.csv  # Mensajes de prueba con datos personales
tests/                # Pruebas automatizadas
docs/
  SPRINT_PLAN.md      # Plan de trabajo detallado
```
