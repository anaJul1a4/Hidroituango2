/* ───────── navegación (de la presentación PAE) ───────── */
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
const TR = ["DEF", "MAM", "JJA", "SON"];

$("#themeTg").addEventListener("click", () => {
  const d = document.documentElement, dark = (d.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark";
  d.dataset.theme = dark ? "light" : "dark";
  try { localStorage.setItem("theme", d.dataset.theme); } catch (e) {}
  etiquetaTema(); redibujar();
});
function etiquetaTema() {
  const d = document.documentElement, dark = (d.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark";
  $("#themeTg .tlbl").textContent = dark ? "Modo claro" : "Modo oscuro";
}
etiquetaTema();
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { etiquetaTema(); redibujar(); });

const slides = $$(".slide"), dots = $("#dots"), main = $("#main");
let cur = 0;
slides.forEach((s, i) => {
  const b = document.createElement("button"); b.className = "g" + (s.dataset.g || "");
  b.setAttribute("aria-label", "Diapositiva " + (i + 1) + ": " + ((s.querySelector("h1,h2") || {}).textContent || ""));
  b.onclick = () => go(i); dots.appendChild(b);
});
function go(i) {
  cur = clamp(i, 0, slides.length - 1);
  slides.forEach((s, k) => s.classList.toggle("on", k === cur));
  [...dots.children].forEach((d, k) => d.classList.toggle("on", k === cur));
  $("#counter").textContent = (cur + 1) + " / " + slides.length;
  $("#secLabel").innerHTML = "<b>" + slides[cur].dataset.sec + "</b>";
  $$("nav.series .mod").forEach(m => {
    const t = document.getElementById(m.dataset.go);
    m.classList.toggle("on", !!t && t.dataset.sec === slides[cur].dataset.sec);
  });
  $("#prev").disabled = cur === 0; $("#next").disabled = cur === slides.length - 1;
  main.scrollTop = 0;
  dibujar(slides[cur].id);
  fitSlide();
  try { history.replaceState(null, "", "#" + slides[cur].id); } catch (e) {}
}
/* en pantallas anchas, una diapositiva más alta que la ventana se reduce hasta caber (nunca por debajo de 0,7) */
function fitSlide() {
  const sl = slides[cur]; sl.style.zoom = "";
  if (window.innerWidth < 900) return;
  const avail = main.clientHeight, need = sl.offsetHeight;
}
$("#prev").onclick = () => go(cur - 1); $("#next").onclick = () => go(cur + 1);
document.addEventListener("click", e => {
  const b = e.target.closest("[data-go]"); if (!b) return;
  const v = b.dataset.go; go(isNaN(+v) ? slides.indexOf(document.getElementById(v)) : +v);
});
document.addEventListener("keydown", e => {
  if (["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName) || e.metaKey || e.ctrlKey || e.altKey) return;
  if (["ArrowRight", "PageDown"].includes(e.key)) { e.preventDefault(); go(cur + 1); }
  if (["ArrowLeft", "PageUp"].includes(e.key)) { e.preventDefault(); go(cur - 1); }
  if (e.key === "Home") go(0); if (e.key === "End") go(slides.length - 1);
});
let tx = null, ty = null;
main.addEventListener("touchstart", e => { if (e.target.closest(".js-plotly-plot,.nosw")) { tx = null; return; } tx = e.touches[0].clientX; ty = e.touches[0].clientY; }, { passive: true });
main.addEventListener("touchend", e => {
  if (tx == null) return; const dx = e.changedTouches[0].clientX - tx, dy = e.changedTouches[0].clientY - ty;
  if (Math.abs(dx) > 70 && Math.abs(dx) > 2 * Math.abs(dy)) go(cur + (dx < 0 ? 1 : -1)); tx = null;
});

/* chips: botones de opción que redibujan su gráfica */
const ESTADO = {};
$$(".chips").forEach(g => {
  const bs = $$("button.chip", g);
  const on = bs.find(b => b.getAttribute("aria-pressed") === "true") || bs[0];
  ESTADO[g.id] = on.dataset.v; bs.forEach(b => b.setAttribute("aria-pressed", b === on ? "true" : "false"));
  bs.forEach(b => b.addEventListener("click", () => {
    bs.forEach(x => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
    ESTADO[g.id] = b.dataset.v; dibujar(slides[cur].id);
  }));
});

/* ───────── gráficas: estáticas (sin zoom ni arrastre), valores al pasar el cursor ───────── */
const CFG = { responsive: true, displayModeBar: false, scrollZoom: false, doubleClick: false, staticPlot: false };
const COL = { "Cubo IDEAM": () => css("--fg"), "IDEAM normales (kriging, Trabajo 1)": () => "#b07a0c", "CHIRPS v2.0": () => "#1d4ed8",
  "CHIRPS v3.0": () => "#9aa3b2", "ERA5-Land": () => "#ea580c", "ERA5": () => "#b91c1c", "ERA5-Land QM": () => "#ea580c", "ERA5 QM": () => "#b91c1c" };
function ax(t, extra) {
  return Object.assign({ title: { text: t, font: { size: 12, color: css("--muted") } }, gridcolor: css("--line"), linecolor: css("--line"),
    zeroline: false, tickfont: { size: 11, color: css("--muted"), family: css("--f-mono") }, fixedrange: true, automargin: true }, extra || {});
}
function lay(extra) {
  return Object.assign({ paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", dragmode: false,
    font: { family: css("--f-body"), color: css("--fg"), size: 12 }, margin: { l: 56, r: 14, t: 34, b: 44 },
    hoverlabel: { bgcolor: css("--bg"), bordercolor: css("--line"), font: { color: css("--fg"), size: 12 } },
    legend: { orientation: "h", x: 0, y: 1.02, yanchor: "bottom", font: { size: 11 }, itemclick: false, itemdoubleclick: false },
    showlegend: true }, extra || {});
}
const plot = (id, tr, L) => Plotly.react(id, tr, lay(L), CFG);
const linea = (nom, x, y, color, extra) => Object.assign({ type: "scatter", mode: "lines+markers", name: nom, x, y,
  line: { color, width: 2 }, marker: { size: 5, color }, hovertemplate: `${nom}: %{y:,.0f}<extra></extra>` }, extra || {});

const G = {
  "d-cubo"() {
    const q = D.qc, v = ESTADO.qcVista;
    if (v === "ciclo") plot("qcFig", [
      linea("Cubo original", MESES, q.orig, "#b91c1c", { line: { color: "#b91c1c", width: 2, dash: "dot" }, hovertemplate: "Cubo original · %{x}: %{y:.0f} mm<extra></extra>" }),
      linea("Cubo limpio", MESES, q.limpio, css("--fg"), { hovertemplate: "Cubo limpio · %{x}: %{y:.0f} mm<extra></extra>" }),
      linea("CHIRPS v2.0", MESES, q.chirps, "#1d4ed8", { hovertemplate: "CHIRPS v2.0 · %{x}: %{y:.0f} mm<extra></extra>" })],
      { xaxis: ax(""), yaxis: ax("Precipitación media de la cuenca, 1981–2010 (mm/mes)", { rangemode: "tozero" }), hovermode: "x unified" });
    if (v === "serie") plot("qcFig", [
      { type: "scatter", mode: "lines", name: "Cubo original", x: q.t, y: q.so, line: { color: "#b91c1c", width: 1.2 }, hovertemplate: "Cubo original: %{y:.0f} mm<extra></extra>" },
      { type: "scatter", mode: "lines", name: "Cubo limpio", x: q.t, y: q.sl, line: { color: css("--fg"), width: 1.4 }, hovertemplate: "Cubo limpio: %{y:.0f} mm<extra></extra>" },
      { type: "scatter", mode: "lines", name: "CHIRPS v2.0", x: q.t, y: q.sc, line: { color: "#1d4ed8", width: 1.2 }, hovertemplate: "CHIRPS v2.0: %{y:.0f} mm<extra></extra>" }],
      { xaxis: ax("", { type: "date" }), yaxis: ax("Precipitación mensual de la cuenca (mm)", { rangemode: "tozero" }), hovermode: "x unified" });
    $("#qcFig").hidden = v === "marc"; $("#qcImg").hidden = v !== "marc";
  },
  "d-ciclo"() {
    const g = { obs: ["IDEAM normales (kriging, Trabajo 1)", "Cubo IDEAM", "CHIRPS v2.0", "CHIRPS v3.0"], rea: ["Cubo IDEAM", "ERA5-Land", "ERA5"],
      qm: ["Cubo IDEAM", "ERA5-Land QM", "ERA5 QM", "CHIRPS v2.0"] }[ESTADO.ciclo];
    plot("cicloFig", g.filter(k => D.ciclo[k]).map(k => linea(k, MESES, D.ciclo[k], COL[k](), {
      line: { color: COL[k](), width: k === "Cubo IDEAM" ? 2.8 : 2, dash: k.endsWith("QM") ? "dash" : "solid" },
      hovertemplate: `${k} · %{x}: %{y:.0f} mm<extra></extra>` })),
      { xaxis: ax(""), yaxis: ax("Precipitación media mensual de la cuenca, 1981–2010 (mm)", { rangemode: "tozero" }) });
  },
  "d-eto"() {
    plot("etoFig", [
      { type: "bar", name: "P (Cubo)", x: MESES, y: D.eto.p, marker: { color: "rgba(29,78,216,.25)" }, hovertemplate: "P · %{x}: %{y:.0f} mm<extra></extra>" },
      linea("ETo Penman-Monteith", MESES, D.eto.pm, "#ea580c", { hovertemplate: "ETo PM · %{x}: %{y:.0f} mm<extra></extra>" }),
      linea("ETo Hargreaves", MESES, D.eto.hg, "#b91c1c", { line: { color: "#b91c1c", width: 2, dash: "dash" }, hovertemplate: "ETo Hargreaves · %{x}: %{y:.0f} mm<extra></extra>" })],
      { xaxis: ax(""), yaxis: ax("Media de la cuenca, 1981–2010 (mm/mes)", { rangemode: "tozero" }) });
  },

  "m-serie"() {
    const e = ESTADO.serieEst, s = D.serie;
    plot("serieFig", [
      { type: "scatter", mode: "lines", name: "Observado", x: s.t, y: s.obs[e], line: { color: css("--fg"), width: 1.6 }, connectgaps: false, hovertemplate: "Observado: %{y:,.0f} m³/s<extra></extra>" },
      { type: "scatter", mode: "lines", name: "Simulado (abcd)", x: s.t, y: s.sim[e], line: { color: "#ea580c", width: 1.6 }, hovertemplate: "Simulado: %{y:,.0f} m³/s<extra></extra>" }],
      { hovermode: "x unified", xaxis: ax("", { type: "date" }), yaxis: ax(`Caudal medio mensual en ${e} (m³/s)`, { rangemode: "tozero" }),
        shapes: [{ type: "rect", xref: "x", yref: "paper", x0: "1982-01", x1: "2005-12", y0: 0, y1: 1, fillcolor: css("--line"), opacity: .35, line: { width: 0 }, layer: "below" }] });
  },

  "p-mapas"() {
    const n = ESTADO.pMapa === "nino";
    $("#pMapaHost").hidden = !n; $("#pMapaHost2").hidden = n;
  },


  "s-memoria"() {
    const a = D.anom;
    plot("anomFig", [
      { type: "scatter", mode: "lines", name: "Lluvia", x: a.t, y: a.P, line: { color: "#60a5fa", width: 1.2 }, hovertemplate: "Lluvia: z %{y:+.2f}<extra></extra>" },
      { type: "scatter", mode: "lines", name: "Suelo (abcd)", x: a.t, y: a.S, line: { color: "#b07a0c", width: 1.8 }, hovertemplate: "Suelo: z %{y:+.2f}<extra></extra>" },
      { type: "scatter", mode: "lines", name: "Caudal en la presa", x: a.t, y: a.Q, line: { color: "#1d4ed8", width: 1.6 }, hovertemplate: "Caudal: z %{y:+.2f}<extra></extra>" },
      { type: "scatter", mode: "lines", name: "ONI (eje der.)", x: a.t, y: a.oni, yaxis: "y2", line: { color: "#b91c1c", width: 1.4, dash: "dot" }, hovertemplate: "ONI: %{y:+.2f} °C<extra></extra>" }],
      { hovermode: "x unified", xaxis: ax("", { type: "date" }), yaxis: ax("Anomalía estandarizada"),
        yaxis2: ax("ONI (°C)", { overlaying: "y", side: "right", showgrid: false, autorange: "reversed" }), margin: { l: 56, r: 56, t: 34, b: 40 } });
  },

  "q-ciclo"() {
    const e = ESTADO.cEst, d = D.cpf[e], t = [];
    const col = { "El Niño": "#b91c1c", "Neutro": "#9aa3b2", "La Niña": "#1d4ed8" };
    ["El Niño", "Neutro", "La Niña"].forEach(fa => {
      t.push(linea(`${fa} · observado`, MESES, d[fa].obs, col[fa], { hovertemplate: `${fa} · observado · %{x}: %{y:,.0f} m³/s<extra></extra>` }));
      t.push(linea(`${fa} · simulado`, MESES, d[fa].sim, col[fa], { line: { color: col[fa], width: 1.6, dash: "dot" }, marker: { size: 4, color: col[fa] }, hovertemplate: `${fa} · simulado · %{x}: %{y:,.0f} m³/s<extra></extra>` }));
    });
    plot("cFig", t, { xaxis: ax(""), yaxis: ax(`Caudal medio mensual en ${e} (m³/s)`, { rangemode: "tozero" }) });
  },
  "q-rez"() {
    const k = [0, 1, 2, 3, 4, 5, 6];
    const s = [["ONI → lluvia", D.rez.P, "#60a5fa", "solid"], ["ONI → suelo", D.rez.S, "#b07a0c", "solid"],
      ["ONI → caudal observado (presa)", D.rez["Q obs presa"], "#1d4ed8", "solid"], ["ONI → caudal simulado (presa)", D.rez["Q sim presa"], "#1d4ed8", "dot"]];
    plot("rezFig", s.map(([n, y, c, dsh]) => linea(n, k, y, c, { line: { color: c, width: 2, dash: dsh }, hovertemplate: `${n} · rezago %{x} meses: r = %{y:.2f}<extra></extra>` })),
      { xaxis: ax("Rezago (meses): la variable va detrás del ONI", { dtick: 1 }), yaxis: ax("Correlación con el ONI", { range: [-0.8, 0] }) });
  }
};
function dibujar(id) { if (G[id]) G[id](); }
function redibujar() { dibujar(slides[cur].id); }
let rt; window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { fitSlide(); redibujar(); }, 150); });
const ini = slides.findIndex(s => "#" + s.id === location.hash);
go(ini >= 0 ? ini : 0);
