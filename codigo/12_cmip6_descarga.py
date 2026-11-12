"""
Trabajo 2 · proyecciones CMIP6 · paso 1: descarga y selección de modelos por su ciclo anual.

Fuente: catálogo CMIP6 de Pangeo en Google Cloud (copia pública de ESGF, formato zarr; acceso anónimo).
Tabla Amon (mensual). Un miembro por modelo, el mismo en todos los experimentos y variables (r1i1p1f1 si existe).

  python 12_cmip6_descarga.py tamizaje      pr histórica 1981–2014 de los 28 modelos con pr, tasmax y tasmin en historical,
                                            ssp245 y ssp585 → ciclo anual de la cuenca frente al Cubo → ranking y selección
  python 12_cmip6_descarga.py proyecciones  pr, tasmax y tasmin de los 6 modelos elegidos: historical 1981–2014 y
                                            ssp245/ssp585 2015–2100

Sólo se guarda el recuadro 1°S–11°N, 80–72°W (con margen para interpolar a la grilla del Cubo los modelos de grilla gruesa).
Unidades: pr en mm/mes (flujo × días del mes del calendario gregoriano), tasmax y tasmin en °C. Tiempo: primer día de cada mes.

Selección (1981–2010, P media de la cuenca, modelo interpolado bilinealmente a las celdas del Cubo):
  · r del ciclo anual con el del Cubo (forma: régimen bimodal y su fase),
  · RMSE del ciclo normalizado por su media (forma independiente del sesgo),
  · |sesgo| de la media anual (pesa la mitad: el QDM lo corrige, pero un sesgo enorme revela física pobre).
Puntaje = rango(r) + rango(RMSE normalizado) + 0,5 · rango(|sesgo|); se elige el mejor de cada familia de modelos (los que comparten
componente atmosférico), hasta 6.

Salidas: HIDROITUANGO/CMIP6/<modelo>/<experimento>_<variable>.nc y trabajo2/resultados/11_cmip6/
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[2]
R2 = ROOT / "trabajo2" / "resultados"
DATA = ROOT / "CMIP6"
OUT = R2 / "11_cmip6"
OUT.mkdir(parents=True, exist_ok=True)
DATA.mkdir(exist_ok=True)
LAT, LON = (-1.0, 11.0), (-80.0, -72.0)
NSEL = 6
FAMILIA = {"ACCESS-CM2": "UM (Hadley)", "HadGEM3-GC31-LL": "UM (Hadley)", "UKESM1-0-LL": "UM (Hadley)", "KACE-1-0-G": "UM (Hadley)",
           "CNRM-CM6-1": "CNRM", "CNRM-CM6-1-HR": "CNRM", "CNRM-ESM2-1": "CNRM", "CanESM5": "CanESM", "CanESM5-CanOE": "CanESM",
           "EC-Earth3": "EC-Earth", "EC-Earth3-Veg": "EC-Earth", "EC-Earth3-Veg-LR": "EC-Earth",
           "AWI-CM-1-1-MR": "ECHAM (MPI)", "MPI-ESM1-2-HR": "ECHAM (MPI)", "MPI-ESM1-2-LR": "ECHAM (MPI)", "NESM3": "ECHAM (MPI)",
           "INM-CM4-8": "INM", "INM-CM5-0": "INM", "MIROC6": "MIROC", "MIROC-ES2L": "MIROC", "GFDL-CM4": "GFDL", "GFDL-ESM4": "GFDL"}
EXP_ESC = ["ssp245", "ssp585"]
VARS = ["pr", "tasmax", "tasmin"]


def catalogo():
    f = OUT / "catalogo_amon.csv"
    if f.exists():
        return pd.read_csv(f)
    c = pd.read_csv("https://storage.googleapis.com/cmip6/pangeo-cmip6.csv", low_memory=False)
    c = c[(c.table_id == "Amon") & c.variable_id.isin(VARS) & c.experiment_id.isin(["historical"] + EXP_ESC)]
    c.to_csv(f, index=False)
    return c


def miembros(c):
    need = {(e, v) for e in ["historical"] + EXP_ESC for v in VARS}
    sel = {}
    for (m, mem), d in c.groupby(["source_id", "member_id"]):
        if need <= set(zip(d.experiment_id, d.variable_id)):
            sel.setdefault(m, []).append(mem)
    out = {}
    for m, ms in sel.items():
        out[m] = next((p for p in ["r1i1p1f1", "r1i1p1f2", "r1i1p1f3", "r1i1p2f1"] if p in ms), sorted(ms)[0])
    return dict(sorted(out.items()))


def bajar(c, modelo, miembro, exp, var, t0, t1):
    dest = DATA / modelo / f"{exp}_{var}.nc"
    if dest.exists():
        return xr.open_dataarray(dest)
    fila = c[(c.source_id == modelo) & (c.member_id == miembro) & (c.experiment_id == exp) & (c.variable_id == var)]
    fila = fila.sort_values("version").iloc[-1]
    ds = xr.open_zarr(fila.zstore, consolidated=True, storage_options={"token": "anon"}, use_cftime=True)
    da = ds[var]
    ren = {k: v for k, v in {"latitude": "lat", "longitude": "lon"}.items() if k in da.dims}
    da = da.rename(ren)
    lon = da.lon
    if float(lon.max()) > 180:
        da = da.assign_coords(lon=((lon + 180) % 360) - 180).sortby("lon")
    da = da.sortby("lat").sel(lat=slice(*LAT), lon=slice(*LON)).sel(time=slice(str(t0), str(t1))).load()
    años, meses = da.time.dt.year.values, da.time.dt.month.values
    t = pd.to_datetime({"year": años, "month": meses, "day": 1})
    da = da.assign_coords(time=t.values)
    if var == "pr":
        dias = xr.DataArray(t.dt.days_in_month.values, dims="time", coords={"time": t.values})
        da = da * 86400 * dias
        da.attrs = {"units": "mm/mes"}
    else:
        da = da - 273.15
        da.attrs = {"units": "°C"}
    da = da.drop_vars([v for v in da.coords if v not in ("time", "lat", "lon")]).astype("float32")
    da.name = var
    dest.parent.mkdir(exist_ok=True)
    da.to_netcdf(dest)
    return da


def a_cuenca(da, cel):
    v = da.interp(lat=xr.DataArray(cel.lat.values, dims="c"), lon=xr.DataArray(cel.lon.values, dims="c"))
    w = cel.a_cuenca_km2.values
    return pd.Series((v.values * w).sum(1) / w.sum(), index=pd.DatetimeIndex(da.time.values))


if __name__ == "__main__":
    fase = sys.argv[1] if len(sys.argv) > 1 else "tamizaje"
    c = catalogo()
    mm = miembros(c)
    print(len(mm), "modelos")
    cel = pd.read_csv(R2 / "01_entradas" / "grilla_celdas.csv")
    cubo = pd.read_csv(R2 / "02_comparacion" / "ciclo_anual_cuenca.csv", index_col=0)["Cubo IDEAM"].values
    if fase == "tamizaje":
        filas, ciclos = [], {}
        for m, mem in mm.items():
            try:
                da = bajar(c, m, mem, "historical", "pr", 1981, 2014)
            except Exception as e:  # noqa: BLE001
                print(f"  {m}: error {e}")
                continue
            s = a_cuenca(da, cel)["1981":"2010"]
            cy = s.groupby(s.index.month).mean().values
            ciclos[m] = cy
            filas.append({"modelo": m, "miembro": mem, "familia": FAMILIA.get(m, m), "resolución (°)": float(np.abs(np.diff(da.lat.values)).mean()),
                          "P anual (mm)": cy.sum(), "sesgo (%)": 100 * (cy.sum() / cubo.sum() - 1),
                          "r del ciclo": np.corrcoef(cy, cubo)[0, 1],
                          "RMSE del ciclo normalizado": np.sqrt(np.mean((cy / cy.mean() - cubo / cubo.mean()) ** 2))})
            print(f"  {m:<18} r={filas[-1]['r del ciclo']:+.2f}  sesgo={filas[-1]['sesgo (%)']:+.0f} %", flush=True)
        t = pd.DataFrame(filas).set_index("modelo")
        t["puntaje"] = (t["r del ciclo"].rank(ascending=False) + t["RMSE del ciclo normalizado"].rank()
                        + 0.5 * t["sesgo (%)"].abs().rank())
        t = t.sort_values("puntaje")
        elegidos, fams = [], set()
        for m, r in t.iterrows():
            if r.familia not in fams and len(elegidos) < NSEL:
                elegidos.append(m); fams.add(r.familia)
        t["elegido"] = t.index.isin(elegidos)
        t.to_csv(OUT / "tamizaje_modelos.csv", encoding="utf-8-sig")
        pd.DataFrame(ciclos, index=range(1, 13)).assign(**{"Cubo IDEAM": cubo}).to_csv(OUT / "ciclos_historicos.csv", encoding="utf-8-sig")
        print(t.round(2).to_string())
        print("Elegidos:", elegidos)
    else:
        t = pd.read_csv(OUT / "tamizaje_modelos.csv", index_col=0)
        for m in t.index[t.elegido]:
            for var in VARS:
                bajar(c, m, mm[m], "historical", var, 1981, 2014)
                for e in EXP_ESC:
                    bajar(c, m, mm[m], e, var, 2015, 2100)
            print("  listo", m, flush=True)
