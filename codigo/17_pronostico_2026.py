"""
Trabajo 2 · pronóstico estacional en tiempo casi real: aportes a Hidroituango de noviembre de 2026 a abril de 2027 (El Niño 2026–27).

1. Lluvia 2024-01 … 2026-09: CHIRPS v2.0 (IRI Data Library, descargado el 12-nov-2026) llevado a las celdas del Cubo e igualado al Cubo
   con la razón Cubo/CHIRPS de cada celda y mes calendario en 1981–2010 (ambos interpolados del mismo modo). CHIRPS de octubre de
   2026 aún no se publica: la lluvia de octubre (climatología del Cubo × f) se ajusta para que el caudal simulado de octubre tenga la
   misma anomalía que los aportes diarios de XM del 1 al 23 de octubre (supuesto principal, «c»). Como sensibilidad: (a) octubre con
   la misma anomalía relativa que julio–septiembre de 2026 y (b) octubre normal.
2. ETo 2024–2026: ETo de Hargreaves climatológica de cada celda y mes (Cubo 1981–2023).
3. Modelo abcd final (regionalizado, Cubo, Hargreaves) corrido de 1981-01 a 2026-10 → S y G de la cuenca al final de octubre de 2026.
   Se verifica que 1981–2023 reproduce la serie de 06_enso_suelo_caudales.py y se comparan las anomalías simuladas de 2024–2026 con
   los aportes diarios a Ituango publicados por XM (cada uno frente a su climatología).
4. Pronóstico emitido al final de octubre de 2026 con los métodos del numeral 5 ajustados con todos los datos 1982–2017:
   KNN de años análogos (k = 15) → mediana e intervalo del 80 % del aporte de noviembre a abril; P(trimestre seco NDE) por KNN y por
   regresión logística con ONI y suelo, y nivel de alerta.

Salidas: trabajo2/resultados/12_pronostico_2026/
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
src = (ROOT / "trabajo2" / "scripts" / "04_modelo_abcd.py").read_text(encoding="utf-8").split("grupos_dist = ")[0].replace("cache=True", "cache=False")
exec(compile(src, "04_base", "exec"))                      # abcd, piezas, cel, ORDEN, NOM, ENT …
R2 = ROOT / "trabajo2" / "resultados"
OUT = R2 / "12_pronostico_2026"
OUT.mkdir(exist_ok=True)
FIG = R2 / "07_figuras"
CH = ROOT / "PRECIPITACION_COLOMBIA_CHIRPS_v2"
ROJO, AZUL, NEGRO, GRIS, AMBAR, NARANJA = "#b91c1c", "#1d4ed8", "#1f2328", "#9aa3b2", "#b07a0c", "#ea580c"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": "#d9d9d9", "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False})
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
K = 15

# ------------------------------------------------------------------------------------------------- 1. lluvia
def chirps(f):
    d = xr.open_dataset(f, decode_times=False).precipitation
    t = pd.date_range("1960-01-01", periods=int(d["T"].values.max() - 0.5) + 1, freq="MS")[(d["T"].values - 0.5).astype(int)]
    d = d.assign_coords(T=t).rename({"T": "time", "X": "lon", "Y": "lat"})
    v = d.interp(lat=xr.DataArray(cel.lat.values, dims="c"), lon=xr.DataArray(cel.lon.values, dims="c"))
    return pd.DataFrame(v.values, index=pd.DatetimeIndex(v.time.values), columns=cel.index)


ch_h = chirps(CH / "CHIRPS_v2p0_mensual_cuenca_1981_2025.nc")
ch_n = chirps(CH / "descarga_2026" / "chirps_2024_2026.nc")
cubo = pd.DataFrame(xr.open_dataarray(ENT / "P_Cubo_IDEAM.nc").values, index=tiempo, columns=cel.index)
b0, b1 = "1981", "2010"
razon = (cubo[b0:b1].groupby(cubo[b0:b1].index.month).mean() / ch_h[b0:b1].groupby(ch_h[b0:b1].index.month).mean()).clip(0.5, 2.0)
pn = ch_n["2024-01":"2026-09"] * razon.loc[ch_n["2024-01":"2026-09"].index.month].values
clim_cubo = cubo[b0:b1].groupby(cubo[b0:b1].index.month).mean()
w = cel.a_cuenca_km2.values
cuenca = lambda df: pd.Series((df.values * w).sum(1) / w.sum(), index=df.index)  # noqa: E731
anom_jas = cuenca(pn["2026-07":"2026-09"]).sum() / cuenca(clim_cubo.loc[[7, 8, 9]]).sum()
print(f"lluvia jul–sep 2026 = {100 * anom_jas:.0f} % de lo normal")
oct_a = clim_cubo.loc[[10]] * anom_jas
oct_b = clim_cubo.loc[[10]]
t_ext = pd.date_range("2024-01-01", "2026-10-01", freq="MS")
eto = xr.open_dataarray(ENT / "ETo_HG.nc").values
eto_df = pd.DataFrame(eto, index=tiempo, columns=cel.index)
eto_clim = eto_df.groupby(eto_df.index.month).mean()
E_ext = eto_clim.loc[t_ext.month].values


def correr(p_oct):
    P_ext = np.vstack([pn.values, p_oct.values])
    P = np.vstack([cubo.values, P_ext]); E = np.vstack([eto, E_ext])
    t = tiempo.append(t_ext)
    par = pd.read_csv(R2 / "04_abcd" / "regionalizado_parametros.csv")
    p0 = par[(par.producto == "Cubo IDEAM") & (par.ETo == "Hargreaves")].iloc[0]
    iu = np.array([ORDEN.index(u) for u in piezas.unidad]); n = len(piezas)
    bU = np.array([p0[f"b {NOM[u]}"] for u in ORDEN])
    Pp = np.ascontiguousarray(P[:, piezas.i.values]); Ep = np.ascontiguousarray(E[:, piezas.i.values])
    q, S, G, ET = abcd(Pp, Ep, np.full(n, p0.a), bU[iu], np.full(n, p0.c), np.full(n, p0.d))
    km2 = piezas.km2.values
    cel_k = piezas.groupby("celda").km2.sum()
    agg = lambda X: pd.DataFrame(X * km2, columns=piezas.celda).T.groupby(level=0).sum().T.values / cel_k.values  # noqa: E731
    wc = cel.loc[cel_k.index, "a_cuenca_km2"].values
    Sc = pd.Series((agg(S) * wc).sum(1) / wc.sum(), index=t)
    Gc = pd.Series((agg(G) * wc).sum(1) / wc.sum(), index=t)
    segs = t.days_in_month.values * 86400.0
    abajo = np.isin(iu, np.arange(len(ORDEN)))
    Qp = pd.Series((q[:, abajo] * km2[abajo]).sum(1) * 1e3 / segs, index=t)
    return Sc, Gc, Qp, pd.Series((P * w).sum(1) / w.sum(), index=t)


# octubre: la lluvia se ajusta para que la anomalía simulada del caudal de octubre iguale la de los aportes XM (1–23 de octubre)
_xm = pd.read_csv(ROOT / "trabajo1" / "datos" / "xm" / "aportes_caudal_ituango.csv", parse_dates=["Date"]).set_index("Date").Value
_xh = pd.read_csv(ROOT / "trabajo1" / "datos" / "xm" / "aportes_caudal_mediahist_ituango.csv", parse_dates=["Date"]).set_index("Date").Value
an_oct_xm = 100 * (_xm["2026-10"].mean() / _xh["2026-10"].mean() - 1)


def an_oct(f_):
    _, _, Q_, _ = correr(clim_cubo.loc[[10]] * f_)
    c_ = Q_["1981":"2010"].groupby(Q_["1981":"2010"].index.month).mean()
    return 100 * (Q_["2026-10-01"] / c_[10] - 1)


lo, hi = 0.2, 1.6
for _ in range(14):
    mid = (lo + hi) / 2
    lo, hi = (mid, hi) if an_oct(mid) < an_oct_xm else (lo, mid)
f_oct = (lo + hi) / 2
print(f"octubre: anomalía XM {an_oct_xm:.0f} % → lluvia de octubre = {100 * f_oct:.0f} % de la normal")
oct_c = clim_cubo.loc[[10]] * f_oct
res = {k: correr(p) for k, p in {"c": oct_c, "a": oct_a, "b": oct_b}.items()}
Sc, Gc, Qp, Pc = res["c"]
sc0 = pd.read_csv(R2 / "06_enso_suelo_Q" / "series_cuenca.csv", index_col=0, parse_dates=True)
print("control 1981–2023: r(S) =", round(Sc[:"2023"].corr(sc0.S), 4), " r(G) =", round(Gc[:"2023"].corr(sc0.G), 4),
      " dif. media S =", round(float((Sc[:"2023"] - sc0.S).abs().max()), 2))

# ------------------------------------------------------------------------------------------------- 2. verificación con XM
xm = pd.read_csv(ROOT / "trabajo1" / "datos" / "xm" / "aportes_caudal_ituango.csv", parse_dates=["Date"]).set_index("Date").Value
xmh = pd.read_csv(ROOT / "trabajo1" / "datos" / "xm" / "aportes_caudal_mediahist_ituango.csv", parse_dates=["Date"]).set_index("Date").Value
xm_m = xm.resample("MS").mean(); xmh_m = xmh.resample("MS").mean()
dias = xm.resample("MS").count()
xm_m = xm_m[dias >= 20]
an_xm = 100 * (xm_m / xmh_m.reindex(xm_m.index) - 1)
qcl = Qp[b0:b1].groupby(Qp[b0:b1].index.month).mean()
an_sim = 100 * (Qp / qcl.loc[Qp.index.month].values - 1)
ver = pd.DataFrame({"aporte XM (m³/s)": xm_m, "media histórica XM (m³/s)": xmh_m.reindex(xm_m.index), "anomalía XM (%)": an_xm,
                    "Q simulado (m³/s)": Qp.reindex(xm_m.index), "anomalía simulada (%)": an_sim.reindex(xm_m.index)}).dropna()
ver.round(1).to_csv(OUT / "verificacion_xm.csv", encoding="utf-8-sig")
r_ver = ver["anomalía XM (%)"].corr(ver["anomalía simulada (%)"])
print(f"verificación {ver.index[0]:%Y-%m}–{ver.index[-1]:%Y-%m}: r anomalías = {r_ver:.2f}, n = {len(ver)}")

# ------------------------------------------------------------------------------------------------- 3. predictores y entrenamiento
oni_f = ROOT / "trabajo1" / "datos" / "enso_2026-11" / "oni.ascii.txt"
o = pd.read_csv(oni_f, sep=r"\s+")
est = ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"]
o["mes"] = o.SEAS.map({s: i + 1 for i, s in enumerate(est)})
oni = pd.Series(o.ANOM.values, index=pd.to_datetime(dict(year=o.YR, month=o.mes, day=1)))   # trimestre centrado en el mes
t_all = Sc.index
X = pd.DataFrame({"ONI": oni.reindex(t_all).shift(1), "S": Sc, "G": Gc})
X["ΔONI"] = X.ONI - X.ONI.shift(3)
X = X[["ONI", "ΔONI", "S", "G"]]
base = X[:"2023"]
mu = base.groupby(base.index.month).mean(); sd = base.groupby(base.index.month).std()
Xz = (X - mu.loc[X.index.month].values) / sd.loc[X.index.month].values
qo = pd.read_csv(R2 / "03_caudales" / "Q_mensual_estaciones.csv", index_col=0, parse_dates=True)["PRESA"].reindex(t_all)
qo[qo.index.year > 2017] = np.nan
lq = np.log(qo)
q3 = qo.rolling(3).mean().shift(-3)
ok = Xz.notna().all(axis=1) & q3.notna() & (t_all.year >= 1982) & (t_all <= "2017-09-01")
mes = t_all.month.values
t0 = pd.Timestamp("2026-10-01")
emi = Xz.loc[t0]
print("estado al final de octubre de 2026:", X.loc[t0].round(2).to_dict(), "| z:", emi.round(2).to_dict())

# KNN
m = t0.month
cand = np.where(ok.values & np.isin(mes, [(m - 2) % 12 + 1, m, m % 12 + 1]))[0]
d = np.sqrt(((Xz.values[cand] - emi.values) ** 2).sum(1))
an = cand[np.argsort(d)[:K]]
anal = pd.DataFrame({"mes análogo": t_all[an].strftime("%Y-%m"), "distancia": np.sort(d)[:K],
                     **{c: X.values[an, i] for i, c in enumerate(X.columns)}})
lqm = lq.groupby(lq.index.month)
mu_q, sd_q = lqm.mean(), lqm.std()
H = 6
ens = np.full((K, H), np.nan)
for j, a in enumerate(an):
    for h in range(1, H + 1):
        ta = t_all[a] + pd.DateOffset(months=h); tt = t0 + pd.DateOffset(months=h)
        z = (lq.get(ta, np.nan) - mu_q[ta.month]) / sd_q[ta.month]
        ens[j, h - 1] = np.exp(mu_q[tt.month] + z * sd_q[tt.month])
meses_f = [t0 + pd.DateOffset(months=h) for h in range(1, H + 1)]
clim_q = np.exp([mu_q[t.month] for t in meses_f])
pron = pd.DataFrame({"mes": [t.strftime("%Y-%m") for t in meses_f], "mediana (m³/s)": np.nanmedian(ens, 0),
                     "p10 (m³/s)": np.nanpercentile(ens, 10, 0), "p90 (m³/s)": np.nanpercentile(ens, 90, 0),
                     "climatología, mediana (m³/s)": clim_q})
pron["mediana frente a la climatología (%)"] = 100 * (pron["mediana (m³/s)"] / pron["climatología, mediana (m³/s)"] - 1)
anal["aporte medio de los 3 meses siguientes (m³/s)"] = q3.values[an]
thr = np.quantile(q3[ok & (mes == m)], 0.2)
z3 = (np.log(q3.values[an]) - np.log(q3[ok & (mes == m)]).mean()) / np.log(q3[ok & (mes == m)]).std()
p_knn = float(np.mean(q3.values[an] * 0 + (np.exp(np.log(q3[ok & (mes == m)]).mean() + z3 * np.log(q3[ok & (mes == m)]).std()) < thr)))


# logística (todos los datos)
def logit_fit(x, y, lam=1e-3):
    A = np.column_stack([np.ones(len(x)), x]); b = np.zeros(A.shape[1])
    for _ in range(60):
        p = 1 / (1 + np.exp(-A @ b)); W = p * (1 - p)
        b += np.linalg.solve(A.T @ (A * W[:, None]) + lam * np.eye(len(b)), A.T @ (y - p) - lam * b)
    return b


ev = np.array([q3.values[i] < np.quantile(q3[ok & (mes == mes[i])], 0.2) for i in np.where(ok)[0]], float)
b = logit_fit(Xz.values[ok.values][:, [0, 2]], ev)
p_log = float(1 / (1 + np.exp(-(b[0] + b[1] * emi.ONI + b[2] * emi.S))))
b1 = logit_fit(Xz.values[ok.values][:, [0]], ev)
p_log1 = float(1 / (1 + np.exp(-(b1[0] + b1[1] * emi.ONI))))
nivel = lambda p: "rojo" if p >= 0.5 else ("amarillo" if p >= 0.2 else "verde")  # noqa: E731

# sensibilidad al supuesto de octubre
sens = {}
for k_, (S_, G_, Q_, P_) in res.items():
    xz = (pd.Series({"ONI": X.loc[t0, "ONI"], "ΔONI": X.loc[t0, "ΔONI"], "S": S_[t0], "G": G_[t0]}) - mu.loc[10]) / sd.loc[10]
    sens[k_] = {"S z": float(xz.S), "G z": float(xz.G), "P(seco) logística": float(1 / (1 + np.exp(-(b[0] + b[1] * xz.ONI + b[2] * xz.S))))}
print("sensibilidad a la lluvia de octubre:", {k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in sens.items()})

pron.round(1).to_csv(OUT / "pronostico_nov2026_abr2027.csv", index=False, encoding="utf-8-sig")
anal.round(2).to_csv(OUT / "analogos.csv", index=False, encoding="utf-8-sig")
resumen = {"emision": "2026-10", "ONI ASO 2026": float(oni["2026-09-01"]), "ONI disponible (predictor)": float(X.loc[t0, "ONI"]),
           "lluvia jul-sep 2026 (% de lo normal)": float(100 * anom_jas), "S z": float(emi.S), "G z": float(emi.G),
           "P(seco) KNN": p_knn, "P(seco) logística ONI+S": p_log, "P(seco) logística ONI": p_log1,
           "nivel logística": nivel(p_log), "nivel KNN": nivel(p_knn), "umbral p20 Q3 (m³/s, IDEAM)": float(thr),
           "r anomalías verificación XM": float(r_ver), "sensibilidad octubre": sens, "lluvia octubre (% de la normal)": float(100 * f_oct), "anomalía XM octubre (%)": float(an_oct_xm),
           "Q3 mediana KNN (m³/s)": float(np.nanmedian(np.nanmean(ens[:, :3], 1)))}
(OUT / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
print(pron.round(0).to_string()); print(anal.round(2).to_string()); print(json.dumps(resumen, ensure_ascii=False, indent=1))

# ------------------------------------------------------------------------------------------------- figura (300 dpi)
fig, axs = plt.subplots(1, 2, figsize=(14, 4.6), gridspec_kw={"width_ratios": [1.5, 1]})
ax = axs[0]
xx = np.arange(H)
ax.fill_between(xx, pron["p10 (m³/s)"], pron["p90 (m³/s)"], color=AZUL, alpha=0.15, lw=0, label=f"Intervalo 80 % de los {K} análogos")
for j in range(K):
    ax.plot(xx, ens[j], color=AZUL, lw=0.5, alpha=0.35)
ax.plot(xx, pron["mediana (m³/s)"], "-o", color=AZUL, lw=2.4, ms=5, label="Mediana de los análogos")
ax.plot(xx, pron["climatología, mediana (m³/s)"], "--", color=GRIS, lw=2, label="Climatología 1981–2017 (mediana)")
ax.set_xticks(xx, [f"{MESES[t.month - 1]} {t.year}" for t in meses_f]); ax.set_ylim(0)
ax.set_ylabel("Aporte medio mensual a la presa (m³/s, escala IDEAM)")
ax.set_title(f"a) Pronóstico emitido al final de octubre de 2026 · ONI ASO = +{oni['2026-09-01']:.2f} °C, suelo z = {emi.S:+.2f}".replace(".", ","),
             fontsize=10, loc="left")
ax.legend(fontsize=8.5, loc="upper right")
ax = axs[1]
v = ver[ver.index >= "2023-01-01"]
ax.axhline(0, color="#555", lw=0.8)
ax.plot(v.index, v["anomalía XM (%)"], "-o", color=NEGRO, ms=3, lw=1.6, label="Aporte XM frente a su media histórica")
ax.plot(Qp["2023-01":].index, an_sim["2023-01":], "-", color=NARANJA, lw=1.8, label="Simulado abcd frente a 1981–2010")
ax.axvspan(pd.Timestamp("2024-01-01"), pd.Timestamp("2026-10-31"), color=GRIS, alpha=0.12, lw=0)
ax.text(pd.Timestamp("2024-02-01"), ax.get_ylim()[1] * 0.9 if ax.get_ylim()[1] > 0 else 50, "lluvia CHIRPS escalada", fontsize=8, color="#555")
ax.set_ylabel("Anomalía del aporte mensual (%)"); ax.legend(fontsize=8.5, loc="lower left")
ax.set_title(f"b) Estado inicial: simulado frente a XM (r = {r_ver:.2f})".replace(".", ","), fontsize=10, loc="left")
fig.tight_layout()
fig.savefig(FIG / "fig_pronostico_2026.png", dpi=300, bbox_inches="tight", facecolor="white"); plt.close(fig)
sit = {"meses": pron.mes.tolist(), "med": pron["mediana (m³/s)"].round(0).tolist(), "p10": pron["p10 (m³/s)"].round(0).tolist(),
       "p90": pron["p90 (m³/s)"].round(0).tolist(), "clim": pron["climatología, mediana (m³/s)"].round(0).tolist(),
       "ens": np.round(ens, 0).tolist(), "ver_t": v.index.strftime("%Y-%m").tolist(), "ver_xm": v["anomalía XM (%)"].round(1).tolist(),
       "sim_t": Qp["2023-01":].index.strftime("%Y-%m").tolist(), "sim": an_sim["2023-01":].round(1).tolist(), **resumen}
(OUT / "sitio.json").write_text(json.dumps(sit, ensure_ascii=False), encoding="utf-8")
