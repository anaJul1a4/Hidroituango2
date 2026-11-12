"""
Trabajo 2 · numeral 1a–b: variables de entrada del modelo lluvia–escorrentía mensual en la grilla del Cubo de datos del IDEAM.

Grilla de modelación: la del Cubo de datos del IDEAM (0,1°; P, Tmax, Tmin y HR mensuales 1981–2023, generado con CDT a partir de
1567 estaciones). Cada celda lleva la fracción de su área dentro de cada una de las 10 unidades del modelo: las áreas incrementales
entre las estaciones del cauce principal del Trabajo 1 (La Balsa → Juanchito → … → Cañafisto) y la última, de Cañafisto a la presa.

Precipitación (mm/mes), 1981–2023, llevada a la grilla del Cubo:
  · Cubo IDEAM (nativo, tras el control de calidad de 00_limpieza_cubo.py), CHIRPS v2.0 y v3.0 (interpolación lineal desde 0,05°), ERA5-Land (misma retícula), ERA5 (lineal desde 0,25°).
  · ERA5 y ERA5-Land corregidos por mapeo de cuantiles empírico, por celda y mes calendario, con el Cubo como referencia
    (ajuste 1981–2010, aplicación 1981–2023; 2011–2023 queda como verificación independiente). En el Trabajo 1 la referencia fue
    CHIRPS v2.0 porque del IDEAM sólo había normales.
Evapotranspiración de referencia (mm/mes), con Tmax, Tmin y HR del Cubo:
  · FAO Penman-Monteith (Allen et al., 1998), el método recomendado por el IDEAM (NT IDEAM-METEO/003-2021), con el procedimiento de
    FAO-56 para datos faltantes: radiación solar de la diferencia de temperaturas (ec. 50, kRs = 0,16 interior), viento de 2 m/s,
    presión según la elevación media de la celda (DEM GLO-30 del Trabajo 1) y ea de la humedad relativa media (ec. 19).
  · Hargreaves-Samani (1985), el método del Trabajo 1, como contraste.

Salidas: trabajo2/resultados/01_entradas/ grilla_celdas.csv (celdas y fracciones), P_<producto>.nc, ETo_PM.nc, ETo_HG.nc,
         T_cubo.nc, series_unidades.csv (promedios por unidad y cuenca), qm_cubo.csv (resumen de la corrección)
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from rasterio.warp import Resampling, reproject
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "trabajo1" / "scripts"))
import productos  # noqa: E402

T1 = ROOT / "trabajo1" / "resultados"
CUBO = ROOT / "CUBO_IDEAM"
OUT = ROOT / "trabajo2" / "resultados" / "01_entradas"
OUT.mkdir(parents=True, exist_ok=True)
T0, TF = "1981-01-01", "2023-12-01"

# ----------------------------------------------------------------------------- unidades del modelo (áreas incrementales)
sub = gpd.read_file(T1 / "06_caudales" / "subcuencas_estaciones.gpkg", layer="areas_drenaje").sort_values("area_km2_DEM")
cuenca = gpd.read_file(T1 / "01_delimitacion" / "cuenca_cauca_hidroituango.gpkg", layer="cuenca").to_crs(sub.crs)
ORDEN = ["26027010", "26067010", "26107070", "26177030", "26167070", "26187110", "26207030", "26207080", "26217050"]
NOM = dict(zip(sub.codigo, sub.estacion.str.title()))
NOM["26217050"] = "Cañafisto"
geo = {r.codigo: r.geometry for r in sub.itertuples()}
geo["PRESA"] = cuenca.geometry.iloc[0]
unidades, previa = {}, None
for c in ORDEN + ["PRESA"]:
    g = geo[c].intersection(geo["PRESA"])
    unidades[c] = g if previa is None else g.difference(previa)
    previa = g if previa is None else previa.union(g)
U = gpd.GeoDataFrame({"unidad": list(unidades), "geometry": list(unidades.values())}, crs=sub.crs)
U["area_km2"] = U.area / 1e6
U["salida"] = [NOM.get(c, "Presa") for c in U.unidad]
U.to_file(OUT / "unidades.gpkg", driver="GPKG")

# ----------------------------------------------------------------------------- celdas del Cubo (0,1°) y fracciones
cp = xr.open_dataset(CUBO / "prcp_mes_acum_1981_2023.nc")
w, s, e, n = cuenca.to_crs(4326).total_bounds
lat = cp.lat.values[(cp.lat.values > s - 0.1) & (cp.lat.values < n + 0.1)]
lon = cp.lon.values[(cp.lon.values > w - 0.1) & (cp.lon.values < e + 0.1)]
celdas = gpd.GeoDataFrame([{"lat": la, "lon": lo, "geometry": box(lo - 0.05, la - 0.05, lo + 0.05, la + 0.05)}
                           for la in lat for lo in lon], crs=4326).to_crs(sub.crs)
celdas["area_celda_km2"] = celdas.area / 1e6
inter = gpd.overlay(celdas.reset_index(names="celda"), U[["unidad", "geometry"]], how="intersection")
inter["a_km2"] = inter.area / 1e6
fr = inter.pivot_table(index="celda", columns="unidad", values="a_km2", aggfunc="sum").reindex(columns=list(unidades)).fillna(0)
cel = celdas.loc[fr.index, ["lat", "lon", "area_celda_km2"]].join(fr)
cel["a_cuenca_km2"] = fr.sum(1)

# elevación media de cada celda (DEM GLO-30 de 90 m del Trabajo 1)
with rasterio.open(T1 / "01_delimitacion" / "dem_glo30_90m_3116.tif") as dem:
    z = np.full((len(lat), len(lon)), np.nan, dtype="float32")
    dst_t = rasterio.transform.from_origin(lon.min() - 0.05, lat.max() + 0.05, 0.1, 0.1)
    reproject(dem.read(1, masked=True).filled(np.nan).astype("float32"), z, src_transform=dem.transform, src_crs=dem.crs,
              dst_transform=dst_t, dst_crs="EPSG:4326", resampling=Resampling.average, src_nodata=np.nan, dst_nodata=np.nan)
zz = xr.DataArray(z, coords={"lat": np.sort(lat)[::-1], "lon": np.sort(lon)}, dims=("lat", "lon"))
cel["z_m"] = [float(zz.sel(lat=r.lat, lon=r.lon, method="nearest")) for r in cel.itertuples()]
cel.round(5).to_csv(OUT / "grilla_celdas.csv", index_label="celda", encoding="utf-8-sig")
print(f"{len(cel)} celdas de 0,1° con parte en la cuenca; área {cel.a_cuenca_km2.sum():,.0f} km²")


def a_grilla(da):
    """DataArray (time, lat, lon) → (time, celda) en las celdas de la cuenca."""
    da = da.sel(time=slice(T0, TF))
    return da.sel(lat=xr.DataArray(cel.lat.values, dims="celda"), lon=xr.DataArray(cel.lon.values, dims="celda"), method="nearest") \
        if np.allclose(np.diff(da.lat.values[:2]).__abs__(), 0.1, atol=1e-3) else \
        da.interp(lat=xr.DataArray(cel.lat.values, dims="celda"), lon=xr.DataArray(cel.lon.values, dims="celda"))


# ----------------------------------------------------------------------------- precipitación
P = {"Cubo IDEAM": a_grilla(xr.open_dataarray(CUBO / "prcp_mes_limpio_cuenca_1981_2023.nc").sortby("lat"))}  # 00_limpieza_cubo.py
for nom, clave in [("CHIRPS v2.0", "CHIRPS"), ("CHIRPS v3.0", "CHIRPS v3.0"), ("ERA5-Land", "ERA5-Land"), ("ERA5", "ERA5")]:
    p = productos.abrir(clave).precip.sortby("lat").sortby("lon")
    P[nom] = a_grilla(p)


def qm(sim, ref, cal=("1981-01-01", "2010-12-01")):
    """Mapeo de cuantiles empírico por celda y mes calendario (cuantiles 1–99 e interpolación lineal; fuera del rango, la razón del
    extremo)."""
    out = sim.copy()
    qs = np.linspace(0.01, 0.99, 99)
    for m in range(1, 13):
        sc, rc = sim.sel(time=slice(*cal)), ref.sel(time=slice(*cal))
        sc, rc = sc.where(sc.time.dt.month == m, drop=True), rc.where(rc.time.dt.month == m, drop=True)
        qsim, qref = np.nanquantile(sc.values, qs, axis=0), np.nanquantile(rc.values, qs, axis=0)
        idx = sim.time.dt.month == m
        x = sim.values[idx.values]
        y = np.empty_like(x)
        for j in range(x.shape[1]):
            xs, xr_ = qsim[:, j], qref[:, j]
            y[:, j] = np.interp(x[:, j], xs, xr_)
            alto, bajo = x[:, j] > xs[-1], x[:, j] < xs[0]
            y[alto, j] = x[alto, j] * xr_[-1] / max(xs[-1], 1e-6)
            y[bajo, j] = x[bajo, j] * xr_[0] / max(xs[0], 1e-6)
        out.values[idx.values] = np.clip(y, 0, None)
    return out


for nom in ["ERA5-Land", "ERA5"]:
    P[f"{nom} QM"] = qm(P[nom], P["Cubo IDEAM"])
for nom, da in P.items():
    da.rename("P").to_netcdf(OUT / f"P_{nom.replace(' ', '_')}.nc")

# ----------------------------------------------------------------------------- temperatura, humedad y ETo
T = {v: a_grilla(xr.open_dataset(CUBO / f"{v}_mes_prom_1981_2023.nc")[k]) for v, k in
     [("tmax", "tmpr"), ("tmin", "tmpr"), ("tmed", "tmpr"), ("humd", "humd")]}
xr.Dataset(T).to_netcdf(OUT / "T_cubo.nc")
tiempo = pd.DatetimeIndex(T["tmax"].time.values)
dias = tiempo.days_in_month.values[:, None]
J = (tiempo + pd.Timedelta(days=14)).dayofyear.values[:, None]                    # día central del mes
phi = np.radians(cel.lat.values)[None, :]
dr = 1 + 0.033 * np.cos(2 * np.pi * J / 365)
dl = 0.409 * np.sin(2 * np.pi * J / 365 - 1.39)
ws = np.arccos(-np.tan(phi) * np.tan(dl))
Ra = 24 * 60 / np.pi * 0.0820 * dr * (ws * np.sin(phi) * np.sin(dl) + np.cos(phi) * np.cos(dl) * np.sin(ws))   # MJ/m²/día
tx, tn = T["tmax"].values, T["tmin"].values
tm = (tx + tn) / 2
dT = np.clip(tx - tn, 0.1, None)
# Hargreaves-Samani (Trabajo 1): 0,0023·0,408·Ra·(Tm + 17,8)·√(Tmax − Tmin)
ETo_HG = 0.0023 * 0.408 * Ra * (tm + 17.8) * np.sqrt(dT) * dias
# FAO Penman-Monteith con datos faltantes (FAO-56)
zc = cel.z_m.values[None, :]
Pr = 101.3 * ((293 - 0.0065 * zc) / 293) ** 5.26
gam = 0.000665 * Pr
e0 = lambda t: 0.6108 * np.exp(17.27 * t / (t + 237.3))  # noqa: E731
es = (e0(tx) + e0(tn)) / 2
ea = np.clip(T["humd"].values, 1, 100) / 100 * es
Delta = 4098 * e0(tm) / (tm + 237.3) ** 2
Rs = 0.16 * np.sqrt(dT) * Ra
Rso = (0.75 + 2e-5 * zc) * Ra
Rnl = 4.903e-9 * ((tx + 273.16) ** 4 + (tn + 273.16) ** 4) / 2 * (0.34 - 0.14 * np.sqrt(ea)) * (1.35 * np.clip(Rs / Rso, 0.25, 1) - 0.35)
Rn = (1 - 0.23) * Rs - Rnl
u2 = 2.0
ETo_PM = (0.408 * Delta * Rn + gam * 900 / (tm + 273) * u2 * (es - ea)) / (Delta + gam * (1 + 0.34 * u2)) * dias
for nom, a in [("ETo_PM", ETo_PM), ("ETo_HG", ETo_HG)]:
    xr.DataArray(np.clip(a, 0, None), coords=T["tmax"].coords, dims=T["tmax"].dims, name="ETo").to_netcdf(OUT / f"{nom}.nc")

# ----------------------------------------------------------------------------- promedios por unidad y cuenca
fr = cel[list(unidades)].values                                                     # km² de cada celda en cada unidad
series = {}
var = {**{f"P {k}": v.values for k, v in P.items()}, "ETo PM": ETo_PM, "ETo Hargreaves": ETo_HG, "Tmax": tx, "Tmin": tn,
       "Tmed": T["tmed"].values, "HR": T["humd"].values}
for k, a in var.items():
    a = np.where(np.isfinite(a), a, np.nan)
    for j, u in enumerate(unidades):
        wj = fr[:, j]
        series[(k, u)] = np.nansum(a * wj, 1) / np.sum(wj * np.isfinite(a), 1)
    wc = fr.sum(1)
    series[(k, "CUENCA")] = np.nansum(a * wc, 1) / np.sum(wc * np.isfinite(a), 1)
S = pd.DataFrame(series, index=tiempo)
S.columns = pd.MultiIndex.from_tuples(S.columns, names=["variable", "unidad"])
S.round(3).to_csv(OUT / "series_unidades.csv", encoding="utf-8-sig")
U.drop(columns="geometry").round(1).to_csv(OUT / "unidades.csv", index=False, encoding="utf-8-sig")

# resumen: medias anuales de la cuenca y verificación de la corrección en 2011–2023
c = S.xs("CUENCA", axis=1, level="unidad")
anual = lambda x, a, b: x[a:b].resample("YS").sum().mean()  # noqa: E731
res = pd.DataFrame({"1981–2010 (mm/año)": [anual(c[k], "1981", "2010") for k in c if k.startswith(("P ", "ETo"))],
                    "2011–2023 (mm/año)": [anual(c[k], "2011", "2023") for k in c if k.startswith(("P ", "ETo"))]},
                   index=[k for k in c if k.startswith(("P ", "ETo"))])
ref = c["P Cubo IDEAM"]
for per, (a, b) in {"1981–2010": ("1981", "2010"), "2011–2023": ("2011", "2023")}.items():
    res[f"r mensual con el Cubo {per}"] = [c[k][a:b].corr(ref[a:b]) if k.startswith("P ") else np.nan for k in res.index]
res.round(3).to_csv(OUT / "resumen_entradas.csv", encoding="utf-8-sig")
pd.set_option("display.width", 200)
print(U.drop(columns="geometry").round(0).to_string(index=False))
print(res.round(2).to_string())
