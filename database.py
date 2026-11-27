import sqlite3
from datetime import datetime

DB_NAME = "restaurante.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # 1. Catálogo de productos / insumos / platillos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            categoria TEXT DEFAULT 'General',
            unidad TEXT DEFAULT 'Unidad',
            costo_unitario REAL NOT NULL DEFAULT 0.0,
            merma_pct REAL NOT NULL DEFAULT 0.0,
            margen_pct REAL NOT NULL DEFAULT 35.0,
            aplica_isv INTEGER NOT NULL DEFAULT 1,
            precio_venta REAL NOT NULL DEFAULT 0.0,
            stock_actual REAL NOT NULL DEFAULT 0.0,
            stock_minimo REAL NOT NULL DEFAULT 5.0,
            actualizado_en TEXT
        )
    """)

    # 2. Movimientos de inventario (ENTRADA, SALIDA, MERMA)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS movimientos_inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            producto_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            cantidad REAL NOT NULL,
            motivo TEXT,
            FOREIGN KEY (producto_id) REFERENCES productos (id)
        )
    """)

    # 3. Registro de ingresos y gastos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS finanzas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            tipo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            descripcion TEXT,
            metodo_pago TEXT DEFAULT 'Efectivo',
            monto REAL NOT NULL
        )
    """)

    conn.commit()
    seed_sample_data(conn)
    conn.close()


def seed_sample_data(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS total FROM productos")
    if cur.fetchone()["total"] == 0:
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
        hoy = datetime.now().strftime("%Y-%m-%d")

        productos_ejemplo = [
            ("PLA-001", "Filete de Res 8oz", "Platillos", "Porción", 110.0, 5.0, 45.0, 1, 232.01, 18.0, 8.0, ahora),
            ("BEB-002", "Jugo Natural Naranja", "Bebidas", "Vaso", 14.0, 8.0, 50.0, 1, 36.57, 4.0, 10.0, ahora),
            ("INS-003", "Aceite Vegetal (Litro)", "Insumos", "Litro", 58.0, 0.0, 30.0, 1, 86.71, 12.0, 5.0, ahora),
        ]
        cur.executemany("""
            INSERT INTO productos (
                codigo, nombre, categoria, unidad, costo_unitario,
                merma_pct, margen_pct, aplica_isv, precio_venta,
                stock_actual, stock_minimo, actualizado_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, productos_ejemplo)

        finanzas_ejemplo = [
            (hoy, "INGRESO", "Ventas de Salón", "Ventas turno mañana", "Efectivo", 4850.00),
            (hoy, "GASTO", "Insumos y Mercadería", "Compra rápida de verduras", "Efectivo", 1120.00),
        ]
        cur.executemany("""
            INSERT INTO finanzas (fecha, tipo, categoria, descripcion, metodo_pago, monto)
            VALUES (?, ?, ?, ?, ?, ?)
        """, finanzas_ejemplo)

        conn.commit()