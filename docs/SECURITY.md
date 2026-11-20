# Seguridad del proyecto — evidencia del laboratorio

## 1. Alcance autorizado
- Repositorio: https://github.com/saraarteagar91/fdsi-gp-04-pii-llm (público)
- Rama evaluada y commit de línea base: `experimentos` / `9844c9028f4b35d05586b7c1604dd200c8f9c127`
- Rama del laboratorio: `security/lab-fsi`
- Tecnología: Python 3.12, FastAPI + Uvicorn, SQLite, Presidio/spaCy (guardián de PII), PyNaCl (cifrado), LLM externo compatible con OpenAI (Gemini) o Claude.
- Componentes: tienda `app` (página web + API), `guardian` (detección y cifrado de PII), `vault` (bóveda con llave privada), `chatbot` (Andi).
- Autenticación: correo + contraseña (hash scrypt), cookie de sesión `am_session` HttpOnly + SameSite=Lax, bloqueo tras 5 intentos fallidos.
- APIs principales: `/api/auth/*`, catálogo/carrito/pedidos, `/api/chat` en modos Unsecure y Secure, `/health`.
- Activos: datos personales ficticios de clientes (nombre, cédula, correo, celular), llave privada de la bóveda, llaves de API del LLM (`.env`, excluido de git).
- Riesgo principal: fuga de PII hacia el LLM o hacia el navegador de un tercero (XSS/clickjacking en la página del chat).
- URL de staging propio: no hay staging HTTPS. DAST ejecutado sobre `http://localhost:8077` con Docker (alternativa permitida por la guía).
- Responsable / autorización: equipo GP-04, sobre su propio entorno local, 2026-11-04.
- Fuera de alcance: producción, sistemas de terceros (API de Gemini/Anthropic), datos reales y pruebas destructivas.

## 2. Línea base y herramientas
| Herramienta | Tipo | Fecha | Resultado (antes → después) | Enlace a evidencia |
|---|---|---|---|---|
| Semgrep 1.183 (`p/owasp-top-ten`, `p/secrets`) | SAST | 2026-11-04 | 6 → 0 (acciones de GitHub con tag mutable) | [antes](evidencias/semgrep-antes.json) · [después](evidencias/semgrep-despues.json) · artefacto `resultado-semgrep` en Actions |
| CodeQL Default setup | SAST | — | Pendiente de activar en Settings → Advanced Security (disponible al ser repo público) | Settings → Advanced Security |
| Gitleaks 8 (historial completo, 8 commits) | Secretos | 2026-11-04 | 0 secretos | [gitleaks.json](evidencias/gitleaks.json) · job `Gitleaks` en Actions |
| pip-audit (entorno `.venv`) / Dependabot | SCA | 2026-11-04 | 20 avisos en 3 paquetes (certifi, filelock, setuptools) | [pip-audit.json](evidencias/pip-audit.json) |
| OWASP ZAP Baseline (Docker, pasivo) | DAST pasivo | 2026-11-04 | 7 → 4 alertas WARN, 0 FAIL | [antes](evidencias/zap-antes.html) · [después](evidencias/zap-despues.html) |

