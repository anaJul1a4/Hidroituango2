"""
Sitio web del Trabajo 2 (modelación hidrológica mensual y ENSO, cuenca del Cauca hasta Hidroituango), en formato de presentación:
una diapositiva a la vez, secciones en el encabezado, navegación con flechas, puntos y teclado, y modo claro/oscuro. El estilo es el de
la presentación PAE Orinoquía–Amazonía (estilo_deck.css), que sigue los tokens de carlosdhoyos.github.io.

Reglas del sitio (las mismas del Trabajo 1): figuras originales (mapas como PNG→WebP, sin redibujar); gráficas Plotly estáticas
(sin zoom ni arrastre, valores al pasar el cursor); lluvia en azul y sequía en rojo; sin verdes, rosados ni morados en los datos.

Uso: python trabajo2/sitio/construir.py   →   trabajo2/sitio/docs/index.html (+ img/)
"""
import hashlib
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
R2 = ROOT / "trabajo2" / "resultados"
SITIO = Path(__file__).resolve().parent
DOCS = SITIO / "docs"
IMG = DOCS / "img"
IMG.mkdir(parents=True, exist_ok=True)
T1_URL = "https://anajul1a4.github.io/balance-hidrico-hidroituango/"

final = json.loads((R2 / "04_abcd" / "modelo_final.json").read_text(encoding="utf-8")) \
    if (R2 / "04_abcd" / "modelo_final.json").exists() else {"tipo": "secuencial", "producto": "Cubo IDEAM", "eto": "Penman-Monteith"}
D = {}


def f(v, d=0):
    s = f"{v:,.{d}f}".replace(",", " ").replace(".", ",")
    return s.replace("-", "−")


def fig(src, nombre, alt, ancho=3200):
    im = Image.open(src).convert("RGB")
    if im.width > ancho:
        im = im.resize((ancho, round(im.height * ancho / im.width)), Image.LANCZOS)
    im.save(IMG / f"{nombre}.webp", "WEBP", quality=88, method=6)
    v = hashlib.md5((IMG / f"{nombre}.webp").read_bytes()).hexdigest()[:8]
    return (f"<a href='img/{nombre}.webp?v={v}' target='_blank' rel='noopener' title='Abrir en tamaño completo'>"
            f"<img class='figimg' src='img/{nombre}.webp?v={v}' width='{im.width}' height='{im.height}' alt='{html.escape(alt)}' loading='lazy'></a>")


def tabla(df, fmt=None, idx=True):
    fmt = fmt or {}
    cab = ("<th></th>" if idx else "") + "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    filas = ""
    for i, r in df.iterrows():
        tds = f"<td>{html.escape(str(i))}</td>" if idx else ""
        for c, v in r.items():
            if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
                tds += f"<td class='n'>{'—' if pd.isna(v) else f(v, fmt.get(c, 2))}</td>"
            else:
                tds += f"<td>{html.escape(str(v))}</td>"
        filas += f"<tr>{tds}</tr>"
    return f"<div class='tw'><table class='tb'><thead><tr>{cab}</tr></thead><tbody>{filas}</tbody></table></div>"


def chips(id_, opciones, on=0):
    return f"<div class='chips' id='{id_}'>" + "".join(
        f"<button class='chip' type='button' data-v='{html.escape(v)}'{' aria-pressed=\"true\"' if k == on else ''}>{html.escape(t)}</button>"
        for k, (v, t) in enumerate(opciones)) + "</div>"


# ============================================================================= datos
ENT = R2 / "01_entradas"
S = pd.read_csv(ENT / "series_unidades.csv", header=[0, 1], index_col=0, parse_dates=True)
C = S.xs("CUENCA", axis=1, level="unidad")
cic = pd.read_csv(R2 / "02_comparacion" / "ciclo_anual_cuenca.csv", index_col=0)
met = pd.read_csv(R2 / "02_comparacion" / "metricas_vs_cubo.csv")
bal = pd.read_csv(R2 / "02_comparacion" / "balance_productos_cubo.csv", dtype={"codigo": str})
marc = pd.read_csv(R2 / "00_limpieza_cubo" / "marcados_por_mes.csv", index_col=0, parse_dates=True)

# Cubo original (archivo mensual nacional) en la cuenca, para mostrar el error
cel = pd.read_csv(ENT / "grilla_celdas.csv")
w = cel.a_cuenca_km2.values
orig = xr.open_dataset(ROOT / "CUBO_IDEAM" / "prcp_mes_acum_1981_2023.nc").prcp.sel(
    lat=xr.DataArray(cel.lat.values, dims="c"), lon=xr.DataArray(cel.lon.values, dims="c"), method="nearest")
orig_c = pd.Series((orig.values * w).sum(1) / w.sum(), index=pd.DatetimeIndex(orig.time.values))
b = orig_c["1981":"2010"]
D["qc"] = {"orig": b.groupby(b.index.month).mean().round(0).tolist(), "limpio": cic["Cubo IDEAM"].round(0).tolist(),
           "chirps": cic["CHIRPS v2.0"].round(0).tolist(),
           "marc": marc.groupby(marc.index.month)["celdas-día marcadas"].sum().tolist(),
           "t": orig_c.index.strftime("%Y-%m").tolist(), "so": orig_c.round(0).tolist(),
           "sl": C["P Cubo IDEAM"].reindex(orig_c.index).round(0).tolist(), "sc": C["P CHIRPS v2.0"].reindex(orig_c.index).round(0).tolist()}
r_o = orig_c.corr(C["P CHIRPS v2.0"].reindex(orig_c.index))
r_l = C["P Cubo IDEAM"].corr(C["P CHIRPS v2.0"])
D["ciclo"] = {k: cic[k].round(1).tolist() for k in cic.columns}

m81 = met[met.periodo == "1981–2010"].set_index("producto")
m11 = met[met.periodo == "2011–2023"].set_index("producto")
tab_met = pd.DataFrame({"P anual 1981–2010 (mm)": m81["P anual (mm/año)"], "sesgo (%)": m81["sesgo (%)"],
                        "r mensual": m81["r mensual"], "r anomalías": m81["r anomalías mensuales"],
                        "r espacial": m81["r espacial (media anual)"], "KGE 1981–2010": m81["KGE"], "KGE 2011–2023": m11["KGE"]})
tab_met.index.name = "frente al Cubo"
tab_met.loc["Cubo IDEAM"] = [C["P Cubo IDEAM"]["1981":"2010"].resample("YS").sum().mean(), 0, 1, 1, 1, 1, 1]
tab_met = tab_met.loc[["Cubo IDEAM", "CHIRPS v2.0", "CHIRPS v3.0", "ERA5-Land", "ERA5", "ERA5-Land QM", "ERA5 QM"]]
pres = bal[bal.codigo == "PRESA"].pivot(index="producto", columns="ETo", values="error (%)")
est9 = bal[bal.codigo != "PRESA"].groupby(["producto", "ETo"])["error (%)"].apply(lambda e: e.abs().mean()).unstack()
tab_bal = pd.DataFrame({"P (mm/año)": bal[(bal.codigo == "PRESA") & (bal.ETo == "Penman-Monteith")].set_index("producto")["P"],
                        "error cierre, ETo PM (%)": pres["Penman-Monteith"], "error cierre, ETo Hargreaves (%)": pres["Hargreaves"],
                        "error medio 9 estaciones, PM (%)": est9["Penman-Monteith"],
                        "error medio 9 estaciones, Hargreaves (%)": est9["Hargreaves"]}).loc[tab_met.index]
tab_bal.index.name = "producto"

# ---- modelo abcd
ABC = R2 / "04_abcd"
M = pd.read_csv(ABC / "metricas.csv")
if (ABC / "regionalizado_metricas.csv").exists():
    M = pd.concat([M, pd.read_csv(ABC / "regionalizado_metricas.csv")])
M["per"] = np.where(M.periodo.str.startswith("cal"), "cal", "val")
qobs = pd.read_csv(R2 / "03_caudales" / "Q_mensual_estaciones.csv", index_col=0, parse_dates=True)
EST = ["La Balsa", "Juanchito", "La Victoria", "La Virginia", "Irra", "La Pintada", "Puente Iglesias", "Bolombolo", "Cañafisto", "Presa"]
COD = dict(zip(EST, ["26027010", "26067010", "26107070", "26177030", "26167070", "26187110", "26207030", "26207080", "26217050", "PRESA"]))
etq = "PM" if final["eto"] == "Penman-Monteith" else "HG"
arch = (ABC / f"Q_simulado_reg_{final['producto'].replace(' ', '_')}_{etq}.csv") if final["tipo"] == "regionalizado" \
    else (ABC / f"Q_simulado_{final['producto'].replace(' ', '_')}.csv")
qsim = pd.read_csv(arch, index_col=0, parse_dates=True)
modelo_final = "abcd semidistribuido regionalizado" if final["tipo"] == "regionalizado" else "abcd semidistribuido"
mf = M[(M.modelo == modelo_final) & (M.producto == final["producto"]) & (M.ETo == final["eto"])]
D["kge"] = {"est": EST, "cal": [float(mf[(mf["estación"] == e) & (mf.per == "cal")].KGE.iloc[0]) for e in EST],
            "val": [float(mf[(mf["estación"] == e) & (mf.per == "val")].KGE.iloc[0]) for e in EST],
            "pb_val": [float(mf[(mf["estación"] == e) & (mf.per == "val")].PBIAS.iloc[0]) for e in EST]}
D["serie"] = {"t": qsim.index.strftime("%Y-%m").tolist(),
              "obs": {e: qobs[COD[e]].reindex(qsim.index).round(1).where(lambda s: s.notna(), None).tolist() for e in EST},
              "sim": {e: qsim[e].round(1).tolist() for e in EST}}
res_m = M.groupby(["modelo", "producto", "ETo", "per"]).KGE.mean().unstack("per")
pz = M[M.codigo == "PRESA"].pivot_table(index=["modelo", "producto", "ETo"], columns="per", values="KGE")
tab_mod = pd.DataFrame({"KGE medio estaciones (cal)": res_m["cal"], "KGE medio estaciones (val)": res_m["val"],
                        "KGE presa (cal)": pz["cal"], "KGE presa (val)": pz["val"]})
semi = tab_mod.index.get_level_values(0).str.contains("semidistribuido")
tab_mod.loc[~semi, ["KGE medio estaciones (cal)", "KGE medio estaciones (val)"]] = np.nan
tab_mod = tab_mod.reset_index()
orden_m = {"abcd semidistribuido regionalizado": 0, "abcd semidistribuido": 1, "abcd agregado": 2,
           "empírico con memoria Q = α·W + γ·Q(t−1) + β": 3, "empírico Q = α·W + β": 4}
