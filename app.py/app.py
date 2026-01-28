import streamlit as st
import pandas as pd
from streamlit.connections import ExperimentalBaseConnection
import gspread
from google.oauth2 import service_account
from datetime import datetime
import time
import hashlib

# ===================== CONFIGURACIÓN =====================
st.set_page_config(
    page_title="Inventario Ropa Caballero",
    page_icon="👔",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ===================== SEGURIDAD =====================
def hash_password(password):
    """Hash simple para contraseña (en producción usaría bcrypt)"""
    return hashlib.sha256(password.encode()).hexdigest()

# Contraseña hasheada para "admin123"
HASHED_PASSWORD = "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9"

# ===================== SESSION STATE =====================
if 'admin_logged_in' not in st.session_state:
    st.session_state.admin_logged_in = False
if 'force_refresh' not in st.session_state:
    st.session_state.force_refresh = False
if 'last_update' not in st.session_state:
    st.session_state.last_update = None

# ===================== CONEXIÓN GOOGLE SHEETS =====================
class GSheetsConnection(ExperimentalBaseConnection):
    def _connect(self, **kwargs):
        """Conecta a Google Sheets"""
        try:
            credentials_dict = st.secrets["gcp_service_account"]
            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict,
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"
                ]
            )
            return gspread.authorize(credentials)
        except Exception as e:
            st.error(f"❌ Error de conexión: {e}")
            return None
    
    def read(self, spreadsheet: str, worksheet: str = "Sheet1", **kwargs) -> pd.DataFrame:
        """Lee datos de Google Sheets"""
        try:
            conn = self._connect()
            if conn is None:
                return pd.DataFrame()
            
            sh = conn.open(spreadsheet)
            ws = sh.worksheet(worksheet)
            data = ws.get_all_values()
            
            if data and len(data) > 1:
                df = pd.DataFrame(data[1:], columns=data[0])
                # Convertir columnas numéricas
                numeric_columns = ['Entrada', 'Ventas', 'Stock', 'Precio']
                for col in numeric_columns:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
                return df
            return pd.DataFrame()
        except gspread.exceptions.SpreadsheetNotFound:
            st.error("📄 No se encontró la hoja de cálculo. Verifica el nombre.")
            return pd.DataFrame()
        except Exception as e:
            st.error(f"📖 Error al leer datos: {e}")
            return pd.DataFrame()
    
    def update(self, spreadsheet: str, worksheet: str, data: pd.DataFrame, **kwargs):
        """Actualiza datos en Google Sheets"""
        try:
            conn = self._connect()
            if conn is None:
                return False
            
            sh = conn.open(spreadsheet)
            ws = sh.worksheet(worksheet)
            
            # Convertir DataFrame a lista de listas
            data = data.fillna("")
            data_list = [data.columns.tolist()] + data.values.tolist()
            
            # Limpiar hoja y escribir nuevos datos
            ws.clear()
            ws.update('A1', data_list)
            return True
        except Exception as e:
            st.error(f"💾 Error al guardar: {e}")
            return False

# ===================== FUNCIONES AUXILIARES =====================
@st.cache_resource
def init_connection():
    """Inicializa la conexión a Google Sheets"""
    return GSheetsConnection("gsheets")

def load_inventory_data():
    """Carga datos del inventario"""
    try:
        df = conn.read("Inventario Ropa Caballero", "Sheet1")
        
        if df.empty or 'ID' not in df.columns:
            df = pd.DataFrame(columns=[
                "ID", "Categoria", "Producto", "Talla", "Color", 
                "Entrada", "Ventas", "Stock", "Precio"
            ])
        
        # Asegurar columnas
        required_columns = ["ID", "Categoria", "Producto", "Talla", "Color", 
                           "Entrada", "Ventas", "Stock", "Precio"]
        for col in required_columns:
            if col not in df.columns:
                df[col] = 0 if col in ["Entrada", "Ventas", "Stock", "Precio"] else ""
        
        return df
    except Exception as e:
        st.error(f"⚠️ Error cargando inventario: {e}")
        return pd.DataFrame(columns=required_columns)

