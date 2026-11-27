import streamlit as st
import pandas as pd
from datetime import datetime
from database import init_db, get_connection
from modulos import costos_precios, inventarios, ingresos_gastos, etiquetado

st.set_page_config(
    page_title="Gestor de Restaurante",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
    <style>
        .stButton > button {
            border-radius: 8px;
            height: 2.7em;
            font-weight: 600;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.6rem;
        }
    </style>
""", unsafe_allow_html=True)

init_db()


def mostrar_inicio():
    st.title("🍽️ Panel General del Restaurante")
    st.caption("Resumen rápido del día para tomar decisiones sin complicaciones.")

    hoy = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()

    df_fin = pd.read_sql_query(
        "SELECT * FROM finanzas WHERE fecha = ?", conn, params=(hoy,)
    )
    df_prod = pd.read_sql_query("SELECT * FROM productos", conn)
    conn.close()

    ingresos_hoy = df_fin[df_fin["tipo"] == "INGRESO"]["monto"].sum() if not df_fin.empty else 0.0
    gastos_hoy = df_fin[df_fin["tipo"] == "GASTO"]["monto"].sum() if not df_fin.empty else 0.0
    balance_hoy = ingresos_hoy - gastos_hoy

    bajos_stock = df_prod[df_prod["stock_actual"] <= df_prod["stock_minimo"]] if not df_prod.empty else pd.DataFrame()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Ingresos de Hoy", f"L {ingresos_hoy:,.2f}")
    col2.metric("Gastos de Hoy", f"L {gastos_hoy:,.2f}")
    col3.metric("Balance del Día", f"L {balance_hoy:,.2f}")
    col4.metric("Productos por Reponer", f"{len(bajos_stock)}")

    st.divider()

    st.subheader("⚠️ Alertas de Inventario (Stock Bajo o Crítico)")
    if bajos_stock.empty:
        st.success("Todo el inventario está por encima del stock mínimo.")
    else:
        st.warning("Estos productos están en su límite mínimo o por debajo:")
        st.dataframe(
            bajos_stock[["codigo", "nombre", "categoria", "stock_actual", "stock_minimo", "unidad"]],
            use_container_width=True,
            hide_index=True,
        )

    st.info("💡 Usa el menú de la izquierda para entrar a **Costos y Precios**, **Inventarios**, **Ingresos y Gastos** o **Etiquetado de Productos**.")


def main():
    with st.sidebar:
        st.markdown("## 🍽️ Mi Restaurante")
        st.markdown("---")
        modulo = st.radio(
            "Selecciona un módulo:",
            [
                "🏠 Inicio",
                "💰 Costos y Precios",
                "📦 Control de Inventarios",
                "📊 Ingresos y Gastos",
                "🏷️ Etiquetado de Productos",
            ],
            label_visibility="collapsed",
        )
        st.markdown("---")
        st.caption(f"Fecha: {datetime.now().strftime('%d/%m/%Y')}")

    if modulo == "🏠 Inicio":
        mostrar_inicio()
    elif modulo == "💰 Costos y Precios":
        costos_precios.render()
    elif modulo == "📦 Control de Inventarios":
        inventarios.render()
    elif modulo == "📊 Ingresos y Gastos":
        ingresos_gastos.render()
    elif modulo == "🏷️ Etiquetado de Productos":
        etiquetado.render()


if __name__ == "__main__":
    main()