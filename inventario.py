import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io

# Importaciones para cámara y códigos
from PIL import Image
from pyzbar.pyzbar import decode
import numpy as np

# Configuración
st.set_page_config(page_title="POS Pro - Carrito de Compras", layout="centered")

DB_INVENTARIO = "inventario.csv"
DB_VENTAS = "ventas.csv"

# --- INICIALIZACIÓN DE MEMORIA (CARRITO) ---
if 'carrito' not in st.session_state:
    st.session_state.carrito = []

# --- FUNCIONES DE DATOS ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        df = pd.read_csv(archivo)
        for col in columnas:
            if col not in df.columns: df[col] = ""
        return df
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

# Cargar DBs
columnas_inv = ["Codigo", "Tiene_Codigo", "Producto", "Categoría", "Precio Venta", "Stock Actual", "Stock Mínimo"]
df_inv = cargar_datos(DB_INVENTARIO, columnas_inv)
df_ventas = cargar_datos(DB_VENTAS, ["Fecha", "Vendedor", "Producto", "Cantidad", "Total", "Metodo Pago", "Punto Salida"])

# --- SIDEBAR ---
st.sidebar.title("Configuración")
vendedor = st.sidebar.selectbox("👤 Vendedor", ["Admin", "Vendedor 1", "Vendedor 2"])
salida = st.sidebar.radio("📍 Punto de Salida", ["Salida 1", "Salida 2"])

pestana = st.tabs(["🛒 Punto de Venta", "📦 Inventario", "📊 Cierre Diario"])

# --- PESTAÑA 1: PUNTO DE VENTA (CON CARRITO) ---
with pestana[0]:
    st.subheader("🛒 Lista de Compra")
    
    col_izq, col_der = st.columns([1, 1])
    
    with col_izq:
        modo_busqueda = st.radio("Buscar por:", ["Código / Lector", "Cámara", "Nombre"], horizontal=True)
        producto_encontrado = None
        
        if modo_busqueda == "Código / Lector":
            cod_in = st.text_input("Escanea o escribe el código")
            if cod_in:
                res = df_inv[df_inv["Codigo"].astype(str) == cod_in]
                if not res.empty: producto_encontrado = res.iloc[0]
                else: st.error("No encontrado")
                
        elif modo_busqueda == "Cámara":
            foto = st.camera_input("Foto al código")
            if foto:
                decod = decode(np.array(Image.open(foto)))
                if decod:
                    c = decod[0].data.decode('utf-8')
                    res = df_inv[df_inv["Codigo"].astype(str) == c]
                    if not res.empty: producto_encontrado = res.iloc[0]
        else:
            nom_in = st.text_input("Nombre del producto")
            sug = df_inv[df_inv["Producto"].str.contains(nom_in, case=False)]["Producto"].tolist()
            sel = st.selectbox("Selecciona", ["-"] + sug)
            if sel != "-":
                producto_encontrado = df_inv[df_inv["Producto"] == sel].iloc[0]

    # SI SE ENCUENTRA UN PRODUCTO, MOSTRAR OPCIÓN DE AÑADIR
    with col_der:
        if producto_encontrado is not None:
            st.info(f"**{producto_encontrado['Producto']}**\n\nPrecio: ${producto_encontrado['Precio Venta']} | Stock: {producto_encontrado['Stock Actual']}")
            cant_add = st.number_input("Cantidad", min_value=1, max_value=int(producto_encontrado['Stock Actual']), value=1)
            
            if st.button("➕ Añadir al Carrito"):
                # Agregar al estado de la sesión
                st.session_state.carrito.append({
                    "Producto": producto_encontrado['Producto'],
                    "Precio": producto_encontrado['Precio Venta'],
