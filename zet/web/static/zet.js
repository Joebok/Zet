const state = {
  characters: [],
  phasesByCharacter: {},
  onboardingStatuses: {},
  headerPreviews: {},
  onboardingOptions: { species_ancestry: [], gender_presentation: [] },
  character: null,
  phase: null,
  assets: [],
  selectedAssetId: null,
  assetFilters: {
    todoOnly: false,
    hideBaseImages: false,
    pipeline: "",
  },
  assetDetailMode: "status",
  assetDetail: null,
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
  turnaroundRows: [],
  selectedTurnaroundId: null,
  selectedAuxiliaryTurnaroundId: null,
  turnaroundDetail: null,
  manifestTasks: [],
  selectedManifestAssetId: null,
  manifestDetail: null,
  selectedSource: null,
  sourceEditor: null,
  identityKeys: [],
  identityKeyMode: "list",
  selectedIdentityKeyId: null,
  identityKeySourceAssetId: null,
  identityKeyPreview: null,
  costumes: [],
  selectedCostumeSlug: null,
  expressionAssets: [],
  expressionDefinitions: [],
  expressionIdentityKeys: [],
  selectedExpressionAssetId: null,
  auxiliaryResources: [],
  selectedAuxiliaryResourceId: null,
  auxiliaryResourceImageBlob: null,
  phaseComparison: {
    character: "",
    leftPhase: "",
    rightPhase: "",
    pipeline: "",
    leftCostume: "",
    rightCostume: "",
    selectedIndex: 0,
    selectedSlotKey: "",
    rows: [],
  },
};

const LAST_CONTEXT_STORAGE_KEY = "zet:last-character-phase";
const HIDE_BASE_IMAGES_STORAGE_KEY = "zet:asset-hide-base-images";

const characterSelect = document.querySelector("#character-select");
const phaseSelect = document.querySelector("#phase-select");
const newCharacterButton = document.querySelector("#new-character");
const newPhaseButton = document.querySelector("#new-phase");
const headerFitmentPreview = document.querySelector("#header-fitment-preview");
const toolbarSettingsButton = document.querySelector("#toolbar-settings-button");
const toolbarSettingsMenu = document.querySelector("#toolbar-settings-menu");
const toolbarHarvestAi = document.querySelector("#toolbar-harvest-ai");
const onboardingStatus = document.querySelector("#onboarding-status");
const onboardingMessage = document.querySelector("#onboarding-message");
const onboardingCharacter = document.querySelector("#onboarding-character");
const onboardingPhase = document.querySelector("#onboarding-phase");
const onboardingSpecies = document.querySelector("#onboarding-species");
const onboardingGender = document.querySelector("#onboarding-gender");
const onboardingArtStyle = document.querySelector("#onboarding-art-style");
const onboardingSaveDraft = document.querySelector("#onboarding-save-draft");
const onboardingDownloadTemplate = document.querySelector("#onboarding-download-template");
const onboardingCopyGptPrompt = document.querySelector("#onboarding-copy-gpt-prompt");
const onboardingGptPrompt = document.querySelector("#onboarding-gpt-prompt");
const onboardingTemplateFile = document.querySelector("#onboarding-template-file");
const onboardingUploadTemplate = document.querySelector("#onboarding-upload-template");
const onboardingTitle = document.querySelector("#onboarding-title");
const onboardingStatusList = document.querySelector("#onboarding-status-list");
const onboardingValidation = document.querySelector("#onboarding-validation");
const assetFilterTodo = document.querySelector("#asset-filter-todo");
const assetFilterHideBase = document.querySelector("#asset-filter-hide-base");
const assetFilterPipeline = document.querySelector("#asset-filter-pipeline");
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
const assetDetailStatusMode = document.querySelector("#asset-detail-status-mode");
const assetDetailImageMode = document.querySelector("#asset-detail-image-mode");
const assetStatusDetail = document.querySelector("#asset-status-detail");
const assetLockedDetail = document.querySelector("#asset-locked-detail");
const assetLockedImage = document.querySelector("#asset-locked-image");
const assetLockedPath = document.querySelector("#asset-locked-path");
const createIdentityFromAssetButton = document.querySelector("#create-identity-from-asset");
const openCharacterTemplateButton = document.querySelector("#open-character-template");
const openGoverningTemplateButton = document.querySelector("#open-governing-template");
const assetNoteDialog = document.querySelector("#asset-note-dialog");
const assetNoteTitle = document.querySelector("#asset-note-title");
const assetNoteText = document.querySelector("#asset-note-text");
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
const sourceInspectorEmpty = document.querySelector("#source-inspector-empty");
const sourceInspectorDetail = document.querySelector("#source-inspector-detail");
const sourceInspectorText = document.querySelector("#source-inspector-text");
const sourceOpenEditor = document.querySelector("#source-open-editor");
const condensedDialog = document.querySelector("#condensed-dialog");
const condensedText = document.querySelector("#condensed-text");
const copyCondensedButton = document.querySelector("#copy-condensed");
const promptDiffDialog = document.querySelector("#prompt-diff-dialog");
const promptDiffSummary = document.querySelector("#prompt-diff-summary");
const promptDiffOld = document.querySelector("#prompt-diff-old");
const promptDiffNew = document.querySelector("#prompt-diff-new");
const renderReviewStatus = document.querySelector("#render-review-status");
const renderReviewTaskBody = document.querySelector("#render-review-task-table tbody");
const renderReviewPrev = document.querySelector("#render-review-prev");
const renderReviewNext = document.querySelector("#render-review-next");
const renderReviewTitle = document.querySelector("#render-review-title");
const renderReviewPath = document.querySelector("#render-review-path");
const renderReviewMessage = document.querySelector("#render-review-message");
const candidateRender = document.querySelector("#candidate-render");
const lockedRender = document.querySelector("#locked-render");
const renderPromoteButton = document.querySelector("#render-promote");
const renderFailRenderButton = document.querySelector("#render-fail-render");
const renderFailRegenerateButton = document.querySelector("#render-fail-regenerate");
const renderStageText = document.querySelector("#render-stage-text");
const renderHistoryText = document.querySelector("#render-history-text");
const renderReviewComment = document.querySelector("#render-review-comment");
const renderCommentSave = document.querySelector("#render-comment-save");
const aiControlsStatus = document.querySelector("#ai-controls-status");
const aiControlsMessage = document.querySelector("#ai-controls-message");
const proxyStopState = document.querySelector("#proxy-stop-state");
const harvestAiButton = document.querySelector("#harvest-ai");
const archiveHarvestedAiButton = document.querySelector("#archive-harvested-ai");
const refreshAiControlsButton = document.querySelector("#refresh-ai-controls");
const activateProxyStopButton = document.querySelector("#activate-proxy-stop");
const resumeProxyStopButton = document.querySelector("#resume-proxy-stop");
const dumpAiQueueButton = document.querySelector("#dump-ai-queue");
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
const settingAiPromptReviewModel = document.querySelector("#setting-ai-prompt-review-model");
const settingAiPromptReviewFile = document.querySelector("#setting-ai-prompt-review-file");
const settingRenderBackend = document.querySelector("#setting-render-backend");
const pipelineConfigPaths = document.querySelector("#pipeline-config-paths");
const projectConfigTableBody = document.querySelector("#project-config-table tbody");
const pipelineStageTableBody = document.querySelector("#pipeline-stage-table tbody");
const promptReviewPipeline = document.querySelector("#prompt-review-pipeline");
const promptReviewMode = document.querySelector("#prompt-review-mode");
const promptReviewSave = document.querySelector("#prompt-review-save");
const batchRenderPipeline = document.querySelector("#batch-render-pipeline");
const batchIncludeLocked = document.querySelector("#batch-include-locked");
const batchRenderResetButton = document.querySelector("#batch-render-reset");
const batchRenderResultTableBody = document.querySelector("#batch-render-result-table tbody");
const sourceEditorStatus = document.querySelector("#source-editor-status");
const sourceEditorMessage = document.querySelector("#source-editor-message");
const sourceEditorWarning = document.querySelector("#source-editor-warning");
const sourceEditorTitle = document.querySelector("#source-editor-title");
const sourceEditorSave = document.querySelector("#source-editor-save");
const sourceEditorRecompile = document.querySelector("#source-editor-recompile");
const sourceEditorClearReviewAids = document.querySelector("#source-editor-clear-review-aids");
const sourceEditorMeta = document.querySelector("#source-editor-meta");
const sourceEditorText = document.querySelector("#source-editor-text");
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
const renderConsoleHelperPanel = document.querySelector("#render-console-helper-panel");
const renderConsoleHelperText = document.querySelector("#render-console-helper-text");
const renderConsoleSaveHelper = document.querySelector("#render-console-save-helper");
const renderConsoleCopyHelper = document.querySelector("#render-console-copy-helper");
const renderConsolePrompt = document.querySelector("#render-console-prompt");
const renderConsolePasteZone = document.querySelector("#render-console-paste-zone");
const renderConsoleFileInput = document.querySelector("#render-console-file-input");
const renderConsoleImagePreview = document.querySelector("#render-console-image-preview");
const renderConsoleSaveImage = document.querySelector("#render-console-save-image");
const renderConsoleSaveStatus = document.querySelector("#render-console-save-status");
const renderConsoleAnswerComment = document.querySelector("#render-console-answer-comment");
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
const turnaroundStatus = document.querySelector("#turnaround-status");
const turnaroundMessage = document.querySelector("#turnaround-message");
const turnaroundTableBody = document.querySelector("#turnaround-table tbody");
const turnaroundTitle = document.querySelector("#turnaround-title");
const turnaroundCandidate = document.querySelector("#turnaround-candidate");
const turnaroundLocked = document.querySelector("#turnaround-locked");
const turnaroundSourceAssets = document.querySelector("#turnaround-source-assets");
const turnaroundPaths = document.querySelector("#turnaround-paths");
const turnaroundDetectionTolerance = document.querySelector("#turnaround-detection-tolerance");
const turnaroundPartialLabel = document.querySelector("#turnaround-partial-label");
const turnaroundPartialPercent = document.querySelector("#turnaround-partial-percent");
const turnaroundSavePartial = document.querySelector("#turnaround-save-partial");
const turnaroundAuxTableBody = document.querySelector("#turnaround-aux-table tbody");
const identityKeyStatus = document.querySelector("#identity-key-status");
const identityKeyMessage = document.querySelector("#identity-key-message");
const identityKeyTableBody = document.querySelector("#identity-key-table tbody");
const identityKeyShowList = document.querySelector("#identity-key-show-list");
const identityKeyTitle = document.querySelector("#identity-key-title");
const identityKeyLabel = document.querySelector("#identity-key-label");
const identityKeyPercent = document.querySelector("#identity-key-percent");
const identityKeyCreatePreview = document.querySelector("#identity-key-create-preview");
const identityKeySave = document.querySelector("#identity-key-save");
const identityKeyOriginal = document.querySelector("#identity-key-original");
const identityKeyPreview = document.querySelector("#identity-key-preview");
const costumeStatus = document.querySelector("#costume-status");
const costumeMessage = document.querySelector("#costume-message");
const costumeTableBody = document.querySelector("#costume-table tbody");
const costumeAddNew = document.querySelector("#costume-add-new");
const costumeFormTitle = document.querySelector("#costume-form-title");
const costumeName = document.querySelector("#costume-name");
const costumeTemplateFileWrap = document.querySelector("#costume-template-file-wrap");
const costumeTemplateFile = document.querySelector("#costume-template-file");
const costumeCreate = document.querySelector("#costume-create");
const costumePreviewSection = document.querySelector("#costume-preview-section");
const costumePreview = document.querySelector("#costume-preview");
const expressionStatus = document.querySelector("#expression-status");
const expressionMessage = document.querySelector("#expression-message");
const expressionTableBody = document.querySelector("#expression-table tbody");
const expressionAddNew = document.querySelector("#expression-add-new");
const expressionFormTitle = document.querySelector("#expression-form-title");
const expressionLabel = document.querySelector("#expression-label");
const expressionIdentityKey = document.querySelector("#expression-identity-key");
const expressionDefinitionFileWrap = document.querySelector("#expression-definition-file-wrap");
const expressionDefinitionFile = document.querySelector("#expression-definition-file");
const expressionCreate = document.querySelector("#expression-create");
const expressionPreviewSection = document.querySelector("#expression-preview-section");
const expressionPreview = document.querySelector("#expression-preview");
const auxResourceStatus = document.querySelector("#aux-resource-status");
const auxResourceMessage = document.querySelector("#aux-resource-message");
const auxResourceCategory = document.querySelector("#aux-resource-category");
const auxResourceSearch = document.querySelector("#aux-resource-search");
const auxResourceShowThumbnails = document.querySelector("#aux-resource-show-thumbnails");
const auxResourceTable = document.querySelector("#aux-resource-table");
const auxResourceTableBody = document.querySelector("#aux-resource-table tbody");
const auxResourceAdd = document.querySelector("#aux-resource-add");
const auxResourceFormTitle = document.querySelector("#aux-resource-form-title");
const auxResourceFormCategory = document.querySelector("#aux-resource-form-category");
const auxResourceLabel = document.querySelector("#aux-resource-label");
const auxResourcePasteZone = document.querySelector("#aux-resource-paste-zone");
const auxResourceFileInput = document.querySelector("#aux-resource-file-input");
const auxResourceImagePreview = document.querySelector("#aux-resource-image-preview");
const auxResourceSave = document.querySelector("#aux-resource-save");
const auxResourceClear = document.querySelector("#aux-resource-clear");
const auxResourceTag = document.querySelector("#aux-resource-tag");
const auxResourceCopyTag = document.querySelector("#aux-resource-copy-tag");
const phaseComparisonStatus = document.querySelector("#phase-comparison-status");
const phaseComparisonMessage = document.querySelector("#phase-comparison-message");
const phaseComparisonCharacter = document.querySelector("#phase-comparison-character");
const phaseComparisonLeftPhase = document.querySelector("#phase-comparison-left-phase");
const phaseComparisonRightPhase = document.querySelector("#phase-comparison-right-phase");
const phaseComparisonPipeline = document.querySelector("#phase-comparison-pipeline");
const phaseComparisonLeftCostumeWrap = document.querySelector("#phase-comparison-left-costume-wrap");
const phaseComparisonRightCostumeWrap = document.querySelector("#phase-comparison-right-costume-wrap");
const phaseComparisonLeftCostume = document.querySelector("#phase-comparison-left-costume");
const phaseComparisonRightCostume = document.querySelector("#phase-comparison-right-costume");
const phaseComparisonPrev = document.querySelector("#phase-comparison-prev");
const phaseComparisonNext = document.querySelector("#phase-comparison-next");
const phaseComparisonMeta = document.querySelector("#phase-comparison-meta");
const phaseComparisonLeftTitle = document.querySelector("#phase-comparison-left-title");
const phaseComparisonRightTitle = document.querySelector("#phase-comparison-right-title");
const phaseComparisonLeftImage = document.querySelector("#phase-comparison-left-image");
const phaseComparisonRightImage = document.querySelector("#phase-comparison-right-image");
const phaseComparisonLeftMeta = document.querySelector("#phase-comparison-left-meta");
const phaseComparisonRightMeta = document.querySelector("#phase-comparison-right-meta");

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

