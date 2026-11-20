# Cómo correr Andes Market en otro computador

> 🔐 **Lab. 06 (F-07):** la contraseña del administrador ya no está en el repositorio. Cada equipo tiene la suya, aleatoria, en `secrets/env/app.env` (`APP_ADMIN_PASSWORD`), que nunca se sube. Si tenían una base vieja, la tienda rota la contraseña del admin al arrancar.
>
> ⚠️ Este archivo contiene contraseñas de **clientes de prueba**. Sirven solo para el ambiente local del seminario. Si suben el proyecto a un repositorio público, quiten este archivo o cambien las contraseñas.

## 1. Credenciales para entrar a la aplicación

| Rol | Correo | Contraseña | Qué puede hacer |
|---|---|---|---|
| **Administrador** | `admin@andesmarket.co` | Aleatoria: `APP_ADMIN_PASSWORD` en `secrets/env/app.env` (la crea `python -m scripts.setup_secrets`) | Todo lo de un cliente, más el **Centro de seguridad**, el **modo inseguro** del chat y la auditoría de cada mensaje |
| Cliente | `juan.perez@gmail.com` | `Juan#Andes2026` | Comprar, ver sus pedidos (AM-10231, AM-09874) y usar el chat |
| Cliente | `sara.arteaga@correo.edu.co` | `Sara#Andes2026` | Pedido AM-10458 |
| Cliente | `maria.rodriguez@outlook.com` | `Maria#Andes2026` | Pedido AM-10512 |
| Cliente | `andres.vivas@empresa.com.co` | `Andres#Andes2026` | Pedido AM-10577 |
| Cliente | `johan.beltran@hotmail.com` | `Johan#Andes2026` | Pedido AM-10603 |

También pueden crear cuentas nuevas desde la página, con "Ingresar" → "Regístrate".

Estas cuentas se crean solas la primera vez que arranca la tienda, a partir de `data/seed/usuarios_demo.json`. Si cambian una contraseña desde la página y la olvidan, borren la carpeta `data/db/` y al reiniciar todo vuelve a como está en esta tabla.

## 2. Qué NO necesitan copiar ni conocer

**Las llaves de cifrado y los tokens entre servicios** (carpeta `secrets/`) **no son contraseñas que deban saberse**. Cada computador genera las suyas con un comando (paso 3.5), y es mejor así: las llaves no deben viajar de un equipo a otro.

Solo hay una excepción. Si copian también la carpeta `logs/`, esos datos quedan ilegibles con llaves nuevas. No pasa nada grave: simplemente no la copien. (La bóveda ya no guarda nada en disco; si ven una carpeta `data/vault/` de versiones anteriores, se puede borrar.)

**Lo que NO deben copiar al otro PC:** `.venv/`, `secrets/`, `data/db/`, `data/vault/`, `logs/*.jsonl`.

## 3. Opción A — Con Python (recomendada para desarrollar)

**Requisitos:** Windows 10/11, Linux o macOS, e internet la primera vez (para descargar librerías).

1. **Copiar el proyecto**: la carpeta `fdsi-gp-04-pii-llm` (por USB, OneDrive o `git clone` si lo suben a GitHub).
2. **Instalar Python 3.12.** Python 3.13 y 3.14 todavía no son compatibles con spaCy. En Windows, en una terminal:
   ```bash
   py install 3.12
   ```
3. **Crear el entorno e instalar las librerías.** Desde la carpeta `fdsi-gp-04-pii-llm`:
   ```bash
   py -V:3.12 -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   En Linux o macOS: `python3.12 -m venv .venv` y `source .venv/bin/activate`.
4. **Descargar el modelo de idioma español** (una sola vez, unos 40 MB):
   ```bash
   python -m spacy download es_core_news_md
   ```
5. **Generar las llaves y tokens de este computador** (una sola vez):
   ```bash
   python -m scripts.setup_secrets
   ```
6. **Arrancar los 4 servicios:**
   ```bash
   python -m scripts.run_all
   ```
7. Abrir **http://127.0.0.1:8000** e ingresar con un usuario de la tabla de arriba.

Para detener todo: `Ctrl + C` en la terminal.

**Las siguientes veces** solo se necesita:

```bash
.venv\Scripts\activate
python -m scripts.run_all
```

## 4. Opción B — Con Docker (no requiere instalar Python)

**Requisitos:** Docker Desktop instalado y abierto. Para generar las llaves se necesita Python una vez; si no lo tienen, usen la opción A hasta el paso 5.

```bash
python -m scripts.setup_secrets
docker compose up -d --build
```

Abrir **http://localhost:8000**. Para detener: `docker compose down`.

La primera construcción tarda varios minutos. Las siguientes veces basta con `docker compose up -d`.

## 5. Opcional — Usar Claude como chatbot

No es necesario: por defecto el chat usa **Andi**, el modelo entrenado por el equipo, y no requiere ninguna clave.

Si quieren usar Claude:
1. Copien `.env.example` como `.env`.
2. Completen en `.env`:
   ```
   CHATBOT_LLM_PROVIDER=anthropic
   CHATBOT_ANTHROPIC_API_KEY=su-clave-de-anthropic
   ```

La clave de API es personal: no la escriban en este archivo ni la suban al repositorio (`.env` ya está excluido en `.gitignore`).

## 6. Problemas comunes

| Problema | Solución |
|---|---|
| `pip install` falla compilando paquetes | Están usando Python 3.13 o 3.14. Creen el entorno con Python 3.12 (paso 3.2) |
| "Los puertos [...] ya están en uso" | Quedó abierta otra ejecución o Docker. Ciérrenla (`Ctrl+C` o `docker compose down`) |
| "El asistente no está disponible" en el chat | Alguno de los servicios no arrancó. Revisen la terminal de `run_all` |
| La página se ve desactualizada | Recarguen con `Ctrl + F5` |
| Olvidaron una contraseña de prueba | Borren `data/db/` y reinicien: vuelven las de la tabla |
| Docker no descarga la imagen de Python (error de DNS) | Revisen la conexión y repitan `docker pull python:3.11-slim` |

## 7. Comandos útiles

```bash
pytest -q
python -m scripts.evaluate
python -m scripts.train_guardian
python -m scripts.train_bot
```

- `pytest -q`: corre las 68 pruebas automatizadas.
- `python -m scripts.evaluate`: corre la evaluación completa. Antes hay que instalar las dependencias de evaluación con `pip install -r requirements-eval.txt`.
- `python -m scripts.train_guardian`: reentrena el modelo guardián (unos 4 minutos).
- `python -m scripts.train_bot`: reentrena el chatbot Andi.
