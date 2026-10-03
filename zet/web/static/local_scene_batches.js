/* Dynamic scene targets use the same candidate cards and reference layout as local assets. */
window.SceneBatches = (() => {
  const page = document.querySelector("#scene-batches-page");
  const host = document.querySelector("#scene-batch-groups");
  const message = document.querySelector("#scene-batch-message");
  const history = document.querySelector("#scene-batch-history");
  const planHost = document.querySelector("#scene-batch-plan");
  let context = null, run = null, pending = false, timer = null, version = 0;
  const observations = new Map();
  const node = (tag, text, className = "") => {
    const element = document.createElement(tag);
    if (text != null) element.textContent = text;
    if (className) element.className = className;
    return element;
  };
  const base = () => `/api/stories/${encodeURIComponent(context.story)}/scenes/${encodeURIComponent(context.scene)}/local-batches`;
  const route = (target, suffix, attempt = run.groups[target].attempt_id) => `${base()}/${run.run_id}/targets/${encodeURIComponent(target)}/${suffix}?attempt_id=${encodeURIComponent(attempt || "")}`;
  async function request(url, payload) {
    const response = await fetch(url, payload === undefined ? {} : { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
    const value = await response.json();
    if (!response.ok) throw new Error(value.detail || "Scene batch request failed.");
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
    const expectedVersion = version, expectedId = run.run_id, endpoint = base();
    pending = true;
    message.textContent = `${action.replaceAll("-", " ")}…`;
    render();
    try {
      const updated = await request(`${endpoint}/${expectedId}/actions/${action}`, payload);
      if (version !== expectedVersion || run?.run_id !== expectedId) return;
      run = updated;
      message.textContent = run.status.replaceAll("_", " "); render(); await list();
    } catch (error) { if (version === expectedVersion) message.textContent = error.message; }
    finally { if (version === expectedVersion) { pending = false; render(); } }
  }
  function render() {
    const expanded = new Set(Array.from(host.querySelectorAll("details[open]")).map(item => item.dataset.target));
    host.replaceChildren();
    document.querySelector("#scene-batch-new").disabled = pending || !context;
    document.querySelector("#scene-batch-refresh").disabled = pending || !run;
    history.disabled = pending;
    document.querySelector("#scene-batch-publish").disabled = pending || run?.status !== "READY_TO_PUBLISH";
    for (const selector of ["#scene-batch-start", "#scene-batch-stop", "#scene-batch-rename"]) document.querySelector(selector).disabled = pending || !run;
    document.querySelector("#scene-batch-recompile").disabled = pending || !run || Object.values(run.groups).some(group => group.candidates.some(item => ["QUEUED", "RUNNING"].includes(item.status)));
    const packageLink = document.querySelector("#scene-batch-package"); packageLink.hidden = !run;
    if (!run) return;
    packageLink.href = `${base()}/${run.run_id}/prompt-improvement-package`;
    document.querySelector("#scene-batch-status").textContent = `${run.batch_name || run.run_id.slice(0, 8)} · ${run.status.replaceAll("_", " ")}`;
    for (const definition of run.targets) {
      const target = definition.target_id, group = run.groups[target], ranking = run.rankings[target] || {};
      const section = node("section", null, "local-pipeline-view");
      section.append(node("h2", definition.label));
      section.append(node("p", `${group.status.replaceAll("_", " ")}${group.stale_reason ? ` · ${group.stale_reason}` : ""}`));
      if (definition.dependencies.length) section.append(node("p", `Requires selections: ${definition.dependencies.join(", ")}`, "muted"));
      const ready = run.ready_targets.includes(target), active = group.candidates.some(item => ["QUEUED", "RUNNING"].includes(item.status));
      const actions = node("div", null, "button-row compact");
      button(actions, "Compile Prompt", "compile", {target_id: target}, !ready || active || group.candidates.length > 0);
      button(actions, "Render", "render", {target_id: target}, !ready || active || group.candidates.length > 0);
      button(actions, "Retry Failed", "retry", {target_id: target}, active || !group.candidates.some(item => ["FAILED", "STOPPED"].includes(item.status)));
      button(actions, "Rerender Group", "rerender", {target_id: target}, active || !group.attempt_id);
      button(actions, "Re-evaluate", "reevaluate", {target_id: target}, active || !group.candidates.some(item => item.status === "COMPLETE"));
      if (group.prompt_path) {
        link(actions, "Image prompt", route(target, "prompt"));
        button(actions, "Analyze Prompt", "analyze-prompt", {target_id: target}, ["QUEUED", "RUNNING"].includes(group.analysis?.status));
        button(actions, "Second Opinion", "second-opinion", {target_id: target}, group.analysis?.status !== "COMPLETE");
      }
      section.append(actions);
      if (group.analysis) {
        const analysis = node("p", `Prompt analysis: ${group.analysis.status}${group.analysis.error ? ` · ${group.analysis.error}` : ""}`);
        if (group.analysis.status === "COMPLETE") link(analysis, " View analysis", route(target, "analysis")); section.append(analysis);
      }
      const sources = node("div", null, "local-pipeline-sources");
      (group.reference_images || []).forEach((reference, index) => {
        const figure = node("figure"), caption = `Image ${reference.image_index || index + 1} — ${reference.prompt_role || reference.role || "reference"}: ${reference.label || reference.tag}`;
        const image = node("img"); image.src = route(target, `references/${index}`); image.alt = caption; image.loading = "lazy";
        figure.append(node("figcaption", caption), image); sources.append(figure);
      });
      section.append(sources);
      if (ranking.status) section.append(node("p", `Rating: ${ranking.status}${ranking.error ? ` · ${ranking.error}` : ""}`, "muted"));
      const order = ranking.ordered_candidate_ids || [], cards = node("div", null, "scene-batch-candidates");
      const candidates = [...group.candidates].sort((a, b) => {
        const ai = order.indexOf(a.candidate_id), bi = order.indexOf(b.candidate_id);
        return (ai < 0 ? 999 : ai) - (bi < 0 ? 999 : bi);
      });
      for (const candidate of candidates) {
        const selected = run.selected_views[target] === candidate.candidate_id;
        const card = node("article", null, `local-pipeline-candidate${selected ? " is-selected" : ""}`);
        card.append(node("h3", `${candidate.candidate_id}${selected ? " · Selected" : ""}`));
        if (candidate.status === "COMPLETE") {
          const image = node("img"); image.src = route(target, `images/${encodeURIComponent(candidate.candidate_id)}`); image.alt = candidate.candidate_id; image.loading = "lazy";
          const anchor = node("a", null, "local-pipeline-candidate-image"); anchor.href = image.src; anchor.target = "_blank"; anchor.append(image); card.append(anchor);
        }
        card.append(node("p", `${candidate.status}${candidate.error ? ` · ${candidate.error}` : ""}`));
        if ((candidate.render_attempts || []).length > 1) {
          const attempts = node("details"); attempts.append(node("summary", `${candidate.render_attempts.length} render attempts`));
          candidate.render_attempts.forEach((attempt, index) => attempts.append(node("p", `Attempt ${index + 1}: ${attempt.status || "Submitted"}${attempt.error ? ` · ${attempt.error}` : ""}`)));
          card.append(attempts);
        }
        const entry = ranking.entries?.find(item => item.candidate_id === candidate.candidate_id);
        if (entry) card.append(node("p", `#${order.indexOf(candidate.candidate_id) + 1} — ${entry.reason}`));
        const controls = node("div", null, "button-row compact"), payload = {target_id: target, candidate_id: candidate.candidate_id};
        const decision = node("select"); decision.setAttribute("aria-label", `${candidate.candidate_id} human review`);
        for (const value of ["undecided", "keep", "reject"]) { const option = node("option", value); option.value = value; decision.append(option); }
        decision.value = candidate.human_review?.decision || "undecided";
        decision.disabled = pending;
        decision.addEventListener("change", () => void perform("review", {...payload, decision: decision.value}));
        controls.append(decision);
        if (["FAILED", "STOPPED"].includes(candidate.status)) button(controls, "Retry", "retry", payload, active);
        button(controls, selected ? "Unselect" : "Select", "select", {...payload, candidate_id: selected ? "" : candidate.candidate_id}, candidate.status !== "COMPLETE" || ranking.status !== "COMPLETE");
        button(controls, "↑", "move-rank", {...payload, direction: "up"}, !order.includes(candidate.candidate_id));
        button(controls, "↓", "move-rank", {...payload, direction: "down"}, !order.includes(candidate.candidate_id));
        card.append(controls); cards.append(card);
      }
      section.append(cards);
      const details = node("details"); details.dataset.target = target; details.open = expanded.has(target);
      details.append(node("summary", "Observations"));
      const notes = node("textarea"); notes.setAttribute("aria-label", `${definition.label} observations`);
      notes.value = observations.has(target) ? observations.get(target) : run.view_reviews?.[target]?.observations || "";
      notes.addEventListener("input", () => observations.set(target, notes.value)); details.append(notes);
      const noteActions = node("div", null, "button-row compact");
      const save = node("button", "Save observations"); save.type = "button";
      save.disabled = pending;
      save.addEventListener("click", async () => { await perform("save-observations", {target_id: target, observations: notes.value}); observations.delete(target); });
      noteActions.append(save); button(noteActions, "Analyze Images", "analyze-images", {target_id: target}, !group.candidates.some(item => item.status === "COMPLETE"));
      details.append(noteActions);
      const ai = run.view_reviews?.[target]?.ai_observations || {};
      details.append(node("p", `AI observations: ${ai.status || "PENDING"}${ai.error ? ` · ${ai.error}` : ""}\n${ai.text || ""}`, "scene-batch-observations")); section.append(details);
      if (group.attempts.length) {
        const previous = node("details"); previous.dataset.target = `${target}-history`; previous.open = expanded.has(previous.dataset.target);
        previous.append(node("summary", `${group.attempts.length} previous attempt(s)`));
        for (const attempt of group.attempts) {
          previous.append(node("p", `Stale: ${attempt.stale_reason || "Superseded attempt"}`));
          link(previous, "Saved image prompt", route(target, "prompt", attempt.attempt_id));
          const evidence = node("div", null, "local-pipeline-sources");
          (attempt.reference_images || []).forEach((reference, index) => {
            const figure = node("figure"), caption = `Image ${index + 1}: ${reference.prompt_role || reference.role || reference.label || "reference"}`;
            const image = node("img"); image.src = route(target, `references/${index}`, attempt.attempt_id); image.alt = caption;
            figure.append(node("figcaption", caption), image); evidence.append(figure);
          }); previous.append(evidence);
          const archive = node("div", null, "scene-batch-candidates");
          for (const candidate of attempt.candidates) {
            const card = node("article", null, "local-pipeline-candidate");
            card.append(node("p", `${candidate.candidate_id} · ${candidate.status}${candidate.candidate_id === attempt.selected_candidate_id ? " · Previously selected" : ""}`));
            if (candidate.status === "COMPLETE") {
              const image = node("img"); image.src = route(target, `images/${encodeURIComponent(candidate.candidate_id)}`, attempt.attempt_id); image.alt = candidate.candidate_id;
              const anchor = node("a", null, "local-pipeline-candidate-image"); anchor.href = image.src; anchor.target = "_blank"; anchor.append(image); card.append(anchor);
            }
            const entry = attempt.ranking?.entries?.find(item => item.candidate_id === candidate.candidate_id);
            if (entry) card.append(node("p", entry.reason)); archive.append(card);
          } previous.append(archive);
        } section.append(previous);
      }
      host.append(section);
    }
  }
  async function list() {
    const expectedVersion = version;
    const query = new URLSearchParams({target_id: context.retiredTarget || "main", ask_id: context.retiredAskId || ""});
    const payload = await request(`${base()}?${query}`);
    if (expectedVersion !== version) return null;
    history.replaceChildren();
    history.append(new Option("Choose a batch", ""));
    for (const batch of payload.batches) history.append(new Option(`${batch.batch_name || batch.run_id.slice(0, 8)} · ${batch.status} · ${batch.created_at}`, batch.run_id));
    history.value = run?.run_id || "";
    return payload;
  }
  async function refresh() {
    if (!run || pending || !page.classList.contains("active") || document.hidden) return;
    const expectedVersion = version, expectedId = run.run_id;
    try {
      const updated = await request(`${base()}/${expectedId}`);
      if (pending || expectedVersion !== version || expectedId !== run?.run_id) return;
      run = updated;
      if (!page.contains(document.activeElement) || !document.activeElement.matches("textarea,input,select")) render();
    } catch (error) { message.textContent = error.message; }
  }
  async function open(nextContext) {
    clearInterval(timer); const expectedVersion = ++version; pending = false;
    if (!nextContext.story || !nextContext.scene) { message.textContent = "Select a story and scene first."; context = null; run = null; render(); return; }
    if (context?.story !== nextContext.story || context?.scene !== nextContext.scene) { run = null; observations.clear(); }
    context = nextContext;
    document.querySelector("#scene-batch-context").textContent = `${context.story} / ${context.scene}`;
    try {
      const preview = await request(`${base()}/preview`, {}); planHost.replaceChildren();
      if (expectedVersion !== version) return;
      for (const target of preview.targets) {
        const label = node("label", target.label), input = node("input"); input.type = "number"; input.min = "1"; input.max = "16"; input.value = "4"; input.dataset.target = target.target_id;
        label.append(input); planHost.append(label);
      }
      const listing = await list();
      if (expectedVersion !== version) return;
      const query = new URLSearchParams(location.search), preferred = query.get("batch");
      const id = nextContext.retiredPage ? listing.linked_batch_id : run?.run_id || preferred || history.options[1]?.value;
      const updated = id ? await request(`${base()}/${encodeURIComponent(id)}`) : null;
      if (expectedVersion !== version) return;
      run = updated; history.value = run?.run_id || "";
      document.querySelector("#scene-batch-name").value = run?.batch_name || "";
      message.textContent = nextContext.retiredPage && !id ? "Render Console and Image Review are retired. This historical render has no scene batch. Create a new batch here." : "Select candidates between stages. Publishing keeps the existing scene image paths."; render();
      timer = setInterval(() => void refresh(), 3000);
    } catch (error) { message.textContent = error.message; }
  }
  history.addEventListener("change", async () => {
    if (!history.value || pending) return;
    const expectedVersion = ++version;
    try {
      const updated = await request(`${base()}/${encodeURIComponent(history.value)}`);
      if (expectedVersion !== version) return;
      observations.clear(); run = updated;
      document.querySelector("#scene-batch-name").value = run.batch_name || "";
      render(); setRoute();
    } catch (error) { if (expectedVersion === version) message.textContent = error.message; }
  });
  function setRoute() {
    const url = new URL(location.href); url.searchParams.set("batch", run.run_id); window.history.replaceState({}, "", url);
  }
  document.querySelector("#scene-batch-new").addEventListener("click", async () => {
    if (!context || pending) return;
    const expectedVersion = version; pending = true;
    message.textContent = "Creating scene batch…";
    render();
    try {
      const counts = Object.fromEntries(Array.from(planHost.querySelectorAll("input")).map(input => [input.dataset.target, Number(input.value)]));
      const updated = await request(base(), {counts, batch_name: document.querySelector("#scene-batch-name").value});
      if (expectedVersion !== version) return;
      run = updated; observations.clear(); await list(); render(); setRoute();
    } catch (error) { message.textContent = error.message; }
    finally { if (expectedVersion === version) { pending = false; render(); } }
  });
  document.querySelector("#scene-batch-start").addEventListener("click", () => void perform(run?.status === "STOPPED" ? "resume" : "start"));
  document.querySelector("#scene-batch-stop").addEventListener("click", () => void perform("stop"));
  document.querySelector("#scene-batch-publish").addEventListener("click", () => void perform("publish"));
  document.querySelector("#scene-batch-recompile").addEventListener("click", () => void perform("recompile"));
  document.querySelector("#scene-batch-rename").addEventListener("click", () => void perform("rename", {batch_name: document.querySelector("#scene-batch-name").value}));
  document.querySelector("#scene-batch-refresh").addEventListener("click", () => void refresh());
  return {open};
})();
