"""
Trabajo 2 · informe escrito en Word con la línea gráfica del informe final del Trabajo 1:
Times New Roman 11 justificado, títulos en negrita, tablas con título arriba («Tabla N.» en negrita cursiva, texto en cursiva),
figuras con leyenda centrada debajo («Figura N.» en negrita), portada con el escudo de la Universidad.

Incluye los numerales 1 a 5 del enunciado. Técnicas del numeral 5: mapeo de cuantiles, KNN con años análogos y regresión logística.
La EOF se reporta dentro del numeral 4. Las proyecciones CMIP6 y la operación del embalse (pywr) se agregarán después.

Incluye además la sección 6 (proyecciones CMIP6 con QDM). La operación del embalse (pywr) se agregará después.
Las cifras se leen de los resultados (trabajo2/resultados/); las figuras son los PNG de 300 dpi de 07_figuras y de cada numeral.
Salida: trabajo2/informe/Informe_Trabajo2_Hidroituango.docx
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[2]
R2 = ROOT / "trabajo2" / "resultados"
FG = R2 / "07_figuras"
INF = ROOT / "trabajo2" / "informe"
INF.mkdir(exist_ok=True)
SITIO = "https://anajul1a4.github.io/Hidroituango2/"
SITIO_T1 = "https://anajul1a4.github.io/balance-hidrico-hidroituango/"


# ============================================================================================ formato
def n(v, d=0, signo=False):
    """Número con punto decimal (como el Trabajo 1), espacio de miles desde 10 000 y signo menos tipográfico."""
    s = f"{v:+.{d}f}" if signo else f"{v:.{d}f}"
    ent, _, dec = s.lstrip("+-").partition(".")
    if len(ent) > 4:
        ent = f"{int(ent):,}".replace(",", " ")
    out = ent + ("." + dec if dec else "")
    if s.startswith("-"):
        out = "−" + out
    elif s.startswith("+"):
        out = "+" + out
    return out


doc = Document()
st = doc.styles["Normal"]
st.font.name = "Times New Roman"; st.font.size = Pt(11)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
st.paragraph_format.space_after = Pt(8); st.paragraph_format.line_spacing = 1.15
for s in doc.sections:
    s.page_width, s.page_height = Cm(21.0), Cm(29.7)
    s.left_margin = s.right_margin = Cm(2.54); s.top_margin = s.bottom_margin = Cm(2.54)
ANCHO = Cm(15.9)
for nivel in (1, 2, 3):
    h = doc.styles[f"Heading {nivel}"]
    h.font.name = "Times New Roman"; h.font.size = Pt(11); h.font.bold = True; h.font.italic = False
    h.font.color.rgb = RGBColor(0, 0, 0)
    h.element.rPr.rFonts.set(qn("w:asciiTheme"), "") if False else None
    rf = h.element.rPr.rFonts
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rf.set(qn(a), "Times New Roman")
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rf.get(qn(a)) is not None:
            del rf.attrib[qn(a)]
    h.paragraph_format.space_before = Pt(14 if nivel == 1 else 10); h.paragraph_format.space_after = Pt(6)
    h.paragraph_format.keep_with_next = True
NT, NF = [0], [0]


def par(texto="", just=True, italic=False, bold=False, center=False, size=None, after=None):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else (WD_ALIGN_PARAGRAPH.JUSTIFY if just else WD_ALIGN_PARAGRAPH.LEFT)
    if texto:
        rich(p, texto, italic=italic, bold=bold, size=size)
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    return p


def rich(p, texto, italic=False, bold=False, size=None):
    """Texto con marcas simples: **negrita**, _cursiva_, ^superíndice^ y ~subíndice~."""
    import re
    for trozo in re.split(r"(\*\*.+?\*\*|_.+?_|\^.+?\^|~.+?~)", texto):
        if not trozo:
            continue
        b, i, sup, sub = bold, italic, False, False
        if trozo.startswith("**"):
            trozo, b = trozo[2:-2], True
        elif trozo.startswith("_") and trozo.endswith("_") and len(trozo) > 2:
            trozo, i = trozo[1:-1], True
        elif trozo.startswith("^"):
            trozo, sup = trozo[1:-1], True
        elif trozo.startswith("~"):
            trozo, sub = trozo[1:-1], True
        r = p.add_run(trozo)
        r.bold, r.italic = b, i
        r.font.superscript, r.font.subscript = sup, sub
        if size:
            r.font.size = Pt(size)
    return p


def titulo(texto, nivel=1):
    return doc.add_heading(texto, level=nivel)


def ecuacion(texto):
    p = par(center=True)
    rich(p, texto, italic=True)
    return p


def vinetas(items):
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        rich(p, it)
        p.paragraph_format.space_after = Pt(3)


def figura(ruta, texto, ancho=ANCHO):
    NF[0] += 1
    p = par(center=True, after=2)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(ruta), width=ancho)
    c = par(center=True)
    r = c.add_run(f"Figura {NF[0]}. "); r.bold = True
    rich(c, texto)
    return NF[0]


def leyenda_tabla(texto):
    NT[0] += 1
    p = par(just=True, after=4)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(f"Tabla {NT[0]}. "); r.bold = True; r.italic = True
    rich(p, texto, italic=True)
    return NT[0]


def bordes(tabla, color="BFBFBF"):
    tblPr = tabla._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{lado}")
        e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "4"); e.set(qn("w:space"), "0"); e.set(qn("w:color"), color)
        b.append(e)
    tblPr.append(b)


def tabla(cab, filas, anchos=None, size=10, negrita_col1=True, resaltar=None):
    t = doc.add_table(rows=1 + len(filas), cols=len(cab))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    bordes(t)
    for i, fila in enumerate([cab] + filas):
        for j, v in enumerate(fila):
            c = t.cell(i, j)
            c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p = c.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(1); p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.line_spacing = 1.0
            rich(p, str(v), bold=(i == 0 or (j == 0 and negrita_col1) or (resaltar is not None and i - 1 == resaltar)), size=size)
            if i < len(filas):
                p.paragraph_format.keep_with_next = True          # la tabla no se parte entre páginas
    if anchos:
        for j, w in enumerate(anchos):
            for c in t.columns[j].cells:
                c.width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def salto():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ============================================================================================ datos
ENT = R2 / "01_entradas"
cel = pd.read_csv(ENT / "grilla_celdas.csv")
w = cel.a_cuenca_km2.values
S = pd.read_csv(ENT / "series_unidades.csv", header=[0, 1], index_col=0, parse_dates=True)
C = S.xs("CUENCA", axis=1, level="unidad")
cic = pd.read_csv(R2 / "02_comparacion" / "ciclo_anual_cuenca.csv", index_col=0)
met = pd.read_csv(R2 / "02_comparacion" / "metricas_vs_cubo.csv")
m81, m11 = met[met.periodo == "1981–2010"].set_index("producto"), met[met.periodo == "2011–2023"].set_index("producto")
bal = pd.read_csv(R2 / "02_comparacion" / "balance_productos_cubo.csv", dtype={"codigo": str})
orig = xr.open_dataset(ROOT / "CUBO_IDEAM" / "prcp_mes_acum_1981_2023.nc").prcp.sel(
    lat=xr.DataArray(cel.lat.values, dims="c"), lon=xr.DataArray(cel.lon.values, dims="c"), method="nearest")
oc = pd.Series((orig.values * w).sum(1) / w.sum(), index=pd.DatetimeIndex(orig.time.values))
r_o = oc.corr(C["P CHIRPS v2.0"].reindex(oc.index)); r_l = C["P Cubo IDEAM"].corr(C["P CHIRPS v2.0"])
P_orig = oc["1981":"2010"].resample("YS").sum().mean(); P_cubo = C["P Cubo IDEAM"]["1981":"2010"].resample("YS").sum().mean()
e95 = oc["1995-01"].iloc[0]; c95 = C["P CHIRPS v2.0"]["1995-01"].iloc[0]
eto_pm = C["ETo PM"]["1981":"2010"].resample("YS").sum().mean(); eto_hg = C["ETo Hargreaves"]["1981":"2010"].resample("YS").sum().mean()
marc = pd.read_csv(R2 / "00_limpieza_cubo" / "marcados_por_mes.csv", index_col=0, parse_dates=True)
frac_marc = None
ABC = R2 / "04_abcd"
fin = json.loads((ABC / "modelo_final.json").read_text(encoding="utf-8"))
M = pd.concat([pd.read_csv(ABC / "metricas.csv"), pd.read_csv(ABC / "regionalizado_metricas.csv")])
M["per"] = np.where(M.periodo.str.startswith("cal"), "cal", "val")
REG = "abcd semidistribuido regionalizado"
mf = M[(M.modelo == REG) & (M.producto == "Cubo IDEAM") & (M.ETo == "Hargreaves")]
EST = ["La Balsa", "Juanchito", "La Victoria", "La Virginia", "Irra", "La Pintada", "Puente Iglesias", "Bolombolo", "Cañafisto", "Presa"]
par_r = pd.read_csv(ABC / "regionalizado_parametros.csv")
p0 = par_r[(par_r.producto == "Cubo IDEAM") & (par_r.ETo == "Hargreaves")].iloc[0]
kv = mf[mf.per == "val"].KGE.mean(); kc = mf[mf.per == "cal"].KGE.mean()
pres = mf[mf["estación"] == "Presa"].set_index("per")


def kmed(modelo, prod, eto, per="val"):
    d = M[(M.modelo == modelo) & (M.producto == prod) & (M.ETo == eto) & (M.per == per)]
    return d.KGE.mean()


def kpre(modelo, prod, eto, per="val", col="KGE"):
    d = M[(M.modelo == modelo) & (M.producto == prod) & (M.ETo == eto) & (M.per == per) & (M.codigo == "PRESA")]
    return float(d[col].iloc[0]) if len(d) else np.nan


EP, ES = R2 / "05_enso_P", R2 / "06_enso_suelo_Q"
comp = pd.read_csv(EP / "compuestos_cuenca.csv")
cons = pd.read_csv(EP / "consistencia.csv")
coni = pd.read_csv(EP / "correlacion_oni.csv")
fases = pd.read_csv(EP / "fases_enso.csv")
ts = pd.read_csv(ES / "suelo_compuestos.csv").set_index(["fase", "trimestre"])
tq = pd.read_csv(ES / "caudales_compuestos.csv")
rz = pd.read_csv(ES / "rezagos_oni.csv").set_index("variable")
rp = pd.read_csv(ES / "rezagos_P.csv", index_col=0)
cpf = pd.read_csv(ES / "ciclo_por_fase.csv")
mem = pd.read_csv(ES / "suelo_memoria_celdas.csv", index_col=0)
eofr = pd.read_csv(R2 / "09_eof" / "eof_resumen.csv", index_col=0)
PRN = R2 / "08_pronostico"
mq3 = pd.read_csv(PRN / "metricas_Q3.csv", index_col=0)
mpb = pd.read_csv(PRN / "metricas_probabilidad.csv", index_col=0)
hzm = pd.read_csv(PRN / "horizonte_mensual.csv", index_col=0)
alr = pd.read_csv(PRN / "alertas.csv")
cof = pd.read_csv(PRN / "coeficientes_logistica.csv")
prs = json.loads((PRN / "sitio.json").read_text(encoding="utf-8"))
K = prs["K"]; KQ = f"KNN (k = {K})"; LS = "Logística · ONI + suelo"; LO = "Logística · ONI"
TR = ["DEF", "MAM", "JJA", "SON"]
PRODS5 = ["Cubo IDEAM", "CHIRPS v2.0", "CHIRPS v3.0", "ERA5-Land", "ERA5"]


def zc(p, t, fa):
    return float(comp[(comp.producto == p) & (comp.trimestre == t) & (comp.fase == fa)]["z medio de la cuenca"].iloc[0])


def zq(e, t, fa, col):
    return float(tq[(tq["estación"] == e) & (tq.trimestre == t) & (tq.fase == fa)][col].iloc[0])


def ro(p, t):
    return float(coni[(coni.producto == p) & (coni.trimestre == t)]["r(ONI, z cuenca)"].iloc[0])


def rcons(p, t, fa):
    return float(cons[(cons.producto == p) & (cons.trimestre == t) & (cons.fase == fa)]["r espacial con el Cubo"].iloc[0])


cp = cpf[cpf["estación"] == "Presa"].pivot(index="mes", columns="fase", values=["Q observado", "Q simulado"])
red_obs = 100 * (cp["Q observado"]["El Niño"] / cp["Q observado"]["Neutro"] - 1)
red_sim = 100 * (cp["Q simulado"]["El Niño"] / cp["Q simulado"]["Neutro"] - 1)
aum_obs = 100 * (cp["Q observado"]["La Niña"] / cp["Q observado"]["Neutro"] - 1)
MESN = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
n_nino = int((fases[(fases.YR >= 1981) & (fases.YR <= 2023)].fase == "El Niño").sum())
orx = lambda mod, var: float(cof[(cof.modelo == mod) & (cof.variable == var)]["razón de odds por 1 σ"].iloc[0])  # noqa: E731
al = lambda met_, niv, col: float(alr[(alr["método"] == met_) & (alr.nivel.str.startswith(niv))][col].iloc[0])  # noqa: E731
FRQ, PCT = "frecuencia observada del trimestre seco (%)", "% de los meses"

# ============================================================================================ portada
par()
p = par(center=True); p.add_run().add_picture(str(INF / "escudo_unal.png"), width=Cm(4.2))
for _ in range(2):
    par()
par("**Trabajo 2 Hidrometeorología**", center=True)
for _ in range(3):
    par()
par("Modelación hidrológica mensual de la cuenca del río Cauca hasta Hidroituango y efectos del ENSO sobre la lluvia, la humedad del "
    "suelo y los caudales", center=True)
for _ in range(2):
    par()
par("Juliana Aguirre Lopera", center=True, after=4)
par("David Moreno Yepes", center=True)
par()
p = par(center=True); r = p.add_run(SITIO); r.font.color.rgb = RGBColor(0x11, 0x55, 0xCC); r.underline = True
for _ in range(6):
    par()
par("Facultad de Minas, Universidad Nacional de Colombia, sede Medellín", center=True, after=4)
par("12 de noviembre de 2026", center=True)
p = par(after=0); r = p.add_run("Nota: "); r.bold = True; r.italic = True
rich(p, "las figuras de este informe se limitan a lo solicitado en el enunciado; en la página web se presentan análisis adicionales y "
        "las series en formato interactivo.", italic=True)
salto()

# ============================================================================================ resumen
titulo("Resumen")
par(f"La generación hidroeléctrica en Colombia depende de cuánta agua llega a los embalses mes a mes, y esa cantidad cambia con El Niño "
    f"y La Niña y cambiará con el clima de las próximas décadas. En este trabajo se construyó un modelo lluvia-escorrentía mensual para la "
    f"cuenca del río Cauca hasta Hidroituango (35 992 km²) y se usó para estudiar cómo responden la lluvia, la humedad del suelo y los "
    f"caudales al ENSO. Se evaluaron cinco productos de precipitación: el Cubo de datos del IDEAM, CHIRPS v2.0, CHIRPS v3.0, ERA5-Land y "
    f"ERA5. El Cubo traía valores diarios de hasta 4702 mm que hubo que depurar; una vez corregido, coincide con CHIRPS (r mensual de "
    f"{n(r_l, 2)}). ERA5 y ERA5-Land, en cambio, casi triplican la lluvia y solo sirven después de corregirlos por mapeo de cuantiles. "
    f"El modelo abcd, semidistribuido en diez unidades y calibrado a la vez con diez estaciones de caudal, reprodujo los caudales "
    f"mensuales con un KGE de validación de {n(kv, 2)} en promedio y de {n(pres.loc['val', 'KGE'], 2)} en la presa. Durante El Niño la "
    f"lluvia de la cuenca baja sobre todo en diciembre-febrero y junio-agosto, el suelo se seca en más del 99 % del área y sigue seco en "
    f"marzo-mayo aunque la lluvia ya esté cerca de lo normal, y los caudales en la presa caen hasta {n(zq('Presa', 'DEF', 'El Niño', 'z Q observado'), 2)} "
    f"desviaciones estándar, con unos dos meses de rezago frente al ONI. Esa memoria del suelo y del acuífero es aprovechable: con el ONI "
    f"y el estado del suelo simulado, un pronóstico por años análogos (KNN) reduce en un {n(100 * mq3.loc[KQ, 'CRPSS'])} % el error de la "
    f"climatología para el aporte de los tres meses siguientes, y una regresión logística estima la probabilidad de un trimestre seco "
    f"con la que se definieron umbrales de alerta. Con seis modelos CMIP6 corregidos por mapeo de cuantiles con deltas, el caudal medio en "
    f"la presa cambia poco en este siglo, pero en el escenario SSP5-8.5 los caudales bajos se reducen cerca de un 30 % hacia 2071-2100 por "
    f"el aumento de la evapotranspiración. Se concluye que el modelo abcd con la lluvia del Cubo, o de CHIRPS v2.0 para operar en "
    f"tiempo casi real, es una base adecuada para un sistema de modelación mensual de los aportes a Hidroituango.")

# ============================================================================================ introducción
titulo("Introducción")
par("Cerca del 69 % de la matriz eléctrica de Colombia es hidráulica (La República, 2019, con datos de XM). Esta dependencia hace que la "
    "disponibilidad de energía siga de cerca a la del agua. Cuando llueve menos, los embalses bajan, la generación térmica, más costosa, "
    "tiene que cubrir la diferencia y el precio de la energía sube. La sequía asociada a El Niño de 1991-1992 llevó a un racionamiento de "
    "cerca de un año (Carvajal et al., 1998), y durante El Niño 2015-2016 el país llegó cerca de repetirlo: se evitó con generación "
    "térmica, importaciones desde Ecuador y campañas de ahorro (Superservicios, 2016).")
par("Hidroituango, sobre el río Cauca en Antioquia, es la central más grande del país, con 2400 MW en ocho unidades de 300 MW. En el "
    f"Trabajo 1 se estimó con un balance de largo plazo que su cuenca produce en promedio unos 1000 m³/s, y se mostró que los caudales "
    "responden al ENSO con más fuerza que la lluvia. Ese promedio sirve para dimensionar el proyecto, pero no para operarlo. La operación "
    "se decide mes a mes: cuánta agua guardar antes de la temporada seca, cuánta energía ofrecer y cuándo prepararse para una sequía. "
    "Para eso hace falta un modelo que convierta la lluvia y la temperatura de cada mes en caudal, y que represente el agua que la cuenca "
    "almacena en el suelo y en el acuífero, porque es esa agua almacenada la que mantiene el río en los meses secos.")
par("El problema no es solo la variabilidad actual. Según el IPCC (2021), el calentamiento global seguirá intensificando el ciclo "
    "hidrológico y su variabilidad, incluida la severidad de los periodos húmedos y secos. Una mayor temperatura aumenta además la demanda "
    "evaporativa, de modo que, aun con la misma lluvia, puede llegar menos agua a los ríos. Para el sector eléctrico, saber cómo cambiará "
    "la oferta de agua de una cuenca como la del Cauca es parte de la planeación de largo plazo, y la herramienta para estimarlo es la "
    "misma: un modelo hidrológico calibrado que pueda alimentarse con escenarios climáticos.")
par("En este trabajo se construye ese modelo y se usa para tres fines: (1) evaluar qué información climática es más adecuada para "
    "simular los caudales mensuales de la cuenca; (2) describir los efectos de El Niño y La Niña sobre la lluvia, la humedad del suelo y "
    "los caudales; (3) mostrar cómo la memoria del suelo y del acuífero permite anticipar los aportes de los meses siguientes, y (4) estimar "
    "con modelos climáticos CMIP6 cómo podría cambiar la oferta de agua de la cuenca en este siglo. El efecto sobre la operación del "
    "embalse y la energía generada se presentará en una entrega posterior.")

# zona de estudio
titulo("Cuenca de estudio")
par("La cuenca aportante a Hidroituango comprende los primeros 855 km del río Cauca, desde su nacimiento en el Macizo Colombiano hasta "
    "el sitio de presa (7.13° N, 75.66° W), con un área de 35 992 km² según la delimitación con el DEM Copernicus GLO-30 del Trabajo 1. "
    "El río atraviesa tres ambientes: la cabecera en el Macizo, el valle geográfico del río Cauca entre Popayán y Cartago, y el cañón "
    "antioqueño desde La Pintada hasta la presa. La lluvia media es de unos 2000 mm/año, con un régimen bimodal: temporadas húmedas en "
    "marzo-mayo y octubre-noviembre y estiajes en diciembre-febrero y junio-agosto.")
par("Para el modelo se usaron las diez estaciones de caudal del cauce principal validadas en el Trabajo 1 (La Balsa, Juanchito, La "
    "Victoria, La Virginia, Irra, La Pintada, Puente Iglesias, Bolombolo y Cañafisto) y el caudal de Puerto Valdivia transferido a la "
    "presa por relación de áreas (35 992 / 37 267). Desde 2018 Puerto Valdivia mide el caudal regulado por el embalse, así que el caudal "
    "en la presa se usó solo hasta 2017. La cuenca se dividió en diez unidades, que son las áreas incrementales entre estaciones "
    "sucesivas (Figura 1).")
figura(FG / "mapa_unidades.png", "Unidades del modelo (áreas incrementales entre estaciones de caudal del río Cauca) y estaciones usadas "
       "en la calibración.", ancho=Cm(10.5))

# ============================================================================================ numeral 1
titulo("1. Calibración y evaluación de un modelo lluvia-escorrentía mensual")
titulo("1a. Variables de entrada", 2)
par("**Precipitación.** Se evaluaron cinco productos de lluvia mensual en el periodo común 1981-2023 (Tabla 1). Todos se llevaron a la "
    "grilla del Cubo de datos del IDEAM (0.1°, unos 11 km), que tiene 376 celdas en la cuenca. Para cada celda se calculó la fracción "
    "de su área que cae en cada unidad, de modo que las series de lluvia de cada unidad son el promedio ponderado por área de sus celdas. "
    "CHIRPS se agregó desde 0.05°, ERA5-Land se tomó en su propia retícula de 0.1° y ERA5 se interpoló desde 0.25°.")
leyenda_tabla("Productos de precipitación evaluados.")
tabla(["Producto", "Tipo", "Resolución", "Referencia"],
      [["Cubo de datos IDEAM", "Interpolación de 1567 estaciones con el software CDT", "0.1°", "IDEAM (2025)"],
       ["CHIRPS v2.0", "Satélite infrarrojo combinado con estaciones", "0.05°", "Funk et al. (2015)"],
       ["CHIRPS v3.0", "Nueva versión de CHIRPS, con más estaciones", "0.05°", "Climate Hazards Center"],
       ["ERA5-Land", "Reanálisis de superficie forzado por ERA5", "0.1°", "Muñoz-Sabater et al. (2021)"],
       ["ERA5", "Reanálisis atmosférico global", "0.25°", "Hersbach et al. (2020)"]], anchos=[3.4, 6.6, 2.0, 3.9])

par("**Control de calidad del Cubo de datos.** El Cubo es el producto más cercano a las estaciones, pero al revisarlo en la cuenca se "
    f"encontraron valores diarios imposibles, de 1945 a 4702 mm en un solo día, concentrados en diciembre-febrero. El archivo mensual es "
    f"la suma de los diarios, así que hereda esos errores. En enero de 1995, por ejemplo, la lluvia media de la cuenca era de {n(e95)} mm, "
    f"cuando CHIRPS da {n(c95)} mm, y el ciclo anual mostraba enero y febrero tan lluviosos como octubre (Figura 2a). La correlación "
    f"mensual con CHIRPS era de solo {n(r_o, 2)}.")
par("Los valores erróneos aparecen como celdas aisladas, mucho más altas que todas sus vecinas el mismo día. Por eso se marcó como error "
    "la lluvia diaria de una celda que supera 100 mm y es más de cuatro veces la mediana de sus 5 × 5 vecinas, o que supera 500 mm, y "
    "se reemplazó por esa mediana. La corrección cambió solo el 0.09 % de las celdas-día, pero bajó la lluvia media de la cuenca de "
    f"{n(P_orig)} a {n(P_cubo)} mm/año y subió la correlación mensual con CHIRPS a {n(r_l, 2)} (Figura 2). Este error del Cubo no está "
    "documentado y podría afectar otras cuencas, por lo que convendría reportarlo al IDEAM.")
figura(FG / "fig_cubo_limpieza.png", "Lluvia media de la cuenca en el Cubo de datos original, en el Cubo después del control de calidad y en "
       "CHIRPS v2.0: a) ciclo anual 1981-2010; b) serie mensual 1981-2023.")

par("**Temperatura y evapotranspiración de referencia.** El Cubo incluye temperatura máxima, mínima y media y humedad relativa mensuales "
    "en la misma grilla. Con ellas se calculó la evapotranspiración de referencia (ETo) de dos formas. La primera es FAO Penman-Monteith, "
    "el método que adoptó el IDEAM como referencia para Colombia (IDEAM, 2021). Como el Cubo no trae radiación ni viento, se usó el "
    "procedimiento de FAO-56 para datos faltantes (Allen et al., 1998): la radiación solar se estimó con la diferencia Tmax - Tmin "
    "(k~Rs~ = 0.16, para sitios del interior), la presión de vapor real con la humedad relativa media, el viento se fijó en 2 m/s y la "
    "presión atmosférica se calculó con la elevación media de cada celda. La segunda es Hargreaves y Samani (1985), el método del "
    "Trabajo 1, que solo usa la temperatura y la radiación extraterrestre:")
ecuacion("ETo = 0.0023 · 0.408 · Ra · (Tmed + 17.8) · (Tmax − Tmin)^0.5^")
par(f"En 1981-2010 la ETo media de la cuenca es de {n(eto_pm)} mm/año con Penman-Monteith y de {n(eto_hg)} mm/año con Hargreaves, un "
    f"{n(100 * (eto_hg / eto_pm - 1))} % más (Figura 3c). Las dos se usaron en el modelo para ver cuánto pesa esta elección.")

titulo("1b. Evaluación y corrección de los productos", 2)
par("Cada producto se comparó con el Cubo corregido en la serie mensual promedio de la cuenca, con la correlación de Pearson, el sesgo, el "
    "KGE y la correlación de las anomalías mensuales (la serie sin el ciclo anual), que mide si el producto acierta en qué meses llueve más "
    "o menos de lo normal. La comparación se hizo en 1981-2010 y se repitió en 2011-2023 como verificación independiente (Tabla 2). La "
    "Figura 4 compara los campos de lluvia media anual y la Figura 3 los ciclos anuales.")
leyenda_tabla("Lluvia media de la cuenca de cada producto frente al Cubo de datos del IDEAM corregido.")
fil = []
for p_ in ["Cubo IDEAM", "CHIRPS v2.0", "CHIRPS v3.0", "ERA5-Land", "ERA5", "ERA5-Land QM", "ERA5 QM"]:
    nom = p_.replace(" QM", " corregido")
    if p_ == "Cubo IDEAM":
        fil.append([nom, n(P_cubo), "—", "—", "—", "—", "—"])
    else:
        a, b = m81.loc[p_], m11.loc[p_]
        fil.append([nom, n(a["P anual (mm/año)"]), ("0.0" if abs(a["sesgo (%)"]) < 0.05 else n(a["sesgo (%)"], 1, True)), n(a["r mensual"], 2), n(a["r anomalías mensuales"], 2),
                    n(a["KGE"], 2), n(b["KGE"], 2)])
tabla(["Producto", "P 1981-2010 (mm/año)", "Sesgo (%)", "r mensual", "r de las anomalías", "KGE 1981-2010", "KGE 2011-2023"], fil,
      anchos=[3.2, 2.3, 1.8, 1.8, 2.2, 2.2, 2.2])
par(f"Los tres productos que usan estaciones coinciden. CHIRPS v2.0 tiene un sesgo de {n(m81.loc['CHIRPS v2.0', 'sesgo (%)'], 1, True)} % y una "
    f"correlación de sus anomalías de {n(m81.loc['CHIRPS v2.0', 'r anomalías mensuales'], 2)}; CHIRPS v3.0 tiene menos sesgo "
    f"({n(m81.loc['CHIRPS v3.0', 'sesgo (%)'], 1, True)} %) pero sigue algo peor la secuencia de los meses ({n(m81.loc['CHIRPS v3.0', 'r anomalías mensuales'], 2)}). "
    f"Los tres reproducen el ciclo bimodal y el mismo patrón espacial, con la lluvia más alta en las vertientes de las cordilleras y el "
    f"mínimo en el fondo del valle (Figura 4). ERA5 y ERA5-Land, como en el Trabajo 1, casi triplican la lluvia "
    f"({n(m81.loc['ERA5', 'P anual (mm/año)'])} mm/año, {n(m81.loc['ERA5', 'sesgo (%)'], 0, True)} %), su patrón espacial no se "
    f"parece al de las estaciones (r espacial ≈ 0) y aplanan el ciclo anual, con el máximo en abril-mayo (Figura 3a).")
figura(FG / "fig_ciclo_productos.png", "Ciclo anual de la lluvia media de la cuenca (1981-2010): a) productos sin corregir y normales del "
       "IDEAM interpoladas en el Trabajo 1; b) ERA5 y ERA5-Land corregidos por mapeo de cuantiles con el Cubo; c) evapotranspiración de "
       "referencia por Penman-Monteith y por Hargreaves.")
figura(R2 / "02_comparacion" / "mapas_P_productos.png", "Precipitación media anual 1981-2010 de cada producto en la grilla del Cubo de "
       "datos del IDEAM. Un mismo valor tiene el mismo color en todos los mapas. «QM»: corregido por mapeo de cuantiles con el Cubo.")
par("**Corrección de sesgo.** En el Trabajo 1 ERA5 y ERA5-Land ya se habían corregido por mapeo de cuantiles con CHIRPS v2.0 como "
    "referencia, porque del IDEAM solo se tenían normales climatológicas. En este trabajo se repitió la corrección con el Cubo, que sí "
    "tiene series mensuales en cada celda. El método y su evaluación se presentan como técnica de análisis de datos en la sección 5.1. En "
    f"síntesis, la corrección elimina el sesgo y recupera el ciclo anual y el patrón medio, pero no la secuencia de los meses: en "
    f"2011-2023 ERA5 corregido tiene un KGE de {n(m11.loc['ERA5 QM', 'KGE'], 2)}, frente a {n(m11.loc['CHIRPS v2.0', 'KGE'], 2)} de CHIRPS.")
par("**Balance de largo plazo.** Para elegir los productos de la simulación se repitió el balance del Trabajo 1 (ETR de Budyko celda a "
    "celda) con cada combinación de lluvia y ETo, y se comparó con el caudal observado en las nueve estaciones y en la presa (Tabla 3).")
leyenda_tabla("Error del balance de largo plazo 1981-2010 (Q estimado / Q observado − 1) con cada producto de lluvia y cada ETo.")
rb = pd.read_csv(R2 / "02_comparacion" / "resumen_balance.csv", header=[0, 1], index_col=0)
fil = []
for p_ in ["Cubo IDEAM", "CHIRPS v2.0", "CHIRPS v3.0", "ERA5-Land", "ERA5", "ERA5 QM"]:
    r_ = rb.loc[p_]
    fil.append([p_.replace(" QM", " corregido"), n(float(r_[("cierre", "Penman-Monteith")]), 1, True), n(float(r_[("cierre", "Hargreaves")]), 1, True),
                n(float(r_[("MAE", "Penman-Monteith")]), 1), n(float(r_[("MAE", "Hargreaves")]), 1)])
tabla(["Producto", "Cierre, ETo PM (%)", "Cierre, ETo Hargreaves (%)", "Error absoluto medio 9 estaciones, PM (%)",
       "Error absoluto medio 9 estaciones, Hargreaves (%)"], fil, anchos=[3.2, 2.8, 3.0, 3.4, 3.5])
par("Con la lluvia del Cubo el balance produce más agua de la observada: +20 % en el cierre con Penman-Monteith y +9 % con Hargreaves. "
    "Con CHIRPS v2.0, que tiene unos 6 % menos de lluvia, el error queda entre −4 % y +7 %. Esto indica que el Cubo sobrestima algo la "
    "lluvia de la cuenca, o que la curva de Budyko subestima la evaporación, y que la ETo más alta de Hargreaves compensa parte de la "
    "diferencia. Con base en estos resultados se llevaron al modelo los productos con estaciones (Cubo, CHIRPS v2.0 y v3.0) y los "
    "reanálisis corregidos; ERA5 sin corregir se incluyó solo como contraste.")

titulo("1c. Modelo abcd: calibración y validación", 2)
par("Se usó el modelo de balance hídrico mensual abcd (Thomas, 1981), en la notación de Martinez y Gupta (2010). Tiene dos depósitos, el "
    "suelo (S) y el agua subterránea (G), y cuatro parámetros. En cada mes el agua disponible W es la lluvia más el almacenamiento del mes "
    "anterior, y la oportunidad de evapotranspiración Y es la parte de W que puede quedarse en el suelo o evaporarse:")
ecuacion("W~t~ = P~t~ + S~t−1~            Y~t~ = (W~t~ + b) / 2a − [((W~t~ + b) / 2a)^2^ − W~t~ · b / a]^0.5^")
ecuacion("S~t~ = Y~t~ · exp(−ETo~t~ / b)            ETR~t~ = Y~t~ − S~t~")
ecuacion("G~t~ = [G~t−1~ + c · (W~t~ − Y~t~)] / (1 + d)            Q~t~ = (1 − c) · (W~t~ − Y~t~) + d · G~t~")
par("El parámetro a (entre 0 y 1) controla qué tan pronto se genera escorrentía antes de que el suelo se llene; b (mm) es la capacidad de "
    "almacenamiento del suelo más la evapotranspiración del mes; c es la fracción del excedente que recarga el acuífero, y d (1/mes) la "
    "rapidez con que el acuífero se vacía al río. S es la variable de humedad del suelo que se analiza en el numeral 3, y G da al caudal "
    "la memoria que se discute en el numeral 4.")
par("**Versión distribuida y calibración multisitio.** El modelo se corrió en cada una de las 376 celdas del Cubo con su propia lluvia y "
    "su propia ETo, y el caudal en cada estación es la suma de lo que producen las celdas de las unidades aguas arriba. Con paso mensual, "
    "el tiempo de viaje del agua por el cauce (días) no se representa. La función objetivo fue el KGE (Gupta et al., 2009), que combina "
    "correlación, variabilidad y sesgo, y se optimizó por evolución diferencial (Storn y Price, 1997). El periodo de calibración fue "
    "1982-2005 (1981 se usó para calentar el modelo) y el de validación 2006-2023; en la presa la validación llega hasta 2017.")
par("Se probaron dos esquemas. En el primero, secuencial, cada unidad tiene sus cuatro parámetros y se calibra de aguas arriba hacia "
    "abajo con su estación. El ajuste fue bueno, pero muchos parámetros quedaron en los límites del rango: las unidades pequeñas absorbían "
    "el error de lo simulado aguas arriba. En el segundo, regionalizado, a, c y d son comunes a toda la cuenca y b es propio de cada unidad "
    "(14 parámetros), y todos se ajustan a la vez para maximizar el KGE medio de las diez estaciones. Este esquema se probó con las dos "
    "mejores lluvias (Cubo y CHIRPS v2.0) y las dos ETo.")
par(f"La mejor combinación fue el modelo regionalizado con la lluvia del Cubo y la ETo de Hargreaves, con un KGE medio de {n(kc, 2)} en "
    f"calibración y de {n(kv, 2)} en validación (Tabla 4 y Figura 5). Sus parámetros comunes son a = {n(p0.a, 2)}, c = {n(p0.c, 2)} y "
    f"d = {n(p0.d, 2)}/mes; b varía entre {n(min(p0[c_] for c_ in p0.index if c_.startswith('b ')))} y 3000 mm. Un c alto significa que "
    f"casi todo el excedente pasa por el acuífero, lo que es coherente con la respuesta lenta de los caudales que se describe en el "
    f"numeral 4. Tres unidades (La Balsa, Juanchito y la última unidad antes de la presa) quedaron con b en el límite de 3000 mm: es la "
    f"forma que tiene el modelo de evaporar más agua donde la lluvia del Cubo excede lo que mide el río.")
leyenda_tabla("Desempeño del modelo final (abcd regionalizado, lluvia del Cubo, ETo de Hargreaves) por estación.")
fil = []
for e in EST:
    d = mf[mf["estación"] == e].set_index("per")
    fil.append([e, n(d.loc["cal", "NSE"], 2), n(d.loc["cal", "KGE"], 2), n(d.loc["cal", "PBIAS"], 1, True), n(d.loc["val", "NSE"], 2),
                n(d.loc["val", "KGE"], 2), n(d.loc["val", "RMSE"]), n(d.loc["val", "PBIAS"], 1, True)])
tabla(["Estación", "NSE cal.", "KGE cal.", "Sesgo cal. (%)", "NSE val.", "KGE val.", "RMSE val. (m³/s)", "Sesgo val. (%)"], fil,
      anchos=[3.0, 1.6, 1.6, 1.9, 1.6, 1.6, 2.4, 1.9], size=9.5)
figura(FG / "fig_kge_estaciones.png", "KGE de calibración (1982-2005) y de validación (2006-2023) del modelo final en cada estación. El "
       "número blanco es el sesgo de la validación; la línea punteada marca KGE = 0.75.")
par("El desempeño se mantiene fuera del periodo de calibración en casi todas las estaciones. Desde La Victoria hacia aguas abajo el KGE de "
    f"validación está entre {n(mf[(mf.per == 'val') & mf['estación'].isin(EST[2:])].KGE.min(), 2)} y "
    f"{n(mf[(mf.per == 'val') & mf['estación'].isin(EST[2:])].KGE.max(), 2)}, y en la presa el NSE es de {n(pres.loc['val', 'NSE'], 2)} con un "
    f"sesgo de {n(pres.loc['val', 'PBIAS'], 1, True)} %. Las dos estaciones más débiles son las de aguas arriba. La Balsa está aguas abajo "
    "del embalse de Salvajina, que desde 1985 regula el caudal mes a mes, y el modelo no representa esa regulación. Juanchito recibe la "
    "misma regulación y además las extracciones para riego y acueductos del valle, y en validación el modelo subestima su caudal en un 22 %. "
    "La Figura 6 muestra que el modelo ubica en su lugar las sequías de El Niño (1992, 1997-1998, 2009-2010, 2015-2016) y los caudales "
    "altos de La Niña (1999-2000, 2008, 2010-2011), aunque subestima algunos picos, como el de finales de 2010.")
figura(FG / "fig_series_Q.png", "Caudal medio mensual observado y simulado por el modelo final en La Virginia, Bolombolo y la presa. La "
       "banda gris es el periodo de calibración.")

par("**Comparación de configuraciones.** La Tabla 5 resume las variantes probadas. Se incluyó la ecuación empírica de las diapositivas "
    "del curso, Q = α · (P − ETR) + β, con la ETR de Budyko mensual, ajustada por mínimos cuadrados en la presa, y la misma ecuación con el "
    "caudal del mes anterior como predictor adicional.")
leyenda_tabla("KGE de las configuraciones probadas: promedio de las diez estaciones y en la presa (validación). Se resalta el modelo final.")
filas_m = [
    ("abcd regionalizado", REG, "Cubo IDEAM", "Hargreaves"), ("abcd regionalizado", REG, "Cubo IDEAM", "Penman-Monteith"),
    ("abcd regionalizado", REG, "CHIRPS v2.0", "Penman-Monteith"), ("abcd regionalizado", REG, "CHIRPS v2.0", "Hargreaves"),
    ("abcd secuencial", "abcd semidistribuido", "Cubo IDEAM", "Penman-Monteith"), ("abcd secuencial", "abcd semidistribuido", "CHIRPS v3.0", "Penman-Monteith"),
    ("abcd secuencial", "abcd semidistribuido", "ERA5-Land QM", "Penman-Monteith"), ("abcd secuencial", "abcd semidistribuido", "ERA5 QM", "Penman-Monteith"),
    ("abcd secuencial", "abcd semidistribuido", "ERA5", "Penman-Monteith"), ("abcd agregado", "abcd agregado", "Cubo IDEAM", "Penman-Monteith"),
    ("Empírico con Q(t−1)", "empírico con memoria Q = α·W + γ·Q(t−1) + β", "Cubo IDEAM", "Penman-Monteith"),
    ("Empírico", "empírico Q = α·W + β", "Cubo IDEAM", "Penman-Monteith")]
fil = []
for et, mo, pr_, eto in filas_m:
    semi = "semidistribuido" in mo
    fil.append([et, pr_.replace(" QM", " corregido"), "PM" if eto == "Penman-Monteith" else "Hargreaves",
                n(kmed(mo, pr_, eto), 2) if semi else "—", n(kpre(mo, pr_, eto), 2)])
tabla(["Configuración", "Lluvia", "ETo", "KGE medio 10 estaciones", "KGE presa"], fil, anchos=[3.6, 3.2, 2.4, 3.2, 2.4], size=9.5, resaltar=0)
par(f"Tres resultados responden a la pregunta del numeral. Primero, los productos con estaciones son claramente mejores que los "
    f"reanálisis: con el Cubo o con CHIRPS v2.0 el KGE medio de validación está entre {n(kmed(REG, 'CHIRPS v2.0', 'Hargreaves'), 2)} y "
    f"{n(kv, 2)}, con ERA5 corregido baja a {n(kmed('abcd semidistribuido', 'ERA5 QM', 'Penman-Monteith'), 2)} y con ERA5 sin corregir es "
    f"negativo. Segundo, la ETo pesa poco: cambiar Penman-Monteith por Hargreaves mueve el KGE medio menos de 0.02, como se espera en una "
    f"cuenca húmeda donde la ETR está limitada por la energía y no por el agua. Tercero, la memoria es indispensable. La ecuación empírica "
    f"solo usa la lluvia del mes y llega a un KGE de {n(kpre('empírico Q = α·W + β', 'Cubo IDEAM', 'Penman-Monteith'), 2)} en la presa; con "
    f"el caudal del mes anterior sube a {n(kpre('empírico con memoria Q = α·W + γ·Q(t−1) + β', 'Cubo IDEAM', 'Penman-Monteith'), 2)}, cerca "
    f"del abcd, porque Q(t−1) le entrega la memoria que el abcd representa con el suelo y el acuífero. La diferencia es que el abcd no "
    f"necesita conocer el caudal observado para simular, así que puede correrse con pronósticos o escenarios de lluvia.")
par(f"El modelo agregado, con una sola unidad hasta la presa, alcanza en ella un KGE de {n(kpre('abcd agregado', 'Cubo IDEAM', 'Penman-Monteith'), 2)}, "
    "similar al distribuido. La ventaja de la versión distribuida no está en la presa sino en que entrega caudales en las diez estaciones "
    "y la humedad del suelo en cada celda, que se usan en los numerales 3 y 4.")
par(f"**¿Qué combinación es más adecuada para un sistema operativo?** El modelo abcd distribuido, con calibración multisitio regionalizada "
    f"y ETo de Hargreaves. Para calibrar y reconstruir el pasado, la mejor lluvia es la del Cubo corregido. Para operar, sin embargo, el "
    f"Cubo tiene una limitación: es un producto de reanálisis de estaciones que hoy llega hasta 2023 y no se actualiza en tiempo real. "
    f"CHIRPS v2.0 se publica con pocas semanas de rezago y con él el modelo pierde poco (KGE medio de validación de "
    f"{n(kmed(REG, 'CHIRPS v2.0', 'Penman-Monteith'), 2)}), así que es la lluvia adecuada para correr el sistema mes a mes. Los "
    f"reanálisis, aun corregidos, no deben usarse para este fin.")

# ============================================================================================ numeral 2
titulo("2. Impactos del ENSO sobre la precipitación")
par("Para cada celda, producto y trimestre (DEF, MAM, JJA y SON) se calculó la anomalía estandarizada de la lluvia trimestral:")
ecuacion("z = (P~trimestre~ − media) / desviación estándar")
par(f"con la media y la desviación estándar de 1981-2010. Cada trimestre de 1981-2023 se clasificó como El Niño, La Niña o neutro con el "
    f"Índice Oceánico El Niño (ONI) de la NOAA y la regla del Centro de Predicción Climática (CPC): El Niño cuando el ONI es mayor o igual "
    f"a +0.5 °C durante al menos cinco trimestres móviles seguidos, y La Niña cuando es menor o igual a −0.5 °C en las mismas condiciones. "
    f"El compuesto de cada fase es el promedio de z en sus trimestres (Figuras 7 y 8). Además se calculó la correlación de Pearson entre "
    f"el ONI y el z medio de la cuenca para cada trimestre (Tabla 6).")
figura(EP / "mapas_compuesto_nino.png", ancho=Cm(13), texto="Anomalía estandarizada media de la precipitación en los trimestres El Niño, por producto (filas) y "
       "trimestre (columnas), 1981-2023. Rojo: más seco que lo normal; azul: más húmedo. z̄ es el promedio de la cuenca.")
figura(EP / "mapas_compuesto_nina.png", ancho=Cm(13), texto="Anomalía estandarizada media de la precipitación en los trimestres La Niña, por producto y trimestre, "
       "1981-2023.")
par(f"**Respuesta estacional.** Con el Cubo, El Niño reduce la lluvia de la cuenca sobre todo en DEF (z = {n(zc('Cubo IDEAM', 'DEF', 'El Niño'), 2)}) "
    f"y JJA ({n(zc('Cubo IDEAM', 'JJA', 'El Niño'), 2)}), menos en SON ({n(zc('Cubo IDEAM', 'SON', 'El Niño'), 2)}) y muy poco en MAM "
    f"({n(zc('Cubo IDEAM', 'MAM', 'El Niño'), 2)}). La relación lineal con el ONI sigue el mismo orden: r = {n(ro('Cubo IDEAM', 'DEF'), 2)} "
    f"en DEF, {n(ro('Cubo IDEAM', 'JJA'), 2)} en JJA, {n(ro('Cubo IDEAM', 'SON'), 2)} en SON y {n(ro('Cubo IDEAM', 'MAM'), 2)} en MAM. "
    f"La Niña produce la imagen opuesta, con su mayor anomalía en JJA (z = {n(zc('Cubo IDEAM', 'JJA', 'La Niña'), 2, True)}). Este "
    f"comportamiento coincide con lo descrito para los Andes colombianos por Poveda et al. (2001, 2011): la señal del ENSO es más fuerte en "
    f"diciembre-febrero, cuando el evento está en su madurez, y se debilita en marzo-mayo, cuando muchos eventos ya están terminando. Que "
    f"DEF y JJA coincidan con los estiajes del ciclo bimodal es importante para la generación: El Niño hace más secos los meses que ya "
    f"son secos.")
par("**Diferencias espaciales.** En DEF, JJA y SON de El Niño más del 96 % del área tiene anomalías negativas con el Cubo, de modo que la "
    "señal cubre toda la cuenca. En MAM la respuesta es más débil y desigual: el 78 % del área es más seca de lo normal, sobre todo el "
    "valle y el cañón, mientras que partes de la cabecera no muestran señal. En La Niña las anomalías positivas más fuertes aparecen en el "
    "alto Cauca y en el cañón antioqueño en JJA.")
leyenda_tabla("Correlación entre el ONI y la anomalía estandarizada de la lluvia de la cuenca por trimestre (1981-2023, n = 43).")
tabla(["Producto"] + TR, [[p_.replace(" QM", " corregido")] + [n(ro(p_, t), 2) for t in TR]
                          for p_ in ["Cubo IDEAM", "CHIRPS v2.0", "CHIRPS v3.0", "ERA5-Land", "ERA5", "ERA5 QM"]], anchos=[3.6, 2.2, 2.2, 2.2, 2.2])
figura(FG / "fig_enso_P_productos.png", "Anomalía estandarizada media de la lluvia de la cuenca en los trimestres El Niño y La Niña, por producto.")
leyenda_tabla("Correlación espacial entre el compuesto de cada producto y el del Cubo de datos.")
fil = [[p_.replace(" QM", " corregido")] + [n(rcons(p_, t, fa), 2) for fa in ["El Niño", "La Niña"] for t in TR]
       for p_ in ["CHIRPS v2.0", "CHIRPS v3.0", "ERA5-Land", "ERA5", "ERA5 QM"]]
tabla(["Producto"] + [f"{fa[3:] if fa.startswith('El') else fa[3:]} {t}" for fa in ["El Niño", "La Niña"] for t in TR], fil,
      anchos=[2.9] + [1.6] * 8, size=9)
par(f"**Consistencia entre productos.** En el promedio de la cuenca todos los productos coinciden en el signo y en el orden de magnitud de "
    f"la anomalía de DEF y JJA (Figura 9). En DEF de El Niño z va de {n(min(zc(p_, 'DEF', 'El Niño') for p_ in PRODS5), 2)} a "
    f"{n(max(zc(p_, 'DEF', 'El Niño') for p_ in PRODS5), 2)} según el producto. Las diferencias aparecen en dos lugares. En MAM ERA5 y "
    f"ERA5-Land dan anomalías positivas (z ≈ +0.1) en El Niño, contrarias a las de los productos con estaciones; en SON exageran la "
    f"sequía (z de {n(zc('ERA5-Land', 'SON', 'El Niño'), 2)} en ERA5-Land frente a {n(zc('Cubo IDEAM', 'SON', 'El Niño'), 2)} en el Cubo). "
    f"Y en el espacio, solo CHIRPS se parece al Cubo, con correlaciones espaciales de {n(min(rcons(p_, t, fa) for p_ in ['CHIRPS v2.0'] for t in TR for fa in ['El Niño', 'La Niña']), 2)} "
    f"a {n(max(rcons(p_, t, fa) for p_ in ['CHIRPS v2.0'] for t in TR for fa in ['El Niño', 'La Niña']), 2)} (Tabla 7). Los reanálisis tienen "
    f"correlaciones cercanas a cero o negativas, y la corrección por mapeo de cuantiles no las mejora, porque corrige la distribución de "
    f"cada celda pero no la forma en que el reanálisis reparte la anomalía en el espacio. Se concluye que todos los productos representan "
    f"de forma consistente la señal del ENSO en el promedio de la cuenca y en los trimestres de mayor impacto, pero solo los productos con "
    f"estaciones (Cubo y CHIRPS) la representan de forma consistente en el espacio y en MAM.")

# ============================================================================================ numeral 3
titulo("3. Impactos de El Niño sobre la humedad del suelo")
par("Se usó el almacenamiento de agua en el suelo S del modelo final, mes a mes y en cada celda. Para cada trimestre se calculó la "
    "anomalía estandarizada de S con la media y la desviación estándar de 1981-2010, igual que para la lluvia, y se promedió en los "
    "trimestres de cada fase (Figura 10). La Figura 11 compara la anomalía del suelo con la de la lluvia del Cubo calculada de la misma "
    "forma, y la Tabla 8 resume los valores de la cuenca.")
figura(ES / "mapas_suelo_enso.png", "Anomalía estandarizada media de la humedad del suelo simulada (S del modelo abcd) en los trimestres El "
       "Niño (arriba) y La Niña (abajo), 1981-2023. Rojo: más seco que lo normal; azul: más húmedo.")
leyenda_tabla("Anomalía estandarizada media de la humedad del suelo y de la lluvia de la cuenca en los trimestres El Niño y La Niña.")
fil = []
for t in TR:
    a, b = ts.loc[("El Niño", t)], ts.loc[("La Niña", t)]
    fil.append([t, n(a["z P cuenca"], 2), n(a["z S cuenca"], 2), n(a["% área con S por debajo de lo normal"]), n(b["z P cuenca"], 2, True),
                n(b["z S cuenca"], 2, True)])
tabla(["Trimestre", "z lluvia El Niño", "z suelo El Niño", "Área con suelo más seco que lo normal, El Niño (%)", "z lluvia La Niña",
       "z suelo La Niña"], fil, anchos=[2.0, 2.3, 2.3, 4.0, 2.3, 2.3])
figura(FG / "fig_suelo_lluvia_enso.png", "Anomalía estandarizada de la humedad del suelo frente a la de la lluvia de la cuenca, por trimestre, en "
       "El Niño y La Niña.", ancho=Cm(13))
sD, sM = ts.loc[("El Niño", "DEF")], ts.loc[("El Niño", "MAM")]
par(f"**¿Qué ocurre con la humedad del suelo durante El Niño?** El suelo se seca en toda la cuenca y en los cuatro trimestres. En cada "
    f"trimestre de El Niño más del 99 % del área queda con el suelo por debajo de lo normal, y la anomalía media va de "
    f"{n(ts.xs('El Niño').loc[TR, 'z S cuenca'].max(), 2)} a {n(ts.xs('El Niño').loc[TR, 'z S cuenca'].min(), 2)} desviaciones estándar.")
par(f"**Magnitud.** La anomalía del suelo es mayor que la de la lluvia en todos los trimestres. En DEF la lluvia tiene z = {n(sD['z P cuenca'], 2)} "
    f"y el suelo {n(sD['z S cuenca'], 2)}. El suelo amplifica la señal porque acumula: su contenido de cada mes depende de la lluvia y de la "
    f"evapotranspiración de los meses anteriores, de modo que varios meses moderadamente secos seguidos producen un déficit mayor que el de "
    f"cualquiera de ellos.")
par(f"**Persistencia.** La diferencia más clara está en MAM. La lluvia de MAM casi no responde a El Niño (z = {n(sM['z P cuenca'], 2)}), pero "
    f"el suelo sigue en {n(sM['z S cuenca'], 2)}, tan seco como en DEF: arrastra el déficit de diciembre-febrero hasta abril o mayo. La "
    f"autocorrelación de un mes de las anomalías del suelo de la cuenca es de {n(rz.loc['S', 'memoria r1'], 2)}, frente a "
    f"{n(rz.loc['P', 'memoria r1'], 2)} de la lluvia, y su correlación con el ONI es máxima con {int(np.argmin([rz.loc['S', f'ONI → S rezago {k}'] for k in range(7)]))} "
    f"meses de rezago (r = {n(min(rz.loc['S', f'ONI → S rezago {k}'] for k in range(7)), 2)}).")
par(f"**Distribución espacial.** La Figura 12 muestra que la memoria del suelo no es igual en toda la cuenca. La autocorrelación de un mes "
    f"va de {n(mem.memoria_r1.min(), 2)} a {n(mem.memoria_r1.max(), 2)} entre celdas. Es mayor en la cabecera y en las celdas de alta montaña, "
    f"donde el parámetro b de su unidad es grande y el suelo tarda más en vaciarse, y menor en el valle medio (La Virginia e Irra), donde "
    f"b es pequeño y el suelo responde casi solo a la lluvia del mes. En casi todas las celdas la respuesta del suelo a la lluvia es "
    f"inmediata (rezago de cero meses); lo que cambia de un sitio a otro es cuánto dura la anomalía.")
figura(ES / "mapas_memoria_suelo.png", "Memoria de la humedad del suelo simulada: autocorrelación de un mes de sus anomalías (izquierda) y "
       "rezago, en meses, de la máxima correlación con la lluvia (derecha).", ancho=Cm(11))
par("Estos resultados coinciden con los de Poveda et al. (2001), que encontraron en Colombia anomalías negativas de la humedad del suelo "
    "durante El Niño, con una respuesta más lenta que la de la lluvia. Para la generación, la consecuencia es que el final de un evento El "
    "Niño no significa el final de la sequía hidrológica: el suelo seco absorbe la lluvia de los primeros meses de la temporada húmeda "
    "antes de que el río vuelva a crecer.")

# ============================================================================================ numeral 4
titulo("4. Impactos de El Niño sobre los caudales")
par("Se calcularon las anomalías estandarizadas trimestrales de los caudales observados y simulados en las diez estaciones, con el mismo "
    "procedimiento de la lluvia y del suelo. En la presa se usaron los años 1981-2017. La Figura 13 y la Tabla 9 muestran los resultados "
    "en tres estaciones representativas: La Virginia, al final del valle; Bolombolo, en el cañón, y la presa.")
figura(FG / "fig_caudales_enso.png", "Anomalía estandarizada media del caudal en los trimestres El Niño y La Niña: observada (barras) y "
       "simulada por el modelo abcd (puntos).")
leyenda_tabla("Anomalía estandarizada media del caudal observado y simulado en los trimestres El Niño y La Niña.")
fil = []
for e in ["La Virginia", "Bolombolo", "Presa"]:
    for fa in ["El Niño", "La Niña"]:
        fil.append([e, fa] + [f"{n(zq(e, t, fa, 'z Q observado'), 2, True)} / {n(zq(e, t, fa, 'z Q simulado'), 2, True)}" for t in TR])
tabla(["Estación", "Fase", "DEF (obs. / sim.)", "MAM (obs. / sim.)", "JJA (obs. / sim.)", "SON (obs. / sim.)"], fil,
      anchos=[2.6, 1.9, 2.85, 2.85, 2.85, 2.85], size=9.5)
par(f"**Periodos de mayor reducción e incremento.** En El Niño los caudales bajan en todos los trimestres y en todas las estaciones. La "
    f"mayor reducción en la presa ocurre en DEF (z = {n(zq('Presa', 'DEF', 'El Niño', 'z Q observado'), 2)}) y continúa en MAM "
    f"({n(zq('Presa', 'MAM', 'El Niño', 'z Q observado'), 2)}), aunque la lluvia de MAM casi no cambie: es el efecto del suelo seco y del "
    f"acuífero vacío descrito en el numeral 3. En La Niña los mayores incrementos ocurren en MAM en las tres estaciones (z de "
    f"{n(zq('Presa', 'MAM', 'La Niña', 'z Q observado'), 2, True)} a {n(zq('La Virginia', 'MAM', 'La Niña', 'z Q observado'), 2, True)}), "
    f"también un trimestre después del máximo de la lluvia. La señal crece hacia aguas abajo: en DEF de El Niño pasa de "
    f"{n(zq('La Virginia', 'DEF', 'El Niño', 'z Q observado'), 2)} en La Virginia a {n(zq('Presa', 'DEF', 'El Niño', 'z Q observado'), 2)} en la presa, "
    f"porque se suman los aportes del cañón antioqueño, donde la lluvia de El Niño en DEF es más deficitaria.")
par(f"**¿Reproduce el modelo la respuesta al ENSO?** El modelo acierta el signo en todas las combinaciones de estación, fase y trimestre, y "
    f"en La Virginia y Bolombolo también la magnitud (diferencias menores de 0.2 desviaciones estándar en la mayoría de los casos). Su "
    f"mayor error está en la presa en DEF de El Niño, donde simula {n(zq('Presa', 'DEF', 'El Niño', 'z Q simulado'), 2)} frente a "
    f"{n(zq('Presa', 'DEF', 'El Niño', 'z Q observado'), 2)} observado. Una posible causa es que la lluvia del Cubo en el cañón, con pocas "
    f"estaciones de alta montaña, no capta toda la sequía de esos eventos.")
par("El ciclo anual por fase confirma esta evaluación (Figura 14). El Niño no cambia la forma bimodal del ciclo; lo desplaza hacia abajo. En "
    f"la presa, el caudal observado en los meses El Niño es entre {n(-red_obs.max())} % y {n(-red_obs.min())} % menor que en los meses "
    f"neutros, con la mayor reducción en {MESN[int(red_obs.idxmin()) - 1]} ({n(red_obs.min())} %), en plena temporada seca de comienzo de "
    f"año. El simulado reproduce ese patrón, con reducciones entre {n(-red_sim.max())} % y {n(-red_sim.min())} % y el máximo en "
    f"{MESN[int(red_sim.idxmin()) - 1]} ({n(red_sim.min())} %). La Niña aumenta el caudal sobre todo en noviembre-marzo (hasta "
    f"{n(aum_obs.max(), 0, True)} %), y el modelo también lo reproduce. Como el modelo sigue el ciclo de cada fase, puede usarse para estimar "
    f"cómo se verán los meses de un evento ENSO a partir de su lluvia.")
figura(FG / "fig_ciclo_fases.png", "Ciclo anual del caudal en los meses El Niño, neutros y La Niña (fase según el ONI del trimestre centrado "
       "en cada mes), observado (líneas continuas) y simulado (punteadas).")

titulo("Relación entre lluvia, humedad del suelo y caudales", 2)
par("Para cuantificar el almacenamiento y la memoria se calcularon, con las anomalías mensuales de la cuenca, las correlaciones del ONI con "
    "la lluvia, el suelo, el acuífero y el caudal con rezagos de 0 a 6 meses, y las de la lluvia con las demás variables (Figura 15).")
figura(FG / "fig_rezagos.png", "Correlación de las anomalías mensuales de la cuenca: a) del ONI con la lluvia, el suelo, el acuífero y el "
       "caudal en la presa según el rezago; b) de la lluvia con el suelo, el acuífero y el caudal.")
rQ = [rz.loc["Q obs presa", f"ONI → Q obs presa rezago {k}"] for k in range(7)]
par(f"La correlación del ONI con la lluvia es de {n(rz.loc['P', 'ONI → P rezago 0'], 2)} en el mismo mes y decae lentamente. Con el suelo, "
    f"el acuífero y el caudal la correlación es más fuerte y alcanza su máximo con dos meses de rezago: "
    f"{n(min(rz.loc['S', f'ONI → S rezago {k}'] for k in range(7)), 2)} para el suelo, "
    f"{n(min(rz.loc['G', f'ONI → G rezago {k}'] for k in range(7)), 2)} para el acuífero y {n(min(rQ), 2)} para el caudal observado en la "
    f"presa. Una anomalía de lluvia sigue correlacionada con el caudal dos meses después ({n(rp.loc['P → Q obs', 'rezago 2 meses'], 2)}). La "
    f"autocorrelación de un mes es de {n(rz.loc['P', 'memoria r1'], 2)} para la lluvia, {n(rz.loc['S', 'memoria r1'], 2)} para el suelo, "
    f"{n(rz.loc['G', 'memoria r1'], 2)} para el acuífero y {n(rz.loc['Q obs presa', 'memoria r1'], 2)} para el caudal observado.")
par("La interpretación física es la de una cuenca que funciona como un filtro. La lluvia mensual tiene poca memoria y mucho ruido de un mes "
    "a otro. El suelo y el acuífero la integran: almacenan los excesos y se van vaciando en los meses secos, así que sus anomalías duran "
    "más y siguen a la componente lenta de la lluvia, que es la que impone el ENSO. Por eso los caudales responden al ENSO con más fuerza "
    "que la lluvia que los produce, como ya se había visto en el Trabajo 1 con una variabilidad interanual 2.6 veces mayor, y con unos "
    "dos meses de retraso. Ese rezago tiene valor práctico: el estado del ENSO y la humedad del suelo de hoy contienen información sobre los "
    "caudales de los próximos meses, que es lo que se aprovecha en la sección 5.")
titulo("Patrón espacial dominante: funciones ortogonales empíricas", 2)
e1, eS = eofr.loc["Cubo IDEAM"], eofr.loc["Suelo S (abcd)"]
par("Para comprobar si el ENSO es la fuente principal de variabilidad de la cuenca sin suponerlo de antemano, se calcularon funciones "
    "ortogonales empíricas (EOF) de las anomalías de lluvia de cada producto y de la humedad del suelo. Se usaron las anomalías "
    "trimestrales móviles de cada celda (1981-2023), estandarizadas por mes calendario y ponderadas por la raíz del área, y se "
    "descompusieron en valores singulares. Cada modo tiene un patrón espacial (mapa de correlación entre su componente principal y cada "
    "celda) y una serie de tiempo, su componente principal (CP), que se correlacionó con el ONI. La separación entre modos se verificó con "
    "la regla de North et al. (1982).")
figura(FG / "fig_eof_mapas.png", ancho=Cm(14.5), texto="Dos primeros modos (EOF) de las anomalías trimestrales de la lluvia de cada producto y de la humedad del "
       "suelo simulada. Los mapas son la correlación de la componente principal con cada celda; el título indica la varianza explicada y la "
       "correlación de la componente con el ONI.")
par(f"El primer modo tiene el mismo signo en toda la cuenca y explica el {n(e1['varianza EOF1 (%)'])} % de la varianza de la lluvia del Cubo "
    f"y el {n(eS['varianza EOF1 (%)'])} % de la del suelo. Su componente principal se correlaciona con el ONI: "
    f"{n(e1['r(CP1, ONI) máxima'], 2)} para la lluvia y {n(eS['r(CP1, ONI) máxima'], 2)} para el suelo, con un mes de rezago. Es decir, la "
    f"forma más común en que varía la cuenca es que toda ella se seque o se humedezca a la vez, y eso ocurre al ritmo del ENSO. El segundo "
    f"modo del Cubo explica solo el {n(e1['varianza EOF2 (%)'])} % y no se separa del tercero según la regla de North, de modo que no hay un "
    f"segundo patrón robusto. En ERA5 y ERA5-Land corregidos, en cambio, el segundo modo explica entre el "
    f"{n(eofr.loc['ERA5-Land QM', 'varianza EOF2 (%)'])} % y el {n(eofr.loc['ERA5 QM', 'varianza EOF2 (%)'])} % con manchas aisladas que "
    f"ningún producto con estaciones muestra, y su componente se mueve en sentido contrario a la del Cubo "
    f"(r = {n(eofr.loc['ERA5 QM', 'r temporal CP2 con el Cubo'], 2)}). Esto confirma, por otra vía, la conclusión del numeral 2 sobre la "
    f"consistencia espacial de los reanálisis. Que un solo modo ligado al ENSO domine la lluvia y el suelo explica también por qué los "
    f"caudales de las diez estaciones responden al mismo tiempo y con el mismo signo.")

# ============================================================================================ numeral 5
titulo("5. Aplicación de técnicas de análisis de datos")
par("Se aplicaron tres técnicas vistas en el curso, elegidas por su utilidad para la operación de una central hidroeléctrica: el mapeo de "
    "cuantiles, para corregir la información climática que entra al modelo; los K vecinos más cercanos (KNN), para pronosticar los "
    "aportes de los próximos meses, y la regresión logística, para estimar la probabilidad de un trimestre seco y definir umbrales de "
    "alerta. Las dos últimas aprovechan la memoria descrita en el numeral 4. Para ellas el pronóstico se emite al final de cada mes t con "
    "la información disponible en ese momento: el ONI del trimestre que termina en t (el trimestre centrado en t todavía no se conoce), su "
    "cambio en los últimos tres meses y el almacenamiento de agua en el suelo (S) y en el acuífero (G) de la cuenca que simula el modelo "
    "abcd. Todas las variables se estandarizaron por mes calendario. El objetivo es el aporte en la presa observado entre 1982 y 2017.")
par("Ambas técnicas se evaluaron con validación cruzada dejando un año fuera: para pronosticar los meses de un año, ese año y los seis "
    "meses anteriores y posteriores se excluyeron de todo el ajuste, de modo que ningún pronóstico usa información de su propio periodo.")

titulo("5.1. Mapeo de cuantiles (quantile mapping)", 2)
par("**Objetivo.** Corregir el sesgo de la lluvia de ERA5 y ERA5-Land para saber si, una vez corregidos, pueden reemplazar a los productos "
    "con estaciones en el modelo. La pregunta es práctica: los reanálisis tienen cobertura global y continua, y si funcionaran servirían "
    "en cuencas sin estaciones.")
par("**Variables.** Lluvia mensual de ERA5 y ERA5-Land en las 376 celdas de la cuenca (1981-2023), con la lluvia mensual del Cubo corregido "
    "en las mismas celdas como referencia.")
par("**Método.** Para cada celda y cada mes calendario se construyeron las funciones de distribución empíricas del reanálisis (F~rea~) y del "
    "Cubo (F~obs~) con los datos de 1981-2010 (Gudmundsson et al., 2012). Cada valor x del reanálisis se reemplaza por el valor del Cubo "
    "que tiene la misma probabilidad de no excedencia:")
ecuacion("x~corregido~ = F~obs~^−1^ [ F~rea~ (x) ]")
par("Se usaron los cuantiles 1 a 99; fuera de ese rango se aplicó la razón entre los extremos. La corrección se ajustó en 1981-2010 y se "
    "aplicó a 1981-2023, de modo que 2011-2023 sirve como verificación independiente.")
par(f"**Resultados.** En 1981-2010 la corrección elimina el sesgo de +176 % y deja el ciclo anual y la lluvia media de cada celda iguales "
    f"a los del Cubo (Figuras 3b y 4). En 2011-2023, sin reajustar, ERA5 corregido conserva un sesgo de "
    f"{n(m11.loc['ERA5 QM', 'sesgo (%)'], 1, True)} % y un KGE de {n(m11.loc['ERA5 QM', 'KGE'], 2)}, y ERA5-Land un sesgo de "
    f"{n(m11.loc['ERA5-Land QM', 'sesgo (%)'], 1, True)} % y un KGE de {n(m11.loc['ERA5-Land QM', 'KGE'], 2)} (Tabla 2). Lo que no "
    f"mejora es la secuencia de los meses: la correlación de las anomalías con el Cubo es de "
    f"{n(m81.loc['ERA5 QM', 'r anomalías mensuales'], 2)}, frente a {n(m81.loc['CHIRPS v2.0', 'r anomalías mensuales'], 2)} de CHIRPS. En "
    f"el modelo abcd, ERA5 corregido pasa de un KGE medio de validación negativo ({n(kmed('abcd semidistribuido', 'ERA5', 'Penman-Monteith'), 2)}) "
    f"a {n(kmed('abcd semidistribuido', 'ERA5 QM', 'Penman-Monteith'), 2)}, todavía lejos de los "
    f"{n(kmed('abcd semidistribuido', 'Cubo IDEAM', 'Penman-Monteith'), 2)} que da el Cubo con la misma configuración (Tabla 5). Tampoco "
    f"corrige el patrón espacial de la respuesta al ENSO (Tabla 7).")
par("**Interpretación física e hidrológica.** El mapeo de cuantiles corrige la distribución de valores de cada celda, pero conserva el orden "
    "en que el reanálisis los produce. Los errores de ERA5 en esta cuenca no son solo de magnitud: su lluvia proviene de pronósticos de "
    "corto plazo del modelo atmosférico, sin asimilación de pluviómetros, y su resolución no resuelve dos cordilleras y un valle "
    "interandino. Por eso falla en cuándo y dónde llueve más o menos de lo normal, y eso es justamente lo que el modelo hidrológico "
    "necesita para reproducir la secuencia de caudales y la respuesta al ENSO.")
par("**Valor agregado.** La técnica permitió separar dos tipos de error: el sesgo, que se puede corregir, y la falta de información sobre la "
    "variabilidad, que no. Con ello se descartó el uso de los reanálisis en un sistema operativo de la cuenca y se justificó la elección de "
    "productos con estaciones. La misma técnica, en su versión que conserva los cambios proyectados por cuantil, se usará para corregir los "
    "modelos climáticos CMIP6 en la siguiente entrega (Cannon et al., 2015).")

titulo("5.2. K vecinos más cercanos (KNN): pronóstico estacional con años análogos", 2)
par("**Objetivo.** Pronosticar el aporte mensual a Hidroituango con uno a seis meses de anticipación y expresar ese pronóstico como un "
    "rango de valores posibles con una confiabilidad conocida. Es el tipo de información que necesita el operador para decidir cuánta agua "
    "guardar en el embalse antes de una temporada seca.")
par("**Variables.** Los predictores son el ONI del trimestre recién terminado, su cambio en tres meses y el almacenamiento S y G de la "
    "cuenca al final del mes. El objetivo es el caudal observado en la presa en los seis meses siguientes y su promedio en los tres "
    "siguientes.")
par(f"**Método.** El KNN aplicado como método de análogos (Lall y Sharma, 1996) busca en la historia los meses cuyo estado se parece más al "
    f"de hoy y usa lo que ocurrió después de ellos como pronóstico. Se tomaron los k meses más cercanos en distancia euclidiana entre los "
    f"cuatro predictores estandarizados, buscados en el mismo mes calendario ± 1 para respetar la estacionalidad. Lo que siguió a cada "
    f"análogo se expresó como anomalía estandarizada del logaritmo del caudal y se llevó a la climatología del mes pronosticado. Así se "
    f"obtienen k trayectorias posibles; de ellas salen la mediana, el intervalo del 80 % (percentiles 10 y 90) y la probabilidad de cualquier "
    f"evento. El número de vecinos (k = {K}) se eligió con el CRPS (Hersbach, 2000), que mide el error de toda la distribución "
    f"pronosticada. Las referencias fueron la climatología, que da para cada mes la distribución histórica sin información adicional, y la "
    f"persistencia, que supone que la anomalía actual del caudal se mantiene.")
leyenda_tabla("Pronóstico del aporte medio de los tres meses siguientes en la presa (validación cruzada 1982-2017).")
tabla(["Método", "NSE de la mediana", "CRPS (m³/s)", "CRPSS", "Cobertura del intervalo del 80 % (%)", "Ancho medio del intervalo (m³/s)"],
      [["Climatología", n(mq3.loc["Climatología", "NSE de la mediana"], 2), n(mq3.loc["Climatología", "CRPS (m³/s)"]), "0",
        n(mq3.loc["Climatología", "Cobertura del intervalo 80 % (%)"]), n(mq3.loc["Climatología", "Ancho medio del intervalo 80 % (m³/s)"])],
       ["Persistencia", n(mq3.loc["Persistencia", "NSE de la mediana"], 2), "—", "—", "—", "—"],
       [f"KNN (k = {K})", n(mq3.loc[KQ, "NSE de la mediana"], 2), n(mq3.loc[KQ, "CRPS (m³/s)"]), n(mq3.loc[KQ, "CRPSS"], 2),
        n(mq3.loc[KQ, "Cobertura del intervalo 80 % (%)"]), n(mq3.loc[KQ, "Ancho medio del intervalo 80 % (m³/s)"])]],
      anchos=[2.8, 2.3, 2.1, 1.7, 3.5, 3.5], resaltar=2)
figura(FG / "fig_knn_horizonte.png", "Habilidad del pronóstico de años análogos según la anticipación: a) NSE de la mediana frente a la "
       "persistencia y la climatología; b) mejora del CRPS frente a la climatología (CRPSS) y cobertura del intervalo del 80 %.")
par(f"**Resultados.** Para el aporte de los tres meses siguientes, la mediana de los análogos tiene un NSE de {n(mq3.loc[KQ, 'NSE de la mediana'], 2)}, "
    f"frente a {n(mq3.loc['Persistencia', 'NSE de la mediana'], 2)} de la persistencia y {n(mq3.loc['Climatología', 'NSE de la mediana'], 2)} "
    f"de la climatología, y su CRPS es un {n(100 * mq3.loc[KQ, 'CRPSS'])} % menor que el de la climatología (Tabla 10). Mes a mes, con un mes "
    f"de anticipación el KNN empata con la persistencia (NSE de {n(hzm.loc[1, 'NSE KNN'], 2)} y {n(hzm.loc[1, 'NSE persistencia'], 2)}), pero "
    f"a partir del segundo mes la supera y a seis meses conserva un NSE de {n(hzm.loc[6, 'NSE KNN'], 2)}, cuando el de la persistencia ya "
    f"cayó a {n(hzm.loc[6, 'NSE persistencia'], 2)} (Figura 17). El intervalo nominal del 80 % contuvo al caudal observado el "
    f"{n(mq3.loc[KQ, 'Cobertura del intervalo 80 % (%)'])} % de las veces y es un "
    f"{n(100 * (1 - mq3.loc[KQ, 'Ancho medio del intervalo 80 % (m³/s)'] / mq3.loc['Climatología', 'Ancho medio del intervalo 80 % (m³/s)']))} % "
    f"más angosto que el de la climatología. Los análogos son, por tanto, algo optimistas sobre su propia precisión, y en la práctica ese "
    f"intervalo debe leerse como uno de cerca del 67 %.")
figura(FG / "fig_knn_ejemplos.png", "Pronósticos de años análogos emitidos al final de agosto de 1997 y de 2015 (inicio de los dos El Niño "
       "más intensos del periodo) y de 2010 (La Niña), frente a la climatología y al caudal observado.")
e97, e15, e10 = (prs["ejemplos"][k_] for k_ in ["1997-08", "2015-08", "2010-08"])
par(f"La Figura 18 muestra tres casos. En agosto de 1997, con el ONI en +1.5 °C y el suelo ya seco (z = {n(e97['S'], 2)}), los análogos "
    f"pronosticaron caudales por debajo de la climatología para todo el semestre siguiente, y el observado quedó dentro del intervalo. En "
    f"agosto de 2015 el pronóstico también fue de caudales bajos, pero el observado quedó por debajo incluso del percentil 10: la sequía de "
    f"2015-2016 fue más severa que la de cualquiera de los años de entrenamiento, y un método de análogos no puede pronosticar algo que no "
    f"tiene en su historia. En agosto de 2010, con La Niña y el suelo húmedo (z = {n(e10['S'], 2, True)}), el pronóstico se ubicó por encima "
    f"de la climatología, aunque se quedó corto ante la creciente extrema de noviembre de 2010.")
par("**Interpretación física e hidrológica.** La habilidad a varios meses no viene de pronosticar la lluvia, sino de la memoria de la "
    "cuenca. El suelo y el acuífero de hoy determinan buena parte del caudal de los próximos meses, y el ONI anticipa si los meses que "
    "vienen serán secos o húmedos, porque los eventos ENSO duran de nueve meses a dos años. A un mes la persistencia ya contiene esa "
    "información; a más meses el KNN la extrae mejor porque combina el estado del almacenamiento con el del Pacífico.")
par("**Valor agregado.** El KNN convierte la relación entre ENSO, suelo y caudal de los numerales 3 y 4 en un pronóstico utilizable, con "
    "una medida verificada de su confiabilidad, y no requiere suponer ninguna forma para esa relación. En el Trabajo 1 el mismo método, "
    "aplicado a caudales diarios a 10 días, apenas igualaba a la persistencia (NSE de 0.43), porque a esa escala el caudal depende del "
    "tiempo atmosférico de los días siguientes; a escala mensual y con el estado del suelo como predictor, en cambio, sí aporta información.")

titulo("5.3. Regresión logística: probabilidad de un trimestre seco y umbrales de alerta", 2)
par("**Objetivo.** Estimar la probabilidad de que los tres meses siguientes sean secos para la generación y, con ella, definir niveles de "
    "alerta que puedan usarse para decidir. Se definió como trimestre seco aquel en que el aporte medio de los tres meses siguientes queda "
    "por debajo del percentil 20 de su distribución histórica para ese mes de emisión.")
par("**Variables.** La variable de respuesta es binaria (1 si el trimestre siguiente es seco, 0 si no). Se ajustaron dos modelos: uno con el "
    "ONI como único predictor y otro con el ONI y la humedad del suelo S de la cuenca.")
par("**Método.** La regresión logística (Hosmer et al., 2013) modela la probabilidad del evento como")
ecuacion("P(seco) = 1 / [1 + exp(−(β~0~ + β~1~ · ONI + β~2~ · S))]")
par("y sus coeficientes se ajustan por máxima verosimilitud. Como los predictores están estandarizados, exp(β) es el factor por el que se "
    "multiplican las probabilidades relativas (odds) del evento cuando el predictor aumenta una desviación estándar. Los modelos se "
    "evaluaron con la misma validación cruzada del KNN mediante el puntaje de Brier (Brier, 1950), su mejora frente a la climatología (BSS) "
    "y el área bajo la curva ROC (AUC), que mide la capacidad de separar los trimestres secos de los demás (Wilks, 2011). La climatología "
    "asigna siempre una probabilidad del 20 %. Además, la probabilidad del KNN (la fracción de análogos que terminaron en un trimestre seco) "
    "se comparó con la de la regresión logística.")
leyenda_tabla("Coeficientes de la regresión logística ajustada con todos los datos (1982-2017).")
fil = []
for _, r_ in cof.iterrows():
    fil.append([r_.modelo.replace("Logística · ", ""), r_.variable, n(r_["β"], 2, True), n(r_["error estándar"], 2), n(r_["z"], 1, True),
                "—" if pd.isna(r_["razón de odds por 1 σ"]) else n(r_["razón de odds por 1 σ"], 2)])
tabla(["Modelo", "Variable", "β", "Error estándar", "z", "exp(β) por 1 σ"], fil, anchos=[2.8, 2.4, 2.0, 2.4, 1.8, 2.6])
leyenda_tabla("Probabilidad de un trimestre seco: desempeño en la validación cruzada.")
tabla(["Método", "Brier", "BSS", "AUC"],
      [[i.replace("Logística · ", "Logística: ").replace("Climatología (20 %)", "Climatología (20 %)"), n(r_.Brier, 3), n(r_.BSS, 2), n(r_["AUC (ROC)"], 2)]
       for i, r_ in mpb.iterrows()], anchos=[5.0, 2.2, 2.2, 2.2], resaltar=3)
figura(FG / "fig_prob_trimestre_seco.png", "a) Probabilidad de un trimestre seco según el ONI, con el suelo seco, normal y húmedo; b) "
       "diagrama de confiabilidad y c) curvas ROC de la regresión logística y del KNN en la validación cruzada.")
par(f"**Resultados.** Con solo el ONI, cada desviación estándar adicional del índice multiplica los odds de un trimestre seco por "
    f"{n(orx(LO, 'ONI'), 1)}. Cuando se agrega el suelo, este domina: un suelo una desviación estándar más seco multiplica los odds por "
    f"{n(1 / orx(LS, 'S'), 1)}, y el efecto del ONI baja a {n(orx(LS, 'ONI'), 1)} (Tabla 11). El modelo con ONI y suelo mejora el puntaje "
    f"de Brier de la climatología en un {n(100 * mpb.loc[LS, 'BSS'])} % y tiene un AUC de {n(mpb.loc[LS, 'AUC (ROC)'], 2)}; con solo el ONI "
    f"la mejora es del {n(100 * mpb.loc[LO, 'BSS'])} % (Tabla 12). En el diagrama de confiabilidad sus probabilidades siguen de cerca la "
    f"frecuencia observada (Figura 19b).")
par(f"**Comparación con el KNN.** Las dos técnicas separan igual de bien los trimestres secos de los demás (AUC de "
    f"{n(mpb.loc[LS, 'AUC (ROC)'], 2)} y {n(mpb.loc[KQ, 'AUC (ROC)'], 2)}), pero la regresión logística está mejor calibrada (BSS de "
    f"{n(mpb.loc[LS, 'BSS'], 2)} frente a {n(mpb.loc[KQ, 'BSS'], 2)}). La diferencia está en cómo tratan los casos extremos. La probabilidad "
    f"del KNN es una fracción de {K} análogos, y cuando el estado de hoy es más extremo que casi todos los de la historia los análogos "
    f"incluyen meses menos secos y la probabilidad queda comprimida. En agosto de 1997 el KNN dio un {n(100 * e97['pknn'])} % y la logística "
    f"un {n(100 * e97['plog'])} %; el trimestre fue seco. La logística extrapola la tendencia de la curva y por eso responde mejor a los "
    f"eventos fuertes, mientras que el KNN no supone ninguna forma para la relación. Los dos métodos no son excluyentes: cuando coinciden, "
    f"la alerta es más confiable.")
leyenda_tabla("Niveles de alerta definidos con la probabilidad de un trimestre seco y su desempeño en la validación cruzada.")
fil = []
for niv, rango in [("Verde", "< 20 %"), ("Amarillo", "20-50 %"), ("Rojo", "≥ 50 %")]:
    fil.append([niv, rango] + [f"{n(al(m_, niv, PCT))} % / {n(al(m_, niv, FRQ))} %" for m_ in [LS, KQ, LO]])
tabla(["Nivel", "P(trimestre seco)", "Logística ONI + suelo", f"KNN (k = {K})", "Logística ONI"], fil, anchos=[1.8, 2.6, 3.8, 3.8, 3.8])
par("En cada celda: porcentaje de los meses en ese nivel / porcentaje de esos meses en que el trimestre siguiente fue seco.", size=None)
figura(FG / "fig_alertas_serie.png", "Probabilidad de un trimestre seco estimada por la regresión logística con ONI y suelo en la validación "
       "cruzada (puntos coloreados por nivel de alerta) y trimestres secos observados (barras).")
par(f"**Umbrales de alerta.** Con la regresión logística con ONI y suelo se definieron tres niveles (Tabla 13 y Figura 20). En verde "
    f"(probabilidad menor del 20 %) estuvo el {n(al(LS, 'Verde', PCT))} % de los meses, y solo el {n(al(LS, 'Verde', FRQ))} % de ellos "
    f"fue seguido por un trimestre seco. En amarillo (20-50 %) estuvo el {n(al(LS, 'Amarillo', PCT))} %, con un {n(al(LS, 'Amarillo', FRQ))} % "
    f"de trimestres secos. En rojo (50 % o más) estuvo el {n(al(LS, 'Rojo', PCT))} % de los meses, concentrados en los El Niño de "
    f"1991-1992, 1997-1998, 2009-2010 y 2015-2016, y el trimestre siguiente fue seco en el {n(al(LS, 'Rojo', FRQ))} % de los casos. Con el "
    f"KNN el rojo es más raro ({n(al(KQ, 'Rojo', PCT))} % de los meses) pero acierta el {n(al(KQ, 'Rojo', FRQ))} %.")
par("**Interpretación física e hidrológica.** Que el suelo pese más que el ONI tiene una explicación directa. El ONI describe el estado del "
    "Pacífico, que se traducirá en lluvia en los meses siguientes; la humedad del suelo ya contiene el efecto del ENSO de los meses "
    "anteriores, porque integra la lluvia y la evapotranspiración acumuladas (numeral 3). Cuando ambos indican sequía, el trimestre "
    "siguiente parte de un almacenamiento bajo y recibe además menos lluvia, y por eso la probabilidad crece rápidamente.")
par("**Valor agregado.** La regresión logística traduce la relación física entre ENSO, suelo y caudal en una regla de decisión simple y "
    "verificada: con dos números disponibles al final de cada mes se obtiene una probabilidad y un nivel de alerta. Para la operación de "
    "Hidroituango, una alerta roja indica que conviene conservar agua en el embalse y prever el respaldo térmico; una verde, que el riesgo "
    "de un trimestre seco es bajo. Además, el resultado muestra que un sistema operativo de pronóstico necesita la humedad del suelo, que "
    "no se mide en la cuenca pero que el modelo abcd sí estima.")

titulo("5.4. Aplicación: pronóstico emitido al final de octubre de 2026", 2)
P26 = R2 / "12_pronostico_2026"
s26 = json.loads((P26 / "resumen.json").read_text(encoding="utf-8"))
pr26 = pd.read_csv(P26 / "pronostico_nov2026_abr2027.csv")
an26 = pd.read_csv(P26 / "analogos.csv")
se = s26["sensibilidad octubre"]
par(f"Las dos técnicas se aplicaron al evento El Niño en curso, que en agosto-octubre de 2026 alcanzó un ONI de +{n(s26['ONI ASO 2026'], 2)} °C, "
    f"el mayor del registro. Para conocer el estado actual del suelo y del acuífero, el modelo abcd se extendió de enero de 2024 a octubre de "
    f"2026 con la lluvia de CHIRPS v2.0, igualada al Cubo con la razón entre ambos productos de cada celda y mes calendario en 1981-2010, y "
    f"con la ETo de Hargreaves climatológica, porque el Cubo termina en 2023. Entre julio y septiembre de 2026 la cuenca recibió el "
    f"{n(s26['lluvia jul-sep 2026 (% de lo normal)'])} % de su lluvia normal. CHIRPS de octubre aún no estaba publicado; su lluvia se ajustó "
    f"para que el caudal simulado de octubre tuviera la misma anomalía que los aportes diarios a Ituango publicados por XM del 1 al 23 de "
    f"octubre ({n(s26['anomalía XM octubre (%)'])} %), y resultó del {n(s26['lluvia octubre (% de la normal)'])} % de la normal. Entre octubre "
    f"de 2022 y octubre de 2026 las anomalías mensuales simuladas siguen a las de XM con r = {n(s26['r anomalías verificación XM'], 2)} "
    f"(Figura 21b), lo que respalda el estado inicial.")
par(f"Al final de octubre de 2026 el suelo de la cuenca está en z = {n(s26['S z'], 2)} y el acuífero en z = {n(s26['G z'], 2)}, mientras que "
    f"el ONI está 2.9 desviaciones estándar por encima de su media. Con estos valores la regresión logística da una probabilidad de "
    f"{n(100 * s26['P(seco) logística ONI+S'])} % de que el trimestre noviembre-enero sea seco, y el KNN de {n(100 * s26['P(seco) KNN'])} %: "
    f"alerta roja con los dos métodos. La mediana de los análogos ubica el aporte de enero a abril de 2027 entre un "
    f"{n(-pr26['mediana frente a la climatología (%)'].iloc[2:].max())} % y un {n(-pr26['mediana frente a la climatología (%)'].iloc[2:].min())} % "
    f"por debajo de la climatología (Tabla 14 y Figura 21a). Los análogos más cercanos son {', '.join(an26['mes análogo'].head(5))}, es decir, "
    f"el comienzo de los El Niño de 1997-1998, 1982-1983, 1987-1988 y 2015-2016.")
leyenda_tabla("Pronóstico del aporte mensual a la presa emitido al final de octubre de 2026 (KNN, k = 15; m³/s en la escala de Puerto "
              "Valdivia transferido).")
tabla(["Mes", "Mediana", "Percentil 10", "Percentil 90", "Climatología (mediana)", "Mediana frente a la climatología (%)"],
      [[r_["mes"], n(r_["mediana (m³/s)"]), n(r_["p10 (m³/s)"]), n(r_["p90 (m³/s)"]), n(r_["climatología, mediana (m³/s)"]),
        n(r_["mediana frente a la climatología (%)"], 0, True)] for _, r_ in pr26.iterrows()], anchos=[2.2, 2.2, 2.4, 2.4, 3.0, 3.6])
figura(FG / "fig_pronostico_2026.png", "a) Pronóstico del aporte mensual a la presa de noviembre de 2026 a abril de 2027 por años análogos; b) "
       "anomalía del aporte mensual simulado frente a la de los aportes publicados por XM (2023-2026). La banda gris es el periodo en que el "
       "modelo se alimentó con CHIRPS.")
par(f"El pronóstico tiene dos fuentes de incertidumbre. La primera es la lluvia de octubre: si se hubiera supuesto un octubre tan seco "
    f"como julio-septiembre, el suelo habría quedado en z = {n(se['a']['S z'], 1)} y la probabilidad de trimestre seco en "
    f"{n(100 * se['a']['P(seco) logística'])} %; con un octubre normal, en {n(100 * se['b']['P(seco) logística'])} %. El dato de XM de "
    f"octubre fue el que permitió acotarla. La segunda es que ningún mes de la historia tuvo un ONI tan alto, así que los análogos "
    f"corresponden a eventos más débiles y el pronóstico probablemente subestima la sequía; el caso de 2015 (sección 5.2) muestra ese "
    f"mismo sesgo. Los caudales están en la escala de Puerto Valdivia transferido, cuya media es entre 10 % y 30 % mayor que la de los "
    f"aportes que publica XM, por lo que para la operación conviene leerlos como anomalías.")

# ============================================================================================ 6. proyecciones CMIP6
CM = R2 / "11_cmip6"
tam = pd.read_csv(CM / "tamizaje_modelos.csv", index_col=0)
cme = pd.read_csv(CM / "cambios_conjunto.csv", header=[0, 1], index_col=[0, 1])
cpm = pd.read_csv(CM / "cambios_por_modelo.csv")
md, mn, mx = cme["mediana"], cme["mínimo"], cme["máximo"]
sgn = cme["modelos con el signo de la mediana"]
cms = json.loads((CM / "sitio.json").read_text(encoding="utf-8"))
EL = list(tam.index[tam.elegido])
c85 = cms["ciclo"]["ssp585"]
fm = lambda per, i0, i1, cy=c85: 100 * (np.mean(cy[per]["med"][i0:i1]) / np.mean(cy["1981–2010"]["med"][i0:i1]) - 1)  # noqa: E731
d_fm, d_my = fm("2071–2100", 1, 3), fm("2071–2100", 4, 5)
v = lambda e, p, c: float(md.loc[(e, p), c])  # noqa: E731

titulo("6. Proyecciones climáticas CMIP6 y disponibilidad de agua")
par("Para estimar cómo podría cambiar la oferta de agua de la cuenca, el modelo abcd final se alimentó con la lluvia y la temperatura de "
    "modelos climáticos globales del CMIP6 (Eyring et al., 2016), en dos escenarios de emisiones del ScenarioMIP (O'Neill et al., 2016): "
    "SSP2-4.5, intermedio, y SSP5-8.5, de emisiones altas. Los cambios se evaluaron en tres periodos, 2021-2050, 2041-2070 y 2071-2100, "
    "frente a 1981-2010.")
titulo("Selección de modelos por su ciclo anual", 2)
par(f"Se revisaron los {len(tam)} modelos del archivo CMIP6 que tienen lluvia, temperatura máxima y mínima mensuales en el periodo "
    f"histórico y en los dos escenarios, con un mismo miembro del conjunto. Para cada uno se interpoló la lluvia a las celdas de la "
    f"cuenca y se comparó su ciclo anual de 1981-2010 con el del Cubo. El criterio principal fue la forma del ciclo, medida con la "
    f"correlación y con el error del ciclo normalizado por su media; el sesgo de la lluvia anual se usó con la mitad del peso, porque la "
    f"corrección posterior lo elimina, pero un sesgo enorme puede indicar una física pobre. Se eligió el mejor modelo de cada familia (los "
    f"que comparten el componente atmosférico no son independientes), hasta seis (Tabla 15 y Figura 22).")
leyenda_tabla("Modelos CMIP6 elegidos por su ciclo anual de lluvia en la cuenca (1981-2010).")
fil = [[m, tam.loc[m, "familia"], tam.loc[m, "miembro"], n(tam.loc[m, "resolución (°)"], 2), n(tam.loc[m, "r del ciclo"], 2),
        n(tam.loc[m, "RMSE del ciclo normalizado"], 2), n(tam.loc[m, "sesgo (%)"], 0, True)] for m in EL]
tabla(["Modelo", "Familia", "Miembro", "Resolución (°)", "r del ciclo", "Error del ciclo normalizado", "Sesgo (%)"], fil,
      anchos=[3.0, 2.6, 2.0, 2.0, 1.8, 2.6, 1.8], size=9.5)
figura(FG / "fig_cmip6_tamizaje.png", "Ciclo anual normalizado de la lluvia de la cuenca (1981-2010) en los 28 modelos CMIP6 revisados (gris), "
       "en los seis elegidos y en el Cubo de datos del IDEAM.", ancho=Cm(13))
par(f"Pocos modelos reproducen el régimen bimodal. Los de la familia del Hadley Centre (ACCESS-CM2, HadGEM3-GC31-LL, UKESM1-0-LL y "
    f"KACE-1-0-G) y los CNRM tienen correlaciones de su ciclo con el del Cubo de {n(tam.loc[['ACCESS-CM2', 'UKESM1-0-LL', 'CNRM-CM6-1'], 'r del ciclo'].min(), 2)} "
    f"a {n(tam.loc['CNRM-CM6-1-HR', 'r del ciclo'], 2)}, y MIROC6 llega a ser negativa. AWI-CM-1-1-MR fue el mejor, con r = "
    f"{n(tam.loc['AWI-CM-1-1-MR', 'r del ciclo'], 2)} y un sesgo de {n(tam.loc['AWI-CM-1-1-MR', 'sesgo (%)'], 0, True)} %. El sesgo de la "
    f"media no descartó a ningún modelo con buena forma del ciclo: FGOALS-g3 casi cuadruplica la lluvia, como ERA5, pero ubica bien las dos "
    f"temporadas. Este es el mismo problema de magnitud que se encontró en los reanálisis, y se resolvió de la misma forma, con mapeo de "
    f"cuantiles.")
titulo("Corrección por mapeo de cuantiles con deltas (QDM)", 2)
par("El mapeo de cuantiles de la sección 5.1 no sirve tal cual para proyecciones: aplicado al futuro con la función de transferencia del "
    "pasado, puede alterar el cambio que proyecta el modelo, en especial en los extremos (Cannon et al., 2015). Por eso se usó su versión "
    "con deltas (QDM), que corrige el clima histórico del modelo y conserva el cambio relativo que proyecta en cada cuantil. Para cada "
    "celda, mes calendario y década futura, se toma la ventana de 30 años del modelo centrada en esa década y se calcula:")
ecuacion("τ = F~modelo, ventana~ (x)            Δ = x / F~modelo, 1981-2010~^−1^ (τ)            x~corregido~ = F~Cubo, 1981-2010~^−1^ (τ) · Δ")
par("Para la lluvia el cambio Δ es multiplicativo, y para Tmax y Tmin es aditivo (x − F^−1^(τ)). Con las temperaturas corregidas se "
    "calculó la ETo de Hargreaves, y la lluvia y la ETo entraron al modelo abcd con los parámetros calibrados en el numeral 1. Los cambios "
    "de cada modelo se calcularon frente a su propio periodo 1981-2010 corregido y simulado, de modo que el error del modelo hidrológico "
    "se cancela en la comparación.")
titulo("Cambios proyectados", 2)
leyenda_tabla("Cambios proyectados frente a 1981-2010 (mediana de los seis modelos; entre paréntesis, el mínimo y el máximo).")
cols = [("ΔT (°C)", "Temperatura (°C)", 1), ("ΔP (%)", "Lluvia (%)", 0), ("ΔETo (%)", "ETo (%)", 0), ("ΔS (%)", "Humedad del suelo (%)", 1),
        ("ΔQ presa (%)", "Caudal medio en la presa (%)", 0), ("ΔQ10 presa (%)", "Caudal bajo, percentil 10 (%)", 0),
        ("trimestres secos (%)", "Trimestres secos (% de los meses)", 0)]
pers = [("SSP2-4.5", "2041–2070"), ("SSP2-4.5", "2071–2100"), ("SSP5-8.5", "2041–2070"), ("SSP5-8.5", "2071–2100")]
fil = []
for c_, nom, d in cols:
    sg = not c_.startswith("tri")
    fil.append([nom] + [f"{n(md.loc[k, c_], d, sg)} ({n(mn.loc[k, c_], d, sg)} a {n(mx.loc[k, c_], d, sg)})" for k in pers])
tabla(["Variable"] + [f"{e}, {p.replace('–', '-')}" for e, p in pers], fil, anchos=[3.5, 3.1, 3.1, 3.1, 3.1], size=9)
figura(FG / "fig_cmip6_cambios.png", "Cambios proyectados frente a 1981-2010 en la lluvia, la ETo, el caudal medio en la presa y la frecuencia de "
       "trimestres secos. Las barras son la mediana de los seis modelos y los puntos, cada modelo.")
par(f"**Temperatura y evapotranspiración.** Es el cambio más robusto: los seis modelos coinciden en el aumento. Hacia 2071-2100 la cuenca "
    f"se calienta {n(v('SSP2-4.5', '2071–2100', 'ΔT (°C)'), 1)} °C en SSP2-4.5 y {n(v('SSP5-8.5', '2071–2100', 'ΔT (°C)'), 1)} °C en SSP5-8.5, "
    f"y la ETo sube un {n(v('SSP2-4.5', '2071–2100', 'ΔETo (%)'))} % y un {n(v('SSP5-8.5', '2071–2100', 'ΔETo (%)'))} % (Tabla 16 y Figura 23).")
par(f"**Lluvia.** La mediana cambia poco, entre {n(md['ΔP (%)'].min(), 0, True)} % y {n(md['ΔP (%)'].max(), 0, True)} % según el escenario y el "
    f"periodo, y los modelos no coinciden en el signo: en SSP5-8.5 hacia 2071-2100 van de {n(mn.loc[('SSP5-8.5', '2071–2100'), 'ΔP (%)'], 0, True)} % "
    f"(MRI-ESM2-0) a {n(mx.loc[('SSP5-8.5', '2071–2100'), 'ΔP (%)'], 0, True)} % (GISS-E2-1-G). En el espacio (Figura 24), SSP2-4.5 da algo más "
    f"de lluvia en casi toda la cuenca, y SSP5-8.5 acentúa el contraste entre estaciones: junio-agosto más húmedo en el alto Cauca y el "
    f"valle, y diciembre-febrero más seco en el cañón antioqueño, la zona que más aporta a la presa. En la mayor parte de la cuenca, sin "
    f"embargo, menos de cinco de los seis modelos coinciden en el signo del cambio de la lluvia.")
figura(FG / "fig_cmip6_mapas_P.png", "Cambio proyectado de la lluvia anual y trimestral (mediana de los seis modelos corregidos por QDM). Los "
       "puntos marcan las celdas en que menos de cinco de los seis modelos coinciden en el signo.", ancho=Cm(13.5))
par(f"**Caudales.** El caudal medio en la presa cambia poco: la mediana va de {n(md['ΔQ presa (%)'].min(), 0, True)} % a "
    f"{n(md['ΔQ presa (%)'].max(), 0, True)} %, con un rango entre modelos de {n(mn.loc[('SSP5-8.5', '2071–2100'), 'ΔQ presa (%)'], 0, True)} % a "
    f"{n(mx.loc[('SSP5-8.5', '2071–2100'), 'ΔQ presa (%)'], 0, True)} % en SSP5-8.5 hacia 2071-2100. Los caudales bajos, en cambio, sí se "
    f"reducen: en SSP5-8.5 el percentil 10 del caudal mensual cae un {n(-v('SSP5-8.5', '2071–2100', 'ΔQ10 presa (%)'))} % hacia 2071-2100, y "
    f"la frecuencia de trimestres secos (la misma definición de la alerta de la sección 5.3) pasa del 20 % de los meses a "
    f"{n(v('SSP5-8.5', '2071–2100', 'trimestres secos (%)'))} %. La razón es la combinación de más evapotranspiración y menos lluvia en "
    f"diciembre-febrero. El ciclo anual del aporte conserva su forma bimodal (Figura 25), pero en SSP5-8.5 el estiaje de comienzo de año se "
    f"hace más profundo: hacia 2071-2100 el aporte de febrero-marzo baja un {n(-d_fm)} %, mientras que el de mayo sube un {n(d_my)} %.")
figura(FG / "fig_cmip6_ciclo_presa.png", "Ciclo anual del aporte a la presa simulado con el clima de los seis modelos corregidos (mediana) en "
       "cada periodo, con el rango entre modelos en 2041-2070 y 2071-2100, en los dos escenarios.")
par("**Implicaciones para la generación.** Para Hidroituango, la conclusión no es que vaya a llegar menos agua en promedio, sino que los "
    "meses secos serían más secos y más frecuentes, sobre todo en un escenario de emisiones altas. Esto pesa más que el promedio, porque "
    "la energía firme de una central y el riesgo de desabastecimiento dependen de los estiajes. Además, la incertidumbre entre modelos es "
    "mayor que el cambio de la mediana, de modo que la planeación debería considerar el rango de escenarios y no solo un valor central. El "
    "efecto de estos caudales sobre la operación del embalse y la energía generada se evaluará con el modelo de operación del Trabajo 1.")
par("Estos resultados tienen varias limitaciones. Seis modelos con un solo miembro cada uno no representan toda la incertidumbre del "
    "CMIP6. El QDM corrige la distribución mensual de cada celda pero no los errores del modelo en la secuencia de los meses ni en la "
    "representación del ENSO. Y el modelo abcd se usa con los parámetros calibrados en el clima actual, sin cambios en la vegetación ni "
    "en el uso del suelo.")

# ============================================================================================ conclusiones
titulo("Conclusiones")
par(f"El Cubo de datos del IDEAM es la mejor referencia de lluvia mensual para la cuenca, pero solo después de un control de calidad: su "
    f"archivo diario trae valores de hasta 4702 mm que inflaban la lluvia media en un "
    f"{n(100 * (P_orig / P_cubo - 1))} % y deformaban el ciclo anual. CHIRPS v2.0 lo iguala casi en todo. ERA5 y ERA5-Land triplican la "
    f"lluvia, y el mapeo de cuantiles corrige su sesgo pero no su secuencia mensual ni su patrón espacial.")
par(f"El modelo abcd distribuido, con calibración multisitio regionalizada, reproduce los caudales mensuales de diez estaciones (KGE medio "
    f"de validación de {n(kv, 2)} y de {n(pres.loc['val', 'KGE'], 2)} en la presa). Para un sistema operativo se recomienda este modelo con "
    f"ETo de Hargreaves y lluvia de CHIRPS v2.0, que se actualiza en tiempo casi real; la ecuación empírica sin memoria no es suficiente.")
par("El Niño reduce la lluvia de la cuenca sobre todo en diciembre-febrero y junio-agosto, los mismos meses de los estiajes, y la "
    "respuesta es coherente entre productos en el promedio de la cuenca, pero solo los productos con estaciones coinciden en su "
    "distribución espacial.")
par("El suelo amplifica y prolonga la sequía de El Niño: se seca en más del 99 % del área, con anomalías mayores que las de la lluvia, y "
    "sigue seco en marzo-mayo aunque la lluvia ya esté cerca de lo normal.")
par(f"Los caudales caen en todos los trimestres de El Niño, con la mayor reducción en la presa en diciembre-marzo, y responden al ENSO con "
    f"unos dos meses de rezago a través del suelo y del acuífero. El modelo reproduce esa respuesta en el signo y en el ciclo anual de cada "
    f"fase, aunque subestima la sequía extrema en la presa. El primer modo de variabilidad de la lluvia y del suelo cubre toda la cuenca y "
    f"está ligado al ENSO.")
par("La memoria de la cuenca permite anticipar los aportes. Un pronóstico por años análogos supera a la persistencia desde el segundo "
    "mes, y una regresión logística con el ONI y la humedad del suelo simulada da una probabilidad confiable de trimestre seco: con alerta "
    "roja, tres de cada cuatro trimestres siguientes fueron secos. Aplicados al El Niño 2026-2027, el más intenso del registro, los dos "
    "métodos emiten alerta roja al final de octubre de 2026 y anticipan aportes de enero a abril de 2027 entre un tercio y un 40 % por "
    "debajo de lo normal.")
par(f"Con seis modelos CMIP6 elegidos por su ciclo anual y corregidos por QDM, el caudal medio en la presa cambia poco en este siglo, pero "
    f"los estiajes se profundizan: en SSP5-8.5 hacia 2071-2100 el caudal bajo cae un {n(-v('SSP5-8.5', '2071–2100', 'ΔQ10 presa (%)'))} % y "
    f"los trimestres secos pasan del 20 % al {n(v('SSP5-8.5', '2071–2100', 'trimestres secos (%)'))} % de los meses, por el aumento de la "
    f"evapotranspiración y la menor lluvia de diciembre-febrero. El aumento de temperatura y de ETo es robusto; el signo del cambio de la "
    f"lluvia, no.")

# ============================================================================================ referencias
titulo("Referencias")
refs = [
    "Allen, R. G., Pereira, L. S., Raes, D. y Smith, M. (1998). _Crop evapotranspiration: Guidelines for computing crop water requirements_ "
    "(FAO Irrigation and Drainage Paper 56). FAO.",
    "Brier, G. W. (1950). Verification of forecasts expressed in terms of probability. _Monthly Weather Review_, 78(1), 1-3.",
    "Cannon, A. J., Sobie, S. R. y Murdock, T. Q. (2015). Bias correction of GCM precipitation by quantile mapping: How well do methods "
    "preserve changes in quantiles and extremes? _Journal of Climate_, 28(17), 6938-6959.",
    "Carvajal, Y., Jiménez, H. y Materón, H. (1998). Incidencia del fenómeno ENSO en la hidroclimatología del valle del río Cauca, "
    "Colombia. _Bulletin de l'Institut Français d'Études Andines_, 27(3), 743-751.",
    "Funk, C., Peterson, P., Landsfeld, M., Pedreros, D., Verdin, J., Shukla, S., Husak, G., Rowland, J., Harrison, L., Hoell, A. y "
    "Michaelsen, J. (2015). The climate hazards infrared precipitation with stations: A new environmental record for monitoring extremes. "
    "_Scientific Data_, 2, 150066.",
    "Gudmundsson, L., Bremnes, J. B., Haugen, J. E. y Engen-Skaugen, T. (2012). Technical Note: Downscaling RCM precipitation to the "
    "station scale using statistical transformations, a comparison of methods. _Hydrology and Earth System Sciences_, 16, 3383-3390.",
    "Gupta, H. V., Kling, H., Yilmaz, K. K. y Martinez, G. F. (2009). Decomposition of the mean squared error and NSE performance criteria: "
    "Implications for improving hydrological modelling. _Journal of Hydrology_, 377, 80-91.",
    "Hargreaves, G. H. y Samani, Z. A. (1985). Reference crop evapotranspiration from temperature. _Applied Engineering in Agriculture_, "
    "1(2), 96-99.",
    "Hersbach, H. (2000). Decomposition of the continuous ranked probability score for ensemble prediction systems. _Weather and "
    "Forecasting_, 15, 559-570.",
    "Hersbach, H. et al. (2020). The ERA5 global reanalysis. _Quarterly Journal of the Royal Meteorological Society_, 146(730), 1999-2049.",
    "Hosmer, D. W., Lemeshow, S. y Sturdivant, R. X. (2013). _Applied logistic regression_ (3.ª ed.). Wiley.",
    "IDEAM. (2021). _Nota técnica IDEAM-METEO/003-2021: Estimación de la evapotranspiración de referencia_. Instituto de Hidrología, "
    "Meteorología y Estudios Ambientales.",
    "IDEAM. (2025). _Cubo de datos: precipitación, temperatura y humedad relativa diarias y mensuales 1981-2023_. "
    "https://bart.ideam.gov.co/meteorologia/DATOS/CUBO%20DE%20DATOS/",
    "IPCC. (2021). Summary for policymakers. En _Climate Change 2021: The Physical Science Basis. Contribution of Working Group I to the "
    "Sixth Assessment Report of the Intergovernmental Panel on Climate Change_. Cambridge University Press.",
    "La República. (20 de marzo de 2019). La oferta hidráulica equivale a cerca de 69 % de la matriz energética del país. "
    "https://www.larepublica.co/especiales/minas-y-energia-marzo-2019/la-oferta-hidraulica-equivale-a-cerca-de-69-de-la-matriz-energetica-del-pais-2842181",
    "Lall, U. y Sharma, A. (1996). A nearest neighbor bootstrap for resampling hydrologic time series. _Water Resources Research_, 32(3), "
    "679-693.",
    "Martinez, G. F. y Gupta, H. V. (2010). Toward improved identification of hydrological models: A diagnostic evaluation of the \"abcd\" "
    "monthly water balance model for the conterminous United States. _Water Resources Research_, 46, W08507.",
    "Muñoz-Sabater, J. et al. (2021). ERA5-Land: A state-of-the-art global reanalysis dataset for land applications. _Earth System Science "
    "Data_, 13, 4349-4383.",
    "NOAA Climate Prediction Center. (2026). _Oceanic Niño Index (ONI)_. https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt",
    "North, G. R., Bell, T. L., Cahalan, R. F. y Moeng, F. J. (1982). Sampling errors in the estimation of empirical orthogonal functions. "
    "_Monthly Weather Review_, 110, 699-706.",
    "Poveda, G., Jaramillo, A., Gil, M. M., Quiceno, N. y Mantilla, R. I. (2001). Seasonality in ENSO-related precipitation, river "
    "discharges, soil moisture, and vegetation index in Colombia. _Water Resources Research_, 37(8), 2169-2178.",
    "Poveda, G., Álvarez, D. M. y Rueda, O. A. (2011). Hydro-climatic variability over the Andes of Colombia associated with ENSO: A review "
    "of climatic processes and their impact on one of the Earth's most important biodiversity hotspots. _Climate Dynamics_, 36, 2233-2249.",
    "Storn, R. y Price, K. (1997). Differential evolution: A simple and efficient heuristic for global optimization over continuous spaces. "
    "_Journal of Global Optimization_, 11, 341-359.",
    "Eyring, V., Bony, S., Meehl, G. A., Senior, C. A., Stevens, B., Stouffer, R. J. y Taylor, K. E. (2016). Overview of the Coupled Model "
    "Intercomparison Project Phase 6 (CMIP6) experimental design and organization. _Geoscientific Model Development_, 9, 1937-1965.",
    "O'Neill, B. C. et al. (2016). The Scenario Model Intercomparison Project (ScenarioMIP) for CMIP6. _Geoscientific Model Development_, 9, "
    "3461-3482.",
    "Superintendencia de Servicios Públicos Domiciliarios. (2016). _Informe 105-2016: Experiencias del fenómeno de El Niño 2015-2016_. "
    "https://www.superservicios.gov.co/sites/default/files/inline-files/informeno105-2016_experienciasdelnino2015-2016.pdf",
    "Thomas, H. A. (1981). _Improved methods for national water assessment_. U.S. Water Resources Council.",
    "Wilks, D. S. (2011). _Statistical methods in the atmospheric sciences_ (3.ª ed.). Academic Press.",
]
for r_ in sorted(refs, key=lambda x: x.lower().replace('ó','o')):
    p = par(r_, just=False, after=6)
    p.paragraph_format.left_indent = Cm(1.0); p.paragraph_format.first_line_indent = Cm(-1.0)

# numeración de página
sec = doc.sections[0]
fp = sec.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
for tag, txt in [("begin", None), (None, "PAGE"), ("end", None)]:
    r = fp.add_run()
    if tag:
        e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), tag); r._r.append(e)
    else:
        e = OxmlElement("w:instrText"); e.set(qn("xml:space"), "preserve"); e.text = txt; r._r.append(e)
sec.different_first_page_header_footer = True

salida = INF / "Informe_Trabajo2_Hidroituango.docx"
doc.save(salida)
print("guardado", salida, "·", NF[0], "figuras ·", NT[0], "tablas")