function fileUrl(path, cacheKey = "") {
  const params = new URLSearchParams({ path });
  if (cacheKey) {
    params.set("v", cacheKey);
  }
  return `/api/file?${params.toString()}`;
}

function downloadFileUrl(path) {
  const params = new URLSearchParams({ path, download: "true" });
  return `/api/file?${params.toString()}`;
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

function showSourceEditorMessage(message, kind = "info") {
  sourceEditorMessage.textContent = message || "";
  sourceEditorMessage.className = `action-message ${kind}`;
  sourceEditorMessage.hidden = !message;
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

function showTurnaroundMessage(message, kind = "info") {
  turnaroundMessage.textContent = message || "";
  turnaroundMessage.className = `action-message ${kind}`;
  turnaroundMessage.hidden = !message;
}

function showIdentityKeyMessage(message, kind = "info") {
  identityKeyMessage.textContent = message || "";
  identityKeyMessage.className = `action-message ${kind}`;
  identityKeyMessage.hidden = !message;
}

function showCostumeMessage(message, kind = "info") {
  costumeMessage.textContent = message || "";
  costumeMessage.className = `action-message ${kind}`;
  costumeMessage.hidden = !message;
}

function showExpressionMessage(message, kind = "info") {
  expressionMessage.textContent = message || "";
  expressionMessage.className = `action-message ${kind}`;
  expressionMessage.hidden = !message;
}

function showAuxResourceMessage(message, kind = "info") {
  auxResourceMessage.textContent = message || "";
  auxResourceMessage.className = `action-message ${kind}`;
  auxResourceMessage.hidden = !message;
}

function showPhaseComparisonMessage(message, kind = "info") {
  phaseComparisonMessage.textContent = message || "";
  phaseComparisonMessage.className = `action-message ${kind}`;
  phaseComparisonMessage.hidden = !message;
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

function setSelectValueCaseInsensitive(select, value) {
  const raw = String(value || "");
  const match = Array.from(select.options).find((item) => item.value.toLowerCase() === raw.toLowerCase());
  select.value = match ? match.value : raw;
}

function currentQuery() {
  return new URLSearchParams({ character: state.character, phase: state.phase });
}

function loadStoredContext() {
  try {
    const raw = window.localStorage.getItem(LAST_CONTEXT_STORAGE_KEY);
    if (!raw) {
      return { character: "", phase: "" };
    }
    const data = JSON.parse(raw);
    return {
      character: String(data?.character || ""),
      phase: String(data?.phase || ""),
    };
  } catch {
    return { character: "", phase: "" };
  }
}

function saveStoredContext() {
  try {
    window.localStorage.setItem(
      LAST_CONTEXT_STORAGE_KEY,
      JSON.stringify({ character: state.character || "", phase: state.phase || "" }),
    );
  } catch {
    // Ignore storage failures and keep the app usable.
  }
}

function loadStoredAssetFilters() {
  // Keep the base-image visibility preference across browser sessions.
  state.assetFilters.hideBaseImages = window.localStorage.getItem(HIDE_BASE_IMAGES_STORAGE_KEY) === "true";
  assetFilterHideBase.checked = state.assetFilters.hideBaseImages;
}

function saveStoredAssetFilters() {
  window.localStorage.setItem(HIDE_BASE_IMAGES_STORAGE_KEY, state.assetFilters.hideBaseImages ? "true" : "false");
}

async function loadContext() {
  const payload = await fetchJson("/api/context");
  const stored = loadStoredContext();
  state.characters = payload.characters || [];
  state.phasesByCharacter = payload.phases_by_character || {};
  state.onboardingStatuses = payload.onboarding_statuses || {};
  state.headerPreviews = payload.header_previews || {};
  state.onboardingOptions = payload.onboarding_options || { species_ancestry: [], gender_presentation: [] };
  const preferredCharacter = state.character || stored.character;
  state.character = preferredCharacter && state.characters.includes(preferredCharacter) ? preferredCharacter : payload.default_character;
  const phases = state.phasesByCharacter[state.character] || [];
  const preferredPhase = state.phase || stored.phase;
  state.phase = preferredPhase && phases.includes(preferredPhase) ? preferredPhase : payload.default_phase;
  setSelectOptions(characterSelect, state.characters);
  characterSelect.value = state.character || "";
  setSelectOptions(onboardingSpecies, state.onboardingOptions.species_ancestry || []);
  setSelectOptions(onboardingGender, state.onboardingOptions.gender_presentation || []);
  updatePhaseSelect();
  saveStoredContext();
  renderOnboarding();
}

function updateHeaderFitmentPreview() {
  // Show the locked Front-Left-3-4 head-fitment image when this phase has one.
  const preview = state.headerPreviews?.[state.character]?.[state.phase] || null;
  if (preview?.image_path) {
    const cacheKey = [
      state.character || "",
      state.phase || "",
      preview.asset_id || "",
      preview.updated_at || "",
      Date.now().toString(),
    ].join("|");
    headerFitmentPreview.src = fileUrl(preview.image_path, cacheKey);
    headerFitmentPreview.hidden = false;
  } else {
    headerFitmentPreview.hidden = true;
    headerFitmentPreview.removeAttribute("src");
  }
}

function updatePhaseSelect() {
  const phases = state.phasesByCharacter[state.character] || [];
  setSelectOptions(phaseSelect, phases);
  if (!phases.includes(state.phase)) {
    state.phase = phases[0] || null;
  }
  phaseSelect.value = state.phase || "";
  saveStoredContext();
  updateHeaderFitmentPreview();
}

function selectedOnboardingStatus() {
  return state.onboardingStatuses?.[state.character]?.[state.phase] || null;
}

function selectedPhaseReady() {
  const status = selectedOnboardingStatus();
  return !status || status.complete;
}

function showOnboardingMessage(message, kind = "info") {
  onboardingMessage.hidden = false;
  onboardingMessage.textContent = message;
  onboardingMessage.dataset.kind = kind;
}

function onboardingHelperPrompt(templatePath = "") {
  const character = onboardingCharacter.value || state.character || "[Character Name]";
  const phase = onboardingPhase.value || state.phase || "[Character Phase]";
  const species = onboardingSpecies.value || "[Species / Ancestry]";
  const gender = onboardingGender.value || "[Gender Presentation]";
  const artStyle = onboardingArtStyle.value || "[Canonical Art Style]";
  return `I am building a structured Zet character image template for ${character}, phase ${phase}.

I will attach:
- The draft markdown file named Character_Image_Template.md${templatePath ? ` from ${templatePath}` : ""}
- One or more reference images for the character/phase

Your task:
Fill out the Character_Image_Template.md using the attached reference image(s) and the metadata below, then return the completed template as a downloadable markdown file named Character_Image_Template.md.

Metadata to preserve exactly:
- Character Name: ${character}
- Character Phase: ${phase}
- Species / Ancestry: ${species}
- Gender Presentation: ${gender}
- Canonical Art Style: ${artStyle}

Hard rules:
- Do not remove, rename, reorder, or alter any ZET compiler markers.
- Preserve every line shaped like <!-- ZET:BEGIN SECTION_NAME --> and <!-- ZET:END SECTION_NAME --> exactly.
- Keep all section names exactly as written.
- Do not delete empty sections; fill useful sections, but leave uncertain sections empty rather than inventing facts.
- Do not add markdown fences around the final file.
- Do not summarize the file in the final answer.
- Return the completed markdown file itself, suitable for saving directly as Character_Image_Template.md.
- Keep prompt language factual, visual, and render-facing.
- Avoid story, personality, mood, scene action, or narrative unless the section explicitly asks for picaresque/flavor text.
- Preserve the template's existing structure, headings, bullet style, and metadata fields.

Content guidance:
- Use the reference image(s) to describe visible body, head, face, hair, ears, costume-neutral appearance, proportions, silhouette, and view-specific notes.
- Keep the character identity stable across all sections.
- If a detail is not visible or cannot be confidently inferred, write a cautious generic rule or leave that section blank.
- Do not invent props, weapons, costume details, injuries, markings, or accessories that are not visible or explicitly provided.
- Keep species/ancestry-specific traits consistent with ${species}.

Before returning the file:
- Check that every ZET BEGIN marker has the matching ZET END marker.
- Check that no compiler marker text has changed.
- Check that the top metadata fields still match the values above.
- Check that the result is plain markdown, not a chat explanation.`;
}

function updateOnboardingHelperPrompt(templatePath = "") {
  onboardingGptPrompt.value = onboardingHelperPrompt(templatePath || selectedOnboardingStatus()?.template_path || "");
  onboardingCopyGptPrompt.disabled = !onboardingGptPrompt.value.trim();
}

function renderOnboarding() {
  const status = selectedOnboardingStatus();
  const ready = selectedPhaseReady();
  for (const button of document.querySelectorAll(".workflow-tab")) {
    button.disabled = !ready;
  }
  const onboardingTab = document.querySelector('.tab[data-page="onboarding"]');
  onboardingTab.hidden = ready;
  if (!ready && !document.querySelector("#onboarding-page").classList.contains("active")) {
    activatePage("onboarding");
  }
  onboardingStatus.textContent = ready ? "Complete" : "Waiting for setup";
  const characterName = status?.character_name || state.character || "";
  const phaseName = state.phase || "";
  onboardingTitle.textContent = characterName && phaseName ? `${characterName} / ${phaseName}` : "Character Setup";
  onboardingCharacter.value = characterName;
  onboardingPhase.value = phaseName;
  setSelectValueCaseInsensitive(onboardingSpecies, status?.species_ancestry || onboardingSpecies.value);
  setSelectValueCaseInsensitive(onboardingGender, status?.gender_presentation || onboardingGender.value);
  onboardingArtStyle.value = status?.canonical_art_style || onboardingArtStyle.value || "";
  onboardingDownloadTemplate.hidden = !status?.template_path;
  if (status?.template_path) {
    onboardingDownloadTemplate.href = downloadFileUrl(status.template_path);
    onboardingDownloadTemplate.download = "Character_Image_Template.md";
  }
  updateOnboardingHelperPrompt(status?.template_path || "");
  onboardingStatusList.replaceChildren();
  if (status) {
    const rows = [
      ["Template", status.template_exists ? "present" : "missing"],
      ["Pipelines", status.pipelines_exists ? "present" : "missing"],
      ["Assets", status.assets_exists ? "present" : "missing"],
      ["Path", status.template_path || ""],
    ];
    for (const [label, value] of rows) {
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      dd.textContent = value;
      onboardingStatusList.append(dt, dd);
    }
    const lines = [...(status.messages || []), ...(status.validation_errors || [])];
    onboardingValidation.textContent = lines.length ? lines.join("\n") : "Template is valid.";
  } else {
    onboardingValidation.textContent = "Create a new character or phase to begin.";
  }
}

async function refreshCurrentContext() {
  await loadContext();
  if (selectedPhaseReady()) {
    await loadAssets();
  }
}

async function prefillOnboarding(character, sourcePhase = "") {
  const params = new URLSearchParams({ character, source_phase: sourcePhase });
  const payload = await fetchJson(`/api/onboarding/prefill?${params.toString()}`);
  const prefill = payload.prefill || {};
  onboardingCharacter.value = prefill.character || character || "";
  setSelectValueCaseInsensitive(onboardingSpecies, prefill.species_ancestry || onboardingSpecies.value);
  setSelectValueCaseInsensitive(onboardingGender, prefill.gender_presentation || onboardingGender.value);
  onboardingArtStyle.value = prefill.canonical_art_style || onboardingArtStyle.value;
}

function startNewPhase() {
  onboardingCharacter.value = state.character || "";
  onboardingPhase.value = "";
  onboardingArtStyle.value = "";
  prefillOnboarding(state.character || "", state.phase || "").catch((error) => showOnboardingMessage(error.message, "error"));
  activatePage("onboarding");
}

function startNewCharacter() {
  onboardingCharacter.value = "";
  onboardingPhase.value = "Adult";
  onboardingArtStyle.value = "";
  if (onboardingSpecies.options.length) {
    onboardingSpecies.selectedIndex = 0;
  }
  if (onboardingGender.options.length) {
    onboardingGender.selectedIndex = 0;
  }
  activatePage("onboarding");
}

async function saveOnboardingDraft() {
  try {
    const payload = await fetchJson("/api/onboarding/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        character: onboardingCharacter.value,
        phase: onboardingPhase.value,
        species_ancestry: onboardingSpecies.value,
        gender_presentation: onboardingGender.value,
        canonical_art_style: onboardingArtStyle.value,
        source_phase: state.character === onboardingCharacter.value ? state.phase : "",
      }),
    });
    state.character = payload.draft?.character || onboardingCharacter.value;
    state.phase = payload.draft?.phase || onboardingPhase.value;
    showOnboardingMessage(payload.message || "Draft saved.");
    await refreshCurrentContext();
    const templatePath = payload.draft?.template_path;
    if (templatePath) {
      onboardingDownloadTemplate.href = downloadFileUrl(templatePath);
      onboardingDownloadTemplate.download = "Character_Image_Template.md";
      onboardingDownloadTemplate.hidden = false;
      updateOnboardingHelperPrompt(templatePath);
    }
  } catch (error) {
    showOnboardingMessage(error.message, "error");
  }
}

async function uploadOnboardingTemplate() {
  const file = onboardingTemplateFile.files?.[0];
  if (!file) {
    showOnboardingMessage("Choose a Character_Image_Template.md file first.", "error");
    return;
  }
  try {
    const params = new URLSearchParams({ character: state.character, phase: state.phase });
    const payload = await fetchJson(`/api/onboarding/template?${params.toString()}`, {
      method: "POST",
      headers: { "Content-Type": file.type || "text/markdown" },
      body: file,
    });
    showOnboardingMessage(payload.message || "Template uploaded.");
    await refreshCurrentContext();
    renderOnboarding();
    if (payload.status?.complete) {
      activatePage("assets");
    }
  } catch (error) {
    showOnboardingMessage(error.message, "error");
  } finally {
    onboardingTemplateFile.value = "";
  }
}

