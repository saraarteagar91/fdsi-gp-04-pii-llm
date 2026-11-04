# Guion de la demo — Lab. 05 (5 minutos, 3 personas)

Proyecto: FDSI-GP-04 — Andes Market · Rama: `security/lab-fsi` · Línea base: `9844c90`
Soporte: [SECURITY.md](SECURITY.md) · [REPORTE_HALLAZGOS.md](REPORTE_HALLAZGOS.md)

| Tiempo | Quién | Bloque |
|---|---|---|
| 0:00–1:00 | Johan | Problema e impacto |
| 1:00–2:30 | Sara | Evidencia (herramientas + validación manual) |
| 2:30–4:00 | Camilo | Corrección y nueva evidencia |
| 4:00–5:00 | Johan | Limitaciones y cierre |

---

## 1. Problema (Johan, ~30 s)
> "Andes Market es una tienda con un chatbot donde los clientes escriben datos personales: nombre, cédula, correo y celular, todos ficticios en este laboratorio. El guardián protege esos datos antes de enviarlos al LLM. Al revisar la página web con OWASP ZAP encontramos que la defensa del navegador estaba vacía: no había Content-Security-Policy, ni protección contra clickjacking, ni `nosniff`."

## 2. Impacto (Johan, ~30 s)
> "Es el hallazgo F-01, de severidad media. Por sí solo no es explotable, pero `app.js` arma las vistas con `innerHTML`. Si alguna plantilla olvidara escapar un dato, un script inyectado podría leer la PII que el usuario escribe en el chat. Y sin `X-Frame-Options`, otro sitio podría meter la tienda en un iframe y engañar al usuario. Afecta sobre todo la confidencialidad y también la integridad."

## 3. Evidencia (Sara, ~1 min 30 s)
1. **Pipeline:** mostrar en GitHub la pestaña **Actions** → "Seguridad estática - SAST y secretos" (Semgrep + Gitleaks).
2. **Semgrep:** 6 hallazgos al inicio, todos en los workflows por usar acciones con tag mutable (F-02). En el código Python no encontró nada, y lo verificamos: las consultas SQL usan parámetros `?`.
3. **Gitleaks:** 0 secretos en los 8 commits del historial. `.env` y `secrets/` nunca se subieron.
4. **SCA (pip-audit / Dependabot):** 20 avisos en 3 paquetes. `certifi` sí aplica porque httpx lo usa para el TLS hacia el LLM (F-03). `filelock` es transitiva de torch (F-04).
5. **ZAP antes:** abrir `docs/evidencias/zap-antes.html`. Muestra 7 alertas, entre ellas 10020 (clickjacking), 10021 (nosniff), 10038 (CSP) y 10063 (Permissions-Policy).
6. **Validación manual (demo en vivo):** `curl -sI` a la versión de línea base (comandos abajo). No aparece ni `content-security-policy` ni `x-frame-options`.

## 4. Corrección (Camilo, ~45 s)
> "La corrección es pequeña y fácil de rastrear: un middleware `security_headers` en `app/main.py`. Agrega una CSP con `script-src 'self'`, `frame-ancestors 'none'` y `object-src 'none'`, además de `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy` y `Permissions-Policy`. También fijamos las acciones de GitHub a su SHA (F-02) y subimos `certifi` (F-03). La prueba de regresión es `tests/test_security_headers.py`: falla si alguien quita un encabezado o si la CSP permite scripts en línea."

## 5. Nueva evidencia (Camilo, ~45 s)
1. `curl -sI` a la versión corregida: ahora aparecen los encabezados.
2. Abrir `docs/evidencias/zap-despues.html`: bajó de 7 a 4 alertas y desaparecen 10020, 10021, 10038 y 10063.
3. Semgrep: de 6 a 0. `pytest`: 75/75, incluidas las 7 pruebas nuevas.

