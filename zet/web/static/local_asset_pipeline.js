(() => {
  const pagePipelines = {
    "local-body-reference": "body-reference",
    "local-head-image": "head-image",
    "local-head-image-edit": "head-image-edit",
    "local-character-assembly": "character-assembly",
    "local-costume-dressing": "costume-dressing",
  };
  const $ = (id) => document.getElementById(`local-pipeline-${id}`);
    const statusLabels = {
    QUEUED: "Queued", PREFLIGHT: "Checking inputs", RUNNING: "Running", STOPPING: "Stopping",
    REEVALUATING: "Re-evaluating", READY_FOR_VIEWS: "Ready for other views",
    AWAITING_FRONT_ANCHOR: "Awaiting FRONT selection", AWAITING_HUMAN_SELECTION: "Awaiting selection",
    REVIEW_REQUIRED: "Review required", COMPLETE: "Complete", CANCELLED: "Stopped",
    STOPPED: "Stopped", INTERRUPTED: "Interrupted", ERROR: "Error", PENDING: "Pending",
    FAILED: "Failed",
  };
  const evaluationLabels = {
    STAGING: "Staging ranking", RUNNING: "Ranking running", COMPLETE: "Ranking complete",
    QUEUED: "Queued", FAILED: "Ranking failed", EMPTY: "No images to rank", STALE: "Ranking stale",
    SUPERSEDED: "Superseded", SKIPPED: "Skipped",
  };
  const renderStatusLabels = {
    PENDING: "Image pending", QUEUED: "Render queued", RUNNING: "Rendering",
    COMPLETE: "Image ready", FAILED: "Render failed",
  };
  const activeStatuses = new Set(["PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING"]);
  const state = { pipeline: "", generation: 0, run: null, runs: [], reviewCandidates: [], reviewIndex: -1,
    frontSourcePath: "", poll: null, previewGeneration: 0, sourcePreviewGeneration: 0, contextKey: "", compareOpposite: false,
    polledRun: null, pollInFlight: false, renderedSelections: {}, runsState: "loading",
    runState: "absent", costumesState: "absent", runRequest: 0, reviewActionPending: false, bulkActionPending: false };
  const restoreParams = new URLSearchParams(window.location.search);

  function contextKey() {
    return `${document.querySelector("#universe-select").value}\u0000${document.querySelector("#character-select").value}\u0000${document.querySelector("#phase-select").value}\u0000${selectedCostume()}`;
  }

  function isCostume() { return state.pipeline === "costume-dressing"; }
  function hasSharedAssetRouter() { return ["character-assembly", "costume-dressing"].includes(state.pipeline); }
  function baseUrl() { return `/api/local/${state.pipeline}`; }
  function selectedCostume() { return $("costume")?.value || ""; }
  function query(extra = {}) {
    const params = new URLSearchParams({
      character: document.querySelector("#character-select").value,
      phase: document.querySelector("#phase-select").value,
      ...extra,
    });
    if (isCostume()) params.set("costume", selectedCostume());
    return `?${params.toString()}`;
  }

  function syncPipelineRoute() {
    if (!state.pipeline || !document.querySelector("#local-pipeline-page").classList.contains("active")) return;
    const params = new URLSearchParams(window.location.search);
    params.set("page", Object.keys(pagePipelines).find((page) => pagePipelines[page] === state.pipeline));
    const runId = $("runs").value;
    if (runId) params.set("local_batch", runId);
    else params.delete("local_batch");
    if (isCostume() && selectedCostume()) params.set("local_costume", selectedCostume());
    else params.delete("local_costume");
    const search = params.toString();
    window.history.replaceState({}, "", `${window.location.pathname}${search ? `?${search}` : ""}${window.location.hash}`);
  }

  async function request(path, options = {}) {
    const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json",
      "X-Zet-Universe": document.querySelector("#universe-select").value, ...options.headers } });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || response.statusText || "Request failed");
    return data;
  }

  function setStatus(message, error = false) {
    $("status").textContent = message || "";
    $("status").classList.toggle("error", error);
    $("status").classList.toggle("success", !error && Boolean(message));
  }

  function busy(run = state.run) { return Boolean(run && (activeStatuses.has(run.status) || run.slot_work_pending)); }

  function unstartedViews(run) {
    return (run?.views || []).filter((view) => (view !== "FRONT" || hasSharedAssetRouter()) && (() => {
      const candidates = (run.candidates || []).filter((candidate) => candidate.view === view);
      return candidates.length > 0 && candidates.some((candidate) => candidate.image_filled === false || !candidate.image_path);
    })());
  }

  function route(action, runId = state.run?.run_id || "", view = "", candidateId = "") {
    const id = encodeURIComponent(runId);
    const encodedView = encodeURIComponent(view);
    const candidate = encodeURIComponent(candidateId);
    switch (action) {
      case "preview": return `${baseUrl()}/preview`;
      case "runs": return `${baseUrl()}/runs${query()}`;
      case "create": return `${baseUrl()}/runs`;
      case "detail": return `${baseUrl()}/runs/${id}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "image": return `${baseUrl()}/runs/${id}/images/${candidate}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "reference-image": return `${baseUrl()}/runs/${id}/reference-images/${encodedView}/${encodeURIComponent(candidate)}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "rename": return `${baseUrl()}/runs/${id}/name${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "start": return `${baseUrl()}/runs/${id}/start${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "resume": return `${baseUrl()}/runs/${id}/resume${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "stop": return `${baseUrl()}/runs/${id}/stop${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "rerun": return `${baseUrl()}/runs/${id}/rerun${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "reevaluate": return `${baseUrl()}/runs/${id}/reevaluate${query()}`;
      case "delete": return `${baseUrl()}/runs/${id}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "rerun-view": return `${baseUrl()}/runs/${id}/views/${encodedView}/rerun${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "rerun-failed": return `${baseUrl()}/runs/${id}/rerun-failed${query({ view })}`;
      case "observations": return `${baseUrl()}/runs/${id}/views/${encodedView}/observations${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "reanalyze": return `${baseUrl()}/runs/${id}/views/${encodedView}/reanalyze${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "prompt-improvement-package": return `${baseUrl()}/runs/${id}/prompt-improvement-package${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "move-rank": return `${baseUrl()}/runs/${id}/views/${encodedView}/ranking/move${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "select":
      case "unselect": return `${baseUrl()}/runs/${id}/views/${encodedView}/select${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "review": return `${baseUrl()}/runs/${id}/candidates/${candidate}/review${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "retry": return `${baseUrl()}/runs/${id}/candidates/${candidate}/retry${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "lock": return `${baseUrl()}/runs/${id}/views/${encodedView}/lock${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "lock-all-preview":
      case "lock-all":
      case "unlock-all": return `${baseUrl()}/runs/${id}/${action}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "lock-preview": return `${baseUrl()}/runs/${id}/views/${encodedView}/lock-preview${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "unlock": return `${baseUrl()}/runs/${id}/views/${encodedView}/unlock${query()}`;
      case "proceed": return `${baseUrl()}/runs/${id}/views/FRONT/proceed${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "image-prompt": return `${baseUrl()}/runs/${id}/image-prompt/${encodedView}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
            case "source": return ["head-image", "head-image-edit"].includes(state.pipeline)
        ? `${baseUrl()}/runs/${id}/source`
        : `${baseUrl()}/runs/${id}/sources/${encodedView}/${encodeURIComponent(candidate)}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      default: throw new Error(`Unsupported Local workflow action: ${action}`);
    }
  }

  function versionedImageUrl(url, version) {
    if (!version) return universeImageUrl(url);
    const resolved = universeImageUrl(url);
    return `${resolved}${resolved.includes("?") ? "&" : "?"}v=${encodeURIComponent(version)}`;
  }

  function payload() {
    const lockedPhaseSource = state.pipeline === "head-image-edit" && $("apply-phase-change").checked && $("source-mode").value === "locked";
    return {
      character: document.querySelector("#character-select").value,
      phase: document.querySelector("#phase-select").value,
      costume: isCostume() ? selectedCostume() : "",
      front_count: Number($("front-count").value),
      other_count: Number($("other-count").value),
      use_front_anchor: state.pipeline === "character-assembly" ? false : hasSharedAssetRouter() ? $("use-anchor").checked : state.pipeline === "body-reference" || ["head-image", "head-image-edit"].includes(state.pipeline),
      head_pipeline: state.pipeline === "character-assembly" ? $("head-pipeline").value : "head-image",
      front_source_path: lockedPhaseSource ? "" : state.frontSourcePath,
      front_source_phase: lockedPhaseSource ? $("source-phase").value : "",
      apply_phase_change: state.pipeline === "head-image-edit" ? $("apply-phase-change").checked
        : state.pipeline === "head-image" && Boolean(state.frontSourcePath) && $("apply-phase-change").checked,
      source_batches: hasSharedAssetRouter() ? Object.fromEntries(Array.from($("source-batches").querySelectorAll("select[data-source-role]"), (select) => [select.dataset.sourceRole, select.value])) : {},
    };
  }

  function lockedPhaseSourceSelected() {
    return state.pipeline === "head-image-edit" && $("apply-phase-change").checked && $("source-mode").value === "locked";
  }

  function populateSourcePhases() {
    const select = $("source-phase");
    const previous = select.value;
    const target = document.querySelector("#phase-select").value;
    select.replaceChildren(new Option("Choose a source phase", ""));
    for (const option of document.querySelector("#phase-select").options) {
      if (option.value && option.value !== target) select.add(new Option(option.textContent, option.value));
    }
    select.value = Array.from(select.options).some(option => option.value === previous) ? previous : "";
  }

  function updateSourceControls() {
    const phaseChange = state.pipeline === "head-image-edit" && $("apply-phase-change").checked;
    $("source-mode-option").hidden = !phaseChange;
    $("upload-source").hidden = lockedPhaseSourceSelected();
    $("locked-source").hidden = !lockedPhaseSourceSelected();
    if (state.pipeline === "head-image-edit") $("apply-phase-change").disabled = false;
  }

  async function refreshLockedPhaseSource() {
    const generation = ++state.sourcePreviewGeneration;
    const host = $("locked-preview");
    host.replaceChildren();
    if (!lockedPhaseSourceSelected()) return;
    const character = document.querySelector("#character-select").value;
    const phase = $("source-phase").value;
    if (!phase) { host.textContent = "Choose a source phase."; return; }
    host.textContent = "Checking locked FRONT image…";
    try {
      const result = await request(`/api/local/assets?${new URLSearchParams({ character, phase })}`);
      if (generation !== state.sourcePreviewGeneration || !lockedPhaseSourceSelected() || $("source-phase").value !== phase) return;
      const asset = (result.assets || []).find(item => item.pipeline?.toLowerCase() === "head-image-edit"
        && item.view === "FRONT" && !item.qualifier);
      host.replaceChildren();
      if (asset) {
        const image = document.createElement("img");
        image.src = universeImageUrl(`/api/local/assets/${encodeURIComponent(asset.key)}/image?${new URLSearchParams({ character, phase, v: asset.image_sha256 || "" })}`);
        image.alt = `Locked FRONT Head-Image Edit image from ${phase}`;
        host.append(image);
      } else {
        host.append(`No locked FRONT Head-Image Edit image in ${phase}. `);
        const link = document.createElement("a");
        link.href = `/?${new URLSearchParams({ page: "local-head-image-edit", character, phase })}`;
        link.textContent = `Go to ${phase} and lock FRONT first`;
        host.append(link);
      }
    } catch (error) {
      if (generation === state.sourcePreviewGeneration) host.textContent = error.message;
    }
  }

  function continuationDisabled(run) {
    return busy(run) || Boolean(run?.slot_render_ids?.length) || !run?.progression?.can_continue;
  }

  function orderedViews(run) {
    const order = ["FRONT", "FRONT_LEFT_3_4", "FRONT_RIGHT_3_4", "LEFT_PROFILE", "RIGHT_PROFILE", "BACK_LEFT_3_4", "BACK_RIGHT_3_4", "BACK"];
    const position = view => order.includes(view) ? order.indexOf(view) : order.length;
    return [...(run?.views || [])].sort((a, b) => position(a) - position(b));
  }

  function syncViewContinueButtons(host = $("views")) {
    const top = $("proceed");
    for (const button of host.querySelectorAll("button[data-local-action='proceed']")) {
      button.hidden = top.hidden || top.disabled;
      button.disabled = top.disabled;
      button.textContent = top.textContent;
      button.title = top.title;
    }
  }

  function frontRenderControl() {
    const run = state.run;
    if (isCostume()) return null;
    if (state.pipeline === "body-reference" && run && !run.progression) {
      const ready = run.status === "QUEUED" && !busy(run);
      return { disabled: !ready, reason: ready ? "Start the queued Body batch." : "Queue a Body batch before starting renders.",
        start: async () => { if (state.run?.status !== "QUEUED" || busy(state.run)) throw new Error("Body batch is not ready to start."); await perform("start"); } };
    }
    return { disabled: continuationDisabled(run) || run?.progression?.stage !== -1,
      reason: run?.progression?.stage >= 0 ? "FRONT has already started. Use the view controls to generate more images." : run?.progression?.reason || "Generate FRONT from the accepted template version.",
      start: async () => {
        if (continuationDisabled(state.run) || state.run?.progression?.stage !== -1) throw new Error("FRONT is not ready to start.");
        await perform("proceed");
      } };
  }

  function setBusyControls() {
    const run = state.run;
    const isBusy = busy(run) || Boolean(run?.slot_render_ids?.length);
    const resumable = ["INTERRUPTED", "STOPPED"].includes(run?.status)
      || (run?.status === "CANCELLED" && run?.created_by_autogenerate);
    $("start").hidden = !run;
    $("start").disabled = isBusy || !(run?.status === "QUEUED" || resumable);
    $("start").textContent = resumable ? "Resume batch" : "Start batch";
    $("stop").hidden = !busy(run);
    $("stop").disabled = !busy(run);
    $("rerun").disabled = !run || isBusy;
    $("reevaluate").disabled = !run || isBusy || !(run.candidates || []).some((item) => item.image_path);
    $("prompt-improvement-package").hidden = !run;
    if (run) $("prompt-improvement-package").href = route("prompt-improvement-package", run.run_id);
    $("delete").disabled = !run || isBusy;
    $("rename").hidden = !run;
    $("proceed").hidden = !run;
    $("proceed").disabled = isBusy || (run?.status === "READY_FOR_VIEWS" && (run.target_views || []).length > 0)
      || (!run?.front_anchor && !(hasSharedAssetRouter()
        && (run?.use_front_anchor === false || unstartedViews(run).includes("FRONT"))))
      || !unstartedViews(run).length;
    if (run?.progression) {
      $("start").hidden = !resumable;
      $("proceed").hidden = false;
      $("proceed").disabled = continuationDisabled(run);
      $("proceed").textContent = state.pipeline === "character-assembly"
        ? (run.progression.next_views.includes("FRONT") ? "Run front"
          : run.progression.next_views.length ? "Run remaining" : "All views rendered")
        : isCostume() ? (run.progression.next_views.length ? "Run ready views" : "No unrendered views ready") : run.progression.next_views.length ? `Continue → ${run.progression.next_views.join(" + ")}` : "All stages open";
      $("proceed").title = run.progression.reason || (state.pipeline === "character-assembly"
        ? "Render FRONT first, select it, then run remaining views. Luna compares proportions and identity with the selected FRONT."
        : "Generate the next stage from your selected images");
      $("anchor-option").hidden = true;
    }
    const progression = $("progression");
    progression.hidden = !run?.progression;
    if (run?.progression) {
      progression.replaceChildren();
      const label = document.createElement("p");
      label.textContent = run.progression.prompt_review_required ? "Phase 1 · Analyze and accept the governing prompts below."
        : run.progression.complete ? "All requested views selected. Refinement and publication remain available."
          : run.progression.stage < 0 ? (state.pipeline === "character-assembly" ? "Ready to assemble FRONT." : "Prompts accepted · Ready to generate FRONT.")
            : `Stage ${run.progression.stage + 1} · ${run.progression.current_views.join(" + ")}. ${run.progression.reason}`;
      if (state.pipeline === "character-assembly" && !run.progression.complete) {
        label.textContent = run.progression.reason || (run.progression.next_views.length
          ? (run.progression.next_views.includes("FRONT")
            ? "Run front, then select the FRONT image Luna should use to compare proportions and identity."
            : "Run remaining views. Luna will prioritize head-to-body proportion and identity matches with your selected FRONT; renders use only matching body and head images.")
          : "All requested views rendered. Select and publish the images you want to keep.");
      }
      if (isCostume()) label.textContent = run.progression.prompt_review_required
        ? "Analyze and accept governing prompts, then choose each view’s rendering mode and reference."
        : run.progression.reason || "Run any view with available mode inputs, or use Run ready views for the remaining candidates.";
      progression.append(label);
      for (const warning of run.reference_warnings || []) {
        const note = document.createElement("p"); note.className = "muted";
        note.textContent = `${warning.view}: ${warning.message}`; progression.append(note);
      }
    }
    if (state.pipeline === "character-assembly") $("anchor-option").hidden = true;
    $("back-reference-label").hidden = ["body-reference", "head-image-edit", "character-assembly", "costume-dressing"].includes(state.pipeline) || !run?.progression?.next_views.includes("BACK");
    if (run && $("back-reference").dataset.runId !== run.run_id) {
      $("back-reference").value = run.character_progression?.back_reference || "BACK_LEFT_3_4";
      $("back-reference").dataset.runId = run.run_id;
    }
    for (const option of $("back-reference").options) option.disabled = !run?.selected_views?.[option.value];
    syncViewContinueButtons();
  }

  function addLink(parent, label, href) {
    const link = document.createElement("a");
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = label;
    parent.append(link);
  }

  function universeImageUrl(path) {
    const url = new URL(path, window.location.origin);
    const universe = document.querySelector("#universe-select").value;
    if (universe) url.searchParams.set("universe_id", universe);
    return url.pathname + url.search;
  }

  function imageUrl(candidate) { const url = universeImageUrl(route("image", state.run.run_id, "", candidate.candidate_id)); return `${url}${url.includes("?") ? "&" : "?"}v=${encodeURIComponent(candidate.ask_id || candidate.image_sha256 || candidate.candidate_id)}`; }

  function renderErrorDetails(candidate) {
    const message = String(candidate.render_error || "").trim();
    if (!message) return null;
    const details = document.createElement("details");
    details.className = "local-pipeline-render-error error-text";
    const summary = document.createElement("summary");
    const firstLine = message.split(/\r?\n/)[0];
    summary.textContent = `Render error: ${firstLine.length > 160 ? `${firstLine.slice(0, 160)}…` : firstLine}`;
    const body = document.createElement("p");
    body.textContent = message;
    details.append(summary, body);
    return details;
  }

  function addButton(host, text, action, { disabled = false, primary = false, view = "", candidate = "", title = "" } = {}) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    if (title) button.title = title;
    if (["delete", "clear"].includes(action)) button.classList.add("danger-text-action");
    button.dataset.localAction = action;
    button.dataset.view = view;
    button.dataset.candidate = candidate;
    button.disabled = disabled;
    if (primary) button.classList.add("primary-action");
    host.append(button);
    return button;
  }

  function addRecompileOption(host, id = "") {
    const label = document.createElement("label");
    label.className = "local-pipeline-recompile-option";
    const text = document.createElement("span");
    text.textContent = "Recompile";
    label.title = "Generate, Regen and Regen view: compile the prompt from current templates first. Retry reuses saved inputs.";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.dataset.recompile = "true";
    if (id) input.id = id;
    label.append(text, input);
    label.addEventListener("click", (event) => event.stopPropagation());
    host.append(label);
    return input;
  }

  function renderSelectedViews(run) {
    const host = $("selected");
    host.replaceChildren();
    const selected = run.selected_views || {};
    const qualifier = isCostume() ? String(run.costume || "").trim().toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "_").replace(/^_+|_+$/g, "") : "";
    const assetKey = (view) => `${state.pipeline}${qualifier ? `:${qualifier}` : ""}:${view}`;
    const controls = document.createElement("div");
    controls.className = "button-row local-pipeline-bulk-controls";
    const hasUnlockedSelection = Object.entries(selected).some(([view, id]) => {
      const asset = run.local_assets?.[assetKey(view)];
      return id && !(asset?.locked && asset.batch_id === run.run_id && asset.candidate_id === id);
    });
    const hasLocks = Object.entries(run.local_assets || {}).some(([key, asset]) =>
      asset.locked && key === assetKey(asset.view));
    addButton(controls, "Lock all", "lock-all", { disabled: state.bulkActionPending || !hasUnlockedSelection });
    addButton(controls, "Unlock all", "unlock-all", { disabled: state.bulkActionPending || !hasLocks });
    host.append(controls);
    const lockNotice = document.createElement("p");
    lockNotice.className = "local-pipeline-lock-notice";
    lockNotice.setAttribute("role", "status");
    lockNotice.textContent = "Locked images for this pipeline in another batch.";
    lockNotice.hidden = true;
    host.append(lockNotice);
    for (const view of orderedViews(run)) {
      const article = document.createElement("article");
      article.className = "local-pipeline-selected-card";
      const title = document.createElement("h2");
      title.textContent = view;
      article.append(title);
      const candidate = (run.candidates || []).find((item) => item.candidate_id === selected[view] && item.image_path);
      if (!candidate) {
        const empty = document.createElement("p");
        empty.className = "muted";
        empty.textContent = "No image selected";
        article.append(empty);
      } else {
        const image = document.createElement("img");
        image.loading = "lazy";
        image.src = imageUrl(candidate);
        image.alt = `Selected ${view} candidate ${candidate.candidate_id}`;
        article.append(image);
        const assetKey = `${state.pipeline}${qualifier ? `:${qualifier}` : ""}:${view}`;
        const asset = run.local_assets?.[assetKey];
        const locked = Boolean(asset?.locked && asset.candidate_id === candidate.candidate_id
          && asset.batch_id === run.run_id);
        const lockedInAnotherBatch = Boolean(asset?.locked && asset.batch_id !== run.run_id);
        if (lockedInAnotherBatch) lockNotice.hidden = false;
        const lockState = document.createElement("p");
        lockState.className = locked ? "success-text" : "muted";
        lockState.textContent = locked ? "Locked local asset" : "Selected · not locked";
        article.append(lockState);
        const controls = document.createElement("div");
        controls.className = "button-row compact";
        const overrideNeedsUnlock = Boolean(candidate.override && asset?.locked && !locked);
        if (overrideNeedsUnlock) {
          lockState.textContent = "Override selected. Unlock the published image before locking this override.";
          addButton(controls, "Unlock published image", "unlock", { view });
        }
        addButton(controls, locked ? "Unlock" : "Lock", locked ? "unlock" : "lock",
          { view, disabled: overrideNeedsUnlock });
        if (!locked) addButton(controls, "Unselect", "unselect", { view, candidate: candidate.candidate_id });
        const refine = document.createElement("a");
        refine.textContent = "Refine";
        refine.href = refinementUrl(view);
        refine.className = "button";
        controls.append(refine);
        article.append(controls);
      }
      host.append(article);
    }
    host.hidden = !run.views?.length;
  }

  function refinementUrl(view) {
    const params = new URLSearchParams({ pipeline: state.pipeline, run_id: state.run.run_id, view,
      universe_id: document.querySelector("#universe-select").value });
    if (isCostume()) params.set("costume", selectedCostume());
    return `/local-character-refinement?${params}`;
  }

  function renderCandidate(view, candidate, ranking, run) {
    const card = document.createElement("article");
    const selectedViews = run.selected_views || {};
    const selected = run.selected_views?.[view] === candidate.candidate_id;
    card.className = `local-pipeline-candidate${selected ? " is-selected" : ""}`;
    card.dataset.view = view;
    card.dataset.candidate = candidate.candidate_id;
    card.dataset.slot = String(candidate.slot || candidate.ordinal || "");
    const heading = document.createElement("h3");
    heading.textContent = `Slot ${candidate.slot || candidate.ordinal} · ${candidate.candidate_id}`;
    card.append(heading);
    if (candidate.image_path) {
      const imageButton = document.createElement("button");
      imageButton.className = "local-pipeline-candidate-image";
      imageButton.dataset.localAction = "review";
      imageButton.dataset.candidate = candidate.candidate_id;
      const image = document.createElement("img");
      image.loading = "lazy";
      image.src = imageUrl(candidate);
      image.alt = `${view} candidate ${candidate.candidate_id}`;
      imageButton.append(image);
      card.append(imageButton);
      if (candidate.elapsed_seconds != null && Number.isFinite(Number(candidate.elapsed_seconds))) {
        const generationTime = document.createElement("p");
        generationTime.className = "local-pipeline-generation-time muted";
        generationTime.textContent = `Generated in ${Math.round(Number(candidate.elapsed_seconds))} seconds`;
        card.append(generationTime);
      }
    }
    const status = document.createElement("p");
    status.className = "muted image-card-state";
    const rankingOrder = ranking.luna_ordered_candidate_ids?.length
      ? ranking.luna_ordered_candidate_ids
      : ranking.ordered_candidate_ids || [];
    const rank = rankingOrder.indexOf(candidate.candidate_id);
    status.textContent = `${candidate.slot_waiting ? `Waiting for prerequisites · ${candidate.slot_waiting}` : renderStatusLabels[candidate.render_status] || statusLabels[candidate.status] || candidate.status || "Unknown"}${rank >= 0 ? ` · Rank #${rank + 1}${ranking.status === "STALE" ? " (stale)" : ""}` : ""}`;
    if (candidate.override) status.textContent += " / Override";
    card.append(status);
    const renderError = renderErrorDetails(candidate);
    if (renderError) card.append(renderError);
    const human = document.createElement("p");
    human.className = "muted";
    human.textContent = `Human ${candidate.human_review?.decision || "undecided"}`;
    card.append(human);
    const controls = document.createElement("div");
    controls.className = "button-row compact local-pipeline-candidate-controls";
    addButton(controls, "Review", "review", { view, candidate: candidate.candidate_id });
    if (candidate.image_path) {
      addButton(controls, selected ? "Unselect" : "Select", selected ? "unselect" : "select", { primary: !selected, view, candidate: candidate.candidate_id });
    } else if (selected) addButton(controls, "Unselect", "unselect", {view, candidate: candidate.candidate_id});
    const slot = candidate.slot;
    const disabled = Boolean(candidate.slot_reason);
    if (slot) {
      if (slot <= 8 && (candidate.image_path || ["QUEUED", "RUNNING"].includes(candidate.render_status))) addSlotButton(controls, "Regen", "regenerate", view, slot, disabled, candidate.slot_reason);
      else if (slot <= 8 && candidate.render_status === "FAILED") addSlotButton(controls, "Retry", "retry", view, slot, disabled, candidate.slot_reason);
      addSlotButton(controls, "Clear", "clear", view, slot, disabled, candidate.slot_reason);
    }
    if (candidate.review_error) addButton(controls, "Retry review", "retry", { disabled: busy(run), view, candidate: candidate.candidate_id });
    const locked = Object.values(run.local_assets || {}).some(asset => asset.locked && asset.batch_id === run.run_id && asset.candidate_id === candidate.candidate_id && asset.view === view);
    card.dataset.state = locked ? "locked" : selected ? "selected" : candidate.slot_waiting ? "reserved" : candidate.render_status === "FAILED" ? "failed" : candidate.image_path ? "available" : "pending";
    if (selected) status.textContent += " · Selected";
    if (locked) status.textContent += " · Locked";
    if (candidate.slot_reason) { const reason = document.createElement("p"); reason.className = "slot-action-reason muted"; reason.textContent = candidate.slot_reason; card.append(reason); }
    if (controls.childElementCount) card.append(controls);
    window.ZetImageCardUI.scan(card);
    return card;
  }

  function addSlotButton(host, label, operation, view, slot, disabled, reason = "") {
    const button = document.createElement("button"); button.type = "button"; button.textContent = operation === "regenerate" ? "Regenerate" : operation === "clear" ? "Clear slot" : label;
    if (operation === "clear") button.className = "danger-text-action";
    if (operation === "generate") button.className = "primary-action";
    button.disabled = disabled; button.title = reason || "";
    button.addEventListener("click", () => void slotAction(operation, view, slot).catch(error => setStatus(error.message, true)));
    host.append(button);
  }

  async function slotAction(operation, view, slot, count = 1) {
    const generation = state.generation, runId = state.run.run_id, key = contextKey();
    const suffix = isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : "";
    const path = `${baseUrl()}/runs/${encodeURIComponent(runId)}/views/${encodeURIComponent(view)}/slots${slot ? `/${slot}/${operation}` : ""}${suffix}`;
    const recompile = Boolean($("views").querySelector(`details[data-view="${view}"] input[data-recompile]`)?.checked);
    await request(path, {method: "POST", body: JSON.stringify({... (slot ? {expected_candidate_id: state.run.slots_by_view?.[view]?.[slot - 1] || null} : {count}), recompile})});
    if (generation !== state.generation || state.run?.run_id !== runId || contextKey() !== key) return;
    await loadRun(runId, generation);
    setStatus(operation === "clear" ? "Slot cleared." : "Renders queued.");
  }

  function mergeLiveRun(latest) {
    const currentId = state.reviewCandidates[state.reviewIndex]?.candidate_id;
    const decision = $("review-panel").querySelector("input[name='local-human-decision']:checked")?.value;
    const oldRun = state.run;
    state.run = latest;
    window.ZetTemplateImprovement?.update(latest, state.pipeline, () => loadRun(latest.run_id), frontRenderControl);
    const signature = run => JSON.stringify([run?.candidates, run?.slots_by_view, run?.slot_controls, run?.rankings, run?.evaluations, run?.selected_views, run?.local_assets, run?.view_reviews, run?.sources, run?.front_source_sha256, run?.view_reference_recipes, run?.active_template_revision_id]);
    const changed = signature(oldRun) !== signature(latest);
    const replacement = document.createElement("div");
    if (changed) renderViews(latest, replacement);
    const host = $("views");
    for (const next of [...replacement.children]) {
      const previous = [...host.children].find(item => item.dataset.view === next.dataset.view);
      if (!previous) { host.append(next); continue; }
      const gallery = previous.querySelector(".local-pipeline-gallery"), newGallery = next.querySelector(".local-pipeline-gallery");
      if (gallery && newGallery) {
        const newCards = [...newGallery.children];
        const cardKey = card => card.dataset.candidate ? `candidate:${card.dataset.candidate}` : `slot:${card.dataset.slot}`;
        const oldKeys = [...gallery.children].map(cardKey), newKeys = newCards.map(cardKey);
        if (oldKeys.length !== newKeys.length || oldKeys.some((key, index) => key !== newKeys[index])) {
          const focus = document.activeElement;
          const focusedCard = focus?.closest(".local-pipeline-candidate");
          const focusKey = focusedCard ? cardKey(focusedCard) : "";
          const focusAction = focus?.dataset.imageAction || (focus?.classList.contains("local-pipeline-candidate-image") ? "preview" : "");
          const openDetails = new Map([...gallery.children].map(card => [cardKey(card), [...card.querySelectorAll("details")].map(section => section.open)]));
          for (const card of newCards) {
            const open = openDetails.get(cardKey(card)) || [];
            card.querySelectorAll("details").forEach((section, index) => { if (open[index] !== undefined) section.open = open[index]; });
          }
          gallery.replaceChildren(...newCards);
          if (focusKey && focusAction) {
            const target = [...gallery.children].find(card => cardKey(card) === focusKey);
            const control = focusAction === "preview" ? target?.querySelector(".local-pipeline-candidate-image")
              : [...(target?.querySelectorAll("button,a") || [])].find(button => button.dataset.imageAction === focusAction);
            control?.focus({ preventScroll: true });
          }
        } else {
          for (let index = 0; index < newCards.length; index++) {
            const card = gallery.children[index], newCard = newCards[index];
            [...card.querySelectorAll("details")].forEach((section, sectionIndex) => { const nextSection = newCard.querySelectorAll("details")[sectionIndex]; if (nextSection) nextSection.open = section.open; });
            if (card.outerHTML === newCard.outerHTML) continue;
            const focus = document.activeElement;
            const focusAction = card.contains(focus) ? focus?.dataset.imageAction || (focus?.classList.contains("local-pipeline-candidate-image") ? "preview" : "") : "";
            card.replaceWith(newCard);
            const control = focusAction === "preview" ? newCard.querySelector(".local-pipeline-candidate-image")
              : [...newCard.querySelectorAll("button,a")].find(button => button.dataset.imageAction === focusAction);
            if (focusAction) control?.focus({ preventScroll: true });
          }
          while (gallery.children.length > newCards.length) gallery.lastElementChild.remove();
        }
      }
      const view = next.dataset.view;
      const sourceSignature = run => JSON.stringify([run?.sources?.[view], run?.front_source_sha256, (run?.candidates || []).filter(item => item.view === view).map(item => item.reference_images)]);
      if (sourceSignature(oldRun) !== sourceSignature(latest)) {
        previous.querySelectorAll(".local-pipeline-sources").forEach(section => section.remove());
        next.querySelectorAll(".local-pipeline-sources").forEach(section => previous.insertBefore(section, previous.querySelector(".local-pipeline-observations")));
      }
      const observations = previous.querySelector("textarea[data-view-observations]");
      if (observations && observations.value === (oldRun?.view_reviews?.[view]?.observations || "")) observations.value = latest.view_reviews?.[view]?.observations || "";
      const recompile = previous.querySelector("input[data-recompile]");
      const nextRecompile = next.querySelector("input[data-recompile]");
      if (recompile && nextRecompile) nextRecompile.checked = recompile.checked;
      const oldRecipe = previous.querySelector(".local-pipeline-reference-recipe"), nextRecipe = next.querySelector(".local-pipeline-reference-recipe");
      if (oldRecipe && nextRecipe && (JSON.stringify(oldRun?.view_reference_recipes?.[view]) !== JSON.stringify(latest.view_reference_recipes?.[view]) || JSON.stringify(oldRun?.selected_views) !== JSON.stringify(latest.selected_views))) {
        const oldSelect = oldRecipe.querySelector("select"), nextSelect = nextRecipe.querySelector("select");
        const savedRecipe = oldRun?.view_reference_recipes?.[view] || { mode: "default" };
        const savedValue = savedRecipe.mode === "selected_view" ? savedRecipe.source_view : savedRecipe.mode;
        if (oldSelect.value !== savedValue) nextSelect.value = oldSelect.value;
        oldRecipe.replaceWith(nextRecipe);
      }
      for (const selector of ["summary", ".render-slot-add", ".local-pipeline-review-progress", ".local-pipeline-ai-observations"]) {
        const oldSection = previous.querySelector(selector), newSection = next.querySelector(selector);
        if (selector === ".render-slot-add" && oldSection && newSection) newSection.querySelector("input").value = oldSection.querySelector("input").value;
        if (oldSection && newSection && oldSection.outerHTML !== newSection.outerHTML && !oldSection.contains(document.activeElement)) oldSection.replaceWith(newSection);
        else if (!oldSection && newSection) previous.append(newSection);
      }
    }
    if (JSON.stringify(oldRun?.selected_views) !== JSON.stringify(latest.selected_views) || JSON.stringify(oldRun?.local_assets) !== JSON.stringify(latest.local_assets)) renderSelectedViews(latest);
    setBusyControls(); updateRefreshButton();
    $("summary").textContent = `${latest.character} · ${latest.phase}${latest.costume ? ` · ${latest.costume}` : ""} · ${latest.render_progress?.COMPLETE || 0}/${latest.candidate_count} images · ${statusLabels[latest.status] || latest.status}`;
    if ($("review-dialog").open && changed) {
      const oldAddCount = $("review-panel").querySelector(".render-slot-add input")?.value;
      state.reviewCandidates = orderedReviewCandidates();
      const index = state.reviewCandidates.findIndex(item => item.candidate_id === currentId);
      state.reviewIndex = index >= 0 ? index : Math.min(state.reviewIndex, state.reviewCandidates.length - 1);
      if (state.reviewIndex >= 0) {
        const focus = document.activeElement;
        const focusName = focus?.name, focusAction = focus?.dataset.imageAction;
        const hadFocus = $("review-panel").contains(focus);
        renderReview();
        const newAddCount = $("review-panel").querySelector(".render-slot-add input");
        if (newAddCount && oldAddCount) newAddCount.value = oldAddCount;
        if (index >= 0 && decision) { const radio = $("review-panel").querySelector(`input[value="${decision}"]`); if (radio) radio.checked = true; }
        if (hadFocus && focus?.closest(".render-slot-add")) newAddCount?.focus({ preventScroll: true });
        else if (hadFocus && focusName) $("review-panel").querySelector(`input[name="${focusName}"]:checked`)?.focus({ preventScroll: true });
        else if (hadFocus && focusAction) [...$("review-panel").querySelectorAll("button")].find(button => button.dataset.imageAction === focusAction)?.focus({ preventScroll: true });
      } else $("review-dialog").close();
    }
  }

  function viewOverrideInput(run, view) {
    const section = document.createElement("details");
    section.className = "local-pipeline-override";
    const heading = document.createElement("summary");
    heading.textContent = `${view} override image`;
    const body = document.createElement("div");
    body.className = "local-pipeline-override-body";
    const row = document.createElement("div");
    row.className = "local-pipeline-override-input";
    const help = document.createElement("p");
    help.className = "muted";
    help.textContent = "Use your own image as the selected candidate, then Lock it from Selected views. Replaces the selected working slot; published images stay intact until explicitly unlocked and relocked.";
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/png,image/jpeg,image/webp";
    input.setAttribute("aria-label", `${view} override image`);
    const zone = document.createElement("div");
    zone.className = "paste-zone";
    zone.setAttribute("aria-label", `Paste ${view} override image`);
    const preview = document.createElement("img");
    preview.alt = `${view} override preview`;
    preview.hidden = true;
    preview.style.maxWidth = "240px";
    const apply = document.createElement("button");
    apply.type = "button";
    apply.textContent = "Use as selected";
    apply.disabled = true;
    const message = document.createElement("p");
    message.setAttribute("role", "status");
    let stagedFile = null, expectedSelected = "", uploading = false;
    const generation = state.generation, pipeline = state.pipeline, context = contextKey();
    const current = () => section.isConnected && state.generation === generation && state.pipeline === pipeline
      && state.run?.run_id === run.run_id && contextKey() === context;
    const stage = file => {
      if (!file || !current() || uploading) return;
      if (file.size > 32 * 1024 * 1024) { message.textContent = "Choose an image under 32 MB."; return; }
      stagedFile = file;
      expectedSelected = state.run.selected_views?.[view] || "";
      const url = URL.createObjectURL(file);
      preview.onload = preview.onerror = () => URL.revokeObjectURL(url);
      preview.src = url;
      preview.hidden = false;
      apply.disabled = false;
      message.textContent = "Override staged. Use as selected to apply it.";
    };
    input.addEventListener("change", () => stage(input.files?.[0]));
    zone.addEventListener("paste", event => {
      const file = [...(event.clipboardData?.items || [])].find(item => item.type.startsWith("image/"))?.getAsFile();
      if (file) { event.preventDefault(); stage(file); }
    });
    apply.addEventListener("click", async () => {
      if (!stagedFile || !current() || uploading) return;
      uploading = true;
      apply.disabled = input.disabled = true;
      message.textContent = "Importing override…";
      const params = new URLSearchParams({ filename: stagedFile.name || "pasted-image.png",
        expected_selected_id: expectedSelected, ...(isCostume() ? { costume: selectedCostume() } : {}) });
      try {
        const result = await request(`${baseUrl()}/runs/${encodeURIComponent(run.run_id)}/views/${encodeURIComponent(view)}/override?${params}`, {
          method: "POST", headers: { "Content-Type": stagedFile.type || "application/octet-stream" }, body: stagedFile,
        });
        if (!current()) return;
        mergeLiveRun(result);
        expectedSelected = result.selected_views?.[view] || "";
        stagedFile = null;
        input.value = "";
        preview.hidden = true;
        message.textContent = "Override selected. Use Lock in Selected views to publish it.";
      } catch (error) {
        if (current()) message.textContent = error.message;
      } finally {
        uploading = false;
        input.disabled = false;
        apply.disabled = !stagedFile;
      }
    });
    row.append(input, zone);
    body.append(help, row, preview, message);
    section.append(heading, body);
    window.ZetImageInput.attach(zone, input);
    const actions = zone.nextElementSibling;
    actions.insertBefore(apply, actions.querySelector(".image-input-status"));
    return section;
  }

  function costumeRenderControls(run, view) {
    const settings = run.render_settings?.[view] || {}, section = document.createElement("div");
    section.className = "costume-render-settings";
    const modeLabel = document.createElement("label"); modeLabel.textContent = "Render mode";
    const mode = document.createElement("select"); mode.dataset.renderMode = view;
    for (const [value, text] of [["doll-dressing-ref", "Doll-dressing (w/ Ref)"], ["doll-dressing-no-ref", "Doll-dressing (no Ref)"], ["rotate", "Rotate"]]) {
      if (view !== "FRONT" || value === "doll-dressing-ref") mode.add(new Option(text, value));
    }
    mode.value = settings.mode; modeLabel.append(mode);
    const referenceLabel = document.createElement("label"); referenceLabel.textContent = "Costume reference view";
    const reference = document.createElement("select"); reference.dataset.costumeReference = view;
    reference.add(new Option(view === "FRONT" ? "FRONT uses matching Assembly only" : "Choose a different view", ""));
    for (const sourceView of run.views || []) if (sourceView !== view) {
      reference.add(new Option(`${sourceView}${run.selected_views?.[sourceView] ? " · selected" : " · image not selected"}`, sourceView));
    }
    reference.value = settings.costume_reference_view || "";
    const sync = () => { reference.disabled = view === "FRONT" || mode.value === "doll-dressing-no-ref"; };
    mode.addEventListener("change", sync); sync(); referenceLabel.append(reference);
    section.append(modeLabel, referenceLabel);
    addButton(section, "Save render settings", "save-costume-render-settings", {view});
    const help = document.createElement("p"); help.className = "muted";
    help.textContent = run.slot_controls?.[view]?.stage_reason || "Ready. Views run independently with their chosen mode inputs. Retry retains the submitted prompt and images.";
    section.append(help); return section;
  }

  function renderViews(run, host = $("views")) {
    const previousOpen = new Map(Array.from(host.querySelectorAll("details.local-pipeline-view"), (details) => [details.dataset.view, details.open]));
    const previousObservationsOpen = new Map(Array.from(host.querySelectorAll("details.local-pipeline-observations"), (details) => [details.dataset.view, details.open]));
    host.replaceChildren();
    for (const view of orderedViews(run)) {
      const candidates = (run.candidates || []).filter((candidate) => candidate.view === view);
      const details = document.createElement("details");
      details.className = "local-pipeline-view";
      details.dataset.view = view;
      const selected = run.selected_views?.[view] || "";
      const selectionChanged = Object.hasOwn(state.renderedSelections, view) && state.renderedSelections[view] !== selected;
      details.open = selectionChanged && selected ? false : (previousOpen.has(view) ? previousOpen.get(view) : !selected);
      const summary = document.createElement("summary");
      const heading = document.createElement("strong");
      heading.textContent = `${view} · ${run.selected_views?.[view] || "not selected"} · ${candidates.filter((item) => item.image_path).length}/${candidates.length} images`;
      summary.append(heading);
      const ranking = run.rankings?.[view] || {};
      const evaluation = run.evaluations?.[view] || {};
      const viewActions = document.createElement("span");
      viewActions.className = "button-row compact";
      const viewReady = isCostume() ? !run.slot_controls?.[view]?.stage_reason : view === "FRONT" || (state.pipeline === "character-assembly"
        ? Boolean(run.selected_views?.FRONT) && !run.stale_selections?.includes("FRONT")
        : run.use_front_anchor === false || Boolean(run.front_anchor));
      addRecompileOption(viewActions);
      const stageReason = run.slot_controls?.[view]?.stage_reason || "";
      const stageMenu = document.createElement("details"); stageMenu.className = "local-stage-menu";
      const stageLabel = document.createElement("summary"); stageLabel.textContent = "Stage…"; stageMenu.append(stageLabel);
      const stageItems = document.createElement("div"); stageItems.className = "local-stage-items"; stageMenu.append(stageItems);
      addButton(stageItems, "Stage in Image Generator", "stage-image-generation", { disabled: Boolean(stageReason), view, title: stageReason });
      if (isCostume()) {
        const controls = run.slot_controls?.[view] || {};
        addButton(stageItems, "Stage no Costume ref", "stage-no-costume-ref", { disabled: Boolean(controls.no_costume_ref_reason), view,
          title: controls.no_costume_ref_reason || "Stage without a prior rendered costume view." });
        addButton(stageItems, "Stage Rotation", "stage-rotation", { disabled: Boolean(controls.rotation_reason), view,
          title: controls.rotation_reason || `Rotate selected ${controls.rotation_source_view} into ${view}.` });
      }
      viewActions.append(stageMenu);
      addButton(viewActions, "Regen view", "rerun-view", { disabled: busy(run) || Boolean(run?.slot_render_ids?.length) || !viewReady || !candidates.length, view });
      addButton(viewActions, "Re-run failed", "rerun-failed", { disabled: busy(run) || Boolean(run?.slot_render_ids?.length) || !viewReady || !candidates.some((item) => item.status === "FAILED" || item.human_review?.decision === "reject"), view });
      addButton(viewActions, "Re-evaluate", "reevaluate-view", { disabled: busy(run) || Boolean(run?.slot_render_ids?.length) || (!isCostume() && !viewReady) || !candidates.some((item) => item.image_path), view });
      addButton(viewActions, "Post Render Adjustments", "post-render-adjustments", { disabled: !candidates.some((item) => item.image_path), view });
      const ai = run.view_reviews?.[view]?.ai_observations || {};
      summary.append(viewActions);
      details.append(summary);
      details.append(viewOverrideInput(run, view));
      if (hasSharedAssetRouter() || (["head-image", "head-image-edit"].includes(state.pipeline) && view === "FRONT" && run.front_source)) {
        const roles = ["head-image", "head-image-edit"].includes(state.pipeline)
          ? ["front_reference"]
          : state.pipeline === "character-assembly"
          ? ["body_reference", "head_image"]
          : ["character_assembly"];
        const sources = document.createElement("div");
        sources.className = "local-pipeline-sources";
        for (const role of roles) {
          const figure = document.createElement("figure");
          const caption = document.createElement("figcaption");
          caption.textContent = role.replaceAll("_", " ");
          const image = document.createElement("img");
          image.loading = "lazy";
          image.alt = caption.textContent;
          const source = run.sources?.[view]?.[role] || {};
          const version = source.sha256 || source.image_sha256 || source.image_path ||
            (role === "front_reference" ? run.front_source_sha256 || run.front_source : "");
          image.src = versionedImageUrl(route("source", run.run_id, view, role), version);
          figure.append(caption, image);
          sources.append(figure);
        }
        details.append(sources);
      }
      const referenceImages = [];
      const seenReferences = new Set();
      for (const candidate of candidates) {
        for (const reference of candidate.reference_images || []) {
          const key = reference.sha256
            ? `sha256:${reference.sha256}`
            : `${reference.role || ""}\u0000${reference.prompt_role || ""}\u0000${reference.label || reference.tag || ""}`;
          if (reference.path && !seenReferences.has(key)) {
            seenReferences.add(key);
            referenceImages.push(reference);
          }
        }
      }
      const renderedRoles = ["head-image", "head-image-edit"].includes(state.pipeline) && view === "FRONT" && run.front_source
        ? new Set(["head_image_source"])
        : state.pipeline === "character-assembly"
        ? new Set(["body_reference", "head_image"])
        : state.pipeline === "costume-dressing"
        ? new Set(["character_assembly"])
        : new Set();
      const remainingReferences = referenceImages
        .map((reference, index) => ({ reference, index }))
        .filter(({ reference }) => !renderedRoles.has(reference.role));
      if (remainingReferences.length) {
        const sources = document.createElement("div");
        sources.className = "local-pipeline-sources";
        for (const { reference, index } of remainingReferences) {
          const figure = document.createElement("figure");
          const caption = document.createElement("figcaption");
          const imageIndex = reference.image_index || index + 1;
          const promptRole = reference.prompt_role || reference.role || "reference";
          const label = reference.label || reference.tag || "Reference image";
          caption.textContent = `Image ${imageIndex} — ${promptRole}: ${label}`;
          const image = document.createElement("img");
          image.loading = "lazy";
          image.alt = caption.textContent;
          image.src = versionedImageUrl(route("reference-image", run.run_id, view, String(index)),
            reference.sha256 || reference.path || `${view}:${reference.role || "reference"}:${index}`);
          figure.append(caption, image);
          sources.append(figure);
        }
        details.append(sources);
      }
      const links = document.createElement("p");
      links.className = "muted";
      links.append(document.createTextNode(" · "));
      addLink(links, "Image prompt", route("image-prompt", run.run_id, view));
      const promptHelp = document.createElement("p"); promptHelp.className = "muted local-pipeline-prompt-help";
      promptHelp.textContent = "Generate / Regen use the current view prompt. Recompile builds it from current templates first. Retry uses the failed render’s saved prompt.";
      details.append(links, promptHelp);
      const recipeSection = document.createElement("div"); recipeSection.className = "local-pipeline-reference-recipe";
      const recipeLabel = document.createElement("label"); recipeLabel.textContent = "Reference for new individual renders";
      const recipeSelect = document.createElement("select"); recipeSelect.dataset.referenceRecipe = view;
      recipeSelect.add(new Option("Pipeline default", "default"));
      recipeSelect.add(new Option(hasSharedAssetRouter() ? "No batch anchor" : "No view reference (text only)", "none"));
      for (const sourceView of run.views || []) {
        if (sourceView === view) continue;
        const cid = run.selected_views?.[sourceView] || (sourceView === "FRONT" ? run.front_anchor : "");
        recipeSelect.add(new Option(`Selected ${sourceView}${cid ? ` · ${cid}` : " (choose an image first)"}`, sourceView));
      }
      const recipe = run.view_reference_recipes?.[view] || { mode: "default" };
      recipeSelect.value = recipe.mode === "selected_view" ? recipe.source_view : recipe.mode;
      recipeLabel.append(recipeSelect); recipeSection.append(recipeLabel);
      addButton(recipeSection, "Save reference", "save-view-reference", { view });
      const recipeHelp = document.createElement("p"); recipeHelp.className = "muted";
      recipeHelp.textContent = "Applies to future Generate / Regen in individual slots. Matching pipeline inputs remain. Custom choices compile automatically; Retry keeps its saved inputs. A front reference can pull a rear image toward the front angle.";
      if (run.character_progression && view !== "BACK") {
        recipeSelect.disabled = true;
        recipeSection.querySelector("button").hidden = true;
        recipeHelp.textContent = view === "FRONT" ? "Uses this pipeline’s FRONT prerequisites." : state.pipeline === "head-image-edit" ? "Uses selected FRONT independently. Submitted renders retain their frozen reference." : "Uses the selected predecessor from the preceding stage. Submitted renders retain their frozen reference.";
      }
      if (run.character_progression && view === "BACK") {
        const sources = ["body-reference", "head-image-edit"].includes(state.pipeline) ? ["FRONT"] : ["BACK_LEFT_3_4", "BACK_RIGHT_3_4"];
        for (const option of [...recipeSelect.options]) if (!sources.includes(option.value)) option.remove();
        recipeSelect.value = recipe.source_view || run.character_progression.back_reference;
        if (["body-reference", "head-image-edit"].includes(state.pipeline)) {
          recipeSelect.value = "FRONT";
          recipeSelect.disabled = true;
          recipeSection.querySelector("button").hidden = true;
          recipeHelp.textContent = "Uses the selected FRONT image for future BACK renders. Submitted renders retain their frozen reference.";
        } else {
          recipeHelp.textContent = "Choose either selected rear three-quarter for future BACK renders. Existing images stay unchanged.";
        }
      }
      recipeSection.append(recipeHelp);
      if (isCostume()) details.append(costumeRenderControls(run, view));
      else if (state.pipeline !== "character-assembly") details.append(recipeSection);
      const observationDetails = document.createElement("details");
      observationDetails.className = "local-pipeline-observations";
      observationDetails.dataset.view = view;
      observationDetails.open = previousObservationsOpen.get(view) || false;
      const observationSummary = document.createElement("summary");
      observationSummary.textContent = "Observations";
      observationDetails.append(observationSummary);
      const observationSection = document.createElement("section");
      observationSection.className = "local-pipeline-view-observations";
      const observationsLabel = document.createElement("label");
      observationsLabel.textContent = "Your observations";
      const observations = document.createElement("textarea");
      observations.dataset.viewObservations = view;
      observations.value = run.view_reviews?.[view]?.observations || "";
      observationsLabel.append(observations);
      observationSection.append(observationsLabel);
      addButton(observationSection, "Save observations", "save-observations", { view });
      const aiHeading = document.createElement("h4");
      aiHeading.textContent = "AI Observations";
      const aiContent = document.createElement("p");
      aiContent.className = "muted local-pipeline-ai-observations";
      aiContent.textContent = `${ai.status || "Pending"}${ai.error ? ` · ${ai.error}` : ""}${ai.stale_reason ? ` · ${ai.stale_reason}` : ""}${ai.text ? `\n\n${ai.text}` : ""}`;
      observationSection.append(aiHeading, aiContent);
      addButton(observationSection, ai.status === "COMPLETE" ? "Run AI Observations again" : "Run AI Observations", "run-observations",
        { view, disabled: ["QUEUED", "RUNNING"].includes(ai.status) || !candidates.some(item => item.image_available) });
      observationDetails.append(observationSection);
      const reviewProgress = document.createElement("p");
      if (evaluation.evaluation_id || ranking.status) {
        reviewProgress.className = "muted local-pipeline-review-progress";
        const rankText = evaluationLabels[evaluation.ranking_status] || evaluationLabels[ranking.status] || "Ranking not queued";
        reviewProgress.textContent = `Luna ranking · ${rankText}`;
      }
      const gallery = document.createElement("div");
      gallery.className = "local-pipeline-gallery";
      const slots = run.slots_by_view?.[view] || [...candidates.map(item => item.candidate_id), ...Array(Math.max(0, 8 - candidates.length)).fill(null)];
      const candidateSlots = slots.map((id, index) => ({
        id,
        slot: index + 1,
        candidate: candidates.find(item => item.candidate_id === id),
      })).filter(item => item.candidate);
      const appendEmptySlot = index => {
        const card = document.createElement("article"); card.className = "local-pipeline-candidate render-slot-empty";
        card.dataset.slot = String(index + 1);
        const title = document.createElement("h3"); title.textContent = `Slot ${index + 1}`;
        const empty = document.createElement("p"); empty.textContent = "Empty"; empty.className = "image-card-state"; card.dataset.state = "empty";
        card.append(title, empty);
        const control = run.slot_controls?.[view] || {};
        addSlotButton(card, "Generate", "generate", view, index + 1, !control.can_generate, control.reason);
        if (!control.can_generate && control.reason) {
          const reason = document.createElement("p"); reason.className = "slot-action-reason muted";
          reason.textContent = control.reason; card.append(reason);
        }
        window.ZetImageCardUI.scan(card);
        gallery.append(card);
      };
      const lunaOrder = ranking.status === "COMPLETE"
        ? (ranking.luna_ordered_candidate_ids?.length ? ranking.luna_ordered_candidate_ids : ranking.ordered_candidate_ids || [])
        : [];
      const displayCandidateSlots = lunaOrder.length
        ? sortCandidatesByDisplayOrder(run, view, candidateSlots, item => item.id, item => item.slot)
        : candidateSlots;
      if (lunaOrder.length) {
        displayCandidateSlots.forEach(({candidate, slot}) => gallery.append(renderCandidate(view, {...candidate, slot}, ranking, run)));
        slots.forEach((id, index) => {
          if (!candidateSlots.some(item => item.slot === index + 1)) appendEmptySlot(index);
        });
      } else {
        slots.forEach((id, index) => {
          const candidate = candidates.find(item => item.candidate_id === id);
          if (candidate) gallery.append(renderCandidate(view, {...candidate, slot: index + 1}, ranking, run));
          else appendEmptySlot(index);
        });
      }
      const control = run.slot_controls?.[view] || {};
      details.append(window.ZetRenderSlots.countControl(control.empty_count || 0, count => void slotAction("generate", view, null, count).catch(error => setStatus(error.message, true)), {disabled: !control.can_generate, reason: control.legacy ? "Legacy gallery: clear surplus candidates before adding renders." : control.reason}));
      details.append(gallery);
      details.append(observationDetails);
      if (reviewProgress.textContent) details.append(reviewProgress);
      const continuation = document.createElement("div");
      continuation.className = "button-row compact";
      if (!isCostume()) addButton(continuation, "Continue", "proceed", { primary: true });
      details.append(continuation);
      host.append(details);
    }
    syncViewContinueButtons(host);
    state.renderedSelections = { ...(run.selected_views || {}) };
  }

  function updateRefreshButton() {
    const button = $("refresh");
    const hasRun = Boolean(state.run?.run_id);
    const hasNewImages = Boolean(state.polledRun);
    button.disabled = false;
    button.textContent = hasNewImages ? "Refresh · Updates available" : "Refresh";
  }

  function render() {
    const run = state.run;
    window.ZetTemplateImprovement?.update(run, state.pipeline, () => loadRun(run?.run_id || ""), frontRenderControl);
    renderLineageWarnings(run);
    if (!run) {
      $("lineage-warning").hidden = true;
      $("options").open = true;
      $("summary").textContent = "No batch selected. Check requirements and create a new batch.";
      $("rename").hidden = true;
      $("selected").replaceChildren();
      $("selected").hidden = true;
      $("views").replaceChildren();
      state.renderedSelections = {};
      state.polledRun = null;
      updateRefreshButton();
      setBusyControls();
      return;
    }
    if ($("options").dataset.batch !== run.run_id) {
      if (window.matchMedia("(max-width: 1360px)").matches) $("options").open = false;
      $("options").dataset.batch = run.run_id;
    }
    const progress = run.page_summary || {};
    const completed = run.render_progress?.COMPLETE ?? progress.completed_count ?? run.complete_count ?? (run.candidates || []).filter((item) => item.image_path).length;
    const phaseChangeSummary = ["head-image", "head-image-edit"].includes(state.pipeline) && run.apply_phase_change ? " · Phase change rules applied" : "";
    $("summary").textContent = `${run.character} · ${run.phase}${run.costume ? ` · ${run.costume}` : ""}${phaseChangeSummary}${state.pipeline === "character-assembly" ? ` · Heads: ${run.head_pipeline === "head-image-edit" ? "Head-Image Edit" : "Head-Image"}` : ""} · ${run.run_id} · ${completed}/${run.candidate_count || (run.candidates || []).length} images · ${statusLabels[run.status] || run.status}${run.front_anchor ? ` · FRONT ${run.front_anchor}` : ""}${progress.stale_selections?.length ? ` · stale selections ${progress.stale_selections.join(", ")}` : ""}`;
    if (document.activeElement !== $("batch-name")) $("batch-name").value = run.batch_name || "";
    setBusyControls();
    renderSelectedViews(run);
    renderViews(run);
    updateRefreshButton();
  }

  function renderLineageWarnings(run) {
    const host = $("lineage-warning");
    const warnings = run?.lineage_warnings || {};
    const views = Object.entries(warnings).filter(([, entries]) => entries?.length);
    host.hidden = !views.length;
    host.textContent = views.length ? "Source lineage warning" : "";
  }

  function renderSourceBatchOptions(result) {
    if (!hasSharedAssetRouter()) return;
    const host = $("source-batches");
    const selected = Object.fromEntries(Array.from(host.querySelectorAll("select[data-source-role]"), (item) => [item.dataset.sourceRole, item.value]));
    host.replaceChildren();
    for (const [role, runs] of Object.entries(result.source_batch_options || {})) {
      const label = document.createElement("label");
      label.textContent = `${role.replaceAll("_", " ")} source batch`;
      const select = document.createElement("select");
      select.dataset.sourceRole = role;
      select.add(new Option("Current locked images", "locked"));
      for (const run of runs) select.add(new Option(`${run.batch_name} · ${(run.selected_views || []).length}/${(state.run?.views || []).length || 8} selected views`, run.run_id));
      select.value = selected[role] && Array.from(select.options).some((option) => option.value === selected[role])
        ? selected[role] : "locked";
      label.append(select);
      host.append(label);
    }
    host.hidden = false;
  }

  async function loadRun(runId, generation = state.generation) {
    const requestId = ++state.runRequest;
    state.runState = runId ? "loading" : "absent";
    if (!runId) { state.run = null; render(); return; }
    try {
      const loaded = await request(route("detail", runId));
      if (requestId !== state.runRequest || generation !== state.generation || contextKey() !== state.contextKey) return;
      const sameRun = state.run?.run_id === loaded.run_id;
      if (sameRun) mergeLiveRun(loaded); else state.run = loaded;
      syncRunOption(loaded);
      state.runState = "selected";
      state.polledRun = null;
      if (!sameRun) {
        if (state.pipeline === "character-assembly" && $("head-pipeline").value !== (loaded.head_pipeline || "head-image")) {
          $("head-pipeline").value = loaded.head_pipeline || "head-image";
          $("source-batches").replaceChildren();
          void readiness();
        }
        render();
      }
    } catch (error) {
      if (requestId !== state.runRequest || generation !== state.generation) return;
      state.runState = "unavailable";
      throw error;
    }
  }

  function syncRunOption(run) {
    const option = [...$("runs").options].find(item => item.value === run.run_id);
    if (!option) return;
    const summary = state.runs.find(item => item.run_id === run.run_id) || {};
    const label = statusLabels[run.status] || run.status;
    const phaseChangeLabel = ["head-image", "head-image-edit"].includes(state.pipeline) && run.apply_phase_change ? " · Phase change rules" : "";
    const progressionLabel = !["character-assembly", "costume-dressing"].includes(state.pipeline) && run.character_progression
      ? !run.character_progression.accepted_revision_id ? " · Prompt review" : ` · Stage ${Math.max(1, run.character_progression.stage + 1)}` : "";
    const countLabel = run.status === "COMPLETE" ? " · Complete" : run.status === "AWAITING_HUMAN_SELECTION" ? " · Awaiting selection" : "";
    option.textContent = `${summary.batch_name || run.batch_name || run.run_id} · ${label}${phaseChangeLabel}${progressionLabel}${countLabel} · ${run.run_id}`;
  }

  async function pollForImages(runId, generation = state.generation) {
    if (state.pollInFlight || !state.run || state.run.run_id !== runId) return;
    state.pollInFlight = true;
    const requestId = state.runRequest;
    try {
      const latest = await request(route("detail", runId));
      if (requestId !== state.runRequest || generation !== state.generation || state.run?.run_id !== runId) return;
      if (contextKey() !== state.contextKey || !document.querySelector("#local-pipeline-page").classList.contains("active")) return;
      mergeLiveRun(latest);
    } catch (error) {
      setStatus(`Unable to check renders: ${error.message}. Retrying automatically.`, true);
    } finally {
      state.pollInFlight = false;
    }
  }

  async function refreshRuns(preferred = "", generation = state.generation) {
    state.runsState = "loading";
    let result;
    try { result = await request(route("runs")); }
    catch (error) { if (generation === state.generation) state.runsState = "unavailable"; throw error; }
    if (generation !== state.generation) return;
    state.runs = result.runs || [];
    state.runsState = "selected";
    const select = $("runs");
    select.replaceChildren();
    for (const run of state.runs) {
      const phaseChangeLabel = ["head-image", "head-image-edit"].includes(state.pipeline) && run.apply_phase_change ? " · Phase change rules" : "";
      select.add(new Option(`${run.batch_name || run.run_id} · ${statusLabels[run.status] || run.status}${phaseChangeLabel}${!["character-assembly", "costume-dressing"].includes(state.pipeline) && run.character_progression ? !run.character_progression.accepted_revision_id ? " · Prompt review" : ` · Stage ${Math.max(1, run.character_progression.stage + 1)}` : ""} · ${run.run_id}`, run.run_id));
    }
    if (!state.runs.length) select.add(new Option("No batches for this character, phase, and costume", ""));
    const current = state.run?.run_id;
    const routeBatch = new URLSearchParams(window.location.search).get("local_batch") || "";
    if (restoreParams.get("task_context") === "1" && routeBatch && !state.runs.some((run) => run.run_id === routeBatch)) {
      window.ZetTaskCapture.notice(`Recorded batch "${routeBatch}" is unavailable for this selection. Showing an available batch, if any.`);
    }
    const chosen = [preferred, current, routeBatch].find((id) => id && state.runs.some((run) => run.run_id === id)) || state.runs[0]?.run_id || "";
    select.value = chosen;
    await loadRun(chosen, generation);
    syncPipelineRoute();
  }

  async function readiness() {
    const generation = ++state.previewGeneration;
    if (lockedPhaseSourceSelected()) void refreshLockedPhaseSource();
    $("create").disabled = true;
    $("readiness").textContent = "Checking required inputs…";
    try {
      const result = await request(route("preview"), { method: "POST", body: JSON.stringify(payload()) });
      if (generation !== state.previewGeneration) return;
      const blockers = result.blocking_reasons || [];
      renderSourceBatchOptions(result);
      const canCreate = result.can_create !== false && blockers.length === 0;
      $("readiness").textContent = blockers.length ? blockers.join(" · ")
        : `${result.candidate_count || ""} candidates across ${(result.views || []).length} views. ${canCreate ? "Ready to create." : "Resolve requirements first."}`;
      $("create").disabled = !canCreate;
    } catch (error) {
      if (generation !== state.previewGeneration) return;
      $("readiness").textContent = error.message;
      $("create").disabled = true;
    }
  }

  async function refreshContext() {
    state.generation += 1;
    state.runRequest += 1;
    state.runsState = "loading";
    state.runState = "loading";
    state.contextKey = contextKey();
    const generation = state.generation;
    state.run = null;
    state.polledRun = null;
    state.renderedSelections = {};
    state.sourcePreviewGeneration += 1;
    state.frontSourcePath = "";
    $("apply-phase-change").checked = false;
    $("apply-phase-change").disabled = state.pipeline !== "head-image-edit";
    $("source-mode").value = "upload";
    populateSourcePhases();
    updateSourceControls();
    $("locked-preview").textContent = "Choose a source phase.";
    $("source-preview").textContent = "No FRONT reference selected.";
    $("source-file").value = "";
    $("source-remove").hidden = true;
    try {
      await loadCostumes();
      if (generation !== state.generation) return;
      state.contextKey = contextKey();
      await Promise.all([refreshRuns("", generation), readiness()]);
    } catch (error) { setStatus(error.message, true); }
  }

  async function loadCostumes() {
    if (!isCostume()) return;
    state.costumesState = "loading";
    const generation = state.generation;
    const pipeline = state.pipeline;
    const character = document.querySelector("#character-select").value;
    const phase = document.querySelector("#phase-select").value;
    let data;
    try { data = await request(`/api/costumes?${new URLSearchParams({ character, phase })}`); }
    catch (error) { if (generation === state.generation) state.costumesState = "unavailable"; throw error; }
    if (generation !== state.generation || pipeline !== state.pipeline || contextKey() !== state.contextKey) return;
    state.costumesState = "selected";
    const select = $("costume");
    const previous = select.value;
    select.replaceChildren(...(data.costumes || []).map((item) => new Option(item.name, item.name)));
    if (!select.options.length) select.add(new Option("No costumes available", ""));
    const routeCostume = new URLSearchParams(window.location.search).get("local_costume") || "";
    const routedCostume = (data.costumes || []).find((item) => item.name === routeCostume || item.slug === routeCostume);
    const preferred = routedCostume?.name || routeCostume || previous;
    if (Array.from(select.options).some((item) => item.value === preferred)) select.value = preferred;
    else if (routeCostume && restoreParams.get("task_context") === "1") {
      window.ZetTaskCapture.notice(`Recorded costume "${routeCostume}" is unavailable. Showing an available costume, if any.`);
    }
  }

  function startPolling() {
    clearInterval(state.poll);
    state.poll = setInterval(() => {
      if (state.pipeline && document.querySelector("#local-pipeline-page").classList.contains("active") && state.run?.run_id) void pollForImages(state.run.run_id, state.generation);
    }, 5000);
  }

  function configurePipeline(pipeline) {
    state.pipeline = pipeline;
    state.runsState = "loading";
    state.runState = "absent";
    state.costumesState = isCostume() ? "loading" : "absent";
    state.generation += 1;
    state.contextKey = contextKey();
    state.run = null;
    state.frontSourcePath = "";
    $("apply-phase-change").checked = false;
    $("apply-phase-change").disabled = pipeline !== "head-image-edit";
    $("source-mode").value = "upload";
    populateSourcePhases();
    updateSourceControls();
    document.querySelector("#local-pipeline-title").textContent = {
      "body-reference": "Body-Reference", "head-image": "Head-Image", "head-image-edit": "Head-Image Edit",
      "character-assembly": "Character-Assembly", "costume-dressing": "Costume-Dressing",
    }[pipeline];
    $("costume-label").hidden = !isCostume();
    $("anchor-option").hidden = state.pipeline === "character-assembly" || !hasSharedAssetRouter();
    $("source-batches").hidden = !hasSharedAssetRouter();
    $("head-pipeline-label").hidden = pipeline !== "character-assembly";
    $("head-pipeline").value = "head-image";
    $("rerun-refresh-option").hidden = !hasSharedAssetRouter();
    if (hasSharedAssetRouter()) $("use-anchor").checked = false;
    $("source-option").hidden = !["head-image", "head-image-edit"].includes(pipeline);
    $("source-remove").hidden = true;
    $("source-preview").textContent = "No FRONT reference selected.";
    $("runs").replaceChildren(new Option("Loading batches…", ""));
    $("views").replaceChildren();
    $("selected").replaceChildren();
    setStatus("");
    startPolling();
    const generation = state.generation;
    void refreshContext().catch((error) => setStatus(error.message, true));
  }

  async function uploadHeadSource(file) {
    if (!file) return;
    const context = { character: document.querySelector("#character-select").value, phase: document.querySelector("#phase-select").value };
    if (busy()) { setStatus("Stop the current batch before changing its reference image.", true); return; }
    try {
      const response = await fetch(`${baseUrl()}/sources?${new URLSearchParams({ ...context, filename: file.name || "pasted-reference.png" })}`, {
        method: "POST", headers: { "Content-Type": file.type || "application/octet-stream",
          "X-Zet-Universe": document.querySelector("#universe-select").value }, body: file,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Could not upload the reference image.");
      state.frontSourcePath = data.path || "";
      $("apply-phase-change").disabled = state.pipeline !== "head-image-edit" && !state.frontSourcePath;
      $("source-preview").replaceChildren();
      const image = document.createElement("img");
      image.src = URL.createObjectURL(file);
      image.alt = "Selected FRONT reference";
      $("source-preview").append(image);
      $("source-remove").hidden = false;
      setStatus("Reference staged for the next batch.");
      void readiness();
    } catch (error) { setStatus(error.message, true); }
  }

  async function perform(action, view = "", candidateId = "", body = undefined) {
    if (action === "proceed" && state.run?.character_progression) body = {
      expected_stage: state.run.character_progression.stage, back_reference: $("back-reference").value };
    const runId = state.run?.run_id || "";
    const generation = state.generation;
    const pipeline = state.pipeline;
    const context = contextKey();
    const requestId = ++state.runRequest;
    const method = action === "rename"
      ? "PUT" : action === "delete" ? "DELETE" : "POST";
    let path;
    if (action === "reevaluate-view") path = `${baseUrl()}/runs/${encodeURIComponent(state.run.run_id)}/reevaluate${query({ view })}`;
    else path = route(action, state.run?.run_id, view, candidateId);
    const result = await request(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });
    if (requestId !== state.runRequest || generation !== state.generation || pipeline !== state.pipeline ||
        context !== contextKey() || (runId && state.run?.run_id !== runId)) return result;
    if (action === "delete") {
      state.run = null;
      await refreshRuns();
      setStatus("Batch deleted.");
      return;
    }
    if (action === "proceed") {
      const queued = (result.target_views || []).length;
      const blocked = Object.values(result.blocked_views || {});
      setStatus(queued ? `Work queued for ${queued} view(s).${blocked.length ? ` ${blocked.length} view(s) still need locked inputs.` : ""}`
        : blocked.length ? `No views are ready. ${blocked[0]}` : "No unstarted views remain.");
    } else if (action === "resume" && result.status !== "QUEUED") {
      setStatus("Batch ready to continue.");
    } else if (["start", "resume", "stop", "retry", "rerun", "rerun-view", "rerun-failed", "reevaluate", "reevaluate-view"].includes(action)) {
      setStatus(action === "stop" ? "Stop requested." : "Work queued.");
    } else if (action === "lock" || action === "unlock" || action === "select" || action === "unselect") {
      setStatus("Selection updated.");
    }
    if (["review", "select", "unselect", "move-rank"].includes(action) && result?.run_id) {
      mergeLiveRun(result);
    } else await loadRun(state.run?.run_id);
  }

  function sortCandidatesByDisplayOrder(run, view, candidates, candidateId = item => item.candidate_id, slotNumber = item => item.slot || item.ordinal || 0) {
    const ranking = run.rankings?.[view] || {};
    const lunaOrder = ranking.status === "COMPLETE"
      ? (ranking.luna_ordered_candidate_ids?.length ? ranking.luna_ordered_candidate_ids : ranking.ordered_candidate_ids || [])
      : [];
    const rankById = new Map(lunaOrder.map((id, index) => [id, index]));
    return [...candidates].sort((left, right) =>
      (rankById.get(candidateId(left)) ?? Number.MAX_SAFE_INTEGER) - (rankById.get(candidateId(right)) ?? Number.MAX_SAFE_INTEGER)
      || slotNumber(left) - slotNumber(right));
  }

  function physicalSlotNumber(run, view, candidate) {
    const slots = run.slots_by_view?.[view] || [];
    const slotIndex = slots.indexOf(candidate.candidate_id);
    return slotIndex >= 0 ? slotIndex + 1 : candidate.slot || candidate.ordinal || 0;
  }

  function orderedReviewCandidates() {
    const run = state.run;
    const views = orderedViews(run);
    return views.flatMap(view => sortCandidatesByDisplayOrder(run, view,
      (run?.candidates || []).filter(item => item.view === view),
      item => item.candidate_id, item => physicalSlotNumber(run, view, item)));
  }

  function normalizedDecision(value) {
    return ({ pass: "keep", fail: "reject" })[String(value || "undecided").toLowerCase()] || String(value || "undecided").toLowerCase();
  }

  async function saveReviewDecision(candidate) {
    if (!candidate.image_path) return candidate;
    const decision = normalizedDecision($("review-panel").querySelector("input[name='local-human-decision']:checked")?.value);
    const current = (state.run?.candidates || []).find(item => item.candidate_id === candidate.candidate_id) || candidate;
    if (decision !== normalizedDecision(current.human_review?.decision)) {
      await perform("review", candidate.view, candidate.candidate_id, { decision });
    }
    state.reviewCandidates = orderedReviewCandidates();
    state.reviewIndex = state.reviewCandidates.findIndex((item) => item.candidate_id === candidate.candidate_id);
    return state.reviewCandidates[state.reviewIndex] || candidate;
  }

  function reviewPending(message = "") {
    const host = $("review-panel");
    if (host) host.setAttribute("aria-busy", String(Boolean(message)));
    for (const id of ["review-prev", "review-next", "review-prev-view", "review-next-view"]) {
      const button = $(id);
      if (button) button.disabled = Boolean(message) || button.dataset.reviewBoundary === "true";
    }
    let status = document.getElementById("review-action-status");
    if (message) {
      if (!status) {
        status = document.createElement("p");
        status.id = "review-action-status";
        status.className = "action-message info";
        status.setAttribute("role", "status");
        host?.prepend(status);
      }
      status.textContent = message;
    } else status?.remove();
  }

  async function navigateReview(direction) {
    if (state.reviewActionPending) return;
    const candidate = state.reviewCandidates[state.reviewIndex];
    if (!candidate) return;
    state.reviewActionPending = true;
    reviewPending("Saving this review before moving to another candidate…");
    try {
      await saveReviewDecision(candidate);
      state.reviewCandidates = orderedReviewCandidates();
      state.reviewIndex = state.reviewCandidates.findIndex((item) => item.candidate_id === candidate.candidate_id) + direction;
      renderReview();
    } catch (error) { setStatus(error.message, true); }
    finally { state.reviewActionPending = false; reviewPending(); }
  }

  async function navigateReviewView(direction) {
    if (state.reviewActionPending) return;
    const candidate = state.reviewCandidates[state.reviewIndex];
    if (!candidate) return;
    state.reviewActionPending = true;
    reviewPending("Saving this review before changing views…");
    try {
      await saveReviewDecision(candidate);
      state.reviewCandidates = orderedReviewCandidates();
      const availableViews = orderedViews(state.run).filter((view) =>
        state.reviewCandidates.some((item) => item.view === view));
      const targetView = availableViews[availableViews.indexOf(candidate.view) + direction];
      if (!targetView) return;
      state.reviewIndex = state.reviewCandidates.findIndex((item) => item.view === targetView);
      renderReview();
    } catch (error) { setStatus(error.message, true); }
    finally { state.reviewActionPending = false; reviewPending(); }
  }

  function renderReview() {
    const candidate = state.reviewCandidates[state.reviewIndex];
    if (!candidate) return;
    const run = state.run;
    const oppositeViews = {
      LEFT_PROFILE: "RIGHT_PROFILE", RIGHT_PROFILE: "LEFT_PROFILE",
      FRONT_LEFT_3_4: "FRONT_RIGHT_3_4", FRONT_RIGHT_3_4: "FRONT_LEFT_3_4",
      BACK_LEFT_3_4: "BACK_RIGHT_3_4", BACK_RIGHT_3_4: "BACK_LEFT_3_4",
    };
    const oppositeView = oppositeViews[candidate.view];
    const selectedViews = run.selected_views || {};
    const candidates = run.candidates || [];
    const frontId = run.front_anchor || selectedViews.FRONT;
    const front = candidates.find((item) => item.candidate_id === frontId && item.view === "FRONT" && item.image_path);
    const oppositeId = oppositeView && selectedViews[oppositeView];
    const opposite = oppositeId && candidates.find((item) => item.candidate_id === oppositeId
      && item.view === oppositeView && item.image_path);
    const toggleLabel = $("review-toggle-label");
    const toggle = $("review-toggle");
    toggleLabel.hidden = !oppositeView;
    toggle.disabled = !opposite;
    toggle.checked = state.compareOpposite && Boolean(opposite);
    const comparison = toggle.checked ? opposite : front;
    $("review-compare-title").textContent = toggle.checked ? `Selected ${oppositeView}` : "Selected FRONT";
    const compareImage = $("review-compare-image");
    if (comparison) {
      compareImage.src = imageUrl(comparison);
      compareImage.alt = `${toggle.checked ? `Selected ${oppositeView}` : "Selected FRONT"} ${comparison.candidate_id}`;
      compareImage.hidden = false;
      $("review-compare-empty").hidden = true;
    } else {
      compareImage.removeAttribute("src");
      compareImage.hidden = true;
      $("review-compare-empty").hidden = false;
      $("review-compare-empty").textContent = "No selected FRONT image is available for comparison.";
    }
    $("review-compare-image").closest("figure").hidden = !comparison;
    $("review-compare-image").closest(".local-pipeline-review-comparison").classList.toggle("single-image", !comparison);
    const reviewImage = $("review-image");
    reviewImage.hidden = !candidate.image_path;
    if (candidate.image_path) reviewImage.src = imageUrl(candidate);
    else reviewImage.removeAttribute("src");
    reviewImage.alt = `${candidate.view} candidate ${candidate.candidate_id}`;
    let placeholder = reviewImage.parentElement.querySelector(".image-review-placeholder");
    if (!placeholder) {
      placeholder = document.createElement("p"); placeholder.className = "image-review-placeholder";
      reviewImage.after(placeholder);
    }
    placeholder.hidden = Boolean(candidate.image_path);
    placeholder.textContent = "No image available yet.";
    const panel = $("review-panel");
    const previousCandidate = panel.dataset.candidate;
    const previousDetails = panel.querySelector(".local-pipeline-review-details");
    const detailsOpen = previousDetails?.open || false;
    const detailsScroll = previousDetails?.scrollTop || 0;
    const qualityScroll = panel.querySelector(".local-pipeline-review-quality")?.scrollTop || 0;
    panel.dataset.candidate = candidate.candidate_id;
    panel.replaceChildren();
    const title = document.createElement("h2");
    title.textContent = candidate.candidate_id;
    const view = document.createElement("p");
    view.className = "local-pipeline-review-position";
    view.textContent = `${candidate.view} · Slot ${candidate.slot || candidate.ordinal} · ${state.reviewIndex + 1} of ${state.reviewCandidates.length} · ${statusLabels[candidate.status] || candidate.status}`;
    const info = document.createElement("p");
    info.className = "local-pipeline-review-meta muted";
    const metadata = [candidate.method && `Method: ${candidate.method}`, candidate.seed && `Seed: ${candidate.seed}`].filter(Boolean);
    if (candidate.elapsed_seconds != null && Number.isFinite(Number(candidate.elapsed_seconds))) {
      metadata.push(`Generation time: ${Math.round(Number(candidate.elapsed_seconds))} seconds`);
    }
    info.textContent = metadata.join(" · ");
    const decision = document.createElement("fieldset");
    decision.className = "decision-options local-pipeline-decision-options";
    decision.disabled = !candidate.image_path;
    const legend = document.createElement("legend");
    legend.textContent = "Human decision";
    decision.append(legend);
    const savedDecision = candidate.human_review?.decision === "pass" ? "keep"
      : candidate.human_review?.decision === "fail" ? "reject" : candidate.human_review?.decision || "undecided";
    for (const [value, label] of [["undecided", "Undecided"], ["keep", "Pass"], ["reject", "Fail"]]) {
      const wrapper = document.createElement("label");
      wrapper.className = "decision-option";
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = "local-human-decision";
      radio.value = value;
      radio.checked = savedDecision === value;
      wrapper.append(radio, document.createTextNode(label));
      decision.append(wrapper);
    }
    const save = document.createElement("button");
    save.className = "neutral-action";
    save.textContent = "Save review";
    save.disabled = !candidate.image_path;
    save.addEventListener("click", async () => {
      if (state.reviewActionPending) return;
      state.reviewActionPending = true;
      try {
        await saveReviewDecision(candidate);
        renderReview();
      } catch (error) { setStatus(error.message, true); }
      finally { state.reviewActionPending = false; }
    });
    const select = document.createElement("button");
    select.textContent = "Select this image";
    select.className = "primary-action";
    select.disabled = !candidate.image_path || selectedViews[candidate.view] === candidate.candidate_id;
    select.addEventListener("click", async () => {
      if (state.reviewActionPending) return;
      state.reviewActionPending = true;
      try {
        await saveReviewDecision(candidate);
        await perform("select", candidate.view, candidate.candidate_id, { candidate_id: candidate.candidate_id });
        state.reviewCandidates = orderedReviewCandidates();
        state.reviewIndex = state.reviewCandidates.findIndex((item) => item.candidate_id === candidate.candidate_id);
        renderReview();
      } catch (error) { setStatus(error.message, true); }
      finally { state.reviewActionPending = false; }
    });
    const content = document.createElement("section");
    content.className = "local-pipeline-review-content";
    if (candidate.override) view.textContent += " / Override";
    const renderError = renderErrorDetails(candidate);
    // Errors remain visible even when prompt details are collapsed.
    const ranking = run.rankings?.[candidate.view] || {};
    const rankingOrder = ranking.luna_ordered_candidate_ids?.length ? ranking.luna_ordered_candidate_ids : ranking.ordered_candidate_ids || [];
    const rankingPosition = rankingOrder.indexOf(candidate.candidate_id);
    const adjustedOrder = ranking.ordered_candidate_ids || [];
    const adjustedPosition = adjustedOrder.indexOf(candidate.candidate_id);
    const rankEntry = (ranking.entries || []).find((item) => item.candidate_id === candidate.candidate_id);
    const rankingInfo = document.createElement("p");
    rankingInfo.className = "local-pipeline-review-explanation local-pipeline-review-rank";
    rankingInfo.textContent = ranking.status === "STALE"
      ? `Luna ranking stale · ${ranking.stale_reason || "Review inputs changed"}${rankingPosition >= 0 ? ` · Previous rank #${rankingPosition + 1}` : ""}`
      : ranking.status === "FAILED" ? `Luna ranking failed · ${ranking.error || "No details available"}`
        : rankingPosition >= 0 ? `Luna rank #${rankingPosition + 1}${rankEntry?.reason ? ` · ${rankEntry.reason}` : ""}` : "";
    const analysis = document.createElement("div");
    analysis.className = "local-pipeline-review-analyses";
    if (state.pipeline === "body-reference") {
      for (const [provider, titleText] of [["local", "Local review"], ["luna", "Luna review"]]) {
        const result = candidate.analyses?.[provider];
        if (!result && !(provider === "luna" ? candidate.luna_error : candidate.local_job?.error)) continue;
        const row = document.createElement("p");
        row.className = "local-pipeline-review-explanation";
        const status = result ? (result.pass === true && !result.uncertain ? "Pass" : result.uncertain ? "Uncertain" : "Fail")
          : provider === "local" ? candidate.local_job?.status || "Pending" : candidate.luna_status || "Pending";
        const reason = result?.failure_reason || (result?.failure_categories || []).join(", ") || result?.evidence
          || (provider === "luna" && candidate.luna_error) || (provider === "local" && candidate.local_job?.error) || "";
        row.textContent = `${titleText}: ${status}${reason ? ` · ${reason}` : ""}`;
        analysis.append(row);
      }
    }
    const actions = document.createElement("div");
    actions.className = "button-row compact local-pipeline-review-actions";
    actions.append(save);
    const more = document.createElement("details");
    more.className = "local-pipeline-review-details";
    more.open = previousCandidate === candidate.candidate_id && detailsOpen;
    const moreSummary = document.createElement("summary");
    moreSummary.textContent = "Prompt and source";
    const moreActions = document.createElement("div");
    moreActions.className = "button-row compact";
    const prompt = document.createElement("pre");
    prompt.textContent = candidate.render_input?.prompt || candidate.prompt || "Prompt not recorded";
    const references = document.createElement("p"); references.className = "muted";
    references.textContent = (candidate.render_input?.references || candidate.reference_images || [])
      .map((ref, index) => `Image ${index + 1}: ${ref.label || ref.role || "Reference"}`).join(" · ");
    content.append(prompt, references);
    more.append(moreSummary, content);
    const slot = candidate.slot || candidate.ordinal;
    if (slot <= 8) {
      if (selectedViews[candidate.view] === candidate.candidate_id) {
        const unselect = document.createElement("button"); unselect.textContent = "Unselect";
        unselect.addEventListener("click", () => void perform("unselect", candidate.view, candidate.candidate_id, {candidate_id: ""}).catch(error => setStatus(error.message, true)));
        actions.append(unselect);
      }
      addSlotButton(moreActions, "Regenerate", "regenerate", candidate.view, slot, Boolean(candidate.slot_reason), candidate.slot_reason);
      addSlotButton(moreActions, "Clear slot", "clear", candidate.view, slot, Boolean(candidate.slot_reason), candidate.slot_reason);
    }
    const control = run.slot_controls?.[candidate.view] || {};
    moreActions.append(window.ZetRenderSlots.countControl(control.empty_count || 0, count => void slotAction("generate", candidate.view, null, count).catch(error => setStatus(error.message, true)), {disabled: !control.can_generate, reason: control.reason}));
    if (!select.disabled) actions.append(select);
    if (candidate.image_path && adjustedPosition >= 0) {
      const up = document.createElement("button");
      up.type = "button";
      up.textContent = "Rank up";
      up.disabled = adjustedPosition <= 0;
      up.addEventListener("click", async () => {
        if (state.reviewActionPending) return;
        state.reviewActionPending = true;
        try {
          await saveReviewDecision(candidate);
          await perform("move-rank", candidate.view, candidate.candidate_id, { candidate_id: candidate.candidate_id, direction: "up" });
          state.reviewCandidates = orderedReviewCandidates();
          state.reviewIndex = state.reviewCandidates.findIndex((item) => item.candidate_id === candidate.candidate_id);
          renderReview();
        } catch (error) { setStatus(error.message, true); }
        finally { state.reviewActionPending = false; }
      });
      const down = document.createElement("button");
      down.type = "button";
      down.textContent = "Rank down";
      down.disabled = adjustedPosition >= adjustedOrder.length - 1;
      down.addEventListener("click", async () => {
        if (state.reviewActionPending) return;
        state.reviewActionPending = true;
        try {
          await saveReviewDecision(candidate);
          await perform("move-rank", candidate.view, candidate.candidate_id, { candidate_id: candidate.candidate_id, direction: "down" });
          state.reviewCandidates = orderedReviewCandidates();
          state.reviewIndex = state.reviewCandidates.findIndex((item) => item.candidate_id === candidate.candidate_id);
          renderReview();
        } catch (error) { setStatus(error.message, true); }
        finally { state.reviewActionPending = false; }
      });
      moreActions.append(up, down);
    }
    const quality = document.createElement("section");
    quality.className = "local-pipeline-review-quality";
    const qualityHeading = document.createElement("h3");
    qualityHeading.textContent = "Luna rank & image review";
    quality.append(qualityHeading);
    if (rankingInfo.textContent) quality.append(rankingInfo);
    if (analysis.childElementCount) quality.append(analysis);
    panel.append(title, view);
    if (rankingInfo.textContent || analysis.childElementCount) panel.append(quality);
    if (renderError) panel.append(renderError);
    actions.append(...moreActions.children);
    more.append(info);
    panel.append(decision, actions, more);
    window.ZetImageCardUI.scan(panel);
    if (previousCandidate === candidate.candidate_id) {
      more.scrollTop = detailsScroll;
      quality.scrollTop = qualityScroll;
    }
    $("review-prev").dataset.reviewBoundary = String(state.reviewIndex <= 0);
    $("review-next").dataset.reviewBoundary = String(state.reviewIndex >= state.reviewCandidates.length - 1);
    $("review-prev").disabled = state.reviewActionPending || state.reviewIndex <= 0;
    $("review-next").disabled = state.reviewActionPending || state.reviewIndex >= state.reviewCandidates.length - 1;
    const availableViews = orderedViews(run).filter((view) => state.reviewCandidates.some((item) => item.view === view));
    const currentViewIndex = availableViews.indexOf(candidate.view);
    $("review-prev-view").disabled = state.reviewActionPending || currentViewIndex <= 0;
    $("review-next-view").disabled = state.reviewActionPending || currentViewIndex < 0 || currentViewIndex >= availableViews.length - 1;
    $("review-prev-view").dataset.reviewBoundary = String(currentViewIndex <= 0);
    $("review-next-view").dataset.reviewBoundary = String(currentViewIndex < 0 || currentViewIndex >= availableViews.length - 1);
  }

  let reviewOrigin = null;
  function openReview(candidateId) {
    state.reviewCandidates = orderedReviewCandidates();
    state.reviewIndex = state.reviewCandidates.findIndex((item) => item.candidate_id === candidateId);
    if (state.reviewIndex < 0) return;
    state.compareOpposite = false;
    delete $("review-panel").dataset.candidate;
    reviewOrigin = { element: document.activeElement, candidateId, x: scrollX, y: scrollY };
    renderReview();
    $("review-dialog").showModal();
  }

  async function handleAction(button) {
    const action = button.dataset.localAction;
    const view = button.dataset.view;
    if (state.bulkActionPending) return;
    if (action === "lock-all" || action === "unlock-all") {
      const runId = state.run.run_id, pipeline = state.pipeline, context = contextKey(), generation = state.generation;
      const current = () => state.run?.run_id === runId && state.pipeline === pipeline
        && contextKey() === context && state.generation === generation;
      state.bulkActionPending = true;
      renderSelectedViews(state.run);
      try {
        let body;
        let summary = `Unlock all locked images in this pipeline for ${state.run.character} / ${state.run.phase}${isCostume() ? ` / ${state.run.costume}` : ""}, including other batches? Published Inventory images will be retained.`;
        if (action === "lock-all") {
          const plan = await request(route("lock-all-preview", runId));
          if (!current()) return;
          if (!plan.views.length) { setStatus("All selected images are already locked."); return; }
          body = { selected_views: plan.selected_views };
          summary = `Lock all ${plan.views.length} selected images in this batch?\n\n${plan.views.join(", ")}`;
          if (plan.changes?.length) summary += `\n\nPublish or replace these images, including required lineage:\n${plan.changes.map(item => `${item.pipeline} ${item.view} · ${item.batch_name || "selected batch"}${item.replacing_batch ? ` (currently ${item.replacing_batch})` : ""}`).join("\n")}`;
        }
        if (!window.confirm(summary) || !current()) return;
        setStatus(action === "lock-all" ? "Locking selected images…" : "Unlocking pipeline images…");
        const result = await request(route(action, runId), { method: "POST", body: body ? JSON.stringify(body) : undefined });
        if (!current()) return;
        await loadRun(runId);
        if (!current()) return;
        const failures = Object.entries(result.errors || {});
        setStatus(`${result.completed_views.length} image(s) ${action === "lock-all" ? "locked" : "unlocked"}.${failures.length ? ` Failed: ${failures.map(([view, error]) => `${view}: ${error}`).join(" · ")}` : ""}`, failures.length > 0);
      } finally {
        state.bulkActionPending = false;
        if (state.run) renderSelectedViews(state.run);
      }
      return;
    }
    if (action?.startsWith("stage-")) button.closest(".local-stage-menu")?.removeAttribute("open");
    const candidateId = button.dataset.candidate || button.closest?.("[data-candidate]")?.dataset.candidate || "";
    if (action === "review") { openReview(candidateId); return; }
    if (action === "post-render-adjustments") {
      button.disabled = true;
      try {
        const run = state.run, pipeline = state.pipeline, costume = isCostume() ? selectedCostume() : "";
        const query = costume ? `?costume=${encodeURIComponent(costume)}` : "";
        const result = await request(`${baseUrl()}/runs/${encodeURIComponent(run.run_id)}/post-render-prompt${query}`,
          { method: "POST", body: JSON.stringify({ view }) });
        const params = new URLSearchParams({ universe_id: document.querySelector("#universe-select").value,
          pipeline, run_id: run.run_id, session_id: result.session_id, view,
          page: Object.keys(pagePipelines).find(page => pagePipelines[page] === pipeline) });
        if (costume) params.set("costume", costume);
        location.href = `/local-character-prompt-improvement?${params}`;
      } finally { button.disabled = false; }
      return;
    }
    if (action === "stage-image-generation" || action === "stage-rotation" || action === "stage-no-costume-ref") {
      const rotation = action === "stage-rotation";
      const noCostumeRef = action === "stage-no-costume-ref";
      const runId = state.run.run_id, pipeline = state.pipeline, context = contextKey(), generation = state.generation;
      const params = new URLSearchParams();
      if (isCostume()) params.set("costume", selectedCostume());
      const recompile = Boolean(button.closest(".local-pipeline-view")?.querySelector("input[data-recompile]")?.checked);
      const current = () => state.pipeline === pipeline && state.run?.run_id === runId
        && state.generation === generation && contextKey() === context
        && document.querySelector("#local-pipeline-page").classList.contains("active");
      button.disabled = true;
      try {
        await window.zetStageCharacterViewInImageGenerator(
          `${baseUrl()}/runs/${encodeURIComponent(runId)}/views/${encodeURIComponent(view)}/image-generation-stage?${params}`,
          recompile, current, rotation, noCostumeRef);
      } finally { button.disabled = Boolean(state.run?.slot_controls?.[view]?.[
        rotation ? "rotation_reason" : noCostumeRef ? "no_costume_ref_reason" : "stage_reason"]); }
      return;
    }
    if (action === "save-costume-render-settings") {
      const controls = button.closest(".costume-render-settings");
      const settings = state.run.render_settings[view];
      const params = new URLSearchParams({costume: selectedCostume()});
      button.disabled = true;
      try {
        await request(`${baseUrl()}/runs/${encodeURIComponent(state.run.run_id)}/views/${encodeURIComponent(view)}/render-settings?${params}`,
          {method: "PUT", body: JSON.stringify({mode: controls.querySelector("[data-render-mode]").value,
            costume_reference_view: controls.querySelector("[data-costume-reference]").value, expected_revision: settings.revision})});
        await loadRun(state.run.run_id); setStatus("Rendering settings saved for future renders. Retry keeps its frozen inputs.");
      } finally { button.disabled = false; }
      return;
    }
    if (action === "save-view-reference") {
      const value = button.closest(".local-pipeline-reference-recipe").querySelector("select").value;
      const params = isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : "";
      await request(`${baseUrl()}/runs/${encodeURIComponent(state.run.run_id)}/views/${encodeURIComponent(view)}/reference-recipe${params}`,
        { method: "PUT", body: JSON.stringify({ mode: ["default", "none"].includes(value) ? value : "selected_view", source_view: value }) });
      if (view === "BACK" && state.run.character_progression) $("back-reference").value = value;
      await loadRun(state.run.run_id); setStatus("Reference saved for new individual renders."); return;
    }
    if (action === "save-observations") {
      const observations = $("views").querySelector(`textarea[data-view-observations="${view}"]`)?.value || "";
      const result = await request(route("observations", state.run.run_id, view), { method: "PUT", body: JSON.stringify({ observations }) });
      await loadRun(state.run.run_id);
      setStatus("Observations saved.");
      return;
    }
    if (action === "run-observations") {
      await request(route("reanalyze", state.run.run_id, view), { method: "POST" });
      await loadRun(state.run.run_id);
      setStatus(`AI Observations started for ${view}.`);
      return;
    }
    if (action === "lock") {
      if (hasSharedAssetRouter()) {
        const plan = await request(route("lock-preview", state.run.run_id, view));
        const changes = plan.changes || [];
        const summary = changes.length
          ? `Lock ${view} and replace these lineage images?\n\n${changes.map((item) => `${item.pipeline} ${item.view} · ${item.batch_name || "selected batch"}${item.replacing_batch ? ` (currently ${item.replacing_batch})` : ""}`).join("\n")}`
          : `Lock the selected ${view} image? Its required lineage is already locked to these images.`;
        if (!window.confirm(summary)) return;
      }
      await perform("lock", view, candidateId);
      return;
    }
    if (action === "rerun" || action === "rerun-view") {
      const refreshSources = $("rerun-refresh-sources").checked;
      const recompile = action === "rerun"
        ? $("rerun-recompile").checked
        : Boolean(button.closest(".local-pipeline-view")?.querySelector("input[data-recompile]")?.checked);
      const label = recompile || refreshSources ? "refresh references from the chosen source batches" : "retain the original reference snapshots";
      const compileLabel = recompile ? " Recompile prompts from current templates and coding." : "";
      if (!window.confirm(action === "rerun" ? `Re-run this batch and ${label}?${compileLabel} This replaces generated images and reviews.` : `Replace all ${view} candidates and ${label}?${compileLabel}`)) return;
      await perform(action, view, candidateId, { refresh_sources: refreshSources, recompile });
      return;
    }
    if (["delete", "rerun-failed", "unselect", "unlock"].includes(action)) {
      const prompts = {
        delete: "Delete this batch and its run-owned files?", rerun: "Re-run the batch? This replaces generated images and reviews.",
        "rerun-view": `Replace all ${view} candidates?`, "rerun-failed": `Re-run failed ${view} candidates?`,
        unselect: `Unselect ${view}?`, unlock: `Unlock the local ${view} asset?`,
      };
      if (!window.confirm(prompts[action])) return;
    }
    if (action === "rank-up" || action === "rank-down") {
      const ordered = state.run.rankings?.[view]?.ordered_candidate_ids || [];
      const position = ordered.indexOf(candidateId);
      if (position < 0) return;
      await perform("move-rank", view, candidateId, { candidate_id: candidateId, direction: action === "rank-up" ? "up" : "down" });
      return;
    }
    await perform(action, view, candidateId, action === "rename" ? { batch_name: $("batch-name").value } : action === "select" || action === "unselect" ? { candidate_id: action === "unselect" ? "" : candidateId } : undefined);
  }

  function bind() {
    $("refresh").addEventListener("click", () => {
      if (state.polledRun && state.polledRun.run_id === state.run?.run_id) {
        state.run = state.polledRun;
        state.polledRun = null;
        render();
        setStatus("Batch updates loaded.");
        return;
      }
      void Promise.all([refreshRuns(), readiness()]).catch((error) => setStatus(error.message, true));
    });
    $("preview").addEventListener("click", () => void readiness());
    $("create").addEventListener("click", async () => {
      try {
        const created = await request(route("create"), { method: "POST", body: JSON.stringify(payload()) });
        state.frontSourcePath = "";
        $("apply-phase-change").checked = false;
        $("apply-phase-change").disabled = state.pipeline !== "head-image-edit";
        $("source-mode").value = "upload";
        $("source-phase").value = "";
        updateSourceControls();
        $("source-file").value = "";
        $("source-preview").textContent = "No FRONT reference selected.";
        $("source-remove").hidden = true;
        if (hasSharedAssetRouter()) $("use-anchor").checked = false;
        await refreshRuns(created.run_id);
        if (hasSharedAssetRouter()) void readiness();
        setStatus(state.pipeline === "character-assembly" ? "Batch created. Run front, select a FRONT image, then Run remaining. Luna will compare proportions and identity with your selected FRONT." : "Batch created. Analyze and accept its governing prompts, then Continue to generate FRONT.");
      } catch (error) { setStatus(error.message, true); await readiness(); }
    });
    $("rename").addEventListener("submit", async (event) => { event.preventDefault(); await handleAction({ dataset: { localAction: "rename" } }).catch((error) => setStatus(error.message, true)); });
    $("runs").addEventListener("change", () => {
      syncPipelineRoute();
      void loadRun($("runs").value).catch((error) => setStatus(error.message, true));
    });
    $("costume").addEventListener("change", () => { syncPipelineRoute(); void refreshContext(); });
    $("front-count").addEventListener("change", () => void readiness());
    $("other-count").addEventListener("change", () => void readiness());
    $("use-anchor").addEventListener("change", () => void readiness());
    $("source-batches").addEventListener("change", () => void readiness());
    $("head-pipeline").addEventListener("change", () => { $("source-batches").replaceChildren(); void readiness(); });
    $("start").addEventListener("click", () => void perform(["INTERRUPTED", "STOPPED"].includes(state.run?.status)
      || (state.run?.status === "CANCELLED" && state.run?.created_by_autogenerate) ? "resume" : "start").catch((error) => setStatus(error.message, true)));
    $("stop").addEventListener("click", () => void perform("stop").catch((error) => setStatus(error.message, true)));
    $("rerun").addEventListener("click", () => void handleAction({ dataset: { localAction: "rerun" } }).catch((error) => setStatus(error.message, true)));
    $("reevaluate").addEventListener("click", () => void perform("reevaluate").catch((error) => setStatus(error.message, true)));
    $("delete").addEventListener("click", () => void handleAction({ dataset: { localAction: "delete" } }).catch((error) => setStatus(error.message, true)));
    $("proceed").addEventListener("click", () => void perform("proceed").catch((error) => setStatus(error.message, true)));
    $("source-file").addEventListener("change", () => void uploadHeadSource($("source-file").files?.[0]));
    $("apply-phase-change").addEventListener("change", () => {
      updateSourceControls();
      void readiness();
    });
    $("source-mode").addEventListener("change", () => {
      if (lockedPhaseSourceSelected()) {
        state.frontSourcePath = "";
        $("source-file").value = "";
        $("source-preview").textContent = "No FRONT reference selected.";
        $("source-remove").hidden = true;
      } else $("source-phase").value = "";
      updateSourceControls();
      void readiness();
    });
    $("source-phase").addEventListener("change", () => {
      void readiness();
    });
    window.ZetImageInput.attach($("source-paste"), $("source-file"));
    $("source-paste").addEventListener("paste", (event) => {
      const file = Array.from(event.clipboardData?.items || []).map((item) => item.getAsFile()).find(Boolean);
      if (!file) return;
      event.preventDefault();
      void uploadHeadSource(file);
    });
    $("source-remove").addEventListener("click", async () => {
      state.frontSourcePath = "";
      $("apply-phase-change").checked = false;
      $("apply-phase-change").disabled = state.pipeline !== "head-image-edit";
      updateSourceControls();
      $("source-file").value = "";
      $("source-preview").textContent = "No FRONT reference selected.";
      $("source-remove").hidden = true;
      void readiness();
    });
    for (const host of [$("views"), $("selected")]) host.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-local-action]");
      if (button?.closest("summary")) {
        event.preventDefault();
        event.stopPropagation();
      }
      if (button) void handleAction(button).catch((error) => setStatus(error.message, true));
    });
    $("review-close").addEventListener("click", () => $("review-dialog").close());
    $("review-dialog").addEventListener("close", () => {
      if (reviewOrigin) {
        const origin = reviewOrigin.element?.isConnected ? reviewOrigin.element
          : [...$("views").querySelectorAll("button[data-local-action='review']")].find(button => button.dataset.candidate === reviewOrigin.candidateId);
        origin?.focus({ preventScroll: true });
        window.scrollTo(reviewOrigin.x, reviewOrigin.y);
        reviewOrigin = null;
      }
    });
    $("review-task").addEventListener("click", () => void window.ZetTaskCapture.open());
    $("review-toggle").addEventListener("change", () => { state.compareOpposite = $("review-toggle").checked; renderReview(); });
    $("review-prev").addEventListener("click", () => { void navigateReview(-1); });
    $("review-next").addEventListener("click", () => { void navigateReview(1); });
    $("review-prev-view").addEventListener("click", () => { void navigateReviewView(-1); });
    $("review-next-view").addEventListener("click", () => { void navigateReviewView(1); });
  }

  async function activate(page) {
    const pipeline = pagePipelines[page];
    if (!pipeline) return;
    if (pipeline === state.pipeline) {
      if (contextKey() !== state.contextKey) await refreshContext();
      if (!state.poll) startPolling();
      return;
    }
    configurePipeline(pipeline);
  }

  function deactivate() {
    clearInterval(state.poll); state.poll = null; state.runRequest += 1;
    state.generation += 1;
    state.previewGeneration += 1;
  }

  bind();
  document.querySelector("#character-select").addEventListener("change", () => {
    if (state.pipeline && document.querySelector("#local-pipeline-page").classList.contains("active")) setTimeout(() => void refreshContext(), 0);
  });
  document.querySelector("#phase-select").addEventListener("change", () => {
    if (state.pipeline && document.querySelector("#local-pipeline-page").classList.contains("active")) setTimeout(() => void refreshContext(), 0);
  });
  function taskContext(page) {
    const pipeline = pagePipelines[page];
    const parameters = {};
    const selections = { pipeline: { state: "selected", id: pipeline,
      label: document.querySelector("#local-pipeline-title").textContent.trim() } };
    const routeParams = new URLSearchParams(window.location.search);
    const matching = pipeline === state.pipeline && contextKey() === state.contextKey;
    const status = matching ? state.runsState : "loading";
    const runId = status === "selected" ? $("runs").value
      : routeParams.get("page") === page ? routeParams.get("local_batch") || "" : "";
    const run = matching && state.run?.run_id === runId && state.runState === "selected" ? state.run : null;
    const batch = state.runs.find((item) => item.run_id === runId);
    const runSelection = runId ? { state: run ? "selected" : status === "selected" ? state.runState : status,
      id: runId, label: run?.batch_name || batch?.batch_name || runId } : { state: status === "selected" ? "absent" : status };
    selections.run = { ...runSelection };
    selections.batch = { ...runSelection };
    if (runId) parameters.local_batch = runId;
    if (pipeline === "costume-dressing") {
      const costume = matching && state.costumesState === "selected" ? selectedCostume() : routeParams.get("local_costume") || "";
      const costumeState = matching ? state.costumesState : "loading";
      selections.costume = costume ? { state: costumeState, id: costume, label: costume }
        : { state: costumeState === "selected" ? "absent" : costumeState };
      if (costume) parameters.local_costume = costume;
    }
    if (run && $("review-dialog").open) {
      const candidate = state.reviewCandidates[state.reviewIndex];
      if (candidate && (run.candidates || []).some((item) => item.candidate_id === candidate.candidate_id)) {
        selections.candidate = { state: "selected", id: candidate.candidate_id, label: `${candidate.view} · ${candidate.candidate_id}` };
        const asset = Object.entries(run.local_assets || {}).find(([, item]) => item.candidate_id === candidate.candidate_id && item.batch_id === run.run_id);
        if (asset) selections.asset = { state: "selected", id: asset[0], label: candidate.view };
      }
    }
    return { selections, parameters, workflow_status: run?.status || null };
  }
  window.ZetLocalAssetPipeline = { activate, deactivate, taskContext };
})();