async function loadAssets(preferredAssetId = null) {
  if (!state.character || !state.phase) {
    assetStatus.textContent = "No character/phase selected.";
    return;
  }
  if (!selectedPhaseReady()) {
    assetStatus.textContent = "Onboarding must be completed first.";
    state.assets = [];
    renderAssetTable();
    clearDetail();
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
}

function filteredAssets() {
  return state.assets.filter((asset) => {
    if (state.assetFilters.todoOnly && asset.asset_state === "LOCKED") {
      return false;
    }
    if (state.assetFilters.hideBaseImages && isBaseImageAsset(asset)) {
      return false;
    }
    if (state.assetFilters.pipeline && asset.pipeline !== state.assetFilters.pipeline) {
      return false;
    }
    return true;
  });
}

function isBaseImageAsset(asset) {
  return (
    ["Body-Reference", "Head-Fitment", "Character-Assembly"].includes(asset?.pipeline || "") &&
    asset?.asset_state === "LOCKED"
  );
}

function visibleTodoAssets() {
  return filteredAssets().filter((asset) => asset.asset_state !== "LOCKED" && asset.pipeline_stage !== "LOCKED");
}

function renderAssetTable() {
  assetTableBody.replaceChildren();
  const visibleAssets = filteredAssets();
  const visibleIds = new Set(visibleAssets.map((asset) => asset.asset_id));
  if (state.selectedAssetId && !visibleIds.has(state.selectedAssetId)) {
    state.selectedAssetId = visibleAssets[0]?.asset_id || null;
    if (state.selectedAssetId) {
      selectAsset(state.selectedAssetId);
    } else {
      clearDetail();
    }
  }
  assetStatus.textContent = `${visibleAssets.length} of ${state.assets.length} asset(s)`;
  for (const asset of visibleAssets) {
    const row = document.createElement("tr");
    row.dataset.assetId = asset.asset_id;
    if (asset.asset_id === state.selectedAssetId) {
      row.classList.add("selected");
    }
    const values = [
      asset.asset_id,
      asset.pipeline,
      asset.body_view,
      asset.costume,
      asset.asset_state,
      asset.pipeline_stage_display,
      asset.actor,
      asset.ai_state,
      asset.has_render_review_comment ? "NOTE" : "",
      asset.updated_at_display,
    ];
    for (const [index, value] of values.entries()) {
      const cell = document.createElement("td");
      if (index === 8 && value) {
        const badge = document.createElement("span");
        badge.className = "note-badge";
        badge.textContent = "NOTE";
        badge.title = asset.render_review_comment || "";
        badge.addEventListener("click", (event) => {
          event.stopPropagation();
          showAssetNote(asset);
        });
        cell.append(badge);
      } else {
        cell.textContent = value ?? "";
      }
      row.append(cell);
    }
    row.addEventListener("click", () => selectAsset(asset.asset_id));
    assetTableBody.append(row);
  }
}

function showAssetNote(asset) {
  assetNoteTitle.textContent = `Asset ${asset.asset_id} Note`;
  assetNoteText.value = asset.render_review_comment || "";
  if (assetNoteDialog.showModal) {
    assetNoteDialog.showModal();
  } else {
    alert(asset.render_review_comment || "");
  }
}

function applyAssetFilters() {
  state.assetFilters.todoOnly = assetFilterTodo.checked;
  state.assetFilters.hideBaseImages = assetFilterHideBase.checked;
  state.assetFilters.pipeline = assetFilterPipeline.value;
  saveStoredAssetFilters();
  renderAssetTable();
  updateActionButtons(state.assetDetail);
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
  state.assetDetail = null;
  detailTitle.textContent = "Select an asset";
  detailSummary.textContent = "";
  assetJson.textContent = "";
  pathList.replaceChildren();
  stageText.textContent = "";
  historyText.textContent = "";
  assetLockedImage.textContent = "No locked image.";
  assetLockedPath.textContent = "";
  openCharacterTemplateButton.disabled = true;
  openGoverningTemplateButton.disabled = true;
  updateAssetDetailMode();
  updateActionButtons(null);
}

function renderDetail(detail) {
  state.assetDetail = detail;
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
  renderAssetLockedImage(detail);
  updateAssetTemplateButtons(detail);
  updateAssetDetailMode();
  updateActionButtons(detail);
}

function updateAssetTemplateButtons(detail) {
  const asset = detail?.asset || {};
  openCharacterTemplateButton.disabled = !asset.character_template_source?.source_path;
  openGoverningTemplateButton.disabled = !asset.governing_template_source?.source_path;
}

function updateAssetDetailMode() {
  const imageMode = state.assetDetailMode === "locked";
  assetDetailStatusMode.classList.toggle("selected", !imageMode);
  assetDetailImageMode.classList.toggle("selected", imageMode);
  assetStatusDetail.hidden = imageMode;
  assetLockedDetail.hidden = !imageMode;
}

function setAssetDetailMode(mode) {
  state.assetDetailMode = mode === "locked" ? "locked" : "status";
  updateAssetDetailMode();
}

function renderAssetLockedImage(detail) {
  assetLockedImage.replaceChildren();
  const path = detail.paths?.locked_image_path || "";
  const exists = Boolean(detail.exists?.locked_image);
  assetLockedPath.textContent = path;
  if (!exists || !path) {
    assetLockedImage.textContent = "No locked image.";
    return;
  }
  const image = document.createElement("img");
  image.alt = "Locked asset";
  image.src = fileUrl(path, detail.asset?.updated_at || Date.now().toString());
  image.title = path;
  assetLockedImage.append(image);
}

function updateActionButtons(detail) {
  const asset = detail?.asset || null;
  const candidateExists = Boolean(detail?.exists?.candidate_image);
  const lockedExists = Boolean(detail?.exists?.locked_image);
  const hasVisibleTodo = visibleTodoAssets().length > 0;
  for (const button of actionButtons) {
    const action = button.dataset.action;
    let enabled = Boolean(asset);
    if (action === "stage-ai-ask" || action === "retry-ai") {
      enabled = enabled && asset.actor === "AI_AGENT";
    }
    if (action === "run-current-worker") {
      enabled = hasVisibleTodo;
    }
    if (action === "promote-to-locked") {
      enabled = enabled && candidateExists;
    }
    button.disabled = !enabled;
  }
  createIdentityFromAssetButton.disabled = !(asset && asset.asset_state === "LOCKED" && asset.pipeline_stage === "LOCKED" && lockedExists);
}

function startIdentityKeyFromSelectedAsset() {
  const detail = state.assetDetail;
  if (!detail?.asset) {
    return;
  }
  state.identityKeyMode = "update";
  state.selectedIdentityKeyId = null;
  state.identityKeySourceAssetId = detail.asset.asset_id;
  state.identityKeyPreview = null;
  identityKeyLabel.value = "";
  identityKeyPercent.value = "100";
  activatePage("identity-keys");
  renderIdentityKeyUpdate({
    source_asset_id: detail.asset.asset_id,
    source_image_path: detail.paths?.locked_image_path || "",
    label: "",
    crop_percent: 100,
  });
}

async function runAssetAction(action) {
  if (action === "run-current-worker") {
    await advanceVisibleAssets();
    return;
  }
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

async function advanceVisibleAssets() {
  const visible = visibleTodoAssets();
  if (!visible.length) {
    showActionMessage("No displayed todo assets to advance.");
    updateActionButtons(state.assetDetail);
    return;
  }
  showActionMessage(`Advancing ${visible.length} displayed asset(s)...`);
  for (const button of actionButtons) {
    button.disabled = true;
  }
  try {
    const payload = await fetchJson(
      `/api/assets/advance-displayed?${currentQuery().toString()}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset_ids: visible.map((asset) => asset.asset_id) }),
      },
    );
    state.assets = payload.assets || state.assets;
    renderAssetTable();
    if (state.selectedAssetId) {
      await selectAsset(state.selectedAssetId);
    }
    const errors = (payload.results || []).filter((item) => item.status === "ERROR");
    const suffix = errors.length ? ` ${errors.length} error(s); see asset rows/details.` : "";
    showActionMessage((payload.message || "Advance complete.") + suffix, errors.length ? "error" : "success");
  } catch (error) {
    showActionMessage(error.message, "error");
    if (state.selectedAssetId) {
      await selectAsset(state.selectedAssetId);
    }
  } finally {
    updateActionButtons(state.assetDetail);
  }
}

function activatePage(page) {
  if (page !== "onboarding" && page !== "auxiliary-resources" && page !== "phase-comparison" && !selectedPhaseReady()) {
    page = "onboarding";
  }
  for (const button of document.querySelectorAll(".tab")) {
    button.classList.toggle("active", button.dataset.page === page);
  }
  document.querySelector("#onboarding-page").classList.toggle("active", page === "onboarding");
  document.querySelector("#assets-page").classList.toggle("active", page === "assets");
  document.querySelector("#manifest-page").classList.toggle("active", page === "manifest");
  document.querySelector("#prompt-review-page").classList.toggle("active", page === "prompt-review");
  document.querySelector("#render-review-page").classList.toggle("active", page === "render-review");
  document.querySelector("#turnarounds-page").classList.toggle("active", page === "turnarounds");
  document.querySelector("#identity-keys-page").classList.toggle("active", page === "identity-keys");
  document.querySelector("#auxiliary-resources-page").classList.toggle("active", page === "auxiliary-resources");
  document.querySelector("#phase-comparison-page").classList.toggle("active", page === "phase-comparison");
  document.querySelector("#costumes-page").classList.toggle("active", page === "costumes");
  document.querySelector("#expressions-page").classList.toggle("active", page === "expressions");
  document.querySelector("#ai-controls-page").classList.toggle("active", page === "ai-controls");
  document.querySelector("#pipeline-controls-page").classList.toggle("active", page === "pipeline-controls");
  document.querySelector("#render-console-page").classList.toggle("active", page === "render-console");
  document.querySelector("#template-editor-page").classList.toggle("active", page === "template-editor");
  document
    .querySelector("#placeholder-page")
    .classList.toggle(
      "active",
      !["onboarding", "assets", "manifest", "prompt-review", "render-review", "turnarounds", "identity-keys", "auxiliary-resources", "phase-comparison", "costumes", "expressions", "render-console", "ai-controls", "pipeline-controls", "template-editor"].includes(page),
    );
  const activeButton = Array.from(document.querySelectorAll(".tab")).find((button) => button.dataset.page === page);
  placeholderTitle.textContent = activeButton?.textContent || "Page";
  if (page === "prompt-review") {
    loadPromptReviewTasks();
  }
  if (page === "manifest") {
    loadManifestTasks();
  }
  if (page === "render-review") {
    loadRenderReviewTasks();
  }
  if (page === "turnarounds") {
    loadTurnarounds();
  }
  if (page === "identity-keys") {
    loadIdentityKeys();
  }
  if (page === "auxiliary-resources") {
    loadAuxiliaryResources();
  }
  if (page === "phase-comparison") {
    initializePhaseComparisonControls();
    loadPhaseComparison();
  }
  if (page === "costumes") {
    loadCostumes();
  }
  if (page === "expressions") {
    loadExpressions();
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
  if (page === "onboarding") {
    renderOnboarding();
  }
}

function setupTabs() {
  for (const button of document.querySelectorAll(".tab")) {
    button.addEventListener("click", () => {
      if (button.dataset.page === "identity-keys") {
        state.identityKeyMode = "list";
      }
      closeToolbarSettingsMenu();
      activatePage(button.dataset.page);
    });
  }
}

function toggleToolbarSettingsMenu() {
  const isHidden = toolbarSettingsMenu.hidden;
  toolbarSettingsMenu.hidden = !isHidden;
  toolbarSettingsButton.setAttribute("aria-expanded", isHidden ? "true" : "false");
}

function closeToolbarSettingsMenu() {
  toolbarSettingsMenu.hidden = true;
  toolbarSettingsButton.setAttribute("aria-expanded", "false");
}

async function harvestAiFromToolbar() {
  // Run the AI harvest action without navigating away from the current page.
  closeToolbarSettingsMenu();
  toolbarHarvestAi.disabled = true;
  toolbarSettingsButton.textContent = "...";
  try {
    await runAiControlsAction("/api/ai-controls/harvest");
  } finally {
    toolbarHarvestAi.disabled = false;
    toolbarSettingsButton.textContent = "⚙";
  }
}

async function loadIdentityKeys() {
  if (!state.character || !state.phase) {
    identityKeyStatus.textContent = "No character/phase selected.";
    return;
  }
  identityKeyStatus.textContent = "Loading Identity Keys...";
  const payload = await fetchJson(`/api/identity-keys?${currentQuery().toString()}`);
  state.identityKeys = payload.identity_keys || [];
  renderIdentityKeyTable();
  identityKeyStatus.textContent = `${state.identityKeys.length} Identity Key(s)`;
  if (state.identityKeyMode === "list") {
    clearIdentityKeyUpdate();
  }
}

function renderIdentityKeyTable() {
  identityKeyTableBody.replaceChildren();
  for (const item of state.identityKeys) {
    const row = document.createElement("tr");
    row.dataset.identityKeyId = item.identity_key_id;
    row.classList.toggle("selected", item.identity_key_id === state.selectedIdentityKeyId);
    const labelCell = document.createElement("td");
    labelCell.textContent = item.label || "";
    const viewCell = document.createElement("td");
    viewCell.textContent = item.source_body_view || "";
    const imageCell = document.createElement("td");
    imageCell.className = "thumb-cell";
    if (item.image_path) {
      const image = document.createElement("img");
      image.alt = item.label || "Identity Key";
      image.src = fileUrl(item.image_path, item.updated_at || "");
      image.title = item.image_path;
      imageCell.append(image);
    }
    const actionCell = document.createElement("td");
    const updateButton = document.createElement("button");
    updateButton.type = "button";
    updateButton.textContent = "Update";
    updateButton.addEventListener("click", (event) => {
      event.stopPropagation();
      selectIdentityKey(item.identity_key_id);
    });
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteIdentityKey(item.identity_key_id);
    });
    actionCell.append(updateButton, deleteButton);
    row.append(labelCell, viewCell, imageCell, actionCell);
    row.addEventListener("click", () => selectIdentityKey(item.identity_key_id));
    identityKeyTableBody.append(row);
  }
}

function clearIdentityKeyUpdate() {
  state.selectedIdentityKeyId = null;
  state.identityKeySourceAssetId = null;
  state.identityKeyPreview = null;
  identityKeyTitle.textContent = "Select or create an Identity Key";
  identityKeyLabel.value = "";
  identityKeyPercent.value = "100";
  identityKeyCreatePreview.disabled = true;
  identityKeySave.disabled = true;
  identityKeyOriginal.textContent = "No source image.";
  identityKeyPreview.textContent = "No crop preview.";
}

function renderIdentityKeyUpdate(item) {
  state.identityKeyMode = "update";
  state.identityKeySourceAssetId = Number(item.source_asset_id || 0);
  identityKeyTitle.textContent = item.identity_key_id ? `Identity Key | ${item.label}` : `New Identity Key | Asset ${item.source_asset_id}`;
  identityKeyLabel.value = item.label || "";
  identityKeyPercent.value = item.crop_percent || 100;
  renderReviewImage(
    identityKeyOriginal,
    item.source_image_path || "",
    Boolean(item.source_image_path),
    "No source image.",
    "Identity Key source",
    item.updated_at || "",
  );
  renderReviewImage(
    identityKeyPreview,
    state.identityKeyPreview?.preview_path || item.image_path || "",
    Boolean(state.identityKeyPreview?.preview_path || item.image_path),
    "No crop preview.",
    "Identity Key crop",
    item.updated_at || Date.now().toString(),
  );
  identityKeyCreatePreview.disabled = !state.identityKeySourceAssetId;
  identityKeySave.disabled = !state.identityKeySourceAssetId;
}

async function selectIdentityKey(identityKeyId) {
  const item = state.identityKeys.find((key) => key.identity_key_id === identityKeyId);
  if (!item) {
    return;
  }
  state.selectedIdentityKeyId = identityKeyId;
  state.identityKeySourceAssetId = item.source_asset_id;
  state.identityKeyPreview = null;
  renderIdentityKeyTable();
  renderIdentityKeyUpdate(item);
}

async function createIdentityKeyPreview() {
  const sourceAssetId = state.identityKeySourceAssetId;
  if (!sourceAssetId) {
    return;
  }
  showIdentityKeyMessage("Creating Identity Key preview...");
  identityKeyCreatePreview.disabled = true;
  try {
    const payload = await fetchJson(`/api/identity-keys/preview?${currentQuery().toString()}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_asset_id: sourceAssetId,
        identity_key_id: state.selectedIdentityKeyId,
        label: identityKeyLabel.value || "",
        crop_percent: Number(identityKeyPercent.value || 0),
      }),
    });
    state.identityKeyPreview = payload.preview;
    const item = state.selectedIdentityKeyId
      ? state.identityKeys.find((key) => key.identity_key_id === state.selectedIdentityKeyId)
      : {
          source_asset_id: sourceAssetId,
          source_image_path: payload.preview?.source_image_path,
          label: identityKeyLabel.value || "",
          crop_percent: Number(identityKeyPercent.value || 0),
        };
    renderIdentityKeyUpdate(item || {});
    showIdentityKeyMessage("Identity Key preview created.");
  } catch (error) {
    showIdentityKeyMessage(error.message, "error");
  } finally {
    identityKeyCreatePreview.disabled = !state.identityKeySourceAssetId;
  }
}

