"""
Trabajo 2 · proyecciones CMIP6 · paso 2: corrección por mapeo de cuantiles con deltas (QDM) y simulación con el modelo abcd final.

Para cada modelo elegido (12_cmip6_descarga.py) y escenario (SSP2-4.5, SSP5-8.5):
  1. Serie continua 1981–2100: historical (1981–2014) + escenario (2015–2100), interpolada bilinealmente a las 376 celdas del Cubo.
  2. QDM (Cannon et al., 2015), por celda y mes calendario, con el Cubo de 1981–2010 como observación y el modelo de 1981–2010 como
     su histórico. Para cada década objetivo se toma la ventana de 30 años centrada en ella (recortada a 1981–2100):
        τ = probabilidad de no excedencia del valor del modelo en su ventana,
        Δ = x / F_hist⁻¹(τ) (lluvia, multiplicativo) o x − F_hist⁻¹(τ) (temperaturas, aditivo),
        x corregido = F_obs⁻¹(τ) · Δ   o   F_obs⁻¹(τ) + Δ.
     Así el cambio que proyecta el modelo en cada cuantil se conserva, y la distribución de 1981–2010 queda igual a la del Cubo.
     Cuantiles empíricos con posiciones de Weibull; en la lluvia el denominador tiene un mínimo de 1 mm/mes y Δ un máximo de 5.
  3. ETo de Hargreaves con Tmax y Tmin corregidas (la del modelo final).
  4. Modelo abcd semidistribuido regionalizado con los parámetros calibrados (Cubo IDEAM, Hargreaves): Q en las 10 estaciones,
     humedad del suelo S, agua subterránea G y ETR.
Los cambios se miden siempre dentro de cada modelo: futuro frente a su propio 1981–2010 corregido y simulado.

Salidas: trabajo2/resultados/11_cmip6/ series_cuenca_<modelo>_<ssp>.csv, Q_<modelo>_<ssp>.csv, campos_<modelo>_<ssp>.nc (P y ETo
anual por celda y periodo)
"""
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[2]
src = (ROOT / "trabajo2" / "scripts" / "04_modelo_abcd.py").read_text(encoding="utf-8").split("grupos_dist = ")[0].replace("cache=True", "cache=False")
exec(compile(src, "04_base", "exec"))                     # abcd, piezas, cel, ORDEN, NOM, ENT …
R2 = ROOT / "trabajo2" / "resultados"
DATA = ROOT / "CMIP6"
OUT = R2 / "11_cmip6"
ESC = ["ssp245", "ssp585"]
REF = ("1981", "2010")
PERIODOS = {"1981–2010": ("1981", "2010"), "2021–2050": ("2021", "2050"), "2041–2070": ("2041", "2070"), "2071–2100": ("2071", "2100")}

tam = pd.read_csv(OUT / "tamizaje_modelos.csv", index_col=0)
MODELOS = list(tam.index[tam.elegido])
par = pd.read_csv(R2 / "04_abcd" / "regionalizado_parametros.csv")
p0 = par[(par.producto == "Cubo IDEAM") & (par.ETo == "Hargreaves")].iloc[0]
iu = np.array([ORDEN.index(u) for u in piezas.unidad])
aguas_abajo = [np.isin(iu, np.arange(k + 1)) for k in range(len(ORDEN))]
km2 = piezas.km2.values
bU = np.array([p0[f"b {NOM[u]}"] for u in ORDEN])
n = len(km2)
A, Bp, Cp, Dp = np.full(n, p0.a), bU[iu], np.full(n, p0.c), np.full(n, p0.d)

# observación (Cubo) en las celdas, 1981–2010
obsP = xr.open_dataarray(ENT / "P_Cubo_IDEAM.nc").sel(time=slice(*REF)).values
Tc = xr.open_dataset(ENT / "T_cubo.nc").sel(time=slice(*REF))
OBS = {"pr": obsP, "tasmax": Tc.tmax.values, "tasmin": Tc.tmin.values}
t_obs = pd.DatetimeIndex(Tc.time.values)
w_cu = cel.a_cuenca_km2.values


def celdas(da):
    v = da.interp(lat=xr.DataArray(cel.lat.values, dims="c"), lon=xr.DataArray(cel.lon.values, dims="c"))
    return pd.DatetimeIndex(da.time.values), v.values.astype(np.float64)


def cuantil(srt, tau):
    """srt: (m, c) valores ordenados por columna; tau: (k, c) → (k, c), interpolación lineal en posiciones de Weibull."""
    m = srt.shape[0]
    pos = np.clip(tau * (m + 1) - 1, 0, m - 1)
    lo = np.floor(pos).astype(int); hi = np.minimum(lo + 1, m - 1); fr = pos - lo
    return np.take_along_axis(srt, lo, 0) * (1 - fr) + np.take_along_axis(srt, hi, 0) * fr


