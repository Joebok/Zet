const state = {
  characters: [],
  phasesByCharacter: {},
  character: null,
  phase: null,
  assets: [],
  selectedAssetId: null,
  promptReviewTasks: [],
  selectedPromptReviewAssetId: null,
  promptReviewDetail: null,
  renderReviewTasks: [],
  selectedRenderReviewAssetId: null,
  renderReviewDetail: null,
  aiControls: null,
  pipelineControls: null,
  renderConsoleTasks: [],
  selectedRenderConsoleAskId: null,
  renderConsoleDetail: null,
  renderConsoleImageBlob: null,
  manifestTasks: [],
  selectedManifestAssetId: null,
  manifestDetail: null,
};

const characterSelect = document.querySelector("#character-select");
const phaseSelect = document.querySelector("#phase-select");
const assetTableBody = document.querySelector("#asset-table tbody");
const assetStatus = document.querySelector("#asset-status");
const detailTitle = document.querySelector("#detail-title");
const detailSummary = document.querySelector("#detail-summary");
const assetJson = document.querySelector("#asset-json");
const pathList = document.querySelector("#path-list");
const stageText = document.querySelector("#stage-text");
const historyText = document.querySelector("#history-text");
const placeholderTitle = document.querySelector("#placeholder-title");
const actionMessage = document.querySelector("#action-message");
const actionButtons = Array.from(document.querySelectorAll("[data-action]"));
const promptReviewStatus = document.querySelector("#prompt-review-status");
const promptReviewTaskBody = document.querySelector("#prompt-review-task-table tbody");
const promptReviewPrev = document.querySelector("#prompt-review-prev");
const promptReviewNext = document.querySelector("#prompt-review-next");
const promptReviewTitle = document.querySelector("#prompt-review-title");
const promptReviewMessage = document.querySelector("#prompt-review-message");
const promptSearch = document.querySelector("#prompt-search");
const promptPath = document.querySelector("#prompt-path");
const promptText = document.querySelector("#prompt-text");
const copyPromptButton = document.querySelector("#copy-prompt");
const viewCondensedButton = document.querySelector("#view-condensed");
const generateLocalTestButton = document.querySelector("#generate-local-test");
const localTestRender = document.querySelector("#local-test-render");
const promptApproveButton = document.querySelector("#prompt-approve");
const promptFailButton = document.querySelector("#prompt-fail");
const condensedDialog = document.querySelector("#condensed-dialog");
const condensedText = document.querySelector("#condensed-text");
const copyCondensedButton = document.querySelector("#copy-condensed");
const renderReviewStatus = document.querySelector("#render-review-status");
const renderReviewTaskBody = document.querySelector("#render-review-task-table tbody");
const renderReviewPrev = document.querySelector("#render-review-prev");
const renderReviewNext = document.querySelector("#render-review-next");
const renderReviewTitle = document.querySelector("#render-review-title");
const renderReviewPath = document.querySelector("#render-review-path");
const renderReviewMessage = document.querySelector("#render-review-message");
const candidateRender = document.querySelector("#candidate-render");
const renderPromoteButton = document.querySelector("#render-promote");
const renderFailRenderButton = document.querySelector("#render-fail-render");
const renderFailRegenerateButton = document.querySelector("#render-fail-regenerate");
const renderStageText = document.querySelector("#render-stage-text");
const renderHistoryText = document.querySelector("#render-history-text");
const aiControlsStatus = document.querySelector("#ai-controls-status");
const aiControlsMessage = document.querySelector("#ai-controls-message");
const proxyStopState = document.querySelector("#proxy-stop-state");
const harvestAiButton = document.querySelector("#harvest-ai");
const refreshAiControlsButton = document.querySelector("#refresh-ai-controls");
const activateProxyStopButton = document.querySelector("#activate-proxy-stop");
const resumeProxyStopButton = document.querySelector("#resume-proxy-stop");
const monitorInstruction = document.querySelector("#monitor-instruction");
const sendMonitorTestButton = document.querySelector("#send-monitor-test");
const processTableBody = document.querySelector("#process-table tbody");
const queueCounts = document.querySelector("#queue-counts");
const queueAskTableBody = document.querySelector("#queue-ask-table tbody");
const queueClaimedTableBody = document.querySelector("#queue-claimed-table tbody");
const queueAnswerTableBody = document.querySelector("#queue-answer-table tbody");
const queueFailedTableBody = document.querySelector("#queue-failed-table tbody");
const openRenderConsoleTab = document.querySelector("#open-render-console-tab");
const manualRenderCount = document.querySelector("#manual-render-count");
const manualRenderTableBody = document.querySelector("#manual-render-table tbody");
const monitorRequestTableBody = document.querySelector("#monitor-request-table tbody");
const monitorResponseTableBody = document.querySelector("#monitor-response-table tbody");
const pipelineControlsStatus = document.querySelector("#pipeline-controls-status");
const pipelineControlsMessage = document.querySelector("#pipeline-controls-message");
const automationForm = document.querySelector("#automation-form");
const settingPromptCondenseEnabled = document.querySelector("#setting-prompt-condense-enabled");
const settingPromptCondenseModel = document.querySelector("#setting-prompt-condense-model");
const settingPromptCondenseFile = document.querySelector("#setting-prompt-condense-file");
const settingLocalRenderAuto = document.querySelector("#setting-local-render-auto");
const settingLocalRenderPreset = document.querySelector("#setting-local-render-preset");
const settingAiHarvestAuto = document.querySelector("#setting-ai-harvest-auto");
const settingAiHarvestInterval = document.querySelector("#setting-ai-harvest-interval");
const settingRenderBackend = document.querySelector("#setting-render-backend");
const pipelineConfigPaths = document.querySelector("#pipeline-config-paths");
const projectConfigTableBody = document.querySelector("#project-config-table tbody");
const pipelineStageTableBody = document.querySelector("#pipeline-stage-table tbody");
const batchRenderPipeline = document.querySelector("#batch-render-pipeline");
const batchIncludeLocked = document.querySelector("#batch-include-locked");
const batchRenderResetButton = document.querySelector("#batch-render-reset");
const batchRenderResultTableBody = document.querySelector("#batch-render-result-table tbody");
const renderConsoleStatus = document.querySelector("#render-console-status");
const renderConsoleTaskBody = document.querySelector("#render-console-task-table tbody");
const renderConsolePrev = document.querySelector("#render-console-prev");
const renderConsoleNext = document.querySelector("#render-console-next");
const renderConsoleRefresh = document.querySelector("#render-console-refresh");
const renderConsoleTitle = document.querySelector("#render-console-title");
const renderConsoleCopyPrompt = document.querySelector("#render-console-copy-prompt");
const renderConsoleMessage = document.querySelector("#render-console-message");
const consoleAskId = document.querySelector("#console-ask-id");
const consoleAssetLabel = document.querySelector("#console-asset-label");
const consolePipelineLabel = document.querySelector("#console-pipeline-label");
const consoleExpectedOutput = document.querySelector("#console-expected-output");
const renderConsolePrompt = document.querySelector("#render-console-prompt");
const renderConsolePasteZone = document.querySelector("#render-console-paste-zone");
const renderConsoleFileInput = document.querySelector("#render-console-file-input");
const renderConsoleImagePreview = document.querySelector("#render-console-image-preview");
const renderConsoleSaveImage = document.querySelector("#render-console-save-image");
const renderConsoleSaveStatus = document.querySelector("#render-console-save-status");
const renderConsoleFailReason = document.querySelector("#render-console-fail-reason");
const renderConsoleFailTask = document.querySelector("#render-console-fail-task");
const renderConsoleFailStatus = document.querySelector("#render-console-fail-status");
const manifestStatus = document.querySelector("#manifest-status");
const manifestTaskBody = document.querySelector("#manifest-task-table tbody");
const manifestPrev = document.querySelector("#manifest-prev");
const manifestNext = document.querySelector("#manifest-next");
const manifestTitle = document.querySelector("#manifest-title");
const manifestMessage = document.querySelector("#manifest-message");
const saveManifestReferencesButton = document.querySelector("#save-manifest-references");
const bodyReferenceSelect = document.querySelector("#body-reference-select");
const headshotReferenceSelect = document.querySelector("#headshot-reference-select");
const headshotUpload = document.querySelector("#headshot-upload");
const bodyReferencePreview = document.querySelector("#body-reference-preview");
const headshotReferencePreview = document.querySelector("#headshot-reference-preview");
const manifestReferenceJson = document.querySelector("#manifest-reference-json");

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      // Keep HTTP detail.
    }
    throw new Error(detail);
  }
  return response.json();
}

