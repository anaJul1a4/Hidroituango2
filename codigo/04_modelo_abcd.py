"""
Trabajo 2 · numeral 1c: modelo lluvia–escorrentía mensual abcd (Thomas, 1981), semidistribuido, con calibración multisitio.

Modelo abcd por pieza (celda de 0,1° ∩ unidad), con la notación de Martinez y Gupta (2010):
    W = P + S(t−1)                                   agua disponible
    Y = (W + b)/(2a) − √[((W + b)/(2a))² − W·b/a]    oportunidad de evapotranspiración
    S = Y·exp(−ETo/b)        ETR = Y − S             humedad del suelo y evapotranspiración real
    escorrentía directa = (1 − c)(W − Y)    recarga = c(W − Y)
    G = (G(t−1) + recarga)/(1 + d)    flujo base = d·G            Q = escorrentía directa + flujo base
a (0–1): propensión a generar escorrentía antes de saturar el suelo; b (mm): capacidad de almacenamiento (suelo + ETR);
c (0–1): fracción del excedente que recarga el acuífero; d (0–1/mes): constante de recesión del flujo base.

Semidistribución: las 10 unidades (áreas incrementales entre estaciones del cauce principal; 01_entradas.py) tienen sus propios a,
b, c, d; cada celda se simula con la P y la ETo de su celda. Con pasos mensuales y tiempos de viaje de días, el caudal en cada estación
es la suma de lo que generan las unidades aguas arriba.
Calibración multisitio secuencial (de aguas arriba hacia abajo): los parámetros de la unidad k se ajustan para que el caudal simulado
en su estación (lo simulado aguas arriba, ya calibrado, más lo de la unidad k) maximice el KGE (Gupta et al., 2009) en 1982–2005; la
validación temporal es 2006–2023 (en la presa, hasta 2017). 1981 es el año de calentamiento (se corre dos veces).
Optimización: evolución diferencial (scipy).

Experimentos:
  · Productos de P: Cubo IDEAM, CHIRPS v2.0, CHIRPS v3.0, ERA5-Land QM, ERA5 QM (corregidos con el Cubo) y ERA5 sin corregir; ETo de
    Penman-Monteith. Sensibilidad a la ETo (Hargreaves) con el mejor producto.
  · Versión agregada (una sola unidad hasta la presa) para medir el valor de la semidistribución.
  · Modelo empírico de las diapositivas, Q = α·(P − ETR) + β (ETR de Budyko mensual), y su versión con memoria,
    Q = α·(P − ETR) + γ·Q(t−1) + β, ajustados por mínimos cuadrados en la presa: la referencia mínima.

Salidas: trabajo2/resultados/04_abcd/ parametros.csv, metricas.csv, Q_simulado_<producto>.csv, estados_<producto>.nc (S, G, ETR por
         celda), empirico.csv
"""
import time
from pathlib import Path

import numba
import numpy as np
import pandas as pd
import xarray as xr
from scipy.optimize import differential_evolution

ROOT = Path(__file__).resolve().parents[2]
ENT = ROOT / "trabajo2" / "resultados" / "01_entradas"
QOB = ROOT / "trabajo2" / "resultados" / "03_caudales" / "Q_mensual_estaciones.csv"
OUT = ROOT / "trabajo2" / "resultados" / "04_abcd"
OUT.mkdir(parents=True, exist_ok=True)
ORDEN = ["26027010", "26067010", "26107070", "26177030", "26167070", "26187110", "26207030", "26207080", "26217050", "PRESA"]
NOM = {"26027010": "La Balsa", "26067010": "Juanchito", "26107070": "La Victoria", "26177030": "La Virginia", "26167070": "Irra",
       "26187110": "La Pintada", "26207030": "Puente Iglesias", "26207080": "Bolombolo", "26217050": "Cañafisto", "PRESA": "Presa"}
PRODS = ["Cubo IDEAM", "CHIRPS v2.0", "CHIRPS v3.0", "ERA5-Land QM", "ERA5 QM", "ERA5"]
LIM = [(0.5, 1.0), (50.0, 3000.0), (0.0, 1.0), (0.005, 1.0)]                 # a, b, c, d
CAL, VAL = ("1982-01-01", "2005-12-01"), ("2006-01-01", "2023-12-01")

cel = pd.read_csv(ENT / "grilla_celdas.csv", index_col="celda")
qobs = pd.read_csv(QOB, index_col=0, parse_dates=True)
ETO = {"Penman-Monteith": xr.open_dataarray(ENT / "ETo_PM.nc"), "Hargreaves": xr.open_dataarray(ENT / "ETo_HG.nc")}
tiempo = pd.DatetimeIndex(ETO["Penman-Monteith"].time.values)
seg = (tiempo.days_in_month.values * 86400.0)
# piezas: (celda, unidad, km²)
piezas = cel[ORDEN].stack().rename("km2").reset_index().rename(columns={"level_1": "unidad"})
piezas = piezas[piezas.km2 > 0.01].reset_index(drop=True)
pos = {c: i for i, c in enumerate(cel.index)}
piezas["i"] = piezas.celda.map(pos)


