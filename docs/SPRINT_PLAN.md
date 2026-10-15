# Plan de trabajo — FDSI-GP-04

## Sprint 1 — Flujo Unsecure (línea base)
Objetivo: el escenario "Unsecure" funcionando de principio a fin. El mensaje se manda al LLM sin filtro y queda en un log de texto plano.

1. Estructura del proyecto (FastAPI, configuración, dependencias).
2. Endpoint `/unsecure/chat` que reenvía el mensaje tal cual y guarda la conversación completa en `logs/unsecure_raw.jsonl`.
3. Dataset inicial de mensajes con datos personales colombianos.
4. Pruebas automatizadas del comportamiento inseguro (T01 y T02).

## Sprint 2 — Flujo Secure y primera evaluación
1. Detección con Presidio + spaCy y reglas para cédula y teléfono colombianos.
2. Endpoint `/secure/chat`: anonimización, log anonimizado, mapping cifrado aparte y reidentificación de la respuesta final.
3. Pruebas T01–T03 en modo seguro.
4. Primer script de evaluación.

Limitaciones que quedaron de este sprint: no se detectaban direcciones; la evaluación dejaba las direcciones fuera del recall y de la fuga; la utilidad se medía con `difflib` sobre un LLM que solo hacía eco; solo había 3 mensajes de control.

## Sprint 3 — Sitio simulado, asistente entrenado y evaluación corregida
Objetivo: cumplir la idea completa del proyecto. Una página web simulada con un chatbot de IA entrenado que identifica y protege la información sensible, medida con las métricas de la propuesta.

1. **Página web simulada** (Andes Market) con chat, selector de modo seguro o inseguro, auditoría por mensaje y panel de auditoría con métricas, logs y datos de prueba.
2. **Asistente Andi entrenado**: clasificador de intenciones (TF-IDF + regresión logística) con un corpus propio aumentado con datos sintéticos y con marcadores. Mantiene historial, lo que permite probar T03 de forma real.
3. **Sistema de pedidos ficticio** y herramienta `consultar_pedido`: el backend traduce el marcador al dato real solo para la consulta interna (T05).
4. **Mejoras al módulo de protección:**
   - Direcciones colombianas, nombres por contexto o en minúsculas, nombres en MAYÚSCULAS solo con contexto, y correos ofuscados.
   - Marcadores en orden de aparición y consistentes en toda la conversación.
   - Detecciones superpuestas unidas en un solo tramo, para que no quede ningún pedazo expuesto.
   - Guardia de salida sobre la respuesta del modelo.
   - Reidentificación que pasa por el almacén cifrado y se limita al mapping de la propia sesión.
   - Llave de cifrado fuera de `data/`.
5. **Evaluación corregida**: recall por entidad que incluye direcciones, FP/(FP+VN) sobre 15 mensajes de control, fuga medida en el payload real, utilidad con embeddings multilingües, T03 y T05 automatizados, y un conjunto hold-out medido antes de ajustar.
6. 40 pruebas automatizadas, Docker con el modelo de spaCy y el bot entrenado, y documentación.

## Sprint 4 — Separación de servicios y modelo guardián entrenado
Objetivo: atender la observación del profesor. El modelo de IA debe ser externo a la aplicación, y entre la app y el chatbot debe haber otro modelo entrenado que detecte y cifre los datos personales sin poder acceder a ellos después.

1. **Cuatro servicios separados:** tienda (monolito, sin llaves), guardián, bóveda y chatbot. Hablan por HTTP con un token por servicio.
2. **Modelo guardián propio:** NER de spaCy entrenado desde cero con 6.000 frases sintéticas (`guardian/training/`). Modo híbrido: el modelo propone y las reglas de validación confirman.
3. **Cifrado asimétrico** (sealed box X25519 de libsodium): el guardián solo tiene la llave pública y la bóveda la privada. Índice ciego con HMAC y pimienta para marcadores consistentes.
4. **Bóveda:** asigna marcadores, reidentifica solo la conversación propia, descifra para propósitos autorizados y lleva una bitácora de accesos.
5. **Chatbot Andi como servicio externo,** reemplazable por Claude o GPT.
6. **Docker con redes aisladas:** guardián y bóveda sin internet; guardián con disco de solo lectura; chatbot sin acceso a la bóveda. Verificado desde dentro de los contenedores.
7. **Evaluación** del guardián en tres modos (modelo, reglas, híbrido) sobre el conjunto principal y el hold-out, y del sistema completo con HTTP real. 50 pruebas automatizadas, incluidas las de aislamiento.

## Sprint 5 — Tienda completa con cuentas de usuario
Objetivo: que la aplicación sea una tienda real y no una página de prueba, y que cada conversación pertenezca a un usuario autenticado.

1. **Base de datos SQLite** (`app/db.py`) con usuarios, sesiones, productos, carrito y pedidos, llenada desde `data/seed/`.
2. **Inicio de sesión y registro:** contraseñas con scrypt, cookie de sesión HttpOnly/SameSite con token guardado como hash, límite de intentos fallidos y cambio de contraseña. Roles `cliente` y `admin`.
3. **Chat ligado al usuario:** el id de conversación lo genera el servidor y solo lo usa su dueño. Se corrigió que antes se aceptaba un id inventado por el cliente.
4. **Control de acceso a pedidos:** cada cliente solo consulta sus pedidos, también por el chat (evita IDOR). Si pregunta por "mi pedido" sin datos, se usa la cuenta con sesión iniciada.
5. **Nueva interfaz:** inicio, catálogo con filtros y búsqueda, ficha de producto, carrito, compra, mis pedidos con seguimiento, mi cuenta, ingreso y registro, e imágenes de los 12 productos.
6. **Demostración separada:** el modo inseguro, la auditoría por mensaje y el Centro de seguridad quedan solo para el administrador.
7. 62 pruebas automatizadas; evaluación repetida con inicio de sesión (todas las metas se cumplen).

Los resultados están en el README y la explicación sencilla en `docs/COMO_FUNCIONA.md`.
