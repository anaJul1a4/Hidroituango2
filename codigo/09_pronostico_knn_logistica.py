"""
Trabajo 2 · numeral 5 (técnicas de análisis de datos para decisiones de generación):
pronóstico estacional del aporte a la presa con KNN (años análogos) y probabilidad de un trimestre seco con regresión logística.

Momento del pronóstico: fin del mes t. Información disponible entonces (predictores):
  · ONI del trimestre que termina en t (el trimestre centrado en t−1; el centrado en t todavía no se conoce) y su cambio en 3 meses.
  · Humedad del suelo S y agua subterránea G medias de la cuenca al final de t, del modelo abcd final (04b, Cubo IDEAM).
Todos se estandarizan por mes calendario.

Objetivos (caudal observado en la presa, 1981–2017):
  · Q3: aporte medio de los tres meses siguientes (t+1 … t+3).
  · Q de cada mes con anticipación h = 1 … 6.
  · Evento «trimestre seco»: Q3 por debajo del percentil 20 de la climatología de Q3 para ese mes de emisión.

KNN (análogos): los k estados históricos más parecidos (distancia euclidiana en los cuatro predictores estandarizados), buscados en el
mismo mes calendario ± 1. Cada análogo aporta lo que ocurrió después, como anomalía estandarizada de ln Q de su mes, que se lleva a la
climatología del mes pronosticado. Resultado: un conjunto de k trayectorias → mediana, intervalo del 80 % (percentiles 10–90) y
probabilidad del evento (fracción de análogos bajo el umbral). k se elige por CRPS en validación cruzada.

Regresión logística: P(evento) = 1 / (1 + exp(−(β0 + β·x))), con x = ONI (modelo 1) o ONI y S (modelo 2); máxima verosimilitud por
mínimos cuadrados reponderados (IRLS).

Validación cruzada dejando un año fuera: se pronostican los 12 meses de emisión del año y; se excluyen del entrenamiento (análogos,
umbral, climatología y ajuste logístico) los meses de emisión entre julio de y−1 y junio de y+1, para que ninguna ventana objetivo de
entrenamiento se traslape con las de prueba. Referencias: climatología (todos los años de entrenamiento del mismo mes) y persistencia
de la anomalía del último mes.

Salidas: trabajo2/resultados/08_pronostico/
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
OUT = R2 / "08_pronostico"
OUT.mkdir(parents=True, exist_ok=True)
FIG = R2 / "07_figuras"
DPI = 300
ROJO, AZUL, NEGRO, GRIS, AMBAR, NARANJA = "#b91c1c", "#1d4ed8", "#1f2328", "#9aa3b2", "#b07a0c", "#ea580c"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": "#d9d9d9", "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False})
coma = lambda v, d=2: f"{v:.{d}f}".replace(".", ",").replace("-", "−")  # noqa: E731
H = 6
KS = [5, 7, 10, 15, 20]

# ------------------------------------------------------------------------------------------------- datos
sc = pd.read_csv(R2 / "06_enso_suelo_Q" / "series_cuenca.csv", index_col=0, parse_dates=True)
qo = pd.read_csv(R2 / "03_caudales" / "Q_mensual_estaciones.csv", index_col=0, parse_dates=True)["PRESA"]
idx = sc.index
qo = qo.reindex(idx)
qo[qo.index.year > 2017] = np.nan
mes = idx.month.values
anio = idx.year.values
T = len(idx)


def zmes(s):
    g = s.groupby(s.index.month)
    return (s - g.transform("mean")) / g.transform("std")


oni_disp = sc.ONI.shift(1)                                  # trimestre que termina en t
X = pd.DataFrame({"ONI": oni_disp, "ΔONI": oni_disp - oni_disp.shift(3), "S": sc.S, "G": sc.G})
Xz = X.apply(zmes)
# objetivos en ln Q
lq = np.log(qo)
q3 = pd.Series([qo.iloc[t + 1:t + 4].mean() if t + 3 < T and qo.iloc[t + 1:t + 4].notna().all() else np.nan for t in range(T)], idx)
lq3 = np.log(q3)
fut = np.full((T, H), np.nan)                                 # ln Q en t+h
for h in range(1, H + 1):
    fut[:-h, h - 1] = lq.values[h:]
persis = zmes(lq).values                                      # anomalía del último mes (persistencia)
ok = Xz.notna().all(axis=1).values & q3.notna().values             # meses de emisión utilizables
ok &= (anio >= 1982)
mvec = mes


def crps_ens(ens, y):
    ens = np.asarray(ens)
    return np.mean(np.abs(ens - y)) - 0.5 * np.mean(np.abs(ens[:, None] - ens[None, :]))


def logit_fit(x, y, lam=1e-3, it=50):
    A = np.column_stack([np.ones(len(x)), x])
    b = np.zeros(A.shape[1])
    for _ in range(it):
        p = 1 / (1 + np.exp(-A @ b))
        W = p * (1 - p)
        Hm = A.T @ (A * W[:, None]) + lam * np.eye(len(b))
        g = A.T @ (y - p) - lam * b
        d = np.linalg.solve(Hm, g)
        b += d
        if np.abs(d).max() < 1e-8:
            break
    cov = np.linalg.inv(A.T @ (A * (p * (1 - p))[:, None]))
    return b, np.sqrt(np.diag(cov))


def logit_pred(b, x):
    return 1 / (1 + np.exp(-(b[0] + np.atleast_2d(x) @ b[1:])))


def auc(p, y):
    p, y = np.asarray(p), np.asarray(y).astype(bool)
    pos, neg = p[y], p[~y]
    return np.mean([(pp > neg).mean() + 0.5 * (pp == neg).mean() for pp in pos])


# ------------------------------------------------------------------------------------------------- validación cruzada
años = sorted(set(anio[ok]))
Z = Xz.values
res = {k: [] for k in KS}
filas = []
for y in años:
    test = np.where(ok & (anio == y))[0]
    lim0, lim1 = pd.Timestamp(f"{y - 1}-07-01"), pd.Timestamp(f"{y + 1}-06-30")
    train = ok & ~((idx >= lim0) & (idx <= lim1))
    # climatología de ln Q3 y de ln Q por mes, con años de entrenamiento
    for t in test:
        m = mvec[t]
        cand = np.where(train & np.isin(mvec, [(m - 2) % 12 + 1, m, m % 12 + 1]))[0]
        # anomalías estandarizadas del objetivo en cada análogo, respecto a su propio mes de emisión
        def norm(vals, meses, mm):
            out = np.empty(len(vals))
            for j, (v, mj) in enumerate(zip(vals, meses)):
                ref = lq3.values[train & (mvec == mj)]
                out[j] = (v - ref.mean()) / ref.std(ddof=1)
            return out
        ref_m = lq3.values[train & (mvec == m)]
        mu, sd = ref_m.mean(), ref_m.std(ddof=1)
        thr = np.quantile(q3.values[train & (mvec == m)], 0.2)          # umbral del evento (m³/s)
        d = np.sqrt(((Z[cand] - Z[t]) ** 2).sum(1))
        orden = cand[np.argsort(d)]
        za_all = norm(lq3.values[orden], mvec[orden], m)
        # trayectorias mensuales
        fz = np.full((len(orden), H), np.nan)
        for j, a in enumerate(orden):
            for h in range(H):
                ma = (mvec[a] + h) % 12 + 1
                ref = lq.values[(mvec == ma) & ~np.isnan(lq.values) & ~((idx >= lim0) & (idx <= lim1))]
                fz[j, h] = (fut[a, h] - ref.mean()) / ref.std(ddof=1)
        clim_q3 = q3.values[train & (mvec == m)]
        obs = q3.values[t]
        for k in KS:
            ens = np.exp(mu + za_all[:k] * sd)
            res[k].append(crps_ens(ens, obs))
        fila = {"fecha": idx[t], "mes": m, "año": y, "Q3 obs": obs, "umbral p20": thr, "evento": float(obs < thr),
                "clim mediana": np.median(clim_q3), "clim crps": crps_ens(clim_q3, obs),
                "clim p10": np.quantile(clim_q3, 0.1), "clim p90": np.quantile(clim_q3, 0.9),
                "persist": np.exp(mu + persis[t] * sd)}
        for k in KS:
            ens = np.exp(mu + za_all[:k] * sd)
            fila[f"knn{k} mediana"] = np.median(ens)
            fila[f"knn{k} p10"] = np.quantile(ens, 0.1)
            fila[f"knn{k} p90"] = np.quantile(ens, 0.9)
            fila[f"knn{k} prob"] = (ens < thr).mean()
            fila[f"knn{k} crps"] = crps_ens(ens, obs)
            # mensual h = 1..6
            for h in range(H):
                mh = (m + h) % 12 + 1
                ref = lq.values[(mvec == mh) & ~np.isnan(lq.values) & ~((idx >= lim0) & (idx <= lim1))]
                ensh = np.exp(ref.mean() + fz[:k, h][~np.isnan(fz[:k, h])] * ref.std(ddof=1))
                yo = np.exp(fut[t, h])
                fila[f"knn{k} h{h + 1} med"] = np.median(ensh) if len(ensh) else np.nan
                fila[f"knn{k} h{h + 1} p10"] = np.quantile(ensh, 0.1) if len(ensh) else np.nan
                fila[f"knn{k} h{h + 1} p90"] = np.quantile(ensh, 0.9) if len(ensh) else np.nan
                fila[f"knn{k} h{h + 1} crps"] = crps_ens(ensh, yo) if len(ensh) and np.isfinite(yo) else np.nan
        for h in range(H):
            mh = (m + h) % 12 + 1
            ref = lq.values[(mvec == mh) & ~np.isnan(lq.values) & ~((idx >= lim0) & (idx <= lim1))]
            yo = np.exp(fut[t, h])
            fila[f"obs h{h + 1}"] = yo
            fila[f"clim h{h + 1} med"] = np.exp(np.median(ref))
            fila[f"clim h{h + 1} crps"] = crps_ens(np.exp(ref), yo) if np.isfinite(yo) else np.nan
            fila[f"pers h{h + 1}"] = np.exp(ref.mean() + persis[t] * ref.std(ddof=1))
        # logística: evento en entrenamiento con umbral de cada mes de emisión (entrenamiento)
        ytr = np.zeros(train.sum())
        tr_i = np.where(train)[0]
        for j, a in enumerate(tr_i):
            ytr[j] = q3.values[a] < np.quantile(q3.values[train & (mvec == mvec[a])], 0.2)
        for nom, cols in [("logit ONI", [0]), ("logit ONI+S", [0, 2])]:
            b, _ = logit_fit(Z[tr_i][:, cols], ytr)
            fila[f"{nom} prob"] = float(logit_pred(b, Z[t, cols])[0])
        fila["clim prob"] = 0.2
        filas.append(fila)
    print(y, end=" ", flush=True)
print()
cv = pd.DataFrame(filas).set_index("fecha")
crps_k = {k: np.mean(res[k]) for k in KS}
K = min(crps_k, key=crps_k.get)
print("CRPS por k:", {k: round(v, 1) for k, v in crps_k.items()}, "→ k =", K)
cv.to_csv(OUT / "validacion_cruzada.csv", encoding="utf-8-sig")


# ------------------------------------------------------------------------------------------------- métricas
def nse(s, o):
    s, o = np.asarray(s), np.asarray(o)
    m = np.isfinite(s) & np.isfinite(o)
    return 1 - np.sum((s[m] - o[m]) ** 2) / np.sum((o[m] - o[m].mean()) ** 2)


def bs(p, y):
    return np.mean((np.asarray(p) - np.asarray(y)) ** 2)


o = cv["Q3 obs"]
met = pd.DataFrame({
    "Climatología": {"NSE de la mediana": nse(cv["clim mediana"], o), "CRPS (m³/s)": cv["clim crps"].mean(), "CRPSS": 0.0,
                     "Cobertura del intervalo 80 % (%)": 100 * ((o >= cv["clim p10"]) & (o <= cv["clim p90"])).mean(),
                     "Ancho medio del intervalo 80 % (m³/s)": (cv["clim p90"] - cv["clim p10"]).mean()},
    "Persistencia": {"NSE de la mediana": nse(cv["persist"], o)},
    f"KNN (k = {K})": {"NSE de la mediana": nse(cv[f"knn{K} mediana"], o), "CRPS (m³/s)": cv[f"knn{K} crps"].mean(),
                       "CRPSS": 1 - cv[f"knn{K} crps"].mean() / cv["clim crps"].mean(),
                       "Cobertura del intervalo 80 % (%)": 100 * ((o >= cv[f"knn{K} p10"]) & (o <= cv[f"knn{K} p90"])).mean(),
                       "Ancho medio del intervalo 80 % (m³/s)": (cv[f"knn{K} p90"] - cv[f"knn{K} p10"]).mean()}}).T
met.index.name = "Aporte medio de los 3 meses siguientes"
met.to_csv(OUT / "metricas_Q3.csv", encoding="utf-8-sig")
print(met.round(3).to_string())

ev = cv.evento.values
prob = {"Climatología (20 %)": cv["clim prob"], f"KNN (k = {K})": cv[f"knn{K} prob"], "Logística · ONI": cv["logit ONI prob"],
        "Logística · ONI + suelo": cv["logit ONI+S prob"]}
bs0 = bs(cv["clim prob"], ev)
mprob = pd.DataFrame({n: {"Brier": bs(p, ev), "BSS": 1 - bs(p, ev) / bs0, "AUC (ROC)": auc(p, ev) if n[0] != "C" else 0.5}
                      for n, p in prob.items()}).T
mprob.index.name = "P(trimestre seco)"
mprob.to_csv(OUT / "metricas_probabilidad.csv", encoding="utf-8-sig")
print(mprob.round(3).to_string())

# horizonte mensual
hz = []
for h in range(1, H + 1):
    oh = cv[f"obs h{h}"]
    hz.append({"anticipación (meses)": h, "NSE KNN": nse(cv[f"knn{K} h{h} med"], oh), "NSE persistencia": nse(cv[f"pers h{h}"], oh),
               "NSE climatología": nse(cv[f"clim h{h} med"], oh),
               "CRPSS KNN": 1 - cv[f"knn{K} h{h} crps"].mean() / cv[f"clim h{h} crps"].mean(),
               "cobertura 80 % KNN (%)": 100 * ((oh >= cv[f"knn{K} h{h} p10"]) & (oh <= cv[f"knn{K} h{h} p90"]))[oh.notna()].mean()})
hz = pd.DataFrame(hz).set_index("anticipación (meses)")
hz.to_csv(OUT / "horizonte_mensual.csv", encoding="utf-8-sig")
print(hz.round(3).to_string())

# niveles de alerta
niveles = [("Verde (< 20 %)", 0, 0.2), ("Amarillo (20–50 %)", 0.2, 0.5), ("Rojo (≥ 50 %)", 0.5, 1.01)]
al = []
for n, p in list(prob.items())[1:]:
    for nv, a, b_ in niveles:
        sel = (p >= a) & (p < b_)
        al.append({"método": n, "nivel": nv, "meses": int(sel.sum()), "% de los meses": 100 * sel.mean(),
                   "frecuencia observada del trimestre seco (%)": 100 * ev[sel.values].mean() if sel.sum() else np.nan,
                   "% de los trimestres secos captados": 100 * (ev[sel.values].sum() / ev.sum())})
al = pd.DataFrame(al)
al.to_csv(OUT / "alertas.csv", index=False, encoding="utf-8-sig")
print(al.round(1).to_string())

# coeficientes con todos los datos
ytot = np.array([q3.values[a] < np.quantile(q3.values[ok & (mvec == mvec[a])], 0.2) for a in np.where(ok)[0]], float)
coef = []
for nom, cols in [("Logística · ONI", [0]), ("Logística · ONI + suelo", [0, 2])]:
    b, se = logit_fit(Z[ok][:, cols], ytot)
    for j, nm in enumerate(["constante"] + [X.columns[c] for c in cols]):
        coef.append({"modelo": nom, "variable": nm, "β": b[j], "error estándar": se[j], "z": b[j] / se[j],
                     "razón de odds por 1 σ": np.exp(b[j]) if j else np.nan})
coef = pd.DataFrame(coef)
coef.to_csv(OUT / "coeficientes_logistica.csv", index=False, encoding="utf-8-sig")
print(coef.round(3).to_string())
b2 = coef[coef.modelo == "Logística · ONI + suelo"]["β"].values
b1 = coef[coef.modelo == "Logística · ONI"]["β"].values

# ------------------------------------------------------------------------------------------------- figuras (300 dpi)
# 1. habilidad por anticipación
fig, axs = plt.subplots(1, 2, figsize=(11, 4.2))
hh = hz.index.values
axs[0].plot(hh, hz["NSE KNN"], "-o", color=AZUL, label=f"KNN (mediana de {K} análogos)")
axs[0].plot(hh, hz["NSE persistencia"], "-s", color=AMBAR, label="Persistencia de la anomalía")
axs[0].plot(hh, hz["NSE climatología"], "--", color=GRIS, label="Climatología")
axs[0].axhline(0, color="#555", lw=0.8); axs[0].set_xlabel("Anticipación (meses)"); axs[0].set_ylabel("NSE del caudal mensual en la presa")
axs[0].legend(fontsize=8.5); axs[0].set_title("Error del pronóstico central", fontsize=10.5)
axs[1].bar(hh - 0.2, hz["CRPSS KNN"] * 100, 0.4, color=AZUL, label="CRPSS frente a la climatología (%)")
axs[1].bar(hh + 0.2, hz["cobertura 80 % KNN (%)"], 0.4, color=GRIS, label="Cobertura del intervalo del 80 % (%)")
axs[1].axhline(80, color="#555", lw=0.8, ls=":"); axs[1].set_xlabel("Anticipación (meses)"); axs[1].set_ylabel("%")
for x_, v in zip(hh, hz["cobertura 80 % KNN (%)"]):
    axs[1].text(x_ + 0.2, v + 1, f"{v:.0f}", ha="center", fontsize=7.5)
for x_, v in zip(hh, hz["CRPSS KNN"] * 100):
    axs[1].text(x_ - 0.2, max(v, 0) + 1, f"{v:.0f}", ha="center", fontsize=7.5)
axs[1].legend(fontsize=8.5, loc="upper right"); axs[1].set_ylim(0, 100); axs[1].set_title("Pronóstico probabilístico (KNN)", fontsize=10.5)
fig.suptitle("Pronóstico del aporte mensual a la presa con años análogos · validación cruzada 1982–2017", fontsize=11)
fig.tight_layout(); fig.savefig(FIG / "fig_knn_horizonte.png", dpi=DPI, bbox_inches="tight", facecolor="white"); plt.close(fig)

# 2. curvas logísticas y comparación de probabilidades
fig, axs = plt.subplots(1, 3, figsize=(15, 4.4))
xo = np.linspace(-2.5, 3, 200)
ax = axs[0]
ax.plot(xo, logit_pred(b1, xo[:, None]), color=NEGRO, lw=2, label="Sólo ONI")
for sv, c, ls in [(-1, ROJO, "-"), (0, GRIS, "--"), (1, AZUL, "-")]:
    ax.plot(xo, logit_pred(b2, np.column_stack([xo, np.full_like(xo, sv)])), color=c, ls=ls, lw=1.6,
            label=f"ONI + suelo, S {'seco (−1 σ)' if sv < 0 else ('normal' if sv == 0 else 'húmedo (+1 σ)')}")
ax.axhspan(0.5, 1, color=ROJO, alpha=0.06); ax.axhspan(0.2, 0.5, color=AMBAR, alpha=0.08)
ax.set_xlabel("ONI del trimestre que acaba de terminar (anomalía estandarizada)"); ax.set_ylabel("P(trimestre seco)")
ax.set_ylim(0, 1); ax.legend(fontsize=8); ax.set_title("Regresión logística (todos los datos)", fontsize=10.5)
ax = axs[1]
for n, c, mk in [(f"KNN (k = {K})", AZUL, "o"), ("Logística · ONI", NEGRO, "^"), ("Logística · ONI + suelo", NARANJA, "s")]:
    p = prob[n].values
    bins = np.array([0, 0.1, 0.2, 0.35, 0.5, 0.7, 1.01])
    cx, cy, cn = [], [], []
    for a, b_ in zip(bins[:-1], bins[1:]):
        s = (p >= a) & (p < b_)
        if s.sum() >= 8:
            cx.append(p[s].mean()); cy.append(ev[s].mean()); cn.append(s.sum())
    ax.plot(cx, cy, "-" + mk, color=c, label=n, ms=5)
ax.plot([0, 1], [0, 1], ":", color="#555"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
ax.set_xlabel("Probabilidad pronosticada"); ax.set_ylabel("Frecuencia observada del trimestre seco")
ax.legend(fontsize=8); ax.set_title("Confiabilidad (validación cruzada)", fontsize=10.5)
ax = axs[2]
for n, c in [(f"KNN (k = {K})", AZUL), ("Logística · ONI", NEGRO), ("Logística · ONI + suelo", NARANJA)]:
    p = prob[n].values
    th = np.unique(np.concatenate([[1.1], p, [-0.1]]))[::-1]
    tpr = [(p[ev == 1] >= u).mean() for u in th]; fpr = [(p[ev == 0] >= u).mean() for u in th]
    ax.plot(fpr, tpr, color=c, lw=1.8, label=f"{n} · AUC {coma(mprob.loc[n, 'AUC (ROC)'])}")
ax.plot([0, 1], [0, 1], ":", color="#555"); ax.set_xlabel("Tasa de falsas alarmas"); ax.set_ylabel("Tasa de aciertos")
ax.legend(fontsize=8, loc="lower right"); ax.set_title("Curva ROC (validación cruzada)", fontsize=10.5)
fig.suptitle("Probabilidad de que el aporte de los tres meses siguientes quede bajo su percentil 20", fontsize=11)
fig.tight_layout(); fig.savefig(FIG / "fig_prob_trimestre_seco.png", dpi=DPI, bbox_inches="tight", facecolor="white"); plt.close(fig)

# ------------------------------------------------------------------------------------------------- datos para el sitio
ej = {}
for f_ in ["1997-08-01", "2009-08-01", "2015-08-01", "2010-08-01", "1991-11-01", "2007-09-01"]:
    r = cv.loc[f_]
    ej[pd.Timestamp(f_).strftime("%Y-%m")] = {
        "meses": [(pd.Timestamp(f_) + pd.DateOffset(months=h)).strftime("%Y-%m") for h in range(1, H + 1)],
        "med": [round(r[f"knn{K} h{h} med"], 0) for h in range(1, H + 1)],
        "p10": [round(r[f"knn{K} h{h} p10"], 0) for h in range(1, H + 1)],
        "p90": [round(r[f"knn{K} h{h} p90"], 0) for h in range(1, H + 1)],
        "clim": [round(r[f"clim h{h} med"], 0) for h in range(1, H + 1)],
        "obs": [round(r[f"obs h{h}"], 0) for h in range(1, H + 1)],
        "oni": round(float(X.loc[f_, "ONI"]), 2), "S": round(float(Xz.loc[f_, "S"]), 2),
        "pknn": round(float(r[f"knn{K} prob"]), 2), "plog": round(float(r["logit ONI+S prob"]), 2)}
sitio = {"K": K, "ejemplos": ej,
         "prob": {"t": cv.index.strftime("%Y-%m").tolist(), "knn": cv[f"knn{K} prob"].round(2).tolist(),
                  "logS": cv["logit ONI+S prob"].round(3).tolist(), "log": cv["logit ONI prob"].round(3).tolist(),
                  "ev": cv.evento.astype(int).tolist(), "q3": cv["Q3 obs"].round(0).tolist(), "thr": cv["umbral p20"].round(0).tolist()}}
(OUT / "sitio.json").write_text(json.dumps(sitio, ensure_ascii=False), encoding="utf-8")
print("listo")
