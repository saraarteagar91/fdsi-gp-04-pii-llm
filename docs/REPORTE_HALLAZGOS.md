# Informe técnico de hallazgos

**Proyecto:** FDSI-GP-04 — Andes Market (protección de PII en chat con LLM)
**Integrantes:** Johan Sebastián Beltrán, Sara Arteaga, Camilo Vivas
**Repositorio / commit:** https://github.com/saraarteagar91/fdsi-gp-04-pii-llm — línea base `9844c90`, rama `security/lab-fsi`
**Entorno autorizado:** entorno local del equipo (`http://localhost:8077`, Docker para ZAP), datos ficticios
**Fecha:** 2026-11-04

## Resumen ejecutivo
1. **Faltaban los encabezados de seguridad HTTP (F-01, medio).** La página donde los clientes escriben su PII no tenía CSP ni protección contra clickjacking. Un XSS o un iframe malicioso podría capturar lo que escribe el usuario. **Corregido** con un middleware y una prueba de regresión.
2. **La cadena de suministro del pipeline usaba acciones con tags mutables (F-02, bajo).** Si alguien reescribe el tag `v4` de una acción, se ejecuta código ajeno en el CI. **Corregido** fijando las acciones a su SHA.
3. **Dependencias con avisos conocidos (F-03/F-04, bajo).** `certifi` tenía una raíz CA retirada y se usa en el TLS hacia el LLM: **corregido**. `filelock` es transitiva de herramientas de evaluación: aceptado y documentado.

## Metodología
Identificación del alcance → SAST (Semgrep) → detección de secretos (Gitleaks, historial completo) → SCA (pip-audit / Dependabot) → DAST pasivo (ZAP baseline en localhost) → validación manual no destructiva (`curl -I`) → corrección → reescaneo.

## Hallazgo F-01
- **Título:** Ausencia de Content-Security-Policy y encabezados anti-clickjacking
- **Categoría OWASP/CWE:** A05:2021 Security Misconfiguration; CWE-693 (Protection Mechanism Failure), CWE-1021 (Improper Restriction of Rendered UI Layers)
- **Severidad y justificación:** Media. No es explotable por sí sola, pero elimina la defensa en profundidad de una página que maneja PII y donde `app.js` construye vistas con `innerHTML`. Si una plantilla olvidara escapar un dato, nada impediría ejecutar un script inyectado.
- **Evidencia minimizada:** ZAP baseline: `WARN-NEW` 10020 (anti-clickjacking), 10021 (X-Content-Type-Options, ×3), 10038 (CSP), 10063 (Permissions-Policy). `curl -sI /` devolvía solo `content-type`, `etag` y `cache-control`.
- **Impacto:** Confidencialidad (robo de PII por XSS o clickjacking) e integridad (acciones no deseadas en el carrito o el chat desde un iframe).
- **Pasos de validación segura:** levantar la app en local, ejecutar `curl -sI http://localhost:8077/` y ZAP baseline pasivo. No se hicieron ataques activos.
- **Corrección:** middleware `security_headers` en `app/main.py`. CSP con `script-src 'self'`, `frame-ancestors 'none'` y `object-src 'none'`, más `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy` y COOP. Prueba: `tests/test_security_headers.py`.
- **Resultado del reescaneo:** ZAP pasa de 7 a 4 alertas. Las alertas 10020, 10021, 10038 y 10063 desaparecen. Queda 10055 (`style-src 'unsafe-inline'`) como riesgo residual. 75/75 pruebas pasan.

## Hallazgo F-02
- **Título:** Acciones de GitHub referenciadas por tag mutable
- **Categoría OWASP/CWE:** A08:2021 Software and Data Integrity Failures; CWE-829
- **Severidad y justificación:** Baja. Requiere que se comprometa el repositorio de la acción, pero el job de Gitleaks recibe `GITHUB_TOKEN`.
- **Evidencia minimizada:** Semgrep `yaml.github-actions.security.github-actions-mutable-action-tag`, 6 resultados en `.github/workflows/`.
- **Impacto:** Integridad del pipeline y confidencialidad del código y el token.
- **Pasos de validación segura:** revisión estática; no requiere ejecución.
- **Corrección:** cada `uses:` fijado al SHA del commit con el tag como comentario (`actions/checkout@11d5960… # v4`).
- **Resultado del reescaneo:** Semgrep pasa de 6 a 0 hallazgos.
- **Falso positivo analizado:** Semgrep no reportó nada en el código Python. Ninguna de las reglas encontró SQL armado con cadenas (`app/db.py` usa parámetros), así que no hay falsos positivos que descartar en el backend.

## Hallazgo F-03 (SCA)
- **Título:** `certifi 2026.7.22` incluye la raíz `emSign ECC Root CA - G3` retirada
- **Categoría:** A06:2021 Vulnerable and Outdated Components — PYSEC-2026-4320 / GHSA-6q48-6c7w-9gw2
- **¿Aplica al código?** Sí. `httpx` (usado en `app/clients.py` y en los clientes del LLM) valida TLS con el paquete de certifi.
- **Corrección:** `certifi>=2026.10.18` en `requirements.txt` (versión instalada: 2026.10.23). Las pruebas siguen pasando.
- **F-04 (`filelock` 4.2.0):** lo requieren `torch`, `huggingface_hub` y `tldextract`. No se usa en el código de la app y la mayoría de los CVE afectan a Windows o a locks que no usamos. No se actualiza a ciegas; queda pendiente con la próxima actualización del stack de evaluación.

