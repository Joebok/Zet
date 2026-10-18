/* Local template versions and explicit cross-view references. */
(() => {
  const host = document.getElementById("local-template-improvement");
  const decisionDrafts = new Map();
  let context = null, data = null, loading = false, lastFetch = 0, serial = 0, selectedRevision = "", signature = "";
  let direction, model, sourceChoices, history, result, message, active, proposalButton;
  const el = (tag, text = "", cls = "") => {
    const item = document.createElement(tag); item.textContent = text;
    if (cls) item.className = cls;
    return item;
  };
  function endpoint(suffix = "") {
    const params = new URLSearchParams();
    if (context.pipeline === "costume-dressing") params.set("costume", context.run.costume || "");
    return `/api/local/${context.pipeline}/runs/${encodeURIComponent(context.run.run_id)}/template-revisions${suffix}${params.size ? `?${params}` : ""}`;
  }
  async function request(url, options = {}) {
    const response = await fetch(url, { ...options, headers: { "Content-Type": "application/json", "X-Zet-Universe": context.universe } });
    const value = await response.json();
    if (!response.ok) throw new Error(value.detail || "Template action failed.");
    return value;
  }
  function status(text, error = false) { message.textContent = text; message.classList.toggle("error", error); }
  function button(parent, text, action) {
    const control = el("button", text); control.type = "button";
    control.addEventListener("click", async () => {
      const current = serial; control.disabled = true;
      try { await action(); } catch (error) { if (current === serial) status(error.message, true); }
      finally { if (current === serial) control.disabled = false; }
    });
    parent.append(control); return control;
  }
  function field(parent, title, control) { const label = el("label", title); label.append(control); parent.append(label); return control; }
  function sourceDiff(source) {
    const section = el("section", "", "template-master-diff");
    section.setAttribute("aria-label", "Master versus proposed template diff");
    section.append(el("h4", "Master → Proposed"),
      el("p", "Master is the baseline captured for this version. Red / − removes text; green / + adds text.", "muted"));
    const rows = source.master_diff_rows;
    if (!rows) { section.append(el("pre", source.master_diff || "No changes from master", "template-diff")); return section; }
    if (!rows.length) { section.append(el("p", "No changes from master.")); return section; }
    const table = el("table", "", "template-diff-table");
    table.append(el("caption", "Changes from master to the saved proposed template"));
    const columns = el("colgroup");
    for (const cls of ["template-diff-number", "template-diff-text", "template-diff-number", "template-diff-text"]) columns.append(el("col", "", cls));
    table.append(columns);
    const head = el("thead"), headings = el("tr");
    for (const label of ["Master baseline", "Proposed"]) { const cell = el("th", label); cell.colSpan = 2; cell.scope = "colgroup"; headings.append(cell); }
    head.append(headings); table.append(head);
    const body = el("tbody");
    for (const row of rows) {
      const line = el("tr");
      if (row.kind === "gap") { const gap = el("td", "⋯ unchanged lines ⋯", "template-diff-gap"); gap.colSpan = 4; line.append(gap); }
      else for (const side of ["master", "proposed"]) {
        const number = row[`${side}_line`];
        const changed = row.kind !== "equal" && number != null;
        const cls = changed ? side === "master" ? "template-diff-removed" : "template-diff-added" : "";
        const gutter = el("td", number == null ? "" : String(number), `template-diff-line-number ${cls}`);
        const code = el("td", "", `template-diff-code ${cls}`);
        if (number != null) {
          const sign = el("span", changed ? side === "master" ? "− " : "+ " : "  ", "template-diff-sign");
          code.append(sign, document.createTextNode(row[`${side}_text`]));
        } else code.classList.add("template-diff-empty");
        line.append(gutter, code);
      }
      body.append(line);
    }
    table.append(body); section.append(table); return section;
  }
  function build() {
    host.replaceChildren();
    const summary = el("summary", "Improve governing templates"); host.append(summary);
    host.append(el("p", "Review all eight compiled view prompts without images. Choose corrections, accept the batch version, then Continue to generate the next stage. Master updates remain separate.", "muted"));
    active = el("p"); host.append(active);
    sourceChoices = el("div", "", "template-source-choices"); host.append(sourceChoices);
    direction = field(host, "Prompt review instructions / refinement feedback", el("textarea")); direction.rows = 4; direction.maxLength = 20000;
    model = field(host, "Review model", el("input")); model.type = "text";
    window.ZetModelPicker?.attach(model, { required: ["text"], allowDefault: true });
    const actions = el("div", "", "button-row"); host.append(actions);
    proposalButton = button(actions, "Analyze prompts", async () => {
      const initial = serial;
      const source_ids = [...sourceChoices.querySelectorAll("input:checked")].map(input => input.value);
      if (!source_ids.length) throw new Error("Choose at least one source template to edit.");
      const payload = { direction: direction.value, model: model.value, source_ids,
        parent_revision_id: data?.revision?.status === "READY" ? data.revision.revision_id : data?.active_revision_id || undefined };
      const value = await request(endpoint(), { method: "POST", body: JSON.stringify(payload) });
      if (serial !== initial) return;
      selectedRevision = value.revision.revision_id; data = value; signature = ""; renderData(); await context.reload(); status("Text analysis started. You can leave this page while it runs.");
    });
    button(actions, "Refresh revisions", refresh);
    history = field(host, "Saved versions", el("select"));
    history.addEventListener("change", () => { selectedRevision = history.value; signature = ""; void refresh().catch(error => status(error.message, true)); });
    message = el("p", "", "action-message"); message.setAttribute("role", "status"); host.append(message);
    result = el("section", "", "template-revision-result"); host.append(result);
  }
  function renderData() {
    if (!data) return;
    active.textContent = data.active_revision_id ? `Trial version: ${data.active_revision_id.slice(0, 8)}. New renders use its frozen templates.` : "New renders use current master templates.";
    if (!sourceChoices.childElementCount) {
      sourceChoices.append(el("h3", "Templates the proposal may change"));
      data.sources.forEach((source, index) => {
        const check = el("input"); check.type = "checkbox"; check.value = source.source_id; check.checked = true;
        const label = el("label"); label.append(check, document.createTextNode(source.source_id)); sourceChoices.append(label);
      });
    }
    history.replaceChildren(new Option("Latest version", ""));
    for (const item of data.history) history.add(new Option(`${item.revision_id.slice(0, 8)} · ${item.status}${item.promoted_at ? " · promoted" : ""}`, item.revision_id));
    history.value = selectedRevision;
    const revision = data.revision;
    const nextSignature = JSON.stringify([revision, data.active_revision_id]);
    if (signature === nextSignature) return;
    // Never replace a manually edited source while background polling runs.
    if (result.querySelector("textarea[data-dirty='true']") && result.dataset.revision === revision?.revision_id) return;
    signature = nextSignature; result.replaceChildren(); result.dataset.revision = revision?.revision_id || "";
    if (!revision) return;
    if (["PROPOSING", "VALIDATING"].includes(revision.status)) status("Analyzing text; no images are sent.");
    result.append(el("h3", `Version ${revision.revision_id.slice(0, 8)} · ${revision.status}`), el("p", revision.summary || "Preparing proposal…"));
    if (revision.parent_revision_id) result.append(el("p", `Based on ${revision.parent_revision_id.slice(0, 8)}`, "muted"));
    if (revision.error) result.append(el("p", revision.error, "error"));
    if (revision.promotion?.status === "FAILED" || revision.promotion?.status === "APPLYING") result.append(el("p", `Master update ${revision.promotion.status}: ${revision.promotion.error || "interrupted or in progress; review before retrying"}`, "error"));
    if (revision.recommendations) result.append(el("p", revision.recommendations));
    const toolbar = el("div", "", "button-row"); result.append(toolbar);
    if (revision.version === 2 && revision.status === "REVIEW_READY") {
      const findings = el("fieldset"); findings.append(el("legend", "Proposed corrections — check Yes to apply; unchecked means No"));
      let saving = Promise.resolve();
      const chosen = () => [...findings.querySelectorAll("input:checked")].map(input => input.value);
      for (const finding of revision.findings || []) {
        const row = el("section", "", "template-correction");
        const label = el("label"); const check = el("input"); check.type = "checkbox"; check.value = finding.id;
        check.checked = (decisionDrafts.get(revision.revision_id) || revision.selected_ids || []).includes(finding.id);
        label.append(check, document.createTextNode(`Yes — ${finding.rationale}`));
        row.append(label, el("p", `${finding.source_id} · ${finding.views.join(", ")}`, "muted"),
          el("p", "Before"), el("pre", finding.before), el("p", "After"), el("pre", finding.after));
        check.addEventListener("change", () => {
          const selected_ids = chosen();
          decisionDrafts.set(revision.revision_id, selected_ids);
          saving = saving.catch(() => {}).then(() => request(endpoint(`/${revision.revision_id}/decisions`),
            { method: "PUT", body: JSON.stringify({ selected_ids }) }));
          void saving.catch(error => status(error.message, true));
        });
        findings.append(row);
      }
      if (!revision.findings.length) findings.append(el("p", "No corrections proposed. You can accept this version."));
      result.append(findings);
      const accept = async () => {
        await saving;
        const initial = serial;
        const value = await request(endpoint(`/${revision.revision_id}/accept`),
          { method: "POST", body: JSON.stringify({ selected_ids: chosen() }) });
        if (serial !== initial) return;
        data = value; selectedRevision = value.revision.revision_id; signature = "";
        renderData(); await context.reload(); status("Prompt version accepted. Use Continue when ready to generate.");
        return value;
      };
      button(toolbar, "Accept selected corrections", accept);
      button(toolbar, "Apply selected and analyze again", async () => {
        const accepted = await accept(); if (!accepted) return;
        const value = await request(endpoint(), { method: "POST", body: JSON.stringify({
          parent_revision_id: accepted.revision.revision_id, direction: direction.value, model: model.value,
          source_ids: [...sourceChoices.querySelectorAll("input:checked")].map(input => input.value) }) });
        data = value; selectedRevision = value.revision.revision_id; signature = ""; renderData(); await context.reload();
      });
    }
    const switchVersion = async id => {
      const initial = serial;
      const value = await request(endpoint("/activate"), { method: "POST", body: JSON.stringify({ revision_id: id, expected_active: data.active_revision_id }) });
      if (initial !== serial) return;
      data = value; signature = ""; renderData(); await context.reload(); status(id ? "Trial version active. Generate or regenerate an individual image to try it." : "Current master templates restored for new renders.");
    };
    const tryButton = button(toolbar, "Use for new renders", () => switchVersion(revision.revision_id));
    tryButton.disabled = revision.status !== "READY" || (revision.revision_id === data.active_revision_id && !context.run.progression?.prompt_review_required);

    const changed = revision.sources.filter(source => source.text !== source.master_text);
    const promote = button(toolbar, "Update master templates…", async () => {
      if (!window.confirm(`Update these master templates with version ${revision.revision_id.slice(0, 8)}?\n\n${changed.map(source => source.source_id).join("\n")}\n\nThis affects future compilations in other batches. Original text remains in the saved version.`)) return;
      const initial = serial;
      const value = await request(endpoint(`/${revision.revision_id}/promote`), { method: "POST", body: JSON.stringify({ confirm: true }) });
      if (initial !== serial) return;
      data = value; signature = ""; renderData(); status("Master templates updated. Existing images and queued renders retain their saved inputs.");
    });
    promote.disabled = revision.status !== "READY" || !changed.length;
    for (const source of revision.sources) {
      if (!revision.source_ids.includes(source.source_id) && !source.master_diff) continue;
      const details = el("details"); details.open = Boolean(source.master_diff); details.append(el("summary", source.source_id));
      if (source.rationale) details.append(el("p", source.rationale));
      details.append(sourceDiff(source));
      if (source.diff && source.diff !== source.master_diff) {
        const step = el("details"); step.append(el("summary", "Changes from parent version"), el("pre", source.diff, "template-diff")); details.append(step);
      }
      const editor = el("details"); editor.append(el("summary", "Full templates / edit proposal"));
      const pair = el("div", "", "template-source-pair");
      field(pair, "Master baseline", el("pre", source.master_text));
      const edit = field(pair, "Proposed (editable; saves a new version)", el("textarea")); edit.value = source.text; edit.rows = 16; edit.dataset.sourceId = source.source_id;
      const dirtyNote = el("p", "Unsaved edits: save a new version to update the diff.", "muted"); dirtyNote.hidden = true;
      edit.addEventListener("input", () => { edit.dataset.dirty = String(edit.value !== source.text); dirtyNote.hidden = edit.dataset.dirty !== "true"; });
      editor.append(pair, dirtyNote); details.append(editor); result.append(details);
    }
    button(result, "Save edited version", async () => {
      const replacements = Object.fromEntries([...result.querySelectorAll("textarea[data-source-id]")].filter(edit => edit.dataset.dirty === "true").map(edit => [edit.dataset.sourceId, edit.value]));
      if (!Object.keys(replacements).length) throw new Error("Edit a proposed template before saving a new version.");
      const initial = serial;
      const value = await request(endpoint(), { method: "POST", body: JSON.stringify({ parent_revision_id: revision.revision_id,
        direction: direction.value || "Manual template revision", replacements, source_ids: Object.keys(replacements) }) });
      if (initial !== serial) return;
      selectedRevision = value.revision.revision_id; data = value; signature = ""; result.replaceChildren(); renderData(); status("Edited version saved; checking compilation.");
    });
    if (revision.compiled_views?.length) {
      const compiled = el("details"); compiled.append(el("summary", "Compiled prompts for this version"));
      for (const view of revision.compiled_views) { const details = el("details"); details.append(el("summary", view.view), el("pre", view.prompt)); compiled.append(details); }
      result.append(compiled);
    }

  }
  async function refresh() {
    if (!context || loading || !host.open) return;
    const initial = serial, url = endpoint(); loading = true;
    try {
      const parsed = new URL(url, window.location.origin); if (selectedRevision) parsed.searchParams.set("revision_id", selectedRevision);
      const value = await request(parsed.pathname + parsed.search);
      if (serial !== initial) return;
      data = value; renderData();
    } finally { if (serial === initial) { loading = false; lastFetch = Date.now(); } }
  }
  function update(run, pipeline, reload) {
    const universe = document.querySelector("#universe-select").value;
    const key = `${universe}:${pipeline}:${run?.run_id || ""}`;
    host.hidden = !run;
    if (context?.key !== key) {
      serial++; loading = false; lastFetch = 0; data = null; selectedRevision = ""; signature = "";
      context = { key, run, pipeline, reload, universe }; build();
    } else context = { ...context, run, reload };
    if (run?.progression?.prompt_review_required) host.open = true;
    if (run && host.open && Date.now() - lastFetch > 1500) void refresh().catch(error => status(error.message, true));
  }
  host.addEventListener("toggle", () => { if (host.open) void refresh().catch(error => status(error.message, true)); });
  window.ZetTemplateImprovement = { update };
})();
