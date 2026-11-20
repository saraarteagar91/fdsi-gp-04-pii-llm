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

## Reflexión final
- **Lo que encontraron las herramientas:** ZAP encontró la falta de encabezados, que es la falla más relevante para un proyecto de PII. Semgrep solo encontró problemas en el propio pipeline. Gitleaks confirmó que `.env` y `secrets/` nunca se subieron.
- **Lo que no pueden ver:** ninguna herramienta evalúa el riesgo central del proyecto, es decir, si el guardián deja pasar PII al LLM. Eso lo cubren las pruebas propias (`test_secure_flow.py`, `test_isolation.py`).
- **Siguiente paso de DevSecOps:**
  - Quitar `|| true` cuando haya triage.
  - Activar Dependabot y fijar versiones (`pip-compile`).
  - Mover los estilos en línea a CSS para endurecer la CSP.
  - Correr ZAP contra un staging HTTPS.
