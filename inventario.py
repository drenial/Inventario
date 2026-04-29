import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io
from PIL import Image
import numpy as np

# Intentar importaciones críticas de forma segura
try:
    from pyzbar.pyzbar import decode
    SCANNER_OK = True
except:
    SCANNER_OK = False

try:
    import openpyxl
    EXCEL_OK = True
except ImportError:
    EXCEL_OK = False

# Configuración
st.set_page_config(page_title="POS Pro Estable", layout="centered")

DB_INV = "inventario.csv"
DB_VEN = "ventas.csv"

if 'carrito' not in st.session_state: st.session_state.carrito = []

def cargar(arch, cols):
    if os.path.exists(arch):
        try:
            df = pd.read_csv(arch)
            for c in cols:
                if c not in df.columns: df[c] = 0 if "Stock" in c or "Precio" in c else "N/A"
            return df[cols]
        except: return pd.DataFrame(columns=cols)
    return pd.DataFrame(columns=cols)

def guardar(df, arch):
    df.to_csv(arch, index=False)

C_INV = ["Codigo", "Tiene_Codigo", "Producto", "Categoría", "Precio Venta", "Stock Actual", "Stock Mínimo"]
C_VEN = ["Fecha", "Vendedor", "Producto", "Cantidad", "Total", "Metodo Pago", "Punto Salida"]

df_inv = cargar(DB_INV, C_INV)
df_ven = cargar(DB_VEN, C_VEN)

st.sidebar.title("Menú")
vend = st.sidebar.selectbox("Vendedor", ["Admin", "Vendedor 1", "Vendedor 2"])
pos = st.sidebar.radio("Caja", ["Salida 1", "Salida 2"])

t1, t2, t3 = st.tabs(["🛒 Venta", "📦 Stock", "📊 Cierre"])

# --- VENTA ---
with t1:
    st.subheader("🛒 Carrito")
    c1, c2 = st.columns(2)
    p_sel = None
    with c1:
        m = st.radio("Busca por:", ["Código", "Nombre"], horizontal=True)
        if m == "Código":
            cod = st.text_input("Código")
            if cod:
                res = df_inv[df_inv["Codigo"].astype(str) == str(cod)]