function showActionMessage(message, kind = "info") {
  actionMessage.textContent = message || "";
  actionMessage.className = `action-message ${kind}`;
  actionMessage.hidden = !message;
}

function showPromptMessage(message, kind = "info") {
  promptReviewMessage.textContent = message || "";
  promptReviewMessage.className = `action-message ${kind}`;
  promptReviewMessage.hidden = !message;
}

function showRenderMessage(message, kind = "info") {
  renderReviewMessage.textContent = message || "";
  renderReviewMessage.className = `action-message ${kind}`;
  renderReviewMessage.hidden = !message;
}

function showAiControlsMessage(message, kind = "info") {
  aiControlsMessage.textContent = message || "";
  aiControlsMessage.className = `action-message ${kind}`;
  aiControlsMessage.hidden = !message;
}

function showPipelineControlsMessage(message, kind = "info") {
  pipelineControlsMessage.textContent = message || "";
  pipelineControlsMessage.className = `action-message ${kind}`;
  pipelineControlsMessage.hidden = !message;
}

function showRenderConsoleMessage(message, kind = "info") {
  renderConsoleMessage.textContent = message || "";
  renderConsoleMessage.className = `action-message ${kind}`;
  renderConsoleMessage.hidden = !message;
}

function showManifestMessage(message, kind = "info") {
  manifestMessage.textContent = message || "";
  manifestMessage.className = `action-message ${kind}`;
  manifestMessage.hidden = !message;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function option(value, label = value) {
  const item = document.createElement("option");
  item.value = value;
  item.textContent = label;
  return item;
}

function setSelectOptions(select, values) {
  select.replaceChildren(...values.map((value) => option(value)));
}

function currentQuery() {
  return new URLSearchParams({ character: state.character, phase: state.phase });
}

async function loadContext() {
  const payload = await fetchJson("/api/context");
  state.characters = payload.characters || [];
  state.phasesByCharacter = payload.phases_by_character || {};
  state.character = payload.default_character;
  state.phase = payload.default_phase;
  setSelectOptions(characterSelect, state.characters);
  characterSelect.value = state.character || "";
  updatePhaseSelect();
}

function updatePhaseSelect() {
  const phases = state.phasesByCharacter[state.character] || [];
  setSelectOptions(phaseSelect, phases);
  if (!phases.includes(state.phase)) {
    state.phase = phases[0] || null;
  }
  phaseSelect.value = state.phase || "";
}

async function loadAssets(preferredAssetId = null) {
  if (!state.character || !state.phase) {
    assetStatus.textContent = "No character/phase selected.";
    return;
  }
  assetStatus.textContent = "Loading assets...";
  const payload = await fetchJson(`/api/assets?${currentQuery().toString()}`);
  state.assets = payload.assets || [];
  const assetIds = new Set(state.assets.map((asset) => asset.asset_id));
  state.selectedAssetId = preferredAssetId || state.selectedAssetId || state.assets[0]?.asset_id || null;
  if (state.selectedAssetId && !assetIds.has(state.selectedAssetId)) {
    state.selectedAssetId = state.assets[0]?.asset_id || null;
  }
  renderAssetTable();
  if (state.selectedAssetId) {
    await selectAsset(state.selectedAssetId);
  } else {
    clearDetail();
  }
  assetStatus.textContent = `${state.assets.length} asset(s)`;
}

function renderAssetTable() {
  assetTableBody.replaceChildren();
  for (const asset of state.assets) {
    const row = document.createElement("tr");
    row.dataset.assetId = asset.asset_id;
    if (asset.asset_id === state.selectedAssetId) {
      row.classList.add("selected");
    }
    const values = [
      asset.asset_id,
      asset.pipeline,
      asset.body_view,
      asset.head_view,
      asset.asset_state,
      asset.pipeline_stage_display,
      asset.actor,
      asset.ai_state,
      asset.updated_at_display,
    ];
    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = value ?? "";
      row.append(cell);
    }
    row.addEventListener("click", () => selectAsset(asset.asset_id));
    assetTableBody.append(row);
  }
}

async function selectAsset(assetId) {
  state.selectedAssetId = Number(assetId);
  for (const row of assetTableBody.querySelectorAll("tr")) {
    row.classList.toggle("selected", Number(row.dataset.assetId) === state.selectedAssetId);
  }
  const detail = await fetchJson(`/api/assets/${state.selectedAssetId}?${currentQuery().toString()}`);
  renderDetail(detail);
}

function clearDetail() {
  detailTitle.textContent = "Select an asset";
  detailSummary.textContent = "";
  assetJson.textContent = "";
  pathList.replaceChildren();
  stageText.textContent = "";
  historyText.textContent = "";
  updateActionButtons(null);
}

function renderDetail(detail) {
  const asset = detail.asset;
  detailTitle.textContent = `Asset ${asset.asset_id}`;
  detailSummary.textContent = [
    asset.pipeline,
    asset.body_view,
    asset.pipeline_stage,
    asset.actor,
    `ai_state: ${asset.ai_state}`,
  ].join(" | ");
  assetJson.textContent = JSON.stringify(asset, null, 2);
  pathList.replaceChildren();
  for (const [key, value] of Object.entries(detail.paths || {})) {
    const term = document.createElement("dt");
    term.textContent = key;
    const definition = document.createElement("dd");
    definition.textContent = value;
    pathList.append(term, definition);
  }
  stageText.textContent = detail.stage_text || "No stage marker found.";
  historyText.textContent = detail.history_text || "No history found.";
  updateActionButtons(detail);
}

function updateActionButtons(detail) {
  const asset = detail?.asset || null;
  const candidateExists = Boolean(detail?.exists?.candidate_image);
  for (const button of actionButtons) {
    const action = button.dataset.action;
    let enabled = Boolean(asset);
    if (action === "stage-ai-ask" || action === "retry-ai") {
      enabled = enabled && asset.actor === "AI_AGENT";
    }
    if (action === "run-current-worker") {
      enabled = enabled && asset.actor === "PYTHON";
    }
    if (action === "promote-to-locked") {
      enabled = enabled && candidateExists;
    }
    button.disabled = !enabled;
  }
}

