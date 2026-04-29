import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io
from PIL import Image
import numpy as np
from fpdf import FPDF

# --- CONFIGURACIÓN DE SEGURIDAD ---
# CAMBIA "1234" POR TU CLAVE DESEADA
CLAVE_ADMIN = "0302"

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Bodega & Taller POS", page_icon="🛠️", layout="centered")

# Estilo para ocultar menús de Streamlit
st.markdown("<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}</style>", unsafe_allow_html=True)

DB_INV = "inventario.csv"
DB_VEN = "ventas.csv"

# Estados de sesión
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False
if 'ultimo_ticket' not in st.session_state: st.session_state.ultimo_ticket = None

# --- FUNCIONES DE DATOS ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            for col in columnas:
                if col not in df.columns: 
                    df[col] = "" if col not in ["Stock Actual", "Total", "Cantidad", "Precio Venta"] else 0
            return df[columnas]
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

# --- FUNCIÓN GENERAR TICKET PDF (AJUSTADO A 58mm / 5.5cm) ---
def generar_ticket_pdf(vendedor, items, total, metodo, salida):
    # Formato 58mm de ancho (estándar para papel de 5.5cm)
    pdf = FPDF(format=(58, 150)) 
    pdf.add_page()
    pdf.set_margins(left=4, top=4, right=4)
    pdf.set_auto_page_break(auto=True, margin=5)
    
    # Encabezado
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, "MI NEGOCIO", ln=True, align="C")
    pdf.set_font("Arial", "", 7)
    pdf.cell(0, 4, f"Fecha: {datetime.now().strftime('%d/%m/%y %H:%M')}", ln=True, align="C")
    pdf.cell(0, 4, f"Caja: {salida} | Vend: {vendedor}", ln=True, align="C")
    pdf.cell(0, 3, "-"*25, ln=True, align="C")
    
    # Tabla de productos
    pdf.set_font("Arial", "B", 7)
    pdf.cell(25, 5, "Producto/Serv", 0)
    pdf.cell(8, 5, "Cant", 0)
    pdf.cell(15, 5, "Subt", 0, align="R")
    pdf.ln(5)
    
    pdf.set_font("Arial", "", 6)
    for it in items:
        # Nombre corto para que no se desborde
        nom = str(it['Producto'])[:18]
        pdf.cell(25, 4, nom, 0)
        pdf.cell(8, 4, str(it['Cantidad']), 0)
        pdf.cell(15, 4, f"${it['Subtotal']:.2f}", 0, align="R")
        pdf.ln(4)
        # Si es un trabajo, mostrar el modelo del carro abajo
        if it.get("Modelo Carro") and it["Modelo Carro"] != "":
            pdf.set_font("Arial", "I", 5)
            pdf.cell(0, 3, f"  Carro: {it['Modelo Carro']}", ln=True)
            pdf.set_font("Arial", "", 6)
    
    # Totales
    pdf.ln(2)
    pdf.cell(0, 1, "-"*25, ln=True, align="C")
    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 8, f"TOTAL: ${total:.2f}", ln=True, align="R")
    pdf.set_font("Arial", "B", 7)
    pdf.cell(0, 4, f"Pago: {metodo}", ln=True, align="L")
    
    pdf.ln(4)
    pdf.set_font("Arial", "I", 7)
    pdf.cell(0, 5, "¡Gracias por su visita!", ln=True, align="C")
    
    return pdf.output()

# Columnas Base
C_INV = ["Codigo", "Tiene_Codigo", "Producto", "Categoría", "Precio Venta", "Stock Actual", "Stock Mínimo"]
C_VEN = ["Fecha", "Vendedor", "Producto", "Cantidad", "Total", "Metodo Pago", "Punto Salida", "Ayudante", "Descripcion", "Modelo Carro"]

df_inv = cargar_datos(DB_INV, C_INV)
df_ven = cargar_datos(DB_VEN, C_VEN)

# --- SIDEBAR (SEGURIDAD) ---
st.sidebar.title("🔐 Acceso")
if not st.session_state.admin_auth:
    pass_in = st.sidebar.text_input("Clave Admin", type="password")
    if st.sidebar.button("Entrar"):
        if pass_in == CLAVE_ADMIN:
            st.session_state.admin_auth = True
            st.rerun()
else:
    st.sidebar.success("Modo Admin")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.admin_auth = False
        st.rerun()

vendedor_fijo = st.sidebar.selectbox("👤 Personal", ["Vendedor 1", "Vendedor 2", "Admin"])
salida_fija = st.sidebar.radio("📍 Punto", ["Salida 1", "Salida 2"])

# Pestañas
tabs = st.tabs(["🛒 Venta", "📦 Stock", "📊 Cierre"]) if st.session_state.admin_auth else st.tabs(["🛒 Venta"])

