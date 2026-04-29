import streamlit as st
import pandas as pd
import os
from datetime import datetime
from PIL import Image
from pyzbar.pyzbar import decode
import numpy as np

# Configuración
st.set_page_config(page_title="Sistema POS Pro", layout="centered")

# Archivos de base de datos
DB_INVENTARIO = "inventario.csv"
DB_VENTAS = "ventas.csv"

def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        df = pd.read_csv(archivo)
        # Asegurar que todas las columnas existan
        for col in columnas:
            if col not in df.columns:
                df[col] = ""
        return df
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

# Inicializar DataFrames
columnas_inv = ["Codigo", "Tiene_Codigo", "Producto", "Categoría", "Precio Venta", "Stock Actual", "Stock Mínimo"]
df_inv = cargar_datos(DB_INVENTARIO, columnas_inv)
df_ventas = cargar_datos(DB_VENTAS, ["Fecha", "Vendedor", "Producto", "Cantidad", "Total", "Metodo Pago", "Punto Salida"])

# --- SIDEBAR (USUARIO Y SALIDA) ---
st.sidebar.title("Configuración")
vendedor = st.sidebar.selectbox("👤 Vendedor", ["Admin", "Vendedor 1", "Vendedor 2"])
salida = st.sidebar.radio("📍 Punto de Salida", ["Salida 1", "Salida 2"])

pestana = st.tabs(["🛒 Vender", "📦 Inventario", "📊 Reportes"])

# --- PESTAÑA 1: VENDER ---
with pestana[0]:
    st.subheader("Registrar Salida")
    
    opcion_venta = st.radio("Método de búsqueda", ["Escanear", "Búsqueda Manual (Sin Código)"], horizontal=True)
    
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
                    st.error("Código no registrado")
    else:
        # Buscador para productos sin código
        busqueda_v = st.text_input("Escribe nombre del producto...")
        sugerencias = df_inv[df_inv["Producto"].str.contains(busqueda_v, case=False)]["Producto"].tolist()
        producto_encontrado = st.selectbox("Selecciona producto", sugerencias)

    with st.form("form_vender"):
        cant = st.number_input("Cantidad", min_value=1, value=1)
        pago = st.selectbox("Forma de Pago", ["Pago Móvil", "Punto", "Zelle", "Binance", "Efectivo"])
        confirmar = st.form_submit_button("✅ Procesar Venta")
        
        if confirmar and producto_encontrado:
            idx = df_inv[df_inv["Producto"] == producto_encontrado].index[0]
            if df_inv.at[idx, "Stock Actual"] >= cant:
                # Restar stock
                df_inv.at[idx, "Stock Actual"] -= cant
                guardar_datos(df_inv, DB_INVENTARIO)
                # Registrar venta
                nueva_v = pd.DataFrame([{
                    "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "Vendedor": vendedor, "Producto": producto_encontrado,
                    "Cantidad": cant, "Total": df_inv.at[idx, "Precio Venta"] * cant,
                    "Metodo Pago": pago, "Punto Salida": salida
                }])
                df_ventas = pd.concat([df_ventas, nueva_v], ignore_index=True)
                guardar_datos(df_ventas, DB_VENTAS)
                st.success("¡Venta Exitosa!")
                st.rerun()
            else:
                st.error("No hay suficiente stock")

# --- PESTAÑA 2: INVENTARIO ---
with pestana[1]:
    st.subheader("Gestión de Inventario")
    
    # Botón para mostrar/ocultar formulario de agregar
    if "mostrar_form" not in st.session_state:
        st.session_state.mostrar_form = False

    if st.button("➕ AGREGAR NUEVO PRODUCTO"):
        st.session_state.mostrar_form = not st.session_state.mostrar_form

    if st.session_state.mostrar_form:
        with st.container():
            st.markdown("---")
            st.write("### Datos del Nuevo Producto")
            tiene_cod = st.radio("¿Tiene código físico?", ["Sí", "No"], horizontal=True)
            
            with st.form("form_nuevo_prod", clear_on_submit=True):
                col1, col2 = st.columns(2)
                cod_f = col1.text_input("Código Físico", disabled=(tiene_cod == "No"))
                nom_p = col2.text_input("Nombre del Producto")
                cat_p = st.selectbox("Categoría", ["Alimentos", "Bebidas", "Limpieza", "Otros"])
                pre_p = st.number_input("Precio de Venta", min_value=0.0)
                sto_p = st.number_input("Stock Inicial", min_value=0)
                
                if st.form_submit_button("Guardar Producto"):
                    if nom_p:
                        nuevo_p = pd.DataFrame([{
                            "Codigo": cod_f if tiene_cod == "Sí" else "SIN_CODIGO",
                            "Tiene_Codigo": tiene_cod,
                            "Producto": nom_p,
                            "Categoría": cat_p,
                            "Precio Venta": pre_p,
                            "Stock Actual": sto_p,
                            "Stock Mínimo": 5
                        }])
                        df_inv = pd.concat([df_inv, nuevo_p], ignore_index=True)
                        guardar_datos(df_inv, DB_INVENTARIO)
                        st.session_state.mostrar_form = False
                        st.success("Guardado correctamente")
                        st.rerun()
                    else:
                        st.warning("El nombre es obligatorio")
            st.markdown("---")

    # BUSCADOR Y TABLA
    st.write("### Lista de Productos")
    busqueda_inv = st.text_input("🔍 Buscar por nombre o código...")
    filtro_sin_cod = st.checkbox("Ver solo productos SIN código")
    
    df_filtrado = df_inv.copy()
    if busqueda_inv:
        df_filtrado = df_filtrado[df_filtrado["Producto"].str.contains(busqueda_inv, case=False) | 
                                 df_filtrado["Codigo"].astype(str).str.contains(busqueda_inv)]
    if filtro_sin_cod:
        df_filtrado = df_filtrado[df_filtrado["Tiene_Codigo"] == "No"]

    st.dataframe(df_filtrado, use_container_width=True)

# --- PESTAÑA 3: REPORTES ---
with pestana[2]:
    st.subheader("Resumen de Operaciones")
    col_m1, col_m2 = st.columns(2)
    col_m1.metric("Ventas Totales", f"{len(df_ventas)}")
    col_m2.metric("Monto Total", f"${df_ventas['Total'].sum():,.2f}")
    
    st.write("#### Últimas transacciones")
    st.table(df_ventas.tail(10))