## 6. Limitaciones y cierre (Johan, ~1 min)
- La CSP todavía permite `style-src 'unsafe-inline'` por los `style="..."` de las plantillas (F-05, riesgo residual).
- El DAST fue pasivo y en localhost: no evalúa HTTPS/HSTS ni el comportamiento del LLM.
- Un pipeline en verde no significa que la app sea segura: Semgrep y ZAP corren en modo no bloqueante.
- Ninguna herramienta mide el riesgo central del proyecto, que es si el guardián deja pasar PII al LLM. Eso lo cubren nuestras pruebas propias.
> "Siguiente paso: quitar el modo no bloqueante cuando haya triage, activar CodeQL y Dependabot, y mover los estilos en línea a CSS."

---

## Comandos exactos de la demo

Preparar la versión **antes** (línea base `9844c90`) en una carpeta aparte, sin tocar la rama actual:

```bash
cd ~/fdsi-gp-04-pii-llm
git worktree add ../lab05-antes 9844c90
```

**Antes:** levantar la línea base en el puerto 8001 y revisar los encabezados.

```bash
cd ../lab05-antes
../fdsi-gp-04-pii-llm/.venv/bin/uvicorn app.main:app --port 8001
# en otra terminal:
curl -sI http://localhost:8001/
```

Se espera ver solo `content-type`, `etag` y `cache-control`, sin CSP ni X-Frame-Options.

**Después:** levantar la rama `security/lab-fsi` en el puerto 8000.

```bash
cd ~/fdsi-gp-04-pii-llm
.venv/bin/uvicorn app.main:app --port 8000
# en otra terminal:
curl -sI http://localhost:8000/
curl -sI http://localhost:8000/ | grep -iE "content-security|x-frame|x-content-type|referrer|permissions"
```

**Prueba de regresión:**

```bash
.venv/bin/python -m pytest -q tests/test_security_headers.py
```

**Informes ZAP** (se abren en el navegador):

```bash
open docs/evidencias/zap-antes.html
open docs/evidencias/zap-despues.html
```

**Al terminar**, borrar la carpeta temporal:

```bash
git worktree remove ../lab05-antes
```

---

## Preguntas probables del profesor

**¿Qué detectó y qué omitió cada herramienta?**
- *Semgrep (SAST):* detectó las acciones con tag mutable en los workflows. No reportó nada en Python, y lo verificamos: el SQL es parametrizado. No entiende la lógica de negocio, así que no sabe si un usuario puede ver la conversación de otro.
- *Gitleaks:* confirmó que no hay secretos en el historial. Solo detecta patrones conocidos, así que una llave con formato raro podría pasar.
- *pip-audit / Dependabot (SCA):* encontró certifi, filelock y setuptools. No sabe si el código vulnerable se ejecuta realmente: eso lo tuvimos que analizar nosotros.
- *ZAP (DAST pasivo):* encontró la falta de encabezados. Como es pasivo, no prueba inyecciones ni control de acceso, y sin HTTPS no evalúa TLS.

**¿Por qué un pipeline en verde no significa que la app sea segura?**
Semgrep corre con `|| true` y ZAP con `-I`, así que nunca fallan. Además, las herramientas solo encuentran lo que sus reglas conocen. El verde quiere decir "se ejecutó", no "no hay riesgos".

**¿Por qué aceptaron F-04 (filelock)?**
Es una dependencia transitiva de torch, huggingface_hub y tldextract, que usamos en la evaluación y no en la tienda. La mayoría de los CVE son de Windows o de tipos de lock que no usamos. La guía pide no actualizar a ciegas, así que queda documentado y se actualizará junto con el stack de evaluación.

**¿Qué es F-05?**
Es el riesgo residual de la CSP: `style-src` permite `'unsafe-inline'` porque las plantillas usan atributos `style="..."`. Los scripts sí quedan restringidos a `'self'`, y el CSS en línea es mucho menos peligroso que el JS en línea. La corrección completa es mover esos estilos a `styles.css`.

**¿Por qué `/docs` (Swagger) no tiene CSP?**
Swagger UI carga sus scripts desde un CDN y la CSP lo rompería. Igual recibe los demás encabezados. En producción se recomienda desactivarlo.

**¿Cómo validaron sin hacer daño?**
Solo usamos peticiones `HEAD`/`GET` con `curl` y el escaneo pasivo de ZAP, sobre nuestro propio localhost y con datos ficticios del seed. No hicimos fuerza bruta, ni ataques activos, ni pruebas contra la API del LLM.