async function runAssetAction(action) {
  if (!state.selectedAssetId) {
    return;
  }
  showActionMessage("Working...");
  for (const button of actionButtons) {
    button.disabled = true;
  }
  try {
    const payload = await fetchJson(
      `/api/assets/${state.selectedAssetId}/${action}?${currentQuery().toString()}`,
      { method: "POST" },
    );
    state.assets = payload.assets || state.assets;
    renderAssetTable();
    if (payload.detail) {
      renderDetail(payload.detail);
    } else {
      await selectAsset(state.selectedAssetId);
    }
    showActionMessage(payload.message || "Action complete.");
  } catch (error) {
    showActionMessage(error.message, "error");
    await selectAsset(state.selectedAssetId);
  }
}

function setupTabs() {
  for (const button of document.querySelectorAll(".tab")) {
    button.addEventListener("click", () => {
      for (const item of document.querySelectorAll(".tab")) {
        item.classList.toggle("active", item === button);
      }
      const page = button.dataset.page;
      document.querySelector("#assets-page").classList.toggle("active", page === "assets");
      document.querySelector("#manifest-page").classList.toggle("active", page === "manifest");
      document.querySelector("#prompt-review-page").classList.toggle("active", page === "prompt-review");
      document.querySelector("#render-review-page").classList.toggle("active", page === "render-review");
      document.querySelector("#ai-controls-page").classList.toggle("active", page === "ai-controls");
      document.querySelector("#pipeline-controls-page").classList.toggle("active", page === "pipeline-controls");
      document.querySelector("#render-console-page").classList.toggle("active", page === "render-console");
      document
        .querySelector("#placeholder-page")
        .classList.toggle(
          "active",
          !["assets", "manifest", "prompt-review", "render-review", "render-console", "ai-controls", "pipeline-controls"].includes(page),
        );
      placeholderTitle.textContent = button.textContent;
      if (page === "prompt-review") {
        loadPromptReviewTasks();
      }
      if (page === "manifest") {
        loadManifestTasks();
      }
      if (page === "render-review") {
        loadRenderReviewTasks();
      }
      if (page === "ai-controls") {
        loadAiControls();
      }
      if (page === "pipeline-controls") {
        loadPipelineControls();
      }
      if (page === "render-console") {
        loadRenderConsoleTasks();
      }
    });
  }
}

async function loadPromptReviewTasks(preferredAssetId = null) {
  if (!state.character || !state.phase) {
    promptReviewStatus.textContent = "No character/phase selected.";
    return;
  }
  promptReviewStatus.textContent = "Loading prompt reviews...";
  const payload = await fetchJson(`/api/prompt-review/tasks?${currentQuery().toString()}`);
  state.promptReviewTasks = payload.tasks || [];
  const taskIds = new Set(state.promptReviewTasks.map((task) => task.asset_id));
  state.selectedPromptReviewAssetId =
    preferredAssetId || state.selectedPromptReviewAssetId || state.promptReviewTasks[0]?.asset_id || null;
  if (state.selectedPromptReviewAssetId && !taskIds.has(state.selectedPromptReviewAssetId)) {
    state.selectedPromptReviewAssetId = state.promptReviewTasks[0]?.asset_id || null;
  }
  renderPromptReviewTaskTable();
  promptReviewStatus.textContent = `${state.promptReviewTasks.length} prompt(s) waiting`;
  if (state.selectedPromptReviewAssetId) {
    await selectPromptReviewAsset(state.selectedPromptReviewAssetId);
  } else {
    clearPromptReview();
  }
}

function renderPromptReviewTaskTable() {
  promptReviewTaskBody.replaceChildren();
  for (const task of state.promptReviewTasks) {
    const row = document.createElement("tr");
    row.dataset.assetId = task.asset_id;
    row.classList.toggle("selected", task.asset_id === state.selectedPromptReviewAssetId);
    for (const value of [task.asset_id, task.body_view, task.condense_state || ""]) {
      const cell = document.createElement("td");
      cell.textContent = value ?? "";
      row.append(cell);
    }
    row.addEventListener("click", () => selectPromptReviewAsset(task.asset_id));
    promptReviewTaskBody.append(row);
  }
}

async function selectPromptReviewAsset(assetId) {
  state.selectedPromptReviewAssetId = Number(assetId);
  for (const row of promptReviewTaskBody.querySelectorAll("tr")) {
    row.classList.toggle("selected", Number(row.dataset.assetId) === state.selectedPromptReviewAssetId);
  }
  const detail = await fetchJson(`/api/prompt-review/${state.selectedPromptReviewAssetId}?${currentQuery().toString()}`);
  renderPromptReview(detail);
}

function clearPromptReview() {
  state.promptReviewDetail = null;
  promptReviewTitle.textContent = "Select a prompt";
  promptPath.textContent = "";
  promptText.textContent = "";
  localTestRender.textContent = "No local test render.";
  promptReviewPrev.disabled = true;
  promptReviewNext.disabled = true;
  copyPromptButton.disabled = true;
  viewCondensedButton.disabled = true;
  generateLocalTestButton.disabled = true;
  promptApproveButton.disabled = true;
  promptFailButton.disabled = true;
}

function renderPromptReview(detail) {
  state.promptReviewDetail = detail;
  const asset = detail.asset;
  promptReviewTitle.textContent = `Asset ${asset.asset_id} | ${asset.body_view}`;
  promptPath.textContent = detail.prompt_path || "No prompt file found.";
  renderPromptText();
  condensedText.value = detail.condensed_prompt_text || "";
  viewCondensedButton.disabled = !detail.condensed_prompt_text;
  copyPromptButton.disabled = !detail.prompt_text;
  generateLocalTestButton.disabled = !detail.prompt_text || !detail.is_reviewable;
  promptApproveButton.disabled = !detail.is_reviewable;
  promptFailButton.disabled = !detail.is_reviewable;
  renderLocalTestRender(detail.latest_local_test_render);
  updatePromptReviewNavigation();
}

function renderPromptText() {
  const detail = state.promptReviewDetail;
  if (!detail) {
    promptText.textContent = "";
    return;
  }
  const query = promptSearch.value.trim();
  const raw = detail.prompt_text || "";
  if (!query) {
    promptText.textContent = raw || "No prompt text found.";
    return;
  }
  const pattern = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
  promptText.innerHTML = escapeHtml(raw).replace(pattern, (match) => `<mark>${escapeHtml(match)}</mark>`);
}

function renderLocalTestRender(path) {
  localTestRender.replaceChildren();
  if (!path) {
    localTestRender.textContent = "No local test render.";
    return;
  }
  const image = document.createElement("img");
  image.alt = "Latest local test render";
  image.src = `/api/file?path=${encodeURIComponent(path)}`;
  image.title = path;
  localTestRender.append(image);
}

function updatePromptReviewNavigation() {
  const index = state.promptReviewTasks.findIndex((task) => task.asset_id === state.selectedPromptReviewAssetId);
  promptReviewPrev.disabled = index <= 0;
  promptReviewNext.disabled = index < 0 || index >= state.promptReviewTasks.length - 1;
}

