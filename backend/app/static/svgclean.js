/* Turns Plotly's SVG into a clean, fully editable vector file for Illustrator, Inkscape, Affinity,
 * CorelDRAW and PowerPoint ("Convert to Shape"):
 *  - no clipping masks: elements fully inside the plot area are simply unclipped, elements fully
 *    outside it are dropped, and only an element that really crosses the edge keeps its own small clip
 *  - no invisible boxes (hover/click catchers, transparent backgrounds) left behind
 *  - every point, bar, error bar, line and text is its own object, in named groups
 *    ("Control – points", "X axis", "Legend"…) so the Layers panel reads like the graph
 *  - styles written as plain attributes, colors as hex, one font name per text
 *  - round points written as real circles
 *  - text stays text (editable), physical size in points so it opens at the export size
 * Runs in the browser (needs layout to measure positions). */
(() => {
  "use strict";
  const SHAPES = "path,rect,circle,ellipse,line,polyline,polygon,text,image,use";
  const KEEP_PROPS = new Set(["fill", "fill-opacity", "stroke", "stroke-width", "stroke-opacity", "stroke-dasharray", "stroke-linecap",
    "stroke-linejoin", "stroke-miterlimit", "opacity", "font-family", "font-size", "font-weight", "font-style", "text-anchor",
    "dominant-baseline", "letter-spacing", "text-decoration", "visibility", "display", "fill-rule"]);
  const LAYER_NAMES = {
    "bglayer": "Plot background", "gridlayer": "Gridlines", "minor-gridlayer": "Minor gridlines", "zerolinelayer": "Zero line",
    "xaxislayer-above": "X axis ticks and labels", "yaxislayer-above": "Y axis ticks and labels",
    "xlines-above": "X axis line", "ylines-above": "Y axis line", "legend": "Legend", "shapelayer": "Shapes",
    "scatterlayer": "Data", "barlayer": "Bars", "boxlayer": "Box plots", "violinlayer": "Violins", "heatmaplayer": "Heat map",
    "colorbar": "Color scale", "cbaxis": "Color scale axis",
  };
  const SUB_NAMES = { points: "points", errorbars: "error bars", lines: "line", fills: "fill", text: "values" };

  const num = v => { const n = parseFloat(v); return isFinite(n) ? n : null; };
  function hex(c) {
    if (!c) return c;
    const m = String(c).trim().match(/^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/i);
    if (!m) return [String(c).trim(), null];
    const h = "#" + [m[1], m[2], m[3]].map(x => Math.round(+x).toString(16).padStart(2, "0")).join("");
    return [h, m[4] != null ? +m[4] : null];
  }
  const firstFont = f => String(f || "").split(",")[0].replace(/["']/g, "").trim();

  // ---- style attribute → presentation attributes -------------------------------------------
  function styleToAttrs(el, font) {
    const st = el.getAttribute("style");
    el.removeAttribute("style");
    const props = {};
    if (st) st.split(";").forEach(p => { const i = p.indexOf(":"); if (i > 0) props[p.slice(0, i).trim()] = p.slice(i + 1).trim(); });
    // attributes already present count too
    for (const k of KEEP_PROPS) if (el.hasAttribute(k) && props[k] === undefined) props[k] = el.getAttribute(k);
    for (const [k, v0] of Object.entries(props)) {
      if (!KEEP_PROPS.has(k)) continue;
      let v = v0;
      if (k === "fill" || k === "stroke") {
        if (/^url\(/.test(v)) v = v.replace(/["']/g, "");
        else {
          const [h, a] = hex(v);
          v = h;
          if (a != null && a < 1) props[k + "-opacity"] = String((num(props[k + "-opacity"]) ?? 1) * a);
          if (a === 0) v = "none";
        }
      }
      if (k === "stroke-width" || k === "font-size" || k === "letter-spacing") v = String(v).replace(/px$/, "");
      if (k === "font-family") v = font || firstFont(v);
      props[k] = v;
    }
    for (const [k, v] of Object.entries(props)) {
      if (!KEEP_PROPS.has(k) || v === "" || v == null) continue;
      el.setAttribute(k, v);
    }
    // defaults that only add noise
    if (el.getAttribute("opacity") === "1") el.removeAttribute("opacity");
    if (el.getAttribute("fill-opacity") === "1") el.removeAttribute("fill-opacity");
    if (el.getAttribute("stroke-opacity") === "1") el.removeAttribute("stroke-opacity");
    if (el.getAttribute("visibility") === "visible") el.removeAttribute("visibility");
  }

  function invisible(el) {
    const tag = el.tagName.toLowerCase();
    const a = k => el.getAttribute(k);
    if (a("display") === "none" || a("visibility") === "hidden" || num(a("opacity")) === 0) return true;
    if (tag === "text") return !el.textContent.trim() || a("fill") === "none" || num(a("fill-opacity")) === 0;
    if (tag === "image" || tag === "use") return false;
    if (tag === "path" && !/[0-9]/.test(a("d") || "")) return true;
    if (tag === "rect" && (num(a("width")) === 0 || num(a("height")) === 0) && !(a("stroke") && a("stroke") !== "none")) return true;
    const noFill = a("fill") === "none" || a("fill") === "transparent" || num(a("fill-opacity")) === 0;
    // missing fill = black by SVG default, but Plotly always writes one; treat missing as visible
    const noStroke = !a("stroke") || a("stroke") === "none" || num(a("stroke-opacity")) === 0 || num(a("stroke-width")) === 0;
    if (noFill && noStroke) return true;
    if (noFill) el.setAttribute("fill", "none");
    if (noStroke && a("stroke")) { el.removeAttribute("stroke"); el.removeAttribute("stroke-width"); el.removeAttribute("stroke-opacity"); el.removeAttribute("stroke-dasharray"); }
    return false;
  }

  // ---- clipping: keep only what is needed ----------------------------------------------------
  function rootMatrix(svg, el) {
    const a = svg.getScreenCTM(), b = el.getScreenCTM();
    return a && b ? a.inverse().multiply(b) : new DOMMatrix();
  }
  function boxIn(svg, el) {
    let bb;
    try { bb = el.getBBox(); } catch { return null; }
    if (!bb) return null;
    const m = rootMatrix(svg, el), sw = (num(el.getAttribute("stroke-width")) || 0) / 2;
    const pts = [[bb.x - sw, bb.y - sw], [bb.x + bb.width + sw, bb.y - sw], [bb.x - sw, bb.y + bb.height + sw], [bb.x + bb.width + sw, bb.y + bb.height + sw]]
      .map(([x, y]) => new DOMPoint(x, y).matrixTransform(m));
    const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
    return { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) };
  }
  function resolveClips(svg, stats) {
    const users = [...svg.querySelectorAll("[clip-path]")];
    const extra = [];
    users.forEach(g => {
      const ref = (g.getAttribute("clip-path").match(/#([^)"']+)/) || [])[1];
      const cp = ref && svg.querySelector(`clipPath[id="${CSS.escape(ref)}"]`);
      const r = cp && cp.querySelector("rect");
      g.removeAttribute("clip-path");
      if (!r) return;
      // the clip rectangle in root coordinates (it lives in g's user space)
      const m = rootMatrix(svg, g), x = num(r.getAttribute("x")) || 0, y = num(r.getAttribute("y")) || 0;
      const w = num(r.getAttribute("width")) || 0, h = num(r.getAttribute("height")) || 0;
      const c = [[x, y], [x + w, y + h]].map(([px, py]) => new DOMPoint(px, py).matrixTransform(m));
      const clip = { x0: Math.min(c[0].x, c[1].x), y0: Math.min(c[0].y, c[1].y), x1: Math.max(c[0].x, c[1].x), y1: Math.max(c[0].y, c[1].y) };
      const tol = 0.75;
      (g.matches(SHAPES) ? [g] : [...g.querySelectorAll(SHAPES)]).forEach(el => {
        if (el.closest("defs")) return;
        const b = boxIn(svg, el);
        if (!b) return;
        if (b.x0 >= clip.x0 - tol && b.y0 >= clip.y0 - tol && b.x1 <= clip.x1 + tol && b.y1 <= clip.y1 + tol) return;  // fully inside
        if (b.x1 < clip.x0 || b.x0 > clip.x1 || b.y1 < clip.y0 || b.y0 > clip.y1) { el.remove(); stats.dropped++; return; }
        // only just touching the edge (bar outlines, error bar caps on the axis): no clip needed
        const over = Math.max(clip.x0 - b.x0, clip.y0 - b.y0, b.x1 - clip.x1, b.y1 - clip.y1);
        if (over <= Math.max(3, (num(el.getAttribute("stroke-width")) || 0) + 1)) return;
        stats.edges = (stats.edges || []).concat([`${el.tagName}:${over.toFixed(1)}`]);
        extra.push([el, clip]);  // really crosses the edge: give this one element its own clip
      });
    });
    // clip rectangles for the few edge-crossing elements, in their parent's coordinates
    const defs = svg.querySelector("defs") || svg.insertBefore(document.createElementNS(svg.namespaceURI, "defs"), svg.firstChild);
    extra.forEach(([el, clip], i) => {
      const parent = el.parentNode;
      const inv = rootMatrix(svg, parent).inverse();
      const p0 = new DOMPoint(clip.x0, clip.y0).matrixTransform(inv), p1 = new DOMPoint(clip.x1, clip.y1).matrixTransform(inv);
      const id = `edge-clip-${i + 1}`;
      const cp = document.createElementNS(svg.namespaceURI, "clipPath");
      cp.setAttribute("id", id);
      const r = document.createElementNS(svg.namespaceURI, "rect");
      r.setAttribute("x", Math.min(p0.x, p1.x).toFixed(2)); r.setAttribute("y", Math.min(p0.y, p1.y).toFixed(2));
      r.setAttribute("width", Math.abs(p1.x - p0.x).toFixed(2)); r.setAttribute("height", Math.abs(p1.y - p0.y).toFixed(2));
      cp.appendChild(r); defs.appendChild(cp);
      const wrap = document.createElementNS(svg.namespaceURI, "g");
      wrap.setAttribute("clip-path", `url(#${id})`);
      wrap.setAttribute("data-eh-name", "Clipped at the plot edge");
      parent.insertBefore(wrap, el); wrap.appendChild(el);
      stats.clipped++;
    });
    svg.querySelectorAll("defs clipPath:not([id^=edge-clip])").forEach(c => c.remove());
  }

  // ---- naming -------------------------------------------------------------------------------
  const LAYER_TYPE = { barlayer: "bar", boxlayer: "box", violinlayer: "violin", heatmaplayer: "heatmap" };
  function nameGroups(svg, traceNames, traceList) {
    // bars, boxes and violins carry no id: their n-th group is the n-th trace of that type
    Object.entries(LAYER_TYPE).forEach(([layer, type]) => {
      const list = (traceList || []).filter(t => t.type === type);
      svg.querySelectorAll(`g.${layer}`).forEach(L => {
        [...L.children].filter(c => c.classList.contains("trace")).forEach((g, i) => { if (list[i]) g.setAttribute("data-eh-name", list[i].name); });
      });
    });
    svg.querySelectorAll("g.overplot > g.xy, g.overplot > g").forEach(g => { if (!g.hasAttribute("data-eh-name")) g.setAttribute("data-eh-name", "Plot area"); });
    svg.querySelectorAll("g[class]").forEach(g => {
      const cls = g.getAttribute("class").split(/\s+/);
      if (cls.includes("trace")) {
        if (g.hasAttribute("data-eh-name")) return;
        const uid = cls.map(c => c.match(/^trace(.+)$/)).find(m => m && m[1] !== "s");
        const nm = uid && traceNames[uid[1]];
        if (nm) g.setAttribute("data-eh-name", nm);
        return;
      }
      if (SUB_NAMES[cls[0]] && g.parentNode && g.parentNode.getAttribute("data-eh-name")) {
        const parent = g.parentNode.getAttribute("data-eh-name"), inBars = !!g.closest("g.barlayer");
        let sub = inBars && cls[0] === "points" ? "bars" : SUB_NAMES[cls[0]];
        if (/mean and error bar$/.test(parent)) sub = cls[0] === "points" ? "mean" : cls[0] === "errorbars" ? "error bar" : sub;
        g.setAttribute("data-eh-name", `${parent.replace(/ – mean and error bar$/, "")} – ${sub}`);
        return;
      }
      for (const c of cls) if (LAYER_NAMES[c]) { g.setAttribute("data-eh-name", LAYER_NAMES[c]); return; }
    });
    // axis lines are single paths
    svg.querySelectorAll("path[class]").forEach(p => {
      const c = p.getAttribute("class").split(/\s+/)[0];
      if (LAYER_NAMES[c]) p.setAttribute("data-eh-name", LAYER_NAMES[c]);
    });
    // labels and annotations: named by their text
    const lines = el => [...el.querySelectorAll("text")].map(t => { const sp = t.querySelectorAll("tspan.line"); return sp.length ? [...sp].map(x => x.textContent).join(" · ") : t.textContent; }).join(" ").trim().replace(/\s+/g, " ").slice(0, 40);
    svg.querySelectorAll("g.annotation").forEach(g => {
      const t = lines(g);
      g.setAttribute("data-eh-name", t ? `Label: ${t}` : "Label");
    });
    // legend entries: one group per series
    svg.querySelectorAll("g.legend g.traces").forEach(g => {
      const t = g.textContent.trim().replace(/\s+/g, " ").slice(0, 40);
      g.setAttribute("data-eh-name", t ? `Legend: ${t}` : "Legend entry");
    });
    // titles: name the text itself
    svg.querySelectorAll("text.gtitle, text.xtitle, text.ytitle").forEach(t => t.setAttribute("data-eh-name",
      t.classList.contains("gtitle") ? "Title" : t.classList.contains("xtitle") ? "X axis title" : "Y axis title"));
  }

  // ---- round markers → circles ----------------------------------------------------------------
  function circles(svg, stats) {
    svg.querySelectorAll("path").forEach(p => {
      const d = (p.getAttribute("d") || "").replace(/\s+/g, "");
      const m = d.match(/^M([\d.]+),0A\1,\1 ?01,10,-\1A\1,\1 ?00,1\1,0Z$/);
      if (!m) return;
      const t = (p.getAttribute("transform") || "").match(/^translate\(([-\d.e]+)[ ,]+([-\d.e]+)\)$/);
      if (!t && p.getAttribute("transform")) return;
      const c = document.createElementNS(svg.namespaceURI, "circle");
      c.setAttribute("cx", t ? t[1] : "0"); c.setAttribute("cy", t ? t[2] : "0"); c.setAttribute("r", m[1]);
      for (const at of [...p.attributes]) if (!["d", "transform"].includes(at.name)) c.setAttribute(at.name, at.value);
      p.replaceWith(c);
      stats.circles++;
    });
  }

  // ---- tidy the tree ------------------------------------------------------------------------
  function simplify(svg) {
    let changed = true;
    while (changed) {
      changed = false;
      [...svg.querySelectorAll("g")].reverse().forEach(g => {
        if (!g.parentNode) return;
        if (!g.children.length) { g.remove(); changed = true; return; }
        const named = g.hasAttribute("data-eh-name"), attrs = [...g.attributes].map(a => a.name).filter(n => n !== "data-eh-name");
        if (g.closest("defs")) return;
        // a group that adds nothing: lift its children out
        if (!named && !attrs.length) { while (g.firstChild) g.parentNode.insertBefore(g.firstChild, g); g.remove(); changed = true; return; }
        // a transform-only group with one child: move the transform onto the child
        if (attrs.length === 1 && attrs[0] === "transform" && g.children.length === 1 && !named) {
          const ch = g.firstElementChild;
          ch.setAttribute("transform", `${g.getAttribute("transform")} ${ch.getAttribute("transform") || ""}`.trim());
          g.parentNode.insertBefore(ch, g); g.remove(); changed = true;
        }
      });
    }
    // a named group whose only child is another group: keep the outer name, drop the inner group
    [...svg.querySelectorAll("g[data-eh-name]")].reverse().forEach(g => {
      const ch = g.children.length === 1 ? g.firstElementChild : null;
      if (!ch || ch.tagName.toLowerCase() !== "g") return;
      const attrs = [...ch.attributes].map(a => a.name).filter(n => n !== "data-eh-name");
      if (attrs.some(n => n === "clip-path" || n === "transform")) return;
      attrs.forEach(n => { if (!g.hasAttribute(n)) g.setAttribute(n, ch.getAttribute(n)); });
      while (ch.firstChild) g.insertBefore(ch.firstChild, ch);
      ch.remove();
    });
    svg.querySelectorAll("defs").forEach(d => { if (!d.children.length) d.remove(); });
  }

  function finalNames(svg) {
    const used = new Map();
    svg.querySelectorAll("[data-eh-name]").forEach(el => {
      const name = el.getAttribute("data-eh-name");
      el.removeAttribute("data-eh-name");
      let id = name.replace(/[^A-Za-z0-9_-]+/g, "_").replace(/^_+|_+$/g, "") || "item";
      if (!/^[A-Za-z_]/.test(id)) id = "_" + id;
      const n = (used.get(id) || 0) + 1; used.set(id, n);
      el.setAttribute("id", n > 1 ? `${id}_${n}` : id);
      el.setAttribute("data-name", n > 1 ? `${name} ${n}` : name);          // Illustrator / Affinity layer names
      el.setAttribute("data-ink-label", n > 1 ? `${name} ${n}` : name);   // becomes inkscape:label
    });
  }

  /** svgText: Plotly SVG. opts: {traceNames: {uid: name}, font, widthPt, heightPt, title}. Returns {svg, stats}. */
  function clean(svgText, opts = {}) {
    const host = document.createElement("div");
    host.style.cssText = "position:fixed;left:-20000px;top:0;visibility:hidden;pointer-events:none";
    host.innerHTML = svgText;
    document.body.appendChild(host);
    const svg = host.querySelector("svg");
    const stats = { dropped: 0, clipped: 0, circles: 0, invisible: 0 };
    try {
      nameGroups(svg, opts.traceNames || {}, opts.traceList || []);
      // style → attributes first, so visibility checks and measurements see real values
      svg.querySelectorAll("*").forEach(el => styleToAttrs(el, opts.font));
      resolveClips(svg, stats);
      [...svg.querySelectorAll(SHAPES)].forEach(el => { if (!el.closest("defs, clipPath") && invisible(el)) { el.remove(); stats.invisible++; } });
      circles(svg, stats);
      // strip interface leftovers
      svg.querySelectorAll("*").forEach(el => {
        [...el.attributes].forEach(a => {
          if (a.name === "class" || (a.name.startsWith("data-") && a.name !== "data-eh-name") || ["pointer-events", "vector-effect", "cursor", "shape-rendering"].includes(a.name)) el.removeAttribute(a.name);
        });
        if (el.tagName.toLowerCase() === "text" && /\s{2}/.test(el.textContent)) el.setAttribute("xml:space", "preserve");
      });
      simplify(svg);
      // background rectangle first in the file
      const bg = svg.querySelector(":scope > rect");
      if (bg) bg.setAttribute("data-eh-name", "Background");
      finalNames(svg);
      const vb = svg.getAttribute("viewBox") || `0 0 ${svg.getAttribute("width")} ${svg.getAttribute("height")}`;
      [...svg.attributes].forEach(a => { if (!["viewBox", "xmlns", "xmlns:xlink"].includes(a.name)) svg.removeAttribute(a.name); });
      svg.setAttribute("viewBox", vb);
      if (opts.widthPt) { svg.setAttribute("width", `${opts.widthPt}pt`); svg.setAttribute("height", `${opts.heightPt}pt`); }
      svg.setAttribute("version", "1.1");
      if (opts.title) { const t = document.createElementNS(svg.namespaceURI, "title"); t.textContent = opts.title; svg.insertBefore(t, svg.firstChild); }
      const out = new XMLSerializer().serializeToString(svg).replace(/ data-ink-label="/g, ' inkscape:label="')
        .replace(/^<svg/, '<svg xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"');
      return { svg: '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n' + out, stats };
    } finally { host.remove(); }
  }

  /** Several cleaned panels side by side in one file (figure layouts). panels: [{svg, x, y, name}] */
  function combine(panels, W, H, opts = {}) {
    const parser = new DOMParser();
    let body = "";
    panels.forEach(p => {
      const doc = parser.parseFromString(p.svg, "image/svg+xml").documentElement;
      const inner = [...doc.childNodes].filter(n => !(n.nodeType === 1 && n.tagName === "title")).map(n => new XMLSerializer().serializeToString(n)).join("")
        // ids must stay unique across panels
        .replace(/\b(id|data-name|inkscape:label)="([^"]*)"/g, (m, a, v) => `${a}="${a === "id" ? p.idPrefix + v : v}"`)
        .replace(/url\(#([^)]+)\)/g, (m, v) => `url(#${p.idPrefix}${v})`);
      body += `<g id="${p.idPrefix.replace(/_$/, "")}" data-name="${p.name}" inkscape:label="${p.name}" transform="translate(${p.x},${p.y})">${inner}</g>`;
      if (p.extra) body += p.extra;
    });
    return '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n' +
      `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" version="1.1" viewBox="0 0 ${W} ${H}"${opts.widthPt ? ` width="${opts.widthPt}pt" height="${opts.heightPt}pt"` : ""}>${opts.title ? `<title>${opts.title}</title>` : ""}${body}</svg>`;
  }

  window.EHSvg = { clean, combine };
})();
