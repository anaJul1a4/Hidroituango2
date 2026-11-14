"""
Trabajo 2 · numeral 1c: modelo lluvia–escorrentía mensual GR2M (Mouelhi et al., 2006; versión de la clase 6 de Hidrometeorología),
distribuido en las celdas del Cubo de datos y calibrado en varios sitios a la vez.

Ecuaciones (paso mensual; P y ETP en mm/mes):
  reservorio de producción S (capacidad X1):
     φ = tanh(P/X1);  S1 = (S + X1·φ) / (1 + φ·S/X1);  P1 = P + S − S1
     ψ = tanh(ETP/X1); S2 = S1·(1 − ψ) / (1 + ψ·(1 − S1/X1));  ETR = S1 − S2
     S = S2 / [1 + (S2/X1)³]^(1/3);  P2 = S2 − S;  P3 = P1 + P2
  reservorio de enrutamiento R (60 mm):  R1 = R + P3;  R2 = X2·R1;  Q = R2² / (R2 + 60);  R = R2 − Q
Condiciones iniciales S0 = X1/2 y R0 = 30 mm; calentamiento: el primer año se corre dos veces.
Tiempo de viaje por el cauce principal: 855 km a 1 m/s ≈ 10 días < 1 mes, así que el caudal de cada celda se suma en la salida en el
mismo mes (chequeo de consistencia temporal de la clase).

Distribución: el modelo corre en cada pieza celda × unidad (celdas del Cubo de 0,1° recortadas por las 10 áreas incrementales entre
estaciones del cauce principal), con la lluvia y la ETo de su celda. El caudal de cada estación es la suma de las piezas aguas arriba.
Calibración multisitio (en el espíritu de los «factores de corrección» de la clase, pero sin mapas de suelos): X1 propio de cada unidad
y X2 común, ajustados a la vez para maximizar el KGE medio de las 10 estaciones en 1982–2005; validación 2006–2023 (presa: hasta 2017).
Optimización por evolución diferencial; X1 se busca en escala logarítmica (10–10 000 mm) y X2 en 0,3–1,5.

Experimentos: GR2M distribuido con los seis productos de lluvia y ETo de Penman-Monteith, y con Cubo y CHIRPS v2.0 con Hargreaves;
GR2M agregado (una sola unidad hasta la presa). Se incluyen para comparar el abcd regionalizado (04b) y las ecuaciones empíricas (04).
Métricas: NSE, NSE logarítmico, KGE, RMSE y PBIAS.

Salidas: trabajo2/resultados/04_gr2m/ metricas.csv, parametros.csv, Q_simulado_<P>_<ETo>.csv, estados_<P>_<ETo>.nc (S, R, ETR, Q por
celda), modelo_final.json
"""
import json
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
OUT = ROOT / "trabajo2" / "resultados" / "04_gr2m"
OUT.mkdir(parents=True, exist_ok=True)
ORDEN = ["26027010", "26067010", "26107070", "26177030", "26167070", "26187110", "26207030", "26207080", "26217050", "PRESA"]
NOM = {"26027010": "La Balsa", "26067010": "Juanchito", "26107070": "La Victoria", "26177030": "La Virginia", "26167070": "Irra",
       "26187110": "La Pintada", "26207030": "Puente Iglesias", "26207080": "Bolombolo", "26217050": "Cañafisto", "PRESA": "Presa"}
PRODS = ["Cubo IDEAM", "CHIRPS v2.0", "CHIRPS v3.0", "ERA5-Land QM", "ERA5 QM", "ERA5"]
LX1, LX2 = (1.0, 4.0), (0.3, 1.5)                          # log10 X1 (mm), X2 (-)
CAL, VAL = ("1982-01-01", "2005-12-01"), ("2006-01-01", "2023-12-01")

cel = pd.read_csv(ENT / "grilla_celdas.csv", index_col="celda")
qobs = pd.read_csv(QOB, index_col=0, parse_dates=True)
ETO = {"Penman-Monteith": xr.open_dataarray(ENT / "ETo_PM.nc"), "Hargreaves": xr.open_dataarray(ENT / "ETo_HG.nc")}
tiempo = pd.DatetimeIndex(ETO["Penman-Monteith"].time.values)
seg = tiempo.days_in_month.values * 86400.0
piezas = cel[ORDEN].stack().rename("km2").reset_index().rename(columns={"level_1": "unidad"})
piezas = piezas[piezas.km2 > 0.01].reset_index(drop=True)
piezas["i"] = piezas.celda.map({c: i for i, c in enumerate(cel.index)})
iu = np.array([ORDEN.index(u) for u in piezas.unidad])
aguas_arriba = [np.isin(iu, np.arange(k + 1)) for k in range(len(ORDEN))]
km2 = piezas.km2.values
icar = (tiempo >= CAL[0]) & (tiempo <= CAL[1])