async function copyText(value, label = "Copied.") {
  await navigator.clipboard.writeText(value || "");
  showPromptMessage(label);
}

async function runPromptReviewAction(action) {
  if (!state.selectedPromptReviewAssetId) {
    return;
  }
  showPromptMessage("Working...");
  try {
    const payload = await fetchJson(
      `/api/prompt-review/${state.selectedPromptReviewAssetId}/${action}?${currentQuery().toString()}`,
      { method: "POST" },
    );
    if (action === "approve" || action === "fail") {
      showPromptMessage(payload.message || "Review action complete.");
      await loadPromptReviewTasks();
      await loadAssets(state.selectedAssetId);
      return;
    }
    renderPromptReview(payload);
    showPromptMessage(payload.message || "Action complete.");
  } catch (error) {
    showPromptMessage(error.message, "error");
  }
}

async function loadRenderReviewTasks(preferredAssetId = null) {
  if (!state.character || !state.phase) {
    renderReviewStatus.textContent = "No character/phase selected.";
    return;
  }
  renderReviewStatus.textContent = "Loading render reviews...";
  const payload = await fetchJson(`/api/render-review/tasks?${currentQuery().toString()}`);
  state.renderReviewTasks = payload.tasks || [];
  const taskIds = new Set(state.renderReviewTasks.map((task) => task.asset_id));
  state.selectedRenderReviewAssetId =
    preferredAssetId || state.selectedRenderReviewAssetId || state.renderReviewTasks[0]?.asset_id || null;
  if (state.selectedRenderReviewAssetId && !taskIds.has(state.selectedRenderReviewAssetId)) {
    state.selectedRenderReviewAssetId = state.renderReviewTasks[0]?.asset_id || null;
  }
  renderRenderReviewTaskTable();
  renderReviewStatus.textContent = `${state.renderReviewTasks.length} render(s) waiting`;
  if (state.selectedRenderReviewAssetId) {
    await selectRenderReviewAsset(state.selectedRenderReviewAssetId);
  } else {
    clearRenderReview();
  }
}

function renderRenderReviewTaskTable() {
  renderReviewTaskBody.replaceChildren();
  for (const task of state.renderReviewTasks) {
    const row = document.createElement("tr");
    row.dataset.assetId = task.asset_id;
    row.classList.toggle("selected", task.asset_id === state.selectedRenderReviewAssetId);
    for (const value of [task.asset_id, task.body_view, task.candidate_image_exists ? "CAMERA" : ""]) {
      const cell = document.createElement("td");
      cell.textContent = value ?? "";
      row.append(cell);
    }
    row.addEventListener("click", () => selectRenderReviewAsset(task.asset_id));
    renderReviewTaskBody.append(row);
  }
}

async function selectRenderReviewAsset(assetId) {
  state.selectedRenderReviewAssetId = Number(assetId);
  for (const row of renderReviewTaskBody.querySelectorAll("tr")) {
    row.classList.toggle("selected", Number(row.dataset.assetId) === state.selectedRenderReviewAssetId);
  }
  const detail = await fetchJson(`/api/render-review/${state.selectedRenderReviewAssetId}?${currentQuery().toString()}`);
  renderRenderReview(detail);
}

function clearRenderReview() {
  state.renderReviewDetail = null;
  renderReviewTitle.textContent = "Select a render";
  renderReviewPath.textContent = "";
  candidateRender.textContent = "No candidate image.";
  renderStageText.textContent = "";
  renderHistoryText.textContent = "";
  renderReviewPrev.disabled = true;
  renderReviewNext.disabled = true;
  renderPromoteButton.disabled = true;
  renderFailRenderButton.disabled = true;
  renderFailRegenerateButton.disabled = true;
}

function renderRenderReview(detail) {
  state.renderReviewDetail = detail;
  const asset = detail.asset;
  renderReviewTitle.textContent = `Asset ${asset.asset_id} | ${asset.body_view}`;
  renderReviewPath.textContent = detail.candidate_image_path || "";
  renderStageText.textContent = detail.stage_text || "No stage marker found.";
  renderHistoryText.textContent = detail.history_text || "No history found.";
  renderCandidateImage(detail);
  renderPromoteButton.disabled = !detail.is_reviewable || !detail.exists?.candidate_image;
  renderFailRenderButton.disabled = !detail.is_reviewable;
  renderFailRegenerateButton.disabled = !detail.is_reviewable;
  updateRenderReviewNavigation();
}

function renderCandidateImage(detail) {
  candidateRender.replaceChildren();
  if (!detail.exists?.candidate_image || !detail.candidate_image_path) {
    candidateRender.textContent = "No candidate image.";
    return;
  }
  const image = document.createElement("img");
  image.alt = "Candidate render";
  image.src = `/api/file?path=${encodeURIComponent(detail.candidate_image_path)}`;
  image.title = detail.candidate_image_path;
  candidateRender.append(image);
}

function updateRenderReviewNavigation() {
  const index = state.renderReviewTasks.findIndex((task) => task.asset_id === state.selectedRenderReviewAssetId);
  renderReviewPrev.disabled = index <= 0;
  renderReviewNext.disabled = index < 0 || index >= state.renderReviewTasks.length - 1;
}

async function runRenderReviewAction(action) {
  if (!state.selectedRenderReviewAssetId) {
    return;
  }
  showRenderMessage("Working...");
  try {
    const payload = await fetchJson(
      `/api/render-review/${state.selectedRenderReviewAssetId}/${action}?${currentQuery().toString()}`,
      { method: "POST" },
    );
    showRenderMessage(payload.message || "Review action complete.");
    await loadRenderReviewTasks();
    await loadAssets(state.selectedAssetId);
  } catch (error) {
    showRenderMessage(error.message, "error");
  }
}

function renderRows(tbody, rows, columns) {
  tbody.replaceChildren();
  if (!rows || rows.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = Math.max(1, columns.length);
    cell.textContent = "None.";
    row.append(cell);
    tbody.append(row);
    return;
  }
  for (const item of rows) {
    const row = document.createElement("tr");
    for (const column of columns) {
      const cell = document.createElement("td");
      cell.textContent = item[column] ?? "";
      row.append(cell);
    }
    tbody.append(row);
  }
}

async function loadAiControls() {
  aiControlsStatus.textContent = "Loading AI controls...";
  const payload = await fetchJson("/api/ai-controls");
  renderAiControls(payload);
}

function renderAiControls(payload) {
  state.aiControls = payload;
  const stopState = payload.stop_state || {};
  proxyStopState.textContent = stopState.active
    ? `Proxy STOPPED | stop_id: ${stopState.stop_id || ""} | cleared asks: ${stopState.cleared_asks || 0}`
    : "Proxy ACTIVE";
  const counts = payload.queue_counts || {};
  queueCounts.textContent =
    `Ask: ${counts.ask || 0} | Claimed: ${counts.claimed || 0} | Answer: ${counts.answer || 0} | Failed: ${counts.failed || 0}`;
  renderRows(queueAskTableBody, payload.queue?.ask || [], ["ask_id", "asset_id", "pipeline_stage", "worker_type", "task_type"]);
  renderRows(queueClaimedTableBody, payload.queue?.claimed || [], ["worker_id", "ask_id", "asset_id", "worker_type", "task_type"]);
  renderRows(queueAnswerTableBody, payload.queue?.answer || [], ["ask_id", "asset_id", "status", "worker_id"]);
  renderRows(queueFailedTableBody, payload.queue?.failed || [], ["worker_id", "name"]);
  renderRows(manualRenderTableBody, payload.manual_render_asks || [], ["ask_id", "asset_id", "pipeline_stage", "task_type"]);
  renderRows(monitorRequestTableBody, payload.monitor_requests || [], ["test_id", "instruction", "created_at"]);
  renderRows(monitorResponseTableBody, payload.monitor_responses || [], ["test_id", "worker_id", "host", "status", "ollama_ok", "responded_at"]);
  manualRenderCount.textContent = `${(payload.manual_render_asks || []).length} manual render task(s) waiting`;
  renderProcessRows(payload.processes || []);
  aiControlsStatus.textContent = "Ready";
}

