# Plan de trabajo — FDSI-GP-04 (2 sprints)

## Contexto
- El Hito 1 (Propuesta Estructurada) ya fue aprobado, el 05/09.
- La propuesta dice que el proyecto debe estar listo antes del 26/09/2026.
- La meta de estos dos sprints era tener algo que funcione de principio a fin, aunque no se alcanzaran a pulir todos los detalles. Mejor tener Unsecure y Secure funcionando con pruebas sólidas, que tener muchas pruebas a medias.

## Sprint 1 — Flujo Unsecure (línea base)
Objetivo: tener el escenario "Unsecure" de la propuesta funcionando de principio a fin: el mensaje del usuario se manda al LLM sin ningún filtro y queda guardado en un log de texto plano. Este escenario es la base con la que se compara todo lo demás en el Sprint 2.

Lo que se hizo:
1. Estructura del proyecto (servidor, configuración, dependencias).
2. Un endpoint que recibe el mensaje, lo manda tal cual al LLM (o a un simulador si no hay conexión a un LLM real) y guarda la conversación completa, incluyendo el dato personal, en un archivo de log.
3. Un conjunto de 24 mensajes de prueba con datos personales colombianos en distintos formatos (cédulas, teléfonos, correos, nombres, direcciones), que sirve tanto para probar el Sprint 1 como para evaluar el Sprint 2.
4. Pruebas automatizadas que confirman que, en este escenario, el mensaje llega completo al LLM y el log queda sin ningún filtro.

## Sprint 2 — Flujo Secure y evaluación
Objetivo: construir el módulo que detecta y protege los datos personales, y comparar los resultados de Secure contra Unsecure con las pruebas y métricas de la propuesta.

Lo que se hizo:
1. Un módulo que detecta datos personales (nombres, cédulas, teléfonos, correos) en el mensaje, usando reconocimiento de texto en español más reglas propias para los formatos colombianos.
2. Un endpoint que anonimiza el mensaje antes de mandarlo al LLM, guarda en el log solo la versión anonimizada (nunca el dato real), guarda aparte y cifrado el mapeo entre los marcadores y los datos reales, y solo le devuelve el dato real al usuario legítimo en la respuesta final.
3. Pruebas automatizadas que confirman ese comportamiento (9 de 9 pruebas pasan en total, contando las del Sprint 1).
4. Un script de evaluación que corre los mensajes de prueba y calcula las métricas que pedía la propuesta, con una gráfica de resultados.
5. Pendiente: redactar el documento formal de entrega, si el seminario pide uno aparte de este repositorio.

### Resultados obtenidos (el detalle completo está en el README)
Detección de datos personales: 1.00. Falsos positivos: 0.00. Datos que se filtran hacia el LLM: 0. Tiempo extra que toma el filtro: unos 41 milisegundos. Los cuatro resultados están dentro de lo que pedía la propuesta. La métrica de "utilidad de la respuesta" dio 1.00, pero es una aproximación porque se probó con un LLM simulado, no uno real (ver limitaciones abajo).

### Limitaciones que quedaron pendientes
- No se detectan direcciones todavía, solo nombres, cédulas, teléfonos y correos. El dataset de prueba trae 3 casos de direcciones que hoy no se detectan.
- La métrica de utilidad de la respuesta habría que volver a calcularla con un LLM real para que sea una medición exacta.