tab_mod["o"] = tab_mod.modelo.map(orden_m)
tab_mod = tab_mod.sort_values(["o", "KGE presa (val)"], ascending=[True, False]).drop(columns="o")
tab_mod = tab_mod[~((tab_mod.producto == "ERA5") & tab_mod.modelo.str.startswith("empírico"))]
tab_mod.index = tab_mod.modelo + " · " + tab_mod.producto + " · ETo " + tab_mod.ETo.str.replace("Penman-Monteith", "PM")
tab_mod = tab_mod.drop(columns=["modelo", "producto", "ETo"])
tab_mod.index.name = "modelo · P · ETo"
emp = M[(M.codigo == "PRESA") & (M.producto == final["producto"]) & (M.per == "val")].set_index("modelo")
D["emp"] = {"mod": ["empírico Q = α·W + β", "empírico con memoria Q = α·W + γ·Q(t−1) + β", "abcd agregado", modelo_final],
            "kge": [float(emp.loc[k].KGE) if k in emp.index and np.ndim(emp.loc[k].KGE) == 0 else float(emp.loc[k].KGE.iloc[0])
                    for k in ["empírico Q = α·W + β", "empírico con memoria Q = α·W + γ·Q(t−1) + β", "abcd agregado", modelo_final]
                    if k in emp.index]}
par = pd.read_csv(ABC / ("regionalizado_parametros.csv" if final["tipo"] == "regionalizado" else "parametros.csv"))

# ---- ENSO
EP, ES = R2 / "05_enso_P", R2 / "06_enso_suelo_Q"
comp = pd.read_csv(EP / "compuestos_cuenca.csv")
cons = pd.read_csv(EP / "consistencia.csv")
coni = pd.read_csv(EP / "correlacion_oni.csv")
PR = ["Cubo IDEAM", "CHIRPS v2.0", "CHIRPS v3.0", "ERA5-Land", "ERA5", "ERA5-Land QM", "ERA5 QM"]
TR = ["DEF", "MAM", "JJA", "SON"]
D["enso_p"] = {fa: {p: [float(comp[(comp.producto == p) & (comp.trimestre == t) & (comp.fase == fa)]["z medio de la cuenca"].iloc[0])
                        for t in TR] for p in PR} for fa in ["El Niño", "La Niña"]}
tab_cons = cons[cons.producto != "Cubo IDEAM"].pivot_table(index="producto", columns=["fase", "trimestre"],
                                                           values="r espacial con el Cubo").loc[PR[1:]]
tab_cons.columns = [f"{a} {b}" for a, b in tab_cons.columns]
tab_oni = coni.pivot(index="producto", columns="trimestre", values="r(ONI, z cuenca)").loc[PR, TR]
ts = pd.read_csv(ES / "suelo_compuestos.csv")
tq = pd.read_csv(ES / "caudales_compuestos.csv")
D["enso_q"] = {e: {fa: {"obs": [float(tq[(tq["estación"] == e) & (tq.trimestre == t) & (tq.fase == fa)]["z Q observado"].iloc[0]) for t in TR],
                        "sim": [float(tq[(tq["estación"] == e) & (tq.trimestre == t) & (tq.fase == fa)]["z Q simulado"].iloc[0]) for t in TR]}
                   for fa in ["El Niño", "La Niña"]} for e in ["La Virginia", "Bolombolo", "Presa"]}
D["suelo"] = {fa: {"S": [float(ts[(ts.trimestre == t) & (ts.fase == fa)]["z S cuenca"].iloc[0]) for t in TR],
                   "P": [float(ts[(ts.trimestre == t) & (ts.fase == fa)]["z P cuenca"].iloc[0]) for t in TR]} for fa in ["El Niño", "La Niña"]}
cpf = pd.read_csv(ES / "ciclo_por_fase.csv")
D["cpf"] = {e: {fa: {"obs": cpf[(cpf["estación"] == e) & (cpf.fase == fa)]["Q observado"].round(0).tolist(),
                     "sim": cpf[(cpf["estación"] == e) & (cpf.fase == fa)]["Q simulado"].round(0).tolist()}
                for fa in ["El Niño", "Neutro", "La Niña"]} for e in ["La Virginia", "Bolombolo", "Presa"]}
rz = pd.read_csv(ES / "rezagos_oni.csv").set_index("variable")
D["rez"] = {v: [float(rz.loc[v, f"ONI → {v} rezago {k}"]) for k in range(7)] for v in ["P", "S", "Q sim presa", "Q obs presa"]}
rp = pd.read_csv(ES / "rezagos_P.csv", index_col=0)
D["rezP"] = {k: rp.loc[k].round(3).tolist() for k in rp.index}
an = pd.read_csv(ES / "anomalias_mensuales_cuenca.csv", index_col=0, parse_dates=True)
sc = pd.read_csv(ES / "series_cuenca.csv", index_col=0, parse_dates=True)
roll = lambda s: s.rolling(3, center=True).mean()  # noqa: E731
D["anom"] = {"t": an.index.strftime("%Y-%m").tolist(), "P": roll(an.P).round(2).where(lambda s: s.notna(), None).tolist(),
             "S": an.S.round(2).tolist(), "Q": roll(an["Q obs presa"]).round(2).where(lambda s: s.notna(), None).tolist(),
             "oni": sc.ONI.round(2).where(lambda s: s.notna(), None).tolist()}

# ============================================================================= diapositivas
SEC = [("portada", "", "Inicio"), ("datos", "1", "Datos de entrada"), ("abcd", "2", "Modelo abcd"),
       ("enso-p", "3", "ENSO y lluvia"), ("suelo", "4", "Humedad del suelo"), ("caudal", "5", "Caudales"), ("cierre", "6", "Cierre")]
sl = []


def slide(id_, sec, kicker, titulo, cuerpo, g="d", k="k-data"):
    sl.append(f"<section class='slide' id='{id_}' data-g='{g}' data-sec='{html.escape(sec)}'><p class='kicker {k}'>{kicker}</p>"
              f"<h2>{titulo}</h2>{cuerpo}</section>")


cp_pres = mf[(mf["estación"] == "Presa")].set_index("per")
kv_med = mf[mf.per == "val"].KGE.mean()
# ---- portada
sl.append(f"""<section class='slide portada' id='portada' data-g='' data-sec='Trabajo 2 · Hidrometeorología'>
<p class='kicker'>Trabajo 2 · Hidrometeorología · UNAL Medellín</p>
<h1>¿Qué tan bien podemos simular mes a mes el agua que llega a <span class='hl'>Hidroituango</span>, y qué le hace El Niño?</h1>
<p class='lead'>Modelo lluvia–escorrentía mensual abcd para la cuenca del río Cauca hasta la presa (35 992 km²), calibrado en diez
estaciones a la vez con el Cubo de datos del IDEAM, y la huella de El Niño y La Niña en la lluvia, la humedad del suelo y los
caudales. Continúa el <a href='{T1_URL}'>Trabajo 1 (balance hídrico de largo plazo)</a>.</p>
<div class='cards3'>
<button class='card lift pick' type='button' data-go='d-cubo'><h4>1 · Datos de entrada</h4><p>Cinco productos de lluvia, el Cubo del IDEAM
limpio y ERA5 corregido.</p></button>
<button class='card lift pick' type='button' data-go='m-como'><h4>2 · Modelo abcd</h4><p>Cuatro parámetros, diez unidades, diez estaciones.</p></button>
<button class='card lift pick' type='button' data-go='p-mapas'><h4>3 · ENSO y lluvia</h4><p>Anomalías por trimestre y producto.</p></button>
<button class='card lift pick' type='button' data-go='s-mapas'><h4>4 · Humedad del suelo</h4><p>El suelo alarga la sequía de El Niño.</p></button>
<button class='card lift pick' type='button' data-go='q-comp'><h4>5 · Caudales</h4><p>Observados y simulados en El Niño y La Niña.</p></button>
<button class='card lift pick' type='button' data-go='g-intro'><h4>6 · Decisiones de generación</h4><p>KNN, regresión logística, EOF y Fourier.</p></button>
<button class='card lift pick' type='button' data-go='c-tam'><h4>7 · Proyecciones CMIP6</h4><p>Seis modelos, dos escenarios, el abcd hasta 2100.</p></button>
</div></section>""")

# ---- 1. datos
slide("d-cubo", "1 · Datos de entrada", "1a · Cubo de datos del IDEAM · control de calidad",
      "El Cubo del IDEAM traía días de hasta 4700 mm en la cuenca: hubo que limpiarlo antes de usarlo", f"""
<div class='two fig'><div>
<p>El Cubo de datos es la grilla diaria de 0,1° que el IDEAM generó con el software CDT a partir de 1567 estaciones (lluvia,
temperaturas y humedad, 1981–2023). En la cuenca, el archivo diario trae <b>valores imposibles, de 1945 a 4702 mm en un día</b>,
sobre todo en diciembre–febrero, y el archivo mensual es la suma de esos días.</p>
<div class='callout amber'><b>Efecto:</b> en enero de 1995 la lluvia media de la cuenca salía en {f(orig_c['1995-01'].iloc[0])} mm (CHIRPS: 60 mm), y el ciclo
anual mostraba enero y febrero tan lluviosos como octubre. La correlación mensual con CHIRPS era {f(r_o, 2)}.</div>
<p><b>Corrección.</b> Se marca la lluvia diaria de una celda que supera 100 mm y es más de 4 veces la mediana de sus 5 × 5 vecinas ese
día (un «ojo de buey» aislado), o que supera 500 mm; se reemplaza por esa mediana. Cambia sólo el 0,09 % de las celdas-día y la
correlación con CHIRPS pasa a {f(r_l, 2)}.</p>
{chips('qcVista', [('ciclo', 'Ciclo anual'), ('serie', 'Serie mensual'), ('marc', 'Celdas marcadas por mes')])}
<p class='tryit'>pasa a la serie mensual y busca enero de 1995 y enero de 1998, en plena sequía de El Niño.</p>
</div><div class='panel'><div class='tshost' id='qcFig' style='height:480px'></div>
<div id='qcImg' hidden>{fig(R2 / '07_figuras' / 'fig_celdas_marcadas.png', 'celdas_marcadas', 'Celdas-día corregidas por mes')}</div></div></div>""")

