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
st.set_page_config(page_title="POS Pro - Cierre Diario", layout="centered")

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
df_inv = cargar_datos(DB_INVENTARIO, ["Codigo", "Tiene_Codigo", "Producto", "Categoría", "Precio Venta", "Stock Actual", "Stock Mínimo"])
df_ventas = cargar_datos(DB_VENTAS, ["Fecha", "Vendedor", "Producto", "Cantidad", "Total", "Metodo Pago", "Punto Salida"])

# --- SIDEBAR ---
st.sidebar.title("Configuración")
vendedor = st.sidebar.selectbox("👤 Vendedor", ["Admin", "Vendedor 1", "Vendedor 2"])
salida = st.sidebar.radio("📍 Punto de Salida", ["Salida 1", "Salida 2"])

pestana = st.tabs(["🛒 Vender", "📦 Inventario", "📊 Cierre Diario"])

# --- PESTAÑA 1: VENDER (Sin cambios importantes) ---
with pestana[0]:
    st.subheader("Registrar Salida")
    opcion_venta = st.radio("Método", ["Escanear", "Búsqueda Manual"], horizontal=True)
    producto_encontrado = None
    
    if opcion_venta == "Escanear":
        foto = st.camera_input("Enfoca el código")
        if foto:
            img = Image.open(foto)
            decodificado = decode(np.array(img))
            if decodificado:
                cod = decodificado[0].data.decode('utf-8')
                res = df_inv[df_inv["Codigo"].astype(str) == cod]
                if not res.empty:
                    producto_encontrado = res.iloc[0]["Producto"]
                    st.success(f"Detectado: {producto_encontrado}")
    else:
        busqueda_v = st.text_input("Escribe nombre...")
        sugerencias = df_inv[df_inv["Producto"].str.contains(busqueda_v, case=False)]["Producto"].tolist()
        producto_encontrado = st.selectbox("Selecciona", sugerencias)

    with st.form("form_vender"):
        cant = st.number_input("Cantidad", min_value=1, value=1)
        pago = st.selectbox("Forma de Pago", ["Pago Móvil", "Punto", "Zelle", "Binance", "Efectivo"])
        if st.form_submit_button("✅ Procesar Venta") and producto_encontrado:
            idx = df_inv[df_inv["Producto"] == producto_encontrado].index[0]
            if df_inv.at[idx, "Stock Actual"] >= cant:
                df_inv.at[idx, "Stock Actual"] -= cant
                guardar_datos(df_inv, DB_INVENTARIO)
                nueva_v = pd.DataFrame([{
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Vendedor": vendedor, "Producto": producto_encontrado,
                    "Cantidad": cant, "Total": df_inv.at[idx, "Precio Venta"] * cant,
                    "Metodo Pago": pago, "Punto Salida": salida
                }])
                df_ventas = pd.concat([df_ventas, nueva_v], ignore_index=True)
                guardar_datos(df_ventas, DB_VENTAS)
                st.success("¡Venta Exitosa!")
                st.rerun()

# --- PESTAÑA 2: INVENTARIO (Botón agregar e interfaz nueva) ---
with pestana[1]:
    st.subheader("Gestión de Inventario")
    if st.button("➕ AGREGAR NUEVO PRODUCTO"):
        st.session_state.mostrar_form = not st.session_state.get('mostrar_form', False)

    if st.session_state.get('mostrar_form', False):
        with st.form("form_nuevo_prod"):
            tiene_cod = st.radio("¿Tiene código?", ["Sí", "No"], horizontal=True)
            cod_f = st.text_input("Código Físico")
            nom_p = st.text_input("Nombre")
            pre_p = st.number_input("Precio", min_value=0.0)
            sto_p = st.number_input("Stock", min_value=0)
            if st.form_submit_button("Guardar"):
                nuevo_p = pd.DataFrame([{"Codigo": cod_f if tiene_cod=="Sí" else "SIN_CODIGO", "Tiene_Codigo": tiene_cod, "Producto": nom_p, "Categoría": "General", "Precio Venta": pre_p, "Stock Actual": sto_p, "Stock Mínimo": 5}])
                df_inv = pd.concat([df_inv, nuevo_p], ignore_index=True)
                guardar_datos(df_inv, DB_INVENTARIO)
                st.rerun()

    st.dataframe(df_inv, use_container_width=True)

# --- PESTAÑA 3: CIERRE DIARIO ---
with pestana[2]:
    st.subheader("📊 Reporte de Cierre")
    
    # Selector de fecha para el cierre
    fecha_cierre = st.date_input("Selecciona el día para el cierre", datetime.now())
    fecha_str = fecha_cierre.strftime("%Y-%m-%d")
    
    # Filtrar ventas del día
    ventas_hoy = df_ventas[df_ventas["Fecha"].str.contains(fecha_str)]
    
    if not ventas_hoy.empty:
        # Métricas principales
        total_dinero = ventas_hoy["Total"].sum()
        st.metric("INGRESO TOTAL DEL DÍA", f"${total_dinero:,.2f}")
        
        col_c1, col_c2 = st.columns(2)
        
        # Resumen por Método de Pago
        with col_c1:
            st.write("**Por Método de Pago:**")
            resumen_pago = ventas_hoy.groupby("Metodo Pago")["Total"].sum()
            st.dataframe(resumen_pago)
            
        # Resumen por Punto de Salida
        with col_c2:
            st.write("**Por Punto de Salida:**")
            resumen_salida = ventas_hoy.groupby("Punto Salida")["Total"].sum()
            st.dataframe(resumen_salida)

        st.write("**Detalle de productos vendidos:**")
        detalle_prod = ventas_hoy.groupby("Producto")["Cantidad"].sum().reset_index()
        st.table(detalle_prod)

        # --- FUNCIÓN PARA DESCARGAR EXCEL ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            ventas_hoy.to_excel(writer, index=False, sheet_name='Ventas_Detalladas')
            resumen_pago.to_excel(writer, sheet_name='Resumen_Pagos')
            detalle_prod.to_excel(writer, index=False, sheet_name='Resumen_Productos')
        
        st.download_button(
            label="📥 Descargar Cierre en Excel",
            data=output.getvalue(),
            file_name=f"cierre_{fecha_str}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning(f"No hay ventas registradas el día {fecha_str}")