def save_inventory_data(df):
    """Guarda datos en Google Sheets"""
    try:
        success = conn.update("Inventario Ropa Caballero", "Sheet1", df)
        if success:
            st.session_state.last_update = datetime.now()
            st.success("✅ Datos guardados")
            time.sleep(1.5)
            st.rerun()
        return success
    except Exception as e:
        st.error(f"💥 Error crítico: {e}")
        return False

def get_tallas_opciones(categoria):
    """Opciones de tallas según categoría"""
    if isinstance(categoria, str) and any(word in categoria.lower() for word in ['pantalón', 'short', 'pantalon']):
        return ['28', '30', '32', '34', '36', '38', '40', '42']
    else:
        return ['XCH', 'CH', 'M', 'G', 'XG', 'XXG']

# ===================== INTERFAZ PRINCIPAL =====================
def main():
    # Inicializar conexión global
    global conn
    conn = init_connection()
    
    st.title("👔 Control de Inventario - Ropa de Caballero")
    
    # Estado de carga
    with st.spinner("Cargando inventario..."):
        df = load_inventory_data()
    
    # Tabs principales
    tab1, tab2, tab3 = st.tabs([
        "📱 Registrar Ventas", 
        "📊 Reporte y Caja", 
        "📦 Cargar Mercancía"
    ])
    
    # TAB 1: REGISTRAR VENTAS
    with tab1:
        st.header("Registrar Ventas")
        
        if df.empty:
            st.info("📭 No hay productos en inventario. Ve a 'Cargar Mercancía' para agregar productos.")
        else:
            # Buscador
            search_term = st.text_input("🔍 Buscar producto:", 
                                       placeholder="Ej: Camisa, Jean, Short...")
            
            # Filtrar
            if search_term:
                mask = df['Producto'].str.contains(search_term, case=False, na=False)
                filtered_df = df[mask]
            else:
                filtered_df = df[df['Stock'] > 0]  # Mostrar solo con stock
            
            if filtered_df.empty:
                st.warning("🔍 No se encontraron productos con stock disponible")
            else:
                st.write(f"**{len(filtered_df)} productos encontrados**")
                
                for _, row in filtered_df.iterrows():
                    with st.expander(f"👕 {row['Producto']} | 🎨 {row['Color']} | 📏 Talla {row['Talla']} | 📦 Stock: {row['Stock']}"):
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            st.write(f"**Categoría:** {row['Categoria']}")
                            st.write(f"**Precio:** ${row['Precio']:,.0f}")
                            st.write(f"**Ventas acumuladas:** {row['Ventas']}")
                        
                        with col2:
                            if st.button("✅ Vender", key=f"venta_{row['ID']}", 
                                       type="primary", use_container_width=True):
                                idx = df[df['ID'] == row['ID']].index[0]
                                df.at[idx, 'Ventas'] = int(df.at[idx, 'Ventas']) + 1
                                df.at[idx, 'Stock'] = int(df.at[idx, 'Stock']) - 1
                                save_inventory_data(df)
    
    # TAB 2: REPORTE Y CAJA
    with tab2:
        st.header("📊 Reporte Financiero")
        
        if not df.empty:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                ingresos = (df['Ventas'] * df['Precio']).sum()
                st.metric("💰 Ingresos Totales", f"${ingresos:,.0f}")
            
            with col2:
                stock_total = df['Stock'].sum()
                st.metric("📦 Stock Total", stock_total)
            
            with col3:
                valor_inventario = (df['Stock'] * df['Precio']).sum()
                st.metric("🏷️ Valor Inventario", f"${valor_inventario:,.0f}")
            
            # Gráfico simple
            st.subheader("📈 Productos Más Vendidos")
            top_productos = df.nlargest(5, 'Ventas')[['Producto', 'Ventas']]
            st.bar_chart(top_productos.set_index('Producto'))
            
        else:
            st.info("📊 No hay datos para reportes")
        
        # Datos completos
        st.subheader("📋 Inventario Completo")
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Botones de acción
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Actualizar Datos", use_container_width=True):
                    st.cache_data.clear()
                    st.session_state.force_refresh = True
                    st.success("Datos actualizados")
                    st.rerun()
            
            with col2:
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar CSV",
                    data=csv,
                    file_name=f"inventario_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.warning("No hay datos para mostrar")
    
    # TAB 3: CARGAR MERCANCÍA (PROTEGIDO)
    with tab3:
        st.header("📦 Cargar Mercancía")
        
        # Sistema de autenticación
        if not st.session_state.admin_logged_in:
            st.warning("🔐 Acceso restringido - Solo administradores")
            
            with st.form("login_form"):
                password = st.text_input("Contraseña:", type="password")
                submit = st.form_submit_button("🔑 Ingresar", type="primary")
                
                if submit:
                    if hash_password(password) == HASHED_PASSWORD:
                        st.session_state.admin_logged_in = True
                        st.success("✅ Acceso concedido")
                        st.rerun()
                    else:
                        st.error("❌ Contraseña incorrecta")
        else:
            # Mostrar interfaz de administrador
            st.success("👤 Sesión activa - Modo administrador")
            
            if st.button("🚪 Cerrar Sesión", type="secondary"):
                st.session_state.admin_logged_in = False
                st.rerun()
            
            # Formulario de carga
            st.subheader("➕ Agregar Nuevo Producto")
            
            with st.form("nuevo_producto_form"):
                # Categoría
                categorias_existentes = df['Categoria'].unique().tolist() if not df.empty else []
                opciones_cat = categorias_existentes + ["➕ Nueva Categoría"]
                
                categoria_opcion = st.selectbox("Seleccionar Categoría:", opciones_cat)
                
                if categoria_opcion == "➕ Nueva Categoría":
                    categoria = st.text_input("Nombre Nueva Categoría:")
                else:
                    categoria = categoria_opcion
                
                # Campos del producto
                col1, col2 = st.columns(2)
                with col1:
                    producto = st.text_input("Producto *", 
                                           placeholder="Ej: Camisa Manga Larga")
                    color = st.text_input("Color *", placeholder="Ej: Azul, Negro, Blanco")
                
                with col2:
                    # Tallas dinámicas
                    if categoria:
                        tallas = get_tallas_opciones(categoria)
                        talla = st.selectbox("Talla *", tallas)
                    else:
                        talla = st.selectbox("Talla *", ['XCH', 'CH', 'M', 'G', 'XG', 'XXG'])
                    
                    cantidad = st.number_input("Cantidad *", min_value=1, value=1)
                    precio = st.number_input("Precio (COP) *", min_value=0, value=50000, step=1000)
                
                submit_producto = st.form_submit_button("📤 Cargar al Inventario", type="primary")
                
                if submit_producto:
                    if not all([producto, color, categoria, talla]):
                        st.error("❌ Complete todos los campos obligatorios (*)")
                    else:
                        # Generar ID
                        nuevo_id = df['ID'].max() + 1 if not df.empty and 'ID' in df.columns else 1
                        
                        nuevo_producto = pd.DataFrame([{
                            "ID": int(nuevo_id),
                            "Categoria": categoria,
                            "Producto": producto,
                            "Talla": str(talla),
                            "Color": color,
                            "Entrada": int(cantidad),
                            "Ventas": 0,
                            "Stock": int(cantidad),
                            "Precio": int(precio)
                        }])
                        
                        df = pd.concat([df, nuevo_producto], ignore_index=True)
                        
                        if save_inventory_data(df):
                            st.balloons()

# ===================== EJECUCIÓN =====================
if __name__ == "__main__":
    main()