@numba.njit(cache=False)
def gr2m(P, E, X1, X2):
    """P, E: (T, n) mm/mes; X1, X2: (n,). Devuelve Q, S, R, ETR (T, n) en mm/mes (S y R al final de cada mes)."""
    T, n = P.shape
    Q = np.empty((T, n)); S_ = np.empty((T, n)); R_ = np.empty((T, n)); ET = np.empty((T, n))
    for j in range(n):
        x1, x2 = X1[j], X2[j]
        s, r = x1 / 2.0, 30.0
        for rep in range(2):                                      # calentamiento: el primer año dos veces
            t1 = 12 if rep == 0 else T
            for t in range(t1):
                phi = np.tanh(P[t, j] / x1)
                s1 = (s + x1 * phi) / (1.0 + phi * s / x1)
                p1 = P[t, j] + s - s1
                psi = np.tanh(E[t, j] / x1)
                s2 = s1 * (1.0 - psi) / (1.0 + psi * (1.0 - s1 / x1))
                s = s2 / (1.0 + (s2 / x1) ** 3) ** (1.0 / 3.0)
                p3 = p1 + (s2 - s)
                r2 = x2 * (r + p3)
                q = r2 * r2 / (r2 + 60.0)
                r = r2 - q
                if rep == 1:
                    Q[t, j] = q; S_[t, j] = s; R_[t, j] = r; ET[t, j] = s1 - s2
    return Q, S_, R_, ET


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
        return dict(n=len(o), NSE=np.nan, NSElog=np.nan, KGE=np.nan, RMSE=np.nan, PBIAS=np.nan, r=np.nan)
    eps = 0.01 * o.mean()
    ls, lo = np.log(s + eps), np.log(o + eps)
    return dict(n=len(o), NSE=1 - ((s - o) ** 2).sum() / ((o - o.mean()) ** 2).sum(),
                NSElog=1 - ((ls - lo) ** 2).sum() / ((lo - lo.mean()) ** 2).sum(), KGE=kge(s, o),
                RMSE=np.sqrt(((s - o) ** 2).mean()), PBIAS=100 * (s.sum() / o.sum() - 1), r=np.corrcoef(s, o)[0, 1])


def entradas(prod, eto):
    p = xr.open_dataarray(ENT / f"P_{prod.replace(' ', '_')}.nc").values[:, piezas.i.values]
    e = ETO[eto].values[:, piezas.i.values]
    return np.ascontiguousarray(p, dtype=np.float64), np.ascontiguousarray(e, dtype=np.float64)


def parametros(x):
    """x = [log10 X1 de las 10 unidades …, X2] → X1, X2 por pieza."""
    x1u = 10 ** np.asarray(x[:len(ORDEN)])
    return x1u[iu], np.full(len(km2), x[len(ORDEN)])


def estaciones(q):
    qm = q * km2[None, :] * 1e3 / seg[:, None]                 # mm·km²/mes → m³/s
    return {c: qm[:, aguas_arriba[k]].sum(1) for k, c in enumerate(ORDEN)}


def evaluar(sim, etiqueta):
    fil = []
    for cod, s in sim.items():
        for per, (a, b) in {"calibración 1982–2005": CAL, "validación 2006–2023": VAL}.items():
            m = (tiempo >= a) & (tiempo <= b)
            fil.append({**etiqueta, "estación": NOM[cod], "codigo": cod, "periodo": per, **metricas(s[m], qobs[cod].values[m])})
    return fil


o_cal = {c: np.where(icar, qobs[c].values, np.nan) for c in ORDEN}

