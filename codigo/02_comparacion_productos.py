"""
Trabajo 2 · numeral 1a–b: evaluación de los productos de precipitación con el Cubo de datos del IDEAM incluido, y de la ETo.

Productos (grilla del Cubo, 01_entradas.py): Cubo IDEAM (con control de calidad), CHIRPS v2.0, CHIRPS v3.0, ERA5-Land y ERA5 sin
corregir y corregidos por mapeo de cuantiles con el Cubo. En el Trabajo 1 ERA5 y ERA5-Land ya se habían corregido por mapeo de
cuantiles con CHIRPS v2.0 (scripts 28–32): aquí se repite con la referencia que entonces no existía.

  1. Mapas de P media anual 1981–2010 (misma escala de color por valor del Trabajo 1).
  2. Ciclo anual de la cuenca 1981–2010, junto al kriging de las normales IDEAM del Trabajo 1.
  3. Métricas mensuales frente al Cubo (cuenca): r, sesgo, RMSE, KGE y correlación espacial de la media anual.
  4. Balance de largo plazo en las áreas de drenaje de las 9 estaciones y la presa (1981–2010): ETR de Budyko celda a celda con la
     P de cada producto y la ETo de Penman-Monteith o de Hargreaves; Q_est frente al Q observado del Trabajo 1.

Salidas: trabajo2/resultados/02_comparacion/
"""
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "trabajo1" / "scripts"))
import escalas  # noqa: E402

T1 = ROOT / "trabajo1" / "resultados"
ENT = ROOT / "trabajo2" / "resultados" / "01_entradas"
OUT = ROOT / "trabajo2" / "resultados" / "02_comparacion"
OUT.mkdir(parents=True, exist_ok=True)
SEG = 365.25 * 86400
PRODS = ["Cubo IDEAM", "CHIRPS v2.0", "CHIRPS v3.0", "ERA5-Land", "ERA5", "ERA5-Land QM", "ERA5 QM"]
ORDEN = ["26027010", "26067010", "26107070", "26177030", "26167070", "26187110", "26207030", "26207080", "26217050", "PRESA"]

cel = pd.read_csv(ENT / "grilla_celdas.csv", index_col="celda")
U = gpd.read_file(ENT / "unidades.gpkg")
P = {k: xr.open_dataarray(ENT / f"P_{k.replace(' ', '_')}.nc") for k in PRODS}
ETo = {"Penman-Monteith": xr.open_dataarray(ENT / "ETo_PM.nc"), "Hargreaves": xr.open_dataarray(ENT / "ETo_HG.nc")}
anual = lambda da: da.sel(time=slice("1981", "2010")).groupby("time.year").sum().mean("year").values  # noqa: E731
Pa = {k: anual(v) for k, v in P.items()}
Ea = {k: anual(v) for k, v in ETo.items()}
wc = cel.a_cuenca_km2.values

# 1. mapas -----------------------------------------------------------------------------------------------------------
cu = U.to_crs(4326).dissolve()
lat, lon = np.sort(cel.lat.unique()), np.sort(cel.lon.unique())


def malla(v):
    g = np.full((len(lat), len(lon)), np.nan)
    g[np.searchsorted(lat, cel.lat.values), np.searchsorted(lon, cel.lon.values)] = np.where(wc > 0, v, np.nan)
    return g


fig, axs = plt.subplots(2, 4, figsize=(13, 9.2), constrained_layout=True)
vals = [Pa[k] for k in PRODS]
for ax, k in zip(axs.flat, PRODS):
    im = ax.pcolormesh(lon, lat, malla(Pa[k]), cmap=escalas.P["cmap"], norm=escalas.P["norm"], shading="nearest")
    cu.boundary.plot(ax=ax, color="k", lw=0.8)
    U.to_crs(4326).boundary.plot(ax=ax, color="k", lw=0.25, alpha=0.5)
    m = np.nansum(Pa[k] * wc) / wc.sum()
    ax.set_title(f"{k}\nmedia {m:,.0f} mm/año".replace(",", " "), fontsize=10)
    ax.set_aspect("equal"); ax.tick_params(labelsize=7); ax.set_xlabel("Longitud (°)", fontsize=8); ax.set_ylabel("Latitud (°)", fontsize=8)
axs.flat[-1].axis("off")
escalas.barra(fig, im, escalas.P, *[v[wc > 0] for v in vals], ax=axs.flat[-1], fraction=0.5, label="P media anual 1981–2010 (mm/año)")
fig.suptitle("Precipitación media anual 1981–2010 por producto (grilla del Cubo de datos IDEAM, 0,1°)", fontsize=12)
fig.savefig(OUT / "mapas_P_productos.png", dpi=200)
plt.close(fig)

# 2. ciclo anual de la cuenca ----------------------------------------------------------------------------------------
S = pd.read_csv(ENT / "series_unidades.csv", header=[0, 1], index_col=0, parse_dates=True)
C = S.xs("CUENCA", axis=1, level="unidad")
ciclo = pd.DataFrame({k: C[f"P {k}"]["1981":"2010"].groupby(C.index[(C.index.year >= 1981) & (C.index.year <= 2010)].month).mean()
                      for k in PRODS})
