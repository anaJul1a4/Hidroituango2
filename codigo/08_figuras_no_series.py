"""
Trabajo 2 · figuras que no son series de tiempo, en alta resolución (300 dpi) para el sitio y el informe.

Reglas de color: lluvia/húmedo en azul y seco en rojo; categorías con tonos distintos (no tonos de un mismo color); sin verdes,
rosados ni morados.

  fig_celdas_marcadas.png     celdas-día corregidas en el Cubo, por mes calendario (numeral 1a)
  fig_kge_estaciones.png      KGE de calibración y validación del modelo final por estación (1c)
  fig_kge_modelos_presa.png   KGE de validación en la presa: empírico, empírico con memoria, abcd agregado y semidistribuido (1c)
  fig_enso_P_productos.png    z medio de la cuenca por producto, trimestre y fase (2)
  fig_suelo_lluvia_enso.png   z del suelo frente a z de la lluvia, por trimestre y fase (3)
  fig_caudales_enso.png       z del caudal observado y simulado en tres estaciones, por trimestre y fase (4)

Salidas: trabajo2/resultados/07_figuras/
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
R2 = ROOT / "trabajo2" / "resultados"
OUT = R2 / "07_figuras"
OUT.mkdir(parents=True, exist_ok=True)
DPI = 300
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "axes.grid.axis": "y",
                     "grid.color": "#d9d9d9", "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False})
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
TR = ["DEF", "MAM", "JJA", "SON"]
ROJO, AZUL, NEGRO, GRIS, AMBAR, NARANJA = "#b91c1c", "#1d4ed8", "#1f2328", "#9aa3b2", "#b07a0c", "#ea580c"
COLP = {"Cubo IDEAM": NEGRO, "CHIRPS v2.0": AZUL, "CHIRPS v3.0": GRIS, "ERA5-Land": NARANJA, "ERA5": ROJO}
coma = lambda v, d=2: f"{v:.{d}f}".replace(".", ",").replace("-", "−")  # noqa: E731


def guardar(fig, nombre):
    fig.savefig(OUT / nombre, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  ", nombre)


def cero(ax):
    ax.axhline(0, color="#555", lw=0.8)


# ---- 1a: celdas marcadas -----------------------------------------------------------------------------------------
marc = pd.read_csv(R2 / "00_limpieza_cubo" / "marcados_por_mes.csv", index_col=0, parse_dates=True)
m = marc.groupby(marc.index.month)["celdas-día marcadas"].sum()
fig, ax = plt.subplots(figsize=(7.5, 3.8))
b = ax.bar(MESES, m.values, color=AMBAR)
ax.bar_label(b, fmt="%d", fontsize=8, padding=2)
ax.set_ylabel("Celdas-día corregidas, 1981–2023")
ax.set_title("Cubo de datos IDEAM: celdas-día corregidas por mes calendario (recuadro de la cuenca)", fontsize=10.5)
guardar(fig, "fig_celdas_marcadas.png")

# ---- 1c: modelo ---------------------------------------------------------------------------------------------------
ABC = R2 / "04_abcd"
final = json.loads((ABC / "modelo_final.json").read_text(encoding="utf-8"))
M = pd.concat([pd.read_csv(ABC / "metricas.csv"), pd.read_csv(ABC / "regionalizado_metricas.csv")])
M["per"] = np.where(M.periodo.str.startswith("cal"), "cal", "val")
EST = ["La Balsa", "Juanchito", "La Victoria", "La Virginia", "Irra", "La Pintada", "Puente Iglesias", "Bolombolo", "Cañafisto", "Presa"]
mod_f = "abcd semidistribuido regionalizado" if final["tipo"] == "regionalizado" else "abcd semidistribuido"
mf = M[(M.modelo == mod_f) & (M.producto == final["producto"]) & (M.ETo == final["eto"])]
k = mf.pivot_table(index="estación", columns="per", values="KGE").loc[EST]
pb = mf[mf.per == "val"].set_index("estación").PBIAS.loc[EST]
fig, ax = plt.subplots(figsize=(10, 4.4))
x = np.arange(len(EST)); w = 0.38
b1 = ax.bar(x - w / 2, k["cal"], w, color=GRIS, label="Calibración 1982–2005")
b2 = ax.bar(x + w / 2, k["val"], w, color=AZUL, label="Validación 2006–2023")
ax.bar_label(b1, labels=[coma(v) for v in k["cal"]], fontsize=7.5, padding=2)
ax.bar_label(b2, labels=[coma(v) for v in k["val"]], fontsize=7.5, padding=2)
for i, p in enumerate(pb):
    ax.text(x[i] + w / 2, 0.03, f"{p:+.0f} %".replace("-", "−"), ha="center", va="bottom", fontsize=7, color="white", rotation=90)
ax.axhline(0.75, color="#555", lw=0.8, ls=":")
ax.text(-0.45, 0.735, "KGE = 0,75", ha="left", va="top", fontsize=8, color="#555")
ax.set_xticks(x, EST, rotation=25, ha="right"); ax.set_ylim(0, 1.05); ax.set_ylabel("KGE del caudal mensual")
ax.legend(loc="upper left", ncol=2)
ax.set_title(f"Modelo final ({mod_f}, P {final['producto']}, ETo {final['eto']}): KGE por estación "
             "(texto blanco: sesgo de validación)", fontsize=10)
guardar(fig, "fig_kge_estaciones.png")

emp = M[(M.codigo == "PRESA") & (M.producto == final["producto"]) & (M.per == "val")]
emp = emp[(emp.ETo == final["eto"]) | emp.modelo.str.startswith("empírico") | (emp.modelo == "abcd agregado")]
noms = [("empírico Q = α·W + β", "Empírico\nQ = α·(P − ETR) + β", GRIS),
        ("empírico con memoria Q = α·W + γ·Q(t−1) + β", "Empírico con memoria\n+ γ·Q(t−1)", AMBAR),
        ("abcd agregado", "abcd agregado\n(toda la cuenca)", NEGRO), (mod_f, "abcd semidistribuido\nregionalizado", AZUL)]
vals, etqs, cols = [], [], []
for clave, et, c in noms:
    s = emp[emp.modelo == clave]
    if len(s):
        if clave == "abcd agregado" and (s.ETo == final["eto"]).any():
            s = s[s.ETo == final["eto"]]
        vals.append(float(s.KGE.iloc[0])); etqs.append(et); cols.append(c)
fig, ax = plt.subplots(figsize=(7.5, 4.2))
b = ax.bar(etqs, vals, color=cols, width=0.6)
ax.bar_label(b, labels=[coma(v) for v in vals], fontsize=9, padding=2)
ax.set_ylim(0, 1.05); ax.set_ylabel("KGE en la presa, validación")
ax.set_title(f"Ecuación empírica frente al modelo abcd (P {final['producto']})", fontsize=10.5)
ax.tick_params(axis="x", labelsize=8.5)
guardar(fig, "fig_kge_modelos_presa.png")

# ---- 2: ENSO y lluvia por producto ------------------------------------------------------------------------------
comp = pd.read_csv(R2 / "05_enso_P" / "compuestos_cuenca.csv")
PR = list(COLP)
fig, axs = plt.subplots(1, 2, figsize=(12, 4.4), sharey=True)
w = 0.16
for ax, fa in zip(axs, ["El Niño", "La Niña"]):
    for j, p in enumerate(PR):
        v = [float(comp[(comp.producto == p) & (comp.trimestre == t) & (comp.fase == fa)]["z medio de la cuenca"].iloc[0]) for t in TR]
        ax.bar(np.arange(4) + (j - 2) * w, v, w, color=COLP[p], label=p)
    cero(ax); ax.set_xticks(range(4), TR); ax.set_title(fa, fontsize=11, color=ROJO if fa == "El Niño" else AZUL)
axs[0].set_ylabel("z medio de la cuenca (anomalía estandarizada)")
fig.suptitle("Anomalía estandarizada de la precipitación trimestral en la cuenca, compuestos 1981–2023 (base 1981–2010)", fontsize=11)
fig.tight_layout()
h, l = axs[0].get_legend_handles_labels()
fig.legend(h, l, ncol=5, loc="upper center", bbox_to_anchor=(0.5, 0.0), fontsize=9)
guardar(fig, "fig_enso_P_productos.png")

# ---- 3: suelo frente a lluvia ------------------------------------------------------------------------------------
ts = pd.read_csv(R2 / "06_enso_suelo_Q" / "suelo_compuestos.csv")
fig, ax = plt.subplots(figsize=(8.5, 4.4))
w = 0.2
for j, (fa, c) in enumerate([("El Niño", ROJO), ("La Niña", AZUL)]):
    d = ts[ts.fase == fa].set_index("trimestre").loc[TR]
    xp = np.arange(4) + (2 * j - 1.5) * w
    b1 = ax.bar(xp, d["z P cuenca"], w, facecolor="white", edgecolor=c, hatch="////", lw=1, label=f"Lluvia · {fa}")
    b2 = ax.bar(xp + w, d["z S cuenca"], w, color=c, label=f"Suelo (abcd) · {fa}")
    ax.bar_label(b1, labels=[coma(v) for v in d["z P cuenca"]], fontsize=7, padding=2)
    ax.bar_label(b2, labels=[coma(v) for v in d["z S cuenca"]], fontsize=7, padding=2)
cero(ax); ax.set_xticks(range(4), TR); ax.set_ylabel("z medio de la cuenca")
ax.legend(ncol=4, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.08))
ax.set_title("Humedad del suelo simulada frente a la lluvia en El Niño y La Niña", fontsize=10.5)
guardar(fig, "fig_suelo_lluvia_enso.png")

# ---- 4: caudales observados y simulados -------------------------------------------------------------------------
tq = pd.read_csv(R2 / "06_enso_suelo_Q" / "caudales_compuestos.csv")
E3 = ["La Virginia", "Bolombolo", "Presa"]
fig, axs = plt.subplots(1, 3, figsize=(13, 4.4), sharey=True)
w = 0.36
for ax, e in zip(axs, E3):
    for j, (fa, c, mk) in enumerate([("El Niño", ROJO, "D"), ("La Niña", AZUL, "o")]):
        d = tq[(tq["estación"] == e) & (tq.fase == fa)].set_index("trimestre").loc[TR]
        xp = np.arange(4) + (j - 0.5) * w
        ax.bar(xp, d["z Q observado"], w, color=c, alpha=0.8, label=f"Observado · {fa}")
        ax.scatter(xp, d["z Q simulado"], marker=mk, s=34, color=NEGRO, zorder=3, label=f"Simulado · {fa}")
    cero(ax); ax.set_xticks(range(4), TR); ax.set_title(e, fontsize=11)
axs[0].set_ylabel("z del caudal (anomalía estandarizada)")
h, l = axs[0].get_legend_handles_labels()
fig.legend(h, l, ncol=4, loc="lower center", bbox_to_anchor=(0.5, -0.06), fontsize=9)
fig.suptitle("Caudales en El Niño y La Niña: observado (barras) y simulado por el modelo abcd (puntos)", fontsize=11)
fig.tight_layout()
guardar(fig, "fig_caudales_enso.png")
