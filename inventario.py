import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io

# --- CONFIGURACIÓN DE SEGURIDAD ---
CLAVE_ADMIN = "0302" # Cambia tu clave aquí

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema POS & Taller", page_icon="🛠️", layout="centered")

DB_INV = "inventario.csv"
DB_VEN = "ventas.csv"

# Inicializar estados de sesión
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False

# --- FUNCIONES DE DATOS ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            for col in columnas:
                if col not in df.columns: 
                    df[col] = "" if col not in ["Stock Actual", "Total", "Cantidad", "Precio Venta"] else 0
            return df[columnas]
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

# Columnas Base
C_INV = ["Codigo", "Tiene_Codigo", "Producto", "Categoría", "Precio Venta", "Stock Actual", "Stock Mínimo"]
C_VEN = ["Fecha", "Vendedor", "Producto", "Cantidad", "Total", "Metodo Pago", "Punto Salida", "Ayudante", "Descripcion", "Modelo Carro"]

df_inv = cargar_datos(DB_INV, C_INV)
df_ven = cargar_datos(DB_VEN, C_VEN)

# --- SIDEBAR (SEGURIDAD) ---
st.sidebar.title("🔐 Acceso")
if not st.session_state.admin_auth:
    pass_in = st.sidebar.text_input("Clave Admin", type="password")
    if st.sidebar.button("Entrar"):
        if pass_in == CLAVE_ADMIN:
            st.session_state.admin_auth = True
            st.rerun()
else:
    st.sidebar.success("Modo Admin Activo")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.admin_auth = False
        st.rerun()

vendedor_fijo = st.sidebar.selectbox("👤 Vendedor/Técnico", ["Vendedor 1", "Vendedor 2", "Admin"])
salida_fija = st.sidebar.radio("📍 Punto de Salida", ["Salida 1", "Salida 2"])

# Pestañas condicionales
if st.session_state.admin_auth:
    tabs = st.tabs(["🛒 Facturación", "📦 Inventario", "📊 Cierre Diario"])
else:
    tabs = st.tabs(["🛒 Facturación"])

# --- PESTAÑA 1: FACTURACIÓN (PRODUCTOS Y TRABAJOS) ---
with tabs[0]:
    st.subheader("🛒 Punto de Venta")
    opcion = st.radio("¿Qué vas a cobrar?", ["📦 Producto", "🛠️ Servicio/Trabajo"], horizontal=True)
    p_sel = None

    if opcion == "📦 Producto":
        c1, c2 = st.columns(2)
        with c1:
            m = st.radio("Buscar por:", ["Código", "Nombre"], horizontal=True)
            if m == "Código":
                cod = st.text_input("Escribe Código")
                if cod:
                    res = df_inv[df_inv["Codigo"].astype(str) == str(cod)]
                    if not res.empty: p_sel = res.iloc[0]
            else:
                nom = st.text_input("Nombre del producto")
                if nom:
                    sug = df_inv[df_inv["Producto"].str.contains(nom, case=False)]["Producto"].tolist()
                    sel = st.selectbox("Seleccionar", ["-"] + sug)
                    if sel != "-": p_sel = df_inv[df_inv["Producto"] == sel].iloc[0]
        with c2:
            if p_sel is not None:
                st.info(f"**{p_sel['Producto']}**\n\nStock: {p_sel['Stock Actual']}")
                can = st.number_input("Cantidad", min_value=1, max_value=max(1, int(p_sel['Stock Actual'])), value=1)
                if st.button("➕ Añadir al Carrito"):
                    st.session_state.carrito.append({
                        "Tipo": "Prod", "Producto": p_sel['Producto'],
                        "Precio": float(p_sel['Precio Venta']), "Cantidad": int(can),
                        "Subtotal": float(p_sel['Precio Venta']*can),
                        "Ayudante": "", "Descripcion": "", "Modelo Carro": ""
                    })
                    st.rerun()
    else:
        with st.container():
            st.info("🛠️ Datos del Trabajo")
            ct1, ct2 = st.columns(2)
            with ct1:
                desc = st.text_area("¿Qué se hizo?")
                carro = st.text_input("Modelo del Carro (Opcional)")
            with ct2:
                ayu = st.text_input("Nombre del Ayudante")
                pre = st.number_input("Costo de Mano de Obra ($)", min_value=0.0)
            if st.button("➕ Añadir Servicio"):
                if desc and pre > 0:
                    st.session_state.carrito.append({
                        "Tipo": "Trab", "Producto": "SERV: " + desc[:20],
                        "Precio": float(pre), "Cantidad": 1, "Subtotal": float(pre),
                        "Ayudante": ayu, "Descripcion": desc, "Modelo Carro": carro
                    })
                    st.rerun()

    st.divider()
    if st.session_state.carrito:
        st.write("### Detalle de Compra")
        for i, it in enumerate(st.session_state.carrito):
            col_i, col_d = st.columns([4, 1])
            icono = "📦" if it["Tipo"] == "Prod" else "🛠️"
            col_i.write(f"{icono} **{it['Cantidad']}x** {it['Producto']} — ${it['Subtotal']:.2f}")
            if col_d.button("🗑️", key=f"del_{i}"):
                st.session_state.carrito.pop(i); st.rerun()
        
        total_p = sum(i['Subtotal'] for i in st.session_state.carrito)
        st.markdown(f"## TOTAL: ${total_p:,.2f}")
        met = st.selectbox("Forma de Pago", ["Pago Móvil", "Punto", "Zelle", "Binance", "Efectivo"])
        
        cb1, cb2 = st.columns(2)
        if cb1.button("✅ FINALIZAR Y FACTURAR", use_container_width=True):
            for it in st.session_state.carrito:
                if it["Tipo"] == "Prod":
                    idx = df_inv[df_inv["Producto"] == it["Producto"]].index[0]
                    df_inv.at[idx, "Stock Actual"] -= it["Cantidad"]
                
                nueva_v = pd.DataFrame([{
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Vendedor": vendedor_fijo, "Producto": it["Producto"],
                    "Cantidad": it["Cantidad"], "Total": it["Subtotal"],
                    "Metodo Pago": met, "Punto Salida": salida_fija,
                    "Ayudante": it["Ayudante"], "Descripcion": it["Descripcion"], "Modelo Carro": it["Modelo Carro"]
                }])
                df_ven = pd.concat([df_ven, nueva_v], ignore_index=True)
            
            guardar_datos(df_inv, DB_INV); guardar_datos(df_ven, DB_VEN)
            st.session_state.carrito = []
            st.success("¡Venta procesada con éxito!")
            st.rerun()
        
        if cb2.button("🚫 CANCELAR TODO", use_container_width=True):
            st.session_state.carrito = []
            st.rerun()

