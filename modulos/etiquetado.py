import io
import os
import tempfile
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd
import barcode
from barcode.writer import ImageWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from database import get_connection


def _obtener_barcode_path(codigo: str, tmp_dir: str, cache_codigos: dict) -> str:
    codigo_limpio = (
        "".join(ch for ch in str(codigo) if ch.isalnum() or ch in ("-", "_"))
        or "PROD001"
    )
    if codigo_limpio not in cache_codigos:
        code128 = barcode.get("code128", codigo_limpio, writer=ImageWriter())
        cache_codigos[codigo_limpio] = code128.save(
            os.path.join(tmp_dir, f"barcode_{len(cache_codigos)}"),
            options={"module_height": 7.0, "font_size": 7, "quiet_zone": 1.5},
        )
    return cache_codigos[codigo_limpio]


def generar_pdf_lote(lote: list[dict]) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    tmp_dir = tempfile.mkdtemp()
    cache_codigos = {}

    # Expandir cada ítem del lote según su cantidad de etiquetas
    etiquetas_expandidas = []
    for item in lote:
        barcode_path = _obtener_barcode_path(item["codigo"], tmp_dir, cache_codigos)
        for _ in range(int(item["cantidad"])):
            etiquetas_expandidas.append({**item, "barcode_path": barcode_path})

    cols = 3
    rows = 5
    margin_x = 26
    margin_y = 28
    gap_x = 12
    gap_y = 14

    card_w = (width - 2 * margin_x - (cols - 1) * gap_x) / cols
    card_h = (height - 2 * margin_y - (rows - 1) * gap_y) / rows

    for idx, etiq in enumerate(etiquetas_expandidas):
        slot = idx % (cols * rows)
        if idx > 0 and slot == 0:
            c.showPage()

        col = slot % cols
        row = slot // cols

        x = margin_x + col * (card_w + gap_x)
        y = height - margin_y - (row + 1) * card_h - row * gap_y

        c.roundRect(x, y, card_w, card_h, 6, stroke=1, fill=0)

        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(x + 8, y + card_h - 15, str(etiq["nombre"])[:28])

        c.setFont("Helvetica", 7.8)
        c.drawString(x + 8, y + card_h - 27, f"Elab: {etiq['fecha_elab']}  |  Venc: {etiq['fecha_venc']}")

        c.setFont("Helvetica-Bold", 7.8)
        c.drawString(x + 8, y + card_h - 38, f"Etiquetó: {etiq['etiquetado_por'][:26]}")

        c.drawImage(
            etiq["barcode_path"],
            x + 14,
            y + 5,
            width=card_w - 28,
            height=card_h - 46,
            preserveAspectRatio=True,
            anchor="c",
        )

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def render():
    st.title("🏷️ Etiquetado de Productos")
    st.caption("Arma un lote con uno o varios productos y genera un solo PDF listo para imprimir.")

    if "lote_etiquetas" not in st.session_state:
        st.session_state["lote_etiquetas"] = []

    conn = get_connection()
    df_prod = pd.read_sql_query("SELECT * FROM productos ORDER BY nombre", conn)
    conn.close()

    if df_prod.empty:
        st.warning("No hay productos registrados para etiquetar.")
        return

    opciones = {
        f"{r['codigo']} - {r['nombre']} (Stock: {r['stock_actual']} {r['unidad']})": r
        for _, r in df_prod.iterrows()
    }
    seleccion = st.selectbox("Selecciona el producto a agregar al lote:", list(opciones.keys()))
    producto = opciones[seleccion]

    hoy = datetime.now().date()
    venc_defecto = hoy + timedelta(days=3)
    responsable_previo = st.session_state.get("ultimo_etiquetador", "")

    with st.form("form_agregar_lote"):
        c1, c2, c3 = st.columns(3)
        fecha_elab_dt = c1.date_input("Fecha de elaboración", value=hoy)
        fecha_venc_dt = c2.date_input("Fecha de vencimiento", value=venc_defecto)
        cantidad = c3.number_input("Cantidad de etiquetas", min_value=1, max_value=120, value=4, step=1)

        etiquetado_por = st.text_input(
            "Nombre de quien lo etiquetó",
            value=responsable_previo,
            placeholder="Ej. Carlos López",
        )

        agregar_sig = st.form_submit_button("➕ Guardar y Siguiente Producto", type="primary")
        if agregar_sig:
            if not etiquetado_por.strip():
                st.error("Por favor ingresa el nombre de quien etiquetó el producto.")
            elif fecha_venc_dt < fecha_elab_dt:
                st.error("La fecha de vencimiento no puede ser anterior a la fecha de elaboración.")
            else:
                st.session_state["ultimo_etiquetador"] = etiquetado_por.strip()
                st.session_state["lote_etiquetas"].append({
                    "codigo": str(producto["codigo"]),
                    "nombre": str(producto["nombre"]),
                    "fecha_elab": fecha_elab_dt.strftime("%d/%m/%Y"),
                    "fecha_venc": fecha_venc_dt.strftime("%d/%m/%Y"),
                    "etiquetado_por": etiquetado_por.strip(),
                    "cantidad": int(cantidad),
                })
                st.session_state.pop("pdf_lote_bytes", None)
                st.success(
                    f"Guardado en lote: {int(cantidad)} etiqueta(s) de '{producto['nombre']}'. "
                    "Selecciona otro producto arriba para continuar."
                )

    lote = st.session_state["lote_etiquetas"]

    st.divider()
    st.subheader(f"📋 Lote Actual ({sum(x['cantidad'] for x in lote)} etiquetas en total)")

    if not lote:
        st.info("Aún no has agregado productos al lote. Usa el botón **Guardar y Siguiente Producto**.")
    else:
        df_lote = pd.DataFrame(lote)[
            ["codigo", "nombre", "fecha_elab", "fecha_venc", "etiquetado_por", "cantidad"]
        ]
        df_lote.columns = ["Código", "Producto", "Elaboración", "Vencimiento", "Etiquetó", "Cantidad"]
        st.dataframe(df_lote, use_container_width=True, hide_index=True)

        col_a, col_b, col_c = st.columns([2, 2, 1])

        if col_a.button("📄 Generar PDF de Todo el Lote", type="primary"):
            st.session_state["pdf_lote_bytes"] = generar_pdf_lote(lote)
            st.session_state["pdf_lote_nombre"] = f"etiquetas_lote_{hoy.strftime('%Y%m%d')}.pdf"

        quitar_idx = col_b.selectbox(
            "Quitar un ítem del lote:",
            ["-- Ninguno --"] + [f"#{i + 1}: {x['codigo']} - {x['nombre']} ({x['cantidad']})" for i, x in enumerate(lote)],
            label_visibility="collapsed",
        )
        if quitar_idx != "-- Ninguno --":
            idx_borrar = int(quitar_idx.split(":")[0].replace("#", "")) - 1
            st.session_state["lote_etiquetas"].pop(idx_borrar)
            st.session_state.pop("pdf_lote_bytes", None)
            st.rerun()

        if col_c.button("🗑️ Limpiar"):
            st.session_state["lote_etiquetas"] = []
            st.session_state.pop("pdf_lote_bytes", None)
            st.rerun()

    if "pdf_lote_bytes" in st.session_state:
        st.download_button(
            label="📥 Descargar PDF del Lote Completo",
            data=st.session_state["pdf_lote_bytes"],
            file_name=st.session_state["pdf_lote_nombre"],
            mime="application/pdf",
        )