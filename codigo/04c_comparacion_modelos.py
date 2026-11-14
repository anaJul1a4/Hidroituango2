"""
Trabajo 2 · numerales 1c, 3 y 4: comparación de los modelos abcd (04, 04b) y GR2M (04_modelo_gr2m.py).

  1. Tabla única de métricas en la presa y en las 10 estaciones (NSE, NSE logarítmico, KGE, RMSE, PBIAS) para las mismas
     combinaciones de lluvia y ETo. El NSE logarítmico del abcd se calcula aquí con sus caudales simulados.
  2. Modelo principal: el de mayor KGE medio de validación en las 10 estaciones (se guarda en 04_comparacion/modelo_principal.json).
  3. Figuras de 300 dpi:
       fig_modelos_kge.png       KGE de validación por estación, abcd y GR2M
       fig_modelos_enso.png      humedad del suelo y caudal en la presa en El Niño y La Niña según cada modelo, y memoria (rezagos)

Salidas: trabajo2/resultados/04_comparacion/ y 07_figuras/
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
AB, GR = R2 / "04_abcd", R2 / "04_gr2m"
OUT = R2 / "04_comparacion"; OUT.mkdir(exist_ok=True)
FIG = R2 / "07_figuras"
ROJO, AZUL, NEGRO, GRIS, AMBAR, NARANJA = "#b91c1c", "#1d4ed8", "#1f2328", "#9aa3b2", "#b07a0c", "#ea580c"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "axes.grid.axis": "y",
                     "grid.color": "#d9d9d9", "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False})
EST = ["La Balsa", "Juanchito", "La Victoria", "La Virginia", "Irra", "La Pintada", "Puente Iglesias", "Bolombolo", "Cañafisto", "Presa"]
COD = dict(zip(EST, ["26027010", "26067010", "26107070", "26177030", "26167070", "26187110", "26207030", "26207080", "26217050", "PRESA"]))
CAL, VAL = ("1982-01-01", "2005-12-01"), ("2006-01-01", "2023-12-01")
qobs = pd.read_csv(R2 / "03_caudales" / "Q_mensual_estaciones.csv", index_col=0, parse_dates=True)
coma = lambda v, d=2: f"{v:.{d}f}".replace(".", ",").replace("-", "−")  # noqa: E731


def nselog(s, o):
    m = np.isfinite(o) & np.isfinite(s)
    s, o = s[m], o[m]
    if len(o) < 24:
        return np.nan
    e = 0.01 * o.mean()
    ls, lo = np.log(s + e), np.log(o + e)
    return 1 - ((ls - lo) ** 2).sum() / ((lo - lo.mean()) ** 2).sum()


# ------------------------------------------------------------------------------------------------- 1. métricas
ma = pd.concat([pd.read_csv(AB / "metricas.csv"), pd.read_csv(AB / "regionalizado_metricas.csv")])
ma = ma[ma.modelo.isin(["abcd semidistribuido", "abcd semidistribuido regionalizado", "abcd agregado"])].copy()
ma["modelo"] = ma.modelo.map({"abcd semidistribuido": "abcd distribuido secuencial (4 parámetros por unidad)",
                              "abcd semidistribuido regionalizado": "abcd distribuido multisitio (14 parámetros)",
                              "abcd agregado": "abcd agregado (4 parámetros)"})
# NSE logarítmico del abcd a partir de sus caudales simulados
nl = []
for _, r in ma.iterrows():
    if r.modelo.startswith("abcd distribuido multisitio"):
        f = AB / f"Q_simulado_reg_{r.producto.replace(' ', '_')}_{'PM' if r.ETo == 'Penman-Monteith' else 'HG'}.csv"
    elif r.modelo.startswith("abcd distribuido secuencial"):
        f = AB / f"Q_simulado_{r.producto.replace(' ', '_')}.csv"
    else:
        nl.append(np.nan); continue
    if not f.exists() or (r.modelo.startswith("abcd distribuido secuencial") and r.ETo != "Penman-Monteith"):
        nl.append(np.nan); continue
    q = pd.read_csv(f, index_col=0, parse_dates=True)[r["estación"]]
    a, b = (CAL if r.periodo.startswith("cal") else VAL)
    m = (q.index >= a) & (q.index <= b)
    nl.append(nselog(q.values[m], qobs[COD[r["estación"]]].reindex(q.index).values[m]))
ma["NSElog"] = nl
mg = pd.read_csv(GR / "metricas.csv")
mg = mg[mg.modelo.str.startswith("GR2M") | mg.modelo.str.startswith("empírico")].copy()
mg["modelo"] = mg.modelo.replace({"GR2M distribuido": "GR2M distribuido multisitio (11 parámetros)", "GR2M agregado": "GR2M agregado (2 parámetros)"})
M = pd.concat([ma, mg], ignore_index=True)
M["per"] = np.where(M.periodo.str.startswith("cal"), "cal", "val")
M.round(3).to_csv(OUT / "metricas_modelos.csv", index=False, encoding="utf-8-sig")

dist = M[M.modelo.str.contains("multisitio")]
kv = dist[dist.per == "val"].groupby(["modelo", "producto", "ETo"]).KGE.mean()
best = kv.idxmax()
fam = "abcd" if best[0].startswith("abcd") else "GR2M"
best_g = kv[kv.index.get_level_values(0).str.startswith("GR2M")].idxmax()
best_a = kv[kv.index.get_level_values(0).str.startswith("abcd")].idxmax()
princ = {"modelo": fam, "producto": best[1], "eto": best[2], "KGE medio val": float(kv.max()),
         "abcd": {"producto": best_a[1], "eto": best_a[2], "KGE medio val": float(kv[best_a])},
         "GR2M": {"producto": best_g[1], "eto": best_g[2], "KGE medio val": float(kv[best_g])}}
json.dump(princ, open(OUT / "modelo_principal.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("modelo principal:", princ)

# tabla resumen: misma lluvia y ETo, dos modelos
filas = []
for mod in ["abcd distribuido multisitio (14 parámetros)", "GR2M distribuido multisitio (11 parámetros)",
            "abcd distribuido secuencial (4 parámetros por unidad)", "abcd agregado (4 parámetros)", "GR2M agregado (2 parámetros)",
            "empírico con memoria Q = α·W + γ·Q(t−1) + β", "empírico Q = α·W + β"]:
    d = M[M.modelo == mod]
    for (prod, eto), g in d.groupby(["producto", "ETo"]):
        pz = g[(g.codigo == "PRESA") & (g.per == "val")]
        if not len(pz):
            continue
        pz = pz.iloc[0]
        est = g[g.per == "val"]
        filas.append({"modelo": mod, "producto": prod, "ETo": eto,
                      "KGE medio 10 estaciones (val)": est.KGE.mean() if len(est) > 1 else np.nan,
                      "KGE presa (val)": pz.KGE, "NSE presa (val)": pz.NSE, "NSE log presa (val)": pz.NSElog,
                      "PBIAS presa (val, %)": pz.PBIAS})
T = pd.DataFrame(filas)
T.round(3).to_csv(OUT / "resumen_modelos.csv", index=False, encoding="utf-8-sig")
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
print(T.round(2).to_string())

# ------------------------------------------------------------------------------------------------- 2. figura KGE por estación
pa, pg = princ["abcd"], princ["GR2M"]
sel_a = M[(M.modelo == "abcd distribuido multisitio (14 parámetros)") & (M.producto == pa["producto"]) & (M.ETo == pa["eto"]) & (M.per == "val")].set_index("estación")
sel_g = M[(M.modelo == "GR2M distribuido multisitio (11 parámetros)") & (M.producto == pg["producto"]) & (M.ETo == pg["eto"]) & (M.per == "val")].set_index("estación")
fig, axs = plt.subplots(1, 2, figsize=(14, 4.4), gridspec_kw={"width_ratios": [2.2, 1]})
ax = axs[0]
x = np.arange(len(EST)); w = 0.38
b1 = ax.bar(x - w / 2, sel_a.loc[EST, "KGE"], w, color=NEGRO, label=f"abcd (14 parámetros) · media {coma(sel_a.KGE.mean())}")
b2 = ax.bar(x + w / 2, sel_g.loc[EST, "KGE"], w, color=AMBAR, label=f"GR2M (11 parámetros) · media {coma(sel_g.KGE.mean())}")
ax.bar_label(b1, labels=[coma(v) for v in sel_a.loc[EST, "KGE"]], fontsize=7, padding=2)
ax.bar_label(b2, labels=[coma(v) for v in sel_g.loc[EST, "KGE"]], fontsize=7, padding=2)
ax.axhline(0.75, color="#555", lw=0.8, ls=":")
ax.set_xticks(x, EST, rotation=25, ha="right"); ax.set_ylim(0, 1.05); ax.set_ylabel("KGE de validación 2006–2023")
ax.legend(loc="upper left", ncol=2, fontsize=8.5)
ax.set_title(f"a) Validación por estación (P {pa['producto']}, ETo {pa['eto']})", fontsize=10.5, loc="left")
ax = axs[1]
mets = ["KGE", "NSE", "NSElog"]
va = [sel_a.loc["Presa", m] for m in mets]; vg = [sel_g.loc["Presa", m] for m in mets]
x2 = np.arange(3)
b1 = ax.bar(x2 - w / 2, va, w, color=NEGRO, label="abcd"); b2 = ax.bar(x2 + w / 2, vg, w, color=AMBAR, label="GR2M")
ax.bar_label(b1, labels=[coma(v) for v in va], fontsize=8, padding=2); ax.bar_label(b2, labels=[coma(v) for v in vg], fontsize=8, padding=2)
ax.set_xticks(x2, ["KGE", "NSE", "NSE log"]); ax.set_ylim(0, 1.15); ax.legend(fontsize=8.5, loc="upper center", ncol=2)
ax.set_title("b) Presa, validación 2006–2017", fontsize=10.5, loc="left")
fig.tight_layout()
fig.savefig(FIG / "fig_modelos_kge.png", dpi=300, bbox_inches="tight", facecolor="white"); plt.close(fig)

# ------------------------------------------------------------------------------------------------- 3. figura ENSO y memoria
EA, EG = R2 / "06_enso_suelo_Q", R2 / "06_enso_suelo_Q_gr2m"
TR = ["DEF", "MAM", "JJA", "SON"]
sa, sg = pd.read_csv(EA / "suelo_compuestos.csv"), pd.read_csv(EG / "suelo_compuestos.csv")
qa, qg = pd.read_csv(EA / "caudales_compuestos.csv"), pd.read_csv(EG / "caudales_compuestos.csv")
ra, rg = pd.read_csv(EA / "rezagos_P.csv", index_col=0), pd.read_csv(EG / "rezagos_P.csv", index_col=0)
oa, og = pd.read_csv(EA / "rezagos_oni.csv").set_index("variable"), pd.read_csv(EG / "rezagos_oni.csv").set_index("variable")
fig, axs = plt.subplots(1, 3, figsize=(16, 4.5))
ax = axs[0]
w = 0.26
for j, (fa, c) in enumerate([("El Niño", ROJO), ("La Niña", AZUL)]):
    a_ = sa[sa.fase == fa].set_index("trimestre").loc[TR]; g_ = sg[sg.fase == fa].set_index("trimestre").loc[TR]
    xx = np.arange(4) + (j - 0.5) * 0.42
    ax.bar(xx - w / 3, a_["z P cuenca"], w / 1.5, facecolor="white", edgecolor=c, hatch="////", lw=0.8, label=f"Lluvia · {fa}")
    ax.bar(xx + w / 3, a_["z S cuenca"], w / 1.5, color=c, alpha=0.9, label=f"Suelo abcd · {fa}")
    ax.scatter(xx + w / 3, g_["z S cuenca"], marker="D", s=30, color=AMBAR, edgecolor=NEGRO, zorder=3, label="Suelo GR2M" if j == 0 else None)
ax.axhline(0, color="#555", lw=0.8); ax.set_xticks(range(4), TR); ax.set_ylabel("z medio de la cuenca")
ax.legend(fontsize=7.5, ncol=2, loc="lower center", bbox_to_anchor=(0.5, -0.33))
ax.set_title("a) Humedad del suelo: abcd (barras) y GR2M (rombos)", fontsize=10, loc="left")
ax = axs[1]
for j, (fa, c) in enumerate([("El Niño", ROJO), ("La Niña", AZUL)]):
    o_ = qa[(qa["estación"] == "Presa") & (qa.fase == fa)].set_index("trimestre").loc[TR]
    g_ = qg[(qg["estación"] == "Presa") & (qg.fase == fa)].set_index("trimestre").loc[TR]
    xx = np.arange(4) + (j - 0.5) * 0.4
    ax.bar(xx, o_["z Q observado"], 0.36, color=c, alpha=0.75, label=f"Observado · {fa}")
    ax.scatter(xx - 0.07, o_["z Q simulado"], marker="o", s=30, color=NEGRO, zorder=3, label="abcd" if j == 0 else None)
    ax.scatter(xx + 0.07, g_["z Q simulado"], marker="D", s=30, color=AMBAR, edgecolor=NEGRO, zorder=3, label="GR2M" if j == 0 else None)
ax.axhline(0, color="#555", lw=0.8); ax.set_xticks(range(4), TR); ax.set_ylabel("z del caudal en la presa")
ax.legend(fontsize=7.5, ncol=2, loc="lower center", bbox_to_anchor=(0.5, -0.33))
ax.set_title("b) Caudal en la presa: observado y simulado", fontsize=10, loc="left")
ax = axs[2]
k = np.arange(7)
ax.plot(k, ra.loc["P → Q obs"].values, "-o", color=AZUL, lw=2.4, ms=4, label=f"Observado (memoria r1 = {coma(oa.loc['Q obs presa', 'memoria r1'])})")
ax.plot(k, ra.loc["P → Q sim"].values, "-o", color=NEGRO, lw=1.8, ms=4, label=f"abcd (r1 = {coma(oa.loc['Q sim presa', 'memoria r1'])})")
ax.plot(k, rg.loc["P → Q sim"].values, "--D", color=AMBAR, lw=1.8, ms=4, label=f"GR2M (r1 = {coma(og.loc['Q sim presa', 'memoria r1'])})")
ax.set_xlabel("Rezago (meses): el caudal va detrás de la lluvia"); ax.set_ylabel("Correlación con la anomalía de lluvia")
ax.set_ylim(0, 1); ax.legend(fontsize=8)
ax.set_title("c) Memoria: respuesta del caudal en la presa a la lluvia", fontsize=10, loc="left")
fig.tight_layout()
fig.savefig(FIG / "fig_modelos_enso.png", dpi=300, bbox_inches="tight", facecolor="white"); plt.close(fig)
print("listo")