slide("d-mapas", "1 · Datos de entrada", "1a · productos de precipitación · media 1981–2010",
      "Con el Cubo limpio, los productos con estaciones coinciden; ERA5 y ERA5-Land triplican la lluvia y la corrección la devuelve", f"""
<div class='two fig'><div>
<p>Los siete campos están en la grilla del Cubo (0,1°): CHIRPS v2.0 y v3.0 interpolados desde 0,05°, ERA5-Land en su retícula y ERA5
interpolado desde 0,25°. La escala de color es la del Trabajo 1: el mismo valor tiene el mismo color en todos los mapas.</p>
<ul class='pts'><li><b>Cubo, CHIRPS v2.0 y CHIRPS v3.0</b>: 2000–2200 mm/año, con el mismo patrón (correlación espacial 0,82–0,85).</li>
<li><b>ERA5 y ERA5-Land</b>: cerca de 6000 mm/año y sin relación con el patrón observado (correlación espacial ≈ 0).</li>
<li><b>ERA5 y ERA5-Land corregidos</b> por mapeo de cuantiles con el Cubo: recuperan la media y el patrón.</li></ul>
<p class='note'>Producto que se usa para cada celda en el modelo: su propio valor mensual; los mapas sólo resumen el promedio.</p>
</div><div class='panel'>{fig(R2 / '02_comparacion' / 'mapas_P_productos.png', 'mapas_P', 'Mapas de precipitación media anual por producto')}</div></div>""")

slide("d-ciclo", "1 · Datos de entrada", "1a–b · ciclo anual y métricas frente al Cubo",
      "Todos los productos con estaciones repiten el ciclo bimodal; ERA5 sin corregir lo aplana y lo multiplica por tres", f"""
<div class='two fig'><div>
{chips('ciclo', [('obs', 'Con estaciones'), ('rea', 'Reanálisis sin corregir'), ('qm', 'Reanálisis corregidos')])}
<p class='tryit'>compara los reanálisis corregidos con el Cubo: la media coincide por construcción, pero mira la tabla para 2011–2023.</p>
{tabla(tab_met, {"P anual 1981–2010 (mm)": 0, "sesgo (%)": 1})}
<p class='note'>Serie mensual promedio de la cuenca. KGE: eficiencia de Kling–Gupta (1 = perfecto). «r anomalías»: correlación sin el ciclo
anual. 2011–2023 no se usó para ajustar la corrección: es la verificación independiente.</p>
</div><div class='panel'><div class='tshost' id='cicloFig' style='height:480px'></div></div></div>""")

slide("d-qm", "1 · Datos de entrada", "1b · corrección de sesgo · mapeo de cuantiles",
      "ERA5 ya estaba corregido en el Trabajo 1 con CHIRPS; aquí se corrige con el Cubo, la referencia que entonces no había", f"""
<div class='two even'><div>
<div class='callout blue'><b>Trabajo 1.</b> ERA5 y ERA5-Land se corrigieron por mapeo de cuantiles empírico, por celda y por mes
calendario, con CHIRPS v2.0 como referencia (1981–2010), porque del IDEAM sólo había normales. El sesgo de +190 % desapareció y el
balance de largo plazo pasó a cerrar dentro de ±10 %.</div>
<p><b>Trabajo 2.</b> El mismo método con el Cubo como referencia: para cada celda y mes, el valor de ERA5 se reemplaza por el del Cubo
con la misma probabilidad acumulada (cuantiles 1 a 99 de 1981–2010; fuera de ese rango, la razón del extremo). Se aplica a 1981–2023.</p>
<ul class='pts'><li>La media y el ciclo anual quedan iguales a los del Cubo en 1981–2010.</li>
<li>En 2011–2023, sin reajustar, ERA5 corregido conserva un sesgo de {f(m11.loc['ERA5 QM', 'sesgo (%)'], 1)} % y KGE {f(m11.loc['ERA5 QM', 'KGE'], 2)};
ERA5-Land, {f(m11.loc['ERA5-Land QM', 'sesgo (%)'], 1)} % y KGE {f(m11.loc['ERA5-Land QM', 'KGE'], 2)}.</li>
<li>La corrección arregla la distribución de cada celda, pero no la secuencia mes a mes: la correlación de las anomalías con el Cubo
sigue en {f(m81.loc['ERA5 QM', 'r anomalías mensuales'], 2)}, frente a {f(m81.loc['CHIRPS v2.0', 'r anomalías mensuales'], 2)} de CHIRPS.</li></ul>
</div><div>
<h3>Balance de largo plazo 1981–2010 con cada producto (Budyko celda a celda)</h3>
{tabla(tab_bal, {"P (mm/año)": 0, **{c: 1 for c in tab_bal.columns if c != "P (mm/año)"}})}
<p class='note'>Error = Q estimado / Q observado − 1. Cierre: presa (Puerto Valdivia transferido por áreas). Mismo método del punto 12 del
Trabajo 1, ahora en la grilla del Cubo.</p></div></div>""")

eto_pm, eto_hg = C["ETo PM"]["1981":"2010"].resample("YS").sum().mean(), C["ETo Hargreaves"]["1981":"2010"].resample("YS").sum().mean()
D["eto"] = {"pm": cic["ETo Penman-Monteith"].round(1).tolist(), "hg": cic["ETo Hargreaves"].round(1).tolist(),
            "p": cic["Cubo IDEAM"].round(1).tolist()}
slide("d-eto", "1 · Datos de entrada", "1a · evapotranspiración de referencia",
      f"FAO Penman-Monteith, el método del IDEAM, da {f(eto_pm)} mm/año; Hargreaves, el del Trabajo 1, un 15 % más", f"""
<div class='two fig'><div>
<p>El IDEAM y la UPRA adoptaron <b>FAO Penman-Monteith</b> como método oficial de la ETo en Colombia (Nota técnica IDEAM-METEO/003-2021).
Necesita radiación, humedad y viento; el Cubo trae temperaturas y humedad relativa pero no brillo solar, así que se usa el procedimiento de
FAO-56 para datos faltantes:</p>
<ul class='pts'><li>Radiación solar a partir de Tmax − Tmin (ec. 50, kRs = 0,16, interior).</li>
<li>Presión de vapor real con la humedad relativa media del Cubo (ec. 19).</li>
<li>Viento de 2 m/s y presión atmosférica según la elevación media de cada celda (DEM de 90 m del Trabajo 1).</li></ul>
<p><b>Hargreaves</b> ({f(eto_hg)} mm/año) sólo usa temperatura y radiación extraterrestre. Ambas ETo se prueban en el modelo; la diferencia
pesa poco en una cuenca húmeda, donde la ETR está limitada por energía.</p>
</div><div class='panel'><div class='tshost' id='etoFig' style='height:460px'></div></div></div>""")

# ---- 2. modelo
slide("m-como", "2 · Modelo abcd", "1c · modelo lluvia–escorrentía mensual abcd (Thomas, 1981)",
      "Cuatro parámetros, dos depósitos: el suelo decide cuánto se evapora y el acuífero cuánto tarda en salir", f"""
<div class='two fig'><div>
<p class='eq'>W = P + S<sub>t−1</sub> &nbsp;·&nbsp; Y = (W + b)/(2a) − √[((W + b)/(2a))² − W·b/a]</p>
<p class='eq'>S = Y·e<sup>−ETo/b</sup> &nbsp;·&nbsp; ETR = Y − S</p>
<p class='eq'>Q = (1 − c)(W − Y) + d·G &nbsp;·&nbsp; G = [G<sub>t−1</sub> + c(W − Y)] / (1 + d)</p>
<ul class='pts'><li><b>a</b> (0–1): qué tan pronto se genera escorrentía antes de que el suelo se llene.</li>
<li><b>b</b> (mm): capacidad del suelo más la evapotranspiración del mes; controla cuánta lluvia se queda.</li>
<li><b>c</b> (0–1): fracción del excedente que recarga el acuífero.</li>
<li><b>d</b> (1/mes): rapidez con la que el acuífero se vacía al río.</li></ul>
<p class='note'>Notación de Martinez y Gupta (2010). S (humedad del suelo) es la variable de estado que responde el numeral 3, y G (agua
subterránea) da la memoria de los caudales del numeral 4. Una regresión empírica como la de las diapositivas no tiene ninguna de las dos.</p>
</div><div class='panel'>
<svg viewBox='0 0 420 330' class='esq' role='img' aria-label='Esquema del modelo abcd'>
<defs><marker id='fl' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' markerHeight='7' orient='auto'><path d='M0,0 L10,5 L0,10 z' class='fl'/></marker></defs>
<text x='150' y='22' class='lb'>P (lluvia)</text><line x1='170' y1='28' x2='170' y2='70' class='ar' marker-end='url(#fl)'/>
<text x='255' y='52' class='lb'>ETR</text><line x1='230' y1='95' x2='265' y2='60' class='ar' marker-end='url(#fl)'/>
<rect x='100' y='72' width='140' height='80' rx='10' class='bx'/><text x='170' y='108' text-anchor='middle' class='lb'>Suelo · S</text>
<text x='170' y='128' text-anchor='middle' class='mu'>a, b</text>
<line x1='240' y1='135' x2='340' y2='135' class='ar' marker-end='url(#fl)'/><text x='250' y='127' class='mu'>(1 − c)(W − Y)</text>
<line x1='170' y1='152' x2='170' y2='205' class='ar' marker-end='url(#fl)'/><text x='178' y='185' class='mu'>c(W − Y)</text>
<rect x='100' y='207' width='140' height='80' rx='10' class='bx'/><text x='170' y='243' text-anchor='middle' class='lb'>Acuífero · G</text>
<text x='170' y='263' text-anchor='middle' class='mu'>d</text>
<line x1='240' y1='247' x2='340' y2='247' class='ar' marker-end='url(#fl)'/><text x='262' y='240' class='mu'>d·G</text>
<rect x='342' y='110' width='66' height='160' rx='10' class='bx q'/><text x='375' y='195' text-anchor='middle' class='lb'>Q</text>
</svg></div></div>""")

pr_txt = ""
if final["tipo"] == "regionalizado":
    p0 = par[(par.producto == final["producto"]) & (par.ETo == final["eto"])].iloc[0]
    pr_txt = (f"<p>Parámetros comunes calibrados: a = {f(p0.a, 3)}, c = {f(p0.c, 2)}, d = {f(p0.d, 3)}/mes; b entre "
              f"{f(min(p0[c] for c in p0.index if c.startswith('b ')))} y {f(max(p0[c] for c in p0.index if c.startswith('b ')))} mm según la unidad.</p>")
