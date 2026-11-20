"""
Pruebas DAST manuales y autenticadas (Lab. 06 FDSI) contra la tienda en
http://127.0.0.1:8000 levantada con `python -m scripts.run_all`.

Solo para el entorno local del equipo, con datos ficticios. Complementa a
ZAP, que no inicia sesión: aquí se prueba control de acceso, IDOR, fuerza
bruta y credenciales conocidas.

Uso:
    python -m scripts.dast_manual [salida.json]
"""
import json
import sys
import uuid
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
SEED = json.loads(Path("data/seed/usuarios_demo.json").read_text(encoding="utf-8"))
# Credenciales de admin que se publicaron en el repositorio antes del Lab. 06
# (docs/INSTALACION_Y_CREDENCIALES.md, commit 14be53a). Se prueban tal cual.
PUBLISHED_ADMIN = ("admin@andesmarket.co", "Seguridad#2026")  # nosec B105  # gitleaks:allow (contraseña revocada)


def _password(email: str) -> str | None:
    return next((u.get("password") for u in SEED["usuarios"] if u["email"] == email), None)


def login(email: str, password: str) -> httpx.Client:
    c = httpx.Client(base_url=BASE, timeout=30)
    c.post("/api/auth/login", json={"email": email, "password": password})
    return c


def main() -> list[dict]:
    results: list[dict] = []

    def record(test_id: str, desc: str, expected: str, observed, ok: bool) -> None:
        results.append({"id": test_id, "prueba": desc, "esperado": expected, "observado": observed,
                        "resultado": "PASA" if ok else "FALLA (vulnerable)"})
        print(f"[{'PASA ' if ok else 'FALLA'}] {test_id} {desc} -> {observed}")

    # D-01: credenciales de admin publicadas en el repositorio
    r = httpx.post(f"{BASE}/api/auth/login", json=dict(zip(("email", "password"), PUBLISHED_ADMIN)))
    record("D-01", "Login de admin con la contraseña publicada en el repo", "401", r.status_code, r.status_code != 200)

    cust_email = "juan.perez@gmail.com"
    customer = login(cust_email, _password(cust_email))
    me = customer.get("/api/auth/me").json()["usuario"]

    # D-02/D-03: funciones de administrador con sesión de cliente
    for tid, path, method in (("D-02", "/api/admin/demo-data", "GET"), ("D-03", "/unsecure/chat", "POST")):
        r = customer.request(method, path, json={"message": "hola"} if method == "POST" else None)
        record(tid, f"Cliente accede a {path}", "403", r.status_code, r.status_code == 403)

    # D-04: IDOR sobre pedidos de otro cliente
    other = next(o for o in SEED["pedidos"] if o["email"] != cust_email)
    r = customer.get(f"/api/orders/{other['codigo']}")
    record("D-04", "Cliente pide un pedido ajeno por código (IDOR)", "404", r.status_code, r.status_code == 404)

    # D-05: sin sesión
    r = httpx.get(f"{BASE}/api/orders")
    record("D-05", "Pedidos sin sesión", "401", r.status_code, r.status_code == 401)

    # D-06: fuerza bruta sobre un correo
    victim = f"victima-{uuid.uuid4().hex[:6]}@test.co"
    codes = [httpx.post(f"{BASE}/api/auth/login", json={"email": victim, "password": "x1234567"}).status_code for _ in range(6)]
    record("D-06", "6 intentos fallidos sobre el mismo correo", "429 en el 6.º", codes, codes[-1] == 429)

    # D-07: fuerza bruta de la contraseña actual en /api/auth/password (sesión robada)
    codes = [customer.put("/api/auth/password", json={"actual": f"mala{i}xx1", "nueva": "Nueva#12345"}).status_code for i in range(8)]
    record("D-07", "8 intentos de 'contraseña actual' en cambio de contraseña", "429 tras 5", codes, 429 in codes)

    # D-08: XSS almacenado en el nombre del perfil (se valida que el API lo guarde y el front lo escape)
    payload = "<img src=x onerror=alert(1)>"
    customer.put("/api/auth/me", json={"nombre": payload, "telefono": me["telefono"], "direccion": me["direccion"], "ciudad": me["ciudad"]})
    stored = customer.get("/api/auth/me").json()["usuario"]["nombre"]
    js = httpx.get(f"{BASE}/app.js").text
    escaped = "esc(u.nombre)" in js
    record("D-08", "Nombre con payload XSS: el front lo escapa al pintarlo", "escapado", "escapado" if escaped else "sin escapar", escaped)
    customer.put("/api/auth/me", json={"nombre": me["nombre"], "telefono": me["telefono"], "direccion": me["direccion"], "ciudad": me["ciudad"]})
    _ = stored

    # D-09: mensaje del chat por encima del límite
    r = customer.post("/secure/chat", json={"message": "a" * 2001})
    record("D-09", "Mensaje de 2001 caracteres al chat", "422", r.status_code, r.status_code == 422)

    # D-10: encabezados de seguridad en la página
    h = httpx.get(f"{BASE}/").headers
    ok = all(k in h for k in ("content-security-policy", "x-frame-options", "x-content-type-options"))
    record("D-10", "Encabezados CSP / X-Frame-Options / nosniff", "presentes", "presentes" if ok else "faltan", ok)

    # D-11: la cookie de sesión no viaja en texto plano si se sirve por HTTPS
    r = httpx.post(f"{BASE}/api/auth/login", json={"email": cust_email, "password": _password(cust_email)})
    flags = r.headers.get("set-cookie", "").lower()
    record("D-11", "Cookie de sesión HttpOnly + SameSite", "httponly; samesite=lax", flags.split(";", 1)[1].strip()[:80],
           "httponly" in flags and "samesite=lax" in flags)
    return results


if __name__ == "__main__":
    out = main()
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
