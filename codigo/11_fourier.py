"""
Trabajo 2 · numeral 5: análisis espectral (transformada de Fourier) de la lluvia, el suelo, el acuífero y el caudal de la cuenca.

Series mensuales medias de la cuenca (06_enso_suelo_caudales.py): P del Cubo, S y G del modelo abcd final, caudal en la presa
observado (1981–2017) y simulado (1981–2023), y el ONI. Se usan anomalías estandarizadas por mes calendario (sin ciclo anual).

  1. Densidad espectral por el método de Welch (FFT de segmentos de 128 meses, ventana de Hann, traslape del 50 %), normalizada
     para que su integral sea la varianza (= 1). Referencia: ruido rojo AR(1) con la misma autocorrelación de un mes, con su
     banda del 95 % (χ² con 2 × número de segmentos grados de libertad).
  2. Fracción de la varianza por bandas de periodo (periodograma de toda la serie): < 1 año, 1–2 años, 2–7 años (ENSO), > 7 años.
  3. La cuenca como filtro: ganancia |H(f)| = √(S_xx / S_PP) de cada variable respecto a la lluvia (> 1: la variable tiene más
     varianza que la lluvia en esa banda, relativa a su varianza total).
  4. Coherencia cuadrática con el ONI y su nivel de significancia del 95 %, 1 − 0,05^(1/(n_seg − 1)).
  5. Memoria: escala integral de tiempo T = 1 + 2 Σ ρ_k (hasta el primer cruce por cero de la autocorrelación), en meses.

Salidas: trabajo2/resultados/10_fourier/ y figura en 07_figuras/
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import signal, stats  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
R2 = ROOT / "trabajo2" / "resultados"
OUT = R2 / "10_fourier"
OUT.mkdir(parents=True, exist_ok=True)
FIG = R2 / "07_figuras"
NSEG = 128
ROJO, AZUL, NEGRO, GRIS, AMBAR, NARANJA = "#b91c1c", "#1d4ed8", "#1f2328", "#9aa3b2", "#b07a0c", "#ea580c"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": "#d9d9d9", "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False})

sc = pd.read_csv(R2 / "06_enso_suelo_Q" / "series_cuenca.csv", index_col=0, parse_dates=True)
an = pd.read_csv(R2 / "06_enso_suelo_Q" / "anomalias_mensuales_cuenca.csv", index_col=0, parse_dates=True)
qo = pd.read_csv(R2 / "03_caudales" / "Q_mensual_estaciones.csv", index_col=0, parse_dates=True)["PRESA"].reindex(sc.index)
qo[qo.index.year > 2017] = np.nan


def zmes(s):
    g = s.groupby(s.index.month)
    return (s - g.transform("mean")) / g.transform("std")


V = {"Lluvia P (Cubo)": zmes(sc.P), "Suelo S": zmes(sc.S), "Acuífero G": zmes(sc.G),
     "Caudal simulado (presa)": an["Q sim presa"], "Caudal observado (presa)": zmes(qo["1981":"2017"].interpolate(limit=3)),
     "ONI": zmes(sc.ONI)}
V = {k: v.dropna() for k, v in V.items()}
COL = {"Lluvia P (Cubo)": AZUL, "Suelo S": AMBAR, "Acuífero G": GRIS, "Caudal simulado (presa)": NARANJA,
       "Caudal observado (presa)": NEGRO, "ONI": ROJO}
print({k: (v.index[0].strftime("%Y-%m"), v.index[-1].strftime("%Y-%m"), len(v)) for k, v in V.items()})


def welch(x):
    f, p = signal.welch(x, fs=1.0, window="hann", nperseg=NSEG, noverlap=NSEG // 2, detrend="linear")
    return f[1:], p[1:] / np.trapezoid(p[1:], f[1:]) * np.var(x)   # densidad cuya integral ≈ varianza


def escala_integral(x):
    x = np.asarray(x) - np.mean(x)
    r = [1.0]
    for k in range(1, 60):
        rk = np.corrcoef(x[:-k], x[k:])[0, 1]
        if rk <= 0:
            break
        r.append(rk)
    return 1 + 2 * sum(r[1:]), r[1] if len(r) > 1 else 0.0


ESP, filas = {}, []
for nom, s in V.items():
    x = s.values
    f, p = welch(x)
    T, r1 = escala_integral(x)
    nseg = (len(x) - NSEG) // (NSEG // 2) + 1
    roja = (1 - r1 ** 2) / (1 - 2 * r1 * np.cos(2 * np.pi * f) + r1 ** 2)
    roja = roja / np.trapezoid(roja, f) * np.var(x)
    lim = roja * stats.chi2.ppf(0.95, 2 * nseg) / (2 * nseg)
    ESP[nom] = (f, p, roja, lim)
    # periodograma completo para las bandas
    xf = signal.detrend(x)
    F = np.fft.rfftfreq(len(xf)); Pw = np.abs(np.fft.rfft(xf)) ** 2
    F, Pw = F[1:], Pw[1:]
    per = 1 / F / 12                                             # años
    tot = Pw.sum()
    filas.append({"variable": nom, "periodo": f"{s.index[0].year}–{s.index[-1].year}", "r(1 mes)": r1,
                  "escala integral de tiempo (meses)": T,
                  "varianza < 1 año (%)": 100 * Pw[per < 1].sum() / tot, "varianza 1–2 años (%)": 100 * Pw[(per >= 1) & (per < 2)].sum() / tot,
                  "varianza 2–7 años, ENSO (%)": 100 * Pw[(per >= 2) & (per <= 7)].sum() / tot, "varianza > 7 años (%)": 100 * Pw[per > 7].sum() / tot,
                  "picos sobre ruido rojo (años)": ", ".join(f"{1 / ff / 12:.1f}" for ff, pp, ll in zip(f, p, lim) if pp > ll and 1 / ff / 12 >= 1)})
tab = pd.DataFrame(filas).set_index("variable")
tab.to_csv(OUT / "bandas_y_memoria.csv", encoding="utf-8-sig")
print(tab.round(2).to_string())

# coherencia con el ONI y ganancia respecto a la lluvia
coh = {}
for nom, s in V.items():
    if nom == "ONI":
        continue
    j = pd.concat([s, V["ONI"]], axis=1, join="inner").dropna()
    f, c = signal.coherence(j.iloc[:, 0].values, j.iloc[:, 1].values, fs=1.0, window="hann", nperseg=NSEG, noverlap=NSEG // 2, detrend="linear")
    nseg = (len(j) - NSEG) // (NSEG // 2) + 1
    coh[nom] = (f[1:], c[1:], 1 - 0.05 ** (1 / (nseg - 1)))
ganancia = {}
fP, pP = ESP["Lluvia P (Cubo)"][:2]
for nom in ["Suelo S", "Acuífero G", "Caudal simulado (presa)", "Caudal observado (presa)"]:
    ganancia[nom] = np.sqrt(ESP[nom][1] / pP)
banda = (1 / fP / 12 >= 2) & (1 / fP / 12 <= 7)
res_c = pd.DataFrame({nom: {"coherencia media con el ONI, 2–7 años": c[(1 / f / 12 >= 2) & (1 / f / 12 <= 7)].mean(),
                            "nivel 95 %": lv,
                            "ganancia media respecto a la lluvia, 2–7 años": ganancia[nom][banda].mean() if nom in ganancia else np.nan,
                            "ganancia media respecto a la lluvia, < 1 año": ganancia[nom][1 / fP / 12 < 1].mean() if nom in ganancia else np.nan}
                      for nom, (f, c, lv) in coh.items()}).T
res_c.index.name = "variable"
res_c.to_csv(OUT / "coherencia_ganancia.csv", encoding="utf-8-sig")
print(res_c.round(2).to_string())

# ------------------------------------------------------------------------------------------------- figura (300 dpi)
fig, axs = plt.subplots(1, 3, figsize=(16, 4.8))
ax = axs[0]
for nom in ["Lluvia P (Cubo)", "Suelo S", "Caudal observado (presa)", "ONI"]:
    f, p, roja, lim = ESP[nom]
    per = 1 / f / 12
    ax.plot(per, p, color=COL[nom], lw=2, label=nom)
    ax.plot(per, lim, color=COL[nom], lw=0.9, ls=":")
ax.axvspan(2, 7, color=GRIS, alpha=0.15); ax.text(3.7, ax.get_ylim()[1] * 0.92 if False else 0, "")
ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(per.max() * 1.02, per.min())
ax.set_xticks([0.25, 0.5, 1, 2, 3, 5, 7, 10]); ax.set_xticklabels(["0,25", "0,5", "1", "2", "3", "5", "7", "10"])
ax.set_xlabel("Periodo (años)"); ax.set_ylabel("Densidad espectral (varianza por ciclo/mes)")
ax.legend(fontsize=8, loc="lower left"); ax.set_title("Espectros (punteado: 95 % del ruido rojo)", fontsize=10.5)
ax = axs[1]
for nom, g in ganancia.items():
    ax.plot(1 / fP / 12, g, color=COL[nom], lw=2, label=nom)
ax.axhline(1, color="#555", lw=0.8); ax.axvspan(2, 7, color=GRIS, alpha=0.15)
ax.set_xscale("log"); ax.set_xlim((1 / fP / 12).max() * 1.02, (1 / fP / 12).min())
ax.set_xticks([0.25, 0.5, 1, 2, 3, 5, 7, 10]); ax.set_xticklabels(["0,25", "0,5", "1", "2", "3", "5", "7", "10"])
ax.set_xlabel("Periodo (años)"); ax.set_ylabel("Ganancia √(S variable / S lluvia)")
ax.legend(fontsize=8, loc="lower left"); ax.set_title("La cuenca como filtro: amplifica los periodos largos", fontsize=10.5)
ax = axs[2]
for nom in ["Lluvia P (Cubo)", "Suelo S", "Caudal observado (presa)", "Caudal simulado (presa)"]:
    f, c, lv = coh[nom]
    ax.plot(1 / f / 12, c, color=COL[nom], lw=2, label=nom)
ax.axhline(coh["Caudal observado (presa)"][2], color="#555", lw=0.8, ls=":")
ax.text(9.5, coh["Caudal observado (presa)"][2] + 0.01, "95 %", fontsize=8, color="#555", ha="left")
ax.axvspan(2, 7, color=GRIS, alpha=0.15)
ax.set_xscale("log"); ax.set_xlim(10.7 * 1.02, 0.5)
ax.set_xticks([0.5, 1, 2, 3, 5, 7, 10]); ax.set_xticklabels(["0,5", "1", "2", "3", "5", "7", "10"])
ax.set_ylim(0, 1); ax.set_xlabel("Periodo (años)"); ax.set_ylabel("Coherencia cuadrática con el ONI")
ax.legend(fontsize=8, loc="upper right"); ax.set_title("Coherencia con el ONI", fontsize=10.5)
fig.suptitle("Análisis espectral de las anomalías mensuales de la cuenca (Welch, segmentos de 128 meses) · banda gris: 2–7 años (ENSO)",
             fontsize=11)
fig.tight_layout()
fig.savefig(FIG / "fig_fourier.png", dpi=300, bbox_inches="tight", facecolor="white")
plt.close(fig)