slide("m-unidades", "2 · Modelo abcd", "1c · semidistribución y calibración multisitio",
      "Diez unidades entre estaciones del cauce principal, cada celda de 0,1° con su propia lluvia y ETo", f"""
<div class='two even'><div>
<p>Las unidades son las <b>áreas incrementales</b> entre las estaciones del Cauca (las mismas áreas de drenaje del Trabajo 1). Cada celda
del Cubo se simula con su lluvia y su ETo; el caudal en cada estación es la suma de lo que generan las unidades aguas arriba (con paso
mensual, el tiempo de viaje del agua, de días, no importa).</p>
<p><b>Calibración multisitio.</b> Objetivo: KGE en 1982–2005; validación en 2006–2023 (en la presa, hasta 2017: después Puerto Valdivia
mide el caudal regulado por el embalse). Optimización por evolución diferencial.</p>
<ul class='pts'><li><b>Secuencial</b>: 4 parámetros por unidad, de aguas arriba hacia abajo. Ajusta bien, pero deja parámetros en los límites del
rango: las unidades pequeñas absorben el error de las de arriba.</li>
<li><b>Simultánea regionalizada</b>: a, c y d comunes y b propio de cada unidad (14 parámetros), ajustados a la vez para el KGE medio de las
diez estaciones. Es el modelo final: mejor validación y parámetros con sentido físico (tres unidades conservan b en el límite de 3000 mm, señal de que allí la lluvia del Cubo sobra frente al caudal observado).</li></ul>
{pr_txt}
<p class='note'>Modelo final: {html.escape(modelo_final)}, P del {html.escape(final['producto'])}, ETo de {html.escape(final['eto'])}.</p>
</div><div class='panel'>{fig(R2 / '07_figuras' / 'mapa_unidades.png', 'unidades', 'Unidades del modelo y estaciones')}</div></div>""")

slide("m-desemp", "2 · Modelo abcd", "1c · desempeño por estación",
      f"El modelo reproduce los caudales mensuales en las diez estaciones: KGE medio de {f(kv_med, 2)} en la validación", f"""
<div class='two fig'><div>
<p>El desempeño se sostiene fuera del periodo de calibración en casi todas las estaciones. Las dos más débiles son las de aguas arriba:</p>
<ul class='pts'><li><b>La Balsa</b>: está aguas abajo del embalse de Salvajina (desde 1985), que regula el caudal mes a mes, y el modelo no
lo representa.</li><li><b>Juanchito</b>: recibe esa misma regulación y la menor cobertura de datos de validación.</li></ul>
<p>Desde La Virginia hacia abajo el KGE de validación está entre 0,76 y 0,92, y en la presa llega a 0,92: es la parte de la cuenca que más aporta.</p>
<p class='note'>KGE ≥ 0,75 suele considerarse bueno para caudales mensuales. La validación usa sólo los meses con dato observado.</p>
</div><div class='panel'>{fig(R2 / '07_figuras' / 'fig_kge_estaciones.png', 'kge_estaciones', 'KGE por estación')}</div></div>""")

slide("m-serie", "2 · Modelo abcd", "1c · caudales observados y simulados",
      "Las sequías de El Niño (1992, 1998, 2010, 2015–16) y las crecientes de La Niña (1999, 2008, 2010–11) quedan en su lugar", f"""
{chips('serieEst', [(e, e) for e in ['La Virginia', 'La Pintada', 'Bolombolo', 'Cañafisto', 'Presa', 'La Balsa']])}
<div class='panel'><div class='tshost' id='serieFig' style='height:520px'></div></div>
<p class='note'>Caudal medio mensual (m³/s). La banda gris es la calibración (1982–2005). En la presa el observado termina en 2017.</p>""")

slide("m-emp", "2 · Modelo abcd", "1c · ¿qué combinación sirve para un sistema operativo?",
      "La ecuación empírica sin memoria explica poco; con el caudal del mes anterior se acerca al abcd, que además da el estado del suelo", f"""
<div class='two fig'><div>
<p>La ecuación de las diapositivas, Q = α·(P − ETR) + β con ETR de Budyko mensual, sólo usa la lluvia del mes y alcanza un KGE de validación
de {f(D['emp']['kge'][0], 2)} en la presa. Agregar el caudal del mes anterior, Q(t−1), la lleva a {f(D['emp']['kge'][1], 2)}: la memoria de la
cuenca es lo que le faltaba. El abcd tiene esa memoria de forma física (suelo y acuífero) y no necesita conocer el caudal observado para
simular, así que puede correrse con escenarios de lluvia o de clima futuro.</p>
{tabla(tab_mod, {c: 2 for c in tab_mod.columns})}
</div><div class='panel'>{fig(R2 / '07_figuras' / 'fig_kge_modelos_presa.png', 'kge_modelos', 'KGE de los modelos en la presa')}
<div class='callout teal'><b>Respuesta.</b> Para un sistema operativo mensual: modelo abcd semidistribuido con la lluvia del Cubo del IDEAM
(o CHIRPS v2.0, casi igual de bueno y disponible en tiempo casi real), ETo de Hargreaves y calibración multisitio regionalizada. ERA5 sólo sirve corregido, y aun
así queda por debajo de los productos con estaciones.</div></div></div>""")

# ---- 3. ENSO y lluvia
slide("p-mapas", "3 · ENSO y lluvia", "2 · anomalías estandarizadas de la precipitación · compuestos 1981–2023",
      "El Niño seca casi toda la cuenca en diciembre–febrero y junio–agosto; marzo–mayo es la temporada menos sensible", f"""
<div class='two fig'><div>
{chips('pMapa', [('nino', 'El Niño'), ('nina', 'La Niña')])}
<p>z = (P del trimestre − media) / desviación estándar, por celda y trimestre (base 1981–2010). Cada mapa es el promedio de z en los
trimestres de la fase, según la definición del CPC: ONI ≥ +0,5 °C (El Niño) o ≤ −0,5 °C (La Niña) durante al menos cinco trimestres
seguidos.</p>
<p class='tryit'>compara las filas del Cubo y CHIRPS con las de ERA5: el promedio de la cuenca se parece, el dibujo no.</p>
<p class='note'>Rojo = más seco que lo normal; azul = más húmedo. z̄ es el promedio de la cuenca.</p>
</div><div class='panel'><div id='pMapaHost'>{fig(R2 / '05_enso_P' / 'mapas_compuesto_nino.png', 'enso_P_nino', 'Compuestos El Niño')}</div>
<div id='pMapaHost2' hidden>{fig(R2 / '05_enso_P' / 'mapas_compuesto_nina.png', 'enso_P_nina', 'Compuestos La Niña')}</div></div></div>""")

slide("p-cuenca", "3 · ENSO y lluvia", "2 · consistencia entre productos",
      "Todos los productos coinciden en el signo y el tamaño de la anomalía de la cuenca; sólo los de estaciones coinciden en dónde ocurre", f"""
<div class='two fig'><div>
<div class='panel'>{fig(R2 / '07_figuras' / 'fig_enso_P_productos.png', 'enso_P_productos', 'z de la cuenca por producto')}</div>
<h3>Correlación entre el ONI y z de la cuenca, por trimestre</h3>
{tabla(tab_oni, {c: 2 for c in TR})}
</div><div>
<h3>Correlación espacial de cada compuesto con el del Cubo</h3>
{tabla(tab_cons, {c: 2 for c in tab_cons.columns})}
<ul class='pts'><li><b>Señal de la cuenca</b>: en DEF todos los productos dan z ≈ −0,8 en El Niño, y la correlación con el ONI llega a −0,81.
En JJA La Niña es la anomalía más grande (z ≈ +1,1).</li>
<li><b>Patrón espacial</b>: CHIRPS se parece al Cubo (r de 0,2 a 0,6); ERA5 y ERA5-Land no (r cercano a 0 o negativo). El mapeo de cuantiles
corrige la media de cada celda, no la respuesta espacial al ENSO.</li>
<li><b>MAM</b>: es el único trimestre en que los reanálisis no ven señal de El Niño.</li></ul></div></div>""")

# ---- 4. suelo
s_def = ts[(ts.trimestre == "DEF") & (ts.fase == "El Niño")].iloc[0]
s_mam = ts[(ts.trimestre == "MAM") & (ts.fase == "El Niño")].iloc[0]
slide("s-mapas", "4 · Humedad del suelo", "3 · humedad del suelo simulada (S del abcd)",
      "Durante El Niño el suelo se seca en toda la cuenca, y más que la lluvia: en marzo–mayo sigue seco aunque ya llueva casi normal", f"""
<div class='two fig'><div>
<div class='panel'>{fig(R2 / '07_figuras' / 'fig_suelo_lluvia_enso.png', 'suelo_lluvia', 'Suelo frente a lluvia en El Niño y La Niña')}</div>
<ul class='pts'><li><b>Magnitud</b>: en DEF de El Niño, z de la lluvia = {f(s_def['z P cuenca'], 2)} y z del suelo = {f(s_def['z S cuenca'], 2)}.
El suelo amplifica la anomalía porque acumula varios meses de déficit.</li>
<li><b>Persistencia</b>: en MAM la lluvia ya casi no tiene señal (z = {f(s_mam['z P cuenca'], 2)}) pero el suelo sigue en
{f(s_mam['z S cuenca'], 2)}: arrastra la sequía de diciembre–febrero.</li>
<li><b>Extensión</b>: en todos los trimestres de El Niño más del 96 % del área queda con el suelo por debajo de lo normal. La Niña da la
imagen opuesta, con anomalías algo menores.</li></ul>
</div><div class='panel'>{fig(R2 / '06_enso_suelo_Q' / 'mapas_suelo_enso.png', 'suelo_enso', 'Humedad del suelo en El Niño y La Niña')}</div></div>""")

slide("s-memoria", "4 · Humedad del suelo", "3 · memoria del suelo",
      "El suelo recuerda la lluvia de los meses anteriores: por eso responde al ENSO con más fuerza y durante más tiempo que la lluvia", f"""
<div class='two fig'><div>
<div class='panel'><div class='tshost' id='anomFig' style='height:460px'></div></div>
<p class='note'>Anomalías mensuales estandarizadas de la cuenca (P y Q, media móvil de 3 meses) y ONI. Q es el observado en la presa.</p>
</div><div>
{fig(R2 / '06_enso_suelo_Q' / 'mapas_memoria_suelo.png', 'memoria_suelo', 'Memoria y rezago del suelo')}
<p>La autocorrelación de un mes de las anomalías del suelo es {f(rz.loc['S', 'memoria r1'], 2)} (la de la lluvia, {f(rz.loc['P', 'memoria r1'], 2)}):
un mes seco deja el suelo seco el mes siguiente. La correlación del ONI con el suelo es máxima con 2–3 meses de rezago
({f(min(D['rez']['S']), 2)}), mientras que con la lluvia es máxima en el mismo mes.</p></div></div>""")

# ---- 5. caudales
slide("q-comp", "5 · Caudales", "4 · anomalías estandarizadas de los caudales, observados y simulados",
      "Los caudales caen en todos los trimestres de El Niño, y la mayor reducción en la presa llega en diciembre–febrero", f"""
<div class='full'><div class='cols2txt'>
<p>Barras: z del caudal observado; puntos: z del simulado por el modelo abcd con la lluvia del Cubo. Mismas fases y trimestres del numeral 2.</p>
<ul class='pts'><li>En la presa, El Niño baja el caudal en DEF (z = {f(D['enso_q']['Presa']['El Niño']['obs'][0], 2)}) y en MAM
({f(D['enso_q']['Presa']['El Niño']['obs'][1], 2)}), aunque la lluvia de MAM casi no cambie: es el suelo seco y el acuífero vacío.</li>
<li>El modelo reproduce el signo y el orden de magnitud en todas las combinaciones de fase y trimestre; subestima el extremo de El Niño en la
presa en DEF.</li></ul>
<p class='note'>En La Virginia la señal es más pareja entre trimestres que en la presa.</p>
</div><div class='panel'>{fig(R2 / '07_figuras' / 'fig_caudales_enso.png', 'caudales_enso', 'Caudales observados y simulados en El Niño y La Niña')}</div></div>""")

