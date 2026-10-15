"""
Arranca los cuatro servicios en procesos separados (sin Docker):

  tienda    http://127.0.0.1:8000   (pública: página web + API)
  guardián  http://127.0.0.1:8101   (solo escucha en 127.0.0.1)
  bóveda    http://127.0.0.1:8102   (solo escucha en 127.0.0.1)
  chatbot   http://127.0.0.1:8103   (solo escucha en 127.0.0.1)

Cada proceso recibe SOLO sus propias variables de entorno: el guardián no
ve la ruta de la llave privada, la tienda no ve ninguna llave, etc.

Uso:
    python -m scripts.run_all
"""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from scripts.setup_secrets import ROOT, read_env, setup

SERVICES = [
    ("guardian", "guardian.main:app", 8101),
    ("vault", "vault.main:app", 8102),
    ("chatbot", "chatbot.main:app", 8103),
    ("tienda", "app.main:app", 8000),
]

# Variables que NO deben heredarse a ningún servicio desde la consola.
_SCRUB = ("GUARDIAN_", "VAULT_", "CHATBOT_", "APP_")


def service_env(name: str) -> dict[str, str]:
    base = {k: v for k, v in os.environ.items() if not k.startswith(_SCRUB)}
    env_file = {"tienda": "app.env"}.get(name, f"{name}.env")
    base.update(read_env(ROOT / "env" / env_file))
    base["PYTHONIOENCODING"] = "utf-8"
    if name == "chatbot":
        # la API key de un LLM comercial (opcional, en .env) solo la recibe el chatbot
        dotenv = read_env(Path(".env")) if Path(".env").exists() else {}
        base.update({k: v for k, v in {**dotenv, **os.environ}.items() if k.startswith("CHATBOT_") and k != "CHATBOT_TOKEN"})
    return base


def wait_ready(port: int, timeout: float = 120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def _port_in_use(port: int) -> bool:
    import socket

    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> None:
    busy = [port for _, _, port in SERVICES if _port_in_use(port)]
    if busy:
        print(f"Los puertos {busy} ya están en uso. ¿Quedó abierta otra ejecución (o Docker)? Ciérrala e intenta de nuevo.")
        sys.exit(1)
    setup()
    if not Path("models/guardian_ner").exists():
        print("Falta el modelo guardián: entrenando (python -m scripts.train_guardian)...")
        subprocess.run([sys.executable, "-m", "scripts.train_guardian"], check=True)

    procs = []
    try:
        for name, target, port in SERVICES:
            host = "0.0.0.0" if name == "tienda" and "--public" in sys.argv else "127.0.0.1"
            procs.append(subprocess.Popen(
                [sys.executable, "-m", "uvicorn", target, "--host", host, "--port", str(port), "--log-level", "warning"],
                env=service_env(name),
            ))
            ok = wait_ready(port)
            print(f"  {name:9s} {'listo' if ok else 'NO RESPONDE'} en el puerto {port}", flush=True)
        print("\nAndes Market: http://127.0.0.1:8000   (Ctrl+C para detener)", flush=True)
        while all(p.poll() is None for p in procs):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
