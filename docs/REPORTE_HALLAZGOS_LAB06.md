# Lab. 06 — Hallazgos de seguridad: SAST, SCA, detección de secretos y DAST

**Proyecto:** FDSI-GP-04 — Andes Market (protección de PII en chat con LLM)
**Integrantes:** Johan Sebastián Beltrán, Sara Arteaga, Andrés Camilo Vivas
**Rama:** `security/lab06-hallazgos`, creada desde `security/lab-fsi` (línea base `12b0ead`, Lab. 05)
**Entorno autorizado:** equipo local del grupo. Los cuatro servicios corren con `python -m scripts.run_all` en `http://127.0.0.1:8000`, con datos ficticios y el chatbot `local` (sin llamadas al LLM externo). Las herramientas corren en Docker.
**Fecha:** 2026-11-19
**Evidencias:** `docs/evidencias/lab06/` (archivos `*-antes.*` y `*-despues.*`)

## Resumen ejecutivo

| | Antes | Después |
|---|---|---|
| Hallazgos propios corregidos | — | **7** (F-07 a F-13) |
| Login de admin con la contraseña publicada en el repo (DAST D-01) | **200 OK** | 401 |
| Intentos para adivinar la contraseña actual (D-07) | ilimitados | bloqueo (429) al 6.º |
| pip-audit (venv completo, 82 paquetes) | 21 vulns en 4 paquetes | **0** |
| Trivy imagen base (HIGH/CRITICAL con parche) | 3 | 0 (+1 falso positivo) |
| Trivy config (Dockerfile/compose) | 1 (DS-0026) | 0 |
| ZAP baseline (pasivo) | 5 alertas (0 FAIL) | 3 (0 FAIL) |
| ZAP API scan (activo, OpenAPI) | 6 alertas (0 FAIL) | 5 (0 FAIL, solo informativas/FP) |
| Bandit | 14 (B311 ×4) | 13 (los B311 restantes son FP en datos de entrenamiento) |
| Semgrep (5 rulesets, 291 reglas) | 0 | 0 |
| Pruebas `pytest` | 75/75 | **84/84** (9 de regresión nuevas) |

**Hallazgo más grave: F-07 (alta).** La cuenta de **administrador** tenía una contraseña fija escrita en `data/seed/usuarios_demo.json` y en la documentación, y el **repositorio es público**. Cualquiera que desplegara el proyecto quedaba con un admin de contraseña conocida. Ese admin ve el Centro de seguridad, los logs crudos con PII y el modo inseguro del chat. **Ni Semgrep ni Gitleaks lo detectaron**: lo encontró la revisión manual y lo confirmó el DAST autenticado.

## Metodología

| Fase | Herramienta / técnica | Configuración |
|---|---|---|
| SAST | Semgrep (Docker `semgrep/semgrep`) | `p/owasp-top-ten`, `p/python`, `p/secrets`, `p/javascript`, `p/fastapi` |
| SAST | Bandit 1.x | `-r app chatbot common guardian vault scripts` |
| SAST | **Revisión manual** de los ~3 800 líneas (routers, auth, sesiones, bóveda, guardián, `static/app.js`) | Fuentes → sumideros (`innerHTML`), control de acceso por endpoint, límites de entrada |
| SD | Gitleaks 8 (Docker) | Modo `git` (11 commits, historial completo) y modo `dir` (árbol de trabajo); **regla propia** `.gitleaks.toml` |
| SCA | pip-audit sobre `pip freeze` del `.venv` | `--no-deps --disable-pip` (82 paquetes) |
| SCA | Trivy (Docker) | `image python:3.11-slim` (HIGH/CRITICAL) y `config` (Dockerfile + compose) |
| DAST | OWASP ZAP (Docker) | `zap-baseline.py` (pasivo) y `zap-api-scan.py -f openapi` (activo, contra `/openapi.json`) |
| DAST | **Pruebas autenticadas propias**: `scripts/dast_manual.py` | 11 casos: credenciales, control de acceso, IDOR, fuerza bruta, XSS, límites, cookies |

ZAP no inicia sesión. Por eso el control de acceso y la autenticación se probaron con `dast_manual.py`, que entra como cliente y como admin.

