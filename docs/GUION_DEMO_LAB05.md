# Guion de la demo — Lab. 05 (5 minutos, 2 personas)

Proyecto: FDSI-GP-04 — Andes Market · Rama: `security/lab-fsi` · Línea base: `9844c90`
Expositores: Johan y Camilo
Soporte: [SECURITY.md](SECURITY.md) · [REPORTE_HALLAZGOS.md](REPORTE_HALLAZGOS.md)

| Tiempo | Quién | Bloque |
|---|---|---|
| 0:00–1:00 | Johan | Problema e impacto |
| 1:00–2:30 | Johan | Evidencia (herramientas + validación manual) |
| 2:30–4:00 | Camilo | Corrección y nueva evidencia |
| 4:00–5:00 | Johan | Limitaciones y cierre |

---

## 1. Problema (Johan, ~30 s)
> "Andes Market es una tienda con un chatbot donde los clientes escriben datos personales: nombre, cédula, correo y celular, todos ficticios en este laboratorio. El guardián protege esos datos antes de enviarlos al LLM, y un panel de auditoría muestra paso a paso qué pasó con cada mensaje. El problema principal estaba en ese panel: la función `step()` decidía si escapaba un texto según si empezaba por `<div`. Además, con OWASP ZAP vimos que la página no tenía Content-Security-Policy, ni protección contra clickjacking, ni `nosniff`."

## 2. Impacto (Johan, ~30 s)
> "Es el hallazgo F-08, de severidad alta. Un mensaje del usuario o una respuesta del LLM que empezara por `<div` se insertaba en la página como HTML activo. La respuesta del LLM puede estar influida por terceros mediante inyección de prompt, así que un script inyectado podría leer la PII de la conversación. La falta de encabezados (F-01, severidad media) lo agravaba: sin CSP no había una segunda barrera que bloqueara ese script, y sin `X-Frame-Options` otro sitio podía meter la tienda en un iframe. Afecta sobre todo la confidencialidad y también la integridad."

## 3. Evidencia (Johan, ~1 min 30 s)
1. **CodeQL (F-08):** mostrar en GitHub **Security → Code scanning**. La alerta #3 es "DOM text reinterpreted as HTML", severidad alta, en `static/app.js`. Semgrep no lo detectó. Las otras dos alertas son expresiones regulares de bajo riesgo (F-09 mitigado y F-10 falso positivo).
2. **Pipeline:** mostrar la pestaña **Actions** → "Seguridad estática - SAST y secretos" (Semgrep + Gitleaks).
3. **Semgrep:** 6 hallazgos al inicio, todos en los workflows por usar acciones con tag mutable (F-02). En el código Python no encontró nada, y lo verificamos: las consultas SQL usan parámetros `?`.
4. **Gitleaks:** 0 secretos en los 8 commits del historial. `.env` y `secrets/` nunca se subieron.
5. **ZAP antes:** abrir `docs/evidencias/zap-antes.html`. Muestra 7 alertas, entre ellas 10020 (clickjacking), 10021 (nosniff), 10038 (CSP) y 10063 (Permissions-Policy).
6. **Validación manual (demo en vivo):** `curl -sI` a la versión de línea base (comandos abajo). No aparece ni `content-security-policy` ni `x-frame-options`.

## 4. Corrección (Camilo, ~45 s)
> "La corrección principal es F-08. En lugar de adivinar por el contenido, el HTML que arma nuestro propio código, como las etiquetas de los servicios, se marca de forma explícita con `trusted()`. Todo lo demás, incluidos el mensaje del usuario, la respuesta del LLM y el título, pasa siempre por `esc()`. El panel se ve igual que antes. Además, un middleware `security_headers` en `app/main.py` agrega CSP con `script-src 'self'` y `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy` y `Permissions-Policy` (F-01). También fijamos las acciones de GitHub a su SHA (F-02) y subimos `certifi` (F-03)."

