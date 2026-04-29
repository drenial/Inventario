import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io
from PIL import Image
try:
    from pyzbar.pyzbar import decode
except:
    pass # Por si la librería de escáner tiene problemas en algún sistema
import numpy as np

# Configuración
st.set_page_config(page_title="POS Pro - Estable", layout="centered")

DB_INVENTARIO = "inventario.csv"
DB_VENTAS = "ventas.csv"

# --- INICIALIZACIÓN SEGURA DEL CARRITO ---
if 'carrito' not in st.session_state:
    st.session_state.carrito = []
if 'mostrar_form' not in st.session_state:
    st.session_state.mostrar_form = False

# --- FUNCIÓN PARA CARGAR DATOS SIN ERRORES ---
def cargar_datos(archivo, columnas_requeridas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            # Verificar si faltan columnas y agregarlas si es necesario
            for col in columnas_requeridas:
                if col not in df.columns:
                    df[col] = 0 if "Stock" in col or "Precio" in col else "N/A"
            return df[columnas_requeridas] # Retornar solo las columnas que necesitamos
        except:
            return pd.DataFrame(columns=columnas_requeridas)
    return pd.DataFrame(columns=columnas_requeridas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

# Columnas exactas para evitar errores
COL_INV = ["Codigo", "Tiene_Codigo", "Producto", "Categoría", "Precio Venta", "Stock Actual", "Stock Mínimo"]
COL_VEN = ["Fecha", "Vendedor", "Producto", "Cantidad", "Total", "Metodo Pago", "Punto Salida"]

df_inv = cargar_datos(DB_INVENTARIO, COL_INV)
df_ventas = cargar_datos(DB_VENTAS, COL_VEN)

# --- SIDEBAR ---
st.sidebar.title("Configuración")
vendedor = st.sidebar.selectbox("👤 Vendedor", ["Admin", "Vendedor 1", "Vendedor 2"])
salida = st.sidebar.radio("📍 Punto de Salida", ["Salida 1", "Salida 2"])

pestana = st.tabs(["🛒 Punto de Venta", "📦 Inventario", "📊 Cierre Diario"])

# --- PESTAÑA 1: PUNTO DE VENTA ---
with pestana[0]:
    st.subheader("🛒 Lista de Compra")
    
    col_izq, col_der = st.columns([1, 1])
    producto_encontrado = None
    
    with col_izq:
        modo = st.radio("Buscar por:", ["Código", "Cámara", "Nombre"], horizontal=True)
        if modo == "Código":
            cod_in = st.text_input("Escribe código")
            if cod_in:
                res = df_inv[df_inv["Codigo"].astype(str) == str(cod_in)]
                if not res.empty: producto_encontrado = res.iloc[0]
                else: st.error("No encontrado")
        elif modo == "Cámara":
            foto = st.camera_input("Foto")
            if foto:
                try:
                    decod = decode(np.array(Image.open(foto)))
                    if decod:
                        c = decod[0].data.decode('utf-8')
                        res = df_inv[df_inv["Codigo"].astype(str) == str(c)]
                        if not res.empty: producto_encontrado = res.iloc[0]
                except: st.error("Error al usar la cámara")
        else:
            nom_in = st.text_input("Nombre producto")
            if nom_in:
                sug = df_inv[df_inv["Producto"].str.contains(nom_in, case=False)]["Producto"].tolist()
                sel = st.selectbox("Selecciona", ["-"] + sug)
                if sel != "-":
                    producto_encontrado = df_inv[df_inv["Producto"] == sel].iloc[0]

    with col_der:
        if producto_encontrado is not None:
            st.info(f"**{producto_encontrado['Producto']}**\n\nPrecio: ${producto_encontrado['Precio Venta']}")
            cant_add = st.number_input("Cant", min_value=1, max_value=max(1, int(producto_encontrado['Stock Actual'])), value=1)
            if st.button("➕ Añadir"):
                st.session_state.carrito.append({
                    "Producto": producto_encontrado['Producto'],
                    "Precio": float(producto_encontrado['Precio Venta']),
                    "Cantidad": int(cant_add),
                    "Subtotal": float(producto_encontrado['Precio Venta'] * cant_add)
                })
                st.rerun()

    st.divider()
    if st.session_state.carrito:
        df_cart = pd.DataFrame(st.session_state.carrito)
        st.table(df_cart)
        total = df_cart["Subtotal"].sum()
        st.markdown(f"### TOTAL: ${total:,.2f}")
        
        metodo = st.selectbox("Pago", ["Pago Móvil", "Punto", "Zelle", "Binance", "Efectivo"])
        c1, c2 = st.columns(2)
        
        if c1.button("✅ FACTURAR", use_container_width=True):
            for item in st.session_state.carrito:
                # Restar stock
                if item["Producto"] in df_inv["Producto"].values:
                    idx = df_inv[df_inv["Producto"] == item["Producto"]].index[0]
                    df_inv.at[idx, "Stock Actual"] -= item["Cantidad"]
                
                # Registrar venta
                nueva_v = pd.DataFrame([{
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Vendedor": vendedor, "Producto": item["Producto"],
                    "Cantidad": item["Cantidad"], "Total": item["Subtotal"],
                    "Metodo Pago": metodo, "Punto Salida": salida
                }])
                df_ventas = pd.concat([df_ventas, nueva_v], ignore_index=True)
            
            guardar_datos(df_inv, DB_INVENTARIO)
            guardar_datos(df_ventas, DB_VENTAS)
            st.session_state.carrito = []
            st.success("Venta realizada")
            st.rerun()
            
        if c2.button("🗑️ CANCELAR", use_container_width=True):
            st.session_state.carrito = []
            st.rerun()

# --- PESTAÑA 2: INVENTARIO ---
with pestana[1]:
    st.subheader("Inventario")
    if st.button("➕ NUEVO PRODUCTO"):
        st.session_state.mostrar_form = not st.session_state.mostrar_form
    
    if st.session_state.mostrar_form:
        with st.form("f_nuevo"):
            t_c = st.radio("¿Código?", ["Sí", "No"], horizontal=True)
            c_f = st.text_input("Código")
            n_p = st.text_input("Nombre")
            p_p = st.number_input("Precio", min_value=0.0)
            s_p = st.number_input("Stock", min_value=0)
            if st.form_submit_button("Guardar"):
                if n_p:
                    nuevo = pd.DataFrame([{"Codigo": c_f if t_c=="Sí" else "SIN_CODIGO", "Tiene_Codigo": t_c, "Producto": n_p, "Categoría": "General", "Precio Venta": p_p, "Stock Actual": s_p, "Stock Mínimo": 5}])
                    df_inv = pd.concat([df_inv, nuevo], ignore_index=True)
                    guardar_datos(df_inv, DB_INVENTARIO)
                    st.session_state.mostrar_form = False
                    st.rerun()
    
    st.dataframe(df_inv, use_container_width=True)

# --- PESTAÑA 3: CIERRE ---
with pestana[2]:
    st.subheader("Cierre")
    f_sel = st.date_input("Día", datetime.now())
    v_dia = df_ventas[df_ventas["Fecha"].str.contains(f_sel.strftime("%Y-%m-%d"))]
    if not v_dia.empty:
        st.metric("TOTAL", f"${v_dia['Total'].sum():,.2f}")
        st.dataframe(v_dia)
        # Botón para borrar base de datos si hay errores críticos
        if st.sidebar.button("⚠️ RESETEAR TODO (BORRAR DATOS)"):
            if os.path.exists(DB_INVENTARIO): os.remove(DB_INVENTARIO)
            if os.path.exists(DB_VENTAS): os.remove(DB_VENTAS)
            st.rerun()
