/* One native draft control; decorations and diffs never modify its contents. */
(() => {
  const byId = id => document.getElementById(id);
  const text = byId("source-editor-text"), full = byId("template-editor-full");
  const decoration = byId("template-editor-decoration"), controls = byId("template-editor-controls");
  const view = byId("template-editor-view"), search = byId("template-editor-search");
  const display = byId("template-editor-display"), diff = byId("template-editor-diff");
  const rows = byId("template-editor-diff-rows"), diffStatus = byId("template-editor-diff-status");
  const refresh = byId("template-editor-refresh"), diagnostics = byId("template-editor-diagnostics");
  const count = byId("template-editor-match-count");
  let detail = null, request = null, analysis = null, revision = 0, timer, serial = 0, diffSerial = 0;
  let diffResult = null, composing = false;

  function marked(value) {
    const fragment = document.createDocumentFragment();
    if (!search.value) { fragment.append(document.createTextNode(value)); return [fragment, 0]; }
    const pattern = new RegExp(search.value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "giu");
    let cursor = 0, matches = 0;
    for (const match of value.matchAll(pattern)) {
      fragment.append(document.createTextNode(value.slice(cursor, match.index)));
      const mark = document.createElement("mark"); mark.textContent = match[0]; fragment.append(mark);
      cursor = match.index + match[0].length; matches++;
    }
    fragment.append(document.createTextNode(value.slice(cursor)));
    return [fragment, matches];
  }

  function syncScroll() {
    decoration.style.width = `${text.clientWidth + 2}px`;
    decoration.style.height = `${text.clientHeight + 2}px`;
    decoration.scrollTop = text.scrollTop; decoration.scrollLeft = text.scrollLeft;
  }

  function paint() {
    if (!detail?.template_kind) return;
    const fragment = document.createDocumentFragment();
    let matches = 0;
    const lines = text.value.split("\n");
    lines.forEach((line, index) => {
      const span = document.createElement("span");
      const applicable = analysis?.line_views?.[index];
      if (view.value && Array.isArray(applicable) && !applicable.includes(view.value)) span.className = "template-editor-inactive";
      const [content, found] = marked(line); span.append(content); matches += found;
      fragment.append(span);
      if (index < lines.length - 1) fragment.append(document.createTextNode("\n"));
    });
    fragment.append(document.createTextNode("\u200b"));
    decoration.replaceChildren(fragment);
    syncScroll();
    if (display.value === "full") count.textContent = `${matches} matches`;
  }

  function focusLine(number) {
    display.value = "full"; showDisplay();
    const start = text.value.split("\n").slice(0, number - 1).reduce((total, line) => total + line.length + 1, 0);
    text.focus(); text.setSelectionRange(start, text.value.indexOf("\n", start) < 0 ? text.value.length : text.value.indexOf("\n", start));
    text.scrollTop = Math.max(0, (number - 3) * parseFloat(getComputedStyle(text).lineHeight)); syncScroll();
  }

  function showDiagnostics(items = [], message = "") {
    diagnostics.replaceChildren();
    const summary = document.createElement("p");
    summary.textContent = message || (items.length ? `${items.length} validation issue(s). Save is blocked until these are fixed.` : "Structure and view tags are valid.");
    diagnostics.append(summary);
    if (!items.length) return;
    const list = document.createElement("ul");
    for (const item of items) {
      const li = document.createElement("li"), label = document.createElement(item.line ? "button" : "span");
      label.textContent = `${item.line ? `Line ${item.line}: ` : ""}${item.message}`;
      if (item.line) { label.type = "button"; label.addEventListener("click", () => focusLine(item.line)); }
      li.append(label); list.append(li);
    }
    diagnostics.append(list);
  }

  function payload() {
    return {path: detail.path, text: text.value, master_revision: detail.master_revision, draft_revision: revision};
  }

  async function analyze() {
    if (!detail?.template_kind || composing) return;
    const target = detail, draft = revision, token = ++serial;
    try {
      const value = await request("/api/edit-source/analyze", payload());
      if (target !== detail || draft !== revision || token !== serial) return;
      analysis = value; paint(); showDiagnostics(value.diagnostics);
    } catch (error) {
      if (target !== detail || draft !== revision || token !== serial) return;
      showDiagnostics([], `Validation unavailable: ${error.message}. Your draft is retained.`);
    }
  }

  function paintDiff() {
    rows.replaceChildren(); let matches = 0;
    for (const row of diffResult?.rows || []) {
      const tr = document.createElement("tr"); tr.className = `template-editor-diff-${row.kind}`;
      if (row.kind === "gap") { const td = document.createElement("td"); td.colSpan = 4; td.textContent = "…"; tr.append(td); }
      else {
        for (const side of ["master", "proposed"]) {
          const number = document.createElement("td"); number.className = "template-editor-line-number";
          number.textContent = row[`${side}_line`] || "";
          const cell = document.createElement("td"), pre = document.createElement("pre");
          const [content, found] = marked(row[`${side}_text`] || ""); matches += found; pre.append(content); cell.append(pre); tr.append(number, cell);
        }
      }
      rows.append(tr);
    }
    count.textContent = `${matches} displayed diff matches`;
  }

  async function loadDiff() {
    const target = detail, draft = revision, token = ++diffSerial;
    diffResult = null; rows.replaceChildren(); count.textContent = ""; diffStatus.textContent = "Reading master on disk…";
    refresh.disabled = true;
    try {
      const value = await request("/api/edit-source/diff", payload());
      if (target !== detail || draft !== revision || token !== diffSerial) return;
      diffResult = value; paintDiff();
      diffStatus.textContent = `Master revision ${value.master_revision.slice(0, 12)}. ${value.final_newline_change ? `Final newline ${value.final_newline_change}.` : value.rows.length ? "" : "No changes."}${value.conflict ? " Master changed since opening; save will be blocked. Your draft is retained." : ""}`;
    } catch (error) {
      if (target === detail && token === diffSerial) diffStatus.textContent = error.message;
    } finally { if (target === detail && token === diffSerial) refresh.disabled = false; }
  }

  function showDisplay() {
    const isDiff = detail?.template_kind && display.value === "diff";
    full.hidden = Boolean(isDiff); diff.hidden = !isDiff; refresh.hidden = !isDiff;
    if (isDiff) loadDiff(); else { paint(); requestAnimationFrame(syncScroll); }
  }

  function changed() {
    if (!detail?.template_kind) return;
    revision++; serial++; analysis = null; paint(); clearTimeout(timer);
    showDiagnostics([], "Checking edited structure and view tags…");
    if (!composing) timer = setTimeout(analyze, 300);
  }
  text.addEventListener("input", changed);
  text.addEventListener("compositionstart", () => { composing = true; clearTimeout(timer); });
  text.addEventListener("compositionend", () => { composing = false; changed(); });
  text.addEventListener("scroll", syncScroll);
  new ResizeObserver(syncScroll).observe(text);
  view.addEventListener("change", paint);
  search.addEventListener("input", () => { paint(); if (display.value === "diff") paintDiff(); });
  display.addEventListener("change", showDisplay);
  refresh.addEventListener("click", loadDiff);

  window.ZetTemplateEditor = {
    load(value, send) {
      detail = value; request = send; revision++; serial++; diffSerial++; clearTimeout(timer);
      analysis = value; diffResult = null; view.replaceChildren(new Option("Off", ""));
      for (const name of value.views || []) view.add(new Option(name.toLowerCase().replaceAll("_", " ").replace("3 4", "¾"), name));
      view.value = ""; search.value = ""; display.value = "full";
      const specialized = Boolean(value.template_kind);
      controls.hidden = !specialized; decoration.hidden = !specialized;
      byId("template-editor-help").hidden = !specialized;
      byId("source-editor-legacy-help").hidden = specialized;
      diagnostics.hidden = !specialized; full.classList.toggle("template-editor-decorated", specialized);
      showDiagnostics(value.diagnostics); showDisplay();
      text.scrollTop = 0;
      if (specialized && value.start_line) requestAnimationFrame(() => focusLine(value.start_line));
    },
    saved(value) {
      if (!detail?.template_kind) return;
      detail.master_revision = value.master_revision;
      if (display.value === "diff") loadDiff();
      analyze();
    },
    invalid(value) {
      if (value.line_views) analysis = value;
      paint(); showDiagnostics(value.diagnostics, value.message);
      requestAnimationFrame(() => diagnostics.scrollIntoView({block: "center"}));
    },
  };
})();