## 5. Nueva evidencia (Camilo, ~45 s)
1. **Comparación con node** (comandos abajo) usando la entrada `<div><img src=x onerror=1>`: antes sale como HTML activo (`<div><img src=x onerror=1>`); después sale escapada (`&lt;div&gt;&lt;img src=x onerror=1&gt;`).
2. **Pruebas de regresión:** `tests/test_audit_panel_xss.py` (F-08) y `tests/test_security_headers.py` (F-01). `pytest`: 77 de 77 pruebas pasan, frente a 68 en la línea base.
3. `curl -sI` a la versión corregida: ahora aparecen los encabezados. En `docs/evidencias/zap-despues.html` ZAP baja de 7 a 4 alertas, y Semgrep pasa de 6 a 0.

## 6. Limitaciones y cierre (Johan, ~1 min)
- CodeQL solo analizó `main`, porque el Default setup solo analiza los Pull Requests hacia la rama principal. Por eso las 3 alertas siguen abiertas en GitHub hasta que el cambio llegue a `main`.
- La CSP todavía permite `style-src 'unsafe-inline'` por los `style="..."` de las plantillas (F-05, riesgo residual).
- El DAST fue pasivo y en localhost: no evalúa HTTPS/HSTS ni el comportamiento del LLM.
- Un pipeline en verde no significa que la app sea segura: Semgrep y ZAP corren en modo no bloqueante.
- Ninguna herramienta mide el riesgo central del proyecto, que es si el guardián deja pasar PII al LLM. Eso lo cubren nuestras pruebas propias.
> "CodeQL, Dependabot, secret scanning y push protection ya están activos desde el 2026-11-20. Siguiente paso: quitar el modo no bloqueante cuando haya triage y mover los estilos en línea a CSS."

---

## Comandos exactos de la demo

> **Nota sobre los puertos.** La evidencia registrada en `SECURITY.md`, `REPORTE_HALLAZGOS.md` y los informes ZAP se generó con la app en `http://localhost:8077`. En la demostración en vivo usamos puertos distintos para tener las dos versiones corriendo al mismo tiempo: **8001** para la línea base (antes) y **8000** para la versión corregida (después). El puerto no cambia el resultado: los encabezados dependen del código, no del puerto.

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

**Comparación con node (F-08):** ejecuta la función `step()` de cada versión con la entrada `<div><img src=x onerror=1>`.

```bash
cd ~/fdsi-gp-04-pii-llm
STEP='const src=require("fs").readFileSync(process.argv[1],"utf8");
const pick=(re)=>(src.match(re)||[""])[0];
eval([/const ESC = .*;/,/const esc = .*;/,/class TrustedHtml .*/,/const trusted = .*;/,/const asHtml = .*;/,/function step\([\s\S]*?\n    \}/].map(pick).join("\n"));
console.log(step("1. Lo que escribió el usuario","<div><img src=x onerror=1>"));'
node -e "$STEP" ../lab05-antes/static/app.js   # antes: <div><img src=x onerror=1>
node -e "$STEP" static/app.js                   # después: &lt;div&gt;&lt;img src=x onerror=1&gt;
```

**Pruebas de regresión:**

```bash
.venv/bin/python -m pytest -q tests/test_audit_panel_xss.py tests/test_security_headers.py
.venv/bin/python -m pytest -q   # 77 de 77
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

**¿Por qué Dependabot dio 0 alertas y pip-audit 20?**
`requirements.txt` usa rangos `>=` sin versiones fijas, así que Dependabot no sabe qué versión se instala y no puede compararla con los avisos. pip-audit revisa el entorno realmente instalado en el `.venv`, incluidas las dependencias transitivas.

**¿Cómo decidieron que el hallazgo de Gitleaks era un falso positivo?**
Revisamos el texto marcado: era el ejemplo de un exploit dentro de un aviso de `filelock` en `docs/evidencias/pip-audit.json`, con una ruta de víctima y un token de muestra, no una credencial del proyecto. Ignoramos solo ese hallazgo con su huella en `.gitleaksignore`, sin excluir la carpeta, para que siga vigilada.

**¿Qué detectó CodeQL que no detectó Semgrep?**
El XSS de F-08: CodeQL siguió el dato desde el mensaje del usuario y la respuesta del LLM hasta el `innerHTML` del panel de auditoría. Semgrep no lo reportó.
