# Modelación hidrológica mensual y ENSO · cuenca del río Cauca hasta Hidroituango

Trabajo 2 de Hidrometeorología (Universidad Nacional de Colombia, sede Medellín). Continúa el
[Trabajo 1: balance hídrico de largo plazo](https://anajul1a4.github.io/balance-hidrico-hidroituango/).

**Sitio (presentación interactiva):** https://anajul1a4.github.io/hidroituango2/

## Qué hay

1. **Datos de entrada**
   - Precipitación mensual 1981–2023 de cinco productos en la grilla del Cubo de datos del IDEAM (0,1°): Cubo IDEAM, CHIRPS
     v2.0, CHIRPS v3.0, ERA5-Land y ERA5.
   - ERA5 y ERA5-Land corregidos por mapeo de cuantiles con el Cubo como referencia. En el Trabajo 1 ya se habían corregido
     con CHIRPS v2.0.
   - Evapotranspiración de referencia por FAO Penman-Monteith (el método de la Nota técnica IDEAM-METEO/003-2021, con el
     procedimiento de FAO-56 para datos faltantes) y por Hargreaves.
2. **Control de calidad del Cubo de datos del IDEAM.** El archivo diario (versión del 18-sep-2025) trae en la cuenca valores
   de hasta 4702 mm/día, y el mensual los suma. Se corrigen las celdas-día aisladas: más de 100 mm y más de 4 veces la mediana
   de sus 5 × 5 vecinas, o más de 500 mm. Cambia el 0,09 % de las celdas-día y la correlación mensual con CHIRPS pasa de 0,52
   a 0,96.
3. **Modelo abcd** (Thomas, 1981) semidistribuido.
   - Estructura: 10 unidades (áreas incrementales entre estaciones del cauce principal); cada celda tiene su propia lluvia y
     su propia ETo.
   - Calibración multisitio con 10 estaciones; KGE en 1982–2005, validación en 2006–2023.
   - Modelo final, regionalizado: a, c y d comunes y b por unidad, con el Cubo y la ETo de Hargreaves. KGE de validación:
     0,82 en promedio y 0,92 en la presa.
   - Comparación con el modelo agregado y con la ecuación empírica Q = α·(P − ETR) + β, sin y con memoria.
4. **ENSO**
   - Anomalías estandarizadas trimestrales (DEF, MAM, JJA, SON) de la precipitación (por producto), de la humedad del suelo
     simulada y de los caudales observados y simulados.
   - Compuestos El Niño y La Niña (fases del CPC sobre el ONI), consistencia entre productos y rezagos de la respuesta.

## Estructura

| Carpeta | Contenido |
|---|---|
| `docs/` | Sitio publicado en GitHub Pages (`index.html`, figuras en `img/`, Plotly en `assets/`). |
| `codigo/` | Scripts en orden: `00_limpieza_cubo.py`, `01_entradas.py`, `02_comparacion_productos.py`, `03_caudales_mensuales.py`, `04_modelo_abcd.py`, `04b_abcd_regionalizado.py`, `05_enso_precipitacion.py`, `06_enso_suelo_caudales.py`, `07_mapa_unidades.py`, `08_figuras_no_series.py`. |
| `codigo/sitio/` | Generador del sitio (`construir.py`), estilos y gráficas. El estilo de presentación es el de la presentación PAE Orinoquía–Amazonía. |
| `memorias/` | Resultados: tablas CSV, figuras en PNG de 300 dpi (mapas y gráficas que no son series, listas para el informe), parámetros, métricas y estados del modelo final (S, G, ETR y Q por celda). |
| `datos/` | Precipitación mensual del Cubo de datos IDEAM en la cuenca, tras el control de calidad. |

## Cómo reproducir

Los scripts esperan la estructura de carpetas del proyecto original:

- `HIDROITUANGO/trabajo1/`: resultados del Trabajo 1, es decir cuenca, áreas de drenaje, DEM, caudales diarios del IDEAM y ONI.
- `HIDROITUANGO/trabajo2/scripts/`: este código.
- `HIDROITUANGO/CUBO_IDEAM/`: archivos del Cubo de datos.

El Cubo de datos se descarga de https://bart.ideam.gov.co/meteorologia/DATOS/CUBO%20DE%20DATOS/. Se usan `prcp_dia_*.nc` (recortados
a la cuenca) y `tmax_`, `tmin_`, `tmed_` y `humd_mes_prom_1981_2023.nc`.

Python 3.13 con numpy, pandas, xarray, geopandas, rasterio, scipy, numba y matplotlib. Orden: 00 → 08 y luego
`python codigo/sitio/construir.py`.

## Fuentes de datos

- IDEAM: Cubo de datos (CDT, 1981–2023); caudales medios diarios (archivo nacional Hidrología Nacional Diaria).
- CHIRPS v2.0 y v3.0 (Climate Hazards Center, UCSB); ERA5 y ERA5-Land (ECMWF, Copernicus).
- ONI (NOAA Climate Prediction Center).
