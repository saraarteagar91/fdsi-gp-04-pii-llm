"""
Genera los secretos de cada servicio, cada uno en su propia carpeta, para
que ningún servicio reciba lo que no necesita:

  secrets/guardian/public.key   llave PÚBLICA (solo cifra)        -> guardián
  secrets/guardian/pepper.key   pimienta del índice ciego         -> guardián
  secrets/vault/private.key     llave PRIVADA (descifra)          -> bóveda
  secrets/env/<servicio>.env    tokens entre servicios
  secrets/env/app.env           + APP_ADMIN_PASSWORD (contraseña aleatoria
                                del administrador, Lab. 06 F-07)

La tienda recibe los tres tokens pero ninguna llave.

Uso:
    python -m scripts.setup_secrets           # crea lo que falte
    python -m scripts.setup_secrets --force   # rota todo (los datos cifrados viejos quedan ilegibles)
"""
import base64
import secrets
import sys
from pathlib import Path

from nacl.public import PrivateKey

ROOT = Path("secrets")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def setup(root: Path = ROOT, force: bool = False) -> dict[str, str]:
    private_path = root / "vault" / "private.key"
    public_path = root / "guardian" / "public.key"
    pepper_path = root / "guardian" / "pepper.key"
    if force or not private_path.exists():
        key = PrivateKey.generate()
        _write(private_path, base64.b64encode(bytes(key)).decode())
        _write(public_path, base64.b64encode(bytes(key.public_key)).decode())
    if force or not pepper_path.exists():
        _write(pepper_path, base64.b64encode(secrets.token_bytes(32)).decode())

    env_dir = root / "env"
    tokens_file = env_dir / "app.env"
    if force or not tokens_file.exists():
        tokens = {s: secrets.token_urlsafe(32) for s in ("guardian", "vault", "chatbot")}
        _write(env_dir / "guardian.env", f"GUARDIAN_TOKEN={tokens['guardian']}\n")
        _write(env_dir / "vault.env", f"VAULT_TOKEN={tokens['vault']}\n")
        _write(env_dir / "chatbot.env", f"CHATBOT_TOKEN={tokens['chatbot']}\n")
        _write(tokens_file, "".join(f"APP_{s.upper()}_TOKEN={t}\n" for s, t in tokens.items()))
    # Lab. 06 (F-07): la contraseña del administrador ya no está en el repo.
    # Se genera al azar aquí (también en instalaciones viejas que no la tienen).
    if "APP_ADMIN_PASSWORD" not in read_env(tokens_file):
        with tokens_file.open("a", encoding="utf-8") as f:
            f.write(f"APP_ADMIN_PASSWORD={secrets.token_urlsafe(18)}\n")
    return {"private": str(private_path), "public": str(public_path), "pepper": str(pepper_path)}


def read_env(path: Path) -> dict[str, str]:
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


if __name__ == "__main__":
    paths = setup(force="--force" in sys.argv)
    print("Secretos listos:")
    for name, p in paths.items():
        print(f"  {name:8s} {p}")
    print(f"  tokens   {ROOT / 'env'}")
    print(f"  admin    contraseña en {ROOT / 'env' / 'app.env'} (APP_ADMIN_PASSWORD)")