@numba.njit(cache=True)
def abcd(P, E, a, b, c, d):
    """P, E: (T, n) mm/mes; a, b, c, d: (n,). Devuelve Q, S, G, ETR (T, n) en mm/mes."""
    T, n = P.shape
    Q = np.empty((T, n)); S = np.empty((T, n)); G = np.empty((T, n)); ET = np.empty((T, n))
    for j in range(n):
        s, g = b[j] / 2, 50.0
        for rep in range(2):                                                    # calentamiento: el primer año dos veces
            t0, t1 = (0, 12) if rep == 0 else (0, T)
            for t in range(t0, t1):
                w = P[t, j] + s
                k = (w + b[j]) / (2 * a[j])
                y = k - np.sqrt(max(k * k - w * b[j] / a[j], 0.0))
                s = y * np.exp(-E[t, j] / b[j])
                ex = w - y
                g = (g + c[j] * ex) / (1 + d[j])
                if rep == 1:
                    Q[t, j] = (1 - c[j]) * ex + d[j] * g
                    S[t, j] = s; G[t, j] = g; ET[t, j] = y - s
    return Q, S, G, ET


def a_m3s(qmm, km2):
    return (qmm * km2[None, :]).sum(1) * 1e3 / seg                         # mm·km² → m³/s


def kge(s, o):
    m = np.isfinite(o) & np.isfinite(s)
    s, o = s[m], o[m]
    if len(o) < 24:
        return np.nan
    r = np.corrcoef(s, o)[0, 1]
    return 1 - np.sqrt((r - 1) ** 2 + (s.std() / o.std() - 1) ** 2 + (s.mean() / o.mean() - 1) ** 2)


def metricas(s, o):
    m = np.isfinite(o) & np.isfinite(s)
    s, o = s[m], o[m]
    if len(o) < 24:
        return dict(n=len(o), NSE=np.nan, KGE=np.nan, RMSE=np.nan, PBIAS=np.nan, r=np.nan)
    return dict(n=len(o), NSE=1 - ((s - o) ** 2).sum() / ((o - o.mean()) ** 2).sum(), KGE=kge(s, o),
                RMSE=np.sqrt(((s - o) ** 2).mean()), PBIAS=100 * (s.sum() / o.sum() - 1), r=np.corrcoef(s, o)[0, 1])


icar = (tiempo >= CAL[0]) & (tiempo <= CAL[1])


def calibrar(P, E, grupos, objetivo):
    """grupos: lista de (código de estación, índices de piezas de la unidad). Calibración secuencial multisitio."""
    par, aguas_arriba, sim = {}, np.zeros(len(tiempo)), {}
    for cod, idx in grupos:
        Pu, Eu, km2 = P[:, idx], E[:, idx], piezas.km2.values[idx]
        o = objetivo[cod].values.copy(); o[~icar] = np.nan
        uno = np.ones(len(idx))

        def f(x):
            q, *_ = abcd(Pu, Eu, x[0] * uno, x[1] * uno, x[2] * uno, x[3] * uno)
            v = kge(aguas_arriba + a_m3s(q, km2), o)
            return 10.0 if not np.isfinite(v) else -v
        r = differential_evolution(f, LIM, seed=1, popsize=12, maxiter=120, tol=1e-6, polish=True)
        par[cod] = r.x
        q, *_ = abcd(Pu, Eu, *(r.x[k] * uno for k in range(4)))
        aguas_arriba = aguas_arriba + a_m3s(q, km2)
        sim[cod] = aguas_arriba.copy()
    return par, sim


def entradas(prod, eto):
    p = xr.open_dataarray(ENT / f"P_{prod.replace(' ', '_')}.nc").values[:, piezas.i.values]
    e = ETO[eto].values[:, piezas.i.values]
    return np.ascontiguousarray(p, dtype=np.float64), np.ascontiguousarray(e, dtype=np.float64)


def evaluar(sim, etiqueta):
    fil = []
    for cod, s in sim.items():
        for per, (a, b) in {"calibración 1982–2005": CAL, "validación 2006–2023": VAL}.items():
            m = (tiempo >= a) & (tiempo <= b)
            fil.append({**etiqueta, "estación": NOM[cod], "codigo": cod, "periodo": per,
                        **metricas(s[m], qobs[cod].values[m])})
    return fil