## Hallazgos

### F-07 — Credenciales de administrador fijas y publicadas (SD + DAST) — **ALTA**
- **CWE-798** (Hard-coded Credentials), **CWE-1392** (Default Credentials) · OWASP **A07:2021** Identification and Authentication Failures.
- **Dónde:** `data/seed/usuarios_demo.json` (desde el commit `14be53a`), `docs/INSTALACION_Y_CREDENCIALES.md` y `docs/GUIA_DEMO_EN_VIVO.md`. `app/db.py::_seed` crea el admin con esa contraseña.
- **Cómo se encontró:** revisión manual del seed. **Gitleaks (reglas por defecto) no lo detectó**: solo reportó un falso positivo en `docs/evidencias/pip-audit.json`. Semgrep `p/secrets` tampoco.
- **Explotación confirmada (DAST D-01):** `POST /api/auth/login` con la contraseña publicada → **200** y cookie de sesión de admin.
- **Corrección:**
  - El seed ya no trae contraseña de admin. `scripts/setup_secrets.py` genera `APP_ADMIN_PASSWORD` aleatoria (`secrets.token_urlsafe(18)`) en `secrets/env/app.env`, que está en `.gitignore` y `.dockerignore`. También la agrega en instalaciones viejas.
  - Si la variable está vacía, **no se crea** la cuenta de administrador.
  - `app/db.py::_sync_admin_password` **rota** el hash en bases existentes al arrancar y cierra las sesiones del admin.
  - Se actualizó la documentación.
- **Prevención:** regla propia `credencial-en-datos` en `.gitleaks.toml` (la usa también el job de Gitleaks del CI). Validada sobre el commit original: **sí la detecta** (`gitleaks-regla-propia-commit-14be53a.json`).
- **Validación:**
  - D-01 → **401** contra la base real ya rotada.
  - Pruebas: `test_f07_seed_has_no_admin_password`, `test_f07_published_admin_password_no_longer_works`, `test_f07_admin_password_comes_from_secrets` y `test_f07_existing_database_rotates_old_admin_hash`.
- **Nota:** la contraseña vieja sigue en el historial del repo público. No se reescribe el historial porque ya está **revocada**, que es la acción que importa. Las contraseñas de **clientes** de prueba siguen en el seed como riesgo aceptado: son datos ficticios para la demo local y la regla tiene un allowlist explícito para ellas.

### F-08 — XSS basado en DOM en el panel de auditoría (SAST manual) — **MEDIA**
- **CWE-79** · OWASP **A03:2021** Injection.
- **Dónde:** `static/app.js`, función `step()`. Si el contenido empezaba por `"<div"`, se insertaba con `innerHTML` **sin escapar**. Por ahí pasan el mensaje del usuario, la entrada y la salida del LLM, el log y la respuesta final.
- **Escenario:** el admin abre «Ver auditoría» de una respuesta del LLM que empieza por `<div>` (por ejemplo, inducida con *prompt injection*) y el HTML se pinta. La CSP `script-src 'self'` de F-01 (Lab. 05) **bloquea** los scripts en línea y los `onerror`. Por eso la severidad es media y no alta, pero el HTML inyectado sí podía alterar la página (phishing o UI falsa dentro del panel).
- **Cómo se encontró:** revisión manual de los sumideros `innerHTML`. **Semgrep `p/javascript` no lo marcó**.
- **Corrección:** el HTML de confianza se marca de forma explícita con `trusted()`, usando un `Symbol` que el texto del servidor no puede falsificar. Todo lo demás se escapa siempre con `esc()`.
- **Validación:** `test_f08_audit_panel_does_not_trust_text_that_looks_like_html` y la página revisada en el navegador sin errores de consola.

### F-09 — Fuerza bruta sobre «contraseña actual» en el cambio de contraseña (DAST) — **MEDIA**
- **CWE-307** · OWASP **A07:2021**.
- **Dónde:** `PUT /api/auth/password` no tenía límite de intentos. El login sí lo tenía.
- **Escenario:** con una sesión robada de 8 h, el atacante adivina la contraseña real del usuario y luego la cambia. Así toma la cuenta y la reutiliza en otros sitios.
- **Evidencia (D-07 antes):** 8 intentos → `[401 ×8]`, sin bloqueo.
- **Corrección:** mismo bloqueo que el login (5 fallos en 15 min, por usuario).
- **Validación:** D-07 después → `[401 ×5, 429, 429, 429]` · `test_f09_change_password_is_rate_limited`.

