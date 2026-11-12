"""
Trabajo 2 · proyecciones CMIP6 · paso 3: cambios proyectados en la cuenca para el sector hidroeléctrico.

Con las series de 13_cmip6_qdm_abcd.py (6 modelos × SSP2-4.5 y SSP5-8.5), cambios de cada periodo futuro (2021–2050, 2041–2070,
2071–2100) frente a 1981–2010 del mismo modelo:
  · lluvia, temperatura media, ETo, humedad del suelo, ETR y caudal medio en la presa (anual y por trimestre);
  · frecuencia de trimestres secos: meses en que el aporte medio de los tres meses siguientes queda bajo el percentil 20 de
    1981–2010 (para ese mes calendario), la misma definición del numeral 5 (por construcción, 20 % en 1981–2010);
  · caudal de estiaje: percentil 10 del caudal mensual en la presa.
Conjunto: mediana de los 6 modelos, rango y número de modelos que coinciden en el signo.

Salidas: trabajo2/resultados/11_cmip6/cambios_*.csv, sitio.json; figuras de 300 dpi en 07_figuras/
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
OUT = R2 / "11_cmip6"
FIG = R2 / "07_figuras"
ENT = R2 / "01_entradas"
ESC = {"ssp245": "SSP2-4.5", "ssp585": "SSP5-8.5"}
PER = {"2021–2050": ("2021", "2050"), "2041–2070": ("2041", "2070"), "2071–2100": ("2071", "2100")}
BASE = ("1981", "2010")
TRI = {"DEF": [12, 1, 2], "MAM": [3, 4, 5], "JJA": [6, 7, 8], "SON": [9, 10, 11]}
ROJO, AZUL, NEGRO, GRIS, AMBAR, NARANJA = "#b91c1c", "#1d4ed8", "#1f2328", "#9aa3b2", "#b07a0c", "#ea580c"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "axes.grid.axis": "y",
                     "grid.color": "#d9d9d9", "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False})
tam = pd.read_csv(OUT / "tamizaje_modelos.csv", index_col=0)
MOD = list(tam.index[tam.elegido])
COLM = dict(zip(MOD, [AZUL, ROJO, AMBAR, NEGRO, NARANJA, GRIS]))
MK = dict(zip(MOD, ["o", "s", "^", "D", "v", "P"]))

S, Q = {}, {}
for m in MOD:
    for e in ESC:
        S[(m, e)] = pd.read_csv(OUT / f"series_cuenca_{m}_{e}.csv", index_col=0, parse_dates=True)
        Q[(m, e)] = pd.read_csv(OUT / f"Q_{m}_{e}.csv", index_col=0, parse_dates=True)


def anual(s, a0, a1, suma=True):
    d = s[a0:a1]
    return d.resample("YS").sum().mean() if suma else d.mean()


def q3_evento(q, a0, a1):
    q3 = q.rolling(3).mean().shift(-3)                          # aporte medio de t+1 … t+3
    b = q3[BASE[0]:BASE[1]]
    thr = b.groupby(b.index.month).quantile(0.2)
    d = q3[a0:a1].dropna()
    return 100 * (d < thr.reindex(d.index.month).values).mean()


filas = []
for (m, e), s in S.items():
    q = Q[(m, e)].Presa
    tm = (s.Tmax + s.Tmin) / 2
    base = {"P": anual(s.P, *BASE), "ETo": anual(s.ETo, *BASE), "ETR": anual(s.ETR, *BASE), "S": s.S[BASE[0]:BASE[1]].mean(),
            "Q": q[BASE[0]:BASE[1]].mean(), "T": tm[BASE[0]:BASE[1]].mean(), "Q10": q[BASE[0]:BASE[1]].quantile(0.1)}
    for per, (a0, a1) in PER.items():
        f = {"modelo": m, "escenario": ESC[e], "periodo": per,
             "ΔP (%)": 100 * (anual(s.P, a0, a1) / base["P"] - 1), "ΔT (°C)": tm[a0:a1].mean() - base["T"],
             "ΔETo (%)": 100 * (anual(s.ETo, a0, a1) / base["ETo"] - 1), "ΔETR (%)": 100 * (anual(s.ETR, a0, a1) / base["ETR"] - 1),
             "ΔS (%)": 100 * (s.S[a0:a1].mean() / base["S"] - 1), "ΔQ presa (%)": 100 * (q[a0:a1].mean() / base["Q"] - 1),
             "ΔQ10 presa (%)": 100 * (q[a0:a1].quantile(0.1) / base["Q10"] - 1),
             "trimestres secos (%)": q3_evento(q, a0, a1), "Q presa 1981–2010 (m³/s)": base["Q"]}
        for tri, ms in TRI.items():
            sb, sf = s.P[s.P.index.month.isin(ms)], q[q.index.month.isin(ms)]
            f[f"ΔP {tri} (%)"] = 100 * (sb[a0:a1].mean() / sb[BASE[0]:BASE[1]].mean() - 1)
            f[f"ΔQ {tri} (%)"] = 100 * (sf[a0:a1].mean() / sf[BASE[0]:BASE[1]].mean() - 1)
        filas.append(f)
C = pd.DataFrame(filas)
C.to_csv(OUT / "cambios_por_modelo.csv", index=False, encoding="utf-8-sig")
cols = [c for c in C.columns if c.startswith("Δ") or c.startswith("trimestres")]
g = C.groupby(["escenario", "periodo"])[cols]
ens = pd.concat({"mediana": g.median(), "mínimo": g.min(), "máximo": g.max(),
                 "modelos con el signo de la mediana": C.groupby(["escenario", "periodo"]).apply(
                     lambda d: pd.Series({c: int((np.sign(d[c] - (20 if c.startswith("tri") else 0)) ==
                                                  np.sign(d[c].median() - (20 if c.startswith("tri") else 0))).sum()) for c in cols}),
                     include_groups=False)}, axis=1)
ens.to_csv(OUT / "cambios_conjunto.csv", encoding="utf-8-sig")
pd.set_option("display.width", 250)
print(ens["mediana"][["ΔP (%)", "ΔT (°C)", "ΔETo (%)", "ΔS (%)", "ΔQ presa (%)", "ΔQ10 presa (%)", "trimestres secos (%)"]].round(1).to_string())
print(ens["modelos con el signo de la mediana"][["ΔP (%)", "ΔQ presa (%)", "ΔQ10 presa (%)", "trimestres secos (%)"]].to_string())
print(C.pivot_table(index="modelo", columns=["escenario", "periodo"], values="ΔQ presa (%)").round(0).to_string())

# ------------------------------------------------------------------------------------------------- figuras (300 dpi)
# 1. cambios en la presa por modelo
fig, axs = plt.subplots(2, 4, figsize=(15, 7.4), sharey="col")
varsf = [("ΔP (%)", "Lluvia (%)"), ("ΔETo (%)", "ETo (%)"), ("ΔQ presa (%)", "Caudal medio en la presa (%)"),
         ("trimestres secos (%)", "Trimestres secos (% de los meses)")]
for i, e in enumerate(ESC.values()):
    for j, (c, tit) in enumerate(varsf):
        ax = axs[i, j]
        d = C[C.escenario == e]
        x = np.arange(len(PER))
        for k, m in enumerate(MOD):
            v = d[d.modelo == m].set_index("periodo").loc[list(PER), c]
            ax.scatter(x + (k - 2.5) * 0.07, v, color=COLM[m], marker=MK[m], s=28, zorder=3, label=m if (i, j) == (0, 0) else None)
        med = d.groupby("periodo")[c].median().loc[list(PER)]
        ax.bar(x, med, 0.6, color=(ROJO if c != "ΔP (%)" and c != "ΔQ presa (%)" else GRIS), alpha=0.18, zorder=1)
        for xx, vv in zip(x, med):
            ax.text(xx, vv, f"{vv:+.0f}".replace("-", "−"), ha="center", va="bottom" if vv >= 0 else "top", fontsize=8.5, fontweight="bold")
        ax.axhline(20 if c.startswith("tri") else 0, color="#555", lw=0.8, ls=":" if c.startswith("tri") else "-")
        ax.set_xticks(x, list(PER), fontsize=8.5)
        if i == 0:
            ax.set_title(tit, fontsize=10.5)
        if j == 0:
            ax.set_ylabel(e, fontsize=11, fontweight="bold")
fig.legend(*axs[0, 0].get_legend_handles_labels(), ncol=6, loc="lower center", bbox_to_anchor=(0.5, -0.03), fontsize=9)
fig.suptitle("Cambios proyectados frente a 1981–2010 en la cuenca hasta Hidroituango (barra: mediana de los 6 modelos; puntos: cada modelo)\n"
             "trimestres secos: aporte de los tres meses siguientes bajo el percentil 20 de 1981–2010 (línea punteada: 20 %)", fontsize=11)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(FIG / "fig_cmip6_cambios.png", dpi=300, bbox_inches="tight", facecolor="white"); plt.close(fig)

# 2. mapas de cambio de lluvia (mediana del conjunto) y acuerdo entre modelos
cel = pd.read_csv(ENT / "grilla_celdas.csv")
U = gpd.read_file(ENT / "unidades.gpkg").to_crs(4326); cu = U.dissolve()
lat, lon = np.sort(cel.lat.unique()), np.sort(cel.lon.unique())


def malla(v):
    gr = np.full((len(lat), len(lon)), np.nan)
    gr[np.searchsorted(lat, cel.lat.values), np.searchsorted(lon, cel.lon.values)] = v
    return gr


niv = np.array([-30, -20, -15, -10, -5, -2, 2, 5, 10, 15, 20, 30])
cmap = plt.get_cmap("RdBu", len(niv) + 1)
norm = BoundaryNorm(np.concatenate([[-100], niv, [100]]), cmap.N)
filasm = [(e, p) for e in ESC for p in ["2041–2070", "2071–2100"]]
colsm = ["P", "P DEF", "P MAM", "P JJA", "P SON"]
fig, axs = plt.subplots(len(filasm), len(colsm), figsize=(2.15 * len(colsm) + 1.5, 4.3 * len(filasm)), constrained_layout=True)
for i, (e, p) in enumerate(filasm):
    camp = [xr.open_dataset(OUT / f"campos_{m}_{e}.nc") for m in MOD]
    for j, v in enumerate(colsm):
        dlt = np.array([100 * (c[v].sel(periodo=p).values / c[v].sel(periodo="1981–2010").values - 1) for c in camp])
        med = np.median(dlt, 0)
        acu = (np.sign(dlt) == np.sign(med)[None, :]).sum(0)
        ax = axs[i, j]
        im = ax.pcolormesh(lon, lat, malla(med), cmap=cmap, norm=norm, shading="nearest")
        sel = acu < 5
        ax.scatter(cel.lon.values[sel], cel.lat.values[sel], s=0.6, color="#333", marker=".")
        cu.boundary.plot(ax=ax, color="k", lw=0.8)
        wm = np.average(med, weights=cel.a_cuenca_km2.values)
        ax.set_title(f"{ESC[e]} · {p}\n{('Anual' if v == 'P' else v[2:])}: {wm:+.0f} %".replace("-", "−"), fontsize=8.5)
        ax.set_aspect("equal"); ax.tick_params(labelsize=6); ax.set_xlabel(""); ax.set_ylabel("")
cb = fig.colorbar(im, ax=axs, shrink=0.5, ticks=niv)
cb.set_label("Cambio de la lluvia frente a 1981–2010 (%), mediana de los 6 modelos")
fig.suptitle("Cambio proyectado de la lluvia (QDM sobre la grilla del Cubo) · puntos: menos de 5 de los 6 modelos coinciden en el signo",
             fontsize=11)
fig.savefig(FIG / "fig_cmip6_mapas_P.png", dpi=300, facecolor="white"); plt.close(fig)

# 3. ciclos del tamizaje (para el informe)
cic = pd.read_csv(OUT / "ciclos_historicos.csv", index_col=0)
fig, ax = plt.subplots(figsize=(9, 4.6))
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
for m in cic.columns.drop("Cubo IDEAM"):
    norm_c = cic[m] / cic[m].mean()
    ax.plot(MESES, norm_c, color=COLM[m] if m in MOD else "#cfd4dc", lw=2.2 if m in MOD else 0.9, zorder=3 if m in MOD else 1,
            label=m if m in MOD else None)
ax.plot(MESES, cic["Cubo IDEAM"] / cic["Cubo IDEAM"].mean(), color=NEGRO, lw=3.2, ls="--", label="Cubo IDEAM", zorder=4)
ax.set_ylabel("P mensual / P media mensual (1981–2010)")
ax.legend(ncol=4, fontsize=8, loc="upper center")
ax.set_title("Ciclo anual normalizado de la lluvia de la cuenca en los 28 modelos CMIP6 (gris) y los 6 elegidos", fontsize=10.5)
fig.savefig(FIG / "fig_cmip6_tamizaje.png", dpi=300, bbox_inches="tight", facecolor="white"); plt.close(fig)

# ------------------------------------------------------------------------------------------------- datos del sitio (series)
qobs = pd.read_csv(R2 / "03_caudales" / "Q_mensual_estaciones.csv", index_col=0, parse_dates=True)["PRESA"]
fin = json.loads((R2 / "04_abcd" / "modelo_final.json").read_text(encoding="utf-8"))
qcubo = pd.read_csv(R2 / "04_abcd" / f"Q_simulado_reg_Cubo_IDEAM_{'HG' if fin['eto'] == 'Hargreaves' else 'PM'}.csv",
                    index_col=0, parse_dates=True)["Presa"]
sit = {"ciclo": {}, "anual": {}, "tam": {m: (cic[m] / cic[m].mean()).round(3).tolist() for m in cic.columns}, "elegidos": MOD}
cb_ = lambda s: s[BASE[0]:BASE[1]].groupby(s[BASE[0]:BASE[1]].index.month).mean()  # noqa: E731
sit["ciclo"]["obs"] = cb_(qobs).round(0).tolist(); sit["ciclo"]["cubo"] = cb_(qcubo).round(0).tolist()
for e in ESC:
    cy = {}
    for per, (a0, a1) in {"1981–2010": BASE, **PER}.items():
        M_ = np.array([Q[(m, e)].Presa[a0:a1].groupby(Q[(m, e)].Presa[a0:a1].index.month).mean().values for m in MOD])
        cy[per] = {"med": np.median(M_, 0).round(0).tolist(), "min": M_.min(0).round(0).tolist(), "max": M_.max(0).round(0).tolist()}
    sit["ciclo"][e] = cy
    A_ = pd.DataFrame({m: Q[(m, e)].Presa.resample("YS").mean() for m in MOD})
    A10 = A_.rolling(10, center=True, min_periods=6).mean()
    rel = 100 * (A10 / A_[BASE[0]:BASE[1]].mean() - 1)
    sit["anual"][e] = {"t": A_.index.year.tolist(), "med": rel.median(1).round(1).tolist(), "min": rel.min(1).round(1).tolist(),
                       "max": rel.max(1).round(1).tolist(), **{m: rel[m].round(1).tolist() for m in MOD}}
(OUT / "sitio.json").write_text(json.dumps(sit, ensure_ascii=False), encoding="utf-8")
print("listo")

# 4. ciclo anual del aporte a la presa por periodo (figura para el informe)
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
COLP = {"1981–2010": NEGRO, "2021–2050": GRIS, "2041–2070": AMBAR, "2071–2100": ROJO}
fig, axs = plt.subplots(1, 2, figsize=(13, 4.4), sharey=True)
for ax, e in zip(axs, ESC):
    cy = sit["ciclo"][e]
    ax.plot(MESES, sit["ciclo"]["obs"], ":", color="#555", lw=1.5, label="Observado 1981–2010")
    for per, c in COLP.items():
        if per in ("2041–2070", "2071–2100"):
            ax.fill_between(MESES, cy[per]["min"], cy[per]["max"], color=c, alpha=0.12, lw=0)
        ax.plot(MESES, cy[per]["med"], "-o", color=c, lw=2.4 if per == "1981–2010" else 1.8, ms=3.5,
                label=f"{per} (mediana de los 6 modelos)" if per != "1981–2010" else "1981–2010 simulado (mediana)")
    ax.set_title(ESC[e], fontsize=11, loc="left", fontweight="bold"); ax.set_ylim(0); ax.tick_params(axis="x", labelsize=8.5)
axs[0].set_ylabel("Aporte medio mensual a la presa (m³/s)")
h, l = axs[0].get_legend_handles_labels()
fig.legend(h, l, ncol=5, loc="lower center", bbox_to_anchor=(0.5, -0.06), fontsize=8.5)
fig.suptitle("Ciclo anual del aporte a Hidroituango con el clima proyectado (bandas: rango de los 6 modelos en 2041–2070 y 2071–2100)", fontsize=11)
fig.tight_layout()
fig.savefig(FIG / "fig_cmip6_ciclo_presa.png", dpi=300, bbox_inches="tight", facecolor="white"); plt.close(fig)
