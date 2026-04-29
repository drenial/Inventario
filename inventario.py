import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io
from PIL import Image
import numpy as np

# --- CONFIGURACIÓN DE SEGURIDAD ---
# CAMBIA "1234" POR TU CLAVE DESEADA
CLAVE_ADMIN = "0302" 

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Mi Bodega POS", 
    page_icon="📦",
    layout="centered"
)

# Estilo para ocultar menú de Streamlit y que parezca App nativa
hide_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_style, unsafe_allow_html=True)

DB_INV = "inventario.csv"
DB_VEN = "ventas.csv"

# Estados de sesión
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False

# --- FUNCIONES DE DATOS ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            for col in columnas:
                if col not in df.columns: df[col] = 0 if ("Stock" in col or "Precio" in col) else "N/A"
            return df[columnas]
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

C_INV = ["Codigo", "Tiene_Codigo", "Producto", "Categoría", "Precio Venta", "Stock Actual", "Stock Mínimo"]
C_VEN = ["Fecha", "Vendedor", "Producto", "Cantidad", "Total", "Metodo Pago", "Punto Salida"]

df_inv = cargar_datos(DB_INV, C_INV)
df_ven = cargar_datos(DB_VEN, C_VEN)

# --- SIDEBAR (LOGIN ADMIN) ---
st.sidebar.title("🔐 Acceso")
if not st.session_state.admin_auth:
    password = st.sidebar.text_input("Clave de Admin", type="password")
    if st.sidebar.button("Entrar"):
        if password == CLAVE_ADMIN:
            st.session_state.admin_auth = True
            st.rerun()
        else:
            st.sidebar.error("Clave incorrecta")
else:
    st.sidebar.success("Modo Admin Activo")
    if st.sidebar.button("Cerrar Sesión Admin"):
        st.session_state.admin_auth = False
        st.rerun()

vendedor = st.sidebar.selectbox("👤 Vendedor", ["Vendedor 1", "Vendedor 2", "Admin"])
salida = st.sidebar.radio("📍 Punto", ["Salida 1", "Salida 2"])

# --- SISTEMA DE PESTAÑAS DINÁMICAS ---
# Si no es admin, solo ve la pestaña de Vender
if st.session_state.admin_auth:
    pestanas = st.tabs(["🛒 Punto de Venta", "📦 Inventario", "📊 Cierre Diario"])
else:
    pestanas = st.tabs(["🛒 Punto de Venta"])

