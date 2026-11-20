# Guion de sustentación — Lab. 06 (5 minutos)

**Quién habla:** A = Johan · B = Camilo

**Tener abierto antes de empezar:**
- `docs/REPORTE_HALLAZGOS_LAB06.md`
- Una terminal con la app corriendo (`python -m scripts.run_all`)

---

### 1. Introducción — A (30 s)
"Analizamos nuestro proyecto, Andes Market: una tienda con un chatbot que protege los datos personales antes de enviarlos al LLM. Hicimos SAST, SCA, detección de secretos y DAST. Encontramos y corregimos 7 hallazgos. Les contamos los más importantes."

### 2. Secretos — B (1 min 15 s)
- **Qué:** la contraseña del administrador estaba escrita en el repositorio, y el repositorio es público. Cualquiera podía entrar como admin.
- **Cómo:** Gitleaks no la detectó. La encontramos revisando el código y comprobamos que funcionaba: el login respondía 200.
- **Solución:** ahora la contraseña es aleatoria y vive en `secrets/`, que no se sube a git. Además creamos una regla propia de Gitleaks para detectar esto.
- **Validación (en vivo):** correr `python -m scripts.dast_manual` y mostrar que la prueba D-01 ahora da 401.

### 3. SAST — A (1 min)
- **Qué:** un XSS en el panel de auditoría. Se mostraba como HTML cualquier texto que empezara por `<div`, incluso la respuesta del LLM.
- **Cómo:** Semgrep no encontró nada; lo vimos revisando el código. Bandit marcó 3 consultas SQL, pero son falsos positivos porque usan parámetros. También marcó los códigos de pedido hechos con `random`, y ese aviso sí aplicaba.
- **Solución:** solo se pinta como HTML lo que marcamos como seguro; todo lo demás se escapa. Los códigos de pedido ahora usan `secrets`.
- **Validación:** pruebas automáticas nuevas.

### 4. SCA — B (1 min)
- **Qué:** 21 vulnerabilidades en 4 librerías. Lo interesante: `certifi` ya estaba corregido en `requirements.txt` desde el Lab. 05, pero nunca reinstalamos el entorno.
- **Cómo:** pip-audit y Trivy. Revisamos si cada vulnerabilidad nos afectaba de verdad.
- **Solución:** actualizamos las librerías y el Dockerfile.
- **Validación:** pip-audit pasó de 21 a 0.

### 5. DAST — A (55 s)
- **Qué:** ZAP no encontró fallas graves, solo avisos; corregimos dos encabezados que faltaban. Como ZAP no inicia sesión, hicimos 11 pruebas propias. Con ellas vimos que en "cambiar contraseña" se podía adivinar la contraseña actual sin límite.
- **Solución:** ahora se bloquea a los 5 intentos.
- **Validación:** las 11 pruebas pasan. También comprobamos que un cliente no puede ver pedidos ajenos ni entrar a las páginas de admin.

### 6. Cierre — B (20 s)
"Pasamos de 75 a 84 pruebas, todas en verde. Lo que más aprendimos: las herramientas automáticas no encontraron los dos problemas más graves. Hizo falta revisar el código y probar la app con sesión iniciada."

---

### Si el profesor pregunta…
- **¿Por qué no borraron la contraseña del historial de git?** Porque ya la cambiamos y la vieja no sirve. Borrarla del historial no garantiza nada: alguien pudo haber clonado el repo antes.
- **¿Por qué el XSS es media y no alta?** Porque la CSP bloquea los scripts. Aun así se podía meter HTML falso, y lo corregimos.
- **¿Y las contraseñas de los clientes de prueba?** Son datos ficticios para la demo local. Es un riesgo aceptado y documentado.
