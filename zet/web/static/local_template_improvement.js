/* Local template versions and explicit cross-view references. */
(() => {
  const host = document.getElementById("local-template-improvement");
  let context = null, data = null, loading = false, lastFetch = 0, serial = 0, selectedRevision = "", signature = "";
  let direction, model, representatives, sourceChoices, history, result, message, active, proposalButton;
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
  function build() {
    host.replaceChildren();
    const summary = el("summary", "Improve governing templates"); host.append(summary);
    host.append(el("p", "Choose one representative per view and describe the changes. Proposals are saved as versions; try a version with individual Generate / Regen before updating master templates.", "muted"));
    active = el("p"); host.append(active);
    representatives = el("div", "", "template-representatives"); host.append(representatives);
    sourceChoices = el("div", "", "template-source-choices"); host.append(sourceChoices);
    direction = field(host, "Targeted changes and consistency goals", el("textarea")); direction.rows = 4; direction.maxLength = 20000;
    model = field(host, "Review model", el("input")); model.type = "text";
    window.ZetModelPicker?.attach(model, { required: ["vision"], allowDefault: true });
    const actions = el("div", "", "button-row"); host.append(actions);
    proposalButton = button(actions, "Propose template revision", async () => {
      // Save visible observations first, including edits made since the last view save.
      const initial = serial, captured = context;
      for (const input of document.querySelectorAll("#local-pipeline-views textarea[data-view-observations]")) {
        const view = input.dataset.viewObservations;
        if (input.value === (captured.run.view_reviews?.[view]?.observations || "")) continue;
        const params = captured.pipeline === "costume-dressing" ? `?costume=${encodeURIComponent(captured.run.costume || "")}` : "";
        await request(`/api/local/${captured.pipeline}/runs/${encodeURIComponent(captured.run.run_id)}/views/${encodeURIComponent(view)}/observations${params}`,
          { method: "PUT", body: JSON.stringify({ observations: input.value }) });
        if (serial !== initial) return;
      }
      const source_ids = [...sourceChoices.querySelectorAll("input:checked")].map(input => input.value);
      if (!source_ids.length) throw new Error("Choose at least one source template to edit.");
      const payload = { direction: direction.value, model: model.value, source_ids,
        representatives: Object.fromEntries([...representatives.querySelectorAll("select")].map(select => [select.dataset.view, select.value])) };
      const value = await request(endpoint(), { method: "POST", body: JSON.stringify(payload) });
      if (serial !== initial) return;
      selectedRevision = value.revision.revision_id; data = value; signature = ""; renderData(); status("Proposal saved. You can leave this page while it runs.");
    });
    button(actions, "Refresh revisions", refresh);
    history = field(host, "Saved versions", el("select"));
    history.addEventListener("change", () => { selectedRevision = history.value; signature = ""; void refresh().catch(error => status(error.message, true)); });
    message = el("p", "", "action-message"); message.setAttribute("role", "status"); host.append(message);
    result = el("section", "", "template-revision-result"); host.append(result);
  }
  function renderRepresentatives() {
    const saved = Object.fromEntries([...representatives.querySelectorAll("select")].map(select => [select.dataset.view, select.value]));
    representatives.replaceChildren(el("h3", "Representative images"));
    for (const view of context.run.views || []) {
      const row = el("div", "", "template-representative");
      const select = el("select"); select.dataset.view = view;
      const auto = data.representatives.find(item => item.view === view);
      select.add(new Option(auto ? `Automatic: ${auto.candidate_id} (${auto.reason})` : "Automatic: no selected image or current Luna #1", ""));
      select.add(new Option("Exclude this view", "skip"));
      for (const candidate of context.run.candidates || []) {
        if (candidate.view === view && candidate.image_path && candidate.human_review?.decision !== "reject") select.add(new Option(candidate.candidate_id, candidate.candidate_id));
      }
      field(row, view.replaceAll("_", " "), select);
      if ([...select.options].some(option => option.value === saved[view])) select.value = saved[view];
      const image = el("img"); image.alt = `${view} representative`; image.loading = "lazy";
      const updateImage = () => {
        const cid = select.value === "skip" ? "" : select.value || auto?.candidate_id;
        image.hidden = !cid;
        if (cid) {
          const params = new URLSearchParams({ universe_id: context.universe });
          if (context.pipeline === "costume-dressing") params.set("costume", context.run.costume || "");
          image.src = `/api/local/${context.pipeline}/runs/${encodeURIComponent(context.run.run_id)}/images/${encodeURIComponent(cid)}?${params}`;
        }
      };
      select.addEventListener("change", updateImage); updateImage(); row.append(image); representatives.append(row);
    }
  }
  function renderData() {
    if (!data) return;
    active.textContent = data.active_revision_id ? `Trial version: ${data.active_revision_id.slice(0, 8)}. New individual renders use its templates.` : "New renders use current master templates.";
    if (!sourceChoices.childElementCount) {
      sourceChoices.append(el("h3", "Templates the proposal may change"));
      data.sources.forEach((source, index) => {
        const check = el("input"); check.type = "checkbox"; check.value = source.source_id; check.checked = index === 0;
        const label = el("label"); label.append(check, document.createTextNode(source.source_id)); sourceChoices.append(label);
      });
    }
    const repsSignature = JSON.stringify([data.representatives, (context.run.candidates || []).map(c => [c.candidate_id, c.image_path, c.human_review?.decision])]);
    if (representatives.dataset.signature !== repsSignature && !representatives.contains(document.activeElement)) {
      renderRepresentatives(); representatives.dataset.signature = repsSignature;
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
    result.append(el("h3", `Version ${revision.revision_id.slice(0, 8)} · ${revision.status}`), el("p", revision.summary || "Preparing proposal…"));
    if (revision.parent_revision_id) result.append(el("p", `Based on ${revision.parent_revision_id.slice(0, 8)}`, "muted"));
    if (revision.error) result.append(el("p", revision.error, "error"));
    if (revision.promotion?.status === "FAILED" || revision.promotion?.status === "APPLYING") result.append(el("p", `Master update ${revision.promotion.status}: ${revision.promotion.error || "interrupted or in progress; review before retrying"}`, "error"));
    if (revision.recommendations) result.append(el("p", revision.recommendations));
    const toolbar = el("div", "", "button-row"); result.append(toolbar);
    const switchVersion = async id => {
      const initial = serial;
      const value = await request(endpoint("/activate"), { method: "POST", body: JSON.stringify({ revision_id: id, expected_active: data.active_revision_id }) });
      if (initial !== serial) return;
      data = value; signature = ""; renderData(); await context.reload(); status(id ? "Trial version active. Generate or regenerate an individual image to try it." : "Current master templates restored for new renders.");
    };
    const tryButton = button(toolbar, "Use for new renders", () => switchVersion(revision.revision_id));
    tryButton.disabled = revision.status !== "READY" || revision.revision_id === data.active_revision_id;
    const masters = button(toolbar, "Use current masters", () => switchVersion("")); masters.disabled = !data.active_revision_id;
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
      details.append(el("pre", source.master_diff || "No changes from master", "template-diff"));
      if (source.diff && source.diff !== source.master_diff) {
        const step = el("details"); step.append(el("summary", "Changes from parent version"), el("pre", source.diff, "template-diff")); details.append(step);
      }
      const pair = el("div", "", "template-source-pair");
      field(pair, "Master", el("pre", source.master_text));
      const edit = field(pair, "Proposed (editable; saves a new version)", el("textarea")); edit.value = source.text; edit.rows = 16; edit.dataset.sourceId = source.source_id;
      edit.addEventListener("input", () => { edit.dataset.dirty = String(edit.value !== source.text); });
      details.append(pair); result.append(details);
    }
    button(result, "Save edited version", async () => {
      const replacements = Object.fromEntries([...result.querySelectorAll("textarea[data-source-id]")].filter(edit => edit.dataset.dirty === "true").map(edit => [edit.dataset.sourceId, edit.value]));
      if (!Object.keys(replacements).length) throw new Error("Edit a proposed template before saving a new version.");
      const initial = serial;
      const value = await request(endpoint(), { method: "POST", body: JSON.stringify({ parent_revision_id: revision.revision_id,
        direction: direction.value || "Manual template revision", replacements, source_ids: Object.keys(replacements),
        representatives: Object.fromEntries(revision.representatives.map(item => [item.view, item.candidate_id])) }) });
      if (initial !== serial) return;
      selectedRevision = value.revision.revision_id; data = value; signature = ""; result.replaceChildren(); renderData(); status("Edited version saved; checking compilation.");
    });
    if (revision.compiled_views?.length) {
      const compiled = el("details"); compiled.append(el("summary", "Compiled prompts for this version"));
      for (const view of revision.compiled_views) { const details = el("details"); details.append(el("summary", view.view), el("pre", view.prompt)); compiled.append(details); }
      result.append(compiled);
    }
    const evidence = el("details"); evidence.append(el("summary", "Saved evidence and direction"), el("p", revision.direction),
      el("p", revision.representatives.map(item => `${item.view}: ${item.candidate_id} (${item.reason})`).join(" · ")),
      el("pre", JSON.stringify(revision.observations, null, 2))); result.append(evidence);
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
    if (run && host.open && Date.now() - lastFetch > 1500) void refresh().catch(error => status(error.message, true));
  }
  host.addEventListener("toggle", () => { if (host.open) void refresh().catch(error => status(error.message, true)); });
  window.ZetTemplateImprovement = { update };
})();
