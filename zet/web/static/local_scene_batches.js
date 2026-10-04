/* Current scene renders are cultivated in eight stable slots per target. */
window.SceneBatches = (() => {
  const page = document.querySelector("#scene-batches-page");
  const host = document.querySelector("#scene-batch-groups");
  const message = document.querySelector("#scene-batch-message");
  let context = null, run = null, pending = false, timer = null, version = 0;
  const observations = new Map();
  const node = (tag, text, className = "") => {
    const element = document.createElement(tag);
    if (text != null) element.textContent = text;
    if (className) element.className = className;
    return element;
  };
  const base = () => `/api/stories/${encodeURIComponent(context.story)}/scenes/${encodeURIComponent(context.scene)}/local-batches`;
  const route = (target, suffix) => `${base()}/${run.run_id}/targets/${encodeURIComponent(target)}/${suffix}`;
  async function request(url, payload, method = payload === undefined ? "GET" : "POST") {
    const options = payload === undefined ? (method === "GET" ? {} : {method})
      : {method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)};
    const response = await fetch(url, options);
    const value = await response.json();
    if (!response.ok) throw new Error(typeof value.detail === "string" ? value.detail
      : value.detail ? JSON.stringify(value.detail) : "Scene render request failed.");
    return value;
  }
  function link(hostElement, label, href) {
    const anchor = node("a", label); anchor.href = href; anchor.target = "_blank"; anchor.rel = "noopener";
    hostElement.append(anchor);
  }
  function button(hostElement, label, action, payload = {}, disabled = false) {
    const control = node("button", label); control.type = "button"; control.disabled = pending || disabled;
    control.addEventListener("click", () => void perform(action, payload)); hostElement.append(control);
  }
  async function perform(action, payload = {}) {
    if (pending || !run) return;
    const expectedVersion = version, expectedId = run.run_id;
    pending = true;
    message.textContent = `${action.replaceAll("-", " ")}…`;
    render();
    try {
      const updated = await request(`${base()}/${expectedId}/actions/${action}`, payload);
      if (version !== expectedVersion || run?.run_id !== expectedId) return;
      run = updated;
      message.textContent = run.status.replaceAll("_", " "); render();
    } catch (error) { if (version === expectedVersion) message.textContent = error.message; }
    finally { if (version === expectedVersion) { pending = false; render(); scheduleRefresh(); } }
  }
  function render() {
    const expanded = new Set(Array.from(host.querySelectorAll("details[open]")).map(item => item.dataset.target));
    host.replaceChildren();
    const refresh = document.querySelector("#scene-batch-refresh");
    const start = document.querySelector("#scene-batch-start");
    const stop = document.querySelector("#scene-batch-stop");
    const publish = document.querySelector("#scene-batch-publish");
    refresh.disabled = pending || !run;
    start.disabled = pending || !run || !(run.ready_targets || []).length;
    stop.disabled = pending || !run || !Object.values(run.groups).some(group =>
      group.candidates.some(item => ["SUBMITTING", "QUEUED", "RUNNING"].includes(item.status)));
    publish.disabled = pending || run?.status !== "READY_TO_PUBLISH";
    if (!run) return;
    document.querySelector("#scene-batch-status").textContent = run.status.replaceAll("_", " ");
    for (const definition of run.targets) {
      const target = definition.target_id, group = run.groups[target];
      const section = node("section", null, "local-pipeline-view");
      section.append(node("h2", definition.label));
      section.append(node("p", group.status.replaceAll("_", " ")));
      if (group.subject_count != null) {
        section.append(node("p", `Required characters (${group.subject_count}): ${(group.subject_labels || []).join(", ") || "none"}`, "scene-batch-subject-summary"));
      }
      if ((group.reference_assignments || []).length) {
        const assigned = group.reference_assignments.map(item => `${item.label || "Reference"} → ${item.applies_to || "scene"} (${String(item.role || "visual reference").replaceAll("_", " ")})`);
        section.append(node("p", `Identity and reference assignments: ${assigned.join("; ")}`, "scene-batch-subject-summary"));
      }
      if (definition.dependencies.length) section.append(node("p", `Requires selections: ${definition.dependencies.join(", ")}`, "muted"));
      const ready = definition.dependencies.every(dependency => run.selected_views[dependency]);
      const active = group.active_candidates || group.candidates;
      const controls = node("div", null, "button-row compact");
      button(controls, "Render First 4", "render", {target_id: target}, !ready);
      button(controls, "Render 8 New Images", "rerender", {target_id: target}, !ready);
      if (group.prompt_path) {
        link(controls, "Image prompt", route(target, "prompt"));
        button(controls, "Analyze Prompt", "analyze-prompt", {target_id: target}, ["QUEUED", "RUNNING"].includes(group.analysis?.status));
        button(controls, "Second Opinion", "second-opinion", {target_id: target}, group.analysis?.status !== "COMPLETE");
      }
      section.append(controls);
      if (group.analysis) {
        const analysis = node("p", `Prompt analysis: ${group.analysis.status}${group.analysis.error ? ` · ${group.analysis.error}` : ""}`);
        if (group.analysis.status === "COMPLETE") link(analysis, " View analysis", route(target, "analysis"));
        section.append(analysis);
      }
      const sources = node("div", null, "local-pipeline-sources");
      (group.next_reference_images || group.reference_images || []).forEach((reference, index) => {
        const figure = node("figure"), caption = `Image ${reference.image_index || index + 1} — ${reference.prompt_role || reference.role || "reference"}: ${reference.label || reference.tag}`;
        const image = node("img"); image.src = route(target, `next-references/${index}`); image.alt = caption; image.loading = "lazy";
        figure.append(node("figcaption", caption), image); sources.append(figure);
      });
      section.append(sources);
      const cards = node("div", null, "scene-batch-candidates");
      const renderCandidate = slot => {
        const selected = run.selected_views[target] === slot.candidate_id;
        const card = node("article", null, `local-pipeline-candidate${selected ? " is-selected" : ""}`);
        card.append(node("h3", `Slot ${slot.slot || "—"}${selected ? " · Selected" : ""}`));
        card.append(node("p", `${slot.status}${slot.error ? ` · ${slot.error}` : ""}`));
        if (slot.status === "COMPLETE") {
          const image = node("img"); image.src = route(target, `images/${encodeURIComponent(slot.candidate_id)}`);
          image.alt = `${definition.label} slot ${slot.slot}`; image.loading = "lazy";
          const anchor = node("a", null, "local-pipeline-candidate-image"); anchor.href = image.src; anchor.target = "_blank"; anchor.append(image); card.append(anchor);
        }
        const slotActions = node("div", null, "button-row compact"), payload = {target_id: target, candidate_id: slot.candidate_id};
        button(slotActions, selected ? "Unselect" : "Select", "select",
          {...payload, candidate_id: selected ? "" : slot.candidate_id},
          slot.status !== "COMPLETE");
        button(slotActions, "Retry", "retry", payload, ["SUBMITTING", "QUEUED", "RUNNING"].includes(slot.status));
        button(slotActions, "Clear", "clear", payload);
        card.append(slotActions); return card;
      };
      for (const slot of active) cards.append(renderCandidate(slot));
      for (const slot of group.history_candidates || []) {
        if (slot.status !== "COMPLETE") continue;
        const details = node("details", null, "scene-batch-history");
        details.append(node("summary", `Earlier render · slot ${slot.slot || "—"}`));
        details.append(renderCandidate(slot)); cards.append(details);
      }
      section.append(cards);
      const details = node("details"); details.dataset.target = target;
      details.open = expanded.has(target);
      details.append(node("summary", "Observations"));
      const notes = node("textarea"); notes.setAttribute("aria-label", `${definition.label} observations`);
      notes.value = observations.has(target) ? observations.get(target) : run.view_reviews?.[target]?.observations || "";
      notes.addEventListener("input", () => observations.set(target, notes.value)); details.append(notes);
      const noteActions = node("div", null, "button-row compact");
      const save = node("button", "Save observations"); save.type = "button"; save.disabled = pending;
      save.addEventListener("click", async () => { await perform("save-observations", {target_id: target, observations: notes.value}); observations.delete(target); });
      noteActions.append(save); button(noteActions, "Analyze Images", "analyze-images", {target_id: target}, !group.candidates.some(item => item.status === "COMPLETE"));
      details.append(noteActions);
      const ai = run.view_reviews?.[target]?.ai_observations || {};
      details.append(node("p", `AI observations: ${ai.status || "PENDING"}${ai.error ? ` · ${ai.error}` : ""}\n${ai.text || ""}`, "scene-batch-observations"));
      section.append(details); host.append(section);
    }
    for (const definition of run.historical_targets || []) {
      const group = run.groups[definition.target_id];
      const section = node("section", null, "local-pipeline-view scene-batch-history-target");
      section.append(node("h2", `${definition.label} · inactive`));
      const cards = node("div", null, "scene-batch-candidates");
      for (const candidate of group.candidates || []) {
        if (candidate.status !== "COMPLETE") continue;
        const card = node("article", null, "local-pipeline-candidate");
        card.append(node("h3", `Slot ${candidate.slot || "—"}`));
        const image = node("img"); image.src = route(definition.target_id, `images/${encodeURIComponent(candidate.candidate_id)}`);
        image.alt = `${definition.label} earlier image`; image.loading = "lazy";
        const anchor = node("a", null, "local-pipeline-candidate-image"); anchor.href = image.src; anchor.target = "_blank"; anchor.append(image); card.append(anchor);
        const actions = node("div", null, "button-row compact");
        const selected = run.selected_views[definition.target_id] === candidate.candidate_id;
        button(actions, selected ? "Unselect" : "Select", "select",
          {target_id: definition.target_id, candidate_id: selected ? "" : candidate.candidate_id});
        card.append(actions); cards.append(card);
      }
      section.append(cards); host.append(section);
    }
  }
  function hasActiveWork() {
    if (!run) return false;
    const active = new Set(["SUBMITTING", "QUEUED", "RUNNING"]);
    return Object.values(run.groups || {}).some(group =>
      (group.candidates || []).some(item => active.has(item.status))
      || active.has(group.analysis?.status))
      || Object.values(run.rankings || {}).some(item => item.status === "RUNNING");
  }
  function scheduleRefresh(delay = 5000) {
    clearTimeout(timer);
    timer = null;
    if (hasActiveWork() && page.classList.contains("active") && !document.hidden) {
      timer = setTimeout(() => void refresh(), delay);
    }
  }
  async function refresh(forcePreviews = false) {
    if (!run || pending || !page.classList.contains("active") || document.hidden) {
      scheduleRefresh();
      return;
    }
    const expectedVersion = version, expectedId = run.run_id;
    try {
      const updated = await request(`${base()}/${expectedId}${forcePreviews ? "?refresh_previews=true" : ""}`);
      if (pending || expectedVersion !== version || expectedId !== run?.run_id) return;
      const changed = updated.updated_at !== run.updated_at;
      run = updated;
      if (changed && (!page.contains(document.activeElement) || !document.activeElement.matches("textarea,input,select"))) render();
    } catch (error) { message.textContent = error.message; }
    scheduleRefresh();
  }
  async function open(nextContext) {
    clearTimeout(timer); timer = null; const expectedVersion = ++version; pending = false;
    if (!nextContext.story || !nextContext.scene) { message.textContent = "Select a story and scene first."; context = null; run = null; render(); return; }
    if (context?.story !== nextContext.story || context?.scene !== nextContext.scene) { run = null; observations.clear(); }
    context = nextContext;
    document.querySelector("#scene-batch-context").textContent = `${context.story} / ${context.scene}`;
    message.textContent = "Loading saved scene render state…";
    try {
      const listed = await request(base());
      if (expectedVersion !== version) return;
      const current = listed.batches?.[0];
      run = current ? await request(`${base()}/${current.run_id}`) : await request(base(), {});
      if (expectedVersion !== version) return;
      message.textContent = "Each target has eight active slots. New renders keep earlier images available for selection.";
      render();
      scheduleRefresh();
    } catch (error) { message.textContent = error.message; run = null; render(); }
  }
  document.querySelector("#scene-batch-start").addEventListener("click", () => void perform("start"));
  document.querySelector("#scene-batch-stop").addEventListener("click", () => void perform("stop"));
  document.querySelector("#scene-batch-publish").addEventListener("click", () => void perform("publish"));
  document.querySelector("#scene-batch-refresh").addEventListener("click", () => void refresh(true));
  document.addEventListener("visibilitychange", () => scheduleRefresh(0));
  return {open};
})();
