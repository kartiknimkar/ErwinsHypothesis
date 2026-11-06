/* Erwin's Hypothesis: preview interface (vanilla JS, no build step). */
(() => {
  "use strict";

  // ---------- project model ----------
  const MIN_ROWS = 15;

  const TYPES = {
    ttest: {
      label: "Compare two groups",
      cols: ["Control", "Treated"],
      colKind: ["Group A", "Group B"],
      hint: "Type or paste the values for each group into its column, one value per cell. Click a column name to rename it. Groups can have different numbers of values (except for a paired test).",
      example: {
        cols: ["Control", "Treated"],
        rows: [[4.2, 6.1], [5.1, 7.3], [3.8, 6.8], [4.9, 5.9], [5.5, 7.9], [4.4, 6.5], [4.0, 7.0], [5.2, 6.2]],
      },
      options: { kind: "unpaired", alpha: 0.05 },
      graph: { title: "", ylabel: "Response", style: "dots", err: "sd" },
    },
    regression: {
      label: "Fit a straight line",
      cols: ["X", "Y"],
      colKind: ["X values", "Y values"],
      hint: "Put the independent variable (what you set or measured first, e.g. concentration) in X and the outcome in Y. Each row is one point. Click a column name to rename it.",
      example: {
        cols: ["Concentration (µg/mL)", "Absorbance"],
        rows: [[0, 0.02], [5, 0.11], [10, 0.21], [20, 0.39], [40, 0.83], [60, 1.18], [80, 1.62]],
      },
      options: { alpha: 0.05 },
      graph: { title: "", band: true },
    },
  };

  let project = null;
  let runTimer = null;

  function uid() { return Math.random().toString(36).slice(2, 10); }
  function blankRows(n, c) { return Array.from({ length: n }, () => Array(c).fill("")); }

  function newSheet(type, withExample = false) {
    const t = TYPES[type];
    const count = project ? project.sheets.filter(s => s.type === type).length + 1 : 1;
    const s = {
      id: uid(), type,
      title: (type === "ttest" ? "Two-group comparison " : "Linear regression ") + count,
      cols: [...t.cols],
      data: blankRows(MIN_ROWS, 2),
      options: { ...t.options },
      graph: { ...t.graph },
    };
    if (withExample) applyExample(s);
    return s;
  }

  function applyExample(s) {
    const ex = TYPES[s.type].example;
    s.cols = [...ex.cols];
    s.data = ex.rows.map(r => r.map(String));
    padRows(s);
  }

  function newProject() {
    project = { sheets: [] };
    const a = newSheet("ttest", true);
    a.title = "Example: Control vs Treated";
    project.sheets.push(a);
    const b = newSheet("regression", true);
    b.title = "Example: Standard curve";
    project.sheets.push(b);
    project.activeId = a.id;
    return project;
  }

  // ---------- saving (to the app folder's "projects" directory) ----------
  let projectName = null, saveTimer = null, saving = Promise.resolve();

  function setStatus(text, err = false) {
    const el = $("save-status");
    el.textContent = text; el.classList.toggle("err", err);
  }
  function save() {
    // autosave shortly after each change
    setStatus("Saving…");
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveNow, 500);
  }
  function saveNow() {
    clearTimeout(saveTimer);
    const name = projectName, body = JSON.stringify({ data: { sheets: project.sheets, activeId: project.activeId } });
    saving = saving.then(async () => {
      try {
        const res = await fetch(`/api/projects/${encodeURIComponent(name)}`, { method: "PUT",
          headers: { "Content-Type": "application/json" }, body });
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
    project = { sheets: data.sheets, activeId: data.activeId || data.sheets[0].id };
    projectName = name;
    $("project-name").value = name;
    setStatus("✓ Saved");
    renderAll();
  }
  async function createProject(name, withExamples) {
    const list = (await api("/api/projects")).projects.map(p => p.name.toLowerCase());
    let n = name, i = 2;
    while (list.includes(n.toLowerCase())) n = `${name} ${i++}`;
    if (projectName) await saveNow();
    project = withExamples ? newProject() : { sheets: [], activeId: null };
    if (!withExamples) { const s = newSheet("ttest"); project.sheets.push(s); project.activeId = s.id; }
    const saved = await api(`/api/projects/${encodeURIComponent(n)}`, { method: "PUT",
      body: JSON.stringify({ data: project }) });
    projectName = saved.name;
    $("project-name").value = projectName;
    setStatus("✓ Saved");
    renderAll();
  }
  function active() { return project.sheets.find(s => s.id === project.activeId) || project.sheets[0]; }

  function padRows(s) {
    // keep a few empty rows at the bottom so there is always room to type
    let lastFilled = -1;
    s.data.forEach((r, i) => { if (r.some(v => String(v).trim() !== "")) lastFilled = i; });
    const want = Math.max(MIN_ROWS, lastFilled + 4);
    while (s.data.length < want) s.data.push(Array(s.cols.length).fill(""));
  }

  // ---------- helpers ----------
  const $ = id => document.getElementById(id);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const isNum = v => String(v).trim() !== "" && !isNaN(Number(String(v).trim()));

  function fmt(v, digits = 4) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    if (v === 0) return "0";
    const a = Math.abs(v);
    if (a >= 1e5 || a < 1e-4) return v.toExponential(2);
    return Number(v.toPrecision(digits)).toString();
  }
  function fmtP(p) {
    if (p === null || p === undefined) return "—";
    if (p < 0.0001) return "P < 0.0001";
    return "P = " + (p < 0.001 ? p.toFixed(4) : p.toFixed(p < 0.01 ? 4 : 3));
  }

  const pOnly = p => fmtP(p).replace(/^P = /, "").replace(/^P < /, "< ");

  // ---------- sidebar ----------
  function renderSidebar() {
    const list = $("sheet-list");
    list.innerHTML = "";
    project.sheets.forEach(s => {
      const li = document.createElement("li");
      li.className = s.id === project.activeId ? "active" : "";
      li.innerHTML = `<span class="t">${esc(s.title)}</span><span class="k">${TYPES[s.type].label}</span>`;
      li.onclick = () => { project.activeId = s.id; save(); renderAll(); };
      list.appendChild(li);
    });
  }

  // ---------- grid ----------
  function renderGrid() {
    const s = active();
    padRows(s);
    const t = TYPES[s.type];
    const grid = $("grid");
    let html = "<thead><tr><th class='rownum'></th>";
    s.cols.forEach((c, j) => {
      html += `<th><span class="colkind">${t.colKind[j]}</span><input data-head="${j}" value="${esc(c)}" spellcheck="false" aria-label="${t.colKind[j]} name"></th>`;
    });
    html += "</tr></thead><tbody>";
    s.data.forEach((r, i) => {
      html += `<tr><td class="rownum">${i + 1}</td>`;
      r.forEach((v, j) => {
        const bad = String(v).trim() !== "" && !isNum(v) ? " bad" : "";
        html += `<td><input class="cell${bad}" data-r="${i}" data-c="${j}" value="${esc(v)}" inputmode="decimal" spellcheck="false"></td>`;
      });
      html += "</tr>";
    });
    grid.innerHTML = html + "</tbody>";
    $("data-hint").textContent = t.hint;
  }

  function cellAt(r, c) { return $("grid").querySelector(`input[data-r="${r}"][data-c="${c}"]`); }

  function onGridInput(e) {
    const el = e.target, s = active();
    if (el.dataset.head !== undefined) {
      s.cols[+el.dataset.head] = el.value;
      save(); scheduleRun(); renderOptions();
      return;
    }
    if (el.dataset.r === undefined) return;
    s.data[+el.dataset.r][+el.dataset.c] = el.value;
    el.classList.toggle("bad", el.value.trim() !== "" && !isNum(el.value));
    const before = s.data.length;
    padRows(s);
    if (s.data.length !== before) { renderGrid(); cellAt(+el.dataset.r, +el.dataset.c).focus(); }
    save(); scheduleRun();
  }

  function onGridPaste(e) {
    const el = e.target;
    if (el.dataset.r === undefined) return;
    const text = (e.clipboardData || window.clipboardData).getData("text");
    if (!/[\t\n\r]/.test(text)) return; // single value: normal paste
    e.preventDefault();
    const s = active();
    const rows = text.replace(/\r/g, "").replace(/\n+$/, "").split("\n").map(l => l.split("\t"));
    const r0 = +el.dataset.r, c0 = +el.dataset.c;
    rows.forEach((row, i) => {
      while (s.data.length <= r0 + i) s.data.push(Array(s.cols.length).fill(""));
      row.forEach((v, j) => { if (c0 + j < s.cols.length) s.data[r0 + i][c0 + j] = v.trim(); });
    });
    padRows(s); save(); renderGrid(); scheduleRun();
  }

  function onGridKey(e) {
    const el = e.target;
    if (el.dataset.r === undefined) return;
    const r = +el.dataset.r, c = +el.dataset.c;
    let target = null;
    if (e.key === "Enter" || (e.key === "ArrowDown")) target = cellAt(r + 1, c);
    else if (e.key === "ArrowUp") target = cellAt(r - 1, c);
    else if (e.key === "ArrowRight" && el.selectionStart === el.value.length) target = cellAt(r, c + 1);
    else if (e.key === "ArrowLeft" && el.selectionStart === 0) target = cellAt(r, c - 1);
    if (target) { e.preventDefault(); target.focus(); target.select(); }
  }

  // ---------- options ----------
  const TEST_CHOICES = [
    ["unpaired", "Unpaired t test", "Two independent groups (different subjects). Assumes similar spread in both groups."],
    ["welch", "Welch's t test", "Independent groups that may have different spread. A safe default when unsure."],
    ["paired", "Paired t test", "The same subjects measured twice (before/after). Each row is one pair."],
    ["mannwhitney", "Mann-Whitney test", "Nonparametric: no normality assumption. Compares ranks instead of means."],
  ];

  function renderOptions() {
    const s = active(), box = $("options");
    let html = "";
    if (s.type === "ttest") {
      html += TEST_CHOICES.map(([k, name, desc]) =>
        `<label class="choice ${s.options.kind === k ? "on" : ""}"><input type="radio" name="kind" value="${k}" ${s.options.kind === k ? "checked" : ""}>
         <span><b>${name}</b><small>${desc}</small></span></label>`).join("");
    }
    html += `<div class="row"><label for="opt-alpha">Significance level (α)</label>
      <select id="opt-alpha">${[0.05, 0.01, 0.1].map(a => `<option value="${a}" ${s.options.alpha === a ? "selected" : ""}>${a}</option>`).join("")}</select></div>`;
    box.innerHTML = html;
    box.querySelectorAll("input[name=kind]").forEach(r => r.onchange = () => {
      s.options.kind = r.value; save(); renderOptions(); scheduleRun();
    });
    $("opt-alpha").onchange = e => { s.options.alpha = Number(e.target.value); save(); scheduleRun(); };
  }

  // ---------- graph controls ----------
  function renderGraphControls() {
    const s = active(), g = s.graph, box = $("graph-controls");
    let html = `<label>Title<input data-g="title" value="${esc(g.title || "")}" placeholder="(none)"></label>`;
    if (s.type === "ttest") {
      html += `<label>Y axis label<input data-g="ylabel" value="${esc(g.ylabel || "")}"></label>
        <label>Style<select data-g="style">
          <option value="dots" ${g.style === "dots" ? "selected" : ""}>Dots + mean</option>
          <option value="bars" ${g.style === "bars" ? "selected" : ""}>Bars + dots</option></select></label>
        <label>Error bars<select data-g="err">
          <option value="sd" ${g.err === "sd" ? "selected" : ""}>Mean ± SD</option>
          <option value="sem" ${g.err === "sem" ? "selected" : ""}>Mean ± SEM</option></select></label>`;
    } else {
      html += `<label>Confidence band<select data-g="band">
          <option value="1" ${g.band ? "selected" : ""}>Show 95% band</option>
          <option value="" ${!g.band ? "selected" : ""}>Hide</option></select></label>`;
    }
    box.innerHTML = html;
    box.querySelectorAll("[data-g]").forEach(el => {
      el.oninput = el.onchange = () => {
        const k = el.dataset.g;
        g[k] = k === "band" ? !!el.value : el.value;
        save(); drawPlot();
      };
    });
  }

  // ---------- run analysis ----------
  let lastResult = null, lastError = null;

  function scheduleRun() { clearTimeout(runTimer); runTimer = setTimeout(run, 250); }

  async function run() {
    const s = active();
    const colVals = j => s.data.map(r => r[j]);
    let url, body;
    if (s.type === "ttest") {
      url = "/api/ttest";
      body = { a: colVals(0), b: colVals(1), name_a: s.cols[0] || "A", name_b: s.cols[1] || "B",
               kind: s.options.kind, alpha: s.options.alpha };
    } else {
      url = "/api/regression";
      body = { x: colVals(0), y: colVals(1), alpha: s.options.alpha };
    }
    // non-numeric cells are flagged in the grid and skipped
    const clean = arr => arr.map(v => (isNum(v) ? Number(v) : null));
    Object.keys(body).forEach(k => { if (Array.isArray(body[k])) body[k] = clean(body[k]); });

    const sheetId = s.id;
    try {
      const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const json = await res.json();
      if (active().id !== sheetId) return; // user switched sheets meanwhile
      if (!res.ok) { lastResult = null; lastError = json.detail || "Something went wrong."; }
      else { lastResult = json; lastError = null; }
    } catch {
      lastResult = null; lastError = "Can't reach the analysis engine. Is the app still running?";
    }
    renderResults(); drawPlot();
  }

  // ---------- results ----------
  function renderResults() {
    const s = active(), box = $("results");
    if (lastError) {
      box.innerHTML = `<div class="summary err"><b>Not enough to analyze yet.</b> ${esc(lastError)}</div>`;
      return;
    }
    const r = lastResult;
    if (!r) { box.innerHTML = ""; return; }
    const pct = Math.round((1 - r.alpha) * 100);
    let html = "";
    if (s.type === "ttest") {
      const [a, b] = r.groups;
      const dir = r.difference > 0 ? "higher" : "lower";
      const what = r.kind === "mannwhitney" ? "median" : "mean";
      html += r.significant
        ? `<div class="summary sig"><b>Significant difference</b> (${fmtP(r.p)}, ${r.stars}). The ${what} of <b>${esc(b.name)}</b> is ${fmt(Math.abs(r.difference))} ${dir} than <b>${esc(a.name)}</b>${r.ci_low !== null ? ` (${pct}% CI of the difference: ${fmt(r.ci_low)} to ${fmt(r.ci_high)})` : ""}.</div>`
        : `<div class="summary ns"><b>No significant difference</b> (${fmtP(r.p)}, ns). The data don't show convincing evidence that <b>${esc(a.name)}</b> and <b>${esc(b.name)}</b> differ. That isn't proof they're the same; a larger sample might detect a smaller effect.</div>`;
      html += `<table class="res">
        <tr class="sec"><td colspan="2">${esc(r.test_name)}</td></tr>
        <tr><td>P value</td><td>${pOnly(r.p)}</td></tr>
        <tr><td>Significance (α = ${r.alpha})</td><td>${r.stars}</td></tr>
        <tr><td>${r.statistic_name}${r.df !== null ? ", df" : ""}</td><td>${r.statistic_name} = ${fmt(r.statistic)}${r.df !== null ? `, df = ${fmt(r.df)}` : ""}</td></tr>
        <tr><td>${esc(r.difference_label)}</td><td>${fmt(r.difference)}</td></tr>
        ${r.ci_low !== null ? `<tr><td>${pct}% confidence interval</td><td>${fmt(r.ci_low)} to ${fmt(r.ci_high)}</td></tr>` : ""}
        ${r.n_pairs ? `<tr><td>Number of pairs</td><td>${r.n_pairs}</td></tr>` : ""}
        <tr class="sec"><td colspan="2">Descriptive statistics</td></tr>
        <tr><td></td><td>${esc(a.name)} &nbsp;·&nbsp; ${esc(b.name)}</td></tr>
        ${[["n", "n"], ["Mean", "mean"], ["SD", "sd"], ["SEM", "sem"], ["Median", "median"], ["Min", "min"], ["Max", "max"]]
          .map(([l, k]) => `<tr><td>${l}</td><td>${fmt(a[k])} &nbsp;·&nbsp; ${fmt(b[k])}</td></tr>`).join("")}
      </table>`;
      if (r.variance_check && r.variance_check.p < 0.05) {
        html += `<p class="note">⚠︎ The two groups have significantly different spread (F test ${fmtP(r.variance_check.p)}). Consider Welch's t test, which doesn't assume equal variances.</p>`;
      }
    } else {
      const xName = esc(s.cols[0] || "X"), yName = esc(s.cols[1] || "Y");
      html += r.significant
        ? `<div class="summary sig"><b>Significant relationship</b> (${fmtP(r.p)}, ${r.stars}). ${yName} changes by ${fmt(r.slope)} for each 1-unit increase in ${xName}. R² = ${fmt(r.r_squared, 3)}: about ${(r.r_squared * 100).toFixed(r.r_squared > 0.99 ? 1 : 0)}% of the variation in ${yName} is explained by the line.</div>`
        : `<div class="summary ns"><b>No significant linear relationship</b> (${fmtP(r.p)}, ns). The slope is not distinguishable from zero with these data (R² = ${fmt(r.r_squared, 3)}).</div>`;
      html += `<table class="res">
        <tr class="sec"><td colspan="2">Best-fit line</td></tr>
        <tr><td>Equation</td><td>${r.equation}</td></tr>
        <tr><td>Slope</td><td>${fmt(r.slope)} ± ${fmt(r.slope_se)}</td></tr>
        <tr><td>Y-intercept</td><td>${fmt(r.intercept)} ± ${fmt(r.intercept_se)}</td></tr>
        <tr><td>X-intercept</td><td>${fmt(r.x_intercept)}</td></tr>
        <tr class="sec"><td colspan="2">${pct}% confidence intervals</td></tr>
        <tr><td>Slope</td><td>${fmt(r.slope_ci[0])} to ${fmt(r.slope_ci[1])}</td></tr>
        <tr><td>Y-intercept</td><td>${fmt(r.intercept_ci[0])} to ${fmt(r.intercept_ci[1])}</td></tr>
        <tr class="sec"><td colspan="2">Goodness of fit</td></tr>
        <tr><td>R²</td><td>${fmt(r.r_squared)}</td></tr>
        <tr><td>Sy.x (residual SD)</td><td>${fmt(r.sy_x)}</td></tr>
        <tr class="sec"><td colspan="2">Is the slope different from zero?</td></tr>
        <tr><td>F, df</td><td>F = ${fmt(r.F)}, df = 1, ${r.df}</td></tr>
        <tr><td>P value</td><td>${pOnly(r.p)}</td></tr>
        <tr><td>Number of points</td><td>${r.n}</td></tr>
      </table>`;
      html += `<p class="note">"±" values are standard errors.</p>`;
    }
    box.innerHTML = html;
  }

  // ---------- plot ----------
  const PALETTE = ["#2f5bea", "#e4572e", "#17a398", "#8b5cf6"];
  const BASE_LAYOUT = {
    margin: { l: 64, r: 20, t: 46, b: 56 },
    paper_bgcolor: "#fff", plot_bgcolor: "#fff",
    font: { family: "-apple-system, Helvetica, Arial, sans-serif", size: 13, color: "#1d2433" },
    showlegend: false,
  };
  const AXIS = { showline: true, linewidth: 1.5, linecolor: "#1d2433", ticks: "outside", tickwidth: 1.5,
    ticklen: 5, showgrid: false, zeroline: false };

  function drawPlot() {
    const s = active(), el = $("plot");
    const r = lastResult;
    if (!r) {
      Plotly.purge(el);
      el.innerHTML = `<div class="empty"><div>Your graph will appear here once there is enough data.<br>Try <b>Load example</b> to see how it works.</div></div>`;
      return;
    }
    if (el.querySelector(".empty")) el.innerHTML = "";
    const g = s.graph;
    const config = { displaylogo: false, responsive: true,
      modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d", "toggleSpikelines"] };
    const title = g.title ? { text: g.title, font: { size: 16 } } : undefined;

    if (s.type === "ttest") {
      const traces = [], shapes = [], annotations = [];
      let ymax = -Infinity, ymin = Infinity;
      const groups = [0, 1].map(j => s.data.map(row => row[j]).filter(isNum).map(Number));
      groups.forEach((vals, j) => {
        const st = r.groups[j], color = PALETTE[j];
        const err = g.err === "sem" ? st.sem : st.sd;
        // deterministic jitter so dots don't sit on top of each other
        const xs = vals.map((_, i) => j + ((i * 0.618) % 1 - 0.5) * 0.28);
        vals.forEach(v => { ymax = Math.max(ymax, v); ymin = Math.min(ymin, v); });
        ymax = Math.max(ymax, st.mean + (err || 0));
        if (g.style === "bars") {
          traces.push({ type: "bar", x: [j], y: [st.mean], width: 0.55, marker: { color: color + "33", line: { color, width: 1.5 } },
            error_y: { type: "data", array: [err || 0], visible: true, color: "#1d2433", thickness: 1.5, width: 10 }, hoverinfo: "skip" });
        }
        traces.push({ type: "scatter", mode: "markers", x: xs, y: vals,
          marker: { color, size: 9, opacity: 0.85, line: { color: "#fff", width: 1 } },
          hovertemplate: `${esc(st.name)}: %{y}<extra></extra>` });
        if (g.style !== "bars") {
          traces.push({ type: "scatter", mode: "markers", x: [j], y: [st.mean],
            marker: { symbol: "line-ew", size: 44, line: { width: 3, color: "#1d2433" } },
            error_y: { type: "data", array: [err || 0], visible: true, color: "#1d2433", thickness: 1.5, width: 12 },
            hovertemplate: `Mean ${fmt(st.mean)} ± ${fmt(err)}<extra></extra>` });
        }
      });
      // significance bracket
      const span = (ymax - Math.min(0, ymin)) || 1;
      const yb = ymax + span * 0.08, tick = span * 0.03;
      shapes.push({ type: "path", path: `M 0 ${yb - tick} L 0 ${yb} L 1 ${yb} L 1 ${yb - tick}`, line: { color: "#1d2433", width: 1.5 } });
      annotations.push({ x: 0.5, y: yb, text: r.stars, showarrow: false, yanchor: "bottom", font: { size: r.stars === "ns" ? 13 : 18 } });
      const yrange = g.style === "bars" ? [Math.min(0, ymin - span * 0.05), yb + span * 0.14] : [ymin - span * 0.1, yb + span * 0.14];
      Plotly.react(el, traces, { ...BASE_LAYOUT, title, shapes, annotations,
        xaxis: { ...AXIS, tickvals: [0, 1], ticktext: r.groups.map(x => esc(x.name)), range: [-0.6, 1.6] },
        yaxis: { ...AXIS, title: { text: esc(g.ylabel || "") }, range: yrange } }, config);
    } else {
      const traces = [];
      if (g.band) {
        traces.push({ x: r.line.x, y: r.line.low, mode: "lines", line: { width: 0 }, hoverinfo: "skip" });
        traces.push({ x: r.line.x, y: r.line.high, mode: "lines", line: { width: 0 }, fill: "tonexty",
          fillcolor: "rgba(47,91,234,0.13)", hoverinfo: "skip" });
      }
      traces.push({ x: r.line.x, y: r.line.y, mode: "lines", line: { color: PALETTE[0], width: 2.5 },
        hovertemplate: "Fit: %{y:.4g}<extra></extra>" });
      traces.push({ x: r.points.x, y: r.points.y, mode: "markers",
        marker: { color: "#1d2433", size: 9, line: { color: "#fff", width: 1 } },
        hovertemplate: "(%{x}, %{y})<extra></extra>" });
      Plotly.react(el, traces, { ...BASE_LAYOUT, title,
        annotations: [{ xref: "paper", yref: "paper", x: 0.02, y: 0.98, xanchor: "left", yanchor: "top", showarrow: false,
          align: "left", text: `${r.equation}<br>R² = ${fmt(r.r_squared, 4)}`, font: { size: 12, color: "#667085" } }],
        xaxis: { ...AXIS, title: { text: esc(s.cols[0] || "X") } },
        yaxis: { ...AXIS, title: { text: esc(s.cols[1] || "Y") } } }, config);
    }
  }

  async function exportPlot(format) {
    if (!lastResult) { toast("Add some data first, then export the graph."); return; }
    try {
      const url = await Plotly.toImage($("plot"), { format, width: 900, height: 650, scale: format === "png" ? 3 : 1 });
      const res = await api("/api/exports", { method: "POST",
        body: JSON.stringify({ filename: `${projectName} - ${active().title}`, data_url: url }) });
      toast(`Saved <b>${esc(res.file)}</b> to the exports folder`, "exports");
    } catch (e) { toast(esc(e.message || "Export failed.")); }
  }

  // ---------- toast ----------
  let toastTimer = null;
  function toast(html, folder) {
    const el = $("toast");
    el.innerHTML = `<span>${html}</span>` + (folder ? `<button data-reveal="${folder}">Show folder</button>` : "");
    el.hidden = false;
    const b = el.querySelector("button");
    if (b) b.onclick = () => reveal(folder);
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, 6000);
  }
  function reveal(folder) {
    api(`/api/reveal/${folder}`, { method: "POST" }).catch(() => toast("Couldn't open the folder."));
  }

  // ---------- projects dialog ----------
  async function showProjects() {
    $("dialog-backdrop").hidden = false;
    $("new-project-name").value = "";
    const ul = $("project-list");
    ul.innerHTML = `<li class="emptyli">Loading…</li>`;
    try {
      const { projects } = await api("/api/projects");
      if (!projects.length) { ul.innerHTML = `<li class="emptyli">No projects yet.</li>`; return; }
      ul.innerHTML = projects.map(p => {
        const cur = p.name === projectName;
        const when = new Date(p.modified).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
        return `<li class="${cur ? "current" : ""}"><span class="pn">${esc(p.name)}</span><span class="pd">${when}</span>
          ${cur ? `<span class="pd">open now</span>` : `<button class="ghost small" data-open="${esc(p.name)}">Open</button>
          <button class="ghost small danger" data-del="${esc(p.name)}">Delete</button>`}</li>`;
      }).join("");
      ul.querySelectorAll("[data-open]").forEach(b => b.onclick = async () => {
        try { await openProject(b.dataset.open); hideProjects(); } catch (e) { toast(esc(e.message)); }
      });
      ul.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
        if (!confirm(`Delete the project "${b.dataset.del}"? Its file will be removed from the projects folder.`)) return;
        await api(`/api/projects/${encodeURIComponent(b.dataset.del)}`, { method: "DELETE" });
        showProjects();
      });
    } catch (e) { ul.innerHTML = `<li class="emptyli">${esc(e.message)}</li>`; }
  }
  function hideProjects() { $("dialog-backdrop").hidden = true; }

  async function renameProject(newName) {
    newName = newName.trim();
    if (!newName || newName === projectName) { $("project-name").value = projectName; return; }
    try {
      await saveNow();
      const r = await api(`/api/projects/${encodeURIComponent(projectName)}/rename`, { method: "POST",
        body: JSON.stringify({ new_name: newName }) });
      projectName = r.name;
      $("project-name").value = projectName;
      toast(`Project renamed to <b>${esc(projectName)}</b>`);
    } catch (e) { $("project-name").value = projectName; toast(esc(e.message)); }
  }

  function importFile(file) {
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const p = JSON.parse(reader.result);
        if (!Array.isArray(p.sheets) || !p.sheets.length) throw new Error();
        const base = file.name.replace(/\.(ehp|json)$/i, "");
        const list = (await api("/api/projects")).projects.map(x => x.name.toLowerCase());
        let n = base, i = 2;
        while (list.includes(n.toLowerCase())) n = `${base} ${i++}`;
        const saved = await api(`/api/projects/${encodeURIComponent(n)}`, { method: "PUT",
          body: JSON.stringify({ data: { sheets: p.sheets, activeId: p.activeId } }) });
        await openProject(saved.name);
        hideProjects();
        toast(`Imported <b>${esc(saved.name)}</b> into the projects folder`);
      } catch { toast("That file couldn't be imported. Is it an Erwin's Hypothesis project (.ehp)?"); }
    };
    reader.readAsText(file);
  }

  // ---------- wiring ----------
  function renderAll() {
    const s = active();
    project.activeId = s.id;
    $("sheet-title").value = s.title;
    $("sheet-kind").textContent = TYPES[s.type].label;
    lastResult = null; lastError = null;
    renderSidebar(); renderGrid(); renderOptions(); renderGraphControls(); renderResults(); drawPlot();
    run();
  }

  const grid = $("grid");
  grid.addEventListener("input", onGridInput);
  grid.addEventListener("paste", onGridPaste);
  grid.addEventListener("keydown", onGridKey);

  $("sheet-title").addEventListener("input", e => { active().title = e.target.value; save(); renderSidebar(); });
  $("btn-new").onclick = e => { e.stopPropagation(); $("new-menu").hidden = !$("new-menu").hidden; };
  document.addEventListener("click", () => { $("new-menu").hidden = true; });
  $("new-menu").querySelectorAll("button").forEach(b => b.onclick = () => {
    const s = newSheet(b.dataset.type);
    project.sheets.push(s); project.activeId = s.id; save(); renderAll();
    $("new-menu").hidden = true;
  });
  $("btn-delete").onclick = () => {
    const s = active();
    if (!confirm(`Delete "${s.title}"? This can't be undone.`)) return;
    project.sheets = project.sheets.filter(x => x.id !== s.id);
    if (!project.sheets.length) project.sheets.push(newSheet("ttest"));
    project.activeId = project.sheets[0].id; save(); renderAll();
  };
  $("btn-example").onclick = () => { applyExample(active()); save(); renderAll(); };
  $("btn-clear").onclick = () => {
    const s = active();
    if (!confirm("Clear all data in this table?")) return;
    s.data = blankRows(MIN_ROWS, s.cols.length); save(); renderAll();
  };
  $("btn-png").onclick = () => exportPlot("png");
  $("btn-svg").onclick = () => exportPlot("svg");
  $("btn-projects").onclick = showProjects;
  $("dlg-close").onclick = hideProjects;
  $("dialog-backdrop").onclick = e => { if (e.target.id === "dialog-backdrop") hideProjects(); };
  document.addEventListener("keydown", e => { if (e.key === "Escape") hideProjects(); });
  const doCreate = async () => {
    const n = $("new-project-name").value.trim() || "Untitled project";
    try { await createProject(n, false); hideProjects(); } catch (e) { toast(esc(e.message)); }
  };
  $("btn-new-project").onclick = doCreate;
  $("new-project-name").onkeydown = e => { if (e.key === "Enter") doCreate(); };
  $("btn-show-projects").onclick = () => reveal("projects");
  $("btn-import").onclick = () => $("file-import").click();
  $("file-import").onchange = e => { if (e.target.files[0]) importFile(e.target.files[0]); e.target.value = ""; };
  $("project-name").addEventListener("change", e => renameProject(e.target.value));
  $("project-name").addEventListener("keydown", e => { if (e.key === "Enter") e.target.blur(); });
  window.addEventListener("beforeunload", () => { if (saveTimer) saveNow(); });

  // start: reopen the last project, or create a first one with examples
  (async () => {
    try {
      const { projects, last } = await api("/api/projects");
      const pick = last || (projects[0] && projects[0].name);
      if (pick) await openProject(pick);
      else await createProject("My first project", true);
    } catch {
      project = newProject(); projectName = "Untitled";
      $("project-name").value = projectName;
      setStatus("Can't reach the app's engine", true);
      renderAll();
    }
  })();
})();
