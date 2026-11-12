"""
Trabajo 2 · numerales 3 y 4: impactos de El Niño (y La Niña) sobre la humedad del suelo y los caudales.

Con el modelo abcd final (trabajo2/resultados/04_abcd/modelo_final.json: semidistribuido regionalizado, Cubo IDEAM, ETo de Hargreaves):
  3. Humedad del suelo S (mm) por celda: anomalías estandarizadas trimestrales (DEF, MAM, JJA, SON; base 1981–2010), compuestos por
     fase ENSO (las mismas fases del CPC del numeral 2), memoria (autocorrelación de un mes de las anomalías mensuales) y respuesta
     frente a la precipitación (rezago de máxima correlación entre las anomalías mensuales de P y de S).
  4. Caudales observados y simulados en las estaciones: anomalías estandarizadas trimestrales y compuestos ENSO; ciclo anual en años
     El Niño, La Niña y neutros (observado y simulado); rezagos entre las anomalías mensuales de P, S, flujo base G y Q en la cuenca y
     su correlación con el ONI a distintos rezagos.

Salidas: trabajo2/resultados/06_enso_suelo_Q/
"""
import json
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
R2 = ROOT / "trabajo2" / "resultados"
ENT, ABC, EP = R2 / "01_entradas", R2 / "04_abcd", R2 / "05_enso_P"
OUT = R2 / "06_enso_suelo_Q"
OUT.mkdir(parents=True, exist_ok=True)
TRIM = {"DEF": [12, 1, 2], "MAM": [3, 4, 5], "JJA": [6, 7, 8], "SON": [9, 10, 11]}
CPC = {"DEF": "DJF", "MAM": "MAM", "JJA": "JJA", "SON": "SON"}
FASES = ["El Niño", "La Niña"]
EST = ["La Balsa", "Juanchito", "La Victoria", "La Virginia", "Irra", "La Pintada", "Puente Iglesias", "Bolombolo", "Cañafisto", "Presa"]
COD = dict(zip(EST, ["26027010", "26067010", "26107070", "26177030", "26167070", "26187110", "26207030", "26207080", "26217050", "PRESA"]))

fin = json.loads((ABC / "modelo_final.json").read_text(encoding="utf-8"))      # modelo elegido en 04b_abcd_regionalizado.py
mejor = fin["producto"]
etq = f"{mejor.replace(' ', '_')}_{'PM' if fin['eto'] == 'Penman-Monteith' else 'HG'}"
print("modelo:", fin)
st = xr.open_dataset(ABC / (f"estados_reg_{etq}.nc" if fin["tipo"] == "regionalizado" else f"estados_{mejor.replace(' ', '_')}.nc"))
cel = pd.read_csv(ENT / "grilla_celdas.csv", index_col="celda").loc[st.celda.values]
w = cel.a_cuenca_km2.values
tiempo = pd.DatetimeIndex(st.time.values)
P = xr.open_dataarray(ENT / f"P_{mejor.replace(' ', '_')}.nc").sel(time=st.time).values[:, cel.index.map(
    {c: i for i, c in enumerate(pd.read_csv(ENT / "grilla_celdas.csv").celda)}).values]
fases = pd.read_csv(EP / "fases_enso.csv")
fase_de = {(r.YR, r.SEAS): r.fase for r in fases.itertuples()}
oni = fases.assign(mes=fases.SEAS.map({"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6, "JJA": 7, "JAS": 8, "ASO": 9,
                                        "SON": 10, "OND": 11, "NDJ": 12}))
oni = pd.Series(oni.ANOM.values, index=pd.to_datetime(dict(year=oni.YR, month=oni.mes, day=1))).sort_index()


def trimestres(df):
    """DataFrame mensual (tiempo × columnas) → {trimestre: DataFrame año × columnas} (media del trimestre; DEF del año de enero)."""
    anio = np.where(df.index.month == 12, df.index.year + 1, df.index.year)
    out = {}
    for tr, ms in TRIM.items():
        x = df[df.index.month.isin(ms)]
        a = anio[df.index.month.isin(ms)]
        g = x.groupby(a)
        out[tr] = g.mean().where(g.count() == 3)
    return out


def z_trim(df):
    z = {}
    for tr, x in trimestres(df).items():
        b = x.loc[1981:2010]
        z[tr] = (x - b.mean()) / b.std()
    return z


def compuestos(z):
    fil = {}
    for tr, x in z.items():
        f = np.array([fase_de.get((a, CPC[tr]), "Neutro") for a in x.index])
        for fa in FASES:
            fil[(tr, fa)] = (x[f == fa].mean(), int((f == fa).sum()))
    return fil


def anom_mens(s):
    b = s["1981":"2010"]
    clim, sd = b.groupby(b.index.month).mean(), b.groupby(b.index.month).std()
    return (s - clim.reindex(s.index.month).values) / sd.reindex(s.index.month).values