# --- PESTAÑA 1: VENTAS ---
with tabs[0]:
    st.subheader("🛒 Facturación")
    opcion = st.radio("Agregar:", ["📦 Producto", "🛠️ Servicio"], horizontal=True)
    p_sel = None

    if opcion == "📦 Producto":
        c1, c2 = st.columns(2)
        with c1:
            m = st.radio("Buscar:", ["Código", "Nombre"], horizontal=True)
            if m == "Código":
                cod = st.text_input("Código")
                if cod:
                    res = df_inv[df_inv["Codigo"].astype(str) == str(cod)]
                    if not res.empty: p_sel = res.iloc[0]
            else:
                nom = st.text_input("Nombre")
                if nom:
                    sug = df_inv[df_inv["Producto"].str.contains(nom, case=False)]["Producto"].tolist()
                    sel = st.selectbox("Elegir", ["-"] + sug)
                    if sel != "-": p_sel = df_inv[df_inv["Producto"] == sel].iloc[0]
        with c2:
            if p_sel is not None:
                st.info(f"**{p_sel['Producto']}**\n\nStock: {p_sel['Stock Actual']}")
                can = st.number_input("Cant", min_value=1, max_value=max(1, int(p_sel['Stock Actual'])), value=1)
                if st.button("➕ Añadir"):
                    st.session_state.carrito.append({"Tipo": "Prod", "Producto": p_sel['Producto'], "Precio": float(p_sel['Precio Venta']), "Cantidad": int(can), "Subtotal": float(p_sel['Precio Venta']*can), "Ayudante": "", "Descripcion": "", "Modelo Carro": ""})
                    st.rerun()
    else:
        with st.container():
            st.info("🛠️ Trabajo")
            ct1, ct2 = st.columns(2)
            with ct1:
                desc = st.text_area("Descripción")
                carro = st.text_input("Carro (Opcional)")
            with ct2:
                ayu = st.text_input("Ayudante")
                pre = st.number_input("Costo $", min_value=0.0)
            if st.button("➕ Añadir Servicio"):
                if desc and pre > 0:
                    st.session_state.carrito.append({"Tipo": "Trab", "Producto": desc[:20], "Precio": float(pre), "Cantidad": 1, "Subtotal": float(pre), "Ayudante": ayu, "Descripcion": desc, "Modelo Carro": carro})
                    st.rerun()

    st.divider()
    if st.session_state.carrito:
        for i, it in enumerate(st.session_state.carrito):
            col_i, col_d = st.columns([4, 1])
            col_i.write(f"**{it['Cantidad']}x** {it['Producto']} - ${it['Subtotal']:.2f}")
            if col_d.button("🗑️", key=f"del_{i}"):
                st.session_state.carrito.pop(i); st.rerun()
        
        total_p = sum(i['Subtotal'] for i in st.session_state.carrito)
        st.markdown(f"### TOTAL: ${total_p:,.2f}")
        met = st.selectbox("Metodo Pago", ["Pago Móvil", "Punto", "Zelle", "Binance", "Efectivo"])
        
        if st.button("✅ PROCESAR", use_container_width=True):
            ticket_info = {"vendedor": vendedor_fijo, "items": list(st.session_state.carrito), "total": total_p, "metodo": met, "salida": salida_fija}
            for it in st.session_state.carrito:
                if it["Tipo"] == "Prod":
                    idx = df_inv[df_inv["Producto"] == it["Producto"]].index[0]
                    df_inv.at[idx, "Stock Actual"] -= it["Cantidad"]
                nv = pd.DataFrame([{"Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "Vendedor": vendedor_fijo, "Producto": it["Producto"], "Cantidad": it["Cantidad"], "Total": it["Subtotal"], "Metodo Pago": met, "Punto Salida": salida_fija, "Ayudante": it["Ayudante"], "Descripcion": it["Descripcion"], "Modelo Carro": it["Modelo Carro"]}])
                df_ven = pd.concat([df_ven, nv], ignore_index=True)
            guardar_datos(df_inv, DB_INV); guardar_datos(df_ven, DB_VEN)
            st.session_state.ultimo_ticket = ticket_info
            st.session_state.carrito = []
            st.rerun()

    if st.session_state.ultimo_ticket:
        st.success("¡Venta Guardada!")
        pdf_t = generar_ticket_pdf(st.session_state.ultimo_ticket["vendedor"], st.session_state.ultimo_ticket["items"], st.session_state.ultimo_ticket["total"], st.session_state.ultimo_ticket["metodo"], st.session_state.ultimo_ticket["salida"])
        st.download_button("📥 IMPRIMIR TICKET (58mm)", pdf_t, f"ticket_{datetime.now().strftime('%H%M%S')}.pdf", "application/pdf", use_container_width=True)
        if st.button("Nueva Factura"):
            st.session_state.ultimo_ticket = None
            st.rerun()

# --- PESTAÑAS ADMIN ---
if st.session_state.admin_auth:
    with tabs[1]:
        st.subheader("📦 Stock")
        st.dataframe(df_inv, use_container_width=True)
    with tabs[2]:
        st.subheader("📊 Cierre")
        fs = st.date_input("Día", datetime.now()).strftime("%Y-%m-%d")
        vd = df_ven[df_ven["Fecha"].str.contains(fs)]
        if not vd.empty:
            st.metric("TOTAL", f"${vd['Total'].sum():,.2f}")
            st.dataframe(vd[["Fecha", "Producto", "Total", "Metodo Pago", "Modelo Carro"]])
