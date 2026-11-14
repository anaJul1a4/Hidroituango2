"""
Trabajo 2 · figura: unidades de los modelos abcd y GR2M distribuidos (áreas incrementales), estaciones de calibración multisitio y grilla
de 0,1° del Cubo de datos IDEAM.

Salida: trabajo2/resultados/07_figuras/mapa_unidades.png
"""
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from shapely.geometry import box  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
T1 = ROOT / "trabajo1" / "resultados"
ENT = ROOT / "trabajo2" / "resultados" / "01_entradas"
OUT = ROOT / "trabajo2" / "resultados" / "07_figuras"
OUT.mkdir(parents=True, exist_ok=True)

U = gpd.read_file(ENT / "unidades.gpkg").to_crs(4326)
est = gpd.read_file(T1 / "06_caudales" / "subcuencas_estaciones.gpkg", layer="estaciones").to_crs(4326)
est = est[est.codigo.isin([c for c in U.unidad])]
cel = pd.read_csv(ENT / "grilla_celdas.csv")
g = gpd.GeoSeries([box(r.lon - 0.05, r.lat - 0.05, r.lon + 0.05, r.lat + 0.05) for r in cel.itertuples()], crs=4326)
# colores alternos claros (sin verdes ni morados): beige, azul claro, naranja claro, gris
pal = ["#f3e3c3", "#cfe2f3", "#f9cfa8", "#e3e3e3"]
fig, ax = plt.subplots(figsize=(5.2, 9))
U = U.reset_index(drop=True)
U.plot(ax=ax, color=[pal[k % 4] for k in range(len(U))], edgecolor="k", lw=0.6)
g.boundary.plot(ax=ax, color="#888", lw=0.15)
for r in U.itertuples():
    p = r.geometry.representative_point()
    ax.annotate(f"{r.salida}\n{r.area_km2:,.0f} km²".replace(",", " "), (p.x, p.y), fontsize=7, ha="center", va="center")
est.plot(ax=ax, color="#1d4ed8", markersize=28, edgecolor="white", zorder=5)
ax.plot([], [], "o", color="#1d4ed8", label="estación de calibración")
ax.set_xlabel("Longitud (°)"); ax.set_ylabel("Latitud (°)"); ax.set_aspect("equal")
ax.legend(loc="lower right", fontsize=8)
ax.set_title("Unidades de los modelos abcd y GR2M distribuidos\n(áreas incrementales entre estaciones; grilla del Cubo de 0,1°)", fontsize=10)
fig.tight_layout()
fig.savefig(OUT / "mapa_unidades.png", dpi=300)