function renderProcessRows(processes) {
  processTableBody.replaceChildren();
  for (const item of processes) {
    const row = document.createElement("tr");
    for (const value of [item.label || item.process_id, item.running, item.duplicates, item.pids]) {
      const cell = document.createElement("td");
      cell.textContent = value ?? "";
      row.append(cell);
    }
    const actionCell = document.createElement("td");
    const actions = document.createElement("div");
    actions.className = "mini-actions";
    for (const action of ["start", "stop", "restart"]) {
      const button = document.createElement("button");
      button.textContent = action;
      button.disabled = item.manageable !== "yes";
      button.addEventListener("click", () => runAiControlsAction(`/api/ai-controls/processes/${item.process_id}/${action}`));
      actions.append(button);
    }
    actionCell.append(actions);
    row.append(actionCell);
    processTableBody.append(row);
  }
}

async function runAiControlsAction(url) {
  showAiControlsMessage("Working...");
  try {
    const payload = await fetchJson(url, { method: "POST" });
    renderAiControls(payload);
    showAiControlsMessage(payload.message || "Action complete.");
  } catch (error) {
    showAiControlsMessage(error.message, "error");
  }
}

async function loadPipelineControls() {
  if (!state.character || !state.phase) {
    pipelineControlsStatus.textContent = "No character/phase selected.";
    return;
  }
  pipelineControlsStatus.textContent = "Loading pipeline controls...";
  const payload = await fetchJson(`/api/pipeline-controls?${currentQuery().toString()}`);
  renderPipelineControls(payload);
}

function renderPipelineControls(payload) {
  state.pipelineControls = payload;
  const automation = payload.automation || {};
  settingPromptCondenseEnabled.checked = Boolean(automation.prompt_condense_enabled);
  settingPromptCondenseModel.value = automation.prompt_condense_model || "";
  settingPromptCondenseFile.value = automation.prompt_condense_file || "";
  settingLocalRenderAuto.checked = Boolean(automation.local_render_auto_queue_after_condense);
  settingLocalRenderPreset.value = automation.local_render_preset || "";
  settingAiHarvestAuto.checked = Boolean(automation.ai_harvest_auto_enabled);
  settingAiHarvestInterval.value = automation.ai_harvest_interval_seconds ?? 300;
  settingRenderBackend.value = automation.render_backend || "manual_chatgpt";
  pipelineConfigPaths.textContent = `Config: ${payload.config_path || ""} | Pipelines: ${payload.pipelines_path || ""}`;
  renderRows(projectConfigTableBody, payload.project_config_rows || [], ["Scope", "Setting", "Value"]);
  renderRows(pipelineStageTableBody, payload.pipeline_rows || [], ["pipeline", "step", "stage", "actor", "worker", "asset_count"]);
  const currentPipeline = batchRenderPipeline.value;
  setSelectOptions(batchRenderPipeline, payload.pipeline_names || []);
  if ((payload.pipeline_names || []).includes(currentPipeline)) {
    batchRenderPipeline.value = currentPipeline;
  }
  pipelineControlsStatus.textContent = "Ready";
}

function automationPayloadFromForm() {
  return {
    prompt_condense_enabled: settingPromptCondenseEnabled.checked,
    prompt_condense_model: settingPromptCondenseModel.value,
    prompt_condense_file: settingPromptCondenseFile.value,
    local_render_auto_queue_after_condense: settingLocalRenderAuto.checked,
    local_render_preset: settingLocalRenderPreset.value,
    ai_harvest_auto_enabled: settingAiHarvestAuto.checked,
    ai_harvest_interval_seconds: Number(settingAiHarvestInterval.value || 0),
    render_backend: settingRenderBackend.value,
  };
}