slide("q-ciclo", "5 · Caudales", "4 · ciclo anual en años El Niño, neutros y La Niña",
      "El Niño no cambia la forma del ciclo bimodal: lo baja entero, y más en la temporada seca de comienzo de año", f"""
<div class='two fig'><div>
{chips('cEst', [(e, e) for e in ['Presa', 'Bolombolo', 'La Virginia']])}
<p>Caudal medio de cada mes en los meses de cada fase (la fase de cada mes según el ONI del trimestre centrado en él). Líneas continuas:
observado; punteadas: simulado. El modelo reproduce el ciclo en las tres fases, lo que valida su respuesta al ENSO en el ciclo anual,
como pide el numeral 4.</p>
</div><div class='panel'><div class='tshost' id='cFig' style='height:500px'></div></div></div>""")

slide("q-rez", "5 · Caudales", "4 · lluvia, suelo y caudal: almacenamiento y memoria",
      "La señal del Pacífico llega a la lluvia de inmediato y a los caudales con 1–2 meses de rezago, a través del suelo", f"""
<div class='two fig'><div>
<div class='panel'><div class='tshost' id='rezFig' style='height:460px'></div></div>
</div><div>
<ul class='pts'><li><b>ONI → lluvia</b>: correlación máxima en el mismo mes ({f(D['rez']['P'][0], 2)}) y decae en pocos meses.</li>
<li><b>ONI → suelo y caudal</b>: correlación más fuerte ({f(min(D['rez']['S']), 2)} y {f(min(D['rez']['Q obs presa']), 2)}) y máxima con
2 meses de rezago.</li>
<li><b>Lluvia → caudal</b>: la anomalía de lluvia de un mes sigue correlacionada con el caudal 2–3 meses después (0,55 con 2 meses).</li>
<li>La cuenca actúa como un filtro: el suelo y el acuífero acumulan los meses secos, de modo que los caudales responden al ENSO con más
fuerza que la lluvia y con algunos meses de retraso. Ese rezago es aprovechable: el estado del ENSO y la humedad del suelo de hoy anticipan
los caudales de los próximos meses.</li></ul></div></div>""")

# ---- 6. técnicas para decisiones de generación (numeral 5)
PRN, EOFD, FOU = R2 / "08_pronostico", R2 / "09_eof", R2 / "10_fourier"
pr_s = json.loads((PRN / "sitio.json").read_text(encoding="utf-8"))
D["knn"] = pr_s["ejemplos"]
D["prob"] = pr_s["prob"]
_pb = pd.DataFrame({k: v for k, v in pr_s["prob"].items() if k != "t"}, index=pd.to_datetime(pr_s["prob"]["t"]))
_pb = _pb.reindex(pd.date_range(_pb.index[0], _pb.index[-1], freq="MS"))   # meses sin dato → huecos en la gráfica
D["prob"] = {"t": _pb.index.strftime("%Y-%m").tolist(), **{k: _pb[k].tolist() for k in _pb.columns}}
KK = pr_s["K"]
mq3 = pd.read_csv(PRN / "metricas_Q3.csv", index_col=0)
mpb = pd.read_csv(PRN / "metricas_probabilidad.csv", index_col=0)
hzm = pd.read_csv(PRN / "horizonte_mensual.csv", index_col=0)
alr = pd.read_csv(PRN / "alertas.csv")
cof = pd.read_csv(PRN / "coeficientes_logistica.csv")
eofr = pd.read_csv(EOFD / "eof_resumen.csv", index_col=0)
D["eof"] = json.loads((EOFD / "sitio.json").read_text(encoding="utf-8"))
fbt = pd.read_csv(FOU / "bandas_y_memoria.csv", index_col=0)
fcg = pd.read_csv(FOU / "coherencia_ganancia.csv", index_col=0)
FG = R2 / "07_figuras"
kq = f"KNN (k = {KK})"
LS = "Logística · ONI + suelo"
or_s = float(cof[(cof.modelo == LS) & (cof.variable == "S")]["razón de odds por 1 σ"].iloc[0])
or_o1 = float(cof[(cof.modelo == "Logística · ONI") & (cof.variable == "ONI")]["razón de odds por 1 σ"].iloc[0])
or_o2 = float(cof[(cof.modelo == LS) & (cof.variable == "ONI")]["razón de odds por 1 σ"].iloc[0])
alS = alr[alr["método"] == LS].set_index("nivel")
alK = alr[alr["método"] == kq].set_index("nivel")
VE, AM, RO = "Verde (< 20 %)", "Amarillo (20–50 %)", "Rojo (≥ 50 %)"
FRQ, PCT = "frecuencia observada del trimestre seco (%)", "% de los meses"

slide("g-intro", "6 · Decisiones de generación", "5 · técnicas de análisis de datos para la operación",
      "¿Qué puede saber hoy el operador de Hidroituango sobre el agua de los próximos meses?", f"""
<p class='lead'>Los numerales 2 a 4 mostraron que el ENSO se adelanta unos dos meses a los caudales y que el suelo y el acuífero guardan
esa señal. Aquí se convierte en información para decidir: cuánta agua llegará, con qué confianza, y cuándo encender una alerta.</p>
<div class='cards3'>
<button class='card lift pick' type='button' data-go='g-knn'><h4>KNN · años análogos</h4><p>Pronóstico del aporte a 1–6 meses como
conjunto de trayectorias: mediana, intervalo y su confiabilidad verificada.</p></button>
<button class='card lift pick' type='button' data-go='g-logit'><h4>Regresión logística</h4><p>Probabilidad de que los próximos tres meses
sean secos, comparada con la que dan los análogos.</p></button>
<button class='card lift pick' type='button' data-go='g-alertas'><h4>Umbrales de alerta</h4><p>Verde, amarillo y rojo: cuántas veces
acertó cada nivel entre 1982 y 2017.</p></button>
<button class='card lift pick' type='button' data-go='g-2026'><h4>Pronóstico nov 2026 – abr 2027</h4><p>Los dos métodos aplicados al El Niño
en curso: alerta roja.</p></button>
<button class='card lift pick' type='button' data-go='g-eof'><h4>Funciones ortogonales empíricas</h4><p>¿Es el ENSO el modo principal de
variabilidad de la cuenca, y lo ven igual todos los productos?</p></button>
<button class='card lift pick' type='button' data-go='g-fourier'><h4>Transformada de Fourier</h4><p>La cuenca como filtro: por qué los
caudales responden al ENSO más que la lluvia.</p></button>
<button class='card lift pick' type='button' data-go='c-qdm'><h4>Mapeo de cuantiles con deltas (QDM)</h4><p>Corrección de los modelos CMIP6 para las proyecciones de la sección 7.</p></button>
</div>
<p class='note'>Todo se evalúa con validación cruzada dejando un año fuera (1982–2017, caudal observado en la presa): cada pronóstico se
hace sin conocer su año ni el semestre anterior y el siguiente.</p>""", g="g")

slide("g-knn", "6 · Decisiones de generación", "5 · KNN · pronóstico estacional con años análogos",
      "Se buscan en la historia los meses que más se parecen a hoy y se mira qué pasó después", f"""
<div class='two fig'><div>
<p><b>Estado de hoy</b> (fin del mes t): ONI del trimestre que acaba de terminar, su cambio en 3 meses, y la humedad del suelo S y el
agua subterránea G de la cuenca según el modelo abcd. Los cuatro, estandarizados por mes calendario.</p>
<p><b>Análogos</b>: los {KK} meses históricos más cercanos (distancia euclidiana), del mismo mes calendario ± 1. Lo que ocurrió en los 6 meses
siguientes de cada uno, como anomalía de su mes, se lleva a la climatología de hoy: son {KK} trayectorias posibles. k = {KK} minimiza el
CRPS en la validación cruzada.</p>
{chips('knnEj', [(k, k) for k in D['knn']])}
<p class='tryit'>mira agosto de 1997 y de 2015, al comienzo de los dos El Niño más fuertes, y compáralos con agosto de 2010 (La Niña).</p>
<p class='note' id='knnTxt'></p>
</div><div class='panel'><div class='tshost' id='knnFig' style='height:500px'></div></div></div>""", g="g")

cob = mq3.loc[kq, "Cobertura del intervalo 80 % (%)"]
anc = 100 * (1 - mq3.loc[kq, "Ancho medio del intervalo 80 % (m³/s)"] / mq3.loc["Climatología", "Ancho medio del intervalo 80 % (m³/s)"])
slide("g-knn-hab", "6 · Decisiones de generación", "5 · KNN · habilidad y confiabilidad",
      f"Los análogos le ganan a la persistencia desde el segundo mes y reducen el error de la climatología en un {f(100 * mq3.loc[kq, 'CRPSS'])} %", f"""
<div class='two fig'><div>
<ul class='pts'><li><b>Aporte de los próximos 3 meses</b>: NSE de la mediana {f(mq3.loc[kq, 'NSE de la mediana'], 2)}, frente a
{f(mq3.loc['Persistencia', 'NSE de la mediana'], 2)} de la persistencia y {f(mq3.loc['Climatología', 'NSE de la mediana'], 2)} de la climatología.</li>
<li><b>Mes a mes</b>: a 1 mes empata con la persistencia (NSE {f(hzm.loc[1, 'NSE KNN'], 2)}); a 6 meses conserva {f(hzm.loc[6, 'NSE KNN'], 2)}
cuando la persistencia ya cayó a {f(hzm.loc[6, 'NSE persistencia'], 2)}: es la memoria del suelo y del ENSO.</li>
<li><b>Confiabilidad</b>: el intervalo nominal del 80 % contiene al observado el {f(cob)} % de las veces y es un {f(anc)} % más angosto que el
de la climatología. Para operar debe leerse como un intervalo del ≈ {f(cob)} %: los análogos son algo optimistas.</li></ul>
{tabla(mq3, {"NSE de la mediana": 2, "CRPS (m³/s)": 0, "CRPSS": 2, "Cobertura del intervalo 80 % (%)": 0, "Ancho medio del intervalo 80 % (m³/s)": 0})}
<p class='note'>CRPSS: mejora del CRPS (error de toda la distribución) frente a la climatología. En el Trabajo 1, el KNN diario a 10 días
apenas igualaba a la persistencia; a escala mensual sí hay información aprovechable.</p>
</div><div class='panel'>{fig(FG / 'fig_knn_horizonte.png', 'knn_horizonte', 'Habilidad del KNN por anticipación')}</div></div>""", g="g")

