import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "restaurante.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            categoria TEXT NOT NULL,
            unidad TEXT NOT NULL,
            costo_unitario REAL NOT NULL DEFAULT 0,
            merma_pct REAL NOT NULL DEFAULT 0,
            margen_pct REAL NOT NULL DEFAULT 35,
            aplica_isv INTEGER NOT NULL DEFAULT 1,
            precio_venta REAL NOT NULL DEFAULT 0,
            stock_actual REAL NOT NULL DEFAULT 0,
            stock_minimo REAL NOT NULL DEFAULT 0,
            actualizado_en TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS recetas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platillo_id INTEGER NOT NULL,
            insumo_id INTEGER NOT NULL,
            cantidad_requerida REAL NOT NULL DEFAULT 1,
            UNIQUE(platillo_id, insumo_id),
            FOREIGN KEY (platillo_id) REFERENCES productos(id),
            FOREIGN KEY (insumo_id) REFERENCES productos(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS movimientos_inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            producto_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            cantidad REAL NOT NULL,
            motivo TEXT,
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS finanzas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            tipo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            descripcion TEXT,
            metodo_pago TEXT,
            monto REAL NOT NULL
        )
    """)

    conn.commit()
    conn.close()