c1 = pd.read_csv(T1 / "14_ciclo_productos" / "ciclos_productos.csv", index_col=0)
col_ideam = [c for c in c1.columns if "IDEAM" in c]
if col_ideam:
    ciclo.insert(0, "IDEAM normales (kriging, Trabajo 1)", c1[col_ideam[0]].values[:12])
for k, v in ETo.items():
    ciclo[f"ETo {k}"] = C[f"ETo {'PM' if k == 'Penman-Monteith' else 'Hargreaves'}"]["1981":"2010"].groupby(
        C.index[(C.index.year >= 1981) & (C.index.year <= 2010)].month).mean()
ciclo.index.name = "mes"
ciclo.round(1).to_csv(OUT / "ciclo_anual_cuenca.csv", encoding="utf-8-sig")

# 3. métricas frente al Cubo -----------------------------------------------------------------------------------------
ref = C["P Cubo IDEAM"]


def kge(s, o):
    r = np.corrcoef(s, o)[0, 1]
    return 1 - np.sqrt((r - 1) ** 2 + (s.std() / o.std() - 1) ** 2 + (s.mean() / o.mean() - 1) ** 2)


filas = []
for k in PRODS[1:]:
    for per, (a, b) in {"1981–2010": ("1981", "2010"), "2011–2023": ("2011", "2023")}.items():
        s, o = C[f"P {k}"][a:b], ref[a:b]
        an_s, an_o = s.groupby(s.index.year).sum(), o.groupby(o.index.year).sum()
        filas.append({"producto": k, "periodo": per, "P anual (mm/año)": an_s.mean(), "sesgo (%)": 100 * (s.mean() / o.mean() - 1),
                      "r mensual": s.corr(o), "r anomalías mensuales": (s - s.groupby(s.index.month).transform("mean")).corr(
                          o - o.groupby(o.index.month).transform("mean")),
                      "r anual": an_s.corr(an_o), "RMSE (mm/mes)": np.sqrt(((s - o) ** 2).mean()), "KGE": kge(s, o),
                      "r espacial (media anual)": np.corrcoef(Pa[k][wc > 0], Pa["Cubo IDEAM"][wc > 0])[0, 1] if per == "1981–2010" else np.nan})
met = pd.DataFrame(filas)
met.round(3).to_csv(OUT / "metricas_vs_cubo.csv", index=False, encoding="utf-8-sig")

# 4. balance de largo plazo por área de drenaje ----------------------------------------------------------------------
b9 = pd.read_csv(T1 / "09_balance" / "balance_subcuencas.csv", dtype={"codigo": str})
qobs = dict(zip(b9.codigo, b9["Q obs (m³/s)"]))
nom = dict(zip(b9.codigo, b9.estacion))
qobs["PRESA"], nom["PRESA"] = qobs.get("HIDRO", np.nan), "Presa (cierre)"


def budyko(p, etp):
    f = etp / p
    return p * np.sqrt(f * np.tanh(1 / f) * (1 - np.exp(-f)))


bal = []
for i, cod in enumerate(ORDEN):
    w = cel[ORDEN[: i + 1]].sum(1).values                                       # km² de cada celda dentro del área de drenaje
    for k in PRODS:
        for e, ea in Ea.items():
            etr = budyko(Pa[k], ea)
            pm, em, rm = (np.nansum(x * w) / w.sum() for x in (Pa[k], etr, Pa[k] - etr))
            q = rm / 1000 * w.sum() * 1e6 / SEG
            bal.append({"codigo": cod, "estacion": nom.get(cod, cod), "A (km²)": w.sum(), "producto": k, "ETo": e, "P": pm,
                        "ETo media": np.nansum(ea * w) / w.sum(), "ETR": em, "Q est (m³/s)": q, "Q obs (m³/s)": qobs.get(cod),
                        "error (%)": 100 * (q / qobs.get(cod, np.nan) - 1)})
B = pd.DataFrame(bal)
B.round(2).to_csv(OUT / "balance_productos_cubo.csv", index=False, encoding="utf-8-sig")
res = B[B.codigo != "PRESA"].groupby(["producto", "ETo"], sort=False)["error (%)"].agg(
    sesgo="mean", MAE=lambda e: e.abs().mean()).unstack("ETo")
res[("cierre", "Penman-Monteith")] = B[(B.codigo == "PRESA") & (B.ETo == "Penman-Monteith")].set_index("producto")["error (%)"]
res[("cierre", "Hargreaves")] = B[(B.codigo == "PRESA") & (B.ETo == "Hargreaves")].set_index("producto")["error (%)"]
res.round(1).to_csv(OUT / "resumen_balance.csv", encoding="utf-8-sig")

pd.set_option("display.width", 230); pd.set_option("display.max_columns", 20)
print(ciclo.round(0).T.to_string())
print(met.round(2).to_string(index=False))
print(res.round(1).to_string())