async function saveIdentityKey() {
  const sourceAssetId = state.identityKeySourceAssetId;
  if (!sourceAssetId) {
    return;
  }
  showIdentityKeyMessage("Saving Identity Key...");
  identityKeySave.disabled = true;
  try {
    const payload = await fetchJson(`/api/identity-keys?${currentQuery().toString()}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_asset_id: sourceAssetId,
        identity_key_id: state.selectedIdentityKeyId,
        label: identityKeyLabel.value || "",
        crop_percent: Number(identityKeyPercent.value || 0),
      }),
    });
    state.identityKeys = payload.identity_keys || state.identityKeys;
    state.selectedIdentityKeyId = payload.identity_key?.identity_key_id || state.selectedIdentityKeyId;
    state.identityKeyPreview = null;
    renderIdentityKeyTable();
    renderIdentityKeyUpdate(payload.identity_key);
    showIdentityKeyMessage(payload.message || "Identity Key saved.");
  } catch (error) {
    showIdentityKeyMessage(error.message, "error");
  } finally {
    identityKeySave.disabled = !state.identityKeySourceAssetId;
  }
}

async function deleteIdentityKey(identityKeyId) {
  if (!window.confirm("Delete this Identity Key?")) {
    return;
  }
  showIdentityKeyMessage("Deleting Identity Key...");
  try {
    const payload = await fetchJson(`/api/identity-keys/${encodeURIComponent(identityKeyId)}?${currentQuery().toString()}`, {
      method: "DELETE",
    });
    state.identityKeys = payload.identity_keys || [];
    if (state.selectedIdentityKeyId === identityKeyId) {
      clearIdentityKeyUpdate();
    }
    renderIdentityKeyTable();
    showIdentityKeyMessage(payload.message || "Identity Key deleted.");
  } catch (error) {
    showIdentityKeyMessage(error.message, "error");
  }
}

async function loadCostumes() {
  if (!state.character || !state.phase) {
    costumeStatus.textContent = "No character/phase selected.";
    return;
  }
  costumeStatus.textContent = "Loading costumes...";
  const payload = await fetchJson(`/api/costumes?${currentQuery().toString()}`);
  state.costumes = payload.costumes || [];
  if (state.selectedCostumeSlug && !state.costumes.some((item) => item.slug === state.selectedCostumeSlug)) {
    state.selectedCostumeSlug = null;
  }
  renderCostumeTable();
  renderCostumeEditor();
  costumeStatus.textContent = `${state.costumes.length} costume(s)`;
}

function renderCostumeTable() {
  costumeTableBody.replaceChildren();
  for (const costume of state.costumes) {
    const row = document.createElement("tr");
    row.dataset.costumeSlug = costume.slug;
    row.classList.toggle("selected", costume.slug === state.selectedCostumeSlug);
    const nameCell = document.createElement("td");
    nameCell.textContent = costume.name || "";
    const countCell = document.createElement("td");
    countCell.textContent = costume.asset_count ?? 0;
    const pathCell = document.createElement("td");
    pathCell.textContent = costume.path || "";
    const actionCell = document.createElement("td");
    const openButton = document.createElement("button");
    openButton.type = "button";
    openButton.textContent = "Open";
    openButton.addEventListener("click", (event) => {
      event.stopPropagation();
      openSourceEditorForSource(costume.source, showCostumeMessage);
    });
    actionCell.append(openButton);
    row.append(nameCell, countCell, pathCell, actionCell);
    row.addEventListener("click", () => selectCostume(costume.slug));
    costumeTableBody.append(row);
  }
}

function selectedCostume() {
  // Return the currently selected costume row, if any.
  return state.costumes.find((costume) => costume.slug === state.selectedCostumeSlug) || null;
}

function clearCostumeForm() {
  // Switch the costume editor to add-new mode.
  state.selectedCostumeSlug = null;
  costumeName.value = "";
  costumeTemplateFile.value = "";
  renderCostumeTable();
  renderCostumeEditor();
}

function selectCostume(slug) {
  // Fill the costume editor from a selected table row.
  state.selectedCostumeSlug = slug;
  const costume = selectedCostume();
  costumeName.value = costume?.name || "";
  costumeTemplateFile.value = "";
  renderCostumeTable();
  renderCostumeEditor();
}

function renderCostumeEditor() {
  // Render the costume editor controls for add or update mode.
  const costume = selectedCostume();
  const isUpdate = Boolean(costume);
  costumeFormTitle.textContent = isUpdate ? "Update Costume" : "Add Costume";
  costumeCreate.textContent = isUpdate ? "Update Costume" : "Save Costume";
  costumeTemplateFileWrap.hidden = isUpdate;
  costumePreviewSection.hidden = !isUpdate;
  if (isUpdate) {
    renderReviewImage(
      costumePreview,
      costume.locked_preview_path,
      costume.locked_preview_exists,
      "No locked turnaround.",
      "Locked costume turnaround",
      costume.path || costume.name || "",
    );
  }
}

async function saveCostume() {
  const name = costumeName.value.trim();
  const selected = selectedCostume();
  if (!name) {
    showCostumeMessage("Costume name is required.", "error");
    return;
  }
  showCostumeMessage(selected ? "Updating costume..." : "Creating costume...");
  costumeCreate.disabled = true;
  try {
    let payload;
    if (selected) {
      payload = await fetchJson(`/api/costumes/${encodeURIComponent(selected.slug)}?${currentQuery().toString()}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
    } else {
      const params = currentQuery();
      params.set("costume_name", name);
      const file = costumeTemplateFile.files?.[0];
      payload = await fetchJson(`/api/costumes?${params.toString()}`, {
        method: "POST",
        headers: { "Content-Type": "text/markdown; charset=utf-8" },
        body: file ? await file.text() : "",
      });
    }
    state.costumes = payload.costumes || state.costumes;
    state.assets = payload.assets || state.assets;
    state.selectedCostumeSlug = payload.costume?.slug || (selected ? selected.slug : null);
    renderCostumeTable();
    renderCostumeEditor();
    renderAssetTable();
    if (!selected) {
      costumeName.value = "";
      costumeTemplateFile.value = "";
      state.selectedCostumeSlug = null;
      renderCostumeTable();
      renderCostumeEditor();
    }
    showCostumeMessage(payload.message || (selected ? "Costume updated." : "Costume created."));
  } catch (error) {
    showCostumeMessage(error.message, "error");
  } finally {
    costumeCreate.disabled = false;
  }
}

async function loadExpressions() {
  if (!state.character || !state.phase) {
    expressionStatus.textContent = "No character/phase selected.";
    return;
  }
  expressionStatus.textContent = "Loading expressions...";
  const payload = await fetchJson(`/api/expressions?${currentQuery().toString()}`);
  state.expressionAssets = payload.expression_assets || [];
  state.expressionDefinitions = payload.expression_definitions || [];
  state.expressionIdentityKeys = payload.identity_keys || [];
  if (state.selectedExpressionAssetId && !state.expressionAssets.some((item) => item.asset_id === state.selectedExpressionAssetId)) {
    state.selectedExpressionAssetId = null;
  }
  fillExpressionIdentityKeySelect();
  renderExpressionTable();
  renderExpressionEditor();
  expressionStatus.textContent = `${state.expressionAssets.length} expression asset(s)`;
}

function fillExpressionIdentityKeySelect() {
  const items = [option("", "Select Identity Key...")];
  for (const key of state.expressionIdentityKeys) {
    const label = [key.label, key.source_body_view, key.source_costume].filter(Boolean).join(" | ");
    items.push(option(key.identity_key_id, label || key.identity_key_id));
  }
  expressionIdentityKey.replaceChildren(...items);
}

function expressionDefinitionForAsset(asset) {
  return state.expressionDefinitions.find((item) => item.path === asset.expression_definition_path) || null;
}

function renderExpressionTable() {
  expressionTableBody.replaceChildren();
  for (const asset of state.expressionAssets) {
    const row = document.createElement("tr");
    row.dataset.assetId = asset.asset_id;
    row.classList.toggle("selected", asset.asset_id === state.selectedExpressionAssetId);
    const identityKey = state.expressionIdentityKeys.find((key) => key.identity_key_id === asset.identity_key_id);
    const values = [
      asset.asset_id,
      asset.expression,
      identityKey?.label || asset.identity_key_id || "",
      asset.pipeline_stage_display || asset.pipeline_stage,
      asset.asset_state,
      asset.final_image_output,
    ];
    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = value ?? "";
      row.append(cell);
    }
    const actionCell = document.createElement("td");
    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.textContent = "Open";
    editButton.addEventListener("click", (event) => {
      event.stopPropagation();
      const definition = expressionDefinitionForAsset(asset);
      if (definition?.source) {
        openSourceEditorForSource(definition.source, showExpressionMessage);
      }
    });
    actionCell.append(editButton);
    row.append(actionCell);
    row.addEventListener("click", () => selectExpression(asset.asset_id));
    expressionTableBody.append(row);
  }
}

function selectedExpressionAsset() {
  // Return the currently selected expression asset, if any.
  return state.expressionAssets.find((asset) => asset.asset_id === state.selectedExpressionAssetId) || null;
}

function clearExpressionForm() {
  // Switch the expression editor to add-new mode.
  state.selectedExpressionAssetId = null;
  expressionLabel.value = "";
  expressionIdentityKey.value = "";
  expressionDefinitionFile.value = "";
  renderExpressionTable();
  renderExpressionEditor();
}

function selectExpression(assetId) {
  // Fill the expression editor from a selected table row.
  state.selectedExpressionAssetId = assetId;
  const asset = selectedExpressionAsset();
  expressionLabel.value = asset?.expression || "";
  expressionIdentityKey.value = asset?.identity_key_id || "";
  expressionDefinitionFile.value = "";
  renderExpressionTable();
  renderExpressionEditor();
}

function renderExpressionEditor() {
  // Render the expression editor controls for add or update mode.
  const asset = selectedExpressionAsset();
  const isUpdate = Boolean(asset);
  expressionFormTitle.textContent = isUpdate ? "Update Expression" : "Add Expression";
  expressionCreate.textContent = isUpdate ? "Update Expression" : "Save Expression";
  expressionDefinitionFileWrap.hidden = isUpdate;
  expressionPreviewSection.hidden = !isUpdate;
  if (isUpdate) {
    renderReviewImage(
      expressionPreview,
      asset.locked_image_path,
      asset.locked_image_exists,
      "No locked expression.",
      "Locked expression",
      asset.updated_at || "",
    );
  }
}