# --- PESTAÑA 1: PUNTO DE VENTA (Pública para todos) ---
with pestanas[0]:
    st.subheader("🛒 Punto de Venta")
    col_busq, col_conf = st.columns([1, 1])
    p_encontrado = None

    with col_busq:
        modo = st.radio("Buscar por:", ["Código", "Nombre"], horizontal=True)
        if modo == "Código":
            cod_in = st.text_input("Código / Escáner")
            if cod_in:
                res = df_inv[df_inv["Codigo"].astype(str) == str(cod_in)]
                if not res.empty: p_encontrado = res.iloc[0]
                else: st.error("No registrado")
        else:
            nom_in = st.text_input("Nombre del producto")
            if nom_in:
                sug = df_inv[df_inv["Producto"].str.contains(nom_in, case=False)]["Producto"].tolist()
                sel = st.selectbox("Seleccionar", ["-"] + sug)
                if sel != "-": p_encontrado = df_inv[df_inv["Producto"] == sel].iloc[0]

    with col_conf:
        if p_encontrado is not None:
            st.info(f"**{p_encontrado['Producto']}**\n\nPrecio: ${p_encontrado['Precio Venta']}")
            cant = st.number_input("Cantidad", min_value=1, max_value=max(1, int(p_encontrado['Stock Actual'])), value=1)
            if st.button("➕ Añadir"):
                st.session_state.carrito.append({
                    "Producto": p_encontrado['Producto'],
                    "Precio": float(p_encontrado['Precio Venta']),
                    "Cantidad": int(cant),
                    "Subtotal": float(p_encontrado['Precio Venta'] * cant)
                })
                st.rerun()

    st.divider()
    if st.session_state.carrito:
        for i, item in enumerate(st.session_state.carrito):
            c_it, c_dl = st.columns([4, 1])
            c_it.write(f"**{item['Cantidad']}x** {item['Producto']} — ${item['Subtotal']:,.2f}")
            if c_dl.button("🗑️", key=f"del_{i}"):
                st.session_state.carrito.pop(i); st.rerun()
        
        total_p = sum(it['Subtotal'] for it in st.session_state.carrito)
        st.markdown(f"## TOTAL: ${total_p:,.2f}")
        metodo = st.selectbox("Método de Pago", ["Pago Móvil", "Punto", "Zelle", "Binance", "Efectivo"])
        
        cb1, cb2 = st.columns(2)
        if cb1.button("✅ FINALIZAR VENTA", use_container_width=True):
            for item in st.session_state.carrito:
                idx = df_inv[df_inv["Producto"] == item["Producto"]].index[0]
                df_inv.at[idx, "Stock Actual"] -= item["Cantidad"]
                nv = pd.DataFrame([{"Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "Vendedor": vendedor, "Producto": item["Producto"], "Cantidad": item["Cantidad"], "Total": item["Subtotal"], "Metodo Pago": metodo, "Punto Salida": salida}])
                df_ven = pd.concat([df_ven, nv], ignore_index=True)
            guardar_datos(df_inv, DB_INV); guardar_datos(df_ven, DB_VEN)
            st.session_state.carrito = []
            st.success("Venta Exitosa!"); st.rerun()
        if cb2.button("🚫 CANCELAR", use_container_width=True):
            st.session_state.carrito = []; st.rerun()

# --- PESTAÑAS RESTRINGIDAS (SOLO ADMIN) ---
if st.session_state.admin_auth:
    # --- PESTAÑA 2: INVENTARIO ---
    with pestanas[1]:
        st.subheader("📦 Gestión de Stock")
        if st.button("➕ AGREGAR NUEVO PRODUCTO"):
            st.session_state.mostrar_form = not st.session_state.get('mostrar_form', False)
        
        if st.session_state.get('mostrar_form', False):
            with st.form("f_nuevo"):
                t_c = st.radio("¿Código?", ["Sí", "No"], horizontal=True)
                f_c = st.text_input("Código")
                f_n = st.text_input("Nombre")
                f_p = st.number_input("Precio Venta", min_value=0.0)
                f_s = st.number_input("Stock Inicial", min_value=0)
                if st.form_submit_button("Guardar"):
                    nuevo = pd.DataFrame([{"Codigo": f_c if t_c=="Sí" else "SIN_CODIGO", "Tiene_Codigo": t_c, "Producto": f_n, "Categoría": "General", "Precio Venta": f_p, "Stock Actual": f_s, "Stock Mínimo": 5}])
                    df_inv = pd.concat([df_inv, nuevo], ignore_index=True)
                    guardar_datos(df_inv, DB_INV); st.rerun()
        
        st.write("### Ajuste Rápido")
        p_aj = st.selectbox("Seleccionar producto", df_inv["Producto"].tolist() if not df_inv.empty else [])
        if p_aj:
            c_aj = st.number_input("Resta cantidad (Devolución/Daño)", min_value=1, value=1)
            if st.button("Confirmar Resta"):
                idx_a = df_inv[df_inv["Producto"] == p_aj].index[0]
                df_inv.at[idx_a, "Stock Actual"] -= c_aj
                guardar_datos(df_inv, DB_INV); st.success("Ajustado"); st.rerun()
        
        st.divider()
        st.dataframe(df_inv, use_container_width=True)

    # --- PESTAÑA 3: CIERRE ---
    with pestanas[2]:
        st.subheader("📊 Cierre de Caja")
        f_cierre = st.date_input("Fecha", datetime.now())
        f_str = f_cierre.strftime("%Y-%m-%d")
        v_dia = df_ven[df_ven["Fecha"].str.contains(f_str)]
        
        if not v_dia.empty:
            st.metric("INGRESO TOTAL", f"${v_dia['Total'].sum():,.2f}")
            st.write("**Resumen de Pagos:**")
            st.table(v_dia.groupby("Metodo Pago")["Total"].sum())
            
            output = io.BytesIO()
            try:
                with pd.ExcelWriter(output, engine='openpyxl') as wr:
                    v_dia.to_excel(wr, index=False)
                st.download_button("📥 Descargar Excel", output.getvalue(), f"cierre_{f_str}.xlsx")
            except:
                st.download_button("📥 Descargar CSV", v_dia.to_csv(index=False).encode('utf-8'), f"cierre_{f_str}.csv")
        else: st.warning("Sin ventas hoy")
