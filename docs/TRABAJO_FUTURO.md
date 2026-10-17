# Prueba con un LLM real (Gemini) y trabajo futuro

## 1. Qué se probó

Hasta ahora todas las métricas se habían medido con el asistente local Andi. Se hizo una primera prueba con un LLM real de un tercero: **Google Gemini** (`gemini-3.8-flash`, plan gratuito). Se conectó a través de su API compatible con OpenAI (`CHATBOT_OPENAI_BASE_URL`).

- **Solo se usaron datos ficticios.** El plan gratuito de Gemini puede usar lo que recibe para mejorar sus modelos. Por eso se hizo una copia temporal de los conjuntos de prueba en la que se cambiaron los nombres del equipo y todos los correos de dominios reales por valores inventados, con el mismo formato. Con esa copia, la detección del guardián da exactamente las mismas cifras que con los datos originales.
- **El plan gratuito permite solo 20 solicitudes al día por modelo.** Alcanzó para 26 interacciones de prueba, pero no para la evaluación completa (unas 130 llamadas).

## 2. Resultados

| Riesgo revisado | ¿Ocurrió con Gemini? |
|---|---|
| a) El LLM altera los marcadores (`[correo_1]`, traducidos…) | **No.** Se le pidió responder en inglés, escribir el correo en mayúsculas y saludar solo con el primer nombre, y siempre mantuvo los marcadores intactos |
| b) El LLM escribe mal `{{consultar_pedido:...}}` | **No.** 5 de 5 consultas de pedido correctas (por correo, cédula, código, "mi pedido" y con historial). Una vez llamó la herramienta **sin que le preguntaran por un pedido** |
| c) El LLM inventa datos personales | **No.** Se negó a inventarlos. En un ejemplo de formulario escribió `[NOMBRE_1]`, `[CEDULA_1]`… en una conversación donde esos marcadores no existían |
| d) El LLM repite en claro algo que el guardián no detectó | **Sí**, en los 3 casos medidos (sección 3) |

- **Latencia:** la protección (guardián, bóveda y reemplazos) añadió en promedio **≈ 40 ms** por mensaje, con un máximo de 71 ms. Gemini tardó entre 3,6 y 15,6 s por respuesta (mediana 6,1 s).
- **Comparación lado a lado** (mismo mensaje):
  - **Modo inseguro:** Gemini recibió `Hola, soy Valeria Torres Mejía, cédula 1.023.456.789, correo valeria.torres@correoquimbaya.com, celular 315 778 2143 y vivo en la Carrera 12 # 34-56, Bogotá…` y repitió los 5 datos en su respuesta.
  - **Modo seguro:** el texto que habría recibido es `Hola, soy [NOMBRE_1], cédula [CEDULA_1], correo [CORREO_1], celular [TELEFONO_1] y vivo en la [DIRECCION_1]…`. Esta llamada no alcanzó a enviarse por el límite diario; el texto se generó en local con el mismo guardián, y no depende del LLM.

## 3. Riesgo d: lo que el guardián no detecta llega en claro al LLM

Este es el hallazgo principal. **El modo seguro solo protege lo que el guardián detecta.** Si un dato no se detecta, viaja en claro a Google. Además, el LLM lo repite en su respuesta y la repetición queda en el log "anonimizado".

En los tres casos, Google recibió además el *prompt* de sistema de Andi y, en el segundo turno, el historial de la conversación, que contenía el primer turno tal como se muestra abajo.

### Caso d1: dirección rural

