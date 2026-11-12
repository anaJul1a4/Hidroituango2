"""
Trabajo 2 · figuras de series para el informe escrito (300 dpi). En el sitio estas series son gráficas interactivas; en el informe
van como imágenes originales con la misma información.

  fig_cubo_limpieza.png      ciclo anual y serie mensual del Cubo original, del Cubo limpio y de CHIRPS v2.0
  fig_ciclo_productos.png    ciclo anual de la lluvia de la cuenca por producto, sin corregir y corregido, y ETo
  fig_series_Q.png           caudal mensual observado y simulado en La Virginia, Bolombolo y la presa
  fig_ciclo_fases.png        ciclo anual del caudal en meses El Niño, neutros y La Niña, observado y simulado
  fig_rezagos.png            correlación del ONI y de la lluvia con el suelo, el acuífero y el caudal según el rezago
  fig_knn_ejemplos.png       pronósticos de años análogos emitidos en agosto de 1997, 2015 y 2010
  fig_alertas_serie.png      probabilidad de trimestre seco (logística ONI + suelo) y trimestres secos observados
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
R2 = ROOT / "trabajo2" / "resultados"
FIG = R2 / "07_figuras"
ENT = R2 / "01_entradas"
DPI = 300
ROJO, AZUL, NEGRO, GRIS, AMBAR, NARANJA, CELESTE = "#b91c1c", "#1d4ed8", "#1f2328", "#9aa3b2", "#b07a0c", "#ea580c", "#60a5fa"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": "#d9d9d9", "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False})
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def guardar(fig, n):
    fig.savefig(FIG / n, dpi=DPI, bbox_inches="tight", facecolor="white"); plt.close(fig); print("  ", n)


# 1. limpieza del Cubo
cel = pd.read_csv(ENT / "grilla_celdas.csv")
w = cel.a_cuenca_km2.values
orig = xr.open_dataset(ROOT / "CUBO_IDEAM" / "prcp_mes_acum_1981_2023.nc").prcp.sel(
    lat=xr.DataArray(cel.lat.values, dims="c"), lon=xr.DataArray(cel.lon.values, dims="c"), method="nearest")
oc = pd.Series((orig.values * w).sum(1) / w.sum(), index=pd.DatetimeIndex(orig.time.values))
S = pd.read_csv(ENT / "series_unidades.csv", header=[0, 1], index_col=0, parse_dates=True)
C = S.xs("CUENCA", axis=1, level="unidad")
cic = pd.read_csv(R2 / "02_comparacion" / "ciclo_anual_cuenca.csv", index_col=0)
b = oc["1981":"2010"]
fig, axs = plt.subplots(1, 2, figsize=(13, 4.2), gridspec_kw={"width_ratios": [1, 2.2]})
ax = axs[0]
ax.plot(MESES, b.groupby(b.index.month).mean(), ":o", color=ROJO, lw=2, ms=4, label="Cubo original")
ax.plot(MESES, cic["Cubo IDEAM"], "-o", color=NEGRO, lw=2, ms=4, label="Cubo con control de calidad")
ax.plot(MESES, cic["CHIRPS v2.0"], "-o", color=AZUL, lw=1.6, ms=3, label="CHIRPS v2.0")
ax.tick_params(axis="x", labelsize=8, rotation=45); ax.set_ylim(0); ax.set_ylabel("P media de la cuenca 1981–2010 (mm/mes)"); ax.legend(fontsize=8.5); ax.set_title("a) Ciclo anual", fontsize=10.5, loc="left")
ax = axs[1]
ax.plot(oc.index, oc, color=ROJO, lw=1, label="Cubo original")
ax.plot(C.index, C["P Cubo IDEAM"], color=NEGRO, lw=1.1, label="Cubo con control de calidad")
ax.plot(C.index, C["P CHIRPS v2.0"], color=AZUL, lw=0.9, label="CHIRPS v2.0")
ax.set_ylabel("P mensual de la cuenca (mm)"); ax.legend(fontsize=8.5, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.08)); ax.set_title("b) Serie mensual 1981–2023", fontsize=10.5, loc="left")
ax.annotate("enero de 1995", (pd.Timestamp("1995-01-01"), oc["1995-01"].iloc[0]), xytext=(pd.Timestamp("1998-06-01"), oc["1995-01"].iloc[0] * 0.9),
            arrowprops=dict(arrowstyle="->", color="#555"), fontsize=8.5)
guardar(fig, "fig_cubo_limpieza.png")

# 2. ciclo anual por producto y ETo
fig, axs = plt.subplots(1, 3, figsize=(15, 4.3))
grupos = [("a) Productos sin corregir", [("IDEAM normales (kriging, Trabajo 1)", AMBAR, "--"), ("Cubo IDEAM", NEGRO, "-"), ("CHIRPS v2.0", AZUL, "-"),
                                          ("CHIRPS v3.0", GRIS, "-"), ("ERA5-Land", NARANJA, "-"), ("ERA5", ROJO, "-")]),
          ("b) Reanálisis corregidos con el Cubo (mapeo de cuantiles)", [("Cubo IDEAM", NEGRO, "-"), ("CHIRPS v2.0", AZUL, "-"),
                                                                         ("ERA5-Land QM", NARANJA, "--"), ("ERA5 QM", ROJO, ":")])]
for ax, (tit, ss) in zip(axs[:2], grupos):
    for k, c, ls in ss:
        ax.plot(MESES, cic[k], ls, color=c, lw=2.6 if k == "Cubo IDEAM" else 1.8, label=k.replace("IDEAM normales (kriging, Trabajo 1)", "IDEAM, kriging de normales (Trabajo 1)"))
    ax.tick_params(axis="x", labelsize=8, rotation=45); ax.set_ylim(0); ax.set_ylabel("P media de la cuenca 1981–2010 (mm/mes)"); ax.legend(fontsize=8); ax.set_title(tit, fontsize=10.5, loc="left")
ax = axs[2]
ax.bar(MESES, cic["Cubo IDEAM"], color=AZUL, alpha=0.2, label="P (Cubo)")
ax.plot(MESES, cic["ETo Penman-Monteith"], "-o", color=NARANJA, ms=4, label="ETo Penman-Monteith")
ax.plot(MESES, cic["ETo Hargreaves"], "--s", color=ROJO, ms=4, label="ETo Hargreaves")
ax.tick_params(axis="x", labelsize=8, rotation=45); ax.set_ylabel("Media de la cuenca 1981–2010 (mm/mes)"); ax.legend(fontsize=8); ax.set_title("c) Evapotranspiración de referencia", fontsize=10.5, loc="left")
guardar(fig, "fig_ciclo_productos.png")

# 3. series observadas y simuladas
fin = json.loads((R2 / "04_abcd" / "modelo_final.json").read_text(encoding="utf-8"))
qs = pd.read_csv(R2 / "04_abcd" / f"Q_simulado_reg_Cubo_IDEAM_{'HG' if fin['eto'] == 'Hargreaves' else 'PM'}.csv", index_col=0, parse_dates=True)
qo = pd.read_csv(R2 / "03_caudales" / "Q_mensual_estaciones.csv", index_col=0, parse_dates=True)
COD = {"La Virginia": "26177030", "Bolombolo": "26207080", "Presa": "PRESA"}
fig, axs = plt.subplots(3, 1, figsize=(13, 8.4), sharex=True)
for ax, (e, c) in zip(axs, COD.items()):
    ax.axvspan(pd.Timestamp("1982-01-01"), pd.Timestamp("2005-12-31"), color=GRIS, alpha=0.15, lw=0)
    ax.plot(qo.index, qo[c], color=NEGRO, lw=1.1, label="Observado")
    ax.plot(qs.index, qs[e], color=NARANJA, lw=1.1, label="Simulado (abcd)")
    ax.set_ylabel("Q (m³/s)"); ax.set_title(e if e != "Presa" else "Presa (Puerto Valdivia transferido por áreas, hasta 2017)", fontsize=10.5, loc="left")
    ax.set_ylim(0)
h, l = axs[0].get_legend_handles_labels()
fig.legend(h, l, ncol=2, loc="lower center", bbox_to_anchor=(0.5, -0.03), fontsize=9.5)
axs[0].text(pd.Timestamp("1993-06-01"), axs[0].get_ylim()[1] * 0.92, "calibración 1982–2005", ha="center", fontsize=8.5, color="#555")
axs[0].text(pd.Timestamp("2015-01-01"), axs[0].get_ylim()[1] * 0.92, "validación 2006–2023", ha="center", fontsize=8.5, color="#555")
axs[-1].set_xlim(pd.Timestamp("1981-01-01"), pd.Timestamp("2024-01-01"))
guardar(fig, "fig_series_Q.png")

# 4. ciclo anual por fase ENSO
cpf = pd.read_csv(R2 / "06_enso_suelo_Q" / "ciclo_por_fase.csv")
colf = {"El Niño": ROJO, "Neutro": GRIS, "La Niña": AZUL}
fig, axs = plt.subplots(1, 3, figsize=(15, 4.4))
for ax, e in zip(axs, ["La Virginia", "Bolombolo", "Presa"]):
    for fa, c in colf.items():
        d = cpf[(cpf["estación"] == e) & (cpf.fase == fa)]
        ax.plot(MESES, d["Q observado"], "-o", color=c, lw=2, ms=4, label=f"{fa} · observado")
        ax.plot(MESES, d["Q simulado"], "--", color=c, lw=1.5, label=f"{fa} · simulado")
    ax.set_title(e, fontsize=10.5, loc="left"); ax.set_ylim(0); ax.tick_params(axis="x", labelsize=8, rotation=45)
axs[0].set_ylabel("Caudal medio mensual (m³/s)")
h, l = axs[0].get_legend_handles_labels()
fig.legend(h, l, ncol=6, loc="lower center", bbox_to_anchor=(0.5, -0.06), fontsize=8.5)
fig.tight_layout()
guardar(fig, "fig_ciclo_fases.png")

# 5. rezagos
rz = pd.read_csv(R2 / "06_enso_suelo_Q" / "rezagos_oni.csv").set_index("variable")
rp = pd.read_csv(R2 / "06_enso_suelo_Q" / "rezagos_P.csv", index_col=0)
k = np.arange(7)
fig, axs = plt.subplots(1, 2, figsize=(12, 4.2))
for v, n, c, ls in [("P", "Lluvia", CELESTE, "-"), ("S", "Suelo S", AMBAR, "-"), ("G", "Acuífero G", GRIS, "-"),
                    ("Q obs presa", "Caudal observado (presa)", NEGRO, "-"), ("Q sim presa", "Caudal simulado (presa)", NARANJA, "--")]:
    axs[0].plot(k, [rz.loc[v, f"ONI → {v} rezago {i}"] for i in k], ls, marker="o", ms=4, color=c, lw=2, label=n)
axs[0].set_xlabel("Rezago (meses): la variable va detrás del ONI"); axs[0].set_ylabel("Correlación con el ONI")
axs[0].set_title("a) ONI → lluvia, suelo, acuífero y caudal", fontsize=10.5, loc="left"); axs[0].legend(fontsize=8)
for v, n, c, ls in [("P → S", "Suelo S", AMBAR, "-"), ("P → G", "Acuífero G", GRIS, "-"), ("P → Q obs", "Caudal observado (presa)", NEGRO, "-"),
                    ("P → Q sim", "Caudal simulado (presa)", NARANJA, "--")]:
    axs[1].plot(k, rp.loc[v].values, ls, marker="o", ms=4, color=c, lw=2, label=n)
axs[1].set_xlabel("Rezago (meses): la variable va detrás de la lluvia"); axs[1].set_ylabel("Correlación con la anomalía de lluvia")
axs[1].set_title("b) Lluvia → suelo, acuífero y caudal", fontsize=10.5, loc="left"); axs[1].legend(fontsize=8); axs[1].set_ylim(0, 0.8)
guardar(fig, "fig_rezagos.png")

# 6. KNN: ejemplos
pr = json.loads((R2 / "08_pronostico" / "sitio.json").read_text(encoding="utf-8"))
fig, axs = plt.subplots(1, 3, figsize=(15, 4.3), sharey=True)
for ax, k_ in zip(axs, ["1997-08", "2015-08", "2010-08"]):
    e = pr["ejemplos"][k_]
    x = np.arange(1, 7)
    ax.fill_between(x, e["p10"], e["p90"], color=AZUL, alpha=0.15, lw=0, label=f"Intervalo 80 % de los {pr['K']} análogos")
    ax.plot(x, e["med"], "-o", color=AZUL, lw=2, ms=4, label="Mediana de los análogos")
    ax.plot(x, e["clim"], "--", color=GRIS, lw=2, label="Climatología (mediana)")
    ax.plot(x, e["obs"], "-s", color=NEGRO, lw=2.2, ms=5, label="Observado")
    ax.set_xticks(x, [f"{MESES[pd.Timestamp(m).month - 1]} {pd.Timestamp(m).year}" for m in e["meses"]], fontsize=8, rotation=30)
    ax.set_title(f"Emitido al final de {k_}: ONI {e['oni']:+.2f} °C, suelo z = {e['S']:+.2f}\n"
                 f"P(trimestre seco): KNN {100 * e['pknn']:.0f} %, logística {100 * e['plog']:.0f} %".replace(".", ","), fontsize=9, loc="left")
axs[0].set_ylabel("Aporte medio mensual a la presa (m³/s)"); axs[0].set_ylim(0)
h, l = axs[0].get_legend_handles_labels()
fig.legend(h, l, ncol=4, loc="lower center", bbox_to_anchor=(0.5, -0.07), fontsize=9)
guardar(fig, "fig_knn_ejemplos.png")

# 7. serie de alertas
p = pd.DataFrame({k_: v for k_, v in pr["prob"].items() if k_ != "t"}, index=pd.to_datetime(pr["prob"]["t"]))
p = p.reindex(pd.date_range(p.index[0], p.index[-1], freq="MS"))
fig, ax = plt.subplots(figsize=(13, 3.8))
ev = p.ev == 1
ax.bar(p.index[ev], np.ones(ev.sum()), width=31, color=ROJO, alpha=0.13, lw=0, label="Trimestre seco observado")
ax.plot(p.index, p.logS, color=NEGRO, lw=1)
col = np.where(p.logS >= 0.5, ROJO, np.where(p.logS >= 0.2, AMBAR, GRIS))
ax.scatter(p.index, p.logS, c=col, s=9, zorder=3, label="P(trimestre seco), logística ONI + suelo")
for u, c in [(0.2, AMBAR), (0.5, ROJO)]:
    ax.axhline(u, color=c, lw=1, ls=":")
ax.set_ylim(0, 1); ax.set_ylabel("Probabilidad"); ax.legend(fontsize=8.5, loc="upper left", ncol=2)
ax.xaxis.set_major_locator(mdates.YearLocator(2)); ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.set_xlim(pd.Timestamp("1981-10-01"), pd.Timestamp("2018-01-01"))
guardar(fig, "fig_alertas_serie.png")
