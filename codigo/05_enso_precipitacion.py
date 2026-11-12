"""
Trabajo 2 · numeral 2: impactos de El Niño y La Niña sobre la precipitación de la cuenca.

Fases ENSO: definición operativa del CPC (NOAA) sobre el ONI (ERSST v5): El Niño (La Niña) cuando el ONI ≥ +0,5 °C (≤ −0,5 °C)
durante al menos cinco trimestres móviles consecutivos. Cada trimestre DEF, MAM, JJA y SON se clasifica según el ONI de ese mismo
trimestre (DEF = DJF del CPC: diciembre del año anterior, enero y febrero).
Anomalía estandarizada por celda, producto y trimestre: z = (P_trimestre − media) / desviación estándar, con la media y la desviación
de 1981–2010 de ese trimestre. Compuesto = promedio de z en los trimestres de cada fase (1981–2023).
Consistencia entre productos: correlación espacial de cada compuesto con el del Cubo, fracción de celdas con el mismo signo que el
Cubo y anomalía media de la cuenca. Relación lineal: correlación de Pearson entre el ONI y z de la cuenca por trimestre.

Salidas: trabajo2/resultados/05_enso_P/ fases_enso.csv, compuestos_cuenca.csv, consistencia.csv, correlacion_oni.csv,
         compuestos_celdas.nc, mapas_compuesto_nino.png, mapas_compuesto_nina.png
"""
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ENT = ROOT / "trabajo2" / "resultados" / "01_entradas"
OUT = ROOT / "trabajo2" / "resultados" / "05_enso_P"
OUT.mkdir(parents=True, exist_ok=True)
ONI = ROOT / "trabajo1" / "datos" / "enso" / "oni.ascii.txt"
PRODS = ["Cubo IDEAM", "CHIRPS v2.0", "CHIRPS v3.0", "ERA5-Land", "ERA5", "ERA5-Land QM", "ERA5 QM"]
TRIM = {"DEF": "DJF", "MAM": "MAM", "JJA": "JJA", "SON": "SON"}
FASES = ["El Niño", "La Niña"]


# ----------------------------------------------------------------------------- fases ENSO (CPC)
def fases_oni():
    o = pd.read_csv(ONI, sep=r"\s+")
    estaciones = ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"]
    o["k"] = o.SEAS.map({s: i for i, s in enumerate(estaciones)})
    o = o.sort_values(["YR", "k"]).reset_index(drop=True)
    fase = np.array(["Neutro"] * len(o), dtype=object)
    for signo, nom in [(1, "El Niño"), (-1, "La Niña")]:
        c = (signo * o.ANOM >= 0.5).values
        i = 0
        while i < len(c):
            if c[i]:
                j = i
                while j < len(c) and c[j]:
                    j += 1
                if j - i >= 5:
                    fase[i:j] = nom
                i = j
            else:
                i += 1
    o["fase"] = fase
    return o


oni = fases_oni()
oni[["YR", "SEAS", "ANOM", "fase"]].to_csv(OUT / "fases_enso.csv", index=False, encoding="utf-8-sig")


def trimestral(da):
    """(time, celda) mensual → DataFrame de trimestres DEF, MAM, JJA, SON por año (DEF del año del enero)."""
    s = da.sel(time=slice("1980-12-01", "2023-11-30"))
    t = pd.DatetimeIndex(s.time.values)
    anio = np.where(t.month == 12, t.year + 1, t.year)
    tri = np.select([t.month.isin([12, 1, 2]), t.month.isin([3, 4, 5]), t.month.isin([6, 7, 8])], ["DEF", "MAM", "JJA"], "SON")
    g = xr.DataArray(s.values, dims=("time", "celda")).assign_coords(anio=("time", anio), tri=("time", tri))
    out = {}
    for tr in TRIM:
        x = g.where(g.tri == tr, drop=True)
        n = x.groupby("anio").count()
        out[tr] = x.groupby("anio").sum().where(n == 3)
    return out


def anomalias(da):
    z = {}
    for tr, x in trimestral(da).items():
        base = x.sel(anio=slice(1981, 2010))
        z[tr] = (x - base.mean("anio")) / base.std("anio")
    return z


cel = pd.read_csv(ENT / "grilla_celdas.csv", index_col="celda")
w = cel.a_cuenca_km2.values
fase_de = {(r.YR, s): r.fase for s in TRIM.values() for r in oni[oni.SEAS == s].itertuples()}
oni_de = {(r.YR, r.SEAS): r.ANOM for r in oni.itertuples()}

comp, cons, corr, compc = [], [], [], {}
Z = {}
for prod in PRODS:
    da = xr.open_dataarray(ENT / f"P_{prod.replace(' ', '_')}.nc")
    Z[prod] = anomalias(da)
