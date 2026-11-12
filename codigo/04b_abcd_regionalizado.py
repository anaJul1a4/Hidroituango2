"""
Trabajo 2 · numeral 1c: calibración multisitio simultánea y regionalizada del modelo abcd semidistribuido.

La calibración secuencial (04_modelo_abcd.py) deja parámetros en los límites del rango (a = 1, b = 3000 mm, d = 0,005 o 1): las
unidades incrementales pequeñas absorben el error de lo simulado aguas arriba y los parámetros pierden sentido físico. Aquí:
  · a, c y d son comunes a toda la cuenca y b (capacidad de almacenamiento del suelo y la ETR) es propio de cada unidad: 14 parámetros;
  · se ajustan todos a la vez maximizando el KGE medio de las 10 estaciones en 1982–2005 (evolución diferencial);
  · validación 2006–2023 como en 04_modelo_abcd.py.
Se corre con las combinaciones de P y ETo mejor evaluadas en 04 (Cubo IDEAM y CHIRPS v2.0; Penman-Monteith y Hargreaves).

Salidas: trabajo2/resultados/04_abcd/regionalizado_metricas.csv, regionalizado_parametros.csv, Q_simulado_reg_<P>_<ETo>.csv,
         estados_reg_<P>_<ETo>.nc
"""
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy.optimize import differential_evolution

ROOT = Path(__file__).resolve().parents[2]
src = (ROOT / "trabajo2" / "scripts" / "04_modelo_abcd.py").read_text(encoding="utf-8").split("grupos_dist = ")[0].replace("cache=True", "cache=False")
exec(compile(src, "04_base", "exec"))                     # abcd, entradas, métricas, piezas, qobs, tiempo… (sin correr la calibración)

iu = np.array([ORDEN.index(u) for u in piezas.unidad])   # unidad de cada pieza
aguas_abajo = [np.isin(iu, np.arange(k + 1)) for k in range(len(ORDEN))]   # piezas aguas arriba de cada estación
km2 = piezas.km2.values
o_cal = {c: np.where(icar, qobs[c].values, np.nan) for c in ORDEN}


def correr(x, P, E):
    a, c, d, b = x[0], x[1], x[2], np.asarray(x[3:])
    n = len(km2)
    q, S, G, ET = abcd(P, E, np.full(n, a), b[iu], np.full(n, c), np.full(n, d))
    return q, S, G, ET


def sim_estaciones(q):
    qm = q * km2[None, :] * 1e3 / seg[:, None]
    return {c: qm[:, aguas_abajo[k]].sum(1) for k, c in enumerate(ORDEN)}


filas, pars = [], []
for prod in ["Cubo IDEAM", "CHIRPS v2.0"]:
    for eto in ["Penman-Monteith", "Hargreaves"]:
        P, E = entradas(prod, eto)

        def f(x):
            s = sim_estaciones(correr(x, P, E)[0])
            v = [kge(s[c], o_cal[c]) for c in ORDEN]
            return 10.0 if not np.all(np.isfinite(v)) else -np.mean(v)
        lim = [LIM[0], LIM[2], LIM[3]] + [LIM[1]] * len(ORDEN)
        r = differential_evolution(f, lim, seed=1, popsize=10, maxiter=250, tol=1e-7, polish=True, workers=1)
        q, S, G, ET = correr(r.x, P, E)
        sim = sim_estaciones(q)
        filas += evaluar(sim, {"producto": prod, "ETo": eto, "modelo": "abcd semidistribuido regionalizado"})
        pars.append({"producto": prod, "ETo": eto, "a": r.x[0], "c": r.x[1], "d": r.x[2],
                     **{f"b {NOM[u]}": r.x[3 + k] for k, u in enumerate(ORDEN)}})
        et = f"{prod.replace(' ', '_')}_{'PM' if eto == 'Penman-Monteith' else 'HG'}"
        pd.DataFrame({NOM[c]: s for c, s in sim.items()}, index=tiempo).round(2).to_csv(OUT / f"Q_simulado_reg_{et}.csv",
                                                                                       encoding="utf-8-sig")
        w = km2
        cel_k = piezas.groupby("celda").km2.sum()
        agg = lambda X: (pd.DataFrame(X * w, columns=piezas.celda).T.groupby(level=0).sum().T / cel_k.values)  # noqa: E731
        xr.Dataset({k: (("time", "celda"), agg(X).values) for k, X in [("S", S), ("G", G), ("ETR", ET), ("Q", q)]},
                   coords={"time": tiempo, "celda": cel_k.index.values}).to_netcdf(OUT / f"estados_reg_{et}.nc")
        print(prod, eto, "KGE medio cal", round(-r.fun, 3), flush=True)
M = pd.DataFrame(filas)
M.round(3).to_csv(OUT / "regionalizado_metricas.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(pars).round(4).to_csv(OUT / "regionalizado_parametros.csv", index=False, encoding="utf-8-sig")
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
M["per"] = M.periodo.str[:3]
print(M.groupby(["producto", "ETo", "per"]).KGE.mean().unstack().round(3).to_string())
print(M[M.codigo == "PRESA"].pivot_table(index=["producto", "ETo"], columns="per", values=["KGE", "NSE", "PBIAS"]).round(2).to_string())
print(pd.DataFrame(pars).round(3).T.to_string())
