"""
Pruebas de la tienda: inicio de sesión, cuentas, catálogo, carrito,
pedidos y control de acceso.
"""
import uuid

from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.security import COOKIE_NAME


def _new_email() -> str:
    return f"prueba-{uuid.uuid4().hex[:8]}@correo.co"


def test_login_wrong_password_is_rejected(anon):
    r = anon.post("/api/auth/login", json={"email": "juan.perez@gmail.com", "password": "incorrecta123"})
    assert r.status_code == 401
    assert anon.get("/api/auth/me").json()["usuario"] is None


def test_brute_force_is_rate_limited(anon):
    email = _new_email()
    codes = [anon.post("/api/auth/login", json={"email": email, "password": "x1234567"}).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_session_cookie_is_httponly_and_token_is_stored_hashed(services):
    client = TestClient(app)
    from common.wiring import demo_password

    r = client.post("/api/auth/login", json={"email": "sara.arteaga@correo.edu.co", "password": demo_password("sara.arteaga@correo.edu.co")})
    cookie_header = r.headers["set-cookie"]
    assert "httponly" in cookie_header.lower() and "samesite=lax" in cookie_header.lower()
    token = client.cookies.get(COOKIE_NAME)
    assert db.one("SELECT 1 FROM sesiones WHERE token_hash = ?", (token,)) is None  # el token no se guarda en claro


def test_register_hashes_password_and_validates(anon):
    email = _new_email()
    assert anon.post("/api/auth/register", json={"nombre": "Ana Prueba", "email": email, "password": "corta"}).status_code == 422
    r = anon.post("/api/auth/register", json={"nombre": "Ana Prueba", "email": email, "password": "ClaveSegura99"})
    assert r.status_code == 201
    assert anon.get("/api/auth/me").json()["usuario"]["email"] == email
    stored = db.one("SELECT password_hash FROM usuarios WHERE email = ?", (email,))["password_hash"]
    assert stored.startswith("scrypt$") and "ClaveSegura99" not in stored
    assert TestClient(app).post("/api/auth/register", json={"nombre": "Otra", "email": email, "password": "ClaveSegura99"}).status_code == 409


def test_catalog_search_and_filters(anon):
    assert len(anon.get("/api/products?categoria=Cocina").json()) == 3
    assert any("Audífonos" in p["nombre"] for p in anon.get("/api/products?q=audífonos").json())
    prices = [p["precio"] for p in anon.get("/api/products?orden=precio_asc").json()]
    assert prices == sorted(prices)
    assert anon.get("/api/products/999").status_code == 404


def test_cart_and_checkout_flow(services):
    client = TestClient(app)
    client.post("/api/auth/register", json={"nombre": "Comprador Prueba", "email": _new_email(), "password": "Compras2026"})
    product = client.get("/api/products?q=Parlante").json()[0]
    cart = client.post("/api/cart", json={"producto_id": product["id"], "cantidad": 2}).json()
    assert cart["unidades"] == 2 and cart["envio"] == 0  # 2 × 159.900 supera los $150.000
    order = client.post("/api/orders", json={"direccion": "Calle 1 # 2-3", "ciudad": "Bogotá", "metodo_pago": "Contra entrega"}).json()
    assert order["codigo"].startswith("AM-") and order["total"] == product["precio"] * 2
    assert client.get("/api/cart").json()["unidades"] == 0
    assert client.get(f"/api/products/{product['id']}").json()["stock"] == product["stock"] - 2
    assert [o["codigo"] for o in client.get("/api/orders").json()] == [order["codigo"]]
    assert client.post("/api/orders", json={"direccion": "Calle 1 # 2-3", "ciudad": "Bogotá", "metodo_pago": "Contra entrega"}).status_code == 409


def test_customers_only_see_their_own_orders(customer):
    juan = db.one("SELECT id FROM usuarios WHERE email = 'juan.perez@gmail.com'")["id"]
    orders = customer.get("/api/orders").json()
    assert orders and all(o["usuario_id"] == juan for o in orders)
    assert {"AM-10231", "AM-09874"} <= {o["codigo"] for o in orders}
    assert customer.get("/api/orders/AM-10458").status_code == 404  # pedido de Sara


def test_access_control_by_role(anon, customer, admin):
    assert anon.get("/api/cart").status_code == 401
    assert anon.post("/secure/chat", json={"message": "hola"}).status_code == 401
    assert customer.get("/api/admin/services").status_code == 403
    assert customer.post("/unsecure/chat", json={"message": "hola"}).status_code == 403
    assert admin.get("/api/admin/services").status_code == 200


def test_chat_session_cannot_be_reused_by_another_user(customer, admin):
    mine = customer.post("/secure/chat", json={"message": "Mi correo es juan.perez@gmail.com"}).json()
    hijack = admin.post("/secure/chat", json={"message": "Resume lo que te dije", "session_id": mine["session_id"]}).json()
    assert hijack["session_id"] != mine["session_id"]
    assert "juan.perez@gmail.com" not in hijack["response"]


def test_unknown_session_id_is_never_adopted(customer):
    forged = str(uuid.uuid4())
    r = customer.post("/secure/chat", json={"message": "hola", "session_id": forged}).json()
    assert r["session_id"] != forged