### F-10 — Códigos de pedido con generador no criptográfico (Bandit B311) — **BAJA**
- **CWE-330/338.** `random.randint` en `app/services/orders.py`. El código `AM-xxxxx` es lo que se usa para consultar un pedido en el chat.
- **Impacto real bajo:** el control de acceso (D-04, IDOR → 404) impide ver pedidos ajenos. Aun así es un identificador expuesto.
- **Corrección:** `secrets.randbelow`. El `random.choice` de la transportadora queda marcado `# nosec` (no es sensible).
- **Validación:** Bandit pasa de 4 a 2 B311 (los dos restantes son datos sintéticos de entrenamiento: FP) · `test_f10_order_codes_use_secrets_module`.

### F-11 — Servicios internos sin límite de tamaño de entrada (SAST manual) — **BAJA**
- **CWE-770.** `guardian /protect` y `/redact`, `chatbot /chat` y `vault /tokens` y `/reidentify` aceptaban cuerpos de cualquier tamaño. El NER de spaCy sobre un texto enorme sirve para agotar CPU y memoria.
- **Mitigante:** solo la tienda tiene el token de servicio y limita los mensajes a 2 000 caracteres (D-09).
- **Corrección (defensa en profundidad):** `max_length` de 20 000 en el texto, 40 turnos de historial y 200 entidades.
- **Validación:** `test_f11_internal_services_reject_huge_bodies` (422 en los tres servicios).

### F-12 — Dependencias vulnerables (SCA) — **BAJA / MEDIA**
pip-audit sobre el entorno real: **21 avisos en 4 paquetes**.

| Paquete | Versión | Aviso | ¿Aplica? | Acción | Después |
|---|---|---|---|---|---|
| certifi | 2026.7.22 | PYSEC-2026-4320 / GHSA-6q48-6c7w-9gw2 (raíz emSign retirada) | Sí: TLS de `httpx` hacia el LLM | El Lab. 05 fijó `>=2026.10.18`, pero **el `.venv` nunca se actualizó** (deriva de entorno). Se reinstaló. | 2026.10.23 |
| filelock | 4.2.0 | 17 CVE (CVE-2026-112906…) | No se usa directo (la trae `tldextract`) | `filelock>=4.2.1` en requirements | 4.2.12 |
| opentelemetry-api | 1.45.1 | CVE-2026-126360 (ReDoS en `traceparent`) | Hoy no: no se propaga trazado | `opentelemetry-api>=1.45.2` | 1.45.2 |
| setuptools | 84.0.0 | GHSA-xmj3-9gf7-h52w (path traversal en Windows al instalar wheels) | Solo en tiempo de instalación | Actualizado | 84.2.1 |

**Resultado:** `pip-audit-despues.json` → **0 vulnerabilidades conocidas**.

**Imagen Docker (Trivy):** `python:3.11-slim` (Debian 13.7) tiene **50 HIGH**. 47 no tienen parche publicado (util-linux, ncurses, sqlite y otros). Se corrigen las 3 con parche:
- `zlib1g`, con `apt-get upgrade`.
- `wheel` y `jaraco.context`, con `pip install --upgrade`.

Después quedan 48 sin parche. El único «con parche» que aparece, `setuptools 70.3.0`, es un **falso positivo**: Trivy lo lee del SBOM interno de pip (`pip/_vendor/bom.cdx.json`) y ese paquete no está instalado (el instalado es 84.2.1).

**Trivy config:** DS-0026 (sin `HEALTHCHECK`) → se agregó `HEALTHCHECK` a `/health`, con `PORT` por servicio en el compose → 0.