| | Texto |
|---|---|
| **Mensaje 1 del usuario** | `Envíenlo a la vereda El Rosal, finca La Esperanza, Guasca` |
| **Dato que se escapó** | La dirección rural `vereda El Rosal, finca La Esperanza, Guasca`. El guardián no reconoce direcciones sin nomenclatura urbana (calle, carrera, #) |
| **Lo que recibió Google** | `Envíenlo a la vereda El Rosal, finca La Esperanza, Guasca` (completo, sin ningún marcador) |
| **Respuesta de Gemini** (quedó en el log) | `¡Con gusto! Para actualizar la dirección de entrega de tu pedido a la vereda El Rosal, finca La Esperanza en Guasca, por favor compárteme tu número de pedido (ej. AM-xxxxx) o tu correo registrado. […]` |
| **Mensaje 2 del usuario** | `Repíteme la dirección de envío para confirmar` |
| **Respuesta de Gemini** (quedó en el log) | `La dirección que me indicaste es: **Vereda El Rosal, finca La Esperanza, Guasca.** […]` |

### Caso d2: cédula sin prefijo

| | Texto |
|---|---|
| **Mensaje 1 del usuario** | `el número es 79845123, regístralo como mi identificación` |
| **Dato que se escapó** | La cédula `79845123`. Un número suelto, sin "cédula", "C.C." ni puntos, no se marca a propósito, para no tapar cualquier número. Aquí la palabra "identificación" viene después del número y el guardián no la usa como contexto |
| **Lo que recibió Google** | `el número es 79845123, regístralo como mi identificación` (completo) |
| **Respuesta de Gemini** (quedó en el log) | `¡Hola! He registrado el número 79845123 como tu documento de identificación. ¿Hay algo más en lo que te pueda ayudar hoy?` |
| **Mensaje 2 del usuario** | `¿Qué número de identificación te di?` |
| **Respuesta de Gemini** (quedó en el log) | `Me proporcionaste el número 79845123. ¿Deseas consultar algún pedido o necesitas ayuda con algo más?` |

### Caso d3: teléfono dictado en palabras

| | Texto |
|---|---|
| **Mensaje 1 del usuario** | `me pueden llamar al tres cero cero, cuatro cinco seis, siete ocho nueve cero` |
| **Dato que se escapó** | El celular `300 456 7890`, escrito en palabras. El guardián solo reconoce teléfonos escritos con dígitos |
| **Lo que recibió Google** | `me pueden llamar al tres cero cero, cuatro cinco seis, siete ocho nueve cero` (completo) |
| **Respuesta de Gemini** | `¡Hola! Por este canal no realizamos llamadas telefónicas, pero con mucho gusto puedo ayudarte por aquí. […]` (no lo repitió) |
| **Mensaje 2 del usuario** | `Repíteme mi número de contacto` |
| **Respuesta de Gemini, después de la guardia de salida** (quedó en el log) | `El número que nos indicaste es [DATO_REDACTADO]. […]` |

En el caso d3, **Gemini convirtió las palabras en dígitos** al responder, y entonces la guardia de salida sí lo reconoció y lo borró (`redacciones: TELEFONO`). El log quedó limpio, pero **el número ya había llegado a Google** en el primer mensaje. No se guardó el texto exacto de Gemini antes de la guardia; solo se sabe que contenía un teléfono.

**Un cuarto caso quedó incompleto por el límite diario.** El nombre de un tercero en minúsculas (`mi mamá, doña gloria inés vargas, va a recibir el paquete`) también llegó en claro a Google. No se alcanzó a medir si Gemini lo repetía.

**Por qué importa:** el recall de 1.00 se midió sobre los conjuntos de evaluación, y esos conjuntos no incluyen estos formatos. Con un LLM real, cada formato que el guardián no conoce es una fuga hacia el tercero.

## 4. Trabajo futuro (no aplicado todavía)

**Guardián**
1. Reconocer la cédula por contexto aunque no tenga prefijo, cuando aparecen "identificación", "documento" o "número de documento" cerca, antes o después del número.
2. Pasar a dígitos los números dictados en palabras ("tres cero cero…") antes de detectar, y luego volver a ubicar la posición en el texto original.
3. Reconocer direcciones rurales: vereda, finca, corregimiento, kilómetro, vía.
4. Reconocer nombres de terceros después de expresiones de parentesco o trato: "mi mamá", "mi esposo", "doña", "don".
5. Agregar estos formatos a los datos sintéticos de entrenamiento y a los conjuntos de prueba, para que el recall los incluya.

**Instrucciones al LLM (Gemini)**
6. Llamar `consultar_pedido` solo cuando el usuario pregunte por un pedido. Hoy la llamó cuando el usuario solo había dado su correo, y la bóveda descifró ese dato sin necesidad.
7. No escribir marcadores que no aparecen en la conversación; usar textos como "[tu nombre]".

**Tienda**
8. Reemplazar por un texto genérico los marcadores que la bóveda no reconoce para esa conversación, para que el usuario no vea `[NOMBRE_1]` crudo.
9. Mejorar la guardia de salida: si el LLM repite en su respuesta una secuencia de 6 o más dígitos que venía en el mensaje del usuario, quitarla del log aunque el guardián no la haya detectado.

**Evaluación con un LLM real**
10. Correr `scripts/evaluate.py --live` completo con Gemini (unas 130 llamadas). Con el límite de 20 solicitudes al día hay que repartirlo en varios días o usar otro proveedor gratuito compatible con OpenAI. Faltan por medir con un LLM real: utilidad (similitud), T03 y T05 formales.
