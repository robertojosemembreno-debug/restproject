import io
import os
import tempfile
import streamlit as st
import pandas as pd
import barcode
from barcode.writer import ImageWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from database import get_connection


def generar_pdf_etiquetas(producto, cantidad_etiquetas: int) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Generar imagen del código de barras Code 128
    tmp_dir = tempfile.mkdtemp()
    codigo_limpio = "".join(ch for ch in str(producto["codigo"]) if ch.isalnum() or ch in ("-", "_")) or "PROD001"
    code128 = barcode.get("code128", codigo_limpio, writer=ImageWriter())
    barcode_path = code128.save(
        os.path.join(tmp_dir, "barcode"),
        options={"module_height": 8.0, "font_size": 8, "quiet_zone": 2.0},
    )

    # Cuadrícula de 3 columnas x 6 filas (18 etiquetas por página)
    cols = 3
    rows = 6
    margin_x = 30
    margin_y = 30
    gap_x = 12
    gap_y = 12

    card_w = (width - 2 * margin_x - (cols - 1) * gap_x) / cols
    card_h = (height - 2 * margin_y - (rows - 1) * gap_y) / rows

    idx = 0
    for _ in range(int(cantidad_etiquetas)):
        slot = idx % (cols * rows)
        if idx > 0 and slot == 0:
            c.showPage()

        col = slot % cols
        row = slot // cols

        x = margin_x + col * (card_w + gap_x)
        y = height - margin_y - (row + 1) * card_h - row * gap_y

        c.roundRect(x, y, card_w, card_h, 6, stroke=1, fill=0)

        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 8, y + card_h - 16, str(producto["nombre"])[:24])

        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(x + card_w - 8, y + card_h - 16, f"L {float(producto['precio_venta']):,.2f}")

        c.setFont("Helvetica", 8)
        c.drawString(x + 8, y + card_h - 28, f"Cód: {producto['codigo']} | {producto['unidad']}")

        c.drawImage(
            barcode_path,
            x + 18,
            y + 6,
            width=card_w - 36,
            height=card_h - 38,
            preserveAspectRatio=True,
            anchor="c",
        )

        idx += 1

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def render():
    st.title("🏷️ Etiquetado de Productos")
    st.caption("Genera hojas de etiquetas con código de barras y precio listas para imprimir.")

    conn = get_connection()
    df_prod = pd.read_sql_query("SELECT * FROM productos ORDER BY nombre", conn)
    conn.close()

    if df_prod.empty:
        st.warning("No hay productos registrados para etiquetar.")
        return

    opciones = {f"{r['codigo']} - {r['nombre']} (L {r['precio_venta']:,.2f})": r for _, r in df_prod.iterrows()}
    seleccion = st.selectbox("Selecciona el producto:", list(opciones.keys()))
    producto = opciones[seleccion]

    cantidad = st.number_input("Cantidad de etiquetas a generar", min_value=1, max_value=120, value=6, step=1)

    if st.button("Generar PDF de Etiquetas", type="primary"):
        pdf_bytes = generar_pdf_etiquetas(producto, cantidad)
        st.success(f"Se generaron {cantidad} etiquetas para '{producto['nombre']}'.")
        st.download_button(
            label="📥 Descargar Etiquetas (PDF)",
            data=pdf_bytes,
            file_name=f"etiquetas_{producto['codigo']}.pdf",
            mime="application/pdf",
        )