import streamlit as st
import pandas as pd
import os
from datetime import datetime
from PIL import Image
from pyzbar.pyzbar import decode
import numpy as np

# Configuración
st.set_page_config(page_title="Sistema de Ventas Pro", layout="centered")

# Archivos de base de datos
DB_INVENTARIO = "inventario.csv"
DB_VENTAS = "ventas.csv"

def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        return pd.read_csv(archivo)
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

# Inicializar DataFrames
df_inv = cargar_datos(DB_INVENTARIO, ["Codigo", "Producto", "Categoría", "Precio Venta", "Stock Actual", "Stock Mínimo"])
df_ventas = cargar_datos(DB_VENTAS, ["Fecha", "Vendedor", "Producto", "Cantidad", "Total", "Metodo Pago", "Punto Salida"])

# --- INTERFAZ ---
st.title("🚀 Punto de Venta & Inventario")

# 1. IDENTIFICACIÓN DE USUARIO (VENDEDOR)
vendedor = st.sidebar.selectbox("👤 Selecciona Vendedor", ["Admin", "Vendedor 1", "Vendedor 2", "Otro"])
salida = st.sidebar.radio("📍 Punto de Salida", ["Salida 1", "Salida 2"])

pestana = st.tabs(["🛒 Vender", "📦 Inventario", "📊 Reporte Ventas"])

# --- PESTAÑA 1: VENDER ---
with pestana[0]:
    st.subheader("Registrar Venta")
    
    # Opción de Escáner
    foto = st.camera_input("Escanear código para vender")
    codigo_buscado = ""
    
    if foto:
        imagen = Image.open(foto)
        codigos = decode(np.array(imagen))
        if codigos:
            codigo_buscado = codigos[0].data.decode('utf-8')
            st.success(f"Código detectado: {codigo_buscado}")
    
    # Formulario de venta
    with st.form("form_venta"):
        # Si escaneó algo, buscamos el nombre, si no, usamos buscador manual
        lista_productos = df_inv["Producto"].tolist()
        
        prod_nombre = st.selectbox("Producto", lista_productos)
        cantidad = st.number_input("Cantidad", min_value=1, value=1)
        
        metodo_pago = st.selectbox("Método de Pago", 
                                  ["Pago Móvil", "Punto", "Zelle", "Binance", "Efectivo"])
        
        btn_vender = st.form_submit_button("Finalizar Venta 💰")

    if btn_vender:
        # Lógica de procesamiento de venta
        idx = df_inv[df_inv["Producto"] == prod_nombre].index[0]
        stock_actual = df_inv.at[idx, "Stock Actual"]
        precio_v = df_inv.at[idx, "Precio Venta"]
        
        if stock_actual >= cantidad:
            # 1. Restar del inventario
            df_inv.at[idx, "Stock Actual"] -= cantidad
            guardar_datos(df_inv, DB_INVENTARIO)
            
            # 2. Registrar en ventas
            nueva_venta = pd.DataFrame([{
                "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Vendedor": vendedor,
                "Producto": prod_nombre,
                "Cantidad": cantidad,
                "Total": precio_v * cantidad,
                "Metodo Pago": metodo_pago,
                "Punto Salida": salida
            }])
            df_ventas = pd.concat([df_ventas, nueva_venta], ignore_index=True)
            guardar_datos(df_ventas, DB_VENTAS)
            
            st.balloons()
            st.success(f"Venta realizada: {cantidad}x {prod_nombre} via {metodo_pago}")
            st.rerun()
        else:
            st.error(f"¡Error! Stock insuficiente. Solo quedan {stock_actual}")

# --- PESTAÑA 2: INVENTARIO ---
with pestana[1]:
    st.subheader("Control de Stock")
    
    # Mostrar tabla con alertas de color
    def color_stock(val):
        color = 'red' if val <= 5 else 'black' # Alerta si quedan 5 o menos
        return f'color: {color}'

    st.dataframe(df_inv.style.applymap(color_stock, subset=['Stock Actual']), use_container_width=True)
    
    with st.expander("➕ Agregar / Editar Producto"):
        with st.form("nuevo_p"):
            f_cod = st.text_input("Código de Barras")
            f_nom = st.text_input("Nombre del Producto")
            f_cat = st.selectbox("Categoría", ["General", "Alimentos", "Bebidas", "Limpieza"])
            f_pre = st.number_input("Precio Venta", min_value=0.0)
            f_sto = st.number_input("Stock Inicial", min_value=0)
            f_min = st.number_input("Mínimo Alerta", min_value=5)
            
            if st.form_submit_button("Guardar en Sistema"):
                nuevo = pd.DataFrame([[f_cod, f_nom, f_cat, f_pre, f_sto, f_min]], columns=df_inv.columns)
                df_inv = pd.concat([df_inv, nuevo], ignore_index=True)
                guardar_datos(df_inv, DB_INVENTARIO)
                st.success("Producto registrado")
                st.rerun()

# --- PESTAÑA 3: REPORTE ---
with pestana[2]:
    st.subheader("Historial de Ventas")
    st.write(f"Total vendido hoy: **${df_ventas['Total'].sum():,.2f}**")
    
    # Filtros rápidos
    col_f1, col_f2 = st.columns(2)
    filtro_pago = col_f1.multiselect("Filtrar por Pago", df_ventas["Metodo Pago"].unique())
    filtro_salida = col_f2.multiselect("Filtrar por Salida", ["Salida 1", "Salida 2"])
    
    temp_ventas = df_ventas.copy()
    if filtro_pago:
        temp_ventas = temp_ventas[temp_ventas["Metodo Pago"].isin(filtro_pago)]
    if filtro_salida:
        temp_ventas = temp_ventas[temp_ventas["Punto Salida"].isin(filtro_salida)]
        
    st.dataframe(temp_ventas.sort_values(by="Fecha", ascending=False), use_container_width=True)
    
    if st.button("🗑️ Limpiar Historial de Ventas"):
        if os.path.exists(DB_VENTAS):
            os.remove(DB_VENTAS)
            st.rerun()
