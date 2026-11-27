import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection


def calcular_precio(costo_base: float, merma_pct: float, margen_pct: float, aplica_isv: bool):
    factor_merma = max(0.05, 1.0 - (merma_pct / 100.0))
    costo_real = costo_base / factor_merma

    factor_margen = max(0.05, 1.0 - (margen_pct / 100.0))
    precio_sin_isv = costo_real / factor_margen
    precio_final = precio_sin_isv * 1.15 if aplica_isv else precio_sin_isv
    return round(costo_real, 2), round(precio_sin_isv, 2), round(precio_final, 2)


def render():
    st.title("💰 Costos y Actualización de Precios")
    st.caption("Calcula costos reales con merma, define tu margen y actualiza precios de venta.")

    conn = get_connection()
    df_prod = pd.read_sql_query("SELECT * FROM productos ORDER BY nombre", conn)

    tab1, tab2 = st.tabs(["➕ Nuevo Producto / Platillo", "✏️ Actualizar Existente"])

    with tab1:
        with st.form("form_nuevo_producto"):
            c1, c2, c3 = st.columns(3)
            codigo = c1.text_input("Código (ej. PLA-010)").strip().upper()
            nombre = c2.text_input("Nombre del producto o platillo").strip()
            categoria = c3.selectbox("Categoría", ["Platillos", "Bebidas", "Insumos", "Postres", "Empacados"])

            c4, c5, c6 = st.columns(3)
            unidad = c4.selectbox("Unidad de medida", ["Porción", "Unidad", "Plato", "Vaso", "Kg", "Litro"])
            costo_unitario = c5.number_input("Costo base (L)", min_value=0.0, step=1.0, format="%.2f")
            merma_pct = c6.number_input("Merma estimada (%)", min_value=0.0, max_value=80.0, value=5.0, step=1.0)

            c7, c8, c9 = st.columns(3)
            margen_pct = c7.number_input("Margen deseado (%)", min_value=0.0, max_value=90.0, value=40.0, step=1.0)
            aplica_isv = c8.checkbox("Aplica ISV (15%)", value=True)
            stock_inicial = c9.number_input("Stock inicial", min_value=0.0, value=0.0, step=1.0)

            stock_minimo = st.number_input("Stock mínimo de alerta", min_value=0.0, value=5.0, step=1.0)

            costo_real, precio_neto, precio_sugerido = calcular_precio(
                costo_unitario, merma_pct, margen_pct, aplica_isv
            )
            st.markdown(
                f"**Costo real (con merma):** `L {costo_real:,.2f}`  |  "
                f"**Precio sin ISV:** `L {precio_neto:,.2f}`  |  "
                f"**Precio de venta sugerido:** `L {precio_sugerido:,.2f}`"
            )

            precio_venta_final = st.number_input(
                "Precio de venta final a guardar (L)",
                min_value=0.0,
                value=precio_sugerido,
                step=1.0,
                format="%.2f",
            )

            submitted = st.form_submit_button("Guardar Producto", type="primary")
            if submitted:
                if not codigo or not nombre:
                    st.error("Por favor ingresa al menos el código y el nombre.")
                else:
                    try:
                        ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                        cur = conn.cursor()
                        cur.execute("""
                            INSERT INTO productos (
                                codigo, nombre, categoria, unidad, costo_unitario,
                                merma_pct, margen_pct, aplica_isv, precio_venta,
                                stock_actual, stock_minimo, actualizado_en
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            codigo, nombre, categoria, unidad, costo_unitario,
                            merma_pct, margen_pct, 1 if aplica_isv else 0,
                            precio_venta_final, stock_inicial, stock_minimo, ahora
                        ))
                        conn.commit()
                        st.success(f"Producto '{nombre}' guardado correctamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo guardar (revisa si el código ya existe): {e}")

    with tab2:
        if df_prod.empty:
            st.info("Aún no hay productos registrados.")
        else:
            opciones = {f"{row['codigo']} - {row['nombre']}": row for _, row in df_prod.iterrows()}
            seleccion = st.selectbox("Selecciona un producto para actualizar:", list(opciones.keys()))
            prod = opciones[seleccion]

            c1, c2, c3 = st.columns(3)
            nuevo_costo = c1.number_input(
                "Nuevo costo base (L)", min_value=0.0, value=float(prod["costo_unitario"]), step=1.0, format="%.2f"
            )
            nueva_merma = c2.number_input(
                "Merma (%)", min_value=0.0, max_value=80.0, value=float(prod["merma_pct"]), step=1.0
            )
            nuevo_margen = c3.number_input(
                "Margen deseado (%)", min_value=0.0, max_value=90.0, value=float(prod["margen_pct"]), step=1.0
            )

            nuevo_isv = st.checkbox("Aplica ISV (15%)", value=bool(prod["aplica_isv"]), key="edit_isv")
            costo_real, _, precio_sugerido = calcular_precio(nuevo_costo, nueva_merma, nuevo_margen, nuevo_isv)

            st.info(f"Costo real: **L {costo_real:,.2f}**  →  Precio sugerido: **L {precio_sugerido:,.2f}**")
            nuevo_precio = st.number_input(
                "Precio de venta actualizado (L)",
                min_value=0.0,
                value=precio_sugerido,
                step=1.0,
                format="%.2f",
            )

            if st.button("Actualizar Costo y Precio", type="primary"):
                ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                cur = conn.cursor()
                cur.execute("""
                    UPDATE productos
                    SET costo_unitario = ?, merma_pct = ?, margen_pct = ?,
                        aplica_isv = ?, precio_venta = ?, actualizado_en = ?
                    WHERE id = ?
                """, (nuevo_costo, nueva_merma, nuevo_margen, 1 if nuevo_isv else 0, nuevo_precio, ahora, int(prod["id"])))
                conn.commit()
                st.success("Precios y costos actualizados.")
                st.rerun()

    st.divider()
    st.subheader("📋 Catálogo Actual y Precios")
    if not df_prod.empty:
        st.dataframe(
            df_prod[["codigo", "nombre", "categoria", "unidad", "costo_unitario", "margen_pct", "precio_venta", "stock_actual"]],
            use_container_width=True,
            hide_index=True,
        )

    conn.close()