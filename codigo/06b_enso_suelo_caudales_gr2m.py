"""
Trabajo 2 · numerales 3 y 4 con el modelo GR2M (comparación con el abcd).

Corre exactamente el mismo análisis de 06_enso_suelo_caudales.py (compuestos ENSO de la humedad del suelo y de los caudales, ciclo
anual por fase, memoria y rezagos), pero con los estados y caudales del GR2M distribuido (04_modelo_gr2m.py) con la misma lluvia y ETo
del modelo principal. La humedad del suelo es el reservorio de producción S y el almacenamiento lento es el reservorio de enrutamiento R
(en las tablas conserva el nombre de columna «G» del abcd para que los dos análisis se lean igual).

Salidas: trabajo2/resultados/06_enso_suelo_Q_gr2m/
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
src = (ROOT / "trabajo2" / "scripts" / "06_enso_suelo_caudales.py").read_text(encoding="utf-8")
REP = [
    ('ENT, ABC, EP = R2 / "01_entradas", R2 / "04_abcd", R2 / "05_enso_P"',
     'ENT, ABC, EP = R2 / "01_entradas", R2 / "04_gr2m", R2 / "05_enso_P"'),
    ('OUT = R2 / "06_enso_suelo_Q"', 'OUT = R2 / "06_enso_suelo_Q_gr2m"'),
    ('fin = json.loads((ABC / "modelo_final.json").read_text(encoding="utf-8"))',
     'fin = json.loads((R2 / "04_abcd" / "modelo_final.json").read_text(encoding="utf-8"))'),
    ('st = xr.open_dataset(ABC / (f"estados_reg_{etq}.nc" if fin["tipo"] == "regionalizado" else f"estados_{mejor.replace(\' \', \'_\')}.nc"))',
     'st = xr.open_dataset(ABC / f"estados_{etq}.nc").rename({"R": "G"})'),
    ('qs = pd.read_csv(ABC / (f"Q_simulado_reg_{etq}.csv" if fin["tipo"] == "regionalizado" else f"Q_simulado_{mejor.replace(\' \', \'_\')}.csv")',
     'qs = pd.read_csv(ABC / f"Q_simulado_{etq}.csv"'),
    ("humedad del suelo S (abcd)", "humedad del suelo S (GR2M)"),
    ("Humedad del suelo simulada en trimestres El Niño y La Niña (", "Humedad del suelo simulada por el GR2M en trimestres El Niño y La Niña ("),
]
for a, b in REP:
    assert src.count(a) == 1, a[:70]
    src = src.replace(a, b)
exec(compile(src, "06_gr2m", "exec"))
