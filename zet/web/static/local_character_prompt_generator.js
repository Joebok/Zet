/* Packet-bound local-character prompt generator pilot. */
(() => {
  const q = new URLSearchParams(location.search);
  const pipeline = q.get("pipeline") || "", runId = q.get("run_id") || "";
  const sessionId = q.get("session_id") || "", costume = q.get("costume") || "";
  const universe = q.get("universe_id") || "";
  const $ = id => document.getElementById(`pg-${id}`);
  const root = `/api/local/${encodeURIComponent(pipeline)}/runs/${encodeURIComponent(runId)}/prompt-generator`;
  const query = () => { const value = new URLSearchParams({ universe_id: universe }); if (costume) value.set("costume", costume); return value; };
  const endpoint = suffix => `${root}/${encodeURIComponent(sessionId)}${suffix || ""}?${query()}`;
  let data, busy = false, editStartedAt = 0, originalPrompt = "", viewedDraftId = "";
  let baselinePromptPacketHash = "", baselineOriginal = "", baselineEditStartedAt = 0;
  const reviewStarted = new Map();
  async function request(url, method = "GET", body) {
    const response = await fetch(url, { method, headers: { "Content-Type": "application/json", "X-Zet-Universe": universe },
      body: body === undefined ? undefined : JSON.stringify(body) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Prompt generator request failed.");
    return result;
  }
  function message(text, error = false) { $("message").textContent = text; $("message").classList.toggle("error", error); }
  function addJsonBlock(host, title, value) {
    const details = document.createElement("details"), summary = node("summary", title), pre = node("pre", JSON.stringify(value ?? {}, null, 2));
    details.append(summary, pre); host.append(details);
  }
  async function act(operation, body = {}) {
    if (busy) return;
    busy = true;
    try { data = await request(endpoint(`/${operation}`), "POST", body); paint(); }
    catch (error) { message(error.message, true); }
    finally { busy = false; }
  }
  function node(tag, value) { const item = document.createElement(tag); item.textContent = value; return item; }
  function paintPacket() {
    const p = data.packet; $("context").textContent = `${p.pipeline} · ${p.view}${p.costume ? ` · ${p.costume}` : ""}`;
    const host = $("packet"); host.replaceChildren();
    host.append(node("p", `Packet ${p.packet_hash.slice(0, 16)} · operation: ${p.operation}`));
    host.append(node("p", `Fixed seed set: ${(data.seeds || []).join(", ")} · 4 baseline renders · up to 3 four-seed trial rounds`));
    addJsonBlock(host, "Compiler facts", p.facts);
    addJsonBlock(host, "Source identities and hashes", p.sources);
    addJsonBlock(host, "Required constraints", p.required_constraints);
    addJsonBlock(host, "Render preset and settings", { preset: p.render_preset, settings: p.render_settings });
    addJsonBlock(host, "Frozen instruction modules", p.instruction_modules);
    if (p.direction) addJsonBlock(host, "Human direction for this revision", p.direction);
    if (p.prior_attempts && Object.keys(p.prior_attempts).length) addJsonBlock(host, "Prior trial context", p.prior_attempts);
    if (p.direction && !$("direction").value) $("direction").value = p.direction;
    host.append(node("h3", "Render references"));
    for (const ref of p.references || []) host.append(node("p", `Image ${ref.render_index}: ${ref.label || ref.role} · ${ref.role} · ${ref.sha256?.slice(0, 12) || "no hash"}`));
    host.append(node("h3", "Generator analysis references"));
    for (const ref of p.analysis_references || []) host.append(node("p", `${ref.label || ref.id} · ${ref.role}`));
    $("criteria").value = (p.criteria || []).join("\n");
    if (baselinePromptPacketHash !== p.packet_hash) {
      baselinePromptPacketHash = p.packet_hash;
      const value = data.manual_baseline_prompt_packet_hash === p.packet_hash ? data.manual_baseline_prompt : p.baseline_prompt;
      $("baseline-prompt").value = value || ""; baselineOriginal = value || ""; baselineEditStartedAt = 0;
    }
  }
  function paintHistory() {
    const host = $("history"); host.replaceChildren();
    for (const round of data.history || []) {
      const section = node("section", ""); section.className = "control-panel";
      section.append(node("h3", `${round.kind === "baseline" ? "Baseline" : `Trial round ${round.round}`} · ${new Set(round.attempts.map(item => item.seed)).size} seeds · ${round.attempts.length} submissions`));
      for (const attempt of round.attempts) {
        if (attempt.status === "READY" && !reviewStarted.has(attempt.id)) reviewStarted.set(attempt.id, Date.now());
        const card = node("article", ""); card.className = "post-view-card prompt-generator-card";
        card.append(node("p", `Seed ${attempt.seed} · ${attempt.status}${attempt.error ? ` · ${attempt.error}` : ""}`));
        if (attempt.status === "READY") {
          const layout = node("div", ""); layout.className = "pg-review-layout";
          const imageColumn = node("div", ""); imageColumn.className = "pg-review-image";
          const scoringColumn = node("div", ""); scoringColumn.className = "pg-review-scoring";
          const img = document.createElement("img"); img.src = endpoint(`/images/${encodeURIComponent(attempt.id)}`); img.alt = `Seed ${attempt.seed}`; img.loading = "lazy"; imageColumn.append(img);
          const adopt = node("button", "Adopt into empty batch slot"); adopt.type = "button";
          adopt.addEventListener("click", () => void act("adopt", { round_id: round.id, attempt_id: attempt.id })); imageColumn.append(adopt);
          const editBase = node("button", "Use as edit base for a new packet revision"); editBase.type = "button";
          editBase.addEventListener("click", () => void act("edit-base", { round_id: round.id, attempt_id: attempt.id })); imageColumn.append(editBase);
          const outcomes = [];
          const criteria = round.criterion_sets?.length
            ? round.criterion_sets.flatMap(set => (set.criteria || []).map(criterion => `${set.version}: ${criterion}`))
            : (round.criteria || data.packet.criteria || []);
          for (const criterion of criteria) {
            const label = node("label", `${criterion}: `);
            const select = document.createElement("select");
            for (const [value, text] of [["", "Unscored"], ["pass", "Pass"], ["fail", "Fail"], ["unclear", "Unclear"]]) {
              const option = node("option", text); option.value = value; select.append(option);
            }
            label.append(select); scoringColumn.append(label); outcomes.push({ criterion, select });
          }
          const notes = document.createElement("textarea"); notes.rows = 3; notes.placeholder = "Notes on this image"; scoringColumn.append(notes);
          for (const decision of ["accept", "reject"]) {
            const review = node("button", decision === "accept" ? "Accept image" : "Reject image"); review.type = "button";
            review.addEventListener("click", () => void act("review", { round_id: round.id, attempt_id: attempt.id,
              decision, notes: notes.value, review_seconds: Math.round((Date.now() - reviewStarted.get(attempt.id)) / 1000),
              criteria: outcomes.map(x => ({ criterion: x.criterion, result: x.select.value })).filter(x => x.result) }));
            scoringColumn.append(review);
          }
          if (attempt.human_review?.decision) scoringColumn.append(node("p", `Recorded: ${attempt.human_review.decision}${attempt.human_review.notes ? ` · ${attempt.human_review.notes}` : ""}`));
          layout.append(imageColumn, scoringColumn); card.append(layout);
        }
        if (attempt.status === "FAILED") {
          const retry = node("button", "Retry this seed using its frozen prompt and settings"); retry.type = "button";
          retry.disabled = !data.live_authorized_at || data.render_submissions >= 16 || data.status === "RENDERING";
          retry.addEventListener("click", () => void act("retry", { round_id: round.id, attempt_id: attempt.id })); card.append(retry);
        }
        section.append(card);
      }
      host.append(section);
    }
  }
  function paint() {
    paintPacket(); paintHistory();
    const draft = data.active_draft || {};
    const feedback = $("feedback-round"), selectedFeedback = feedback.value;
    feedback.replaceChildren(node("option", "No prior trial images")); feedback.options[0].value = "";
    for (const round of data.history.filter(item => item.kind === "trial" && item.attempts.some(attempt => attempt.status === "READY"))) {
      const option = node("option", `Trial round ${round.round} · ${round.attempts.filter(attempt => attempt.status === "READY").length} completed images`);
      option.value = round.id; feedback.append(option);
    }
    if ([...feedback.options].some(option => option.value === selectedFeedback)) feedback.value = selectedFeedback;
    const model = $("model"), previous = model.value; model.replaceChildren();
    for (const item of data.model_options || []) {
      const option = node("option", `${item.label} (${item.provider})`); option.value = item.id;
      model.append(option);
    }
    const preferred = previous || data.default_model;
    if ([...model.options].some(option => option.value === preferred)) model.value = preferred;
    $("escalate").disabled = data.higher_tier_available;
    $("escalation-state").textContent = data.higher_tier_available ? "Higher-tier Codex models enabled after explicit escalation request or repeated failures." : "Higher-tier Codex models remain unavailable until requested or repeated constraint failures.";
    if (draft.prompt) $("prompt").value = draft.prompt;
    if (draft.id !== viewedDraftId) { viewedDraftId = draft.id || ""; originalPrompt = draft.prompt || ""; editStartedAt = 0; }
    const completed = data.history.flatMap(round => round.attempts).filter(item => item.status === "READY").length;
    const elapsed = Math.max(0, Math.round((Date.now() - Date.parse(data.created_at)) / 1000));
    const editSeconds = (data.manual_edits || []).reduce((sum, item) => sum + (item.elapsed_seconds || 0), 0);
    const editCharacters = (data.manual_edits || []).reduce((sum, item) => sum + (item.edit_volume_characters || 0), 0);
    const reviewSeconds = data.history.flatMap(round => round.attempts).reduce((sum, item) => sum + (item.human_review?.review_seconds || 0), 0);
    const runtime = draft.runtime || {};
    const usage = Object.fromEntries(Object.entries(runtime).filter(([key, value]) => /token|usage/i.test(key) && (typeof value === "number" || typeof value === "string")));
    $("usage").textContent = `${data.llm_calls}/12 case LLM calls · ${data.render_submissions}/16 case render submissions · ${completed} completed images · ${data.pilot_totals.llm_calls}/36 pilot LLM calls · ${data.pilot_totals.render_submissions}/48 pilot render submissions · ${data.pilot_totals.case_count}/3 cases · ${elapsed}s elapsed · ${editSeconds}s prompt editing / ${editCharacters} changed characters · ${reviewSeconds}s image review · reported usage ${JSON.stringify(usage)} · status ${data.status}`;
    $("authorize").disabled = Boolean(data.live_authorized_at);
    $("authorized").textContent = data.live_authorized_at ? `Authorized ${data.live_authorized_at}` : "Not authorized";
    $("draft").disabled = !data.live_authorized_at || data.llm_calls >= 12 || !model.options.length || ["DRAFTING", "RENDERING"].includes(data.status);
    $("baseline").disabled = !data.live_authorized_at || data.render_submissions >= 16 || data.history.some(item => item.kind === "baseline")
      || !(data.packet.criteria || []).length || data.manual_baseline_prompt_packet_hash !== data.packet.packet_hash;
    $("approve").disabled = draft.status !== "READY" || Boolean(draft.approved);
    $("trial").disabled = !data.live_authorized_at || !draft.approved || data.render_submissions >= 16 || data.status === "RENDERING";
    message(draft.error || data.error || "Packet and trial inputs are frozen for this session.", Boolean(draft.error || data.error));
    const decisions = $("decisions"); decisions.replaceChildren();
    for (const item of data.decisions || []) decisions.append(node("p", `${item.destination}: ${item.text} · ${item.status}`));
  }
  async function refresh() {
    try {
      data = await request(endpoint()); paint();
      if (["DRAFTING", "RENDERING"].includes(data.status)) setTimeout(refresh, 1500);
    } catch (error) { message(error.message, true); }
  }
  $("draft").addEventListener("click", () => void act("draft", { direction: $("direction").value, model: $("model").value,
    feedback_round_id: $("feedback-round").value }));
  $("escalate").addEventListener("click", () => void act("escalate", { reason: $("escalation-reason").value }));
  $("authorize").addEventListener("click", () => {
    if (confirm("Authorize up to 12 LLM calls and 16 render submissions for this case, within the 36-call and 48-render pilot totals?"))
      void act("authorize", { confirm: true });
  });
  $("save-criteria").addEventListener("click", () => void act("criteria", { criteria: $("criteria").value.split(/\r?\n/).map(x => x.trim()).filter(Boolean) }));
  $("baseline-prompt").addEventListener("input", () => { if (!baselineEditStartedAt) baselineEditStartedAt = Date.now(); });
  $("save-baseline-prompt").addEventListener("click", () => {
    const next = $("baseline-prompt").value;
    const changed = Math.abs(next.length - baselineOriginal.length) + [...next].filter((char, index) => char !== baselineOriginal[index]).length;
    void act("edit-baseline", { prompt: next, elapsed_seconds: baselineEditStartedAt ? Math.round((Date.now() - baselineEditStartedAt) / 1000) : 0,
      edit_volume_characters: changed });
    baselineOriginal = next; baselineEditStartedAt = 0;
  });
  $("baseline").addEventListener("click", () => void act("render", { kind: "baseline" }));
  $("prompt").addEventListener("input", () => { if (!editStartedAt) editStartedAt = Date.now(); });
  $("save").addEventListener("click", () => {
    const next = $("prompt").value;
    const changed = Math.abs(next.length - originalPrompt.length) + [...next].filter((char, index) => char !== originalPrompt[index]).length;
    const elapsed_seconds = editStartedAt ? Math.round((Date.now() - editStartedAt) / 1000) : 0;
    void act("edit", { prompt: next, elapsed_seconds, edit_volume_characters: changed });
    originalPrompt = next; editStartedAt = 0;
  });
  $("approve").addEventListener("click", () => void act("approve", { packet_hash: data.packet.packet_hash }));
  $("trial").addEventListener("click", () => void act("render", { kind: "trial" }));
  $("decision-save").addEventListener("click", () => void act("decision", { destination: $("decision-destination").value, text: $("decision-text").value }));
  const back = new URLSearchParams({ universe_id: universe, local_batch: runId }); if (costume) back.set("local_costume", costume);
  $("return").href = `/?${back}`;
  refresh();
})();
