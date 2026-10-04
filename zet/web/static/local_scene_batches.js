/* Current scene renders are cultivated in eight stable slots per target. */
window.SceneBatches = (() => {
  const page = document.querySelector("#scene-batches-page");
  const host = document.querySelector("#scene-batch-groups");
  const message = document.querySelector("#scene-batch-message");
  const reviewDialog = document.querySelector("#scene-batch-review-dialog");
  const reviewMessage = document.querySelector("#scene-batch-review-message");
  let context = null, run = null, pending = false, timer = null, version = 0;
  let reviewKey = null;
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
  const candidateKey = (target, candidateId) => `${target}\u0000${candidateId}`;
  function reviewCandidates() {
    if (!run) return [];
    return (run.targets || []).flatMap(definition => {
      const group = run.groups[definition.target_id];
      const candidates = group?.active_candidates || [];
      return candidates.filter(candidate => candidate.status === "COMPLETE" && candidate.image_path)
        .map(candidate => ({candidate, target: definition.target_id, label: definition.label}));
    });
  }
  function renderReview() {
    if (!reviewDialog.open) return;
    const candidates = reviewCandidates();
    const index = candidates.findIndex(item => candidateKey(item.target, item.candidate.candidate_id) === reviewKey);
    if (index < 0) { reviewDialog.close(); return; }
    const {candidate, target, label} = candidates[index];
    const selected = run.selected_views[target] === candidate.candidate_id;
    const image = document.querySelector("#scene-batch-review-image");
    image.src = route(target, `images/${encodeURIComponent(candidate.candidate_id)}`);
    image.alt = `${label} slot ${candidate.slot} candidate`;
    document.querySelector("#scene-batch-review-title").textContent = label;
    const details = document.querySelector("#scene-batch-review-details");
    details.replaceChildren();
    details.append(node("p", `Slot ${candidate.slot || "—"} · ${selected ? "Selected" : candidate.status}`, "scene-batch-review-status"));
    details.append(node("p", `Candidate: ${candidate.candidate_id}`));
    if (candidate.seed != null) details.append(node("p", `Seed: ${candidate.seed}`));
    if (candidate.elapsed_seconds != null) details.append(node("p", `Generation time: ${Math.round(candidate.elapsed_seconds)} seconds`));
    if (candidate.error) details.append(node("p", candidate.error, "error-text"));
    const ranking = run.rankings?.[target];
    const position = (ranking?.ordered_candidate_ids || []).indexOf(candidate.candidate_id);
    if (position >= 0) details.append(node("p", `Rank: ${position + 1}`));
    const select = document.querySelector("#scene-batch-review-select");
    select.textContent = selected ? "Unselect" : "Select";
    select.disabled = pending;
    document.querySelector("#scene-batch-review-retry").disabled = pending || !run.targets.some(item => item.target_id === target);
    document.querySelector("#scene-batch-review-clear").disabled = pending;
    document.querySelector("#scene-batch-review-prev").disabled = pending || index === 0;
    document.querySelector("#scene-batch-review-next").disabled = pending || index === candidates.length - 1;
    document.querySelector("#scene-batch-review-position").textContent = `${index + 1} of ${candidates.length}`;
  }
  function openReview(target, candidateId) {
    reviewKey = candidateKey(target, candidateId);
    reviewMessage.textContent = "";
    if (!reviewDialog.open) reviewDialog.showModal();
    renderReview();
  }
  function navigateReview(direction) {
    const candidates = reviewCandidates();
    const index = candidates.findIndex(item => candidateKey(item.target, item.candidate.candidate_id) === reviewKey);
    const next = candidates[index + direction];
    if (!next) return;
    reviewKey = candidateKey(next.target, next.candidate.candidate_id);
    reviewMessage.textContent = "";
    renderReview();
  }
  function reviewAction(action) {
    const item = reviewCandidates().find(entry => candidateKey(entry.target, entry.candidate.candidate_id) === reviewKey);
    if (!item) return;
    const selected = run.selected_views[item.target] === item.candidate.candidate_id;
    void perform(action, {target_id: item.target, candidate_id: action === "select" && selected ? "" : item.candidate.candidate_id});
  }
  async function perform(action, payload = {}) {
    if (pending || !run) return;
    const expectedVersion = version, expectedId = run.run_id;
    pending = true;
    message.textContent = `${action.replaceAll("-", " ")}…`;
    if (reviewDialog.open) reviewMessage.textContent = message.textContent;
    render();
    try {
      const updated = await request(`${base()}/${expectedId}/actions/${action}`, payload);
      if (version !== expectedVersion || run?.run_id !== expectedId) return;
      if (action === "clear" && reviewKey === candidateKey(payload.target_id, payload.candidate_id)) {
        const candidates = reviewCandidates();
        const index = candidates.findIndex(item => candidateKey(item.target, item.candidate.candidate_id) === reviewKey);
        const next = candidates[index + 1] || candidates[index - 1];
        reviewKey = next ? candidateKey(next.target, next.candidate.candidate_id) : null;
      }
      run = updated;
      if (!reviewKey && reviewDialog.open) reviewDialog.close();
      message.textContent = run.status.replaceAll("_", " "); render();
      if (reviewDialog.open) reviewMessage.textContent = "";
    } catch (error) {
      if (version === expectedVersion) {
        message.textContent = error.message;
        if (reviewDialog.open) reviewMessage.textContent = error.message;
      }
    } finally { if (version === expectedVersion) { pending = false; render(); scheduleRefresh(); } }
  }
  function render() {
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
    if (!run) { if (reviewDialog.open) reviewDialog.close(); return; }
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
      button(controls, "Fill Slots", "fill", {target_id: target}, !ready || !active.some(slot => slot.status === "EMPTY"));
      if (ready) link(controls, "Image prompt", route(target, "prompt"));
      if (group.prompt_path) {
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
          const review = node("button", null, "local-pipeline-candidate-image scene-batch-review-trigger");
          review.type = "button"; review.setAttribute("aria-label", `Review ${definition.label} slot ${slot.slot}`);
          review.addEventListener("click", () => openReview(target, slot.candidate_id));
          review.append(image); card.append(review);
        }
        const slotActions = node("div", null, "button-row compact"), payload = {target_id: target, candidate_id: slot.candidate_id};
        if (slot.status === "COMPLETE") {
          const reviewButton = node("button", "Review"); reviewButton.type = "button";
          reviewButton.addEventListener("click", () => openReview(target, slot.candidate_id));
          slotActions.append(reviewButton);
        }
        button(slotActions, selected ? "Unselect" : "Select", "select",
          {...payload, candidate_id: selected ? "" : slot.candidate_id},
          slot.status !== "COMPLETE");
        button(slotActions, "Retry", "retry", payload, ["SUBMITTING", "QUEUED", "RUNNING"].includes(slot.status));
        button(slotActions, "Clear", "clear", payload);
        card.append(slotActions); return card;
      };
      for (const slot of active) cards.append(renderCandidate(slot));
      section.append(cards);
      host.append(section);
    }
    renderReview();
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
      else if (changed) renderReview();
    } catch (error) { message.textContent = error.message; }
    scheduleRefresh();
  }
  async function open(nextContext) {
    clearTimeout(timer); timer = null; const expectedVersion = ++version; pending = false;
    if (!nextContext.story || !nextContext.scene) { message.textContent = "Select a story and scene first."; context = null; run = null; render(); return; }
    if (context?.story !== nextContext.story || context?.scene !== nextContext.scene) {
      run = null; reviewKey = null;
      if (reviewDialog.open) reviewDialog.close();
    }
    context = nextContext;
    document.querySelector("#scene-batch-context").textContent = `${context.story} / ${context.scene}`;
    message.textContent = "Loading saved scene render state…";
    try {
      const listed = await request(base());
      if (expectedVersion !== version) return;
      const current = listed.batches?.[0];
      run = current ? await request(`${base()}/${current.run_id}`) : await request(base(), {});
      if (expectedVersion !== version) return;
      message.textContent = "Each target has eight slots. Clearing or retrying a slot replaces its image.";
      render();
      scheduleRefresh();
    } catch (error) { message.textContent = error.message; run = null; render(); }
  }
  document.querySelector("#scene-batch-start").addEventListener("click", () => void perform("start"));
  document.querySelector("#scene-batch-stop").addEventListener("click", () => void perform("stop"));
  document.querySelector("#scene-batch-publish").addEventListener("click", () => void perform("publish"));
  document.querySelector("#scene-batch-refresh").addEventListener("click", () => void refresh(true));
  document.querySelector("#scene-batch-review-close").addEventListener("click", () => reviewDialog.close());
  document.querySelector("#scene-batch-review-prev").addEventListener("click", () => navigateReview(-1));
  document.querySelector("#scene-batch-review-next").addEventListener("click", () => navigateReview(1));
  document.querySelector("#scene-batch-review-select").addEventListener("click", () => reviewAction("select"));
  document.querySelector("#scene-batch-review-retry").addEventListener("click", () => reviewAction("retry"));
  document.querySelector("#scene-batch-review-clear").addEventListener("click", () => reviewAction("clear"));
  document.addEventListener("visibilitychange", () => scheduleRefresh(0));
  return {open};
})();
