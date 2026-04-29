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
st.set_page_config(page_title="POS Pro - Ventas Rápidas", layout="centered")

DB_INVENTARIO = "inventario.csv"
DB_VENTAS = "ventas.csv"

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

# Inicializar
columnas_inv = ["Codigo", "Tiene_Codigo", "Producto", "Categoría", "Precio Venta", "Stock Actual", "Stock Mínimo"]
df_inv = cargar_datos(DB_INVENTARIO, columnas_inv)
df_ventas = cargar_datos(DB_VENTAS, ["Fecha", "Vendedor", "Producto", "Cantidad", "Total", "Metodo Pago", "Punto Salida"])

# --- SIDEBAR ---
st.sidebar.title("Configuración")
vendedor = st.sidebar.selectbox("👤 Vendedor", ["Admin", "Vendedor 1", "Vendedor 2"])
salida = st.sidebar.radio("📍 Punto de Salida", ["Salida 1", "Salida 2"])

pestana = st.tabs(["🛒 Vender", "📦 Inventario", "📊 Cierre Diario"])

# --- PESTAÑA 1: VENDER ---
with pestana[0]:
    st.subheader("Registrar Salida")
    
    # 3 OPCIONES DE BÚSQUEDA
    modo_busqueda = st.radio("Buscar por:", ["Código Manual / Lector", "Cámara (Escanear)", "Nombre del Producto"], horizontal=True)
    
    producto_seleccionado = None
    
    # 1. Búsqueda por Código Manual o Lector Físico
    if modo_busqueda == "Código Manual / Lector":
        codigo_input = st.text_input("Escribe o escanea el código aquí y presiona Enter", key="cod_manual")
        if codigo_input:
            resultado = df_inv[df_inv["Codigo"].astype(str) == codigo_input]
            if not resultado.empty:
                producto_seleccionado = resultado.iloc[0]["Producto"]
                st.info(f"📦 Producto: {producto_seleccionado} | Precio: ${resultado.iloc[0]['Precio Venta']}")
            else:
                st.error("Código no encontrado en inventario")

    # 2. Búsqueda por Cámara
    elif modo_busqueda == "Cámara (Escanear)":
        foto = st.camera_input("Toma foto al código")
        if foto:
            img = Image.open(foto)
            decodificado = decode(np.array(img))
            if decodificado:
                cod = decodificado[0].data.decode('utf-8')
                resultado = df_inv[df_inv["Codigo"].astype(str) == cod]
                if not resultado.empty:
                    producto_seleccionado = resultado.iloc[0]["Producto"]
                    st.success(f"Detectado: {producto_seleccionado}")
                else:
                    st.error(f"Código {cod} no registrado")

    # 3. Búsqueda por Nombre
    else:
        nombre_input = st.text_input("Escribe el nombre del producto...")
        sugerencias = df_inv[df_inv["Producto"].str.contains(nombre_input, case=False)]["Producto"].tolist()
        producto_seleccionado = st.selectbox("Selecciona de la lista", ["Seleccione..."] + sugerencias)
        if producto_seleccionado == "Seleccione...": producto_seleccionado = None

    # FORMULARIO FINAL DE VENTA
    if producto_seleccionado:
        with st.form("confirmar_venta"):
            st.write(f"### Vendiendo: {producto_seleccionado}")
            cant = st.number_input("Cantidad a vender", min_value=1, value=1)
            pago = st.selectbox("Método de Pago", ["Pago Móvil", "Punto", "Zelle", "Binance", "Efectivo"])
            
            if st.form_submit_button("💰 PROCESAR VENTA"):
                idx = df_inv[df_inv["Producto"] == producto_seleccionado].index[0]
                if df_inv.at[idx, "Stock Actual"] >= cant:
                    # Restar stock
                    df_inv.at[idx, "Stock Actual"] -= cant
                    guardar_datos(df_inv, DB_INVENTARIO)
                    # Registrar venta
                    nueva_v = pd.DataFrame([{
                        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Vendedor": vendedor, "Producto": producto_seleccionado,
                        "Cantidad": cant, "Total": df_inv.at[idx, "Precio Venta"] * cant,
                        "Metodo Pago": pago, "Punto Salida": salida
                    }])
                    df_ventas = pd.concat([df_ventas, nueva_v], ignore_index=True)
                    guardar_datos(df_ventas, DB_VENTAS)
                    st.success(f"Vendido: {cant} {producto_seleccionado}")
                    st.rerun()
                else:
                    st.error("No hay stock suficiente")

# --- PESTAÑA 2: INVENTARIO ---
with pestana[1]:
    st.subheader("Gestión de Inventario")
    if st.button("➕ AGREGAR NUEVO PRODUCTO"):
        st.session_state.mostrar_form = not st.session_state.get('mostrar_form', False)

    if st.session_state.get('mostrar_form', False):
        with st.form("form_nuevo_p"):
            tiene_c = st.radio("¿Tiene código?", ["Sí", "No"], horizontal=True)
            cod_f = st.text_input("Código de Barras / Físico")
            nom_p = st.text_input("Nombre del Producto")
            pre_p = st.number_input("Precio Venta", min_value=0.0)
            sto_p = st.number_input("Stock Inicial", min_value=0)
            if st.form_submit_button("Guardar Producto"):
                nuevo = pd.DataFrame([{"Codigo": cod_f if tiene_c=="Sí" else "SIN_CODIGO", "Tiene_Codigo": tiene_c, "Producto": nom_p, "Categoría": "General", "Precio Venta": pre_p, "Stock Actual": sto_p, "Stock Mínimo": 5}])
                df_inv = pd.concat([df_inv, nuevo], ignore_index=True)
                guardar_datos(df_inv, DB_INVENTARIO)
                st.success("Registrado!")
                st.rerun()

    # Buscador en tabla
    busq = st.text_input("🔍 Buscar en inventario por nombre o código...")
    df_ver = df_inv[df_inv["Producto"].str.contains(busq, case=False) | df_inv["Codigo"].astype(str).str.contains(busq)]
    st.dataframe(df_ver, use_container_width=True)

# --- PESTAÑA 3: CIERRE DIARIO ---
with pestana[2]:
    st.subheader("📊 Reporte de Cierre")
    fecha_sel = st.date_input("Día del cierre", datetime.now())
    fecha_s = fecha_sel.strftime("%Y-%m-%d")
    v_dia = df_ventas[df_ventas["Fecha"].str.contains(fecha_s)]
    
    if not v_dia.empty:
        st.metric("INGRESO TOTAL", f"${v_dia['Total'].sum():,.2f}")
        st.write("**Desglose de Pagos:**")
        st.table(v_dia.groupby("Metodo Pago")["Total"].sum())
        
        # Descargar Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            v_dia.to_excel(writer, index=False, sheet_name='Cierre')
        st.download_button("📥 Descargar Cierre Excel", output.getvalue(), f"cierre_{fecha_s}.xlsx")
    else:
        st.warning("No hay ventas en esta fecha")
