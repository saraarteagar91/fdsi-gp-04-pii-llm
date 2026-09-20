# FDSI-GP-04 — Protección de datos personales enviados a un LLM

Proyecto del Seminario Aplicado de Ciberseguridad en IA (2026-2). Implementa
los dos escenarios comparativos descritos en la propuesta del Hito 1:
**Unsecure** (línea base, sin filtro) y **Secure** (con detección y
anonimización de PII antes de llegar al LLM, más reidentificación
controlada para el usuario legítimo).

Este repo se organizó en **2 sprints**. El detalle completo del plan,
prioridades, reparto entre el equipo y plan de contingencia está en
[`docs/SPRINT_PLAN.md`](docs/SPRINT_PLAN.md).

## Estado actual

- ✅ **Sprint 1:** infraestructura del proyecto + flujo Unsecure funcionando
  de punta a punta, con logging en texto plano, dataset de prueba con PII
  y pruebas automatizadas.
- ✅ **Sprint 2:** módulo Secure (Presidio + spaCy + reconocedores custom
  para cédula/teléfono/nombres en mayúsculas colombianos), endpoint
  `/secure/chat` con reidentificación controlada, pruebas T01-T03
  automatizadas, y script de evaluación para T04/T05 y las 5 métricas.

### Resultados de la evaluación (`scripts/evaluate.py`)

Sobre los 28 casos de `data/pii_test_cases.csv`:

| Métrica | Resultado | Umbral propuesta |
|---|---|---|
| Recall de detección de PII | 1.00 | ≥ 0.90 |
| Tasa de falsos positivos | 0.00 | ≤ 0.10 |
| Fuga residual hacia el LLM | 0 entidades | 0 |
| Latencia añadida | ~41 ms | ≤ 500 ms |
| Similitud semántica (proxy)* | 1.00 | ≥ 0.80 |

\* Con el LLM mock (sin costo) usado por defecto. Ver "Limitaciones
conocidas" más abajo — es lo primero que hay que revisar si prueban con
un LLM real.

## Cómo correrlo

### Opción A: local, solo Unsecure (sin Docker, funciona en cualquier Python)

```bash
pip install -r requirements-sprint1.txt
cp .env.example .env          # déjalo con LLM_PROVIDER=mock para probar sin API key
uvicorn app.main:app --reload
```

Abre `http://localhost:8000/docs`. Con solo esto, `/secure/chat` no
aparece (el servidor detecta que faltan Presidio/spaCy y sigue
funcionando solo con `/unsecure/chat` — ver `GET /health`).

### Opción B: local, Unsecure + Secure completo

**Requiere Python 3.11 o 3.12** (spaCy/Presidio/sentence-transformers no
tienen todavía binarios listos para versiones muy nuevas como 3.14 — ver
"Troubleshooting" más abajo si su Python es más reciente).

```bash
python3.12 -m venv .venv          # o python3.11
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download es_core_news_md
cp .env.example .env
uvicorn app.main:app --reload
```

Ahora `http://localhost:8000/docs` muestra ambos endpoints:
`/unsecure/chat` y `/secure/chat`. Pruébenlos con el mismo mensaje y
comparen:

```bash
curl -X POST http://localhost:8000/unsecure/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u1", "message": "Mi nombre es Juan Pérez, cédula 1020304050"}'

curl -X POST http://localhost:8000/secure/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u1", "message": "Mi nombre es Juan Pérez, cédula 1020304050"}'
```

Después revisen:
- `logs/unsecure_raw.jsonl` → el PII completo, en texto plano.
- `logs/secure_anon.jsonl` → solo la versión anonimizada (`[NOMBRE_1]`, `[CEDULA_1]`...).
- `data/secure_mapping.enc.jsonl` → el mapping token→PII, cifrado, en un archivo aparte.

Aun así, la respuesta que reciben del endpoint `/secure/chat` sí trae el
dato real de vuelta (reidentificación controlada solo para el usuario
legítimo) — la respuesta es útil, el log y el LLM nunca vieron el dato.

### Opción C: Docker

```bash
cp .env.example .env
docker compose up --build
```

(La imagen usa `requirements.txt` completo — Docker resuelve el problema
de versión de Python porque usa Python 3.11 dentro del contenedor.)

### Correr las pruebas

```bash
pytest -v
```

`tests/test_unsecure_flow.py` cubre T01/T02 sobre Unsecure.
`tests/test_secure_flow.py` cubre T01/T02/T03 sobre Secure y se salta
automáticamente (`skip`, no falla) si Presidio/spaCy no están instalados.

### Correr la evaluación completa (T04, T05, 5 métricas)

Requiere el entorno completo (Opción B):

```bash
python -m scripts.evaluate
```

