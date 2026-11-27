import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection


def render():
    st.title("📦 Control de Inventarios")
    st.caption("Registra compras (entradas), salidas por consumo/venta y mermas.")

    conn = get_connection()
    df_prod = pd.read_sql_query("SELECT * FROM productos ORDER BY nombre", conn)

    if df_prod.empty:
        st.warning("Primero registra productos en el módulo de Costos y Precios.")
        conn.close()
        return

    with st.form("form_movimiento"):
        opciones = {
            f"{r['codigo']} - {r['nombre']} (Stock: {r['stock_actual']} {r['unidad']})": r
            for _, r in df_prod.iterrows()
        }
        seleccion = st.selectbox("Producto o insumo:", list(opciones.keys()))
        prod = opciones[seleccion]

        c1, c2, c3 = st.columns(3)
        tipo_mov = c1.selectbox("Tipo de movimiento", ["ENTRADA", "SALIDA", "MERMA"])
        cantidad = c2.number_input("Cantidad", min_value=0.1, value=1.0, step=1.0)
        motivo = c3.text_input("Motivo / Referencia (ej. Compra proveedor, Venta, Caducidad)")

        registrar = st.form_submit_button("Registrar Movimiento", type="primary")
        if registrar:
            stock_actual = float(prod["stock_actual"])
            if tipo_mov == "ENTRADA":
                nuevo_stock = stock_actual + cantidad
            else:
                nuevo_stock = stock_actual - cantidad
                if nuevo_stock < 0:
                    st.error("La cantidad supera el stock disponible.")
                    conn.close()
                    return

            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M")

            cur = conn.cursor()
            cur.execute("""
                INSERT INTO movimientos_inventario (fecha, producto_id, tipo, cantidad, motivo)
                VALUES (?, ?, ?, ?, ?)
            """, (fecha_hoy, int(prod["id"]), tipo_mov, cantidad, motivo or tipo_mov))

            cur.execute("""
                UPDATE productos SET stock_actual = ?, actualizado_en = ? WHERE id = ?
            """, (nuevo_stock, ahora, int(prod["id"])))

            conn.commit()
            st.success(f"Movimiento {tipo_mov} registrado. Nuevo stock: {nuevo_stock} {prod['unidad']}.")
            st.rerun()

    st.divider()
    st.subheader("📊 Existencias Actuales")
    df_vista = df_prod.copy()
    df_vista["Estado"] = df_vista.apply(
        lambda r: "🔴 Crítico" if r["stock_actual"] <= r["stock_minimo"] else "🟢 Disponible",
        axis=1,
    )
    st.dataframe(
        df_vista[["Estado", "codigo", "nombre", "categoria", "stock_actual", "stock_minimo", "unidad", "precio_venta"]],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("🕒 Últimos Movimientos")
    df_mov = pd.read_sql_query("""
        SELECT m.fecha, p.codigo, p.nombre, m.tipo, m.cantidad, p.unidad, m.motivo
        FROM movimientos_inventario m
        JOIN productos p ON m.producto_id = p.id
        ORDER BY m.id DESC LIMIT 20
    """, conn)
    st.dataframe(df_mov, use_container_width=True, hide_index=True)

    conn.close()