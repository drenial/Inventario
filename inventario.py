import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io
from PIL import Image
import numpy as np

# Intentar importar el decodificador de forma segura
try:
    from pyzbar.pyzbar import decode
    SCANNER_DISPONIBLE = True
except ImportError:
    SCANNER_DISPONIBLE = False

# Configuración de página
st.set_page_config(page_title="Sistema POS Estable", layout="centered")

DB_INVENTARIO = "inventario.csv"
DB_VENTAS = "ventas.csv"

# Inicializar estados de sesión
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'mostrar_form' not in st.session_state: st.session_state.mostrar_form = False

# --- FUNCIONES DE PERSISTENCIA ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            for col in columnas:
                if col not in df.columns:
                    df[col] = 0 if "Stock" in col or "Precio" in col else "N/A"
            return df[columnas]
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

COL_INV = ["Codigo", "Tiene_Codigo", "Producto", "Categoría", "Precio Venta", "Stock Actual", "Stock Mínimo"]
COL_VEN = ["Fecha", "Vendedor", "Producto", "Cantidad", "Total", "Metodo Pago", "Punto Salida"]

df_inv = cargar_datos(DB_INVENTARIO, COL_INV)
df_ventas = cargar_datos(DB_VENTAS, COL_VEN)

# --- INTERFAZ ---
st.sidebar.title("Configuración")
vendedor = st.sidebar.selectbox("👤 Vendedor", ["Admin", "Vendedor 1", "Vendedor 2"])
salida = st.sidebar.radio("📍 Punto", ["Salida 1", "Salida 2"])

pestana = st.tabs(["🛒 Punto de Venta", "📦 Inventario", "📊 Cierre Diario"])

# --- PESTAÑA 1: VENTA ---
with pestana[0]:
    st.subheader("🛒 Lista de Compra")
    c_izq, c_der = st.columns([1, 1])
    prod_encontrado = None
    
    with c_izq:
        modo = st.radio("Buscar por:", ["Código / Lector", "Cámara", "Nombre"], horizontal=True)
        if modo == "Código / Lector":
            cod_in = st.text_input("Escribe código o escanea con lector físico")
            if cod_in:
                res = df_inv[df_inv["Codigo"].astype(str) == str(cod_in)]
                if not res.empty: prod_encontrado = res.iloc[0]
                else: st.error("Código no encontrado")
        elif modo == "Cámara":
            if SCANNER_DISPONIBLE:
                foto = st.camera_input("Foto al código")
                if foto:
                    img = Image.open(foto)
                    decod = decode(np.array(img))
                    if decod:
                        c = decod[0].data.decode('utf-8')
                        res = df_inv[df_inv["Codigo"].astype(str) == str(c)]
                        if not res.empty: 
                            prod_encontrado = res.iloc[0]
                            st.success(f"Detectado: {prod_encontrado['Producto']}")
                    else: st.warning("No se detectó código en la imagen")
            else: st.error("El módulo de cámara no está configurado correctamente.")
        else:
            nom_in = st.text_input("Nombre del producto")
            if nom_in:
                sug = df_inv[df_inv["Producto"].str.contains(nom_in, case=False)]["Producto"].tolist()
                sel = st.selectbox("Selecciona", ["-"] + sug)
                if sel != "-": prod_encontrado = df_inv[df_inv["Producto"] == sel].iloc[0]

    with c_der:
        if prod_encontrado is not None:
            st.info(f"**{prod_encontrado['Producto']}**\n\nPrecio: ${prod_encontrado['Precio Venta']}")
            cant_add = st.number_input("Cantidad", min_value=1, max_value=max(1, int(prod_encontrado['Stock Actual'])), value=1)
            if st.button("➕ Añadir"):
                st.session_state.carrito.append({
                    "Producto": prod_encontrado['Producto'],
                    "Precio": float(prod_encontrado['Precio Venta']),
                    "Cantidad": int(cant_add),
                    "Subtotal": float(prod_encontrado['Precio Venta'] * cant_add)
                })
                st.rerun()

    st.divider()
    if st.session_state.carrito:
        df_cart = pd.DataFrame(st.session_state.carrito)
        for i, item in enumerate(st.session_state.carrito):
            col_it, col_bo = st.columns([4, 1])
            col_it.write(f"{item['Cantidad']}x {item['Producto']} - ${item['Subtotal']}")
            if col_bo.button("🗑️", key=f"btn_{i}"):
                st.session_state.carrito.pop(i)
                st.rerun()
        
        total = sum(i['Subtotal'] for i in st.session_state.carrito)
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
        if c2.button("🚫 CANCELAR", use_container_width=True):
            st.session_state.carrito = []
            st.rerun()

# --- PESTAÑA 2: INVENTARIO ---
with pestana[1]:
    st.subheader("Inventario")
    c_a1, c_a2 = st.columns(2)
    if c_a1.button("➕ NUEVO PRODUCTO"): st.session_state.mostrar_form = not st.session_state.mostrar_form
    
    with c_a2.expander("📉 AJUSTE MANUAL (RESTAS)"):
        p_aj = st.selectbox("Producto", df_inv["Producto"].tolist() if not df_inv.empty else ["N/A"])
        c_aj = st.number_input("Resta Cantidad", min_value=1, value=1)
        if st.button("Confirmar Ajuste"):
            if not df_inv.empty:
                idx = df_inv[df_inv["Producto"] == p_aj].index[0]
                df_inv.at[idx, "Stock Actual"] -= c_aj
                guardar_datos(df_inv, DB_INVENTARIO)
                st.success("Stock ajustado")
                st.rerun()

    if st.session_state.mostrar_form:
        with st.form("f_new"):
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
    
    st.dataframe(df_inv, use_container_width=True)

# --- PESTAÑA 3: CIERRE ---
with pestana[2]:
    st.subheader("Reporte Diario")
    f_se = st.date_input("Día", datetime.now())
    v_di = df_ventas[df_ventas["Fecha"].str.contains(f_se.strftime("%Y-%m-%d"))]
    if not v_di.empty:
        st.metric("TOTAL", f"${v_di['Total'].sum():,.2f}")
        st.dataframe(v_di)
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as wr:
            v_di.to_excel(wr, index=False)
        st.download_button("📥 Descargar Excel", out.getvalue(), f"cierre_{f_se}.xlsx")
    else: st.warning("Sin ventas registradas")
