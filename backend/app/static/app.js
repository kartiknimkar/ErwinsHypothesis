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
  const COMMON_GRAPH = { title: "", palette: "vivid", pointSize: 8, fontSize: 13, ymin: "", ymax: "", logY: false };

  function axis(g, extra = {}) {
    return { showline: true, linewidth: 1.5, linecolor: "#1b2130", ticks: "outside", tickwidth: 1.5, ticklen: 5,
      showgrid: false, zeroline: false, automargin: true, ...extra };
  }
  function yAxis(g, titleText, extra = {}) {
    const a = axis(g, { title: { text: esc(titleText || "") }, ...extra });
    const cur = extra.range || [null, null];
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
    modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d", "toggleSpikelines"] };

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
    "3i": [["ordinary", "One-way ANOVA + Tukey", "Compares all means; Tukey's test for every pair."],
      ["welch", "Welch's ANOVA + Games-Howell", "When the groups' spreads differ."],
      ["kruskal", "Kruskal-Wallis + Dunn's", "Nonparametric: compares ranks, no normality needed."]],
    "3r": [["rm", "Repeated-measures ANOVA + Tukey", "Each row is one subject measured in every column. Geisser-Greenhouse corrected."],
      ["friedman", "Friedman test + Dunn's", "Nonparametric repeated measures."]],
  };
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
      examples: s => s.cols.length >= 3 ? {
        cols: ["Vehicle", "Drug 10 µM", "Drug 50 µM"],
        rows: [[10.2, 13.4, 18.2], [11.5, 14.8, 17.1], [9.8, 12.9, 19.5], [12.1, 15.2, 16.8], [10.9, 14.1, 18.9], [11.3, 13.7, 17.6]],
      } : {
        cols: ["Control", "Treated"],
        rows: [[4.2, 6.1], [5.1, 7.3], [3.8, 6.8], [4.9, 5.9], [5.5, 7.9], [4.4, 6.5], [4.0, 7.0], [5.2, 6.2]],
      },
      request(s) {
        return ["/api/compare", { groups: s.cols.map((_, j) => s.data.map(r => num(r[j]))), names: s.cols.map((c, j) => c || `Group ${letter(j)}`),
          kind: kindFor(s, filledCols(s).length), alpha: s.options.alpha, outliers: !!s.options.outliers }];
      },
      renderOptions(s) {
        const n = filledCols(s).length, key = choiceKey(s, n), cur = kindFor(s, n);
        const rep = s.options.design === "repeated";
        return `<div class="seg"><button data-design="independent" class="${rep ? "" : "on"}">Different subjects in each group</button><button data-design="repeated" class="${rep ? "on" : ""}">Same subjects (each row = one subject)</button></div>
          <div class="opt-label">${n >= 3 ? `${n} groups: compare all` : "2 groups"}</div>` +
          CHOICES[key].map(([k, name, d]) => `<label class="choice ${cur === k ? "on" : ""}"><input type="radio" name="kind${key}" value="${k}" ${cur === k ? "checked" : ""}><span><b>${name}</b><small>${d}</small></span></label>`).join("") +
          (n >= 3 ? "" : `<p class="hint">Have 3 or more groups? Click <b>+ Group</b> to add a column.</p>`) +
          `<label class="check"><input type="checkbox" data-opt="outliers" ${s.options.outliers ? "checked" : ""}> Identify outliers (Grubbs' test, α = 0.05)</label>` + alphaSelect(s);
      },
      graphControls: s => [
        sel("style", "Style", [["dots", "Dots + mean"], ["bars", "Bars + dots"], ["box", "Box plot"],
          ...(s.options.design === "repeated" ? [["lines", "Before-after (connect subjects)"]] : [])]),
        sel("err", "Error bars", [["sd", "Mean ± SD"], ["sem", "Mean ± SEM"], ["ci95", "Mean ± 95% CI"], ["none", "None"]]),
        sel("brackets", "Significance", [["sig", "Significant pairs"], ["all", "All pairs"], ["none", "Hide"]]),
        txt("ylabel", "Y axis label"), chk("showPoints", "Show points"),
      ],
      renderResults: renderGroupResults,
      draw: drawGroups,
    },
    // ---------------------------------------------------------------- two-way
    twoway: {
      label: "Grouped: two-way ANOVA", newTitle: "Two-way ANOVA",
      minCols: 3, maxCols: 12, fixedCols: 1, textCol: 0, addLabel: "+ Group", minRows: 15,
      colKind: j => j === 0 ? "Row factor" : `Group ${letter(j - 1)}`, newColName: j => `Group ${letter(j - 1)}`,
      hint: "Two factors, e.g. treatment (columns) × sex or time (rows). Type the row name in the first column. For replicates, add more rows with the same name.",
      cols: ["Sex", "Vehicle", "Drug"],
      options: { alpha: 0.05 },
      graph: { ylabel: "Response", style: "bars", err: "sd", brackets: "sig", showPoints: true },
      examples: () => ({
        cols: ["Sex", "Vehicle", "Low dose", "High dose"],
        rows: [["Male", 5.1, 6.9, 8.2], ["Male", 4.8, 7.4, 8.8], ["Male", 5.5, 7.1, 8.5], ["Male", 5.0, 6.6, 8.9],
          ["Female", 6.0, 7.0, 7.1], ["Female", 6.3, 7.7, 7.6], ["Female", 5.8, 7.2, 7.9], ["Female", 6.1, 7.5, 7.4]],
      }),
      request(s) {
        return ["/api/twoway", { rows: s.data.map(r => String(r[0] || "").trim()), columns: s.cols.slice(1).map((_, j) => s.data.map(r => num(r[j + 1]))),
          names: s.cols.slice(1).map((c, j) => c || `Group ${letter(j)}`), alpha: s.options.alpha }];
      },
      renderOptions: s => `<p class="hint">Tests whether the <b>column factor</b> (${esc(s.cols.slice(1).join(", "))}) matters, whether the <b>row factor</b> (${esc(s.cols[0])}) matters, and whether they <b>interact</b> (the treatment effect differs between rows). Then compares the columns within each row.</p>${alphaSelect(s)}`,
      graphControls: () => [
        sel("style", "Style", [["bars", "Bars + dots"], ["dots", "Dots + mean"], ["lines", "Interaction plot (means)"]]),
        sel("err", "Error bars", [["sd", "Mean ± SD"], ["sem", "Mean ± SEM"], ["ci95", "Mean ± 95% CI"], ["none", "None"]]),
        sel("brackets", "Significance", [["sig", "Significant pairs"], ["all", "All pairs"], ["none", "Hide"]]),
        txt("ylabel", "Y axis label"), chk("showPoints", "Show points"),
      ],
      renderResults: renderTwoWayResults,
      draw: drawTwoWay,
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
      examples: s => (modelInfo(s.options.model)?.log_x) ? {
        cols: ["Concentration (µM)", "Response %", "Rep 2", "Rep 3"],
        rows: [[0.01, 98.1, 101.2, 97.4], [0.03, 96.0, 99.5, 95.8], [0.1, 92.7, 88.9, 93.4], [0.3, 80.3, 75.6, 77.9],
          [1, 50.1, 55.8, 52.0], [3, 30.2, 26.9, 29.4], [10, 12.8, 15.1, 13.0], [30, 7.5, 9.2, 6.9], [100, 6.4, 4.8, 6.1]],
      } : {
        cols: ["Concentration (µg/mL)", "Absorbance"],
        rows: [[0, 0.02], [5, 0.11], [10, 0.21], [20, 0.39], [40, 0.83], [60, 1.18], [80, 1.62], ["", 0.55], ["", 1.31]],
      },
      request(s) {
        return ["/api/fit", { x: s.data.map(r => num(r[0])), ys: s.cols.slice(1).map((_, j) => s.data.map(r => num(r[j + 1]))),
          model: s.options.model, compare: s.options.model !== "linear" ? (s.options.compare || null) : null,
          fixed: Object.fromEntries(Object.entries((s.options.fixed || {})[s.options.model] || {}).filter(([, v]) => isNum(v)).map(([k, v]) => [k, Number(v)])),
          equation: s.options.model === "custom" ? (s.options.equation || "") : null,
          initial: s.options.model === "custom" ? Object.fromEntries(Object.entries(s.options.initial || {}).filter(([, v]) => isNum(v)).map(([k, v]) => [k, Number(v)])) : null,
          auc: !!s.options.auc, baseline: isNum(s.options.baseline) ? Number(s.options.baseline) : 0,
          x_is_log: !!s.options.xIsLog, alpha: s.options.alpha }];
      },
      renderOptions(s) {
        const custom = s.options.model === "custom";
        const m = custom ? null : modelInfo(s.options.model);
        return `<div class="opt-label">Fit</div>
          <select id="opt-model">${[["linear", "Straight line (linear regression + correlation)"], ...MODELS.map(m => [m.id, m.name]), ["custom", "User-defined equation…"]]
            .map(([v, l]) => `<option value="${v}" ${s.options.model === v ? "selected" : ""}>${l}</option>`).join("")}</select>
          ${custom ? `<textarea id="opt-equation" class="eq-input" rows="2" spellcheck="false" placeholder="Y = A*exp(-K*X) + C">${esc(s.options.equation || "")}</textarea>
            <p class="hint">Use X, any parameter names, + − * / ^ and exp, ln, log10, sqrt, sin, cos, abs. Example: <code>Y = Top/(1+(X/EC50)^Hill)</code></p>
            <div id="custom-params">${customParamsHTML(s)}</div>`
          : `<div class="eqn">${m ? esc(m.equation) : "Y = Slope·X + Intercept"}</div>`}
          ${m ? `<div class="row"><label for="opt-compare">Compare with</label><select id="opt-compare"><option value="">No comparison</option>${MODELS
            .filter(o => o.id !== m.id && o.log_x === m.log_x).map(o => `<option value="${o.id}" ${s.options.compare === o.id ? "selected" : ""}>${esc(o.name)}</option>`).join("")}</select></div>` : ""}
          ${m && m.params ? `<details class="constrain" ${Object.values((s.options.fixed || {})[m.id] || {}).some(isNum) ? "open" : ""}>
            <summary>Constrain parameters <span class="pd">(optional)</span></summary>
            <p class="hint">Leave blank to fit. Type a value to hold it fixed, e.g. Bottom = 0 and Top = 100 for normalized data.</p>
            <div class="cgrid">${m.params.map(pn => `<label>${esc(pn)}<input type="text" data-fix="${esc(pn)}" value="${esc(((s.options.fixed || {})[m.id] || {})[pn] ?? "")}" placeholder="fit" inputmode="decimal"></label>`).join("")}</div>
          </details>` : ""}
          ${m && m.log_x ? `<label class="check"><input type="checkbox" id="opt-xislog" ${s.options.xIsLog ? "checked" : ""}> X values are already log10(concentration)</label>
            <p class="hint">Otherwise X is concentration and the app takes the log for you (X = 0 is left out, as it has no log).</p>` : ""}
          <div class="row"><label class="check"><input type="checkbox" data-opt="auc" ${s.options.auc ? "checked" : ""}> Area under the curve</label>
            ${s.options.auc ? `<label>baseline Y =</label><input type="text" id="opt-baseline" value="${esc(s.options.baseline ?? "0")}" style="width:70px" inputmode="decimal">` : ""}</div>
          ${alphaSelect(s)}`;
      },
      graphControls: s => [
        txt("xlabel", "X axis label", s.cols[0]), txt("ylabel", "Y axis label", s.cols[1]),
        ...(s.cols.length > 2 ? [sel("repMode", "Replicates", [["mean", "Mean ± SD"], ["sem", "Mean ± SEM"], ["all", "All points"]])] : []),
        txt("xmin", "X min", "auto"), txt("xmax", "X max", "auto"),
        chk("logX", "Log X axis"), chk("band", "95% confidence band"), chk("showEq", "Show equation"),
      ],
      renderResults: renderXYResults,
      draw: drawXY,
    },
    // ---------------------------------------------------------------- multiple variables
    multivar: {
      label: "Multiple variables: correlation", newTitle: "Correlation matrix",
      minCols: 2, maxCols: 20, fixedCols: 0, textCol: -1, addLabel: "+ Variable", minRows: 15,
      colKind: j => `Variable ${j + 1}`, newColName: j => `Variable ${j + 1}`,
      hint: "One column per variable (e.g. weight, glucose, insulin), one row per subject. Every pair of variables is correlated, using the rows where both have values.",
      cols: ["Variable 1", "Variable 2", "Variable 3"],
      options: { method: "pearson", alpha: 0.05 },
      graph: { showValues: true },
      examples: () => ({
        cols: ["Age", "BMI", "Glucose", "Insulin", "Activity"],
        rows: [[34, 22.1, 88, 6.2, 9.5], [45, 27.4, 101, 9.8, 6.1], [52, 31.2, 118, 14.3, 3.2], [29, 21.5, 84, 5.1, 10.2],
          [61, 29.8, 112, 12.9, 4.0], [38, 24.6, 93, 7.7, 8.3], [47, 33.1, 126, 16.2, 2.5], [55, 26.0, 99, 8.9, 6.8],
          [41, 23.3, 90, 6.6, 9.1], [66, 30.5, 121, 13.8, 3.6], [33, 25.8, 95, 8.1, 7.4], [58, 28.2, 108, 11.0, 5.0]],
      }),
      request: s => ["/api/multi", { columns: s.cols.map((_, j) => s.data.map(r => num(r[j]))), names: s.cols.map((c, j) => c || `Variable ${j + 1}`),
        analysis: "correlation", method: s.options.method, alpha: s.options.alpha }],
      renderOptions: s => `<div class="seg"><button data-set="method:pearson" class="${s.options.method === "pearson" ? "on" : ""}">Pearson (linear)</button><button data-set="method:spearman" class="${s.options.method === "spearman" ? "on" : ""}">Spearman (ranks, nonparametric)</button></div>${alphaSelect(s)}`,
      graphControls: () => [chk("showValues", "Show r values")],
      renderResults: renderCorrMatrix,
      draw: drawCorrMatrix,
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
      graphControls: () => [sel("mode", "Show", [["pct", "Percent of each row"], ["count", "Counts"]]), txt("ylabel", "Y axis label")],
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
    s.cols = [...ex.cols];
    s.data = ex.rows.map(r => r.map(v => String(v)));
    padRows(s);
  }
  function examplesProject() {
    project = { sheets: [] };
    const add = (type, title, tweak) => { const s = newSheet(type); if (tweak) tweak(s); applyExample(s); s.title = title; project.sheets.push(s); return s; };
    const first = add("ttest", "Example: two groups");
    add("ttest", "Example: three groups (ANOVA)", s => { s.cols = ["A", "B", "C"]; });
    add("twoway", "Example: two-way ANOVA");
    add("regression", "Example: dose-response (IC50)", s => { s.options.model = "dr_inhibit"; s.graph.logX = true; });
    add("regression", "Example: standard curve");
    add("survival", "Example: survival");
    add("contingency", "Example: contingency");
    add("multivar", "Example: correlation matrix");
    add("diagnostic", "Example: ROC curve");
    add("diagnostic", "Example: Bland-Altman", s => { s.options.analysis = "bland_altman"; });
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
  const snap = s => JSON.stringify({ cols: s.cols, data: s.data });
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
    s.cols = st.cols; s.data = st.data;
    groupOpen = false;
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
      `<li data-id="${s.id}" class="${s.id === project.activeId ? "active" : ""}" title="${esc(TYPES[s.type].label)}">
        <span class="badge t-${s.type}">${badgeText(s.type)}</span><span class="t">${esc(s.title)}</span></li>`).join("");
    $("sheet-list").querySelectorAll("li").forEach(li => li.onclick = () => { project.activeId = li.dataset.id; save(); renderAll(); });
  }
  const badgeText = t => ({ ttest: "G", twoway: "2W", regression: "XY", survival: "S", contingency: "#", multivar: "MV", diagnostic: "Dx" }[t]);

  // ======================================================================
  // data grid
  // ======================================================================
  function renderGrid() {
    const s = active(), t = TYPES[s.type];
    padRows(s);
    const canRemove = j => j >= t.fixedCols && s.cols.length > t.minCols;
    let h = "<thead><tr><th class='rownum'></th>";
    s.cols.forEach((c, j) => {
      h += `<th><div class="colkind">${esc(t.colKind(j, s))}${canRemove(j) ? `<button class="rm" data-rm="${j}" title="Remove this column">✕</button>` : ""}</div>
        <div class="colhead"><input data-head="${j}" value="${esc(c)}" spellcheck="false" aria-label="${esc(t.colKind(j, s))} name"></div></th>`;
    });
    h += "</tr></thead><tbody>";
    s.data.forEach((r, i) => {
      h += `<tr><td class="rownum">${i + 1}</td>`;
      r.forEach((v, j) => {
        const text = j === t.textCol;
        const bad = !text && String(v).trim() !== "" && !isNum(v) ? " bad" : "";
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
  function onGridKey(e) {
    const el = e.target;
    if (el.dataset.r === undefined) return;
    const r = +el.dataset.r, c = +el.dataset.c;
    let target = null;
    if (e.key === "Enter" || e.key === "ArrowDown") target = cellAt(r + 1, c);
    else if (e.key === "ArrowUp") target = cellAt(r - 1, c);
    else if (e.key === "ArrowRight" && el.selectionStart === el.value.length) target = cellAt(r, c + 1);
    else if (e.key === "ArrowLeft" && el.selectionStart === 0) target = cellAt(r, c - 1);
    if (target) { e.preventDefault(); target.focus(); target.select(); }
  }
  function onGridClick(e) {
    const b = e.target.closest("[data-rm]");
    if (!b) return;
    const s = active(), j = +b.dataset.rm;
    const hasData = s.data.some(r => String(r[j]).trim() !== "");
    if (hasData && !confirm(`Remove the column "${s.cols[j]}" and its data? (You can undo.)`)) return;
    recordUndo(true);
    s.cols.splice(j, 1); s.data.forEach(r => r.splice(j, 1));
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
  async function importData(file) {
    const s = active(), t = TYPES[s.type];
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
  const yCols = s => s.type === "regression" || s.type === "survival" || s.type === "twoway" || s.type === "contingency"
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
    box.querySelectorAll("[data-opt]").forEach(cb => cb.onchange = () => { s.options[cb.dataset.opt] = cb.checked; save(); renderOptions(); scheduleRun(); });
    const bl = $("opt-baseline");
    if (bl) bl.oninput = () => { s.options.baseline = bl.value.trim(); bl.classList.toggle("bad", bl.value.trim() !== "" && !isNum(bl.value)); save(); scheduleRun(); };
    const eq = $("opt-equation");
    if (eq) {
      let t = null;
      eq.oninput = () => { s.options.equation = eq.value; save(); clearTimeout(t); t = setTimeout(() => { checkEquation(s); scheduleRun(); }, 400); };
      if (!s.options.eqParams) checkEquation(s);
    }
    const cmp = $("opt-compare");
    if (cmp) cmp.onchange = e => { s.options.compare = e.target.value; save(); scheduleRun(); };
    const lg = $("opt-xislog");
    if (lg) lg.onchange = e => { s.options.xIsLog = e.target.checked; s.graph.logX = !e.target.checked; save(); renderFormat(); scheduleRun(); };
  }

  function seriesNames(s) {
    if (s.type === "ttest") return filledCols(s).map(j => s.cols[j] || `Group ${letter(j)}`);
    if (s.type === "regression") return ["Curve", ...(s.options.compare ? ["Comparison curve"] : []), "Unknowns"];
    if (s.type === "multivar") return [];
    if (s.type === "diagnostic") return s.options.analysis === "roc" ? ["Curve", "Best cutoff"] : ["Points"];
    return s.cols.slice(1).map((c, j) => c || (s.type === "contingency" ? `Outcome ${j + 1}` : `Group ${letter(j)}`));
  }
  const toHex = c => /^#[0-9a-f]{6}$/i.test(c) ? c : "#000000";

  function renderFormat() {
    const s = active(), g = s.graph;
    const ctrls = [txt("title", "Graph title"), ...TYPES[s.type].graphControls(s),
      txt("ymin", "Y min", "auto"), txt("ymax", "Y max", "auto"), chk("logY", "Log Y axis"),
      sel("palette", "Colors", [["vivid", "Vivid"], ["colorblind", "Colorblind-safe"], ["classic", "Classic"], ["pastel", "Pastel"], ["grayscale", "Grayscale"]]),
      { k: "pointSize", label: "Point size", kind: "range", min: 3, max: 16 },
      { k: "fontSize", label: "Font size", kind: "range", min: 9, max: 22 }];
    $("graph-format").innerHTML = ctrls.map(c => {
      const v = g[c.k];
      if (c.kind === "select") return `<label>${c.label}<select data-g="${c.k}">${c.opts.map(([o, l]) => `<option value="${o}" ${v === o ? "selected" : ""}>${l}</option>`).join("")}</select></label>`;
      if (c.kind === "check") return `<label class="check"><input type="checkbox" data-g="${c.k}" ${v ? "checked" : ""}> ${c.label}</label>`;
      if (c.kind === "range") return `<label>${c.label} <input type="range" data-g="${c.k}" min="${c.min}" max="${c.max}" value="${v}"></label>`;
      return `<label>${c.label}<input type="text" data-g="${c.k}" value="${esc(v ?? "")}" placeholder="${esc(c.ph || "")}"></label>`;
    }).join("") + (!seriesNames(s).length ? "" : `<div class="wide colors"><span>Series colors</span>${seriesNames(s).map((n, i) =>
      `<label class="swatch" title="${esc(n)}"><input type="color" data-color="${esc(n)}" value="${toHex(color(g, i, n))}"><span>${esc(n)}</span></label>`).join("")}
      ${g.colors && Object.keys(g.colors).length ? `<button class="ghost small" id="btn-reset-colors">Reset</button>` : ""}</div>`);
    $("graph-format").querySelectorAll("[data-color]").forEach(el => {
      el.oninput = () => { g.colors = { ...(g.colors || {}), [el.dataset.color]: el.value }; save(); drawPlot(); };
      el.onchange = () => renderFormat();
    });
    const rc = $("btn-reset-colors");
    if (rc) rc.onclick = () => { g.colors = {}; save(); renderFormat(); drawPlot(); };
    $("graph-format").querySelectorAll("[data-g]").forEach(el => {
      el.oninput = el.onchange = () => {
        g[el.dataset.g] = el.type === "checkbox" ? el.checked : el.type === "range" ? Number(el.value) : el.value;
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
    const [url, body] = TYPES[s.type].request(s);
    try {
      const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const json = await res.json();
      if (seq !== runSeq) return;
      if (!res.ok) { lastResult = null; lastError = json.detail || "Something went wrong."; }
      else { lastResult = json; lastError = null; }
    } catch { if (seq !== runSeq) return; lastResult = null; lastError = "Can't reach the analysis engine. Is the app still running?"; }
    if (s.type === "ttest") renderOptions(); // options depend on number of filled groups
    renderResults(); drawPlot();
  }

  function renderResults() {
    const s = active(), box = $("results");
    if (lastError) { box.innerHTML = T.summary("err", `<b>Not enough to analyze yet.</b> ${esc(lastError)}`); return; }
    if (!lastResult) { box.innerHTML = ""; return; }
    box.innerHTML = TYPES[s.type].renderResults(lastResult, s);
  }

  // ---------------------------------------------------------------- groups
  function normalityRows(r) {
    if (!r.normality) return [];
    const names = r.normality_of === "differences" ? ["Differences"] : r.groups.map(g => g.name);
    return [T.sec("Normality (Shapiro-Wilk)"), ...r.normality.map((n, i) => T.row(esc(names[i]),
      n ? `W = ${fmt(n.W, 3)}, P = ${fmt(n.p, 3)} · ${n.normal ? "passed" : "<b>not normal</b>"}` : "needs 3+ values"))];
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
        r.comparisons.map(c => ({ cls: c.significant ? "hl" : "", cells: [`${esc(c.a)} vs ${esc(c.b)}`, fmt(c.diff), rankBased ? "" : ci(c.ci_low, c.ci_high), pOnly(c.p), st(c.stars)] })));
      if (r.normality) h += T.table(normalityRows(r));
      if (r.kind === "rm" || r.kind === "friedman") h += `<p class="note">Only rows with a value in every column are used (${r.n_subjects} subjects).</p>`;
      if (r.variance_check && r.variance_check.p < 0.05) h += `<p class="note warn">⚠︎ The groups' spreads differ (Brown-Forsythe ${fmtP(r.variance_check.p)}). Welch's ANOVA is safer.</p>`;
    }
    if (r.outliers) {
      const found = r.outliers.filter(o => o.outliers.length);
      h += `<div class="opt-label" style="margin-top:10px">Outliers (Grubbs' test, α = 0.05)</div>` + (found.length
        ? T.multi(["Group", "Suspected outliers", ""], r.outliers.map(o => [esc(o.name), o.outliers.length ? o.outliers.map(x => `<b>${fmt(x.value)}</b>`).join(", ") : "none", o.n < 3 ? `<span class="pd">needs 3+ values</span>` : ""]))
          + `<p class="note warn">Outliers are circled in red on the graph. The analysis above still includes them: only remove a value if you have a reason beyond the statistics (e.g. a known technical error).</p>`
        : `<p class="note">No outliers found in any group.</p>`);
    }
    h += `<div class="opt-label" style="margin-top:10px">Descriptive statistics</div>` + descTable(r.groups);
    return h;
  }

  // ---------------------------------------------------------------- two-way
  function renderTwoWayResults(r, s) {
    const pct = Math.round((1 - r.alpha) * 100);
    const t = Object.fromEntries(r.table.map(x => [x.source, x]));
    const rowF = esc(s.cols[0] || "Row factor");
    const sigTerm = (x, label) => x.p < r.alpha ? `<b>${label}</b> matters (${fmtP(x.p)}, ${x.stars})` : `${label} doesn't (${fmtP(x.p)})`;
    let h = T.summary(t.Interaction.p < r.alpha || t["Column factor"].p < r.alpha || t["Row factor"].p < r.alpha ? "sig" : "ns",
      `${sigTerm(t["Column factor"], "Column factor (groups)")}; ${sigTerm(t["Row factor"], rowF)}; ` +
      (t.Interaction.p < r.alpha ? `and they <b>interact</b> (${fmtP(t.Interaction.p)}): the group effect depends on ${rowF}.`
        : `no significant interaction (${fmtP(t.Interaction.p)}).`));
    h += T.multi(["Source of variation", "% of total", "F (DFn, DFd)", "P value", ""],
      r.table.filter(x => x.F !== null).map(x => ({ cls: x.p < r.alpha ? "hl" : "",
        cells: [x.source === "Row factor" ? rowF : x.source === "Column factor" ? "Column factor (groups)" : x.source,
          fmt(x.pct, 3) + "%", `F (${x.df}, ${t.Residual.df}) = ${fmt(x.F)}`, pOnly(x.p), st(x.stars)] })));
    h += T.multi(["ANOVA table", "SS", "DF", "MS"], r.table.map(x => [x.source === "Row factor" ? rowF : x.source, fmt(x.SS), x.df, fmt(x.MS)]));
    h += `<div class="opt-label" style="margin-top:10px">${esc(r.posthoc_name)}</div>`;
    h += T.multi([rowF, "Comparison", "Mean diff.", `${pct}% CI`, "Adj. P", ""], r.comparisons.map(c => ({ cls: c.significant ? "hl" : "",
      cells: [esc(c.row), `${esc(c.a)} vs ${esc(c.b)}`, fmt(c.diff), ci(c.ci_low, c.ci_high), pOnly(c.p), st(c.stars)] })));
    h += `<div class="opt-label" style="margin-top:10px">Cell means</div>`;
    h += T.multi([rowF, ...r.cols.map(esc)], r.rows.map((rw, i) => [esc(rw), ...r.cols.map((_, j) => {
      const c = r.cells.find(x => x.i === i && x.j === j);
      return `${fmt(c.mean)} <span class="pd">± ${fmt(c.sd, 3)} (n=${c.n})</span>`;
    })]));
    h += `<p class="note">Mean ± SD. ${r.balanced ? "" : "Unequal group sizes: Type III sums of squares are used. "}Comparisons use the pooled ANOVA error.</p>`;
    return h;
  }

  function drawTwoWay(el, r, s) {
    const g = s.graph, traces = [], shapes = [], annotations = [];
    const nr = r.rows.length, nc = r.cols.length;
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
    const span = (ymax - Math.min(0, ymin)) || 1;
    let topExtra = span * 0.08;
    if (g.brackets !== "none" && g.style !== "lines") {
      const show = r.comparisons.filter(c => g.brackets === "all" || c.significant).map(c => ({ i: pos(c.i, c.j1), j: pos(c.i, c.j2), stars: c.stars }));
      const { items, height } = bracketLayout(show, ymax, span);
      const tick = span * 0.02;
      items.forEach(p => {
        shapes.push({ type: "path", path: `M ${p.i} ${p.y - tick} L ${p.i} ${p.y} L ${p.j} ${p.y} L ${p.j} ${p.y - tick}`, line: { color: "#1b2130", width: 1.2 } });
        annotations.push({ x: (p.i + p.j) / 2, y: p.y, text: p.stars, showarrow: false, yanchor: "bottom", font: { size: p.stars === "ns" ? 10 : 14 } });
      });
      topExtra = Math.max(topExtra, height + span * 0.04);
    }
    const lo = g.style === "bars" ? Math.min(0, ymin) : ymin - span * 0.08;
    Plotly.react(el, traces, { ...baseLayout(g), shapes, annotations, showlegend: true, barmode: "overlay",
      legend: { orientation: "h", y: 1.1, x: 0 },
      xaxis: axis(g, { tickvals: r.rows.map((_, i) => i), ticktext: r.rows.map(esc), range: [-0.6, nr - 0.4], title: { text: esc(s.cols[0] || "") } }),
      yaxis: yAxis(g, g.ylabel, { range: [lo, ymax + topExtra] }) }, PLOT_CONFIG);
  }

  // ---------------------------------------------------------------- XY
  function renderXYResults(r, s) {
    return renderXYCore(r, s) + (r.auc ? renderAUC(r.auc, s) : "") + (r.unknowns ? renderUnknowns(r, s) : "");
  }
  function renderAUC(a, s) {
    if (a.error) return `<p class="note warn">${esc(a.error)}</p>`;
    return T.table([T.sec(`Area under the curve (baseline Y = ${fmt(a.baseline)})`), T.row("Total area", `<b>${fmt(a.total)}</b>`),
      T.row("Area above baseline", fmt(a.positive)), T.row("Area below baseline", fmt(a.negative)),
      T.row(`${esc(s.cols[0] || "X")} range`, `${fmt(a.x_range[0])} to ${fmt(a.x_range[1])}`), T.row("Peak (X, Y)", `${fmt(a.peak_x)}, ${fmt(a.peak_y)}`)]) +
      `<p class="note">Trapezoid rule on the mean Y at each X, using the actual X units.</p>`;
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
    Plotly.react(el, [{ type: "heatmap", z, x: r.names.map((_, j) => j), y: r.names.map((_, i) => i), zmin: -1, zmax: 1,
      colorscale: [[0, "#2166ac"], [0.25, "#92c5de"], [0.5, "#f7f7f7"], [0.75, "#f4a582"], [1, "#b2182b"]],
      colorbar: { title: { text: "r" }, thickness: 12 }, hovertemplate: "r = %{z:.3f}<extra></extra>", xgap: 2, ygap: 2 }],
      { ...baseLayout(g), annotations, margin: { l: 90, r: 20, t: g.title ? 44 : 20, b: 80 },
        xaxis: { tickvals: r.names.map((_, j) => j), ticktext: r.names.map(esc), showgrid: false, zeroline: false },
        yaxis: { tickvals: r.names.map((_, i) => i), ticktext: r.names.map(esc), autorange: "reversed", showgrid: false, zeroline: false, scaleanchor: "x" } },
      PLOT_CONFIG);
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
    Plotly.react(el, [
      { x: [0, 100], y: [0, 100], mode: "lines", line: { color: "#9aa3b2", dash: "dot", width: 1.2 }, hoverinfo: "skip" },
      { x: r.curve.map(p => p.fpr * 100), y: r.curve.map(p => p.tpr * 100), mode: "lines+markers", line: { color: c, width: 2.4, shape: "linear" },
        marker: { size: Math.max(3, g.pointSize - 3), color: c }, customdata: r.curve.map(p => p.cut == null ? "" : fmt(p.cut)),
        hovertemplate: "Cutoff %{customdata}: sensitivity %{y:.1f}%, 100% − specificity %{x:.1f}%<extra></extra>" },
      { x: [100 - r.best.spec], y: [r.best.sens], mode: "markers", marker: { symbol: "star", size: g.pointSize + 8, color: color(g, 1, "Best cutoff") }, hoverinfo: "skip" },
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
    Plotly.react(el, [
      line(0, "dot", "#9aa3b2"), line(r.bias, "solid", "#1b2130"), line(r.loa[0], "dash", "#d62728"), line(r.loa[1], "dash", "#d62728"),
      { x: xs, y: r.points.diff, mode: "markers", marker: { color: c, size: g.pointSize, line: { color: "#fff", width: 1 } }, hovertemplate: "Average %{x:.4g}, difference %{y:.4g}<extra></extra>" },
    ], { ...baseLayout(g), annotations: [["Bias", r.bias], ["+95% LoA", r.loa[1]], ["−95% LoA", r.loa[0]]].map(([t, y]) => ({ x: 1, xref: "paper", xanchor: "right", y, yanchor: "bottom",
        text: `${t} ${fmt(y, 3)}`, showarrow: false, font: { size: (g.fontSize || 13) - 2, color: "#6b7385" } })),
      xaxis: axis(g, { title: { text: `Average of ${esc(r.names[0])} and ${esc(r.names[1])}` } }), yaxis: yAxis(g, `${esc(r.names[1])} − ${esc(r.names[0])}`) }, PLOT_CONFIG);
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
    if (!lastResult) {
      Plotly.purge(el);
      el.innerHTML = `<div class="empty"><div>Your graph appears here once there is enough data.<br>Click <b>Example</b> to see how it works.</div></div>`;
      return;
    }
    if (el.querySelector(".empty")) el.innerHTML = "";
    TYPES[s.type].draw(el, lastResult, s);
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
    const g = s.graph, traces = [], shapes = [], annotations = [];
    const cols = filledCols(s);
    const groups = cols.map(j => s.data.map(row => num(row[j])).filter(v => v !== null));
    let ymax = -Infinity, ymin = Infinity;
    groups.forEach((vals, i) => {
      const stt = r.groups[i] || {}, c = color(g, i, stt.name);
      const err = g.err === "sem" ? stt.sem : g.err === "ci95" ? stt.ci95 : g.err === "sd" ? stt.sd : 0;
      vals.forEach(v => { ymax = Math.max(ymax, v); ymin = Math.min(ymin, v); });
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
    if (g.brackets !== "none") {
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
    Plotly.react(el, traces, { ...baseLayout(g), shapes, annotations,
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
      const stats = rows.map(p => {
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
    const xlo = num(g.xmin), xhi = num(g.xmax);
    if (xlo !== null && xhi !== null) xa.range = g.logX ? [Math.log10(Math.max(xlo, 1e-12)), Math.log10(Math.max(xhi, 1e-12))] : [xlo, xhi];
    Plotly.react(el, traces, { ...baseLayout(g), annotations, xaxis: xa, yaxis: yAxis(g, g.ylabel || s.cols[1] || "Y") }, PLOT_CONFIG);
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
    Plotly.react(el, traces, { ...baseLayout(g), showlegend: true, legend: { x: 1, xanchor: "right", y: 1, bgcolor: "rgba(255,255,255,0.7)" },
      xaxis: axis(g, { title: { text: esc(g.xlabel || s.cols[0] || "Time") }, rangemode: "tozero" }),
      yaxis: yAxis(g, g.ylabel, { range: [0, 105] }) }, PLOT_CONFIG);
  }

  function drawContingency(el, r, s) {
    const g = s.graph;
    const traces = r.cols.map((c, j) => ({ type: "bar", name: esc(c), x: r.rows.map(esc), showlegend: true,
      y: r.table.map((row, i) => g.mode === "count" ? row[j] : r.row_pct[i][j]),
      marker: { color: color(g, j, c), line: { color: "#1b2130", width: 0.8 } },
      hovertemplate: `${esc(c)}: %{y:.3g}${g.mode === "count" ? "" : "%"}<extra></extra>` }));
    Plotly.react(el, traces, { ...baseLayout(g), barmode: "group", bargap: 0.3, showlegend: true,
      legend: { orientation: "h", y: 1.08, x: 0 },
      xaxis: axis(g), yaxis: yAxis(g, g.ylabel || (g.mode === "count" ? "Count" : "Percent of row")) }, PLOT_CONFIG);
  }

  async function exportPlot(format) {
    if (!lastResult) { toast("Add some data first, then export the graph."); return; }
    try {
      const url = await Plotly.toImage($("plot"), { format, width: 900, height: 650, scale: format === "png" ? 3 : 1 });
      const res = await api("/api/exports", { method: "POST", body: JSON.stringify({ filename: `${projectName} - ${active().title}`, data_url: url }) });
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
  function importFile(file) {
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
    lastResult = null; lastError = null;
    renderSidebar(); renderGrid(); renderOptions(); renderFormat(); renderResults(); drawPlot(); updateUndoButtons();
    run();
  }

  const grid = $("grid");
  grid.addEventListener("input", onGridInput);
  grid.addEventListener("paste", onGridPaste);
  grid.addEventListener("keydown", onGridKey);
  grid.addEventListener("click", onGridClick);

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
  $("tf-close").onclick = () => { $("transform-backdrop").hidden = true; };
  $("transform-backdrop").onclick = e => { if (e.target.id === "transform-backdrop") $("transform-backdrop").hidden = true; };
  $("tf-apply").onclick = applyTransform;
  $("file-data").onchange = e => { if (e.target.files[0]) importData(e.target.files[0]); e.target.value = ""; };
  $("btn-example").onclick = () => { recordUndo(true); applyExample(active()); save(); renderGrid(); renderOptions(); renderFormat(); scheduleRun(); };
  $("btn-clear").onclick = () => {
    const s = active();
    recordUndo(true);
    s.data = blankRows(TYPES[s.type].minRows, s.cols.length); save(); renderGrid(); scheduleRun();
    toast("Data cleared. Press Ctrl+Z to undo.");
  };
  $("btn-undo").onclick = () => undoRedo("undo");
  $("btn-redo").onclick = () => undoRedo("redo");
  $("btn-format").onclick = () => {
    const f = $("graph-format"); f.hidden = !f.hidden;
    $("btn-format").classList.toggle("on", !f.hidden); $("btn-format").setAttribute("aria-expanded", String(!f.hidden));
  };
  $("btn-png").onclick = () => exportPlot("png");
  $("btn-svg").onclick = () => exportPlot("svg");
  $("btn-copy").onclick = copyResults;
  $("btn-xlsx").onclick = exportXlsx;
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") { hideProjects(); $("transform-backdrop").hidden = true; }
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