async function saveAutomationSettings(event) {
  event.preventDefault();
  showPipelineControlsMessage("Saving...");
  try {
    const payload = await fetchJson(`/api/pipeline-controls/automation?${currentQuery().toString()}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(automationPayloadFromForm()),
    });
    renderPipelineControls(payload);
    showPipelineControlsMessage(payload.message || "Settings saved.");
  } catch (error) {
    showPipelineControlsMessage(error.message, "error");
  }
}

async function runBatchRenderReset() {
  const pipeline = batchRenderPipeline.value;
  if (!pipeline) {
    return;
  }
  showPipelineControlsMessage("Working...");
  const params = currentQuery();
  params.set("pipeline_name", pipeline);
  params.set("include_locked", batchIncludeLocked.checked ? "true" : "false");
  try {
    const payload = await fetchJson(`/api/pipeline-controls/batch-render-reset?${params.toString()}`, { method: "POST" });
    renderPipelineControls(payload);
    renderRows(batchRenderResultTableBody, payload.batch_results || [], [
      "asset_id",
      "before_stage",
      "before_actor",
      "before_state",
      "status",
      "message",
    ]);
    showPipelineControlsMessage(payload.message || "Batch reset complete.");
    await loadAssets(state.selectedAssetId);
  } catch (error) {
    showPipelineControlsMessage(error.message, "error");
  }
}

async function loadRenderConsoleTasks(preferredAskId = null) {
  renderConsoleStatus.textContent = "Loading render tasks...";
  const payload = await fetchJson("/api/render-console/tasks");
  state.renderConsoleTasks = payload.tasks || [];
  const askIds = new Set(state.renderConsoleTasks.map((task) => task.ask_id));
  state.selectedRenderConsoleAskId =
    preferredAskId || state.selectedRenderConsoleAskId || state.renderConsoleTasks[0]?.ask_id || null;
  if (state.selectedRenderConsoleAskId && !askIds.has(state.selectedRenderConsoleAskId)) {
    state.selectedRenderConsoleAskId = state.renderConsoleTasks[0]?.ask_id || null;
  }
  renderRenderConsoleTaskTable();
  renderConsoleStatus.textContent = `${state.renderConsoleTasks.length} manual render task(s) waiting`;
  if (state.selectedRenderConsoleAskId) {
    await selectRenderConsoleTask(state.selectedRenderConsoleAskId);
  } else {
    clearRenderConsole();
  }
}

function renderRenderConsoleTaskTable() {
  renderConsoleTaskBody.replaceChildren();
  for (const task of state.renderConsoleTasks) {
    const row = document.createElement("tr");
    row.dataset.askId = task.ask_id;
    row.classList.toggle("selected", task.ask_id === state.selectedRenderConsoleAskId);
    for (const value of [task.asset_id ?? "", task.ask_id]) {
      const cell = document.createElement("td");
      cell.textContent = value ?? "";
      row.append(cell);
    }
    row.addEventListener("click", () => selectRenderConsoleTask(task.ask_id));
    renderConsoleTaskBody.append(row);
  }
}

async function selectRenderConsoleTask(askId) {
  state.selectedRenderConsoleAskId = askId;
  for (const row of renderConsoleTaskBody.querySelectorAll("tr")) {
    row.classList.toggle("selected", row.dataset.askId === state.selectedRenderConsoleAskId);
  }
  const detail = await fetchJson(`/api/render-console/tasks/${encodeURIComponent(askId)}`);
  renderRenderConsoleDetail(detail);
}

function clearRenderConsole() {
  state.renderConsoleDetail = null;
  state.renderConsoleImageBlob = null;
  renderConsoleTitle.textContent = "Select a render task";
  consoleAskId.textContent = "";
  consoleAssetLabel.textContent = "";
  consolePipelineLabel.textContent = "";
  consoleExpectedOutput.textContent = "";
  renderConsolePrompt.value = "";
  renderConsoleImagePreview.hidden = true;
  renderConsoleImagePreview.removeAttribute("src");
  renderConsoleSaveImage.disabled = true;
  renderConsoleCopyPrompt.disabled = true;
  renderConsolePrev.disabled = true;
  renderConsoleNext.disabled = true;
  renderConsoleFailTask.disabled = true;
  renderConsoleSaveStatus.textContent = "";
  renderConsoleFailStatus.textContent = "";
}

function renderRenderConsoleDetail(detail) {
  state.renderConsoleDetail = detail;
  clearRenderConsoleImageSelection();
  const task = detail.task;
  renderConsoleTitle.textContent = `Asset ${task.asset_id ?? "unknown"} | ${task.expected_output || task.ask_id}`;
  consoleAskId.textContent = task.ask_id;
  consoleAssetLabel.textContent = `Asset ${task.asset_id ?? "unknown"} | ${task.character} / ${task.phase}`;
  consolePipelineLabel.textContent = `${task.pipeline} | ${task.pipeline_stage}`;
  consoleExpectedOutput.textContent = task.expected_output || "";
  renderConsolePrompt.value = detail.prompt || "";
  renderConsoleCopyPrompt.disabled = !detail.prompt;
  renderConsoleFailTask.disabled = false;
  renderConsoleReferenceFiles(detail.manifest?.reference_files || []);
  updateRenderConsoleNavigation();
}

function renderConsoleReferenceFiles(referenceFiles) {
  const container = document.querySelector("#render-console-reference-files");
  container.replaceChildren();
  for (const reference of referenceFiles || []) {
    const section = document.createElement("section");
    section.className = "reference-preview";
    const title = document.createElement("h3");
    title.textContent = reference.label || reference.role || "Reference";
    const path = document.createElement("p");
    path.className = "status-text";
    path.textContent = reference.path || "";
    section.append(title, path);
    if (reference.path) {
      const image = document.createElement("img");
      image.alt = title.textContent;
      image.src = `/api/file?path=${encodeURIComponent(reference.path)}`;
      section.append(image);
    }
    container.append(section);
  }
}

function updateRenderConsoleNavigation() {
  const index = state.renderConsoleTasks.findIndex((task) => task.ask_id === state.selectedRenderConsoleAskId);
  renderConsolePrev.disabled = index <= 0;
  renderConsoleNext.disabled = index < 0 || index >= state.renderConsoleTasks.length - 1;
}

function clearRenderConsoleImageSelection() {
  state.renderConsoleImageBlob = null;
  renderConsoleImagePreview.hidden = true;
  renderConsoleImagePreview.removeAttribute("src");
  renderConsoleSaveImage.disabled = true;
  renderConsoleSaveStatus.textContent = "";
  renderConsoleFailReason.value = "";
  renderConsoleFailStatus.textContent = "";
}

function setRenderConsoleImageSelection(blob) {
  if (!blob || !blob.type.startsWith("image/")) {
    renderConsoleSaveStatus.textContent = "Clipboard or file did not contain an image.";
    return;
  }
  state.renderConsoleImageBlob = blob;
  renderConsoleImagePreview.src = URL.createObjectURL(blob);
  renderConsoleImagePreview.hidden = false;
  renderConsoleSaveImage.disabled = false;
  renderConsoleSaveStatus.textContent = `Ready to save ${Math.round(blob.size / 1024)} KB image.`;
}

function imageBlobFromPasteEvent(event) {
  const items = event.clipboardData?.items || [];
  for (const item of items) {
    if (item.type.startsWith("image/")) {
      return item.getAsFile();
    }
  }
  return null;
}

async function saveRenderConsoleImage() {
  if (!state.renderConsoleImageBlob || !state.selectedRenderConsoleAskId) {
    return;
  }
  renderConsoleSaveImage.disabled = true;
  renderConsoleSaveStatus.textContent = "Saving image answer...";
  try {
    const response = await fetch(
      `/api/render-console/tasks/${encodeURIComponent(state.selectedRenderConsoleAskId)}/answer-image`,
      {
        method: "POST",
        headers: { "Content-Type": state.renderConsoleImageBlob.type || "application/octet-stream" },
        body: state.renderConsoleImageBlob,
      },
    );
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `${response.status} ${response.statusText}`);
    }
    const payload = await response.json();
    showRenderConsoleMessage(`Saved answer: ${payload.answer_path}`);
    state.renderConsoleTasks = payload.remaining_tasks || [];
    state.selectedRenderConsoleAskId = state.renderConsoleTasks[0]?.ask_id || null;
    renderRenderConsoleTaskTable();
    if (state.selectedRenderConsoleAskId) {
      await selectRenderConsoleTask(state.selectedRenderConsoleAskId);
    } else {
      clearRenderConsole();
    }
    renderConsoleStatus.textContent = `${state.renderConsoleTasks.length} manual render task(s) waiting`;
    await loadAiControls().catch(() => {});
  } catch (error) {
    renderConsoleSaveStatus.textContent = `Save failed: ${error.message}`;
    renderConsoleSaveImage.disabled = false;
  }
}

async function failRenderConsoleTask() {
  if (!state.selectedRenderConsoleAskId) {
    return;
  }
  if (!window.confirm("Fail this manual render task? The asset will be blocked when harvested.")) {
    return;
  }
  renderConsoleFailTask.disabled = true;
  renderConsoleFailStatus.textContent = "Writing failed answer...";
  try {
    const response = await fetch(`/api/render-console/tasks/${encodeURIComponent(state.selectedRenderConsoleAskId)}/fail`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: renderConsoleFailReason.value || "" }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `${response.status} ${response.statusText}`);
    }
    const payload = await response.json();
    showRenderConsoleMessage(`Failed answer written: ${payload.answer_path}`);
    state.renderConsoleTasks = payload.remaining_tasks || [];
    state.selectedRenderConsoleAskId = state.renderConsoleTasks[0]?.ask_id || null;
    renderRenderConsoleTaskTable();
    if (state.selectedRenderConsoleAskId) {
      await selectRenderConsoleTask(state.selectedRenderConsoleAskId);
    } else {
      clearRenderConsole();
    }
    renderConsoleStatus.textContent = `${state.renderConsoleTasks.length} manual render task(s) waiting`;
    await loadAiControls().catch(() => {});
  } catch (error) {
    renderConsoleFailStatus.textContent = `Fail failed: ${error.message}`;
  } finally {
    renderConsoleFailTask.disabled = false;
  }
}

async function loadManifestTasks(preferredAssetId = null) {
  if (!state.character || !state.phase) {
    manifestStatus.textContent = "No character/phase selected.";
    return;
  }
  manifestStatus.textContent = "Loading manifest tasks...";
  const payload = await fetchJson(`/api/head-fitment-manifest/tasks?${currentQuery().toString()}`);
  state.manifestTasks = payload.tasks || [];
  const taskIds = new Set(state.manifestTasks.map((task) => task.asset_id));
  state.selectedManifestAssetId = preferredAssetId || state.selectedManifestAssetId || state.manifestTasks[0]?.asset_id || null;
  if (state.selectedManifestAssetId && !taskIds.has(state.selectedManifestAssetId)) {
    state.selectedManifestAssetId = state.manifestTasks[0]?.asset_id || null;
  }
  renderManifestTaskTable();
  manifestStatus.textContent = `${state.manifestTasks.length} manifest task(s) waiting`;
  if (state.selectedManifestAssetId) {
    await selectManifestAsset(state.selectedManifestAssetId);
  } else {
    clearManifest();
  }
}

function renderManifestTaskTable() {
  manifestTaskBody.replaceChildren();
  for (const task of state.manifestTasks) {
    const row = document.createElement("tr");
    row.dataset.assetId = task.asset_id;
    row.classList.toggle("selected", task.asset_id === state.selectedManifestAssetId);
    const bodyState = task.has_body_reference ? "yes" : (task.pipeline_stage === "ADD_REF" ? "missing" : "");
    const headshotState = task.has_headshot ? "yes" : (task.pipeline_stage === "ADD_REF" ? "missing" : "");
    for (const value of [task.asset_id, bodyState, headshotState]) {
      const cell = document.createElement("td");
      cell.textContent = value ?? "";
      row.append(cell);
    }
    row.addEventListener("click", () => selectManifestAsset(task.asset_id));
    manifestTaskBody.append(row);
  }
}

async function selectManifestAsset(assetId) {
  state.selectedManifestAssetId = Number(assetId);
  for (const row of manifestTaskBody.querySelectorAll("tr")) {
    row.classList.toggle("selected", Number(row.dataset.assetId) === state.selectedManifestAssetId);
  }
  const detail = await fetchJson(`/api/head-fitment-manifest/${state.selectedManifestAssetId}?${currentQuery().toString()}`);
  renderManifest(detail);
}

function clearManifest() {
  state.manifestDetail = null;
  manifestTitle.textContent = "Select a manifest task";
  bodyReferenceSelect.replaceChildren();
  headshotReferenceSelect.replaceChildren();
  bodyReferencePreview.textContent = "No body reference selected.";
  headshotReferencePreview.textContent = "No headshot selected.";
  manifestReferenceJson.textContent = "";
  saveManifestReferencesButton.disabled = true;
  manifestPrev.disabled = true;
  manifestNext.disabled = true;
}

function renderManifest(detail) {
  state.manifestDetail = detail;
  const asset = detail.asset;
  manifestTitle.textContent = `Asset ${asset.asset_id} | ${asset.body_view} / ${asset.head_view}`;
  fillReferenceSelect(bodyReferenceSelect, detail.body_reference_options || [], detail.selected_body_reference?.path || "");
  fillReferenceSelect(headshotReferenceSelect, detail.headshot_options || [], detail.selected_headshot?.path || "");
  manifestReferenceJson.textContent = JSON.stringify(detail.reference_files || [], null, 2);
  saveManifestReferencesButton.disabled = !detail.is_manifest_editable;
  updateManifestPreviews();
  updateManifestNavigation();
}

function fillReferenceSelect(select, options, selectedPath) {
  const items = [option("", "Select image...")];
  for (const item of options) {
    const choice = option(item.path, item.label || item.path);
    choice.disabled = !item.exists;
    items.push(choice);
  }
  select.replaceChildren(...items);
  select.value = selectedPath || "";
}

function renderImagePreview(container, path, emptyText) {
  container.replaceChildren();
  if (!path) {
    container.textContent = emptyText;
    return;
  }
  const image = document.createElement("img");
  image.alt = emptyText;
  image.src = `/api/file?path=${encodeURIComponent(path)}`;
  image.title = path;
  container.append(image);
}

function updateManifestPreviews() {
  renderImagePreview(bodyReferencePreview, bodyReferenceSelect.value, "No body reference selected.");
  renderImagePreview(headshotReferencePreview, headshotReferenceSelect.value, "No headshot selected.");
}

function updateManifestNavigation() {
  const index = state.manifestTasks.findIndex((task) => task.asset_id === state.selectedManifestAssetId);
  manifestPrev.disabled = index <= 0;
  manifestNext.disabled = index < 0 || index >= state.manifestTasks.length - 1;
}

async function saveManifestReferences() {
  if (!state.selectedManifestAssetId) {
    return;
  }
  showManifestMessage("Saving...");
  try {
    const payload = await fetchJson(
      `/api/head-fitment-manifest/${state.selectedManifestAssetId}/references?${currentQuery().toString()}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          body_reference_path: bodyReferenceSelect.value,
          headshot_path: headshotReferenceSelect.value,
        }),
      },
    );
    renderManifest(payload);
    showManifestMessage(payload.message || "References saved.");
    await loadAssets(state.selectedAssetId);
    await loadManifestTasks(state.selectedManifestAssetId);
  } catch (error) {
    showManifestMessage(error.message, "error");
  }
}

async function uploadHeadshotReference() {
  const file = headshotUpload.files?.[0];
  if (!file) {
    return;
  }
  showManifestMessage("Uploading headshot...");
  const params = currentQuery();
  params.set("filename", file.name);
  try {
    const payload = await fetchJson(`/api/head-fitment-manifest/headshots?${params.toString()}`, {
      method: "POST",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file,
    });
    showManifestMessage(`Uploaded ${payload.name}.`);
    await selectManifestAsset(state.selectedManifestAssetId);
    headshotReferenceSelect.value = payload.path;
    updateManifestPreviews();
  } catch (error) {
    showManifestMessage(error.message, "error");
  } finally {
    headshotUpload.value = "";
  }
}

characterSelect.addEventListener("change", async () => {
  state.character = characterSelect.value;
  state.phase = null;
  state.selectedAssetId = null;
  state.selectedPromptReviewAssetId = null;
  state.selectedRenderReviewAssetId = null;
  state.selectedManifestAssetId = null;
  updatePhaseSelect();
  await loadAssets();
  if (document.querySelector("#prompt-review-page").classList.contains("active")) {
    await loadPromptReviewTasks();
  }
  if (document.querySelector("#manifest-page").classList.contains("active")) {
    await loadManifestTasks();
  }
  if (document.querySelector("#render-review-page").classList.contains("active")) {
    await loadRenderReviewTasks();
  }
  if (document.querySelector("#ai-controls-page").classList.contains("active")) {
    await loadAiControls();
  }
  if (document.querySelector("#pipeline-controls-page").classList.contains("active")) {
    await loadPipelineControls();
  }
  if (document.querySelector("#render-console-page").classList.contains("active")) {
    await loadRenderConsoleTasks();
  }
});