### F-13 — Encabezados de aislamiento entre orígenes (DAST ZAP 90004) — **BAJA**
- Faltaban `Cross-Origin-Resource-Policy` y `Cross-Origin-Embedder-Policy`.
- **Corrección:** `same-origin` y `require-corp` en el middleware de `app/main.py`. La página solo carga recursos propios.
- **Validación:** ZAP baseline ya no reporta 90004. La página carga sin errores de consola y `test_zap_90004_cross_origin_isolation_headers` pasa.

## Falsos positivos y riesgos residuales (triage)

| Herramienta | Alerta | Decisión | Por qué |
|---|---|---|---|
| Bandit B608 ×3 | SQL armado con f-string (`store.py:40`, `security.py:99`, `orders.py:43`) | **Falso positivo** | Lo único interpolado son constantes (`PUBLIC_USER_FIELDS`) o claves de una lista blanca (`SORTS`, `where` armado por el servidor). Los valores van siempre como parámetros `?`. |
| Bandit B105 | `REDACTION_TOKEN`, `_TOKEN` | Falso positivo | Son etiquetas de marcadores, no contraseñas. |
| Bandit B104/B310/B603 | `scripts/run_all.py` | Aceptado | Script de desarrollo. `0.0.0.0` solo con `--public` y `urlopen` a `127.0.0.1`. |
| Gitleaks (dir) | `.env` (API key del LLM) y `secrets/env/*.env` (tokens) | **Correcto, no es fuga** | Son secretos reales **fuera de git** (`.gitignore`) y fuera de la imagen (`.dockerignore`). El escaneo del historial (11 commits) confirma que nunca se subieron. |
| Gitleaks (git) | `generic-api-key` en `docs/evidencias/pip-audit.json` | Falso positivo | Hash de un paquete dentro de un reporte. Queda en el allowlist de `.gitleaks.toml`. |
| ZAP 10055 | `style-src 'unsafe-inline'` | **Riesgo residual** | Más de 30 atributos `style=` en las plantillas. Mitigado porque `script-src` no permite `unsafe-inline`. Pendiente: mover los estilos a CSS. |
| ZAP 10027 | Comentario «centro de seguridad (admin)» en `app.js` | Falso positivo | La ruta exige rol admin en el servidor (D-02 → 403). |
| ZAP 10049 | Contenido «storable» | Informativo | `Cache-Control: no-cache` es intencional. |
| ZAP 100001 | Content-Type inesperado en `/` | Falso positivo | El API scan espera JSON y `/` es la SPA en HTML. |
| Trivy | 47 HIGH de Debian sin parche | Aceptado / vigilar | Sin versión corregida publicada. Se reevalúa en cada build. |

## Lo que se verificó y está bien (DAST autenticado)
- D-02 y D-03: un cliente no entra a `/api/admin/*` ni a `/unsecure/chat` (403).
- D-04: **IDOR**. Un cliente no ve pedidos ajenos por código (404).
- D-05: sin sesión → 401.
- D-06: login bloqueado (429) al 6.º intento.
- D-08: un payload XSS guardado en el nombre se escapa al pintarse.
- D-09: mensajes de más de 2 000 caracteres → 422.
- D-10: CSP, X-Frame-Options y nosniff presentes.
- D-11: cookie `HttpOnly` y `SameSite=Lax`.

## Limitaciones
- DAST local por HTTP: no evalúa TLS/HSTS ni la cookie `Secure` (`APP_COOKIE_SECURE=true` solo aplica con HTTPS).
- No se probó *prompt injection* contra el LLM comercial (Gemini), para no enviar datos a un tercero. Se usó el chatbot local.
- El bloqueo por intentos es por correo y por usuario, y vive en memoria. No frena el *password spraying* desde muchas IP ni sobrevive a un reinicio. Recomendación: límite por IP en un proxy.
- Las herramientas automáticas (Semgrep, Gitleaks con reglas por defecto) **no encontraron los dos hallazgos más relevantes** (F-07, F-08). Hizo falta revisión manual y DAST autenticado.

## Cómo reproducir
```bash
python -m scripts.setup_secrets
python -m scripts.run_all                      # en otra terminal
python -m scripts.dast_manual docs/evidencias/lab06/dast-manual-despues.json
python -m pytest -q                            # 84 passed
```
