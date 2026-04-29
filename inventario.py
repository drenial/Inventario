import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io
from PIL import Image
import numpy as np

# --- IMPORTACIONES SEGURAS ---
try:
    from pyzbar.pyzbar import decode
    SCANNER_OK = True
except:
    SCANNER_OK = False

try:
    import openpyxl
    EXCEL_OK = True
except:
    EXCEL_OK = False

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sistema POS Completo", layout="centered")

DB_INV = "inventario.csv"
DB_VEN = "ventas.csv"

# Inicializar estados
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'mostrar_form' not in st.session_state: st.session_state.mostrar_form = False

# --- FUNCIONES DE DATOS ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            for col in columnas:
                if col not in df.columns:
                    df[col] = 0 if ("Stock" in col or "Precio" in col) else "N/A"
            return df[columnas]
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

C_INV = ["Codigo", "Tiene_Codigo", "Producto", "Categoría", "Precio Venta", "Stock Actual", "Stock Mínimo"]
C_VEN = ["Fecha", "Vendedor", "Producto", "Cantidad", "Total", "Metodo Pago", "Punto Salida"]

df_inv = cargar_datos(DB_INV, C_INV)
df_ven = cargar_datos(DB_VEN, C_VEN)

# --- SIDEBAR ---
st.sidebar.title("🚀 Panel de Control")
vendedor = st.sidebar.selectbox("👤 Vendedor", ["Admin", "Vendedor 1", "Vendedor 2"])
salida = st.sidebar.radio("📍 Punto de Salida", ["Salida 1", "Salida 2"])

pestanas = st.tabs(["🛒 Punto de Venta", "📦 Inventario", "📊 Cierre Diario"])

# --- PESTAÑA 1: PUNTO DE VENTA ---
with pestanas[0]:
    st.subheader("🛒 Carrito de Compras")
    col_busq, col_conf = st.columns([1, 1])
    p_encontrado = None

    with col_busq:
        modo = st.radio("Buscar por:", ["Código", "Nombre"], horizontal=True)
        if modo == "Código":
            cod_in = st.text_input("Escanear o escribir código")
            if cod_in:
                res = df_inv[df_inv["Codigo"].astype(str) == str(cod_in)]
                if not res.empty: p_encontrado = res.iloc[0]
                else: st.error("No encontrado")
        else:
            nom_in = st.text_input("Buscar por nombre")
            if nom_in:
                sug = df_inv[df_inv["Producto"].str.contains(nom_in, case=False)]["Producto"].tolist()
                sel = st.selectbox("Seleccionar producto", ["-"] + sug)
                if sel != "-": p_encontrado = df_inv[df_inv["Producto"] == sel].iloc[0]

    with col_conf:
        if p_encontrado is not None:
            st.info(f"**{p_encontrado['Producto']}**\n\nStock: {p_encontrado['Stock Actual']}")
            cant = st.number_input("Cantidad", min_value=1, max_value=max(1, int(p_encontrado['Stock Actual'])), value=1)
            if st.button("➕ Añadir al Carrito"):
                st.session_state.carrito.append({
                    "Producto": p_encontrado['Producto'],
                    "Precio": float(p_encontrado['Precio Venta']),
                    "Cantidad": int(cant),
                    "Subtotal": float(p_encontrado['Precio Venta'] * cant)
                })
                st.rerun()

    st.divider()
    
    if st.session_state.carrito:
        st.write("### Detalle de la Compra")
        # Mostrar items con botón de eliminar individual
        for i, item in enumerate(st.session_state.carrito):
            c_item, c_del = st.columns([4, 1])
            c_item.write(f"**{item['Cantidad']}x** {item['Producto']} — ${item['Subtotal']:,.2f}")
            if c_del.button("🗑️", key=f"del_{i}"):
                st.session_state.carrito.pop(i)
                st.rerun()
        
        total_pagar = sum(it['Subtotal'] for it in st.session_state.carrito)
        st.markdown(f"## TOTAL: ${total_pagar:,.2f}")
        metodo = st.selectbox("Método de Pago", ["Pago Móvil", "Punto", "Zelle", "Binance", "Efectivo"])
        
        cb1, cb2 = st.columns(2)
        if cb1.button("✅ FINALIZAR VENTA", use_container_width=True):
            for item in st.session_state.carrito:
                idx = df_inv[df_inv["Producto"] == item["Producto"]].index[0]
                df_inv.at[idx, "Stock Actual"] -= item["Cantidad"]
                nv = pd.DataFrame([{
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Vendedor": vendedor, "Producto": item["Producto"],
                    "Cantidad": item["Cantidad"], "Total": item["Subtotal"],
                    "Metodo Pago": metodo, "Punto Salida": salida
                }])
                df_ven = pd.concat([df_ven, nv], ignore_index=True)
            guardar_datos(df_inv, DB_INV); guardar_datos(df_ven, DB_VEN)
            st.session_state.carrito = []
            st.success("¡Venta procesada!"); st.balloons(); st.rerun()
            
        if cb2.button("🚫 CANCELAR TODO", use_container_width=True):
            st.session_state.carrito = []
            st.rerun()

