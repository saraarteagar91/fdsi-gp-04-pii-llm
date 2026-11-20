# Lab. 06 — Hallazgos de seguridad

**Proyecto:** FDSI-GP-04 — Andes Market
**Integrantes:** Johan Sebastián Beltrán, Andrés Camilo Vivas
**Rama:** `security/lab06-hallazgos` (sale de `security/lab-fsi`)
**Entorno:** la app corriendo en nuestro PC (`http://127.0.0.1:8000`) con datos ficticios.
**Evidencias:** carpeta `docs/evidencias/lab06/` (cada reporte tiene versión `antes` y `después`).

## Resumen

Encontramos y corregimos **7 hallazgos**. Las pruebas automáticas pasaron de 75 a **84**, todas en verde.

| ID | Hallazgo | Tipo de análisis | Nivel | Estado |
|---|---|---|---|---|
| F-07 | Contraseña del admin escrita en el repositorio público | Secretos + DAST | **Alta** | Corregido |
| F-08 | XSS en el panel de auditoría del chat | SAST | Media | Corregido |
| F-09 | Se podía adivinar la contraseña actual sin límite | DAST | Media | Corregido |
| F-10 | Códigos de pedido generados con `random` | SAST | Baja | Corregido |
| F-11 | Servicios internos aceptaban mensajes de cualquier tamaño | SAST | Baja | Corregido |
| F-12 | Librerías con vulnerabilidades conocidas | SCA | Baja / media | Corregido |
| F-13 | Faltaban dos encabezados de seguridad | DAST | Baja | Corregido |

**Herramientas:**
- **SAST:** Semgrep, Bandit y revisión manual del código.
- **SCA:** pip-audit y Trivy.
- **Secretos:** Gitleaks.
- **DAST:** OWASP ZAP y un script propio de pruebas con sesión iniciada (`scripts/dast_manual.py`).

---

## 1. SAST — análisis del código fuente

**Cómo lo hicimos:**
- Corrimos Semgrep (291 reglas) y Bandit sobre todo el código.
- Revisamos a mano los puntos sensibles: inicio de sesión, permisos y los lugares donde el JavaScript usa `innerHTML`.

**Qué encontramos:**
- **F-08 (media):** en `static/app.js`, el panel de auditoría mostraba como HTML cualquier texto que empezara por `<div`. Por ahí pasan el mensaje del usuario y la respuesta del LLM, así que se podía inyectar HTML (XSS). La política CSP del Lab. 05 ya impedía ejecutar scripts, por eso es media y no alta.
- **F-10 (baja):** Bandit avisó que los códigos de pedido (`AM-xxxxx`) se generaban con `random`, que es predecible.
- **F-11 (baja):** el guardián, el chatbot y la bóveda no limitaban el tamaño de lo que reciben. Un texto gigante podía saturarlos.
- **Falsos positivos:**
  - Bandit marcó 3 consultas SQL. No son peligrosas, porque los valores van siempre como parámetros `?`.
  - Semgrep no encontró nada. Los problemas reales aparecieron con la revisión manual.

**Cómo lo solucionamos:**
- F-08: solo se pinta como HTML lo que el código marca explícitamente como seguro (`trusted()`). Todo lo demás se escapa.
- F-10: los códigos ahora se generan con `secrets`.
- F-11: límite de 20 000 caracteres por mensaje.

**Cómo lo validamos:** con pruebas automáticas nuevas en `tests/test_lab06_security.py`. Bandit pasó de 4 avisos de `random` a 2, y esos 2 son datos de entrenamiento.

## 2. SCA — dependencias vulnerables

**Cómo lo hicimos:**
- pip-audit sobre las 82 librerías instaladas.
- Trivy sobre la imagen Docker y sobre el Dockerfile.

**Qué encontramos:** **21 vulnerabilidades en 4 librerías.**

| Librería | Problema | ¿Nos afecta? | Solución |
|---|---|---|---|
| certifi | Confía en un certificado raíz revocado | Sí: se usa en la conexión segura con el LLM | Actualizada |
| filelock | 17 CVE | Poco: no la usamos directamente | Actualizada a 4.2.12 |
| opentelemetry-api | Se puede bloquear con un texto especial (ReDoS) | Hoy no | Actualizada a 1.45.2 |
| setuptools | Problema al instalar paquetes en Windows | Solo al instalar | Actualizada |

