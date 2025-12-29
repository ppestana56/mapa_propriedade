import streamlit as st
import geopandas as gpd
import fiona
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString
from shapely.ops import linemerge
import matplotlib.pyplot as plt
import contextily as ctx
from pyproj import CRS
from datetime import datetime
import tempfile
import os
import io
from matplotlib_scalebar.scalebar import ScaleBar

# Ativar suporte KML
fiona.drvsupport.supported_drivers['KML'] = 'rw'

# -------------------------
# DICIONÁRIO DE TRADUÇÃO
# -------------------------
LANG = {
    "PT": {
        "title": "Gerador de Mapas de Propriedade",
        "prop_name_label": "Nome da Propriedade (ex: Quinta do Vale)",
        "prop_name_default": "Minha Propriedade",
        "upload_label": "Carregue o ficheiro (GPX, KML, GeoJSON)",
        "processing": "A processar...",
        "area_m2": "Área (m²)",
        "area_ha": "Área (ha)",
        "perim": "Perímetro (m)",
        "map_title": "Mapa de Propriedade",
        "legend_area": "Área",
        "legend_date": "Data",
        "export_title": "📥 Exportar Resultados",
        "free_ver": "✅ Versão Grátis (Amostra)",
        "free_desc": "- Imagem com marca de água\n- Sem escala gráfica",
        "premium_ver": "⭐ Versão Premium (PDF)",
        "premium_desc": "- PDF Limpo (Sem Marcas)\n- Escala e Bússola Profissionais\n- Sistema de Coordenadas PT-TM06",
        "btn_png": "Descarregar Amostra (PNG)",
        "btn_pdf_venda": "🚀 Comprar PDF Profissional",
        "btn_pdf_admin": "📄 Gerar PDF Premium (Admin)",
        "watermark": "AMOSTRA DE VALIDAÇÃO\nOBTER PDF PROFISSIONAL",
        "footer_tech": "Sistema de Coordenadas: ETRS89 / PT-TM06 (Oficial Portugal)"
    },
    "UK": {
        "title": "Property Map Generator",
        "prop_name_label": "Property Name (e.g., Green Valley Farm)",
        "prop_name_default": "My Property",
        "upload_label": "Upload file (GPX, KML, GeoJSON)",
        "processing": "Processing...",
        "area_m2": "Area (sqm)",
        "area_ha": "Area (ha)",
        "perim": "Perimeter (m)",
        "map_title": "Property Map",
        "legend_area": "Area",
        "legend_date": "Date",
        "export_title": "📥 Export Results",
        "free_ver": "✅ Free Version (Sample)",
        "free_desc": "- Watermarked image\n- No scale bar included",
        "premium_ver": "⭐ Premium Version (PDF)",
        "premium_desc": "- Clean PDF (No Watermarks)\n- Professional Scale & Compass\n- Accurate Geo-Metrics",
        "btn_png": "Download Sample (PNG)",
        "btn_pdf_venda": "🚀 Get Professional PDF",
        "btn_pdf_admin": "📄 Generate Premium PDF (Admin)",
        "watermark": "VALIDATION SAMPLE\nGET PROFESSIONAL PDF",
        "footer_tech": "Coordinate System: WGS 84 / Web Mercator"
    }
}

st.set_page_config(page_title="Property Map Tool", layout="centered")
idioma = st.sidebar.selectbox("🌐 Language / Idioma", ["PT", "UK"])
t = LANG[idioma]

st.title(t["title"])
nome_input = st.text_input(t["prop_name_label"], placeholder=t["prop_name_default"])
nome_propriedade = nome_input if nome_input else t["prop_name_default"]

# -------------------------
# FUNÇÕES CORE
# -------------------------

