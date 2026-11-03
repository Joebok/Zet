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
    NOT_STARTED: "Not started",
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
    frontSourcePath: "", poll: null, previewGeneration: 0, sourcePreviewGeneration: 0, contextKey: "", comparisonChoice: "front",
    polledRun: null, pollInFlight: false, renderedSelections: {}, runsState: "loading",
    runState: "absent", costumesState: "absent", runRequest: 0, reviewActionPending: false, bulkActionPending: false,
    costumeSettingsDrafts: {}, restartPending: false, renderMode: "draft", view: "" };
  const restoreParams = new URLSearchParams(window.location.search);
  const pendingBatchSubmissions = new Set();
  const pendingSlotSubmissions = new Set();
  const pendingViewSubmissions = new Set();
  function clearOperationMessage(button, selector) {
    button?.parentElement?.querySelector(selector)?.remove();
  }

  function showOperationStatus() {
    if (!state.run) return;
    const rows = (window.ZetLocalOperations?.rows() || []).filter(row => row.request?.action === "run_available" && row.request?.universe_id === document.querySelector("#universe-select").value
      && row.request?.pipeline === state.pipeline && row.request?.run_id === state.run.run_id);
    rows.sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
    const row = rows.find(item => ["SUBMITTING", "QUEUED", "PREPARING", "WAITING", "RECOVERY_REQUIRED", "UNKNOWN"].includes(item.status)) || rows[0];
    const button = $("proceed");
    if (!row) { clearOperationMessage(button, '[data-submission-status="proceed"]'); return; }
    let message = button.parentElement.querySelector('[data-submission-status="proceed"]');
    if (!message) {
      message = document.createElement("span"); message.className = "action-message";
      message.dataset.submissionStatus = "proceed"; message.setAttribute("role", "status");
      button.insertAdjacentElement("afterend", message);
    }
    const error = row.error || row.result?.error;
    const reasons = {...(row.result?.blocked_views || {}), ...(row.result?.errors || {})};
    message.textContent = `${row.stage || row.status}${error ? `: ${error}` : ""}${Object.keys(reasons).length ? ` — ${Object.entries(reasons).map(([view, reason]) => `${view}: ${reason}`).join(" · ")}` : ""}`;
    message.classList.toggle("error", ["BLOCKED", "FAILED", "RECOVERY_REQUIRED", "PARTIAL", "UNKNOWN"].includes(row.status));
  }
  function showBatchLifecycleStatus() {
    if (!state.run) return;
    const rows = (window.ZetLocalOperations?.rows() || []).filter(row => ["start", "resume"].includes(row.request?.action)
      && row.request?.universe_id === document.querySelector("#universe-select").value && row.request?.pipeline === state.pipeline
      && row.request?.run_id === state.run.run_id);
    rows.sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
    const row = rows.find(item => ["SUBMITTING", "QUEUED", "PREPARING", "WAITING", "UNKNOWN", "RECOVERY_REQUIRED"].includes(item.status)) || rows[0];
    const button = $("start");
    if (!row) { clearOperationMessage(button, '[data-submission-status="batch-lifecycle"]'); return; }
    let message = button.parentElement.querySelector('[data-submission-status="batch-lifecycle"]');
    if (!message) {
      message = document.createElement("span"); message.className = "action-message";
      message.dataset.submissionStatus = "batch-lifecycle"; message.setAttribute("role", "status");
      button.insertAdjacentElement("afterend", message);
    }
    message.textContent = `${row.stage || row.status}${row.error || row.result?.error ? `: ${row.error || row.result.error}` : ""}`;
    message.classList.toggle("error", ["BLOCKED", "FAILED", "RECOVERY_REQUIRED", "PARTIAL", "UNKNOWN"].includes(row.status));
  }
  function showBatchEvaluationStatus() {
    if (!state.run) return;
    const rows = (window.ZetLocalOperations?.rows() || []).filter(row => row.request?.action === "reevaluate" && !row.request?.view
      && row.request?.universe_id === document.querySelector("#universe-select").value && row.request?.pipeline === state.pipeline
      && row.request?.run_id === state.run.run_id && row.request?.render_mode === state.renderMode);
    rows.sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
    const row = rows.find(item => ["SUBMITTING", "QUEUED", "PREPARING", "WAITING", "UNKNOWN", "RECOVERY_REQUIRED"].includes(item.status)) || rows[0];
    const button = $("reevaluate");
    if (!row) { clearOperationMessage(button, '[data-submission-status="reevaluate"]'); return; }
    let message = button.parentElement.querySelector('[data-submission-status="reevaluate"]');
    if (!message) {
      message = document.createElement("span"); message.className = "action-message";
      message.dataset.submissionStatus = "reevaluate"; message.setAttribute("role", "status");
      button.insertAdjacentElement("afterend", message);
    }
    message.textContent = `${row.stage || row.status}${row.error || row.result?.error ? `: ${row.error || row.result.error}` : ""}`;
    message.classList.toggle("error", ["BLOCKED", "FAILED", "RECOVERY_REQUIRED", "PARTIAL", "UNKNOWN"].includes(row.status));
  }
  function showSlotOperationStatus() {
    if (!state.run) return;
    const rows = (window.ZetLocalOperations?.rows() || []).filter(row => ["generate_slots", "regenerate_slot", "retry_render_slot"].includes(row.request?.action)
      && row.request?.universe_id === document.querySelector("#universe-select").value && row.request?.pipeline === state.pipeline
      && row.request?.run_id === state.run.run_id && row.request?.render_mode === state.renderMode);
    rows.sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
    for (const button of document.querySelectorAll("[data-local-slot-view]")) {
      const matching = rows.filter(item => item.request.view === button.dataset.localSlotView
        && String(item.request.slot || "add") === button.dataset.localSlotNumber);
      const row = matching.find(item => ["SUBMITTING", "QUEUED", "PREPARING", "WAITING", "UNKNOWN"].includes(item.status)) || matching[0];
      const inProgress = row && ["SUBMITTING", "QUEUED", "PREPARING", "WAITING", "UNKNOWN"].includes(row.status);
      button.disabled = button.dataset.localSlotDisabled === "true" || Boolean(inProgress);
      if (!row) { if (button.nextElementSibling?.matches("[data-slot-submission-status]")) button.nextElementSibling.remove(); continue; }
      let message = button.nextElementSibling;
      if (!message?.dataset.slotSubmissionStatus) {
        message = document.createElement("span"); message.className = "action-message";
        message.dataset.slotSubmissionStatus = "true"; message.setAttribute("role", "status");
        button.insertAdjacentElement("afterend", message);
      }
      message.textContent = `${row.stage || row.status}${row.error || row.result?.error ? `: ${row.error || row.result.error}` : ""}`;
      message.classList.toggle("error", ["BLOCKED", "FAILED", "RECOVERY_REQUIRED", "PARTIAL", "UNKNOWN"].includes(row.status));
    }
  }
  function showViewOperationStatus() {
    if (!state.run) return;
    const rows = (window.ZetLocalOperations?.rows() || []).filter(row => ["rerun_view", "rerun_failed", "reevaluate"].includes(row.request?.action) && row.request?.view
      && row.request?.universe_id === document.querySelector("#universe-select").value && row.request?.pipeline === state.pipeline
      && row.request?.run_id === state.run.run_id && row.request?.render_mode === state.renderMode);
    rows.sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
    for (const button of document.querySelectorAll("[data-local-view-operation]")) {
      const action = {"rerun-view": "rerun_view", "rerun-failed": "rerun_failed", "reevaluate-view": "reevaluate"}[button.dataset.localViewOperation];
      const matching = rows.filter(item => item.request.view === button.dataset.view && item.request.action === action);
      const row = matching.find(item => ["SUBMITTING", "QUEUED", "PREPARING", "WAITING", "UNKNOWN"].includes(item.status)) || matching[0];
      const inProgress = row && ["SUBMITTING", "QUEUED", "PREPARING", "WAITING", "UNKNOWN"].includes(row.status);
      button.disabled = button.dataset.localViewDisabled === "true" || Boolean(inProgress);
      if (!row) { if (button.nextElementSibling?.matches("[data-view-submission-status]")) button.nextElementSibling.remove(); continue; }
      let message = button.nextElementSibling;
      if (!message?.dataset.viewSubmissionStatus) {
        message = document.createElement("span"); message.className = "action-message";
        message.dataset.viewSubmissionStatus = "true"; message.setAttribute("role", "status");
        button.insertAdjacentElement("afterend", message);
      }
      const reasons = {...(row.result?.blocked_views || {}), ...(row.result?.errors || {})};
      message.textContent = `${row.stage || row.status}${row.error || row.result?.error ? `: ${row.error || row.result.error}` : ""}${Object.keys(reasons).length ? ` — ${Object.entries(reasons).map(([item, reason]) => `${item}: ${reason}`).join(" · ")}` : ""}`;
      message.classList.toggle("error", ["BLOCKED", "FAILED", "RECOVERY_REQUIRED", "PARTIAL", "UNKNOWN"].includes(row.status));
    }
  }
  window.addEventListener("zet-local-operations", () => { if (state.run) { setBusyControls(); showOperationStatus(); showBatchLifecycleStatus(); showBatchEvaluationStatus(); showSlotOperationStatus(); showViewOperationStatus(); } });

  async function submitViewAction(button, action, view, candidateId, body) {
    const key = `${contextKey()}\u0000${state.pipeline}\u0000${state.run?.run_id}\u0000${state.renderMode}\u0000${view}`;
    if (pendingViewSubmissions.has(key)) return;
    pendingViewSubmissions.add(key); button.disabled = true; button.setAttribute("aria-busy", "true");
    let message = button.nextElementSibling;
    if (!message?.dataset.viewSubmissionStatus) {
      message = document.createElement("span"); message.className = "action-message";
      message.dataset.viewSubmissionStatus = "true"; message.setAttribute("role", "status");
      button.insertAdjacentElement("afterend", message);
    }
    message.classList.remove("error"); message.textContent = "Submitting…";
    try {
      const result = await perform(action, view, candidateId, body);
      message.textContent = ["QUEUED", "PREPARING", "WAITING"].includes(result?.status) ? "Action queued — you can continue elsewhere." : result?.stage || "Request processed.";
    } catch (error) {
      message.textContent = `Could not confirm the request: ${error.message}. Check Activity before retrying.`;
      message.classList.add("error");
    } finally {
      pendingViewSubmissions.delete(key); button.removeAttribute("aria-busy");
      button.disabled = button.dataset.localViewDisabled === "true"; showViewOperationStatus();
    }
  }

  async function submitBatchAction(button, action) {
    const key = `${contextKey()}\u0000${state.pipeline}\u0000${state.run?.run_id || ""}\u0000${action}`;
    if (pendingBatchSubmissions.has(key)) return;
    const generation = state.generation;
    const runId = state.run?.run_id;
    const context = contextKey();
    pendingBatchSubmissions.add(key);
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    let message = button.parentElement.querySelector(`[data-submission-status="${action}"]`);
    if (!message) {
      message = document.createElement("span");
      message.className = "action-message";
      message.dataset.submissionStatus = action;
      message.setAttribute("role", "status");
      button.insertAdjacentElement("afterend", message);
    }
    message.classList.remove("error");
    message.textContent = "Submitting…";
    try {
      const result = await perform(action);
      if (generation === state.generation && runId === state.run?.run_id && context === contextKey()) {
        message.textContent = ["QUEUED", "PREPARING", "WAITING"].includes(result?.status)
          ? "Action queued — you can continue elsewhere." : result?.stage || "Request processed. See batch status.";
      }
    } catch (error) {
      if (generation === state.generation && runId === state.run?.run_id && context === contextKey()) {
        message.textContent = `Could not confirm the request: ${error.message}. Refresh the batch before retrying.`;
        message.classList.add("error");
      }
    } finally {
      pendingBatchSubmissions.delete(key);
      if (generation === state.generation && runId === state.run?.run_id && context === contextKey()) {
        button.removeAttribute("aria-busy");
        setBusyControls();
      }
    }
  }

  function contextKey() {
    return `${document.querySelector("#universe-select").value}\u0000${document.querySelector("#character-select").value}\u0000${document.querySelector("#phase-select").value}\u0000${selectedCostume()}`;
  }

  function isCostume() { return state.pipeline === "costume-dressing"; }
  function regenDescription(run, view) {
    const mode = state.renderMode === "final" ? "Final" : "Draft";
    const recipe = run.view_reference_recipes?.[view] || {mode: "default"};
    let references;
    if (state.pipeline === "character-assembly") {
      references = `Resolve the matching ${mode} Body Reference and Head Image inputs for this view again.`;
    } else if (isCostume()) {
      const settings = run.render_settings?.[view] || {};
      references = `Resolve the matching ${mode} Character Assembly input again.`;
      if (view !== "FRONT" && settings.mode === "doll-dressing-no-ref") references += " No selected costume view is used.";
      else if (view !== "FRONT") references += settings.mode === "rotate"
        ? ` Rotate the selected ${settings.costume_reference_view} costume view.`
        : ` Use the selected ${settings.costume_reference_view} costume view as a reference.`;
    } else if (view === "FRONT") {
      const source = run.front_sources_by_mode?.[state.renderMode] || (state.renderMode === "draft" || !run.apply_phase_change ? {path: run.front_source} : {});
      references = recipe.mode === "selected_view" && (state.pipeline === "body-reference" || !run.apply_phase_change)
        ? `Use the selected ${recipe.source_view} image as the reference for new renders (${mode} mode).`
        : state.pipeline !== "body-reference" && source.path && (run.apply_phase_change || recipe.mode !== "none")
        ? `Use the configured ${mode} FRONT input for new renders.` : "No batch view reference is used for FRONT.";
    } else if (recipe.mode === "none") {
      references = "No batch view reference is used.";
    } else {
      const predecessor = {FRONT_LEFT_3_4: "FRONT", FRONT_RIGHT_3_4: "FRONT", LEFT_PROFILE: "FRONT_LEFT_3_4", RIGHT_PROFILE: "FRONT_RIGHT_3_4", BACK_LEFT_3_4: "LEFT_PROFILE", BACK_RIGHT_3_4: "RIGHT_PROFILE", BACK: "BACK_LEFT_3_4"};
      const source = recipe.mode === "selected_view" ? recipe.source_view : run.character_progression
        ? (state.pipeline === "head-image-edit" || (state.pipeline === "body-reference" && view === "BACK") ? "FRONT" : view === "BACK" ? run.character_progression.back_reference || predecessor[view] : predecessor[view])
        : "FRONT";
      references = `Use the currently selected ${source} image as the reference for new renders (${mode} mode).`;
    }
    return `Regenerate eligible occupied ${mode} slots for ${view} with fresh seeds.\n\nPrompts: Compile from current governing masters.\n\nReferences: ${references} Dynamic inputs are captured for new renders; supplemental images follow the prompt’s compilation rules. Source images and locks remain unchanged.\n\nSelected, locked, and active slots are skipped, with reasons reported afterward.`;
  }
  function modeRun(run) {
    if (!run) return run;
    const mode = state.renderMode;
    return {...run, candidates: (run.candidates || []).filter(c => (c.render_mode || "draft") === mode),
      selected_views: run.selected_views_by_mode?.[mode] || (mode === "draft" ? run.selected_views : run.final_selected_views) || {},
      front_anchor: mode === "draft" ? run.front_anchor : run.final_front_anchor,
      slots_by_view: run.slots_by_mode?.[mode] || (mode === "draft" ? run.slots_by_view : run.final_slots_by_view) || {},
      slot_controls: run.slot_controls_by_mode?.[mode] || run.slot_controls || {},
      rankings: mode === "draft" ? run.rankings : run.final_rankings || {}, evaluations: mode === "draft" ? run.evaluations : run.final_evaluations || {}};
  }
  async function updateSizePreview() {
    const mode = state.renderMode, ratio = $("aspect-ratio").value;
    try {
      const sizing = await request(`/api/image-generation/sizing?${new URLSearchParams({render_mode: mode, aspect_ratio: ratio})}`);
      if (mode !== state.renderMode || ratio !== $("aspect-ratio").value) return;
      $("aspect-ratio").setCustomValidity("");
      $("size-preview").textContent = `${sizing.width} × ${sizing.height}`;
    } catch (error) {
      if (mode !== state.renderMode || ratio !== $("aspect-ratio").value) return;
      $("aspect-ratio").setCustomValidity(error.message);
      $("size-preview").textContent = error.message;
    }
  }
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
    params.set("render_mode", state.renderMode);
    const runId = $("runs").value;
    if (runId) {
      params.set("local_batch", runId);
      if (state.run?.character) params.set("character", state.run.character);
      if (state.run?.phase) params.set("phase", state.run.phase);
    }
    else params.delete("local_batch");
    if (isCostume() && selectedCostume()) params.set("local_costume", selectedCostume());
    else params.delete("local_costume");
    if (state.view) params.set("local_view", state.view);
    else params.delete("local_view");
    const search = params.toString();
    window.history.replaceState({}, "", `${window.location.pathname}${search ? `?${search}` : ""}${window.location.hash}`);
  }

  async function request(path, options = {}) {
    const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json",
      "X-Zet-Universe": document.querySelector("#universe-select").value, ...options.headers } });
    const data = await response.json().catch(() => ({}));
    if (!response.ok && data.detail?.preview) {
      const preview = data.detail.preview;
      const approved = await confirmProtectedEffects("Image state changed", data.detail.message,
        preview.protected_effects || [], "Continue");
      if (approved === null) throw new Error("Action cancelled after image state changed.");
      return request(path, {...options, body: JSON.stringify({...JSON.parse(options.body || "{}"),
        confirmation_token: preview.confirmation_token, approved_effects: approved})});
    }
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : response.statusText || "Request failed");
    return data;
  }

  let statusTimer;
  function setStatus(message, error = false) {
    clearTimeout(statusTimer);
    $("status").textContent = window.ZetPipelineMessage(message);
    $("status").classList.toggle("error", error);
    $("status").classList.toggle("success", !error && Boolean(message));
    if (message && !error) statusTimer = setTimeout(() => setStatus(""), 5000);
  }

  function busy(run = state.run) { return Boolean(run && (activeStatuses.has(run.status) || run.slot_work_pending || run.slot_render_ids?.length)); }

  function bulkReadyViews(run) {
    if (!run) return [];
    if (run.progress_by_mode?.[state.renderMode]?.runnable_views) return run.progress_by_mode[state.renderMode].runnable_views;
    const board = modeRun(run), controls = board.slot_controls || {}, pending = new Set(run.slot_render_ids || []);
    const requested = run.character_progression?.requested_views || run.views || [];
    return requested.filter(view => {
      const slots = board.slots_by_view?.[view] || [], control = controls[view] || {};
      if (control.reason || control.legacy) return false;
      const target = Number(view === "FRONT" ? run.front_count || 8 : run.other_count || 4);
      const placeholders = slots.filter(Boolean).slice(0, target).some(id => {
        const c = board.candidates.find(item => item.candidate_id === id);
        return c && c.render_status === "PENDING" && !c.image_path && !c.ask_id && !pending.has(id);
      });
      return slots.filter(Boolean).length < target || placeholders;
    });
  }

  function unstartedViews(run) {
    return (run?.views || []).filter((view) => (view !== "FRONT" || hasSharedAssetRouter()) && (() => {
      const candidates = (run.candidates || []).filter((candidate) => candidate.view === view);
      return candidates.length > 0 && candidates.some((candidate) => candidate.image_filled === false || !candidate.image_path);
    })());
  }

  function route(action, runId = state.run?.run_id || "", view = "", candidateId = "", referenceCandidateId = "") {
    const id = encodeURIComponent(runId);
    const encodedView = encodeURIComponent(view);
    const candidate = encodeURIComponent(candidateId);
    switch (action) {
      case "preview": return `${baseUrl()}/preview`;
      case "runs": return `${baseUrl()}/runs${query()}`;
      case "create": return `${baseUrl()}/runs`;
      case "detail": return `${baseUrl()}/runs/${id}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "image": return `${baseUrl()}/runs/${id}/images/${candidate}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "thumbnail": return `${baseUrl()}/runs/${id}/thumbnails/${candidate}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "reference-image": return `${baseUrl()}/runs/${id}/reference-images/${encodedView}/${candidate}?${new URLSearchParams({render_mode: state.renderMode, candidate_id: referenceCandidateId, ...(isCostume() ? {costume: selectedCostume()} : {})})}`;
      case "reference-thumbnail": return `${baseUrl()}/runs/${id}/reference-thumbnails/${encodedView}/${candidate}?${new URLSearchParams({render_mode: state.renderMode, candidate_id: referenceCandidateId, ...(isCostume() ? {costume: selectedCostume()} : {})})}`;
      case "rename": return `${baseUrl()}/runs/${id}/name${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "start": return `${baseUrl()}/runs/${id}/start${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "run-available": return `${baseUrl()}/runs/${id}/run-available${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "resume": return `${baseUrl()}/runs/${id}/resume${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "stop": return `${baseUrl()}/runs/${id}/stop${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "rerun": return `${baseUrl()}/runs/${id}/rerun${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "restart":
      case "restart-preview": return `${baseUrl()}/runs/${id}/${action}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "reevaluate": return `${baseUrl()}/runs/${id}/reevaluate${query({ render_mode: state.renderMode })}`;
      case "delete": return `${baseUrl()}/runs/${id}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "rerun-view": return `${baseUrl()}/runs/${id}/views/${encodedView}/rerun${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "rerun-failed": return `${baseUrl()}/runs/${id}/rerun-failed${query({ view })}`;
      case "observations": return `${baseUrl()}/runs/${id}/views/${encodedView}/observations${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "reanalyze": return `${baseUrl()}/runs/${id}/views/${encodedView}/reanalyze${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "move-rank": return `${baseUrl()}/runs/${id}/views/${encodedView}/ranking/move${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "select":
      case "unselect": return `${baseUrl()}/runs/${id}/views/${encodedView}/select${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "review": return `${baseUrl()}/runs/${id}/candidates/${candidate}/review${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "retry": return `${baseUrl()}/runs/${id}/candidates/${candidate}/retry${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "lock": return `${baseUrl()}/runs/${id}/views/${encodedView}/lock${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "lock-all-preview":
      case "lock-all":
      case "unlock-all": return `${baseUrl()}/runs/${id}/${action}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "delete-drafts": return `${baseUrl()}/runs/${id}/delete-draft-images${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "lock-preview": return `${baseUrl()}/runs/${id}/views/${encodedView}/lock-preview${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "unlock": return `${baseUrl()}/runs/${id}/views/${encodedView}/unlock${query()}`;
      case "proceed": return `${baseUrl()}/runs/${id}/views/FRONT/proceed${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "image-prompt": return `${baseUrl()}/runs/${id}/image-prompt/${encodedView}${query({render_mode: state.renderMode})}`;
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

  async function showComparison(kind) {
    if (!state.run?.run_id) { setStatus("Choose a batch before checking differences.", true); return; }
    const runId = state.run.run_id, generation = state.generation, mode = state.renderMode, context = contextKey();
    const host = $("comparison-report");
    host.hidden = false;
    host.textContent = "Checking saved batch evidence…";
    try {
      const suffix = query({render_mode: mode});
      const report = await request(`${baseUrl()}/runs/${encodeURIComponent(runId)}/comparisons/${kind}${suffix}`);
      if (generation !== state.generation || runId !== state.run?.run_id || mode !== state.renderMode || context !== contextKey()) return;
      host.replaceChildren();
      const title = document.createElement("strong");
      title.textContent = `${kind === "draft" ? "Final vs Draft" : kind === "masters" ? "Batch vs current masters" : "Frozen vs current references"}: ${report.changed_count} changed, ${report.unavailable_count} unavailable`;
      host.append(title);
      const list = document.createElement("ul");
      for (const row of report.rows || []) {
        const item = document.createElement("li");
        item.textContent = `${row.view || row.label || row.source_id}${row.source_view ? ` / ${row.source_view}` : ""}: ${row.unavailable ? "unavailable" : row.changed === null ? "no comparison available" : row.changed ? "changed" : "unchanged"}`;
        list.append(item);
      }
      host.append(list);
    } catch (error) {
      if (generation === state.generation && runId === state.run?.run_id && context === contextKey()) host.textContent = error.message;
    }
  }

  async function useCurrentMasters() {
    if (!state.run?.run_id) { setStatus("Choose a batch first.", true); return; }
    const runId = state.run.run_id, generation = state.generation, mode = state.renderMode, context = contextKey();
    const host = $("masters-report");
    host.hidden = false;
    host.textContent = "Compiling current masters and checking requested views…";
    $("use-masters").disabled = true;
    try {
      const report = await request(`${baseUrl()}/runs/${encodeURIComponent(runId)}/use-current-masters${query({render_mode: mode})}`, {method: "POST"});
      if (generation !== state.generation || runId !== state.run?.run_id || mode !== state.renderMode || context !== contextKey()) return;
      host.replaceChildren();
      const heading = document.createElement("strong");
      heading.textContent = report.all_ready ? "Current masters and references are ready for every requested view." : "Some views still need inputs.";
      host.append(heading);
      for (const row of report.views || []) {
        const item = document.createElement("details");
        const label = document.createElement("summary");
        label.textContent = `${row.view}: ${row.status === "ready" ? `prompt ${row.prompt_sha256.slice(0, 12)} · ${row.references.length} reference(s)` : row.reason}`;
        item.append(label);
        if (row.status === "ready") {
          const refs = document.createElement("p");
          refs.textContent = row.references.map(ref => `${ref.role || "reference"}: ${ref.candidate_id || ref.sha256.slice(0, 12) || "current"} (${ref.render_mode || mode})`).join(" · ") || "No image references.";
          const prompt = document.createElement("pre");
          prompt.textContent = row.prompt;
          item.append(refs, prompt);
        }
        host.append(item);
      }
      await loadRun(runId);
    } catch (error) {
      if (generation === state.generation && runId === state.run?.run_id && context === contextKey()) host.textContent = error.message;
    } finally { $("use-masters").disabled = false; }
  }

  function payload() {
    const lockedPhaseSource = ["head-image", "head-image-edit"].includes(state.pipeline) && $("apply-phase-change").checked && $("source-mode").value === "locked";
    return {
      batch_name: $("create-name").value,
      character: document.querySelector("#character-select").value,
      phase: document.querySelector("#phase-select").value,
      costume: isCostume() ? selectedCostume() : "",
      universe_style_variant: $("style-variant").value,
      front_count: Number($("front-count").value),
      other_count: Number($("other-count").value),
      use_front_anchor: state.pipeline === "character-assembly" ? false : hasSharedAssetRouter() ? $("use-anchor").checked : state.pipeline === "body-reference" || ["head-image", "head-image-edit"].includes(state.pipeline),
      head_pipeline: state.pipeline === "character-assembly" ? $("head-pipeline").value : "head-image",
      front_source_path: lockedPhaseSource ? "" : state.frontSourcePath,
      front_source_phase: lockedPhaseSource ? $("source-phase").value : "",
      front_source_pipeline: $("source-pipeline").value,
      apply_phase_change: state.pipeline === "head-image-edit" ? $("apply-phase-change").checked
        : state.pipeline === "head-image" && Boolean(state.frontSourcePath || lockedPhaseSource) && $("apply-phase-change").checked,
      source_batches: hasSharedAssetRouter() ? Object.fromEntries(Array.from($("source-batches").querySelectorAll("select[data-source-role]"), (select) => [select.dataset.sourceRole, select.value])) : {},
    };
  }

  function lockedPhaseSourceSelected() {
    return ["head-image", "head-image-edit"].includes(state.pipeline) && $("apply-phase-change").checked && $("source-mode").value === "locked";
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
    const phaseChange = ["head-image", "head-image-edit"].includes(state.pipeline) && $("apply-phase-change").checked;
    $("source-mode-option").hidden = !phaseChange;
    $("upload-source").hidden = lockedPhaseSourceSelected();
    $("locked-source").hidden = !lockedPhaseSourceSelected();
    if (["head-image", "head-image-edit"].includes(state.pipeline)) $("apply-phase-change").disabled = false;
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
      const asset = (result.assets || []).find(item => item.pipeline?.toLowerCase() === $("source-pipeline").value
        && item.view === "FRONT" && !item.qualifier && (item.render_mode || "draft") === "draft");
      host.replaceChildren();
      if (asset) {
        const image = document.createElement("img");
        image.src = universeImageUrl(`/api/local/assets/${encodeURIComponent(asset.key)}/image?${new URLSearchParams({ character, phase, v: asset.image_sha256 || "" })}`);
        image.alt = `Locked FRONT ${window.ZetPipelineLabel($("source-pipeline").value)} image from ${phase}`;
        host.append(image);
      } else {
        host.append(`No locked FRONT ${window.ZetPipelineLabel($("source-pipeline").value)} image in ${phase}. `);
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

  function viewUrl(view = "") {
    const params = new URLSearchParams(window.location.search);
    params.set("page", Object.keys(pagePipelines).find(page => pagePipelines[page] === state.pipeline));
    params.set("render_mode", state.renderMode);
    if (state.run?.run_id) params.set("local_batch", state.run.run_id);
    if (state.run?.character) params.set("character", state.run.character);
    if (state.run?.phase) params.set("phase", state.run.phase);
    if (isCostume() && selectedCostume()) params.set("local_costume", selectedCostume());
    if (view) params.set("local_view", view); else params.delete("local_view");
    return `${window.location.pathname}?${params}`;
  }

  function renderViewNavigation(run) {
    const host = $("view-navigation");
    host.hidden = !state.view || !run;
    if (host.hidden) return;
    const views = orderedViews(run);
    const index = views.indexOf(state.view);
    $("return-batch").href = viewUrl();
    for (const [id, target] of [["previous-view", views[index - 1]], ["next-view", views[index + 1]]]) {
      const link = $(id);
      link.hidden = !target;
      if (target) { link.href = viewUrl(target); link.textContent = `${id === "previous-view" ? "Previous" : "Next"}: ${target.replaceAll("_", " ")}`; }
    }
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
    if (run?.scoped_kind) {
      const active = activeStatuses.has(run.status) || Boolean(run.slot_render_ids?.length);
      $("start").hidden = !["QUEUED", "STOPPED", "INTERRUPTED", "CANCELLED"].includes(run.status);
      $("start").disabled = active;
      $("start").textContent = run.status === "QUEUED" ? "Start batch" : "Resume batch";
      $("stop").hidden = !active;
      $("stop").disabled = !active;
      $("rerun").disabled = false;
      $("reevaluate").disabled = false;
      $("delete").disabled = false;
      $("rename").hidden = false;
      $("proceed").hidden = false;
      $("proceed").disabled = false;
      $("proceed").textContent = state.pipeline === "character-assembly"
        ? run.progression?.next_views?.includes("FRONT") ? "Run front" : "Run remaining" : "Run available";
      return;
    }
    const operationBusy = (window.ZetLocalOperations?.rows() || []).some(row =>
      ["SUBMITTING", "QUEUED", "PREPARING", "WAITING", "UNKNOWN"].includes(row.status) && row.request?.universe_id === document.querySelector("#universe-select").value
      && row.request?.pipeline === state.pipeline && row.request?.run_id === run?.run_id);
    const isBusy = operationBusy || (!run?.slot_paused && (busy(run) || Boolean(run?.slot_render_ids?.length)));
    const resumable = ["INTERRUPTED", "STOPPED"].includes(run?.status)
      || (run?.status === "CANCELLED" && run?.created_by_autogenerate) || Boolean(run?.slot_paused);
    $("start").hidden = !run;
    $("start").disabled = isBusy || !(run?.status === "QUEUED" || resumable);
    $("start").textContent = resumable ? "Resume batch" : "Start batch";
    $("stop").hidden = !isBusy;
    $("stop").disabled = !isBusy;
    $("stop").textContent = run?.slot_render_ids?.length ? "Pause batch" : "Stop batch";
    $("rerun").disabled = !run || isBusy || state.restartPending;
    $("reevaluate").disabled = !run;
    $("reevaluate").removeAttribute("title");
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
      $("proceed").disabled = continuationDisabled(run) || run.progression.complete;
      $("proceed").textContent = state.pipeline === "character-assembly"
        ? (run.progression.complete ? "All views rendered" : run.progression.next_views.includes("FRONT") ? "Run front"
          : run.progression.next_views.length ? "Run remaining" : "All views rendered")
        : run.progression.complete ? "All views selected"
          : isCostume() ? (run.progression.next_views.length ? "Run ready views" : "No unrendered views ready")
            : run.progression.next_views.length ? `Continue → ${run.progression.next_views.join(" + ")}` : "All stages open";
      $("proceed").title = run.progression.complete
        ? (isCostume()
          ? "All requested views are selected. Review each view’s saved mode and references before publication."
          : "All requested views are selected. Refinement and publication remain available.")
        : run.progression.reason || (state.pipeline === "character-assembly"
          ? "Render FRONT first, select it, then run remaining views. Luna compares proportions and identity with the selected FRONT."
          : "Generate the next stage from your selected images");
      $("anchor-option").hidden = true;
      const readyViews = bulkReadyViews(run);
      const frontSelected = Boolean(modeRun(run)?.selected_views?.FRONT);
      $("proceed").disabled = isBusy || !readyViews.length;
      $("proceed").textContent = !frontSelected && readyViews.includes("FRONT") ? "Run front" : "Run available";
      $("proceed").title = readyViews.length ? `Ready: ${readyViews.join(", ")}` : "No views are ready to run.";
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
        : run.progression.reason || (run.progression.complete
          ? "All requested views are selected. Open a view to review its saved mode and references."
          : run.progression.next_views.length
            ? `Ready to run: ${run.progression.next_views.join(" + ")}. Review each view’s saved mode and references before running.`
            : "No views are ready with the saved mode inputs. Open a view to see its prerequisite and next action.");
      progression.append(label);
      const modeProgress = run.progress_by_mode?.[state.renderMode];
      if (modeProgress) label.textContent = `${state.renderMode === "final" ? "Final" : "Draft"}: ${modeProgress.selected_count}/${modeProgress.requested_count} views selected. ${bulkReadyViews(run).length ? `Ready: ${bulkReadyViews(run).join(", ")}.` : "Select required references or review current images."}`;
      for (const warning of run.reference_warnings || []) {
        const note = document.createElement("p"); note.className = "muted";
        note.textContent = `${warning.view}: ${warning.message}`; progression.append(note);
      }
    }
    if (run) {
      const readyViews = bulkReadyViews(run);
      $("proceed").disabled = isBusy || !readyViews.length;
      $("proceed").textContent = !modeRun(run)?.selected_views?.FRONT && readyViews.includes("FRONT") ? "Run front" : "Run available";
      $("proceed").title = readyViews.length ? `Ready: ${readyViews.join(", ")}` : "No views are ready to run.";
    }
    $("style-choice").hidden = state.pipeline === "character-assembly";
    $("saved-style").hidden = !run;
    if (state.pipeline === "character-assembly") $("anchor-option").hidden = true;
    $("back-reference-label").hidden = state.pipeline !== "head-image" || !(run?.character_progression?.requested_views || []).includes("BACK");
    if (run && $("back-reference").dataset.runId !== run.run_id) {
      $("back-reference").value = run.character_progression?.back_reference || "BACK_LEFT_3_4";
      $("back-reference").dataset.runId = run.run_id;
    }
    for (const option of $("back-reference").options) option.disabled = !modeRun(run)?.selected_views?.[option.value];
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

  function imageUrl(candidate, full = false) { return versionedImageUrl(route(full ? "image" : "thumbnail", state.run.run_id, "", candidate.candidate_id), candidate.image_sha256 || ""); }

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
    if (action === "delete-drafts") button.classList.add("danger-action");
    button.dataset.localAction = action;
    if (action === "lock" || action === "unlock") button.classList.add("local-pipeline-lock-action");
    if (["rerun-view", "rerun-failed", "reevaluate-view"].includes(action)) {
      button.dataset.localViewOperation = action; button.dataset.localViewDisabled = String(disabled);
    }
    button.dataset.view = view;
    button.dataset.candidate = candidate;
    button.disabled = disabled;
    if (primary) button.classList.add("primary-action");
    host.append(button);
    return button;
  }

  function candidateModeLabel(candidate, image) {
    const label = document.createElement("p");
    label.className = "image-card-state";
    const update = () => {
      const mode = candidate.render_mode === "final" ? "Final" : "Draft";
      const dimensions = image?.naturalWidth && image?.naturalHeight
        ? ` · ${image.naturalWidth} × ${image.naturalHeight}` : "";
      label.textContent = `${mode}${dimensions}`;
    };
    if (image) image.onload = update;
    update();
    return label;
  }

  function renderSelectedViews(run) {
    const host = $("selected");
    host.replaceChildren();
    const selected = run.selected_views || {};
    const qualifier = isCostume() ? String(run.costume || "").trim().toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "_").replace(/^_+|_+$/g, "") : "";
    const assetKey = (view) => `${state.renderMode === "final" ? "final:" : ""}${state.pipeline}${qualifier ? `:${qualifier}` : ""}:${view}`;
    const controls = document.createElement("div");
    controls.className = "button-row local-pipeline-bulk-controls";
    const hasUnlockedSelection = Object.entries(selected).some(([view, id]) => {
      const asset = run.local_assets?.[assetKey(view)];
      return id && !(asset?.locked && asset.batch_id === run.run_id && asset.candidate_id === id);
    });
    const hasLocks = Object.entries(run.local_assets || {}).some(([key, asset]) =>
      asset.locked && asset.batch_id === run.run_id && key === assetKey(asset.view));
    addButton(controls, "Lock all", "lock-all", { disabled: state.bulkActionPending || !hasUnlockedSelection });
    addButton(controls, "Unlock all", "unlock-all", { disabled: state.bulkActionPending || !hasLocks });
    addButton(controls, "Delete all Draft images", "delete-drafts", { disabled: state.bulkActionPending });
    $("batch-bulk-actions").replaceChildren(controls);
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
      const link = document.createElement("a");
      link.href = viewUrl(view);
      link.textContent = view.replaceAll("_", " ");
      title.append(link);
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
        const imageButton = document.createElement("button");
        imageButton.type = "button";
        imageButton.className = "local-pipeline-selected-image";
        imageButton.setAttribute("aria-label", `Review selected ${view} image`);
        imageButton.append(image);
        imageButton.addEventListener("click", () => openReview(candidate.candidate_id, true));
        article.append(imageButton);
        article.append(candidateModeLabel(candidate, image));
        const asset = run.local_assets?.[assetKey(view)];
        const locked = Boolean(asset?.locked && asset.candidate_id === candidate.candidate_id
          && asset.batch_id === run.run_id);
        const lockedInAnotherBatch = Boolean(asset?.locked && asset.batch_id !== run.run_id);
        if (lockedInAnotherBatch) lockNotice.hidden = false;
        const lockState = document.createElement("p");
        lockState.className = locked ? "success-text" : "muted";
        lockState.textContent = locked ? "Locked" : "";
        lockState.hidden = !locked;
        article.append(lockState);
        const controls = document.createElement("div");
        controls.className = "button-row compact";
        const overrideNeedsUnlock = Boolean(candidate.override && asset?.locked && !locked);
        if (overrideNeedsUnlock) {
          lockState.textContent = "Override selected. Unlock the published image before locking this override.";
          addButton(controls, "Unlock published image", "unlock", { view, disabled: state.bulkActionPending });
        }
        addButton(controls, locked ? "Unlock" : "Lock", locked ? "unlock" : "lock",
          { view, disabled: state.bulkActionPending || overrideNeedsUnlock });
        if (!locked) addButton(controls, "Unselect", "unselect", { view, candidate: candidate.candidate_id,
          disabled: state.bulkActionPending });
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

  function renderBatchCards(run) {
    const host = $("selected");
    host.replaceChildren();
    const controls = document.createElement("div");
    controls.className = "button-row compact";
    addButton(controls, "Lock all", "lock-all");
    addButton(controls, "Unlock all", "unlock-all");
    addButton(controls, "Delete all Draft images", "delete-drafts");
    $("batch-bulk-actions").replaceChildren(controls);
    for (const view of orderedViews(run)) {
      const card = (run.selected_cards || []).find(item => item.view === view);
      if (!card) continue;
      const article = document.createElement("article");
      article.className = "local-pipeline-selected-card";
      const heading = document.createElement("h2"), link = document.createElement("a");
      link.href = viewUrl(card.view); link.textContent = card.view.replaceAll("_", " ");
      link.className = "image-card-text-control";
      heading.append(link); article.append(heading);
      if (card.display_kind) {
        const image = document.createElement("img");
        image.loading = "lazy";
        image.src = card.display_kind === "selected"
          ? versionedImageUrl(route("thumbnail", run.run_id, "", card.display_candidate_id), card.display_image_sha256 || "")
          : versionedImageUrl(`/api/local/assets/${encodeURIComponent(card.locked_key)}/image?${new URLSearchParams({character: run.character, phase: run.phase})}`, card.display_image_sha256 || "");
        image.alt = `${card.display_kind === "selected" ? "Selected" : "Locked"} ${card.view} ${state.renderMode} image`;
        const imageButton = document.createElement("button");
        imageButton.type = "button"; imageButton.className = "local-pipeline-selected-image";
        imageButton.setAttribute("aria-label", `Review ${card.display_kind} ${card.view} image`);
        imageButton.append(image);
        imageButton.addEventListener("click", () => openReview(card.view, true));
        article.append(imageButton);
      }
      const status = document.createElement("p");
      status.className = card.locked || card.display_kind === "locked" ? "success-text" : "";
      status.textContent = card.locked || card.display_kind === "locked" ? "Locked" : card.selected_candidate_id
        ? card.selected_available ? "" : "Selected image unavailable"
        : card.locked_candidate_id ? "Locked image from another selection" : "No image selected";
      status.hidden = !status.textContent;
      article.append(status);
      if (card.selected_candidate_id && card.selected_available) {
        const actions = document.createElement("div"); actions.className = "button-row compact";
        addButton(actions, card.locked ? "Unlock" : "Lock", card.locked ? "unlock" : "lock", {view: card.view});
        article.append(actions);
      }
      host.append(article);
    }
    host.hidden = !run.selected_cards?.length;
  }

  function normalizeScoped(summary, detail = null) {
    const mode = state.renderMode;
    const run = {...summary, scoped_kind: detail ? "view" : "summary",
      operation_contexts: {[mode]: {batch: summary.operation_context,
        views: detail ? {[detail.view]: detail.operation_context} : {},
        candidate_retry: detail?.candidate_retry_contexts || {},
        evaluation: {batch: summary.evaluation_context,
          views: detail ? {[detail.view]: detail.evaluation_context} : {}}}}};
    if (!detail) return run;
    return {...run, ...detail, scoped_kind: "view", progress_by_mode: summary.progress_by_mode,
      progression: summary.progression, candidates: detail.candidates,
      selected_views_by_mode: summary.selected_views_by_mode,
      slots_by_mode: detail.slots_by_mode, slot_controls_by_mode: detail.slot_controls_by_mode,
      rankings: mode === "draft" ? {[detail.view]: detail.ranking} : {},
      final_rankings: mode === "final" ? {[detail.view]: detail.ranking} : {},
      evaluations: mode === "draft" ? {[detail.view]: detail.evaluation} : {},
      final_evaluations: mode === "final" ? {[detail.view]: detail.evaluation} : {},
      view_reviews: {[detail.view]: detail.view_review},
      view_reference_recipes: {[detail.view]: detail.reference_recipe},
      render_settings: {[detail.view]: detail.render_settings}};
  }

  async function readScopedRun(runId) {
    const mode = state.renderMode;
    const suffix = query({render_mode: mode});
    const summaryRequest = request(`${baseUrl()}/runs/${encodeURIComponent(runId)}/summary${suffix}`);
    if (!state.view) return normalizeScoped(await summaryRequest);
    const viewRequest = request(`${baseUrl()}/runs/${encodeURIComponent(runId)}/views/${encodeURIComponent(state.view)}${suffix}`);
    const [summary, detail] = await Promise.all([summaryRequest, viewRequest]);
    return normalizeScoped(summary, detail);
  }

  function refinementUrl(view) {
    const params = new URLSearchParams({ pipeline: state.pipeline, run_id: state.run.run_id, view,
      universe_id: document.querySelector("#universe-select").value, render_mode: state.renderMode });
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
      card.append(candidateModeLabel(candidate, image));
      if (candidate.elapsed_seconds != null && Number.isFinite(Number(candidate.elapsed_seconds))) {
        const generationTime = document.createElement("p");
        generationTime.className = "local-pipeline-generation-time muted";
        generationTime.textContent = `Generated in ${Math.round(Number(candidate.elapsed_seconds))} seconds`;
        card.append(generationTime);
      }
    } else card.append(candidateModeLabel(candidate, null));
    const status = document.createElement("p");
    status.className = "muted image-card-state";
    const rankingOrder = ranking.luna_ordered_candidate_ids?.length
      ? ranking.luna_ordered_candidate_ids
      : ranking.ordered_candidate_ids || [];
    const rank = rankingOrder.indexOf(candidate.candidate_id);
    const proxy = state.run?.proxy_health;
    const warning = ["QUEUED", "RUNNING"].includes(candidate.render_status) && ["attention", "unavailable"].includes(proxy?.status) ? ` · ${proxy.reason || "AI_Proxy needs attention"}` : "";
    const checked = candidate.queue_checked_at ? ` · Checked ${new Date(candidate.queue_checked_at).toLocaleTimeString()}` : "";
    status.textContent = `${candidate.slot_waiting ? `Waiting for prerequisites · ${candidate.slot_waiting}` : candidate.queue_status_label || renderStatusLabels[candidate.render_status] || statusLabels[candidate.status] || candidate.status || "Unknown"}${warning}${checked}${rank >= 0 ? ` · Rank #${rank + 1}${ranking.status === "STALE" ? " (stale)" : ""}` : ""}`;
    if (candidate.override) status.textContent += " / Override";
    card.append(status);
    if (candidate.source_change_fyi) {
      const fyi = document.createElement("span");
      fyi.className = "status-badge review";
      fyi.textContent = "Source changed";
      fyi.title = "A saved source changed after this image was made.";
      card.append(fyi);
    }
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
    button.dataset.localSlotView = view; button.dataset.localSlotNumber = String(slot || "add");
    button.dataset.localSlotDisabled = String(disabled);
    button.addEventListener("click", () => void slotAction(operation, view, slot, 1, button));
    host.append(button);
  }

  async function slotAction(operation, view, slot, count = 1, button = null) {
    const generation = state.generation, runId = state.run.run_id, key = contextKey();
    const suffix = isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : "";
    const path = `${baseUrl()}/runs/${encodeURIComponent(runId)}/views/${encodeURIComponent(view)}/slots${slot ? `/${slot}/${operation}` : ""}${suffix}${suffix ? "&" : "?"}compact=true`;
    if (operation !== "clear" && operation !== "retry" && !$("aspect-ratio").reportValidity()) return;
    const submissionKey = `${key}\u0000${state.pipeline}\u0000${runId}\u0000${state.renderMode}\u0000${view}\u0000${slot || "add"}`;
    if (pendingSlotSubmissions.has(submissionKey)) return;
    pendingSlotSubmissions.add(submissionKey);
    let message;
    if (button) {
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      if (button.nextElementSibling?.dataset.slotSubmissionStatus) button.nextElementSibling.remove();
      message = document.createElement("span");
      message.className = "action-message";
      message.dataset.slotSubmissionStatus = "true";
      message.setAttribute("role", "status");
      message.textContent = "Submitting…";
      button.insertAdjacentElement("afterend", message);
    }
    const selectedSlots = modeRun(state.run).slots_by_view;
    let accepted = false;
    try {
      if (operation !== "clear" && window.ZetLocalOperations) {
        const expected = state.run?.operation_contexts?.[state.renderMode]?.views?.[view];
        if (!expected) throw new Error("Batch inputs are still loading. Refresh before submitting.");
        const actions = {generate: "generate_slots", regenerate: "regenerate_slot", retry: "retry_render_slot"};
        const result = await window.ZetLocalOperations.submit({universe_id: document.querySelector("#universe-select").value,
          pipeline: state.pipeline, run_id: runId, character: state.run.character || "", phase: state.run.phase || "",
          batch_name: state.run.batch_name || "", costume: isCostume() ? selectedCostume() : "", action: actions[operation],
          render_mode: state.renderMode, view, ...(slot ? {slot, expected_candidate_id: selectedSlots?.[view]?.[slot - 1] || ""} : {count}),
          aspect_ratio: $("aspect-ratio").value, expected_context: expected});
        accepted = true;
        if (generation === state.generation && state.run?.run_id === runId && contextKey() === key) {
          if (message) message.textContent = ["QUEUED", "PREPARING", "WAITING"].includes(result.status) ? "Action queued — you can continue elsewhere." : result.stage;
          setStatus("Action queued — you can continue elsewhere.");
        }
        return;
      }
      await request(path, {method: "POST", body: JSON.stringify({... (slot ? {expected_candidate_id: selectedSlots?.[view]?.[slot - 1] || null} : {count}), render_mode: state.renderMode, aspect_ratio: $("aspect-ratio").value})});
      accepted = true;
      if (generation !== state.generation || state.run?.run_id !== runId || contextKey() !== key) return;
      if (message) message.textContent = operation === "clear" ? "Slot cleared." : "Renders queued.";
      await loadRun(runId, generation);
      setStatus(operation === "clear" ? "Slot cleared." : "Renders queued.");
    } catch (error) {
      if (generation === state.generation && state.run?.run_id === runId && contextKey() === key) {
        const text = accepted ? `Request accepted; refresh failed: ${error.message}` : `Could not confirm request: ${error.message}. Refresh before retrying.`;
        if (message) { message.textContent = text; message.classList.add("error"); }
        setStatus(text, true);
      }
    } finally {
      pendingSlotSubmissions.delete(submissionKey);
      if (button) { button.removeAttribute("aria-busy"); button.disabled = button.dataset.localSlotDisabled === "true"; showSlotOperationStatus(); }
    }
  }

  function mergeLiveRun(latest) {
    if (!state.view) {
      state.run = latest;
      render();
      return;
    }
    const currentId = state.reviewCandidates[state.reviewIndex]?.candidate_id;
    const decision = $("review-panel").querySelector("input[name='local-human-decision']:checked")?.value;
    const oldRun = state.run;
    if (isCostume() && oldRun) for (const controls of $("views").querySelectorAll(".costume-render-settings")) {
      const view = controls.querySelector("[data-render-mode]")?.dataset.renderMode;
      if (!view) continue;
      const oldSaved = oldRun.render_settings?.[view] || {};
      const mode = controls.querySelector("[data-render-mode]").value;
      const reference = controls.querySelector("[data-costume-reference]").value;
      const changed = mode !== oldSaved.mode || (view !== "FRONT" && reference !== (oldSaved.costume_reference_view || ""));
      const latestSaved = latest.render_settings?.[view] || {};
      const savedNow = mode === latestSaved.mode
        && (view === "FRONT" || reference === (latestSaved.costume_reference_view || ""));
      if (changed && !savedNow) state.costumeSettingsDrafts[view] = {mode, costume_reference_view: reference, revision: latestSaved.revision};
      else delete state.costumeSettingsDrafts[view];
    }
    state.run = latest;
    $("saved-style").textContent = latest.universe_style_variant ? `Batch style: ${latest.universe_style_variant}` : "Batch style: canonical";
    const signature = run => JSON.stringify([run?.candidates, run?.slots_by_mode, run?.slot_controls_by_mode, run?.render_settings, run?.rankings, run?.evaluations, run?.final_rankings, run?.final_evaluations, run?.selected_views_by_mode, run?.local_assets, run?.locked_draft_comparisons, run?.view_reviews, run?.sources, run?.front_source_sha256, run?.view_reference_recipes, run?.active_template_revision_id]);
    const changed = signature(oldRun) !== signature(latest);
    const replacement = document.createElement("div");
    if (changed) renderViews(modeRun(latest), replacement);
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
      const sourceSignature = run => {
        const board = modeRun(run);
        return JSON.stringify([board?.sources?.[view], board?.front_source_sha256, board?.slots_by_view?.[view],
          (board?.candidates || []).filter(item => item.view === view).map(item => [item.candidate_id, item.reference_images])]);
      };
      if (sourceSignature(oldRun) !== sourceSignature(latest)) {
        previous.querySelectorAll(".local-pipeline-sources").forEach(section => section.remove());
        next.querySelectorAll(".local-pipeline-sources").forEach(section => previous.insertBefore(section, previous.querySelector(".local-pipeline-render-tools")));
      }
      const observations = previous.querySelector("textarea[data-view-observations]");
      if (observations && observations.value === (oldRun?.view_reviews?.[view]?.observations || "")) observations.value = latest.view_reviews?.[view]?.observations || "";
      const oldActions = previous.querySelector(".local-pipeline-view-actions");
      const nextActions = next.querySelector(".local-pipeline-view-actions");
      if (oldActions && nextActions && !oldActions.contains(document.activeElement)) {
        nextActions.querySelector(".local-stage-menu").open = oldActions.querySelector(".local-stage-menu").open;
        oldActions.replaceWith(nextActions);
      }
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
    setBusyControls(); updateRefreshButton();
    const modeProgress = latest.progress_by_mode?.[state.renderMode];
    $("summary").textContent = `${latest.character} · ${latest.phase}${latest.costume ? ` · ${latest.costume}` : ""} · ${state.renderMode === "final" ? "Final" : "Draft"} · ${modeProgress ? `${modeProgress.complete_count}/${modeProgress.candidate_count}` : `${latest.render_progress?.COMPLETE || 0}/${latest.candidate_count}`} images · ${statusLabels[modeProgress?.status || latest.status] || modeProgress?.status || latest.status}`;
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
    const saved = run.render_settings?.[view] || {}, settings = state.costumeSettingsDrafts[view] || saved;
    const section = document.createElement("div");
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
    const sync = () => {
      reference.disabled = view === "FRONT" || mode.value === "doll-dressing-no-ref";
      state.costumeSettingsDrafts[view] = {mode: mode.value, costume_reference_view: reference.value, revision: saved.revision};
      const changed = mode.value !== saved.mode || (view !== "FRONT" && reference.value !== (saved.costume_reference_view || ""));
      readiness.textContent = changed ? "Save these settings to check readiness for this view." : readinessText();
      save.disabled = !changed;
    };
    const save = addButton(section, "Save render settings", "save-costume-render-settings", {view});
    const readiness = document.createElement("p"); readiness.className = "action-message info";
    const readinessText = () => {
      const control = run.slot_controls?.[view] || {};
      const reason = control.mode_reasons?.[settings.mode] || control.stage_reason || control.reason || "";
      if (reason) return `${view}: ${reason}`;
      const selectedReference = settings.costume_reference_view;
      if (view !== "FRONT" && settings.mode !== "doll-dressing-no-ref" && selectedReference
          && !run.selected_views?.[selectedReference]) {
        return `${view}: Select an available, non-rejected ${selectedReference} image in this batch first.`;
      }
      if (view !== "FRONT" && settings.mode !== "doll-dressing-no-ref" && !selectedReference) {
        return `${view}: Choose a different available view as the costume reference, then save settings.`;
      }
      return `${view}: Ready for this saved mode. Retry keeps its submitted prompt and images.`;
    };
    readiness.setAttribute("role", "status"); readiness.setAttribute("aria-live", "polite");
    readiness.textContent = readinessText();
    save.disabled = settings.mode === saved.mode
      && (view === "FRONT" || settings.costume_reference_view === (saved.costume_reference_view || ""));
    mode.addEventListener("change", sync); reference.addEventListener("change", sync);
    referenceLabel.append(reference);
    section.append(modeLabel, referenceLabel);
    section.append(readiness); return section;
  }

  function renderViews(run, host = $("views")) {
    if (isCostume()) for (const controls of host.querySelectorAll(".costume-render-settings")) {
      const view = controls.querySelector("[data-render-mode]")?.dataset.renderMode;
      if (!view) continue;
      const saved = run.render_settings?.[view] || {};
      const mode = controls.querySelector("[data-render-mode]").value;
      const reference = controls.querySelector("[data-costume-reference]").value;
      if (mode !== saved.mode || (view !== "FRONT" && reference !== (saved.costume_reference_view || ""))) {
        state.costumeSettingsDrafts[view] = {mode, costume_reference_view: reference, revision: saved.revision};
      }
    }
    const previousOpen = new Map(Array.from(host.querySelectorAll("details.local-pipeline-view"), (details) => [details.dataset.view, details.open]));
    const previousObservationsOpen = new Map(Array.from(host.querySelectorAll("details.local-pipeline-observations"), (details) => [details.dataset.view, details.open]));
    const previousToolsOpen = new Map(Array.from(host.querySelectorAll("details.local-pipeline-render-tools"), (details) => [details.dataset.view, details.open]));
    const previousOverrideOpen = new Map(Array.from(host.querySelectorAll("details.local-pipeline-view"), (details) => [details.dataset.view, details.querySelector(".local-pipeline-override")?.open]));
    host.replaceChildren();
    for (const view of orderedViews(run).filter(view => !state.view || view === state.view)) {
      const candidates = (run.candidates || []).filter((candidate) => candidate.view === view);
      const slots = run.slots_by_view?.[view] || [...candidates.map(item => item.candidate_id), ...Array(Math.max(0, 8 - candidates.length)).fill(null)];
      const details = document.createElement("details");
      details.className = "local-pipeline-view";
      details.dataset.view = view;
      const selected = run.selected_views?.[view] || "";
      details.open = previousOpen.has(view) ? previousOpen.get(view) : true;
      const summary = document.createElement("summary");
      const heading = document.createElement("strong");
      heading.className = "render-mode-heading";
      heading.textContent = `${view} · ${run.selected_views?.[view] || "not selected"} · ${candidates.filter((item) => item.image_path).length}/${candidates.length} images`;
      summary.append(heading);
      const ranking = run.rankings?.[view] || {};
      const evaluation = run.evaluations?.[view] || {};
      const viewActions = document.createElement("span");
      viewActions.className = "button-row compact local-pipeline-view-actions";
      const actionTime = Boolean(run.scoped_kind);
      const viewReady = !run.slot_controls?.[view]?.stage_reason;
      const stageReason = run.slot_controls?.[view]?.stage_reason || "";
      const stageMenu = document.createElement("details"); stageMenu.className = "local-stage-menu";
      const stageLabel = document.createElement("summary"); stageLabel.textContent = "Stage…"; stageMenu.append(stageLabel);
      stageLabel.addEventListener("click", event => event.stopPropagation());
      const stageItems = document.createElement("div"); stageItems.className = "local-stage-items"; stageMenu.append(stageItems);
      addButton(stageItems, "Stage in Image Generator", "stage-image-generation", { disabled: !actionTime && Boolean(stageReason), view, title: stageReason });
      if (isCostume()) {
        const controls = run.slot_controls?.[view] || {};
        addButton(stageItems, "Stage no Costume ref", "stage-no-costume-ref", { disabled: !actionTime && Boolean(controls.no_costume_ref_reason), view,
          title: controls.no_costume_ref_reason || "Stage without a prior rendered costume view." });
        addButton(stageItems, "Stage Rotation", "stage-rotation", { disabled: !actionTime && Boolean(controls.rotation_reason), view,
          title: controls.rotation_reason || `Rotate selected ${controls.rotation_source_view} into ${view}.` });
      }
      addButton(viewActions, "Regen view", "rerun-view", { disabled: !actionTime && (!viewReady || !candidates.length), view });
      addButton(viewActions, "Re-run failed", "rerun-failed", { disabled: !actionTime && (busy(run) || Boolean(run?.slot_render_ids?.length) || !candidates.some((item) => item.render_status === "FAILED")), view });
      addButton(viewActions, "Re-evaluate", "reevaluate-view", { view });
      addButton(viewActions, "Delete Draft images", "delete-drafts", { disabled: state.bulkActionPending, view });
      viewActions.append(stageMenu);
      addButton(viewActions, "Post Render Adjustments", "post-render-adjustments", { disabled: !candidates.some((item) => item.image_path), view });
      const ai = run.view_reviews?.[view]?.ai_observations || {};
      details.append(summary);
      const override = viewOverrideInput(run, view);
      override.open = previousOverrideOpen.get(view) || false;
      details.append(override);
      const activeHeadSource = run.front_sources_by_mode?.[state.renderMode] || (state.renderMode === "draft" || !run.apply_phase_change ? {path: run.front_source, sha256: run.front_source_sha256} : {});
      if (hasSharedAssetRouter() || (["head-image", "head-image-edit"].includes(state.pipeline) && view === "FRONT" && activeHeadSource.path)) {
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
          const preview = run.source_previews_by_mode?.[state.renderMode]?.[view] || {};
          const source = preview[role] || run.sources?.[view]?.[role] || {};
          const actualMode = source.render_mode || source.origin?.render_mode || "";
          const sourceMode = actualMode === "final" ? "Final" : actualMode === "draft" ? "Draft" : "";
          caption.textContent = role.replaceAll("_", " ");
          const identity = document.createElement("span");
          identity.className = "muted";
          const candidateId = source.candidate_id || source.origin?.candidate_id || "";
          identity.textContent = candidateId ? `${sourceMode || "Uploaded"}/${candidateId}` : (source.origin?.kind === "upload" ? "Uploaded" : sourceMode);
          const image = document.createElement("img");
          image.loading = "lazy";
          image.alt = `${caption.textContent}${identity.textContent ? ` ${identity.textContent}` : ""}`;
          const version = source.sha256 || source.image_sha256 ||
            (role === "front_reference" ? activeHeadSource.sha256 : "");
          const src = role === "front_reference"
            ? `${baseUrl()}/runs/${encodeURIComponent(run.run_id)}/source-thumbnail?render_mode=${state.renderMode}`
            : (() => {
                const url = new URL(`${baseUrl()}/runs/${encodeURIComponent(run.run_id)}/source-thumbnails/${encodeURIComponent(view)}/${encodeURIComponent(role)}`, window.location.href);
                if (isCostume()) url.searchParams.set("costume", selectedCostume());
                if (["character-assembly", "costume-dressing"].includes(state.pipeline)) url.searchParams.set("render_mode", state.renderMode);
                return url.href;
              })();
          if (preview.error) {
            image.hidden = true;
            identity.textContent = preview.error;
          } else {
            image.src = versionedImageUrl(src, version);
          }
          figure.append(caption, identity, image);
          sources.append(figure);
        }
        details.append(sources);
      }
      const referenceImages = [];
      const seenReferences = new Set();
      for (const candidate of candidates) {
        if (!slots.includes(candidate.candidate_id)) continue;
        for (const [index, reference] of (candidate.reference_images || []).entries()) {
          const key = reference.sha256
            ? `sha256:${reference.sha256}`
            : `${reference.role || ""}\u0000${reference.prompt_role || ""}\u0000${reference.label || reference.tag || ""}`;
          if (reference.path && !seenReferences.has(key)) {
            seenReferences.add(key);
            referenceImages.push({reference, index, candidateId: candidate.candidate_id});
          }
        }
      }
      const renderedRoles = ["head-image", "head-image-edit"].includes(state.pipeline) && view === "FRONT" && activeHeadSource.path
        ? new Set(["head_image_source"])
        : state.pipeline === "character-assembly"
        ? new Set(["body_reference", "head_image"])
        : state.pipeline === "costume-dressing"
        ? new Set(["character_assembly"])
        : new Set();
      const remainingReferences = referenceImages
        .filter(({ reference }) => !renderedRoles.has(reference.role));
      if (remainingReferences.length) {
        const sources = document.createElement("div");
        sources.className = "local-pipeline-sources";
        for (const { reference, index, candidateId } of remainingReferences) {
          const figure = document.createElement("figure");
          const caption = document.createElement("figcaption");
          const imageIndex = reference.image_index || index + 1;
          const promptRole = reference.prompt_role || reference.role || "reference";
          const label = reference.label || reference.tag || "Reference image";
          const referenceMode = reference.render_mode === "final" ? "Final" : reference.render_mode === "draft" ? "Draft" : "";
          const referenceCandidate = reference.candidate_id || reference.source_candidate_id || "";
          const identity = referenceCandidate ? `${referenceMode || "Uploaded"}/${referenceCandidate}`
            : referenceMode || (reference.source_kind === "upload" ? "Uploaded" : "");
          caption.textContent = `Image ${imageIndex} — ${promptRole}: ${label}${identity ? ` · ${identity}` : ""}`;
          const image = document.createElement("img");
          image.loading = "lazy";
          image.alt = caption.textContent;
          image.src = versionedImageUrl(route("reference-thumbnail", run.run_id, view, String(index), candidateId), reference.sha256 || "");
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
      promptHelp.textContent = "Generate and Regenerate compile current governing masters and references. Retry uses the failed render’s saved inputs.";
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
      if (view !== "FRONT" && run.views?.includes(recipeSelect.value)) {
        const sourceView = recipeSelect.value;
        const candidateId = run.selected_views_by_mode?.[state.renderMode]?.[sourceView] || "";
        const resolved = document.createElement("p");
        resolved.className = "muted";
        resolved.textContent = candidateId
          ? `Next render reference: ${state.renderMode === "final" ? "Final" : "Draft"} ${sourceView} / ${candidateId}`
          : `Next render reference: ${state.renderMode === "final" ? "Final" : "Draft"} ${sourceView} selection needed`;
        recipeSection.append(resolved);
      }
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
      reviewProgress.className = "status-badge review local-pipeline-review-progress";
      reviewProgress.hidden = !(evaluation.evaluation_id || ranking.status);
      if (evaluation.evaluation_id || ranking.status) {
        const rankText = evaluationLabels[evaluation.ranking_status] || evaluationLabels[ranking.status] || "Ranking not queued";
        reviewProgress.textContent = `Luna ranking · ${rankText}`;
      }
      const gallery = document.createElement("div");
      gallery.className = "local-pipeline-gallery";
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
        addSlotButton(card, "Generate", "generate", view, index + 1, !run.scoped_kind && !control.can_generate, control.reason);
        if (!run.scoped_kind && !control.can_generate && control.reason) {
          const reason = document.createElement("p"); reason.className = "slot-action-reason muted";
          reason.textContent = control.reason; card.append(reason);
        }
        window.ZetImageCardUI.scan(card);
        gallery.append(card);
      };
      const lunaOrder = ["COMPLETE", "STALE"].includes(ranking.status)
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
      const countControl = window.ZetRenderSlots.countControl(control.empty_count || 0, (count, button) => void slotAction("generate", view, null, count, button), {disabled: !run.scoped_kind && !control.can_generate, reason: control.legacy ? "Legacy gallery: clear surplus candidates before adding renders." : control.reason});
      const countButton = countControl.querySelector("button");
      countButton.dataset.localSlotView = view; countButton.dataset.localSlotNumber = "add"; countButton.dataset.localSlotDisabled = String(countButton.disabled);
      const tools = document.createElement("details");
      tools.className = "local-pipeline-render-tools";
      tools.dataset.view = view;
      tools.open = previousToolsOpen.get(view) || false;
      const toolsTitle = document.createElement("summary");
      toolsTitle.textContent = "Render tools";
      tools.append(toolsTitle, viewActions, countControl);
      if (isCostume()) {
        const costumeControls = details.querySelector(".costume-render-settings");
        if (costumeControls) tools.append(costumeControls);
      } else if (recipeSection.isConnected || recipeSection.parentElement === details) tools.append(recipeSection);
      tools.append(promptHelp);
      details.insertBefore(gallery, details.children[1] || null);
      gallery.insertAdjacentElement("afterend", reviewProgress);
      details.append(tools);
      details.append(override);
      details.append(observationDetails);
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

  const phaseSourceDrafts = {};
  let phaseSourcePreviewGeneration = 0;
  async function previewModeSource() {
    const generation = ++phaseSourcePreviewGeneration, run = state.run, mode = state.renderMode;
    const host = $("mode-source-preview"), phase = $("mode-source-phase").value, pipeline = $("mode-source-pipeline").value;
    host.replaceChildren();
    if (!run || $("mode-source-kind").value !== "locked" || !phase) return;
    host.textContent = "Checking locked FRONT image…";
    try {
      const args = new URLSearchParams({character: run.character, phase, render_mode: mode});
      const result = await request(`/api/local/assets?${args}`);
      if (generation !== phaseSourcePreviewGeneration || state.run?.run_id !== run.run_id || state.renderMode !== mode) return;
      const asset = (result.assets || []).find(item => item.pipeline?.toLowerCase() === pipeline && item.view === "FRONT" && !item.qualifier);
      host.replaceChildren();
      if (asset) {
        const image = document.createElement("img"); image.style.maxWidth = "160px";
        image.alt = `${mode} ${pipeline} FRONT from ${phase}`;
        args.set("v", asset.image_sha256 || "");
        image.src = universeImageUrl(`/api/local/assets/${encodeURIComponent(asset.key)}/image?${args}`);
        host.append(image);
      } else {
        const link = document.createElement("a");
        link.href = `/?${new URLSearchParams({page: `local-${pipeline}`, character: run.character, phase, render_mode: mode})}`;
        link.textContent = `Lock ${mode} FRONT in ${phase} first`;
        host.append(link);
      }
    } catch (error) { if (generation === phaseSourcePreviewGeneration) host.textContent = error.message; }
  }
  function renderModeSource(run) {
    const panel = $("mode-source");
    panel.hidden = !run || !["head-image", "head-image-edit"].includes(state.pipeline) || !run.apply_phase_change;
    if (panel.hidden) return;
    const mode = state.renderMode;
    $("mode-source-title").textContent = `${mode === "final" ? "Final" : "Draft"} phase-change FRONT source`;
    const record = run.front_sources_by_mode?.[mode] || (mode === "draft" ? {path: run.front_source, sha256: run.front_source_sha256, origin: run.front_source_origin} : {});
    const host = $("mode-source-current");
    host.replaceChildren();
    if (record?.path) {
      const image = document.createElement("img");
      image.src = versionedImageUrl(`${baseUrl()}/runs/${encodeURIComponent(run.run_id)}/source-thumbnail?render_mode=${mode}`, record.sha256);
      image.alt = `${mode} phase-change source`;
      image.style.maxWidth = "160px";
      host.append(image, document.createTextNode(` ${record.origin?.phase || "Uploaded"} · ${window.ZetPipelineLabel(record.origin?.pipeline || "")}`));
    } else host.textContent = "No source selected for this mode.";
    const selector = $("mode-source-phase");
    const previous = selector.value;
    const key = `${state.pipeline}:${run.run_id}:${mode}`;
    if (selector.dataset.context !== key) {
      selector.replaceChildren(new Option("Choose a source phase", ""));
      for (const option of document.querySelector("#phase-select").options) {
        if (option.value && option.value !== run.phase) selector.add(new Option(option.textContent, option.value));
      }
      selector.dataset.context = key;
      selector.value = phaseSourceDrafts[key]?.phase || previous || "";
      $("mode-source-pipeline").value = phaseSourceDrafts[key]?.pipeline || "head-image-edit";
      $("mode-source-kind").value = phaseSourceDrafts[key]?.kind || "locked";
      $("mode-source-status").textContent = "";
      void previewModeSource();
    }
  }

  function render() {
    const page = document.getElementById("local-pipeline-page");
    page.dataset.renderMode = state.renderMode;
    page.dataset.pageKind = state.view ? "view" : "batch";
    const run = state.run;
    renderViewNavigation(run);
    const comparison = $("comparison-report");
    const comparisonContext = `${state.pipeline}:${run?.run_id || ""}:${state.renderMode}:${isCostume() ? selectedCostume() : ""}`;
    if (comparison.dataset.context !== comparisonContext) {
      comparison.dataset.context = comparisonContext;
      comparison.hidden = true;
      comparison.replaceChildren();
    }
    const mastersReport = $("masters-report");
    if (mastersReport.dataset.context !== comparisonContext) {
      mastersReport.dataset.context = comparisonContext;
      mastersReport.hidden = true;
      mastersReport.replaceChildren();
    }
    if (!state.view) renderModeSource(run);
    if (!state.view) window.ZetTemplateImprovement?.update(run, state.pipeline, () => loadRun(run?.run_id || ""), frontRenderControl);
    if (!run) {
      $("summary").textContent = state.runState === "unavailable" || state.runsState === "unavailable"
        ? "Unable to load this batch. Use Refresh to try again."
        : state.runState === "loading" || state.runsState === "loading"
        ? "Loading batch…"
        : "No batch selected. Check requirements and create a new batch.";
      $("rename").hidden = true;
      $("selected").replaceChildren();
      $("batch-bulk-actions").replaceChildren();
      $("selected").hidden = true;
      $("views").replaceChildren();
      state.renderedSelections = {};
      state.polledRun = null;
      updateRefreshButton();
      setBusyControls();
      return;
    }
    if (run.scoped_kind) {
      $("saved-style").textContent = `Batch style: ${run.universe_style_variant || "canonical"}`;
      const progress = run.progress_by_mode?.[state.renderMode] || {};
      $("summary").textContent = `${run.character} · ${run.phase}${run.costume ? ` · ${run.costume}` : ""} · ${state.renderMode === "final" ? "Final" : "Draft"} · ${progress.complete_count || 0}/${progress.candidate_count || 0} images · ${statusLabels[progress.status || run.status] || progress.status || run.status}`;
      if (document.activeElement !== $("batch-name")) $("batch-name").value = run.batch_name || "";
      setBusyControls();
      if (run.scoped_kind === "summary") {
        renderBatchCards(run);
        $("views").replaceChildren();
      } else {
        $("selected").hidden = true;
        $("batch-bulk-actions").replaceChildren();
        renderViews(modeRun(run));
      }
      updateRefreshButton();
      return;
    }
    const progress = run.page_summary || {};
    $("saved-style").textContent = `Batch style: ${run.universe_style_variant || "canonical"}`;
    const completed = run.render_progress?.COMPLETE ?? progress.completed_count ?? run.complete_count ?? (run.candidates || []).filter((item) => item.image_path).length;
    const phaseChangeSummary = ["head-image", "head-image-edit"].includes(state.pipeline) && run.apply_phase_change ? " · Phase change rules applied" : "";
    const modeProgress = run.progress_by_mode?.[state.renderMode];
    const modeAnchor = modeRun(run)?.front_anchor;
    $("summary").textContent = `${run.character} · ${run.phase}${run.costume ? ` · ${run.costume}` : ""}${phaseChangeSummary}${state.pipeline === "character-assembly" ? ` · Heads: ${window.ZetPipelineLabel(run.head_pipeline || "head-image")}` : ""} · ${run.run_id} · ${state.renderMode === "final" ? "Final" : "Draft"} · ${modeProgress ? `${modeProgress.complete_count}/${modeProgress.candidate_count}` : `${completed}/${run.candidate_count || (run.candidates || []).length}`} images · ${statusLabels[modeProgress?.status || run.status] || modeProgress?.status || run.status}${modeAnchor ? ` · FRONT ${modeAnchor}` : ""}${progress.stale_selections?.length ? ` · stale selections ${progress.stale_selections.join(", ")}` : ""}`;
    if (document.activeElement !== $("batch-name")) $("batch-name").value = run.batch_name || "";
    setBusyControls();
    if (state.view) {
      $("selected").hidden = true;
      $("batch-bulk-actions").replaceChildren();
      renderViews(modeRun(run));
    } else {
      renderSelectedViews(modeRun(run));
      $("views").replaceChildren();
    }
    updateRefreshButton();
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
    if (!runId) { state.run = null; state.costumeSettingsDrafts = {}; render(); return; }
    try {
      const loaded = await readScopedRun(runId);
      if (requestId !== state.runRequest || generation !== state.generation || contextKey() !== state.contextKey) return;
      const sameRun = state.run?.run_id === loaded.run_id;
      if (!sameRun) {
        state.awaitingSettle = false;
        document.querySelectorAll('[data-submission-status]').forEach((message) => { message.textContent = ""; });
        $("proceed").removeAttribute("aria-busy");
      }
      if (sameRun) mergeLiveRun(loaded); else { state.run = loaded; state.costumeSettingsDrafts = {}; setStatus(""); }
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
      if (!state.run) render();
      throw error;
    }
  }

  function syncRunOption(run) {
    const option = [...$("runs").options].find(item => item.value === run.run_id);
    if (!option) return;
    const summary = state.runs.find(item => item.run_id === run.run_id) || {};
    const modeStatus = run.progress_by_mode?.[state.renderMode]?.status || run.status;
    const label = statusLabels[modeStatus] || modeStatus;
    const phaseChangeLabel = ["head-image", "head-image-edit"].includes(state.pipeline) && run.apply_phase_change ? " · Phase change rules" : "";
    option.textContent = `${summary.batch_name || run.batch_name || run.run_id} · ${label}${phaseChangeLabel} · ${run.run_id}`;
  }

  async function pollForImages(runId, generation = state.generation) {
    if (state.pollInFlight || !state.run || state.run.run_id !== runId) return;
    state.pollInFlight = true;
    const requestId = state.runRequest;
    try {
      const suffix = query({render_mode: state.renderMode});
      const summary = normalizeScoped(await request(`${baseUrl()}/runs/${encodeURIComponent(runId)}/summary${suffix}`));
      if (requestId !== state.runRequest || generation !== state.generation || state.run?.run_id !== runId) return;
      if (contextKey() !== state.contextKey || !document.querySelector("#local-pipeline-page").classList.contains("active")) return;
      const operationActive = (window.ZetLocalOperations?.rows() || []).some(row => row.request?.run_id === runId
        && row.request?.pipeline === state.pipeline && ["SUBMITTING", "QUEUED", "PREPARING", "WAITING", "UNKNOWN"].includes(row.status));
      const active = activeStatuses.has(summary.status) || summary.slot_render_ids?.length
        || summary.progress_by_mode?.[state.renderMode]?.current_views?.length || operationActive;
      if (state.view && active) {
        state.awaitingSettle = true;
        state.run.progress_by_mode = summary.progress_by_mode;
        state.run.status = summary.status;
        syncRunOption(state.run);
        return;
      }
      const latest = state.view ? await readScopedRun(runId) : summary;
      if (requestId !== state.runRequest || generation !== state.generation || state.run?.run_id !== runId) return;
      state.awaitingSettle = false;
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
      const modeStatus = run.progress_by_mode?.[state.renderMode]?.status || run.status;
      select.add(new Option(`${run.batch_name || run.run_id} · ${statusLabels[modeStatus] || modeStatus}${phaseChangeLabel} · ${run.run_id}`, run.run_id));
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

  let readinessTimer = null;
  function scheduleReadiness() {
    clearTimeout(readinessTimer);
    readinessTimer = setTimeout(() => void readiness(), 250);
  }

  async function readiness() {
    const generation = ++state.previewGeneration;
    if (lockedPhaseSourceSelected()) void refreshLockedPhaseSource();
    $("readiness").textContent = "Checking required inputs…";
    try {
      const result = await request(route("preview"), { method: "POST", body: JSON.stringify(payload()) });
      if (generation !== state.previewGeneration) return;
      const blockers = result.blocking_reasons || [];
      renderSourceBatchOptions(result);
      const canCreate = result.can_create !== false && blockers.length === 0;
      $("readiness").textContent = blockers.length ? blockers.map(window.ZetPipelineMessage).join(" · ")
        : `${result.candidate_count || ""} candidates across ${(result.views || []).length} views. ${canCreate ? "Ready to create." : "Resolve requirements first."}`;
    } catch (error) {
      if (generation !== state.previewGeneration) return;
      $("readiness").textContent = window.ZetPipelineMessage(error.message);
      // Create runs the authoritative check on click; preview is only guidance.
    }
  }

  async function refreshContext() {
    clearTimeout(readinessTimer);
    state.generation += 1;
    document.querySelectorAll('[data-submission-status]').forEach((message) => { message.textContent = ""; });
    $("proceed").removeAttribute("aria-busy");
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
    render();
    try {
      await loadCostumes();
      if (generation !== state.generation) return;
      state.contextKey = contextKey();
      await Promise.all([refreshRuns("", generation), $("options").open ? readiness() : Promise.resolve()]);
    } catch (error) {
      if (generation !== state.generation) return;
      state.runState = "unavailable";
      render();
      setStatus(error.message, true);
    }
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
      const run = state.run;
      const activeEvaluation = Object.values(run?.evaluations || {}).some(item => ["STAGING", "RUNNING"].includes(item.status))
        || Object.values(run?.final_evaluations || {}).some(item => ["STAGING", "RUNNING"].includes(item.status));
      const pendingOperation = (window.ZetLocalOperations?.rows() || []).some(row => row.request?.run_id === run?.run_id
        && row.request?.pipeline === state.pipeline && ["SUBMITTING", "QUEUED", "PREPARING", "WAITING", "UNKNOWN"].includes(row.status));
      if (!document.hidden && state.pipeline && document.querySelector("#local-pipeline-page").classList.contains("active")
        && run?.run_id && (activeStatuses.has(run.status) || run.slot_render_ids?.length || activeEvaluation || pendingOperation || state.awaitingSettle)) {
        void pollForImages(run.run_id, state.generation);
      }
    }, 3000);
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && state.pipeline && document.querySelector("#local-pipeline-page")?.classList.contains("active") && state.run?.run_id) {
      void pollForImages(state.run.run_id, state.generation);
    }
  });

  function configurePipeline(pipeline) {
    state.pipeline = pipeline;
    state.awaitingSettle = false;
    state.renderMode = new URLSearchParams(window.location.search).get("render_mode") === "final" ? "final" : "draft";
    state.view = (new URLSearchParams(window.location.search).get("local_view") || "").toUpperCase();
    $("render-quality").value = state.renderMode;
    $("aspect-ratio").value = ["head-image", "head-image-edit"].includes(pipeline) ? "1:1" : "2:3";
    void updateSizePreview();
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
      "body-reference": "Body-Reference", "head-image": "Head-Image (Construct)", "head-image-edit": "Head-Image (Edit)",
      "character-assembly": "Character-Assembly", "costume-dressing": "Costume-Dressing",
    }[pipeline];
    $("costume-label").hidden = !isCostume();
    $("anchor-option").hidden = state.pipeline === "character-assembly" || !hasSharedAssetRouter();
    $("source-batches").hidden = !hasSharedAssetRouter();
    $("head-pipeline-label").hidden = pipeline !== "character-assembly";
    $("head-pipeline").value = "head-image";
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
    if (action === "proceed") {
      const frontSelected = Boolean(modeRun(state.run)?.selected_views?.FRONT);
      action = "run-available";
      body = {render_mode: state.renderMode, aspect_ratio: $("aspect-ratio").value,
        scope: frontSelected ? "available" : "front"};
    }
    if (["select", "unselect", "lock", "unlock", "move-rank"].includes(action)) body = {...(body || {}), render_mode: state.renderMode};
    const runId = state.run?.run_id || "";
    const generation = state.generation;
    const pipeline = state.pipeline;
    const context = contextKey();
    const requestId = ++state.runRequest;
    const method = action === "rename"
      ? "PUT" : action === "delete" ? "DELETE" : "POST";
    if (["start", "resume"].includes(action) && window.ZetLocalOperations) {
      const expected = state.run?.operation_contexts?.[state.renderMode]?.batch;
      if (!expected) throw new Error("Batch inputs are still loading. Refresh before submitting.");
      const result = await window.ZetLocalOperations.submit({universe_id: document.querySelector("#universe-select").value,
        pipeline, run_id: runId, character: state.run.character || "", phase: state.run.phase || "",
        batch_name: state.run.batch_name || "", costume: isCostume() ? selectedCostume() : "",
        action, render_mode: state.renderMode, expected_context: expected});
      if (generation === state.generation && context === contextKey() && state.run?.run_id === runId) setStatus("Action queued — you can continue elsewhere.");
      return result;
    }
    if (action === "run-available" && window.ZetLocalOperations) {
      const expected = body.scope === "front" ? state.run?.operation_contexts?.[state.renderMode]?.views?.FRONT : state.run?.operation_contexts?.[state.renderMode]?.batch;
      if (!expected) throw new Error("Batch inputs are still loading. Refresh before submitting.");
      const result = await window.ZetLocalOperations.submit({universe_id: document.querySelector("#universe-select").value,
        pipeline, run_id: runId, character: state.run.character || "", phase: state.run.phase || "",
        batch_name: state.run.batch_name || "", costume: isCostume() ? selectedCostume() : "",
        action: "run_available", render_mode: state.renderMode, aspect_ratio: body.aspect_ratio,
        scope: body.scope, expected_context: expected});
      if (generation === state.generation && context === contextKey() && state.run?.run_id === runId) setStatus("Action queued — you can continue elsewhere.");
      return result;
    }
    if (["rerun-view", "rerun-failed"].includes(action) && window.ZetLocalOperations) {
      const expected = state.run?.operation_contexts?.[state.renderMode]?.views?.[view];
      if (!expected) throw new Error("Batch inputs are still loading. Refresh before submitting.");
      const result = await window.ZetLocalOperations.submit({universe_id: document.querySelector("#universe-select").value,
        pipeline, run_id: runId, character: state.run.character || "", phase: state.run.phase || "",
        batch_name: state.run.batch_name || "", costume: isCostume() ? selectedCostume() : "",
        action: action === "rerun-view" ? "rerun_view" : "rerun_failed", render_mode: state.renderMode,
        view, aspect_ratio: $("aspect-ratio").value, recompile: Boolean(body?.recompile), expected_context: expected});
      if (generation === state.generation && context === contextKey() && state.run?.run_id === runId) setStatus("Action queued — you can continue elsewhere.");
      return result;
    }
    if (["reevaluate", "reevaluate-view"].includes(action) && window.ZetLocalOperations) {
      const contexts = state.run?.operation_contexts?.[state.renderMode]?.evaluation;
      const expected = view ? contexts?.views?.[view] : contexts?.batch;
      if (!expected) throw new Error("Evaluation inputs are still loading. Refresh before submitting.");
      const result = await window.ZetLocalOperations.submit({universe_id: document.querySelector("#universe-select").value,
        pipeline, run_id: runId, character: state.run.character || "", phase: state.run.phase || "",
        batch_name: state.run.batch_name || "", costume: isCostume() ? selectedCostume() : "",
        action: "reevaluate", render_mode: state.renderMode, ...(view ? {view} : {}), expected_context: expected});
      if (generation === state.generation && context === contextKey() && state.run?.run_id === runId) setStatus("Action queued — you can continue elsewhere.");
      return result;
    }
    if (action === "retry" && window.ZetLocalOperations) {
      const candidate = (state.run?.candidates || []).find(item => item.candidate_id === candidateId);
      const expected = state.run?.operation_contexts?.[state.renderMode]?.candidate_retry?.[candidateId];
      if (!candidate || candidate.view !== view || !expected) throw new Error("Candidate inputs changed. Refresh before submitting.");
      const result = await window.ZetLocalOperations.submit({universe_id: document.querySelector("#universe-select").value,
        pipeline, run_id: runId, character: state.run.character || "", phase: state.run.phase || "",
        batch_name: state.run.batch_name || "", costume: isCostume() ? selectedCostume() : "",
        action: "retry_candidate", render_mode: state.renderMode, view, candidate_id: candidateId,
        expected_context: expected});
      if (generation === state.generation && context === contextKey() && state.run?.run_id === runId) setStatus("Action queued — you can continue elsewhere.");
      return result;
    }
    let path;
    if (action === "reevaluate-view") path = `${baseUrl()}/runs/${encodeURIComponent(state.run.run_id)}/reevaluate${query({ view, render_mode: state.renderMode })}`;
    else path = route(action, state.run?.run_id, view, candidateId);
    if (state.run?.scoped_kind && ["review", "select", "unselect", "move-rank", "lock", "unlock", "rename"].includes(action))
      path += `${path.includes("?") ? "&" : "?"}compact=true`;
    const result = await request(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });
    if (requestId !== state.runRequest || generation !== state.generation || pipeline !== state.pipeline ||
        context !== contextKey() || (runId && state.run?.run_id !== runId)) return result;
    if (action === "delete") {
      state.run = null;
      await refreshRuns();
      setStatus("Batch deleted.");
      return;
    }
    if (action === "run-available") {
      const errors = Object.entries(result.errors || {}), blocked = Object.entries(result.blocked_views || {});
      setStatus(`${(result.submitted_candidate_ids || []).length} render(s) queued.${blocked.length ? ` Waiting: ${blocked.map(([view, reason]) => `${view}: ${reason}`).join(" · ")}` : ""}${errors.length ? ` Failed: ${errors.map(([view, reason]) => `${view}: ${reason}`).join(" · ")}` : ""}`, errors.length > 0);
    } else if (action === "resume" && result.status !== "QUEUED") {
      setStatus("Batch ready to continue.");
    } else if (["rerun", "rerun-view", "rerun-failed"].includes(action) && result?.submitted_candidate_ids) {
      const failures = Object.entries(result.errors || {});
      setStatus(`${result.submitted_candidate_ids.length} render(s) queued.${failures.length ? ` Failed: ${failures.map(([id, error]) => `${id}: ${error}`).join(" · ")}` : ""}`, failures.length > 0);
    } else if (["start", "resume", "stop", "retry", "rerun", "rerun-view", "rerun-failed", "reevaluate", "reevaluate-view"].includes(action)) {
      setStatus(action === "stop" && result.slot_paused ? "Batch paused. Already submitted renders may continue; their results will be collected after resuming." : action === "stop" ? "Stop requested." : "Work queued.");
    } else if (action === "lock" || action === "unlock" || action === "select" || action === "unselect") {
      setStatus("Selection updated.");
    }
    if (!state.run?.scoped_kind && ["review", "select", "unselect", "move-rank"].includes(action) && result?.run_id) {
      mergeLiveRun(result);
    } else await loadRun(state.run?.run_id);
  }

  function sortCandidatesByDisplayOrder(run, view, candidates, candidateId = item => item.candidate_id, slotNumber = item => item.slot || item.ordinal || 0) {
    const ranking = run.rankings?.[view] || {};
    const lunaOrder = ["COMPLETE", "STALE"].includes(ranking.status)
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
    const run = modeRun(state.run);
    const views = orderedViews(run);
    if (state.reviewBatchCards) return views.map(view => {
      const card = (state.run.selected_cards || []).find(item => item.view === view && item.display_kind);
      if (!card) return null;
      const locked = card.display_kind === "locked";
      const imageUrlForReview = locked
        ? universeImageUrl(`/api/local/assets/${encodeURIComponent(card.locked_key)}/image?${new URLSearchParams({character: state.run.character, phase: state.run.phase})}`)
        : imageUrl({candidate_id: card.display_candidate_id, image_sha256: card.display_image_sha256}, true);
      return {candidate_id: `${card.display_kind}:${card.view}:${card.display_candidate_id}`, view,
        image_path: imageUrlForReview, review_image_url: versionedImageUrl(imageUrlForReview, card.display_image_sha256),
        review_card: card, render_mode: state.renderMode};
    }).filter(Boolean);
    if (state.reviewSelectedOnly) return views.map(view =>
      (run?.candidates || []).find(item => item.view === view && item.candidate_id === run.selected_views?.[view] && item.image_path)
    ).filter(Boolean);
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
    if (state.reviewSelectedOnly) {
      const next = state.reviewIndex + direction;
      if (next >= 0 && next < state.reviewCandidates.length) { state.reviewIndex = next; renderReview(); }
      return;
    }
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

  const failedComparisons = new Set();
  function refreshComparison() {
    const decision = $("review-panel").querySelector('input[name="local-human-decision"]:checked')?.value;
    renderReview();
    if (decision) {
      const radio = $("review-panel").querySelector(`input[name="local-human-decision"][value="${decision}"]`);
      if (radio) radio.checked = true;
    }
  }
  function renderReview() {
    const candidate = state.reviewCandidates[state.reviewIndex];
    if (!candidate) return;
    const run = modeRun(state.run);
    const oppositeViews = {
      LEFT_PROFILE: "RIGHT_PROFILE", RIGHT_PROFILE: "LEFT_PROFILE",
      FRONT_LEFT_3_4: "FRONT_RIGHT_3_4", FRONT_RIGHT_3_4: "FRONT_LEFT_3_4",
      BACK_LEFT_3_4: "BACK_RIGHT_3_4", BACK_RIGHT_3_4: "BACK_LEFT_3_4",
    };
    const oppositeView = oppositeViews[candidate.view];
    const selectedViews = run.selected_views || {};
    const candidates = run.candidates || [];
    const compareIdentity = (view) => state.run.selected_comparison_images?.[view];
    const frontId = run.front_anchor || selectedViews.FRONT;
    const front = candidates.find((item) => item.candidate_id === frontId && item.view === "FRONT" && item.image_path);
    const frontSummary = compareIdentity("FRONT");
    const oppositeId = oppositeView && selectedViews[oppositeView];
    const opposite = oppositeId && candidates.find((item) => item.candidate_id === oppositeId && item.view === oppositeView && item.image_path);
    const oppositeSummary = oppositeView && compareIdentity(oppositeView);
    const draft = state.run.locked_draft_comparisons?.[candidate.view];
    const options = [];
    if (front && front.candidate_id !== candidate.candidate_id) options.push({id: "front", label: "Selected FRONT", src: imageUrl(front, true)});
    else if (frontSummary && frontSummary.candidate_id !== candidate.candidate_id) options.push({id: "front", label: "Selected FRONT", src: versionedImageUrl(route("image", state.run.run_id, "", frontSummary.candidate_id), frontSummary.image_sha256)});
    if (opposite) options.push({id: "opposite", label: `Selected ${oppositeView}`, src: imageUrl(opposite, true)});
    else if (oppositeSummary) options.push({id: "opposite", label: `Selected ${oppositeView}`, src: versionedImageUrl(route("image", state.run.run_id, "", oppositeSummary.candidate_id), oppositeSummary.image_sha256)});
    if (draft) {
      const params = new URLSearchParams({character: state.run.character, phase: state.run.phase, v: draft.image_sha256 || ""});
      options.push({id: "draft", label: `Locked Draft · ${candidate.view}`, src: universeImageUrl(`/api/local/assets/${encodeURIComponent(draft.key)}/image?${params}`)});
    }
    const toggle = $("review-toggle");
    const available = options.filter(item => !failedComparisons.has(item.src));
    const comparison = available.find(item => item.id === state.comparisonChoice) || available[0];
    state.comparisonChoice = comparison?.id || "front";
    toggle.replaceChildren(...available.map(item => new Option(item.label, item.id)));
    toggle.value = state.comparisonChoice;
    $("review-toggle-label").hidden = available.length < 2;
    $("review-compare-title").textContent = comparison?.label || "Comparison";
    const compareImage = $("review-compare-image");
    if (comparison) {
      compareImage.onerror = () => { failedComparisons.add(comparison.src); refreshComparison(); };
      compareImage.src = comparison.src;
      compareImage.alt = comparison.label;
      compareImage.hidden = false;
    } else { compareImage.removeAttribute("src"); compareImage.hidden = true; }
    $("review-compare-empty").hidden = true;
    compareImage.closest("figure").hidden = !comparison;
    compareImage.closest(".local-pipeline-review-comparison").classList.toggle("single-image", !comparison);
    const reviewImage = $("review-image");
    reviewImage.hidden = !candidate.image_path;
    if (candidate.image_path) reviewImage.src = candidate.review_image_url || imageUrl(candidate, true);
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
    if (state.reviewSelectedOnly) {
      compareImage.closest("figure").hidden = true;
      compareImage.closest(".local-pipeline-review-comparison").classList.add("single-image");
      panel.replaceChildren();
      const heading = document.createElement("h2");
      heading.textContent = `${candidate.view} · ${state.reviewIndex + 1} of ${state.reviewCandidates.length}`;
      const lock = candidate.review_card?.locked || candidate.review_card?.display_kind === "locked"
        || Object.values(run.local_assets || {}).some(item => item.locked && item.batch_id === run.run_id && item.candidate_id === candidate.candidate_id);
      const status = document.createElement("p");
      status.textContent = lock ? "Locked" : "Selected";
      panel.append(heading, status);
      $("review-prev").disabled = state.reviewIndex <= 0;
      $("review-next").disabled = state.reviewIndex >= state.reviewCandidates.length - 1;
      $("review-prev-view").hidden = true;
      $("review-next-view").hidden = true;
      return;
    }
    $("review-prev-view").hidden = false;
    $("review-next-view").hidden = false;
    const previousCandidate = panel.dataset.candidate;
    const previousDetails = panel.querySelector(".local-pipeline-review-details");
    const detailsOpen = previousDetails?.open || false;
    const detailsScroll = previousDetails?.scrollTop || 0;
    const qualityScroll = panel.querySelector(".local-pipeline-review-quality")?.scrollTop || 0;
    panel.dataset.candidate = candidate.candidate_id;
    panel.replaceChildren();
    const title = document.createElement("h2");
    title.textContent = candidate.candidate_id;
    const modeLabel = candidateModeLabel(candidate, candidate.image_path ? reviewImage : null);
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
        : rankingPosition >= 0 ? `Luna rank #${rankingPosition + 1}${rankEntry?.reason ? ` · ${rankEntry.reason}` : ""}`
          : `Luna ranking · ${evaluationLabels[run.evaluations?.[candidate.view]?.ranking_status] || evaluationLabels[ranking.status] || evaluationLabels[run.evaluations?.[candidate.view]?.status] || "Ranking not queued. Use Re-evaluate for this view."}`;
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
    const reviewCount = window.ZetRenderSlots.countControl(control.empty_count || 0, (count, button) => void slotAction("generate", candidate.view, null, count, button), {disabled: !state.run?.scoped_kind && !control.can_generate, reason: control.reason});
    const reviewCountButton = reviewCount.querySelector("button");
    reviewCountButton.dataset.localSlotView = candidate.view; reviewCountButton.dataset.localSlotNumber = "add"; reviewCountButton.dataset.localSlotDisabled = String(reviewCountButton.disabled);
    moreActions.append(reviewCount);
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
    panel.append(title, modeLabel, view);
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
  function openReview(candidateId, selectedOnly = false) {
    state.reviewBatchCards = typeof candidateId === "string" && state.run?.scoped_kind === "summary";
    state.reviewSelectedOnly = selectedOnly;
    state.reviewCandidates = orderedReviewCandidates();
    state.reviewIndex = state.reviewCandidates.findIndex((item) => state.reviewBatchCards ? item.view === candidateId : item.candidate_id === candidateId);
    if (state.reviewIndex < 0) return;
    state.comparisonChoice = "front";
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
      const runId = state.run.run_id, pipeline = state.pipeline, context = contextKey(), generation = state.generation, mode = state.renderMode;
      const current = () => state.run?.run_id === runId && state.pipeline === pipeline
        && contextKey() === context && state.generation === generation && state.renderMode === mode;
      state.bulkActionPending = true;
      if (action === "lock-all") setStatus("Checking selected views for publication…");
      renderSelectedViews(modeRun(state.run));
      try {
        let body = {render_mode: state.renderMode};
        let summary = `Unlock this batch's ${state.renderMode} images? Published Inventory images will be retained.`;
        if (action === "lock-all") {
          const previewUrl = new URL(route("lock-all-preview", runId), location.origin);
          previewUrl.searchParams.set("render_mode", state.renderMode);
          const plan = await request(previewUrl.pathname + previewUrl.search);
          if (!current()) return;
          if (!plan.views.length) { setStatus("All selected images are already locked."); return; }
          body = {render_mode: state.renderMode, selected_views: plan.selected_views};
          summary = `Lock all ${plan.views.length} selected ${state.renderMode} images in this batch?\n\n${plan.views.join(", ")}`;
        }
        const confirmed = await confirmAction(action === "lock-all" ? "Lock selected images" : "Unlock pipeline images",
          summary, action === "lock-all" ? "Lock all" : "Unlock all");
        if (!confirmed || !current()) {
          if (!confirmed && current()) setStatus("No changes made.");
          return;
        }
        setStatus(action === "lock-all" ? "Publishing selected views…" : "Unlocking selected views…");
        const result = await request(route(action, runId), { method: "POST", body: body ? JSON.stringify(body) : undefined });
        if (!current()) return;
        await loadRun(runId);
        if (!current()) return;
        const failures = Object.entries(result.errors || {});
        setStatus(`${result.completed_views.length} image(s) ${action === "lock-all" ? "locked" : "unlocked"}.${failures.length ? ` Failed: ${failures.map(([view, error]) => `${view}: ${error}`).join(" · ")}` : ""}`, failures.length > 0);
      } finally {
        state.bulkActionPending = false;
        if (state.run) renderSelectedViews(modeRun(state.run));
      }
      return;
    }
    if (action === "delete-drafts") {
      const scope = view ? `${view} in this batch` : "this batch";
      const body = view ? {view} : {};
      const previewUrl = new URL(route(action, state.run.run_id, view), location.origin);
      previewUrl.pathname += "/preview";
      const preview = await request(previewUrl.pathname + previewUrl.search, {method: "POST", body: JSON.stringify(body)});
      const approved = await confirmProtectedEffects("Delete Draft images?",
        `Delete Draft images for ${scope}? Matching work will be cancelled. Final images and Inventory copies remain. Approve each affected selection or lock.`,
        preview.protected_effects || [], "Delete Draft images");
      if (approved === null) return;
      await perform(action, view, "", {...body, confirmation_token: preview.confirmation_token, approved_effects: approved});
      setStatus("Draft images deleted.");
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
          { method: "POST", body: JSON.stringify({ view, render_mode: state.renderMode }) });
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
      const runId = state.run.run_id, pipeline = state.pipeline, context = contextKey(), generation = state.generation, renderMode = state.renderMode;
      const params = new URLSearchParams();
      if (isCostume()) params.set("costume", selectedCostume());
      const recompile = true;
      const current = () => state.pipeline === pipeline && state.run?.run_id === runId
        && state.generation === generation && contextKey() === context && state.renderMode === renderMode
        && document.querySelector("#local-pipeline-page").classList.contains("active");
      button.disabled = true;
      try {
        await window.zetStageCharacterViewInImageGenerator(
          `${baseUrl()}/runs/${encodeURIComponent(runId)}/views/${encodeURIComponent(view)}/image-generation-stage?${params}`,
          recompile, current, rotation, noCostumeRef, renderMode);
      } finally { button.disabled = !state.run?.scoped_kind && Boolean(state.run?.slot_controls?.[view]?.[
        rotation ? "rotation_reason" : noCostumeRef ? "no_costume_ref_reason" : "stage_reason"]); }
      return;
    }
    if (action === "save-costume-render-settings") {
      const controls = button.closest(".costume-render-settings");
      const settings = state.run.render_settings[view];
      const params = new URLSearchParams({costume: selectedCostume(), compact: "true"});
      button.disabled = true;
      try {
        await request(`${baseUrl()}/runs/${encodeURIComponent(state.run.run_id)}/views/${encodeURIComponent(view)}/render-settings?${params}`,
          {method: "PUT", body: JSON.stringify({mode: controls.querySelector("[data-render-mode]").value,
            costume_reference_view: controls.querySelector("[data-costume-reference]").value, expected_revision: settings.revision})});
        await loadRun(state.run.run_id); delete state.costumeSettingsDrafts[view]; setStatus("Rendering settings saved for future renders. Retry keeps its frozen inputs.");
      } finally { button.disabled = false; }
      return;
    }
    if (action === "save-view-reference") {
      const value = button.closest(".local-pipeline-reference-recipe").querySelector("select").value;
      const params = isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}&compact=true` : "?compact=true";
      await request(`${baseUrl()}/runs/${encodeURIComponent(state.run.run_id)}/views/${encodeURIComponent(view)}/reference-recipe${params}`,
        { method: "PUT", body: JSON.stringify({ mode: ["default", "none"].includes(value) ? value : "selected_view", source_view: value, render_mode: state.renderMode }) });
      if (view === "BACK" && state.run.character_progression) $("back-reference").value = value;
      await loadRun(state.run.run_id); setStatus("Reference saved for new individual renders."); return;
    }
    if (action === "save-observations") {
      const observations = $("views").querySelector(`textarea[data-view-observations="${view}"]`)?.value || "";
      const path = route("observations", state.run.run_id, view);
      await request(`${path}${path.includes("?") ? "&" : "?"}compact=true`, { method: "PUT", body: JSON.stringify({ observations }) });
      await loadRun(state.run.run_id);
      setStatus("Observations saved.");
      return;
    }
    if (action === "run-observations") {
      const path = route("reanalyze", state.run.run_id, view);
      await request(`${path}${path.includes("?") ? "&" : "?"}compact=true`, { method: "POST" });
      await loadRun(state.run.run_id);
      setStatus(`AI Observations started for ${view}.`);
      return;
    }
    if (action === "lock") {
      if (!(await confirmAction(`Lock ${view} image?`, `Lock the selected ${state.renderMode} ${view} image?`, "Lock image"))) return;
      await perform("lock", view, candidateId);
      return;
    }
    if (action === "rerun" || action === "rerun-view") {
      const recompile = true;
      if (action === "rerun-view") {
        if (!$("aspect-ratio").reportValidity()) return;
        const activeCount = (state.run?.candidates || []).filter(item => item.view === view
          && item.render_mode === state.renderMode && ["QUEUED", "RUNNING"].includes(item.render_status)).length;
        const description = `${regenDescription(state.run, view)}${activeCount
          ? `\n\n${activeCount} active render(s) in this view will be cancelled and allowed to settle before replacements start. Selected and locked images will be preserved.` : ""}`;
        if (!(await confirmAction(`Regenerate ${view}?`, description, "Regenerate", {tone: "primary"}))) return;
        await submitViewAction(button, action, view, candidateId, {render_mode: state.renderMode, aspect_ratio: $("aspect-ratio").value, recompile});
        return;
      }
      const runId = state.run.run_id, mode = state.renderMode, generation = state.generation, context = contextKey(), pipeline = state.pipeline;
      const current = () => state.run?.run_id === runId && state.renderMode === mode && state.generation === generation && contextKey() === context && state.pipeline === pipeline;
      const body = {render_mode: mode, recompile};
      state.restartPending = true;
      $("rerun").disabled = true;
      try {
        const preview = await request(route("restart-preview", runId), {method: "POST", body: JSON.stringify(body)});
        if (!current()) return;
        if (preview.issues?.length) { setStatus(preview.issues.join(" "), true); return; }
        const description = `Clear ${preview.candidate_count} ${mode} candidates, including ${preview.image_count} images? The batch will be ready to run; no renders will start. Approve each affected selection or lock.`;
        const approved = await confirmProtectedEffects(`Re-start ${mode} batch?`, description,
          preview.protected_effects || [], "Re-start batch");
        if (approved === null || !current()) return;
        await request(route("restart", runId), {method: "POST", body: JSON.stringify({...body, approved_effects: approved, confirmation_token: preview.confirmation_token})});
        if (current()) { await loadRun(runId, generation); setStatus(`${mode === "final" ? "Final" : "Draft"} batch ready to run.`); }
      } finally { state.restartPending = false; setBusyControls(); }
      return;
    }
    if (action === "delete") {
      const previewUrl = new URL(route("delete", state.run.run_id), location.origin);
      previewUrl.pathname += "/delete-preview";
      const inspection = await request(previewUrl.pathname + previewUrl.search, {method: "POST"});
      const approved = await confirmProtectedEffects("Delete batch?",
        "Delete this batch and its run-owned files? Locked copies in Inventory remain. Approve each affected selection or lock.",
        inspection.protected_effects || [], "Delete batch");
      if (approved === null) return;
      await perform("delete", "", "", {confirmation_token: inspection.confirmation_token,
        approved_effects: approved});
      return;
    }
    if (["rerun-failed", "unselect", "unlock"].includes(action)) {
      const prompts = {
        delete: "Delete this batch and its run-owned files?", rerun: "Re-run the batch? This replaces generated images and reviews.",
        "rerun-view": `Replace all ${view} candidates?`, "rerun-failed": `Re-run failed ${view} candidates?`,
        unselect: `Unselect ${view}?`, unlock: `Unlock the local ${view} asset?`,
      };
      const titles = { delete: "Delete batch?", unselect: `Unselect ${view}?`, unlock: `Unlock ${view}?` };
      const labels = { delete: "Delete batch", unselect: "Unselect", unlock: "Unlock" };
      if (!(await confirmAction(titles[action] || "Confirm action", prompts[action], labels[action] || "Confirm"))) return;
    }
    if (action === "rerun-failed" || action === "reevaluate-view" || action === "retry") {
      await submitViewAction(button, action, view, candidateId, {render_mode: state.renderMode});
      return;
    }
    if (action === "rank-up" || action === "rank-down") {
      const ordered = modeRun(state.run).rankings?.[view]?.ordered_candidate_ids || [];
      const position = ordered.indexOf(candidateId);
      if (position < 0) return;
      await perform("move-rank", view, candidateId, { candidate_id: candidateId, direction: action === "rank-up" ? "up" : "down" });
      return;
    }
    await perform(action, view, candidateId, action === "rename" ? { batch_name: $("batch-name").value } : action === "select" || action === "unselect" ? { candidate_id: action === "unselect" ? "" : candidateId } : action === "rerun-failed" ? {render_mode: state.renderMode} : undefined);
  }

  function bind() {
    $("back-reference").addEventListener("change", () => {
      if (!state.run) return;
      const runId = state.run.run_id, source = $("back-reference").value, mode = state.renderMode, generation = state.generation;
      void request(`${baseUrl()}/runs/${encodeURIComponent(runId)}/views/BACK/reference-recipe`,
        {method: "PUT", body: JSON.stringify({mode: "selected_view", source_view: source, render_mode: mode})})
        .then(() => { if (generation === state.generation && mode === state.renderMode && state.run?.run_id === runId) return loadRun(runId, generation); })
        .catch(error => setStatus(error.message, true));
    });
    $("render-quality").addEventListener("change", () => {
      setStatus("");
      state.renderMode = $("render-quality").value;
      state.generation += 1;
      state.runRequest += 1;
      state.renderedSelections = {};
      for (const run of state.runs) syncRunOption(run);
      if (state.run) syncRunOption(state.run);
      syncPipelineRoute();
      void updateSizePreview();
      if (state.run?.run_id) void loadRun(state.run.run_id, state.generation).catch(error => setStatus(error.message, true));
      else render();
    });
    $("aspect-ratio").addEventListener("input", () => void updateSizePreview());
    $("refresh").addEventListener("click", () => {
      if (state.polledRun && state.polledRun.run_id === state.run?.run_id) {
        state.run = state.polledRun;
        state.polledRun = null;
        render();
        setStatus("Batch updates loaded.");
        return;
      }
      void Promise.all([refreshRuns(), $("options").open ? readiness() : Promise.resolve()]).catch((error) => setStatus(error.message, true));
    });
    $("preview").addEventListener("click", () => void readiness());
    $("open-create").addEventListener("click", () => {
      $("create-status").textContent = "";
      $("options").showModal();
      void readiness();
    });
    $("cancel-create").addEventListener("click", () => $("options").close());
    $("options").addEventListener("close", () => $("open-create").focus());
    $("create").addEventListener("click", async () => {
      $("create").disabled = true;
      $("create-status").textContent = "Creating batch…";
      try {
        const created = await request(route("create"), { method: "POST", body: JSON.stringify(payload()) });
        $("options").close();
        $("create-name").value = "";
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
        if (hasSharedAssetRouter() && $("options").open) void readiness();
        setStatus(state.pipeline === "character-assembly" ? "Batch created. Run front, select a FRONT image, then Run remaining. Luna will compare proportions and identity with your selected FRONT." : "Batch created. Analyze and accept its governing prompts, then Continue to generate FRONT.");
      } catch (error) { $("create-status").textContent = error.message; await readiness(); }
      finally { $("create").disabled = false; }
    });
    $("open-batch-actions").addEventListener("click", () => $("batch-actions").showModal());
    $("cancel-batch-actions").addEventListener("click", () => $("batch-actions").close());
    $("batch-actions").addEventListener("close", () => $("open-batch-actions").focus());
    $("cancel-rename").addEventListener("click", () => { $("rename").hidden = true; $("batch-actions").close(); });
    $("rename").addEventListener("submit", async (event) => {
      event.preventDefault();
      $("batch-actions").close();
      await handleAction({ dataset: { localAction: "rename" } }).catch((error) => setStatus(error.message, true));
    });
    $("runs").addEventListener("change", () => {
      syncPipelineRoute();
      void loadRun($("runs").value).catch((error) => setStatus(error.message, true));
    });
    $("costume").addEventListener("change", () => {
      state.view = "";
      state.run = null;
      $("runs").value = "";
      syncPipelineRoute();
      void refreshContext();
    });
    $("style-variant").addEventListener("change", scheduleReadiness);
    $("front-count").addEventListener("change", scheduleReadiness);
    $("other-count").addEventListener("change", scheduleReadiness);
    $("use-anchor").addEventListener("change", scheduleReadiness);
    $("source-batches").addEventListener("change", scheduleReadiness);
    $("head-pipeline").addEventListener("change", () => { $("source-batches").replaceChildren(); scheduleReadiness(); });
    $("start").addEventListener("click", () => void perform(["INTERRUPTED", "STOPPED"].includes(state.run?.status)
      || (state.run?.status === "CANCELLED" && state.run?.created_by_autogenerate) || state.run?.slot_paused ? "resume" : "start").catch((error) => setStatus(error.message, true)));
    $("stop").addEventListener("click", () => void perform("stop").catch((error) => setStatus(error.message, true)));
    $("rerun").addEventListener("click", () => void handleAction({ dataset: { localAction: "rerun" } }).catch((error) => setStatus(error.message, true)));
    $("reevaluate").addEventListener("click", (event) => { $("batch-actions").close(); void submitBatchAction(event.currentTarget, "reevaluate"); });
    document.querySelectorAll("[data-local-comparison]").forEach(button => button.addEventListener("click", () => { $("batch-actions").close(); void showComparison(button.dataset.localComparison); }));
    $("use-masters").addEventListener("click", () => { $("batch-actions").close(); void useCurrentMasters(); });
    $("delete").addEventListener("click", () => { $("batch-actions").close(); void handleAction({ dataset: { localAction: "delete" } }).catch((error) => setStatus(error.message, true)); });
    $("proceed").addEventListener("click", (event) => void submitBatchAction(event.currentTarget, "proceed"));
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
    $("source-pipeline").addEventListener("change", () => void readiness());
    for (const field of ["mode-source-phase", "mode-source-pipeline", "mode-source-kind"]) $(field).addEventListener("change", () => {
      if (!state.run) return;
      const key = `${state.pipeline}:${state.run.run_id}:${state.renderMode}`;
      phaseSourceDrafts[key] = {...phaseSourceDrafts[key], phase: $("mode-source-phase").value, pipeline: $("mode-source-pipeline").value, kind: $("mode-source-kind").value};
      void previewModeSource();
    });
    async function stageModeSource(file) {
      if (!file || !state.run) return;
      const run = state.run, mode = state.renderMode, pipeline = state.pipeline;
      const key = `${pipeline}:${run.run_id}:${mode}`;
      const response = await fetch(`${baseUrl()}/sources?${new URLSearchParams({character: run.character, phase: run.phase, filename: file.name || "pasted-reference.png"})}`, {method: "POST", headers: {"Content-Type": file.type || "application/octet-stream", "X-Zet-Universe": document.querySelector("#universe-select").value}, body: file});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not upload source.");
      phaseSourceDrafts[key] = {...phaseSourceDrafts[key], path: data.path, kind: "upload"};
      if (state.run?.run_id === run.run_id && state.renderMode === mode && state.pipeline === pipeline) {
        $("mode-source-kind").value = "upload";
        $("mode-source-status").textContent = `Staged ${file.name}. Save source to apply.`;
        void previewModeSource();
      }
    }
    $("mode-source-file").addEventListener("change", () => void stageModeSource($("mode-source-file").files?.[0]).catch(error => setStatus(error.message, true)));
    $("mode-source-paste").addEventListener("paste", event => {
      const file = Array.from(event.clipboardData?.items || []).map(item => item.getAsFile()).find(Boolean);
      if (file) { event.preventDefault(); void stageModeSource(file).catch(error => setStatus(error.message, true)); }
    });
    $("mode-source-save").addEventListener("click", async () => {
      if (!state.run) return;
      const run = state.run, mode = state.renderMode, pipeline = state.pipeline;
      const key = `${pipeline}:${run.run_id}:${mode}`, draft = phaseSourceDrafts[key] || {};
      const body = $("mode-source-kind").value === "locked"
        ? {render_mode: mode, front_source_phase: $("mode-source-phase").value, front_source_pipeline: $("mode-source-pipeline").value}
        : {render_mode: mode, source_path: draft.path || ""};
      try {
        await request(`${baseUrl()}/runs/${encodeURIComponent(run.run_id)}/source`, {method: "PUT", body: JSON.stringify(body)});
        if (state.run?.run_id === run.run_id && state.pipeline === pipeline) { await loadRun(run.run_id); $("mode-source-status").textContent = "Source saved."; }
      } catch (error) { $("mode-source-status").textContent = error.message; }
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
    for (const host of [$("views"), $("selected"), $("batch-bulk-actions")]) host.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-local-action]");
      if (button && $("batch-actions").open) $("batch-actions").close();
      if (button?.closest("summary")) {
        event.preventDefault();
        event.stopPropagation();
      }
      if (button) void handleAction(button).catch((error) => setStatus(error.message, true));
    });
    $("review-close").addEventListener("click", () => $("review-dialog").close());
    $("review-dialog").addEventListener("keydown", event => {
      if (!state.reviewSelectedOnly || !["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      event.preventDefault();
      void navigateReview(event.key === "ArrowLeft" ? -1 : 1);
    });
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
    $("review-toggle").addEventListener("change", () => { state.comparisonChoice = $("review-toggle").value; refreshComparison(); });
    $("review-prev").addEventListener("click", () => { void navigateReview(-1); });
    $("review-next").addEventListener("click", () => { void navigateReview(1); });
    $("review-prev-view").addEventListener("click", () => { void navigateReviewView(-1); });
    $("review-next-view").addEventListener("click", () => { void navigateReviewView(1); });
  }

  async function activate(page) {
    const pipeline = pagePipelines[page];
    if (!pipeline) return;
    if (pipeline === state.pipeline) {
      const params = new URLSearchParams(window.location.search);
      const routedView = (params.get("local_view") || "").toUpperCase();
      const routedMode = params.get("render_mode") === "final" ? "final" : "draft";
      if (routedView !== state.view || routedMode !== state.renderMode) {
        state.view = routedView;
        state.renderMode = routedMode;
        $("render-quality").value = routedMode;
        state.generation += 1;
        if (state.run?.run_id) await loadRun(state.run.run_id, state.generation);
        render();
      }
      if (contextKey() !== state.contextKey || (!state.poll && !state.run)) await refreshContext();
      if (!state.poll) startPolling();
      return;
    }
    configurePipeline(pipeline);
  }

  function deactivate() {
    clearTimeout(readinessTimer);
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
    const view = matching ? state.view : (routeParams.get("local_view") || "").toUpperCase();
    if (view) {
      parameters.local_view = view;
      selections.view = { state: run ? run.views?.includes(view) ? "selected" : "unavailable" : status,
        id: view, label: view.replaceAll("_", " ") };
    }
    parameters.render_mode = matching ? state.renderMode : routeParams.get("render_mode") === "final" ? "final" : "draft";
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
