import streamlit as st
import pandas as pd
import os

# Configuración optimizada para móvil
st.set_page_config(page_title="Inventario Celular", layout="centered")

ARCHIVO_DB = "inventario.csv"

def cargar_datos():
    if os.path.exists(ARCHIVO_DB):
        return pd.read_csv(ARCHIVO_DB)
    return pd.DataFrame(columns=["Producto", "Categoría", "Precio Venta", "Stock Actual", "Stock Mínimo"])

def guardar_datos(df):
    df.to_csv(ARCHIVO_DB, index=False)

df = cargar_datos()

st.title("📱 Mi Inventario")

# --- MODO LECTURA DE STOCK ---
st.subheader("Resumen rápido")
col1, col2 = st.columns(2)
bajo_stock = df[df["Stock Actual"] <= df["Stock Mínimo"]]
col1.metric("Total", len(df))
col2.metric("Alertas", len(bajo_stock))

# --- BUSCADOR ---
busqueda = st.text_input("🔍 Buscar producto...")
if busqueda:
    df_mostrar = df[df["Producto"].str.contains(busqueda, case=False)]
else:
    df_mostrar = df

# --- LISTA TÁCTIL ---
for i, row in df_mostrar.iterrows():
    with st.expander(f"{row['Producto']} - Stock: {row['Stock Actual']}"):
        st.write(f"Categoría: {row['Categoría']}")
        st.write(f"Precio: ${row['Precio Venta']}")
        
        # Botones grandes para el dedo
        c1, c2 = st.columns(2)
        if c1.button(f"➕ Sumar", key=f"add_{i}"):
            df.at[i, "Stock Actual"] += 1
            guardar_datos(df)
            st.rerun()
            
        if c2.button(f"➖ Restar", key=f"rem_{i}"):
            if df.at[i, "Stock Actual"] > 0:
                df.at[i, "Stock Actual"] -= 1
                guardar_datos(df)
                st.rerun()

st.divider()

# --- AGREGAR PRODUCTO (BOTÓN FLOTANTE AL FINAL) ---
with st.expander("➕ Agregar Nuevo Producto"):
    nombre = st.text_input("Nombre")
    cat = st.selectbox("Categoría", ["General", "Bebidas", "Alimentos", "Limpieza"])
    precio = st.number_input("Precio Venta", min_value=0.0)
    stock = st.number_input("Stock Inicial", min_value=0)
    minimo = st.number_input("Mínimo para alerta", min_value=0)
    
    if st.button("Guardar Producto"):
        nuevo = pd.DataFrame([[nombre, cat, precio, stock, minimo]], columns=df.columns)
        df = pd.concat([df, nuevo], ignore_index=True)
        guardar_datos(df)
        st.success("¡Guardado!")
        st.rerun()