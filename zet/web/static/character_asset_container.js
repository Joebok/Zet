import {renderCandidateBoard, reviewDecisions, reviewPosition, reviewInputs} from "./candidate_board.js";

(() => {
  const $ = (id) => document.getElementById(`character-container-${id}`);
  const pipelineLabels = {
    "body-reference": "Body Reference", "head-image": "Head Image Construct",
    "head-image-edit": "Head Image Edit", "character-assembly": "Character Assembly",
    "costume-dressing": "Costume Dressing",
  };
  const state = {pipeline: "", costume: "", view: "FRONT", detail: null,
    timer: null, active: false, pollInFlight: false, request: 0, sourceRequest: 0, templateProposal: null,
    reviewCandidateId: "", mutation: false, originSlot: null};
  const activeCandidateStates = new Set(["SUBMITTING", "QUEUED", "RUNNING", "DISPATCHING"]);
  const escape = (value) => String(value ?? "").replace(/[&<>"']/g,
    (char) => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[char]));

  function query() {
    const params = new URLSearchParams({character: document.querySelector("#character-select").value,
      phase: document.querySelector("#phase-select").value,
      universe_id: document.querySelector("#universe-select").value});
    if (state.pipeline === "costume-dressing" && state.costume) params.set("costume", state.costume);
    return params;
  }

  async function request(path, options = {}) {
    const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options});
    const data = await response.json().catch(() => ({}));
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
    if (state.active && state.detail?.boards?.[state.view]?.slots.some((id) => id &&
      activeCandidateStates.has(state.detail.boards[state.view].candidates[id]?.status))) {
      state.timer = setInterval(() => { if (activeOnScreen()) void pollProgress(); }, 1500);
    }
  }

  async function loadDetail() {
    const sequence = ++state.request;
    const data = await request(api());
    if (sequence !== state.request || !pageVisible()) return;
    state.detail = data;
    if (!data.boards[state.view]) state.view = data.scope.views[0];
    render();
    if ($("review").open) {
      if (data.boards[state.view].candidates[state.reviewCandidateId]) renderReviewComparison();
      else $("review").close();
    }
    if (["head-image", "head-image-edit"].includes(state.pipeline)) void loadPhaseSourceCandidates();
  }

  async function pollProgress() {
    if (!activeOnScreen() || state.pollInFlight || state.mutation) return;
    const url = api(`/views/${encodeURIComponent(state.view)}/progress`);
    const sequence = state.request;
    state.pollInFlight = true;
    try {
      const progress = await request(url);
      if (!pageVisible() || state.mutation || sequence !== state.request ||
          url !== api(`/views/${encodeURIComponent(state.view)}/progress`) ||
          progress.container_id !== state.detail?.container_id || progress.revision < state.detail.revision) return;
      if (!progress.active.length) {
        state.active = false;
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
      state.pollInFlight = false;
    }
  }

  function imageUrl(candidateId) {
    return api(`/views/${encodeURIComponent(state.view)}/candidates/${encodeURIComponent(candidateId)}/image`);
  }

  function comparisonImageUrl(view, candidateId) {
    return api(`/views/${encodeURIComponent(view)}/candidates/${encodeURIComponent(candidateId)}/image`);
  }

  function saveRouteContext() {
    const params = new URLSearchParams(location.search);
    params.set("page", "character-asset-container");
    params.set("pipeline", state.pipeline);
    params.set("character", document.querySelector("#character-select").value);
    params.set("phase", document.querySelector("#phase-select").value);
    params.set("universe_id", document.querySelector("#universe-select").value);
    if (state.costume) params.set("costume", state.costume);
    else params.delete("costume");
    params.set("view", state.view);
    history.replaceState({}, "", `/?${params}`);
  }

  function render() {
    const detail = state.detail;
    if (!detail) return;
    const scope = detail.scope;
    $("title").textContent = `${pipelineLabels[state.pipeline]} · ${scope.character} · ${scope.phase}`;
    $("context").textContent = scope.costume ? `Costume · ${scope.costume}` : "";
    renderAuthoring();
    const views = $("views");
    views.replaceChildren(...scope.views.map((view) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = view.replaceAll("_", " ");
      button.className = view === state.view ? "primary-action" : "";
      button.addEventListener("click", () => { state.view = view; stopPolling(); $("board").replaceChildren(); saveRouteContext(); void loadDetail().catch((error) => show(error.message, true)); });
      return button;
    }));
    const board = detail.boards[state.view];
    state.active = board.slots.some((id) => id &&
      activeCandidateStates.has(board.candidates[id]?.status));
    renderBoard();
    $("costume-wrap").hidden = state.pipeline !== "costume-dressing";
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
      renderSlotActions: (candidate) => candidate
        ? `<details class="candidate-request-details"><summary>Submitted prompt and references</summary><pre>${escape(candidate.prompt || "")}</pre><ul>${(candidate.render_request?.inputs || []).map((item) => `<li>${escape(item.role || "Reference")}${item.render_mode ? ` · ${escape(item.render_mode)}` : ""}</li>`).join("")}</ul>${candidate.status === "PREPARED" ? `<button data-board-action="submit" data-candidate-id="${escape(candidate.candidate_id)}">Generate</button>` : ""} ${!candidate.locked && board.selected_id !== candidate.candidate_id && !activeCandidateStates.has(candidate.status)
          ? ["draft", "final"].map((mode) => `<button type="button" data-replace="${escape(candidate.candidate_id)}" data-quality="${mode}">Replace with ${mode === "draft" ? "Draft" : "Final"}</button>`).join("") : ""}${candidate.status === "COMPLETE" && candidate.image_path ? `<button data-template-improve="${escape(candidate.candidate_id)}">Suggest Character.md edit from this image</button>` : ""}</details>`
        : ""});
    const host = $("board");
    const focused = document.activeElement;
    [...staging.children].forEach((card, index) => {
      const id = board.slots[index];
      card.dataset.signature = JSON.stringify([id, candidates[id], board.selected_id === id]);
      const previous = host.children[index];
      if (!previous) host.append(card);
      else if (previous.dataset.signature !== card.dataset.signature) {
        const action = previous.contains(focused) ? focused.dataset.candidateAction : "";
        previous.replaceWith(card);
        if (action) [...card.querySelectorAll("button")].find((button) =>
          button.dataset.candidateAction === action)?.focus();
      }
    });
  }

  function renderAuthoring() {
    const detail = state.detail;
    if (!detail) return;
    const sources = detail.sources || {};
    const sourceMode = $("quality").value || "draft";
    const modeSource = (sources.phase_change_by_mode || {})[sourceMode];
    const phaseSource = modeSource === undefined ? (sources.phase_change || {}) : modeSource;
    const authoring = $("authoring");
    authoring.hidden = false;
    $("phase-source").hidden = !["head-image", "head-image-edit"].includes(state.pipeline);
    $("assembly-source").hidden = state.pipeline !== "character-assembly";
    $("view-source").hidden = !["body-reference", "head-image", "head-image-edit"].includes(state.pipeline) || state.view === "FRONT";
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
    const select = $("source-candidate");
    if (!phase) {
      select.replaceChildren(new Option("Choose another phase first", ""));
      return;
    }
    select.replaceChildren(new Option("Loading locked FRONT images…", ""));
    try {
      const data = await request(apiAt(pipeline, phase));
      if (sequence !== state.sourceRequest) return;
      const board = data.boards.FRONT;
      const candidates = board.slots.map((id) => id && board.candidates[id])
        .filter((candidate) => candidate?.locked && candidate.inventory_asset_id);
      select.replaceChildren(new Option(candidates.length ? "Choose a published FRONT" : "No locked, published FRONT available", ""),
        ...candidates.map((candidate) => new Option(`Slot ${candidate.slot} · ${candidate.render_mode}`, candidate.candidate_id)));
      const sourceMode = $("quality").value || "draft";
      const modeSource = (state.detail.sources?.phase_change_by_mode || {})[sourceMode];
      const saved = modeSource === undefined ? (state.detail.sources?.phase_change || {}) : modeSource;
      if (saved.phase === phase && saved.pipeline === pipeline) select.value = saved.candidate_id || "";
    } catch (error) {
      if (sequence === state.sourceRequest) select.replaceChildren(new Option(error.message, ""));
    }
  }

  async function saveSource(name, source, renderMode = "") {
    try {
      state.detail = await request(api(`/sources/${encodeURIComponent(name)}`), {
        method: "PUT", body: JSON.stringify({source, render_mode: renderMode,
          expected_revision: state.detail.revision}),
      });
      render();
      if (["head-image", "head-image-edit"].includes(state.pipeline)) void loadPhaseSourceCandidates();
      $("source-status").textContent = "Reference choice saved for new requests.";
    } catch (error) { $("source-status").textContent = error.message; }
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
    const focusedAction = $("review-actions").contains(focused) ? focused.dataset.candidateAction : "";
    const focusedInput = $("review-pair").contains(focused) ? focused.getAttribute("href") : "";
    const ids = board.slots.filter(Boolean);
    const index = ids.indexOf(state.reviewCandidateId);
    $("review-position").textContent = reviewPosition(candidate, index, ids.length, board.selected_id === state.reviewCandidateId);
    $("review-prev").disabled = index === 0;
    $("review-next").disabled = index === ids.length - 1;
    $("review-copy").disabled = !candidate.prompt;
    $("review-actions").innerHTML = reviewDecisions({id: state.reviewCandidateId,
      candidate: {...candidate, image: Boolean(candidate.image_path)}, selected: board.selected_id === state.reviewCandidateId,
      busy: state.mutation, escape});

    const choices = [...$("review-compare").selectedOptions].map((option) => {
      const [view, id] = option.value.split(":");
      const item = state.detail.boards[view]?.candidates?.[id];
      return item?.image_path ? {view, id, item} : null;
    }).filter(Boolean);
    const pair = $("review-pair");
    pair.style.gridTemplateColumns = choices.length ? "" : "minmax(0, 1fr)";
    const card = (title, image, item) => `<figure><header><strong>${escape(title)}</strong></header>${item.image_path ? `<img src="${escape(image)}" alt="${escape(title)}">` : `<p>${item.status === "FAILED" ? escape(item.error || "Render failed.") : "Image pending"}</p>`}<details><summary>Prompt and ordered inputs</summary><pre>${escape(item.prompt || "")}</pre>${item === candidate ? reviewInputs(item.render_request?.inputs,
      index => api(`/views/${state.view}/candidates/${state.reviewCandidateId}/inputs/${index}`), escape) : ""}</details></figure>`;
    const open = [...pair.querySelectorAll("details")].map((details) => details.open);
    pair.innerHTML = `${card(`Candidate · Slot ${candidate.slot} · ${candidate.render_mode}`, imageUrl(state.reviewCandidateId), candidate)}${choices.map(({view, id, item}) => card(`${view.replaceAll("_", " ")} · Slot ${item.slot} · ${item.render_mode}`, comparisonImageUrl(view, id), item)).join("")}`;
    [...pair.querySelectorAll("details")].forEach((details, index) => { details.open = open[index] || false; });
    if (focusedAction) {
      const buttons = [...$("review-actions").querySelectorAll("button:not(:disabled)")];
      (buttons.find(button => button.dataset.candidateAction === focusedAction) || $("review-close")).focus();
    } else if (focusedInput) {
      [...pair.querySelectorAll("a")].find(link => link.getAttribute("href") === focusedInput)?.focus();
    }
  }

  function renderTemplateProposal() {
    const host = $("template-proposal");
    const proposal = state.templateProposal;
    host.replaceChildren();
    host.hidden = !proposal;
    if (!proposal) return;
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
        } catch (error) { show(error.message, true); accept.disabled = false; }
      });
      host.append(accept);
    }
  }

  async function costumeOptions() {
    if (state.pipeline !== "costume-dressing") return;
    const params = query();
    const data = await request(`/api/costumes?${params}`);
    const select = $("costume");
    select.replaceChildren(...data.costumes.map((costume) => {
      const option = document.createElement("option");
      option.value = costume.slug;
      option.textContent = costume.name;
      return option;
    }));
    if (!data.costumes.some((costume) => costume.slug === state.costume)) state.costume = "";
    select.value = state.costume;
  }

  async function activate(pipeline) {
    state.pipeline = pipeline || state.pipeline || new URLSearchParams(location.search).get("pipeline") || "body-reference";
    state.templateProposal = null;
    $("apply-phase-change").checked = false;
    state.request += 1;
    state.detail = null;
    $("board").replaceChildren();
    if ($("review").open) $("review").close();
    state.costume = state.pipeline === "costume-dressing"
      ? new URLSearchParams(location.search).get("costume") || state.costume : "";
    state.view = new URLSearchParams(location.search).get("view") || state.view;
    state.active = true;
    stopPolling();
    try {
      if (state.pipeline === "costume-dressing" && !state.costume) {
        $("costume-wrap").hidden = false;
        await costumeOptions();
        if (!state.costume) {
          show("Choose a costume to open its Asset Container.");
          return;
        }
      }
      await loadDetail();
      const savedProposal = await request(api("/template-proposals"));
      state.templateProposal = savedProposal.proposal;
      renderTemplateProposal();
      show("Container ready.");
    } catch (error) {
      show(error.message, true);
    }
  }

  async function generate(count, renderMode, replacement = {}) {
    if (state.mutation || !state.detail) return;
    const scope = api();
    const sequence = state.request;
    const view = state.view;
    const buttons = [...document.querySelectorAll(".character-container-render-action")];
    state.mutation = true;
    buttons.forEach((button) => { button.disabled = true; });
    show("Preparing render…");
    try {
      const result = await request(api(`/views/${encodeURIComponent(view)}/generate`), {
        method: "POST", body: JSON.stringify({count, render_mode: renderMode,
          aspect_ratio: $("aspect").value, expected_revision: state.detail.revision,
          apply_phase_change: $("apply-phase-change").checked, ...replacement}),
      });
      if (!pageVisible() || sequence !== state.request || scope !== api() || view !== state.view) return;
      state.detail = result;
      render();
      show("Render slots updated.");
    } catch (error) {
      if (sequence === state.request && scope === api() && view === state.view && pageVisible()) {
        show(error.message, true);
        await loadDetail().catch(() => {});
      }
    } finally {
      state.mutation = false;
      buttons.forEach((button) => { button.disabled = false; });
    }
  }

  async function previewPrompt() {
    const button = $("prompt-preview-button");
    button.disabled = true;
    try {
      const preview = await request(api(`/views/${encodeURIComponent(state.view)}/prompt`), {
        method: "POST", body: JSON.stringify({render_mode: $("quality").value,
          apply_phase_change: $("apply-phase-change").checked}),
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
    } catch (error) { show(error.message, true); }
    finally { button.disabled = false; }
  }

  document.querySelectorAll(".character-container-render-action").forEach((button) => {
    button.addEventListener("click", () => void generate(Number(button.dataset.count), button.dataset.quality));
  });
  $("prompt-preview-button").addEventListener("click", () => void previewPrompt());
  $("edit-template").addEventListener("click", async () => {
    try {
      const master = await request(api("/template"));
      await window.ZetSourceEditor.open({source_path: master.source_path,
        source_label: `Character.md · ${master.character} · ${master.phase}`, editable: true},
        (message) => show(message, true));
    } catch (error) { show(error.message, true); }
  });
  $("refresh").addEventListener("click", () => void loadDetail().then(pollProgress));
  $("costume").addEventListener("change", () => { state.costume = $("costume").value; saveRouteContext(); void activate(state.pipeline); });
  $("source-phase").addEventListener("change", () => void loadPhaseSourceCandidates());
  $("source-pipeline").addEventListener("change", () => void loadPhaseSourceCandidates());
  $("save-phase-source").addEventListener("click", () => {
    const source = {phase: $("source-phase").value, pipeline: $("source-pipeline").value,
      candidate_id: $("source-candidate").value};
    if (!source.phase || !source.candidate_id) { $("source-status").textContent = "Choose a locked, published FRONT first."; return; }
    void saveSource("phase_change_by_mode", source, $("quality").value);
  });
  $("clear-phase-source").addEventListener("click", () =>
    void saveSource("phase_change_by_mode", {}, $("quality").value));
  $("upload-phase-source").addEventListener("click", async () => {
    const file = $("phase-source-file").files?.[0];
    if (!file) { $("source-status").textContent = "Choose a PNG, JPEG, or WebP image first."; return; }
    const params = query();
    params.set("render_mode", $("quality").value);
    params.set("filename", file.name);
    params.set("expected_revision", state.detail.revision);
    try {
      state.detail = await request(`/api/character-containers/${encodeURIComponent(state.pipeline)}/sources/phase-change-upload?${params}`, {
        method: "PUT", headers: {"Content-Type": file.type || "application/octet-stream"}, body: file,
      });
      $("phase-source-file").value = "";
      render();
      $("source-candidate").replaceChildren(new Option("Managed upload selected", ""));
      $("source-status").textContent = "Managed upload saved for new requests at this quality.";
    } catch (error) { $("source-status").textContent = error.message; }
  });
  $("quality").addEventListener("change", () => {
    if (["head-image", "head-image-edit"].includes(state.pipeline)) {
      renderAuthoring();
      void loadPhaseSourceCandidates();
    }
  });
  $("save-head-pipeline").addEventListener("click", () => void saveSource("head_pipeline", $("head-pipeline").value));
  $("save-view-source").addEventListener("click", () => {
    const views = {...(state.detail.sources?.views || {}), [state.view]: $("source-view").value};
    void saveSource("views", views);
  });
  $("board").addEventListener("click", async (event) => {
    const reviewButton = event.target.closest("[data-review]");
    if (reviewButton) {
      state.originSlot = reviewButton.dataset.review;
      $("review-status").textContent = "";
      review(reviewButton.dataset.review);
      return;
    }
    const replacement = event.target.closest("[data-replace]");
    if (replacement) {
      const id = replacement.dataset.replace;
      const candidate = state.detail.boards[state.view].candidates[id];
      if (confirm(`Replace slot ${candidate.slot} and delete its current candidate?`)) {
        void generate(1, replacement.dataset.quality, {slot: candidate.slot, expected_candidate_id: id});
      }
      return;
    }
    const improve = event.target.closest("[data-template-improve]");
    if (improve) {
      improve.disabled = true;
      const originalLabel = improve.textContent;
      improve.textContent = "Preparing proposal…";
      $("authoring").open = true;
      try {
        state.templateProposal = await request(api("/template-proposals"), {method: "POST",
          body: JSON.stringify({view: state.view, candidate_id: improve.dataset.templateImprove,
            direction: $("template-guidance").value, expected_revision: state.detail.revision})});
        renderTemplateProposal();
        $("template-proposal").scrollIntoView({block: "nearest", behavior: "smooth"});
        show("Proposal ready. Review the diff and compiled prompt before accepting it.");
      } catch (error) { show(error.message, true); }
      finally { improve.disabled = false; improve.textContent = originalLabel; }
      return;
    }
    await boardAction(event);
  });

  async function boardAction(event) {
    const button = event.target.closest("[data-candidate-action], [data-board-action]");
    if (!button || state.mutation) return;
    const id = button.dataset.candidate || button.dataset.candidateId;
    const action = button.dataset.candidateAction || button.dataset.boardAction;
    const candidate = state.detail.boards[state.view].candidates[id];
    const payload = {expected_revision: state.detail.revision};
    if (action === "clear") {
      payload.expected_candidate_id = id;
      payload.confirm_selected = state.detail.boards[state.view].selected_id === id && confirm("Clear the selected candidate from this board?");
      if (state.detail.boards[state.view].selected_id === id && !payload.confirm_selected) return;
      if (candidate.locked) { show("Unlock the candidate before clearing its slot.", true); return; }
    }
    const scope = api();
    const sequence = state.request;
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
      if (!pageVisible() || sequence !== state.request || scope !== api() || view !== state.view) return;
      state.detail = result;
      state.mutation = false;
      render();
      if (!modal) {
        const card = $("board").children[candidate.slot - 1];
        card.append(feedback);
        feedback.textContent = action === "lock" ? "Locked and published." : "Slot updated.";
        const next = [...card.querySelectorAll("button:not(:disabled)")].find(control =>
          control.dataset.candidateAction === action || control.dataset.review === id);
        next?.focus();
      }
      if (modal) {
        renderReviewComparison();
        feedback.textContent = action === "lock" ? "Locked and published." : "Candidate updated.";
      }
    } catch (error) {
      if (sequence === state.request && scope === api() && view === state.view) feedback.textContent = error.message;
    } finally {
      state.mutation = false;
      button.disabled = false;

    }
  }

  $("review-actions").addEventListener("click", boardAction);
  function moveReview(offset) {
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
    [...$("board").querySelectorAll("button[data-review]")].find((button) =>
      button.dataset.review === state.originSlot)?.focus();
  });
  $("review-copy").onclick = async () => {
    const candidate = state.detail.boards[state.view].candidates[state.reviewCandidateId];
    try {
      await navigator.clipboard.writeText(candidate.prompt);
      $("review-status").textContent = "Prompt copied.";
    } catch (error) { $("review-status").textContent = error.message; }
  };
  $("review-close").addEventListener("click", () => $("review").close());
  document.addEventListener("visibilitychange", () => {
    if (!pageVisible()) { stopPolling(); return; }
    if (state.active) { startPolling(); void pollProgress(); }
    else void loadDetail().catch((error) => show(error.message, true));
  });
  window.addEventListener("zet-character-container-activate", (event) => void activate(event.detail?.pipeline));
  window.addEventListener("zet-character-container-deactivate", () => { state.active = false; stopPolling(); });
  window.ZetCharacterAssetContainer = {
    setPipeline(pipeline) { state.pipeline = pipeline || ""; },
    pipeline() { return state.pipeline; },
    context() { return {pipeline: state.pipeline, costume: state.costume, view: state.view}; },
    activate,
    deactivate() { state.active = false; stopPolling(); },
  };
  if (document.querySelector("#character-asset-container-page")?.classList.contains("active")) {
    void activate(new URLSearchParams(location.search).get("pipeline"));
  }
})();
