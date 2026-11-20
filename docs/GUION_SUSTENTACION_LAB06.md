# Guion de sustentación — Lab. 06 (máximo 5 minutos)

Reparto sugerido: **A** = Johan, **B** = Sara, **C** = Camilo. Tengan abiertos de antemano:
1. `docs/REPORTE_HALLAZGOS_LAB06.md`.
2. Una terminal con la app corriendo (`python -m scripts.run_all`).
3. `docs/evidencias/lab06/zap-baseline-antes.html` y `zap-baseline-despues.html`.

---

**0:00–0:30 · Contexto (A)**
«Analizamos Andes Market, nuestro proyecto: una tienda con chatbot donde un guardián cifra la PII antes de que llegue al LLM. Son cuatro servicios FastAPI. Aplicamos SAST, SCA, detección de secretos y DAST en local con datos ficticios. Encontramos y corregimos 7 hallazgos. Vamos con los más graves.»

**0:30–1:45 · Secret Detection + DAST: F-07, alta (B)**
- **Qué:** la contraseña del administrador estaba fija en `data/seed/usuarios_demo.json` y en los docs, y el repo es público. Cualquier despliegue nacía con un admin de contraseña conocida, que ve logs con PII y el modo inseguro.
- **Cómo:** Gitleaks con reglas por defecto **no lo vio**; solo dio un falso positivo en un reporte. Lo encontramos revisando el seed y lo **explotamos** con el DAST autenticado (D-01): login → 200.
- **Arreglo:**
  - La contraseña ahora es aleatoria, en `secrets/env/app.env` (fuera de git). Si falta, no se crea el admin.
  - Las bases viejas se rotan solas al arrancar.
  - Agregamos una **regla propia de Gitleaks** que sí la detecta en el commit original.
- **Validación (en vivo):** `python -m scripts.dast_manual` → D-01 **PASA (401)**.

**1:45–2:45 · SAST: F-08 XSS y F-10 (C)**
- **Qué:** en `static/app.js`, el panel de auditoría pintaba como HTML cualquier texto que empezara por `<div`, incluida la respuesta del LLM. Es XSS de DOM (CWE-79), media porque nuestra CSP del Lab. 05 bloquea los scripts.
- **Cómo:** revisión manual de los `innerHTML`. Semgrep, con 291 reglas, dio 0 hallazgos. Bandit dio 14 avisos: los B608 de SQL son **falsos positivos** (lista blanca y parámetros `?`). El B311 sí aplicaba a los códigos de pedido, que salían de `random`.
- **Arreglo:** HTML de confianza marcado explícitamente con `trusted()`; todo lo demás se escapa. Códigos de pedido con `secrets`. Límites de tamaño en los servicios internos (F-11).
- **Validación:** pruebas de regresión. Bandit B311 pasa de 4 a 2, y los dos restantes son datos de entrenamiento.

**2:45–3:45 · SCA (A)**
- **Qué:** pip-audit sobre el `.venv` real dio **21 avisos en 4 paquetes**. Lo interesante es certifi: el Lab. 05 lo había corregido en `requirements.txt`, pero el entorno nunca se actualizó. Corregir el archivo no basta si no se reinstala.
- **Cómo lo gestionamos:** analizamos si cada uno aplica.
  - certifi sí aplica (TLS hacia el LLM).
  - filelock es transitiva y no se usa directamente.
  - opentelemetry tiene un ReDoS que hoy no es alcanzable.
  - Se actualizaron todos y se fijaron mínimos en `requirements.txt`.
- **Trivy:** la imagen base tiene 50 HIGH, 47 sin parche. Corregimos las 3 con parche, agregamos `HEALTHCHECK` y documentamos un falso positivo de setuptools que viene del SBOM de pip.
- **Validación:** pip-audit pasa de 21 a **0**; Trivy config de 1 a 0.

**3:45–4:40 · DAST (B)**
- **ZAP baseline y API scan activo:** 0 FAIL. Faltaban los encabezados CORP/COEP; los agregamos y la alerta 90004 desapareció. Queda `style-src 'unsafe-inline'` como riesgo residual: son 36 atributos `style=`.
- **ZAP no inicia sesión**, así que escribimos 11 pruebas autenticadas. Con ellas encontramos **F-09**: el cambio de contraseña permitía adivinar la contraseña actual sin límite (8 × 401). Ahora bloquea al 6.º intento (429).
- También comprobamos lo que sí estaba bien: IDOR (404), un cliente sin acceso a funciones de admin (403) y el bloqueo del login.

**4:40–5:00 · Cierre (C)**
«Pasamos de 75 a 84 pruebas, todas en verde, y todo quedó en la rama `security/lab06-hallazgos` con las evidencias antes y después. Lo más importante que aprendimos: las herramientas automáticas no encontraron los dos hallazgos más graves. Hizo falta revisión manual y DAST autenticado.»

---

### Preguntas probables
- **¿Por qué no reescribieron el historial de git para borrar la contraseña?** Porque ya está revocada (rotada). Reescribir un historial público no la «des-publica», porque pudo haberse clonado. Lo que importa es la rotación.
- **¿Por qué el XSS es media y no alta?** Porque la CSP `script-src 'self'` impide ejecutar scripts en línea y `onerror`. Aun así se podía inyectar HTML (UI falsa), y no dependemos de una sola capa.
- **¿Las contraseñas de los clientes de prueba?** Riesgo aceptado: son datos ficticios para la demo local. La regla de Gitleaks tiene un allowlist explícito para ellas y no aplica a un admin.
