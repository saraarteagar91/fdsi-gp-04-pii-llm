# Cómo funciona el proyecto (explicado fácil)

## 1. La idea en una frase

La tienda le pasa cada mensaje a un **guardián** (un modelo de IA que entrenamos nosotros). El guardián encuentra los datos personales y los **cifra con un candado que él mismo no puede abrir**. Al **chatbot** solo le llegan marcadores como `[CORREO_1]`, y la única que tiene la llave para abrir el candado es la **bóveda**.

## 2. Las cuatro piezas

Piensa en una oficina con cuatro personas que no confían entre sí:

| Pieza | Analogía | Qué hace | Qué no puede hacer |
|---|---|---|---|
| **Tienda** | La recepcionista | Recibe al cliente, maneja cuentas, carrito y pedidos, coordina todo | No tiene llaves: no puede descifrar nada por su cuenta |
| **Guardián** | El que mete las cartas en sobres sellados | Lee el mensaje, encuentra los datos personales y los mete en un "sobre" cifrado | No puede abrir los sobres (solo tiene la llave pública), no guarda nada, no tiene internet |
| **Bóveda** | La caja fuerte | Guarda los sobres; es la única con la llave para abrirlos | No lee mensajes ni habla con el chatbot |
| **Chatbot (Andi)** | El asesor que atiende | Conversa con el cliente | Nunca ve datos reales, solo `[NOMBRE_1]`, `[CORREO_1]`… |

## 3. La tienda por dentro: usuarios y base de datos

- **Base de datos:** SQLite, en el archivo `data/db/andes_market.db`. Guarda usuarios, sesiones, productos, carritos y pedidos. Se crea sola la primera vez, con los datos de `data/seed/`.
- **Inicio de sesión:**
  - La contraseña nunca se guarda; solo su "huella" scrypt.
  - Al entrar, el navegador recibe una cookie que JavaScript no puede leer.
  - Si alguien falla 5 veces seguidas, ese correo se bloquea 15 minutos.
- **Dos roles:**
  - **Cliente:** compra, ve *sus* pedidos y usa el chat siempre en modo seguro.
  - **Administrador:** además ve el Centro de seguridad y puede usar el modo inseguro en el chat para la demostración.
- **El chat es de quien inició sesión.** Cada conversación le pertenece a un usuario. Aunque alguien copie el código de otra conversación, el servidor no se la entrega.
- **"¿Dónde está mi pedido?"** funciona sin escribir ningún dato: la tienda sabe quién inició sesión y busca su último pedido. Si un cliente escribe el código o el correo de **otra** persona, el sistema responde que no encuentra ese pedido en su cuenta.

Los usuarios de prueba y sus contraseñas están en `data/seed/usuarios_demo.json`.

## 4. Qué pasa con un mensaje, paso a paso

El usuario escribe: *"Hola, soy Juan, mi correo es juan@gmail.com, ¿cómo va mi pedido?"*

1. **Tienda → Guardián.** El guardián lee el texto y encuentra `Juan` (NOMBRE) y `juan@gmail.com` (CORREO). Cifra cada dato con la **llave pública** y devuelve solo esto: "en la posición 11 a 15 hay un NOMBRE, este es el sobre cifrado". Nunca devuelve el dato en claro. Después lo olvida.
2. **Tienda → Bóveda.** La bóveda guarda los sobres y asigna los marcadores `[NOMBRE_1]` y `[CORREO_1]`. Si en otro mensaje aparece el mismo correo, le da el mismo marcador. Lo reconoce por un "índice ciego", una huella con clave secreta, sin abrir el sobre.
3. **La tienda cambia** los datos por los marcadores: *"Hola, soy [NOMBRE_1], mi correo es [CORREO_1], ¿cómo va mi pedido?"*
4. **Tienda → Chatbot.** Solo viaja ese texto con marcadores. Andi responde: *"Claro [NOMBRE_1], reviso el pedido de [CORREO_1] {{consultar_pedido:[CORREO_1]}}"*.
5. **Tienda → Guardián (guardia de salida).** Revisa que el chatbot no haya inventado datos personales. Si los hay, los borra.
6. **Consulta del pedido.** Para buscar el pedido hace falta el correo real. La tienda se lo pide a la bóveda **con un propósito autorizado** ("consultar_pedido"). La bóveda abre ese sobre, lo anota en su bitácora y la tienda busca el pedido. El resultado ("AM-10231, en camino") no tiene datos personales.
7. **Log.** Se guarda solo la versión con marcadores.
8. **Tienda → Bóveda → Usuario.** La bóveda cambia los marcadores por los datos reales, **solo los de esa conversación**, y el usuario ve: *"Claro Juan, reviso el pedido de juan@gmail.com. Tu pedido AM-10231 está en camino."*

## 5. El reto del profesor y cómo lo resolvimos

> "El modelo que cifra tampoco puede tener acceso a la información."

Detectar un dato sin leerlo es imposible. Por eso el guardián lo ve un instante, pero se diseñó para **no poder aprovecharlo**:

| Riesgo | Cómo se evita | Cómo se comprobó |
|---|---|---|
| Que el guardián descifre después | Cifrado **asimétrico**: el guardián solo tiene la llave pública; la privada está únicamente en la bóveda | Prueba automática: intentar descifrar con la llave pública falla. `/health` del guardián dice `puede_descifrar: false` |
| Que el guardián guarde el dato | Sin base de datos ni logs; en Docker su disco es de **solo lectura** | Prueba que bloquea cualquier escritura de archivos; dentro del contenedor, `touch` → "Read-only file system" |
| Que el guardián lo envíe afuera | Red interna **sin internet** y sin acceso a los otros servicios | Desde el contenedor: pypi.org, bóveda y chatbot → BLOQUEADO |
| Que el guardián "aprenda" datos reales | Entrenado **solo con datos sintéticos inventados** y nunca se reentrena con lo que escriben los usuarios | El generador `guardian/training/synth.py` arma nombres, cédulas, etc. al azar |
| Que el chatbot llegue a la bóveda | Redes separadas | Desde el contenedor del chatbot: bóveda → BLOQUEADO |
| Que cualquiera use los servicios | Cada servicio exige su token | Sin token → 401 |
| Que un usuario vea datos de otro | La bóveda solo reidentifica marcadores de la conversación indicada | Prueba con otra sesión: el marcador no se revela |

Además, el mismo correo no se guarda con un hash simple, porque una cédula se podría adivinar probando todas las combinaciones. Se usa un **HMAC con pimienta secreta**, que solo tiene el guardián.

## 6. Los dos modelos entrenados por el equipo

**Guardián (detector de datos personales):**
- Es una red neuronal de spaCy (NER) entrenada **desde cero**.
- Se entrenó con 6.000 frases sintéticas y se validó con 1.000, en 14 épocas y unos 4 minutos en un portátil.
- Detecta NOMBRE, CEDULA, TELEFONO, CORREO y DIRECCION.
- Pesa 4 MB y corre sin internet.
- Se combina con reglas de validación: el modelo propone y las reglas confirman (por ejemplo, "un celular tiene 10 dígitos y empieza por 3"). Ese es el modo **híbrido**.

**Andi (chatbot):**
- Clasificador de intenciones (TF-IDF + regresión logística) con 15 intenciones y 374 ejemplos.
- Exactitud de 84,5 % en validación cruzada.
- Se entrenó con mensajes crudos y con marcadores, así que entiende igual los dos modos.
- Si se quiere, se cambia por Claude o GPT sin tocar nada más.

## 7. Resultados que pueden mostrar

| | Resultado | Meta de la propuesta |
|---|---|---|
| Recall de detección | 100 % | ≥ 90 % |
| Falsos positivos | 0 % | ≤ 10 % |
| Datos que llegan al chatbot | 0 | 0 |
| Tiempo extra por la protección (4 servicios por red) | ≈ 52 ms | ≤ 500 ms |
| Utilidad de la respuesta | 91 % | ≥ 80 % |
| T05: consultas de pedido correctas en modo seguro | 10/10 | igual que el modo inseguro |

El dato que mejor muestra el valor del modelo entrenado, medido con 30 mensajes que nunca vio:

| | Recall en casos nuevos |
|---|---|
| Solo reglas (como estaba antes) | 75 % |
| Solo el modelo entrenado | **95,8 %** |

## 8. Cómo hacer la demostración

1. `python -m scripts.run_all` (o `docker compose up`) y abrir http://127.0.0.1:8000.
2. **Como cliente** (por ejemplo Juan; las contraseñas están en `data/seed/usuarios_demo.json`):
   - comprar un producto: agregar al carrito → finalizar compra → ver el pedido en «Mis pedidos»;
   - en el chat, preguntar "¿Dónde está mi pedido?": responde con su pedido sin que haya escrito ningún dato;
   - preguntar por el pedido de otra clienta, "¿Cómo va el pedido AM-10458?": se niega.
3. **Como administrador:** cerrar sesión e ingresar con la cuenta de administrador.
4. Abrir el chat en **modo inseguro**, pulsar "T01 Datos personales" y luego "Ver auditoría": el chatbot recibió todo en claro (en rojo).
5. Pulsar "Nueva", cambiar a **modo seguro** y repetir: el chatbot solo recibió marcadores (en verde), y se ve el sobre cifrado de cada dato.
6. Pulsar "T03 Resumen": el chatbot repite marcadores; el usuario ve sus datos completos.
7. Abrir **Mi cuenta → Centro de seguridad**:
   - el estado de los 4 servicios (el guardián dice "¿puede descifrar? No");
   - las métricas;
   - la comparación entre el modelo entrenado y las reglas;
   - los dos logs lado a lado.

## 9. Lo que todavía no hace

- No evita que el guardián vea el dato un instante. Para eso habría que detectar en el navegador del usuario o usar enclaves de hardware; es trabajo futuro y conviene mencionarlo en la sustentación.
- No detecta direcciones rurales ("vereda El Rosal, finca La Esperanza").
- Los pagos con PSE y tarjeta son simulados (no hay pasarela real) y no hay recuperación de contraseña por correo.
- No se probó con Claude real (no hay clave de API configurada).