def qdm(t, X, obs, mult):
    """t: tiempos 1981–2100; X: (T, c) modelo; obs: (360, c) Cubo 1981–2010 mensual. Devuelve X corregido (T, c)."""
    Y = np.full_like(X, np.nan)
    años, meses = t.year.values, t.month.values
    for mm in range(1, 13):
        io = t_obs.month == mm
        so = np.sort(obs[io], 0)
        ih = (meses == mm) & (años >= 1981) & (años <= 2010)
        sh = np.sort(X[ih], 0)
        for d0 in range(1981, 2101, 10):
            blk = (meses == mm) & (años >= d0) & (años <= d0 + 9)
            if not blk.any():
                continue
            if d0 <= 2001:                                        # 1981–2010: el histórico es su propia ventana
                w0, w1 = 1981, 2010
            else:
                w0 = min(max(d0 - 10, 1981), 2071); w1 = w0 + 29
            iw = (meses == mm) & (años >= w0) & (años <= w1)
            sw = np.sort(X[iw], 0)
            x = X[blk]
            nw = sw.shape[0]
            tau = (np.sum(sw[None, :, :] <= x[:, None, :], 1) - 0.5) / nw            # (k, c)
            tau = np.clip(tau, 1 / (nw + 1), nw / (nw + 1))
            qh = cuantil(sh, tau); qo = cuantil(so, tau)
            if mult:
                delta = np.minimum(x / np.maximum(qh, 1.0), 5.0)
                Y[blk] = qo * delta
            else:
                Y[blk] = qo + (x - qh)
    return Y


def hargreaves(t, tx, tn):
    dias = t.days_in_month.values[:, None]
    J = (t + pd.Timedelta(days=14)).dayofyear.values[:, None]
    phi = np.radians(cel.lat.values)[None, :]
    dr = 1 + 0.033 * np.cos(2 * np.pi * J / 365)
    dl = 0.409 * np.sin(2 * np.pi * J / 365 - 1.39)
    ws = np.arccos(-np.tan(phi) * np.tan(dl))
    Ra = 24 * 60 / np.pi * 0.0820 * dr * (ws * np.sin(phi) * np.sin(dl) + np.cos(phi) * np.cos(dl) * np.sin(ws))
    return 0.0023 * 0.408 * Ra * ((tx + tn) / 2 + 17.8) * np.sqrt(np.clip(tx - tn, 0.1, None)) * dias


def cuenca(X):
    return (X * w_cu[None, :]).sum(1) / w_cu.sum()


for m in MODELOS:
    for e in ESC:
        if (OUT / f"Q_{m}_{e}.csv").exists():
            print("ya existe", m, e); continue
        corr = {}
        for v in ["pr", "tasmax", "tasmin"]:
            th, xh = celdas(xr.open_dataarray(DATA / m / f"historical_{v}.nc"))
            tf, xf = celdas(xr.open_dataarray(DATA / m / f"{e}_{v}.nc"))
            t = th.append(tf)
            X = np.concatenate([xh, xf])
            corr[v] = qdm(t, X, OBS[v], mult=(v == "pr"))
            corr[v + "_crudo"] = X
        tx, tn = corr["tasmax"], corr["tasmin"]
        tx, tn = np.maximum(tx, tn + 0.1), np.minimum(tx, tn)
        E = hargreaves(t, tx, tn)
        Pp = np.ascontiguousarray(corr["pr"][:, piezas.i.values]); Ep = np.ascontiguousarray(E[:, piezas.i.values])
        segs = t.days_in_month.values * 86400.0
        q, S, G, ET = abcd(Pp, Ep, A, Bp, Cp, Dp)
        qm = q * km2[None, :] * 1e3 / segs[:, None]
        Q = pd.DataFrame({NOM[c]: qm[:, aguas_abajo[k]].sum(1) for k, c in enumerate(ORDEN)}, index=t)
        Q.round(2).to_csv(OUT / f"Q_{m}_{e}.csv", encoding="utf-8-sig")
        wp = km2 / km2.sum()
        sc = pd.DataFrame({"P": cuenca(corr["pr"]), "P cruda": cuenca(corr["pr_crudo"]), "Tmax": cuenca(tx), "Tmin": cuenca(tn),
                           "Tmax cruda": cuenca(corr["tasmax_crudo"]), "Tmin cruda": cuenca(corr["tasmin_crudo"]), "ETo": cuenca(E),
                           "S": (S * wp).sum(1), "G": (G * wp).sum(1), "ETR": (ET * wp).sum(1)}, index=t)
        sc.round(3).to_csv(OUT / f"series_cuenca_{m}_{e}.csv", encoding="utf-8-sig")
        # campos anuales medios por periodo (para mapas)
        anual = {}
        for nom, X in [("P", corr["pr"]), ("ETo", E), ("Tmed", (tx + tn) / 2)]:
            df = pd.DataFrame(X, index=t)
            for per, (a0, a1) in PERIODOS.items():
                d = df[a0:a1]
                anual[(nom, per)] = d.resample("YS").sum().mean().values if nom != "Tmed" else d.mean().values
                for tri, ms in {"DEF": [12, 1, 2], "MAM": [3, 4, 5], "JJA": [6, 7, 8], "SON": [9, 10, 11]}.items():
                    dd = d[d.index.month.isin(ms)]
                    anual[(nom + " " + tri, per)] = dd.groupby(dd.index.year).sum().mean().values if nom != "Tmed" else dd.mean().values
        vs = sorted({k[0] for k in anual}); ps = list(PERIODOS)
        xr.Dataset({v: (("periodo", "celda"), np.array([anual[(v, p)] for p in ps])) for v in vs},
                   coords={"periodo": ps, "celda": cel.index.values}).to_netcdf(OUT / f"campos_{m}_{e}.nc")
        print(f"{m:<16} {e}: P {sc.P['1981':'2010'].resample('YS').sum().mean():.0f} → {sc.P['2071':'2100'].resample('YS').sum().mean():.0f} mm/año; "
              f"Q presa {Q.Presa['1981':'2010'].mean():.0f} → {Q.Presa['2071':'2100'].mean():.0f} m³/s", flush=True)
