import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection


def render():
    st.title("📦 Control de Inventarios")
    st.caption("Registra compras (entradas), salidas con descuento automático de consumibles y mermas.")

    conn = get_connection()
    df_prod = pd.read_sql_query("SELECT * FROM productos ORDER BY nombre", conn)

    if df_prod.empty:
        st.warning("Primero registra productos en el módulo de Costos y Precios.")
        conn.close()
        return

    opciones = {
        f"{r['codigo']} - {r['nombre']} [{r['categoria']}] (Stock: {r['stock_actual']} {r['unidad']})": r
        for _, r in df_prod.iterrows()
    }
    seleccion = st.selectbox("Producto, platillo o insumo:", list(opciones.keys()))
    prod = opciones[seleccion]

    # Mostrar vista previa si tiene consumibles vinculados
    df_receta = pd.read_sql_query("""
        SELECT r.insumo_id, r.cantidad_requerida, p.codigo, p.nombre, p.unidad, p.stock_actual
        FROM recetas r
        JOIN productos p ON r.insumo_id = p.id
        WHERE r.platillo_id = ?
    """, conn, params=(int(prod["id"]),))

    if not df_receta.empty:
        st.info("🧾 **Este producto tiene receta vinculada:** al registrar una **SALIDA**, se descontarán automáticamente estos consumibles:")
        st.dataframe(
            df_receta[["codigo", "nombre", "cantidad_requerida", "unidad", "stock_actual"]],
            use_container_width=True,
            hide_index=True,
        )

    with st.form("form_movimiento"):
        c1, c2, c3 = st.columns(3)
        tipo_mov = c1.selectbox("Tipo de movimiento", ["SALIDA", "ENTRADA", "MERMA"])
        cantidad = c2.number_input("Cantidad", min_value=0.1, value=1.0, step=1.0)
        motivo = c3.text_input("Motivo / Referencia (ej. Venta mesa, Compra proveedor, Caducidad)")

        registrar = st.form_submit_button("Registrar Movimiento", type="primary")
        if registrar:
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
            cur = conn.cursor()

            # Caso 1: SALIDA de un platillo con receta/consumibles asociados
            if tipo_mov == "SALIDA" and not df_receta.empty:
                faltantes = []
                for _, item in df_receta.iterrows():
                    consumo_total = round(float(item["cantidad_requerida"]) * float(cantidad), 4)
                    if float(item["stock_actual"]) < consumo_total:
                        faltantes.append(
                            f"{item['nombre']} (requiere {consumo_total} {item['unidad']}, disponible: {item['stock_actual']})"
                        )

                if faltantes:
                    st.error("No hay suficientes consumibles en inventario:\n- " + "\n- ".join(faltantes))
                    conn.close()
                    return

                # Descontar cada consumible automáticamente
                resumen_descuentos = []
                for _, item in df_receta.iterrows():
                    consumo_total = round(float(item["cantidad_requerida"]) * float(cantidad), 4)
                    nuevo_stock_insumo = round(float(item["stock_actual"]) - consumo_total, 4)

                    cur.execute(
                        "UPDATE productos SET stock_actual = ?, actualizado_en = ? WHERE id = ?",
                        (nuevo_stock_insumo, ahora, int(item["insumo_id"])),
                    )
                    cur.execute(
                        """
                        INSERT INTO movimientos_inventario (fecha, producto_id, tipo, cantidad, motivo)
                        VALUES (?, ?, 'SALIDA', ?, ?)
                        """,
                        (
                            fecha_hoy,
                            int(item["insumo_id"]),
                            consumo_total,
                            f"Consumo por salida de {cantidad} {prod['unidad']} de {prod['nombre']}" + (f" ({motivo})" if motivo else ""),
                        ),
                    )
                    resumen_descuentos.append(f"{item['nombre']}: -{consumo_total} {item['unidad']}")

                # Si el platillo también tenía stock físico preparado, lo reduce sin bloquear si estaba en 0
                stock_platillo = float(prod["stock_actual"])
                if stock_platillo > 0:
                    nuevo_stock_plat = max(0.0, stock_platillo - cantidad)
                    cur.execute(
                        "UPDATE productos SET stock_actual = ?, actualizado_en = ? WHERE id = ?",
                        (nuevo_stock_plat, ahora, int(prod["id"])),
                    )

                cur.execute(
                    """
                    INSERT INTO movimientos_inventario (fecha, producto_id, tipo, cantidad, motivo)
                    VALUES (?, ?, 'SALIDA', ?, ?)
                    """,
                    (fecha_hoy, int(prod["id"]), cantidad, motivo or "Salida de platillo (descuento de consumibles)"),
                )

                conn.commit()
                st.success(
                    f"Salida de {cantidad} {prod['unidad']} de '{prod['nombre']}' registrada.\n\n"
                    f"**Consumibles descontados:** {', '.join(resumen_descuentos)}"
                )
                st.rerun()

            # Caso 2: Movimiento normal (ENTRADA, MERMA o SALIDA sin receta)
            else:
                stock_actual = float(prod["stock_actual"])
                if tipo_mov == "ENTRADA":
                    nuevo_stock = stock_actual + cantidad
                else:
                    nuevo_stock = stock_actual - cantidad
                    if nuevo_stock < 0:
                        st.error("La cantidad supera el stock disponible.")
                        conn.close()
                        return

                cur.execute(
                    """
                    INSERT INTO movimientos_inventario (fecha, producto_id, tipo, cantidad, motivo)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (fecha_hoy, int(prod["id"]), tipo_mov, cantidad, motivo or tipo_mov),
                )

                cur.execute(
                    "UPDATE productos SET stock_actual = ?, actualizado_en = ? WHERE id = ?",
                    (nuevo_stock, ahora, int(prod["id"])),
                )

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