# --- PESTAÑA 2: INVENTARIO ---
with pestanas[1]:
    st.subheader("📦 Gestión de Productos")
    
    col_b1, col_b2 = st.columns(2)
    if col_b1.button("➕ AGREGAR NUEVO"):
        st.session_state.mostrar_form = not st.session_state.mostrar_form
    
    # AJUSTE MANUAL (RESTAS)
    with col_b2.expander("📉 RESTA MANUAL (Cambios/Daños)"):
        if not df_inv.empty:
            p_aj = st.selectbox("Producto a ajustar", df_inv["Producto"].tolist())
            c_aj = st.number_input("Cantidad a eliminar", min_value=1, value=1)
            motivo = st.text_input("Motivo")
            if st.button("Confirmar Resta"):
                idx_a = df_inv[df_inv["Producto"] == p_aj].index[0]
                if df_inv.at[idx_a, "Stock Actual"] >= c_aj:
                    df_inv.at[idx_a, "Stock Actual"] -= c_aj
                    guardar_datos(df_inv, DB_INV)
                    st.warning(f"Se restaron {c_aj} de {p_aj}")
                    st.rerun()
                else: st.error("Stock insuficiente")

    if st.session_state.mostrar_form:
        with st.form("nuevo_p_form"):
            t_cod = st.radio("¿Tiene código físico?", ["Sí", "No"], horizontal=True)
            f_cod = st.text_input("Código")
            f_nom = st.text_input("Nombre del Producto")
            f_pre = st.number_input("Precio Venta", min_value=0.0)
            f_sto = st.number_input("Stock Inicial", min_value=0)
            if st.form_submit_button("Guardar Producto"):
                nuevo = pd.DataFrame([{
                    "Codigo": f_cod if t_cod=="Sí" else "SIN_CODIGO",
                    "Tiene_Codigo": t_cod, "Producto": f_nom,
                    "Categoría": "General", "Precio Venta": f_pre,
                    "Stock Actual": f_sto, "Stock Mínimo": 5
                }])
                df_inv = pd.concat([df_inv, nuevo], ignore_index=True)
                guardar_datos(df_inv, DB_INV)
                st.session_state.mostrar_form = False
                st.rerun()
    
    st.divider()
    st.write("### Inventario Actual")
    busq_inv = st.text_input("🔍 Buscar en inventario...")
    df_mostrar = df_inv[df_inv["Producto"].str.contains(busq_inv, case=False) | df_inv["Codigo"].astype(str).str.contains(busq_inv)]
    st.dataframe(df_mostrar, use_container_width=True)

# --- PESTAÑA 3: CIERRE DIARIO ---
with pestanas[2]:
    st.subheader("📊 Reporte de Ventas")
    f_cierre = st.date_input("Seleccionar Fecha", datetime.now())
    f_str = f_cierre.strftime("%Y-%m-%d")
    
    v_dia = df_ven[df_ven["Fecha"].str.contains(f_str)]
    
    if not v_dia.empty:
        st.metric("INGRESO TOTAL", f"${v_dia['Total'].sum():,.2f}")
        
        c_r1, c_r2 = st.columns(2)
        with c_r1:
            st.write("**Pagos por Método:**")
            st.table(v_dia.groupby("Metodo Pago")["Total"].sum())
        with c_r2:
            st.write("**Pagos por Caja:**")
            st.table(v_dia.groupby("Punto Salida")["Total"].sum())
            
        st.write("**Detalle de Ventas:**")
        st.dataframe(v_dia, use_container_width=True)
        
        # DESCARGA SEGURA
        if EXCEL_OK:
            try:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as wr:
                    v_dia.to_excel(wr, index=False)
                st.download_button("📥 Descargar Excel", buf.getvalue(), f"cierre_{f_str}.xlsx")
            except:
                st.download_button("📥 Descargar CSV (Backup)", v_dia.to_csv(index=False).encode('utf-8'), f"cierre_{f_str}.csv")
        else:
            st.download_button("📥 Descargar CSV", v_dia.to_csv(index=False).encode('utf-8'), f"cierre_{f_str}.csv")
    else:
        st.warning(f"No hay ventas registradas el día {f_str}")