## Hallazgo F-07 (Secretos)
- **Título:** Gitleaks reporta un posible secreto en el reporte de pip-audit
- **Categoría:** Informativo — falso positivo
- **Qué detectó:** regla `generic-api-key` en `docs/evidencias/pip-audit.json`, línea 1, commit `0fd9f9e`.
- **Por qué es falso positivo:** es parte de la descripción de un CVE de `filelock` que trae el reporte de pip-audit (ejemplo de exploit con ruta de víctima y token de muestra), no una credencial del proyecto.
- **Decisión:** se ignora solo ese hallazgo con un fingerprint en `.gitleaksignore`. No se excluye la carpeta `docs/evidencias/` para seguir vigilándola.

## Hallazgo F-08
- **Título:** El panel de auditoría inserta como HTML el texto del usuario y del LLM (CodeQL #3, "DOM text reinterpreted as HTML")
- **Categoría OWASP/CWE:** A03:2021 Injection; CWE-79 (Cross-site Scripting)
- **Severidad y justificación:** Alta. El panel muestra el mensaje del usuario (`d.userText`) y la respuesta del LLM (`a.llm_output`). Un texto que empiece por `<div` se ejecutaría en el navegador, y la respuesta del LLM puede estar influida por terceros (inyección de prompt).
- **Evidencia minimizada:** CodeQL alerta #3 en `static/app.js:822` (`auditBody.innerHTML` en `showAudit`). Con la entrada `<div><img src=x onerror=1>`, el `step()` anterior devolvía `<div><img src=x onerror=1>` sin escapar.
- **Impacto:** Confidencialidad (robo de PII de la conversación) e integridad (acciones en nombre del usuario).
- **Pasos de validación segura:** ejecutar la función `step()` con node fuera del navegador y revisar la salida. No se hizo ningún ataque sobre la app.
- **Antes:** `step()` decidía si escapaba según el contenido: `content.startsWith("<div")` evitaba el escape, y el título (que incluye `a.llm_provider`) se insertaba sin escapar.
- **Después:** el HTML armado por el propio código (las pills) se marca de forma explícita con `trusted()`, que crea una instancia de `TrustedHtml`. Todo lo demás pasa siempre por `esc()`, igual que el título y la clase. Un objeto que llegue por JSON no puede hacerse pasar por el marcador. El panel se ve igual que antes.
- **Prueba de regresión:** `tests/test_audit_panel_xss.py` comprueba que `static/app.js` ya no contiene `startsWith("<div")` y ejecuta `step()` con node usando la entrada `<div><img src=x onerror=1>`: el texto del usuario, el del LLM y el título salen escapados, y las pills siguen saliendo como HTML. Falla con el código anterior y pasa con el nuevo; `pytest` pasa 77/77.

## Hallazgo F-09
- **Título:** Regex del correo con posible coste polinómico (CodeQL #1, "Polynomial regular expression used on uncontrolled data")
- **Categoría OWASP/CWE:** CWE-1333 (Inefficient Regular Expression Complexity)
- **Severidad y justificación:** Baja. `_EMAIL_RE` en `app/routers/auth.py:48` se aplica al correo que envía el usuario, pero `LoginIn` y `RegisterIn` limitan el correo a `max_length=200`, así que la entrada no puede crecer lo suficiente para causar una demora apreciable.
- **Decisión:** aceptado / mitigado; no se cambia el código en este laboratorio.
- **Mejora sugerida:** validar el correo con un tipo de Pydantic en lugar de una regex propia.

## Hallazgo F-10
- **Título:** Regex de presentación con posible coste polinómico (CodeQL #2, "Polynomial regular expression used on uncontrolled data")
- **Categoría OWASP/CWE:** CWE-1333 — Informativo
- **Por qué es falso positivo:** `_PRESENTATION_RE` en `guardian/engine.py:155` se aplica sobre un fragmento de máximo 30 caracteres (`text[max(0, r.start - 30):r.start]`), así que en la práctica no hay entrada larga que procesar.
- **Decisión:** falso positivo en la práctica; no se cambia el código.

## Nota sobre SCA
Dependabot dio 0 alertas y pip-audit 20: cada herramienta cubre algo distinto. Dependabot solo ve lo declarado en `requirements.txt`, que usa rangos `>=` sin versiones fijas; pip-audit revisa lo que de verdad está instalado en el `.venv`, incluidas las dependencias transitivas.

## Reflexión final
- **Lo que encontraron las herramientas:** ZAP encontró la falta de encabezados, que es la falla más relevante para un proyecto de PII. Semgrep solo encontró problemas en el propio pipeline. Gitleaks confirmó que `.env` y `secrets/` nunca se subieron.
- **Lo que no pueden ver:** ninguna herramienta evalúa el riesgo central del proyecto, es decir, si el guardián deja pasar PII al LLM. Eso lo cubren las pruebas propias (`test_secure_flow.py`, `test_isolation.py`).
- **Siguiente paso de DevSecOps:**
  - Quitar `|| true` cuando haya triage.
  - Fijar versiones en `requirements.txt` (o usar un archivo de bloqueo) para que Dependabot pueda detectar vulnerabilidades en las dependencias (por ejemplo, con `pip-compile`).
  - Mover los estilos en línea a CSS para endurecer la CSP.
  - Correr ZAP contra un staging HTTPS.
