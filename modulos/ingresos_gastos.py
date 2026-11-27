import io
import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection


def render():
    st.title("📊 Registro de Ingresos y Gastos")
    st.caption("Control diario de ventas, otros ingresos y gastos operativos del restaurante.")

    conn = get_connection()

    with st.form("form_finanzas"):
        c1, c2, c3 = st.columns(3)
        tipo = c1.selectbox("Tipo de registro", ["INGRESO", "GASTO"])
        categoria = c2.selectbox(
            "Categoría",
            [
                "Ventas de Salón",
                "Pedidos / Delivery",
                "Insumos y Mercadería",
                "Servicios (Luz, Agua, Gas, Internet)",
                "Personal / Planilla",
                "Mantenimiento y Limpieza",
                "Otros",
            ],
        )
        metodo = c3.selectbox("Método de pago", ["Efectivo", "Tarjeta", "Transferencia"])

        c4, c5 = st.columns(2)
        monto = c4.number_input("Monto (L)", min_value=0.01, step=10.0, format="%.2f")
        descripcion = c5.text_input("Descripción breve (ej. Cierre de caja, Compra de gas)")

        guardar = st.form_submit_button("Guardar Registro", type="primary")
        if guardar:
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO finanzas (fecha, tipo, categoria, descripcion, metodo_pago, monto)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (fecha_hoy, tipo, categoria, descripcion, metodo, monto))
            conn.commit()
            st.success(f"{tipo} de L {monto:,.2f} guardado.")
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