async function saveExpression() {
  const label = expressionLabel.value.trim();
  const identityKeyId = expressionIdentityKey.value;
  const file = expressionDefinitionFile.files?.[0];
  const selected = selectedExpressionAsset();
  if (!label || !identityKeyId) {
    showExpressionMessage("Label and Identity Key are required.", "error");
    return;
  }
  let regenerate = false;
  if (selected && selected.identity_key_id !== identityKeyId) {
    regenerate = window.confirm("Identity Key changed. Reset this expression to regenerate from MANIFEST?");
    if (selected.asset_state === "LOCKED" && !regenerate) {
      const keepLocked = window.confirm("This expression is LOCKED. Keep the current locked image even though the Identity Key changed?");
      if (!keepLocked) {
        return;
      }
    }
  }
  showExpressionMessage(selected ? "Updating expression..." : "Creating expression...");
  expressionCreate.disabled = true;
  try {
    let payload;
    if (selected) {
      payload = await fetchJson(`/api/expressions/${selected.asset_id}?${currentQuery().toString()}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label, identity_key_id: identityKeyId, regenerate }),
      });
    } else {
      const params = currentQuery();
      params.set("label", label);
      params.set("identity_key_id", identityKeyId);
      payload = await fetchJson(`/api/expressions?${params.toString()}`, {
        method: "POST",
        headers: { "Content-Type": "text/markdown; charset=utf-8" },
        body: file ? await file.text() : "",
      });
    }
    state.expressionAssets = payload.expression_assets || state.expressionAssets;
    state.expressionDefinitions = payload.expression_definitions || state.expressionDefinitions;
    state.expressionIdentityKeys = payload.identity_keys || state.expressionIdentityKeys;
    state.assets = payload.assets || state.assets;
    state.selectedExpressionAssetId = payload.asset?.asset_id || (selected ? selected.asset_id : null);
    fillExpressionIdentityKeySelect();
    renderExpressionTable();
    renderExpressionEditor();
    renderAssetTable();
    if (!selected) {
      expressionLabel.value = "";
      expressionDefinitionFile.value = "";
      state.selectedExpressionAssetId = null;
      renderExpressionTable();
      renderExpressionEditor();
    }
    showExpressionMessage(payload.message || (selected ? "Expression updated." : "Expression created."));
  } catch (error) {
    showExpressionMessage(error.message, "error");
  } finally {
    expressionCreate.disabled = false;
  }
}

function updateAuxiliaryResourceCategoryDisplay() {
  // Keep the editor header matched to the currently filtered resource category.
  const selected = auxResourceCategory.options[auxResourceCategory.selectedIndex];
  auxResourceFormCategory.textContent = selected?.textContent || "Person";
}

function clearAuxiliaryResourceForm() {
  state.selectedAuxiliaryResourceId = null;
  state.auxiliaryResourceImageBlob = null;
  updateAuxiliaryResourceCategoryDisplay();
  auxResourceFormTitle.textContent = "Add Resource";
  auxResourceLabel.value = "";
  auxResourceTag.textContent = "";
  auxResourceCopyTag.disabled = true;
  auxResourceImagePreview.hidden = true;
  auxResourceImagePreview.removeAttribute("src");
  auxResourceSave.textContent = "Save Resource";
  auxResourceFileInput.value = "";
  for (const row of auxResourceTableBody.querySelectorAll("tr")) {
    row.classList.remove("selected");
  }
}

function setAuxiliaryResourceImageSelection(blob) {
  if (!blob || !blob.type.startsWith("image/")) {
    showAuxResourceMessage("Clipboard or file did not contain an image.", "error");
    return;
  }
  state.auxiliaryResourceImageBlob = blob;
  auxResourceImagePreview.src = URL.createObjectURL(blob);
  auxResourceImagePreview.hidden = false;
  showAuxResourceMessage(`Ready to save ${Math.round(blob.size / 1024)} KB image.`);
}

async function loadAuxiliaryResources() {
  updateAuxiliaryResourceCategoryDisplay();
  auxResourceStatus.textContent = "Loading auxiliary resources...";
  const params = new URLSearchParams({ category: auxResourceCategory.value || "person" });
  try {
    const payload = await fetchJson(`/api/auxiliary-resources?${params.toString()}`);
    state.auxiliaryResources = payload.resources || [];
    const visibleCount = renderAuxiliaryResourceTable();
    auxResourceStatus.textContent = `${visibleCount} of ${state.auxiliaryResources.length} ${auxResourceCategory.value} resource(s)`;
  } catch (error) {
    auxResourceStatus.textContent = "Load failed.";
    showAuxResourceMessage(error.message, "error");
  }
}

function renderAuxiliaryResourceTable() {
  const search = (auxResourceSearch.value || "").trim().toLowerCase();
  const visibleResources = search
    ? state.auxiliaryResources.filter((resource) => (resource.label || "").toLowerCase().includes(search))
    : state.auxiliaryResources;
  auxResourceTableBody.replaceChildren();
  auxResourceTable.classList.toggle("aux-resource-table-no-thumbs", !auxResourceShowThumbnails.checked);
  if (!visibleResources.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.textContent = state.auxiliaryResources.length ? "No resources match this search." : "No resources.";
    row.append(cell);
    auxResourceTableBody.append(row);
    return 0;
  }
  for (const resource of visibleResources) {
    const row = document.createElement("tr");
    row.dataset.resourceId = resource.resource_id;
    row.classList.toggle("selected", resource.resource_id === state.selectedAuxiliaryResourceId);
    const imageCell = document.createElement("td");
    imageCell.className = "aux-thumbnail-cell";
    if (resource.image_path) {
      const image = document.createElement("img");
      image.className = "aux-resource-thumb";
      image.alt = resource.label || resource.resource_id;
      image.src = fileUrl(resource.image_path, resource.updated_at || "");
      imageCell.append(image);
    }
    const labelCell = document.createElement("td");
    labelCell.textContent = resource.label || "";
    const tagCell = document.createElement("td");
    tagCell.textContent = resource.tag || "";
    const actionCell = document.createElement("td");
    const copyButton = document.createElement("button");
    copyButton.type = "button";
    copyButton.textContent = "Copy";
    copyButton.addEventListener("click", (event) => {
      event.stopPropagation();
      copyText(resource.tag || "", "Resource tag copied.");
    });
    actionCell.append(copyButton);
    row.append(imageCell, labelCell, tagCell, actionCell);
    row.addEventListener("click", () => selectAuxiliaryResource(resource.resource_id));
    auxResourceTableBody.append(row);
  }
  return visibleResources.length;
}

function refreshAuxiliaryResourceTable() {
  // Re-render the auxiliary resource table after local filter changes.
  const visibleCount = renderAuxiliaryResourceTable();
  auxResourceStatus.textContent = `${visibleCount} of ${state.auxiliaryResources.length} ${auxResourceCategory.value} resource(s)`;
}

function selectAuxiliaryResource(resourceId) {
  const resource = state.auxiliaryResources.find((item) => item.resource_id === resourceId);
  if (!resource) {
    return;
  }
  state.selectedAuxiliaryResourceId = resource.resource_id;
  state.auxiliaryResourceImageBlob = null;
  updateAuxiliaryResourceCategoryDisplay();
  auxResourceFormTitle.textContent = "Update Resource";
  auxResourceLabel.value = resource.label || "";
  auxResourceTag.textContent = resource.tag || "";
  auxResourceCopyTag.disabled = !resource.tag;
  auxResourceSave.textContent = "Update Resource";
  auxResourceImagePreview.src = fileUrl(resource.image_path, resource.updated_at || "");
  auxResourceImagePreview.hidden = !resource.image_path;
  renderAuxiliaryResourceTable();
}

async function saveAuxiliaryResource() {
  const label = auxResourceLabel.value.trim();
  if (!label) {
    showAuxResourceMessage("Label is required.", "error");
    return;
  }
  const isUpdate = Boolean(state.selectedAuxiliaryResourceId);
  if (!isUpdate && !state.auxiliaryResourceImageBlob) {
    showAuxResourceMessage("Image is required.", "error");
    return;
  }
  const params = new URLSearchParams({
    category: auxResourceCategory.value || "person",
    label,
  });
  if (isUpdate && state.auxiliaryResourceImageBlob) {
    params.set("replace_image", "true");
  }
  auxResourceSave.disabled = true;
  showAuxResourceMessage(isUpdate ? "Updating resource..." : "Creating resource...");
  try {
    const url = isUpdate
      ? `/api/auxiliary-resources/${encodeURIComponent(state.selectedAuxiliaryResourceId)}?${params.toString()}`
      : `/api/auxiliary-resources?${params.toString()}`;
    const blob = state.auxiliaryResourceImageBlob || new Blob([]);
    const payload = await fetchJson(url, {
      method: isUpdate ? "PUT" : "POST",
      headers: { "Content-Type": blob.type || "image/png" },
      body: blob,
    });
    state.auxiliaryResources = payload.resources || state.auxiliaryResources;
    state.selectedAuxiliaryResourceId = payload.resource?.resource_id || state.selectedAuxiliaryResourceId;
    state.auxiliaryResourceImageBlob = null;
    renderAuxiliaryResourceTable();
    selectAuxiliaryResource(state.selectedAuxiliaryResourceId);
    showAuxResourceMessage(payload.message || "Resource saved.");
  } catch (error) {
    showAuxResourceMessage(error.message, "error");
  } finally {
    auxResourceSave.disabled = false;
  }
}

function initializePhaseComparisonControls() {
  // Seed comparison controls from the current dashboard context when needed.
  if (!state.phaseComparison.character) {
    state.phaseComparison.character = state.character || state.characters[0] || "";
  }
  setSelectOptions(phaseComparisonCharacter, state.characters || []);
  phaseComparisonCharacter.value = state.phaseComparison.character || "";
  syncPhaseComparisonPhaseOptions();
}

function syncPhaseComparisonPhaseOptions() {
  // Keep left and right phase dropdowns valid for the selected comparison character.
  const character = phaseComparisonCharacter.value || state.phaseComparison.character || "";
  const phases = state.phasesByCharacter[character] || [];
  const fallbackLeft = state.phase && phases.includes(state.phase) ? state.phase : phases[0] || "";
  const fallbackRight = phases.find((phase) => phase !== fallbackLeft) || fallbackLeft;
  state.phaseComparison.character = character;
  state.phaseComparison.leftPhase = phases.includes(state.phaseComparison.leftPhase)
    ? state.phaseComparison.leftPhase
    : fallbackLeft;
  state.phaseComparison.rightPhase = phases.includes(state.phaseComparison.rightPhase)
    ? state.phaseComparison.rightPhase
    : fallbackRight;
  setSelectOptions(phaseComparisonLeftPhase, phases);
  setSelectOptions(phaseComparisonRightPhase, phases);
  phaseComparisonLeftPhase.value = state.phaseComparison.leftPhase || "";
  phaseComparisonRightPhase.value = state.phaseComparison.rightPhase || "";
}

async function loadPhaseComparison({ preserveSlot = true, resetIndex = false } = {}) {
  const character = phaseComparisonCharacter.value || state.phaseComparison.character;
  const leftPhase = phaseComparisonLeftPhase.value || state.phaseComparison.leftPhase;
  const rightPhase = phaseComparisonRightPhase.value || state.phaseComparison.rightPhase;
  if (!character || !leftPhase || !rightPhase) {
    clearPhaseComparison("Choose a character and two phases.");
    return;
  }
  phaseComparisonStatus.textContent = "Loading phase comparison...";
  const params = new URLSearchParams({
    character,
    left_phase: leftPhase,
    right_phase: rightPhase,
    pipeline: phaseComparisonPipeline.value || state.phaseComparison.pipeline || "",
    selected_index: String(resetIndex ? 0 : state.phaseComparison.selectedIndex || 0),
    selected_slot_key: preserveSlot ? (state.phaseComparison.selectedSlotKey || "") : "",
    left_costume: phaseComparisonLeftCostume.value || state.phaseComparison.leftCostume || "",
    right_costume: phaseComparisonRightCostume.value || state.phaseComparison.rightCostume || "",
  });
  try {
    const payload = await fetchJson(`/api/phase-comparison?${params.toString()}`);
    renderPhaseComparison(payload);
  } catch (error) {
    clearPhaseComparison("Phase comparison failed.");
    showPhaseComparisonMessage(error.message, "error");
  }
}

function renderPhaseComparison(payload) {
  state.phaseComparison.character = payload.character || "";
  state.phaseComparison.leftPhase = payload.left_phase || "";
  state.phaseComparison.rightPhase = payload.right_phase || "";
  state.phaseComparison.pipeline = payload.pipeline || "";
  state.phaseComparison.leftCostume = payload.selected_left_costume || "";
  state.phaseComparison.rightCostume = payload.selected_right_costume || "";
  state.phaseComparison.selectedIndex = payload.selected_index || 0;
  state.phaseComparison.selectedSlotKey = payload.selected_row?.slot_key || "";
  state.phaseComparison.rows = payload.rows || [];
  phaseComparisonCharacter.value = state.phaseComparison.character;
  syncPhaseComparisonPhaseOptions();
  const currentPipeline = phaseComparisonPipeline.value;
  setSelectOptions(phaseComparisonPipeline, payload.available_pipelines || []);
  phaseComparisonPipeline.value = (payload.available_pipelines || []).includes(payload.pipeline)
    ? payload.pipeline
    : ((payload.available_pipelines || []).includes(currentPipeline) ? currentPipeline : "");
  renderPhaseComparisonCostumeControls(payload);
  phaseComparisonStatus.textContent = `${state.phaseComparison.rows.length} comparison slot(s)`;
  phaseComparisonPrev.disabled = state.phaseComparison.rows.length <= 1;
  phaseComparisonNext.disabled = state.phaseComparison.rows.length <= 1;
  renderPhaseComparisonRow(payload.selected_row || null);
  showPhaseComparisonMessage("");
}

function renderPhaseComparisonCostumeControls(payload) {
  // Costume-Dressing compares independently selected costumes by shared view slots.
  const showCostumes = payload.pipeline === "Costume-Dressing";
  phaseComparisonLeftCostumeWrap.hidden = !showCostumes;
  phaseComparisonRightCostumeWrap.hidden = !showCostumes;
  if (!showCostumes) {
    phaseComparisonLeftCostume.replaceChildren();
    phaseComparisonRightCostume.replaceChildren();
    return;
  }
  setSelectOptions(phaseComparisonLeftCostume, payload.left_costumes || []);
  setSelectOptions(phaseComparisonRightCostume, payload.right_costumes || []);
  phaseComparisonLeftCostume.value = payload.selected_left_costume || "";
  phaseComparisonRightCostume.value = payload.selected_right_costume || "";
}

function clearPhaseComparison(message = "No comparison rows.") {
  state.phaseComparison.rows = [];
  state.phaseComparison.selectedIndex = 0;
  state.phaseComparison.selectedSlotKey = "";
  state.phaseComparison.leftCostume = "";
  state.phaseComparison.rightCostume = "";
  phaseComparisonStatus.textContent = message;
  phaseComparisonMeta.textContent = "";
  phaseComparisonPrev.disabled = true;
  phaseComparisonNext.disabled = true;
  phaseComparisonLeftCostumeWrap.hidden = true;
  phaseComparisonRightCostumeWrap.hidden = true;
  phaseComparisonLeftTitle.textContent = "Left Phase";
  phaseComparisonRightTitle.textContent = "Right Phase";
  renderPhaseComparisonSide(phaseComparisonLeftImage, phaseComparisonLeftMeta, null);
  renderPhaseComparisonSide(phaseComparisonRightImage, phaseComparisonRightMeta, null);
}

function renderPhaseComparisonRow(row) {
  if (!row) {
    clearPhaseComparison();
    return;
  }
  phaseComparisonMeta.textContent =
    `${row.pipeline} | ${row.slot_label} | ${state.phaseComparison.selectedIndex + 1} of ${state.phaseComparison.rows.length}`;
  phaseComparisonLeftTitle.textContent = row.left?.phase || "Left Phase";
  phaseComparisonRightTitle.textContent = row.right?.phase || "Right Phase";
  renderPhaseComparisonSide(phaseComparisonLeftImage, phaseComparisonLeftMeta, row.left);
  renderPhaseComparisonSide(phaseComparisonRightImage, phaseComparisonRightMeta, row.right);
}

function renderPhaseComparisonSide(imageContainer, metaContainer, side) {
  imageContainer.replaceChildren();
  imageContainer.classList.toggle("missing-slot", !side?.image_exists);
  if (side?.image_exists && side.image_path) {
    const image = document.createElement("img");
    image.alt = side.label || "Locked asset";
    image.src = fileUrl(side.image_path, side.updated_at || Date.now().toString());
    imageContainer.append(image);
  } else {
    imageContainer.textContent = side?.label || "No locked asset for this slot.";
  }
  renderPhaseComparisonMeta(metaContainer, side);
}

function renderPhaseComparisonMeta(container, side) {
  container.replaceChildren();
  const rows = [
    ["Asset", side?.asset_id ? `Asset ${side.asset_id}` : "Missing"],
    ["Body", side?.body_view || ""],
    ["Head", side?.head_view || ""],
    ["Costume", side?.costume || ""],
    ["Expression", side?.expression || ""],
  ];
  for (const [label, value] of rows) {
    const term = document.createElement("dt");
    term.textContent = label;
    const description = document.createElement("dd");
    description.textContent = value || "-";
    container.append(term, description);
  }
}

function movePhaseComparison(delta) {
  // Move to the next or previous comparison slot, wrapping at both ends.
  if (!state.phaseComparison.rows.length) {
    return;
  }
  const length = state.phaseComparison.rows.length;
  const nextIndex = (state.phaseComparison.selectedIndex + delta + length) % length;
  state.phaseComparison.selectedIndex = nextIndex;
  state.phaseComparison.selectedSlotKey = "";
  loadPhaseComparison({ preserveSlot: false });
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
  clearSourceInspector();
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
  generateLocalTestButton.disabled = !detail.prompt_text || !detail.is_reviewable || !detail.supports_local_test_render;
  promptApproveButton.disabled = !detail.is_reviewable;
  promptFailButton.disabled = !detail.is_reviewable;
  renderLocalTestRender(detail.latest_local_test_render);
  clearSourceInspector();
  updatePromptReviewNavigation();
}

function renderPromptText() {
  const detail = state.promptReviewDetail;
  if (!detail) {
    promptText.replaceChildren();
    return;
  }
  const query = promptSearch.value.trim();
  const raw = detail.prompt_text || "";
  const lines = raw.split(/\r?\n/);
  if (lines.length && lines[lines.length - 1] === "") {
    lines.pop();
  }
  if (!query) {
    renderPromptLines(lines, null);
    return;
  }
  const pattern = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
  renderPromptLines(lines, pattern);
}

function sourceForPromptLine(lineNumber) {
  const fragments = state.promptReviewDetail?.source_map?.fragments || [];
  return fragments.find(
    (fragment) => lineNumber >= Number(fragment.prompt_start_line || 0) && lineNumber <= Number(fragment.prompt_end_line || 0),
  );
}

function sourceBadgeLabel(source) {
  const kind = source?.source_kind || "unknown";
  const labels = {
    static_prompt_template: "template",
    character_template_section: "character",
    shared_template_section: "shared",
    costume_template_section: "costume",
    config_view_instruction: "view",
    config_rule: "rule",
    template_metadata_field: "metadata",
    expression_definition: "expression",
    runtime_generated: "generated",
  };
  return labels[kind] || kind;
}

function sourceTooltip(source) {
  if (!source) {
    return "No source map entry for this line.";
  }
  const parts = [
    source.source_label || source.source_kind || "Source",
    source.section_name ? `Section: ${source.section_name}` : "",
    source.json_pointer ? `JSON: ${source.json_pointer}` : "",
    source.source_path ? `Path: ${source.source_path}` : "",
    source.start_line ? `Source lines: ${source.start_line}-${source.end_line || source.start_line}` : "",
  ];
  return parts.filter(Boolean).join("\n");
}

function clearSourceInspector() {
  state.selectedSource = null;
  sourceInspectorEmpty.hidden = false;
  sourceInspectorDetail.hidden = true;
  sourceInspectorText.hidden = true;
  sourceOpenEditor.disabled = true;
  sourceInspectorDetail.replaceChildren();
  sourceInspectorText.textContent = "";
}

function addInspectorRow(label, value) {
  if (value === undefined || value === null || value === "") {
    return;
  }
  const term = document.createElement("dt");
  term.textContent = label;
  const definition = document.createElement("dd");
  definition.textContent = String(value);
  sourceInspectorDetail.append(term, definition);
}

function showSourceInspector(source, lineNumber, lineText) {
  state.selectedSource = source || null;
  sourceInspectorEmpty.hidden = true;
  sourceInspectorDetail.hidden = false;
  sourceInspectorText.hidden = false;
  sourceOpenEditor.disabled = !source || source.editable === false || !source.source_path;
  sourceInspectorDetail.replaceChildren();
  addInspectorRow("Prompt line", lineNumber);
  addInspectorRow("Source", sourceBadgeLabel(source));
  addInspectorRow("Label", source?.source_label);
  addInspectorRow("Path", source?.source_path);
  addInspectorRow("Section", source?.section_name);
  addInspectorRow("JSON", source?.json_pointer);
  addInspectorRow("Metadata", source?.metadata_key);
  addInspectorRow("Source lines", source?.start_line ? `${source.start_line}-${source.end_line || source.start_line}` : "");
  addInspectorRow("Editable", source?.editable === false ? "No" : "Yes");
  sourceInspectorText.textContent = lineText || "";
}

function addEditorMeta(label, value) {
  if (value === undefined || value === null || value === "") {
    return;
  }
  const term = document.createElement("dt");
  term.textContent = label;
  const definition = document.createElement("dd");
  definition.textContent = String(value);
  sourceEditorMeta.append(term, definition);
}

function renderSourceEditor(detail) {
  state.sourceEditor = detail;
  sourceEditorTitle.textContent = detail.source?.source_label || detail.path || "Source";
  sourceEditorStatus.textContent = detail.editor_type || "";
  sourceEditorMeta.replaceChildren();
  addEditorMeta("Path", detail.path);
  addEditorMeta("Type", detail.editor_type);
  addEditorMeta("Section", detail.section_name);
  addEditorMeta("JSON", detail.json_pointer);
  addEditorMeta("Source lines", detail.start_line ? `${detail.start_line}-${detail.end_line || detail.start_line}` : "");
  sourceEditorText.value = detail.text || "";
  sourceEditorSave.disabled = false;
  sourceEditorRecompile.disabled = !state.promptReviewDetail?.is_reviewable;
  sourceEditorClearReviewAids.checked = true;
  sourceEditorWarning.textContent = detail.warning || "";
  sourceEditorWarning.hidden = !detail.warning;
  showSourceEditorMessage("");
}

async function openSelectedSourceEditor() {
  if (!state.selectedSource) {
    return;
  }
  await openSourceEditorForSource(state.selectedSource, showPromptMessage);
}

async function openSourceEditorForSource(source, errorHandler = showSourceEditorMessage) {
  if (!source) {
    return;
  }
  showSourceEditorMessage("Loading source...");
  try {
    const detail = await fetchJson("/api/edit-source/load", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(source),
    });
    renderSourceEditor(detail);
    activatePage("template-editor");
  } catch (error) {
    errorHandler(error.message, "error");
  }
}

async function saveSourceEditor() {
  if (!state.sourceEditor) {
    return;
  }
  sourceEditorSave.disabled = true;
  showSourceEditorMessage("Saving...");
  try {
    const payload = {
      editor_type: state.sourceEditor.editor_type,
      path: state.sourceEditor.path,
      section_name: state.sourceEditor.section_name,
      json_pointer: state.sourceEditor.json_pointer,
      text: sourceEditorText.value,
    };
    const result = await fetchJson("/api/edit-source/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    showSourceEditorMessage(`Saved ${result.path}.`);
  } catch (error) {
    showSourceEditorMessage(error.message, "error");
  } finally {
    sourceEditorSave.disabled = false;
  }
}

async function recompileCurrentPrompt() {
  const assetId = state.promptReviewDetail?.asset?.asset_id || state.selectedPromptReviewAssetId;
  if (!assetId) {
    showSourceEditorMessage("No prompt review asset is selected.", "error");
    return;
  }
  const params = currentQuery();
  params.set("invalidate_review_artifacts", sourceEditorClearReviewAids.checked ? "true" : "false");
  sourceEditorRecompile.disabled = true;
  showSourceEditorMessage("Recompiling current prompt...");
  try {
    const payload = await fetchJson(`/api/prompt-review/${assetId}/recompile?${params.toString()}`, { method: "POST" });
    renderPromptReview(payload);
    await loadPromptReviewTasks(assetId);
    await loadAssets(state.selectedAssetId);
    showSourceEditorMessage(payload.message || "Prompt recompiled.");
    showPromptMessage(payload.message || "Prompt recompiled.");
    renderPromptDiff(payload.prompt_diff);
  } catch (error) {
    showSourceEditorMessage(error.message, "error");
  } finally {
    sourceEditorRecompile.disabled = !state.promptReviewDetail?.is_reviewable;
  }
}

function renderPromptDiff(diff) {
  if (!diff) {
    return;
  }
  promptDiffOld.replaceChildren();
  promptDiffNew.replaceChildren();
  renderPromptDiffPane(promptDiffOld, diff.old_rows || []);
  renderPromptDiffPane(promptDiffNew, diff.new_rows || []);
  const oldChanged = (diff.old_rows || []).filter((row) => row.status !== "unchanged").length;
  const newChanged = (diff.new_rows || []).filter((row) => row.status !== "unchanged").length;
  promptDiffSummary.textContent = diff.changed
    ? `Changed lines: before ${oldChanged}, after ${newChanged}`
    : "No prompt text changes detected.";
  promptDiffDialog.showModal();
}

function renderPromptDiffPane(container, rows) {
  if (!rows.length) {
    container.textContent = "No prompt lines.";
    return;
  }
  for (const row of rows) {
    const line = document.createElement("div");
    line.className = `prompt-diff-row ${row.status || "unchanged"}`;
    const lineNo = document.createElement("span");
    lineNo.className = "prompt-diff-line";
    lineNo.textContent = row.line_no ?? "";
    const source = document.createElement("span");
    source.className = "prompt-diff-source";
    source.textContent = sourceBadgeLabel(row);
    source.title = row.source_label || row.source_kind || "";
    const text = document.createElement("span");
    text.className = "prompt-diff-text";
    text.textContent = row.text || " ";
    line.append(lineNo, source, text);
    container.append(line);
  }
}

function renderPromptLines(lines, searchPattern) {
  promptText.replaceChildren();
  if (!lines.length) {
    promptText.textContent = "No prompt text found.";
    return;
  }
  lines.forEach((line, index) => {
    const lineNumber = index + 1;
    const source = sourceForPromptLine(lineNumber);
    const row = document.createElement("div");
    row.className = "prompt-line";
    if (!line.trim()) {
      row.classList.add("blank");
      row.append(document.createElement("span"), document.createElement("span"));
      promptText.append(row);
      return;
    }
    const badge = document.createElement("button");
    badge.type = "button";
    badge.className = `prompt-source-badge source-${sourceBadgeLabel(source).replace(/[^a-z0-9_-]/gi, "-")}`;
    badge.textContent = sourceBadgeLabel(source);
    badge.title = sourceTooltip(source);
    badge.addEventListener("click", () => showSourceInspector(source, lineNumber, line));
    const text = document.createElement("span");
    text.className = "prompt-line-text";
    if (searchPattern) {
      text.innerHTML = escapeHtml(line || " ").replace(searchPattern, (match) => `<mark>${escapeHtml(match)}</mark>`);
    } else {
      text.textContent = line || " ";
    }
    row.append(badge, text);
    promptText.append(row);
  });
}

function renderLocalTestRender(path) {
  localTestRender.replaceChildren();
  if (!path) {
    localTestRender.textContent = "No local test render.";
    return;
  }
  const image = document.createElement("img");
  image.alt = "Latest local test render";
  image.src = fileUrl(path, Date.now().toString());
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
      if (action === "approve" && state.promptReviewTasks.length === 0) {
        activatePage("render-console");
      }
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
  lockedRender.textContent = "No locked image.";
  renderStageText.textContent = "";
  renderHistoryText.textContent = "";
  renderReviewComment.value = "";
  renderCommentSave.disabled = true;
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
  renderReviewComment.value = detail.render_review_comment || "";
  renderStageText.textContent = detail.stage_text || "No stage marker found.";
  renderHistoryText.textContent = detail.history_text || "No history found.";
  renderCandidateImage(detail);
  renderLockedImage(detail);
  renderPromoteButton.disabled = !detail.is_reviewable || !detail.exists?.candidate_image;
  renderFailRenderButton.disabled = !detail.is_reviewable;
  renderFailRegenerateButton.disabled = !detail.is_reviewable;
  renderCommentSave.disabled = !detail.is_reviewable;
  updateRenderReviewNavigation();
}

async function saveRenderReviewComment() {
  if (!state.selectedRenderReviewAssetId) {
    return;
  }
  renderCommentSave.disabled = true;
  showRenderMessage("Saving comment...");
  try {
    const payload = await fetchJson(
      `/api/render-review/${state.selectedRenderReviewAssetId}/comment?${currentQuery().toString()}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment: renderReviewComment.value || "" }),
      },
    );
    state.assets = payload.assets || state.assets;
    renderRenderReview(payload);
    renderAssetTable();
    showRenderMessage(payload.message || "Comment saved.");
  } catch (error) {
    showRenderMessage(error.message, "error");
  } finally {
    renderCommentSave.disabled = false;
  }
}