slide("g-logit", "6 · Decisiones de generación", "5 · regresión logística · probabilidad de un trimestre seco",
      "El estado del suelo dice más que el ONI: con los dos, la probabilidad de un trimestre seco es confiable", f"""
<div class='stackfig'><div class='txtcols'>
<p><b>Evento</b>: el aporte medio de los tres meses siguientes queda por debajo de su percentil 20 (para ese mes de emisión).
P = 1 / (1 + e<sup>−(β₀ + β·x)</sup>), ajustada por máxima verosimilitud.</p>
<ul class='pts'><li><b>Sólo ONI</b>: cada desviación estándar del ONI multiplica los odds de un trimestre seco por {f(or_o1, 1)}.</li>
<li><b>ONI y suelo</b>: domina el suelo. Un suelo una desviación estándar más seco multiplica los odds por {f(1 / or_s, 1)} y el ONI queda en
{f(or_o2, 1)}: S ya integra el ENSO de los meses anteriores.</li>
<li><b>Frente a los análogos</b>: la logística con ONI y suelo y el KNN discriminan igual (AUC {f(mpb.loc[LS, 'AUC (ROC)'], 2)} y
{f(mpb.loc[kq, 'AUC (ROC)'], 2)}); la logística está mejor calibrada (BSS {f(mpb.loc[LS, 'BSS'], 2)} frente a {f(mpb.loc[kq, 'BSS'], 2)}).
No son excluyentes: si las dos coinciden, la alerta es más firme.</li></ul>
{tabla(mpb, {"Brier": 3, "BSS": 2, "AUC (ROC)": 2})}
</div><div class='panel'>{fig(FG / 'fig_prob_trimestre_seco.png', 'prob_seco', 'Regresión logística, confiabilidad y ROC')}</div></div>""", g="g")

orden_n = [VE, AM, RO]
t_f = alr.pivot(index="nivel", columns="método", values=FRQ).loc[orden_n]
t_p = alr.pivot(index="nivel", columns="método", values=PCT).loc[orden_n]
tal = pd.DataFrame({m_: [f"{f(t_f.loc[n, m_])} % ({f(t_p.loc[n, m_])} % de los meses)" for n in orden_n]
                    for m_ in [LS, kq, "Logística · ONI"]}, index=orden_n).T
tal.index.name = "trimestre seco observado"
slide("g-alertas", "6 · Decisiones de generación", "5 · umbrales de alerta",
      f"Con alerta roja el trimestre fue seco el {f(alS.loc[RO, FRQ])} % de las veces; con verde, sólo el {f(alS.loc[VE, FRQ])} %", f"""
{chips('alMet', [('logS', LS), ('knn', kq), ('log', 'Logística · ONI')])}
<div class='panel'><div class='tshost' id='alFig' style='height:440px'></div></div>
<div class='two even'><div>
<ul class='pts'><li><b>Verde</b> (P &lt; 20 %): operación normal; el {f(alS.loc[VE, PCT])} % de los meses.</li>
<li><b>Amarillo</b> (20–50 %): vigilar el embalse; el trimestre fue seco {f(alS.loc[AM, FRQ])} % de las veces.</li>
<li><b>Rojo</b> (≥ 50 %): conservar agua; el {f(alS.loc[RO, PCT])} % de los meses, concentrados en los El Niño de 1991–92, 1997–98, 2009–10
y 2015–16.</li></ul>
<p class='note'>Barras: trimestres que sí fueron secos. Probabilidades de la validación cruzada (cada año sin conocerse a sí mismo). Con el KNN
el rojo es más raro ({f(alK.loc[RO, PCT])} % de los meses) pero acierta el {f(alK.loc[RO, FRQ])} %.</p>
</div><div>{tabla(tal)}</div></div>""", g="g")

p26 = json.loads((R2 / "12_pronostico_2026" / "sitio.json").read_text(encoding="utf-8"))
D["p26"] = p26
pr26 = pd.read_csv(R2 / "12_pronostico_2026" / "pronostico_nov2026_abr2027.csv")
an26 = pd.read_csv(R2 / "12_pronostico_2026" / "analogos.csv")
sens26 = p26["sensibilidad octubre"]
t26 = pr26.set_index("mes")[["mediana (m³/s)", "p10 (m³/s)", "p90 (m³/s)", "climatología, mediana (m³/s)", "mediana frente a la climatología (%)"]]
t26.index.name = "mes pronosticado"
slide("g-2026", "6 · Decisiones de generación", "5 · aplicación · pronóstico emitido al final de octubre de 2026",
      f"Con El Niño más fuerte del registro (ONI ASO = +{f(p26['ONI ASO 2026'], 2)} °C), los análogos anticipan una temporada seca de enero–abril de 2027 entre 34 % y 41 % por debajo de lo normal: alerta roja", f"""
<div class='two fig'><div>
{chips('p26Vista', [('pron', 'Pronóstico nov 2026 – abr 2027'), ('ver', 'Estado inicial frente a XM')])}
<p><b>Estado inicial.</b> El modelo abcd se extendió hasta octubre de 2026 con CHIRPS v2.0 igualado al Cubo (julio–septiembre de 2026 llovió
el {f(p26['lluvia jul-sep 2026 (% de lo normal)'])} % de lo normal) y ETo climatológica. CHIRPS de octubre aún no se publica: su lluvia se ajustó
para que el caudal simulado de octubre tenga la anomalía de los aportes de XM del 1 al 23 de octubre ({f(p26['anomalía XM octubre (%)'])} %), y
resultó del {f(p26['lluvia octubre (% de la normal)'])} % de la normal. Desde 2022 el modelo sigue las anomalías de XM con r = {f(p26['r anomalías verificación XM'], 2)}.</p>
<ul class='pts'><li><b>Predictores</b>: ONI = +{f(p26['ONI disponible (predictor)'], 2)} °C (z = +2,9, fuera del rango histórico); suelo z = {f(p26['S z'], 2)}; acuífero z = {f(p26['G z'], 2)}.</li>
<li><b>Trimestre noviembre–enero</b>: P(seco) = {f(100 * p26['P(seco) logística ONI+S'])} % con la regresión logística y {f(100 * p26['P(seco) KNN'])} % con los análogos: <b>alerta roja</b> con los dos métodos.</li>
<li><b>Sensibilidad</b>: si octubre hubiera sido tan seco como julio–septiembre, el suelo estaría en z = {f(sens26['a']['S z'], 1)} y P(seco) subiría a {f(100 * sens26['a']['P(seco) logística'])} %; con
octubre normal, {f(100 * sens26['b']['P(seco) logística'])} %. El dato de XM de octubre es el que más pesa en el pronóstico.</li></ul>
<p class='note'>Análogos más cercanos: {', '.join(an26['mes análogo'].head(5))}. Ningún análogo tiene un ONI tan alto: el pronóstico probablemente
subestima la sequía. Caudales en la escala IDEAM (Puerto Valdivia transferido), cuya media es 10–30 % mayor que la de XM.</p>
{tabla(t26, {c: 0 for c in t26.columns})}
</div><div class='panel'><div class='tshost' id='p26Fig' style='height:520px'></div></div></div>""", g="g")

e1 = eofr.loc["Cubo IDEAM"]
slide("g-eof", "6 · Decisiones de generación", "5 · EOF · modos de variabilidad de la lluvia y del suelo",
      f"El primer modo es toda la cuenca a la vez ({f(e1['varianza EOF1 (%)'])} % de la varianza) y es el ENSO; ERA5 muestra un segundo modo que las estaciones no ven", f"""
<div class='two fig'><div>
<p>Anomalías trimestrales móviles de cada celda, ponderadas por área; EOF por descomposición en valores singulares. Los mapas son la
correlación entre la componente principal (CP) y cada celda.</p>
<ul class='pts'><li><b>EOF1</b>: un solo signo en toda la cuenca, con {f(eofr['varianza EOF1 (%)'].min())}–{f(eofr['varianza EOF1 (%)'].max())} %
de la varianza según el campo. Su CP se correlaciona con el ONI: {f(e1['r(CP1, ONI) máxima'], 2)} en el Cubo y
{f(eofr.loc['Suelo S (abcd)', 'r(CP1, ONI) máxima'], 2)} en el suelo. El ENSO aparece como modo dominante sin haberlo supuesto.</li>
<li><b>EOF2</b>: en el Cubo explica {f(e1['varianza EOF2 (%)'])} % y no se separa de la EOF3 (regla de North): no hay un segundo modo robusto.
CHIRPS muestra un contraste débil norte (Antioquia)–sur (Valle). ERA5-Land y ERA5 corregidos le dan {f(eofr.loc['ERA5-Land QM', 'varianza EOF2 (%)'])} y
{f(eofr.loc['ERA5 QM', 'varianza EOF2 (%)'])} %, con manchas aisladas y una CP opuesta a la del Cubo (r = {f(eofr.loc['ERA5 QM', 'r temporal CP2 con el Cubo'], 2)}).</li>
<li><b>Consistencia</b>: la CP1 de CHIRPS v2.0 sigue a la del Cubo (r = {f(eofr.loc['CHIRPS v2.0', 'r temporal CP1 con el Cubo'], 2)}); la de ERA5
corregido, menos ({f(eofr.loc['ERA5 QM', 'r temporal CP1 con el Cubo'], 2)}).</li></ul>
</div><div class='panel'>{fig(FG / 'fig_eof_mapas.png', 'eof_mapas', 'EOF de la lluvia y del suelo')}</div></div>
<div class='panel'><div class='tshost' id='eofFig' style='height:380px'></div></div>
<p class='note'>Componente principal 1 de la lluvia (Cubo) y del suelo frente al ONI, con el eje del ONI invertido: cuando el ONI sube, la cuenca se seca.</p>""", g="g")