def load_geometry(uploaded_file):
    suffix = uploaded_file.name.split(".")[-1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{suffix}") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name
    try:
        if suffix == "gpx":
            try: gdf = gpd.read_file(tmp_path, layer='tracks')
            except: gdf = gpd.read_file(tmp_path, layer='track_points')
        elif suffix == "kml":
            layers = fiona.listlayers(tmp_path)
            gdf = gpd.read_file(tmp_path, layer=layers[0] if layers else None)
        else: gdf = gpd.read_file(tmp_path)
    finally:
        if os.path.exists(tmp_path): os.remove(tmp_path)
    return gdf

def validate_and_convert(gdf):
    gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString', 'Polygon', 'MultiPolygon'])]
    if gdf.empty: raise ValueError("Invalid Geometry")
    geom = gdf.geometry.iloc[0]
    if isinstance(geom, MultiLineString): geom = linemerge(geom)
    if geom.type in ['LineString', 'LinearRing']:
        coords = list(geom.coords); coords.append(coords[0]) if coords[0] != coords[-1] else None
        geom = Polygon(coords)
    new_gdf = gpd.GeoDataFrame(geometry=[geom], crs=gdf.crs)
    if new_gdf.crs is None: new_gdf.set_crs(epsg=4326, inplace=True)
    return new_gdf.to_crs(epsg=3763)

def render_map(gdf, area_m2, area_ha, perimeter_m, t_dict, property_name, is_premium=False):
    # PDF Premium com alta densidade de pixels (300 DPI)
    fig, ax = plt.subplots(figsize=(10, 12), dpi=300 if is_premium else 100)
    gdf.plot(ax=ax, facecolor="#4CAF50", edgecolor="black", linewidth=2, alpha=0.4, zorder=2)
    
    try:
        ctx.add_basemap(ax, crs=gdf.crs.to_string(), source=ctx.providers.OpenStreetMap.Mapnik, zorder=1)
    except: pass

    ax.set_title(f"{property_name}\n({t_dict['map_title']})", fontsize=16, fontweight='bold', pad=20)

    # DIFERENCIAÇÃO TÉCNICA
    if is_premium:
        # Elementos que o cliente PAGA para ter
        ax.add_artist(ScaleBar(1, units="m", location="lower right", box_alpha=0.7))
        ax.annotate('N', xy=(0.95, 0.95), xytext=(0.95, 0.87),
                    arrowprops=dict(facecolor='black', width=3, headwidth=10),
                    ha='center', va='center', fontsize=15, fontweight='bold', xycoords='axes fraction')
        ax.text(0.5, -0.02, t_dict["footer_tech"], transform=ax.transAxes, ha="center", fontsize=8, color="gray")
    else:
        # Marca de água na versão grátis
        ax.text(0.5, 0.5, t_dict["watermark"], transform=ax.transAxes, 
                ha="center", va="center", fontsize=22, color="red", alpha=0.25, rotation=35, fontweight='bold')

    ax.axis("off")
    legenda = (f"{t_dict['legend_area']}: {area_m2:,.0f} m² ({area_ha:.2f} ha)\n"
               f"{t_dict['perim']}: {perimeter_m:,.0f} m\n"
               f"{t_dict['legend_date']}: {datetime.now().strftime('%d/%m/%Y')}")
    ax.text(0.02, 0.02, legenda, transform=ax.transAxes, fontsize=10, bbox=dict(facecolor="white", alpha=0.8))
    
    return fig

# -------------------------
# INTERFACE STREAMLIT
# -------------------------
file = st.file_uploader(t["upload_label"], type=["kml", "gpx", "geojson"])

if file:
    try:
        with st.spinner(t["processing"]):
            gdf = validate_and_convert(load_geometry(file))
            geom = gdf.geometry.iloc[0]
            a_m2, a_ha, perim = geom.area, geom.area/10000, geom.length
            
            # Gerar ambas as versões
            fig_free = render_map(gdf, a_m2, a_ha, perim, t, nome_propriedade, is_premium=False)
            fig_premium = render_map(gdf, a_m2, a_ha, perim, t, nome_propriedade, is_premium=True)

        st.pyplot(fig_free)
        
        st.divider()
        col_free, col_prem = st.columns(2)
        
        with col_free:
            st.subheader(t["free_ver"])
            st.write(t["free_desc"])
            buf_png = io.BytesIO()
            fig_free.savefig(buf_png, format="png", bbox_inches="tight")
            st.download_button(t["btn_png"], buf_png.getvalue(), file_name=f"amostra_{nome_propriedade}.png", use_container_width=True)

        with col_prem:
            st.subheader(t["premium_ver"])
            st.write(t["premium_desc"])
            st.link_button(t["btn_pdf_venda"], "https://pestanaeu.gumroad.com/l/mapa-propriedade", use_container_width=True)
            
            # BOTÃO ADMIN (Apenas para o proprietário da app gerar o ficheiro pago)
            buf_pdf = io.BytesIO()
            fig_premium.savefig(buf_pdf, format="pdf", bbox_inches="tight")
            st.download_button(t["btn_pdf_admin"], buf_pdf.getvalue(), file_name=f"Relatorio_{nome_propriedade}.pdf", use_container_width=True)

    except Exception as e:
        st.error(f"Erro / Error: {e}")
