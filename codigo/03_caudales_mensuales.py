"""
Trabajo 2 · numeral 1c: caudales medios mensuales observados en las estaciones del cauce principal (calibración multisitio).

Fuente: caudales medios diarios del IDEAM (archivo nacional HidrologiaNacionalDiaria, 12-ago-2026; Trabajo 1). Un mes se acepta
con al menos 80 % de días con dato. Cierre (presa): Puerto Valdivia × 35 992/37 267 hasta 2017; desde 2018 Puerto Valdivia mide el
caudal regulado que sale de la presa y no se usa.

Salida: trabajo2/resultados/03_caudales/Q_mensual_estaciones.csv (m³/s), disponibilidad.csv
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
QD = ROOT / "trabajo1" / "datos" / "caudales_ideam" / "q_media_diaria"
OUT = ROOT / "trabajo2" / "resultados" / "03_caudales"
OUT.mkdir(parents=True, exist_ok=True)
EST = {"26027010": "La Balsa", "26067010": "Juanchito", "26107070": "La Victoria", "26177030": "La Virginia", "26167070": "Irra",
       "26187110": "La Pintada", "26207030": "Puente Iglesias", "26207080": "Bolombolo", "26217050": "Cañafisto",
       "26237040": "Puerto Valdivia"}
IDX = pd.date_range("1981-01-01", "2023-12-01", freq="MS")

Q = {}
for c in EST:
    d = pd.read_csv(QD / f"Q_MEDIA_D@{c}.data", sep="|")
    s = d.Valor.astype(float).groupby(pd.DatetimeIndex(pd.to_datetime(d.Fecha)).normalize()).mean()
    s = s.reindex(pd.date_range("1981-01-01", "2023-12-31"))
    m, n = s.resample("MS").mean(), s.resample("MS").count() / s.resample("MS").size()
    Q[c] = m.where(n >= 0.8).reindex(IDX)
Q = pd.DataFrame(Q)
Q["PRESA"] = (Q["26237040"] * 35991.8 / 37267.0).where(Q.index < "2018-01-01")
Q.index.name = "mes"
Q.round(2).to_csv(OUT / "Q_mensual_estaciones.csv", encoding="utf-8-sig")
disp = pd.DataFrame({"estación": [EST.get(c, "Presa (Pto. Valdivia transferido)") for c in Q],
                     "% meses 1981–2005": [100 * Q[c]["1981":"2005"].notna().mean() for c in Q],
                     "% meses 2006–2023": [100 * Q[c]["2006":"2023"].notna().mean() for c in Q],
                     "Q medio 1981–2010 (m³/s)": [Q[c]["1981":"2010"].mean() for c in Q]}, index=Q.columns)
disp.round(1).to_csv(OUT / "disponibilidad.csv", encoding="utf-8-sig")
print(disp.round(0).to_string())