for prod in PRODS:
    for tr, z in Z[prod].items():
        anios = z.anio.values
        f = np.array([fase_de.get((a, TRIM[tr]), "Neutro") for a in anios])
        zc = (z * w).sum("celda") / w.sum()                               # z media de la cuenca (de las anomalías por celda)
        # z de la serie de cuenca (estandarizando la serie agregada)
        for fa in FASES:
            sel = f == fa
            mapa = z.isel(anio=np.where(sel)[0]).mean("anio").values
            compc[(prod, tr, fa)] = mapa
            comp.append({"producto": prod, "trimestre": tr, "fase": fa, "n trimestres": int(sel.sum()),
                         "z medio de la cuenca": float(zc.isel(anio=np.where(sel)[0]).mean()),
                         "% de la cuenca con z < 0": 100 * float((w * (mapa < 0)).sum() / w.sum())})
        o = np.array([oni_de.get((a, TRIM[tr]), np.nan) for a in anios])
        m = np.isfinite(o) & np.isfinite(zc.values)
        corr.append({"producto": prod, "trimestre": tr, "r(ONI, z cuenca)": np.corrcoef(o[m], zc.values[m])[0, 1], "n": int(m.sum())})
for (prod, tr, fa), mapa in compc.items():
    ref = compc[("Cubo IDEAM", tr, fa)]
    ok = np.isfinite(mapa) & np.isfinite(ref) & (w > 0)
    cons.append({"producto": prod, "trimestre": tr, "fase": fa, "r espacial con el Cubo": np.corrcoef(mapa[ok], ref[ok])[0, 1],
                 "% área con el mismo signo que el Cubo": 100 * (w[ok] * (np.sign(mapa[ok]) == np.sign(ref[ok]))).sum() / w[ok].sum()})
C = pd.DataFrame(comp); K = pd.DataFrame(cons); R = pd.DataFrame(corr)
C.round(3).to_csv(OUT / "compuestos_cuenca.csv", index=False, encoding="utf-8-sig")
K.round(3).to_csv(OUT / "consistencia.csv", index=False, encoding="utf-8-sig")
R.round(3).to_csv(OUT / "correlacion_oni.csv", index=False, encoding="utf-8-sig")
xr.Dataset({f"{p}|{t}|{f}": (("celda",), m) for (p, t, f), m in compc.items()},
           coords={"celda": cel.index.values}).to_netcdf(OUT / "compuestos_celdas.nc")

# ----------------------------------------------------------------------------- mapas (rojo = más seco, azul = más húmedo)
U = gpd.read_file(ENT / "unidades.gpkg").to_crs(4326)
cu = U.dissolve()
lat, lon = np.sort(cel.lat.unique()), np.sort(cel.lon.unique())
CL = [-1.5, -1.0, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1.0, 1.5]
cmap = ListedColormap(plt.get_cmap("RdBu")(np.linspace(0.05, 0.95, len(CL) + 1)))
norm = BoundaryNorm([-9] + CL + [9], cmap.N)
MAP_PRODS = ["Cubo IDEAM", "CHIRPS v2.0", "CHIRPS v3.0", "ERA5-Land", "ERA5"]


def malla(v):
    g = np.full((len(lat), len(lon)), np.nan)
    g[np.searchsorted(lat, cel.lat.values), np.searchsorted(lon, cel.lon.values)] = np.where(w > 0, v, np.nan)
    return g


for fa, arch in [("El Niño", "mapas_compuesto_nino.png"), ("La Niña", "mapas_compuesto_nina.png")]:
    fig, axs = plt.subplots(len(MAP_PRODS), 4, figsize=(9.5, 15), constrained_layout=True)
    for i, prod in enumerate(MAP_PRODS):
        for j, tr in enumerate(TRIM):
            ax = axs[i, j]
            im = ax.pcolormesh(lon, lat, malla(compc[(prod, tr, fa)]), cmap=cmap, norm=norm, shading="nearest")
            cu.boundary.plot(ax=ax, color="k", lw=0.7)
            ax.set_xticks([]); ax.set_yticks([]); ax.set_aspect("equal")
            zc = C[(C.producto == prod) & (C.trimestre == tr) & (C.fase == fa)]["z medio de la cuenca"].iloc[0]
            ax.set_title(f"{tr} · z̄ = {zc:+.2f}", fontsize=9)
            ax.set_xlabel("")
            ax.set_ylabel(prod if j == 0 else "", fontsize=10)
    n = C[(C.producto == "Cubo IDEAM") & (C.fase == fa)].set_index("trimestre")["n trimestres"]
    fig.colorbar(im, ax=axs, orientation="horizontal", fraction=0.025, pad=0.01, ticks=CL,
                 label="Anomalía estandarizada de la precipitación (z): rojo = más seco, azul = más húmedo")
    fig.suptitle(f"Precipitación en trimestres {fa} (1981–2023; n = " + ", ".join(f"{k} {v}" for k, v in n.items()) + ")",
                 fontsize=11)
    fig.savefig(OUT / arch, dpi=300)
    plt.close(fig)

pd.set_option("display.width", 220)
print(C.pivot_table(index="producto", columns=["fase", "trimestre"], values="z medio de la cuenca").loc[PRODS].round(2).to_string())
print(K.pivot_table(index="producto", columns=["fase", "trimestre"], values="r espacial con el Cubo").loc[PRODS].round(2).to_string())
print(R.pivot(index="producto", columns="trimestre", values="r(ONI, z cuenca)").loc[PRODS].round(2).to_string())