function renderReviewImage(container, path, exists, emptyText, altText, cacheKey = "") {
  container.replaceChildren();
  if (!exists || !path) {
    container.textContent = emptyText;
    return;
  }
  const image = document.createElement("img");
  image.alt = altText;
  image.src = fileUrl(path, cacheKey || Date.now().toString());
  image.title = path;
  container.append(image);
}

function renderCandidateImage(detail) {
  renderReviewImage(
    candidateRender,
    detail.candidate_image_path,
    detail.exists?.candidate_image,
    "No candidate image.",
    "Candidate render",
    detail.asset?.updated_at || "",
  );
}

function renderLockedImage(detail) {
  renderReviewImage(
    lockedRender,
    detail.locked_image_path,
    detail.exists?.locked_image,
    "No locked image.",
    "Locked render",
    detail.asset?.updated_at || "",
  );
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

async function promoteRenderReview() {
  if (!state.selectedRenderReviewAssetId) {
    return;
  }
  const replacingLockedImage = Boolean(state.renderReviewDetail?.exists?.locked_image);
  const params = currentQuery();
  if (replacingLockedImage) {
    const confirmed = window.confirm("A locked image already exists for this asset. Replace it with the candidate image?");
    if (!confirmed) {
      return;
    }
    params.set("replace_existing", "true");
  }
  showRenderMessage("Working...");
  try {
    const payload = await fetchJson(
      `/api/render-review/${state.selectedRenderReviewAssetId}/promote-to-locked?${params.toString()}`,
      { method: "POST" },
    );
    showRenderMessage(payload.message || "Render approved.");
    await loadRenderReviewTasks();
    await loadAssets(state.selectedAssetId);
  } catch (error) {
    showRenderMessage(error.message, "error");
  }
}

async function loadTurnarounds(preferredTurnaroundId = null) {
  if (!state.character || !state.phase) {
    turnaroundStatus.textContent = "No character/phase selected.";
    return;
  }
  turnaroundStatus.textContent = "Loading turnarounds...";
  const payload = await fetchJson(`/api/turnarounds?${currentQuery().toString()}`);
  state.turnaroundRows = payload.rows || [];
  const ids = new Set(state.turnaroundRows.map((row) => row.turnaround_id));
  state.selectedTurnaroundId =
    preferredTurnaroundId || state.selectedTurnaroundId || state.turnaroundRows[0]?.turnaround_id || null;
  if (state.selectedTurnaroundId && !ids.has(state.selectedTurnaroundId)) {
    state.selectedTurnaroundId = state.turnaroundRows[0]?.turnaround_id || null;
  }
  renderTurnaroundTable();
  const readyCount = state.turnaroundRows.filter((row) => row.ready).length;
  turnaroundStatus.textContent = `${readyCount} ready of ${state.turnaroundRows.length} turnaround task(s)`;
  if (state.selectedTurnaroundId) {
    await selectTurnaround(state.selectedTurnaroundId);
  } else {
    clearTurnaround();
  }
}

function renderTurnaroundTable() {
  turnaroundTableBody.replaceChildren();
  for (const rowData of state.turnaroundRows) {
    const row = document.createElement("tr");
    row.dataset.turnaroundId = rowData.turnaround_id;
    row.classList.toggle("selected", rowData.turnaround_id === state.selectedTurnaroundId);
    const actionCell = document.createElement("td");
    const generateButton = document.createElement("button");
    generateButton.type = "button";
    generateButton.textContent = "Generate";
    generateButton.disabled = !rowData.ready;
    generateButton.addEventListener("click", (event) => {
      event.stopPropagation();
      generateTurnaround(rowData.turnaround_id, Number(turnaroundDetectionTolerance.value || rowData.detection_tolerance || 50));
    });
    actionCell.append(generateButton);
    const promoteButton = document.createElement("button");
    promoteButton.type = "button";
    promoteButton.textContent = "Promote";
    promoteButton.disabled = !rowData.candidate_image_exists;
    promoteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      promoteTurnaround(rowData);
    });
    actionCell.append(promoteButton);
    const statusCell = document.createElement("td");
    const statusBadge = document.createElement("span");
    const normalizedStatus = String(rowData.status || "").toLowerCase();
    let badgeText = rowData.ready ? "READY" : "MISSING";
    if (normalizedStatus === "locked") {
      badgeText = "LOCKED";
    } else if (normalizedStatus.includes("candidate")) {
      badgeText = "CANDIDATE";
    }
    statusBadge.className = `status-badge ${rowData.ready ? "ready" : "missing"}`;
    statusBadge.textContent = badgeText;
    statusBadge.title = rowData.status || "";
    statusCell.append(statusBadge);
    const cells = [
      rowData.label,
      statusCell,
      `${rowData.locked_count}/8`,
    ];
    for (const value of cells) {
      const cell = document.createElement("td");
      if (value instanceof HTMLElement) {
        cell.append(...value.childNodes);
      } else {
        cell.textContent = value ?? "";
      }
      row.append(cell);
    }
    row.append(actionCell);
    const missingCell = document.createElement("td");
    missingCell.textContent = (rowData.missing_views || []).join(", ");
    row.append(missingCell);
    row.addEventListener("click", () => selectTurnaround(rowData.turnaround_id));
    turnaroundTableBody.append(row);
    for (const aux of rowData.auxiliary_sheets || []) {
      turnaroundTableBody.append(renderAuxiliaryMainTableRow(rowData, aux));
    }
  }
}

