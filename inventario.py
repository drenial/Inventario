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
st.set_page_config(page_title="POS & Servicios", page_icon="🛠️", layout="centered")

# Estilo para ocultar menús de Streamlit
st.markdown("<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}</style>", unsafe_allow_html=True)

DB_INV = "inventario.csv"
DB_VEN = "ventas.csv"

if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False

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

# Columnas actualizadas para incluir servicios
C_INV = ["Codigo", "Tiene_Codigo", "Producto", "Categoría", "Precio Venta", "Stock Actual", "Stock Mínimo"]
C_VEN = ["Fecha", "Vendedor", "Producto", "Cantidad", "Total", "Metodo Pago", "Punto Salida", "Ayudante", "Descripcion", "Modelo Carro"]

df_inv = cargar_datos(DB_INV, C_INV)
df_ven = cargar_datos(DB_VEN, C_VEN)

# --- SIDEBAR (ACCESO) ---
st.sidebar.title("🔐 Acceso")
if not st.session_state.admin_auth:
    password = st.sidebar.text_input("Clave de Admin", type="password")
    if st.sidebar.button("Entrar"):
        if password == CLAVE_ADMIN:
            st.session_state.admin_auth = True
            st.rerun()
else:
    st.sidebar.success("Modo Admin")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.admin_auth = False
        st.rerun()

vendedor_fijo = st.sidebar.selectbox("👤 Vendedor/Técnico", ["Vendedor 1", "Vendedor 2", "Admin"])
salida = st.sidebar.radio("📍 Punto", ["Salida 1", "Salida 2"])

pestanas = st.tabs(["🛒 Punto de Venta", "📦 Inventario", "📊 Cierre Diario"]) if st.session_state.admin_auth else st.tabs(["🛒 Punto de Venta"])

# --- PESTAÑA 1: PUNTO DE VENTA ---
with pestanas[0]:
    st.subheader("🛒 Facturación")
    
    tipo_item = st.radio("¿Qué deseas agregar?", ["🛒 Producto", "🛠️ Trabajo/Servicio"], horizontal=True)
    p_encontrado = None

    if tipo_item == "🛒 Producto":
        c_b1, c_b2 = st.columns(2)
        with c_b1:
            modo = st.radio("Buscar por:", ["Código", "Nombre"], horizontal=True)
            if modo == "Código":
                cod_in = st.text_input("Escanear/Escribir Código")
                if cod_in:
                    res = df_inv[df_inv["Codigo"].astype(str) == str(cod_in)]
                    if not res.empty: p_encontrado = res.iloc[0]
            else:
                nom_in = st.text_input("Nombre del producto")
                if nom_in:
                    sug = df_inv[df_inv["Producto"].str.contains(nom_in, case=False)]["Producto"].tolist()
                    sel = st.selectbox("Seleccionar", ["-"] + sug)
                    if sel != "-": p_encontrado = df_inv[df_inv["Producto"] == sel].iloc[0]
        
        with c_b2:
            if p_encontrado is not None:
                st.info(f"**{p_encontrado['Producto']}**\n\nPrecio: ${p_encontrado['Precio Venta']}")
                cant = st.number_input("Cant", min_value=1, max_value=max(1, int(p_encontrado['Stock Actual'])), value=1)
                if st.button("➕ Añadir Producto"):
                    st.session_state.carrito.append({
                        "Tipo": "Producto", "Producto": p_encontrado['Producto'],
                        "Precio": float(p_encontrado['Precio Venta']), "Cantidad": int(cant),
                        "Subtotal": float(p_encontrado['Precio Venta'] * cant),
                        "Ayudante": "", "Descripcion": "Venta de repuesto", "Modelo Carro": ""
                    })
                    st.rerun()
    
    else: # SECCIÓN DE TRABAJO/SERVICIO
        with st.container():
            st.info("🛠️ Registro de Mano de Obra / Trabajo")
            c_t1, c_t2 = st.columns(2)
            with c_t1:
                desc_trabajo = st.text_area("¿Qué trabajo se realizó?", placeholder="Ej: Cambio de aceite y filtro")
                modelo_carro = st.text_input("Modelo del Carro (Opcional)")
            with c_t2:
                ayudante = st.text_input("Nombre del Ayudante (Opcional)")
                precio_trabajo = st.number_input("Costo del Trabajo ($)", min_value=0.0, step=1.0)
            
            if st.button("➕ Añadir Trabajo al Carrito"):
                if desc_trabajo and precio_trabajo > 0:
                    st.session_state.carrito.append({
                        "Tipo": "Trabajo", "Producto": "SERVICIO: " + desc_trabajo[:20] + "...",
                        "Precio": float(precio_trabajo), "Cantidad": 1,
                        "Subtotal": float(precio_trabajo),
                        "Ayudante": ayudante, "Descripcion": desc_trabajo, "Modelo Carro": modelo_carro
                    })
                    st.success("Trabajo añadido")
                    st.rerun()
                else: st.warning("Por favor rellena descripción y precio")

    st.divider()
    
    if st.session_state.carrito:
        st.write("### Detalle de Factura")
        for i, item in enumerate(st.session_state.carrito):
            c_it, c_dl = st.columns([4, 1])
            tipo_icon = "📦" if item["Tipo"] == "Producto" else "🛠️"
            c_it.write(f"{tipo_icon} **{item['Cantidad']}x** {item['Producto']} — ${item['Subtotal']:,.2f}")
            if c_dl.button("🗑️", key=f"del_{i}"):
                st.session_state.carrito.pop(i); st.rerun()
        
        total_p = sum(it['Subtotal'] for it in st.session_state.carrito)
        st.markdown(f"## TOTAL A COBRAR: ${total_p:,.2f}")
        metodo = st.selectbox("Método de Pago", ["Pago Móvil", "Punto", "Zelle", "Binance", "Efectivo"])
        
        cb1, cb2 = st.columns(2)
        if cb1.button("✅ PROCESAR TODO", use_container_width=True):
            for item in st.session_state.carrito:
                # Si es producto, restar stock
                if item["Tipo"] == "Producto":
                    idx = df_inv[df_inv["Producto"] == item["Producto"]].index[0]
                    df_inv.at[idx, "Stock Actual"] -= item["Cantidad"]
                
                # Registrar en ventas (Producto o Trabajo)
                nv = pd.DataFrame([{
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Vendedor": vendedor_fijo, "Producto": item["Producto"],
                    "Cantidad": item["Cantidad"], "Total": item["Subtotal"],
                    "Metodo Pago": metodo, "Punto Salida": salida,
                    "Ayudante": item["Ayudante"], "Descripcion": item["Descripcion"],
                    "Modelo Carro": item["Modelo Carro"]
                }])
                df_ven = pd.concat([df_ven, nv], ignore_index=True)
            
            guardar_datos(df_inv, DB_INV); guardar_datos