phaseSelect.addEventListener("change", async () => {
  state.phase = phaseSelect.value;
  state.selectedAssetId = null;
  state.selectedPromptReviewAssetId = null;
  state.selectedRenderReviewAssetId = null;
  state.selectedManifestAssetId = null;
  await loadAssets();
  if (document.querySelector("#prompt-review-page").classList.contains("active")) {
    await loadPromptReviewTasks();
  }
  if (document.querySelector("#manifest-page").classList.contains("active")) {
    await loadManifestTasks();
  }
  if (document.querySelector("#render-review-page").classList.contains("active")) {
    await loadRenderReviewTasks();
  }
  if (document.querySelector("#ai-controls-page").classList.contains("active")) {
    await loadAiControls();
  }
  if (document.querySelector("#pipeline-controls-page").classList.contains("active")) {
    await loadPipelineControls();
  }
  if (document.querySelector("#render-console-page").classList.contains("active")) {
    await loadRenderConsoleTasks();
  }
});

for (const button of actionButtons) {
  button.addEventListener("click", () => runAssetAction(button.dataset.action));
}

promptSearch.addEventListener("input", renderPromptText);
copyPromptButton.addEventListener("click", () => copyText(state.promptReviewDetail?.prompt_text || "", "Prompt copied."));
copyCondensedButton.addEventListener("click", () => copyText(condensedText.value, "Condensed prompt copied."));
viewCondensedButton.addEventListener("click", () => condensedDialog.showModal());
generateLocalTestButton.addEventListener("click", () => runPromptReviewAction("local-test-render"));
promptApproveButton.addEventListener("click", () => runPromptReviewAction("approve"));
promptFailButton.addEventListener("click", () => runPromptReviewAction("fail"));
promptReviewPrev.addEventListener("click", () => {
  const index = state.promptReviewTasks.findIndex((task) => task.asset_id === state.selectedPromptReviewAssetId);
  if (index > 0) {
    selectPromptReviewAsset(state.promptReviewTasks[index - 1].asset_id);
  }
});
promptReviewNext.addEventListener("click", () => {
  const index = state.promptReviewTasks.findIndex((task) => task.asset_id === state.selectedPromptReviewAssetId);
  if (index >= 0 && index < state.promptReviewTasks.length - 1) {
    selectPromptReviewAsset(state.promptReviewTasks[index + 1].asset_id);
  }
});
renderPromoteButton.addEventListener("click", () => runRenderReviewAction("promote-to-locked"));
renderFailRenderButton.addEventListener("click", () => runRenderReviewAction("fail-to-render"));
renderFailRegenerateButton.addEventListener("click", () => runRenderReviewAction("fail-to-regenerate"));
renderReviewPrev.addEventListener("click", () => {
  const index = state.renderReviewTasks.findIndex((task) => task.asset_id === state.selectedRenderReviewAssetId);
  if (index > 0) {
    selectRenderReviewAsset(state.renderReviewTasks[index - 1].asset_id);
  }
});
renderReviewNext.addEventListener("click", () => {
  const index = state.renderReviewTasks.findIndex((task) => task.asset_id === state.selectedRenderReviewAssetId);
  if (index >= 0 && index < state.renderReviewTasks.length - 1) {
    selectRenderReviewAsset(state.renderReviewTasks[index + 1].asset_id);
  }
});
refreshAiControlsButton.addEventListener("click", loadAiControls);
harvestAiButton.addEventListener("click", () => runAiControlsAction("/api/ai-controls/harvest"));
activateProxyStopButton.addEventListener("click", () => runAiControlsAction("/api/ai-controls/stop"));
resumeProxyStopButton.addEventListener("click", () => runAiControlsAction("/api/ai-controls/resume"));
sendMonitorTestButton.addEventListener("click", () => {
  const params = new URLSearchParams({ instruction: monitorInstruction.value || "" });
  runAiControlsAction(`/api/ai-controls/monitor-test?${params.toString()}`);
});
openRenderConsoleTab.addEventListener("click", () => {
  document.querySelector('.tab[data-page="render-console"]').click();
});
automationForm.addEventListener("submit", saveAutomationSettings);
batchRenderResetButton.addEventListener("click", runBatchRenderReset);
renderConsoleRefresh.addEventListener("click", () => loadRenderConsoleTasks());
renderConsoleCopyPrompt.addEventListener("click", async () => {
  await navigator.clipboard.writeText(state.renderConsoleDetail?.prompt || "");
  showRenderConsoleMessage("Prompt copied.");
});
renderConsolePrev.addEventListener("click", () => {
  const index = state.renderConsoleTasks.findIndex((task) => task.ask_id === state.selectedRenderConsoleAskId);
  if (index > 0) {
    selectRenderConsoleTask(state.renderConsoleTasks[index - 1].ask_id);
  }
});
renderConsoleNext.addEventListener("click", () => {
  const index = state.renderConsoleTasks.findIndex((task) => task.ask_id === state.selectedRenderConsoleAskId);
  if (index >= 0 && index < state.renderConsoleTasks.length - 1) {
    selectRenderConsoleTask(state.renderConsoleTasks[index + 1].ask_id);
  }
});
renderConsolePasteZone.addEventListener("paste", (event) => {
  const blob = imageBlobFromPasteEvent(event);
  if (blob) {
    event.preventDefault();
    setRenderConsoleImageSelection(blob);
  }
});
renderConsolePasteZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  renderConsolePasteZone.classList.add("drag-over");
});
renderConsolePasteZone.addEventListener("dragleave", () => {
  renderConsolePasteZone.classList.remove("drag-over");
});
renderConsolePasteZone.addEventListener("drop", (event) => {
  event.preventDefault();
  renderConsolePasteZone.classList.remove("drag-over");
  setRenderConsoleImageSelection(event.dataTransfer?.files?.[0]);
});
renderConsoleFileInput.addEventListener("change", () => {
  setRenderConsoleImageSelection(renderConsoleFileInput.files?.[0]);
});
renderConsoleSaveImage.addEventListener("click", saveRenderConsoleImage);
renderConsoleFailTask.addEventListener("click", failRenderConsoleTask);
bodyReferenceSelect.addEventListener("change", updateManifestPreviews);
headshotReferenceSelect.addEventListener("change", updateManifestPreviews);
headshotUpload.addEventListener("change", uploadHeadshotReference);
saveManifestReferencesButton.addEventListener("click", saveManifestReferences);
manifestPrev.addEventListener("click", () => {
  const index = state.manifestTasks.findIndex((task) => task.asset_id === state.selectedManifestAssetId);
  if (index > 0) {
    selectManifestAsset(state.manifestTasks[index - 1].asset_id);
  }
});
manifestNext.addEventListener("click", () => {
  const index = state.manifestTasks.findIndex((task) => task.asset_id === state.selectedManifestAssetId);
  if (index >= 0 && index < state.manifestTasks.length - 1) {
    selectManifestAsset(state.manifestTasks[index + 1].asset_id);
  }
});

async function main() {
  setupTabs();
  try {
    await loadContext();
    await loadAssets();
  } catch (error) {
    assetStatus.textContent = error.message;
  }
}

main();
