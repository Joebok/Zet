import {renderCandidateBoard, renderBoardActions, candidateActions, reviewPosition, reviewInputs} from "./candidate_board.js?v=20261107-render-time";

(() => {
  const $ = (id) => document.getElementById(`character-container-${id}`);
  const pipelineLabels = {
    "body-reference": "Body Reference", "head-image": "Head Image Construct",
    "head-image-edit": "Head Image Edit", "character-assembly": "Character Assembly",
    "costume-dressing": "Costume Dressing",
  };
  const state = {pipeline: "", costume: "", view: "", detail: null,
    timer: null, active: false, pollInFlight: false, request: 0, sourceRequest: 0, templateProposal: null,
    reviewCandidateId: "", mutation: false, originSlot: null, scope: null, controller: null, templateTimer: null};
  const reviewZoom = window.ZetReviewImageZoom.attach($("review"), () => [...$("review-pair").querySelectorAll("img")]);
  const activeCandidateStates = new Set(["SUBMITTING", "QUEUED", "RUNNING", "DISPATCHING"]);
  const escape = (value) => String(value ?? "").replace(/[&<>"']/g,
    (char) => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[char]));

  function query() {
    const params = new URLSearchParams(state.scope || {});
    if (state.pipeline === "costume-dressing" && state.costume) params.set("costume", state.costume);
    return params;
  }

  async function request(path, options = {}) {
    const signal = state.controller.signal;
    const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options, signal});
    const data = await response.json().catch(() => ({}));
    signal.throwIfAborted();
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status}).`);
    return data;
  }

  function api(suffix = "") {
    return `/api/character-containers/${encodeURIComponent(state.pipeline)}${suffix}?${query()}`;
  }

  function apiAt(pipeline, phase) {
    const params = query();
    params.set("phase", phase);
    params.delete("costume");
    return `/api/character-containers/${encodeURIComponent(pipeline)}?${params}`;
  }

  function show(message, error = false) {
    $("status").textContent = message;
    $("status").classList.toggle("error", error);
  }

  function stopPolling() {
    clearInterval(state.timer);
    state.timer = null;
  }

  function pageVisible() {
    return document.visibilityState === "visible" &&
      document.querySelector("#character-asset-container-page").classList.contains("active");
  }

  function activeOnScreen() { return state.active && pageVisible(); }

  function startPolling() {
    stopPolling();
    if (!pageVisible()) return;
    if (state.active && state.view && state.detail?.boards?.[state.view]?.slots.some((id) => id &&
      activeCandidateStates.has(state.detail.boards[state.view].candidates[id]?.status))) {
      state.timer = setInterval(() => { if (activeOnScreen()) void pollProgress(); }, 1500);
    }
  }

  async function loadDetail() {
    const sequence = ++state.request;
    const data = await request(api());
    if (sequence !== state.request || data.revision < (state.detail?.revision ?? -1)) return;
    state.detail = data;
    if (state.view && !data.boards[state.view]) state.view = data.scope.views[0];
    render();
    if ($("review").open) {
      if (data.boards[state.view]?.candidates[state.reviewCandidateId]) renderReviewComparison();
      else $("review").close();
    }
    if (!state.view && isHead()) void loadPhaseSourceCandidates();
  }

  async function pollProgress() {
    if (!activeOnScreen() || !state.view || !state.detail || state.pollInFlight || state.mutation || !state.timer) return;
    const url = api(`/views/${encodeURIComponent(state.view)}/progress`);
    const sequence = state.request;
    const signal = state.controller.signal;
    state.pollInFlight = true;
    try {
      const progress = await request(url);
      if (!pageVisible() || state.mutation || sequence !== state.request ||
          url !== api(`/views/${encodeURIComponent(state.view)}/progress`) ||
          progress.container_id !== state.detail?.container_id || progress.revision < state.detail.revision) return;
      if (!progress.active.length) {
        stopPolling();
        await loadDetail();
        return;
      }
      const board = state.detail.boards[state.view];
      if (progress.slots.length !== board.slots.filter(Boolean).length ||
          progress.slots.some((slot) => board.slots[slot.slot - 1] !== slot.candidate_id)) {
        await loadDetail();
        return;
      }
      let changed = board.selected_id !== progress.selected_id;
      board.selected_id = progress.selected_id;
      state.detail.revision = progress.revision;
      for (const slot of progress.slots) {
        const candidate = board.candidates[slot.candidate_id];
        if (candidate.status === slot.status && !!candidate.image_path === slot.image &&
            (candidate.error || "") === slot.error && !!candidate.locked === slot.locked) continue;
        Object.assign(candidate, {status: slot.status, error: slot.error, locked: slot.locked, image_path: slot.image ? "available" : ""});
        changed = true;
      }
      if (changed) {
        renderBoard();
        if ($("review").open) renderReviewComparison();
      }
    } catch (error) {
      if (sequence === state.request && pageVisible()) show(error.message, true);
    } finally {
      if (!signal.aborted) state.pollInFlight = false;
    }
  }

  function imageUrl(candidateId) {
    return comparisonImageUrl(state.view, candidateId);
  }

  function comparisonImageUrl(view, candidateId) {
    const quality = state.detail?.boards[view]?.candidates[candidateId]?.render_mode || "draft";
    return api(`/views/${encodeURIComponent(view)}/candidates/${encodeURIComponent(candidateId)}/image`) + `&quality=${encodeURIComponent(quality)}`;
  }

  function route(view = state.view) {
    const params = query();
    params.set("page", "character-asset-container");
    params.set("pipeline", state.pipeline);
    if (view) params.set("view", view);
    return `/?${params}`;
  }

  function syncRoute() {
    if (new URLSearchParams(location.search).get("page") === "character-asset-container") {
      history.replaceState({}, "", route());
    }
  }

  function navigate(view) {
    history.pushState({}, "", route(view));
    return activate(state.pipeline, {view, costume: state.costume, guidance: $("template-guidance").value});
  }

  function isHead() { return ["head-image", "head-image-edit"].includes(state.pipeline); }

  function render() {
    const {scope, boards} = state.detail;
    $("title").textContent = `${pipelineLabels[state.pipeline]} · ${scope.character} · ${scope.phase}`;
    $("context").textContent = [scope.costume, state.view.replaceAll("_", " ")].filter(Boolean).join(" · ");
    $("workspace").hidden = !state.view;
    $("costume-wrap").hidden = state.pipeline !== "costume-dressing" || Boolean(state.view);
    $("outputs").hidden = Boolean(state.view);
    $("refresh").hidden = false;
    $("back").href = route("");
    renderAuthoring();
    if (state.view) renderBoard();
    else {
      $("outputs").innerHTML = scope.views.map(view => {
        const board = boards[view];
        const candidate = board.candidates[board.selected_id];
        const label = view.replaceAll("_", " ");
        const href = escape(route(view));
        const image = candidate?.image_path
          ? `<a href="${href}" data-container-view="${view}"><img loading="lazy" src="${escape(comparisonImageUrl(view, board.selected_id))}" alt="${escape(label)}"></a>`
          : '<div class="placeholder">No selected image</div>';
        return `<article class="narrative-slot character-container-output"><h3>${escape(label)}</h3>${image}
          ${candidate?.image_path ? `<p><span class="narrative-render-mode-pill ${candidate.render_mode === "final" ? "final" : "draft"}">${candidate.render_mode === "final" ? "Final" : "Draft"}</span> · ${candidate.locked ? "Locked" : "Selected"}</p>` : ""}
          <a href="${href}" data-container-view="${view}" class="image-card-text-control">Open ${escape(label)} Candidate Board</a></article>`;
      }).join("");
    }
    startPolling();
  }

  function renderBoard() {
    const board = state.detail.boards[state.view];
    const staging = document.createElement("div");
    const candidates = Object.fromEntries(Object.entries(board.candidates).map(([id, candidate]) => [id, {
      ...candidate,
      image: Boolean(candidate.image_path),
    }]));
    renderCandidateBoard({host: staging, slots: board.slots, candidates,
      selectedId: board.selected_id, escape, imageUrl,
      renderActions: (candidate, index) => renderActions(candidate, index + 1),
      renderDetails: (candidate) => candidate
        ? `<details class="candidate-request-details"><summary>Submitted prompt and references</summary><pre>${escape(candidate.prompt || "")}</pre><ul>${(candidate.render_request?.inputs || []).map(item => `<li>${escape(item.role || "Reference")}${item.render_mode ? ` · ${escape(item.render_mode)}` : ""}</li>`).join("")}</ul>${candidate.status === "PREPARED" ? `<button data-board-action="submit" data-candidate-id="${escape(candidate.candidate_id)}">Generate</button>` : ""} ${candidate.status === "COMPLETE" && candidate.image_path ? `<button data-template-improve="${escape(candidate.candidate_id)}">Improve template from this image</button>` : ""}</details>`
        : ""});
    const host = $("board");
    const focused = document.activeElement;
    [...staging.children].forEach((card, index) => {
      const id = board.slots[index];
      card.dataset.signature = JSON.stringify([id, candidates[id], board.selected_id === id]);
      const previous = host.children[index];
      if (!previous) host.append(card);
      else if (previous.dataset.signature !== card.dataset.signature) {
        const action = previous.contains(focused) ? focused.dataset.actionKey : "";
        previous.replaceWith(card);
        if (action) [...card.querySelectorAll("button")].find((button) =>
          button.dataset.actionKey === action)?.focus();
      }
    });
  }

  function renderActions(candidate, slot, review = false) {
    const id = candidate?.candidate_id;
    const selected = Boolean(id) && state.detail.boards[state.view].selected_id === id;
    const active = activeCandidateStates.has(candidate?.status);
    return candidateActions({id, candidate, slot, selected, escape, review, busy: review && state.mutation,
      canReplace: !active && !selected && !candidate?.locked,
      canClear: !active && !candidate?.locked, showProtectedRegen: review});
  }

  function renderAuthoring() {
    const detail = state.detail;
    if (!detail) return;
    const sources = detail.sources || {};
    const byMode = sources.phase_change_by_mode || {};
    const phaseSource = sources.phase_change ?? byMode.final ?? byMode.draft ?? {};
    const authoring = $("authoring");
    authoring.hidden = Boolean(state.view);
    $("template-improvement").hidden = Boolean(state.view);
    $("edit-costume-template").hidden = state.pipeline !== "costume-dressing";
    renderTemplateChoices();
    $("apply-wrap").hidden = !isHead() || state.view !== "FRONT";
    $("phase-source").hidden = !["head-image", "head-image-edit"].includes(state.pipeline);
    $("assembly-source").hidden = state.pipeline !== "character-assembly";
    $("view-source").hidden = !["body-reference", "head-image", "head-image-edit"].includes(state.pipeline) || !state.view || state.view === "FRONT";
    const phaseSelect = $("source-phase");
    const phases = Array.from(document.querySelector("#phase-select").options)
      .filter((option) => option.value && option.value !== detail.scope.phase);
    phaseSelect.replaceChildren(...phases.map((phase) => new Option(phase.textContent, phase.value)));
    phaseSelect.value = phases.some((phase) => phase.value === phaseSource.phase)
      ? phaseSource.phase : (phases[0]?.value || "");
    $("source-pipeline").value = phaseSource.pipeline || "head-image";
    $("head-pipeline").value = sources.head_pipeline || "head-image";

    const recipe = {...(sources.views || {})};
    const sourceView = $("source-view");
    const choices = detail.scope.views.filter((view) => view !== state.view);
    const options = choices.map((view) => new Option(view.replaceAll("_", " "), view));
    if (state.pipeline !== "head-image-edit") options.unshift(new Option("No image reference", ""));
    sourceView.replaceChildren(...options);
    sourceView.value = recipe[state.view] ?? (state.pipeline === "head-image-edit" ? "FRONT" : "");
  }

  async function loadPhaseSourceCandidates() {
    const sequence = ++state.sourceRequest;
    const phase = $("source-phase").value;
    const pipeline = $("source-pipeline").value;
    if (!phase) {
      $("source-status").textContent = "Choose a source phase.";
      return;
    }
    $("source-status").textContent = "Checking the current locked FRONT…";
    try {
      const data = await request(apiAt(pipeline, phase));
      if (sequence !== state.sourceRequest) return;
      const board = data.boards.FRONT;
      const candidate = board.slots.map((id) => id && board.candidates[id])
        .find((item) => item?.locked && item.inventory_asset_id);
      $("source-status").textContent = candidate
        ? `Current source: locked FRONT · ${candidate.render_mode} · slot ${candidate.slot}`
        : "No locked, published FRONT yet. Save this phase and pipeline; new FRONT requests will wait until one is locked.";
    } catch (error) {
      if (sequence === state.sourceRequest) $("source-status").textContent = error.message;
    }
  }

  async function saveSource(name, source, renderMode = "") {
    try {
      state.detail = await request(api(`/sources/${encodeURIComponent(name)}`), {
        method: "PUT", body: JSON.stringify({source, render_mode: renderMode,
          expected_revision: state.detail.revision}),
      });
      render();
      if (!state.view && isHead()) void loadPhaseSourceCandidates();
      $("source-status").textContent = "Reference choice saved for new requests.";
    } catch (error) { if (error.name !== "AbortError") $("source-status").textContent = error.message; }
  }

  function review(candidateId) {
    if (state.reviewCandidateId !== candidateId) $("review-pair").replaceChildren();
    const board = state.detail?.boards?.[state.view];
    const candidate = board?.candidates?.[candidateId];
    if (!candidate) return;
    state.reviewCandidateId = candidateId;
    const opposites = {FRONT_LEFT_3_4: "FRONT_RIGHT_3_4", FRONT_RIGHT_3_4: "FRONT_LEFT_3_4",
      LEFT_PROFILE: "RIGHT_PROFILE", RIGHT_PROFILE: "LEFT_PROFILE",
      BACK_LEFT_3_4: "BACK_RIGHT_3_4", BACK_RIGHT_3_4: "BACK_LEFT_3_4"};
    const preferred = state.view === "FRONT"
      ? ["FRONT_LEFT_3_4", "FRONT_RIGHT_3_4", "LEFT_PROFILE", "RIGHT_PROFILE"]
      : ["FRONT", opposites[state.view]].filter(Boolean);
    const choices = [];
    for (const [view, viewBoard] of Object.entries(state.detail.boards)) {
      const id = viewBoard.selected_id;
      const item = id && viewBoard.candidates[id];
      if (!item?.image_path || id === candidateId) continue;
      if (item.render_mode === "draft" && (item.locked || viewBoard.selected_id === id)) continue;
      choices.push({id, view, item});
    }
    const priority = (choice) => {
      const index = preferred.indexOf(choice.view);
      return index < 0 ? preferred.length : index;
    };
    choices.sort((left, right) => priority(left) - priority(right));
    const compare = $("review-compare");
    compare.replaceChildren(...choices.map((choice) => {
      const label = `${choice.view.replaceAll("_", " ")} · Slot ${choice.item.slot} · ${choice.item.render_mode}`;
      const option = new Option(label, `${choice.view}:${choice.id}`);
      return option;
    }));
    compare.size = Math.min(4, Math.max(2, choices.length));
    if (choices.length) {
      const selectedChoice = choices.find((choice) => preferred.includes(choice.view)) || choices[0];
      compare.value = `${selectedChoice.view}:${selectedChoice.id}`;
    }
    compare.disabled = choices.length === 0;
    renderReviewComparison();
    compare.onchange = () => renderReviewComparison();
    if (!$("review").open) $("review").showModal();
  }

  function renderReviewComparison() {
    const board = state.detail?.boards?.[state.view];
    const candidate = board?.candidates?.[state.reviewCandidateId];
    if (!candidate) return;
    const focused = document.activeElement;
    const focusedAction = $("review-actions").contains(focused) ? focused.dataset.actionKey : "";
    const focusedInput = $("review-prompt").contains(focused) ? focused.getAttribute("href") : "";
    const ids = board.slots.filter(Boolean);
    const index = ids.indexOf(state.reviewCandidateId);
    $("review-position").textContent = reviewPosition(candidate, index, ids.length, board.selected_id === state.reviewCandidateId);
    $("review-prev").disabled = state.mutation || index === 0;
    $("review-next").disabled = state.mutation || index === ids.length - 1;
    $("review-copy").disabled = !candidate.prompt;
    $("review-actions").innerHTML = renderActions({...candidate, image: Boolean(candidate.image_path)}, candidate.slot, true);

    const choices = [...$("review-compare").selectedOptions].map((option) => {
      const [view, id] = option.value.split(":");
      const item = state.detail.boards[view]?.candidates?.[id];
      return item?.image_path ? {view, id, item} : null;
    }).filter(Boolean);
    const pair = $("review-pair");
    pair.classList.toggle("single-image", !choices.length);
    const images = [{view: state.view, id: state.reviewCandidateId, item: candidate}, ...choices];
    const title = ({view, item}) => `${item === candidate ? "Candidate" : view.replaceAll("_", " ")} · Slot ${item.slot} · ${item.render_mode}`;
    pair.innerHTML = images.map(image => `<figure><header><strong>${escape(title(image))}</strong></header>
      ${image.item.image_path ? `<img src="${escape(comparisonImageUrl(image.view, image.id))}" alt="${escape(title(image))}">`
        : `<p>${escape(image.item.status === "FAILED" ? image.item.error || "Render failed." : "No image available yet.")}</p>`}</figure>`).join("");
    reviewZoom.sync(`${state.view}:${state.reviewCandidateId}:${candidate.image_path || candidate.status}`);
    const prompt = $("review-prompt");
    const open = new Set([...prompt.querySelectorAll("details[open]")].map(details => details.dataset.promptKey));
    prompt.innerHTML = images.map(({view, id, item}) => {
      const key = `${view}:${id}`;
      return `<details data-prompt-key="${escape(key)}" ${open.has(key) ? "open" : ""}><summary>${item === candidate ? "Prompt and ordered inputs" : escape(title({view, item}))}</summary>
        <pre>${escape(item.prompt || "")}</pre>${reviewInputs(item.render_request?.inputs,
        index => api(`/views/${view}/candidates/${id}/inputs/${index}`), escape)}</details>`;
    }).join("");
    window.ZetImageCardUI.scan($("review"));
    if (focusedAction) {
      const buttons = [...$("review-actions").querySelectorAll("button:not(:disabled)")];
      (buttons.find(button => button.dataset.actionKey === focusedAction) || $("review-close")).focus();
    } else if (focusedInput) {
      [...$("review-prompt").querySelectorAll("a")].find(link => link.getAttribute("href") === focusedInput)?.focus();
    }
  }

  function renderTemplateChoices() {
    if (!state.detail) return;
    const picker = $("template-candidate");
    const chosen = picker.value;
    const options = [new Option("Choose a finished candidate", "")];
    for (const [view, board] of Object.entries(state.detail.boards)) {
      for (const candidate of Object.values(board.candidates)) {
        if (candidate.status === "COMPLETE" && candidate.image_path && board.slots.includes(candidate.candidate_id)) {
          options.push(new Option(`${view.replaceAll("_", " ")} · slot ${candidate.slot} · ${candidate.render_mode}`,
            `${view}:${candidate.candidate_id}`));
        }
      }
    }
    picker.replaceChildren(...options); picker.value = chosen;
  }

  function updateTemplateMode() {
    $("template-candidate-wrap").hidden = $("template-mode").value !== "candidate";
  }

  function watchTemplateReview() {
    clearInterval(state.templateTimer); state.templateTimer = null;
    if (!state.active || state.view || !$("template-improvement").open ||
        state.templateProposal?.schema_version !== 2 || state.templateProposal.status !== "PROPOSING") return;
    state.templateTimer = setInterval(async () => {
      if (!state.active || state.view || !$("template-improvement").open) { clearInterval(state.templateTimer); state.templateTimer = null; return; }
      try {
        state.templateProposal = await request(api(`/template-proposals/${state.templateProposal.proposal_id}`));
        renderTemplateProposal();
        if (state.templateProposal.status !== "PROPOSING") { clearInterval(state.templateTimer); state.templateTimer = null; }
      } catch (error) { reportError(error); clearInterval(state.templateTimer); state.templateTimer = null; }
    }, 3000);
  }

  function renderTemplateProposal() {
    const host = $("template-proposal");
    const proposal = state.templateProposal;
    host.replaceChildren();
    host.hidden = !proposal;
    if (!proposal) return;
    if (proposal.schema_version === 2) {
      const heading = document.createElement("h3");
      heading.textContent = `Template review · ${proposal.status}`;
      host.append(heading);
      if (proposal.error) { const error = document.createElement("p");
        error.textContent = `${proposal.failure_stage ? `${proposal.failure_stage}: ` : ""}${proposal.error}`; host.append(error); }
      if (proposal.summary) { const summary = document.createElement("p"); summary.textContent = proposal.summary; host.append(summary); }
      if (proposal.rejected_findings?.length) {
        const details = document.createElement("details"); details.open = proposal.status === "FAILED";
        const title = document.createElement("summary");
        title.textContent = `${proposal.rejected_findings.length} rejected correction${proposal.rejected_findings.length === 1 ? "" : "s"}`;
        details.append(title);
        const list = document.createElement("ul");
        for (const rejected of proposal.rejected_findings) {
          const item = document.createElement("li");
          item.textContent = `Finding ${rejected.number} · ${rejected.source_id || "unknown source"}`
            + `${rejected.reported_views?.length ? ` · reported views: ${rejected.reported_views.join(", ")}` : ""}`
            + ` · ${(rejected.reasons || []).join(" ")}`;
          list.append(item);
        }
        details.append(list); host.append(details);
      }
      if (proposal.status === "REVIEW_READY" || proposal.status === "ACCEPTED") {
        const list = document.createElement("div");
        for (const finding of proposal.findings || []) {
          const label = document.createElement("label");
          const check = document.createElement("input"); check.type = "checkbox"; check.value = finding.id;
          check.checked = (proposal.selected_ids || []).includes(finding.id);
          check.disabled = proposal.status === "ACCEPTED";
          label.append(check, document.createTextNode(`${finding.source_id} · ${finding.views.join(", ")} · ${finding.rationale}`));
          const before = document.createElement("pre"); before.textContent = `Before\n${finding.before}`;
          const after = document.createElement("pre"); after.textContent = `After\n${finding.after}`;
          list.append(label, before, after);
        }
        if (!(proposal.findings || []).length) { const none = document.createElement("p"); none.textContent = "No changes suggested."; list.append(none); }
        host.append(list);
        if (proposal.status === "REVIEW_READY") {
          const review = document.createElement("button"); review.type = "button"; review.textContent = "Preview selected corrections";
          review.addEventListener("click", async () => {
            review.disabled = true;
            try {
              const ids = [...list.querySelectorAll("input:checked")].map(input => input.value);
              state.templateProposal = await request(api(`/template-proposals/${proposal.proposal_id}/decisions`),
                {method: "PUT", body: JSON.stringify({selected_ids: ids})});
              renderTemplateProposal();
            } catch (error) { reportError(error); review.disabled = false; }
          });
          host.append(review);
        }
        for (const diff of proposal.diffs || []) {
          const details = document.createElement("details");
          const summary = document.createElement("summary"); summary.textContent = `${diff.source_id} master → proposed`;
          const pre = document.createElement("pre"); pre.textContent = (diff.rows || []).map(row =>
            row.kind === "gap" ? "…" : `${row.master_line == null ? "" : `− ${row.master_text || ""}`}\n${row.proposed_line == null ? "" : `+ ${row.proposed_text || ""}`}`).join("\n");
          details.append(summary, pre); host.append(details);
        }
        if (proposal.previews) {
          const previews = document.createElement("details");
          const summary = document.createElement("summary"); summary.textContent = "Compiled prompt previews"; previews.append(summary);
          for (const item of proposal.previews) { const detail = document.createElement("details");
            const title = document.createElement("summary"); title.textContent = item.view;
            const pre = document.createElement("pre"); pre.textContent = item.prompt; detail.append(title, pre); previews.append(detail); }
          host.append(previews);
          if (proposal.status === "REVIEW_READY") {
            const accept = document.createElement("button"); accept.type = "button"; accept.textContent = "Accept selected corrections and save masters";
            list.addEventListener("change", () => { accept.disabled = true;
              accept.title = "Preview the changed selection before accepting."; });
            accept.addEventListener("click", async () => {
              if (!confirm("Save the selected corrections to the governing master templates?")) return;
              accept.disabled = true;
              try { state.templateProposal = await request(api(`/template-proposals/${proposal.proposal_id}/accept`),
                {method: "POST", body: JSON.stringify({confirm: true})}); renderTemplateProposal();
                show("Governing templates updated for future prompts."); }
              catch (error) { reportError(error); accept.disabled = false; }
            }); host.append(accept);
          }
        }
      }
      return;
    }
    const heading = document.createElement("h3");
    heading.textContent = `${proposal.status === "ACCEPTED" ? "Accepted template proposal" : "Template proposal"} · ${proposal.view} · ${proposal.render_mode}`;
    const summary = document.createElement("p"); summary.textContent = proposal.summary || "";
    const rationale = document.createElement("p"); rationale.textContent = proposal.rationale || "";
    const diff = document.createElement("pre"); diff.textContent = proposal.diff || "No changes proposed.";
    const compiled = document.createElement("details");
    const detailsSummary = document.createElement("summary"); detailsSummary.textContent = "Prompt preview with the proposed master";
    const prompt = document.createElement("pre"); prompt.textContent = proposal.compiled_prompt || "";
    compiled.append(detailsSummary, prompt);
    host.append(heading, summary, rationale, diff, compiled);
    if (proposal.status === "PROPOSED" && proposal.diff) {
      const accept = document.createElement("button");
      accept.type = "button"; accept.textContent = "Accept proposal and update Character.md";
      accept.addEventListener("click", async () => {
        if (!window.confirm("Save this reviewed proposal to the governing Character.md? It will affect new prompts only.")) return;
        accept.disabled = true;
        try {
          state.templateProposal = await request(api(`/template-proposals/${encodeURIComponent(proposal.proposal_id)}/accept`), {
            method: "POST", body: JSON.stringify({confirm: true}),
          });
          renderTemplateProposal();
          show("Character.md updated. Existing candidates keep their captured prompts and inputs.");
        } catch (error) { reportError(error); accept.disabled = false; }
      });
      host.append(accept);
    }
  }

  async function costumeOptions() {
    const data = await request(`/api/costumes?${query()}`);
    const select = $("costume");
    select.replaceChildren(new Option("Choose a costume", ""),
      ...data.costumes.map(costume => new Option(costume.name, costume.slug)));
    state.costume = data.costumes.find(costume =>
      costume.slug === state.costume || costume.name === state.costume)?.slug || "";
    select.value = state.costume;
  }

  function deactivate() {
    clearInterval(state.templateTimer); state.templateTimer = null;
    state.controller?.abort();
    state.request += 1;
    state.sourceRequest += 1;
    state.active = false;
    stopPolling();
    if ($("review").open) $("review").close();
  }

  async function activate(pipeline, options = {}) {
    const params = new URLSearchParams(location.search);
    deactivate();
    const controller = new AbortController();
    state.controller = controller;
    state.scope = options.scope || {
      character: document.querySelector("#character-select").value,
      phase: document.querySelector("#phase-select").value,
      universe_id: document.querySelector("#universe-select").value,
    };
    state.pipeline = pipeline || params.get("pipeline") || "body-reference";
    $("board-actions").innerHTML = renderBoardActions();
    state.view = options.view ?? params.get("view") ?? "";
    state.costume = state.pipeline === "costume-dressing"
      ? options.costume ?? params.get("costume") ?? "" : "";
    state.active = true;
    state.pollInFlight = false;
    state.mutation = false;
    state.detail = null;
    state.templateProposal = options.proposal || null;
    state.originSlot = null;
    state.reviewCandidateId = "";
    for (const id of ["board", "outputs", "review-pair", "review-prompt", "prompt-references", "source-status", "prompt-text"]) $(id).replaceChildren();
    for (const id of ["workspace", "outputs", "authoring", "template-improvement", "prompt-preview", "refresh", "costume-wrap"]) $(id).hidden = true;
    $("authoring").open = false;
    $("template-improvement").open = Boolean(options.proposal || options.templateCandidate);
    $("apply-phase-change").checked = false;
    $("phase-source-file").value = "";
    $("template-guidance").value = options.guidance ?? "";
    $("prompt-preview-button").disabled = false;
    document.querySelectorAll(".candidate-board-actions button").forEach(button => { button.disabled = false; });
    $("title").textContent = pipelineLabels[state.pipeline] || "Character Asset Container";
    $("context").textContent = "";
    renderTemplateProposal();
    show("Loading Asset Container…");
    if (options.sync !== false) syncRoute();
    if (!state.scope.character || !state.scope.phase) {
      show("Choose a character and phase to open its Asset Container.");
      return;
    }
    try {
      if (state.pipeline === "costume-dressing") {
        $("costume").disabled = true;
        await costumeOptions();
        $("costume").disabled = false;
        if (!state.costume) {
          $("costume-wrap").hidden = false;
          syncRoute();
          show("Choose a costume to open its Asset Container.");
          return;
        }
      }
      await loadDetail();
      controller.signal.throwIfAborted();
      syncRoute();
      if (!state.view) {
        const sources = await request(api("/template-sources"));
        $("template-sources").replaceChildren(...sources.sources.map(source => {
          const label = document.createElement("label"); const input = document.createElement("input");
          input.type = "checkbox"; input.value = source.source_id; input.checked = true;
          label.append(input, document.createTextNode(` Improve ${source.source_id}`)); return label;
        }));
        const savedProposal = await request(api("/template-proposals"));
        if (!options.proposal) state.templateProposal = savedProposal.proposal;
        renderTemplateProposal();
        renderTemplateChoices();
        if (options.templateCandidate) { $("template-mode").value = "candidate";
          $("template-candidate").value = options.templateCandidate; updateTemplateMode(); }
        watchTemplateReview();
      }
      show("Container ready.");
    } catch (error) {
      if (!controller.signal.aborted) {
        $("costume").disabled = false;
        $("costume-wrap").hidden = state.pipeline !== "costume-dressing";
        show(error.message, true);
      }
    }
  }

  async function generate(count, renderMode, replacement = {}) {
    if (state.mutation || !state.detail) return;
    const scope = api();
    const view = state.view;
    const signal = state.controller.signal;
    const modal = $("review").open;
    const buttons = [...document.querySelectorAll(".candidate-board-actions [data-board-action='render']")];
    state.mutation = true;
    buttons.forEach((button) => { button.disabled = true; });
    const feedback = (message, error = false) => modal && $("review").open
      ? $("review-status").textContent = message : show(message, error);
    feedback("Preparing render…");
    if (modal) renderReviewComparison();
    try {
      const result = await request(api(`/views/${encodeURIComponent(view)}/generate`), {
        method: "POST", body: JSON.stringify({count, render_mode: renderMode,
          aspect_ratio: $("aspect").value, expected_revision: state.detail.revision,
          apply_phase_change: $("apply-phase-change").checked, ...replacement}),
      });
      if (signal.aborted || scope !== api() || view !== state.view || result.revision < state.detail.revision) return;
      state.detail = result;
      render();
      if (modal && $("review").open && replacement.slot) {
        review(result.boards[view].slots[replacement.slot - 1]);
      }
      feedback("Render slots updated.");
    } catch (error) {
      if (!signal.aborted && scope === api() && view === state.view) {
        feedback(error.message, true);
        await loadDetail().catch(() => {});
      }
    } finally {
      if (!signal.aborted) {
        state.mutation = false;
        buttons.forEach((button) => { button.disabled = false; });
        if ($("review").open) renderReviewComparison();
      }
    }
  }

  async function previewPrompt() {
    const signal = state.controller.signal;
    const button = $("prompt-preview-button");
    button.disabled = true;
    try {
      const preview = await request(api(`/views/${encodeURIComponent(state.view)}/prompt`), {
        method: "POST", body: JSON.stringify({apply_phase_change: $("apply-phase-change").checked}),
      });
      $("prompt-text").textContent = preview.prompt;
      $("prompt-references").replaceChildren(...preview.reference_inputs.map((input) => {
        const item = document.createElement("li");
        item.textContent = `${input.role || input.label || "Reference"}${input.render_mode ? ` · ${input.render_mode}` : ""}`;
        return item;
      }));
      $("prompt-preview").hidden = false;
      $("prompt-preview").open = true;
      show("Prompt compiled from current masters and selected references.");
    } catch (error) { reportError(error); }
    finally { if (!signal.aborted) button.disabled = false; }
  }

  $("board-actions").addEventListener("click", (event) => {
    const button = event.target.closest("[data-board-action]");
    if (!button || state.mutation || !state.detail || !state.view) return;
    if (button.dataset.boardAction === "render") {
      void generate(Number(button.dataset.count), button.dataset.mode);
      return;
    }
    void bulkBoardAction(button);
  });

  async function bulkBoardAction(button) {
    const action = button.dataset.boardAction;
    const endpoint = action === "delete-drafts" ? "delete-drafts" : "delete-non-selected";
    const title = action === "delete-drafts" ? "Delete Draft images?" : "Delete Non-Selected candidates?";
    const prompt = action === "delete-drafts"
      ? "Delete all Draft candidates in this view? Approve each selected or locked candidate affected."
      : "Clear every candidate except selected or locked candidates in this view?";
    const controls = [...$("board-actions").querySelectorAll("button")];
    controls.forEach(control => { control.disabled = true; });
    state.mutation = true;
    show("Reviewing candidates to delete…");
    try {
      const endpointPath = `/views/${encodeURIComponent(state.view)}/${endpoint}`;
      const path = api(endpointPath);
      const preview = await request(api(`${endpointPath}/preview`), {method: "POST", body: "{}"});
      const candidates = preview.candidates || [];
      if (!candidates.length) { show("No candidates match this action."); return; }
      const effects = (preview.protected_effects || []).map(effect => ({...effect,
        preview_url: state.detail.boards[state.view].candidates[effect.candidate_id]?.image_path
          ? imageUrl(effect.candidate_id) : ""}));
      let approved = [];
      if (effects.length) {
        approved = await window.confirmProtectedEffects(title,
          `${prompt} ${candidates.length} slot${candidates.length === 1 ? "" : "s"} will be cleared.`, effects,
          action === "delete-drafts" ? "Delete Drafts" : "Delete Non-Selected");
        if (approved === null) return;
      } else if (!confirm(`${prompt}\n\n${candidates.length} slot${candidates.length === 1 ? "" : "s"} will be cleared.`)) return;
      const result = await request(path, {method: "POST", body: JSON.stringify({
        confirmation_token: preview.confirmation_token, expected_revision: preview.revision,
        approved_effects: approved,
      })});
      const previous = state.detail.boards[state.view];
      const removedReviewCandidate = previous.candidates[state.reviewCandidateId] &&
        !result.boards[state.view].candidates[state.reviewCandidateId];
      const previousSlot = previous.candidates[state.reviewCandidateId]?.slot || state.originSlot || 1;
      state.detail = result;
      render();
      if ($("review").open) {
        if (removedReviewCandidate) {
          const slots = result.boards[state.view].slots;
          const next = slots.slice(previousSlot).find(Boolean) || slots.slice(0, previousSlot - 1).reverse().find(Boolean);
          if (next) review(next); else $("review").close();
        } else renderReviewComparison();
      }
      show(`${candidates.length} candidate slot${candidates.length === 1 ? "" : "s"} cleared.`);
    } catch (error) { reportError(error); }
    finally {
      state.mutation = false;
      controls.forEach(control => { control.disabled = false; });
      if ($("review").open) renderReviewComparison();
    }
  }
  $("prompt-preview-button").addEventListener("click", () => void previewPrompt());
  $("edit-template").addEventListener("click", async () => {
    const signal = state.controller.signal;
    try {
      const master = await request(api("/template"));
      await window.ZetSourceEditor.open({source_path: master.source_path,
        source_label: `Character.md · ${master.character} · ${master.phase}`, editable: true},
        (message) => show(message, true), signal);
    } catch (error) { reportError(error); }
  });
  $("edit-costume-template").addEventListener("click", async () => {
    try {
      const sources = await request(api("/template-sources"));
      const costume = sources.sources.find(source => source.kind === "costume");
      if (!costume) throw new Error("The governing Costume template is unavailable.");
      await window.ZetSourceEditor.open({source_path: costume.source_path,
        source_label: costume.source_id, editable: true}, (message) => show(message, true), state.controller.signal);
    } catch (error) { reportError(error); }
  });
  window.ZetModelPicker?.attach($("template-model"), {required: ["text"], allowDefault: true});
  $("template-mode").addEventListener("change", updateTemplateMode);
  $("template-improvement").addEventListener("toggle", watchTemplateReview);
  $("template-reload").addEventListener("click", async () => {
    try { state.templateProposal = (await request(api("/template-proposals"))).proposal;
      renderTemplateProposal(); watchTemplateReview(); }
    catch (error) { reportError(error); }
  });
  $("template-analyze").addEventListener("click", async () => {
    if (!state.detail) return;
    const button = $("template-analyze"); button.disabled = true;
    const mode = $("template-mode").value;
    const choice = $("template-candidate").value;
    if (mode === "candidate" && !choice) { $("template-status").textContent = "Choose a finished candidate."; button.disabled = false; return; }
    const [view, candidate_id] = mode === "candidate" ? choice.split(":") : ["", ""];
    try {
      state.templateProposal = await request(api("/template-reviews"), {method: "POST",
        body: JSON.stringify({mode, view, candidate_id, direction: $("template-guidance").value,
          model: $("template-model").value, expected_revision: state.detail.revision,
          source_ids: [...$("template-sources").querySelectorAll("input:checked")].map(input => input.value)})});
      $("template-status").textContent = "Analyzing templates…";
      renderTemplateProposal(); watchTemplateReview();
    } catch (error) { $("template-status").textContent = error.message; reportError(error); }
    finally { button.disabled = false; }
  });
  function refresh() {
    void loadDetail().then(pollProgress).catch(reportError);
  }
  function reportError(error) {
    if (error.name !== "AbortError") show(error.message, true);
  }
  $("refresh").addEventListener("click", refresh);
  $("costume").addEventListener("change", () => void activate(state.pipeline, {costume: $("costume").value, view: state.view}));
  function followViewLink(event, link, view) {
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    void navigate(view);
  }
  $("back").addEventListener("click", event => followViewLink(event, $("back"), ""));
  $("outputs").addEventListener("click", event => {
    const link = event.target.closest("a[data-container-view]");
    followViewLink(event, link, link?.dataset.containerView);
  });
  $("source-phase").addEventListener("change", () => void loadPhaseSourceCandidates());
  $("source-pipeline").addEventListener("change", () => void loadPhaseSourceCandidates());
  $("save-phase-source").addEventListener("click", () => {
    const source = {phase: $("source-phase").value, pipeline: $("source-pipeline").value};
    if (!source.phase) { $("source-status").textContent = "Choose a source phase first."; return; }
    void saveSource("phase_change", source);
  });
  $("clear-phase-source").addEventListener("click", () =>
    void saveSource("phase_change", {}));
  $("upload-phase-source").addEventListener("click", async () => {
    const file = $("phase-source-file").files?.[0];
    if (!file) { $("source-status").textContent = "Choose a PNG, JPEG, or WebP image first."; return; }
    const params = query();
    params.set("filename", file.name);
    params.set("expected_revision", state.detail.revision);
    try {
      state.detail = await request(`/api/character-containers/${encodeURIComponent(state.pipeline)}/sources/phase-change-upload?${params}`, {
        method: "PUT", headers: {"Content-Type": file.type || "application/octet-stream"}, body: file,
      });
      $("phase-source-file").value = "";
      render();
      $("source-status").textContent = "Managed upload saved for new FRONT requests.";
    } catch (error) { if (error.name !== "AbortError") $("source-status").textContent = error.message; }
  });
  $("save-head-pipeline").addEventListener("click", () => void saveSource("head_pipeline", $("head-pipeline").value));
  $("save-view-source").addEventListener("click", () => {
    const views = {...(state.detail.sources?.views || {}), [state.view]: $("source-view").value};
    void saveSource("views", views);
  });
  $("board").addEventListener("click", async (event) => {
    const reviewButton = event.target.closest("[data-review]");
    if (reviewButton) {
      state.originSlot = state.detail.boards[state.view].candidates[reviewButton.dataset.review].slot;
      $("review-status").textContent = "";
      review(reviewButton.dataset.review);
      return;
    }
    const improve = event.target.closest("[data-template-improve]");
    if (improve) {
      const candidate = `${state.view}:${improve.dataset.templateImprove}`;
      history.pushState({}, "", route(""));
      await activate(state.pipeline, {view: "", costume: state.costume, templateCandidate: candidate});
      return;
    }
    await boardAction(event);
  });

  async function boardAction(event) {
    const button = event.target.closest("[data-candidate-action], [data-board-action], [data-render-slot]");
    if (!button || state.mutation || !state.detail) return;
    const board = state.detail.boards[state.view];
    if (button.dataset.renderSlot) {
      const slot = Number(button.dataset.renderSlot);
      const id = board.slots[slot - 1];
      if (!id || confirm(`Replace slot ${slot} and delete its current candidate?`)) {
        await generate(1, button.dataset.mode, {slot, expected_candidate_id: id});
      }
      return;
    }
    const id = button.dataset.candidate || button.dataset.candidateId;
    const action = button.dataset.candidateAction || button.dataset.boardAction;
    const candidate = board.candidates[id];
    if (!candidate) return;
    const signal = state.controller.signal;
    const payload = {expected_revision: state.detail.revision};
    if (action === "clear") {
      payload.expected_candidate_id = id;
      payload.confirm_selected = state.detail.boards[state.view].selected_id === id && confirm("Clear the selected candidate from this board?");
      if (state.detail.boards[state.view].selected_id === id && !payload.confirm_selected) return;
      if (candidate.locked) { show("Unlock the candidate before clearing its slot.", true); return; }
    }
    const scope = api();
    const view = state.view;
    const modal = $("review").open;
    const feedback = modal ? $("review-status") : document.createElement("p");
    if (!modal) {
      button.closest("article").querySelector("p[data-slot-feedback]")?.remove();
      feedback.dataset.slotFeedback = "";
      feedback.setAttribute("role", "status");
      button.closest("article").append(feedback);
    }
    feedback.textContent = "Working…";
    button.disabled = true;
    state.mutation = true;
    try {
      const result = await request(api(`/views/${encodeURIComponent(view)}/candidates/${encodeURIComponent(id)}/${action}`),
        {method: "POST", body: JSON.stringify(payload)});
      if (signal.aborted || scope !== api() || view !== state.view || result.revision < state.detail.revision) return;
      state.detail = result;
      state.mutation = false;
      render();
      const updated = result.boards[view].candidates[id];
      const upscaleFeedback = updated?.error || "Upscale queued.";
      if (!modal) {
        const card = $("board").children[candidate.slot - 1];
        card.append(feedback);
        feedback.textContent = action === "upscale" ? upscaleFeedback : action === "lock" ? "Locked and published." : "Slot updated.";
        const next = [...card.querySelectorAll("button:not(:disabled)")].find(control =>
          control.dataset.candidateAction === action || control.dataset.review === id);
        next?.focus();
      }
      if (modal && $("review").open) {
        if (action === "clear") {
          const slots = result.boards[view].slots;
          const next = slots.slice(candidate.slot).find(Boolean) || slots.slice(0, candidate.slot - 1).reverse().find(Boolean);
          if (next) review(next);
          else {
            state.originSlot = candidate.slot;
            $("review").close();
          }
        } else renderReviewComparison();
        feedback.textContent = action === "upscale" ? upscaleFeedback : action === "lock" ? "Locked and published." : "Candidate updated.";
      }
    } catch (error) {
      if (!signal.aborted) {
        feedback.textContent = error.message;
        await loadDetail().catch(() => {});
      }
    } finally {
      if (!signal.aborted && state.mutation) {
        state.mutation = false;
        button.disabled = false;
        if (modal && $("review").open) renderReviewComparison();
      }
    }
  }

  $("review-actions").addEventListener("click", boardAction);
  function moveReview(offset) {
    if (state.mutation) return;
    const ids = state.detail.boards[state.view].slots.filter(Boolean);
    const id = ids[ids.indexOf(state.reviewCandidateId) + offset];
    if (id) review(id);
  }
  $("review-prev").onclick = () => moveReview(-1);
  $("review-next").onclick = () => moveReview(1);
  $("review").addEventListener("keydown", (event) => {
    if (event.target.closest("select, input, textarea")) return;
    if (event.key === "ArrowLeft") moveReview(-1);
    if (event.key === "ArrowRight") moveReview(1);
  });
  $("review").addEventListener("close", () => {
    if ($("review").open || !state.originSlot) return;
    const card = $("board").children[state.originSlot - 1];
    (card?.querySelector("button:not(:disabled)") || $("back")).focus();
  });
  $("review-copy").onclick = async () => {
    const candidate = state.detail.boards[state.view].candidates[state.reviewCandidateId];
    const signal = state.controller.signal;
    try {
      await navigator.clipboard.writeText(candidate.prompt);
      if (!signal.aborted) $("review-status").textContent = "Prompt copied.";
    } catch (error) { if (!signal.aborted) $("review-status").textContent = error.message; }
  };
  $("review-close").addEventListener("click", () => $("review").close());
  document.addEventListener("visibilitychange", () => {
    if (!pageVisible()) { stopPolling(); return; }
    if (state.active && state.scope?.phase && (state.pipeline !== "costume-dressing" || state.costume)) refresh();
  });
  window.ZetCharacterAssetContainer = {
    pipeline() { return state.pipeline; },
    context() { return {pipeline: state.pipeline, costume: state.costume, view: state.view}; },
    activate,
    deactivate,
    refreshScope() { return activate(state.pipeline, {view: state.view, costume: state.costume}); },
  };
  if (document.querySelector("#character-asset-container-page")?.classList.contains("active")) {
    void activate(new URLSearchParams(location.search).get("pipeline"));
  }
})();
