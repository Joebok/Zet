/* Dedicated observation-led Character.md review and private trial workspace. */
(() => {
  const params = new URLSearchParams(location.search);
  const pipeline = params.get("pipeline") || "", runId = params.get("run_id") || "";
  const sessionId = params.get("session_id") || "", costume = params.get("costume") || "";
  const universe = params.get("universe_id") || "", page = params.get("page") || "";
  const $ = id => document.getElementById(`post-${id}`);
  let data, busy = false, refreshing = false;
  const query = () => { const q = new URLSearchParams({ universe_id: universe }); if (costume) q.set("costume", costume); return q; };
  const base = `/api/local/${encodeURIComponent(pipeline)}/runs/${encodeURIComponent(runId)}`;
  const endpoint = suffix => `${base}/post-render-prompt/${encodeURIComponent(sessionId)}${suffix || ""}?${query()}`;
  function returnUrl() {
    const q = new URLSearchParams({ page, local_batch: runId, universe_id: universe });
    if (costume) q.set("local_costume", costume);
    return `/?${q}`;
  }
  async function request(url, method = "GET", body) {
    const response = await fetch(url, { method, headers: { "Content-Type": "application/json", "X-Zet-Universe": universe },
      body: body === undefined ? undefined : JSON.stringify(body) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Prompt improvement request failed.");
    return result;
  }
  const el = (tag, value = "") => { const node = document.createElement(tag); node.textContent = value; return node; };
  function message(value, error = false) { $("message").textContent = value; $("message").classList.toggle("error", error); }
  async function act(operation, body = {}) {
    if (busy) return;
    busy = true;
    try { data = await request(endpoint(`/${operation}`), "POST", body); render(); }
    catch (error) { message(error.message, true); }
    finally { busy = false; }
  }
  function cardImage(candidateId) { return `${base}/images/${encodeURIComponent(candidateId)}?${query()}`; }
  function renderViews() {
    const host = $("views"), oldNotes = new Map([...host.querySelectorAll("textarea[data-view]")].map(node => [node.dataset.view, node.value]));
    const open = new Set([...host.querySelectorAll("details[open]")].map(node => node.dataset.view));
    const focused = document.activeElement?.matches?.("textarea[data-view]") ? document.activeElement : null;
    const focusedView = focused?.dataset.view, selection = focused ? [focused.selectionStart, focused.selectionEnd] : null;
    const galleryScroll = new Map([...host.querySelectorAll("section.control-panel")].map(section => [section.querySelector("details")?.dataset.view, section.querySelector(".post-view-gallery")?.scrollLeft || 0]));
    host.replaceChildren();
    for (const view of data.views) {
      const section = el("section"); section.className = "control-panel";
      section.append(el("h2", view.view.replaceAll("_", " ")));
      const gallery = el("div"); gallery.className = "post-view-gallery";
      for (const candidate of view.candidates.filter(item => item.image_available)) {
        const card = el("article"); card.className = "post-view-card";
        const img = el("img"); img.src = cardImage(candidate.candidate_id); img.alt = `${view.view} ${candidate.candidate_id}`; img.loading = "lazy";
        card.append(img, el("p", `${candidate.candidate_id}${candidate.selected ? " · selected" : ""}`));
        if (data.representatives.some(item => item.candidate_id === candidate.candidate_id)) card.append(el("strong", "Evidence for this view"));
        else if (["OBSERVING", "REVIEW_READY", "FAILED"].includes(data.status)) {
          const choose = el("button", "Use as evidence"); choose.type = "button";
          choose.addEventListener("click", () => void act("representative", { view: view.view, candidate_id: candidate.candidate_id }));
          card.append(choose);
        }
        gallery.append(card);
      }
      section.append(gallery); gallery.scrollLeft = galleryScroll.get(view.view) || 0;
      const details = el("details"); details.dataset.view = view.view; details.open = open.has(view.view);
      details.append(el("summary", "Observations"));
      const notes = el("textarea"); notes.rows = 4; notes.dataset.view = view.view;
      notes.value = oldNotes.has(view.view) ? oldNotes.get(view.view) : data.observations?.[view.view]?.observations || "";
      const label = el("label", "Your observations"); label.append(notes); details.append(label);
      const save = el("button", "Save observations"); save.type = "button";
      save.addEventListener("click", async () => {
        try { await request(`${base}/views/${encodeURIComponent(view.view)}/observations?${query()}`, "PUT", { observations: notes.value });
          message(`Observations saved for ${view.view}.`); await refresh(); }
        catch (error) { message(error.message, true); }
      });
      details.append(save);
      const ai = data.observations?.[view.view]?.ai_observations || {};
      details.append(el("h3", "AI Observations"), el("p", `${ai.status || "Pending"}${ai.error ? ` · ${ai.error}` : ""}${ai.stale_reason ? ` · ${ai.stale_reason}` : ""}`));
      if (ai.text) details.append(el("p", ai.text));
      const run = el("button", ai.status === "COMPLETE" ? "Run AI Observations again" : "Run AI Observations"); run.type = "button";
      run.disabled = ["QUEUED", "RUNNING"].includes(ai.status) || !view.candidates.some(item => item.image_available);
      run.addEventListener("click", async () => {
        try { await request(`${base}/views/${encodeURIComponent(view.view)}/reanalyze?${query()}`, "POST", {});
          message(`AI Observations started for ${view.view}.`); await refresh(); }
        catch (error) { message(error.message, true); }
      });
      details.append(run); section.append(details); host.append(section);
    }
    if (focusedView) {
      const next = [...host.querySelectorAll("textarea[data-view]")].find(node => node.dataset.view === focusedView);
      next?.focus({ preventScroll: true });
      if (next && selection) next.setSelectionRange(...selection);
    }
  }
  function renderAnalysis() {
    const host = $("analysis"); host.replaceChildren();
    const analysis = data.analysis || {};
    if (analysis.status) host.append(el("h3", `Review · ${analysis.status}`), el("p", analysis.error || analysis.summary || "Analyzing…"));
    if (data.status === "REVIEW_READY") {
      for (const item of analysis.findings || []) {
        const row = el("section"); row.className = "template-correction post-finding";
        const label = el("label"); label.className = "template-correction-choice";
        const check = el("input"); check.type = "checkbox"; check.value = item.id;
        check.setAttribute("aria-label", `Apply correction: ${item.rationale}`);
        check.checked = (analysis.selected_ids || []).includes(item.id);
        check.addEventListener("change", () => {
          const selected_ids = [...host.querySelectorAll("input:checked")].map(input => input.value);
          void request(endpoint("/decisions"), "POST", { selected_ids }).then(value => { data = value; renderDiff(); }).catch(error => message(error.message, true));
        });
        label.append(check);
        const content = el("div"); content.className = "template-correction-content";
        content.append(el("p", `${item.rationale} · ${item.views.join(", ")}`),
          el("p", "Before"), el("pre", item.before), el("p", "After"), el("pre", item.after));
        row.append(label, content); host.append(row);
      }
      if (!(analysis.findings || []).length) host.append(el("p", "No Character.md changes suggested. Add observations or direction and analyze again."));
    }
    $("trial").hidden = data.status !== "REVIEW_READY" || !(analysis.findings || []).length;
  }
  function renderTrials() {
    const section = $("results"), host = $("trial-cards"), attempts = data.trial?.attempts || [];
    section.hidden = !attempts.length; host.replaceChildren();
    for (const attempt of attempts) {
      const card = el("article"); card.className = "post-view-card";
      card.append(el("h3", `${attempt.view.replaceAll("_", " ")} · Trial ${attempt.number}`));
      if (attempt.status === "READY") {
        const img = el("img"); img.src = endpoint(`/images/${encodeURIComponent(attempt.id)}`); img.alt = `${attempt.view} trial ${attempt.number}`;
        card.append(img);
      }
      card.append(el("p", attempt.error || attempt.status));
      if (attempt.status === "FAILED") {
        const retry = el("button", "Retry render"); retry.type = "button";
        retry.addEventListener("click", () => void act("retry", { attempt_id: attempt.id })); card.append(retry);
      }
      host.append(card);
    }
    const ready = data.status === "TRIAL_READY" && attempts.every(item => item.status === "READY");
    $("keep").disabled = !ready && data.status !== "KEEPING"; $("refine").disabled = !ready;
  }
  function renderDiff() {
    const host = $("diff"); host.replaceChildren();
    host.append(el("h3", "Character.md: master → proposed"));
    if (!(data.diff_rows || []).length) {
      host.append(el("p", "Select suggestions to preview the source diff.")); return;
    }
    const frame = el("div"); frame.className = "post-template-diff";
    const table = el("table"); table.className = "template-diff-table";
    table.append(el("caption", "Changes from master to the selected proposal"));
    const columns = el("colgroup");
    for (const cls of ["template-diff-number", "template-diff-text", "template-diff-number", "template-diff-text"]) {
      const column = el("col"); column.className = cls; columns.append(column);
    }
    table.append(columns);
    const head = el("thead"), headings = el("tr");
    for (const label of ["Master baseline", "Proposed"]) {
      const cell = el("th", label); cell.colSpan = 2; cell.scope = "colgroup"; headings.append(cell);
    }
    head.append(headings); table.append(head);
    const body = el("tbody");
    for (const row of data.diff_rows) {
      const line = el("tr");
      if (row.kind === "gap") {
        const gap = el("td", "⋯ unchanged lines ⋯"); gap.className = "template-diff-gap"; gap.colSpan = 4; line.append(gap);
      } else for (const side of ["master", "proposed"]) {
        const number = row[`${side}_line`];
        const changed = row.kind !== "equal" && number != null;
        const cls = changed ? side === "master" ? "template-diff-removed" : "template-diff-added" : "";
        const gutter = el("td", number == null ? "" : String(number)); gutter.className = `template-diff-line-number ${cls}`;
        const code = el("td"); code.className = `template-diff-code ${cls}`;
        if (number != null) {
          const sign = el("span", changed ? side === "master" ? "− " : "+ " : "  "); sign.className = "template-diff-sign";
          code.append(sign, document.createTextNode(row[`${side}_text`]));
        } else code.classList.add("template-diff-empty");
        line.append(gutter, code);
      }
      body.append(line);
    }
    table.append(body); frame.append(table); host.append(frame);
  }
  function render() {
    if (!data) return;
    if (data.status === "CANCELLED") { message("Improvement cancelled. Saved observations remain."); return; }
    $("title").textContent = `${data.view || data.views?.[0]?.view || "View"} · Post Render Adjustments`;
    renderViews(); renderAnalysis(); renderDiff(); renderTrials();
    $("propose").disabled = !["OBSERVING", "TRIAL_READY", "REVIEW_READY", "FAILED"].includes(data.status);
    $("cancel").disabled = ["CANCELLED", "KEPT", "KEEPING"].includes(data.status);
    if (data.status === "KEPT") message("Character.md updated and batch prompts recompiled. Return to the batch.");
    else if (data.status === "KEEPING") message(`Finalizing template change: ${data.error || "in progress"}`, Boolean(data.error));
    else if (data.status === "CANCELLED") message("Improvement cancelled. Saved observations remain.");
    else if (data.error) message(data.error, true);
  }
  async function refresh() {
    if (refreshing || busy) return;
    refreshing = true;
    try { data = await request(endpoint()); render(); }
    catch (error) { message(error.message, true); }
    finally { refreshing = false; }
  }
  $("return").href = returnUrl();
  $("propose").addEventListener("click", () => void act("propose", { direction: $("direction").value }));
  $("refine").addEventListener("click", () => { $("direction").focus(); message("Add or revise observations, then suggest another round of edits."); });
  $("trial").addEventListener("click", () => void act("trial", { selected_ids: [...$("analysis").querySelectorAll("input:checked")].map(input => input.value) }));
  $("keep").addEventListener("click", async () => { await act("keep"); if (data?.status === "KEPT") location.href = returnUrl(); });
  $("cancel").addEventListener("click", async () => { await act("cancel"); if (data?.status === "CANCELLED") location.href = returnUrl(); });
  void refresh(); setInterval(() => {
    const aiPending = Object.values(data?.observations || {}).some(review => ["QUEUED", "RUNNING"].includes(review?.ai_observations?.status));
    if (["ANALYZING", "TRIAL_RUNNING", "KEEPING"].includes(data?.status) || aiPending) void refresh();
  }, 2500);
})();
