"""
Trabajo 2 · operación de Hidroituango con pywr (modelo del Trabajo 1, scripts 34 y 41) alimentada con:

A. El pronóstico de años análogos emitido al final de octubre de 2026 (17_pronostico_2026.py): 15 trayectorias mensuales del aporte
   de noviembre de 2026 a abril de 2027. Cada una se lleva a escala diaria y a la escala de XM (como en 40_aportes_nino_2026.py):
       aporte diario = media histórica XM del mes × (pronóstico del mes / climatología IDEAM del mes) × (forma diaria del mes análogo)
   donde la forma diaria es Q diario / Q medio del mes que siguió al análogo. Estado inicial real (volumen útil y capacidad útil de
   XM), 1200 MW y 900 MW (disponibilidad real), tres políticas de operación y la ENFICC de XM, igual que en 41_pywr_nino_2026.py.

B. Las proyecciones CMIP6 (13_cmip6_qdm_abcd.py): para cada modelo, escenario y periodo de 30 años, serie diaria con la secuencia
   mensual del modelo y la forma diaria de 1981–2010:
       Q diario futuro = Qobs_clim(m) × Qsim(año futuro i, m) / Qsim_clim_1981–2010(m) × Q diario(año 1980 + i) / Qobs(año 1980 + i, m)
   Se simula con la central completa (8 unidades, 2400 MW), caudal mínimo de 450 m³/s y curva guía del 50 % (34_pywr_hidroituango.py),
   y se compara con 1981–2010 del mismo modelo pasado por la misma transformación.

Se ejecuta con trabajo1/.venv_pywr. Salidas: trabajo2/resultados/13_pywr/
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from pywr.model import Model  # noqa: E402
from pywr.nodes import Catchment, Link, Output, Storage  # noqa: E402
from pywr.parameters import ArrayIndexedParameter, ConstantParameter, ControlCurveParameter, MonthlyProfileParameter  # noqa: E402
from pywr.recorders import NumpyArrayNodeRecorder, NumpyArrayStorageRecorder  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
T1, R2 = ROOT / "trabajo1", ROOT / "trabajo2" / "resultados"
XM = T1 / "datos" / "xm"
OUT = R2 / "13_pywr"; OUT.mkdir(exist_ok=True)
FIG = R2 / "07_figuras"
D = 86400 / 1e6
V_DIS, COTA_MIN, COTA_MAX = 900.0, 390.0, 420.0
Q_UNIDAD, P_UNIDAD, H_DIS = 168.8, 300.0, 197.3
ETA = P_UNIDAD * 1e6 / (1000 * 9.81 * Q_UNIDAD * H_DIS)
ROJO, AZUL, NEGRO, GRIS, AMBAR, NARANJA = "#b91c1c", "#1d4ed8", "#1f2328", "#9aa3b2", "#b07a0c", "#ea580c"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "axes.grid.axis": "y",
                     "grid.color": "#d9d9d9", "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False})


def xm(nom):
    x = pd.read_csv(XM / f"{nom}.csv", parse_dates=["Date"]).drop_duplicates("Date", keep="last").set_index("Date").sort_index()
    return x.Value.astype(float)


def simular(q, curva, mw, v_util, v0, q_min=None):
    """curva: 12 valores (fracción del volumen útil). Por debajo de la curva se turbina el aporte del día (o el caudal mínimo)."""
    n = mw / P_UNIDAD
    m = Model(start=q.index[0], end=q.index[-1])
    ap = Catchment(m, "aporte", flow=ArrayIndexedParameter(m, (q * D).values))
    emb = Storage(m, "embalse", max_volume=v_util, min_volume=0.0, initial_volume=v0, initial_volume_pc=v0 / v_util, cost=-1.0)
    qmax = n * Q_UNIDAD
    bajo = np.minimum(q.values, qmax) if q_min is None else np.full(len(q), min(q_min, qmax))
    turb = Link(m, "turbinas", cost=-100.0,
                max_flow=ControlCurveParameter(m, emb, [MonthlyProfileParameter(m, curva)],
                                               parameters=[ConstantParameter(m, qmax * D), ArrayIndexedParameter(m, bajo * D)]))
    vert = Link(m, "vertedero", cost=50.0)
    rio = Output(m, "cauca_aguas_abajo")
    ap.connect(emb); emb.connect(turb); emb.connect(vert); turb.connect(rio); vert.connect(rio)
    r_t, r_v, r_s = NumpyArrayNodeRecorder(m, turb), NumpyArrayNodeRecorder(m, vert), NumpyArrayStorageRecorder(m, emb)
    m.run()
    qt, qv, v = r_t.data[:, 0] / D, r_v.data[:, 0] / D, r_s.data[:, 0]
    c = COTA_MIN + (COTA_MAX - COTA_MIN) * np.clip(v, 0, V_DIS) / V_DIS
    p = np.minimum(ETA * 1000 * 9.81 * (H_DIS + c - (COTA_MIN + COTA_MAX) / 2) * qt / 1e6, mw)
    return pd.DataFrame({"Q_aporte": q.values, "Q_turbinado": qt, "Q_vertido": qv, "V_util_hm3": v, "energia_GWh": p * 24 / 1000},
                        index=q.index)


qd = pd.read_csv(T1 / "resultados" / "20_nino_2026" / "aportes_presa_1959_2026.csv", index_col=0, parse_dates=True)["Q_presa_m3s"]
qd = qd[qd.index.year <= 2017]

# ============================================================================================ A. pronóstico nov 2026 – abr 2027
P26 = R2 / "12_pronostico_2026"
s26 = json.loads((P26 / "sitio.json").read_text(encoding="utf-8"))
an = pd.read_csv(P26 / "analogos.csv")
ens, clim = np.array(s26["ens"], dtype=float), np.array(s26["clim"])
_med = np.nanmedian(ens, 0)
ens = np.where(np.isnan(ens), _med[None, :], ens)    # mes del análogo sin caudal observado: mediana de los demás análogos
mh = xm("aportes_caudal_mediahist_ituango").resample("MS").mean()
mh_mes = mh.groupby(mh.index.month).mean()
vol, cap, enf = xm("volumen_util_ituango_m3").dropna() / 1e6, xm("capacidad_util_ituango_m3").dropna() / 1e6, xm("enficc_ituango_kwh") / 1e6
V0, V_UTIL, ENFICC = float(vol.iloc[-1]), float(cap.iloc[-1]), float(enf[enf > 0].iloc[-1])
print(f"estado inicial {vol.index[-1].date()}: {V0:.0f} de {V_UTIL:.0f} hm³ útiles; ENFICC {ENFICC:.2f} GWh/día")
fechas = pd.date_range("2026-11-01", "2027-04-30")
meses_t = pd.date_range("2026-11-01", periods=6, freq="MS")
E = {}
for j, a in enumerate(pd.to_datetime(an["mes análogo"])):
    serie = []
    for h, tm in enumerate(meses_t, start=1):
        ma = a + pd.DateOffset(months=h)
        dd = qd[ma: ma + pd.offsets.MonthEnd(0)].dropna()
        forma = (dd / dd.mean()).values if len(dd) >= 10 else np.ones(10)     # mes sin datos diarios: forma plana
        nd = tm.days_in_month
        forma = np.interp(np.linspace(0, 1, nd), np.linspace(0, 1, len(forma)), forma)
        serie.append(mh_mes[tm.month] * ens[j, h - 1] / clim[h - 1] * forma)
    E[an["mes análogo"][j]] = np.concatenate(serie)
E = pd.DataFrame(E, index=fechas)
E.round(1).to_csv(OUT / "escenarios_knn_nov2026_abr2027.csv", encoding="utf-8-sig")
POL = {"Generar al máximo": [0.0] * 12, "Curva guía 50 %": [0.5] * 12,
       "Reservar para feb–abr": [0.95, 0.60, 0.30, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.95, 0.95]}
filas = []
for mw in [1200, 900]:
    for pol, curva in POL.items():
        for esc in E.columns:
            s = simular(E[esc], curva, mw, V_UTIL, V0)
            falta = np.clip(ENFICC - s.energia_GWh, 0, None)
            filas.append({"MW": mw, "política": pol, "análogo": esc, "Aporte medio XM (m³/s)": s.Q_aporte.mean(),
                          "Energía nov–abr (GWh)": s.energia_GWh.sum(), "Energía feb–abr (GWh)": s.energia_GWh["2027-02":"2027-04"].sum(),
                          "Días bajo la ENFICC": int((falta > 0.01).sum()), "Faltante ENFICC (GWh)": falta.sum(),
                          "Volumen útil mínimo (hm³)": s.V_util_hm3.min()})
RA = pd.DataFrame(filas)
RA.round(2).to_csv(OUT / "pronostico_energia_por_analogo.csv", index=False, encoding="utf-8-sig")
qs = lambda c: RA.groupby(["MW", "política"])[c].quantile([0.1, 0.5, 0.9]).unstack()  # noqa: E731
resA = pd.concat({c: qs(c) for c in ["Energía nov–abr (GWh)", "Energía feb–abr (GWh)", "Días bajo la ENFICC", "Faltante ENFICC (GWh)"]}, axis=1)
resA.columns = [f"{a} p{int(100 * b)}" for a, b in resA.columns]
resA.round(1).to_csv(OUT / "pronostico_energia_resumen.csv", encoding="utf-8-sig")
pd.set_option("display.width", 260); pd.set_option("display.max_columns", 30)
print(resA.round(0).to_string())
print("ENFICC nov–abr total:", round(ENFICC * len(fechas)), "GWh")

# ============================================================================================ B. proyecciones CMIP6
CM = R2 / "11_cmip6"
tam = pd.read_csv(CM / "tamizaje_modelos.csv", index_col=0)
MOD = list(tam.index[tam.elegido])
ESC = {"ssp245": "SSP2-4.5", "ssp585": "SSP5-8.5"}
PER = {"1981–2010": 1981, "2021–2050": 2021, "2041–2070": 2041, "2071–2100": 2071}
qb = pd.read_csv(T1 / "resultados" / "18_pywr" / "aportes_presa_diarios_1981_2010.csv", index_col=0, parse_dates=True)["Q_presa_m3s"]
qb_m = qb.resample("MS").mean()
qobs_clim = qb_m.groupby(qb_m.index.month).mean()
filasB = []
for mo in MOD:
    for e in ESC:
        qs_ = pd.read_csv(CM / f"Q_{mo}_{e}.csv", index_col=0, parse_dates=True)["Presa"]
        cl = qs_["1981":"2010"].groupby(qs_["1981":"2010"].index.month).mean()
        for per, y0 in PER.items():
            fac = []
            for d in qb.index:
                yf = y0 + (d.year - 1981)
                fac.append(qs_[pd.Timestamp(yf, d.month, 1)] / cl[d.month])
            fac = np.array(fac)
            qm_ = qb_m.reindex(qb.index.to_period("M").to_timestamp()).values
            qf = pd.Series(qobs_clim.reindex(qb.index.month).values * fac * qb.values / qm_, index=qb.index)
            s = simular(qf, [0.5] * 12, 2400, V_DIS, V_DIS, q_min=450.0)
            an_ = s.energia_GWh.resample("YS").sum()
            filasB.append({"modelo": mo, "escenario": ESC[e], "periodo": per, "Aporte medio (m³/s)": qf.mean(),
                           "Energía media (GWh/año)": an_.mean(), "Energía anual excedida 95 % (GWh/año)": an_.quantile(0.05),
                           "Energía dic–abr (GWh/año)": s.energia_GWh[s.index.month.isin([12, 1, 2, 3, 4])].sum() / 30,
                           "Agua vertida (%)": 100 * s.Q_vertido.sum() / s.Q_aporte.sum(),
                           "Días bajo la curva guía (%)": 100 * (s.V_util_hm3 < 0.5 * V_DIS).mean()})
        print("  ", mo, e, flush=True)
RB = pd.DataFrame(filasB)
base = RB[RB.periodo == "1981–2010"].set_index(["modelo", "escenario"])
for c in ["Energía media (GWh/año)", "Energía anual excedida 95 % (GWh/año)", "Energía dic–abr (GWh/año)"]:
    RB[f"Δ {c.split(' (')[0]} (%)"] = [100 * (r[c] / base.loc[(r.modelo, r.escenario), c] - 1) for _, r in RB.iterrows()]
RB.round(2).to_csv(OUT / "proyecciones_energia_por_modelo.csv", index=False, encoding="utf-8-sig")
dcols = [c for c in RB.columns if c.startswith("Δ")]
fut = RB[RB.periodo != "1981–2010"]
resB = pd.concat({"mediana": fut.groupby(["escenario", "periodo"])[dcols].median(), "mínimo": fut.groupby(["escenario", "periodo"])[dcols].min(),
                  "máximo": fut.groupby(["escenario", "periodo"])[dcols].max()}, axis=1)
resB.round(1).to_csv(OUT / "proyecciones_energia_conjunto.csv", encoding="utf-8-sig")
print(resB.round(1).to_string())
print("Energía media 1981–2010 (mediana de modelos):", round(base["Energía media (GWh/año)"].median()), "GWh/año")

# ============================================================================================ figura (300 dpi)
fig, axs = plt.subplots(1, 2, figsize=(14, 4.6), gridspec_kw={"width_ratios": [1, 1.25]})
ax = axs[0]
r12 = RA[RA.MW == 1200]
pols = list(POL)
for i, pol in enumerate(pols):
    v = r12[r12["política"] == pol]["Energía nov–abr (GWh)"].values
    ax.boxplot(v, positions=[i], widths=0.5, patch_artist=True, boxprops=dict(facecolor=[GRIS, AMBAR, AZUL][i], alpha=0.35),
               medianprops=dict(color=NEGRO, lw=2), whis=(10, 90), showfliers=False)
    ax.scatter(np.full(len(v), i) + np.random.default_rng(1).uniform(-0.12, 0.12, len(v)), v, s=12, color=NEGRO, zorder=3)
ax.axhline(ENFICC * len(fechas), color=ROJO, lw=1.2, ls="--")
ax.text(2.45, ENFICC * len(fechas), "ENFICC nov–abr", color=ROJO, fontsize=8.5, va="bottom", ha="right")
ax.set_xticks(range(3), pols, fontsize=9); ax.set_ylabel("Energía generada nov 2026 – abr 2027 (GWh)")
ax.set_title("a) Pronóstico: 15 análogos, 4 unidades (1200 MW), estado real del embalse", fontsize=10, loc="left")
ax = axs[1]
x = np.arange(3); wb = 0.36
for k, (e, c) in enumerate([("SSP2-4.5", AMBAR), ("SSP5-8.5", ROJO)]):
    for jj, (col, hatch, lab) in enumerate([("Δ Energía media (%)", None, "energía media"), ("Δ Energía anual excedida 95 % (%)", "///", "energía del año seco (5 %)")]):
        pos = x + (k - 0.5) * wb + (jj - 0.5) * wb / 2
        d = fut[fut.escenario == e]
        med = d.groupby("periodo")[col].median().reindex(list(PER)[1:])
        ax.bar(pos, med, wb / 2, color=c if hatch is None else "white", edgecolor=c, hatch=hatch, lw=1, label=f"{e} · {lab}")
        for p_i, per in enumerate(list(PER)[1:]):
            vv = d[d.periodo == per][col].values
            ax.plot([pos[p_i]] * 2, [vv.min(), vv.max()], color=NEGRO, lw=0.8)
ax.axhline(0, color="#555", lw=0.8)
ax.set_xticks(x, list(PER)[1:]); ax.set_ylabel("Cambio frente a 1981–2010 (%)")
ax.legend(fontsize=8, ncol=2, loc="lower left")
ax.set_title("b) Proyecciones: central completa (2400 MW); barra = mediana, línea = rango de 6 modelos", fontsize=10, loc="left")
fig.tight_layout()
fig.savefig(FIG / "fig_pywr_energia.png", dpi=300, bbox_inches="tight", facecolor="white"); plt.close(fig)
json.dump({"V0": V0, "V_UTIL": V_UTIL, "ENFICC_dia": ENFICC, "ENFICC_nov_abr": ENFICC * len(fechas), "fecha_estado": str(vol.index[-1].date()),
           "E_base_mediana": float(base["Energía media (GWh/año)"].median())},
          open(OUT / "resumen.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
