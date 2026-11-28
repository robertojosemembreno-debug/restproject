import io
import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection


def render():
    st.title("📊 Registro de Ingresos y Gastos")
    st.caption("Control diario de ventas, otros ingresos y gastos operativos del restaurante.")

    conn = get_connection()
    df_prod = pd.read_sql_query("SELECT * FROM productos ORDER BY nombre", conn)

    c1, c2, c3 = st.columns(3)
    tipo = c1.selectbox("Tipo de registro", ["INGRESO", "GASTO"], key="fin_tipo")
    categorias_posibles = (
        ["Ventas de Salón", "Pedidos / Delivery", "Otros Ingresos"]
        if tipo == "INGRESO"
        else [
            "Insumos y Mercadería",
            "Servicios (Luz, Agua, Gas, Internet)",
            "Personal / Planilla",
            "Mantenimiento y Limpieza",
            "Otros",
        ]
    )
    categoria = c2.selectbox("Categoría", categorias_posibles, key="fin_cat")
    metodo = c3.selectbox("Método de pago", ["Efectivo", "Tarjeta", "Transferencia"], key="fin_met")

    descontar_inv = False
    prod_sel = None
    cantidad_vendida = 1.0
    monto_sugerido = 0.01

    if tipo == "INGRESO" and categoria in ("Ventas de Salón", "Pedidos / Delivery") and not df_prod.empty:
        descontar_inv = st.checkbox("Descontar producto y consumibles de inventario al guardar venta", value=True)
        if descontar_inv:
            col_p, col_q = st.columns([3, 1])
            op_prod = {
                f"{r['codigo']} - {r['nombre']} (Precio: L {r['precio_venta']:,.2f} | Stock: {r['stock_actual']})": r
                for _, r in df_prod.iterrows()
            }
            sel_nombre = col_p.selectbox("Platillo o producto vendido:", list(op_prod.keys()), key="fin_prod")
            prod_sel = op_prod[sel_nombre]
            cantidad_vendida = col_q.number_input("Cantidad vendida", min_value=0.1, value=1.0, step=1.0, key="fin_cant")
            monto_sugerido = round(float(prod_sel["precio_venta"]) * float(cantidad_vendida), 2)

    with st.form("form_finanzas"):
        c4, c5 = st.columns(2)
        monto = c4.number_input(
            "Monto (L)",
            min_value=0.01,
            value=max(0.01, monto_sugerido),
            step=10.0,
            format="%.2f",
        )
        desc_defecto = (
            f"Venta de {cantidad_vendida} {prod_sel['unidad']} de {prod_sel['nombre']}"
            if (descontar_inv and prod_sel is not None)
            else ""
        )
        descripcion = c5.text_input("Descripción breve", value=desc_defecto)

        guardar = st.form_submit_button("Guardar Registro", type="primary")
        if guardar:
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
            cur = conn.cursor()

            detalle_extra = ""
            if descontar_inv and prod_sel is not None:
                df_receta = pd.read_sql_query(
                    """
                    SELECT r.insumo_id, r.cantidad_requerida, p.nombre, p.unidad, p.stock_actual
                    FROM recetas r
                    JOIN productos p ON r.insumo_id = p.id
                    WHERE r.platillo_id = ?
                    """,
                    conn,
                    params=(int(prod_sel["id"]),),
                )

                if not df_receta.empty:
                    faltantes = []
                    for _, item in df_receta.iterrows():
                        consumo_total = round(float(item["cantidad_requerida"]) * float(cantidad_vendida), 4)
                        if float(item["stock_actual"]) < consumo_total:
                            faltantes.append(
                                f"{item['nombre']} (requiere {consumo_total} {item['unidad']}, disponible: {item['stock_actual']})"
                            )
                    if faltantes:
                        st.error("No hay suficientes consumibles para esta venta:\n- " + "\n- ".join(faltantes))
                        conn.close()
                        return

                    descuentos = []
                    for _, item in df_receta.iterrows():
                        consumo_total = round(float(item["cantidad_requerida"]) * float(cantidad_vendida), 4)
                        nuevo_stock_ins = round(float(item["stock_actual"]) - consumo_total, 4)
                        cur.execute(
                            "UPDATE productos SET stock_actual = ?, actualizado_en = ? WHERE id = ?",
                            (nuevo_stock_ins, ahora, int(item["insumo_id"])),
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
                                f"Venta ({categoria}): {cantidad_vendida}x {prod_sel['nombre']}",
                            ),
                        )
                        descuentos.append(f"{item['nombre']}: -{consumo_total} {item['unidad']}")

                    if float(prod_sel["stock_actual"]) > 0:
                        nuevo_stock_plat = max(0.0, float(prod_sel["stock_actual"]) - float(cantidad_vendida))
                        cur.execute(
                            "UPDATE productos SET stock_actual = ?, actualizado_en = ? WHERE id = ?",
                            (nuevo_stock_plat, ahora, int(prod_sel["id"])),
                        )

                    cur.execute(
                        """
                        INSERT INTO movimientos_inventario (fecha, producto_id, tipo, cantidad, motivo)
                        VALUES (?, ?, 'SALIDA', ?, ?)
                        """,
                        (fecha_hoy, int(prod_sel["id"]), cantidad_vendida, f"Venta ({categoria})"),
                    )
                    detalle_extra = " | Consumibles descontados: " + ", ".join(descuentos)
                else:
                    stock_act = float(prod_sel["stock_actual"])
                    if stock_act < float(cantidad_vendida):
                        st.error(f"Stock insuficiente de '{prod_sel['nombre']}' (disponible: {stock_act}).")
                        conn.close()
                        return
                    nuevo_stock = round(stock_act - float(cantidad_vendida), 4)
                    cur.execute(
                        "UPDATE productos SET stock_actual = ?, actualizado_en = ? WHERE id = ?",
                        (nuevo_stock, ahora, int(prod_sel["id"])),
                    )
                    cur.execute(
                        """
                        INSERT INTO movimientos_inventario (fecha, producto_id, tipo, cantidad, motivo)
                        VALUES (?, ?, 'SALIDA', ?, ?)
                        """,
                        (fecha_hoy, int(prod_sel["id"]), cantidad_vendida, f"Venta ({categoria})"),
                    )
                    detalle_extra = f" | Stock {prod_sel['nombre']}: -{cantidad_vendida} {prod_sel['unidad']}"

            cur.execute(
                """
                INSERT INTO finanzas (fecha, tipo, categoria, descripcion, metodo_pago, monto)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (fecha_hoy, tipo, categoria, (descripcion or categoria) + detalle_extra, metodo, monto),
            )
            conn.commit()
            st.success(f"{tipo} de L {monto:,.2f} guardado.{detalle_extra}")
            st.rerun()

    df_fin = pd.read_sql_query("SELECT * FROM finanzas ORDER BY id DESC", conn)
    conn.close()

    if not df_fin.empty:
        total_ing = df_fin[df_fin["tipo"] == "INGRESO"]["monto"].sum()
        total_gas = df_fin[df_fin["tipo"] == "GASTO"]["monto"].sum()
        balance = total_ing - total_gas

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Ingresos", f"L {total_ing:,.2f}")
        m2.metric("Total Gastos", f"L {total_gas:,.2f}")
        m3.metric("Balance Neto", f"L {balance:,.2f}")

        st.divider()
        st.dataframe(
            df_fin[["fecha", "tipo", "categoria", "metodo_pago", "descripcion", "monto"]],
            use_container_width=True,
            hide_index=True,
        )

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_fin.to_excel(writer, index=False, sheet_name="Ingresos_y_Gastos")
        st.download_button(
            label="📥 Descargar Reporte en Excel",
            data=buffer.getvalue(),
            file_name=f"ingresos_gastos_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )