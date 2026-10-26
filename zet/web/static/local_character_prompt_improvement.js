/* Dedicated observation-led Character.md review and private trial workspace. */
(() => {
  const params = new URLSearchParams(location.search);
  const pipeline = params.get("pipeline") || "", runId = params.get("run_id") || "";
  const sessionId = params.get("session_id") || "", costume = params.get("costume") || "";
  const universe = params.get("universe_id") || "", page = params.get("page") || "";
  const $ = id => document.getElementById(`post-${id}`);
  let data, busy = false, refreshing = false, deciding = false, criteriaSaving = false, responseVersion = 0;
  const isCostume = pipeline === "costume-dressing";
  let criteriaDraft = null, criteriaRevision = 0, criteriaDirty = false;
  let criteriaStatus = "", criteriaStatusError = false, criteriaInvalidIndex = null;
  let suggestionStatus = "", suggestionStatusError = false;
  let viewerAttemptId = "", viewerOriginId = "";
  const sourceLabel = () => data?.source_label || "Character.md";
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
  function inlineStatus(id, value, error = false) {
    const target = $(id);
    target.textContent = value;
    target.classList.toggle("error", error);
  }
  async function act(operation, body = {}) {
    if (busy) return;
    busy = true;
    responseVersion += 1;
    let succeeded = true;
    try { data = await request(endpoint(`/${operation}`), "POST", body); render(); }
    catch (error) { succeeded = false; message(error.message, true); }
    finally { busy = false; render(); }
    return succeeded;
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
        responseVersion += 1;
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
        responseVersion += 1;
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
        check.dataset.findingChoice = item.id;
        row.dataset.findingId = item.id;
        check.setAttribute("aria-label", `Apply correction: ${item.rationale}`);
        check.checked = (analysis.selected_ids || []).includes(item.id);
        check.addEventListener("change", () => void saveDecisions());
        label.append(check);
        const content = el("div"); content.className = "template-correction-content";
        content.append(el("p", `${item.rationale} · ${item.views.join(", ")}`),
          el("p", "Before"), el("pre", item.before), el("p", "After"), el("pre", item.after));
        if (isCostume) {
          content.append(el("p", `Criteria: ${(item.criteria_ids || []).join(", ")}. ${item.scope_note || ""}`));
          for (const [key, title, values, selected] of [
            ["views", "Affected views", data.all_views, item.selected_views],
            ["modes", "Rendering modes", data.render_modes, item.selected_modes],
          ]) {
            const group = el("fieldset"); group.className = "post-scope"; group.append(el("legend", title));
            for (const value of values) {
              const choice = el("input"); choice.type = "checkbox"; choice.value = value; choice.dataset.scope = key;
              choice.checked = (selected || []).includes(value);
              choice.addEventListener("change", () => void saveDecisions());
              const option = el("label", value.replaceAll("_", " ")); option.prepend(choice); group.append(option);
            }
            content.append(group);
          }
        }
        row.append(label, content); host.append(row);
      }
      if (!(analysis.findings || []).length) host.append(el("p", `No ${sourceLabel()} changes suggested. Add observations or direction and analyze again.`));
    }
    $("trial").hidden = data.status !== "REVIEW_READY" || !(analysis.findings || []).length;
    $("trial").disabled = deciding || !(analysis.selected_ids || []).length;
  }
  async function saveDecisions() {
    if (deciding) return;
    deciding = true; $("trial").disabled = true;
    responseVersion += 1;
    const rows = [...$("analysis").querySelectorAll("[data-finding-id]")];
    const selected = rows.filter(row => row.querySelector("[data-finding-choice]").checked);
    const payload = isCostume ? {expected_revision: data.revision, choices: selected.map(row => ({id: row.dataset.findingId,
      views: [...row.querySelectorAll('[data-scope="views"]:checked')].map(input => input.value),
      modes: [...row.querySelectorAll('[data-scope="modes"]:checked')].map(input => input.value)}))}
      : {selected_ids: selected.map(row => row.dataset.findingId)};
    for (const input of $("analysis").querySelectorAll("input")) input.disabled = true;
    try { data = await request(endpoint("/decisions"), "POST", payload); renderDiff(); }
    catch (error) { message(error.message, true); renderAnalysis(); }
    finally {
      deciding = false;
      for (const input of $("analysis").querySelectorAll("input")) input.disabled = false;
      $("trial").disabled = !(data.analysis?.selected_ids || []).length;
    }
  }
  function renderCriteria() {
    $("criteria-section").hidden = !isCostume;
    if (!isCostume || criteriaDirty) return;
    criteriaDraft = structuredClone(data.criteria.items); criteriaRevision = data.criteria.revision;
    drawCriteria();
    inlineStatus("criteria-status", criteriaStatus, criteriaStatusError);
  }
  function drawCriteria() {
    const host = $("criteria"); host.replaceChildren();
    for (const [index, item] of criteriaDraft.entries()) {
      const row = el("div"); row.className = "post-criterion";
      if (item.id) row.dataset.criterionId = item.id;
      const status = el("input"); status.type = "checkbox"; status.checked = item.status === "accomplished";
      status.disabled = criteriaSaving;
      status.setAttribute("aria-label", `Accomplished: ${item.text || "new criterion"}`);
      status.addEventListener("change", () => { item.status = status.checked ? "accomplished" : "in_progress"; criteriaDirty = true; });
      const text = el("input"); text.type = "text"; text.maxLength = 4000; text.value = item.text;
      text.readOnly = item.status === "accomplished";
      text.disabled = criteriaSaving;
      if (criteriaInvalidIndex === index) text.setAttribute("aria-invalid", "true");
      text.setAttribute("aria-label", "Acceptance criterion");
      text.addEventListener("input", () => {
        item.text = text.value; criteriaDirty = true;
        criteriaInvalidIndex = null;
        text.removeAttribute("aria-invalid");
        if (criteriaStatusError) { criteriaStatus = ""; criteriaStatusError = false; inlineStatus("criteria-status", ""); }
      });
      row.append(status, text); host.append(row);
    }
    $("add-criterion").disabled = criteriaSaving;
    $("save-criteria").disabled = criteriaSaving;
    inlineStatus("criteria-status", criteriaStatus, criteriaStatusError);
  }
  async function saveCriteria() {
    if (busy || criteriaSaving) {
      criteriaStatus = "Wait for the current request to finish before saving criteria.";
      criteriaStatusError = true;
      inlineStatus("criteria-status", criteriaStatus, true);
      return;
    }
    const rows = [...$("criteria").querySelectorAll(".post-criterion")];
    const submitted = rows.map(row => ({row, id: row.dataset.criterionId || "",
      text: row.querySelector('input[type="text"]').value, status: row.querySelector('input[type="checkbox"]').checked ? "accomplished" : "in_progress"}));
    const items = submitted.filter(item => item.id || item.text.trim());
    const invalid = items.find(item => !item.text.trim() || item.text.length > 4000);
    if (!items.length || invalid) {
      const row = invalid?.row || rows.find(item => !item.querySelector('input[type="text"]').value.trim());
      criteriaInvalidIndex = rows.indexOf(row);
      const field = row?.querySelector('input[type="text"]');
      field?.setAttribute("aria-invalid", "true");
      field?.focus();
      criteriaStatus = invalid ? "Enter text for every saved criterion (maximum 4,000 characters)." : "Enter a criterion before saving.";
      criteriaStatusError = true;
      inlineStatus("criteria-status", criteriaStatus, true);
      return;
    }
    criteriaInvalidIndex = null;
    for (const item of submitted) item.row.querySelector('input[type="text"]').removeAttribute("aria-invalid");
    const payloadRows = items.map(item => item.row);
    const payload = {expected_revision: criteriaRevision,
      items: items.map(({id, text, status}) => ({...(id ? {id} : {}), text: text.trim(), status}))};
    criteriaSaving = true;
    busy = true;
    responseVersion += 1;
    criteriaStatus = "Saving acceptance criteria…";
    criteriaStatusError = false;
    drawCriteria();
    try {
      data.criteria = await request(`${base}/views/${encodeURIComponent(data.view)}/acceptance-criteria?${query()}`, "PUT", payload);
      criteriaDirty = false; renderCriteria(); message("Acceptance criteria saved for this costume and view.");
      criteriaStatus = "Acceptance criteria saved for this costume and view.";
      criteriaStatusError = false;
    } catch (error) {
      message(error.message, true);
      const match = error.message.match(/criterion\s+(\d+)/i);
      const badRow = match ? payloadRows[Number(match[1]) - 1] : null;
      criteriaInvalidIndex = badRow ? Number(match[1]) - 1 : null;
      const field = badRow?.querySelector('input[type="text"]');
      field?.setAttribute("aria-invalid", "true");
      criteriaStatus = error.message;
      criteriaStatusError = true;
    } finally {
      criteriaSaving = false;
      busy = false;
      drawCriteria();
      inlineStatus("criteria-status", criteriaStatus, criteriaStatusError);
    }
  }
  function readyTrials() { return (data?.trial?.attempts || []).filter(attempt => attempt.status === "READY"); }
  function showPrompt(attempt) {
    $("prompt-title").textContent = `${attempt.view.replaceAll("_", " ")} · Trial ${attempt.number} generation prompt`;
    $("prompt-text").textContent = attempt.prompt || "The saved generation prompt is unavailable for this trial.";
    $("prompt-dialog").showModal();
  }
  function renderViewer() {
    const attempts = readyTrials(), index = attempts.findIndex(attempt => attempt.id === viewerAttemptId);
    if (index < 0) { $("viewer").close(); return; }
    const attempt = attempts[index];
    $("viewer-title").textContent = `${attempt.view.replaceAll("_", " ")} · Trial ${attempt.number} · ${index + 1} of ${attempts.length}`;
    const image = $("viewer-image"), url = endpoint(`/images/${encodeURIComponent(attempt.id)}`);
    if (image.getAttribute("src") !== url) image.src = url;
    image.alt = `${attempt.view} trial ${attempt.number}`;
    $("viewer-previous").disabled = index === 0;
    $("viewer-next").disabled = index === attempts.length - 1;
  }
  function moveViewer(step) {
    const attempts = readyTrials(), index = attempts.findIndex(attempt => attempt.id === viewerAttemptId);
    const next = attempts[index + step];
    if (next) { viewerAttemptId = next.id; renderViewer(); }
  }
  function renderTrials() {
    const section = $("results"), host = $("trial-cards"), attempts = data.trial?.attempts || [];
    section.hidden = !attempts.length; host.replaceChildren();
    for (const attempt of attempts) {
      const card = el("article"); card.className = "post-view-card";
      card.append(el("h3", `${attempt.view.replaceAll("_", " ")} · Trial ${attempt.number}`));
      if (attempt.status === "READY") {
        const img = el("img"); img.src = endpoint(`/images/${encodeURIComponent(attempt.id)}`); img.alt = `${attempt.view} trial ${attempt.number}`;
        const expand = el("button"); expand.type = "button"; expand.className = "post-trial-expand";
        expand.dataset.trialId = attempt.id;
        expand.setAttribute("aria-label", `Expand ${attempt.view} trial ${attempt.number}`);
        expand.addEventListener("click", () => {
          viewerAttemptId = attempt.id; viewerOriginId = attempt.id; renderViewer(); $("viewer").showModal();
        });
        expand.append(img); card.append(expand);
      }
      const prompt = el("button", "View generation prompt"); prompt.type = "button"; prompt.className = "post-prompt-link";
      prompt.addEventListener("click", () => showPrompt(attempt)); card.append(prompt);
      card.append(el("p", attempt.error || attempt.status));
      if (attempt.status === "FAILED") {
        const retry = el("button", "Retry render"); retry.type = "button";
        retry.addEventListener("click", () => void act("retry", { attempt_id: attempt.id })); card.append(retry);
      }
      host.append(card);
    }
    if ($("viewer").open) renderViewer();
    const assessment = data.trial?.assessment;
    $("assessment").replaceChildren();
    if (isCostume && assessment) {
      $("assessment").append(el("h3", "AI acceptance assessment · advisory"), el("p", assessment.error || assessment.summary || assessment.status));
      for (const item of assessment.items || []) $("assessment").append(el("p", `${data.criteria.items.find(c => c.id === item.criterion_id)?.text || item.criterion_id}: ${item.assessment} — ${item.evidence}`));
      if (assessment.status === "FAILED") {
        const retry = el("button", "Retry assessment"); retry.type = "button";
        retry.addEventListener("click", () => void act("retry", {evaluation: true})); $("assessment").append(retry);
      }
    }
    const ready = data.status === "TRIAL_READY" && attempts.every(item => item.status === "READY");
    $("keep").disabled = !ready && data.status !== "KEEPING"; $("refine").disabled = !ready;
  }
  function renderDiff() {
    const host = $("diff"); host.replaceChildren();
    host.append(el("h3", `${sourceLabel()}: session baseline → cumulative proposal`));
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
    if (isCostume && JSON.stringify(data.master_diff_rows) !== JSON.stringify(data.diff_rows)) {
      const master = el("details"); master.append(el("summary", "Complete master → proposed changes (includes existing batch costume edits)"));
      const changes = (data.master_diff_rows || []).filter(row => row.kind !== "equal" && row.kind !== "gap");
      master.append(el("pre", changes.map(row => `${row.master_text ? `− ${row.master_text}\n` : ""}${row.proposed_text ? `+ ${row.proposed_text}` : ""}`).join("\n")));
      host.append(master);
    }
  }
  function render() {
    if (!data) return;
    if (data.status === "CANCELLED") { message("Improvement cancelled. Saved observations remain."); return; }
    $("title").textContent = `${data.view || data.views?.[0]?.view || "View"} · Post Render Adjustments`;
    if (isCostume) {
      const settings = data.render_settings;
      $("explanation").textContent = `${sourceLabel()} · ${settings.mode} · ${settings.mode !== "doll-dressing-no-ref" && settings.costume_reference_view ? `costume reference ${settings.costume_reference_view}` : "matching Assembly only"}. Review scoped costume edits and four private target-view trials.`;
      $("suggestion-title").textContent = "Costume template suggestions";
      $("propose").textContent = "Suggest costume template edits";
      $("keep").textContent = "Save reviewed costume template to master";
      $("trial-explanation").textContent = "Four private target-view renders reuse this session’s seeds across rounds. They do not enter the batch gallery. Mark accomplished criteria yourself after reviewing the images.";
    }
    renderViews(); renderCriteria(); renderAnalysis(); renderDiff(); renderTrials();
    if (data.analysis?.status === "FAILED") {
      suggestionStatus = data.analysis.error || "Suggestion analysis failed.";
      suggestionStatusError = true;
    } else if (data.status === "ANALYZING" || ["QUEUED", "RUNNING"].includes(data.analysis?.status)) {
      suggestionStatus = "Analyzing the selected image and unfinished criteria…";
      suggestionStatusError = false;
    } else if (data.status === "REVIEW_READY") {
      const count = data.analysis?.findings?.length || 0;
      suggestionStatus = count ? `${count} costume template suggestion${count === 1 ? "" : "s"} ready for review.`
        : "No edits were suggested. Add observations or direction, then try again.";
      suggestionStatusError = false;
    }
    inlineStatus("suggestion-status", suggestionStatus, suggestionStatusError);
    $("history-items").replaceChildren(...(data.history || []).map(item => el("p", `Round ${item.round} · ${item.trial_id}`)));
    $("propose").disabled = busy || !["OBSERVING", "TRIAL_READY", "REVIEW_READY", "FAILED"].includes(data.status);
    $("cancel").disabled = ["CANCELLED", "KEPT", "KEEPING"].includes(data.status);
    if (data.status === "KEPT") message(`${sourceLabel()} updated and available batch prompts recompiled. Return to the batch.`);
    else if (data.status === "KEEPING") message(`Finalizing template change: ${data.error || "in progress"}`, Boolean(data.error));
    else if (data.status === "CANCELLED") message("Improvement cancelled. Saved observations remain.");
    else if (data.error) message(data.error, true);
  }
  async function refresh() {
    if (refreshing || busy || deciding) return;
    refreshing = true;
    const requestedVersion = responseVersion;
    try {
      const latest = await request(endpoint());
      if (requestedVersion === responseVersion) { data = latest; render(); }
    }
    catch (error) { message(error.message, true); }
    finally { refreshing = false; }
  }
  $("return").href = returnUrl();
  $("viewer-close").addEventListener("click", () => $("viewer").close());
  $("viewer-previous").addEventListener("click", () => moveViewer(-1));
  $("viewer-next").addEventListener("click", () => moveViewer(1));
  $("viewer-prompt").addEventListener("click", () => {
    const attempt = readyTrials().find(item => item.id === viewerAttemptId);
    if (attempt) showPrompt(attempt);
  });
  $("viewer").addEventListener("keydown", event => {
    if ($("prompt-dialog").open) return;
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault(); moveViewer(event.key === "ArrowLeft" ? -1 : 1);
    }
  });
  $("viewer").addEventListener("close", () => {
    [...$("trial-cards").querySelectorAll("[data-trial-id]")].find(node => node.dataset.trialId === viewerOriginId)?.focus({preventScroll: true});
    viewerAttemptId = "";
  });
  $("prompt-close").addEventListener("click", () => $("prompt-dialog").close());
  $("propose").addEventListener("click", () => {
    if (criteriaDirty) {
      criteriaStatus = "Save acceptance criteria before suggesting costume template edits.";
      criteriaStatusError = true;
      inlineStatus("criteria-status", criteriaStatus, true);
      $("save-criteria").focus();
      $("criteria-section").scrollIntoView({behavior: "smooth", block: "center"});
      return;
    }
    if (busy) {
      suggestionStatus = "Wait for the current request to finish before suggesting edits.";
      suggestionStatusError = true;
      inlineStatus("suggestion-status", suggestionStatus, true);
      return;
    }
    suggestionStatus = "Submitting costume template suggestion request…";
    suggestionStatusError = false;
    inlineStatus("suggestion-status", suggestionStatus);
    $("propose").disabled = true;
    void (async () => {
      try {
        const succeeded = await act("propose", {direction: $("direction").value});
        if (!succeeded) {
          suggestionStatus = $("message").textContent || "Suggestion request failed.";
          suggestionStatusError = true;
          return;
        }
        if (data?.status === "ANALYZING" || data?.analysis?.status === "QUEUED") {
          suggestionStatus = "Analyzing the selected image and unfinished criteria…";
          suggestionStatusError = false;
        } else if (data?.analysis?.status === "FAILED") {
          suggestionStatus = data.analysis.error || "Suggestion analysis failed.";
          suggestionStatusError = true;
        } else if (data?.status === "REVIEW_READY") {
          const count = data.analysis?.findings?.length || 0;
          suggestionStatus = count ? `${count} costume template suggestion${count === 1 ? "" : "s"} ready for review.`
            : "No edits were suggested. Add observations or direction, then try again.";
          suggestionStatusError = false;
        }
      } finally {
        inlineStatus("suggestion-status", suggestionStatus, suggestionStatusError);
        $("propose").disabled = busy || !["OBSERVING", "TRIAL_READY", "REVIEW_READY", "FAILED"].includes(data?.status);
      }
    })();
  });
  $("add-criterion").addEventListener("click", () => {
    if (criteriaSaving) return;
    criteriaDraft.push({text: "", status: "in_progress"}); criteriaDirty = true; criteriaStatus = ""; drawCriteria();
  });
  $("save-criteria").addEventListener("click", () => void saveCriteria());
  $("refine").addEventListener("click", () => { $("direction").focus(); message("Add or revise observations, then suggest another round of edits."); });
  $("trial").addEventListener("click", () => {
    if (deciding || criteriaDirty) { message("Finish saving your choices and criteria before accepting the diff.", true); return; }
    void act("trial", {selected_ids: data.analysis.selected_ids,
      ...(isCostume ? {diff_sha256: data.diff_sha256, expected_revision: data.revision} : {})});
  });
  $("keep").addEventListener("click", async () => {
    if (criteriaDirty) { message("Save acceptance criteria before saving the template.", true); return; }
    await act("keep"); if (data?.status === "KEPT") location.href = returnUrl(); });
  $("cancel").addEventListener("click", async () => { await act("cancel"); if (data?.status === "CANCELLED") location.href = returnUrl(); });
  void refresh(); setInterval(() => {
    const aiPending = Object.values(data?.observations || {}).some(review => ["QUEUED", "RUNNING"].includes(review?.ai_observations?.status));
    if (["ANALYZING", "TRIAL_RUNNING", "KEEPING"].includes(data?.status) || aiPending || ["QUEUED", "RUNNING"].includes(data?.trial?.assessment?.status)) void refresh();
  }, 2500);
})();