> Dato curioso: en el Lab. 05 ya habíamos corregido `certifi` en `requirements.txt`, pero nunca reinstalamos el entorno. **Corregir el archivo no sirve si no se reinstala.**

**Imagen Docker (Trivy):**
- La imagen base tiene 50 vulnerabilidades altas. 47 todavía no tienen parche publicado.
- Corregimos las 3 que sí lo tenían, actualizando paquetes en el Dockerfile.
- Agregamos un `HEALTHCHECK`, que Trivy pedía.

**Cómo lo validamos:**
- pip-audit pasó de **21 a 0**.
- Trivy config pasó de 1 a 0.
- Las 3 vulnerabilidades corregibles de la imagen desaparecieron.

## 3. Detección de secretos

**Cómo lo hicimos:** Gitleaks sobre todo el historial de git (11 commits) y sobre la carpeta del proyecto.

**Qué encontramos:**
- **F-07 (alta):** la contraseña del administrador estaba escrita en `data/seed/usuarios_demo.json` y en la documentación, y **el repositorio es público**. Con ella cualquiera podía entrar como admin y ver los logs con datos personales.
- Gitleaks **no lo detectó** con sus reglas normales. Lo encontramos revisando el código.
- Los tokens y la API key del LLM están en `.env` y `secrets/`. Revisamos el historial y **nunca se subieron a git**: están bien protegidos.

**Cómo lo solucionamos:**
- La contraseña del admin ahora es **aleatoria** y se guarda en `secrets/env/app.env`, que no se sube al repositorio.
- Si alguien tenía la base de datos vieja, la contraseña se cambia sola al arrancar la app.
- Creamos una **regla propia de Gitleaks** (`.gitleaks.toml`) que detecta contraseñas escritas en archivos de datos.

**Cómo lo validamos:**
- Probamos entrar con la contraseña vieja: antes **200 (entraba)**, ahora **401 (rechazado)**.
- Corrimos la regla nueva sobre el commit donde se filtró la contraseña, y sí la detecta.

## 4. DAST — pruebas con la aplicación corriendo

**Cómo lo hicimos:**
- Corrimos OWASP ZAP en dos modos: pasivo (baseline) y activo contra la API.
- ZAP no inicia sesión, así que escribimos `scripts/dast_manual.py`: **11 pruebas** que entran como cliente y como admin.

**Qué encontramos:**
- ZAP: **0 fallas graves**. Solo avisos. El más útil decía que faltaban dos encabezados de seguridad (**F-13**).
- Pruebas propias:
  - **F-07:** el login con la contraseña publicada funcionaba.
  - **F-09:** en "cambiar contraseña" se podía probar la contraseña actual sin límite (8 intentos, ningún bloqueo).
- Lo que **sí estaba bien:**
  - Un cliente no puede ver pedidos de otros (IDOR → 404).
  - Un cliente no puede entrar a las páginas de admin (403).
  - El login se bloquea tras 5 intentos fallidos.
  - Un payload XSS en el nombre se muestra escapado.

**Cómo lo solucionamos:**
- F-09: el cambio de contraseña se bloquea tras 5 intentos fallidos, igual que el login.
- F-13: agregamos los encabezados `Cross-Origin-Resource-Policy` y `Cross-Origin-Embedder-Policy`.

**Cómo lo validamos:**
- Las 11 pruebas pasan. El cambio de contraseña ahora responde 429 en el 6.º intento.
- ZAP baseline pasó de 5 a 3 avisos.

---

## Lo que queda pendiente (riesgos aceptados)

- **`style-src 'unsafe-inline'`:** las plantillas tienen 36 estilos escritos dentro del HTML. Se pueden mover a CSS más adelante. El riesgo es bajo porque los scripts sí están bloqueados.
- **Contraseñas de los clientes de prueba:** siguen en el seed. Son datos ficticios para la demo local.
- **47 vulnerabilidades de la imagen base sin parche publicado:** se revisan en cada nueva construcción.
- **La contraseña vieja del admin sigue en el historial de git:** no importa, porque ya no funciona.

## Conclusión

Las herramientas automáticas ayudan, pero **los dos hallazgos más graves (F-07 y F-08) solo aparecieron con revisión manual y pruebas con sesión iniciada.**

## Cómo repetir las pruebas

```bash
python -m scripts.setup_secrets
python -m scripts.run_all          # dejar corriendo en otra terminal
python -m scripts.dast_manual      # 11 pruebas DAST
python -m pytest -q                # 84 pruebas
```
