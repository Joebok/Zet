/* Local template versions and explicit cross-view references. */
(() => {
  const host = document.getElementById("local-template-improvement");
  const decisionDrafts = new Map();
  const editors = new Map();
  let context = null, data = null, loading = false, lastFetch = 0, serial = 0, selectedRevision = "", signature = "", mutation = 0;
  let direction, model, sourceChoices, history, result, message, active, workflowStatus, frontButton;
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
    const writes = options.method && options.method !== "GET";
    if (writes) mutation++;
    const response = await fetch(url, { ...options, headers: { "Content-Type": "application/json", "X-Zet-Universe": context.universe } });
    const value = await response.json();
    if (writes) mutation++;
    if (!response.ok) throw new Error(value.detail || "Template action failed.");
    return value;
  }
  function status(text, error = false) { message.textContent = text; message.classList.toggle("error", error); }
  function button(parent, text, action) {
    const control = el("button", text); control.type = "button";
    control.addEventListener("click", async () => {
      const current = serial; control.disabled = true;
      try { await action(); } catch (error) { if (current === serial) status(error.message, true); }
      finally { if (current === serial) { if (control === frontButton) updateFrontButton(); else control.disabled = false; } }
    });
    parent.append(control); return control;
  }
  function field(parent, title, control) { const label = el("label", title); label.append(control); parent.append(label); return control; }
  const chosenSources = () => [...sourceChoices.querySelectorAll("input:checked")].map(input => input.value);
  async function analyze(fromMaster = false) {
    const initial = serial, source_ids = chosenSources();
    if (!source_ids.length) throw new Error("Choose at least one source template to edit.");
    const value = await request(endpoint(), { method: "POST", body: JSON.stringify({
      direction: direction.value, model: model.value, source_ids, from_master: fromMaster,
      parent_revision_id: !fromMaster && data?.revision?.status === "READY" ? data.revision.revision_id : undefined }) });
    if (serial !== initial) return;
    selectedRevision = value.revision.revision_id; data = value; signature = ""; renderData(); await context.reload();
    status(fromMaster ? "Restarted from current masters; earlier versions remain in history." : "Text analysis started. You can leave this page while it runs.");
  }
  function updateWorkflowStatus() {
    if (!workflowStatus || !data) return;
    workflowStatus.replaceChildren(el("h3", "Template status"));
    const revision = data.revision, activeId = data.active_revision_id;
    const notes = [];
    if (!data.accepted_revision_id && context.run.character_progression) notes.push("Review required: accept a version or skip improvement before starting FRONT.");
    if (activeId) {
      notes.push(`New renders use batch version ${activeId.slice(0, 8)}.${data.active_revision.review_skipped ? " Improvement was skipped." : ""} ${data.active_revision.differs_from_master ? "Its templates differ from current masters; those differences are batch-only." : "Its frozen templates match current masters."}`);
    } else notes.push("New renders use current master templates once the review gate is complete.");
    if (revision) {
      const sources = new Map(data.sources.map(source => [source.source_id, source.text]));
      const pending = revision.sources.filter(source => source.text !== sources.get(source.source_id));
      const drift = revision.sources.some(source => source.master_text !== sources.get(source.source_id) && source.text !== sources.get(source.source_id));
      if (revision.status === "REVIEW_READY") {
        const count = (decisionDrafts.get(revision.revision_id) || revision.selected_ids || []).length;
        notes.push(revision.accepted_revision_id ? `This review was accepted as version ${revision.accepted_revision_id.slice(0, 8)}.`
          : `${count} of ${revision.findings.length} proposed corrections selected; none are applied until you accept.`);
      } else if (revision.status === "READY") {
        notes.push(revision.review_skipped ? "This version compiled current masters without AI analysis." : revision.manual
          ? "Manual proposal saved and compiled." : `${revision.selected_ids?.length || 0} corrections accepted and compiled.`);
        if (revision.revision_id !== activeId) notes.push("This saved proposal is not used for new renders. Choose Use for new renders to apply it to this batch.");
      } else notes.push(`Viewed version: ${revision.status}${revision.error ? ` — ${revision.error}` : ""}.`);
      notes.push(revision.promoted_at ? `Master templates were updated from this version (${revision.promoted_at}). ${pending.length ? "Current masters have since changed." : "Current masters match this proposal."}`
        : pending.length ? `${pending.length} template(s) in this proposal differ from current masters. Master updates have not been applied from this version.`
          : "Current masters match this proposal; no master update is pending.");
      if (drift) notes.push("Masters changed since this baseline. Restart from current masters to incorporate those edits before accepting or promoting.");
    }
    const unsaved = [...editors.values()].filter(editor => editor.contextKey === context.key && !editor.window.closed && editor.dirty).length;
    if (unsaved) notes.push(`${unsaved} editor window(s) have unsaved changes. Save proposed to compile them and update the diff.`);
    for (const note of notes) workflowStatus.append(el("p", note));
  }
  function updateFrontButton() {
    if (!frontButton) return;
    const control = context.frontControl?.();
    frontButton.disabled = !control || control.disabled;
    frontButton.title = control?.reason || "FRONT has already started.";
  }
  function appendStatusAndFront(revision) {
    workflowStatus = el("section", "", "template-workflow-status"); workflowStatus.setAttribute("aria-live", "polite");
    result.append(workflowStatus); updateWorkflowStatus();
    if (revision?.compiled_views?.length) {
      const compiled = el("details"); compiled.append(el("summary", "Compiled prompts for this version"));
      for (const view of revision.compiled_views) { const details = el("details"); details.append(el("summary", view.view), el("pre", view.prompt)); compiled.append(details); }
      result.append(compiled);
    }
    const actions = el("div", "", "button-row"); result.append(actions);
    frontButton = button(actions, "Start Front Renders", async () => {
      const control = context.frontControl?.();
      if (!control || control.disabled) throw new Error(control?.reason || "FRONT is not ready to start.");
      await control.start(); updateFrontButton();
    });
    frontButton.classList.add("primary-action");
    if (context.pipeline === "costume-dressing") frontButton.hidden = true;
    updateFrontButton();
  }
  function openEditor(source, revision) {
    let key = `${context.key}:${revision.revision_id}:${source.source_id}`;
    const existing = editors.get(key);
    if (existing && !existing.window.closed) { existing.window.focus(); return; }
    const popup = window.open("", "_blank", "popup,width=1100,height=850,resizable=yes,scrollbars=yes");
    if (!popup) throw new Error("Allow pop-up windows for Zet, then open the template editor again.");
    const initial = serial, doc = popup.document;
    doc.title = `Edit master template proposal · ${source.label || source.source_id}`;
    doc.documentElement.lang = "en";
    const style = doc.createElement("link"); style.rel = "stylesheet";
    style.href = document.querySelector('link[href*="/static/zet.css"]')?.href || new URL("/static/zet.css", location.origin).href; doc.head.append(style);
    doc.body.className = "template-proposal-window";
    const title = el("h1", "Edit master template"), identity = el("p", source.source_id, "muted");
    const note = el("p", "Edit the proposed template below. Save proposed compiles a new version and updates the dashboard diff. Updating master templates is a separate action on the dashboard.");
    const text = el("textarea"); text.value = source.text; text.spellcheck = false; text.setAttribute("aria-label", "Proposed template");
    const editor = { window: popup, dirty: false, contextKey: context.key }; editors.set(key, editor);
    const feedback = el("p", "No unsaved changes.", "action-message"); feedback.setAttribute("role", "status");
    const actions = el("div", "", "button-row");
    button(actions, "Save proposed", async () => {
      save.disabled = true;
      try {
        if (initial !== serial || data?.revision?.revision_id !== revision.revision_id) throw new Error("The batch or viewed version changed. Keep your text here and reopen the current proposal to save against it.");
        if (text.value === source.text) throw new Error("Edit the template before saving a proposal.");
        const proposed = text.value;
        feedback.textContent = "Compiling proposed template…";
        const value = await request(endpoint(), { method: "POST", body: JSON.stringify({ parent_revision_id: revision.revision_id,
          direction: direction.value || "Manual template revision", replacements: { [source.source_id]: proposed }, source_ids: [source.source_id] }) });
        if (initial !== serial) throw new Error("Proposal saved to the original batch. Return to that batch to review it.");
        data = value; selectedRevision = value.revision.revision_id; signature = "";
        revision = value.revision; source = revision.sources.find(item => item.source_id === source.source_id);
        editor.dirty = text.value !== source.text;
        editors.delete(key); key = `${context.key}:${revision.revision_id}:${source.source_id}`; editors.set(key, editor);
        renderData(); await context.reload();
        feedback.textContent = `Proposed version saved and compiled. The dashboard diff is updated; master templates have not been changed.${editor.dirty ? " Further edits in this window are still unsaved." : ""}`;
        status(feedback.textContent);
      } catch (error) { feedback.textContent = error.message; }
      finally { save.disabled = false; updateWorkflowStatus(); }
    });
    const save = actions.lastElementChild;
    button(actions, "Close", () => { popup.close(); });
    text.addEventListener("input", () => { editor.dirty = text.value !== source.text; feedback.textContent = editor.dirty ? "Unsaved changes — Save proposed to update the diff." : "No unsaved changes."; updateWorkflowStatus(); });
    popup.addEventListener("beforeunload", event => { if (editor.dirty) { event.preventDefault(); event.returnValue = ""; } });
    popup.addEventListener("pagehide", () => { editors.delete(key); updateWorkflowStatus(); });
    doc.body.replaceChildren(title, identity, note, text, actions, feedback); popup.focus();
  }
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
    host.append(el("p", "Review the compiled prompts, choose corrections or skip improvement, then start FRONT. Master updates remain a separate choice.", "muted"));
    active = el("p"); host.append(active);
    sourceChoices = el("div", "", "template-source-choices"); host.append(sourceChoices);
    direction = field(host, "Prompt review instructions / refinement feedback", el("textarea", "", "template-review-instructions")); direction.rows = 2; direction.maxLength = 20000;
    model = field(host, "Review model", el("input")); model.type = "text";
    window.ZetModelPicker?.attach(model, { required: ["text"], allowDefault: true });
    const actions = el("div", "", "button-row"); host.append(actions);
    button(actions, "Analyze prompts", () => analyze());
    button(actions, "Restart from current masters", () => analyze(true));
    button(actions, "Skip improvement — use current masters", async () => {
      const initial = serial;
      const value = await request(endpoint(), { method: "POST", body: JSON.stringify({ from_master: true, skip_analysis: true, expected_active: data?.active_revision_id || "" }) });
      if (serial !== initial) return;
      data = value; selectedRevision = value.revision.revision_id; signature = ""; renderData(); await context.reload();
      status("Improvement skipped. Current masters compiled for this batch; FRONT is ready to start.");
    });
    const reload = button(actions, "Reload saved results", refresh);
    reload.title = "Reload saved versions and analysis status. Does not recompile or incorporate master-template edits.";
    host.append(el("p", "Restart recompiles and analyzes current masters, leaving earlier versions in history. Reload saved results only checks saved results and analysis status.", "muted"));
    history = field(host, "Saved versions", el("select"));
    history.addEventListener("change", () => { selectedRevision = history.value; signature = ""; void refresh().catch(error => status(error.message, true)); });
    message = el("p", "", "action-message"); message.setAttribute("role", "status"); host.append(message);
    result = el("section", "", "template-revision-result"); host.append(result);
  }
  function renderData() {
    if (!data) return;
    active.textContent = data.active_revision_id ? `Batch version: ${data.active_revision_id.slice(0, 8)}. New renders use its frozen templates.` : "No batch template version selected.";
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
    const nextSignature = JSON.stringify([revision, data.active_revision_id, data.active_revision, data.accepted_revision_id, data.sources]);
    if (signature === nextSignature) { updateWorkflowStatus(); updateFrontButton(); return; }
    signature = nextSignature; result.replaceChildren(); result.dataset.revision = revision?.revision_id || "";
    if (!revision) { appendStatusAndFront(null); return; }
    if (["PROPOSING", "VALIDATING"].includes(revision.status)) status("Analyzing text; no images are sent.");
    result.append(el("h3", `Version ${revision.revision_id.slice(0, 8)} · ${revision.status}`), el("p", revision.summary || "Preparing proposal…"));
    if (revision.parent_revision_id) result.append(el("p", `Based on ${revision.parent_revision_id.slice(0, 8)}`, "muted"));
    if (revision.error) result.append(el("p", revision.error, "error"));
    if (revision.promotion?.status === "FAILED" || revision.promotion?.status === "APPLYING") result.append(el("p", `Master update ${revision.promotion.status}: ${revision.promotion.error || "interrupted or in progress; review before retrying"}`, "error"));
    if (revision.recommendations) result.append(el("p", revision.recommendations));
    const reviewActions = el("div", "", "button-row");
    if (revision.version === 2 && revision.status === "REVIEW_READY") {
      const findings = el("fieldset"); findings.append(el("legend", "Proposed corrections — check Yes to apply; unchecked means No"));
      let saving = Promise.resolve();
      const chosen = () => [...findings.querySelectorAll("input:checked")].map(input => input.value);
      for (const finding of revision.findings || []) {
        const row = el("section", "", "template-correction");
        const label = el("label", "", "template-correction-choice"); const check = el("input"); check.type = "checkbox"; check.value = finding.id;
        check.setAttribute("aria-label", `Apply correction: ${finding.rationale}`);
        check.checked = (decisionDrafts.get(revision.revision_id) || revision.selected_ids || []).includes(finding.id);
        label.append(check);
        const content = el("div", "", "template-correction-content");
        content.append(el("p", finding.rationale), el("p", `${finding.source_id} · ${finding.views.join(", ")}`, "muted"),
          el("p", "Before"), el("pre", finding.before), el("p", "After"), el("pre", finding.after));
        row.append(label, content);
        check.addEventListener("change", () => {
          const selected_ids = chosen();
          decisionDrafts.set(revision.revision_id, selected_ids);
          updateWorkflowStatus();
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
      button(reviewActions, "Accept selected corrections", accept);
      button(reviewActions, "Apply selected and analyze again", async () => {
        const accepted = await accept(); if (!accepted) return;
        const value = await request(endpoint(), { method: "POST", body: JSON.stringify({
          parent_revision_id: accepted.revision.revision_id, direction: direction.value, model: model.value,
          source_ids: [...sourceChoices.querySelectorAll("input:checked")].map(input => input.value) }) });
        data = value; selectedRevision = value.revision.revision_id; signature = ""; renderData(); await context.reload();
      });
      result.append(reviewActions);
    }
    const switchVersion = async id => {
      const initial = serial;
      const value = await request(endpoint("/activate"), { method: "POST", body: JSON.stringify({ revision_id: id, expected_active: data.active_revision_id }) });
      if (initial !== serial) return;
      data = value; signature = ""; renderData(); await context.reload(); status(id ? "Trial version active. Generate or regenerate an individual image to try it." : "Current master templates restored for new renders.");
    };
    const toolbar = el("div", "", "button-row");
    const tryButton = button(toolbar, "Use for new renders", () => switchVersion(revision.revision_id));
    tryButton.disabled = revision.status !== "READY" || (revision.revision_id === data.active_revision_id && !context.run.progression?.prompt_review_required);

    const changed = revision.sources.filter(source => source.text !== source.master_text);
    const promote = button(toolbar, "Update master templates…", async () => {
      if (!window.confirm(`Update these master templates with version ${revision.revision_id.slice(0, 8)}?\n\n${changed.map(source => source.source_id).join("\n")}\n\nThis affects future compilations in other batches. Original text remains in the saved version.`)) return;
      const initial = serial;
      const value = await request(endpoint(`/${revision.revision_id}/promote`), { method: "POST", body: JSON.stringify({ confirm: true }) });
      if (initial !== serial) return;
      data = value; signature = ""; renderData(); await context.reload(); status("Master templates updated. Existing images and queued renders retain their saved inputs.");
    });
    promote.disabled = revision.status !== "READY" || !changed.length || revision.sources.every(source => data.sources.some(master => master.source_id === source.source_id && master.text === source.text));
    for (const source of revision.sources) {
      if (!revision.source_ids.includes(source.source_id) && !source.master_diff) continue;
      const details = el("details"); details.open = Boolean(source.master_diff); details.append(el("summary", source.source_id));
      if (source.rationale) details.append(el("p", source.rationale));
      details.append(sourceDiff(source));
      const edit = button(details, "Edit master template", () => openEditor(source, revision));
      edit.disabled = !["READY", "REVIEW_READY", "FAILED"].includes(revision.status);
      result.append(details);
    }
    result.append(toolbar);
    appendStatusAndFront(revision);

  }
  async function refresh() {
    if (!context || loading || !host.open) return;
    const initial = serial, url = endpoint(), startedMutation = mutation, startedRevision = selectedRevision; loading = true;
    try {
      const parsed = new URL(url, window.location.origin); if (selectedRevision) parsed.searchParams.set("revision_id", selectedRevision);
      const value = await request(parsed.pathname + parsed.search);
      if (serial !== initial || startedMutation !== mutation || startedRevision !== selectedRevision) return;
      data = value; renderData();
    } finally { if (serial === initial) { loading = false; lastFetch = Date.now(); } }
  }
  function update(run, pipeline, reload, frontControl) {
    const universe = document.querySelector("#universe-select").value;
    const key = `${universe}:${pipeline}:${run?.run_id || ""}`;
    host.hidden = !run || pipeline === "character-assembly";
    if (pipeline === "character-assembly") {
      serial++; context = null; loading = false; data = null; host.open = false; host.replaceChildren();
      return;
    }
    if (context?.key !== key) {
      serial++; loading = false; lastFetch = 0; data = null; selectedRevision = ""; signature = "";
      context = { key, run, pipeline, reload, universe, frontControl }; build();
    } else context = { ...context, run, reload, frontControl };
    updateWorkflowStatus(); updateFrontButton();
    if (run?.progression?.prompt_review_required) host.open = true;
    if (run && host.open && Date.now() - lastFetch > 1500) void refresh().catch(error => status(error.message, true));
  }
  host.addEventListener("toggle", () => { if (host.open) void refresh().catch(error => status(error.message, true)); });
  window.ZetTemplateImprovement = { update };
})();
