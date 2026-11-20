## Lab 05: SAST, secretos, SCA, DAST y corrección de encabezados de seguridad

### Resumen
Integra controles de seguridad al ciclo de desarrollo y corrige los hallazgos priorizados:

- **Pipeline:** workflow `Seguridad estática - SAST y secretos` (Semgrep + Gitleaks) en cada PR, y workflow manual de DAST pasivo con OWASP ZAP. Las acciones están fijadas a SHA.
- **F-01 (corregido):** middleware `security_headers` en `app/main.py` que agrega CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` y `Cross-Origin-Opener-Policy`.
- **F-03 (corregido):** `certifi>=2026.10.18` en `requirements.txt`.
- **F-08 (corregido):** el panel de auditoría de `static/app.js` ya no decide por `startsWith("<div")` si escapa; el HTML propio se marca con `trusted()` y el texto del usuario y del LLM pasa siempre por `esc()` (CodeQL #3).
- **Pruebas de regresión:** `tests/test_security_headers.py` y `tests/test_audit_panel_xss.py`.
- **Documentación:** `docs/SECURITY.md`, `docs/REPORTE_HALLAZGOS.md` y evidencias en `docs/evidencias/`.
- **Limpieza:** `.idea/` sale del repositorio y se agrega a `.gitignore`.

Línea base: `9844c90` · Entorno: localhost con datos ficticios.

### Hallazgos
| ID | Categoría | Descripción | Riesgo | Estado |
|---|---|---|---|---|
| F-01 | A05 / CWE-693, CWE-1021 | Sin CSP ni encabezados anti-clickjacking / nosniff | Medio | ✅ Corregido |
| F-02 | A08 / CWE-829 | Acciones de GitHub con tag mutable | Bajo | ✅ Corregido |
| F-03 | A06 | `certifi` con raíz CA retirada (GHSA-6q48-6c7w-9gw2) | Bajo | ✅ Corregido |
| F-04 | A06 | `filelock` 4.2.0, transitiva de torch/huggingface_hub | Bajo | Aceptado / pendiente |
| F-05 | Informativo | CSP con `style-src 'unsafe-inline'` | Bajo | Riesgo residual |
| F-06 | Informativo | Comentario "admin" en `app.js` reportado por ZAP | Info | Falso positivo |
| F-07 | Secretos | Gitleaks marcó texto de ejemplo de un exploit de filelock en `pip-audit.json` | Info | Falso positivo (`.gitleaksignore`) |
| F-08 | A03 / CWE-79 | CodeQL #3: XSS en el panel de auditoría por `startsWith("<div")` | Alto | ✅ Corregido |
| F-09 | CWE-1333 | CodeQL #1: regex del correo (`auth.py:48`), limitado a 200 caracteres | Bajo | Aceptado / mitigado |
| F-10 | CWE-1333 | CodeQL #2: regex de presentación (`engine.py:155`) sobre máximo 30 caracteres | Info | Falso positivo |

### Evidencias (antes → después)
| Herramienta | Antes | Después | Archivos |
|---|---|---|---|
| Semgrep (`p/owasp-top-ten`, `p/secrets`) | 6 | 0 | `docs/evidencias/semgrep-antes.json`, `semgrep-despues.json` |
| Gitleaks (historial completo) | 0 | 0 | `docs/evidencias/gitleaks.json` |
| pip-audit | 20 avisos / 3 paquetes | certifi corregido | `docs/evidencias/pip-audit.json` |
| OWASP ZAP baseline | 7 WARN | 4 WARN (0 FAIL) | `docs/evidencias/zap-antes.html`, `zap-despues.html` |
| pytest | 68 | 77 (incluye 9 nuevas) | `tests/test_security_headers.py`, `tests/test_audit_panel_xss.py` |

Validación manual: antes, `curl -sI http://localhost:8077/` no devolvía `Content-Security-Policy` ni `X-Frame-Options`; después devuelve ambos.

### Checklist de seguridad del Pull Request
- [x] El cambio tiene una descripción funcional y un alcance definido.
- [x] Revisé que no se subieran credenciales, tokens ni archivos .env.
- [x] El SAST fue ejecutado; interpreté hallazgos verdaderos y falsos positivos.
- [x] Revisé dependencias y actualizaciones relevantes.
- [x] Revisé autenticación y autorización si el cambio afecta APIs. *(El cambio no modifica autenticación ni autorización; solo agrega encabezados de respuesta.)*
- [x] Se ejecutaron pruebas funcionales y de regresión.
- [x] Si hay DAST, fue sobre mi staging autorizado. *(ZAP pasivo sobre localhost propio; no hay staging HTTPS.)*
- [x] Vinculé hallazgos, decisiones de mitigación y evidencias.

### Limitaciones
- CodeQL (Default setup), secret scanning, push protection y Dependabot quedaron activados el 2026-11-20; la primera ejecución de CodeQL fue sobre main, no sobre la rama corregida.
- El DAST fue pasivo y local, sin HTTPS.
- El pipeline corre en modo no bloqueante (`|| true` / `-I`): en verde no significa seguro.