Genera:
- `data/evaluation_results.csv` — detalle caso por caso.
- `data/evaluation_summary.json` — las 5 métricas agregadas.
- `data/evaluation_metrics.png` — gráfica de barras vs. umbral esperado.

## Troubleshooting: "Failed to build spacy/thinc/blis" (o pydantic-core) en Python 3.14+

Esto pasa porque **spaCy/Presidio (y a veces pydantic-core) todavía no
publican wheels precompilados para versiones de Python muy nuevas**. Al no
encontrar un wheel, pip intenta compilar desde código fuente y eso falla.

Para el Sprint 1 esto no bloquea nada: usa `requirements-sprint1.txt`, que
no tiene versiones fijas exactas (dejamos rangos `>=` para que pip elija
automáticamente una versión con binario ya publicado).

Para el Sprint 2, la solución es usar Python 3.11 o 3.12 (con soporte
maduro en todo el ecosistema científico) en un entorno virtual aparte:

```bash
# con Homebrew, sin tocar la versión de Python que ya tengas instalada
brew install python@3.12
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download es_core_news_md
```

Si no tienes Homebrew, instala Python 3.12 desde python.org y usa
`python3.12` (o la ruta completa al ejecutable) al crear el venv.

## Usar un LLM real (opcional)

Por defecto `LLM_PROVIDER=mock` en `.env.example`, así que todo el flujo
—incluyendo pruebas, demo y evaluación— corre sin necesitar una API key ni
gastar créditos. Si quieren probar contra un modelo real:

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

(o `LLM_PROVIDER=openai` con `OPENAI_API_KEY`). Úsenlo solo en un ambiente
propio de prueba, nunca con datos reales de usuarios, tal como se aclara en
la propuesta.

## Limitaciones conocidas (léanlas antes del Hito 2)

- **DIRECCION no está implementada.** El dataset trae 3 casos de
  direcciones (T19-T21) que hoy no se detectan — no había un reconocedor
  confiable de direcciones colombianas listo a tiempo. `scripts/evaluate.py`
  los reporta aparte (`casos_direccion_no_implementados`) en vez de
  ocultarlos. Si hay tiempo, un reconocedor por patrón (Calle/Cra/Diagonal
  + números) siguiendo el mismo esquema de `recognizers.py` lo resolvería.
- **La "similitud semántica" es un proxy, no la métrica real.** Con el LLM
  mock (que solo hace eco del mensaje) no tiene sentido pagar por
  embeddings — así que `scripts/evaluate.py` usa similitud de texto
  (`difflib`) entre la respuesta Unsecure y Secure. Es honesto, pero **no
  es lo que describe la sección 7 de la propuesta**. Si prueban con un
  LLM real (`LLM_PROVIDER=anthropic`), reemplacen `_similarity()` en
  `scripts/evaluate.py` por embeddings de `sentence-transformers` — el
  resto del script no cambia.
- **El NER de spaCy falla con nombres en MAYÚSCULAS SOSTENIDAS** si no
  hay un reconocedor de patrón que lo complemente — ya lo agregamos
  (`build_nombre_mayusculas_recognizer` en `recognizers.py`), pero es un
  buen ejemplo para explicar en la sustentación por qué el enfoque
  híbrido (NER + reglas) del diseño de la propuesta es necesario.
- Presidio aplica `re.IGNORECASE` a los patrones por defecto — si agregan
  un reconocedor nuevo que dependa de mayúsculas/minúsculas, hay que
  pasar `global_regex_flags` explícitamente (ver el comentario en
  `recognizers.py`) o el patrón termina matcheando cualquier texto.

## Estructura

```
app/
  main.py                    # FastAPI app (registra /secure solo si Presidio/spaCy están instalados)
  config.py                  # Settings (env vars)
  logging_config.py          # Logs JSON: unsecure_raw.jsonl y secure_anon.jsonl
  llm_client.py              # Wrapper del LLM (anthropic/openai/mock)
  routers/
    unsecure.py               # POST /unsecure/chat
    secure.py                 # POST /secure/chat
  pii/
    engine.py                 # AnalyzerEngine de Presidio + spaCy (es)
    recognizers.py             # Reconocedores custom: cédula, teléfono, nombre en mayúsculas
    anonymizer.py              # anonymize()/reidentify()
    reid_store.py              # Mapping token->PII cifrado (Fernet), separado del log
scripts/
  evaluate.py                 # T04, T05 y las 5 métricas + gráfica
data/
  pii_test_cases.csv          # 28 casos de PII en formatos colombianos variados (T04)
  evaluation_*.{csv,json,png} # Se generan al correr scripts/evaluate.py
tests/
  test_unsecure_flow.py
  test_secure_flow.py
docs/
  SPRINT_PLAN.md              # Plan detallado de los 2 sprints
```
