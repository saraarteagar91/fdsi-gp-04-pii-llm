"""
Sistema de pedidos de la tienda (dentro del límite de confianza).

Control de acceso: un cliente solo puede consultar SUS pedidos, aunque en
el chat escriba el correo, la cédula o el código de pedido de otra persona
(evita enumerar pedidos ajenos). Un administrador puede consultar todos.
"""
import random
import re
import secrets
from datetime import date, timedelta

from app import db

CARRIERS = ["Envía", "Servientrega", "Coordinadora", "Interrapidísimo"]
MY_ACCOUNT = "mi_cuenta"  # "el pedido de la cuenta con la que inicié sesión"


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def find_order(identifier: str, user: dict | None) -> dict | None:
    """Busca un pedido por código (AM-xxxxx), correo, cédula o "mi_cuenta",
    restringido a los pedidos del usuario (salvo administradores)."""
    if user is None:
        return None
    ident = identifier.strip()
    where, params = None, ()
    if ident == MY_ACCOUNT:
        where, params = "p.usuario_id = ?", (user["id"],)
    elif re.fullmatch(r"(?i)AM-\d+", ident):
        where, params = "p.codigo = ? COLLATE NOCASE", (ident,)
    elif "@" in ident:
        where, params = "u.email = ? COLLATE NOCASE", (ident,)
    elif len(_digits(ident)) >= 6:
        where, params = "u.cedula = ?", (_digits(ident),)
    if where is None:
        return None
    if user["rol"] != "admin":
        where += " AND p.usuario_id = ?"
        params += (user["id"],)
    return db.one(
        f"SELECT p.* FROM pedidos p JOIN usuarios u ON u.id = p.usuario_id WHERE {where} ORDER BY p.creado DESC, p.id DESC LIMIT 1",
        params,
    )


def order_items(order_id: int) -> list[dict]:
    return db.query(
        "SELECT i.cantidad, i.precio_unitario, pr.id AS producto_id, pr.nombre, pr.sku FROM pedido_items i "
        "JOIN productos pr ON pr.id = i.producto_id WHERE i.pedido_id = ?",
        (order_id,),
    )


def describe_order(order: dict | None) -> str:
    """Texto SIN datos personales que se le muestra al usuario."""
    if order is None:
        return (
            "No encontré ese pedido en tu cuenta. Revisa el número de pedido (AM-xxxxx) en «Mis pedidos»; "
            "por seguridad solo puedo consultar los pedidos de la cuenta con la que iniciaste sesión."
        )
    names = ", ".join(i["nombre"] for i in order_items(order["id"]))
    return (
        f"Tu pedido {order['codigo']} ({names}) está «{order['estado']}» con "
        f"{order['transportadora']}; fecha estimada de entrega: {order['fecha_entrega']}."
    )


def _business_days(start: date, n: int) -> date:
    d = start
    while n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def create_order(user: dict, direccion: str, ciudad: str, metodo_pago: str) -> dict:
    """Convierte el carrito en un pedido, descontando inventario."""
    with db.transaction() as c:
        cart = [dict(r) for r in c.execute(
            "SELECT c.producto_id, c.cantidad, p.precio, p.stock, p.nombre FROM carrito c "
            "JOIN productos p ON p.id = c.producto_id WHERE c.usuario_id = ?", (user["id"],)).fetchall()]
        if not cart:
            raise ValueError("Tu carrito está vacío.")
        for item in cart:
            if item["cantidad"] > item["stock"]:
                raise ValueError(f"Solo quedan {item['stock']} unidades de {item['nombre']}.")
        while True:
            # Lab. 06 (F-10, Bandit B311): el código de pedido sirve para consultarlo
            # en el chat; se genera con un generador criptográfico, no con random.
            code = f"AM-{10700 + secrets.randbelow(99999 - 10700 + 1)}"
            if not c.execute("SELECT 1 FROM pedidos WHERE codigo = ?", (code,)).fetchone():
                break
        total = sum(i["precio"] * i["cantidad"] for i in cart)
        total += 0 if total >= 150000 else 9900
        city_fast = ciudad.strip().lower() in ("bogotá", "bogota", "medellín", "medellin", "cali")
        eta = _business_days(date.today(), 2 if city_fast else 5).strftime("%d/%m/%Y")
        estado = "Pago en verificación" if metodo_pago == "PSE" else "Confirmado"
        cur = c.execute(
            "INSERT INTO pedidos (codigo, usuario_id, estado, transportadora, fecha_entrega, total, direccion_envio, metodo_pago, creado)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (code, user["id"], estado, random.choice(CARRIERS), eta, total, f"{direccion}, {ciudad}", metodo_pago, date.today().isoformat()),  # nosec B311 (transportadora)
        )
        for i in cart:
            c.execute("INSERT INTO pedido_items VALUES (?,?,?,?)", (cur.lastrowid, i["producto_id"], i["cantidad"], i["precio"]))
            c.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (i["cantidad"], i["producto_id"]))
        c.execute("DELETE FROM carrito WHERE usuario_id = ?", (user["id"],))
    return db.one("SELECT * FROM pedidos WHERE codigo = ?", (code,))


def demo_customers() -> list[dict]:
    """Clientes de prueba con su último pedido (solo para el administrador)."""
    return db.query(
        "SELECT u.nombre, u.cedula, u.email AS correo, u.telefono, "
        "(SELECT codigo FROM pedidos p WHERE p.usuario_id = u.id ORDER BY creado DESC LIMIT 1) AS pedido "
        "FROM usuarios u WHERE u.rol = 'cliente' ORDER BY u.id"
    )