# ----------------------------------------------------------------------------- numeral 3: humedad del suelo
S = pd.DataFrame(st.S.values, index=tiempo, columns=cel.index)
zS = z_trim(S["1981-01":"2023-11"])
cS = compuestos(zS)
Sc = pd.Series((st.S.values * w).sum(1) / w.sum(), index=tiempo)
Pc = pd.Series((P * w).sum(1) / w.sum(), index=tiempo)
Gc = pd.Series((st.G.values * w).sum(1) / w.sum(), index=tiempo)
filas = []
for (tr, fa), (v, n) in cS.items():
    zcu = z_trim(Sc.to_frame("S"))[tr]
    f = np.array([fase_de.get((a, CPC[tr]), "Neutro") for a in zcu.index])
    zP = z_trim(Pc.to_frame("P"))[tr]
    filas.append({"trimestre": tr, "fase": fa, "n": n, "z S cuenca": float(zcu[f == fa].mean().iloc[0]),
                  "z P cuenca": float(zP[f == fa].mean().iloc[0]),
                  "% área con S por debajo de lo normal": 100 * float((w * (v.values < 0)).sum() / w.sum())})
TS = pd.DataFrame(filas)
TS.round(3).to_csv(OUT / "suelo_compuestos.csv", index=False, encoding="utf-8-sig")
# memoria y rezago P → S por celda (anomalías mensuales)
aS = S.apply(anom_mens)
aP = pd.DataFrame(P, index=tiempo, columns=cel.index).apply(anom_mens)
mem = aS.apply(lambda s: s.autocorr(1))
rez = pd.Series({c: int(np.nanargmax([aP[c].corr(aS[c].shift(-k)) for k in range(0, 4)])) for c in cel.index})
pd.DataFrame({"memoria_r1": mem, "rezago_P_S_meses": rez}).round(3).to_csv(OUT / "suelo_memoria_celdas.csv", encoding="utf-8-sig")

# ----------------------------------------------------------------------------- numeral 4: caudales
qo = pd.read_csv(R2 / "03_caudales" / "Q_mensual_estaciones.csv", index_col=0, parse_dates=True)
qs = pd.read_csv(ABC / (f"Q_simulado_reg_{etq}.csv" if fin["tipo"] == "regionalizado" else f"Q_simulado_{mejor.replace(' ', '_')}.csv"),
                 index_col=0, parse_dates=True)
Qo = pd.DataFrame({e: qo[COD[e]] for e in EST})["1981-01":"2023-11"]
Qs = qs[EST]["1981-01":"2023-11"]
zo, zs = z_trim(Qo), z_trim(Qs)
co, cs = compuestos(zo), compuestos(zs)
fq = []
for (tr, fa) in co:
    for e in EST:
        fq.append({"estación": e, "trimestre": tr, "fase": fa, "n": co[(tr, fa)][1], "z Q observado": co[(tr, fa)][0][e],
                   "z Q simulado": cs[(tr, fa)][0][e]})
TQ = pd.DataFrame(fq)
TQ.round(3).to_csv(OUT / "caudales_compuestos.csv", index=False, encoding="utf-8-sig")
# ciclo anual por fase (fase del mes según el ONI del trimestre centrado en ese mes)
fase_mes = {}
for r in fases.itertuples():
    m = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6, "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}[r.SEAS]
    fase_mes[pd.Timestamp(r.YR, m, 1)] = r.fase
fm = pd.Series([fase_mes.get(t, "Neutro") for t in tiempo], index=tiempo)
cic = []
for e in ["La Virginia", "Bolombolo", "Presa"]:
    for fa in ["El Niño", "Neutro", "La Niña"]:
        sel = (fm == fa) & qo.index.isin(tiempo)
        for mes in range(1, 13):
            mm = sel & (tiempo.month == mes)
            cic.append({"estación": e, "fase": fa, "mes": mes, "Q observado": qo[COD[e]].reindex(tiempo)[mm].mean(),
                        "Q simulado": qs[e].reindex(tiempo)[mm & qo[COD[e]].reindex(tiempo).notna()].mean()})
pd.DataFrame(cic).round(1).to_csv(OUT / "ciclo_por_fase.csv", index=False, encoding="utf-8-sig")
# rezagos y relación con el ONI (cuenca: P, S, G; presa: Q obs)
A = pd.DataFrame({"P": anom_mens(Pc), "S": anom_mens(Sc), "G": anom_mens(Gc), "Q sim presa": anom_mens(qs["Presa"]),
                  "Q obs presa": anom_mens(qo["PRESA"].reindex(tiempo))})
lag = []
for v in A:
    lag.append({"variable": v, **{f"ONI → {v} rezago {k}": A[v].corr(oni.reindex(tiempo).shift(k)) for k in range(0, 7)},
                "memoria r1": A[v].autocorr(1), "memoria r3": A[v].autocorr(3)})
