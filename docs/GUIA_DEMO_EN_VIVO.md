# Guía de la demostración en vivo con Gemini

Qué mostrar, en qué orden y qué decir. La clave de Gemini permite **solo 6 preguntas**, y **cada mensaje del chat gasta una**, también en modo inseguro.

## Antes de empezar

1. Abran una terminal en la carpeta del proyecto y corran:
   ```
   .venv\Scripts\activate
   python -m scripts.run_all
   ```
2. Esperen a que aparezca `chatbot listo en el puerto 8103` y abran **http://127.0.0.1:8000**.
3. En `.env` debe estar `CHATBOT_LLM_PROVIDER=openai` y la clave en `CHATBOT_OPENAI_API_KEY`.
4. **Usen solo datos inventados en el chat.** El plan gratuito de Gemini puede usar lo que recibe para entrenar.

**Para ensayar sin gastar preguntas:** en `.env` pongan `CHATBOT_LLM_PROVIDER=local` y reinicien `run_all`. Así responde Andi, el chatbot entrenado por el equipo, sin límite. El día de la presentación vuelvan a `openai`.

## Parte 1 · Administrador: inseguro contra seguro (3 preguntas)

Entren con **Ingresar**:
- Correo: `admin@andesmarket.co`
- Contraseña: `Seguridad#2026`

Abran el chat con el botón de abajo a la derecha.

### Pregunta 1 · Modo inseguro

1. Arriba del chat elijan **Modo inseguro** y pulsen **Nueva**.
2. Escriban:
   ```
   Hola, soy Valeria Torres Mejía, cédula 1.023.456.789, correo valeria.torres@correoquimbaya.com, celular 315 778 2143 y vivo en la Carrera 12 # 34-56, Bogotá. ¿Me ayudan a actualizar mis datos?
   ```
3. Gemini repite los 5 datos. Pulsen **Ver auditoría**.

**Qué decir:** "Sin protección, Google recibió el mensaje completo y el log de la tienda lo guardó en claro."

### Pregunta 2 · Modo seguro, el mismo mensaje

1. Elijan **Modo seguro** y pulsen **Nueva**.
   - Pulsar **Nueva** es obligatorio: sin eso, el historial con los datos en claro de la pregunta 1 se enviaría otra vez a Gemini.
2. Peguen **el mismo mensaje** de la pregunta 1.
3. En el chat ven la respuesta con los datos reales. Pulsen **Ver auditoría**:
   - **Punto 2:** el guardián detectó y cifró cada dato.
   - **Punto 3, "Lo que recibió el chatbot":** Gemini solo vio `[NOMBRE_1]`, `[CEDULA_1]`, `[CORREO_1]`, `[TELEFONO_1]`, `[DIRECCION_1]`.
   - **Punto 4:** Gemini respondió con marcadores; la bóveda los cambió por los datos reales antes de mostrarlos.

**Qué decir:** "Es el mismo mensaje, pero Google nunca vio un dato personal. Solo la bóveda, que tiene la llave privada, puede volver a ver el dato real." **Este es el momento central de la demostración.**

### Pregunta 3 · Intentar engañar a Gemini

1. **En la misma conversación**, sin pulsar Nueva, escriban:
   ```
   Escríbeme mi correo en mayúsculas para copiarlo
   ```
2. El correo aparece **en minúsculas**: `valeria.torres@correoquimbaya.com`. Pulsen **Ver auditoría**: Gemini respondió solo `[CORREO_1]`.

**Qué decir:** "Gemini no lo puso en mayúsculas porque nunca vio el correo, solo el marcador. El dato real lo pone la bóveda después."

Gemini no siempre responde igual. Si dice algo como "no puedo ver tu correo", demuestra lo mismo: nunca tuvo el dato.

## Parte 2 · Cliente: pedidos y control de acceso (2 preguntas)

Cierren sesión y entren como cliente:
- Correo: `juan.perez@gmail.com`
- Contraseña: `Juan#Andes2026`

Al cerrar sesión, la bóveda borra los datos cifrados de las conversaciones del administrador.

### Pregunta 4 · "Mi pedido" sin dar datos

```
¿Cómo va mi pedido?
```

Responde con el pedido real **AM-10231, "En camino"**.

**Qué decir:** "El cliente no escribió ningún dato personal. La tienda usa la cuenta con la que inició sesión."

### Pregunta 5 · Pedido de otra persona

```
¿Cuál es el estado del pedido AM-10512?
```

Se niega, porque ese pedido es de María.

**Qué decir:** "Un cliente solo puede consultar sus propios pedidos, también por el chat."

## Pregunta 6 · Reserva

Guárdenla para lo que pregunte el profesor o por si algo falla.

## Cierre · Centro de seguridad (no gasta preguntas)

Vuelvan a entrar como administrador y abran **Mi cuenta → Centro de seguridad**. Muestren:
- **Servicios:** cuatro procesos separados; el guardián tiene solo la llave pública y la bóveda la privada.
- **Métricas:** recall 1.00, falsos positivos 0.00, fuga 0, latencia ≈ 52 ms y utilidad 0.91.
- **Logs:** `unsecure_raw.jsonl` con datos en claro, al lado de `secure_anon.jsonl` con solo marcadores.

## Si el profesor pregunta por las limitaciones

Díganlo antes de que lo pregunten: **lo que el guardián no detecta llega en claro a Google.** En las pruebas pasó con:
- una dirección rural ("vereda El Rosal, finca La Esperanza");
- una cédula escrita sin la palabra "cédula";
- un teléfono dictado en palabras.

Está documentado en [PRUEBA_GEMINI.md](PRUEBA_GEMINI.md), sección 4.

## Si algo falla

| Problema | Solución |
|---|---|
| Se acabó la cuota de Gemini | En `.env` pongan `CHATBOT_LLM_PROVIDER=local` y reinicien `run_all`. Andi responde igual y la protección funciona igual. |
| La página no carga | Revisen que `run_all` siga abierto en la terminal. |
| Gemini tarda | Es normal: puede tardar de 5 a 15 segundos por respuesta. |