bP, bQ = fbt.loc["Lluvia P (Cubo)"], fbt.loc["Caudal observado (presa)"]
CS = "Caudal simulado (presa)"
tfb = fbt[["r(1 mes)", "escala integral de tiempo (meses)", "varianza < 1 año (%)", "varianza 2–7 años, ENSO (%)", "varianza > 7 años (%)"]]
slide("g-fourier", "6 · Decisiones de generación", "5 · transformada de Fourier · la cuenca como filtro",
      f"La lluvia pone el {f(bP['varianza 2–7 años, ENSO (%)'])} % de su varianza en la banda del ENSO; el caudal, el {f(bQ['varianza 2–7 años, ENSO (%)'])} %", f"""
<div class='stackfig'><div class='txtcols'>
<p>Densidad espectral de las anomalías mensuales (Welch: FFT en segmentos de 128 meses), ganancia de cada variable frente a la lluvia y
coherencia con el ONI.</p>
<ul class='pts'><li><b>Filtro pasa-bajos</b>: el suelo, el acuífero y el caudal amortiguan las fluctuaciones de menos de un año (ganancia ≈
{f(fcg.loc[CS, 'ganancia media respecto a la lluvia, < 1 año'], 1)}) y refuerzan las de 2–7 años (≈ {f(fcg.loc[CS, 'ganancia media respecto a la lluvia, 2–7 años'], 1)}).</li>
<li><b>Memoria</b>: la escala integral de tiempo es de {f(bP['escala integral de tiempo (meses)'])} meses para la lluvia y de ≈ {f(bQ['escala integral de tiempo (meses)'])}
para el suelo, el acuífero y el caudal.</li>
<li><b>ENSO</b>: la lluvia tiene picos sobre el ruido rojo en {str(bP['picos sobre ruido rojo (años)']).replace('.', ',')} años; en la banda de 2–7 años la coherencia
con el ONI es {f(fcg.loc['Lluvia P (Cubo)', 'coherencia media con el ONI, 2–7 años'], 2)} para la lluvia y {f(fcg.loc['Caudal observado (presa)', 'coherencia media con el ONI, 2–7 años'], 2)}
para el caudal observado (umbral del 95 %: {f(fcg.loc['Caudal observado (presa)', 'nivel 95 %'], 2)}).</li></ul>
<p>Es la conclusión de los rezagos del numeral 4, ahora en frecuencia: la cuenca acumula, y por eso los caudales dependen del ENSO más que la
lluvia que los produce. Esa memoria es la que aprovechan el KNN y la regresión logística.</p>
{tabla(tfb, {"r(1 mes)": 2, "escala integral de tiempo (meses)": 1, "varianza < 1 año (%)": 0, "varianza 2–7 años, ENSO (%)": 0, "varianza > 7 años (%)": 0})}
</div><div class='panel'>{fig(FG / 'fig_fourier.png', 'fourier', 'Espectros, ganancia y coherencia')}</div></div>""", g="g")

# ---- 7. proyecciones CMIP6
CM = R2 / "11_cmip6"
cm_s = json.loads((CM / "sitio.json").read_text(encoding="utf-8"))
D["cmip"] = cm_s
tam = pd.read_csv(CM / "tamizaje_modelos.csv", index_col=0)
cpm = pd.read_csv(CM / "cambios_por_modelo.csv")
cme = pd.read_csv(CM / "cambios_conjunto.csv", header=[0, 1], index_col=[0, 1])
med_ = cme["mediana"]; mn_ = cme["mínimo"]; mx_ = cme["máximo"]
el = list(tam.index[tam.elegido])
t_tam = tam.loc[el, ["familia", "resolución (°)", "r del ciclo", "RMSE del ciclo normalizado", "sesgo (%)"]].copy()
t_tam.index.name = "modelo elegido"
t_c = pd.DataFrame({f"{e} · {p}": {"Temperatura (°C)": med_.loc[(e, p), "ΔT (°C)"], "Lluvia (%)": med_.loc[(e, p), "ΔP (%)"],
                                   "ETo (%)": med_.loc[(e, p), "ΔETo (%)"], "Humedad del suelo (%)": med_.loc[(e, p), "ΔS (%)"],
                                   "Caudal medio en la presa (%)": med_.loc[(e, p), "ΔQ presa (%)"],
                                   "Caudal bajo, percentil 10 (%)": med_.loc[(e, p), "ΔQ10 presa (%)"],
                                   "Trimestres secos (% de los meses)": med_.loc[(e, p), "trimestres secos (%)"]}
                    for e in ["SSP2-4.5", "SSP5-8.5"] for p in ["2041–2070", "2071–2100"]})
t_c.index.name = "mediana de los 6 modelos"
q85 = (mn_.loc[("SSP5-8.5", "2071–2100"), "ΔQ presa (%)"], mx_.loc[("SSP5-8.5", "2071–2100"), "ΔQ presa (%)"])
cy85 = cm_s["ciclo"]["ssp585"]
dfm = 100 * (np.mean(cy85["2071–2100"]["med"][1:3]) / np.mean(cy85["1981–2010"]["med"][1:3]) - 1)

slide("c-tam", "7 · Proyecciones", "proyecciones CMIP6 · selección de modelos por su ciclo anual",
      "De 28 modelos CMIP6, sólo unos pocos reproducen el régimen bimodal de la cuenca; se eligieron seis, uno por familia", f"""
<div class='two fig'><div>
<p>Se revisaron los 28 modelos del archivo CMIP6 (copia pública de Pangeo) que tienen lluvia, Tmax y Tmin mensuales en el periodo
histórico y en SSP2-4.5 y SSP5-8.5. Para cada uno se calculó el ciclo anual de la lluvia de la cuenca en 1981–2010 y se comparó con el
del Cubo por su forma (correlación y error del ciclo normalizado por su media) y, con la mitad del peso, por su sesgo.</p>
<ul class='pts'><li>Se eligió el mejor de cada familia de modelos (los que comparten componente atmosférico no son independientes), hasta seis.</li>
<li>Los modelos de la familia del Hadley Centre (ACCESS-CM2, UKESM1, HadGEM3) y los CNRM no reproducen el ciclo bimodal (r ≤ 0,35).</li>
<li>El sesgo de la media no descarta un modelo: FGOALS-g3 cuadruplica la lluvia pero tiene la forma correcta del ciclo, y el mapeo de
cuantiles corrige la magnitud.</li></ul>
{tabla(t_tam, {"resolución (°)": 2, "r del ciclo": 2, "RMSE del ciclo normalizado": 2, "sesgo (%)": 0})}
<p class='tryit'>pasa el cursor sobre las líneas grises: son los 22 modelos descartados.</p>
</div><div class='panel'><div class='tshost' id='tamFig' style='height:500px'></div></div></div>""", g="c")

slide("c-qdm", "7 · Proyecciones", "proyecciones CMIP6 · mapeo de cuantiles con deltas (QDM)",
      "La corrección iguala el clima simulado de 1981–2010 al del Cubo y conserva el cambio que proyecta cada modelo en cada cuantil", f"""
<div class='two even'><div>
<p>Cannon et al. (2015) mostraron que el mapeo de cuantiles tradicional puede inflar el cambio proyectado de los extremos. El QDM lo evita:
corrige la distribución del periodo histórico y le suma (o multiplica) el cambio del modelo en ese mismo cuantil.</p>
<p class='eq'>τ = F<sub>modelo, ventana</sub>(x) &nbsp;·&nbsp; Δ = x / F<sub>modelo, 1981–2010</sub><sup>−1</sup>(τ)</p>
<p class='eq'>x<sub>corregido</sub> = F<sub>Cubo, 1981–2010</sub><sup>−1</sup>(τ) · Δ</p>
<ul class='pts'><li>Por celda (las 376 del Cubo) y por mes calendario; ventanas de 30 años centradas en cada década.</li>
<li>Lluvia: Δ multiplicativo; Tmax y Tmin: Δ aditivo.</li>
<li>Con Tmax y Tmin corregidas se calcula la ETo de Hargreaves y todo entra al modelo abcd final, con sus parámetros calibrados.</li>
<li>Los cambios se miden siempre dentro de cada modelo: su futuro frente a su propio 1981–2010 corregido.</li></ul>
</div><div>
{tabla(t_c, {c: 1 for c in t_c.columns})}
<p class='note'>Trimestres secos: meses en que el aporte medio de los tres siguientes queda bajo el percentil 20 de 1981–2010 (la definición de
la alerta del numeral 5); en 1981–2010 es 20 % por construcción.</p></div></div>""", g="c")

slide("c-cambios", "7 · Proyecciones", "proyecciones CMIP6 · cambios en la cuenca",
      f"El caudal medio casi no cambia, pero los estiajes sí: en SSP5-8.5 el caudal bajo cae {f(-med_.loc[('SSP5-8.5', '2071–2100'), 'ΔQ10 presa (%)'])} % y los trimestres secos pasan de 20 % a {f(med_.loc[('SSP5-8.5', '2071–2100'), 'trimestres secos (%)'])} % de los meses", f"""
<div class='stackfig'><div class='txtcols'>
<ul class='pts'><li><b>Temperatura y ETo</b>: los seis modelos coinciden. Hacia 2071–2100 la cuenca se calienta {f(med_.loc[('SSP2-4.5', '2071–2100'), 'ΔT (°C)'], 1)} °C
(SSP2-4.5) o {f(med_.loc[('SSP5-8.5', '2071–2100'), 'ΔT (°C)'], 1)} °C (SSP5-8.5), y la ETo sube {f(med_.loc[('SSP2-4.5', '2071–2100'), 'ΔETo (%)'])} % y {f(med_.loc[('SSP5-8.5', '2071–2100'), 'ΔETo (%)'])} %.</li>
<li><b>Lluvia</b>: la mediana cambia poco ({f(med_.loc[('SSP5-8.5', '2071–2100'), 'ΔP (%)'], 0)} % a {f(med_.loc[('SSP2-4.5', '2041–2070'), 'ΔP (%)'], 0)} %), pero los modelos no coinciden
en el signo: van de {f(mn_.loc[('SSP5-8.5', '2071–2100'), 'ΔP (%)'])} % a {f(mx_.loc[('SSP5-8.5', '2071–2100'), 'ΔP (%)'], 0)} % en SSP5-8.5.</li></ul>
<ul class='pts'><li><b>Caudal medio en la presa</b>: entre {f(med_['ΔQ presa (%)'].min())} % y {f(med_['ΔQ presa (%)'].max(), 0)} % según el escenario y el periodo,
con un rango entre modelos de {f(q85[0])} % a +{f(q85[1])} % en SSP5-8.5 hacia 2071–2100.</li>
<li><b>Estiajes</b>: con más evaporación, los meses secos se vuelven más secos aunque la lluvia anual no cambie. Para la generación, este es
el resultado que importa: la energía firme depende de los meses secos, no del promedio.</li></ul></div>
<div class='panel'>{fig(R2 / '07_figuras' / 'fig_cmip6_cambios.png', 'cmip6_cambios', 'Cambios proyectados por modelo')}</div></div>""", g="c")