function renderAuxiliaryMainTableRow(parentRow, aux) {
  const row = document.createElement("tr");
  row.dataset.turnaroundId = aux.turnaround_id;
  row.dataset.parentTurnaroundId = parentRow.turnaround_id;
  row.classList.add("auxiliary-row");
  row.classList.toggle("selected", aux.turnaround_id === state.selectedAuxiliaryTurnaroundId);

  const labelCell = document.createElement("td");
  labelCell.textContent = `  ${aux.label}`;

  const statusCell = document.createElement("td");
  const statusBadge = document.createElement("span");
  statusBadge.className = `status-badge ${aux.locked_image_exists ? "ready" : "review"}`;
  statusBadge.textContent = aux.locked_image_exists ? "LOCKED" : "REVIEW";
  statusBadge.title = aux.status || "";
  statusCell.append(statusBadge);

  const countCell = document.createElement("td");
  countCell.textContent = `${aux.crop_percent}%`;

  const missingCell = document.createElement("td");
  missingCell.textContent = "partial";

  const actionCell = document.createElement("td");
  const promoteButton = document.createElement("button");
  promoteButton.type = "button";
  promoteButton.textContent = "Promote";
  promoteButton.disabled = !aux.candidate_image_exists;
  promoteButton.addEventListener("click", (event) => {
    event.stopPropagation();
    promoteTurnaround(aux);
  });
  actionCell.append(promoteButton);

  const deleteButton = document.createElement("button");
  deleteButton.type = "button";
  deleteButton.textContent = "Delete";
  deleteButton.disabled = !aux.deletable;
  deleteButton.addEventListener("click", (event) => {
    event.stopPropagation();
    deletePartialTurnaround(aux.turnaround_id);
  });
  actionCell.append(deleteButton);

  row.append(labelCell, statusCell, countCell, actionCell, missingCell);
  row.addEventListener("click", () => selectAuxiliaryTurnaround(parentRow.turnaround_id, aux.turnaround_id));
  return row;
}

async function selectTurnaround(turnaroundId) {
  state.selectedTurnaroundId = turnaroundId;
  state.selectedAuxiliaryTurnaroundId = null;
  turnaroundPartialLabel.value = "";
  turnaroundPartialPercent.value = "45";
  turnaroundDetectionTolerance.value = "50";
  for (const row of turnaroundTableBody.querySelectorAll("tr")) {
    row.classList.toggle("selected", row.dataset.turnaroundId === state.selectedTurnaroundId);
  }
  const detail = await fetchJson(`/api/turnarounds/${encodeURIComponent(turnaroundId)}?${currentQuery().toString()}`);
  renderTurnaround(detail.row);
}

async function selectAuxiliaryTurnaround(parentTurnaroundId, auxiliaryTurnaroundId) {
  state.selectedTurnaroundId = parentTurnaroundId;
  state.selectedAuxiliaryTurnaroundId = auxiliaryTurnaroundId;
  const detail = await fetchJson(`/api/turnarounds/${encodeURIComponent(parentTurnaroundId)}?${currentQuery().toString()}`);
  renderTurnaroundTable();
  renderTurnaround(detail.row);
}

function clearTurnaround() {
  state.turnaroundDetail = null;
  state.selectedAuxiliaryTurnaroundId = null;
  turnaroundTitle.textContent = "Select a turnaround";
  turnaroundCandidate.textContent = "No candidate image.";
  turnaroundLocked.textContent = "No locked turnaround.";
  turnaroundSourceAssets.textContent = "";
  turnaroundPaths.replaceChildren();
  turnaroundAuxTableBody.replaceChildren();
  turnaroundPartialLabel.value = "";
  turnaroundPartialPercent.value = "45";
  turnaroundDetectionTolerance.value = "50";
  turnaroundSavePartial.disabled = true;
}

function renderTurnaround(row) {
  state.turnaroundDetail = row;
  const selectedAux = (row?.auxiliary_sheets || []).find((item) => item.turnaround_id === state.selectedAuxiliaryTurnaroundId);
  if (selectedAux) {
    turnaroundPartialLabel.value = selectedAux.label || "";
    turnaroundPartialPercent.value = selectedAux.crop_percent || 45;
  }
  turnaroundDetectionTolerance.value = selectedAux
    ? (selectedAux.detection_tolerance || 50)
    : (row?.detection_tolerance || 50);
  turnaroundTitle.textContent = selectedAux ? `${row.label} | ${selectedAux.label}` : (row ? row.label : "Select a turnaround");
  renderTurnaroundPrimaryPreview(row);
  if (selectedAux) {
    renderReviewImage(
      turnaroundLocked,
      selectedAux.locked_image_path,
      selectedAux.locked_image_exists,
      "No locked partial.",
      "Locked partial turnaround",
      selectedAux.updated_at || "",
    );
  } else {
    renderReviewImage(
      turnaroundLocked,
      row?.locked_image_path,
      row?.locked_image_exists,
      "No locked turnaround.",
      "Locked turnaround",
      row?.updated_at || "",
    );
  }
  turnaroundSourceAssets.textContent = JSON.stringify(row?.source_asset_ids || [], null, 2);
  turnaroundPaths.replaceChildren();
  const paths = {
    candidate_image_path: row?.candidate_image_path || "",
    locked_image_path: row?.locked_image_path || "",
    analysis_path: row?.analysis_path || "",
    diagnostics_path: row?.diagnostics_path || "",
  };
  for (const [key, value] of Object.entries(paths)) {
    const term = document.createElement("dt");
    term.textContent = key;
    const definition = document.createElement("dd");
    definition.textContent = value;
    turnaroundPaths.append(term, definition);
  }
  turnaroundSavePartial.disabled = !row?.ready;
  turnaroundSavePartial.textContent = selectedAux ? "Update Partial" : "Create Partial";
  renderAuxiliaryTurnaroundTable(row?.auxiliary_sheets || []);
}

function renderTurnaroundPrimaryPreview(row) {
  const selectedAux = (row?.auxiliary_sheets || []).find((item) => item.turnaround_id === state.selectedAuxiliaryTurnaroundId);
  if (selectedAux) {
    renderReviewImage(
      turnaroundCandidate,
      selectedAux.candidate_image_path,
      selectedAux.candidate_image_exists,
      "No partial image.",
      "Partial turnaround",
      selectedAux.updated_at || "",
    );
    return;
  }
  renderReviewImage(
    turnaroundCandidate,
    row?.candidate_image_path,
    row?.candidate_image_exists,
    "No candidate image.",
    "Candidate turnaround",
    row?.updated_at || "",
  );
}

function renderAuxiliaryTurnaroundTable(items) {
  turnaroundAuxTableBody.replaceChildren();
  if (!items.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 3;
    cell.textContent = "None.";
    row.append(cell);
    turnaroundAuxTableBody.append(row);
    return;
  }
  for (const item of items) {
    const row = document.createElement("tr");
    row.dataset.turnaroundId = item.turnaround_id;
    row.classList.toggle("selected", item.turnaround_id === state.selectedAuxiliaryTurnaroundId);
    const labelCell = document.createElement("td");
    labelCell.textContent = item.label || "";
    const percentCell = document.createElement("td");
    percentCell.textContent = item.crop_percent ? `${item.crop_percent}%` : "";
    const actionCell = document.createElement("td");
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.textContent = "Delete";
    deleteButton.disabled = !item.deletable;
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      deletePartialTurnaround(item.turnaround_id);
    });
    actionCell.append(deleteButton);
    row.append(labelCell, percentCell, actionCell);
    row.addEventListener("click", () => {
      state.selectedAuxiliaryTurnaroundId = item.turnaround_id;
      turnaroundPartialLabel.value = item.label || "";
      turnaroundPartialPercent.value = item.crop_percent || 45;
      renderTurnaround(state.turnaroundDetail);
    });
    turnaroundAuxTableBody.append(row);
  }
}