if __name__ == "__main__":
    filas, pars = [], []
    corridas = [(p, "Penman-Monteith") for p in PRODS] + [("Cubo IDEAM", "Hargreaves"), ("CHIRPS v2.0", "Hargreaves")]
    for prod, eto in corridas:
        t0 = time.time()
        P, E = entradas(prod, eto)

        def f(x):
            s = estaciones(gr2m(P, E, *parametros(x))[0])
            v = [kge(s[c], o_cal[c]) for c in ORDEN]
            return 10.0 if not np.all(np.isfinite(v)) else -np.mean(v)
        r = differential_evolution(f, [LX1] * len(ORDEN) + [LX2], seed=1, popsize=10, maxiter=250, tol=1e-7, polish=True)
        q, S, R, ET = gr2m(P, E, *parametros(r.x))
        sim = estaciones(q)
        filas += evaluar(sim, {"producto": prod, "ETo": eto, "modelo": "GR2M distribuido"})
        pars.append({"producto": prod, "ETo": eto, "X2": r.x[-1], **{f"X1 {NOM[u]}": 10 ** r.x[k] for k, u in enumerate(ORDEN)}})
        et = f"{prod.replace(' ', '_')}_{'PM' if eto == 'Penman-Monteith' else 'HG'}"
        pd.DataFrame({NOM[c]: s for c, s in sim.items()}, index=tiempo).round(2).to_csv(OUT / f"Q_simulado_{et}.csv", encoding="utf-8-sig")
        cel_k = piezas.groupby("celda").km2.sum()
        agg = lambda X: (pd.DataFrame(X * km2, columns=piezas.celda).T.groupby(level=0).sum().T / cel_k.values)  # noqa: E731
        x1c = agg(np.tile(parametros(r.x)[0], (1, 1))).values[0]
        xr.Dataset({k: (("time", "celda"), agg(X).values) for k, X in [("S", S), ("R", R), ("ETR", ET), ("Q", q)]} |
                   {"X1": (("celda",), x1c)},
                   coords={"time": tiempo, "celda": cel_k.index.values}).to_netcdf(OUT / f"estados_{et}.nc")
        # agregado (una unidad hasta la presa)
        w = km2 / km2.sum()
        Pl, El = np.ascontiguousarray((P * w).sum(1, keepdims=True)), np.ascontiguousarray((E * w).sum(1, keepdims=True))
        ol = o_cal["PRESA"]

        def fl(x):
            qq = gr2m(Pl, El, np.array([10 ** x[0]]), np.array([x[1]]))[0][:, 0] * km2.sum() * 1e3 / seg
            v = kge(qq, ol)
            return 10.0 if not np.isfinite(v) else -v
        rl = differential_evolution(fl, [LX1, LX2], seed=1, popsize=15, maxiter=200, tol=1e-8)
        ql = gr2m(Pl, El, np.array([10 ** rl.x[0]]), np.array([rl.x[1]]))[0][:, 0] * km2.sum() * 1e3 / seg
        filas += evaluar({"PRESA": ql}, {"producto": prod, "ETo": eto, "modelo": "GR2M agregado"})
        pars.append({"producto": prod, "ETo": eto, "X2": rl.x[1], "X1 agregado (presa)": 10 ** rl.x[0]})
        print(f"{prod} · {eto}: KGE medio cal {-r.fun:.3f} · {time.time() - t0:.0f} s", flush=True)

    # comparación: abcd regionalizado (04b) y ecuaciones empíricas (04)
    A = ROOT / "trabajo2" / "resultados" / "04_abcd"
    ab = pd.read_csv(A / "regionalizado_metricas.csv")
    ab = ab[(ab.producto == "Cubo IDEAM") & (ab.ETo == "Hargreaves")].assign(modelo="abcd distribuido (4 parámetros, comparación)")
    em = pd.read_csv(A / "metricas.csv")
    em = em[em.modelo.str.startswith("empírico")]
    M = pd.concat([pd.DataFrame(filas), ab, em], ignore_index=True)
    M.round(3).to_csv(OUT / "metricas.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(pars).round(4).to_csv(OUT / "parametros.csv", index=False, encoding="utf-8-sig")
    M["per"] = M.periodo.str[:3]
    d = M[M.modelo == "GR2M distribuido"]
    res = d.groupby(["producto", "ETo", "per"]).KGE.mean().unstack()
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(res.round(3).to_string())
    print(M[M.codigo == "PRESA"].pivot_table(index=["modelo", "producto", "ETo"], columns="per", values=["KGE", "NSE", "NSElog", "PBIAS"]).round(2).to_string())
    best = res["val"].idxmax()
    pv = d[(d.producto == best[0]) & (d.ETo == best[1]) & (d.codigo == "PRESA") & (d.per == "val")].KGE.iloc[0]
    json.dump({"modelo": "GR2M distribuido", "producto": best[0], "eto": best[1],
               "criterio": f"mayor KGE medio de validación 2006–2023 en las 10 estaciones ({res['val'].max():.3f}); KGE de validación en la presa {pv:.2f}"},
              open(OUT / "modelo_final.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("modelo final:", best)
    print(pd.DataFrame(pars).round(3).T.to_string())
