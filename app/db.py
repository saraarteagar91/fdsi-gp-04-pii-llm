"""
Base de datos de la tienda: SQLite (archivo data/db/andes_market.db).

Tablas: usuarios, sesiones de inicio de sesión, productos, carrito,
pedidos y sus productos. Las contraseñas se guardan solo como hash
scrypt con sal; los tokens de sesión, solo como hash SHA-256.

Si la base está vacía, se crea y se llena con data/seed/ al arrancar.
"""
import json
import sqlite3
import threading
from pathlib import Path

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    nombre TEXT NOT NULL,
    cedula TEXT,
    telefono TEXT,
    direccion TEXT,
    ciudad TEXT,
    rol TEXT NOT NULL DEFAULT 'cliente' CHECK (rol IN ('cliente', 'admin')),
    creado TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS sesiones (
    token_hash TEXT PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    expira REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    categoria TEXT NOT NULL,
    precio INTEGER NOT NULL,
    precio_antes INTEGER,
    descripcion TEXT NOT NULL,
    stock INTEGER NOT NULL,
    rating REAL NOT NULL,
    reviews INTEGER NOT NULL,
    destacado INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS carrito (
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    producto_id INTEGER NOT NULL REFERENCES productos(id),
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (usuario_id, producto_id)
);
CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    estado TEXT NOT NULL,
    transportadora TEXT NOT NULL,
    fecha_entrega TEXT NOT NULL,
    total INTEGER NOT NULL,
    direccion_envio TEXT,
    metodo_pago TEXT,
    creado TEXT NOT NULL DEFAULT (date('now'))
);
CREATE TABLE IF NOT EXISTS pedido_items (
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    producto_id INTEGER NOT NULL REFERENCES productos(id),
    cantidad INTEGER NOT NULL,
    precio_unitario INTEGER NOT NULL
);
"""

_lock = threading.RLock()  # reentrante: una transacción puede hacer varias consultas
_conn: sqlite3.Connection | None = None


def db_path() -> Path:
    return Path(settings.db_path)


def conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            db_path().parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(db_path(), check_same_thread=False, isolation_level=None)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA foreign_keys = ON")
            _conn.execute("PRAGMA journal_mode = WAL")
            _conn.executescript(SCHEMA)
            if _conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0:
                _seed(_conn)
        return _conn


def query(sql: str, params: tuple = ()) -> list[dict]:
    with _lock:
        return [dict(r) for r in conn().execute(sql, params).fetchall()]


def one(sql: str, params: tuple = ()) -> dict | None:
    with _lock:
        row = conn().execute(sql, params).fetchone()
        return dict(row) if row else None


def execute(sql: str, params: tuple = ()) -> int:
    with _lock:
        return conn().execute(sql, params).lastrowid


def transaction():
    return _Tx()


class _Tx:
    def __enter__(self):
        _lock.acquire()
        conn().execute("BEGIN")
        return conn()

    def __exit__(self, exc_type, *_):
        conn().execute("ROLLBACK" if exc_type else "COMMIT")
        _lock.release()


def _seed(c: sqlite3.Connection) -> None:
    from app.security import hash_password

    seed_dir = Path(settings.data_dir) / "seed"
    catalog = json.loads((seed_dir / "catalogo.json").read_text(encoding="utf-8"))["productos"]
    demo = json.loads((seed_dir / "usuarios_demo.json").read_text(encoding="utf-8"))

    c.execute("BEGIN")
    for p in catalog:
        c.execute(
            "INSERT INTO productos (sku, nombre, categoria, precio, precio_antes, descripcion, stock, rating, reviews, destacado)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (p["sku"], p["nombre"], p["categoria"], p["precio"], p["precio_antes"], p["descripcion"], p["stock"], p["rating"], p["reviews"], p["destacado"]),
        )
    for u in demo["usuarios"]:
        c.execute(
            "INSERT INTO usuarios (email, password_hash, nombre, cedula, telefono, direccion, ciudad, rol) VALUES (?,?,?,?,?,?,?,?)",
            (u["email"], hash_password(u["password"]), u["nombre"], u["cedula"], u["telefono"], u["direccion"], u["ciudad"], u["rol"]),
        )
    for o in demo["pedidos"]:
        user = c.execute("SELECT id, direccion, ciudad FROM usuarios WHERE email = ?", (o["email"],)).fetchone()
        items = [(c.execute("SELECT id, precio FROM productos WHERE sku = ?", (sku,)).fetchone(), qty) for sku, qty in o["items"]]
        total = sum(p["precio"] * q for p, q in items)
        cur = c.execute(
            "INSERT INTO pedidos (codigo, usuario_id, estado, transportadora, fecha_entrega, total, direccion_envio, metodo_pago, creado)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (o["codigo"], user["id"], o["estado"], o["transportadora"], o["fecha_entrega"], total,
             f"{user['direccion']}, {user['ciudad']}", "Tarjeta de crédito", o["creado"]),
        )
        for p, q in items:
            c.execute("INSERT INTO pedido_items VALUES (?,?,?,?)", (cur.lastrowid, p["id"], q, p["precio"]))
    c.execute("COMMIT")


def reset_connection() -> None:
    """Solo para pruebas: cierra la conexión para usar otra base."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None
