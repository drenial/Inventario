import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io
from PIL import Image
try:
    from pyzbar.pyzbar import decode
except:
    pass
import numpy as np

# Configuración
st.set_page_config(page_title="POS Pro - Ajustes", layout="centered")

DB_INVENTARIO = "inventario.csv"
DB_VENTAS = "ventas.csv"

if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'mostrar_form' not in st.session_state: st.session_state.mostrar_form = False

def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            for col in columnas:
                if col not in df.columns: df[col] = 0 if "Stock" in col or "Precio" in col else "N/A"
            return df[columnas]
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

COL_INV = ["Codigo", "Tiene_Codigo", "Producto", "Categoría", "Precio Venta", "Stock Actual", "Stock Mínimo"]
COL_VEN = ["Fecha", "Vendedor", "Producto", "Cantidad", "Total", "Metodo Pago", "Punto Salida"]

df_inv = cargar_datos(DB_INVENTARIO, COL_INV)
df_ventas = cargar_datos(DB_VENTAS, COL_VEN)

# --- SIDEBAR ---
st.sidebar.title("Panel de Control")
vendedor = st.sidebar.selectbox("👤 Vendedor", ["Admin", "Vendedor 1", "Vendedor 2"])
salida = st.sidebar.radio("📍 Punto", ["Salida 1", "Salida 2"])

pestana = st.tabs(["🛒 Punto de Venta", "📦 Inventario", "📊 Cierre Diario"])

# --- PESTAÑA 1: PUNTO DE VENTA ---
with pestana[0]:
    st.subheader("🛒 Lista de Compra")
    c_izq, c_der = st.columns([1, 1])
    prod_encontrado = None
    
    with c_izq:
        modo = st.radio("Buscar por:", ["Código", "Nombre"], horizontal=True)
        if modo == "Código":
            cod_in = st.text_input("Escribe código")
            if cod_in:
                res = df_inv[df_inv["Codigo"].astype(str) == str(cod_in)]
                if not res.empty: prod_encontrado = res.iloc[0]
        else:
            nom_in = st.text_input("Nombre producto")
            if nom_in:
                sug = df_inv[df_inv["Producto"].str.contains(nom_in, case=False)]["Producto"].tolist()
                sel = st.selectbox("Selecciona", ["-"] + sug)
                if sel != "-": prod_encontrado = df_inv[df_inv["Producto"] == sel].iloc[0]

    with c_der:
        if prod_encontrado is not None:
            st.info(f"**{prod_encontrado['Producto']}**\n\nStock: {prod_encontrado['Stock Actual']}")
            cant_add = st.number_input("Cant", min_value=1, value=1)
            if st.button("➕ Añadir al Carrito"):
                st.session_state.carrito.append({
                    "Producto": prod_encontrado['Producto'],
                    "Precio": float(prod_encontrado['Precio Venta']),
                    "Cantidad": int(cant_add),
                    "Subtotal": float(prod_encontrado['Precio Venta'] * cant_add)
                })
                st.rerun()

    st.divider()
    
    if st.session_state.carrito:
        st.write("### Carrito Actual")
        # Mostrar carrito con opción de eliminar línea
        for i, item in enumerate(st.session_state.carrito):
            col_item, col_del = st.columns([4, 1])
            col_item.write(f"{item['Cantidad']}x {item['Producto']} - ${item['Subtotal']}")
            if col_del.button("🗑️", key=f"del_{i}"):
                st.session_state.carrito.pop(i)
                st.rerun()
        
        total = sum(item['Subtotal'] for item in st.session_state.carrito)
        st.markdown(f"### TOTAL: ${total:,.2f}")
        metodo = st.selectbox("Pago", ["Pago Móvil", "Punto", "Zelle", "Binance", "Efectivo"])
        
        c1, c2 = st.columns(2)
        if c1.button("✅ FACTURAR", use_container_width=True):
            for item in st.session_state.carrito:
                idx = df_inv[df_inv["Producto"] == item["Producto"]].index[0]
                df_inv.at[idx, "Stock Actual"] -= item["Cantidad"]
                nueva_v = pd.DataFrame([{"Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "Vendedor": vendedor, "Producto": item["Producto"], "Cantidad": item["Cantidad"], "Total": item["Subtotal"], "Metodo Pago": metodo, "Punto Salida": salida}])
                df_ventas = pd.concat([df_ventas, nueva_v], ignore_index=True)
            guardar_datos(df_inv, DB_INVENTARIO)
            guardar_datos(df_ventas, DB_VENTAS)
            st.session_state.carrito = []
            st.success("Venta realizada")
            st.rerun()
        if c2.button("🚫 CANCELAR TODO", use_container_width=True):
            st.session_state.carrito = []
            st.rerun()

# --- PESTAÑA 2: INVENTARIO (CON AJUSTE MANUAL) ---
with pestana[1]:
    st.subheader("Gestión de Inventario")
    
    col_a1, col_a2 = st.columns(2)
    if col_a1.button("➕ NUEVO PRODUCTO"):
        st.session_state.mostrar_form = not st.session_state.mostrar_form
    
    # --- NUEVA FUNCIÓN: AJUSTE MANUAL ---
    with col_a2.expander("📉 ELIMINAR / AJUSTAR STOCK"):
        prod_ajuste = st.selectbox("Producto a ajustar", df_inv["Producto"].tolist())
        cant_ajuste = st.number_input("Cantidad a RESTAR", min_value=1, value=1)
        motivo = st.text_input("Motivo (ej. Cambio, Dañado)")
        if st.button("Confirmar Resta Manual"):
            idx = df_inv[df_inv["Producto"] == prod_ajuste].index[0]
            if df_inv.at[idx, "Stock Actual"] >= cant_ajuste:
                df_inv.at[idx, "Stock Actual"] -= cant_ajuste
                guardar_datos(df_inv, DB_INVENTARIO)
                st.warning(f"Se restaron {cant_ajuste} unidades de {prod_ajuste} por: {motivo}")
                st.rerun()
            else:
                st.error("No puedes restar más de lo que hay en stock")

    if st.session_state.mostrar_form:
        with st.form("f_nuevo"):
            t_c = st.radio("¿Código?", ["Sí", "No"], horizontal=True)
            c_f = st.text_input("Código")
            n_p = st.text_input("Nombre")
            p_p = st.number_input("Precio", min_value=0.0)
            s_p = st.number_input("Stock", min_value=0)
            if st.form_submit_button("Guardar"):
                nuevo = pd.DataFrame([{"Codigo": c_f if t_c=="Sí" else "SIN_CODIGO", "Tiene_Codigo": t_c, "Producto": n_p, "Categoría": "General", "Precio Venta": p_p, "Stock Actual": s_p, "Stock Mínimo": 5}])
                df_inv = pd.concat([df_inv, nuevo], ignore_index=True)
                guardar_datos(df_inv, DB_INVENTARIO)
                st.session_state.mostrar_form = False
                st.rerun()
    
    st.write("### Stock Actual")
    st.dataframe(df_inv, use_container_width=True)

# --- PESTAÑA 3: CIERRE ---
with pestana[2]:
    st.subheader("Reporte")
    f_sel = st.date_input("Día", datetime.now())
    v_dia = df_ventas[df_ventas["Fecha"].str.contains(f_sel.strftime("%Y-%m-%d"))]
    if not v_dia.empty:
        st.metric("TOTAL", f"${v_dia['Total'].sum():,.2f}")
        st.dataframe(v_dia)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            v_dia.to_excel(writer, index=False, sheet_name='Cierre')
        st.download_button("📥 Excel", output.getvalue(), f"cierre_{f_sel}.xlsx")
