/* Guided, revision-bound prompt refinement with independent human review. */
(() => {
  const query = new URLSearchParams(location.search);
  const pipeline = query.get("pipeline") || "", runId = query.get("run_id") || "";
  const universe = query.get("universe_id") || "", costume = query.get("costume") || "";
  let sessionId = query.get("session_id") || "", data, busy = false, pollTimer, saveTimer, dirty = false;
  let mode = ["history", "image", "round"].includes(query.get("stage")) ? query.get("stage") : "current";
  let roundId = query.get("round") || "", imageIndex = Number(query.get("image")) || 0;
  let reviewForm = null, criteriaText = null, criteriaRevision = null, directionText = null, directionId = null;
  const $ = id => document.getElementById(`pg-${id}`), drafts = new Map();
  const active = new Set(["RENDERING", "EVALUATING", "DIRECTIONS_GENERATING", "DRAFTING"]);
  const terminal = new Set(["FINISHED", "SCRAPPED", "CANCELLED"]);
  const labels = {SETUP:"Set up baseline", NEEDS_EVALUATION:"Existing round needs evaluation", RENDERING:"Rendering images", EVALUATING:"Evaluating images", REVIEW_IMAGES:"Review images", REVIEW_ROUND:"Review round", DIRECTIONS_GENERATING:"Preparing directions", DIRECTIONS_REVIEW:"Review directions", DRAFTING:"Writing prompt", DRAFT_REVIEW:"Approve draft", FAILED:"Action required", FINISHED:"Run finished", SCRAPPED:"Run archived", CANCELLED:"Run archived"};
  function endpoint(suffix = "") {
    const q = new URLSearchParams({universe_id: universe}); if (costume) q.set("costume", costume);
    return `/api/local/${encodeURIComponent(pipeline)}/runs/${encodeURIComponent(runId)}/prompt-generator/${encodeURIComponent(sessionId)}${suffix}?${q}`;
  }
  function node(tag, text, className) {
    const item = document.createElement(tag); if (text !== undefined) item.textContent = text;
    if (className) item.className = className; return item;
  }
  function message(text, error = false) { $("message").textContent = text; $("message").classList.toggle("error", error); }
  function button(text, action, host, className = "") {
    const item = node("button", text, className); item.type = "button";
    item.addEventListener("click", () => { void action(item); }); host.append(item); return item;
  }
  function promptLink(host, target, text = "View prompt ↗") {
    const link = node("a", text); link.href = endpoint(`/prompts/${encodeURIComponent(target)}`); link.target = "_blank"; link.rel = "noopener"; host.append(link);
  }
  function panel(title, text) {
    const section = node("section", undefined, "pg-panel"); section.append(node("h2", title));
    if (text) section.append(node("p", text)); return section;
  }
  function attempts(round) { return [...new Map(round.attempts.map(a => [a.seed, a])).values()]; }
  function currentRound() { return data.history.at(-1); }
  function updateUrl() {
    const url = new URL(location.href); url.searchParams.set("stage", mode === "current" ? data.stage.toLowerCase().replaceAll("_", "-") : mode); url.searchParams.set("session_id", sessionId);
    if (roundId) url.searchParams.set("round", roundId); else url.searchParams.delete("round");
    url.searchParams.set("image", String(imageIndex)); history.replaceState(null, "", url);
  }
  async function request(suffix = "", body) {
    const response = await fetch(endpoint(suffix), {method: body === undefined ? "GET" : "POST", headers: {"Content-Type":"application/json", "X-Zet-Universe": universe}, body: body === undefined ? undefined : JSON.stringify(body)});
    const result = await response.json(); if (!response.ok) throw new Error(result.detail || "Pilot request failed."); return result;
  }
  function schedulePoll() { clearTimeout(pollTimer); if (data && active.has(data.stage)) pollTimer = setTimeout(refresh, 1500); }
  async function refresh() {
    if (busy || dirty) { schedulePoll(); return; }
    try { data = await request(); paint(); if ($("message").textContent === "Loading saved progress…") message("Saved progress loaded."); schedulePoll(); }
    catch (error) { message(`${error.message} Retrying saved progress; you can also reload this page.`, true); schedulePoll(); }
  }
  function pending(on, selected, text) {
    busy = on; $("workspace").setAttribute("aria-busy", String(on));
    document.querySelectorAll("button").forEach(b => { b.disabled = on || b.dataset.unavailable === "true"; });
    if (selected) document.querySelectorAll("textarea, select, input[type=radio]").forEach(el => { el.disabled = on; });
    if (on && selected) { selected.dataset.label = selected.textContent; selected.textContent = text; selected.setAttribute("aria-busy", "true"); }
    if (!on && selected) { selected.textContent = selected.dataset.label || selected.textContent; selected.removeAttribute("aria-busy"); }
  }
  async function act(operation, values = {}, selected, confirmation = "Saved.") {
    if (busy) return false;
    if (dirty && !(await flushReview())) return false;
    pending(true, selected, "Working…"); message(`${selected?.dataset.label || "Saving"}…`);
    try {
      data = await request(`/${operation}`, {...values, revision: data.revision});
      if (data.session_id !== sessionId) { sessionId = data.session_id; drafts.clear(); criteriaRevision = null; directionId = null; }
      mode = "current"; roundId = ""; imageIndex = 0;
      $("menu").open = false;
      paint(); message(confirmation); return true;
    } catch (error) { message(error.message, true); return false; }
    finally { pending(false, selected); schedulePoll(); }
  }
  async function navigate(nextMode, nextRound = "", index = 0) {
    if (busy || !(await flushReview())) return;
    mode = nextMode; roundId = nextRound; imageIndex = index; $("menu").open = false; paint();
  }
  function editReview() {
    dirty = true; reviewForm.draft.confirmed = false;
    const status = document.getElementById("pg-save-state"); if (status) status.textContent = "Saving…";
    clearTimeout(saveTimer); saveTimer = setTimeout(() => { void flushReview(); }, 500);
  }
  async function flushReview(confirm = false, selected) {
    if (confirm && reviewForm?.draft.criteria.some(c => !c.result || !c.chosen)) {
      message("Choose Pass, Fail or Unclear for every criterion before confirming this image.", true); return false;
    }
    clearTimeout(saveTimer);
    if (!reviewForm || (!dirty && !confirm)) return true;
    if (busy) return false;
    const form = reviewForm, version = JSON.stringify(form.draft); let saved = false;
    pending(true, selected, "Saving…");
    try {
      data = await request("/review", {revision: data.revision, attempt_id: form.attemptId, ...form.draft, confirm});
      if (version === JSON.stringify(form.draft)) dirty = false;
      saved = true;
      form.draft.confirmed = confirm; drafts.set(form.key, form.draft);
      const status = document.getElementById("pg-save-state"); if (status) status.textContent = confirm ? "Review confirmed" : (dirty ? "Saving…" : "Saved");
      message(confirm ? "Image review confirmed." : "Review saved."); return !dirty;
    } catch (error) {
      dirty = true; const status = document.getElementById("pg-save-state"); if (status) status.textContent = "Save failed — retry"; message(error.message, true); return false;
    } finally { pending(false, selected); if (saved && dirty) saveTimer = setTimeout(() => { void flushReview(); }, 500); }
  }
  function criteriaEditor(host, setup = false) {
    const label = node("label", "Visual acceptance criteria — one requirement per line"), input = node("textarea"); input.rows = 4; input.id = "pg-criteria";
    if (criteriaRevision !== data.criteria_revision) { criteriaRevision = data.criteria_revision; criteriaText = data.criteria_records.map(c => c.text).join("\n"); }
    input.value = criteriaText; input.addEventListener("input", () => { criteriaText = input.value; }); label.append(input); host.append(label);
    if (!setup) button("Save criteria and reassess these images", b => act("criteria", {criteria: input.value.split(/\r?\n/)}, b, "Criteria saved. Reassessing the current images."), host);
    return input;
  }
  function paintHeader() {
    const renderingLabel = data.rendering_mode === "rotate" ? "Rotate" : data.rendering_mode === "doll-dressing" ? "Doll-dressing" : "";
    $("context").textContent = `${pipeline}${renderingLabel ? ` · ${renderingLabel}` : ""} · ${data.packet.view}${costume ? ` · ${costume}` : ""} · Run ${sessionId.slice(0, 8)} · ${data.history.length ? `Round ${currentRound().round}` : "Baseline setup"}`;
    $("stage").textContent = labels[data.stage]; $("next").textContent = `Next: ${data.next_action}`;
    const steps = $("steps"); steps.replaceChildren();
    const stageIndex = {SETUP:0, NEEDS_EVALUATION:1, RENDERING:data.history.length < 2 ? 0 : 5, EVALUATING:1, REVIEW_IMAGES:2, REVIEW_ROUND:2, DIRECTIONS_GENERATING:3, DIRECTIONS_REVIEW:3, DRAFTING:4, DRAFT_REVIEW:4};
    ["Baseline", "AI evaluation", "Your review", "Directions", "Draft approval", "Next images"].forEach((label, index) => { const step = node("span", `${index + 1}. ${label}`); if (index === stageIndex[data.stage]) { step.className = "pg-step-current"; step.setAttribute("aria-current", "step"); } steps.append(step); });
    const menu = $("run-menu"); menu.replaceChildren();
    for (const round of data.history) button(`${round.kind === "baseline" ? "Baseline" : `Round ${round.round}`} · view results`, () => navigate("history", round.id), menu);
    for (const item of data.sessions || []) {
      if (item.session_id === sessionId) continue;
      const renderingLabel = item.rendering_mode === "rotate" ? "Rotate · " : item.rendering_mode === "doll-dressing" ? "Doll-dressing · " : "";
      const link = node("a", `${renderingLabel}Run ${item.session_id.slice(0, 8)} · ${labels[item.status] || item.status}`), url = new URL(location.href);
      url.searchParams.set("session_id", item.session_id); url.searchParams.set("stage", "current"); url.searchParams.delete("round"); link.href = url; menu.append(link);
    }
    if (!terminal.has(data.stage)) button("Scrap run", b => act("scrap", {}, b, "Run archived. All evidence has been retained."), menu, "pg-secondary");
    button("Scrap and start over", b => act("restart", {}, b, "Fresh setup prepared. No AI work has started."), menu, "pg-secondary");
  }
  function setup(host) {
    const rotation = data.rendering_mode === "rotate";
    const section = panel(rotation ? "Start with the compiled Rotate prompt" : "Start with the current compiled prompt", rotation
      ? "Rotate the frozen dressed source into the Assembly orientation. Assembly controls orientation, stance and framing only. Set concrete visual criteria before starting."
      : "Zet has frozen the current prompt, reference images and render settings. Set concrete visual criteria before starting."), input = criteriaEditor(section, true);
    section.append(node("p", "Start generates four baseline images and evaluates each against these criteria. Each later round requires your approval and reuses these four seeds."));
    promptLink(section, "baseline", "View compiled baseline prompt ↗");
    button("Start baseline — 4 images", b => act("start", {criteria: input.value.split(/\r?\n/)}, b, "Baseline approved. Rendering four images; AI evaluations follow."), section); host.append(section);
  }
  function progress(host) {
    const section = panel(labels[data.stage], "Progress is saved. You can leave this page and resume later."), round = currentRound();
    if (round && ["RENDERING", "EVALUATING"].includes(data.stage)) {
      const grid = node("div", undefined, "pg-progress-grid");
      attempts(round).forEach((attempt, index) => {
        const card = node("article", undefined, "pg-progress-card");
        if (attempt.status === "READY") { const img = node("img"); img.src = endpoint(`/images/${attempt.id}`); img.alt = `Image ${index + 1}`; card.append(img); }
        card.append(node("h3", `Image ${index + 1}`), node("p", attempt.status === "READY" ? `Image ready · AI ${(attempt.ai_evaluation?.status || "waiting").toLowerCase()}` : attempt.status.toLowerCase())); grid.append(card);
      }); section.append(grid);
    }
    host.append(section);
  }
  function review(host, round, readOnly = false) {
    const values = attempts(round); imageIndex = Math.max(0, Math.min(imageIndex, values.length - 1)); const attempt = values[imageIndex];
    const layout = node("section", undefined, "pg-review-layout"), left = node("div", undefined, "pg-image-column"), image = node("img");
    image.src = endpoint(`/images/${attempt.id}`); image.alt = `Round ${round.round}, image ${imageIndex + 1}, seed ${attempt.seed}`; image.title = "Click to enlarge"; image.tabIndex = 0;
    const zoom = () => { $("zoom-image").src = image.src; $("zoom").showModal(); };
    image.addEventListener("click", zoom); image.addEventListener("keydown", e => { if (e.key === "Enter") zoom(); }); left.append(image);
    const nav = node("div", undefined, "pg-image-nav");
    values.forEach((item, index) => {
      const b = button(`${index + 1}${item.human_correction?.confirmed ? " ✓" : ""}`, () => navigate(readOnly ? "history" : "image", readOnly ? round.id : "", index), nav);
      b.setAttribute("aria-label", `Image ${index + 1}${item.human_correction?.confirmed ? ", review confirmed" : ""}`); if (index === imageIndex) b.setAttribute("aria-current", "true");
    }); button("Enlarge image", zoom, nav, "pg-secondary"); left.append(nav);
    const right = node("div", undefined, "pg-review-column");
    right.append(node("h2", `${readOnly ? "History · " : ""}Image ${imageIndex + 1} of 4`), node("p", `${round.kind === "baseline" ? "Baseline" : `Round ${round.round}`} · Seed ${attempt.seed} · Criteria revision ${round.criteria_revision}`, "pg-muted"));
    if (round.approved_directions) {
      const changes = node("details"); changes.append(node("summary", "What changed in this round"), node("p", round.draft_summary || ""), node("p", round.approved_directions)); right.append(changes);
    }
    const evaluation = attempt.ai_evaluation || {}, key = `${attempt.id}:${round.criteria_revision}`;
    if (evaluation.summary) right.append(node("p", evaluation.summary, "pg-ai-summary"));
    let draft = drafts.get(key);
    if (!draft) {
      const human = attempt.human_correction?.criteria_revision === round.criteria_revision ? attempt.human_correction : null;
      draft = {criteria: (round.criteria_records || []).map(c => {
        const saved = human?.criteria?.find(s => s.id === c.id), chosen = saved?.chosen === true || human?.confirmed === true;
        return {id:c.id, result:chosen ? saved?.result || "" : "", chosen:Boolean(chosen && saved?.result), explanation:saved?.explanation || ""};
      }), notes:human?.notes || "", confirmed:human?.confirmed || false}; drafts.set(key, draft);
    }
    if (!readOnly) reviewForm = {draft, key, attemptId: attempt.id};
    for (const criterion of round.criteria_records || []) {
      const row = node("section", undefined, "pg-criterion"), ai = evaluation.criteria?.find(s => s.id === criterion.id), correction = draft.criteria.find(c => c.id === criterion.id);
      row.append(node("h3", criterion.text));
      const finding = node("p", undefined, "pg-ai-finding");
      if (ai) finding.append(node("span", `AI: ${ai.result.toUpperCase()}`, `pg-result-pill pg-result-${ai.result}`), node("span", ai.explanation));
      else finding.textContent = "AI evaluation not yet available.";
      row.append(finding);
      if (readOnly) {
        const conclusion = node("p"); conclusion.append(correction.result
          ? node("span", `You: ${correction.result.toUpperCase()}`, `pg-result-pill pg-result-${correction.result}`)
          : node("span", "Your conclusion: Not reviewed", "pg-muted"));
        if (correction.explanation) conclusion.append(node("span", ` ${correction.explanation}`)); row.append(conclusion);
      }
      else {
        const choices = node("fieldset", undefined, "pg-conclusion"); choices.setAttribute("aria-label", `Your conclusion: ${criterion.text}`); choices.append(node("legend", "Your conclusion"));
        for (const value of ["pass", "fail", "unclear"]) {
          const label = node("label", undefined, "pg-result-choice"), radio = node("input");
          radio.type = "radio"; radio.name = `pg-conclusion-${attempt.id}-${criterion.id}`; radio.value = value; radio.checked = correction.result === value;
          radio.addEventListener("change", () => { if (radio.checked) { correction.result = value; correction.chosen = true; editReview(); } });
          label.append(radio, node("span", value[0].toUpperCase() + value.slice(1), `pg-result-pill pg-result-${value}`)); choices.append(label);
        }
        row.append(choices);
        const why = node("textarea"); why.rows = 2; why.placeholder = "Correction or explanation (optional)"; why.setAttribute("aria-label", `Your explanation: ${criterion.text}`); why.value = correction.explanation;
        why.addEventListener("input", () => { correction.explanation = why.value; editReview(); }); row.append(why);
      } right.append(row);
    }
    if (readOnly) right.append(node("p", `Your notes: ${draft.notes || attempt.human_review?.notes || "None"}`));
    else {
      const label = node("label", "Your notes"), notes = node("textarea"); notes.rows = 3; notes.value = draft.notes;
      notes.addEventListener("input", () => { draft.notes = notes.value; editReview(); }); label.append(notes); right.append(label);
    }
    if (attempt.review_history?.length || attempt.evaluation_history?.length || round.assessment_history?.length) {
      const details = node("details"); details.append(node("summary", "Earlier evaluations and your corrections"), node("pre", JSON.stringify({evaluations:attempt.evaluation_history || [], reviews:attempt.review_history || [], assessments:round.assessment_history || []}, null, 2))); right.append(details);
    }
    if (!readOnly) {
      const footer = node("div", undefined, "pg-review-footer"), state = node("span", draft.confirmed ? "Review confirmed" : "Review not yet confirmed"); state.id = "pg-save-state"; state.setAttribute("aria-live", "polite"); footer.append(state);
      button("Save review", b => { dirty = true; return flushReview(false, b); }, footer, "pg-secondary");
      button("Confirm review and next image", async b => {
        if (!(await flushReview(true, b))) return;
        const next = attempts(currentRound()).findIndex(a => !a.human_correction?.confirmed);
        mode = next < 0 ? "round" : "image"; imageIndex = Math.max(0, next); paint(); message("Image review confirmed and saved.");
      }, footer); right.append(footer);
    }
    promptLink(right, round.id, "View this round’s prompt ↗");
    if (readOnly && attempt.human_correction?.confirmed && attempt.human_correction?.decision === "accept" && !["SCRAPPED", "CANCELLED"].includes(data.stage)) {
      const b = button(attempt.adopted_candidate_id ? "Already adopted" : "Adopt into empty batch slot", b => act("adopt", {round_id:round.id, attempt_id:attempt.id}, b, "Image adopted into an empty slot. Selection and locking remain separate."), right, "pg-secondary");
      if (attempt.adopted_candidate_id) { b.disabled = true; b.dataset.unavailable = "true"; }
    }
    layout.append(left, right); host.append(layout);
  }
  function roundReview(host) {
    const round = currentRound(), values = attempts(round), section = panel("Four-image round review", "Your confirmed conclusions guide the next round. Editing criteria will reassess these same four images before you continue.");
    const table = node("table"), header = node("tr"); for (const text of ["Criterion", "Pass", "Fail", "Unclear"]) header.append(node("th", text)); table.append(header);
    for (const criterion of round.criteria_records) { const row = node("tr"); row.append(node("td", criterion.text)); for (const result of ["pass", "fail", "unclear"]) row.append(node("td", String(values.filter(a => a.human_correction?.criteria?.some(c => c.id === criterion.id && c.result === result)).length))); table.append(row); }
    section.append(table, node("p", `${values.filter(a => a.human_correction?.decision === "accept").length} of 4 images accepted by your confirmed criteria.`));
    values.forEach((a, index) => { const row = node("div", undefined, "pg-round-result"); button(`Review image ${index + 1}`, () => navigate("image", "", index), row, "pg-secondary"); row.append(node("span", a.human_correction?.notes || "No additional notes.")); section.append(row); });
    const edit = node("details"); edit.append(node("summary", "Edit acceptance criteria and reassess")); criteriaEditor(edit); section.append(edit);
    section.append(node("p", "Approving the next round authorizes its AI directions, draft, four images and evaluations. Zet still pauses for your direction and draft approvals."));
    const actions = node("div", undefined, "pg-actions");
    button("Approve next round", b => act("next-round", {}, b, "Next round approved. Preparing suggested directions from your reviews."), actions);
    button("Finish run", b => act("finish", {}, b, "Run finished. Accepted images remain available under results."), actions, "pg-secondary"); section.append(actions); host.append(section);
  }
  function directions(host) {
    const section = panel("Review suggested directions", "Approve or edit what should change. Zet will write the render prompt from your approved directions."), proposal = data.directions;
    section.append(node("p", proposal.rationale || ""));
    if (proposal.preserve?.length) { section.append(node("h3", "Preserve")); const list = node("ul"); proposal.preserve.forEach(value => list.append(node("li", value))); section.append(list); }
    if (proposal.evidence_ids?.length) section.append(node("p", `Evidence: ${proposal.evidence_ids.map(id => `image ${attempts(currentRound()).findIndex(a => a.id === id) + 1}`).join(", ")}`, "pg-muted"));
    if (directionId !== proposal.id) { directionId = proposal.id; directionText = proposal.approved_text || proposal.direction || ""; }
    const input = node("textarea"); input.rows = 7; input.setAttribute("aria-label", "Directions for the next prompt"); input.value = directionText; input.addEventListener("input", () => { directionText = input.value; }); section.append(input);
    if (data.draft_feedback) section.append(node("p", `Your draft feedback: ${data.draft_feedback}`));
    button("Approve directions and generate draft", b => act("directions", {direction:input.value}, b, "Directions approved. Writing the next prompt."), section); host.append(section);
  }
  function draftApproval(host) {
    const section = panel("Approve the generated draft", data.active_draft.summary || "The generated prompt follows your approved directions.");
    section.append(node("h3", "Approved directions"), node("p", data.directions.approved_text), node("p", "Validation passed: packet identity, reference bindings and required compiler clauses."));
    promptLink(section, data.active_draft.id, "View generated prompt in a new tab ↗");
    button("Approve draft and render 4 images", b => act("approve", {draft_id:data.active_draft.id}, b, "Draft approved. Rendering four images; AI evaluations follow."), section);
    const feedback = node("textarea"); feedback.rows = 3; feedback.placeholder = "What should change before another draft?"; feedback.setAttribute("aria-label", "Draft feedback"); section.append(feedback);
    button("Revise directions", b => act("revise", {feedback:feedback.value}, b, "Returned to direction review. No new AI work has started."), section, "pg-secondary"); host.append(section);
  }
  function failure(host) {
    const section = panel("This step needs attention", data.error);
    if (data.failed_step === "render") for (const a of attempts(currentRound()).filter(a => a.status === "FAILED")) { section.append(node("p", `Seed ${a.seed}: ${a.error}`)); button(`Retry image · seed ${a.seed}`, b => act("retry-step", {attempt_id:a.id}, b, "Retry started. Completed images are preserved."), section); }
    else {
      for (const a of currentRound() ? attempts(currentRound()) : []) if (a.ai_evaluation?.error) section.append(node("p", `Seed ${a.seed}: ${a.ai_evaluation.error}`));
      button(`Retry ${data.failed_step || "failed step"}`, b => act("retry-step", {}, b, "Retry started for the failed step."), section);
    }
    if (data.failed_step === "draft") { promptLink(section, data.active_draft.id, "Inspect failed draft ↗"); button("Revise directions", b => act("revise", {}, b, "Returned to direction review."), section, "pg-secondary"); }
    host.append(section);
  }
  function paint() {
    reviewForm = null; paintHeader(); const host = $("workspace"); host.replaceChildren();
    if (mode === "history") { const round = data.history.find(r => r.id === roundId); if (round) review(host, round, true); else { mode = "current"; roundId = ""; } }
    if (mode !== "history") {
      if (data.stage === "SETUP") setup(host);
      else if (data.stage === "NEEDS_EVALUATION") {
        const section = panel("Continue your existing pilot", "Your images, scores, notes and diagnostics have been preserved. Evaluate this round to enter the guided cycle; no completed images will be replaced.");
        button("Evaluate existing round", b => act("evaluate", {}, b, "Existing round evaluation approved."), section); if (data.legacy_draft?.error) section.append(node("p", `Previous draft failure: ${data.legacy_draft.error}`)); host.append(section);
      } else if (active.has(data.stage)) progress(host);
      else if (data.stage === "REVIEW_ROUND" && mode !== "image") roundReview(host);
      else if (data.stage === "REVIEW_IMAGES" || data.stage === "REVIEW_ROUND") review(host, currentRound());
      else if (data.stage === "DIRECTIONS_REVIEW") directions(host);
      else if (data.stage === "DRAFT_REVIEW") draftApproval(host);
      else if (data.stage === "FAILED") failure(host);
      else if (terminal.has(data.stage)) {
        const section = panel(labels[data.stage], data.stage === "FINISHED" ? "Open a completed round to inspect results and separately adopt an accepted image." : "All evidence is retained as read-only history. Starting over will prepare fresh inputs without launching AI work.");
        for (const round of data.history) button(`View ${round.kind === "baseline" ? "baseline" : `round ${round.round}`} results`, () => navigate("history", round.id), section, "pg-secondary");
        button("Start over", b => act("restart", {}, b, "Fresh setup ready."), section); host.append(section);
      }
    }
    if (data.stage === "REVIEW_IMAGES" && mode !== "history") { const edit = node("details", undefined, "pg-criteria-edit"); edit.append(node("summary", "Edit acceptance criteria and reassess this round")); criteriaEditor(edit); host.append(edit); }
    updateUrl();
  }
  $("current").addEventListener("click", e => { e.preventDefault(); void navigate("current"); });
  $("close-zoom").addEventListener("click", () => $("zoom").close());
  window.addEventListener("beforeunload", e => { if (dirty) { e.preventDefault(); e.returnValue = ""; } });
  const back = new URLSearchParams({universe_id:universe, local_batch:runId}); if (costume) back.set("local_costume", costume); $("return").href = `/?${back}`;
  refresh();
})();
