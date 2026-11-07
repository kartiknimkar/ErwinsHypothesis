/* Erwin's Hypothesis interface (vanilla JS, no build step).
 * Each analysis type is described in TYPES (data layout, options, request, results, graph). */
(() => {
  "use strict";

  // ======================================================================
  // helpers
  // ======================================================================
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const isNum = v => String(v ?? "").trim() !== "" && !isNaN(Number(String(v).trim()));
  const num = v => (isNum(v) ? Number(v) : null);
  const uid = () => Math.random().toString(36).slice(2, 10);
  const letter = i => String.fromCharCode(65 + (i % 26));

  function fmt(v, digits = 4) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    if (v === 0) return "0";
    const a = Math.abs(v);
    if (a >= 1e6 || a < 1e-4) return v.toExponential(2);
    return Number(v.toPrecision(digits)).toString();
  }
  function fmtP(p) {
    if (p === null || p === undefined) return "—";
    if (p < 0.0001) return "P < 0.0001";
    return "P = " + (p < 0.001 ? p.toFixed(4) : p < 0.01 ? p.toFixed(4) : p.toFixed(3));
  }
  const pOnly = p => fmtP(p).replace(/^P = /, "").replace(/^P < /, "< ");
  const stars = p => p < 0.0001 ? "****" : p < 0.001 ? "***" : p < 0.01 ? "**" : p < 0.05 ? "*" : "ns";
  const st = s => `<span class="st ${s === "ns" ? "ns" : ""}">${s}</span>`;
  const ci = (lo, hi) => (lo === null || lo === undefined) ? "—" : `${fmt(lo)} to ${fmt(hi)}`;

  // results table builder
  const T = {
    sec: t => `<tr class="sec"><td colspan="9">${t}</td></tr>`,
    row: (l, v, cls = "") => `<tr class="${cls}"><td>${l}</td><td>${v}</td></tr>`,
    table: rows => `<div class="tbl-wrap"><table class="res">${rows.join("")}</table></div>`,
    multi: (head, rows) => `<div class="tbl-wrap"><table class="res multi"><tr>${head.map(h => `<th>${h}</th>`).join("")}</tr>${rows.map(r => `<tr${r.cls ? ` class="${r.cls}"` : ""}>${(r.cells || r).map(c => `<td>${c}</td>`).join("")}</tr>`).join("")}</table></div>`,
    summary: (cls, html) => `<div class="summary ${cls}">${html}</div>`,
  };

  // ======================================================================
  // graph styling shared by all types
  // ======================================================================
  const PALETTES = {
    vivid: ["#2f5bea", "#e4572e", "#17a398", "#8b5cf6", "#f2a541", "#d6336c", "#2b9348", "#6c757d"],
    colorblind: ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"],
    classic: ["#000000", "#d62728", "#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b", "#7f7f7f"],
    pastel: ["#7aa6f0", "#f4a582", "#80cdc1", "#c2a5cf", "#fdd49e", "#f1b6da", "#a6d96a", "#bababa"],
    grayscale: ["#111111", "#666666", "#999999", "#444444", "#bbbbbb", "#222222", "#888888", "#555555"],
  };
  // a color picked by the user for a named series wins over the palette
  const color = (g, i, name) => (name != null && g.colors && g.colors[name]) || (PALETTES[g.palette] || PALETTES.vivid)[i % 8];
  const COMMON_GRAPH = {
    tickAngle: "auto", minorTicks: false, breakFrom: "", breakTo: "", breakSize: 35,
    fontFamily: "Arial", textColor: "#1b2130", titleSize: "", tickSize: "",
    pointSymbol: "default", pointOpacity: 0.85, pointLine: 1, pointLineColor: "#ffffff",
    lineScale: 1, errWidth: 1.5, capWidth: 9, barOpacity: "", barLine: 1.6, pattern: "none",
    axisWidth: 1.5, tickDir: "outside", tickLen: 5, grid: false, bg: "white", legendPos: "auto",
    pcaPlot: "biplot", pcaLabels: false, title: "", palette: "vivid", pointSize: 8, fontSize: 13, ymin: "", ymax: "", logY: false, exportSize: "15", exportDpi: "300" };
  // export sizes in inches (width x height); journals usually ask for 300-600 DPI
  const EXPORT_SIZES = { "1": [3.5, 2.8, "Single column (3.5 × 2.8 in)"], "15": [5.5, 4.2, "1.5 column (5.5 × 4.2 in)"],
    "2": [7.2, 5, "Double column (7.2 × 5 in)"], "slide": [10, 6.5, "Slide (10 × 6.5 in)"], "sq": [4, 4, "Square (4 × 4 in)"] };

  function axis(g, extra = {}) {
    return { showline: true, linewidth: 1.5, linecolor: "#1b2130", ticks: "outside", tickwidth: 1.5, ticklen: 5,
      showgrid: false, zeroline: false, automargin: true, ...extra };
  }
  function yAxis(g, titleText, extra = {}) {
    const a = axis(g, { title: { text: esc(titleText || "") }, ...extra });
    const cur = extra.range || [null, null];
    if (!g.logY && num(g.ytick) > 0) { a.dtick = num(g.ytick); a.tick0 = 0; }
    if (g.logY) { a.type = "log"; delete a.range; }
    const lo = num(g.ymin), hi = num(g.ymax);
    if (lo !== null || hi !== null) {
      const r = [lo ?? (g.logY ? null : cur[0]), hi ?? (g.logY ? null : cur[1])];
      if (r[0] !== null && r[1] !== null) a.range = g.logY ? r.map(v => Math.log10(Math.max(v, 1e-12))) : r;
      else { delete a.range; a.autorange = true; }
    }
    return a;
  }
  function baseLayout(g) {
    return {
      margin: { l: 60, r: 16, t: g.title ? 44 : 20, b: 52 },
      paper_bgcolor: "#fff", plot_bgcolor: "#fff", showlegend: false,
      font: { family: "-apple-system, Segoe UI, Helvetica, Arial, sans-serif", size: Number(g.fontSize) || 13, color: "#1b2130" },
      title: g.title ? { text: esc(g.title), font: { size: (Number(g.fontSize) || 13) + 3 } } : undefined,
    };
  }
  const PLOT_CONFIG = { displaylogo: false, responsive: true,
    // click titles, axis titles, legend entries and text labels on the graph to edit them; drag legend / labels to move
    edits: { titleText: true, axisTitleText: true, legendText: true, legendPosition: true, annotationText: true, annotationPosition: true },
    modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d", "toggleSpikelines"] };


  // ======================================================================
  // graph style pass: applies the Format panel's text / point / line / bar / axis settings
  // to every graph type, right before it is drawn
  // ======================================================================
  let styleCtx = null;
  const PATTERNS = ["/", "\\", "x", ".", "-", "|", "+"];
  function hexToRgba(c, a) {
    const m = /^#?([0-9a-f]{6})/i.exec(String(c || ""));
    if (!m) return c;
    const n = parseInt(m[1], 16);
    return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`;
  }
  const plainText = v => String(v ?? "").replace(/<br\s*\/?>/gi, " ").replace(/<[^>]*>/g, "").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
  // turn a vertical graph sideways: swap X/Y of every trace, shape and label, and list categories top to bottom
  function flipLayout(data, layout) {
    data.forEach(t => {
      [t.x, t.y] = [t.y, t.x];
      if (t.error_y) { t.error_x = t.error_y; delete t.error_y; }
      if (t.type === "bar" || t.type === "box" || t.type === "violin") t.orientation = "h";
      if (t.marker && t.marker.symbol === "line-ew") t.marker.symbol = "line-ns";
    });
    [layout.xaxis, layout.yaxis] = [layout.yaxis || {}, layout.xaxis || {}];
    if (layout.yaxis.tickvals && Array.isArray(layout.yaxis.range)) layout.yaxis.range = [...layout.yaxis.range].reverse();
    else if (layout.yaxis.tickvals || layout.yaxis.type === "category" || !layout.yaxis.type) layout.yaxis.autorange = layout.yaxis.range ? undefined : "reversed";
    (layout.shapes || []).forEach(sh => {
      if (sh.path) sh.path = sh.path.replace(/([MLHVZ])\s*(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)/g, "$1 $3 $2");
      [sh.x0, sh.y0, sh.x1, sh.y1, sh.xref, sh.yref] = [sh.y0, sh.x0, sh.y1, sh.x1, sh.yref, sh.xref];
    });
    (layout.annotations || []).forEach(a => {
      if (a.xref === "paper" || a.yref === "paper") return;
      [a.x, a.y] = [a.y, a.x];
      if (a.yanchor === "bottom") { delete a.yanchor; a.xanchor = "left"; a.xshift = 3; }
    });
  }
  // Y axis break: the plot is split into a lower part [bottom, from] and an upper part [to, top];
  // every trace is drawn on both, and labels/brackets above the break move to the upper part
  function breakYAxis(data, layout, g) {
    const from = num(g.breakFrom), to = num(g.breakTo);
    if (from === null || to === null || to <= from || g.logY) return;
    const ya = layout.yaxis || {};
    let lo = Array.isArray(ya.range) ? ya.range[0] : null, hi = Array.isArray(ya.range) ? ya.range[1] : null;
    if (lo === null || hi === null) {
      const ys = data.flatMap(t => (Array.isArray(t.y) ? t.y : []).map((v, i) => Number(v) + ((t.error_y && t.error_y.array && t.error_y.array[i]) || 0))).filter(Number.isFinite);
      if (!ys.length) return;
      lo = lo ?? Math.min(0, ...ys); hi = hi ?? Math.max(...ys) * 1.05;
    }
    if (!(from > lo && to < hi)) return;
    const frac = Math.min(0.8, Math.max(0.15, (Number(g.breakSize) || 35) / 100)), gap = 0.035;
    layout.yaxis = { ...ya, range: [lo, from], domain: [0, frac], autorange: false, title: { text: "" } };
    if (layout.yaxis.dtick === undefined && num(g.ytick) === null) layout.yaxis.nticks = 3;
    layout.yaxis2 = { ...ya, range: [to, hi], domain: [frac + gap, 1], autorange: false, anchor: "x" };
    const extra = data.map(t => ({ ...t, yaxis: "y2", showlegend: false }));
    data.push(...extra);
    (layout.shapes || []).forEach(sh => {
      const ys = sh.path ? [...sh.path.matchAll(/[ML]\s*-?[\d.eE+-]+\s+(-?[\d.eE+-]+)/g)].map(m => Number(m[1])) : [sh.y0, sh.y1];
      if (sh.yref !== "paper" && ys.every(v => v >= to)) sh.yref = "y2";
    });
    (layout.annotations || []).forEach(a => { if (a.yref !== "paper" && a.y >= to) a.yref = "y2"; });
    // the break marks: two short slanted lines across the axis
    const c = g.textColor || "#1b2130", w = Number(g.axisWidth) || 1.5;
    layout.shapes = [...(layout.shapes || []),
      ...[frac, frac + gap].map(y => ({ type: "line", xref: "paper", yref: "paper", x0: -0.018, x1: 0.018, y0: y - 0.012, y1: y + 0.012, line: { color: c, width: w } }))];
  }
  function applyStyle(data, layout, g) {
    if (!g) return;
    if (g.horizontal && layout.meta === "flippable") flipLayout(data, layout);
    const ls = Number(g.lineScale) || 1, family = `${g.fontFamily || "Arial"}, Helvetica, Arial, sans-serif`;
    layout.font = { ...(layout.font || {}), family, color: g.textColor || "#1b2130" };
    if (layout.title && layout.title.font) layout.title.font.family = family;
    Object.keys(layout).filter(k => /^[xy]axis\d*$/.test(k)).forEach(k => {
      const a = layout[k];
      if (a.showline) {
        a.linewidth = Number(g.axisWidth); a.tickwidth = Number(g.axisWidth); a.linecolor = g.textColor;
        a.ticks = g.tickDir === "none" ? "" : g.tickDir; a.ticklen = Number(g.tickLen); a.tickcolor = g.textColor;
      }
      if (g.grid) { a.showgrid = true; a.gridcolor = "#e3e6eb"; a.gridwidth = 1; }
      if (num(g.tickSize)) a.tickfont = { ...(a.tickfont || {}), size: num(g.tickSize) };
      if (num(g.titleSize) && a.title) a.title = { ...(typeof a.title === "object" ? a.title : { text: a.title }), font: { size: num(g.titleSize) } };
    });
    if (g.bg === "transparent") { layout.paper_bgcolor = "rgba(0,0,0,0)"; layout.plot_bgcolor = "rgba(0,0,0,0)"; }
    else if (g.bg === "light") { layout.paper_bgcolor = "#ffffff"; layout.plot_bgcolor = "#f4f5f7"; }
    const pos = { tr: { x: 1, xanchor: "right", y: 1, orientation: "v" }, tl: { x: 0.02, xanchor: "left", y: 1, orientation: "v" },
      outside: { x: 1.02, xanchor: "left", y: 1, orientation: "v" }, top: { x: 0, y: 1.12, orientation: "h" }, bottom: { x: 0, y: -0.22, orientation: "h" } }[g.legendPos];
    if (pos && layout.showlegend) layout.legend = { ...(layout.legend || {}), ...pos, bgcolor: "rgba(255,255,255,0)" };
    if (g.legendPos === "outside" && layout.showlegend) layout.margin = { ...(layout.margin || {}), r: 130 };
    if (g.legendPos === "hide" || g.legend === "hide") layout.showlegend = false;
    if (g.legendXY && layout.showlegend) layout.legend = { ...(layout.legend || {}), ...g.legendXY };
    if (layout.xaxis && g.tickAngle !== undefined && g.tickAngle !== "auto") layout.xaxis.tickangle = Number(g.tickAngle);
    if (g.minorTicks) Object.keys(layout).filter(k => /^[xy]axis\d*$/.test(k)).forEach(k => {
      const a = layout[k];
      if (a.showline && a.type !== "category" && !a.tickvals) a.minor = { ticks: g.tickDir === "none" ? "" : g.tickDir, ticklen: Math.max(2, Number(g.tickLen) / 2), tickwidth: Number(g.axisWidth) * 0.7, tickcolor: g.textColor };
    });
    if (!g.horizontal && layout.meta === "flippable") breakYAxis(data, layout, g);
    // text edited directly on the graph
    Object.entries(g.axisText || {}).forEach(([k, v]) => { if (layout[k]) layout[k].title = { ...(typeof layout[k].title === "object" ? layout[k].title : {}), text: esc(v) }; });
    data.forEach(t => {
      if (t.name == null) return;
      if (t.meta == null) t.meta = plainText(t.name);
      const nn = (g.legendNames || {})[t.meta];
      if (nn != null) t.name = esc(nn);
    });
    layout.annotations = [...(layout.annotations || []), ...(g.notes || []).map(n => ({ text: esc(n.text || " "), x: n.x ?? 0.5, y: n.y ?? 0.95,
      xref: "paper", yref: "paper", showarrow: false, font: { size: Number(n.size) || (Number(g.fontSize) || 13) } }))];
    (layout.shapes || []).forEach(sh => { if (sh.line && sh.line.width) sh.line.width *= ls; });
    let barIdx = 0;
    data.forEach(t => {
      const mk = t.marker;
      if (t.line && t.line.width) t.line = { ...t.line, width: t.line.width * ls };
      if (t.error_y) t.error_y = { ...t.error_y, thickness: Number(g.errWidth), width: Number(g.capWidth) };
      if (mk && (t.type === "scatter" || !t.type) && /markers/.test(t.mode || "")) {
        const special = mk.symbol && mk.symbol !== "circle";
        if (!special) {
          if (g.pointSymbol && g.pointSymbol !== "default") mk.symbol = g.pointSymbol;
          mk.opacity = Number(g.pointOpacity);
          mk.line = { ...(mk.line || {}), width: Number(g.pointLine), color: g.pointLineColor };
        } else if (mk.line && mk.line.width) mk.line = { ...mk.line, width: mk.line.width * ls };
      }
      if ((t.type === "box" || t.type === "violin") && mk) mk.opacity = Number(g.pointOpacity);
      if (t.type === "bar" && mk) {
        const isHex = c => typeof c === "string" && /^#[0-9a-f]{6}/i.test(c);
        const base = isHex(mk.line && mk.line.color) ? mk.line.color.slice(0, 7) : isHex(mk.color) ? mk.color.slice(0, 7) : null;
        if (g.barOpacity !== "" && g.barOpacity != null && base) mk.color = hexToRgba(base, Number(g.barOpacity));
        mk.line = { ...(mk.line || {}), width: Number(g.barLine), color: (mk.line && mk.line.color) || base || "#1b2130" };
        if (g.pattern && g.pattern !== "none") mk.pattern = { shape: g.pattern === "vary" ? PATTERNS[barIdx % PATTERNS.length] : g.pattern,
          fgcolor: base || "#1b2130", size: 7, solidity: 0.28, fillmode: "overlay" };
        barIdx++;
      }
    });
  }
  function styledReact(el, data, layout, config) {
    const g = styleCtx;
    applyStyle(data, layout, g);
    el._ehG = g;
    el._ehNote0 = (layout.annotations || []).length - ((g && g.notes) || []).length;
    const p = Plotly.react(el, data, layout, config);
    Promise.resolve(p).then(() => wireGraphEdits(el));
    return p;
  }
  // keep edits made directly on the graph (titles, legend text/position, text labels)
  function wireGraphEdits(el) {
    // Plotly can rebuild the plot (dropping listeners), so re-attach after every draw
    if (!el.on) return;
    if (el._ehHandlers && el.removeListener) { el.removeListener("plotly_relayout", el._ehHandlers[0]); el.removeListener("plotly_restyle", el._ehHandlers[1]); }
    const done = () => { save(); if (el.id === "plot" && !$("graph-format").hidden) renderFormat(); };
    const onRelayout = ev => {
      const g = el._ehG; if (!g || !ev) return;
      let changed = false;
      Object.entries(ev).forEach(([k, v]) => {
        if (k === "title.text") { g.title = plainText(v); changed = true; return; }
        let m = /^([xy]axis\d*)\.title\.text$/.exec(k);
        if (m) { g.axisText = { ...(g.axisText || {}), [m[1]]: plainText(v) }; changed = true; return; }
        if (k === "legend.x" || k === "legend.y") { g.legendXY = { ...(g.legendXY || {}), [k.slice(7)]: v }; changed = true; return; }
        m = /^annotations\[(\d+)\]\.(text|x|y)$/.exec(k);
        if (m) {
          const i = Number(m[1]) - el._ehNote0;
          if (g.notes && i >= 0 && g.notes[i]) { g.notes[i][m[2]] = m[2] === "text" ? plainText(v) : v; changed = true; }
        }
      });
      if (changed) done();
    };
    const onRestyle = ev => {
      const g = el._ehG; if (!g || !ev || !ev[0] || !("name" in ev[0])) return;
      const names = ev[0].name, idx = ev[1] || [];
      idx.forEach((ti, n) => {
        const t = el.data[ti]; if (!t) return;
        g.legendNames = { ...(g.legendNames || {}), [t.meta ?? ""]: plainText(Array.isArray(names) ? names[n] : names) };
      });
      done();
    };
    el.on("plotly_relayout", onRelayout); el.on("plotly_restyle", onRestyle);
    el._ehHandlers = [onRelayout, onRestyle];
  }

  // ======================================================================
  // analysis types
  // ======================================================================
  // test choices by [number of groups][design]
  const CHOICES = {
    "2i": [["welch", "Welch's t test", "Spread may differ between groups. Safe default."],
      ["unpaired", "Unpaired t test", "Assumes both groups have similar spread."],
      ["mannwhitney", "Mann-Whitney test", "Nonparametric: compares ranks, no normality needed."]],
    "2r": [["paired", "Paired t test", "Each row is one subject measured in both columns."],
      ["wilcoxon", "Wilcoxon signed-rank test", "Nonparametric paired test."]],
    "3i": [["ordinary", "One-way ANOVA", "Compares all means, then each pair (Tukey) or each group vs control (Dunnett). Choose below."],
      ["welch", "Welch's ANOVA + Games-Howell", "When the groups' spreads differ."],
      ["kruskal", "Kruskal-Wallis + Dunn's", "Nonparametric: compares ranks, no normality needed."]],
    "3r": [["rm", "Repeated-measures ANOVA + Tukey", "Each row is one subject measured in every column. Geisser-Greenhouse corrected."],
      ["friedman", "Friedman test + Dunn's", "Nonparametric repeated measures."]],
  };
  function postHocOptions(s, kind) {
    const to = s.options.compareTo || "all", ph = s.options.posthoc || "tukey";
    const methods = to === "control"
      ? [["dunnett", "Dunnett (recommended)"], ["holm", "Holm-Šídák"], ["sidak", "Šídák"], ["bonferroni", "Bonferroni"], ["lsd", "Fisher's LSD (no correction)"]]
      : [["tukey", "Tukey (recommended)"], ["holm", "Holm-Šídák"], ["sidak", "Šídák"], ["bonferroni", "Bonferroni"], ["lsd", "Fisher's LSD (no correction)"]];
    return `<div class="row"><label for="opt-cmpto">Compare</label><select id="opt-cmpto"><option value="all" ${to === "all" ? "selected" : ""}>every pair of groups</option>
      <option value="control" ${to === "control" ? "selected" : ""}>each group with the first column (control)</option></select>
      ${kind === "ordinary" ? `<label for="opt-posthoc">Correction</label><select id="opt-posthoc">${methods.map(([v, l]) => `<option value="${v}" ${ph === v ? "selected" : ""}>${l}</option>`).join("")}</select>` : `<span class="pd">Dunn's test</span>`}</div>`;
  }
  const choiceKey = (s, n) => `${n >= 3 ? 3 : 2}${s.options.design === "repeated" ? "r" : "i"}`;
  const kindFor = (s, n) => { const key = choiceKey(s, n); const k = s.options["kind" + key]; return CHOICES[key].some(c => c[0] === k) ? k : CHOICES[key][0][0]; };
  let MODELS = [
    { id: "dr_inhibit", name: "Dose-response: inhibition (IC50)", log_x: true, equation: "Y = Bottom + (Top − Bottom) / (1 + 10^((LogIC50 − X)·HillSlope))" },
    { id: "dr_stim", name: "Dose-response: stimulation (EC50)", log_x: true, equation: "Y = Bottom + (Top − Bottom) / (1 + 10^((LogEC50 − X)·HillSlope))" },
    { id: "michaelis", name: "Michaelis-Menten (enzyme kinetics)", log_x: false, equation: "Y = Vmax·X / (Km + X)" },
    { id: "exp_decay", name: "Exponential decay (one phase)", log_x: false, equation: "Y = (Y0 − Plateau)·exp(−K·X) + Plateau" },
    { id: "exp_growth", name: "Exponential growth", log_x: false, equation: "Y = Y0·exp(K·X)" },
    { id: "assoc", name: "One-phase association", log_x: false, equation: "Y = Y0 + (Plateau − Y0)·(1 − exp(−K·X))" },
  ];
  const modelInfo = id => MODELS.find(m => m.id === id);

  const TYPES = {
    // ---------------------------------------------------------------- groups
    ttest: {
      label: "Compare groups", newTitle: "Group comparison",
      minCols: 2, maxCols: 12, fixedCols: 0, textCol: -1, addLabel: "+ Group", minRows: 15,
      colKind: j => `Group ${letter(j)}`, newColName: j => `Group ${letter(j)}`,
      hint: "One column per group, one value per cell. Paste straight from Excel. Click a column name to rename it.",
      cols: ["Control", "Treated"],
      options: { design: "independent", alpha: 0.05 },
      graph: { ylabel: "Response", style: "dots", err: "sd", brackets: "sig", showPoints: true },
      examples: s => s.options.mode === "freq" ? {
        cols: ["Wild type", "Knockout"],
        rows: [[12.1, 14.3], [13.2, 15.8], [11.9, 16.4], [13.7, 15.2], [12.8, 17.2], [14.9, 16.1], [13.1, 15.5], [12.4, 18.3],
          [14.1, 14.7], [13.9, 16.8], [10.8, 15.6], [14.6, 14.8], [13.4, 15.3], [12.9, 17.9], [13.6, 16.3], [14.4, 15.1],
          [11.5, 19.2], [13.8, 16.6], [12.6, 15.9], [15.0, 17.4], [13.3, 14.9], [14.2, 16.0], [12.2, 18.8], [13.0, 15.7],
          [11.2, 16.9], [13.5, 20.4], [14.0, 15.4], [12.7, 17.0], [13.2, 16.2], [15.4, 19.7]],
      } : s.cols.length >= 3 ? {
        cols: ["Vehicle", "Drug 10 µM", "Drug 50 µM"],
        rows: [[10.2, 13.4, 18.2], [11.5, 14.8, 17.1], [9.8, 12.9, 19.5], [12.1, 15.2, 16.8], [10.9, 14.1, 18.9], [11.3, 13.7, 17.6]],
      } : {
        cols: ["Control", "Treated"],
        rows: [[4.2, 6.1], [5.1, 7.3], [3.8, 6.8], [4.9, 5.9], [5.5, 7.9], [4.4, 6.5], [4.0, 7.0], [5.2, 6.2]],
      },
      request(s) {
        const groups = s.cols.map((_, j) => s.data.map(r => num(r[j]))), names = s.cols.map((c, j) => c || `Group ${letter(j)}`);
        if (s.options.mode === "freq") return ["/api/freq", { groups, names, y: s.options.freqY || "count", cumulative: !!s.options.cumulative,
          bin_width: isNum(s.options.binWidth) ? Number(s.options.binWidth) : null, bin_start: isNum(s.options.binStart) ? Number(s.options.binStart) : null }];
        if (s.options.mode === "describe") return ["/api/colstats", { groups, names, alpha: s.options.alpha,
          hypothetical: isNum(s.options.hypothetical) ? Number(s.options.hypothetical) : null }];
        return ["/api/compare", { groups, names, kind: kindFor(s, filledCols(s).length), alpha: s.options.alpha, outliers: !!s.options.outliers,
          posthoc: s.options.posthoc || "tukey", compare_to: s.options.compareTo || "all",
          outlier_method: s.options.outlierMethod || "rout", q: Number(s.options.routQ ?? 0.01) }];
      },
      renderOptions(s) {
        const n = filledCols(s).length, key = choiceKey(s, n), cur = kindFor(s, n);
        const rep = s.options.design === "repeated";
        const md = s.options.mode || "compare";
        const modeSeg = `<div class="seg"><button data-set="mode:compare" class="${md === "compare" ? "on" : ""}">Compare the groups</button><button data-set="mode:describe" class="${md === "describe" ? "on" : ""}">Describe each column</button><button data-set="mode:freq" class="${md === "freq" ? "on" : ""}">Distribution</button></div>`;
        if (md === "freq") {
          const fy = s.options.freqY || "count";
          return modeSeg + `<p class="hint">Histogram (frequency distribution) of each column, with a normal Q-Q plot and normality tests to check whether the values look normally distributed. Choose the plot under <b>Format</b>.</p>
          <div class="opt-label">Show on Y</div><div class="seg">${[["count", "Number of values"], ["percent", "Percent"], ["fraction", "Fraction"]].map(([k, l]) => `<button data-set="freqY:${k}" class="${fy === k ? "on" : ""}">${l}</button>`).join("")}</div>
          <label class="check"><input type="checkbox" data-opt="cumulative" ${s.options.cumulative ? "checked" : ""}> Cumulative (running total)</label>
          <div class="row"><label for="opt-binw">Bin width</label><input type="text" id="opt-binw" data-num="binWidth" value="${esc(s.options.binWidth ?? "")}" placeholder="auto" style="width:80px" inputmode="decimal">
          <label for="opt-bins">First bin starts at</label><input type="text" id="opt-bins" data-num="binStart" value="${esc(s.options.binStart ?? "")}" placeholder="auto" style="width:80px" inputmode="decimal"></div>`;
        }
        if (s.options.mode === "describe") return modeSeg + `<p class="hint">Full descriptive statistics and normality tests for each column. Optionally test whether each column's mean (and median) differs from a hypothetical value.</p>
          <div class="row"><label for="opt-hyp">Compare with hypothetical value</label><input type="text" id="opt-hyp" value="${esc(s.options.hypothetical ?? "")}" placeholder="none" style="width:80px" inputmode="decimal"></div>${alphaSelect(s)}`;
        return modeSeg + `<div class="seg"><button data-design="independent" class="${rep ? "" : "on"}">Different subjects in each group</button><button data-design="repeated" class="${rep ? "on" : ""}">Same subjects (each row = one subject)</button></div>
          <div class="opt-label">${n >= 3 ? `${n} groups: compare all` : "2 groups"}</div>` +
          CHOICES[key].map(([k, name, d]) => `<label class="choice ${cur === k ? "on" : ""}"><input type="radio" name="kind${key}" value="${k}" ${cur === k ? "checked" : ""}><span><b>${name}</b><small>${d}</small></span></label>`).join("") +
          (n >= 3 ? "" : `<p class="hint">Have 3 or more groups? Click <b>+ Group</b> to add a column.</p>`) +
          (n >= 3 && (cur === "ordinary" || cur === "kruskal") ? postHocOptions(s, cur) : "") +
          `<div class="row"><label class="check"><input type="checkbox" data-opt="outliers" ${s.options.outliers ? "checked" : ""}> Identify outliers</label>
          ${s.options.outliers ? `<select id="opt-outmethod"><option value="rout" ${(s.options.outlierMethod || "rout") === "rout" ? "selected" : ""}>ROUT (finds one or several)</option><option value="grubbs" ${s.options.outlierMethod === "grubbs" ? "selected" : ""}>Grubbs' test (α = 0.05)</option></select>
            ${(s.options.outlierMethod || "rout") === "rout" ? `<label for="opt-routq">Q</label>` + `<select id="opt-routq">${[["0.001", "0.1%"], ["0.01", "1% (recommended)"], ["0.05", "5%"], ["0.1", "10%"]].map(([v, l]) => `<option value="${v}" ${String(s.options.routQ ?? "0.01") === v ? "selected" : ""}>${l}</option>`).join("")}</select>` : ""}` : ""}</div>` + alphaSelect(s);
      },
      graphControls: s => s.options.mode === "freq" ? [
        sel("freqPlot", "Plot", [["hist", "Histogram (bars)"], ["poly", "Frequency polygon (lines)"], ["qq", "Normal Q-Q plot"]]),
        sel("freqBars", "Several columns", [["overlay", "Overlapping"], ["group", "Side by side"], ["stack", "Stacked"]]),
        chk("normalCurve", "Show normal curve"), txt("xlabel", "Values axis label"),
      ] : [
        sel("style", "Style", [["dots", "Dots + mean"], ["bars", "Bars + dots"], ["box", "Box plot"], ["violin", "Violin plot"],
          ...(s.options.design === "repeated" ? [["lines", "Before-after (connect subjects)"]] : [])]),
        sel("err", "Error bars", [["sd", "Mean ± SD"], ["sem", "Mean ± SEM"], ["ci95", "Mean ± 95% CI"], ["none", "None"]]),
        sel("brackets", "Significance", [["sig", "Significant pairs"], ["all", "All pairs"], ["none", "Hide"]]),
        txt("ylabel", "Y axis label"), chk("showPoints", "Show points"), chk("horizontal", "Horizontal (sideways)"),
      ],
      renderResults: (r, s) => r.kind === "freq" ? renderFreq(r) : r.kind === "describe" ? renderColStats(r) : renderGroupResults(r, s),
      draw: drawGroups,
    },
    // ---------------------------------------------------------------- nested (subjects with replicates)
    nested: {
      label: "Nested (subjects with replicates)", newTitle: "Nested",
      minCols: 3, maxCols: 13, fixedCols: 1, textCol: 0, addLabel: "+ Replicate", minRows: 15,
      colKind: j => j === 0 ? "Group" : `Rep ${j}`, newColName: j => `Rep ${j}`,
      hint: "One row per subject (e.g. one animal or one culture): its group name in the first column, then its replicate measurements (e.g. several cells) to the right. Repeat the group name for every subject in that group.",
      cols: ["Group", "Rep 1", "Rep 2", "Rep 3"],
      options: { alpha: 0.05 },
      graph: { ylabel: "Response", err: "sd", brackets: "sig", showPoints: true },
      examples: () => ({
        cols: ["Group", "Cell 1", "Cell 2", "Cell 3", "Cell 4", "Cell 5"],
        rows: [["Control", 10.2, 11.1, 9.6, 10.8, ""], ["Control", 12.4, 11.9, 13.1, "", ""], ["Control", 9.1, 9.9, 8.7, 9.5, 10.0], ["Control", 11.3, 10.6, 11.8, 11.0, ""],
          ["Drug A", 13.8, 14.6, 13.1, 14.0, ""], ["Drug A", 12.2, 12.9, 13.5, "", ""], ["Drug A", 15.1, 14.4, 15.8, 14.9, 15.3], ["Drug A", 13.0, 13.7, 12.6, 13.3, ""],
          ["Drug B", 11.5, 12.0, 11.1, 12.4, ""], ["Drug B", 13.2, 12.7, 13.6, "", ""], ["Drug B", 10.8, 11.4, 10.5, 11.0, 11.7], ["Drug B", 12.1, 11.6, 12.6, 12.3, ""]],
      }),
      request: s => {
        const rows = s.data.filter(r => String(r[0] ?? "").trim() !== "" && r.slice(1).some(isNum));
        return ["/api/nested", { groups: rows.map(r => String(r[0]).trim()), values: rows.map(r => r.slice(1).map(num).filter(v => v !== null)), alpha: s.options.alpha }];
      },
      renderOptions: s => `<p class="hint">Each subject's replicates are <b>not</b> independent, so treating every cell as its own data point would exaggerate the evidence. The nested test (a mixed-effects model) compares the groups using the variation <b>between subjects</b>, while still using every replicate.</p>${alphaSelect(s)}`,
      graphControls: () => [
        sel("err", "Error bars", [["sd", "Mean ± SD of subject means"], ["sem", "Mean ± SEM (model)"], ["none", "None"]]),
        sel("brackets", "Significance", [["sig", "Significant pairs"], ["all", "All pairs"], ["none", "Hide"]]),
        txt("ylabel", "Y axis label"), chk("showPoints", "Show every replicate"), chk("horizontal", "Horizontal (sideways)"),
      ],
      renderResults: (r, s) => renderNested(r, s),
      draw: drawNested,
    },
    // ---------------------------------------------------------------- summary data
    summary: {
      label: "Compare groups (mean, SD, n)", newTitle: "Summary data",
      minCols: 4, maxCols: 4, fixedCols: 4, textCol: 0, addLabel: "", minRows: 8,
      colKind: (j, s) => ["Group", "Mean", (s && s.options.err === "sem") ? "SEM" : "SD", "n"][j], newColName: () => "",
      hint: "One row per group: its name, mean, SD (or SEM) and number of values (n). Use this when you only have summary numbers, e.g. from a paper.",
      cols: ["Group", "Mean", "SD", "n"],
      options: { err: "sd", kind2: "welch", kind3: "ordinary", alpha: 0.05 },
      graph: { ylabel: "Response", style: "bars", err: "sd", brackets: "sig", showPoints: false },
      examples: () => ({ cols: ["Group", "Mean", "SD", "n"], rows: [["Control", 4.6, 0.6, 8], ["Drug A", 6.7, 0.7, 8], ["Drug B", 5.2, 0.9, 7]] }),
      request(s) {
        const rows = s.data.filter(r => isNum(r[1]) && isNum(r[2]) && isNum(r[3]));
        const n = rows.length;
        return ["/api/summary", { groups: rows.map((r, i) => ({ name: String(r[0] || `Group ${i + 1}`), mean: Number(r[1]), sd: Number(r[2]), n: Number(r[3]) })),
          err: s.options.err, kind: n >= 3 ? s.options.kind3 : s.options.kind2, alpha: s.options.alpha,
          posthoc: s.options.posthoc || "tukey", compare_to: s.options.compareTo || "all" }];
      },
      renderOptions(s) {
        const n = s.data.filter(r => isNum(r[1]) && isNum(r[2]) && isNum(r[3])).length;
        const list = n >= 3 ? [["ordinary", "One-way ANOVA", "Compares all means, then each pair (Tukey) or each group vs control (Dunnett)."], ["welch", "Welch's ANOVA + Games-Howell", "When the groups' spreads differ."]]
          : [["welch", "Welch's t test", "Spread may differ between groups. Safe default."], ["unpaired", "Unpaired t test", "Assumes both groups have similar spread."]];
        const key = n >= 3 ? "kind3" : "kind2";
        return `<div class="seg"><button data-set="err:sd" class="${s.options.err !== "sem" ? "on" : ""}">Second column is SD</button><button data-set="err:sem" class="${s.options.err === "sem" ? "on" : ""}">Second column is SEM</button></div>
          <div class="opt-label">${n >= 3 ? `${n} groups` : "2 groups"}</div>` +
          list.map(([k, name, d]) => `<label class="choice ${s.options[key] === k ? "on" : ""}"><input type="radio" name="${key}" value="${k}" ${s.options[key] === k ? "checked" : ""}><span><b>${name}</b><small>${d}</small></span></label>`).join("") +
          (n >= 3 && (s.options.kind3 || "ordinary") === "ordinary" ? postHocOptions(s, "ordinary") : "") +
          `<p class="hint">These tests are exact from summary data. Paired, nonparametric and normality tests need the individual values.</p>${alphaSelect(s)}`;
      },
      graphControls: () => [
        sel("style", "Style", [["bars", "Bars"], ["dots", "Mean only"]]),
        sel("err", "Error bars", [["sd", "Mean ± SD"], ["sem", "Mean ± SEM"], ["ci95", "Mean ± 95% CI"], ["none", "None"]]),
        sel("brackets", "Significance", [["sig", "Significant pairs"], ["all", "All pairs"], ["none", "Hide"]]), txt("ylabel", "Y axis label"), chk("horizontal", "Horizontal (sideways)"),
      ],
      renderResults: (r, s) => renderGroupResults(r, s) + `<p class="note">Computed from summary data (mean, ${s.options.err === "sem" ? "SEM" : "SD"}, n).</p>`,
      draw: drawGroups,
    },
    // ---------------------------------------------------------------- two-way
    twoway: {
      label: "Grouped (two factors)", newTitle: "Grouped",
      minCols: 3, maxCols: 12, fixedCols: 1, textCol: 0, addLabel: "+ Group", minRows: 15,
      colKind: j => j === 0 ? "Row factor" : `Group ${letter(j - 1)}`, newColName: j => `Group ${letter(j - 1)}`,
      hint: "Two factors, e.g. treatment (columns) × sex or time (rows). Type the row name in the first column. For replicates, add more rows with the same name.",
      cols: ["Sex", "Vehicle", "Drug"],
      options: { alpha: 0.05 },
      graph: { ylabel: "Response", style: "bars", err: "sd", brackets: "sig", showPoints: true },
      examples: s => s.options.rm && s.options.analysis !== "multit" ? {
        cols: ["Day", "Vehicle", "Drug"],
        rows: [["0", 10.2, 10.4], ["0", 9.8, 9.9], ["0", 10.5, 10.1], ["0", 10.0, 10.6], ["7", 11.1, 12.3], ["7", 10.9, 11.8], ["7", 11.6, 12.0], ["7", 10.8, 12.9],
          ["14", 12.0, 14.6], ["14", 11.7, 14.1], ["14", 12.5, 13.8], ["14", 11.6, 15.2], ["21", 12.8, 17.3], ["21", 12.4, 16.5], ["21", 13.3, 16.9], ["21", 12.2, 18.0]],
      } : s.options.analysis === "multit" ? {
        cols: ["Gene", "Wild type", "Knockout"],
        rows: [["Il6", 1.0, 3.9], ["Il6", 1.2, 4.4], ["Il6", 0.9, 3.6], ["Tnf", 2.1, 2.3], ["Tnf", 1.9, 2.0], ["Tnf", 2.2, 2.6],
          ["Ccl2", 0.8, 2.4], ["Ccl2", 1.1, 2.9], ["Ccl2", 0.9, 2.1], ["Actb", 10.2, 10.0], ["Actb", 9.8, 10.4], ["Actb", 10.1, 9.9],
          ["Il10", 0.5, 0.4], ["Il10", 0.6, 0.7], ["Il10", 0.4, 0.5], ["Cxcl1", 1.4, 2.6], ["Cxcl1", 1.6, 3.1], ["Cxcl1", 1.3, 2.8]],
      } : ({
        cols: ["Sex", "Vehicle", "Low dose", "High dose"],
        rows: [["Male", 5.1, 6.9, 8.2], ["Male", 4.8, 7.4, 8.8], ["Male", 5.5, 7.1, 8.5], ["Male", 5.0, 6.6, 8.9],
          ["Female", 6.0, 7.0, 7.1], ["Female", 6.3, 7.7, 7.6], ["Female", 5.8, 7.2, 7.9], ["Female", 6.1, 7.5, 7.4]],
      }),
      request(s) {
        const body = { rows: s.data.map(r => String(r[0] || "").trim()), columns: s.cols.slice(1).map((_, j) => s.data.map(r => num(r[j + 1]))),
          names: s.cols.slice(1).map((c, j) => c || `Group ${letter(j)}`), alpha: s.options.alpha };
        if (s.options.analysis === "multit") return ["/api/multit", { ...body, kind: s.options.mtKind || "welch", q: s.options.q || 0.05 }];
        return ["/api/twoway", { ...body, rm: !!s.options.rm, compare: s.options.twCompare || "within_rows" }];
      },
      renderOptions: s => `<div class="seg"><button data-set="analysis:anova" class="${s.options.analysis !== "multit" ? "on" : ""}">Two-way ANOVA</button><button data-set="analysis:multit" class="${s.options.analysis === "multit" ? "on" : ""}">Multiple t tests (one per row name)</button></div>` +
        (s.options.analysis === "multit" ? `<p class="hint">One t test for each row name (e.g. each gene or protein), comparing the two columns. Rows with the same name are replicates. P values are corrected for the number of tests with the false discovery rate (Benjamini-Hochberg).</p>
          <div class="row"><label>Test</label><select id="opt-mtkind">${[["welch", "Welch's t test"], ["unpaired", "Unpaired t test"], ["mannwhitney", "Mann-Whitney"]].map(([v, l]) => `<option value="${v}" ${(s.options.mtKind || "welch") === v ? "selected" : ""}>${l}</option>`).join("")}</select>
          <label>FDR (Q)</label><select id="opt-q">${[0.01, 0.05, 0.1].map(v => `<option ${(s.options.q || 0.05) === v ? "selected" : ""}>${v}</option>`).join("")}</select></div>` : `<p class="hint">Tests whether the <b>column factor</b> (${esc(s.cols.slice(1).join(", "))}) matters, whether the <b>row factor</b> (${esc(s.cols[0])}) matters, and whether they <b>interact</b> (the treatment effect differs between rows). Then compares the columns within each row.</p>
          <label class="check"><input type="checkbox" data-opt="rm" ${s.options.rm ? "checked" : ""}> Same subjects measured at every row (repeated measures, e.g. a time course)</label>
          ${s.options.rm ? `<p class="hint">Enter each subject in the same position under every row name: the 1st value under each time point in a column is subject 1, the 2nd is subject 2, and so on. Subjects missing a time point are left out.</p>`
            : `<div class="row"><label for="opt-twcmp">Multiple comparisons</label><select id="opt-twcmp">${[["within_rows", `Compare columns within each ${esc(s.cols[0] || "row")}`], ["within_cols", `Compare ${esc(s.cols[0] || "row")} levels within each column`],
              ["col_means", "Compare column means (main effect)"], ["row_means", `Compare ${esc(s.cols[0] || "row")} means (main effect)`]].map(([v, l]) => `<option value="${v}" ${(s.options.twCompare || "within_rows") === v ? "selected" : ""}>${l}</option>`).join("")}</select></div>`}${alphaSelect(s)}`),
      graphControls: () => [
        sel("style", "Style", [["bars", "Bars + dots"], ["stacked", "Stacked bars (means)"], ["dots", "Dots + mean"], ["lines", "Interaction plot (means)"]]),
        sel("err", "Error bars", [["sd", "Mean ± SD"], ["sem", "Mean ± SEM"], ["ci95", "Mean ± 95% CI"], ["none", "None"]]),
        sel("brackets", "Significance", [["sig", "Significant pairs"], ["all", "All pairs"], ["none", "Hide"]]),
        txt("ylabel", "Y axis label"), chk("showPoints", "Show points"), chk("horizontal", "Horizontal (sideways)"),
      ],
      renderResults: (r, s) => r.test_name === "Multiple t tests" ? renderMultiT(r) : renderTwoWayResults(r, s),
      draw: (el, r, s) => r.test_name === "Multiple t tests" ? drawVolcano(el, r, s) : drawTwoWay(el, r, s),
    },
    // ---------------------------------------------------------------- XY
    regression: {
      label: "XY: curves & regression", newTitle: "XY analysis",
      minCols: 2, maxCols: 13, fixedCols: 1, textCol: -1, addLabel: "+ Replicate", minRows: 15,
      colKind: j => j === 0 ? "X" : `Y${j}`, newColName: j => `Y${j}`,
      hint: "X in the first column; Y values to the right. Add Y columns for replicates. Unknown samples: leave X blank and enter their Y; the app reads their X off the fitted curve (standard-curve interpolation).",
      cols: ["X", "Y"],
      options: { model: "linear", xIsLog: false, alpha: 0.05 },
      graph: { xlabel: "", ylabel: "", band: true, showEq: true, repMode: "mean", logX: false, xmin: "", xmax: "" },
      examples: s => s.options.yMode === "datasets" ? {
        cols: ["Concentration (µM)", "Compound A", "Compound B"],
        rows: [[0.01, 99.2, 100.4], [0.03, 97.1, 99.0], [0.1, 91.5, 97.6], [0.3, 77.4, 93.1], [1, 53.8, 82.2],
          [3, 27.6, 58.9], [10, 13.9, 30.4], [30, 7.2, 14.1], [100, 5.8, 7.3]],
      } : (modelInfo(s.options.model)?.log_x) ? {
        cols: ["Concentration (µM)", "Response %", "Rep 2", "Rep 3"],
        rows: [[0.01, 98.1, 101.2, 97.4], [0.03, 96.0, 99.5, 95.8], [0.1, 92.7, 88.9, 93.4], [0.3, 80.3, 75.6, 77.9],
          [1, 50.1, 55.8, 52.0], [3, 30.2, 26.9, 29.4], [10, 12.8, 15.1, 13.0], [30, 7.5, 9.2, 6.9], [100, 6.4, 4.8, 6.1]],
      } : {
        cols: ["Concentration (µg/mL)", "Absorbance"],
        rows: [[0, 0.02], [5, 0.11], [10, 0.21], [20, 0.39], [40, 0.83], [60, 1.18], [80, 1.62], ["", 0.55], ["", 1.31]],
      },
      request(s) {
        if (s.options.yMode === "datasets") {
          const fixed = Object.fromEntries(Object.entries((s.options.fixed || {})[s.options.model] || {}).filter(([, v]) => isNum(v)).map(([k, v]) => [k, Number(v)]));
          return ["/api/fitmulti", { x: s.data.map(r => num(r[0])), ys: s.cols.slice(1).map((_, j) => s.data.map(r => num(r[j + 1]))),
            names: s.cols.slice(1).map((c, j) => c || `Y${j + 1}`), model: s.options.model, x_is_log: !!s.options.xIsLog, alpha: s.options.alpha, fixed,
            compare: s.options.cmpParam || null, equation: s.options.model === "custom" ? (s.options.equation || "") : null,
            initial: s.options.model === "custom" ? Object.fromEntries(Object.entries(s.options.initial || {}).filter(([, v]) => isNum(v)).map(([k, v]) => [k, Number(v)])) : null }];
        }
        return ["/api/fit", { x: s.data.map(r => num(r[0])), ys: s.cols.slice(1).map((_, j) => s.data.map(r => num(r[j + 1]))),
          model: s.options.model, compare: s.options.model !== "linear" ? (s.options.compare || null) : null,
          fixed: Object.fromEntries(Object.entries((s.options.fixed || {})[s.options.model] || {}).filter(([, v]) => isNum(v)).map(([k, v]) => [k, Number(v)])),
          equation: s.options.model === "custom" ? (s.options.equation || "") : null,
          initial: s.options.model === "custom" ? Object.fromEntries(Object.entries(s.options.initial || {}).filter(([, v]) => isNum(v)).map(([k, v]) => [k, Number(v)])) : null,
          auc: !!s.options.auc, baseline: isNum(s.options.baseline) ? Number(s.options.baseline) : 0,
          rout_q: s.options.rout ? Number(s.options.routQ ?? 0.01) : null,
          x_is_log: !!s.options.xIsLog, alpha: s.options.alpha }];
      },
      renderOptions(s) {
        const custom = s.options.model === "custom";
        const m = custom ? null : modelInfo(s.options.model);
        const multi = s.options.yMode === "datasets";
        const pnames = s.options.model === "linear" ? ["Slope", "Intercept"] : custom ? (s.options.eqParams || []) : (m && m.params) || [];
        const ySeg = `<div class="seg"><button data-set="yMode:replicates" class="${multi ? "" : "on"}">Y columns = replicates of one curve</button><button data-set="yMode:datasets" class="${multi ? "on" : ""}">Each Y column = its own curve</button></div>`;
        const cmpSel = multi ? `<div class="row"><label for="opt-cmpparam">Compare curves</label><select id="opt-cmpparam"><option value="">No comparison</option>${pnames
          .map(pn => `<option value="${esc(pn)}" ${s.options.cmpParam === pn ? "selected" : ""}>Is ${esc(pn)} different between curves?</option>`).join("")}<option value="all" ${s.options.cmpParam === "all" ? "selected" : ""}>Do the curves differ at all?</option></select></div>` : "";
        return ySeg + `<div class="opt-label">Fit</div>
          <select id="opt-model">${[["linear", "Straight line (linear regression + correlation)"], ...MODELS.map(m => [m.id, m.name]), ["custom", "User-defined equation…"]]
            .map(([v, l]) => `<option value="${v}" ${s.options.model === v ? "selected" : ""}>${l}</option>`).join("")}</select>
          ${custom ? `<textarea id="opt-equation" class="eq-input" rows="2" spellcheck="false" placeholder="Y = A*exp(-K*X) + C">${esc(s.options.equation || "")}</textarea>
            <p class="hint">Use X, any parameter names, + − * / ^ and exp, ln, log10, sqrt, sin, cos, abs. Example: <code>Y = Top/(1+(X/EC50)^Hill)</code></p>
            <div id="custom-params">${customParamsHTML(s)}</div>`
          : `<div class="eqn">${m ? esc(m.equation) : "Y = Slope·X + Intercept"}</div>`}
          ${cmpSel}
          ${m && !multi ? `<div class="row"><label for="opt-compare">Compare with</label><select id="opt-compare"><option value="">No comparison</option>${MODELS
            .filter(o => o.id !== m.id && o.log_x === m.log_x).map(o => `<option value="${o.id}" ${s.options.compare === o.id ? "selected" : ""}>${esc(o.name)}</option>`).join("")}</select></div>` : ""}
          ${m && m.params ? `<details class="constrain" ${Object.values((s.options.fixed || {})[m.id] || {}).some(isNum) ? "open" : ""}>
            <summary>Constrain parameters <span class="pd">(optional)</span></summary>
            <p class="hint">Leave blank to fit. Type a value to hold it fixed, e.g. Bottom = 0 and Top = 100 for normalized data.</p>
            <div class="cgrid">${m.params.map(pn => `<label>${esc(pn)}<input type="text" data-fix="${esc(pn)}" value="${esc(((s.options.fixed || {})[m.id] || {})[pn] ?? "")}" placeholder="fit" inputmode="decimal"></label>`).join("")}</div>
          </details>` : ""}
          ${m && m.log_x ? `<label class="check"><input type="checkbox" id="opt-xislog" ${s.options.xIsLog ? "checked" : ""}> X values are already log10(concentration)</label>
            <p class="hint">Otherwise X is concentration and the app takes the log for you (X = 0 is left out, as it has no log).</p>` : ""}
          ${multi ? "" : `<div class="row"><label class="check"><input type="checkbox" data-opt="rout" ${s.options.rout ? "checked" : ""}> Remove outliers before fitting (ROUT)</label>
            ${s.options.rout ? `<label for="opt-routq">Q</label>` + `<select id="opt-routq">${[["0.001", "0.1%"], ["0.01", "1% (recommended)"], ["0.05", "5%"], ["0.1", "10%"]].map(([v, l]) => `<option value="${v}" ${String(s.options.routQ ?? "0.01") === v ? "selected" : ""}>${l}</option>`).join("")}</select>` : ""}</div>`}
          ${multi ? "" : `<div class="row"><label class="check"><input type="checkbox" data-opt="auc" ${s.options.auc ? "checked" : ""}> Area under the curve</label>
            ${s.options.auc ? `<label>baseline Y =</label><input type="text" id="opt-baseline" value="${esc(s.options.baseline ?? "0")}" style="width:70px" inputmode="decimal">` : ""}</div>`}
          ${alphaSelect(s)}`;
      },
      graphControls: s => [
        txt("xlabel", "X axis label", s.cols[0]), txt("ylabel", "Y axis label", s.cols[1]),
        ...(s.cols.length > 2 && s.options.yMode !== "datasets" ? [sel("repMode", "Replicates", [["mean", "Mean ± SD"], ["sem", "Mean ± SEM"], ["all", "All points"]])] : []),
        txt("xmin", "X min", "auto"), txt("xmax", "X max", "auto"), txt("xtick", "X tick every", "auto"),
        chk("logX", "Log X axis"), chk("band", "95% confidence band"), chk("showEq", "Show equation"),
      ],
      renderResults: (r, s) => r.multi ? renderMultiFit(r, s) : renderXYResults(r, s),
      draw: (el, r, s) => r.multi ? drawMultiFit(el, r, s) : drawXY(el, r, s),
    },
    // ---------------------------------------------------------------- multiple variables
    multivar: {
      label: "Multiple variables", newTitle: "Multiple variables",
      minCols: 2, maxCols: 20, fixedCols: 0, textCol: -1, addLabel: "+ Variable", minRows: 15,
      colKind: (j, s) => s && s.options.analysis === "cox" ? (j === 0 ? "Time" : j === 1 ? "Event (1/0)" : `Predictor ${j - 1}`)
        : s && s.options.analysis && s.options.analysis !== "correlation" ? (j === 0 ? (s.options.analysis === "logistic" ? "Outcome (0/1)" : "Outcome (Y)") : `Predictor ${j}`) : `Variable ${j + 1}`,
      newColName: j => `Variable ${j + 1}`,
      hint: "One column per variable (e.g. age, BMI, glucose), one row per subject. For regression, put the outcome in the first column and the predictors to its right.",
      cols: ["Variable 1", "Variable 2", "Variable 3"],
      options: { analysis: "correlation", method: "pearson", alpha: 0.05 },
      graph: { showValues: true },
      examples: s => s.options.analysis === "cox" ? {
        cols: ["Months", "Died (1/0)", "Age", "Treated (1/0)", "Tumor size (cm)"],
        rows: [[5, 1, 71, 0, 4.2], [8, 1, 66, 0, 3.5], [12, 1, 59, 1, 3.9], [14, 0, 48, 1, 2.1], [3, 1, 74, 0, 5.0], [22, 0, 52, 1, 1.8],
          [9, 1, 63, 1, 4.4], [18, 1, 69, 0, 2.6], [30, 0, 45, 1, 1.5], [6, 1, 77, 0, 3.1], [25, 1, 58, 1, 2.9], [16, 0, 61, 0, 2.2],
          [11, 1, 68, 0, 3.8], [28, 0, 50, 1, 2.4], [4, 1, 72, 1, 4.8], [20, 1, 64, 0, 2.0], [33, 0, 47, 1, 1.2], [7, 1, 70, 0, 3.3],
          [26, 0, 55, 1, 3.0], [13, 1, 62, 0, 2.7], [35, 0, 49, 1, 1.9], [10, 1, 75, 1, 3.6], [19, 0, 57, 0, 2.3], [24, 1, 60, 1, 4.1]],
      } : s.options.analysis === "logistic" ? {
        cols: ["Diabetes (0/1)", "Age", "BMI", "Activity"],
        rows: [[0, 34, 22.1, 9.5], [0, 45, 27.4, 6.1], [1, 52, 31.2, 3.2], [0, 29, 21.5, 10.2], [1, 61, 29.8, 4.0], [0, 38, 24.6, 8.3],
          [1, 47, 33.1, 2.5], [0, 55, 29.6, 3.8], [0, 41, 23.3, 9.1], [1, 66, 30.5, 3.6], [0, 33, 25.8, 7.4], [1, 58, 25.2, 7.9],
          [0, 49, 31.5, 4.1], [1, 44, 26.9, 8.1], [0, 62, 24.1, 8.8], [1, 57, 30.9, 2.9], [0, 36, 26.5, 5.5], [1, 51, 29.4, 7.0],
          [0, 40, 28.8, 6.5], [1, 63, 27.7, 4.4]],
      } : s.options.analysis === "mlr" ? {
        cols: ["Glucose", "Age", "BMI", "Activity"],
        rows: [[88, 34, 22.1, 9.5], [101, 45, 27.4, 6.1], [118, 52, 31.2, 3.2], [84, 29, 21.5, 10.2], [112, 61, 29.8, 4.0], [93, 38, 24.6, 8.3],
          [126, 47, 33.1, 2.5], [99, 55, 26.0, 6.8], [90, 41, 23.3, 9.1], [121, 66, 30.5, 3.6], [95, 33, 25.8, 7.4], [108, 58, 28.2, 5.0],
          [104, 49, 27.9, 4.1], [115, 44, 32.4, 6.2], [97, 62, 24.1, 8.8], [119, 57, 30.9, 2.9], [96, 36, 26.5, 5.5], [110, 51, 29.4, 7.0]],
      } : ({
        cols: ["Age", "BMI", "Glucose", "Insulin", "Activity"],
        rows: [[34, 22.1, 88, 6.2, 9.5], [45, 27.4, 101, 9.8, 6.1], [52, 31.2, 118, 14.3, 3.2], [29, 21.5, 84, 5.1, 10.2],
          [61, 29.8, 112, 12.9, 4.0], [38, 24.6, 93, 7.7, 8.3], [47, 33.1, 126, 16.2, 2.5], [55, 26.0, 99, 8.9, 6.8],
          [41, 23.3, 90, 6.6, 9.1], [66, 30.5, 121, 13.8, 3.6], [33, 25.8, 95, 8.1, 7.4], [58, 28.2, 108, 11.0, 5.0]],
      }),
      request: s => ["/api/multi", { columns: s.cols.map((_, j) => s.data.map(r => num(r[j]))), names: s.cols.map((c, j) => c || `Variable ${j + 1}`),
        analysis: s.options.analysis || "correlation", alpha: s.options.alpha,
        method: s.options.analysis === "pca" ? (s.options.pcaScale || "standardized") : s.options.method }],
      renderOptions: s => `<div class="seg"><button data-set="analysis:correlation" class="${(s.options.analysis || "correlation") === "correlation" ? "on" : ""}">Correlation matrix</button><button data-set="analysis:mlr" class="${s.options.analysis === "mlr" ? "on" : ""}">Multiple linear regression</button><button data-set="analysis:logistic" class="${s.options.analysis === "logistic" ? "on" : ""}">Logistic regression</button><button data-set="analysis:cox" class="${s.options.analysis === "cox" ? "on" : ""}">Cox regression</button><button data-set="analysis:pca" class="${s.options.analysis === "pca" ? "on" : ""}">PCA</button></div>` +
        (s.options.analysis === "pca" ? `<p class="hint">Principal component analysis finds the few directions (components) that capture most of the variation across all variables. Rows missing any value are left out.</p>
          <div class="seg"><button data-set="pcaScale:standardized" class="${(s.options.pcaScale || "standardized") === "standardized" ? "on" : ""}">Standardize variables (recommended)</button><button data-set="pcaScale:covariance" class="${s.options.pcaScale === "covariance" ? "on" : ""}">Use raw units</button></div>` :
        (s.options.analysis || "correlation") !== "correlation" ? `<p class="hint">${s.options.analysis === "cox" ? "Survival with several predictors: first column = time to event or last follow-up, second column = 1 if the event (e.g. death) happened, 0 if censored, then one column per predictor (numbers; use 1/0 for yes/no). Results are hazard ratios." : s.options.analysis === "logistic" ? "Predicts a yes/no outcome (first column: 1 = yes, 0 = no) from the other columns. Results are odds ratios." : "Predicts the outcome (first column) from all the other columns at once; each coefficient is adjusted for the other predictors."} Rows missing any value are left out.</p>${alphaSelect(s)}` : `<div class="seg"><button data-set="method:pearson" class="${s.options.method === "pearson" ? "on" : ""}">Pearson (linear)</button><button data-set="method:spearman" class="${s.options.method === "spearman" ? "on" : ""}">Spearman (ranks, nonparametric)</button></div>${alphaSelect(s)}`),
      graphControls: s => (s.options.analysis || "correlation") === "correlation" ? [chk("showValues", "Show r values")]
        : s.options.analysis === "pca" ? [sel("pcaPlot", "Plot", [["biplot", "Biplot (PC1 vs PC2)"], ["scree", "Scree plot"]]), chk("pcaLabels", "Label rows")] : [],
      renderResults: (r, s) => r.kind === "cox" ? renderCox(r) : r.kind === "pca" ? renderPCA(r) : r.kind === "linear" ? renderMLR(r) : r.kind === "logistic" ? renderLogistic(r) : renderCorrMatrix(r),
      draw: (el, r, s) => r.kind === "cox" ? drawForest(el, r, s) : r.kind === "pca" ? drawPCA(el, r, s) : r.kind === "linear" ? drawMLR(el, r, s) : r.kind === "logistic" ? drawROC(el, { auc: r.auc, curve: r.roc_curve, best: null }, s) : drawCorrMatrix(el, r, s),
    },
    // ---------------------------------------------------------------- diagnostics
    diagnostic: {
      label: "ROC & method comparison", newTitle: "Diagnostic",
      minCols: 2, maxCols: 2, fixedCols: 2, textCol: -1, addLabel: "+ Column", minRows: 15,
      colKind: (j, s) => (s && s.options.analysis === "bland_altman") ? ["Method A", "Method B"][j] : ["Controls", "Patients"][j],
      newColName: j => `Column ${j + 1}`,
      hint: "ROC: the test's values for people without the condition (Controls) and with it (Patients). Bland-Altman: the same samples measured by two methods, one row per sample.",
      cols: ["Controls", "Patients"],
      options: { analysis: "roc", alpha: 0.05 },
      graph: {},
      examples: s => s.options.analysis === "bland_altman" ? {
        cols: ["Lab analyzer", "Point-of-care"],
        rows: [[5.1, 5.3], [6.8, 7.1], [4.4, 4.3], [9.2, 9.8], [7.5, 7.6], [5.9, 6.3], [8.1, 8.2], [10.4, 11.1], [6.2, 6.1], [7.0, 7.4], [4.9, 5.2], [8.8, 9.3]],
      } : {
        cols: ["Healthy", "Disease"],
        rows: [[1.2, 2.9], [0.8, 3.6], [1.9, 1.7], [1.5, 4.2], [2.4, 2.8], [0.9, 3.1], [1.1, 5.0], [2.0, 2.2], [1.6, 3.9], [1.3, 2.6], [2.7, 4.4], [1.0, 3.3]],
      },
      request: s => ["/api/multi", { columns: [0, 1].map(j => s.data.map(r => num(r[j]))), names: s.cols.slice(0, 2), analysis: s.options.analysis, alpha: s.options.alpha }],
      renderOptions: s => `<div class="seg"><button data-set="analysis:roc" class="${s.options.analysis === "roc" ? "on" : ""}">ROC curve</button><button data-set="analysis:bland_altman" class="${s.options.analysis === "bland_altman" ? "on" : ""}">Bland-Altman agreement</button></div>
        <p class="hint">${s.options.analysis === "roc" ? "How well does the test separate patients from controls? Gives the area under the ROC curve and the best cutoff." : "Do two methods agree? Shows the average difference (bias) and the range where 95% of differences fall (limits of agreement)."}</p>${alphaSelect(s)}`,
      graphControls: () => [],
      renderResults: (r, s) => s.options.analysis === "roc" ? renderROC(r) : renderBA(r),
      draw: (el, r, s) => s.options.analysis === "roc" ? drawROC(el, r, s) : drawBA(el, r, s),
    },
    // ---------------------------------------------------------------- figure layout
    layout: {
      label: "Figure layout", newTitle: "Figure",
      minCols: 0, maxCols: 0, fixedCols: 0, textCol: -1, addLabel: "", minRows: 0, noData: true,
      colKind: () => "", newColName: () => "",
      hint: "", cols: [], options: { panels: [], ncol: 2, letters: true, alpha: 0.05 },
      graph: { exportSize: "2", letterSize: 16 },
      examples: () => ({ cols: [], rows: [] }),
      async runCustom(s) {
        const ids = (s.options.panels || []).filter(id => project.sheets.some(x => x.id === id && x.type !== "layout"));
        if (!ids.length) throw new Error("Tick the analyses to include in this figure (left).");
        const panels = await Promise.all(ids.map(async id => {
          const sh = project.sheets.find(x => x.id === id);
          const [url, body] = TYPES[sh.type].request(masked(sh));
          try {
            const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
            const json = await res.json();
            return res.ok ? { sheet: masked(sh), result: json } : { sheet: sh, error: json.detail || "Not enough data." };
          } catch { return { sheet: sh, error: "Can't reach the analysis engine." }; }
        }));
        return { kind: "layout", panels };
      },
      request: () => null,
      renderOptions(s) {
        const others = project.sheets.filter(x => x.type !== "layout");
        const sel = s.options.panels || [];
        return `<div class="opt-label">Analyses to include (in order)</div>
          <div class="panel-list">${others.map(x => `<label class="check"><input type="checkbox" data-panel="${x.id}" ${sel.includes(x.id) ? "checked" : ""}>
            <span class="badge t-${x.type}">${badgeText(x.type)}</span> ${esc(x.title)}${sel.includes(x.id) ? ` <span class="pd">(${String.fromCharCode(65 + sel.indexOf(x.id))})</span>` : ""}</label>`).join("") || `<p class="hint">Create some analyses first.</p>`}</div>
          <div class="row"><label>Columns</label><select id="opt-ncol">${[1, 2, 3].map(n => `<option ${s.options.ncol === n ? "selected" : ""}>${n}</option>`).join("")}</select>
          <label class="check"><input type="checkbox" data-opt="letters" ${s.options.letters ? "checked" : ""}> Panel letters (A, B, C…)</label></div>
          <p class="hint">Each panel uses that analysis's own graph and Format settings. Export as PNG or TIFF for a single figure file.</p>`;
      },
      graphControls: () => [{ k: "letterSize", label: "Letter size", kind: "range", min: 10, max: 28 }],
      renderResults: r => {
        const ok = r.panels.filter(p => !p.error);
        return T.summary("ns", `${ok.length} panel${ok.length === 1 ? "" : "s"} in this figure.`) +
          T.multi(["Panel", "Analysis", "Result"], r.panels.map((p, i) => [String.fromCharCode(65 + i), esc(p.sheet.title),
            p.error ? `<span class="pd">${esc(p.error)}</span>` : esc(layoutSummary(p))])).replace('class="res multi"', 'class="res multi left"');
      },
      draw: drawLayout,
    },
    // ---------------------------------------------------------------- survival
    survival: {
      label: "Survival", newTitle: "Survival",
      minCols: 2, maxCols: 13, fixedCols: 1, textCol: -1, addLabel: "+ Group", minRows: 20,
      colKind: j => j === 0 ? "Time" : `Group ${letter(j - 1)}`, newColName: j => `Group ${letter(j - 1)}`,
      hint: "One row per subject. Time in the first column. In that subject's group column enter 1 if the event happened (e.g. death) or 0 if censored (still alive / lost to follow-up). Leave other groups blank.",
      cols: ["Days", "Treated", "Control"],
      options: { alpha: 0.05 },
      graph: { xlabel: "", ylabel: "Percent survival", showCI: false, showCensor: true },
      examples: () => {
        const T1 = [6, 6, 6, 7, 10, 13, 16, 22, 23, 6, 9, 10, 11, 17, 19, 20, 25, 32, 32, 34, 35];
        const E1 = [1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
        const T2 = [1, 1, 2, 2, 3, 4, 4, 5, 5, 8, 8, 8, 8, 11, 11, 12, 12, 15, 17, 22, 23];
        return { cols: ["Weeks", "6-MP", "Placebo"], rows: [...T1.map((t, i) => [t, E1[i], ""]), ...T2.map(t => [t, "", 1])] };
      },
      request(s) {
        return ["/api/survival", { times: s.data.map(r => num(r[0])), groups: s.cols.slice(1).map((_, j) => s.data.map(r => num(r[j + 1]))),
          names: s.cols.slice(1).map((c, j) => c || `Group ${letter(j)}`), alpha: s.options.alpha }];
      },
      renderOptions: s => `<p class="hint">Kaplan-Meier survival curves for each group. With 2 or more groups, the log-rank (Mantel-Cox) test compares them; with 2 groups you also get the hazard ratio.</p>${alphaSelect(s)}`,
      graphControls: s => [txt("xlabel", "X axis label", s.cols[0]), txt("ylabel", "Y axis label"),
        chk("showCensor", "Mark censored"), chk("showCI", "95% confidence bands")],
      renderResults: renderSurvivalResults,
      draw: drawSurvival,
    },
    // ---------------------------------------------------------------- contingency
    contingency: {
      label: "Contingency table", newTitle: "Contingency",
      minCols: 3, maxCols: 9, fixedCols: 1, textCol: 0, addLabel: "+ Outcome", minRows: 6,
      colKind: j => j === 0 ? "Row name" : `Outcome ${j}`, newColName: j => `Outcome ${j}`,
      hint: "Each row is a group (type its name in the first column). Enter counts (number of subjects) in the outcome columns.",
      cols: ["Group", "Outcome 1", "Outcome 2"],
      options: { alpha: 0.05 },
      graph: { ylabel: "", mode: "pct" },
      examples: () => ({ cols: ["Group", "Responded", "No response"], rows: [["Treated", 38, 12], ["Placebo", 23, 27]] }),
      request(s) {
        const rows = s.data.filter(r => r.slice(1).some(isNum));
        return ["/api/contingency", { table: rows.map(r => r.slice(1).map(v => num(v))), rows: rows.map((r, i) => String(r[0] || `Row ${i + 1}`)),
          cols: s.cols.slice(1).map((c, j) => c || `Outcome ${j + 1}`), alpha: s.options.alpha }];
      },
      renderOptions: s => `<p class="hint">2×2 tables: Fisher's exact test, odds ratio and relative risk. Larger tables: chi-square test.</p>${alphaSelect(s)}`,
      graphControls: () => [sel("mode", "Show", [["pct", "Percent of each row"], ["count", "Counts"]]), txt("ylabel", "Y axis label"), chk("stack", "Stacked bars"), chk("horizontal", "Horizontal (sideways)")],
      renderResults: renderContingencyResults,
      draw: drawContingency,
    },
  };

  function customParamsHTML(s) {
    const names = s.options.eqParams || [];
    if (s.options.eqError) return `<p class="note warn">${esc(s.options.eqError)}</p>`;
    if (!names.length) return "";
    const fx = (s.options.fixed || {}).custom || {}, init = s.options.initial || {};
    return `<div class="opt-label">Parameters: starting value and (optional) fixed value</div>
      <div class="cgrid">${names.map(n => `<label>${esc(n)}<input type="text" data-init="${esc(n)}" value="${esc(init[n] ?? "")}" placeholder="start: 1" inputmode="decimal">
        <input type="text" data-fix="${esc(n)}" value="${esc(fx[n] ?? "")}" placeholder="fit" inputmode="decimal"></label>`).join("")}</div>
      <p class="hint">If the fit fails, give starting values close to what you expect.</p>`;
  }
  async function checkEquation(s) {
    try {
      const r = await api("/api/equation", { method: "POST", body: JSON.stringify({ equation: s.options.equation || "" }) });
      s.options.eqParams = r.params; s.options.eqError = r.ok ? "" : r.error;
    } catch { s.options.eqError = ""; }
    const box = $("custom-params");
    if (box && active() === s) { box.innerHTML = customParamsHTML(s); wireParamInputs(s); }
  }
  function wireParamInputs(s) {
    $("options").querySelectorAll("[data-fix]").forEach(inp => inp.oninput = () => {
      const f = (s.options.fixed = s.options.fixed || {}), mf = (f[s.options.model] = f[s.options.model] || {});
      mf[inp.dataset.fix] = inp.value.trim();
      inp.classList.toggle("bad", inp.value.trim() !== "" && !isNum(inp.value));
      save(); scheduleRun();
    });
    $("options").querySelectorAll("[data-init]").forEach(inp => inp.oninput = () => {
      (s.options.initial = s.options.initial || {})[inp.dataset.init] = inp.value.trim();
      inp.classList.toggle("bad", inp.value.trim() !== "" && !isNum(inp.value));
      save(); scheduleRun();
    });
  }

  const filledCols = s => s.cols.map((_, j) => j).filter(j => s.data.some(r => isNum(r[j])));
  const alphaSelect = s => `<div class="row"><label for="opt-alpha">Significance level α</label><select id="opt-alpha">${[0.05, 0.01, 0.1]
    .map(a => `<option value="${a}" ${s.options.alpha === a ? "selected" : ""}>${a}</option>`).join("")}</select></div>`;

  // graph format control descriptors
  const sel = (k, label, opts) => ({ k, label, kind: "select", opts });
  const txt = (k, label, ph = "") => ({ k, label, kind: "text", ph });
  const chk = (k, label) => ({ k, label, kind: "check" });

  // ======================================================================
  // project model
  // ======================================================================
  let project = null;
  const blankRows = (n, c) => Array.from({ length: n }, () => Array(c).fill(""));

  function newSheet(type, withExample = false) {
    const t = TYPES[type];
    const count = project ? project.sheets.filter(x => x.type === type).length + 1 : 1;
    const s = { id: uid(), type, title: `${t.newTitle} ${count}`, cols: [...t.cols], data: blankRows(t.minRows, t.cols.length),
      options: { ...t.options }, graph: { ...COMMON_GRAPH, ...t.graph } };
    if (withExample) applyExample(s);
    return s;
  }
  function normalize(s) {
    // upgrade sheets saved by older versions
    const t = TYPES[s.type] || TYPES.ttest;
    if (!TYPES[s.type]) s.type = "ttest";
    s.options = { ...t.options, ...(s.options || {}) };
    if (s.type === "ttest" && !s.options.migrated) {
      // older versions stored kind / kind2 / kind3
      const k2 = s.options.kind2 || s.options.kind;
      if (k2 === "paired") { s.options.design = "repeated"; s.options.kind2r = "paired"; }
      else if (k2) s.options.kind2i = k2;
      if (s.options.kind3) s.options.kind3i = s.options.kind3;
      s.options.migrated = true;
    }
    s.graph = { ...COMMON_GRAPH, ...t.graph, ...(s.graph || {}) };
    s.data = (s.data || []).map(r => s.cols.map((_, j) => r[j] ?? ""));
    padRows(s);
    return s;
  }
  function applyExample(s) {
    const ex = TYPES[s.type].examples(s);
    s.excluded = [];
    s.cols = [...ex.cols];
    s.data = ex.rows.map(r => r.map(v => String(v)));
    padRows(s);
  }
  function examplesProject() {
    project = { sheets: [] };
    const add = (type, title, tweak) => { const s = newSheet(type); if (tweak) tweak(s); applyExample(s); s.title = title; project.sheets.push(s); return s; };
    const first = add("ttest", "Example: two groups");
    add("ttest", "Example: three groups (ANOVA)", s => { s.cols = ["A", "B", "C"]; });
    add("summary", "Example: from mean, SD and n");
    add("ttest", "Example: distribution (histogram, Q-Q)", s => {
      s.options.mode = "freq"; s.graph.normalCurve = true; s.graph.ylabel = "Cell size (µm)"; });
    add("ttest", "Example: column statistics", s => { s.cols = ["A", "B", "C"]; s.options.mode = "describe"; s.options.hypothetical = "12"; });
    add("nested", "Example: nested (cells within animals)");
    add("twoway", "Example: two-way ANOVA");
    add("twoway", "Example: multiple t tests", s => { s.options.analysis = "multit"; });
    add("twoway", "Example: time course (repeated measures)", s => { s.options.rm = true; s.graph.style = "lines"; s.graph.err = "sem"; });
    add("regression", "Example: dose-response (IC50)", s => { s.options.model = "dr_inhibit"; s.graph.logX = true; });
    add("regression", "Example: standard curve");
    add("regression", "Example: compare two IC50s", s => { s.options.model = "dr_inhibit"; s.options.yMode = "datasets"; s.options.cmpParam = "LogIC50"; s.graph.logX = true; });
    add("survival", "Example: survival");
    const figPanels = project.sheets.filter(x => ["Example: two groups", "Example: three groups (ANOVA)", "Example: dose-response (IC50)", "Example: survival"].includes(x.title)).map(x => x.id);
    add("contingency", "Example: contingency");
    add("multivar", "Example: correlation matrix");
    add("multivar", "Example: multiple regression", s => { s.options.analysis = "mlr"; });
    add("multivar", "Example: logistic regression", s => { s.options.analysis = "logistic"; });
    add("multivar", "Example: Cox regression", s => { s.options.analysis = "cox"; });
    add("multivar", "Example: PCA", s => { s.options.analysis = "pca"; });
    add("diagnostic", "Example: ROC curve");
    add("diagnostic", "Example: Bland-Altman", s => { s.options.analysis = "bland_altman"; });
    add("layout", "Example: figure layout", s => { s.options.panels = figPanels; });
    project.activeId = first.id;
    return project;
  }
  const active = () => project.sheets.find(s => s.id === project.activeId) || project.sheets[0];
  function padRows(s) {
    let last = -1;
    s.data.forEach((r, i) => { if (r.some(v => String(v).trim() !== "")) last = i; });
    const want = Math.max(TYPES[s.type].minRows, last + 4);
    while (s.data.length < want) s.data.push(Array(s.cols.length).fill(""));
  }

  // ======================================================================
  // undo / redo (per analysis, kept in memory)
  // ======================================================================
  const history = {};
  let groupOpen = false, groupTimer = null;
  const snap = s => JSON.stringify({ cols: s.cols, data: s.data, excluded: s.excluded || [] });
  // ---- excluded values: kept in the table, left out of analyses and graphs
  const exKey = (r, c) => `${r}:${c}`;
  const isExcluded = (s, r, c) => !!(s.excluded && s.excluded.includes(exKey(r, c)));
  function masked(s) {
    if (!s.excluded || !s.excluded.length) return s;
    const set = new Set(s.excluded);
    return { ...s, data: s.data.map((row, r) => row.map((v, c) => set.has(exKey(r, c)) ? "" : v)) };
  }
  function shiftExcludedRows(s, at, delta) {   // rows inserted (delta > 0) or deleted (delta < 0) at index `at`
    if (!s.excluded) return;
    s.excluded = s.excluded.map(k => k.split(":").map(Number)).filter(([r]) => delta > 0 || r < at || r >= at - delta)
      .map(([r, c]) => exKey(r >= at ? r + delta : r, c));
  }
  function dropExcludedCol(s, j) {
    if (!s.excluded) return;
    s.excluded = s.excluded.map(k => k.split(":").map(Number)).filter(([, c]) => c !== j).map(([r, c]) => exKey(r, c > j ? c - 1 : c));
  }
  function hist(s) { return history[s.id] || (history[s.id] = { undo: [], redo: [] }); }
  function recordUndo(force = false) {
    const s = active(), h = hist(s);
    if (groupOpen && !force) { clearTimeout(groupTimer); groupTimer = setTimeout(() => (groupOpen = false), 800); return; }
    h.undo.push(snap(s)); if (h.undo.length > 200) h.undo.shift();
    h.redo = [];
    groupOpen = !force;
    clearTimeout(groupTimer); groupTimer = setTimeout(() => (groupOpen = false), 800);
    updateUndoButtons();
  }
  function undoRedo(dir) {
    const s = active(), h = hist(s);
    const from = dir === "undo" ? h.undo : h.redo, to = dir === "undo" ? h.redo : h.undo;
    if (!from.length) return;
    to.push(snap(s));
    const st = JSON.parse(from.pop());
    s.cols = st.cols; s.data = st.data; s.excluded = st.excluded || [];
    groupOpen = false; selA = selB = null;
    save(); renderGrid(); renderOptions(); renderFormat(); scheduleRun(); updateUndoButtons();
  }
  function updateUndoButtons() {
    const h = hist(active());
    $("btn-undo").disabled = !h.undo.length;
    $("btn-redo").disabled = !h.redo.length;
  }

  // ======================================================================
  // saving (to the app folder's "projects" directory)
  // ======================================================================
  let projectName = null, saveTimer = null, saving = Promise.resolve();
  function setStatus(text, err = false) { const el = $("save-status"); el.textContent = text; el.classList.toggle("err", err); }
  function save() { setStatus("Saving…"); clearTimeout(saveTimer); saveTimer = setTimeout(saveNow, 500); }
  function saveNow() {
    clearTimeout(saveTimer); saveTimer = null;
    if (!projectName) return saving;
    const name = projectName, body = JSON.stringify({ data: { sheets: project.sheets, activeId: project.activeId } });
    saving = saving.then(async () => {
      try {
        const res = await fetch(`/api/projects/${encodeURIComponent(name)}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body });
        if (!res.ok) throw new Error();
        setStatus("✓ Saved");
      } catch { setStatus("Not saved: is the app still running?", true); }
    });
    return saving;
  }
  async function api(url, opts = {}) {
    const res = await fetch(url, { headers: { "Content-Type": "application/json" }, ...opts });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json.detail || "Something went wrong.");
    return json;
  }
  async function openProject(name) {
    await saveNow();
    const data = await api(`/api/projects/${encodeURIComponent(name)}`);
    if (!Array.isArray(data.sheets) || !data.sheets.length) throw new Error("This project has no analyses.");
    project = { sheets: data.sheets.map(normalize), activeId: data.activeId || data.sheets[0].id };
    projectName = name; $("project-name").value = name; setStatus("✓ Saved");
    renderAll();
  }
  async function uniqueName(base) {
    const list = (await api("/api/projects")).projects.map(p => p.name.toLowerCase());
    let n = base, i = 2;
    while (list.includes(n.toLowerCase())) n = `${base} ${i++}`;
    return n;
  }
  async function createProject(name, withExamples) {
    const n = await uniqueName(name);
    if (projectName) await saveNow();
    if (withExamples) examplesProject();
    else { project = { sheets: [] }; const s = newSheet("ttest"); project.sheets.push(s); project.activeId = s.id; }
    const saved = await api(`/api/projects/${encodeURIComponent(n)}`, { method: "PUT", body: JSON.stringify({ data: project }) });
    projectName = saved.name; $("project-name").value = projectName; setStatus("✓ Saved");
    renderAll();
  }

  // ======================================================================
  // sidebar & header
  // ======================================================================
  function renderSidebar() {
    $("sheet-list").innerHTML = project.sheets.map(s =>
      `<li data-id="${s.id}" draggable="true" class="${s.id === project.activeId ? "active" : ""}" title="${esc(TYPES[s.type].label)}. Drag to reorder.">
        <span class="badge t-${s.type}">${badgeText(s.type)}</span><span class="t">${esc(s.title)}</span></li>`).join("");
    $("sheet-list").querySelectorAll("li").forEach(li => {
      li.onclick = () => { project.activeId = li.dataset.id; save(); renderAll(); };
      li.ondragstart = e => { e.dataTransfer.setData("text/plain", li.dataset.id); e.dataTransfer.effectAllowed = "move"; };
      li.ondragover = e => { e.preventDefault(); li.classList.add("drag-over"); };
      li.ondragleave = () => li.classList.remove("drag-over");
      li.ondrop = e => {
        e.preventDefault(); li.classList.remove("drag-over");
        const from = project.sheets.findIndex(x => x.id === e.dataTransfer.getData("text/plain"));
        const to = project.sheets.findIndex(x => x.id === li.dataset.id);
        if (from < 0 || to < 0 || from === to) return;
        const [moved] = project.sheets.splice(from, 1);
        project.sheets.splice(to, 0, moved);
        save(); renderSidebar();
      };
    });
  }
  const badgeText = t => ({ nested: "N", layout: "▦", summary: "Σ", ttest: "G", twoway: "2W", regression: "XY", survival: "S", contingency: "#", multivar: "MV", diagnostic: "Dx" }[t]);

  // ======================================================================
  // data grid
  // ======================================================================
  function renderGrid() {
    const s = active(), t = TYPES[s.type];
    document.querySelector(".data-card").classList.toggle("no-data", !!t.noData);
    if (t.noData) { $("grid").innerHTML = ""; $("data-hint").textContent = ""; return; }
    padRows(s);
    const canRemove = j => j >= t.fixedCols && s.cols.length > t.minCols;
    let h = "<thead><tr><th class='rownum'></th>";
    s.cols.forEach((c, j) => {
      h += `<th><div class="colkind">${esc(t.colKind(j, s))}${canRemove(j) ? `<button class="rm" data-rm="${j}" title="Remove this column">✕</button>` : ""}</div>
        <div class="colhead"><input data-head="${j}" value="${esc(c)}" spellcheck="false" aria-label="${esc(t.colKind(j, s))} name"></div></th>`;
    });
    h += "</tr></thead><tbody>";
    s.data.forEach((r, i) => {
      h += `<tr><td class="rownum" data-row="${i}" title="Click to select the row; right-click to insert or delete rows">${i + 1}</td>`;
      r.forEach((v, j) => {
        const text = j === t.textCol;
        const bad = (!text && String(v).trim() !== "" && !isNum(v) ? " bad" : "") + (isExcluded(s, i, j) ? " excl" : "");
        h += `<td><input class="cell${text ? " txt" : ""}${bad}" data-r="${i}" data-c="${j}" value="${esc(v)}" ${text ? "" : 'inputmode="decimal"'} spellcheck="false"></td>`;
      });
      h += "</tr>";
    });
    $("grid").innerHTML = h + "</tbody>";
    $("data-hint").textContent = t.hint;
    const add = $("btn-addcol");
    add.textContent = t.addLabel;
    add.disabled = s.cols.length >= t.maxCols;
    add.hidden = t.minCols === t.maxCols;
  }
  const cellAt = (r, c) => $("grid").querySelector(`input[data-r="${r}"][data-c="${c}"]`);

  function onGridInput(e) {
    const el = e.target, s = active(), t = TYPES[s.type];
    if (el.dataset.head !== undefined) {
      recordUndo();
      s.cols[+el.dataset.head] = el.value;
      save(); scheduleRun();
      return;
    }
    if (el.dataset.r === undefined) return;
    if (multiSel()) clearSel();
    recordUndo();
    const c = +el.dataset.c;
    s.data[+el.dataset.r][c] = el.value;
    el.classList.toggle("bad", c !== t.textCol && el.value.trim() !== "" && !isNum(el.value));
    const before = s.data.length;
    padRows(s);
    if (s.data.length !== before) { renderGrid(); cellAt(+el.dataset.r, c).focus(); }
    save(); scheduleRun();
  }
  function onGridPaste(e) {
    const el = e.target;
    if (el.dataset.r === undefined) return;
    const text = (e.clipboardData || window.clipboardData).getData("text");
    if (!/[\t\n\r]/.test(text)) return;
    e.preventDefault();
    const s = active(), t = TYPES[s.type];
    recordUndo(true);
    const rows = text.replace(/\r/g, "").replace(/\n+$/, "").split("\n").map(l => l.split("\t"));
    const r0 = +el.dataset.r, c0 = +el.dataset.c;
    const need = Math.min(t.maxCols, c0 + Math.max(...rows.map(r => r.length)));
    while (s.cols.length < need) { s.cols.push(t.newColName(s.cols.length)); s.data.forEach(r => r.push("")); }
    rows.forEach((row, i) => {
      while (s.data.length <= r0 + i) s.data.push(Array(s.cols.length).fill(""));
      row.forEach((v, j) => { if (c0 + j < s.cols.length) s.data[r0 + i][c0 + j] = v.trim(); });
    });
    padRows(s); save(); renderGrid(); renderOptions(); scheduleRun();
  }
  // ---------------------------------------------------------------- cell selection (blocks / rows)
  let selA = null, selB = null, dragging = false;
  const selRange = () => selA && selB ? { r0: Math.min(selA.r, selB.r), r1: Math.max(selA.r, selB.r), c0: Math.min(selA.c, selB.c), c1: Math.max(selA.c, selB.c) } : null;
  const multiSel = () => { const g = selRange(); return g && (g.r0 !== g.r1 || g.c0 !== g.c1); };
  function paintSel() {
    const g = selRange(), multi = multiSel();
    $("grid").querySelectorAll("input.cell").forEach(inp => {
      const r = +inp.dataset.r, c = +inp.dataset.c;
      inp.classList.toggle("sel", !!(multi && r >= g.r0 && r <= g.r1 && c >= g.c0 && c <= g.c1));
    });
  }
  function clearSel() { selA = selB = null; paintSel(); }
  function selectedTSV() {
    const s = active(), g = selRange();
    const lines = [];
    for (let r = g.r0; r <= g.r1; r++) lines.push(s.data[r].slice(g.c0, g.c1 + 1).map(v => String(v ?? "")).join("\t"));
    return lines.join("\n");
  }
  function clearSelectedCells() {
    const s = active(), g = selRange();
    recordUndo(true);
    for (let r = g.r0; r <= g.r1; r++) for (let c = g.c0; c <= g.c1; c++) s.data[r][c] = "";
    save(); renderGrid(); paintSel(); scheduleRun();
  }
  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); }
    catch { const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove(); }
  }
  function onGridMouseDown(e) {
    const s = active();
    const rn = e.target.closest("[data-row]");
    if (rn && e.button === 0) {   // row number: select whole rows
      const r = +rn.dataset.row;
      if (e.shiftKey && selA) selB = { r, c: s.cols.length - 1 };
      else { selA = { r, c: 0 }; selB = { r, c: s.cols.length - 1 }; }
      dragging = true; paintSel(); e.preventDefault();
      const first = cellAt(selA.r, 0); if (first) first.focus({ preventScroll: true });
      return;
    }
    const el = e.target.closest("input.cell");
    if (!el || e.button !== 0) return;
    const pos = { r: +el.dataset.r, c: +el.dataset.c };
    if (e.shiftKey && selA) { selB = pos; e.preventDefault(); paintSel(); return; }
    selA = pos; selB = pos; dragging = true; paintSel();
  }
  function onGridMouseOver(e) {
    if (!dragging || !selA) return;
    const rn = e.target.closest("[data-row]");
    if (rn && selA.c === 0 && selB && selB.c === active().cols.length - 1) { selB = { r: +rn.dataset.row, c: selB.c }; paintSel(); return; }
    const el = e.target.closest("input.cell");
    if (!el) return;
    const pos = { r: +el.dataset.r, c: +el.dataset.c };
    if (pos.r !== selB.r || pos.c !== selB.c) { selB = pos; paintSel(); window.getSelection()?.removeAllRanges(); }
  }
  document.addEventListener("mouseup", () => { dragging = false; });
  // right-click a row number: insert / delete rows
  function onGridContext(e) {
    const cellEl = e.target.closest("input.cell");
    if (cellEl) { cellMenu(e, cellEl); return; }
    const rn = e.target.closest("[data-row]");
    if (!rn) return;
    e.preventDefault();
    const s = active(), r = +rn.dataset.row;
    const g = selRange();
    const rows = g && g.c0 === 0 && g.c1 === s.cols.length - 1 && r >= g.r0 && r <= g.r1 ? [g.r0, g.r1] : [r, r];
    const menu = $("row-menu");
    menu.innerHTML = `<button data-act="above">Insert row above</button><button data-act="below">Insert row below</button>
      <button data-act="delete" class="danger">Delete ${rows[1] > rows[0] ? `rows ${rows[0] + 1}–${rows[1] + 1}` : `row ${r + 1}`}</button>`;
    menu.style.left = `${e.clientX}px`; menu.style.top = `${e.clientY}px`; menu.hidden = false;
    menu.querySelectorAll("button").forEach(b => b.onclick = () => {
      recordUndo(true);
      const blank = () => Array(s.cols.length).fill("");
      if (b.dataset.act === "above") { s.data.splice(rows[0], 0, blank()); shiftExcludedRows(s, rows[0], 1); }
      else if (b.dataset.act === "below") { s.data.splice(rows[1] + 1, 0, blank()); shiftExcludedRows(s, rows[1] + 1, 1); }
      else { s.data.splice(rows[0], rows[1] - rows[0] + 1); shiftExcludedRows(s, rows[0], -(rows[1] - rows[0] + 1)); }
      menu.hidden = true; clearSel(); padRows(s); save(); renderGrid(); scheduleRun();
    });
  }
  function cellMenu(e, el) {
    const s = active(), r = +el.dataset.r, c = +el.dataset.c, t = TYPES[s.type];
    if (c === t.textCol) return;
    e.preventDefault();
    const g = selRange();
    const inSel = g && r >= g.r0 && r <= g.r1 && c >= g.c0 && c <= g.c1;
    const cells = [];
    const R = inSel ? g : { r0: r, r1: r, c0: c, c1: c };
    for (let i = R.r0; i <= R.r1; i++) for (let j = R.c0; j <= R.c1; j++) if (j !== t.textCol && isNum(s.data[i][j])) cells.push([i, j]);
    if (!cells.length) return;
    const allEx = cells.every(([i, j]) => isExcluded(s, i, j));
    const menu = $("row-menu");
    menu.innerHTML = `<button data-act="ex">${allEx ? "Include" : "Exclude"} ${cells.length > 1 ? `${cells.length} values` : "this value"}</button>
      <p class="hint" style="margin:4px 8px">${allEx ? "Use it in analyses and graphs again." : "Kept in the table (blue italics) but left out of analyses and graphs."}</p>`;
    menu.style.left = `${e.clientX}px`; menu.style.top = `${e.clientY}px`; menu.hidden = false;
    menu.querySelector("button").onclick = () => {
      recordUndo(true);
      const set = new Set(s.excluded || []);
      cells.forEach(([i, j]) => allEx ? set.delete(exKey(i, j)) : set.add(exKey(i, j)));
      s.excluded = [...set];
      menu.hidden = true; save(); renderGrid(); paintSel(); scheduleRun();
    };
  }
  document.addEventListener("click", e => { if (!e.target.closest("#row-menu")) $("row-menu").hidden = true; });
  // copy / cut / delete for a selected block, wherever keyboard focus is (grid cell or page)
  function blockKey(e) {
    const mod = e.ctrlKey || e.metaKey, k = e.key.toLowerCase();
    if (mod && k === "c") { e.preventDefault(); copyText(selectedTSV()); toast("Copied the selected cells."); return true; }
    if (mod && k === "x") { e.preventDefault(); copyText(selectedTSV()); clearSelectedCells(); return true; }
    if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); clearSelectedCells(); return true; }
    if (e.key === "Escape") { clearSel(); return true; }
    return false;
  }
  document.addEventListener("keydown", e => {
    if (!multiSel() || e.defaultPrevented) return;
    if (e.target !== document.body && !e.target.closest("#grid")) return;
    blockKey(e);
  });

  function onGridKey(e) {
    const el = e.target;
    if (el.dataset.r === undefined) return;
    const r = +el.dataset.r, c = +el.dataset.c;
    if (multiSel() && blockKey(e)) return;
    if (e.shiftKey && ["ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight"].includes(e.key)) {
      if (!selA) selA = { r, c };
      const b = selB || { r, c };
      const d = { ArrowDown: [1, 0], ArrowUp: [-1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] }[e.key];
      const nr = Math.max(0, Math.min(active().data.length - 1, b.r + d[0])), nc = Math.max(0, Math.min(active().cols.length - 1, b.c + d[1]));
      selB = { r: nr, c: nc }; e.preventDefault(); paintSel();
      return;
    }
    let target = null;
    if (e.key === "Enter" || e.key === "ArrowDown") target = cellAt(r + 1, c);
    else if (e.key === "ArrowUp") target = cellAt(r - 1, c);
    else if (e.key === "ArrowRight" && el.selectionStart === el.value.length) target = cellAt(r, c + 1);
    else if (e.key === "ArrowLeft" && el.selectionStart === 0) target = cellAt(r, c - 1);
    if (target) { e.preventDefault(); clearSel(); target.focus(); target.select(); selA = selB = { r: +target.dataset.r, c: +target.dataset.c }; }
  }
  function onGridClick(e) {
    const b = e.target.closest("[data-rm]");
    if (!b) return;
    const s = active(), j = +b.dataset.rm;
    const hasData = s.data.some(r => String(r[j]).trim() !== "");
    if (hasData && !confirm(`Remove the column "${s.cols[j]}" and its data? (You can undo.)`)) return;
    recordUndo(true);
    s.cols.splice(j, 1); s.data.forEach(r => r.splice(j, 1)); dropExcludedCol(s, j);
    save(); renderGrid(); renderOptions(); renderFormat(); scheduleRun();
  }
  function addColumn() {
    const s = active(), t = TYPES[s.type];
    if (s.cols.length >= t.maxCols) return;
    recordUndo(true);
    s.cols.push(t.newColName(s.cols.length)); s.data.forEach(r => r.push(""));
    save(); renderGrid(); renderOptions(); renderFormat();
    const inp = $("grid").querySelector(`input[data-head="${s.cols.length - 1}"]`);
    if (inp) { inp.focus(); inp.select(); }
  }

  // ======================================================================
  // "Help me choose": a short question flow that recommends and creates an analysis
  // ======================================================================
  const NORMAL_Q = (next) => ({ q: "Are the values roughly bell-shaped (normally distributed)?", opts: [
    ["Yes, or I'm not sure", "Most lab measurements are. The app checks normality for you in the results.", next(true)],
    ["No: skewed, ranked or scores", "e.g. very skewed data, ranks, pain scores, counts with many zeros.", next(false)] ] });
  const rec = (title, why, type, setup) => ({ rec: { title, why, type, setup } });
  const GUIDE = { q: "What do you want to do?", opts: [
    ["Compare groups", "e.g. control vs treated; several doses; before vs after", { q: "How are your groups defined?", opts: [
      ["By one factor", "e.g. treatment only (control, drug A, drug B)", { q: "How many groups?", opts: [
        ["Two groups", "", { q: "Are the same subjects measured in both groups?", opts: [
          ["No: different subjects", "e.g. separate mice per group", NORMAL_Q(n => n
            ? rec("Welch's t test", "Compares two independent means without assuming equal spread; a safe default.", "ttest", s => { s.options.design = "independent"; s.options.kind2i = "welch"; })
            : rec("Mann-Whitney test", "Compares two independent groups by ranks; no normality needed.", "ttest", s => { s.options.design = "independent"; s.options.kind2i = "mannwhitney"; }))],
          ["Yes: before/after or matched pairs", "each row is one subject or pair", NORMAL_Q(n => n
            ? rec("Paired t test", "Tests whether the average within-subject difference is zero.", "ttest", s => { s.options.design = "repeated"; s.options.kind2r = "paired"; })
            : rec("Wilcoxon signed-rank test", "Nonparametric paired test on the within-subject differences.", "ttest", s => { s.options.design = "repeated"; s.options.kind2r = "wilcoxon"; }))] ] }],
        ["Three or more groups", "", { q: "Are the same subjects measured in every group?", opts: [
          ["No: different subjects", "", NORMAL_Q(n => n
            ? rec("One-way ANOVA + Tukey", "Tests whether any group mean differs, then compares every pair with Tukey's test. If the results warn that spreads differ, switch to Welch's ANOVA.", "ttest", s => { s.options.design = "independent"; s.cols = ["Group A", "Group B", "Group C"]; s.data = s.data.map(r => [...r, ""]); s.options.kind3i = "ordinary"; })
            : rec("Kruskal-Wallis + Dunn's", "Nonparametric comparison of three or more independent groups.", "ttest", s => { s.options.design = "independent"; s.cols = ["Group A", "Group B", "Group C"]; s.data = s.data.map(r => [...r, ""]); s.options.kind3i = "kruskal"; }))],
          ["Yes: repeated measures", "each row is one subject measured in every column", NORMAL_Q(n => n
            ? rec("Repeated-measures ANOVA + Tukey", "Accounts for subject-to-subject differences; Geisser-Greenhouse corrected.", "ttest", s => { s.options.design = "repeated"; s.cols = ["Time 1", "Time 2", "Time 3"]; s.data = s.data.map(r => [...r, ""]); s.options.kind3r = "rm"; })
            : rec("Friedman test + Dunn's", "Nonparametric repeated-measures comparison.", "ttest", s => { s.options.design = "repeated"; s.cols = ["Time 1", "Time 2", "Time 3"]; s.data = s.data.map(r => [...r, ""]); s.options.kind3r = "friedman"; }))] ] }] ] }],
      ["By two factors", "e.g. treatment × sex, or treatment × time", { q: "Is one factor time points (or conditions) measured on the same subjects?", opts: [
        ["No: every value is a different subject", "", rec("Two-way ANOVA", "Tests both factors and their interaction, then compares groups within each row.", "twoway", s => {})],
        ["Yes: e.g. each animal measured on several days", "", rec("Two-way repeated-measures ANOVA", "Mixed ANOVA for time courses: put time points as row names and groups as columns.", "twoway", s => { s.options.rm = true; s.graph.style = "lines"; s.graph.err = "sem"; })] ] }],
      ["Many separate items (genes, proteins…)", "the same two groups compared for each item", rec("Multiple t tests with FDR", "One test per item with false-discovery-rate correction and a volcano plot.", "twoway", s => { s.options.analysis = "multit"; s.cols = ["Gene", "Control", "Treated"]; })] ] }],
    ["Compare groups with several measurements per subject", "e.g. many cells from each animal (technical replicates)", rec("Nested t test / nested ANOVA", "Uses every replicate but compares groups by subject-to-subject variation, so replicates aren't treated as independent.", "nested", s => {})],
    ["Compare groups from published means", "I only have mean, SD (or SEM) and n for each group", rec("Compare groups (mean, SD, n)", "Exact t tests and ANOVA from summary statistics: one row per group.", "summary", s => {})],
    ["See how my values are distributed", "histogram, Q-Q plot, is it normal?", rec("Frequency distribution + Q-Q plot", "Histogram of each column with a normal curve, a normal Q-Q plot and normality tests. Switch the plot under Format.", "ttest", s => { s.options.mode = "freq"; s.graph.normalCurve = true; })],
    ["Describe my data", "mean, SD, median, normality; or compare to a known value", rec("Column statistics", "Full descriptive statistics for each column; enter a hypothetical value to test against it.", "ttest", s => { s.options.mode = "describe"; })],
    ["Relationship between X and Y", "dose-response, standard curves, correlation, kinetics", { q: "What kind of relationship?", opts: [
      ["A straight line or correlation", "", rec("Linear regression + correlation", "Slope, intercept, R², Pearson and Spearman correlation.", "regression", s => {})],
      ["Dose-response (IC50 / EC50)", "response vs concentration", { q: "Does the response go down or up with dose?", opts: [
        ["Down (inhibition)", "", rec("Dose-response: inhibition (IC50)", "4-parameter logistic fit; enter concentrations as X (the app takes the log).", "regression", s => { s.options.model = "dr_inhibit"; s.graph.logX = true; })],
        ["Up (stimulation)", "", rec("Dose-response: stimulation (EC50)", "4-parameter logistic fit; enter concentrations as X.", "regression", s => { s.options.model = "dr_stim"; s.graph.logX = true; })] ] }],
      ["Read unknowns off a standard curve", "ELISA, BCA, Bradford, qPCR", rec("Standard curve + interpolation", "Enter standards with X, and unknowns with X left blank: their concentrations are read off the fitted line. Switch the fit to 4PL for ELISA.", "regression", s => {})],
      ["Enzyme kinetics, decay, growth or binding", "", rec("Curve fitting", "Choose Michaelis-Menten, exponential decay/growth or one-phase association in the Fit list.", "regression", s => { s.options.model = "michaelis"; })] ] }],
    ["Time until an event", "survival, relapse, time to failure", { q: "What do you want to know?", opts: [
      ["Compare survival between groups", "e.g. treated vs control", rec("Kaplan-Meier survival + log-rank", "Survival curves, median survival, log-rank test and hazard ratio.", "survival", s => {})],
      ["Effect of several factors at once", "e.g. treatment adjusted for age and tumor size", rec("Cox proportional hazards regression", "Hazard ratios for each predictor, adjusted for the others. Columns: time, event (1/0), then predictors.", "multivar", s => { s.options.analysis = "cox"; s.cols = ["Time", "Event (1/0)", "Predictor 1", "Predictor 2"]; s.data = s.data.map(r => [...r, "", ""].slice(0, 4)); })] ] }],
    ["Compare proportions (yes/no outcomes)", "e.g. responders vs non-responders by group", rec("Contingency table", "Fisher's exact test (2×2) or chi-square, with odds ratio and relative risk.", "contingency", s => {})],
    ["Many variables at once", "correlations, predicting an outcome, PCA", { q: "What do you want to learn?", opts: [
      ["How all the variables correlate", "", rec("Correlation matrix", "Every pair of variables, with a heatmap.", "multivar", s => {})],
      ["Predict a measured outcome", "e.g. blood pressure from age, BMI, dose", rec("Multiple linear regression", "Outcome in the first column, predictors to the right.", "multivar", s => { s.options.analysis = "mlr"; })],
      ["Predict a yes/no outcome", "e.g. disease from risk factors", rec("Logistic regression", "Outcome (1/0) in the first column; results are odds ratios.", "multivar", s => { s.options.analysis = "logistic"; })],
      ["Find the main patterns", "reduce many variables to a few", rec("Principal component analysis", "Biplot and scree plot of the main components.", "multivar", s => { s.options.analysis = "pca"; })] ] }],
    ["Evaluate a test or compare two methods", "diagnostic accuracy, method agreement", { q: "Which question?", opts: [
      ["How well does a test separate patients from controls?", "", rec("ROC curve", "Area under the curve, best cutoff, sensitivity and specificity.", "diagnostic", s => {})],
      ["Do two methods give the same values?", "same samples measured twice", rec("Bland-Altman", "Bias and 95% limits of agreement.", "diagnostic", s => { s.options.analysis = "bland_altman"; s.cols = ["Method A", "Method B"]; })] ] }],
    ["Make a multi-panel figure", "combine existing graphs", rec("Figure layout", "Tick the analyses to include; export as one PNG or TIFF.", "layout", s => {})],
  ] };
  let guidePath = [];
  function showGuide() { guidePath = []; renderGuide(); $("guide-backdrop").hidden = false; }
  function renderGuide() {
    let node = GUIDE;
    const crumbs = [];
    guidePath.forEach(i => { crumbs.push(node.opts[i][0]); node = node.opts[i][2]; });
    const back = guidePath.length ? `<button class="ghost small" id="guide-back">← Back</button>` : "<span></span>";
    const path = crumbs.length ? `<div class="guide-path">${crumbs.map(esc).join(" › ")}</div>` : "";
    if (node.rec) {
      const r = node.rec;
      $("guide-body").innerHTML = `${path}<div class="guide-rec">Use: <b>${esc(r.title)}</b><br>${esc(r.why)}</div>
        <div class="guide-foot">${back}<button class="primary small" id="guide-create">Create this analysis</button></div>`;
      $("guide-create").onclick = () => {
        const sh = newSheet(r.type);
        r.setup(sh);
        sh.title = r.title;
        normalize(sh);
        project.sheets.push(sh); project.activeId = sh.id;
        $("guide-backdrop").hidden = true;
        save(); renderAll();
        toast(`Created <b>${esc(r.title)}</b>. Click <b>Example</b> to see sample data, or type/paste your own.`);
      };
    } else {
      $("guide-body").innerHTML = `${path}<div class="guide-q">${esc(node.q)}</div><div class="guide-opts">${node.opts.map(([t, d], i) =>
        `<button data-gi="${i}"><b>${esc(t)}</b>${d ? `<small>${esc(d)}</small>` : ""}</button>`).join("")}</div><div class="guide-foot">${back}<span></span></div>`;
      $("guide-body").querySelectorAll("[data-gi]").forEach(b => b.onclick = () => { guidePath.push(Number(b.dataset.gi)); renderGuide(); });
    }
    const bk = $("guide-back"); if (bk) bk.onclick = () => { guidePath.pop(); renderGuide(); };
  }

  // ======================================================================
  // import data from Excel / CSV
  // ======================================================================
  function readBase64(file) {
    return new Promise((ok, fail) => {
      const r = new FileReader();
      r.onload = () => ok(String(r.result).split(",")[1] || "");
      r.onerror = fail;
      r.readAsDataURL(file);
    });
  }
  async function pzfxSheets(file) {
    const data = await readBase64(file);
    const res = await api("/api/import", { method: "POST", body: JSON.stringify({ filename: file.name, data }) });
    const sheets = res.tables.map(tb => {
      const sh = newSheet(tb.type);
      sh.title = tb.title; sh.cols = tb.cols; sh.data = tb.rows.map(r => r.map(v => String(v ?? "")));
      Object.assign(sh.options, tb.options || {});
      if (tb.type === "regression" && tb.options && tb.options.yMode === "datasets") sh.options.cmpParam = "";
      return normalize(sh);
    });
    return { sheets, notes: res.notes || [] };
  }
  async function importData(file) {
    const s = active(), t = TYPES[s.type];
    if (/\.pzfx$/i.test(file.name)) {
      try {
        const { sheets, notes } = await pzfxSheets(file);
        project.sheets.push(...sheets); project.activeId = sheets[0].id; save(); renderAll();
        toast(`Imported ${sheets.length} table${sheets.length === 1 ? "" : "s"} from the Prism file as new analyses.${notes.length ? " " + notes.map(esc).join(" ") : ""}`);
      } catch (e) { toast(esc(e.message || "Import failed.")); }
      return;
    }
    try {
      const data = await readBase64(file);
      let res = await api("/api/import", { method: "POST", body: JSON.stringify({ filename: file.name, data }) });
      if (res.sheets && res.sheets.length > 1) {
        const pick = prompt(`This workbook has ${res.sheets.length} sheets. Type the number of the one to import:\n\n` +
          res.sheets.map((n, i) => `${i + 1}. ${n}`).join("\n"), "1");
        if (pick === null) return;
        const name = res.sheets[Math.max(0, Math.min(res.sheets.length - 1, (parseInt(pick, 10) || 1) - 1))];
        if (name !== res.sheet) res = await api("/api/import", { method: "POST", body: JSON.stringify({ filename: file.name, data, sheet: name }) });
      }
      let rows = res.rows;
      if (!rows.length) { toast("That file has no data."); return; }
      if (s.data.some(r => r.some(v => String(v).trim() !== "")) && !confirm("Replace the data in this table with the file's data? (You can undo.)")) return;
      // first row is a header if it has text where the rows below have numbers
      const first = rows[0], rest = rows.slice(1);
      const header = rest.length > 0 && first.some((v, j) => j !== t.textCol && v !== "" && !isNum(v) && rest.some(r => isNum(r[j])));
      const width = Math.min(t.maxCols, Math.max(t.minCols, ...rows.map(r => r.length)));
      recordUndo(true);
      s.cols = Array.from({ length: width }, (_, j) => (header && first[j]) || (j < s.cols.length ? s.cols[j] : t.newColName(j)));
      s.data = (header ? rest : rows).map(r => Array.from({ length: width }, (_, j) => r[j] ?? ""));
      s.excluded = [];
      padRows(s); save(); renderGrid(); renderOptions(); renderFormat(); scheduleRun();
      const cut = Math.max(...rows.map(r => r.length)) > t.maxCols ? ` Only the first ${t.maxCols} columns fit this table.` : "";
      toast(`Imported ${s.data.filter(r => r.some(v => v !== "")).length} rows from <b>${esc(file.name)}</b>${res.sheet ? ` (${esc(res.sheet)})` : ""}.${cut}`);
    } catch (e) { toast(esc(e.message || "Import failed.")); }
  }

  // ======================================================================
  // transform / normalize into a new analysis
  // ======================================================================
  const TRANSFORMS = [
    ["minmax", "Normalize each column to 0–100%", "Smallest value → 0%, largest → 100%."],
    ["ref", "Normalize to chosen 0% and 100% values", "e.g. 0% = background, 100% = untreated control."],
    ["baseline", "Percent of the first row", "Each column divided by its first value × 100 (e.g. % of time 0)."],
    ["log10", "Log10", "Values ≤ 0 become blank."],
    ["ln", "Natural log (ln)", "Values ≤ 0 become blank."],
    ["recip", "Reciprocal (1/Y)", "Zero becomes blank."],
    ["sqrt", "Square root", "Negative values become blank."],
    ["linear", "Y × K + C", "Multiply and/or add a constant (e.g. unit conversion)."],
  ];
  // which columns hold Y values (numbers to transform) for each analysis type
  const yCols = s => s.type === "regression" || s.type === "survival" || s.type === "twoway" || s.type === "contingency" || s.type === "nested"
    ? s.cols.map((_, j) => j).slice(1) : s.cols.map((_, j) => j);
  function showTransform() {
    const s = active();
    if (s.type === "survival" || s.type === "contingency") { toast("Transforms aren't meaningful for survival or contingency data."); return; }
    const op = s._tf || "minmax";
    $("tf-body").innerHTML = TRANSFORMS.map(([k, name, d]) => `<label class="choice ${op === k ? "on" : ""}"><input type="radio" name="tf" value="${k}" ${op === k ? "checked" : ""}><span><b>${name}</b><small>${d}</small></span></label>`).join("") +
      `<div class="row" id="tf-params"></div>` + (s.type === "regression" ? `<label class="check"><input type="checkbox" id="tf-x"> Transform X instead of Y (log10 / ln / reciprocal / square root only)</label>` : "");
    const params = () => {
      const k = $("tf-body").querySelector("input[name=tf]:checked").value;
      $("tf-params").innerHTML = k === "ref" ? `<label>0% =</label><input type="text" id="tf-a" value="0" style="width:80px"><label>100% =</label><input type="text" id="tf-b" value="100" style="width:80px">`
        : k === "linear" ? `<label>K =</label><input type="text" id="tf-a" value="1" style="width:80px"><label>C =</label><input type="text" id="tf-b" value="0" style="width:80px">` : "";
      $("tf-body").querySelectorAll(".choice").forEach(c => c.classList.toggle("on", c.querySelector("input").checked));
    };
    $("tf-body").querySelectorAll("input[name=tf]").forEach(r => r.onchange = params);
    params();
    $("transform-backdrop").hidden = false;
  }
  function applyTransform() {
    const s = active(), k = $("tf-body").querySelector("input[name=tf]:checked").value;
    const a = num($("tf-a") && $("tf-a").value), b = num($("tf-b") && $("tf-b").value);
    const onX = $("tf-x") && $("tf-x").checked;
    if (onX && !["log10", "ln", "recip", "sqrt"].includes(k)) { toast("For X, choose log10, ln, reciprocal or square root."); return; }
    if (k === "ref" && (a === null || b === null || a === b)) { toast("Enter two different numbers for 0% and 100%."); return; }
    if (k === "linear" && (a === null || b === null)) { toast("Enter numbers for K and C."); return; }
    const cols = onX ? [0] : yCols(s);
    const copy = JSON.parse(JSON.stringify(s));
    copy.id = uid();
    const name = TRANSFORMS.find(t => t[0] === k)[1];
    copy.title = `${s.title} (${onX ? "X: " : ""}${name.toLowerCase().replace("normalize each column to ", "normalized ").replace("normalize to chosen 0% and 100% values", "normalized")})`;
    const f = { log10: v => v > 0 ? Math.log10(v) : null, ln: v => v > 0 ? Math.log(v) : null, recip: v => v !== 0 ? 1 / v : null,
      sqrt: v => v >= 0 ? Math.sqrt(v) : null, linear: v => v * a + b, ref: v => (v - a) / (b - a) * 100 };
    cols.forEach(j => {
      const vals = copy.data.map(r => num(r[j]));
      const present = vals.filter(v => v !== null);
      if (!present.length) return;
      let fn = f[k];
      if (k === "minmax") { const lo = Math.min(...present), hi = Math.max(...present); fn = v => hi === lo ? null : (v - lo) / (hi - lo) * 100; }
      if (k === "baseline") { const first = present[0]; fn = v => first ? v / first * 100 : null; }
      copy.data.forEach((r, i) => { if (vals[i] !== null) { const out = fn(vals[i]); r[j] = out === null || !isFinite(out) ? "" : String(Number(out.toPrecision(10))); } });
    });
    let dropped = 0;
    if (onX && copy.type === "regression") {
      copy.options.xIsLog = k === "log10"; copy.graph.logX = false;
      // a blank X means "unknown sample" in XY tables, so rows whose X has no transform are left out
      copy.data = copy.data.filter((r, i) => { const bad = num(s.data[i][0]) !== null && r[0] === ""; if (bad) dropped++; return !bad; });
      padRows(copy);
    }
    if (["minmax", "ref", "baseline"].includes(k) && copy.graph.ylabel !== undefined) copy.graph.ylabel = (copy.graph.ylabel || copy.cols[1] || "Response").replace(/ ?\(%\)$/, "") + " (%)";
    const idx = project.sheets.findIndex(x => x.id === s.id);
    project.sheets.splice(idx + 1, 0, copy);
    project.activeId = copy.id; s._tf = k;
    $("transform-backdrop").hidden = true;
    save(); renderAll();
    toast(`Created <b>${esc(copy.title)}</b>${dropped ? `. ${dropped} row(s) left out (X couldn't be transformed, e.g. log of 0)` : ""}`);
  }

  // ======================================================================
  // options & graph format panel
  // ======================================================================
  function renderOptions() {
    const s = active(), box = $("options");
    box.innerHTML = TYPES[s.type].renderOptions(s);
    box.querySelectorAll("input[type=radio]").forEach(r => r.onchange = () => { s.options[r.name] = r.value; save(); renderOptions(); scheduleRun(); });
    box.querySelectorAll("[data-set]").forEach(b => b.onclick = () => {
      const [k, v] = b.dataset.set.split(":");
      s.options[k] = v; save(); renderGrid(); renderOptions(); renderFormat(); scheduleRun();
    });
    box.querySelectorAll("[data-design]").forEach(b => b.onclick = () => {
      s.options.design = b.dataset.design;
      if (s.options.design !== "repeated" && s.graph.style === "lines") s.graph.style = "dots";
      save(); renderOptions(); renderFormat(); scheduleRun();
    });
    const a = $("opt-alpha"); if (a) a.onchange = e => { s.options.alpha = Number(e.target.value); save(); scheduleRun(); };
    const m = $("opt-model");
    if (m) m.onchange = e => {
      s.options.model = e.target.value;
      if (s.options.model === "custom" && !s.options.equation) { s.options.equation = "Y = A*exp(-K*X) + C"; s.options.eqParams = null; }
      const info = modelInfo(s.options.model);
      s.graph.logX = !!(info && info.log_x && !s.options.xIsLog);
      const c = modelInfo(s.options.compare);
      if (!info || !c || c.id === info.id || c.log_x !== info.log_x) s.options.compare = "";
      save(); renderOptions(); renderFormat(); scheduleRun();
    };
    wireParamInputs(s);
    box.querySelectorAll("[data-opt]").forEach(cb => cb.onchange = () => { s.options[cb.dataset.opt] = cb.checked; save(); renderOptions(); if (s.type === "layout") drawPlot(); else scheduleRun(); });
    box.querySelectorAll("[data-panel]").forEach(cb => cb.onchange = () => {
      const list = (s.options.panels = (s.options.panels || []).filter(id => id !== cb.dataset.panel));
      if (cb.checked) list.push(cb.dataset.panel);
      save(); renderOptions(); scheduleRun();
    });
    const nc = $("opt-ncol"); if (nc) nc.onchange = e => { s.options.ncol = Number(e.target.value); save(); drawPlot(); };
    box.querySelectorAll("[data-num]").forEach(inp => inp.oninput = () => {
      const v = inp.value.trim(); s.options[inp.dataset.num] = v; inp.classList.toggle("bad", v !== "" && !isNum(v)); save(); scheduleRun();
    });
    const ct = $("opt-cmpto");
    if (ct) ct.onchange = e => {
      s.options.compareTo = e.target.value;
      const ph = s.options.posthoc || "tukey";
      if (s.options.compareTo === "control" && ph === "tukey") s.options.posthoc = "dunnett";
      if (s.options.compareTo === "all" && ph === "dunnett") s.options.posthoc = "tukey";
      save(); renderOptions(); scheduleRun();
    };
    const tw = $("opt-twcmp"); if (tw) tw.onchange = e => { s.options.twCompare = e.target.value; save(); scheduleRun(); };
    const ph = $("opt-posthoc"); if (ph) ph.onchange = e => { s.options.posthoc = e.target.value; save(); scheduleRun(); };
    const om = $("opt-outmethod"); if (om) om.onchange = e => { s.options.outlierMethod = e.target.value; save(); renderOptions(); scheduleRun(); };
    const rq = $("opt-routq"); if (rq) rq.onchange = e => { s.options.routQ = e.target.value; save(); scheduleRun(); };
    const hy = $("opt-hyp");
    if (hy) hy.oninput = () => { s.options.hypothetical = hy.value.trim(); hy.classList.toggle("bad", hy.value.trim() !== "" && !isNum(hy.value)); save(); scheduleRun(); };
    const bl = $("opt-baseline");
    if (bl) bl.oninput = () => { s.options.baseline = bl.value.trim(); bl.classList.toggle("bad", bl.value.trim() !== "" && !isNum(bl.value)); save(); scheduleRun(); };
    const eq = $("opt-equation");
    if (eq) {
      let t = null;
      eq.oninput = () => { s.options.equation = eq.value; save(); clearTimeout(t); t = setTimeout(() => { checkEquation(s); scheduleRun(); }, 400); };
      if (!s.options.eqParams) checkEquation(s);
    }
    const cp = $("opt-cmpparam"); if (cp) cp.onchange = e => { s.options.cmpParam = e.target.value; save(); scheduleRun(); };
    const cmp = $("opt-compare");
    if (cmp) cmp.onchange = e => { s.options.compare = e.target.value; save(); scheduleRun(); };
    const mk = $("opt-mtkind"); if (mk) mk.onchange = e => { s.options.mtKind = e.target.value; save(); scheduleRun(); };
    const oq = $("opt-q"); if (oq) oq.onchange = e => { s.options.q = Number(e.target.value); save(); scheduleRun(); };
    const lg = $("opt-xislog");
    if (lg) lg.onchange = e => { s.options.xIsLog = e.target.checked; s.graph.logX = !e.target.checked; save(); renderFormat(); scheduleRun(); };
  }

  function seriesNames(s) {
    if (s.type === "ttest") return filledCols(s).map(j => s.cols[j] || `Group ${letter(j)}`);
    if (s.type === "regression" && s.options.yMode === "datasets") return s.cols.slice(1).map((c, j) => c || `Y${j + 1}`);
    if (s.type === "regression") return ["Curve", ...(s.options.compare ? ["Comparison curve"] : []), "Unknowns"];
    if (s.type === "layout") return [];
    if (s.type === "summary") return s.data.filter(r => isNum(r[1])).map((r, i) => String(r[0] || `Group ${i + 1}`));
    if (s.type === "nested") return [...new Set(s.data.map(r => String(r[0] ?? "").trim()).filter(Boolean))];
    if (s.type === "multivar") return (s.options.analysis || "correlation") === "correlation" ? [] : s.options.analysis === "logistic" ? ["Curve"] : s.options.analysis === "pca" ? ["Points", "Loadings"] : ["Points"];
    if (s.type === "twoway" && s.options.analysis === "multit") return ["Discoveries"];
    if (s.type === "diagnostic") return s.options.analysis === "roc" ? ["Curve", "Best cutoff"] : ["Points"];
    return s.cols.slice(1).map((c, j) => c || (s.type === "contingency" ? `Outcome ${j + 1}` : `Group ${letter(j)}`));
  }
  const toHex = c => /^#[0-9a-f]{6}$/i.test(c) ? c : "#000000";

  function renderFormat() {
    const s = active(), g = s.graph;
    const head = label => ({ kind: "head", label });
    const rng = (k, label, min, max, step = 1) => ({ k, label, kind: "range", min, max, step });
    const typeCtrls = TYPES[s.type].graphControls(s);
    const ctrls = [head("Graph"), txt("title", "Graph title"), ...typeCtrls,
      txt("ymin", "Y min", "auto"), txt("ymax", "Y max", "auto"), txt("ytick", "Y tick every", "auto"), chk("logY", "Log Y axis"),
      head("Text"), sel("fontFamily", "Font", [["Arial", "Arial"], ["Helvetica", "Helvetica"], ["Times New Roman", "Times New Roman"], ["Calibri", "Calibri"], ["Verdana", "Verdana"], ["Georgia", "Georgia"], ["Courier New", "Courier New"]]),
      rng("fontSize", "Base font size", 8, 24), txt("titleSize", "Axis title size", "auto"), txt("tickSize", "Tick label size", "auto"),
      { k: "textColor", label: "Text & axis color", kind: "color" },
      head("Colors"), sel("palette", "Palette", [["vivid", "Vivid"], ["colorblind", "Colorblind-safe"], ["classic", "Classic"], ["pastel", "Pastel"], ["grayscale", "Grayscale"]]),
      head("Points"), sel("pointSymbol", "Shape", [["default", "Default"], ["circle", "Circle"], ["square", "Square"], ["diamond", "Diamond"], ["triangle-up", "Triangle"],
        ["circle-open", "Open circle"], ["square-open", "Open square"], ["triangle-up-open", "Open triangle"], ["x", "Cross"]]),
      rng("pointSize", "Size", 2, 20), rng("pointOpacity", "Opacity", 0.1, 1, 0.05), rng("pointLine", "Outline width", 0, 3, 0.25),
      { k: "pointLineColor", label: "Outline color", kind: "color" },
      head("Lines & error bars"), rng("lineScale", "Line thickness", 0.25, 4, 0.25), rng("errWidth", "Error bar thickness", 0.5, 4, 0.25), rng("capWidth", "Error bar cap width", 0, 20),
      head("Bars & fills"), sel("barOpacity", "Fill opacity", [["", "Automatic"], ["0", "0% (outline only)"], ["0.15", "15%"], ["0.3", "30%"], ["0.5", "50%"], ["0.75", "75%"], ["1", "100% (solid)"]]),
      rng("barLine", "Outline width", 0, 4, 0.25), sel("pattern", "Pattern", [["none", "None"], ["/", "Diagonal ////"], ["\\", "Diagonal \\\\"], ["x", "Cross-hatch"], [".", "Dots"], ["-", "Horizontal"], ["|", "Vertical"], ["vary", "Different per series"]]),
      head("Axes & background"), rng("axisWidth", "Axis thickness", 0.5, 4, 0.25), sel("tickDir", "Ticks", [["outside", "Outside"], ["inside", "Inside"], ["none", "None"]]),
      rng("tickLen", "Tick length", 0, 12), chk("minorTicks", "Minor ticks"), chk("grid", "Gridlines"),
      sel("tickAngle", "X label angle", [["auto", "Automatic"], ["0", "Horizontal"], ["-30", "Slanted 30°"], ["-45", "Slanted 45°"], ["-90", "Vertical"]]),
      ...(["ttest", "summary", "twoway", "contingency", "nested"].includes(s.type) ? [txt("breakFrom", "Break Y axis from", "none"), txt("breakTo", "… to", "none"),
        rng("breakSize", "Lower part height %", 15, 80, 5)] : []), sel("bg", "Background", [["white", "White"], ["transparent", "Transparent (for figures)"], ["light", "Light gray plot area"]]),
      sel("legendPos", "Legend", [["auto", "Automatic"], ["tr", "Top right (inside)"], ["tl", "Top left (inside)"], ["outside", "Right (outside)"], ["top", "Above graph"], ["bottom", "Below graph"], ["hide", "Hide"]]),
      head("Text labels"), { kind: "notes" },
      head("Export"), sel("exportSize", "Size", Object.entries(EXPORT_SIZES).map(([k, v]) => [k, v[2]])),
      sel("exportDpi", "Resolution (PNG/TIFF)", [["150", "150 DPI (screen)"], ["300", "300 DPI (print)"], ["600", "600 DPI (high)"]])];
    $("graph-format").innerHTML = ctrls.map(c => {
      const v = g[c.k];
      if (c.kind === "select") return `<label>${c.label}<select data-g="${c.k}">${c.opts.map(([o, l]) => `<option value="${o}" ${v === o ? "selected" : ""}>${l}</option>`).join("")}</select></label>`;
      if (c.kind === "check") return `<label class="check"><input type="checkbox" data-g="${c.k}" ${v ? "checked" : ""}> ${c.label}</label>`;
      if (c.kind === "range") return `<label>${c.label} <span class="rv">${v}</span><input type="range" data-g="${c.k}" min="${c.min}" max="${c.max}" step="${c.step || 1}" value="${v}"></label>`;
      if (c.kind === "head") return `<div class="fhead">${c.label}</div>`;
      if (c.kind === "notes") return `<div class="wide notes"><p class="hint">Tip: click any title, axis title, legend entry or label on the graph to edit it; drag the legend or a label to move it.</p>
        ${(g.notes || []).map((n, i) => `<div class="note-row"><input type="text" data-note="${i}" value="${esc(n.text || "")}" placeholder="Label text"><input type="number" data-note-size="${i}" value="${esc(n.size ?? "")}" placeholder="size" min="6" max="48"><button class="icon" data-note-del="${i}" title="Remove this label">✕</button></div>`).join("")}
        <div class="row"><button class="ghost small" id="btn-add-note">+ Add text label</button>${g.axisText || g.legendNames || g.legendXY ? `<button class="ghost small" id="btn-reset-edits" title="Undo text and legend edits made on the graph">Reset graph edits</button>` : ""}</div></div>`;
      if (c.kind === "color") return `<label>${c.label}<input type="color" data-g="${c.k}" value="${toHex(v)}"></label>`;
      return `<label>${c.label}<input type="text" data-g="${c.k}" value="${esc(v ?? "")}" placeholder="${esc(c.ph || "")}"></label>`;
    }).join("") + (!seriesNames(s).length ? "" : `<div class="wide colors"><span>Series colors</span>${seriesNames(s).map((n, i) =>
      `<label class="swatch" title="${esc(n)}"><input type="color" data-color="${esc(n)}" value="${toHex(color(g, i, n))}"><span>${esc(n)}</span></label>`).join("")}
      ${g.colors && Object.keys(g.colors).length ? `<button class="ghost small" id="btn-reset-colors">Reset</button>` : ""}</div>`);
    $("graph-format").querySelectorAll("[data-color]").forEach(el => {
      el.oninput = () => { g.colors = { ...(g.colors || {}), [el.dataset.color]: el.value }; save(); drawPlot(); };
      el.onchange = () => renderFormat();
    });
    const fmtBox = $("graph-format");
    const an = $("btn-add-note");
    if (an) an.onclick = () => { g.notes = [...(g.notes || []), { text: "Label", x: 0.5, y: 0.95 }]; save(); renderFormat(); drawPlot(); };
    const re = $("btn-reset-edits");
    if (re) re.onclick = () => { delete g.axisText; delete g.legendNames; delete g.legendXY; save(); renderFormat(); drawPlot(); };
    fmtBox.querySelectorAll("[data-note]").forEach(el => el.oninput = () => { g.notes[+el.dataset.note].text = el.value; save(); drawPlot(); });
    fmtBox.querySelectorAll("[data-note-size]").forEach(el => el.oninput = () => { g.notes[+el.dataset.noteSize].size = el.value; save(); drawPlot(); });
    fmtBox.querySelectorAll("[data-note-del]").forEach(el => el.onclick = () => { g.notes.splice(+el.dataset.noteDel, 1); save(); renderFormat(); drawPlot(); });
    const rc = $("btn-reset-colors");
    if (rc) rc.onclick = () => { g.colors = {}; save(); renderFormat(); drawPlot(); };
    $("graph-format").querySelectorAll("[data-g]").forEach(el => {
      el.oninput = el.onchange = () => {
        g[el.dataset.g] = el.type === "checkbox" ? el.checked : el.type === "range" ? Number(el.value) : el.value;
        if (/label$/.test(el.dataset.g)) delete g.axisText;   // a typed axis label replaces one edited on the graph
        if (el.dataset.g === "legendPos") delete g.legendXY;
        if (el.type === "range") el.previousElementSibling.textContent = el.value;
        save(); drawPlot();
      };
    });
  }

  // ======================================================================
  // running analyses
  // ======================================================================
  let lastResult = null, lastError = null, runTimer = null, runSeq = 0;
  function scheduleRun() { clearTimeout(runTimer); runTimer = setTimeout(run, 250); }
  async function run() {
    const s = active(), seq = ++runSeq;
    if (TYPES[s.type].runCustom) {
      try { const r = await TYPES[s.type].runCustom(s); if (seq !== runSeq) return; lastResult = r; lastError = null; }
      catch (e) { if (seq !== runSeq) return; lastResult = null; lastError = e.message; }
      renderResults(); drawPlot();
      return;
    }
    const [url, body] = TYPES[s.type].request(masked(s));
    try {
      const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const json = await res.json();
      if (seq !== runSeq) return;
      if (!res.ok) { lastResult = null; lastError = json.detail || "Something went wrong."; }
      else { lastResult = json; lastError = null; }
    } catch { if (seq !== runSeq) return; lastResult = null; lastError = "Can't reach the analysis engine. Is the app still running?"; }
    if (s.type === "ttest" || s.type === "summary") renderOptions(); // options depend on number of filled groups
    renderResults(); drawPlot();
  }

  function renderResults() {
    const s = active(), box = $("results");
    if (lastError) { box.innerHTML = T.summary("err", `<b>Not enough to analyze yet.</b> ${esc(lastError)}`); return; }
    if (!lastResult) { box.innerHTML = ""; return; }
    box.innerHTML = TYPES[s.type].renderResults(lastResult, s);
    const nx = (s.excluded || []).length;
    if (nx) box.insertAdjacentHTML("afterbegin", `<p class="note warn" style="margin-top:0">${nx} excluded value${nx === 1 ? " is" : "s are"} not used (shown in <i>blue italics</i> in the table). Right-click to include again.</p>`);
    let rep = null;
    try { rep = reportText(lastResult, s); } catch { rep = null; }
    if (rep && lastResult.rout_q) rep.methods += ` Outliers were identified with the ROUT method (Q = ${fmt(lastResult.rout_q * 100)}%; Motulsky & Brown, 2006) and ${(lastResult.outliers || []).length ? `${lastResult.outliers.length} point${lastResult.outliers.length > 1 ? "s were" : " was"} excluded from the fit` : "none were found"}.`;
    else if (rep && lastResult.outliers && lastResult.outliers[0] && lastResult.outliers[0].method === "rout") rep.methods += ` Outliers were screened with the ROUT method (Q = ${fmt(lastResult.outliers[0].q * 100)}%; Motulsky & Brown, 2006).`;
    if (rep) {
      box.insertAdjacentHTML("beforeend", `<details class="report"><summary>Text for your paper</summary>
        <div class="report-block"><div class="opt-label">Methods</div><p id="rep-methods">${rep.methods}</p></div>
        <div class="report-block"><div class="opt-label">Results</div><p id="rep-results">${rep.results}</p></div>
        <button class="ghost small" id="btn-copy-report">Copy text</button>
        <p class="note">Check the wording fits your study. Replace "Erwin's Hypothesis" with the version you used if your journal asks.</p></details>`);
      $("btn-copy-report").onclick = async () => {
        const text = `${$("rep-methods").textContent}\n\n${$("rep-results").textContent}`;
        try { await navigator.clipboard.writeText(text); } catch {
          const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove();
        }
        toast("Methods and results text copied.");
      };
    }
  }

  // ======================================================================
  // "Text for your paper": methods + results sentences in standard reporting style
  // ======================================================================
  const apaP = p => p == null ? "P = n/a" : p < 0.0001 ? "P < 0.0001" : p < 0.001 ? `P = ${p.toFixed(4)}` : `P = ${p.toFixed(3)}`;
  const r2 = (v, d = 2) => v == null || Number.isNaN(v) ? "n/a" : Math.abs(v) >= 1000 || (Math.abs(v) < 0.01 && v !== 0) ? fmt(v, 3) : Number(v).toFixed(d);
  const ALPHA = r => `P < ${r.alpha ?? 0.05} was considered statistically significant.`;
  const SW = "Erwin's Hypothesis";
  function reportText(r, s) {
    const pct = Math.round((1 - (r.alpha ?? 0.05)) * 100);
    const errName = { sd: "mean ± SD", sem: "mean ± SEM", ci95: "mean ± 95% CI" }[s.graph.err] || "mean ± SD";
    if (s.type === "ttest" && r.kind === "freq") {
      const m = `Frequency distributions were tabulated with a bin width of ${fmt(r.bin_width)} (first bin starting at ${fmt(r.bin_start)}). Normality was assessed with the Shapiro-Wilk test and normal Q-Q plots (${SW}).`;
      const res = r.groups.map(g => `${esc(g.name)}: ${r2(g.mean)} ± ${g.sd == null ? "n/a" : r2(g.sd)} (mean ± SD, n = ${g.n})${g.shapiro ? `, Shapiro-Wilk W = ${r2(g.shapiro.W, 3)}, ${apaP(g.shapiro.p)}` : ""}`).join("; ") + ".";
      return { methods: m, results: res };
    }
    if (s.type === "ttest" && r.kind === "describe") {
      const m = `Descriptive statistics were calculated for each group, and normality was assessed with the Shapiro-Wilk test${r.hypothetical != null ? `; each group was compared with a hypothetical value of ${fmt(r.hypothetical)} using a one-sample t test` : ""} (${SW}).`;
      const res = r.groups.map(g => `${esc(g.name)}: ${r2(g.mean)} ± ${r2(g.sd)} (mean ± SD, n = ${g.n})${g.one_sample_t ? `, t(${g.one_sample_t.df}) = ${r2(g.one_sample_t.t)}, ${apaP(g.one_sample_t.p)}` : ""}`).join("; ") + ".";
      return { methods: m, results: res };
    }
    if (s.type === "nested") {
      const two = r.n_groups === 2, c = r.comparisons[0];
      return { methods: `Because several replicate measurements were made on each subject, groups were compared with a ${two ? "nested t test" : "nested one-way ANOVA"} (linear mixed-effects model with subject as a random effect, REML; denominator degrees of freedom = subjects − groups)${two ? "" : ", followed by Tukey's multiple comparisons"}. ${ALPHA(r)} Analyses were performed in ${SW}.`,
        results: two ? `${esc(c.b)} differed ${c.p < r.alpha ? "significantly" : "not significantly"} from ${esc(c.a)} (difference ${r2(c.diff)}, 95% CI ${r2(c.ci[0])} to ${r2(c.ci[1])}; t(${r.df_d}) = ${r2(Math.abs(c.t))}, ${apaP(c.p)}; ${r.n_subjects} subjects, ${r.n_values} measurements).`
          : `Group means differed ${r.p < r.alpha ? "significantly" : "not significantly"} (F(${r.df_n}, ${r.df_d}) = ${r2(r.F)}, ${apaP(r.p)}; ${r.n_subjects} subjects, ${r.n_values} measurements).${r.comparisons.filter(x => x.significant).length ? ` Tukey's test: ${r.comparisons.filter(x => x.significant).map(x => `${esc(x.b)} vs ${esc(x.a)}, ${apaP(x.p)}`).join("; ")}.` : ""}` };
    }
    if (s.type === "summary") s = { ...s, type: "ttest" };
    if (s.type === "ttest" && r.n_groups === 2) {
      const [a, b] = r.groups.map(g => esc(g.name));
      const test = { welch: "Welch's t test", unpaired: "an unpaired t test", paired: "a paired t test", mannwhitney: "the Mann-Whitney test", wilcoxon: "the Wilcoxon matched-pairs signed-rank test" }[r.kind] || r.test_name;
      const np = r.kind === "mannwhitney" || r.kind === "wilcoxon";
      const methods = `${a} and ${b} were compared using ${test} (two-tailed). Data are presented as ${np ? "median (interquartile range) where appropriate, and " : ""}${errName}. ${ALPHA(r)} Analyses were performed in ${SW}.`;
      const stat = r.df != null ? `${r.statistic_name}(${r2(r.df, Number.isInteger(r.df) ? 0 : 1)}) = ${r2(r.statistic)}` : `${r.statistic_name} = ${r2(r.statistic, 1)}`;
      const dir = r.difference > 0 ? "higher than" : "lower than";
      const what = np ? (r.kind === "wilcoxon" ? "median difference" : "median difference") : "mean difference";
      const results = r.significant
        ? `${b} was significantly ${dir} ${a} (${what} ${r2(r.difference)}${r.ci_low != null ? `, ${pct}% CI ${r2(r.ci_low)} to ${r2(r.ci_high)}` : ""}; ${stat}, ${apaP(r.p)}).`
        : `${b} and ${a} did not differ significantly (${what} ${r2(r.difference)}${r.ci_low != null ? `, ${pct}% CI ${r2(r.ci_low)} to ${r2(r.ci_high)}` : ""}; ${stat}, ${apaP(r.p)}).`;
      return { methods, results };
    }
    if (s.type === "ttest") {
      const phName = { tukey: "Tukey's multiple comparisons test", dunnett: "Dunnett's multiple comparisons test (each group vs control)", holm: "the Holm-Šídák multiple comparisons test",
        sidak: "Šídák's multiple comparisons test", bonferroni: "Bonferroni's multiple comparisons test", lsd: "uncorrected Fisher's LSD tests" }[r.posthoc || "tukey"]
        + (r.compare_to === "control" && r.posthoc !== "dunnett" ? " comparing each group with the control" : "");
      const test = { ordinary: `one-way ANOVA followed by ${phName}`, welch: "Welch's ANOVA followed by the Games-Howell test",
        kruskal: `the Kruskal-Wallis test followed by Dunn's multiple comparisons test${r.compare_to === "control" ? " (each group vs control)" : ""}`, rm: "repeated-measures one-way ANOVA with the Geisser-Greenhouse correction, followed by Tukey's multiple comparisons test",
        friedman: "the Friedman test followed by Dunn's multiple comparisons test" }[r.kind];
      const methods = `Groups were compared using ${test}. Data are presented as ${errName}. ${ALPHA(r)} Analyses were performed in ${SW}.`;
      const main = r.kind === "kruskal" ? `H(${r.df_between}) = ${r2(r.H)}` : r.kind === "friedman" ? `χ²(${r.df_between}) = ${r2(r.chi2)}`
        : `F(${r2(r.df_between, Number.isInteger(r.df_between) ? 0 : 2)}, ${r2(r.df_within, Number.isInteger(r.df_within) ? 0 : 2)}) = ${r2(r.F)}`;
      const sig = r.comparisons.filter(c => c.significant);
      const pairs = sig.slice(0, 6).map(c => `${esc(c.a)} and ${esc(c.b)} (${apaP(c.p)})`).join("; ");
      const results = r.significant ? `There was a significant difference among groups (${main}, ${apaP(r.p)}${r.kind === "rm" ? `, ε = ${r2(r.epsilon)}` : ""}).${sig.length ? ` Post hoc comparisons showed differences between ${pairs}${sig.length > 6 ? ", and others" : ""}.` : " No pairwise comparison reached significance."}`
        : `There was no significant difference among groups (${main}, ${apaP(r.p)}).`;
      return { methods, results };
    }
    if (s.type === "twoway" && r.test_name === "Multiple t tests") {
      const test = { welch: "Welch's t tests", unpaired: "unpaired t tests", mannwhitney: "Mann-Whitney tests" }[r.kind] || "t tests";
      return { methods: `Each ${esc(s.cols[0] || "row")} was compared between ${esc(r.names[0])} and ${esc(r.names[1])} using ${test}; P values were adjusted for multiple comparisons with the Benjamini-Hochberg false discovery rate (Q = ${r.q_level * 100}%). Analyses were performed in ${SW}.`,
        results: `${r.n_discoveries} of ${r.items.length} ${r.n_discoveries === 1 ? "was" : "were"} identified as discoveries${r.n_discoveries ? ` (${r.items.filter(i => i.discovery).sort((x, y) => x.p - y.p).slice(0, 8).map(i => esc(i.name)).join(", ")})` : ""}.` };
    }
    if (s.type === "twoway") {
      const t = Object.fromEntries(r.table.map(x => [x.source, x]));
      const rowF = esc(s.cols[0] || "row factor");
      const f = x => `F(${x.df}, ${x.dfd ?? t.Residual.df}) = ${r2(x.F)}, ${apaP(x.p)}`;
      return { methods: `Data were analyzed by ${r.rm ? `two-way repeated-measures (mixed) ANOVA with ${rowF} as the within-subject factor and the Geisser-Greenhouse correction` : "two-way ANOVA"}, followed by ${esc(r.posthoc_name.split(" (")[0])} ${{ within_cols: `comparing levels of ${rowF} within each group`, col_means: "comparing group means averaged over " + rowF, row_means: `comparing ${rowF} means averaged over groups` }[r.compare] || `comparing groups at each level of ${rowF}`}. Data are presented as ${errName}. ${ALPHA(r)} Analyses were performed in ${SW}.`,
        results: `There was ${t.Interaction.p < r.alpha ? "a significant" : "no significant"} interaction between group and ${rowF} (${f(t.Interaction)}). The main effect of group was ${t["Column factor"].p < r.alpha ? "" : "not "}significant (${f(t["Column factor"])}), and the main effect of ${rowF} was ${t["Row factor"].p < r.alpha ? "" : "not "}significant (${f(t["Row factor"])}).` };
    }
    if (s.type === "regression" && r.multi) {
      const ok = r.fits.filter(f => !f.error), c = r.comparison;
      const key = ok[0] && ok[0].derived && ok[0].derived[0] ? ok[0].derived[0].name : null;
      const vals = ok.map(f => key ? `${esc(f.name)} ${r2((f.derived.find(d => d.name === key) || {}).value, 3)}` : `${esc(f.name)}: ${f.params.map(p => `${esc(p.name)} ${r2(p.value, 3)}`).join(", ")}`).join("; ");
      return { methods: `Each dataset was fitted separately by ${r.model === "linear" ? "linear regression" : `nonlinear regression using the model “${esc(r.model_name)}”`}${c && !c.error ? `; ${c.param === "all" ? "whether one curve fits all datasets" : `whether ${esc(c.param)} differs between datasets`} was tested with the extra sum-of-squares F test` : ""}. ${ALPHA(r)} Analyses were performed in ${SW}.`,
        results: `${key ? `${key}: ` : ""}${vals}.${c && !c.error ? ` ${c.param === "all" ? "The curves" : esc(c.param)} ${c.different ? "differed significantly" : "did not differ significantly"} between datasets (F(${c.dfn}, ${c.dfd}) = ${r2(c.F)}, ${apaP(c.p)}).` : ""}` };
    }
    if (s.type === "regression" && r.model === "linear") {
      const c = r.correlation;
      return { methods: `The relationship between ${esc(s.cols[0])} and ${esc(s.cols[1])} was analyzed by least-squares linear regression, and correlation was assessed with Pearson's coefficient${r.unknowns ? `; unknown samples were interpolated from the fitted line` : ""}. ${ALPHA(r)} Analyses were performed in ${SW}.`,
        results: `${r.significant ? "There was a significant linear relationship" : "There was no significant linear relationship"} (slope ${r2(r.slope, 4)}, ${pct}% CI ${r2(r.slope_ci[0], 4)} to ${r2(r.slope_ci[1], 4)}; R² = ${r2(r.r_squared, 3)}; F(1, ${r.df}) = ${r2(r.F)}, ${apaP(r.p)}; Pearson r = ${r2(c.pearson_r, 3)}).` };
    }
    if (s.type === "regression") {
      const key = r.derived && r.derived[0];
      const fixed = r.params.filter(p => p.fixed);
      return { methods: `Data were fitted by nonlinear least-squares regression ${r.model === "custom" ? `to the user-defined equation ${esc(r.equation)}` : `using the model “${esc(r.model_name)}”, ${esc(r.equation)}`}${r.x_is_log && !s.options.xIsLog ? ", with X log10-transformed" : ""}${fixed.length ? `; ${fixed.map(p => `${esc(p.name)} was constrained to ${fmt(p.value)}`).join(", ")}` : ""}. Analyses were performed in ${SW}.`,
        results: `${key && key.value != null ? `The best-fit ${key.name} was ${r2(key.value, 3)}${key.ci && key.ci[0] != null ? ` (${pct}% CI ${r2(key.ci[0], 3)} to ${r2(key.ci[1], 3)})` : ""}; ` : ""}${r.params.filter(p => !p.fixed).map(p => `${esc(p.name)} = ${r2(p.value, 3)}`).join(", ")} (R² = ${r2(r.r_squared, 3)}, n = ${r.n}).` };
    }
    if (s.type === "survival") {
      const m = `Survival was estimated with the Kaplan-Meier method${r.logrank ? " and compared between groups with the log-rank (Mantel-Cox) test" : ""}${r.hazard_ratio ? "; the hazard ratio was calculated with the Mantel-Haenszel method" : ""}. ${ALPHA(r)} Analyses were performed in ${SW}.`;
      const meds = r.curves.map(c => `${esc(c.name)} ${c.median == null ? "not reached" : r2(c.median, 1)}`).join(", ");
      return { methods: m, results: `Median survival: ${meds}.${r.logrank ? ` Survival ${r.p < r.alpha ? "differed significantly" : "did not differ significantly"} between groups (χ²(${r.logrank.df}) = ${r2(r.logrank.chi2)}, ${apaP(r.p)})` : ""}${r.hazard_ratio ? `; hazard ratio (${esc(r.hazard_ratio.label)}) ${r2(r.hazard_ratio.value)}, 95% CI ${r2(r.hazard_ratio.ci[0])} to ${r2(r.hazard_ratio.ci[1])}.` : "."}` };
    }
    if (s.type === "contingency") {
      return { methods: `The association between group and outcome was tested with ${r.fisher ? "Fisher's exact test (two-sided)" : "the chi-square test"}${r.odds_ratio ? "; odds ratios and relative risks are reported with 95% confidence intervals" : ""}. ${ALPHA(r)} Analyses were performed in ${SW}.`,
        results: `${r.table.map((row, i) => `${esc(r.rows[i])}: ${row[0]}/${row.reduce((x, y) => x + y, 0)} (${r2(r.row_pct[i][0], 1)}%) ${esc(r.cols[0]).toLowerCase()}`).join("; ")}. The association was ${r.p < r.alpha ? "" : "not "}significant (${r.fisher ? apaP(r.fisher.p) : `χ²(${r.chi_square.df}) = ${r2(r.chi_square.chi2)}, ${apaP(r.p)}`}${r.odds_ratio ? `; OR ${r2(r.odds_ratio.value)}, 95% CI ${r2(r.odds_ratio.ci[0])} to ${r2(r.odds_ratio.ci[1])}` : ""}).` };
    }
    if (s.type === "multivar" && r.kind === "linear") {
      return { methods: `${esc(r.y_name)} was modeled by multiple linear regression with ${r.coefs.slice(1).map(c => esc(c.name)).join(", ")} as predictors. ${ALPHA(r)} Analyses were performed in ${SW}.`,
        results: `The model explained ${r2(r.r_squared * 100, 1)}% of the variance (adjusted R² = ${r2(r.adj_r_squared, 3)}; F(${r.coefs.length - 1}, ${r.df}) = ${r2(r.F)}, ${apaP(r.p)}). ${r.coefs.slice(1).map(c => `${esc(c.name)}: β = ${r2(c.estimate, 3)} (${pct}% CI ${r2(c.ci[0], 3)} to ${r2(c.ci[1], 3)}), ${apaP(c.p)}`).join("; ")}.` };
    }
    if (s.type === "multivar" && r.kind === "cox") {
      return { methods: `Time to event was analyzed by Cox proportional hazards regression (Efron method for ties) with ${r.coefs.map(c => esc(c.name)).join(", ")} as predictors; hazard ratios are reported with 95% Wald confidence intervals. ${ALPHA(r)} Analyses were performed in ${SW}.`,
        results: `The model was ${r.p < r.alpha ? "" : "not "}significant (likelihood ratio χ²(${r.df}) = ${r2(r.lr_chi2)}, ${apaP(r.p)}; n = ${r.n}, ${r.n_events} events; concordance = ${r2(r.concordance, 3)}). ${r.coefs.map(c => `${esc(c.name)}: HR ${r2(c.hr, 3)} (95% CI ${r2(c.hr_ci[0], 3)} to ${r2(c.hr_ci[1], 3)}), ${apaP(c.p)}`).join("; ")}.` };
    }
    if (s.type === "multivar" && r.kind === "logistic") {
      return { methods: `${esc(r.y_name)} was modeled by binary logistic regression with ${r.coefs.slice(1).map(c => esc(c.name)).join(", ")} as predictors; odds ratios are reported with 95% Wald confidence intervals. ${ALPHA(r)} Analyses were performed in ${SW}.`,
        results: `The model was ${r.p < r.alpha ? "" : "not "}significant (likelihood ratio χ²(${r.coefs.length - 1}) = ${r2(r.lr_chi2)}, ${apaP(r.p)}; AUC = ${r2(r.auc, 3)}). ${r.coefs.slice(1).map(c => `${esc(c.name)}: OR ${r2(c.or, 3)} (95% CI ${r2(c.or_ci[0], 3)} to ${r2(c.or_ci[1], 3)}), ${apaP(c.p)}`).join("; ")}.` };
    }
    if (s.type === "multivar" && r.kind === "pca") {
      return { methods: `Principal component analysis was performed on ${r.standardized ? "standardized" : "unstandardized"} variables (${r.names.map(esc).join(", ")}; n = ${r.n}). Analyses were performed in ${SW}.`,
        results: `The first two components explained ${r2(r.cumulative_pct[Math.min(1, r.cumulative_pct.length - 1)], 1)}% of the total variance (PC1 ${r2(r.variance_pct[0], 1)}%${r.variance_pct[1] != null ? `, PC2 ${r2(r.variance_pct[1], 1)}%` : ""}); ${r.kaiser} component${r.kaiser === 1 ? "" : "s"} had eigenvalues above 1.` };
    }
    if (s.type === "multivar") {
      const sig = r.pairs.filter(p => p.significant);
      return { methods: `Associations between variables were assessed with ${r.method === "pearson" ? "Pearson" : "Spearman"} correlation coefficients (pairwise complete observations). ${ALPHA(r)} Analyses were performed in ${SW}.`,
        results: `${sig.length} of ${r.pairs.length} pairs were significantly correlated. ${r.pairs.slice(0, 4).map(p => `${esc(p.a)} and ${esc(p.b)}: r = ${r2(p.r)}, ${apaP(p.p)}`).join("; ")}.` };
    }
    if (s.type === "diagnostic" && r.test_name === "ROC curve") {
      return { methods: `Diagnostic performance was evaluated by receiver operating characteristic (ROC) analysis; the standard error of the area under the curve was calculated by the Hanley-McNeil method and the optimal cutoff by the Youden index. Analyses were performed in ${SW}.`,
        results: `The area under the ROC curve was ${r2(r.auc, 3)} (${pct}% CI ${r2(r.ci[0], 3)} to ${r2(r.ci[1], 3)}, ${apaP(r.p)}). At a cutoff of ${r.direction === "higher" ? "≥" : "≤"} ${fmt(r.best.cut)}, sensitivity was ${r2(r.best.sens, 1)}% and specificity ${r2(r.best.spec, 1)}% (${r.n_patients} ${esc(r.names[1]).toLowerCase()}, ${r.n_controls} ${esc(r.names[0]).toLowerCase()}).` };
    }
    if (s.type === "diagnostic") {
      return { methods: `Agreement between ${esc(r.names[0])} and ${esc(r.names[1])} was assessed by Bland-Altman analysis (bias and 95% limits of agreement). Analyses were performed in ${SW}.`,
        results: `The mean difference (${esc(r.names[1])} − ${esc(r.names[0])}) was ${r2(r.bias, 3)} (${pct}% CI ${r2(r.bias_ci[0], 3)} to ${r2(r.bias_ci[1], 3)}), with 95% limits of agreement from ${r2(r.loa[0], 3)} to ${r2(r.loa[1], 3)} (n = ${r.n}).` };
    }
    return null;
  }

  // ---------------------------------------------------------------- groups
  function normalityRows(r) {
    if (!r.normality) return [];
    const names = r.normality_of === "differences" ? ["Differences"] : r.groups.map(g => g.name);
    return [T.sec("Normality (Shapiro-Wilk)"), ...r.normality.map((n, i) => T.row(esc(names[i]),
      n ? `W = ${fmt(n.W, 3)}, P = ${fmt(n.p, 3)} · ${n.normal ? "passed" : "<b>not normal</b>"}` : "needs 3+ values"))];
  }
  function renderNested(r, s) {
    const pct = Math.round((1 - r.alpha) * 100), two = r.n_groups === 2;
    let h;
    if (two) {
      const c = r.comparisons[0];
      h = T.summary(c.significant ? "sig" : "ns", `${c.significant ? "<b>Significant difference</b>" : "No significant difference"} (${fmtP(c.p)}${c.significant ? `, ${c.stars}` : ""}). The mean of <b>${esc(c.b)}</b> is ${fmt(Math.abs(c.diff))} ${c.diff >= 0 ? "higher" : "lower"} than <b>${esc(c.a)}</b> (${pct}% CI of the difference: ${ci(...c.ci)}).`);
      h += T.table([T.sec("Nested t test"), T.row("t, df", `t = ${fmt(Math.abs(c.t), 4)}, df = ${r.df_d}`), T.row("P value", `${pOnly(c.p)} ${st(c.stars)}`),
        T.row(`Difference (${esc(c.b)} − ${esc(c.a)})`, `${fmt(c.diff)} ± ${fmt(c.se, 3)}`), T.row(`${pct}% CI of difference`, ci(...c.ci))]);
    } else {
      h = T.summary(r.significant ? "sig" : "ns", `${r.significant ? "<b>The groups differ</b>" : "No significant difference among the groups"} (${fmtP(r.p)}${r.significant ? `, ${r.stars}` : ""}).`);
      h += T.table([T.sec("Nested one-way ANOVA"), T.row("F (DFn, DFd)", `F(${r.df_n}, ${r.df_d}) = ${fmt(r.F, 4)}`), T.row("P value", `${pOnly(r.p)} ${st(r.stars)}`)]);
      h += `<div class="opt-label" style="margin-top:10px">Tukey's multiple comparisons</div>` + T.multi(["Comparison", "Difference", `${pct}% CI`, "Adjusted P", ""],
        r.comparisons.map(c => ({ cls: c.significant ? "hl" : "", cells: [`${esc(c.b)} − ${esc(c.a)}`, fmt(c.diff), ci(...c.ci), pOnly(c.p), st(c.stars)] })));
    }
    h += T.table([T.sec("Variation"), T.row("Between subjects (within groups), variance", fmt(r.var_subject)), T.row("Between replicates (within subjects), variance", fmt(r.var_residual)),
      T.row("Intraclass correlation", r.icc == null ? "—" : `${fmt(r.icc, 3)} (${fmt(r.icc * 100, 3)}% of the variation is between subjects)`),
      T.row("Do subjects differ within groups?", `F(${r.subjects_df[0]}, ${r.subjects_df[1]}) = ${fmt(r.subjects_F, 4)}, P ${pOnly(r.subjects_p)}${r.subjects_p < r.alpha ? " (yes: nesting matters)" : ""}`)]);
    h += T.multi(["", ...r.groups.map(g => esc(g.name))], [
      ["Subjects", ...r.groups.map(g => g.n_subjects)], ["Measurements", ...r.groups.map(g => g.n_values)],
      ["Mean (model)", ...r.groups.map(g => fmt(g.mean))], ["SEM (model)", ...r.groups.map(g => fmt(g.se, 3))],
      [`${pct}% CI of mean`, ...r.groups.map(g => ci(...g.ci))], ["SD of subject means", ...r.groups.map(g => g.sd_of_subject_means == null ? "—" : fmt(g.sd_of_subject_means))]]);
    h += `<p class="note">Mixed-effects model (REML) with subject as a random effect; denominator df = subjects − groups. With equal numbers of replicates and subjects this equals ${two ? "a t test" : "one-way ANOVA"} on the subject means.</p>`;
    return h;
  }
  function drawNested(el, r, s) {
    const g = s.graph, traces = [], shapes = [], annotations = [];
    const rows = s.data.filter(x => String(x[0] ?? "").trim() !== "" && x.slice(1).some(isNum));
    let ymax = -Infinity, ymin = Infinity;
    r.groups.forEach((gr, i) => {
      const c = color(g, i, gr.name), subs = rows.filter(x => String(x[0]).trim() === gr.name);
      const ns = subs.length, w = Math.min(0.7, 0.14 * ns);
      const sx = [], sy = [];
      subs.forEach((row, k) => {
        const x0 = i + (ns > 1 ? -w / 2 + w * k / (ns - 1) : 0), vals = row.slice(1).map(num).filter(v => v !== null);
        const m = vals.reduce((a, b) => a + b, 0) / vals.length;
        vals.forEach(v => { ymax = Math.max(ymax, v); ymin = Math.min(ymin, v); });
        sx.push(x0); sy.push(m);
        if (g.showPoints) traces.push({ type: "scatter", mode: "markers", x: vals.map((_, q) => x0 + ((q * 0.618) % 1 - 0.5) * 0.05), y: vals, showlegend: false,
          marker: { color: c, size: Math.max(3, g.pointSize * 0.55), opacity: 0.45 }, hovertemplate: `${esc(gr.name)}, subject ${k + 1}: %{y}<extra></extra>` });
      });
      traces.push({ type: "scatter", mode: "markers", x: sx, y: sy, showlegend: false, marker: { color: c, size: g.pointSize + 2, line: { color: "#fff", width: 1 } },
        hovertemplate: `${esc(gr.name)} subject mean: %{y:.4g}<extra></extra>` });
      const err = g.err === "sem" ? gr.se : g.err === "sd" ? (gr.sd_of_subject_means || 0) : 0;
      ymax = Math.max(ymax, gr.mean + err);
      traces.push({ type: "scatter", mode: "markers", x: [i], y: [gr.mean], showlegend: false, marker: { symbol: "line-ew", size: 44, line: { width: 3, color: "#1b2130" } },
        error_y: { type: "data", array: [err], visible: g.err !== "none", color: "#1b2130", thickness: 1.5, width: 11 }, hovertemplate: `Mean ${fmt(gr.mean)}<extra></extra>` });
    });
    const span = (ymax - ymin) || 1;
    let topExtra = span * 0.06;
    if (g.brackets !== "none") {
      const show = r.comparisons.filter(c => g.brackets === "all" || c.significant);
      const { items, height } = bracketLayout(show, ymax, span);
      const tick = span * 0.025;
      items.forEach(p => {
        shapes.push({ type: "path", path: `M ${p.i + 0.04} ${p.y - tick} L ${p.i + 0.04} ${p.y} L ${p.j - 0.04} ${p.y} L ${p.j - 0.04} ${p.y - tick}`, line: { color: "#1b2130", width: 1.3 } });
        annotations.push({ x: (p.i + p.j) / 2, y: p.y, text: p.stars, showarrow: false, yanchor: "bottom", font: { size: p.stars === "ns" ? 11 : 16 } });
      });
      topExtra = Math.max(topExtra, height + span * 0.04);
    }
    styledReact(el, traces, { ...baseLayout(g), shapes, annotations, meta: "flippable",
      xaxis: axis(g, { tickvals: r.groups.map((_, i) => i), ticktext: r.groups.map(x => esc(x.name)), range: [-0.6, r.groups.length - 0.4] }),
      yaxis: yAxis(g, g.ylabel, { range: [ymin - span * 0.08, ymax + topExtra] }) }, PLOT_CONFIG);
  }
  function descTable(groups) {
    const keys = [["n", "n"], ["Mean", "mean"], ["SD", "sd"], ["SEM", "sem"], ["95% CI of mean", "ci95"], ["Median", "median"], ["Min", "min"], ["Max", "max"]];
    return T.multi(["", ...groups.map(g => esc(g.name))], keys.map(([l, k]) => [l, ...groups.map(g =>
      k === "ci95" ? (g.ci95 == null ? "—" : `${fmt(g.mean - g.ci95, 3)} – ${fmt(g.mean + g.ci95, 3)}`) : fmt(g[k]))]));
  }
  function renderGroupResults(r) {
    const pct = Math.round((1 - r.alpha) * 100);
    let h = "";
    if (r.n_groups === 2) {
      const [a, b] = r.groups, dir = r.difference > 0 ? "higher" : "lower", what = r.kind === "mannwhitney" ? "median" : "mean";
      h += r.significant
        ? T.summary("sig", `<b>Significant difference</b> (${fmtP(r.p)}, ${r.stars}). ` + (r.kind === "wilcoxon"
          ? `The median difference (<b>${esc(b.name)}</b> − <b>${esc(a.name)}</b>) is ${fmt(r.difference)}.`
          : `The ${what} of <b>${esc(b.name)}</b> is ${fmt(Math.abs(r.difference))} ${dir} than <b>${esc(a.name)}</b>${r.ci_low != null ? ` (${pct}% CI of the difference: ${ci(r.ci_low, r.ci_high)})` : ""}.`))
        : T.summary("ns", `<b>No significant difference</b> (${fmtP(r.p)}). The data don't show convincing evidence that <b>${esc(a.name)}</b> and <b>${esc(b.name)}</b> differ. That isn't proof they're the same.`);
      h += T.table([T.sec(esc(r.test_name)), T.row("P value", pOnly(r.p)), T.row(`Significant? (α = ${r.alpha})`, `${r.significant ? "Yes" : "No"} ${st(r.stars)}`),
        T.row(`${r.statistic_name}${r.df != null ? ", df" : ""}`, `${r.statistic_name} = ${fmt(r.statistic)}${r.df != null ? `, df = ${fmt(r.df)}` : ""}`),
        T.row(esc(r.difference_label), fmt(r.difference)), r.ci_low != null ? T.row(`${pct}% CI of difference`, ci(r.ci_low, r.ci_high)) : "",
        r.n_pairs ? T.row("Number of pairs", r.n_pairs) : "", ...normalityRows(r)]);
      if (r.variance_check && r.variance_check.p < 0.05) h += `<p class="note warn">⚠︎ The groups' spreads differ (F test ${fmtP(r.variance_check.p)}). Welch's t test is safer.</p>`;
    } else {
      const sigPairs = r.comparisons.filter(c => c.significant).length;
      h += r.significant
        ? T.summary("sig", `<b>The groups differ</b> (${esc(r.test_name)}, ${fmtP(r.p)}, ${r.stars}). ${sigPairs} of ${r.comparisons.length} pairs differ significantly (see ${esc(r.posthoc_name)} below).`)
        : T.summary("ns", `<b>No significant difference among the ${r.k} groups</b> (${esc(r.test_name)}, ${fmtP(r.p)}).`);
      const main = [T.sec(esc(r.test_name)), T.row("P value", pOnly(r.p)), T.row(`Significant? (α = ${r.alpha})`, `${r.significant ? "Yes" : "No"} ${st(r.stars)}`)];
      if (r.kind === "kruskal") main.push(T.row("Kruskal-Wallis H, df", `H = ${fmt(r.H)}, df = ${r.df_between}`));
      else if (r.kind === "friedman") main.push(T.row("Friedman χ², df", `${fmt(r.chi2)}, ${r.df_between}`), T.row("Subjects (complete rows)", r.n_subjects));
      else main.push(T.row("F (DFn, DFd)", `F (${fmt(r.df_between)}, ${fmt(r.df_within)}) = ${fmt(r.F)}`));
      if (r.kind === "rm") main.push(T.row("Geisser-Greenhouse ε", fmt(r.epsilon, 3)), T.row("P without correction", pOnly(r.p_uncorrected)),
        T.row("Subjects (complete rows)", r.n_subjects));
      if (r.r_squared != null) main.push(T.row("R²", fmt(r.r_squared)));
      h += T.table(main);
      if (r.table) h += T.multi(["ANOVA table", "SS", "DF", "MS"], r.table.map(t => [esc(t.source), fmt(t.SS), fmt(t.df), fmt(t.MS)]));
      const rankBased = r.kind === "kruskal" || r.kind === "friedman";
      h += `<div class="opt-label" style="margin-top:10px">${esc(r.posthoc_name)}</div>`;
      h += T.multi(["Comparison", esc(r.diff_label), rankBased ? "" : `${pct}% CI`, "Adj. P", ""],
        r.comparisons.map(c => ({ cls: c.significant ? "hl" : "", cells: [`${esc(c.a)} vs ${esc(c.b)}`, fmt(c.diff), rankBased ? "" : c.ci_low == null ? "—" : ci(c.ci_low, c.ci_high), pOnly(c.p), st(c.stars)] })));
      if (r.posthoc === "holm") h += `<p class="note">The Holm-Šídák method doesn't produce confidence intervals.</p>`;
      if (r.posthoc === "lsd") h += `<p class="note warn">Fisher's LSD doesn't correct for multiple comparisons, so with many pairs some "significant" results may be chance.</p>`;
      if (r.normality) h += T.table(normalityRows(r));
      if (r.kind === "rm" || r.kind === "friedman") h += `<p class="note">Only rows with a value in every column are used (${r.n_subjects} subjects).</p>`;
      if (r.variance_check && r.variance_check.p < 0.05) h += `<p class="note warn">⚠︎ The groups' spreads differ (Brown-Forsythe ${fmtP(r.variance_check.p)}). Welch's ANOVA is safer.</p>`;
    }
    if (r.outliers) {
      const found = r.outliers.filter(o => o.outliers.length);
      const rout = r.outliers[0] && r.outliers[0].method === "rout";
      h += `<div class="opt-label" style="margin-top:10px">Outliers (${rout ? `ROUT, Q = ${fmt(r.outliers[0].q * 100)}%` : "Grubbs' test, α = 0.05"})</div>` + (found.length
        ? T.multi(["Group", "Suspected outliers", ""], r.outliers.map(o => [esc(o.name), o.outliers.length ? o.outliers.map(x => `<b>${fmt(x.value)}</b>`).join(", ") : "none", o.n < 3 ? `<span class="pd">needs 3+ values</span>` : ""]))
          + `<p class="note warn">Outliers are circled in red on the graph. The analysis above still includes them: only remove a value if you have a reason beyond the statistics (e.g. a known technical error).</p>`
        : `<p class="note">No outliers found in any group.</p>`);
    }
    h += `<div class="opt-label" style="margin-top:10px">Descriptive statistics</div>` + descTable(r.groups);
    return h;
  }

  function renderFreq(r) {
    const G = r.groups;
    const notNormal = G.filter(g => g.shapiro && !g.shapiro.normal);
    let h = T.summary(notNormal.length ? "sig" : "ns", notNormal.length
      ? `The values in ${notNormal.map(g => `<b>${esc(g.name)}</b>`).join(", ")} do not look normally distributed (Shapiro-Wilk ${notNormal.map(g => fmtP(g.shapiro.p)).join(", ")}). Consider a nonparametric test or a log transform.`
      : G.some(g => g.shapiro) ? `No column departs significantly from a normal distribution (Shapiro-Wilk). On the Q-Q plot, points close to the line mean the values fit a normal distribution.`
      : `Too few values to test normality (needs at least 3 per column).`);
    h += `<p class="note">Bin width ${fmt(r.bin_width)}${r.auto_width ? " (chosen automatically)" : ""}, first bin starts at ${fmt(r.bin_start)}. A value exactly on a bin edge goes into the higher bin.</p>`;
    const statRow = (label, f) => [label, ...G.map(g => { const v = f(g); return v == null ? "—" : v; })];
    h += T.multi(["", ...G.map(g => esc(g.name))], [
      statRow("Number of values", g => g.n), statRow("Mean", g => fmt(g.mean)), statRow("Std. deviation", g => g.sd == null ? null : fmt(g.sd)),
      statRow("Median", g => fmt(g.median)), statRow("Minimum", g => fmt(g.min)), statRow("Maximum", g => fmt(g.max)),
      statRow("Skewness", g => g.skewness == null ? null : fmt(g.skewness, 3)),
      statRow("Shapiro-Wilk P", g => g.shapiro ? `${fmt(g.shapiro.p, 3)} (${g.shapiro.normal ? "passed" : "<b>not normal</b>"})` : null),
      statRow("D'Agostino-Pearson P", g => g.dagostino ? `${fmt(g.dagostino.p, 3)} (${g.dagostino.normal ? "passed" : "<b>not normal</b>"})` : "needs n ≥ 8"),
    ]);
    const yName = { count: "Number of values", percent: "Percent", fraction: "Fraction" }[r.y] + (r.cumulative ? " (cumulative)" : "");
    const yv = v => r.y === "count" ? String(Math.round(v)) : fmt(v, 4);
    h += `<div class="opt-label">Frequency table: ${yName}</div>` + T.multi(["Bin", "Center", ...G.map(g => esc(g.name))],
      r.centers.map((c, i) => [`${fmt(r.edges[i])} to &lt; ${fmt(r.edges[i + 1])}`, fmt(c), ...G.map(g => yv(g.values[i]))]));
    return h;
  }
  // normal distribution helpers for drawing (erf: Abramowitz & Stegun 7.1.26, error < 1.5e-7)
  const erf = x => { const t = 1 / (1 + 0.3275911 * Math.abs(x)), y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x); return x >= 0 ? y : -y; };
  const normPdf = (x, m, sd) => Math.exp(-0.5 * ((x - m) / sd) ** 2) / (sd * Math.sqrt(2 * Math.PI));
  const normCdf = (x, m, sd) => 0.5 * (1 + erf((x - m) / (sd * Math.SQRT2)));
  function drawFreq(el, r, s) {
    const g = s.graph, L = baseLayout(g), traces = [];
    const plot = g.freqPlot || "hist", multi = r.groups.length > 1;
    const xTitle = g.xlabel || g.ylabel || "Value";
    if (plot === "qq") {
      let lo = Infinity, hi = -Infinity;
      r.groups.forEach((gr, i) => {
        const c = color(g, i, gr.name);
        gr.qq.predicted.forEach(v => { lo = Math.min(lo, v); hi = Math.max(hi, v); });
        gr.qq.actual.forEach(v => { lo = Math.min(lo, v); hi = Math.max(hi, v); });
        traces.push({ type: "scatter", mode: "markers", name: gr.name, x: gr.qq.predicted, y: gr.qq.actual,
          marker: { color: c, size: g.pointSize, opacity: 0.85, line: { color: "#fff", width: 1 } },
          hovertemplate: `${esc(gr.name)}<br>Predicted %{x:.4g}<br>Actual %{y:.4g}<extra></extra>` });
      });
      const pad = (hi - lo) * 0.05 || 1;
      traces.unshift({ type: "scatter", mode: "lines", x: [lo - pad, hi + pad], y: [lo - pad, hi + pad], showlegend: false,
        line: { color: "#8a93a3", width: 1.5, dash: "dash" }, hoverinfo: "skip" });
      L.xaxis = axis(g, { title: { text: `Predicted if normal (${esc(xTitle)})` } });
      L.yaxis = yAxis(g, `Actual (${xTitle})`);
      L.showlegend = multi;
      return styledReact(el, traces, L, PLOT_CONFIG);
    }
    const h = r.bin_width, scale = gr => (r.y === "count" ? gr.n : r.y === "percent" ? 100 : 1);
    r.groups.forEach((gr, i) => {
      const c = color(g, i, gr.name);
      if (plot === "poly") traces.push({ type: "scatter", mode: "lines+markers", name: gr.name, x: r.centers, y: gr.values,
        line: { color: c, width: 2 }, marker: { color: c, size: g.pointSize * 0.8 }, hovertemplate: `${esc(gr.name)}: %{y}<extra>center %{x}</extra>` });
      else traces.push({ type: "bar", name: gr.name, x: r.centers, y: gr.values, width: multi && (g.freqBars || "overlay") === "group" ? undefined : h,
        marker: { color: hexToRgba(toHex(c), multi && g.freqBars !== "stack" ? 0.5 : 0.75), line: { color: toHex(c), width: 1.2 } },
        hovertemplate: `${esc(gr.name)}: %{y}<extra>%{x}</extra>` });
      if (g.normalCurve && gr.sd > 0) {
        const xs = Array.from({ length: 121 }, (_, k) => r.edges[0] + (r.edges[r.edges.length - 1] - r.edges[0]) * k / 120);
        const ys = xs.map(x => r.cumulative ? normCdf(x, gr.mean, gr.sd) * scale(gr) : normPdf(x, gr.mean, gr.sd) * scale(gr) * h);
        traces.push({ type: "scatter", mode: "lines", x: xs, y: ys, showlegend: false, line: { color: c, width: 2 },
          hovertemplate: `Normal curve (mean ${fmt(gr.mean)}, SD ${fmt(gr.sd)})<extra></extra>` });
      }
    });
    L.barmode = multi ? (g.freqBars || "overlay") : "overlay";
    L.bargap = multi && g.freqBars === "group" ? 0.08 : 0;
    L.xaxis = axis(g, { title: { text: esc(xTitle) } });
    L.yaxis = yAxis(g, { count: "Number of values", percent: "Percent of values", fraction: "Fraction of values" }[r.y] + (r.cumulative ? " (cumulative)" : ""), { rangemode: "tozero" });
    L.showlegend = multi;
    return styledReact(el, traces, L, PLOT_CONFIG);
  }
  function renderColStats(r) {
    const G = r.groups, pct = Math.round((1 - r.alpha) * 100);
    const row = (label, f) => [label, ...G.map(g => { const v = f(g); return v == null ? "—" : v; })];
    const rows = [
      row("Number of values", g => g.n), row("Mean", g => fmt(g.mean)), row("Std. deviation", g => fmt(g.sd)), row("Std. error of mean", g => fmt(g.sem)),
      row(`Lower ${pct}% CI of mean`, g => fmt(g.ci_low)), row(`Upper ${pct}% CI of mean`, g => fmt(g.ci_high)),
      row("Minimum", g => fmt(g.min)), row("25% percentile", g => fmt(g.q1)), row("Median", g => fmt(g.median)), row("75% percentile", g => fmt(g.q3)),
      row("Maximum", g => fmt(g.max)), row("Range", g => fmt(g.range)), row("Interquartile range", g => fmt(g.iqr)),
      row("Coefficient of variation", g => g.cv == null ? null : fmt(g.cv, 4) + "%"),
      row("Geometric mean", g => g.geo_mean == null ? null : fmt(g.geo_mean)), row("Geometric SD factor", g => g.geo_sd_factor == null ? null : fmt(g.geo_sd_factor)),
      row("Skewness", g => g.skewness == null ? null : fmt(g.skewness, 3)), row("Kurtosis", g => g.kurtosis == null ? null : fmt(g.kurtosis, 3)),
      row("Sum", g => fmt(g.sum)),
      row("Shapiro-Wilk P", g => g.shapiro ? `${fmt(g.shapiro.p, 3)} (${g.shapiro.normal ? "passed" : "<b>not normal</b>"})` : null),
      row("D'Agostino-Pearson P", g => g.dagostino ? `${fmt(g.dagostino.p, 3)} (${g.dagostino.normal ? "passed" : "<b>not normal</b>"})` : "needs n ≥ 8"),
    ];
    let h = "";
    if (r.hypothetical != null) {
      const sig = G.filter(g => g.one_sample_t && g.one_sample_t.p < r.alpha);
      h += T.summary(sig.length ? "sig" : "ns", sig.length ? `Mean differs significantly from ${fmt(r.hypothetical)} in: ${sig.map(g => `<b>${esc(g.name)}</b> (${fmtP(g.one_sample_t.p)})`).join(", ")}.`
        : `No column's mean differs significantly from ${fmt(r.hypothetical)}.`);
      rows.push(row(`One-sample t test vs ${fmt(r.hypothetical)}: P`, g => g.one_sample_t ? `${pOnly(g.one_sample_t.p)} ${st(g.one_sample_t.stars)}` : null),
        row("Mean − hypothetical", g => g.one_sample_t ? fmt(g.one_sample_t.diff) : null),
        row(`Wilcoxon signed-rank vs ${fmt(r.hypothetical)}: P`, g => g.wilcoxon ? `${pOnly(g.wilcoxon.p)} ${st(g.wilcoxon.stars)}` : null));
    } else h += T.summary("ns", `Descriptive statistics for ${G.length} column${G.length > 1 ? "s" : ""}. Enter a hypothetical value to test each column's mean against it.`);
    h += T.multi(["", ...G.map(g => esc(g.name))], rows);
    h += `<p class="note">Percentiles use the (n+1)p rank method, as Prism does. Geometric values need all values > 0.</p>`;
    return h;
  }

  // ---------------------------------------------------------------- two-way
  function renderTwoWayResults(r, s) {
    const pct = Math.round((1 - r.alpha) * 100);
    const t = Object.fromEntries(r.table.map(x => [x.source, x]));
    const rowF = esc(s.cols[0] || "Row factor") + (r.rm ? " (repeated)" : "");
    const sigTerm = (x, label) => x.p < r.alpha ? `<b>${label}</b> matters (${fmtP(x.p)}, ${x.stars})` : `${label} doesn't (${fmtP(x.p)})`;
    let h = T.summary(t.Interaction.p < r.alpha || t["Column factor"].p < r.alpha || t["Row factor"].p < r.alpha ? "sig" : "ns",
      `${sigTerm(t["Column factor"], "Column factor (groups)")}; ${sigTerm(t["Row factor"], rowF)}; ` +
      (t.Interaction.p < r.alpha ? `and they <b>interact</b> (${fmtP(t.Interaction.p)}): the group effect depends on ${rowF}.`
        : `no significant interaction (${fmtP(t.Interaction.p)}).`));
    h += T.multi(["Source of variation", "% of total", "F (DFn, DFd)", "P value", ""],
      r.table.filter(x => x.F !== null).map(x => ({ cls: x.p < r.alpha ? "hl" : "",
        cells: [x.source === "Row factor" ? rowF : x.source === "Column factor" ? "Column factor (groups)" : x.source,
          fmt(x.pct, 3) + "%", `F (${x.df}, ${x.dfd ?? t.Residual.df}) = ${fmt(x.F)}`, pOnly(x.p), st(x.stars)] })));
    if (r.rm) h += `<p class="note">Repeated measures: ${r.n_subjects} subjects (${r.subjects_per_group.map((n, i) => `${esc(r.cols[i])}: ${n}`).join(", ")}). Row factor and interaction P values use the Geisser-Greenhouse correction (ε = ${fmt(r.epsilon, 3)}); the column factor is tested against variation between subjects.</p>`;
    h += T.multi(["ANOVA table", "SS", "DF", "MS"], r.table.map(x => [x.source === "Row factor" ? rowF : x.source, fmt(x.SS), x.df, fmt(x.MS)]));
    h += `<div class="opt-label" style="margin-top:10px">${esc(r.posthoc_name)}</div>`;
    const famHead = { within_cols: "Column", col_means: "", row_means: "" }[r.compare] ?? rowF;
    if (r.compare === "col_means" || r.compare === "row_means") h += `<p class="note">Main-effect comparisons use the unweighted means of the cell means (as Prism does), so every ${r.compare === "col_means" ? "row" : "column"} counts equally. ${r.table.find(x => x.source === "Interaction").p < r.alpha ? "⚠︎ The interaction is significant, so main effects can be misleading; look at the comparisons within each row or column too." : ""}</p>`;
    h += T.multi([famHead, "Comparison", "Mean diff.", `${pct}% CI`, "Adj. P", ""], r.comparisons.map(c => ({ cls: c.significant ? "hl" : "",
      cells: [esc(c.row), `${esc(c.a)} vs ${esc(c.b)}`, fmt(c.diff), ci(c.ci_low, c.ci_high), pOnly(c.p), st(c.stars)] })));
    h += `<div class="opt-label" style="margin-top:10px">Cell means</div>`;
    h += T.multi([rowF, ...r.cols.map(esc)], r.rows.map((rw, i) => [esc(rw), ...r.cols.map((_, j) => {
      const c = r.cells.find(x => x.i === i && x.j === j);
      return `${fmt(c.mean)} <span class="pd">± ${fmt(c.sd, 3)} (n=${c.n})</span>`;
    })]));
    h += `<p class="note">Mean ± SD. ${r.balanced ? "" : "Unequal group sizes: Type III sums of squares are used. "}${r.rm ? "Comparisons at each row use that row's own error term." : "Comparisons use the pooled ANOVA error."}</p>`;
    return h;
  }

  function renderMultiT(r) {
    const [a, b] = r.names.map(esc);
    const items = [...r.items].sort((x, y) => x.p - y.p);
    let h = T.summary(r.n_discoveries ? "sig" : "ns", r.n_discoveries
      ? `<b>${r.n_discoveries} of ${r.items.length}</b> rows differ between <b>${a}</b> and <b>${b}</b> at a false discovery rate of ${r.q_level * 100}%: ${items.filter(i => i.discovery).slice(0, 6).map(i => `<b>${esc(i.name)}</b>`).join(", ")}${r.n_discoveries > 6 ? "…" : ""}.`
      : `<b>No discoveries</b> among ${r.items.length} rows at a false discovery rate of ${r.q_level * 100}%.`);
    h += T.multi(["Row", `Mean ${a}`, `Mean ${b}`, "Difference", "log2 fold change", "P", "q (FDR)", ""], items.map(i => ({ cls: i.discovery ? "hl" : "",
      cells: [esc(i.name), fmt(i.mean_a), fmt(i.mean_b), fmt(i.diff), i.log2fc == null ? "—" : fmt(i.log2fc, 3), pOnly(i.p), pOnly(i.q), i.discovery ? "<b>discovery</b>" : ""] })));
    if (r.skipped.length) h += `<p class="note warn">Skipped (fewer than 2 values in a column): ${r.skipped.map(esc).join(", ")}</p>`;
    h += `<p class="note">Difference = ${b} − ${a}. q = Benjamini-Hochberg adjusted P value. Sorted by P.</p>`;
    return h;
  }
  function drawVolcano(el, r, s) {
    const g = s.graph, hit = r.items.filter(i => i.discovery), rest = r.items.filter(i => !i.discovery);
    const tr = (pts, col, name) => ({ x: pts.map(i => i.diff), y: pts.map(i => -Math.log10(Math.max(i.p, 1e-300))), mode: "markers", name, showlegend: true,
      text: pts.map(i => esc(i.name)), marker: { color: col, size: g.pointSize + 1, line: { color: "#fff", width: 1 } },
      hovertemplate: "%{text}: difference %{x:.3g}, P %{customdata}<extra></extra>", customdata: pts.map(i => fmt(i.p, 3)) });
    const annotations = hit.length <= 15 ? hit.map(i => ({ x: i.diff, y: -Math.log10(Math.max(i.p, 1e-300)), text: esc(i.name), showarrow: false, yanchor: "bottom", yshift: 6, font: { size: (g.fontSize || 13) - 2 } })) : [];
    styledReact(el, [tr(rest, "#9aa3b2", "Not significant"), tr(hit, color(g, 1, "Discoveries"), `Discoveries (q < ${r.q_level})`)],
      { ...baseLayout(g), showlegend: true, legend: { orientation: "h", y: 1.08, x: 0 }, annotations,
        xaxis: axis(g, { title: { text: `Difference (${esc(r.names[1])} − ${esc(r.names[0])})` }, zeroline: true, zerolinecolor: "#d0d4db" }),
        yaxis: yAxis(g, g.ylabel && g.ylabel !== "Response" ? g.ylabel : "−log10(P)") }, PLOT_CONFIG);
  }

  function drawTwoWay(el, r, s) {
    const g = s.graph, traces = [], shapes = [], annotations = [];
    const nr = r.rows.length, nc = r.cols.length;
    if (g.style === "stacked") {
      r.cols.forEach((name, j) => {
        const col = color(g, j, name), cells = r.rows.map((_, i) => r.cells.find(c => c.i === i && c.j === j));
        traces.push({ type: "bar", name: esc(name), x: r.rows.map((_, i) => i), y: cells.map(c => c ? c.mean : 0), width: 0.6, showlegend: true,
          marker: { color: col + "99", line: { color: col, width: 1.5 } }, hovertemplate: `${esc(name)}: mean %{y:.4g}<extra></extra>` });
      });
      return styledReact(el, traces, { ...baseLayout(g), barmode: "stack", showlegend: true, meta: "flippable", legend: { orientation: "h", y: 1.1, x: 0, traceorder: "normal" },
        xaxis: axis(g, { tickvals: r.rows.map((_, i) => i), ticktext: r.rows.map(esc), range: [-0.6, nr - 0.4], title: { text: esc(s.cols[0] || "") } }),
        yaxis: yAxis(g, g.ylabel, { rangemode: "tozero" }) }, PLOT_CONFIG);
    }
    const width = 0.8, step = width / nc;
    const pos = (i, j) => i - width / 2 + step * (j + 0.5);
    let ymax = -Infinity, ymin = Infinity;
    const errOf = c => g.err === "sem" ? c.sem : g.err === "ci95" ? c.ci95 : g.err === "sd" ? c.sd : 0;
    r.cols.forEach((name, j) => {
      const col = color(g, j, name);
      const cells = r.rows.map((_, i) => r.cells.find(c => c.i === i && c.j === j));
      cells.forEach(c => { ymax = Math.max(ymax, c.max, c.mean + (errOf(c) || 0)); ymin = Math.min(ymin, c.min); });
      const xs = r.rows.map((_, i) => g.style === "lines" ? i : pos(i, j));
      const errY = { type: "data", array: cells.map(c => errOf(c) || 0), visible: g.err !== "none", color: g.style === "lines" ? col : "#1b2130", thickness: 1.4, width: 6 };
      if (g.style === "bars") traces.push({ type: "bar", x: xs, y: cells.map(c => c.mean), width: step * 0.9, name: esc(name), showlegend: true,
        marker: { color: col + "40", line: { color: col, width: 1.5 } }, error_y: errY, hoverinfo: "skip" });
      else traces.push({ type: "scatter", mode: g.style === "lines" ? "lines+markers" : "markers", x: xs, y: cells.map(c => c.mean), name: esc(name), showlegend: true,
        marker: g.style === "lines" ? { color: col, size: g.pointSize + 2 } : { symbol: "line-ew", size: 26, line: { width: 3, color: col } },
        line: { color: col, width: 2.2 }, error_y: errY, hovertemplate: `${esc(name)}: mean %{y:.4g}<extra></extra>` });
      if (g.showPoints && g.style !== "lines") {
        const px = [], py = [];
        r.rows.forEach((rw, i) => s.data.forEach(row => {
          if (String(row[0] || "").trim() === rw) { const v = num(row[s.cols.indexOf(name, 1)]); if (v !== null) { px.push(pos(i, j) + ((px.length * 0.618) % 1 - 0.5) * step * 0.45); py.push(v); } }
        }));
        traces.push({ type: "scatter", mode: "markers", x: px, y: py, showlegend: false,
          marker: { color: col, size: g.pointSize * 0.85, opacity: 0.85, line: { color: "#fff", width: 1 } }, hovertemplate: "%{y}<extra></extra>" });
      }
    });
    if (r.rm && g.style === "lines" && g.showPoints) r.subjects.forEach(sub => {
      const gi = r.cols.indexOf(sub.group);
      traces.unshift({ x: sub.values.map((_, i) => i), y: sub.values, mode: "lines", showlegend: false, hoverinfo: "skip",
        line: { color: color(g, gi, sub.group) + "55", width: 1 } });
      sub.values.forEach(v => { ymax = Math.max(ymax, v); ymin = Math.min(ymin, v); });
    });
    const span = (ymax - Math.min(0, ymin)) || 1;
    let topExtra = span * 0.08;
    if (g.brackets !== "none" && g.style !== "lines") {
      const show = r.comparisons.filter(c => (g.brackets === "all" || c.significant) && (!c.kind || c.kind === "within_rows" || c.kind === "within_cols"))
        .map(c => c.kind === "within_cols" ? { i: pos(c.i1, c.j), j: pos(c.i2, c.j), stars: c.stars } : { i: pos(c.i, c.j1), j: pos(c.i, c.j2), stars: c.stars });
      const { items, height } = bracketLayout(show, ymax, span);
      const tick = span * 0.02;
      items.forEach(p => {
        shapes.push({ type: "path", path: `M ${p.i} ${p.y - tick} L ${p.i} ${p.y} L ${p.j} ${p.y} L ${p.j} ${p.y - tick}`, line: { color: "#1b2130", width: 1.2 } });
        annotations.push({ x: (p.i + p.j) / 2, y: p.y, text: p.stars, showarrow: false, yanchor: "bottom", font: { size: p.stars === "ns" ? 10 : 14 } });
      });
      topExtra = Math.max(topExtra, height + span * 0.04);
    }
    const lo = g.style === "bars" ? Math.min(0, ymin) : ymin - span * 0.08;
    styledReact(el, traces, { ...baseLayout(g), shapes, annotations, showlegend: true, barmode: "overlay", meta: "flippable",
      legend: { orientation: "h", y: 1.1, x: 0 },
      xaxis: axis(g, { tickvals: r.rows.map((_, i) => i), ticktext: r.rows.map(esc), range: [-0.6, nr - 0.4], title: { text: esc(s.cols[0] || "") } }),
      yaxis: yAxis(g, g.ylabel, { range: [lo, ymax + topExtra] }) }, PLOT_CONFIG);
  }

  // ---------------------------------------------------------------- XY
  function renderXYResults(r, s) {
    return renderXYCore(r, s) + (r.rout_q ? renderXYOutliers(r, s) : "") + (r.auc ? renderAUC(r.auc, s) : "") + (r.unknowns ? renderUnknowns(r, s) : "");
  }
  function renderXYOutliers(r, s) {
    const o = r.outliers || [], q = `Q = ${fmt(r.rout_q * 100)}%`;
    if (!o.length) return `<p class="note">ROUT (${q}) found no outliers, so all points were fitted.</p>`;
    return `<div class="opt-label" style="margin-top:10px">Outliers removed before fitting (ROUT, ${q})</div>` +
      T.multi([esc(s.cols[0] || "X"), "Y"], o.map(p => [fmt(p.x), `<b>${fmt(p.y)}</b>`])) +
      `<p class="note warn">${o.length} point${o.length > 1 ? "s were" : " was"} left out of the fit (crossed out in red on the graph). The results above use the remaining ${r.n} points. Check for a technical reason before reporting.</p>`;
  }
  function renderAUC(a, s) {
    if (a.error) return `<p class="note warn">${esc(a.error)}</p>`;
    return T.table([T.sec(`Area under the curve (baseline Y = ${fmt(a.baseline)})`), T.row("Total area", `<b>${fmt(a.total)}</b>`),
      T.row("Area above baseline", fmt(a.positive)), T.row("Area below baseline", fmt(a.negative)),
      T.row(`${esc(s.cols[0] || "X")} range`, `${fmt(a.x_range[0])} to ${fmt(a.x_range[1])}`), T.row("Peak (X, Y)", `${fmt(a.peak_x)}, ${fmt(a.peak_y)}`)]) +
      `<p class="note">Trapezoid rule on the mean Y at each X, using the actual X units.</p>`;
  }
  function renderMultiFit(r, s) {
    const pct = Math.round((1 - r.alpha) * 100), ok = r.fits.filter(f => !f.error), c = r.comparison;
    let h = "";
    if (c && !c.error) {
      const what = c.param === "all" ? "The curves" : `${esc(c.param)}`;
      h += T.summary(c.different ? "sig" : "ns", c.param === "all"
        ? (c.different ? `<b>The curves differ</b>: separate curves fit significantly better than one shared curve (F (${c.dfn}, ${c.dfd}) = ${fmt(c.F)}, ${fmtP(c.p)}).`
          : `<b>No evidence the curves differ</b>: one shared curve fits the data as well as separate curves (${fmtP(c.p)}).`)
        : (c.different ? `<b>${what} differs between curves</b> (extra sum-of-squares F test, F (${c.dfn}, ${c.dfd}) = ${fmt(c.F)}, ${fmtP(c.p)}).`
          : `<b>No significant difference in ${what}</b> between curves (${fmtP(c.p)}). A shared value of ${fmt(c.shared_value)} fits all curves.`));
    } else if (c && c.error) h += `<p class="note warn">${esc(c.error)}</p>`;
    else h += T.summary("ns", `${ok.length} curve${ok.length === 1 ? "" : "s"} fitted separately. Choose <b>Compare curves</b> to test whether a parameter differs.`);
    const pn = r.param_names;
    const derivedNames = [...new Set(ok.flatMap(f => (f.derived || []).map(d => d.name)))];
    const rows = [...pn.map(n => [esc(n), ...ok.map(f => { const q = f.params.find(p => p.name === n); return q ? (q.fixed ? `${fmt(q.value)} <span class="pd">(fixed)</span>` : `${fmt(q.value)} <span class="pd">± ${fmt(q.se, 3)}</span>`) : "—"; })]),
      ...derivedNames.map(n => ({ cls: "hl", cells: [`<b>${esc(n)}</b>`, ...ok.map(f => { const d = (f.derived || []).find(x => x.name === n); return d && d.value != null ? `<b>${fmt(d.value)}</b>` : "—"; })] })),
      ...derivedNames.map(n => [`${esc(n)} ${pct}% CI`, ...ok.map(f => { const d = (f.derived || []).find(x => x.name === n); return d && d.ci && d.ci[0] != null ? ci(d.ci[0], d.ci[1]) : "—"; })]),
      ["R²", ...ok.map(f => fmt(f.r_squared, 4))], ["Number of points", ...ok.map(f => f.n)]];
    h += T.multi(["", ...ok.map(f => esc(f.name))], rows);
    if (c && !c.error) h += T.table([T.sec(c.param === "all" ? "One curve for all datasets?" : `Is ${esc(c.param)} the same for all curves?`),
      T.row("Sum of squares: separate / shared", `${fmt(c.ss_separate)} / ${fmt(c.ss_shared)}`), T.row(`F (${c.dfn}, ${c.dfd})`, fmt(c.F)), T.row("P value", `${pOnly(c.p)} ${st(stars(c.p))}`)]);
    r.fits.filter(f => f.error).forEach(f => { h += `<p class="note warn">${esc(f.name)}: ${esc(f.error)}</p>`; });
    h += `<p class="note">${esc(r.model_name)}: ${esc(r.equation)}. "±" values are standard errors.</p>`;
    return h;
  }
  function drawMultiFit(el, r, s) {
    const g = s.graph, traces = [];
    const logFit = r.x_is_log && !s.options.xIsLog && r.model !== "linear";
    const tx = x => (logFit ? Math.pow(10, x) : x);
    r.fits.forEach((f, i) => {
      if (f.error) return;
      const col = color(g, i, f.name), j = s.cols.indexOf(f.name, 1);
      const pts = s.data.map(row => [num(row[0]), num(row[j])]).filter(p => p[0] !== null && p[1] !== null && (!logFit || p[0] > 0));
      traces.push({ x: pts.map(p => p[0]), y: pts.map(p => p[1]), mode: "markers", name: esc(f.name), showlegend: false,
        marker: { color: col, size: g.pointSize, line: { color: "#fff", width: 1 } }, hovertemplate: `${esc(f.name)}: (%{x}, %{y})<extra></extra>` });
      traces.push({ x: f.curve.x.map(tx), y: f.curve.y, mode: "lines", name: esc(f.name), line: { color: col, width: 2.4 }, showlegend: true,
        hovertemplate: `${esc(f.name)} fit: %{y:.4g}<extra></extra>` });
    });
    const xa = axis(g, { title: { text: esc(g.xlabel || s.cols[0] || "X") } });
    if (g.logX) xa.type = "log";
    styledReact(el, traces, { ...baseLayout(g), showlegend: true, legend: { x: 1, xanchor: "right", y: 1, bgcolor: "rgba(255,255,255,0.7)" },
      xaxis: xa, yaxis: yAxis(g, g.ylabel || "Response") }, PLOT_CONFIG);
  }
  function renderUnknowns(r, s) {
    const xName = esc(s.cols[0] || "X");
    const ok = r.unknowns.filter(u => u.x != null).length;
    return `<div class="opt-label" style="margin-top:10px">Interpolated unknowns: ${ok} of ${r.unknowns.length} read off the curve</div>` +
      T.multi(["Row", "Y" + (r.unknowns.some(u => u.n > 1) ? " (mean)" : ""), `Interpolated ${xName}`, ""],
        r.unknowns.map(u => ({ cls: u.x != null ? "hl" : "", cells: [u.row, `${fmt(u.y)}${u.n > 1 ? ` <span class="pd">(n=${u.n})</span>` : ""}`,
          u.x != null ? `<b>${fmt(u.x)}</b>` : "—", u.note ? `<span class="pd">${esc(u.note)}</span>` : ""] })));
  }
  function renderXYCore(r, s) {
    const pct = Math.round((1 - r.alpha) * 100);
    const xName = esc(s.cols[0] || "X"), yName = esc(s.cols[1] || "Y");
    if (r.model === "linear") {
      const c = r.correlation;
      let h = r.significant
        ? T.summary("sig", `<b>Significant linear relationship</b> (${fmtP(r.p)}, ${r.stars}). Y changes by ${fmt(r.slope)} per unit of X. R² = ${fmt(r.r_squared, 3)}.`)
        : T.summary("ns", `<b>No significant linear relationship</b> (${fmtP(r.p)}). The slope isn't distinguishable from zero (R² = ${fmt(r.r_squared, 3)}).`);
      h += T.table([T.sec("Best-fit line"), T.row("Equation", r.equation), T.row("Slope ± SE", `${fmt(r.slope)} ± ${fmt(r.slope_se)}`),
        T.row("Y-intercept ± SE", `${fmt(r.intercept)} ± ${fmt(r.intercept_se)}`), T.row("X-intercept", fmt(r.x_intercept)),
        T.row(`Slope ${pct}% CI`, ci(...r.slope_ci)), T.row(`Y-intercept ${pct}% CI`, ci(...r.intercept_ci)),
        T.sec("Goodness of fit"), T.row("R²", fmt(r.r_squared)), T.row("Sy.x", fmt(r.sy_x)), T.row("Number of points", r.n),
        T.sec("Is the slope non-zero?"), T.row("F (1, " + r.df + ")", fmt(r.F)), T.row("P value", `${pOnly(r.p)} ${st(r.stars)}`),
        T.sec("Correlation"), T.row("Pearson r", `${fmt(c.pearson_r)}${c.pearson_ci ? ` (${pct}% CI ${ci(...c.pearson_ci)})` : ""}`),
        T.row("Pearson P", pOnly(c.pearson_p)), T.row("Spearman r", fmt(c.spearman_r)), T.row("Spearman P", pOnly(c.spearman_p))]);
      return h;
    }
    const key = r.derived && r.derived[0];
    const nFixed = r.params.filter(p => p.fixed).length;
    let h = T.summary("sig", `<b>${esc(r.model_name)}</b>: ${key && key.value != null ? `best-fit <b>${key.name} = ${fmt(key.value)}</b>${key.ci && key.ci[0] != null ? ` (${pct}% CI ${ci(key.ci[0], key.ci[1])})` : ""}, ` : ""}R² = ${fmt(r.r_squared, 4)}.` +
      (nFixed ? ` ${nFixed} parameter${nFixed > 1 ? "s" : ""} held fixed (${r.params.filter(p => p.fixed).map(p => `${esc(p.name)} = ${fmt(p.value)}`).join(", ")}).` : ""));
    const rows = [T.sec("Best-fit values"), ...r.params.map(p => T.row(esc(p.name), p.fixed ? `${fmt(p.value)} <span class="pd">(fixed)</span>` : `${fmt(p.value)} ± ${fmt(p.se)}`)),
      ...r.derived.map(d => T.row(esc(d.name), fmt(d.value), "hl")),
      T.sec(`${pct}% confidence intervals`), ...r.params.filter(p => !p.fixed).map(p => T.row(esc(p.name), ci(...p.ci))),
      ...r.derived.filter(d => d.ci).map(d => T.row(esc(d.name), ci(d.ci[0], d.ci[1]))),
      T.sec("Goodness of fit"), T.row("R²", fmt(r.r_squared)), T.row("Sy.x", fmt(r.sy_x)), T.row("Sum of squares", fmt(r.ss_res)),
      T.row("Degrees of freedom", r.df), T.row("Number of points", r.n)];
    h += T.table(rows);
    if (r.comparison) h += renderComparison(r.comparison, r.alpha);
    h += `<p class="note">"±" values are standard errors. ${r.x_is_log ? "X was analyzed as log10(concentration). " : ""}${r.dropped ? `${r.dropped} point(s) with X ≤ 0 were left out (no logarithm).` : ""}</p>`;
    return h;
  }

  function renderComparison(c, alpha) {
    if (c.error) return `<p class="note warn">${esc(c.error)}</p>`;
    const nm = id => id === c.a ? c.name_a : c.name_b;
    let verdict;
    if (c.f_test) {
      const f = c.f_test;
      verdict = f.p < alpha
        ? `The data support the more complex model: <b>${esc(nm(f.complex))}</b> (extra sum-of-squares F test, ${fmtP(f.p)}).`
        : `The extra parameter(s) don't improve the fit enough, so the simpler model is preferred: <b>${esc(nm(f.simple))}</b> (${fmtP(f.p)}).`;
    } else if (c.prob_a != null) {
      const best = c.aicc_preferred, pr = best === c.a ? c.prob_a : 1 - c.prob_a;
      verdict = `<b>${esc(nm(best))}</b> is more likely to be correct (${fmt(pr * 100, 3)}% probability by AICc).`;
    } else verdict = "Not enough points to compare these models.";
    const rows = [T.sec("Model comparison"), T.row(`Sum of squares, df: ${esc(c.name_a)}`, `${fmt(c.ss_a)}, ${c.df_a}`),
      T.row(`Sum of squares, df: ${esc(c.name_b)}`, `${fmt(c.ss_b)}, ${c.df_b}`)];
    if (c.f_test) rows.push(T.row(`F (${c.f_test.dfn}, ${c.f_test.dfd})`, fmt(c.f_test.F)), T.row("P value", pOnly(c.f_test.p)));
    if (c.prob_a != null) rows.push(T.row("AICc difference (B − A)", fmt(c.delta_aicc)), T.row(`Probability ${esc(c.name_a)} is correct`, fmt(c.prob_a * 100, 3) + "%"));
    const fb = c.fit_b, key = fb && fb.derived && fb.derived[0];
    if (key && key.value != null) rows.push(T.row(`${esc(key.name)} from ${esc(c.name_b)}`, fmt(key.value)));
    return `<div class="summary ns" style="margin-top:10px">${verdict}</div>` + T.table(rows);
  }

  // ---------------------------------------------------------------- correlation matrix
  function renderCorrMatrix(r) {
    const pct = Math.round((1 - r.alpha) * 100);
    const sig = r.pairs.filter(p => p.significant);
    const top = r.pairs[0];
    let h = T.summary(sig.length ? "sig" : "ns", sig.length
      ? `<b>${sig.length} of ${r.pairs.length} pairs</b> are significantly correlated. Strongest: <b>${esc(top.a)}</b> and <b>${esc(top.b)}</b> (r = ${fmt(top.r, 3)}, ${fmtP(top.p)}).`
      : `<b>No significant correlations</b> among the ${r.names.length} variables.`);
    h += `<div class="opt-label">${esc(r.test_name)}: r</div>` + T.multi(["", ...r.names.map(esc)],
      r.names.map((n, i) => [esc(n), ...r.names.map((_, j) => i === j ? "1" : r.r[i][j] == null ? "—" : `${fmt(r.r[i][j], 3)} ${st(stars(r.p[i][j]))}`)]));
    h += `<div class="opt-label" style="margin-top:10px">All pairs, strongest first</div>` +
      T.multi(["Pair", "r", r.method === "pearson" ? `${pct}% CI` : "", "P", "n", ""], r.pairs.map(p => ({ cls: p.significant ? "hl" : "",
        cells: [`${esc(p.a)} vs ${esc(p.b)}`, fmt(p.r, 3), p.ci ? ci(p.ci[0], p.ci[1]) : "", pOnly(p.p), p.n, st(p.stars)] })));
    h += `<div class="opt-label" style="margin-top:10px">Descriptive statistics</div>` +
      T.multi(["", "n", "Mean", "SD"], r.describe.map(d => [esc(d.name), d.n, fmt(d.mean), fmt(d.sd)]));
    h += `<p class="note">P values are not corrected for the number of pairs tested (${r.pairs.length}).</p>`;
    return h;
  }
  function drawCorrMatrix(el, r, s) {
    const g = s.graph, k = r.names.length;
    const z = r.r.map(row => row.map(v => v == null ? null : v));
    const annotations = [];
    if (g.showValues) r.r.forEach((row, i) => row.forEach((v, j) => {
      if (v == null) return;
      annotations.push({ x: j, y: i, text: `${fmt(v, 2)}${i !== j && r.p[i][j] < r.alpha ? "<br>" + stars(r.p[i][j]) : ""}`, showarrow: false,
        font: { size: Math.max(9, (g.fontSize || 13) - (k > 6 ? 3 : 1)), color: Math.abs(v) > 0.6 ? "#fff" : "#1b2130" } });
    }));
    styledReact(el, [{ type: "heatmap", z, x: r.names.map((_, j) => j), y: r.names.map((_, i) => i), zmin: -1, zmax: 1,
      colorscale: [[0, "#2166ac"], [0.25, "#92c5de"], [0.5, "#f7f7f7"], [0.75, "#f4a582"], [1, "#b2182b"]],
      colorbar: { title: { text: "r" }, thickness: 12 }, hovertemplate: "r = %{z:.3f}<extra></extra>", xgap: 2, ygap: 2 }],
      { ...baseLayout(g), annotations, margin: { l: 90, r: 20, t: g.title ? 44 : 20, b: 80 },
        xaxis: { tickvals: r.names.map((_, j) => j), ticktext: r.names.map(esc), showgrid: false, zeroline: false },
        yaxis: { tickvals: r.names.map((_, i) => i), ticktext: r.names.map(esc), autorange: "reversed", showgrid: false, zeroline: false, scaleanchor: "x" } },
      PLOT_CONFIG);
  }

  // ---------------------------------------------------------------- PCA
  function renderPCA(r) {
    const k = r.eigenvalues.length, show = Math.min(k, 4);
    let h = T.summary("sig", `The first two components explain <b>${fmt(r.cumulative_pct[Math.min(1, k - 1)], 3)}%</b> of the variation in ${r.names.length} variables. ` +
      `${r.kaiser} component${r.kaiser === 1 ? " has" : "s have"} an eigenvalue above 1 (Kaiser rule)${r.standardized ? "" : " (raw units: the rule applies to standardized data only)"}. ` +
      `PC1 is driven mostly by ${topVars(r, 0)}.`);
    h += T.multi(["Component", "Eigenvalue", "% of variance", "Cumulative %"], r.eigenvalues.map((e, i) => ({ cls: e > 1 && r.standardized ? "hl" : "",
      cells: [`PC${i + 1}`, fmt(e, 4), fmt(r.variance_pct[i], 3), fmt(r.cumulative_pct[i], 4)] })));
    h += `<div class="opt-label" style="margin-top:10px">Loadings${r.standardized ? " (correlation of each variable with each component)" : ""}</div>` +
      T.multi(["Variable", ...Array.from({ length: show }, (_, i) => `PC${i + 1}`)], r.names.map((n, v) => [esc(n), ...Array.from({ length: show }, (_, i) => {
        const L = r.loadings[v][i]; return Math.abs(L) >= 0.5 ? `<b>${fmt(L, 3)}</b>` : fmt(L, 3);
      })]));
    h += `<p class="note">Bold: |loading| ≥ 0.5. ${r.n} rows used${r.dropped ? `; ${r.dropped} left out (missing values)` : ""}. Component signs are arbitrary: only the pattern matters.</p>`;
    return h;
  }
  function topVars(r, pc) {
    return r.names.map((n, v) => [n, r.loadings[v][pc]]).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 2)
      .map(([n, L]) => `<b>${esc(n)}</b> (${L > 0 ? "+" : "−"})`).join(" and ");
  }
  function drawPCA(el, r, s) {
    const g = s.graph;
    if (g.pcaPlot === "scree") {
      styledReact(el, [{ type: "bar", x: r.eigenvalues.map((_, i) => `PC${i + 1}`), y: r.variance_pct, marker: { color: color(g, 0, "Points") + "aa", line: { color: color(g, 0, "Points"), width: 1.4 } },
        hovertemplate: "%{x}: %{y:.1f}%<extra></extra>", name: "% of variance" },
        { x: r.eigenvalues.map((_, i) => `PC${i + 1}`), y: r.cumulative_pct, mode: "lines+markers", line: { color: "#1b2130", width: 2 }, marker: { size: g.pointSize }, name: "Cumulative %", hovertemplate: "Cumulative %{y:.1f}%<extra></extra>" }],
        { ...baseLayout(g), showlegend: true, legend: { orientation: "h", y: 1.08, x: 0 }, xaxis: axis(g), yaxis: yAxis(g, "% of variance", { range: [0, 105] }) }, PLOT_CONFIG);
      return;
    }
    if (r.eigenvalues.length < 2) { Plotly.purge(el); el.innerHTML = `<div class="empty"><div>Need at least 2 components for a biplot.</div></div>`; return; }
    const sc = r.scores, px = sc.map(p => p[0]), py = sc.map(p => p[1]);
    const span = Math.max(...px.map(Math.abs), ...py.map(Math.abs)) || 1;
    const vmax = Math.max(...r.vectors[0].map(Math.abs), ...r.vectors[1].map(Math.abs)) || 1, f = span / vmax * 0.85;
    const shapes = [], annotations = [];
    r.names.forEach((n, v) => {
      const x = r.vectors[0][v] * f, y = r.vectors[1][v] * f;
      annotations.push({ x, y, ax: 0, ay: 0, xref: "x", yref: "y", axref: "x", ayref: "y", showarrow: true, arrowhead: 2, arrowwidth: 1.6, arrowcolor: color(g, 1, "Loadings"), text: "" },
        { x: x * 1.1, y: y * 1.1, text: `<b>${esc(n)}</b>`, showarrow: false, font: { color: color(g, 1, "Loadings"), size: (g.fontSize || 13) - 1 } });
    });
    styledReact(el, [{ x: px, y: py, mode: g.pcaLabels ? "markers+text" : "markers", text: px.map((_, i) => String(i + 1)), textposition: "top center",
      marker: { color: color(g, 0, "Points"), size: g.pointSize, opacity: 0.8, line: { color: "#fff", width: 1 } }, hovertemplate: "Row %{text}: PC1 %{x:.3g}, PC2 %{y:.3g}<extra></extra>" }],
      { ...baseLayout(g), shapes, annotations,
        xaxis: axis(g, { title: { text: `PC1 (${fmt(r.variance_pct[0], 3)}%)` }, zeroline: true, zerolinecolor: "#d0d4db" }),
        yaxis: yAxis(g, `PC2 (${fmt(r.variance_pct[1], 3)}%)`, { zeroline: true, zerolinecolor: "#d0d4db" }) }, PLOT_CONFIG);
  }

  // ---------------------------------------------------------------- multiple / logistic regression
  function renderMLR(r) {
    const pct = Math.round((1 - r.alpha) * 100);
    const preds = r.coefs.slice(1), sig = preds.filter(c => c.p < r.alpha);
    let h = T.summary(r.p < r.alpha ? "sig" : "ns", `The predictors together explain <b>${fmt(r.r_squared * 100, 3)}%</b> of the variation in <b>${esc(r.y_name)}</b> (R², ${fmtP(r.p)}). ` +
      (sig.length ? `Significant on their own (adjusted for the others): ${sig.map(c => `<b>${esc(c.name)}</b> (${c.estimate > 0 ? "+" : ""}${fmt(c.estimate, 3)} per unit)`).join(", ")}.` : "No single predictor is significant after adjusting for the others."));
    h += T.multi(["", "Estimate", "Std. error", `${pct}% CI`, "P", "", "VIF"], r.coefs.map(c => ({ cls: c.name !== "Intercept" && c.p < r.alpha ? "hl" : "",
      cells: [esc(c.name), fmt(c.estimate), fmt(c.se, 3), ci(...c.ci), pOnly(c.p), st(c.stars), c.vif == null ? "" : `${fmt(c.vif, 3)}${c.vif > 5 ? " ⚠︎" : ""}`] })));
    h += T.table([T.sec("Goodness of fit"), T.row("R²", fmt(r.r_squared)), T.row("Adjusted R²", fmt(r.adj_r_squared)), T.row("Sy.x (residual SD)", fmt(r.sy_x)),
      T.row(`F (${r.coefs.length - 1}, ${r.df})`, fmt(r.F)), T.row("P value (model)", pOnly(r.p)), T.row("Rows used", `${r.n}${r.dropped ? ` (${r.dropped} left out: missing values)` : ""}`)]);
    if (r.coefs.some(c => c.vif > 5)) h += `<p class="note warn">⚠︎ VIF above 5: that predictor is strongly correlated with the others, so its coefficient is unstable.</p>`;
    h += `<p class="note">Each estimate is the change in ${esc(r.y_name)} per 1-unit increase in that predictor, holding the others constant.</p>`;
    return h;
  }
  function drawMLR(el, r, s) {
    const g = s.graph, a = r.points.actual, p = r.points.predicted, lo = Math.min(...a, ...p), hi = Math.max(...a, ...p);
    styledReact(el, [{ x: [lo, hi], y: [lo, hi], mode: "lines", line: { color: "#9aa3b2", dash: "dot" }, hoverinfo: "skip" },
      { x: p, y: a, mode: "markers", marker: { color: color(g, 0, "Points"), size: g.pointSize, line: { color: "#fff", width: 1 } }, hovertemplate: "Predicted %{x:.4g}, actual %{y:.4g}<extra></extra>" }],
      { ...baseLayout(g), annotations: [{ xref: "paper", yref: "paper", x: 0.02, y: 0.98, xanchor: "left", yanchor: "top", showarrow: false, text: `R² = ${fmt(r.r_squared, 3)}`, font: { color: "#6b7385" } }],
        xaxis: axis(g, { title: { text: `Predicted ${esc(r.y_name)}` } }), yaxis: yAxis(g, `Actual ${esc(r.y_name)}`) }, PLOT_CONFIG);
  }
  function renderCox(r) {
    const pct = Math.round((1 - r.alpha) * 100);
    const sig = r.coefs.filter(c => c.p < r.alpha);
    let h = T.summary(r.p < r.alpha ? "sig" : "ns", `The predictors together are ${r.p < r.alpha ? "<b>significantly</b>" : "not significantly"} related to survival (likelihood ratio ${fmtP(r.p)}). ` +
      (sig.length ? sig.map(c => `Each 1-unit increase in <b>${esc(c.name)}</b> multiplies the hazard (risk of the event at any moment) by <b>${fmt(c.hr, 3)}</b> (${pct}% CI ${ci(...c.hr_ci)})`).join("; ") + "." : "No single predictor is significant after adjusting for the others."));
    h += T.multi(["", "Hazard ratio", `${pct}% CI`, "β (log hazard)", "Std. error", "z", "P", ""], r.coefs.map(c => ({ cls: c.p < r.alpha ? "hl" : "",
      cells: [esc(c.name), fmt(c.hr), ci(...c.hr_ci), fmt(c.estimate), fmt(c.se, 3), fmt(c.z, 3), pOnly(c.p), st(c.stars)] })));
    h += T.table([T.sec("Model"), T.row(`Likelihood ratio χ² (df ${r.df})`, `${fmt(r.lr_chi2)}, P ${pOnly(r.p)}`),
      T.row("Wald χ²", `${fmt(r.wald_chi2)}, P ${pOnly(r.wald_p)}`), T.row("Score (log-rank) χ²", `${fmt(r.score_chi2)}, P ${pOnly(r.score_p)}`),
      T.row("Concordance (Harrell's C)", fmt(r.concordance, 3)), T.row("Log likelihood", fmt(r.loglik)),
      T.row("Rows used (events)", `${r.n} (${r.n_events})${r.dropped ? `; ${r.dropped} left out: missing values` : ""}`)]);
    if (r.n_events < 10 * r.coefs.length) h += `<p class="note warn">⚠︎ Few events per predictor (rule of thumb: ≥ 10). Estimates may be unreliable; consider fewer predictors.</p>`;
    h += `<p class="note">Ties in event times use Efron's method. The model assumes each predictor's effect on the hazard is constant over time (proportional hazards). Graph: hazard ratios with ${pct}% CIs (forest plot).</p>`;
    return h;
  }
  function drawForest(el, r, s) {
    const g = s.graph, cs = [...r.coefs].reverse(), c0 = color(g, 0, "Points");
    const traces = [{ type: "scatter", mode: "markers", x: cs.map(c => c.hr), y: cs.map(c => esc(c.name)),
      error_x: { type: "data", symmetric: false, array: cs.map(c => c.hr_ci[1] - c.hr), arrayminus: cs.map(c => c.hr - c.hr_ci[0]), color: c0, thickness: 1.6, width: 6 },
      marker: { symbol: "square", color: c0, size: g.pointSize + 2 }, hovertemplate: "%{y}: HR %{x:.3g}<extra></extra>" }];
    styledReact(el, traces, { ...baseLayout(g), margin: { l: 120, r: 20, t: g.title ? 44 : 20, b: 52 },
      shapes: [{ type: "line", xref: "x", yref: "paper", x0: 1, x1: 1, y0: 0, y1: 1, line: { color: "#8a93a3", width: 1.2, dash: "dash" } }],
      xaxis: axis(g, { type: "log", title: { text: "Hazard ratio (log scale)" } }), yaxis: axis(g, { type: "category", automargin: true }) }, PLOT_CONFIG);
  }
  function renderLogistic(r) {
    const pct = Math.round((1 - r.alpha) * 100);
    const sig = r.coefs.slice(1).filter(c => c.p < r.alpha);
    let h = T.summary(r.p < r.alpha ? "sig" : "ns", `The model predicts <b>${esc(r.y_name)}</b> ${r.p < r.alpha ? "significantly better than chance" : "no better than chance"} (likelihood ratio ${fmtP(r.p)}; AUC = ${fmt(r.auc, 3)}). ` +
      (sig.length ? sig.map(c => `Each 1-unit increase in <b>${esc(c.name)}</b> multiplies the odds by <b>${fmt(c.or, 3)}</b> (${pct}% CI ${ci(...c.or_ci)})`).join("; ") + "." : "No single predictor is significant after adjusting for the others."));
    h += T.multi(["", "Odds ratio", `${pct}% CI`, "β (log odds)", "Std. error", "P", ""], r.coefs.map(c => ({ cls: c.name !== "Intercept" && c.p < r.alpha ? "hl" : "",
      cells: [esc(c.name), c.name === "Intercept" ? "—" : fmt(c.or), c.name === "Intercept" ? "" : ci(...c.or_ci), fmt(c.estimate), fmt(c.se, 3), pOnly(c.p), st(c.stars)] })));
    h += T.table([T.sec("Model"), T.row("Likelihood ratio χ²", `${fmt(r.lr_chi2)}, P ${pOnly(r.p)}`), T.row("Area under ROC curve", fmt(r.auc, 3)),
      T.row("McFadden pseudo-R²", fmt(r.mcfadden_r2, 3)), T.row("Tjur R²", fmt(r.tjur_r2, 3)), T.row("Correctly classified (cutoff 0.5)", `${fmt(r.accuracy * 100, 3)}%`),
      T.row("Rows used (events)", `${r.n} (${r.n_events})${r.dropped ? `; ${r.dropped} left out: missing values` : ""}`)]);
    if (r.n_events < 10 * (r.coefs.length - 1) || r.n - r.n_events < 10 * (r.coefs.length - 1)) h += `<p class="note warn">⚠︎ Few events per predictor (rule of thumb: ≥ 10). Estimates may be unreliable; consider fewer predictors.</p>`;
    h += `<p class="note">Graph: ROC curve of the model's predicted probabilities. Odds ratios use Wald confidence intervals.</p>`;
    return h;
  }

  // ---------------------------------------------------------------- ROC & Bland-Altman
  function renderROC(r) {
    const pct = Math.round((1 - r.alpha) * 100);
    const quality = r.auc >= 0.9 ? "excellent" : r.auc >= 0.8 ? "good" : r.auc >= 0.7 ? "fair" : r.auc >= 0.6 ? "poor" : "no better than chance";
    let h = T.summary(r.p < r.alpha ? "sig" : "ns", `Area under the ROC curve = <b>${fmt(r.auc, 3)}</b> (${pct}% CI ${ci(...r.ci)}): <b>${quality}</b> separation of ${esc(r.names[1])} from ${esc(r.names[0])} (${fmtP(r.p)}). ` +
      `Best cutoff: ${r.direction === "higher" ? "≥" : "≤"} <b>${fmt(r.best.cut)}</b> (sensitivity ${fmt(r.best.sens, 3)}%, specificity ${fmt(r.best.spec, 3)}%).`);
    h += T.table([T.sec("Area under the ROC curve"), T.row("Area", fmt(r.auc, 4)), T.row("Std. error", fmt(r.se, 3)), T.row(`${pct}% CI`, ci(...r.ci)),
      T.row("P value (vs 0.5)", `${pOnly(r.p)} ${st(r.stars)}`), T.row(`${esc(r.names[0])} (controls)`, r.n_controls), T.row(`${esc(r.names[1])} (patients)`, r.n_patients),
      T.row("Patients have", `${r.direction} values`)]);
    h += `<div class="opt-label" style="margin-top:10px">Cutoffs (patients if value ${r.direction === "higher" ? "≥" : "≤"} cutoff)</div>` +
      T.multi(["Cutoff", "Sensitivity %", "Specificity %", "Likelihood ratio"], r.table.map(t => ({ cls: t === r.best || (t.cut === r.best.cut) ? "hl" : "",
        cells: [fmt(t.cut), fmt(t.sens, 3), fmt(t.spec, 3), t.lr == null ? "—" : fmt(t.lr, 3)] })));
    h += `<p class="note">Highlighted: the cutoff with the highest sensitivity + specificity (Youden index). SE by Hanley & McNeil.</p>`;
    return h;
  }
  function drawROC(el, r, s) {
    const g = s.graph, c = color(g, 0, "Curve");
    styledReact(el, [
      { x: [0, 100], y: [0, 100], mode: "lines", line: { color: "#9aa3b2", dash: "dot", width: 1.2 }, hoverinfo: "skip" },
      { x: r.curve.map(p => p.fpr * 100), y: r.curve.map(p => p.tpr * 100), mode: "lines+markers", line: { color: c, width: 2.4, shape: "linear" },
        marker: { size: Math.max(3, g.pointSize - 3), color: c }, customdata: r.curve.map(p => p.cut == null ? "" : fmt(p.cut)),
        hovertemplate: "Cutoff %{customdata}: sensitivity %{y:.1f}%, 100% − specificity %{x:.1f}%<extra></extra>" },
      ...(r.best ? [{ x: [100 - r.best.spec], y: [r.best.sens], mode: "markers", marker: { symbol: "star", size: g.pointSize + 8, color: color(g, 1, "Best cutoff") }, hoverinfo: "skip" }] : []),
    ], { ...baseLayout(g), annotations: [{ xref: "paper", yref: "paper", x: 0.98, y: 0.04, xanchor: "right", showarrow: false, text: `AUC = ${fmt(r.auc, 3)}`, font: { size: (g.fontSize || 13) + 1 } }],
      xaxis: axis(g, { title: { text: "100% − Specificity %" }, range: [-2, 102] }), yaxis: yAxis(g, "Sensitivity %", { range: [-2, 102] }) }, PLOT_CONFIG);
  }
  function renderBA(r) {
    const pct = Math.round((1 - r.alpha) * 100);
    let h = T.summary(r.p_bias < r.alpha ? "sig" : "ns", `On average <b>${esc(r.names[1])}</b> reads <b>${fmt(Math.abs(r.bias))} ${r.bias >= 0 ? "higher" : "lower"}</b> than <b>${esc(r.names[0])}</b> (bias${r.p_bias < r.alpha ? ", significantly different from 0" : ", not significantly different from 0"}, ${fmtP(r.p_bias)}). ` +
      `95% of differences fall between <b>${fmt(r.loa[0])}</b> and <b>${fmt(r.loa[1])}</b>. Whether that range is acceptable is a clinical judgement.`);
    h += T.table([T.sec(`Bland-Altman: ${esc(r.names[1])} − ${esc(r.names[0])}`), T.row("Bias (mean difference)", fmt(r.bias)), T.row(`${pct}% CI of bias`, ci(...r.bias_ci)),
      T.row("SD of differences", fmt(r.sd)), T.row("95% limits of agreement", ci(...r.loa)),
      T.row(`Lower limit ${pct}% CI`, ci(...r.loa_lo_ci)), T.row(`Upper limit ${pct}% CI`, ci(...r.loa_hi_ci)), T.row("Number of samples", r.n),
      T.sec("Does the difference depend on the size of the value?"), T.row("Slope of difference vs average", fmt(r.trend_slope)), T.row("P value", pOnly(r.trend_p))]);
    if (r.trend_p != null && r.trend_p < r.alpha) h += `<p class="note warn">⚠︎ The difference grows (or shrinks) with the size of the measurement, so a single bias doesn't describe the disagreement well. Consider analyzing ratios (log values).</p>`;
    return h;
  }
  function drawBA(el, r, s) {
    const g = s.graph, c = color(g, 0, "Points");
    const xs = r.points.avg, lo = Math.min(...xs), hi = Math.max(...xs), pad = (hi - lo) * 0.05 || 1;
    const line = (y, dash, col, label) => ({ x: [lo - pad, hi + pad], y: [y, y], mode: "lines", line: { color: col, width: 1.6, dash }, hoverinfo: "skip", name: label });
    styledReact(el, [
      line(0, "dot", "#9aa3b2"), line(r.bias, "solid", "#1b2130"), line(r.loa[0], "dash", "#d62728"), line(r.loa[1], "dash", "#d62728"),
      { x: xs, y: r.points.diff, mode: "markers", marker: { color: c, size: g.pointSize, line: { color: "#fff", width: 1 } }, hovertemplate: "Average %{x:.4g}, difference %{y:.4g}<extra></extra>" },
    ], { ...baseLayout(g), annotations: [["Bias", r.bias], ["+95% LoA", r.loa[1]], ["−95% LoA", r.loa[0]]].map(([t, y]) => ({ x: 1, xref: "paper", xanchor: "right", y, yanchor: "bottom",
        text: `${t} ${fmt(y, 3)}`, showarrow: false, font: { size: (g.fontSize || 13) - 2, color: "#6b7385" } })),
      xaxis: axis(g, { title: { text: `Average of ${esc(r.names[0])} and ${esc(r.names[1])}` } }), yaxis: yAxis(g, `${esc(r.names[1])} − ${esc(r.names[0])}`) }, PLOT_CONFIG);
  }

  // ---------------------------------------------------------------- figure layout
  function layoutSummary(p) {
    const box = document.createElement("div");
    try { box.innerHTML = TYPES[p.sheet.type].renderResults(p.result, p.sheet); } catch { return ""; }
    const sm = box.querySelector(".summary");
    return sm ? sm.textContent.trim().slice(0, 140) : "";
  }
  function drawLayout(el, r, s) {
    Plotly.purge(el);
    const ncol = s.options.ncol || 2;
    el.innerHTML = `<div class="layout-grid" style="grid-template-columns:repeat(${ncol},1fr)">${r.panels.map((p, i) =>
      `<div class="layout-panel">${s.options.letters ? `<span class="panel-letter" style="font-size:${s.graph.letterSize || 16}px">${String.fromCharCode(65 + i)}</span>` : ""}<div class="layout-plot" id="lp-${i}"></div></div>`).join("")}</div>`;
    r.panels.forEach((p, i) => {
      const div = document.getElementById(`lp-${i}`);
      if (p.error) { div.innerHTML = `<div class="empty"><div>${esc(p.sheet.title)}:<br>${esc(p.error)}</div></div>`; return; }
      styleCtx = p.sheet.graph;
      try { TYPES[p.sheet.type].draw(div, p.result, p.sheet); } catch (e) { div.textContent = "Couldn't draw this graph."; }
    });
  }
  async function exportLayoutSVG() {
    const s = active(), r = lastResult, g = s.graph;
    const [wIn] = EXPORT_SIZES[g.exportSize] || EXPORT_SIZES["2"];
    const ncol = Math.min(s.options.ncol || 2, r.panels.length), nrow = Math.ceil(r.panels.length / ncol);
    const pw = Math.round(wIn * 96 / ncol), ph = Math.round(pw * 0.78), W = pw * ncol, H = ph * nrow;
    let body = "";
    for (let i = 0; i < r.panels.length; i++) {
      const div = document.getElementById(`lp-${i}`);
      if (!div || !div.data) continue;
      const url = await Plotly.toImage(div, { format: "svg", width: pw, height: ph });
      let svg = decodeURIComponent(url.replace(/^data:image\/svg\+xml,/, ""));
      svg = svg.replace(/^<svg/, `<svg x="${(i % ncol) * pw}" y="${Math.floor(i / ncol) * ph}"`);
      body += `<g id="panel-${String.fromCharCode(65 + i)}">${svg}</g>`;
      if (s.options.letters) body += `<text x="${(i % ncol) * pw + 6}" y="${Math.floor(i / ncol) * ph + (g.letterSize || 16) + 2}" font-family="Arial, Helvetica, sans-serif" font-weight="bold" font-size="${g.letterSize || 16}">${String.fromCharCode(65 + i)}</text>`;
    }
    const doc = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${body}</svg>`;
    try {
      const res = await api("/api/exports", { method: "POST", body: JSON.stringify({ filename: `${projectName} - ${s.title}`, data_url: "data:image/svg+xml," + encodeURIComponent(doc) }) });
      toast(`Saved <b>${esc(res.file)}</b> (editable SVG) to the exports folder`, "exports");
    } catch (e) { toast(esc(e.message || "Export failed.")); }
  }
  async function exportLayout(convert) {
    const s = active(), r = lastResult, g = s.graph;
    if (!r || !r.panels.length) return;
    if (!convert) return exportLayoutSVG();
    const [wIn] = EXPORT_SIZES[g.exportSize] || EXPORT_SIZES["2"];
    const ncol = Math.min(s.options.ncol || 2, r.panels.length), nrow = Math.ceil(r.panels.length / ncol);
    const dpi = Number(g.exportDpi || 300), scale = dpi / 96;
    const pw = Math.round(wIn * 96 / ncol), ph = Math.round(pw * 0.78);
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(pw * ncol * scale); canvas.height = Math.round(ph * nrow * scale);
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, canvas.width, canvas.height);
    for (let i = 0; i < r.panels.length; i++) {
      const div = document.getElementById(`lp-${i}`);
      if (!div || !div.data) continue;
      const url = await Plotly.toImage(div, { format: "png", width: pw, height: ph, scale });
      const img = await new Promise(ok => { const im = new Image(); im.onload = () => ok(im); im.src = url; });
      const x = (i % ncol) * pw * scale, y = Math.floor(i / ncol) * ph * scale;
      ctx.drawImage(img, x, y, pw * scale, ph * scale);
      if (s.options.letters) {
        ctx.fillStyle = "#000"; ctx.font = `bold ${Math.round((g.letterSize || 16) * scale)}px Helvetica, Arial, sans-serif`;
        ctx.textBaseline = "top"; ctx.fillText(String.fromCharCode(65 + i), x + 6 * scale, y + 4 * scale);
      }
    }
    try {
      const res = await api("/api/exports", { method: "POST", body: JSON.stringify({ filename: `${projectName} - ${s.title}`,
        data_url: canvas.toDataURL("image/png"), fmt: convert === "tiff" ? "tiff" : null, dpi }) });
      toast(`Saved <b>${esc(res.file)}</b> to the exports folder`, "exports");
    } catch (e) { toast(esc(e.message || "Export failed.")); }
  }

  // ---------------------------------------------------------------- survival
  function renderSurvivalResults(r) {
    let h = "";
    const c = r.curves;
    if (r.logrank) {
      h += r.p < r.alpha
        ? T.summary("sig", `<b>Survival differs between groups</b> (log-rank ${fmtP(r.p)}, ${stars(r.p)}).${r.hazard_ratio ? ` Hazard ratio ${esc(r.hazard_ratio.label)}: <b>${fmt(r.hazard_ratio.value, 3)}</b>.` : ""}`)
        : T.summary("ns", `<b>No significant difference in survival</b> (log-rank ${fmtP(r.p)}).`);
    } else h += T.summary("ns", `Kaplan-Meier estimate for one group. Add another group column to compare.`);
    h += T.multi(["", ...c.map(x => esc(x.name))], [["Subjects", ...c.map(x => x.n)], ["Events", ...c.map(x => x.events)],
      ["Censored", ...c.map(x => x.n - x.events)], ["Median survival", ...c.map(x => x.median == null ? "Undefined" : fmt(x.median))]]);
    if (r.logrank) {
      const rows = [T.sec("Log-rank (Mantel-Cox) test"), T.row("Chi-square, df", `${fmt(r.logrank.chi2)}, ${r.logrank.df}`),
        T.row("P value", `${pOnly(r.p)} ${st(stars(r.p))}`)];
      if (r.hazard_ratio) rows.push(T.sec("Hazard ratio (Mantel-Haenszel)"), T.row(esc(r.hazard_ratio.label), fmt(r.hazard_ratio.value)),
        T.row("95% CI", ci(...r.hazard_ratio.ci)));
      if (r.median_ratio) rows.push(T.row("Ratio of medians", fmt(r.median_ratio)));
      h += T.table(rows);
    }
    h += `<p class="note">"Undefined" median: survival never fell to 50%.</p>`;
    return h;
  }

  // ---------------------------------------------------------------- contingency
  function renderContingencyResults(r) {
    const pct = Math.round((1 - r.alpha) * 100);
    const sig = r.p < r.alpha;
    let h = sig
      ? T.summary("sig", `<b>Significant association</b> between group and outcome (${esc(r.primary)}, ${fmtP(r.p)}, ${stars(r.p)}).`)
      : T.summary("ns", `<b>No significant association</b> between group and outcome (${esc(r.primary)}, ${fmtP(r.p)}).`);
    h += T.multi(["", ...r.cols.map(esc), "Total"], r.table.map((row, i) => [esc(r.rows[i]),
      ...row.map((v, j) => `${v} <span class="pd">(${fmt(r.row_pct[i][j], 3)}%)</span>`), row.reduce((a, b) => a + b, 0)]));
    const rows = [];
    if (r.fisher) rows.push(T.sec("Fisher's exact test"), T.row("P value (two-sided)", `${pOnly(r.fisher.p)} ${st(stars(r.fisher.p))}`));
    rows.push(T.sec("Chi-square test"), T.row("Chi-square, df", `${fmt(r.chi_square.chi2)}, ${r.chi_square.df}`), T.row("P value", pOnly(r.chi_square.p)));
    if (r.odds_ratio) {
      rows.push(T.sec("Effect size"), T.row("Odds ratio", fmt(r.odds_ratio.value)), T.row(`${pct}% CI`, ci(...r.odds_ratio.ci)),
        T.row(`Relative risk (${esc(r.cols[0])})`, fmt(r.relative_risk.value)), T.row(`${pct}% CI`, ci(...r.relative_risk.ci)),
        T.row("Risk difference", fmt(r.risk_difference.value)));
    }
    h += T.table(rows);
    if (r.chi_square.min_expected < 5 && !r.fisher) h += `<p class="note warn">⚠︎ Some expected counts are below 5, so the chi-square P value is approximate.</p>`;
    if (r.odds_ratio) h += `<p class="note">Odds ratio and relative risk compare the first row with the second, for the outcome in the first column.</p>`;
    return h;
  }

  // ======================================================================
  // graphs
  // ======================================================================
  function drawPlot() {
    const s = active(), el = $("plot");
    el.style.height = s.type === "layout" && lastResult ? "auto" : "";
    if (!lastResult) {
      Plotly.purge(el);
      el.innerHTML = `<div class="empty"><div>Your graph appears here once there is enough data.<br>Click <b>Example</b> to see how it works.</div></div>`;
      return;
    }
    if (el.querySelector(".empty")) el.innerHTML = "";
    styleCtx = s.graph;
    TYPES[s.type].draw(el, lastResult, masked(s));
    if (s.graph.legend === "hide" && el.layout && el.layout.showlegend) Plotly.relayout(el, { showlegend: false });
  }

  function bracketLayout(pairs, top, span) {
    // stack brackets so overlapping ones sit on different levels
    const levels = [];
    const sorted = [...pairs].sort((a, b) => (a.j - a.i) - (b.j - b.i) || a.i - b.i);
    const step = span * 0.085, out = [];
    sorted.forEach(p => {
      let lv = 0;
      while ((levels[lv] || []).some(q => !(q.j < p.i || q.i > p.j))) lv++;
      (levels[lv] = levels[lv] || []).push(p);
      out.push({ ...p, y: top + step * (lv + 1) });
    });
    return { items: out, height: step * (levels.length + 1) };
  }

  function drawGroups(el, r, s) {
    if (r.kind === "freq") return drawFreq(el, r, s);
    const g = s.graph, traces = [], shapes = [], annotations = [];
    const summary = s.type === "summary";
    const cols = summary ? [] : filledCols(s);
    const groups = summary ? r.groups.map(() => []) : cols.map(j => s.data.map(row => num(row[j])).filter(v => v !== null));
    let ymax = -Infinity, ymin = Infinity;
    groups.forEach((vals, i) => {
      const stt = r.groups[i] || {}, c = color(g, i, stt.name);
      const err = g.err === "sem" ? stt.sem : g.err === "ci95" ? stt.ci95 : g.err === "sd" ? stt.sd : 0;
      vals.forEach(v => { ymax = Math.max(ymax, v); ymin = Math.min(ymin, v); });
      if (summary) ymin = Math.min(ymin, (stt.mean ?? 0) - (err || 0));
      ymax = Math.max(ymax, (stt.mean ?? 0) + (err || 0));
      if (g.style === "lines") {
        // before-after: one line per subject (row); points are drawn on the lines
        if (i === 0) s.data.forEach(row => {
          const pts = cols.map((j, gi) => [gi, num(row[j])]).filter(p => p[1] !== null);
          if (pts.length >= 2) traces.push({ type: "scatter", mode: "lines+markers", x: pts.map(p => p[0]), y: pts.map(p => p[1]),
            line: { color: "#9aa3b2", width: 1.3 }, marker: { color: "#1b2130", size: g.pointSize * 0.8 }, hovertemplate: "%{y}<extra></extra>" });
        });
        return;
      }
      const xs = vals.map((_, k) => i + ((k * 0.618) % 1 - 0.5) * 0.3);
      if (g.style === "violin") {
        traces.push({ type: "violin", x: vals.map(() => i), y: vals, width: 0.75, points: g.showPoints ? "all" : false, jitter: 0.35, pointpos: 0,
          spanmode: "hard", meanline: { visible: true, color: c, width: 1.5 }, box: { visible: true, width: 0.12, fillcolor: "#ffffff", line: { color: c, width: 1.2 } },
          marker: { color: c, size: g.pointSize * 0.7, opacity: 0.85 }, line: { color: c, width: 1.6 }, fillcolor: c + "26", hoverinfo: "y", name: esc(stt.name) });
        return;
      }
      if (g.style === "box") {
        traces.push({ type: "box", x: vals.map(() => i), y: vals, width: 0.5, boxpoints: g.showPoints ? "all" : false, jitter: 0.45, pointpos: 0,
          marker: { color: c, size: g.pointSize * 0.8, opacity: 0.85 }, line: { color: c, width: 1.6 }, fillcolor: c + "22", hoverinfo: "y", name: esc(stt.name) });
        return;
      }
      if (g.style === "bars") traces.push({ type: "bar", x: [i], y: [stt.mean], width: 0.58, marker: { color: c + "30", line: { color: c, width: 1.6 } },
        error_y: { type: "data", array: [err || 0], visible: g.err !== "none", color: "#1b2130", thickness: 1.5, width: 9 }, hoverinfo: "skip" });
      const outl = ((r.outliers || [])[i] || { outliers: [] }).outliers.map(o => o.value);
      if (outl.length) {
        const ox = [], oy = [];
        vals.forEach((v, k) => { if (outl.includes(v)) { ox.push(xs[k]); oy.push(v); } });
        traces.push({ type: "scatter", mode: "markers", x: ox, y: oy, hovertemplate: "Possible outlier: %{y}<extra></extra>",
          marker: { symbol: "circle-open", size: g.pointSize + 9, line: { color: "#d62728", width: 2 } } });
      }
      if (g.showPoints) traces.push({ type: "scatter", mode: "markers", x: xs, y: vals,
        marker: { color: c, size: g.pointSize, opacity: 0.85, line: { color: "#fff", width: 1 } }, hovertemplate: `${esc(stt.name)}: %{y}<extra></extra>` });
      if (g.style === "dots") traces.push({ type: "scatter", mode: "markers", x: [i], y: [stt.mean],
        marker: { symbol: "line-ew", size: 40, line: { width: 3, color: "#1b2130" } },
        error_y: { type: "data", array: [err || 0], visible: g.err !== "none", color: "#1b2130", thickness: 1.5, width: 11 },
        hovertemplate: `Mean ${fmt(stt.mean)}<extra></extra>` });
    });
    const span = (ymax - Math.min(0, ymin)) || 1;
    let topExtra = span * 0.06;
    if (g.brackets !== "none" && r.kind !== "describe") {
      const pairs = r.n_groups === 2 ? [{ i: 0, j: 1, stars: r.stars, significant: r.significant }]
        : r.comparisons.map(c => ({ i: c.i, j: c.j, stars: c.stars, significant: c.significant }));
      const show = pairs.filter(p => g.brackets === "all" || p.significant);
      const { items, height } = bracketLayout(show, ymax, span);
      const tick = span * 0.025;
      items.forEach(p => {
        shapes.push({ type: "path", path: `M ${p.i + 0.04} ${p.y - tick} L ${p.i + 0.04} ${p.y} L ${p.j - 0.04} ${p.y} L ${p.j - 0.04} ${p.y - tick}`, line: { color: "#1b2130", width: 1.3 } });
        annotations.push({ x: (p.i + p.j) / 2, y: p.y, text: p.stars, showarrow: false, yanchor: "bottom", font: { size: p.stars === "ns" ? 11 : 16 } });
      });
      topExtra = Math.max(topExtra, height + span * 0.04);
    }
    const lo = g.style === "bars" ? Math.min(0, ymin) : ymin - span * 0.08;
    styledReact(el, traces, { ...baseLayout(g), shapes, annotations, meta: "flippable",
      xaxis: axis(g, { tickvals: groups.map((_, i) => i), ticktext: r.groups.map(x => esc(x.name)), range: [-0.6, groups.length - 0.4] }),
      yaxis: yAxis(g, g.ylabel, { range: [lo, ymax + topExtra] }) }, PLOT_CONFIG);
  }

  function drawXY(el, r, s) {
    const g = s.graph, c0 = color(g, 0, "Curve"), traces = [];
    const logFit = r.model !== "linear" && r.x_is_log && !s.options.xIsLog;
    const tx = x => (logFit ? Math.pow(10, x) : x);
    // data points (raw sheet values so the axis shows real concentrations)
    const rows = s.data.map(row => ({ x: num(row[0]), ys: s.cols.slice(1).map((_, j) => num(row[j + 1])).filter(v => v !== null) }))
      .filter(p => p.x !== null && p.ys.length && (!logFit || p.x > 0));
    const reps = s.cols.length > 2 && g.repMode !== "all";
    if (g.band && r.line) {
      traces.push({ x: r.line.x, y: r.line.low, mode: "lines", line: { width: 0 }, hoverinfo: "skip" });
      traces.push({ x: r.line.x, y: r.line.high, mode: "lines", line: { width: 0 }, fill: "tonexty", fillcolor: c0 + "22", hoverinfo: "skip" });
    }
    const curve = r.model === "linear" ? r.line : r.curve;
    traces.push({ x: curve.x.map(tx), y: curve.y, mode: "lines", line: { color: c0, width: 2.4 }, hovertemplate: "Fit: %{y:.4g}<extra></extra>" });
    const cmpFit = r.comparison && r.comparison.fit_b;
    if (cmpFit) traces.push({ x: cmpFit.curve.x.map(tx), y: cmpFit.curve.y, mode: "lines", line: { color: color(g, 1, "Comparison curve"), width: 2, dash: "dash" },
      hovertemplate: `${esc(cmpFit.model_name)}: %{y:.4g}<extra></extra>` });
    if (reps) {
      // ROUT outliers are left out of the plotted mean ± SD too (they're shown separately as red crosses)
      const left = {}; (r.outliers || []).forEach(o => { const k = `${o.x}|${o.y}`; left[k] = (left[k] || 0) + 1; });
      const keep = (x, y) => { const k = `${x}|${y}`; if (left[k]) { left[k]--; return false; } return true; };
      const stats = rows.map(p => ({ ...p, ys: p.ys.filter(y => keep(p.x, y)) })).filter(p => p.ys.length).map(p => {
        const n = p.ys.length, m = p.ys.reduce((a, b) => a + b, 0) / n;
        const sd = n > 1 ? Math.sqrt(p.ys.reduce((a, b) => a + (b - m) ** 2, 0) / (n - 1)) : 0;
        return { x: p.x, m, e: g.repMode === "sem" ? sd / Math.sqrt(n) : sd };
      });
      traces.push({ x: stats.map(p => p.x), y: stats.map(p => p.m), mode: "markers",
        marker: { color: "#1b2130", size: g.pointSize, line: { color: "#fff", width: 1 } },
        error_y: { type: "data", array: stats.map(p => p.e), color: "#1b2130", thickness: 1.4, width: 5 }, hovertemplate: "(%{x}, %{y:.4g})<extra></extra>" });
    } else {
      const pts = rows.flatMap(p => p.ys.map(y => [p.x, y]));
      traces.push({ x: pts.map(p => p[0]), y: pts.map(p => p[1]), mode: "markers",
        marker: { color: "#1b2130", size: g.pointSize, line: { color: "#fff", width: 1 } }, hovertemplate: "(%{x}, %{y})<extra></extra>" });
    }
    if ((r.outliers || []).length) traces.push({ x: r.outliers.map(p => p.x), y: r.outliers.map(p => p.y), mode: "markers", name: "Outliers",
      marker: { symbol: "x-thin-open", color: "#d62728", size: g.pointSize + 8, line: { color: "#d62728", width: 2.2 } }, hovertemplate: "Outlier (not fitted): (%{x}, %{y})<extra></extra>" });
    const unk = (r.unknowns || []).filter(u => u.x != null);
    if (unk.length) traces.push({ x: unk.map(u => u.x), y: unk.map(u => u.y), mode: "markers", name: "Unknowns",
      marker: { symbol: "diamond", color: color(g, 1, "Unknowns"), size: g.pointSize + 3, line: { color: "#fff", width: 1 } },
      hovertemplate: "Unknown: X = %{x:.4g}, Y = %{y:.4g}<extra></extra>" });
    const annotations = [];
    if (g.showEq) {
      let text = r.model === "linear" ? `${r.equation}<br>R² = ${fmt(r.r_squared, 4)}` : `${r.derived[0] ? `${r.derived[0].name} = ${fmt(r.derived[0].value)}<br>` : ""}R² = ${fmt(r.r_squared, 4)}`;
      // put the label in the empty corner: top-left for rising curves, top-right for falling ones
      const falling = curve.y[curve.y.length - 1] < curve.y[0];
      annotations.push({ xref: "paper", yref: "paper", x: falling ? 0.98 : 0.02, y: 0.98, xanchor: falling ? "right" : "left", yanchor: "top",
        showarrow: false, align: falling ? "right" : "left", text, bgcolor: "rgba(255,255,255,0.85)", font: { size: (g.fontSize || 13) - 1, color: "#6b7385" } });
    }
    const xa = axis(g, { title: { text: esc(g.xlabel || s.cols[0] || "X") } });
    if (g.logX) xa.type = "log";
    else if (num(g.xtick) > 0) { xa.dtick = num(g.xtick); xa.tick0 = 0; }
    const xlo = num(g.xmin), xhi = num(g.xmax);
    if (xlo !== null && xhi !== null) xa.range = g.logX ? [Math.log10(Math.max(xlo, 1e-12)), Math.log10(Math.max(xhi, 1e-12))] : [xlo, xhi];
    styledReact(el, traces, { ...baseLayout(g), annotations, xaxis: xa, yaxis: yAxis(g, g.ylabel || s.cols[1] || "Y") }, PLOT_CONFIG);
  }

  function drawSurvival(el, r, s) {
    const g = s.graph, traces = [];
    const tmax = Math.max(...s.data.map(row => num(row[0]) ?? 0));
    r.curves.forEach((c, i) => {
      const col = color(g, i, c.name);
      const xs = [...c.steps.map(p => p.t), tmax], ys = [...c.steps.map(p => p.s * 100), c.steps[c.steps.length - 1].s * 100];
      if (g.showCI) {
        traces.push({ x: xs, y: [...c.steps.map(p => p.lo * 100), c.steps[c.steps.length - 1].lo * 100], mode: "lines", line: { width: 0, shape: "hv" }, hoverinfo: "skip" });
        traces.push({ x: xs, y: [...c.steps.map(p => p.hi * 100), c.steps[c.steps.length - 1].hi * 100], mode: "lines", line: { width: 0, shape: "hv" }, fill: "tonexty", fillcolor: col + "20", hoverinfo: "skip" });
      }
      traces.push({ x: xs, y: ys, mode: "lines", line: { color: col, width: 2.4, shape: "hv" }, name: esc(c.name), showlegend: true,
        hovertemplate: `${esc(c.name)}: %{y:.1f}% at %{x}<extra></extra>` });
      if (g.showCensor && c.censored.t.length) traces.push({ x: c.censored.t, y: c.censored.s.map(v => v * 100), mode: "markers", showlegend: false,
        marker: { symbol: "line-ns", size: g.pointSize + 4, line: { color: col, width: 2 } }, hovertemplate: "Censored at %{x}<extra></extra>" });
    });
    styledReact(el, traces, { ...baseLayout(g), showlegend: true, legend: { x: 1, xanchor: "right", y: 1, bgcolor: "rgba(255,255,255,0.7)" },
      xaxis: axis(g, { title: { text: esc(g.xlabel || s.cols[0] || "Time") }, rangemode: "tozero" }),
      yaxis: yAxis(g, g.ylabel, { range: [0, 105] }) }, PLOT_CONFIG);
  }

  function drawContingency(el, r, s) {
    const g = s.graph;
    const traces = r.cols.map((c, j) => ({ type: "bar", name: esc(c), x: r.rows.map(esc), showlegend: true,
      y: r.table.map((row, i) => g.mode === "count" ? row[j] : r.row_pct[i][j]),
      marker: { color: color(g, j, c), line: { color: "#1b2130", width: 0.8 } },
      hovertemplate: `${esc(c)}: %{y:.3g}${g.mode === "count" ? "" : "%"}<extra></extra>` }));
    styledReact(el, traces, { ...baseLayout(g), barmode: g.stack ? "stack" : "group", bargap: 0.3, showlegend: true, meta: "flippable",
      legend: { orientation: "h", y: 1.08, x: 0 },
      xaxis: axis(g), yaxis: yAxis(g, g.ylabel || (g.mode === "count" ? "Count" : "Percent of row")) }, PLOT_CONFIG);
  }

  async function exportPlot(format, convert) {
    if (!lastResult) { toast("Add some data first, then export the graph."); return; }
    if (active().type === "layout") return exportLayout(format === "png" ? (convert || "png") : null);
    try {
      const g = active().graph, [wIn, hIn] = EXPORT_SIZES[g.exportSize] || EXPORT_SIZES["15"];
      // 96 CSS pixels per inch; PNG resolution comes from the scale factor
      const url = await Plotly.toImage($("plot"), { format, width: Math.round(wIn * 96), height: Math.round(hIn * 96),
        scale: format === "png" ? Number(g.exportDpi || 300) / 96 : 1 });
      const res = await api("/api/exports", { method: "POST", body: JSON.stringify({ filename: `${projectName} - ${active().title}`, data_url: url,
        fmt: convert || null, dpi: format === "png" ? Number(g.exportDpi || 300) : null }) });
      toast(`Saved <b>${esc(res.file)}</b> to the exports folder`, "exports");
    } catch (e) { toast(esc(e.message || "Export failed.")); }
  }

  // ======================================================================
  // copy results (tab-separated, pastes cleanly into Excel / Word)
  // ======================================================================
  function resultsRows() {
    const rows = [];
    $("results").querySelectorAll(".summary, .opt-label, table.res tr, .note").forEach(el => {
      if (el.tagName === "TR") {
        const cells = [...el.children].map(td => td.textContent.trim());
        if (el.classList.contains("sec")) rows.push([], [cells[0].toUpperCase()]);
        else rows.push(cells);
      } else rows.push([], [el.textContent.trim()]);
    });
    while (rows.length && !rows[0].length) rows.shift();
    return rows;
  }
  async function copyResults() {
    if (!$("results").textContent.trim()) return;
    const text = [active().title, "", ...resultsRows().map(r => r.join("\t"))].join("\n");
    try { await navigator.clipboard.writeText(text); }
    catch {
      const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select();
      document.execCommand("copy"); ta.remove();
    }
    toast("Results copied. Paste into Excel, Word or an email.");
  }
  async function exportXlsx() {
    if (!lastResult) { toast("Add some data first, then export."); return; }
    const s = active();
    try {
      const res = await api("/api/exports/xlsx", { method: "POST", body: JSON.stringify({
        filename: `${projectName} - ${s.title}`, title: s.title, results: resultsRows().map(r => r.map(String)),
        data_cols: s.cols.map(String), data_rows: s.data.map(r => r.map(String)) }) });
      toast(`Saved <b>${esc(res.file)}</b> to the exports folder`, "exports");
    } catch (e) { toast(esc(e.message || "Export failed.")); }
  }

  // ======================================================================
  // toast, projects dialog
  // ======================================================================
  let toastTimer = null;
  function toast(html, folder) {
    const el = $("toast");
    el.innerHTML = `<span>${html}</span>` + (folder ? `<button>Show folder</button>` : "");
    el.hidden = false;
    const b = el.querySelector("button"); if (b) b.onclick = () => reveal(folder);
    clearTimeout(toastTimer); toastTimer = setTimeout(() => { el.hidden = true; }, 5000);
  }
  const reveal = folder => api(`/api/reveal/${folder}`, { method: "POST" }).catch(() => toast("Couldn't open the folder."));

  async function showProjects() {
    $("dialog-backdrop").hidden = false; $("new-project-name").value = "";
    const ul = $("project-list");
    ul.innerHTML = `<li class="emptyli">Loading…</li>`;
    try {
      const { projects } = await api("/api/projects");
      if (!projects.length) { ul.innerHTML = `<li class="emptyli">No projects yet.</li>`; return; }
      ul.innerHTML = projects.map(p => {
        const cur = p.name === projectName, when = new Date(p.modified).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
        return `<li class="${cur ? "current" : ""}"><span class="pn">${esc(p.name)}</span><span class="pd">${when}</span>
          ${cur ? `<span class="pd">open</span>` : `<button class="ghost small" data-open="${esc(p.name)}">Open</button><button class="ghost small danger" data-del="${esc(p.name)}">Delete</button>`}</li>`;
      }).join("");
      ul.querySelectorAll("[data-open]").forEach(b => b.onclick = async () => { try { await openProject(b.dataset.open); hideProjects(); } catch (e) { toast(esc(e.message)); } });
      ul.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
        if (!confirm(`Delete the project "${b.dataset.del}"? Its file will be removed from the projects folder.`)) return;
        await api(`/api/projects/${encodeURIComponent(b.dataset.del)}`, { method: "DELETE" }); showProjects();
      });
    } catch (e) { ul.innerHTML = `<li class="emptyli">${esc(e.message)}</li>`; }
  }
  const hideProjects = () => { $("dialog-backdrop").hidden = true; };
  async function renameProject(newName) {
    newName = newName.trim();
    if (!newName || newName === projectName) { $("project-name").value = projectName; return; }
    try {
      await saveNow();
      const r = await api(`/api/projects/${encodeURIComponent(projectName)}/rename`, { method: "POST", body: JSON.stringify({ new_name: newName }) });
      projectName = r.name; $("project-name").value = projectName; toast(`Project renamed to <b>${esc(projectName)}</b>`);
    } catch (e) { $("project-name").value = projectName; toast(esc(e.message)); }
  }
  async function importPzfxProject(file) {
    try {
      const { sheets, notes } = await pzfxSheets(file);
      const n = await uniqueName(file.name.replace(/\.pzfx$/i, ""));
      await saveNow();
      project = { sheets, activeId: sheets[0].id };
      const saved = await api(`/api/projects/${encodeURIComponent(n)}`, { method: "PUT", body: JSON.stringify({ data: project }) });
      projectName = saved.name; $("project-name").value = projectName; setStatus("✓ Saved");
      hideProjects(); renderAll();
      toast(`Opened the Prism file as a new project with ${sheets.length} analyses.${notes.length ? " " + notes.map(esc).join(" ") : ""}`);
    } catch (e) { toast(esc(e.message || "Import failed.")); }
  }
  function importFile(file) {
    if (/\.pzfx$/i.test(file.name)) { importPzfxProject(file); return; }
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const p = JSON.parse(reader.result);
        if (!Array.isArray(p.sheets) || !p.sheets.length) throw new Error();
        const n = await uniqueName(file.name.replace(/\.(ehp|json)$/i, ""));
        const saved = await api(`/api/projects/${encodeURIComponent(n)}`, { method: "PUT", body: JSON.stringify({ data: { sheets: p.sheets, activeId: p.activeId } }) });
        await openProject(saved.name); hideProjects(); toast(`Imported <b>${esc(saved.name)}</b>`);
      } catch { toast("That file couldn't be imported. Is it an Erwin's Hypothesis project (.ehp)?"); }
    };
    reader.readAsText(file);
  }

  // ======================================================================
  // wiring
  // ======================================================================
  function renderAll() {
    const s = active();
    project.activeId = s.id;
    $("sheet-title").value = s.title;
    $("sheet-kind").textContent = TYPES[s.type].label;
    $("sheet-badge").className = `badge t-${s.type}`; $("sheet-badge").textContent = badgeText(s.type);
    lastResult = null; lastError = null; selA = selB = null;
    renderSidebar(); renderGrid(); renderOptions(); renderFormat(); renderResults(); drawPlot(); updateUndoButtons();
    run();
  }

  const grid = $("grid");
  grid.addEventListener("input", onGridInput);
  grid.addEventListener("paste", onGridPaste);
  grid.addEventListener("keydown", onGridKey);
  grid.addEventListener("click", onGridClick);
  grid.addEventListener("mousedown", onGridMouseDown);
  grid.addEventListener("mouseover", onGridMouseOver);
  grid.addEventListener("contextmenu", onGridContext);

  $("sheet-title").addEventListener("input", e => { active().title = e.target.value; save(); renderSidebar(); });
  $("btn-new").onclick = e => { e.stopPropagation(); $("new-menu").hidden = !$("new-menu").hidden; };
  document.addEventListener("click", () => { $("new-menu").hidden = true; });
  $("new-menu").querySelectorAll("button").forEach(b => b.onclick = () => {
    const s = newSheet(b.dataset.type);
    project.sheets.push(s); project.activeId = s.id; save(); renderAll(); $("new-menu").hidden = true;
  });
  $("btn-delete").onclick = () => {
    const s = active();
    if (!confirm(`Delete "${s.title}"? This can't be undone.`)) return;
    project.sheets = project.sheets.filter(x => x.id !== s.id);
    if (!project.sheets.length) project.sheets.push(newSheet("ttest"));
    project.activeId = project.sheets[0].id; save(); renderAll();
  };
  $("btn-addcol").onclick = addColumn;
  $("btn-import-data").onclick = () => $("file-data").click();
  $("btn-transform").onclick = showTransform;
  $("btn-guide").onclick = showGuide;
  $("guide-close").onclick = () => { $("guide-backdrop").hidden = true; };
  $("guide-backdrop").onclick = e => { if (e.target.id === "guide-backdrop") $("guide-backdrop").hidden = true; };
  $("tf-close").onclick = () => { $("transform-backdrop").hidden = true; };
  $("transform-backdrop").onclick = e => { if (e.target.id === "transform-backdrop") $("transform-backdrop").hidden = true; };
  $("tf-apply").onclick = applyTransform;
  $("file-data").onchange = e => { if (e.target.files[0]) importData(e.target.files[0]); e.target.value = ""; };
  $("btn-example").onclick = () => { recordUndo(true); applyExample(active()); save(); renderGrid(); renderOptions(); renderFormat(); scheduleRun(); };
  $("btn-clear").onclick = () => {
    const s = active();
    recordUndo(true);
    s.data = blankRows(TYPES[s.type].minRows, s.cols.length); s.excluded = []; save(); renderGrid(); scheduleRun();
    toast("Data cleared. Press Ctrl+Z to undo.");
  };
  $("btn-dup").onclick = () => {
    const s = active(), copy = JSON.parse(JSON.stringify(s));
    copy.id = uid(); copy.title = `${s.title} (copy)`;
    project.sheets.splice(project.sheets.findIndex(x => x.id === s.id) + 1, 0, copy);
    project.activeId = copy.id; save(); renderAll();
    toast(`Duplicated as <b>${esc(copy.title)}</b>`);
  };
  function applyTheme(t) {
    document.documentElement.dataset.theme = t === "dark" ? "dark" : "light";
    $("btn-theme").textContent = t === "dark" ? "☀" : "☾";
  }
  $("btn-theme").onclick = () => {
    const t = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(t);
    api("/api/prefs", { method: "PUT", body: JSON.stringify({ theme: t }) }).catch(() => {});
  };
  api("/api/prefs").then(p => applyTheme(p.theme)).catch(() => {});
  $("btn-undo").onclick = () => undoRedo("undo");
  $("btn-redo").onclick = () => undoRedo("redo");
  $("btn-format").onclick = () => {
    const f = $("graph-format"); f.hidden = !f.hidden;
    $("btn-format").classList.toggle("on", !f.hidden); $("btn-format").setAttribute("aria-expanded", String(!f.hidden));
  };
  $("btn-png").onclick = () => exportPlot("png");
  $("btn-svg").onclick = () => exportPlot("svg");
  $("btn-tiff").onclick = () => exportPlot("png", "tiff");
  $("btn-copy").onclick = copyResults;
  $("btn-xlsx").onclick = exportXlsx;
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") { hideProjects(); $("transform-backdrop").hidden = true; $("guide-backdrop").hidden = true; }
    const mod = e.ctrlKey || e.metaKey;
    if (!mod) return;
    const inGridOrBody = e.target === document.body || e.target.closest("#grid");
    if (!inGridOrBody) return;
    if (e.key.toLowerCase() === "z" && !e.shiftKey) { e.preventDefault(); undoRedo("undo"); }
    else if (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey)) { e.preventDefault(); undoRedo("redo"); }
  });

  $("btn-projects").onclick = showProjects;
  $("dlg-close").onclick = hideProjects;
  $("dialog-backdrop").onclick = e => { if (e.target.id === "dialog-backdrop") hideProjects(); };
  const doCreate = async () => {
    try { await createProject($("new-project-name").value.trim() || "Untitled project", false); hideProjects(); } catch (e) { toast(esc(e.message)); }
  };
  $("btn-new-project").onclick = doCreate;
  $("new-project-name").onkeydown = e => { if (e.key === "Enter") doCreate(); };
  $("btn-show-projects").onclick = () => reveal("projects");
  $("btn-examples").onclick = async () => {
    try { await createProject("Examples", true); hideProjects(); toast("Created a project with an example of every analysis."); } catch (e) { toast(esc(e.message)); }
  };
  $("btn-import").onclick = () => $("file-import").click();
  $("file-import").onchange = e => { if (e.target.files[0]) importFile(e.target.files[0]); e.target.value = ""; };
  $("project-name").addEventListener("change", e => renameProject(e.target.value));
  $("project-name").addEventListener("keydown", e => { if (e.key === "Enter") e.target.blur(); });
  window.addEventListener("beforeunload", () => { if (saveTimer) saveNow(); });

  // start: reopen the last project, or create one full of examples
  (async () => {
    api("/api/models").then(r => { if (r.models) MODELS = r.models; }).catch(() => {});
    try {
      const { projects, last } = await api("/api/projects");
      const pick = last || (projects[0] && projects[0].name);
      if (pick) await openProject(pick);
      else await createProject("My first project", true);
    } catch {
      examplesProject(); projectName = "Untitled"; $("project-name").value = projectName;
      setStatus("Can't reach the app's engine", true); renderAll();
    }
  })();
})();
