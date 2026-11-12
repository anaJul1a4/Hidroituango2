"""
Trabajo 2 · control de calidad de la precipitación del Cubo de datos del IDEAM.

Problema: el Cubo (NetCDF unificado, versión del 18-sep-2025) trae en la cuenca valores diarios imposibles, de hasta 4702 mm/día,
concentrados en la temporada seca (dic–feb). El archivo mensual es la suma de esos días, así que hereda el error: en enero de 1995 la
media de la cuenca sale en 781 mm (CHIRPS: 60 mm) y el ciclo anual muestra enero y febrero tan lluviosos como octubre.

Corrección (por celda y día): se marca como errónea la lluvia diaria que supera 100 mm y además es más de 4 veces la mediana de las
5 × 5 celdas vecinas ese día (un «ojo de buey» aislado), o que supera 500 mm (por encima de los máximos diarios registrados en la
región andina). El valor marcado se reemplaza por esa mediana. Luego se suman los meses.

Entradas: CUBO_IDEAM/diario_cuenca/prcp_dia_*.nc (recorte 1,6–8,0 °N, 77,4–74,6 °O de los archivos diarios del IDEAM)
Salidas: CUBO_IDEAM/prcp_mes_limpio_cuenca_1981_2023.nc, trabajo2/resultados/00_limpieza_cubo/marcados_por_mes.csv
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy.ndimage import median_filter

ROOT = Path(__file__).resolve().parents[2]
CUBO = ROOT / "CUBO_IDEAM"
OUT = ROOT / "trabajo2" / "resultados" / "00_limpieza_cubo"
OUT.mkdir(parents=True, exist_ok=True)
UMBRAL, VECES, TOPE = 100.0, 4.0, 500.0

d = xr.open_mfdataset(sorted(glob.glob(str(CUBO / "diario_cuenca" / "prcp_dia_*.nc")))).precip.load()
a = d.values.astype("float32")
med = median_filter(np.nan_to_num(a, nan=0), size=(1, 5, 5), mode="nearest")
malo = ((a > UMBRAL) & (a > VECES * np.maximum(med, 5))) | (a > TOPE)
limpio = xr.DataArray(np.where(malo, med, a), coords=d.coords, dims=d.dims, name="prcp")
limpio.attrs = {"units": "mm/mes", "fuente": "Cubo de datos IDEAM (CDT), diario sumado por mes tras el control de calidad",
                "control": f">{UMBRAL:.0f} mm y >{VECES:.0f}× la mediana 5×5, o >{TOPE:.0f} mm → mediana 5×5"}
mes = limpio.resample(time="MS").sum(min_count=1)
mes.attrs = limpio.attrs
mes.to_netcdf(CUBO / "prcp_mes_limpio_cuenca_1981_2023.nc")

m = xr.DataArray(malo, coords=d.coords, dims=d.dims)
r = pd.DataFrame({"celdas-día marcadas": m.resample(time="MS").sum().sum(("lat", "lon")).values,
                  "lluvia retirada (mm, suma de celdas)": xr.DataArray(np.where(malo, a - med, 0), coords=d.coords, dims=d.dims)
                  .resample(time="MS").sum().sum(("lat", "lon")).values}, index=pd.DatetimeIndex(mes.time.values))
r.index.name = "mes"
r.to_csv(OUT / "marcados_por_mes.csv", encoding="utf-8-sig")
print(f"celdas-día marcadas: {malo.sum()} de {np.isfinite(a).sum()} ({100 * malo.mean():.3f} %)")
print(r.groupby(r.index.month)["celdas-día marcadas"].sum().rename("por mes calendario").to_string())
