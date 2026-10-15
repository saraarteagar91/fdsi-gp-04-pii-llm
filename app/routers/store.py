"""API de la tienda: catálogo, carrito y pedidos."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import db
from app.security import require_user
from app.services import orders

router = APIRouter(prefix="/api", tags=["tienda"])

SORTS = {
    "relevancia": "destacado DESC, reviews DESC",
    "precio_asc": "precio ASC",
    "precio_desc": "precio DESC",
    "rating": "rating DESC, reviews DESC",
}


def _with_image(p: dict) -> dict:
    return {**p, "imagen": f"/img/products/{p['sku']}.svg"}


@router.get("/categories")
def categories() -> list[dict]:
    return db.query("SELECT categoria AS nombre, COUNT(*) AS productos FROM productos GROUP BY categoria ORDER BY categoria")


@router.get("/products")
def products(q: str = "", categoria: str = "", orden: str = "relevancia", destacados: bool = False) -> list[dict]:
    where, params = ["1=1"], []
    if q.strip():
        where.append("(nombre LIKE ? OR descripcion LIKE ? OR categoria LIKE ?)")
        params += [f"%{q.strip()}%"] * 3
    if categoria:
        where.append("categoria = ?")
        params.append(categoria)
    if destacados:
        where.append("destacado = 1")
    order_by = SORTS.get(orden, SORTS["relevancia"])
    rows = db.query(f"SELECT * FROM productos WHERE {' AND '.join(where)} ORDER BY {order_by}", tuple(params))
    return [_with_image(p) for p in rows]


@router.get("/products/{product_id}")
def product(product_id: int) -> dict:
    p = db.one("SELECT * FROM productos WHERE id = ?", (product_id,))
    if p is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return _with_image(p)


# ----------------------------------------------------------------- carrito
def _cart(user_id: int) -> dict:
    items = [_with_image(i) for i in db.query(
        "SELECT p.id, p.sku, p.nombre, p.precio, p.stock, c.cantidad FROM carrito c "
        "JOIN productos p ON p.id = c.producto_id WHERE c.usuario_id = ? ORDER BY p.nombre", (user_id,))]
    subtotal = sum(i["precio"] * i["cantidad"] for i in items)
    envio = 0 if subtotal >= 150000 or not items else 9900
    return {"items": items, "subtotal": subtotal, "envio": envio, "total": subtotal + envio,
            "unidades": sum(i["cantidad"] for i in items)}


class CartItemIn(BaseModel):
    producto_id: int
    cantidad: int = Field(ge=1, le=20)


@router.get("/cart")
def get_cart(user: dict = Depends(require_user)) -> dict:
    return _cart(user["id"])


@router.post("/cart")
def add_to_cart(body: CartItemIn, user: dict = Depends(require_user)) -> dict:
    p = db.one("SELECT stock FROM productos WHERE id = ?", (body.producto_id,))
    if p is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    current = db.one("SELECT cantidad FROM carrito WHERE usuario_id = ? AND producto_id = ?", (user["id"], body.producto_id))
    qty = min((current["cantidad"] if current else 0) + body.cantidad, p["stock"], 20)
    if qty <= 0:
        raise HTTPException(status_code=409, detail="Producto agotado")
    db.execute("INSERT INTO carrito VALUES (?,?,?) ON CONFLICT(usuario_id, producto_id) DO UPDATE SET cantidad = excluded.cantidad",
               (user["id"], body.producto_id, qty))
    return _cart(user["id"])


@router.put("/cart/{product_id}")
def set_quantity(product_id: int, body: CartItemIn, user: dict = Depends(require_user)) -> dict:
    p = db.one("SELECT stock FROM productos WHERE id = ?", (product_id,))
    if p is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    db.execute("UPDATE carrito SET cantidad = ? WHERE usuario_id = ? AND producto_id = ?",
               (min(body.cantidad, p["stock"]), user["id"], product_id))
    return _cart(user["id"])


@router.delete("/cart/{product_id}")
def remove_from_cart(product_id: int, user: dict = Depends(require_user)) -> dict:
    db.execute("DELETE FROM carrito WHERE usuario_id = ? AND producto_id = ?", (user["id"], product_id))
    return _cart(user["id"])


# ----------------------------------------------------------------- pedidos
class CheckoutIn(BaseModel):
    direccion: str = Field(min_length=5, max_length=200)
    ciudad: str = Field(min_length=3, max_length=80)
    metodo_pago: str = Field(pattern="^(Contra entrega|PSE|Tarjeta de crédito)$")


@router.post("/orders", status_code=201)
def checkout(body: CheckoutIn, user: dict = Depends(require_user)) -> dict:
    try:
        order = orders.create_order(user, body.direccion.strip(), body.ciudad.strip(), body.metodo_pago)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {**order, "items": orders.order_items(order["id"])}


@router.get("/orders")
def my_orders(user: dict = Depends(require_user)) -> list[dict]:
    rows = db.query("SELECT * FROM pedidos WHERE usuario_id = ? ORDER BY creado DESC, id DESC", (user["id"],))
    return [{**o, "items": [_with_image(i) for i in orders.order_items(o["id"])]} for o in rows]


@router.get("/orders/{code}")
def my_order(code: str, user: dict = Depends(require_user)) -> dict:
    o = db.one("SELECT * FROM pedidos WHERE codigo = ? COLLATE NOCASE AND usuario_id = ?", (code, user["id"]))
    if o is None:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return {**o, "items": [_with_image(i) for i in orders.order_items(o["id"])]}