grupos_dist = [(cod, np.where(piezas.unidad.values == cod)[0]) for cod in ORDEN]
filas, pars = [], []
for prod in PRODS:
    t0 = time.time()
    P, E = entradas(prod, "Penman-Monteith")
    par, sim = calibrar(P, E, grupos_dist, qobs)
    filas += evaluar(sim, {"producto": prod, "ETo": "Penman-Monteith", "modelo": "abcd semidistribuido"})
    pars += [{"producto": prod, "ETo": "Penman-Monteith", "unidad": NOM[c], "a": v[0], "b": v[1], "c": v[2], "d": v[3]}
             for c, v in par.items()]
    pd.DataFrame({NOM[c]: s for c, s in sim.items()}, index=tiempo).round(2).to_csv(
        OUT / f"Q_simulado_{prod.replace(' ', '_')}.csv", encoding="utf-8-sig")
    # estados por celda (promedio ponderado de las piezas de cada celda)
    a_, b_, c_, d_ = (np.array([par[u][k] for u in piezas.unidad]) for k in range(4))
    q, S, G, ET = abcd(P, E, a_, b_, c_, d_)
    w = piezas.km2.values
    agg = lambda X: (pd.DataFrame(X * w, columns=piezas.celda).T.groupby(level=0).sum().T /  # noqa: E731
                     piezas.groupby("celda").km2.sum().values)
    xr.Dataset({k: (("time", "celda"), agg(X).values) for k, X in [("S", S), ("G", G), ("ETR", ET), ("Q", q)]},
               coords={"time": tiempo, "celda": piezas.groupby("celda").km2.sum().index.values}) \
        .to_netcdf(OUT / f"estados_{prod.replace(' ', '_')}.nc")
    # versión agregada (una unidad hasta la presa)
    Pl = (P * w[:, None].T).sum(1, keepdims=True) / w.sum()
    El = (E * w[:, None].T).sum(1, keepdims=True) / w.sum()
    piezas_l = np.array([w.sum()])
    o = qobs["PRESA"].values.copy(); o[~icar] = np.nan

    def fl(x):
        qq, *_ = abcd(Pl, El, np.array([x[0]]), np.array([x[1]]), np.array([x[2]]), np.array([x[3]]))
        v = kge(a_m3s(qq, piezas_l), o)
        return 10.0 if not np.isfinite(v) else -v
    rl = differential_evolution(fl, LIM, seed=1, popsize=12, maxiter=120, tol=1e-6)
    ql, *_ = abcd(Pl, El, *(np.array([rl.x[k]]) for k in range(4)))
    filas += evaluar({"PRESA": a_m3s(ql, piezas_l)}, {"producto": prod, "ETo": "Penman-Monteith", "modelo": "abcd agregado"})
    pars.append({"producto": prod, "ETo": "Penman-Monteith", "unidad": "agregado (presa)", "a": rl.x[0], "b": rl.x[1],
                 "c": rl.x[2], "d": rl.x[3]})
    print(f"{prod}: {time.time() - t0:.0f} s", flush=True)

M = pd.DataFrame(filas)
# sensibilidad a la ETo con el mejor producto (KGE medio de validación en las estaciones)
mejor = (M[(M.modelo == "abcd semidistribuido") & (M.periodo.str.startswith("valid"))].groupby("producto").KGE.mean().idxmax())
P, E = entradas(mejor, "Hargreaves")
par, sim = calibrar(P, E, grupos_dist, qobs)
filas += evaluar(sim, {"producto": mejor, "ETo": "Hargreaves", "modelo": "abcd semidistribuido"})
pars += [{"producto": mejor, "ETo": "Hargreaves", "unidad": NOM[c], "a": v[0], "b": v[1], "c": v[2], "d": v[3]} for c, v in par.items()]

# modelo empírico de las diapositivas, en la presa
S_ = pd.read_csv(ENT / "series_unidades.csv", header=[0, 1], index_col=0, parse_dates=True).xs("CUENCA", axis=1, level="unidad")
A = 35991.8
emp = []
for prod in PRODS:
    p, e = S_[f"P {prod}"].values, S_["ETo PM"].values
    f_ = e / p
    etr = p * np.sqrt(f_ * np.tanh(1 / f_) * (1 - np.exp(-f_)))
    W = p - etr
    qo = qobs["PRESA"].values * seg / (A * 1e3)                                 # m³/s → mm/mes
    for nombre, X in [("empírico Q = α·W + β", np.c_[W, np.ones_like(W)]),
                      ("empírico con memoria Q = α·W + γ·Q(t−1) + β", np.c_[W, np.r_[np.nan, qo[:-1]], np.ones_like(W)])]:
        m = icar & np.isfinite(qo) & np.isfinite(X).all(1)
        coef = np.linalg.lstsq(X[m], qo[m], rcond=None)[0]
        qs = X @ coef * A * 1e3 / seg
        emp.append({"producto": prod, "modelo": nombre, "coeficientes": np.round(coef, 4).tolist()})
        filas += evaluar({"PRESA": qs}, {"producto": prod, "ETo": "Penman-Monteith", "modelo": nombre})
pd.DataFrame(emp).to_csv(OUT / "empirico.csv", index=False, encoding="utf-8-sig")

M = pd.DataFrame(filas)
M.round(3).to_csv(OUT / "metricas.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(pars).round(4).to_csv(OUT / "parametros.csv", index=False, encoding="utf-8-sig")
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
tab = M.pivot_table(index=["modelo", "producto", "ETo"], columns="periodo", values="KGE", aggfunc="mean")
print("KGE medio en las estaciones"); print(tab.round(2).to_string())
print(M[(M.codigo == "PRESA")].pivot_table(index=["modelo", "producto", "ETo"], columns="periodo", values=["NSE", "KGE", "PBIAS"]).round(2).to_string())
print("mejor producto:", mejor)