# --- PESTAÑAS ADMIN ---
if st.session_state.admin_auth:
    # --- INVENTARIO ---
    with tabs[1]:
        st.subheader("📦 Gestión de Inventario")
        col_inv1, col_inv2 = st.columns(2)
        
        if col_inv1.button("➕ AGREGAR PRODUCTO NUEVO"):
            st.session_state.mostrar_form = not st.session_state.get('mostrar_form', False)
        
        with col_inv2.expander("📉 RESTA MANUAL (Daño/Cambio)"):
            p_aj = st.selectbox("Producto", df_inv["Producto"].tolist() if not df_inv.empty else [])
            c_aj = st.number_input("Resta Cantidad", min_value=1, value=1)
            if st.button("Confirmar Ajuste"):
                idx_a = df_inv[df_inv["Producto"] == p_aj].index[0]
                df_inv.at[idx_a, "Stock Actual"] -= c_aj
                guardar_datos(df_inv, DB_INV); st.success("Stock actualizado"); st.rerun()

        if st.session_state.get('mostrar_form', False):
            with st.form("f_nuevo"):
                tc = st.radio("¿Código?", ["Sí", "No"], horizontal=True)
                fc = st.text_input("Código"); fn = st.text_input("Nombre")
                fp = st.number_input("Precio", min_value=0.0); fs = st.number_input("Stock", min_value=0)
                if st.form_submit_button("Guardar"):
                    n = pd.DataFrame([{"Codigo": fc if tc=="Sí" else "SIN_CODIGO", "Tiene_Codigo": tc, "Producto": fn, "Categoría": "General", "Precio Venta": fp, "Stock Actual": fs, "Stock Mínimo": 5}])
                    df_inv = pd.concat([df_inv, n], ignore_index=True); guardar_datos(df_inv, DB_INV); st.rerun()
        
        st.divider()
        st.dataframe(df_inv, use_container_width=True)

    # --- CIERRE DIARIO (REPORTE CON FIX PARA EXCEL) ---
    with tabs[2]:
        st.subheader("📊 Reporte de Cierre")
        fs_dia = st.date_input("Seleccionar Día", datetime.now()).strftime("%Y-%m-%d")
        v_dia = df_ven[df_ven["Fecha"].str.contains(fs_dia)]
        
        if not v_dia.empty:
            st.metric("INGRESO TOTAL", f"${v_dia['Total'].sum():,.2f}")
            st.write("**Detalle por Método de Pago:**")
            st.table(v_dia.groupby("Metodo Pago")["Total"].sum())
            
            st.dataframe(v_dia[["Fecha", "Vendedor", "Producto", "Total", "Metodo Pago", "Modelo Carro", "Ayudante", "Descripcion"]])
            
            # --- SISTEMA DE DESCARGA SEGURO ---
            st.write("---")
            try:
                # Intento generar Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    v_dia.to_excel(writer, index=False)
                st.download_button(label="📥 Descargar Cierre (Excel)", data=output.getvalue(), file_name=f"cierre_{fs_dia}.xlsx")
            except Exception:
                # Si falla openpyxl, doy la opción CSV automáticamente
                st.warning("⚠️ Nota: Exportando a formato CSV por compatibilidad del servidor.")
                csv_data = v_dia.to_csv(index=False).encode('utf-8')
                st.download_button(label="📥 Descargar Cierre (CSV)", data=csv_data, file_name=f"cierre_{fs_dia}.csv")
        else:
            st.info("No hay ventas registradas en esta fecha.")