slide("c-ciclo", "7 · Proyecciones", "proyecciones CMIP6 · ciclo anual del aporte a Hidroituango",
      f"En SSP5-8.5 la temporada seca de comienzo de año se debilita: el aporte de febrero–marzo baja {f(-dfm)} % hacia 2071–2100", f"""
<div class='two fig'><div>
{chips('cmEsc', [('ssp245', 'SSP2-4.5'), ('ssp585', 'SSP5-8.5')], 1)}
{chips('cmVista', [('ciclo', 'Ciclo anual por periodo'), ('anual', 'Aporte anual 1981–2100')])}
<p>Aporte medio mensual a la presa simulado por el modelo abcd con el clima de cada modelo corregido (mediana de los seis y su rango).</p>
<ul class='pts'><li>El ciclo bimodal se conserva, pero en SSP5-8.5 la lluvia se redistribuye: DEF pierde lluvia y MAM–JJA la ganan, así que
el estiaje de enero–marzo se vuelve más profundo y el pico de mayo más alto.</li>
<li>La banda es ancha: la incertidumbre entre modelos es mayor que el cambio de la mediana. Una planeación robusta debe considerar el rango
y no sólo la mediana.</li></ul>
<p class='tryit'>cambia a «Aporte anual» para ver la media móvil de 10 años de cada modelo.</p>
</div><div class='panel'><div class='tshost' id='cmFig' style='height:500px'></div></div></div>""", g="c")

slide("c-mapas", "7 · Proyecciones", "proyecciones CMIP6 · cambio espacial de la lluvia",
      "Más lluvia en el alto Cauca en junio–agosto y menos en el cañón en diciembre–febrero, con poco acuerdo entre modelos", f"""
<div class='two fig'><div>
<p>Mediana de los seis modelos del cambio de la lluvia en cada celda, por trimestre. Los puntos marcan las celdas donde menos de cinco de los
seis modelos coinciden en el signo: allí el cambio no es robusto.</p>
<ul class='pts'><li>En SSP2-4.5 casi toda la cuenca recibe algo más de lluvia (+2 a +10 %), sobre todo en DEF y MAM.</li>
<li>En SSP5-8.5 hacia 2071–2100 el contraste estacional crece: JJA más húmedo en el alto Cauca y el valle; DEF más seco en el cañón
antioqueño, que es la zona que más aporta a la presa, y SON más seco en la vertiente de la cordillera Central.</li>
<li>El acuerdo entre modelos es bajo en la mayor parte de la cuenca. Lo robusto es el aumento de la ETo, no el signo del cambio de la lluvia.</li></ul>
</div><div class='panel'>{fig(R2 / '07_figuras' / 'fig_cmip6_mapas_P.png', 'cmip6_mapas', 'Cambio proyectado de la lluvia')}</div></div>""", g="c")

# ---- cierre
slide("cierre", "8 · Cierre", "Respuestas", "Qué aprendimos y lo que sigue", f"""
<div class='two even'><div class='stack'>
<div class='card lift'><h4>Datos</h4><p>El Cubo del IDEAM es la mejor referencia de lluvia mensual una vez limpio; CHIRPS v2.0 casi lo iguala.
ERA5 y ERA5-Land necesitan corrección y aun corregidos no capturan bien la variabilidad mes a mes.</p></div>
<div class='card lift'><h4>Modelo</h4><p>El abcd semidistribuido reproduce los caudales de diez estaciones (KGE de validación ≈ {f(kv_med, 2)}); la
ecuación empírica sin memoria no basta.</p></div>
<div class='card lift'><h4>ENSO</h4><p>El Niño seca la lluvia en DEF y JJA, el suelo en todo el año y los caudales con 1–2 meses de rezago; el
suelo prolonga la sequía hasta MAM.</p></div>
<div class='card lift'><h4>Decisiones</h4><p>Con el ONI y el suelo de hoy, los análogos pronostican los próximos meses mejor que la persistencia, y la regresión logística da una alerta de trimestre seco confiable (con rojo, 3 de cada 4 trimestres fueron secos).</p></div>
<div class='card lift'><h4>Clima futuro</h4><p>Con seis modelos CMIP6 corregidos por QDM, el caudal medio en la presa cambia poco, pero en SSP5-8.5 los estiajes se profundizan: más ETo y menos lluvia en diciembre–febrero.</p></div></div>
<div class='panel'><h3>Lo que sigue</h3><ul class='pts'>
<li><b>Pronóstico en tiempo real</b> para noviembre de 2026 – abril de 2027, con El Niño en curso: extender CHIRPS y la ETo hasta hoy para calcular el estado del suelo y emitir el pronóstico de análogos y la alerta.</li>
<li><b>Llevar los pronósticos y las proyecciones a energía</b> con el modelo de operación del embalse (pywr) del Trabajo 1.</li>

</ul>
<p class='note'>Datos: IDEAM (Cubo de datos y caudales), CHIRPS (CHC–UCSB), ERA5 y ERA5-Land (ECMWF–Copernicus), ONI (NOAA CPC).</p>
</div></div>""")

slide("refs", "8 · Cierre", "Referencias", "Referencias", """
<ul class='pts refs'>
<li>Allen, R. G., Pereira, L. S., Raes, D. y Smith, M. (1998). <i>Crop evapotranspiration</i>. FAO Irrigation and Drainage Paper 56, Roma.</li>
<li>Budyko, M. I. (1974). <i>Climate and Life</i>. Academic Press.</li>
<li>Funk, C. et al. (2015). The climate hazards infrared precipitation with stations. <i>Scientific Data</i>, 2, 150066.</li>
<li>Gupta, H. V., Kling, H., Yilmaz, K. K. y Martinez, G. F. (2009). Decomposition of the mean squared error and NSE performance criteria.
<i>Journal of Hydrology</i>, 377, 80–91.</li>
<li>Guzmán, H. et al. (2021). <i>Estimación de la evapotranspiración de referencia (ETo) en Colombia</i>. Nota técnica IDEAM-METEO/003-2021.</li>
<li>Hargreaves, G. H. y Samani, Z. A. (1985). Reference crop evapotranspiration from temperature. <i>Applied Engineering in Agriculture</i>, 1(2), 96–99.</li>
<li>Hersbach, H. et al. (2020). The ERA5 global reanalysis. <i>QJRMS</i>, 146, 1999–2049.</li>
<li>IDEAM (2025). Cubo de datos: precipitación, temperatura y humedad relativa diarias y mensuales 1981–2023 (CDT).</li>
<li>Martinez, G. F. y Gupta, H. V. (2010). Toward improved identification of hydrological models: A diagnostic evaluation of the “abcd”
monthly water balance model for the conterminous United States. <i>Water Resources Research</i>, 46, W08507.</li>
<li>Muñoz-Sabater, J. et al. (2021). ERA5-Land. <i>Earth System Science Data</i>, 13, 4349–4383.</li>
<li>Hersbach, H. (2000). Decomposition of the continuous ranked probability score for ensemble prediction systems. <i>Weather and Forecasting</i>, 15, 559–570.</li>
<li>Lall, U. y Sharma, A. (1996). A nearest neighbor bootstrap for resampling hydrologic time series. <i>Water Resources Research</i>, 32(3), 679–693.</li>
<li>North, G. R., Bell, T. L., Cahalan, R. F. y Moeng, F. J. (1982). Sampling errors in the estimation of empirical orthogonal functions. <i>Monthly Weather Review</i>, 110, 699–706.</li>
<li>Welch, P. (1967). The use of fast Fourier transform for the estimation of power spectra. <i>IEEE Transactions on Audio and Electroacoustics</i>, 15(2), 70–73.</li>
<li>Cannon, A. J., Sobie, S. R. y Murdock, T. Q. (2015). Bias correction of GCM precipitation by quantile mapping: How well do methods preserve changes in quantiles and extremes? <i>Journal of Climate</i>, 28(17), 6938–6959.</li>
<li>Eyring, V. et al. (2016). Overview of the Coupled Model Intercomparison Project Phase 6 (CMIP6) experimental design and organization. <i>Geoscientific Model Development</i>, 9, 1937–1965.</li>
<li>O'Neill, B. C. et al. (2016). The Scenario Model Intercomparison Project (ScenarioMIP) for CMIP6. <i>Geoscientific Model Development</i>, 9, 3461–3482.</li>
<li>Thomas, H. A. (1981). <i>Improved methods for national water assessment</i>. U.S. Water Resources Council, Washington.</li>
</ul>""")

# ============================================================================= página
def limpio(o):
    """NaN e infinitos → null en el JSON."""
    if isinstance(o, dict):
        return {k: limpio(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [limpio(v) for v in o]
    if isinstance(o, (float, np.floating)):
        return None if not np.isfinite(o) else float(o)
    return o



nav = "".join(f"<button type='button' class='mod' data-go='{g}'><span>{n}</span> {t}</button>" for g, n, t in
              [("d-cubo", "1", "Datos"), ("m-como", "2", "Modelo abcd"), ("p-mapas", "3", "ENSO y lluvia"),
               ("s-mapas", "4", "Suelo"), ("q-comp", "5", "Caudales"), ("g-intro", "6", "Decisiones"), ("c-tam", "7", "Proyecciones"), ("cierre", "8", "Cierre")])
css = (SITIO / "estilo_deck.css").read_text(encoding="utf-8") + (SITIO / "estilo_extra.css").read_text(encoding="utf-8")
js = (SITIO / "graficas.js").read_text(encoding="utf-8")
pagina = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Modelación hidrológica Hidroituango</title>
<meta name="description" content="Trabajo 2 de Hidrometeorología: modelo lluvia–escorrentía mensual abcd semidistribuido de la cuenca del Cauca hasta Hidroituango y efectos de El Niño y La Niña sobre la lluvia, la humedad del suelo y los caudales.">
<script>(function(){{var d=document.documentElement,t;try{{t=localStorage.getItem('theme')}}catch(e){{}}if(t)d.dataset.theme=t;}})()</script>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;1,8..60,400&display=swap" rel="stylesheet">
<style>{css}</style>
<script src="assets/plotly-2.35.2.min.js"></script>
</head><body>
<div class="deck">
<header class="top"><a class="back" href="{T1_URL}">← Trabajo 1</a>
<nav class="series" aria-label="Secciones">{nav}</nav><div class="sec" id="secLabel"><b></b></div>
<button class="theme-tg" id="themeTg" type="button" aria-label="Cambiar entre modo claro y oscuro"><svg class="moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg><svg class="sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg><span class="tlbl"></span></button>
</header>
<main id="main">
{''.join(sl)}
</main>
<footer class="nav-bar"><button class="nav" id="prev" type="button" aria-label="Diapositiva anterior">← <span class="navlbl">Anterior</span></button>
<div class="dots" id="dots"></div><span class="counter" id="counter"></span>
<button class="nav" id="next" type="button" aria-label="Diapositiva siguiente"><span class="navlbl">Siguiente</span> →</button></footer>
</div>
<script>const D = {json.dumps(limpio(D), ensure_ascii=False, separators=(',', ':'), allow_nan=False)};</script>
<script>{js}</script>
</body></html>"""
(DOCS / "index.html").write_text(pagina, encoding="utf-8")
print(f"index.html: {len(pagina.encode('utf-8')) / 1e6:.2f} MB, {len(sl)} diapositivas; modelo final {final}")