async function generateTurnaround(turnaroundId = state.selectedTurnaroundId, detectionTolerance = null) {
  if (!turnaroundId) {
    return;
  }
  showTurnaroundMessage("Generating turnaround...");
  try {
    const tolerance = detectionTolerance ?? (
      turnaroundId === state.selectedTurnaroundId
        ? Number(turnaroundDetectionTolerance.value || 50)
        : null
    );
    const payload = await fetchJson(
      `/api/turnarounds/${encodeURIComponent(turnaroundId)}/generate?${currentQuery().toString()}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ detection_tolerance: tolerance }),
      },
    );
    state.turnaroundRows = payload.rows || state.turnaroundRows;
    renderTurnaroundTable();
    renderTurnaround(payload.row);
    state.selectedTurnaroundId = payload.row?.turnaround_id || turnaroundId;
    showTurnaroundMessage(payload.message || "Turnaround generated.");
  } catch (error) {
    showTurnaroundMessage(error.message, "error");
  }
}

async function savePartialTurnaround() {
  const row = state.turnaroundDetail;
  if (!row?.turnaround_id) {
    return;
  }
  const selectedAux = (row.auxiliary_sheets || []).find((item) => item.turnaround_id === state.selectedAuxiliaryTurnaroundId);
  showTurnaroundMessage(selectedAux ? "Updating partial turnaround..." : "Saving partial turnaround...");
  turnaroundSavePartial.disabled = true;
  try {
    const body = JSON.stringify({
      label: turnaroundPartialLabel.value || "",
      crop_percent: Number(turnaroundPartialPercent.value || 0),
      detection_tolerance: Number(turnaroundDetectionTolerance.value || 50),
    });
    const url = selectedAux
      ? `/api/turnarounds/partials/${encodeURIComponent(selectedAux.turnaround_id)}?${currentQuery().toString()}`
      : `/api/turnarounds/${encodeURIComponent(row.turnaround_id)}/partials?${currentQuery().toString()}`;
    const payload = await fetchJson(url, {
      method: selectedAux ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
    state.turnaroundRows = payload.rows || state.turnaroundRows;
    const saved = selectedAux
      ? (payload.row?.auxiliary_sheets || []).find((item) => item.turnaround_id === selectedAux.turnaround_id)
      : (payload.row?.auxiliary_sheets || []).find((item) => item.label === (turnaroundPartialLabel.value || ""));
    state.selectedAuxiliaryTurnaroundId = saved?.turnaround_id || null;
    renderTurnaroundTable();
    renderTurnaround(payload.row);
    showTurnaroundMessage(payload.message || (selectedAux ? "Partial turnaround updated." : "Partial turnaround saved."));
  } catch (error) {
    showTurnaroundMessage(error.message, "error");
  } finally {
    turnaroundSavePartial.disabled = !state.turnaroundDetail?.ready;
  }
}

async function deletePartialTurnaround(partialId) {
  if (!partialId) {
    return;
  }
  if (!window.confirm("Delete this auxiliary turnaround sheet?")) {
    return;
  }
  showTurnaroundMessage("Deleting partial turnaround...");
  try {
    const payload = await fetchJson(
      `/api/turnarounds/partials/${encodeURIComponent(partialId)}?${currentQuery().toString()}`,
      { method: "DELETE" },
    );
    state.turnaroundRows = payload.rows || state.turnaroundRows;
    state.selectedAuxiliaryTurnaroundId = null;
    renderTurnaroundTable();
    renderTurnaround(payload.row);
    showTurnaroundMessage(payload.message || "Partial turnaround deleted.");
  } catch (error) {
    showTurnaroundMessage(error.message, "error");
  }
}

async function promoteTurnaround(target = null) {
  const selectedAux = (state.turnaroundDetail?.auxiliary_sheets || []).find(
    (item) => item.turnaround_id === state.selectedAuxiliaryTurnaroundId,
  );
  const row = target || selectedAux || state.turnaroundDetail;
  if (!row?.turnaround_id) {
    return;
  }
  const params = currentQuery();
  if (row.locked_image_exists) {
    const confirmed = window.confirm("A locked turnaround already exists. Replace it with the candidate image?");
    if (!confirmed) {
      return;
    }
    params.set("replace_existing", "true");
  }
  showTurnaroundMessage("Promoting turnaround...");
  try {
    const payload = await fetchJson(
      `/api/turnarounds/${encodeURIComponent(row.turnaround_id)}/promote?${params.toString()}`,
      { method: "POST" },
    );
    state.turnaroundRows = payload.rows || state.turnaroundRows;
    renderTurnaroundTable();
    renderTurnaround(payload.row);
    showTurnaroundMessage(payload.message || "Turnaround locked.");
  } catch (error) {
    showTurnaroundMessage(error.message, "error");
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

async function dumpAiQueue() {
  // Require an explicit browser confirmation before deleting pending queue items.
  if (!window.confirm("Dump all pending AI queue asks and claimed tasks? Answers and failed folders will be left alone.")) {
    return;
  }
  await runAiControlsAction("/api/ai-controls/dump-queue");
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
  settingAiPromptReviewModel.value = automation.ai_prompt_review_model || "";
  settingAiPromptReviewFile.value = automation.ai_prompt_review_instructions_file || "";
  settingRenderBackend.value = automation.render_backend || "manual_chatgpt";
  pipelineConfigPaths.textContent = `Config: ${payload.config_path || ""} | Pipelines: ${payload.pipelines_path || ""}`;
  renderRows(projectConfigTableBody, payload.project_config_rows || [], ["Scope", "Setting", "Value"]);
  renderRows(pipelineStageTableBody, payload.pipeline_rows || [], ["pipeline", "step", "stage", "actor", "worker", "asset_count"]);
  const currentPromptReviewPipeline = promptReviewPipeline.value;
  setSelectOptions(promptReviewPipeline, payload.pipeline_names || []);
  if ((payload.pipeline_names || []).includes(currentPromptReviewPipeline)) {
    promptReviewPipeline.value = currentPromptReviewPipeline;
  }
  updatePromptReviewToggle();
  const currentPipeline = batchRenderPipeline.value;
  setSelectOptions(batchRenderPipeline, payload.pipeline_names || []);
  if ((payload.pipeline_names || []).includes(currentPipeline)) {
    batchRenderPipeline.value = currentPipeline;
  }
  pipelineControlsStatus.textContent = "Ready";
}

function updatePromptReviewToggle() {
  const modeByPipeline = state.pipelineControls?.prompt_review_modes || {};
  promptReviewMode.value = modeByPipeline[promptReviewPipeline.value] || "OFF";
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
    ai_prompt_review_model: settingAiPromptReviewModel.value,
    ai_prompt_review_instructions_file: settingAiPromptReviewFile.value,
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

async function savePromptReviewStage() {
  const pipelineName = promptReviewPipeline.value;
  if (!pipelineName) {
    return;
  }
  showPipelineControlsMessage("Saving...");
  try {
    const payload = await fetchJson(`/api/pipeline-controls/prompt-review?${currentQuery().toString()}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pipeline_name: pipelineName, mode: promptReviewMode.value }),
    });
    renderPipelineControls(payload);
    showPipelineControlsMessage(payload.message || "Prompt review setting saved.");
  } catch (error) {
    showPipelineControlsMessage(error.message, "error");
    updatePromptReviewToggle();
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
  const payload = await fetchJson(`/api/render-console/tasks?${currentQuery().toString()}`);
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
  const detail = await fetchJson(`/api/render-console/tasks/${encodeURIComponent(askId)}?${currentQuery().toString()}`);
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
  renderConsoleHelperPanel.hidden = true;
  renderConsoleHelperText.value = "";
  renderConsoleSaveHelper.disabled = true;
  renderConsoleCopyHelper.disabled = true;
  renderConsolePrompt.value = "";
  renderConsoleImagePreview.hidden = true;
  renderConsoleImagePreview.removeAttribute("src");
  renderConsoleSaveImage.disabled = true;
  renderConsoleAnswerComment.value = "";
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
  const helperText = detail.gpt_helper_prompt?.text || "";
  renderConsoleHelperText.value = helperText;
  renderConsoleHelperPanel.hidden = false;
  renderConsoleSaveHelper.disabled = false;
  renderConsoleCopyHelper.disabled = !helperText;
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
      image.src = fileUrl(reference.path, Date.now().toString());
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
  renderConsoleAnswerComment.value = "";
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

async function saveRenderConsoleHelperPrompt() {
  if (!state.selectedRenderConsoleAskId) {
    return;
  }
  renderConsoleSaveHelper.disabled = true;
  try {
    const payload = await fetchJson(
      `/api/render-console/tasks/${encodeURIComponent(state.selectedRenderConsoleAskId)}/gpt-helper-prompt?${currentQuery().toString()}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: renderConsoleHelperText.value || "" }),
      },
    );
    state.renderConsoleDetail.gpt_helper_prompt = payload.gpt_helper_prompt;
    renderConsoleHelperText.value = payload.gpt_helper_prompt?.text || "";
    renderConsoleCopyHelper.disabled = !renderConsoleHelperText.value;
    showRenderConsoleMessage(payload.message || "GPT helper prompt saved.");
  } catch (error) {
    showRenderConsoleMessage(error.message, "error");
  } finally {
    renderConsoleSaveHelper.disabled = false;
  }
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
    const params = currentQuery();
    params.set("render_comment", renderConsoleAnswerComment.value || "");
    const response = await fetch(
      `/api/render-console/tasks/${encodeURIComponent(state.selectedRenderConsoleAskId)}/answer-image?${params.toString()}`,
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
      activatePage("render-review");
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
    const response = await fetch(`/api/render-console/tasks/${encodeURIComponent(state.selectedRenderConsoleAskId)}/fail?${currentQuery().toString()}`, {
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
  image.src = fileUrl(path, Date.now().toString());
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
  saveStoredContext();
  state.selectedAssetId = null;
  state.selectedPromptReviewAssetId = null;
  state.selectedRenderReviewAssetId = null;
  state.selectedRenderConsoleAskId = null;
  state.selectedTurnaroundId = null;
  state.selectedAuxiliaryTurnaroundId = null;
  state.selectedManifestAssetId = null;
  state.selectedIdentityKeyId = null;
  state.identityKeySourceAssetId = null;
  state.identityKeyMode = "list";
  state.selectedCostumeSlug = null;
  state.selectedExpressionAssetId = null;
  updatePhaseSelect();
  renderOnboarding();
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
  if (document.querySelector("#turnarounds-page").classList.contains("active")) {
    await loadTurnarounds();
  }
  if (document.querySelector("#identity-keys-page").classList.contains("active")) {
    await loadIdentityKeys();
  }
  if (document.querySelector("#phase-comparison-page").classList.contains("active")) {
    initializePhaseComparisonControls();
    await loadPhaseComparison();
  }
  if (document.querySelector("#costumes-page").classList.contains("active")) {
    await loadCostumes();
  }
  if (document.querySelector("#expressions-page").classList.contains("active")) {
    await loadExpressions();
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
  saveStoredContext();
  updateHeaderFitmentPreview();
  state.selectedAssetId = null;
  state.selectedPromptReviewAssetId = null;
  state.selectedRenderReviewAssetId = null;
  state.selectedRenderConsoleAskId = null;
  state.selectedTurnaroundId = null;
  state.selectedAuxiliaryTurnaroundId = null;
  state.selectedManifestAssetId = null;
  state.selectedIdentityKeyId = null;
  state.identityKeySourceAssetId = null;
  state.identityKeyMode = "list";
  state.selectedCostumeSlug = null;
  state.selectedExpressionAssetId = null;
  renderOnboarding();
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
  if (document.querySelector("#turnarounds-page").classList.contains("active")) {
    await loadTurnarounds();
  }
  if (document.querySelector("#identity-keys-page").classList.contains("active")) {
    await loadIdentityKeys();
  }
  if (document.querySelector("#phase-comparison-page").classList.contains("active")) {
    initializePhaseComparisonControls();
    await loadPhaseComparison();
  }
  if (document.querySelector("#costumes-page").classList.contains("active")) {
    await loadCostumes();
  }
  if (document.querySelector("#expressions-page").classList.contains("active")) {
    await loadExpressions();
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

newCharacterButton.addEventListener("click", startNewCharacter);
newPhaseButton.addEventListener("click", startNewPhase);
toolbarSettingsButton.addEventListener("click", (event) => {
  event.stopPropagation();
  toggleToolbarSettingsMenu();
});
toolbarHarvestAi.addEventListener("click", (event) => {
  event.stopPropagation();
  harvestAiFromToolbar();
});
document.addEventListener("click", (event) => {
  if (!toolbarSettingsMenu.hidden && !toolbarSettingsMenu.contains(event.target) && event.target !== toolbarSettingsButton) {
    closeToolbarSettingsMenu();
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeToolbarSettingsMenu();
  }
});
onboardingSaveDraft.addEventListener("click", saveOnboardingDraft);
onboardingCopyGptPrompt.addEventListener("click", () => copyText(onboardingGptPrompt.value, "ChatGPT prompt copied."));
onboardingCharacter.addEventListener("input", () => updateOnboardingHelperPrompt());
onboardingPhase.addEventListener("input", () => updateOnboardingHelperPrompt());
onboardingSpecies.addEventListener("change", () => updateOnboardingHelperPrompt());
onboardingGender.addEventListener("change", () => updateOnboardingHelperPrompt());
onboardingArtStyle.addEventListener("input", () => updateOnboardingHelperPrompt());
onboardingUploadTemplate.addEventListener("click", uploadOnboardingTemplate);
assetFilterTodo.addEventListener("change", applyAssetFilters);
assetFilterHideBase.addEventListener("change", applyAssetFilters);
assetFilterPipeline.addEventListener("change", applyAssetFilters);
assetDetailStatusMode.addEventListener("click", () => setAssetDetailMode("status"));
assetDetailImageMode.addEventListener("click", () => setAssetDetailMode("locked"));
createIdentityFromAssetButton.addEventListener("click", startIdentityKeyFromSelectedAsset);
openCharacterTemplateButton.addEventListener("click", () => {
  openSourceEditorForSource(state.assetDetail?.asset?.character_template_source, showActionMessage);
});
openGoverningTemplateButton.addEventListener("click", () => {
  openSourceEditorForSource(state.assetDetail?.asset?.governing_template_source, showActionMessage);
});
identityKeyShowList.addEventListener("click", () => {
  state.identityKeyMode = "list";
  clearIdentityKeyUpdate();
  renderIdentityKeyTable();
});
identityKeyCreatePreview.addEventListener("click", createIdentityKeyPreview);
identityKeySave.addEventListener("click", saveIdentityKey);
costumeAddNew.addEventListener("click", clearCostumeForm);
costumeCreate.addEventListener("click", saveCostume);
expressionAddNew.addEventListener("click", clearExpressionForm);
expressionCreate.addEventListener("click", saveExpression);
auxResourceCategory.addEventListener("change", () => {
  clearAuxiliaryResourceForm();
  loadAuxiliaryResources();
});
auxResourceSearch.addEventListener("input", refreshAuxiliaryResourceTable);
auxResourceShowThumbnails.addEventListener("change", refreshAuxiliaryResourceTable);
auxResourceAdd.addEventListener("click", clearAuxiliaryResourceForm);
auxResourcePasteZone.addEventListener("paste", (event) => {
  const blob = imageBlobFromPasteEvent(event);
  if (blob) {
    event.preventDefault();
    setAuxiliaryResourceImageSelection(blob);
  }
});
auxResourcePasteZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  auxResourcePasteZone.classList.add("drag-over");
});
auxResourcePasteZone.addEventListener("dragleave", () => {
  auxResourcePasteZone.classList.remove("drag-over");
});
auxResourcePasteZone.addEventListener("drop", (event) => {
  event.preventDefault();
  auxResourcePasteZone.classList.remove("drag-over");
  setAuxiliaryResourceImageSelection(event.dataTransfer?.files?.[0]);
});
auxResourceFileInput.addEventListener("change", () => {
  setAuxiliaryResourceImageSelection(auxResourceFileInput.files?.[0]);
});
auxResourceSave.addEventListener("click", saveAuxiliaryResource);
auxResourceClear.addEventListener("click", clearAuxiliaryResourceForm);
auxResourceCopyTag.addEventListener("click", () => copyText(auxResourceTag.textContent || "", "Resource tag copied."));
phaseComparisonCharacter.addEventListener("change", () => {
  state.phaseComparison.character = phaseComparisonCharacter.value;
  state.phaseComparison.pipeline = "";
  state.phaseComparison.selectedIndex = 0;
  state.phaseComparison.selectedSlotKey = "";
  syncPhaseComparisonPhaseOptions();
  loadPhaseComparison({ preserveSlot: false, resetIndex: true });
});
phaseComparisonLeftPhase.addEventListener("change", () => {
  state.phaseComparison.leftPhase = phaseComparisonLeftPhase.value;
  loadPhaseComparison({ preserveSlot: true });
});
phaseComparisonRightPhase.addEventListener("change", () => {
  state.phaseComparison.rightPhase = phaseComparisonRightPhase.value;
  loadPhaseComparison({ preserveSlot: true });
});
phaseComparisonPipeline.addEventListener("change", () => {
  state.phaseComparison.pipeline = phaseComparisonPipeline.value;
  state.phaseComparison.leftCostume = "";
  state.phaseComparison.rightCostume = "";
  state.phaseComparison.selectedIndex = 0;
  state.phaseComparison.selectedSlotKey = "";
  loadPhaseComparison({ preserveSlot: false, resetIndex: true });
});
phaseComparisonLeftCostume.addEventListener("change", () => {
  state.phaseComparison.leftCostume = phaseComparisonLeftCostume.value;
  state.phaseComparison.selectedIndex = 0;
  state.phaseComparison.selectedSlotKey = "";
  loadPhaseComparison({ preserveSlot: false, resetIndex: true });
});
phaseComparisonRightCostume.addEventListener("change", () => {
  state.phaseComparison.rightCostume = phaseComparisonRightCostume.value;
  state.phaseComparison.selectedIndex = 0;
  state.phaseComparison.selectedSlotKey = "";
  loadPhaseComparison({ preserveSlot: false, resetIndex: true });
});
phaseComparisonPrev.addEventListener("click", () => movePhaseComparison(-1));
phaseComparisonNext.addEventListener("click", () => movePhaseComparison(1));
for (const imageBox of [phaseComparisonLeftImage, phaseComparisonRightImage]) {
  imageBox.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      movePhaseComparison(-1);
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      movePhaseComparison(1);
    }
  });
}

promptSearch.addEventListener("input", renderPromptText);
copyPromptButton.addEventListener("click", () => copyText(state.promptReviewDetail?.prompt_text || "", "Prompt copied."));
copyCondensedButton.addEventListener("click", () => copyText(condensedText.value, "Condensed prompt copied."));
viewCondensedButton.addEventListener("click", () => condensedDialog.showModal());
sourceOpenEditor.addEventListener("click", openSelectedSourceEditor);
sourceEditorSave.addEventListener("click", saveSourceEditor);
sourceEditorRecompile.addEventListener("click", recompileCurrentPrompt);
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
renderPromoteButton.addEventListener("click", promoteRenderReview);
renderFailRenderButton.addEventListener("click", () => runRenderReviewAction("fail-to-render"));
renderFailRegenerateButton.addEventListener("click", () => runRenderReviewAction("fail-to-regenerate"));
renderCommentSave.addEventListener("click", saveRenderReviewComment);
turnaroundSavePartial.addEventListener("click", savePartialTurnaround);
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
archiveHarvestedAiButton.addEventListener("click", () => runAiControlsAction("/api/ai-controls/archive-harvested"));
activateProxyStopButton.addEventListener("click", () => runAiControlsAction("/api/ai-controls/stop"));
resumeProxyStopButton.addEventListener("click", () => runAiControlsAction("/api/ai-controls/resume"));
dumpAiQueueButton.addEventListener("click", dumpAiQueue);
sendMonitorTestButton.addEventListener("click", () => {
  const params = new URLSearchParams({ instruction: monitorInstruction.value || "" });
  runAiControlsAction(`/api/ai-controls/monitor-test?${params.toString()}`);
});
openRenderConsoleTab.addEventListener("click", () => {
  document.querySelector('.tab[data-page="render-console"]').click();
});
automationForm.addEventListener("submit", saveAutomationSettings);
promptReviewPipeline.addEventListener("change", updatePromptReviewToggle);
promptReviewSave.addEventListener("click", savePromptReviewStage);
batchRenderResetButton.addEventListener("click", runBatchRenderReset);
renderConsoleRefresh.addEventListener("click", () => loadRenderConsoleTasks());
renderConsoleCopyPrompt.addEventListener("click", async () => {
  await navigator.clipboard.writeText(state.renderConsoleDetail?.prompt || "");
  showRenderConsoleMessage("Prompt copied.");
});
renderConsoleSaveHelper.addEventListener("click", saveRenderConsoleHelperPrompt);
renderConsoleHelperText.addEventListener("input", () => {
  renderConsoleCopyHelper.disabled = !renderConsoleHelperText.value;
});
renderConsoleCopyHelper.addEventListener("click", async () => {
  await navigator.clipboard.writeText(renderConsoleHelperText.value || "");
  showRenderConsoleMessage("GPT helper prompt copied.");
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
  loadStoredAssetFilters();
  try {
    await loadContext();
    await loadAssets();
  } catch (error) {
    assetStatus.textContent = error.message;
  }
}

main();
