"""
Trabajo 2 · numeral 5: funciones ortogonales empíricas (EOF) de la precipitación y de la humedad del suelo en la cuenca.

Para cada producto de lluvia (Cubo IDEAM, CHIRPS v2.0, CHIRPS v3.0, ERA5-Land QM, ERA5 QM) y para S del modelo abcd final:
  1. Anomalía de cada celda: media móvil de 3 meses, estandarizada por mes calendario (1981–2023). El trimestre móvil filtra el
     ruido mensual y deja la escala del ENSO.
  2. Ponderación por √(área de la celda dentro de la cuenca), para que cada km² pese lo mismo.
  3. EOF por descomposición en valores singulares de la matriz tiempo × celda: patrones espaciales (EOF), series temporales
     (componentes principales, CP) y fracción de varianza explicada. Separación de los modos con la regla de North et al. (1982),
     con el número efectivo de datos N* = N (1 − r1²)/(1 + r1²) de la CP1.
  4. Mapa de cada modo como correlación homogénea: correlación entre la CP y la anomalía de cada celda (−1 a 1). Signo: la CP1
     positiva corresponde a una cuenca más húmeda.
  5. Relación con el ENSO: correlación de Pearson entre cada CP y el ONI, con el ONI adelantado 0 a 6 meses.
  6. Consistencia entre productos: correlación espacial de cada EOF con la del Cubo y correlación temporal de las CP.

Salidas: trabajo2/resultados/09_eof/ y figura en 07_figuras/
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
from matplotlib.colors import BoundaryNorm  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
R2 = ROOT / "trabajo2" / "resultados"
ENT = R2 / "01_entradas"
OUT = R2 / "09_eof"
OUT.mkdir(parents=True, exist_ok=True)
FIG = R2 / "07_figuras"
NM = 3
PRODS = ["Cubo IDEAM", "CHIRPS v2.0", "CHIRPS v3.0", "ERA5-Land QM", "ERA5 QM"]

cel = pd.read_csv(ENT / "grilla_celdas.csv", index_col="celda")
final = json.loads((R2 / "04_abcd" / "modelo_final.json").read_text(encoding="utf-8"))
etq = "PM" if final["eto"] == "Penman-Monteith" else "HG"
campos = {p: xr.open_dataarray(ENT / f"P_{p.replace(' ', '_')}.nc") for p in PRODS}
campos["Suelo S (abcd)"] = xr.open_dataset(R2 / "04_abcd" / f"estados_reg_{final['producto'].replace(' ', '_')}_{etq}.nc").S
sc = pd.read_csv(R2 / "06_enso_suelo_Q" / "series_cuenca.csv", index_col=0, parse_dates=True)
oni = sc.ONI


def anomalias(da):
    df = da.to_pandas()
    if "celda" not in da.coords:                                # los P_*.nc vienen en el orden de grilla_celdas.csv
        df.columns = cel.index
    df = df.loc[:, df.columns.isin(cel.index[cel.a_cuenca_km2 > 0])]
    df = df.rolling(NM, center=True).mean().dropna()
    g = df.groupby(df.index.month)
    return (df - g.transform("mean")) / g.transform("std")


def eof(A, w, n=3):
    M = A.values * w[None, :]
    U, s, Vt = np.linalg.svd(M, full_matrices=False)
    var = s ** 2 / np.sum(s ** 2)
    pcs = U[:, :n] * s[:n]
    pcs = (pcs - pcs.mean(0)) / pcs.std(0)
    mapas = np.array([[np.corrcoef(pcs[:, i], A.values[:, j])[0, 1] for j in range(A.shape[1])] for i in range(n)])
    return var, pcs, mapas


R, PC, MAP = {}, {}, {}
for nom, da in campos.items():
    A = anomalias(da)
    w = np.sqrt(cel.loc[A.columns, "a_cuenca_km2"].values / cel.loc[A.columns, "a_cuenca_km2"].mean())
    var, pcs, mapas = eof(A, w)
    for i in range(3):                                          # signo: modo positivo = más húmedo en promedio
        if np.average(mapas[i], weights=w ** 2) < 0:
            mapas[i] *= -1; pcs[:, i] *= -1
    r1 = pd.Series(pcs[:, 0]).autocorr(1)
    n_ef = len(pcs) * (1 - r1 ** 2) / (1 + r1 ** 2)
    err = var * np.sqrt(2 / n_ef)
    PC[nom] = pd.DataFrame(pcs, index=A.index, columns=["CP1", "CP2", "CP3"])
    MAP[nom] = pd.DataFrame(mapas.T, index=A.columns, columns=["EOF1", "EOF2", "EOF3"])
    fila = {"varianza EOF1 (%)": 100 * var[0], "varianza EOF2 (%)": 100 * var[1], "varianza EOF3 (%)": 100 * var[2],
            "N efectivo": n_ef, "EOF1 separada de EOF2 (North)": bool(var[0] - err[0] > var[1] + err[1]),
            "EOF2 separada de EOF3 (North)": bool(var[1] - err[1] > var[2] + err[2])}
    for i in range(2):
        rs = [PC[nom][f"CP{i + 1}"].corr(oni.shift(k).reindex(A.index)) for k in range(7)]
        k = int(np.argmax(np.abs(rs)))
        fila[f"r(CP{i + 1}, ONI) sin rezago"] = rs[0]
        fila[f"r(CP{i + 1}, ONI) máxima"] = rs[k]
        fila[f"rezago de la máxima CP{i + 1} (meses)"] = k
    R[nom] = fila
res = pd.DataFrame(R).T
res.index.name = "campo"
# consistencia con el Cubo
for nom in campos:
    for i in (1, 2):
        res.loc[nom, f"r espacial EOF{i} con el Cubo"] = MAP[nom][f"EOF{i}"].corr(MAP["Cubo IDEAM"][f"EOF{i}"])
        res.loc[nom, f"r temporal CP{i} con el Cubo"] = PC[nom][f"CP{i}"].corr(PC["Cubo IDEAM"][f"CP{i}"])
res.to_csv(OUT / "eof_resumen.csv", encoding="utf-8-sig")
pd.concat(PC, axis=1).to_csv(OUT / "componentes_principales.csv", encoding="utf-8-sig")
pd.concat(MAP, axis=1).to_csv(OUT / "patrones_eof.csv", encoding="utf-8-sig")
pd.set_option("display.width", 250)
print(res.round(2).T.to_string())

# ------------------------------------------------------------------------------------------------- mapas (300 dpi)
U = gpd.read_file(ENT / "unidades.gpkg").to_crs(4326)
cu = U.dissolve()
lat, lon = np.sort(cel.lat.unique()), np.sort(cel.lon.unique())


def malla(serie):
    g = np.full((len(lat), len(lon)), np.nan)
    c = cel.loc[serie.index]
    g[np.searchsorted(lat, c.lat.values), np.searchsorted(lon, c.lon.values)] = serie.values
    return g


niveles = np.round(np.arange(-1, 1.01, 0.2), 1)
norm = BoundaryNorm(niveles, 256)
nomb = list(campos)
fig, axs = plt.subplots(2, len(nomb), figsize=(2.3 * len(nomb) + 1.2, 9.6), constrained_layout=True)
for j, nom in enumerate(nomb):
    for i in range(2):
        ax = axs[i, j]
        im = ax.pcolormesh(lon, lat, malla(MAP[nom][f"EOF{i + 1}"]), cmap="RdBu", norm=norm, shading="nearest")
        cu.boundary.plot(ax=ax, color="k", lw=0.8)
        v = res.loc[nom, f"varianza EOF{i + 1} (%)"]
        r = res.loc[nom, f"r(CP{i + 1}, ONI) máxima"]
        kk = int(res.loc[nom, f"rezago de la máxima CP{i + 1} (meses)"])
        ax.set_title(f"{nom}\nEOF{i + 1}: {v:.0f} % de la varianza\nr(CP, ONI) = {r:+.2f} (rezago {kk})".replace(".", ",").replace("-", "−"),
                     fontsize=8.5)
        ax.set_aspect("equal"); ax.tick_params(labelsize=6.5); ax.set_xlabel(""); ax.set_ylabel("")
cb = fig.colorbar(im, ax=axs, shrink=0.6, ticks=niveles, extend="neither")
cb.set_label("Correlación de la componente principal con la anomalía de cada celda")
fig.suptitle("Modos principales de variabilidad (EOF) de la lluvia y de la humedad del suelo, anomalías trimestrales móviles 1981–2023\n"
             "azul: la celda se humedece cuando la componente es positiva · rojo: se seca", fontsize=11)
fig.savefig(FIG / "fig_eof_mapas.png", dpi=300, facecolor="white")
plt.close(fig)

# datos para el sitio
sitio = {"t": PC["Cubo IDEAM"].index.strftime("%Y-%m").tolist(),
         "oni": oni.reindex(PC["Cubo IDEAM"].index).round(2).tolist(),
         "cp1": {n: PC[n]["CP1"].reindex(PC["Cubo IDEAM"].index).round(2).tolist() for n in nomb}}
(OUT / "sitio.json").write_text(json.dumps(sitio, ensure_ascii=False), encoding="utf-8")