## 3. Hallazgos y gestión
| ID | Categoría | Descripción sin secretos | Riesgo | Archivo/ruta | Cambio propuesto | Estado |
|---|---|---|---|---|---|---|
| F-01 | A05 Security Misconfiguration / CWE-693, CWE-1021 | Sin CSP, X-Frame-Options, X-Content-Type-Options ni Permissions-Policy | Medio | `app/main.py` | Middleware `security_headers` | **Corregido** |
| F-02 | A08 Software and Data Integrity / CWE-829 | Workflows usan acciones por tag mutable (`@v4`) | Bajo | `.github/workflows/*.yml` | Fijar acciones a SHA de commit | **Corregido** |
| F-03 | A06 Vulnerable Components | `certifi 2026.7.22` confía en una raíz CA retirada (GHSA-6q48-6c7w-9gw2) | Bajo | `requirements.txt` | `certifi>=2026.10.18` | **Corregido** |
| F-04 | A06 Vulnerable Components | `filelock 4.2.0` (17 CVE), dependencia transitiva de torch/huggingface_hub | Bajo | entorno | Actualizar a 4.2.1 con el resto del stack de evaluación | Aceptado / pendiente |
| F-05 | Informativo | CSP permite `style-src 'unsafe-inline'` por los `style="..."` de las plantillas | Bajo | `static/app.js`, `static/index.html` | Mover estilos en línea a `styles.css` | Riesgo residual |
| F-06 | Informativo | ZAP detecta el comentario "centro de seguridad (admin)" en `app.js` | Informativo | `static/app.js` | Ninguno: la ruta igual exige rol admin en el servidor | Falso positivo |
| F-07 | Secretos (falso positivo) | Gitleaks marcó con la regla `generic-api-key` el texto de ejemplo de un exploit de `filelock` dentro del reporte de pip-audit; no es una credencial del proyecto | Informativo | `docs/evidencias/pip-audit.json` | Ignorar solo ese hallazgo con un fingerprint en `.gitleaksignore`; no excluir la carpeta | Cerrado (falso positivo documentado) |

## 4. Validación antes y después
- Evidencia inicial: `curl -sI http://localhost:8077/` solo devolvía `content-type`, `etag` y `cache-control`. ZAP: alertas 10020, 10021, 10038 y 10063.
- Pull request con corrección: rama `security/lab-fsi` → `experimentos` (https://github.com/saraarteagar91/fdsi-gp-04-pii-llm/pull/2).
- Evidencia de reescaneo: ZAP ya no reporta 10020/10021/10038/10063. Semgrep pasa de 6 a 0 hallazgos. Las 75 pruebas de `pytest` pasan, incluida `tests/test_security_headers.py`.
- Riesgo residual y decisión: `style-src 'unsafe-inline'` (F-05) y COEP ausente (no aplica: la página no usa `SharedArrayBuffer`). Swagger `/docs` queda sin CSP porque carga scripts de un CDN; se recomienda desactivarlo en producción.

## 5. Pentest autorizado
- Hipótesis: la página del chat (donde el usuario escribe PII) puede cargarse dentro de un `<iframe>` de otro sitio (clickjacking), y el navegador ejecutaría scripts inyectados porque no hay CSP.
- Entorno de pruebas aislado: `uvicorn app.main:app --port 8077` en la máquina del equipo, con datos ficticios del seed.
- Solicitudes inocuas y respuestas observadas:
  - Antes: `curl -sI http://localhost:8077/` → sin `X-Frame-Options` ni `Content-Security-Policy`.
  - Después: `X-Frame-Options: DENY`, `Content-Security-Policy: ... script-src 'self'; ... frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`.
- Resultado: validado (el encabezado faltaba) y corregido.
- Recomendación y prueba de regresión: `tests/test_security_headers.py` comprueba los encabezados en `/`, archivos estáticos, `/health` y un 404, y que `script-src` no permita `unsafe-inline` ni `unsafe-eval`.

## 6. Limitaciones
- El repositorio es público, así que CodeQL Default setup y secret scanning nativo están disponibles sin costo. Sus resultados se registrarán cuando se activen en Settings → Advanced Security. Mientras tanto, Semgrep y Gitleaks cubren SAST y secretos.
- Al ser público, cualquier persona puede ver las evidencias de `docs/evidencias/`. Solo contienen datos ficticios y `localhost`.
- Activar Dependabot y los controles de Settings requiere permisos de administrador del repositorio.
- El DAST es pasivo y local: no evalúa TLS/HSTS (no hay HTTPS) ni las respuestas del LLM.
- Un pipeline en verde no significa que la aplicación sea segura: Semgrep y ZAP corren con `|| true` / `-I`.
