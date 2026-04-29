import streamlit as st
import pandas as pd
import os
from PIL import Image
from pyzbar.pyzbar import decode
import cv2
import numpy as np

# Configuración
st.set_page_config(page_title="Inventario con Scan", layout="centered")

ARCHIVO_DB = "inventario.csv"

def cargar_datos():
    if os.path.exists(ARCHIVO_DB):
        return pd.read_csv(ARCHIVO_DB)
    # Añadimos la columna 'Codigo' a la estructura
    return pd.DataFrame(columns=["Codigo", "Producto", "Categoría", "Precio Venta", "Stock Actual", "Stock Mínimo"])

def guardar_datos(df):
    df.to_csv(ARCHIVO_DB, index=False)

df = cargar_datos()

st.title("📦 Inventario con Escáner")

# --- SECCIÓN DEL ESCÁNER ---
st.subheader("📷 Escanear Producto")
foto = st.camera_input("Toma una foto al código de barras")

if foto:
    # Procesar la imagen
    imagen = Image.open(foto)
    imagen_np = np.array(imagen)
    codigos = decode(imagen_np)
    
    if codigos:
        codigo_detectado = codigos[0].data.decode('utf-8')
        st.success(f"Código detectado: {codigo_detectado}")
        
        # Buscar en el inventario
        item = df[df["Codigo"].astype(str) == codigo_detectado]
        
        if not item.empty:
            idx = item.index[0]
            st.write(f"**Producto:** {df.at[idx, 'Producto']}")
            st.write(f"**Stock actual:** {df.at[idx, 'Stock Actual']}")
            
            c1, c2 = st.columns(2)
            if c1.button("➕ Sumar 1"):
                df.at[idx, "Stock Actual"] += 1
                guardar_datos(df)
                st.rerun()
            if c2.button("➖ Restar 1"):
                df.at[idx, "Stock Actual"] -= 1
                guardar_datos(df)
                st.rerun()
        else:
            st.warning("El código no está registrado.")
            if st.button("Registrar como nuevo producto"):
                st.session_state.nuevo_codigo = codigo_detectado
    else:
        st.error("No se detectó ningún código. Intenta acercar más la cámara o mejorar la luz.")

st.divider()

# --- BUSCADOR Y LISTA ---
busqueda = st.text_input("🔍 Buscar por nombre...")
df_mostrar = df[df["Producto"].str.contains(busqueda, case=False)] if busqueda else df
st.dataframe(df_mostrar, use_container_width=True)

# --- FORMULARIO PARA AGREGAR ---
with st.expander("➕ Agregar / Editar Producto"):
    # Si detectamos un código nuevo, lo precargamos aquí
    codigo_pre = st.session_state.get('nuevo_codigo', "")
    
    with st.form("nuevo_p"):
        f_cod = st.text_input("Código de Barras", value=codigo_pre)
        f_nom = st.text_input("Nombre del Producto")
        f_cat = st.selectbox("Categoría", ["General", "Alimentos", "Bebidas", "Limpieza"])
        f_pre = st.number_input("Precio Venta", min_value=0.0)
        f_sto = st.number_input("Stock Inicial", min_value=0)
        f_min = st.number_input("Mínimo Alerta", min_value=0)
        
        if st.form_submit_button("Guardar"):
            nuevo = pd.DataFrame([[f_cod, f_nom, f_cat, f_pre, f_sto, f_min]], columns=df.columns)
            df = pd.concat([df, nuevo], ignore_index=True)
            guardar_datos(df)
            if 'nuevo_codigo' in st.session_state:
                del st.session_state.nuevo_codigo
            st.rerun()
