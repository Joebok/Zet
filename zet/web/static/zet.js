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
const renderConsoleLink = document.querySelector("#render-console-link");
const manualRenderCount = document.querySelector("#manual-render-count");
const manualRenderTableBody = document.querySelector("#manual-render-table tbody");
const monitorRequestTableBody = document.querySelector("#monitor-request-table tbody");
const monitorResponseTableBody = document.querySelector("#monitor-response-table tbody");

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
      document.querySelector("#prompt-review-page").classList.toggle("active", page === "prompt-review");
      document.querySelector("#render-review-page").classList.toggle("active", page === "render-review");
      document.querySelector("#ai-controls-page").classList.toggle("active", page === "ai-controls");
      document
        .querySelector("#placeholder-page")
        .classList.toggle("active", !["assets", "prompt-review", "render-review", "ai-controls"].includes(page));
      placeholderTitle.textContent = button.textContent;
      if (page === "prompt-review") {
        loadPromptReviewTasks();
      }
      if (page === "render-review") {
        loadRenderReviewTasks();
      }
      if (page === "ai-controls") {
        loadAiControls();
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
  renderConsoleLink.href = payload.render_console_url || "#";
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

characterSelect.addEventListener("change", async () => {
  state.character = characterSelect.value;
  state.phase = null;
  state.selectedAssetId = null;
  state.selectedPromptReviewAssetId = null;
  state.selectedRenderReviewAssetId = null;
  updatePhaseSelect();
  await loadAssets();
  if (document.querySelector("#prompt-review-page").classList.contains("active")) {
    await loadPromptReviewTasks();
  }
  if (document.querySelector("#render-review-page").classList.contains("active")) {
    await loadRenderReviewTasks();
  }
  if (document.querySelector("#ai-controls-page").classList.contains("active")) {
    await loadAiControls();
  }
});

phaseSelect.addEventListener("change", async () => {
  state.phase = phaseSelect.value;
  state.selectedAssetId = null;
  state.selectedPromptReviewAssetId = null;
  state.selectedRenderReviewAssetId = null;
  await loadAssets();
  if (document.querySelector("#prompt-review-page").classList.contains("active")) {
    await loadPromptReviewTasks();
  }
  if (document.querySelector("#render-review-page").classList.contains("active")) {
    await loadRenderReviewTasks();
  }
  if (document.querySelector("#ai-controls-page").classList.contains("active")) {
    await loadAiControls();
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