L = pd.DataFrame(lag)
L.round(3).to_csv(OUT / "rezagos_oni.csv", index=False, encoding="utf-8-sig")
cc = pd.DataFrame({k: [A["P"].corr(A[v].shift(-k)) for v in ["S", "G", "Q sim presa", "Q obs presa"]] for k in range(0, 7)},
                  index=["P → S", "P → G", "P → Q sim", "P → Q obs"])
cc.columns = [f"rezago {k} meses" for k in cc.columns]
cc.round(3).to_csv(OUT / "rezagos_P.csv", encoding="utf-8-sig")
A.round(3).to_csv(OUT / "anomalias_mensuales_cuenca.csv", encoding="utf-8-sig")
pd.DataFrame({"P": Pc, "S": Sc, "G": Gc, "ETR": (st.ETR.values * w).sum(1) / w.sum(), "ONI": oni.reindex(tiempo)}).round(2) \
    .to_csv(OUT / "series_cuenca.csv", encoding="utf-8-sig")

# ----------------------------------------------------------------------------- figuras
U = gpd.read_file(ENT / "unidades.gpkg").to_crs(4326)
cu = U.dissolve()
lat, lon = np.sort(cel.lat.unique()), np.sort(cel.lon.unique())
CL = [-1.5, -1.0, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1.0, 1.5]
cmap = ListedColormap(plt.get_cmap("RdBu")(np.linspace(0.05, 0.95, len(CL) + 1)))
norm = BoundaryNorm([-9] + CL + [9], cmap.N)


def malla(v):
    g = np.full((len(lat), len(lon)), np.nan)
    g[np.searchsorted(lat, cel.lat.values), np.searchsorted(lon, cel.lon.values)] = np.where(w > 0, v, np.nan)
    return g


fig, axs = plt.subplots(2, 4, figsize=(9.5, 7.6), constrained_layout=True)
for i, fa in enumerate(FASES):
    for j, tr in enumerate(TRIM):
        ax = axs[i, j]
        v, n = cS[(tr, fa)]
        im = ax.pcolormesh(lon, lat, malla(v.values), cmap=cmap, norm=norm, shading="nearest")
        cu.boundary.plot(ax=ax, color="k", lw=0.7)
        ax.set_xticks([]); ax.set_yticks([]); ax.set_aspect("equal"); ax.set_xlabel("")
        ax.set_ylabel(fa if j == 0 else "", fontsize=10)
        zc = TS[(TS.trimestre == tr) & (TS.fase == fa)]["z S cuenca"].iloc[0]
        ax.set_title(f"{tr} · z̄ = {zc:+.2f} (n = {n})", fontsize=9)
fig.colorbar(im, ax=axs, orientation="horizontal", fraction=0.04, pad=0.02, ticks=CL,
             label="Anomalía estandarizada de la humedad del suelo S (abcd): rojo = más seco, azul = más húmedo")
fig.suptitle(f"Humedad del suelo simulada en trimestres El Niño y La Niña (1981–2023; P: {mejor}, ETo: {fin['eto']})", fontsize=11)
fig.savefig(OUT / "mapas_suelo_enso.png", dpi=300)
plt.close(fig)

fig, axs = plt.subplots(1, 2, figsize=(7.5, 6), constrained_layout=True)
for ax, (v, t, cm, cl) in zip(axs, [(mem.values, "Memoria: autocorrelación de 1 mes\nde las anomalías de S", "Blues",
                                     [0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0]),
                                    (rez.values.astype(float), "Rezago de la respuesta de S\na la lluvia (meses)", "Oranges",
                                     [-0.5, 0.5, 1.5, 2.5, 3.5])]):
    cmp = ListedColormap(plt.get_cmap(cm)(np.linspace(0.15, 0.95, len(cl) - 1)))
    im = ax.pcolormesh(lon, lat, malla(v), cmap=cmp, norm=BoundaryNorm(cl, cmp.N), shading="nearest")
    cu.boundary.plot(ax=ax, color="k", lw=0.7)
    ax.set_xticks([]); ax.set_yticks([]); ax.set_aspect("equal"); ax.set_title(t, fontsize=10); ax.set_xlabel(""); ax.set_ylabel("")
    cb = fig.colorbar(im, ax=ax, shrink=0.6)
    if cm == "Oranges":
        cb.set_ticks([0, 1, 2, 3])
fig.savefig(OUT / "mapas_memoria_suelo.png", dpi=300)
plt.close(fig)

pd.set_option("display.width", 220)
print(TS.round(2).to_string(index=False))
print(TQ[TQ["estación"].isin(["La Virginia", "Bolombolo", "Presa"])].pivot_table(
    index=["estación"], columns=["fase", "trimestre"], values=["z Q observado", "z Q simulado"]).round(2).T.to_string())
print(L.round(2).T.to_string())
print(cc.round(2).to_string())
