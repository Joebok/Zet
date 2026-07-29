const state = {
  characters: [],
  phasesByCharacter: {},
  onboardingStatuses: {},
  headerPreviews: {},
  onboardingOptions: { species_ancestry: [], gender_presentation: [] },
  auxiliaryResourceCategories: [],
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
  selectedPromptReviewAskId: null,
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
  renderConsoleHarvestTimer: null,
  renderConsoleHarvestRunsRemaining: 0,
  localImageReviewTasks: [],
  selectedLocalImageReviewAskId: null,
  localImageReviewDetail: null,
  localImageReviewHarvestTimer: null,
  localImageReviewHarvestRunsRemaining: 0,
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
  stories: [],
  hasStoryChanges: false,
  selectedStorySlug: null,
  storyDetail: null,
  storySettings: null,
  scenes: [],
  selectedSceneSlug: null,
  sceneDetail: null,
  zines: [],
  selectedZineSlug: null,
  zineDocument: null,
  zineStorySlug: null,
  zineStorySources: [],
  sceneImageReferences: [],
  scenePickerCharacter: "",
  scenePickerSearch: "",
  sceneBuilder: null,
  sceneBuilderOptions: {},
  sceneBuilderReferences: [],
  sceneBuilderOpen: false,
  selectedBuilderPlacementId: null,
  selectedBuilderElementId: null,
  sceneBuilderRendering: false,
  builderImagePickerReferences: [],
  builderImagePickerSearch: "",
  builderElementAuxResources: {},
  builderElementCostumes: [],
  builderCostumesByCharacterPhase: {},
  auxiliaryResources: [],
  selectedAuxiliaryResourceId: null,
  selectedAuxiliaryImageId: null,
  auxiliaryResourceImageBlob: null,
  phaseComparison: {
    character: "",
    leftPhase: "",
    rightPhase: "",
    pipeline: "Character-Assembly",
    leftCostume: "",
    rightCostume: "",
    selectedIndex: 0,
    selectedSlotKey: "",
    rows: [],
  },
  savedBaselines: {
    story: "",
    scene: "",
    sceneBuilder: "",
    sourceEditor: "",
    zine: "",
    settings: "",
  },
  transitionPromise: null,
};

const LAST_CONTEXT_STORAGE_KEY = "zet:last-character-phase";
const HIDE_BASE_IMAGES_STORAGE_KEY = "zet:asset-hide-base-images";

const characterSelect = document.querySelector("#character-select");
const phaseSelect = document.querySelector("#phase-select");
const newCharacterButton = document.querySelector("#new-character");
const newPhaseButton = document.querySelector("#new-phase");
const characterAssetsMenu = document.querySelector("#character-assets-menu");
const headerFitmentPreview = document.querySelector("#header-fitment-preview");
const toolbarTodoButton = document.querySelector("#toolbar-todo-button");
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
const promptReviewRefresh = document.querySelector("#prompt-review-refresh");
const promptReviewTitle = document.querySelector("#prompt-review-title");
const promptReviewMessage = document.querySelector("#prompt-review-message");
const promptSearch = document.querySelector("#prompt-search");
const promptPath = document.querySelector("#prompt-path");
const promptText = document.querySelector("#prompt-text");
const promptReviewSceneBuilder = document.querySelector("#prompt-review-scene-builder");
const copyPromptButton = document.querySelector("#copy-prompt");
const analyzePromptButton = document.querySelector("#analyze-prompt");
const viewPromptAnalysisButton = document.querySelector("#view-prompt-analysis");
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
const localImageConfigMessage = document.querySelector("#local-image-config-message");
const harvestAiButton = document.querySelector("#harvest-ai");
const archiveHarvestedAiButton = document.querySelector("#archive-harvested-ai");
const refreshAiControlsButton = document.querySelector("#refresh-ai-controls");
const processTableBody = document.querySelector("#process-table tbody");
const queueCounts = document.querySelector("#queue-counts");
const queueAskTableBody = document.querySelector("#queue-ask-table tbody");
const queueRunningTableBody = document.querySelector("#queue-running-table tbody");
const queueAnswerTableBody = document.querySelector("#queue-answer-table tbody");
const openRenderConsoleTab = document.querySelector("#open-render-console-tab");
const manualRenderCount = document.querySelector("#manual-render-count");
const manualRenderTableBody = document.querySelector("#manual-render-table tbody");
const pipelineControlsStatus = document.querySelector("#pipeline-controls-status");
const pipelineControlsMessage = document.querySelector("#pipeline-controls-message");
const automationForm = document.querySelector("#automation-form");
const settingLocalRenderBackend = document.querySelector("#setting-local-render-backend");
const stableMatrixSettings = document.querySelector("#stable-matrix-settings");
const comfyuiSettings = document.querySelector("#comfyui-settings");
const settingLocalRenderForgeCouple = document.querySelector("#setting-local-render-forge-couple");
const settingLocalRenderPreset = document.querySelector("#setting-local-render-preset");
const settingLocalRenderCheckpoint = document.querySelector("#setting-local-render-checkpoint");
const refreshLocalRenderCheckpoints = document.querySelector("#refresh-local-render-checkpoints");
const settingLocalRenderPositiveGlobals = document.querySelector("#setting-local-render-positive-globals");
const settingLocalRenderNegativeGlobals = document.querySelector("#setting-local-render-negative-globals");
const settingComfyuiProfile = document.querySelector("#setting-comfyui-profile");
const settingComfyuiServerUrl = document.querySelector("#setting-comfyui-server-url");
const settingComfyuiCheckpoint = document.querySelector("#setting-comfyui-checkpoint");
const refreshComfyuiCheckpoints = document.querySelector("#refresh-comfyui-checkpoints");
const settingComfyuiPositiveGlobals = document.querySelector("#setting-comfyui-positive-globals");
const settingComfyuiNegativeGlobals = document.querySelector("#setting-comfyui-negative-globals");
const settingComfyuiPollSeconds = document.querySelector("#setting-comfyui-poll-seconds");
const settingComfyuiTimeoutSeconds = document.querySelector("#setting-comfyui-timeout-seconds");
const settingZinePrintScale = document.querySelector("#setting-zine-print-scale");
const settingZinePageMargin = document.querySelector("#setting-zine-page-margin");
const zineMarginHelp = document.querySelector("#zine-margin-help");
const settingZineWidth = document.querySelector("#setting-zine-width");
const settingTurnaroundWidth = document.querySelector("#setting-turnaround-width");
const settingAiHarvestAuto = document.querySelector("#setting-ai-harvest-auto");
const settingAiHarvestInterval = document.querySelector("#setting-ai-harvest-interval");
const settingAiPromptAnalysisModel = document.querySelector("#setting-ai-prompt-analysis-model");
const refreshOllamaModels = document.querySelector("#refresh-ollama-models");
const settingAiPromptAnalysisFile = document.querySelector("#setting-ai-prompt-analysis-file");
const settingRenderBackend = document.querySelector("#setting-render-backend");
const pipelineConfigPaths = document.querySelector("#pipeline-config-paths");
const projectConfigTableBody = document.querySelector("#project-config-table tbody");
const pipelineStageTableBody = document.querySelector("#pipeline-stage-table tbody");
const batchRenderPipeline = document.querySelector("#batch-render-pipeline");
const batchIncludeLocked = document.querySelector("#batch-include-locked");
const batchRenderResetButton = document.querySelector("#batch-render-reset");
const batchRenderResultTableBody = document.querySelector("#batch-render-result-table tbody");
const sourceEditorStatus = document.querySelector("#source-editor-status");
const sourceEditorMessage = document.querySelector("#source-editor-message");
const sourceEditorWarning = document.querySelector("#source-editor-warning");
const sourceEditorTitle = document.querySelector("#source-editor-title");
const sourceEditorSave = document.querySelector("#source-editor-save");
const sourceEditorSaveState = document.querySelector("#source-editor-save-state");
const sourceEditorMeta = document.querySelector("#source-editor-meta");
const sourceEditorText = document.querySelector("#source-editor-text");
const storySaveState = document.querySelector("#story-save-state");
const sceneSaveState = document.querySelector("#scene-save-state");
const settingsSaveState = document.querySelector("#settings-save-state");
const unsavedChangesDialog = document.querySelector("#unsaved-changes-dialog");
const unsavedChangesMessage = document.querySelector("#unsaved-changes-message");
const confirmationDialog = document.querySelector("#confirmation-dialog");
const confirmationTitle = document.querySelector("#confirmation-title");
const confirmationMessage = document.querySelector("#confirmation-message");
const confirmationConfirm = document.querySelector("#confirmation-confirm");
const todoDialog = document.querySelector("#todo-dialog");
const todoForm = document.querySelector("#todo-form");
const todoText = document.querySelector("#todo-text");
const promptAnalysisDialog = document.querySelector("#prompt-analysis-dialog");
const promptAnalysisClose = document.querySelector("#prompt-analysis-close");
const promptAnalysisFrame = document.querySelector("#prompt-analysis-frame");
const renderConsoleStatus = document.querySelector("#render-console-status");
const renderConsoleTaskBody = document.querySelector("#render-console-task-table tbody");
const renderConsolePrev = document.querySelector("#render-console-prev");
const renderConsoleNext = document.querySelector("#render-console-next");
const renderConsoleRefresh = document.querySelector("#render-console-refresh");
const renderConsoleTitle = document.querySelector("#render-console-title");
const renderConsoleSceneBuilder = document.querySelector("#render-console-scene-builder");
const renderConsoleReviewPrompt = document.querySelector("#render-console-review-prompt");
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
const renderConsoleLocalTest = document.querySelector("#render-console-local-test");
const renderConsoleCopyLocalApiParams = document.querySelector("#render-console-copy-local-api-params");
const renderConsoleLocalApiPopover = document.querySelector("#render-console-local-api-popover");
const renderConsoleLocalApiText = document.querySelector("#render-console-local-api-text");
const renderConsoleLocalApiCopy = document.querySelector("#render-console-local-api-copy");
const renderConsoleClearLocalTest = document.querySelector("#render-console-clear-local-test");
const renderConsoleLocalStatus = document.querySelector("#render-console-local-status");
const renderConsoleLocalTestRender = document.querySelector("#render-console-local-test-render");
const renderConsolePasteZone = document.querySelector("#render-console-paste-zone");
const renderConsoleFileInput = document.querySelector("#render-console-file-input");
const renderConsoleImagePreview = document.querySelector("#render-console-image-preview");
const renderConsoleSaveImage = document.querySelector("#render-console-save-image");
const renderConsoleSaveStatus = document.querySelector("#render-console-save-status");
const renderConsoleAnswerComment = document.querySelector("#render-console-answer-comment");
const renderConsoleFailReason = document.querySelector("#render-console-fail-reason");
const renderConsoleFailTask = document.querySelector("#render-console-fail-task");
const renderConsoleFailStatus = document.querySelector("#render-console-fail-status");
const localImageReviewStatus = document.querySelector("#local-image-review-status");
const localImageReviewTaskBody = document.querySelector("#local-image-review-task-table tbody");
const localImageReviewPrev = document.querySelector("#local-image-review-prev");
const localImageReviewNext = document.querySelector("#local-image-review-next");
const localImageReviewRefresh = document.querySelector("#local-image-review-refresh");
const localImageReviewTitle = document.querySelector("#local-image-review-title");
const localImageReviewClear = document.querySelector("#local-image-review-clear");
const localImageReviewCount = document.querySelector("#local-image-review-count");
const localImageReviewGenerate = document.querySelector("#local-image-review-generate");
const localImageReviewGenerateAllModels = document.querySelector("#local-image-review-generate-all-models");
const localImageReviewMessage = document.querySelector("#local-image-review-message");
const localImageReviewGallery = document.querySelector("#local-image-review-gallery");
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
const storyStatus = document.querySelector("#story-status");
const storyMessage = document.querySelector("#story-message");
const storyTableBody = document.querySelector("#story-table tbody");
const storyEditorTitle = document.querySelector("#story-editor-title");
const storySave = document.querySelector("#story-save");
const storyDelete = document.querySelector("#story-delete");
const storySettingsLoad = document.querySelector("#story-settings-load");
const storySettingsSave = document.querySelector("#story-settings-save");
const storyNewTitle = document.querySelector("#story-new-title");
const storyCreate = document.querySelector("#story-create");
const storyValidation = document.querySelector("#story-validation");
const storyText = document.querySelector("#story-text");
const storySettingsJson = document.querySelector("#story-settings-json");
const storySettingsFields = document.querySelector("#story-settings-fields");
const storyGitWarning = document.querySelector("#story-git-warning");
const storyGitStatus = document.querySelector("#story-git-status");
const storyGitPull = document.querySelector("#story-git-pull");
const storyGitCommit = document.querySelector("#story-git-commit");
const storyGitOutput = document.querySelector("#story-git-output");
const sceneStatus = document.querySelector("#scene-status");
const sceneMessage = document.querySelector("#scene-message");
const sceneStorySelect = document.querySelector("#scene-story-select");
const sceneNewName = document.querySelector("#scene-new-name");
const sceneCreate = document.querySelector("#scene-create");
const sceneTableBody = document.querySelector("#scene-table tbody");
const sceneEditorTitle = document.querySelector("#scene-editor-title");
const sceneSave = document.querySelector("#scene-save");
const sceneStageRender = document.querySelector("#scene-stage-render");
const sceneBuilderOpen = document.querySelector("#scene-builder-open");
const sceneDelete = document.querySelector("#scene-delete");
const sceneToggleImage = document.querySelector("#scene-toggle-image");
const sceneValidation = document.querySelector("#scene-validation");
const sceneImagePanel = document.querySelector("#scene-image-panel");
const sceneImagePreview = document.querySelector("#scene-image-preview");
const zineStatus = document.querySelector("#zine-status");
const zineMessage = document.querySelector("#zine-message");
const zineTableBody = document.querySelector("#zine-table tbody");
const zineNew = document.querySelector("#zine-new");
const zineEditorTitle = document.querySelector("#zine-editor-title");
const zineEdit = document.querySelector("#zine-edit");
const zineRegenerate = document.querySelector("#zine-regenerate");
const zineDelete = document.querySelector("#zine-delete");
const zineSave = document.querySelector("#zine-save");
const zineStorySelect = document.querySelector("#zine-story-select");
const zineFillStory = document.querySelector("#zine-fill-story");
const zineName = document.querySelector("#zine-name");
const zineSceneOptions = document.querySelector("#zine-scene-options");
const zineFront = document.querySelector("#zine-front");
const zinePage1 = document.querySelector("#zine-page-1");
const zinePage2 = document.querySelector("#zine-page-2");
const zinePage3 = document.querySelector("#zine-page-3");
const zinePage4 = document.querySelector("#zine-page-4");
const zinePage5 = document.querySelector("#zine-page-5");
const zinePage6 = document.querySelector("#zine-page-6");
const zineBack = document.querySelector("#zine-back");
const zineSpread1 = document.querySelector("#zine-spread-1");
const zineSpread3 = document.querySelector("#zine-spread-3");
const zineSpread5 = document.querySelector("#zine-spread-5");
const zinePreviewSection = document.querySelector("#zine-preview-section");
const zinePreview = document.querySelector("#zine-preview");
const sceneBuilderStatus = document.querySelector("#scene-builder-status");
const sceneBuilderPrevious = document.querySelector("#scene-builder-previous");
const sceneBuilderNext = document.querySelector("#scene-builder-next");
const sceneBuilderMessage = document.querySelector("#scene-builder-message");
const sceneBuilderPanel = document.querySelector("#scene-builder-panel");
const builderImagePickerModal = document.querySelector("#builder-image-picker-modal");
const builderElementModal = document.querySelector("#builder-element-modal");
const builderContinueModal = document.querySelector("#builder-continue-modal");
const builderContinueScene = document.querySelector("#builder-continue-scene");
const builderContinueCancel = document.querySelector("#builder-continue-cancel");
const builderContinueConfirm = document.querySelector("#builder-continue-confirm");
const builderElementResourceType = document.querySelector("#builder-element-resource-type");
const builderElementCharacterSection = document.querySelector("#builder-element-character-section");
const builderElementCharacter = document.querySelector("#builder-element-character");
const builderElementPhase = document.querySelector("#builder-element-phase");
const builderElementCostume = document.querySelector("#builder-element-costume");
const builderElementAuxSection = document.querySelector("#builder-element-aux-section");
const builderElementAux = document.querySelector("#builder-element-aux");
const builderElementSceneSection = document.querySelector("#builder-element-scene-section");
const builderElementSceneName = document.querySelector("#builder-element-scene-name");
const builderElementCancel = document.querySelector("#builder-element-cancel");
const builderElementAdd = document.querySelector("#builder-element-add");
const builderImagePickerClose = document.querySelector("#builder-image-picker-close");
const builderImagePickerCharacter = document.querySelector("#builder-image-picker-character");
const builderImagePickerSearch = document.querySelector("#builder-image-picker-search");
const builderImagePickerRefresh = document.querySelector("#builder-image-picker-refresh");
const builderImagePickerStatus = document.querySelector("#builder-image-picker-status");
const builderImagePickerTableBody = document.querySelector("#builder-image-picker-table tbody");
const sceneText = document.querySelector("#scene-text");
const scenePickerCharacter = document.querySelector("#scene-picker-character");
const scenePickerSearch = document.querySelector("#scene-picker-search");
const scenePickerRefresh = document.querySelector("#scene-picker-refresh");
const scenePickerStatus = document.querySelector("#scene-picker-status");
const scenePickerTableBody = document.querySelector("#scene-picker-table tbody");
const fullscreenImageOverlay = document.createElement("dialog");
fullscreenImageOverlay.className = "fullscreen-image-overlay";
fullscreenImageOverlay.setAttribute("aria-label", "Full-size image");
const fullscreenImageClose = document.createElement("button");
fullscreenImageClose.type = "button";
fullscreenImageClose.className = "fullscreen-image-close";
fullscreenImageClose.textContent = "Close";
fullscreenImageClose.setAttribute("aria-label", "Close full-size image");
const fullscreenImage = document.createElement("img");
fullscreenImage.alt = "";
const fullscreenImagePrevious = document.createElement("button");
fullscreenImagePrevious.type = "button";
fullscreenImagePrevious.className = "fullscreen-image-navigation fullscreen-image-previous";
fullscreenImagePrevious.setAttribute("aria-label", "Previous scene");
fullscreenImagePrevious.textContent = "‹";
fullscreenImagePrevious.hidden = true;
const fullscreenImageNext = document.createElement("button");
fullscreenImageNext.type = "button";
fullscreenImageNext.className = "fullscreen-image-navigation fullscreen-image-next";
fullscreenImageNext.setAttribute("aria-label", "Next scene");
fullscreenImageNext.textContent = "›";
fullscreenImageNext.hidden = true;
const fullscreenImageEmpty = document.createElement("p");
fullscreenImageEmpty.className = "fullscreen-image-empty";
fullscreenImageEmpty.hidden = true;
const fullscreenCropBox = document.createElement("div");
fullscreenCropBox.className = "fullscreen-crop-box";
fullscreenCropBox.hidden = true;
fullscreenImageOverlay.append(
  fullscreenImageClose,
  fullscreenImagePrevious,
  fullscreenImage,
  fullscreenImageEmpty,
  fullscreenImageNext,
  fullscreenCropBox,
);
document.body.append(fullscreenImageOverlay);
const auxResourceStatus = document.querySelector("#aux-resource-status");
const auxResourceMessage = document.querySelector("#aux-resource-message");
const auxResourceCategory = document.querySelector("#aux-resource-category");
const auxResourceSearch = document.querySelector("#aux-resource-search");
const auxResourceTable = document.querySelector("#aux-resource-table");
const auxResourceTableBody = document.querySelector("#aux-resource-table tbody");
const auxResourceAdd = document.querySelector("#aux-resource-add");
const auxResourceFormTitle = document.querySelector("#aux-resource-form-title");
const auxResourceFormCategory = document.querySelector("#aux-resource-form-category");
const auxResourceLabel = document.querySelector("#aux-resource-label");
const auxResourceEditTemplate = document.querySelector("#aux-resource-edit-template");
const auxResourcePasteZone = document.querySelector("#aux-resource-paste-zone");
const auxResourceFileInput = document.querySelector("#aux-resource-file-input");
const auxResourceImagePreview = document.querySelector("#aux-resource-image-preview");
auxResourceImagePreview.classList.add("fullscreen-image-trigger");
const auxResourceSave = document.querySelector("#aux-resource-save");
const auxResourceClear = document.querySelector("#aux-resource-clear");
const auxResourceImageList = document.querySelector("#aux-resource-image-list");
const auxResourceNewImage = document.querySelector("#aux-resource-new-image");
const auxResourceImageLabel = document.querySelector("#aux-resource-image-label");
const auxResourceSaveImage = document.querySelector("#aux-resource-save-image");
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
const busyCounts = new WeakMap();

function setBusy(container, busy) {
  if (!container) return;
  const next = Math.max(0, (busyCounts.get(container) || 0) + (busy ? 1 : -1));
  busyCounts.set(container, next);
  if (next) container.setAttribute("aria-busy", "true");
  else container.removeAttribute("aria-busy");
}

async function fetchJson(url, options = {}) {
  const busyTarget = document.querySelector("main > .page.active");
  setBusy(busyTarget, true);
  try {
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
  } finally {
    setBusy(busyTarget, false);
  }
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

function basename(path) {
  // Return the final filename segment from a Windows or POSIX path.
  return String(path || "").split(/[\\/]/).filter(Boolean).pop() || "";
}

function showMessageElement(container, message, kind = "info") {
  container.textContent = message || "";
  container.className = `action-message ${kind}`;
  container.hidden = !message;
  container.setAttribute("role", kind === "error" ? "alert" : "status");
  container.setAttribute("aria-live", kind === "error" ? "assertive" : "polite");
  container.setAttribute("aria-atomic", "true");
}

function showActionMessage(message, kind = "info") {
  showMessageElement(actionMessage, message, kind);
}

function showPromptMessage(message, kind = "info") {
  showMessageElement(promptReviewMessage, message, kind);
}

function showRenderMessage(message, kind = "info") {
  showMessageElement(renderReviewMessage, message, kind);
}

function showAiControlsMessage(message, kind = "info") {
  showMessageElement(aiControlsMessage, message, kind);
}

function showLocalImageConfigMessage(message, kind = "info") {
  showMessageElement(localImageConfigMessage, message, kind);
}

function showPipelineControlsMessage(message, kind = "info") {
  showMessageElement(pipelineControlsMessage, message, kind);
}

function showSourceEditorMessage(message, kind = "info") {
  showMessageElement(sourceEditorMessage, message, kind);
}

function showRenderConsoleMessage(message, kind = "info") {
  showMessageElement(renderConsoleMessage, message, kind);
}

function showManifestMessage(message, kind = "info") {
  showMessageElement(manifestMessage, message, kind);
}

function showTurnaroundMessage(message, kind = "info") {
  showMessageElement(turnaroundMessage, message, kind);
}

function showIdentityKeyMessage(message, kind = "info") {
  showMessageElement(identityKeyMessage, message, kind);
}

function showCostumeMessage(message, kind = "info") {
  showMessageElement(costumeMessage, message, kind);
}

function showExpressionMessage(message, kind = "info") {
  showMessageElement(expressionMessage, message, kind);
}

function showStoryMessage(message, kind = "info") {
  showMessageElement(storyMessage, message, kind);
}

function updateStoryGitWarning(hasChanges) {
  state.hasStoryChanges = Boolean(hasChanges);
  storyGitWarning.hidden = !state.hasStoryChanges;
}

function applyStoryGitPayload(payload) {
  updateStoryGitWarning(payload.has_story_changes);
  storyGitOutput.textContent = payload.output || "";
  if (payload.conflict) {
    alert("Git reported a conflict. Handle the conflicts with VS Code.");
  }
}

function showSceneMessage(message, kind = "info") {
  showMessageElement(sceneMessage, message, kind);
}

function showZineMessage(message, kind = "info") {
  showMessageElement(zineMessage, message, kind);
}

function showSceneBuilderMessage(message, kind = "info") {
  showMessageElement(sceneBuilderMessage, message, kind);
}

function showAuxResourceMessage(message, kind = "info") {
  showMessageElement(auxResourceMessage, message, kind);
}

function showPhaseComparisonMessage(message, kind = "info") {
  showMessageElement(phaseComparisonMessage, message, kind);
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

function makeSelectableRow(row, label, selected, onSelect) {
  const firstCell = row.cells[0];
  if (!firstCell) return;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "row-selection-button";
  button.setAttribute("aria-label", `Select ${label}`);
  if (selected) button.setAttribute("aria-current", "true");
  while (firstCell.firstChild) button.append(firstCell.firstChild);
  firstCell.append(button);
  row.classList.toggle("selected", selected);
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    onSelect();
  });
  row.addEventListener("click", (event) => {
    if (!event.target.closest("button, input, select, textarea, a")) onSelect();
  });
}

function updateSelectableRows(tbody, predicate) {
  for (const row of tbody.querySelectorAll("tr")) {
    const selected = predicate(row);
    row.classList.toggle("selected", selected);
    const button = row.querySelector(".row-selection-button");
    if (button) {
      if (selected) button.setAttribute("aria-current", "true");
      else button.removeAttribute("aria-current");
    }
  }
}

function renderEmptyRow(tbody, columns, message) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = columns;
  cell.className = "empty-table-cell";
  cell.textContent = message;
  row.append(cell);
  tbody.append(row);
}

function formatLocalTimestamp(value) {
  if (value === null || value === undefined || value === "") return "";
  const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function appendAssetSelectionCell(row, task) {
  const cell = document.createElement("td");
  cell.textContent = task.display_label || (task.asset_id != null ? `Asset ${task.asset_id}` : task.ask_id);
  cell.title = task.ask_id || "";
  row.append(cell);
}

function renderAssetTaskTable(tbody, tasks, selectedAskId, selectTask, emptyMessage) {
  tbody.replaceChildren();
  if (!tasks.length) {
    renderEmptyRow(tbody, 1, emptyMessage);
    return;
  }
  for (const task of tasks) {
    const row = document.createElement("tr");
    row.dataset.askId = task.ask_id;
    appendAssetSelectionCell(row, task);
    makeSelectableRow(row, task.display_label || task.ask_id, task.ask_id === selectedAskId, () => selectTask(task.ask_id));
    tbody.append(row);
  }
}

function updateAssetTaskNavigation(tasks, selectedAskId, previousButton, nextButton) {
  const index = tasks.findIndex((task) => task.ask_id === selectedAskId);
  previousButton.disabled = index <= 0;
  nextButton.disabled = index < 0 || index >= tasks.length - 1;
}

function selectAdjacentAssetTask(tasks, selectedAskId, offset, selectTask) {
  const index = tasks.findIndex((task) => task.ask_id === selectedAskId);
  const adjacentTask = tasks[index + offset];
  if (adjacentTask) {
    selectTask(adjacentTask.ask_id);
  }
}

function setSelectOptions(select, values) {
  select.replaceChildren(...values.map((value) => option(value)));
}

function setSelectOptionsWithLabels(select, items) {
  select.replaceChildren(...items.map((item) => option(item.value, item.label)));
}

function getPathValue(object, path) {
  return String(path || "").split(".").reduce((current, part) => current?.[part], object);
}

function setPathValue(object, path, value) {
  const parts = String(path || "").split(".");
  let current = object;
  for (const part of parts.slice(0, -1)) {
    if (!current[part] || typeof current[part] !== "object") {
      current[part] = {};
    }
    current = current[part];
  }
  current[parts.at(-1)] = value;
}

function numberOrText(value) {
  const text = String(value ?? "").trim();
  if (!text) {
    return "";
  }
  const numeric = Number(text);
  return Number.isFinite(numeric) && String(numeric) === text ? numeric : value;
}

function builderOptions(name) {
  return state.sceneBuilderOptions?.[name] || [];
}

function builderOptionHtml(name, selected = "") {
  return builderOptions(name).map((value) => `<option value="${escapeHtml(value)}"${value === selected ? " selected" : ""}>${escapeHtml(value)}</option>`).join("");
}

const SCENE_BUILDER_HELP = {
  "scene.name": "Human-readable scene title.",
  "scene.story_settings_path": "Path to the companion .story.json file containing story-wide art style, dialogue style, and compiler defaults.",
  "scene.associated_png_path": "Path where the rendered image for this scene should be stored or found.",
  "scene.story_beat": "One sentence describing the visual moment or change the image must communicate. Describe what is happening now, not the surrounding plot.",
  "scene.author_notes": "Private author notes. These are not automatically included in prompts unless explicitly compiled.",
  "setup.canvas.orientation": "Image orientation: landscape, portrait, square, comic panel, or custom.",
  "setup.canvas.aspect_ratio": "Target image shape such as 16:9, 4:3, 4:5, 1:1, or custom.",
  "setup.environment.location": "Where the scene takes place. Keep this visual and concrete.",
  "setup.environment.lighting": "Lighting direction, quality, and color.",
  "setup.environment.mood": "Emotional atmosphere conveyed by the image.",
  "setup.environment.weather_or_atmosphere": "Weather, haze, smoke, dust, fresh air, magical glow, or similar environmental conditions.",
  "setup.environment.general_foreground_notes": "Foreground details that support the scene without needing individual elements.",
  "setup.environment.general_background_notes": "Background details that support the scene without needing individual elements.",
  "final_image_prompt_overrides.anatomical_requirements": "Complete Markdown section that replaces the global Anatomical Requirements section when nonblank.",
  "final_image_prompt_overrides.avoid": "Complete Markdown section that replaces the global Avoid section when nonblank.",
  "final_image_prompt_overrides.high_risk_elements": "Complete Markdown section that replaces the global High-Risk Elements section when nonblank.",
  "final_image_prompt_overrides.final_verification": "Complete Markdown section that replaces the global Final Verification section when nonblank.",
  "scene_elements[].display_name": "Human-readable label shown in the UI and generated prompts.",
  "scene_elements[].resource_type": "Where this element comes from: Character, an auxiliary resource type, or Scene-Only.",
  "scene_elements[].element_type": "Type of visible thing: Character, Monster, Prop, or Backdrop.",
  "scene_elements[].reference_images[].tag": "Resolvable image reference tag used by Zet, such as {{ASSET:...}} or {{AUX:...}}.",
  "scene_elements[].element_visual_override": "Element-specific visual override. Use only for temporary scene-specific changes.",
  "scene_elements[].fallback_visual_description": "Short local visual description used only if no canonical source or reference is available.",
  "scene_elements[].notes": "Private notes for this element in this scene.",
  "placements[].position_within_cell": "Position inside the grid cell, or None to suppress placement output for this element.",
  "placements[].depth": "Depth layer: foreground, midground, background, or distant background.",
  "placements[].world_position": "Location within the scene, such as \"at the edge of the pit\" or \"inside the doorway.\"",
  "placements[].pose.summary": "Concise pose summary.",
  "placements[].pose.gaze_target_element_id": "Element ID that this element is looking at.",
  "placements[].pose.expression": "Facial expression or visible emotional state.",
  "setup.composition.focal_point": "The person, action, or visual relationship viewers should notice first.",
  "setup.composition.left_to_right": "Order the important visible elements as the viewer should encounter them from the left side of the image to the right.",
  "setup.composition.composition_notes": "Optional brief instruction about framing, overlap, spacing, or a major visual relationship not captured by placement fields.",
  "placements[].motion.state": "Whether this element is still or visibly moving in the scene.",
  "placements[].motion.direction_screen": "The direction the element is visibly moving within the finished image.",
  "placements[].motion.cue": "A short visual description showing movement, such as trailing hair, a lifted foot, flying fabric, falling debris, or a blurred limb.",
  "placements[].placement_notes": "Private notes about this placement.",
  "interactions[].subject_element_id": "Element initiating or owning the interaction.",
  "interactions[].action": "Action relationship, such as offers, attacks, protects, reaches toward, blocks, watches, or mutual eye contact.",
  "interactions[].target_element_id": "Element receiving or targeted by the interaction.",
  "interactions[].notes": "Private interaction notes.",
  "custom_interactions": "Additional render interactions, one instruction per line.",
  "dialogue[].speaker_element_id": "Element ID of the speaker.",
  "dialogue[].text": "Exact dialogue text to render. Keep punctuation final.",
  "dialogue[].target_element_id": "Who the dialogue is addressed to, if anyone.",
  "dialogue[].pointer_target": "Where the dialogue pointer should aim, usually the speaker's mouth.",
  "dialogue[].max_lines": "Maximum preferred number of wrapped text lines.",
  "dialogue[].notes": "Private dialogue notes.",
  "render_settings.final_image_prompt.output_path": "Where to write the final image prompt markdown.",
  "render_settings.local_render_brief.output_path": "Where to write the local render brief.",
  "render_settings.local_render_prompt.output_path": "Where to write the local render prompt.",
  "render_settings.scene_render_ir.output_path": "Where to write the normalized scene render IR for debugging.",
};

function builderHelpPath(path) {
  return String(path || "").replace(/\.\d+(?=\.|$)/g, "[]");
}

let builderHelpSequence = 0;

function builderCaption(label, path) {
  const helpPath = builderHelpPath(path);
  const help = SCENE_BUILDER_HELP[helpPath];
  const parenthetical = String(label).match(/^\(([^)]+)\)/);
  const conciseLabel = (parenthetical?.[1] || String(label)).replace(/\s*:\s*\.\.\.$|\.\.\.$/g, "").trim();
  if (!help) {
    return `<span class="field-caption"><span>${escapeHtml(conciseLabel)}</span></span>`;
  }
  const helpId = `builder-help-${++builderHelpSequence}`;
  return `<span class="field-caption"><span>${escapeHtml(conciseLabel)}</span><button type="button" class="field-help-button" data-builder-help="${escapeHtml(helpPath)}" aria-label="Help for ${escapeHtml(conciseLabel)}" aria-expanded="false" aria-controls="${helpId}">?</button><span id="${helpId}" class="field-help-text" role="note" hidden>${escapeHtml(help)}</span></span>`;
}

function builderField(path, label, optionsName = "", full = false, type = "text") {
  const value = getPathValue(state.sceneBuilder, path) ?? "";
  const className = full ? ' class="full"' : "";
  if (optionsName) {
    return `<label${className}>${builderCaption(label, path)}<select data-builder-field="${escapeHtml(path)}">${builderOptionHtml(optionsName, value)}</select></label>`;
  }
  if (type === "textarea") {
    return `<label${className}>${builderCaption(label, path)}<textarea data-builder-field="${escapeHtml(path)}">${escapeHtml(value)}</textarea></label>`;
  }
  return `<label${className}>${builderCaption(label, path)}<input type="${type}" value="${escapeHtml(value)}" data-builder-field="${escapeHtml(path)}"></label>`;
}

function closeFullscreenImage() {
  resetFullscreenCrop();
  resetFullscreenNavigation();
  if (fullscreenImageOverlay.open) {
    fullscreenImageOverlay.close();
  }
  fullscreenImage.removeAttribute("src");
  fullscreenImage.alt = "";
}

let fullscreenSceneNavigation = null;

function resetFullscreenNavigation() {
  fullscreenSceneNavigation = null;
  fullscreenImagePrevious.hidden = true;
  fullscreenImageNext.hidden = true;
  fullscreenImageEmpty.hidden = true;
  fullscreenImageEmpty.textContent = "";
  fullscreenImage.hidden = false;
}

function updateFullscreenNavigation() {
  const index = fullscreenSceneNavigation?.index;
  const scenes = fullscreenSceneNavigation?.scenes || [];
  const enabled = Number.isInteger(index) && scenes.length > 0;
  fullscreenImagePrevious.hidden = !enabled;
  fullscreenImageNext.hidden = !enabled;
  fullscreenImagePrevious.disabled = !enabled || index === 0;
  fullscreenImageNext.disabled = !enabled || index === scenes.length - 1;
}

async function navigateFullscreenScene(offset) {
  if (!fullscreenSceneNavigation) return;
  const nextIndex = fullscreenSceneNavigation.index + offset;
  const scene = fullscreenSceneNavigation.scenes[nextIndex];
  if (!scene) return;
  fullscreenImagePrevious.disabled = true;
  fullscreenImageNext.disabled = true;
  try {
    const payload = await fetchJson(
      `/api/stories/${encodeURIComponent(fullscreenSceneNavigation.storySlug)}/scenes/${encodeURIComponent(scene.slug)}`,
    );
    const document = payload.document || {};
    fullscreenSceneNavigation.index = nextIndex;
    const sceneName = document.scene?.title || scene.title || scene.slug;
    if (document.image_exists && document.image_path) {
      fullscreenImage.src = fileUrl(document.image_path, Date.now().toString());
      fullscreenImage.alt = `${sceneName} render`;
      fullscreenImage.hidden = false;
      fullscreenImageEmpty.hidden = true;
    } else {
      fullscreenImage.removeAttribute("src");
      fullscreenImage.alt = "";
      fullscreenImage.hidden = true;
      fullscreenImageEmpty.textContent = `No Image for ${sceneName}`;
      fullscreenImageEmpty.hidden = false;
    }
  } finally {
    updateFullscreenNavigation();
  }
}

function openFullscreenImage(src, alt = "", options = {}) {
  if (!src) {
    return;
  }
  resetFullscreenNavigation();
  fullscreenImage.src = src;
  fullscreenImage.alt = alt;
  const sceneIndex = options.scenes?.findIndex((scene) => scene.slug === options.sceneSlug) ?? -1;
  if (options.storySlug && sceneIndex >= 0) {
    fullscreenSceneNavigation = {
      index: sceneIndex,
      scenes: options.scenes,
      storySlug: options.storySlug,
    };
    updateFullscreenNavigation();
  }
  resetFullscreenCrop();
  fullscreenImageOverlay.showModal();
  fullscreenImageClose.focus();
}

function enableFullscreenImage(image, getOptions = null) {
  if (!image) return null;
  if (image.closest(".fullscreen-image-button")) return image.closest(".fullscreen-image-button");
  const button = document.createElement("button");
  button.type = "button";
  button.className = "fullscreen-image-button";
  button.setAttribute("aria-label", `Open full size: ${image.alt || image.title || "image"}`);
  if (image.parentNode) image.replaceWith(button);
  button.append(image);
  button.addEventListener("click", () => openFullscreenImage(
    image.src,
    image.alt || image.title || "Image",
    getOptions?.() || {},
  ));
  return button;
}

let fullscreenCropStart = null;
let fullscreenCropEnd = null;
let fullscreenCropPointerId = null;

function resetFullscreenCrop() {
  fullscreenCropStart = null;
  fullscreenCropEnd = null;
  fullscreenCropPointerId = null;
  fullscreenCropBox.hidden = true;
  fullscreenCropBox.removeAttribute("style");
}

function fullscreenImagePoint(event) {
  const rect = fullscreenImage.getBoundingClientRect();
  return {
    x: Math.min(Math.max(event.clientX, rect.left), rect.right),
    y: Math.min(Math.max(event.clientY, rect.top), rect.bottom),
  };
}

function updateFullscreenCropBox() {
  if (!fullscreenCropStart || !fullscreenCropEnd) {
    return;
  }
  const left = Math.min(fullscreenCropStart.x, fullscreenCropEnd.x);
  const top = Math.min(fullscreenCropStart.y, fullscreenCropEnd.y);
  const width = Math.abs(fullscreenCropEnd.x - fullscreenCropStart.x);
  const height = Math.abs(fullscreenCropEnd.y - fullscreenCropStart.y);
  fullscreenCropBox.hidden = width < 2 || height < 2;
  fullscreenCropBox.style.left = `${left}px`;
  fullscreenCropBox.style.top = `${top}px`;
  fullscreenCropBox.style.width = `${width}px`;
  fullscreenCropBox.style.height = `${height}px`;
}

function canvasBlob(canvas) {
  return new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
}

async function copyFullscreenCrop() {
  if (!fullscreenCropStart || !fullscreenCropEnd || !fullscreenImage.naturalWidth || !fullscreenImage.naturalHeight) {
    return;
  }
  const imageRect = fullscreenImage.getBoundingClientRect();
  const left = Math.min(fullscreenCropStart.x, fullscreenCropEnd.x);
  const top = Math.min(fullscreenCropStart.y, fullscreenCropEnd.y);
  const width = Math.abs(fullscreenCropEnd.x - fullscreenCropStart.x);
  const height = Math.abs(fullscreenCropEnd.y - fullscreenCropStart.y);
  if (width < 2 || height < 2) {
    resetFullscreenCrop();
    return;
  }
  const scaleX = fullscreenImage.naturalWidth / imageRect.width;
  const scaleY = fullscreenImage.naturalHeight / imageRect.height;
  const sourceX = Math.round((left - imageRect.left) * scaleX);
  const sourceY = Math.round((top - imageRect.top) * scaleY);
  const sourceWidth = Math.round(width * scaleX);
  const sourceHeight = Math.round(height * scaleY);
  const canvas = document.createElement("canvas");
  canvas.width = sourceWidth;
  canvas.height = sourceHeight;
  canvas.getContext("2d").drawImage(
    fullscreenImage,
    sourceX,
    sourceY,
    sourceWidth,
    sourceHeight,
    0,
    0,
    sourceWidth,
    sourceHeight,
  );
  const blob = await canvasBlob(canvas);
  await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
  showAuxResourceMessage("Image snip copied.", "success");
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
  state.auxiliaryResourceCategories = payload.auxiliary_resource_categories || [];
  const preferredCharacter = state.character || stored.character;
  state.character = preferredCharacter && state.characters.includes(preferredCharacter) ? preferredCharacter : payload.default_character;
  const phases = state.phasesByCharacter[state.character] || [];
  const preferredPhase = state.phase || stored.phase;
  state.phase = preferredPhase && phases.includes(preferredPhase) ? preferredPhase : payload.default_phase;
  setSelectOptions(characterSelect, state.characters);
  characterSelect.value = state.character || "";
  setSelectOptionsWithLabels(scenePickerCharacter, [{ value: "", label: "All Characters" }, ...state.characters.map((item) => ({ value: item, label: item }))]);
  setSelectOptionsWithLabels(builderImagePickerCharacter, [{ value: "", label: "All Characters" }, ...state.characters.map((item) => ({ value: item, label: item }))]);
  scenePickerCharacter.value = state.scenePickerCharacter || "";
  scenePickerSearch.value = state.scenePickerSearch || "";
  setSelectOptions(onboardingSpecies, state.onboardingOptions.species_ancestry || []);
  setSelectOptions(onboardingGender, state.onboardingOptions.gender_presentation || []);
  if (state.auxiliaryResourceCategories.length) {
    setSelectOptionsWithLabels(auxResourceCategory, state.auxiliaryResourceCategories.map((item) => ({ value: item.value, label: item.label })));
  }
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
    const page = button.dataset.page || "";
    button.disabled = !ready && !["auxiliary-resources", "phase-comparison", "stories", "scenes", "zine", "ai-controls", "local-image-config", "pipeline-controls"].includes(page);
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

function eligibleAssets() {
  return state.assets.filter((asset) => asset.asset_state !== "LOCKED" && asset.pipeline_stage !== "LOCKED");
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
  if (!visibleAssets.length) {
    renderEmptyRow(assetTableBody, 10, "No assets match the current character, phase, and filters.");
    return;
  }
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
      asset.updated_at,
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
      } else if (index === 9 && value) {
        const time = document.createElement("time");
        time.dateTime = String(value);
        time.title = String(value);
        time.textContent = formatLocalTimestamp(value);
        cell.append(time);
      } else {
        cell.textContent = value ?? "";
      }
      row.append(cell);
    }
    makeSelectableRow(row, `Asset ${asset.asset_id}`, asset.asset_id === state.selectedAssetId, () => selectAsset(asset.asset_id));
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
  updateSelectableRows(assetTableBody, (row) => Number(row.dataset.assetId) === state.selectedAssetId);
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
  assetLockedImage.append(enableFullscreenImage(image));
}

function updateActionButtons(detail) {
  const asset = detail?.asset || null;
  const candidateExists = Boolean(detail?.exists?.candidate_image);
  const lockedExists = Boolean(detail?.exists?.locked_image);
  const hasEligibleAssets = eligibleAssets().length > 0;
  for (const button of actionButtons) {
    const action = button.dataset.action;
    let enabled = Boolean(asset);
    if (action === "advance-all") {
      enabled = hasEligibleAssets;
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
  if (action === "advance-all") {
    await advanceAllAssets();
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

async function advanceAllAssets() {
  const eligible = eligibleAssets();
  if (!eligible.length) {
    showActionMessage("No eligible assets to advance.");
    updateActionButtons(state.assetDetail);
    return;
  }
  showActionMessage(`Advancing ${eligible.length} eligible asset(s)...`);
  for (const button of actionButtons) {
    button.disabled = true;
  }
  try {
    const payload = await fetchJson(
      `/api/assets/advance-all?${currentQuery().toString()}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset_ids: eligible.map((asset) => asset.asset_id) }),
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

function activePageName() {
  const activePage = document.querySelector("main > .page.active");
  return activePage?.id?.replace(/-page$/, "") || "";
}

function controlValues(container) {
  return Array.from(container.querySelectorAll("input, select, textarea")).map((control) => ({
    name: control.id || control.dataset.storySettingPath || control.name || "",
    value: control.type === "checkbox" ? control.checked : control.value,
  }));
}

function storySnapshot() {
  return JSON.stringify({
    slug: state.selectedStorySlug,
    text: storyText.value,
    settings: controlValues(storySettingsFields),
  });
}

function sceneSnapshot() {
  return JSON.stringify({ story: state.selectedStorySlug, scene: state.selectedSceneSlug, text: sceneText.value });
}

function sceneBuilderSnapshot() {
  if (state.sceneBuilder && activePageName() === "scene-builder") {
    builderSyncControls();
  }
  return JSON.stringify(state.sceneBuilder || null);
}

function sourceEditorSnapshot() {
  return JSON.stringify({ path: state.sourceEditor?.path || "", text: sourceEditorText.value });
}

function zineSnapshot() {
  return JSON.stringify({ slug: state.selectedZineSlug, payload: zinePayload() });
}

function settingsSnapshot() {
  return JSON.stringify(automationPayloadFromForm());
}

function setSaveState(container, text, kind = "") {
  if (!container) return;
  container.textContent = text;
  container.className = `save-state ${kind}`.trim();
}

function updateDirtyIndicators() {
  const storyDirty = storySnapshot() !== state.savedBaselines.story;
  if (!(storyDirty && storySaveState.classList.contains("error"))) {
    setSaveState(
      storySaveState,
      state.storyDetail ? (storyDirty ? "Dirty" : "Saved") : "",
      storyDirty ? "dirty" : "saved",
    );
  }
  const sceneDirty = sceneSnapshot() !== state.savedBaselines.scene;
  if (!(sceneDirty && sceneSaveState.classList.contains("error"))) {
    setSaveState(
      sceneSaveState,
      state.sceneDetail ? (sceneDirty ? "Dirty" : "Saved") : "",
      sceneDirty ? "dirty" : "saved",
    );
  }
  const sourceDirty = sourceEditorSnapshot() !== state.savedBaselines.sourceEditor;
  if (!(sourceDirty && sourceEditorSaveState.classList.contains("error"))) {
    setSaveState(
      sourceEditorSaveState,
      state.sourceEditor ? (sourceDirty ? "Dirty" : "Saved") : "",
      sourceDirty ? "dirty" : "saved",
    );
  }
  const settingsDirty = Boolean(state.savedBaselines.settings) && settingsSnapshot() !== state.savedBaselines.settings;
  if (!(settingsDirty && settingsSaveState.classList.contains("error"))) {
    setSaveState(settingsSaveState, state.savedBaselines.settings ? (settingsDirty ? "Dirty" : "Saved") : "", settingsDirty ? "dirty" : "saved");
  }
}

function editorGuardForPage(page = activePageName()) {
  if (page === "stories" && state.storyDetail && storySnapshot() !== state.savedBaselines.story) {
    return { name: "story", autosave: true, save: saveStoryBeforeNavigation };
  }
  if (page === "scenes" && state.sceneDetail && sceneSnapshot() !== state.savedBaselines.scene) {
    return { name: "scene", autosave: true, save: saveSceneBeforeNavigation };
  }
  if (page === "scene-builder" && state.sceneBuilder && sceneBuilderSnapshot() !== state.savedBaselines.sceneBuilder) {
    return { name: "Scene Builder", autosave: true, save: async () => Boolean(await saveSceneBuilder(true)) };
  }
  if (page === "template-editor" && state.sourceEditor && sourceEditorSnapshot() !== state.savedBaselines.sourceEditor) {
    return {
      name: "Source Editor",
      autosave: false,
      save: saveSourceEditor,
      discard: () => { state.savedBaselines.sourceEditor = sourceEditorSnapshot(); },
    };
  }
  if (page === "zine" && state.savedBaselines.zine && zineSnapshot() !== state.savedBaselines.zine) {
    return {
      name: "Zine",
      autosave: false,
      save: saveZine,
      discard: () => { state.savedBaselines.zine = zineSnapshot(); },
    };
  }
  if (["ai-controls", "local-image-config"].includes(page) && state.savedBaselines.settings && settingsSnapshot() !== state.savedBaselines.settings) {
    return {
      name: "project settings",
      autosave: false,
      save: saveAutomationSettings,
      discard: () => { state.savedBaselines.settings = settingsSnapshot(); },
    };
  }
  return null;
}

function dialogResult(dialog) {
  return new Promise((resolve) => {
    dialog.addEventListener("close", () => resolve(dialog.returnValue || "cancel"), { once: true });
    dialog.showModal();
  });
}

async function confirmAction(title, message, confirmLabel = "Confirm") {
  confirmationTitle.textContent = title;
  confirmationMessage.textContent = message;
  confirmationConfirm.textContent = confirmLabel;
  confirmationDialog.returnValue = "cancel";
  return (await dialogResult(confirmationDialog)) === "confirm";
}

async function guardCurrentEditor() {
  const guard = editorGuardForPage();
  if (!guard) return true;
  if (guard.autosave) {
    const saved = await guard.save();
    updateDirtyIndicators();
    return Boolean(saved);
  }
  unsavedChangesMessage.textContent = `Save changes to ${guard.name} before continuing?`;
  unsavedChangesDialog.returnValue = "cancel";
  const choice = await dialogResult(unsavedChangesDialog);
  if (choice === "cancel") return false;
  if (choice === "discard") {
    guard.discard?.();
    updateDirtyIndicators();
    return true;
  }
  const saved = await guard.save();
  updateDirtyIndicators();
  return Boolean(saved);
}

async function runGuardedTransition(action) {
  const previous = state.transitionPromise;
  const execute = async () => {
    if (!(await guardCurrentEditor())) return false;
    await action();
    return true;
  };
  const current = previous
    ? previous.catch(() => false).then(execute)
    : execute();
  state.transitionPromise = current;
  try {
    return await current;
  } finally {
    if (state.transitionPromise === current) {
      state.transitionPromise = null;
    }
  }
}

async function saveStoryBeforeNavigation() {
  if (!state.selectedStorySlug || !state.storyDetail) {
    return true;
  }
  setSaveState(storySaveState, "Saving", "saving");
  try {
    await saveStorySettingsData(state.selectedStorySlug);
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}`, {
      method: "PUT",
      headers: { "Content-Type": "text/markdown; charset=utf-8" },
      body: storyText.value || "",
    });
    state.stories = payload.stories || state.stories;
    updateStoryGitWarning(payload.has_story_changes);
    state.storyDetail = payload.document || null;
    state.selectedStorySlug = state.storyDetail?.story?.slug || state.selectedStorySlug;
    renderStoryTable();
    renderSceneStoryOptions();
    renderValidationBox(storyValidation, state.storyDetail?.validation_errors || [], "Story markdown is valid.");
    showStoryMessage(payload.message || "Story saved.");
    state.savedBaselines.story = storySnapshot();
    setSaveState(storySaveState, "Saved", "saved");
    return true;
  } catch (error) {
    showStoryMessage(error.message, "error");
    setSaveState(storySaveState, "Error", "error");
    return false;
  }
}

async function saveSceneBeforeNavigation() {
  if (!state.selectedStorySlug || !state.selectedSceneSlug || !state.sceneDetail) {
    return true;
  }
  setSaveState(sceneSaveState, "Saving", "saving");
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}`, {
      method: "PUT",
      headers: { "Content-Type": "text/markdown; charset=utf-8" },
      body: sceneText.value || "",
    });
    state.scenes = payload.scenes || state.scenes;
    updateStoryGitWarning(payload.has_story_changes);
    state.sceneDetail = payload.document || null;
    state.selectedSceneSlug = state.sceneDetail?.scene?.slug || state.selectedSceneSlug;
    renderSceneTable();
    renderValidationBox(sceneValidation, state.sceneDetail?.validation_errors || [], "Scene markdown is valid.");
    updateSceneImageToggle();
    showSceneMessage(payload.message || "Scene saved.");
    state.savedBaselines.scene = sceneSnapshot();
    setSaveState(sceneSaveState, "Saved", "saved");
    return true;
  } catch (error) {
    showSceneMessage(error.message, "error");
    setSaveState(sceneSaveState, "Error", "error");
    return false;
  }
}

async function saveBeforePageNavigation(nextPage) {
  const currentPage = activePageName();
  if (currentPage === nextPage) {
    return true;
  }
  return guardCurrentEditor();
}

async function activatePage(page, options = {}) {
  if (!["onboarding", "auxiliary-resources", "phase-comparison", "stories", "scenes", "scene-builder", "prompt-review", "ai-controls", "local-image-config", "pipeline-controls"].includes(page) && !selectedPhaseReady()) {
    page = "onboarding";
  }
  if (!options.skipAutosave && !(await saveBeforePageNavigation(page))) {
    characterAssetsMenu.value = ["assets", "manifest", "costumes", "expressions", "turnarounds", "identity-keys", "phase-comparison"].includes(activePageName())
      ? activePageName()
      : "";
    return false;
  }
  for (const button of document.querySelectorAll(".tab")) {
    button.classList.toggle("active", button.dataset.page === page);
  }
  const characterAssetPages = ["assets", "manifest", "costumes", "expressions", "turnarounds", "identity-keys", "phase-comparison"];
  characterAssetsMenu.classList.toggle("active", characterAssetPages.includes(page));
  characterAssetsMenu.value = characterAssetPages.includes(page) ? page : "";
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
  document.querySelector("#stories-page").classList.toggle("active", page === "stories");
  document.querySelector("#scenes-page").classList.toggle("active", page === "scenes");
  document.querySelector("#zine-page").classList.toggle("active", page === "zine");
  document.querySelector("#scene-builder-page").classList.toggle("active", page === "scene-builder");
  document.querySelector("#ai-controls-page").classList.toggle("active", page === "ai-controls");
  document.querySelector("#local-image-config-page").classList.toggle("active", page === "local-image-config");
  document.querySelector("#pipeline-controls-page").classList.toggle("active", page === "pipeline-controls");
  document.querySelector("#render-console-page").classList.toggle("active", page === "render-console");
  document.querySelector("#local-image-review-page").classList.toggle("active", page === "local-image-review");
  document.querySelector("#template-editor-page").classList.toggle("active", page === "template-editor");
  document
    .querySelector("#placeholder-page")
    .classList.toggle(
      "active",
      !["onboarding", "assets", "manifest", "prompt-review", "render-review", "turnarounds", "identity-keys", "auxiliary-resources", "phase-comparison", "costumes", "expressions", "stories", "scenes", "zine", "scene-builder", "render-console", "local-image-review", "ai-controls", "local-image-config", "pipeline-controls", "template-editor"].includes(page),
    );
  const activeButton = Array.from(document.querySelectorAll(".tab")).find((button) => button.dataset.page === page);
  placeholderTitle.textContent = activeButton?.textContent || "Page";
  if (page === "prompt-review") {
    await loadPromptReviewTasks();
  }
  if (page === "manifest") {
    await loadManifestTasks();
  }
  if (page === "render-review") {
    await loadRenderReviewTasks();
  }
  if (page === "turnarounds") {
    await loadTurnarounds();
  }
  if (page === "identity-keys") {
    await loadIdentityKeys();
  }
  if (page === "auxiliary-resources") {
    await loadAuxiliaryResources();
  }
  if (page === "phase-comparison") {
    initializePhaseComparisonControls();
    await loadPhaseComparison();
  }
  if (page === "costumes") {
    await loadCostumes();
  }
  if (page === "expressions") {
    await loadExpressions();
  }
  if (page === "stories") {
    await loadStories();
  }
  if (page === "scenes") {
    await loadScenesPage();
  }
  if (page === "zine") {
    await loadZines();
  }
  if (page === "scene-builder") {
    await openSceneBuilder();
  }
  if (page === "ai-controls") {
    await loadAiControls();
    await loadPipelineControls();
    await refreshOllamaModelOptions();
  }
  if (page === "pipeline-controls") {
    await loadPipelineControls();
  }
  if (page === "local-image-config") {
    await loadPipelineControls();
  }
  if (page === "render-console") {
    await loadRenderConsoleTasks();
  }
  if (page === "local-image-review") {
    await loadLocalImageReviewTasks();
  }
  if (page === "onboarding") {
    renderOnboarding();
  }
  return true;
}

function setupTabs() {
  characterAssetsMenu.addEventListener("change", async () => {
    const page = characterAssetsMenu.value;
    if (page === "identity-keys") {
      state.identityKeyMode = "list";
    }
    await runGuardedTransition(() => activatePage(page, { skipAutosave: true }));
  });
  for (const button of document.querySelectorAll("button.tab")) {
    button.addEventListener("click", async () => {
      if (button.dataset.page === "identity-keys") {
        state.identityKeyMode = "list";
      }
      closeToolbarSettingsMenu();
      await runGuardedTransition(() => activatePage(button.dataset.page, { skipAutosave: true }));
    });
  }
}

function toggleToolbarSettingsMenu() {
  const isHidden = toolbarSettingsMenu.hidden;
  toolbarSettingsMenu.hidden = !isHidden;
  toolbarSettingsButton.setAttribute("aria-expanded", isHidden ? "true" : "false");
  if (isHidden) {
    const rect = toolbarSettingsButton.getBoundingClientRect();
    toolbarSettingsMenu.style.right = `${Math.max(8, window.innerWidth - rect.right)}px`;
    toolbarSettingsMenu.style.top = `${rect.bottom + 6}px`;
    toolbarSettingsMenu.querySelector("button")?.focus();
  }
}

function closeToolbarSettingsMenu(returnFocus = false) {
  const wasOpen = !toolbarSettingsMenu.hidden;
  toolbarSettingsMenu.hidden = true;
  toolbarSettingsButton.setAttribute("aria-expanded", "false");
  if (returnFocus && wasOpen) toolbarSettingsButton.focus();
}

async function openTodoDialog() {
  closeToolbarSettingsMenu();
  const payload = await fetchJson("/api/todo");
  todoText.value = payload.text || "";
  todoDialog.dataset.savedText = todoText.value;
  todoDialog.showModal();
}

async function persistTodo() {
  if (todoText.value === (todoDialog.dataset.savedText || "")) return;
  await fetchJson("/api/todo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: todoText.value }),
  });
  todoDialog.dataset.savedText = todoText.value;
}

async function saveTodo(event) {
  event.preventDefault();
  await persistTodo();
  todoDialog.close();
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
  if (!state.identityKeys.length) {
    renderEmptyRow(identityKeyTableBody, 4, "No Identity Keys exist for this character and phase.");
    return;
  }
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
    updateButton.className = "update-action";
    updateButton.textContent = "Update";
    updateButton.addEventListener("click", (event) => {
      event.stopPropagation();
      selectIdentityKey(item.identity_key_id);
    });
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "danger-action";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteIdentityKey(item.identity_key_id);
    });
    actionCell.append(updateButton, deleteButton);
    row.append(labelCell, viewCell, imageCell, actionCell);
    makeSelectableRow(row, item.label || item.identity_key_id, item.identity_key_id === state.selectedIdentityKeyId, () => selectIdentityKey(item.identity_key_id));
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
    false,
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
  if (!state.costumes.length) {
    renderEmptyRow(costumeTableBody, 4, "No costumes exist for this character and phase.");
    return;
  }
  for (const costume of state.costumes) {
    const row = document.createElement("tr");
    row.dataset.costumeSlug = costume.slug;
    row.classList.toggle("selected", costume.slug === state.selectedCostumeSlug);
    const nameCell = document.createElement("td");
    nameCell.textContent = costume.name || "";
    const countCell = document.createElement("td");
    countCell.textContent = costume.asset_count ?? 0;
    const pathCell = document.createElement("td");
    pathCell.textContent = basename(costume.path || "");
    pathCell.title = costume.path || "";
    const actionCell = document.createElement("td");
    const openButton = document.createElement("button");
    openButton.type = "button";
    openButton.className = "navigation-action";
    openButton.textContent = "Open";
    openButton.addEventListener("click", (event) => {
      event.stopPropagation();
      if (costume.source?.source_path) {
        openSourceEditorForSource(costume.source, showCostumeMessage);
      } else {
        showCostumeMessage("No costume template source is available for this row.", "error");
      }
    });
    actionCell.append(openButton);
    row.append(nameCell, countCell, pathCell, actionCell);
    makeSelectableRow(row, costume.name || costume.slug, costume.slug === state.selectedCostumeSlug, () => selectCostume(costume.slug));
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
  // Prefer the backend-resolved governing source; legacy assets may still store _Lib-relative paths.
  if (asset.governing_template_source?.source_path) {
    return { source: asset.governing_template_source };
  }
  return state.expressionDefinitions.find((item) => item.path === asset.expression_definition_path) || null;
}

function renderExpressionTable() {
  expressionTableBody.replaceChildren();
  if (!state.expressionAssets.length) {
    renderEmptyRow(expressionTableBody, 7, "No expression assets exist for this character and phase.");
    return;
  }
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
    editButton.className = "navigation-action";
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
    makeSelectableRow(row, asset.expression || `Asset ${asset.asset_id}`, asset.asset_id === state.selectedExpressionAssetId, () => selectExpression(asset.asset_id));
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

async function loadStories(selectSlug = state.selectedStorySlug) {
  // Load shared story documents for the Stories and Scenes pages.
  storyStatus.textContent = "Loading stories...";
  try {
    const payload = await fetchJson("/api/stories");
    state.stories = payload.stories || [];
    updateStoryGitWarning(payload.has_story_changes);
    if (selectSlug && state.stories.some((item) => item.slug === selectSlug)) {
      state.selectedStorySlug = selectSlug;
    } else if (!state.selectedStorySlug || !state.stories.some((item) => item.slug === state.selectedStorySlug)) {
      state.selectedStorySlug = state.stories[0]?.slug || null;
    }
    renderStoryTable();
    renderSceneStoryOptions();
    storyStatus.textContent = `${state.stories.length} stor${state.stories.length === 1 ? "y" : "ies"}`;
    if (document.querySelector("#stories-page").classList.contains("active") && state.selectedStorySlug) {
      await loadStoryDetail(state.selectedStorySlug);
    } else if (!state.selectedStorySlug) {
      clearStoryEditor();
    }
  } catch (error) {
    storyStatus.textContent = "Load failed.";
    showStoryMessage(error.message, "error");
  }
}

function renderStoryTable() {
  // Render the shared stories list.
  storyTableBody.replaceChildren();
  if (!state.stories.length) {
    renderEmptyRow(storyTableBody, 3, "No stories exist. Add a story to begin.");
    return;
  }
  for (const story of state.stories) {
    const row = document.createElement("tr");
    for (const value of [story.title, story.slug, basename(story.story_file_path || "")]) {
      const cell = document.createElement("td");
      cell.textContent = value || "";
      row.append(cell);
    }
    makeSelectableRow(row, story.title || story.slug, story.slug === state.selectedStorySlug, () => selectStory(story.slug));
    storyTableBody.append(row);
  }
}

function renderValidationBox(container, errors, emptyMessage) {
  // Show validation warnings for story and scene markdown editors.
  const items = Array.isArray(errors) ? errors.filter(Boolean) : [];
  if (!items.length) {
    showMessageElement(container, emptyMessage, "info");
    return;
  }
  container.hidden = false;
  container.className = "action-message warning";
  container.setAttribute("role", "status");
  container.setAttribute("aria-live", "polite");
  container.setAttribute("aria-atomic", "true");
  container.innerHTML = items.map((item) => `<div>${escapeHtml(item)}</div>`).join("");
}

function clearStoryEditor() {
  // Reset the story editor when nothing is selected.
  state.storyDetail = null;
  state.storySettings = null;
  storyEditorTitle.textContent = "Select a story";
  storyText.value = "";
  storySettingsJson.value = "";
  storySettingsJson.hidden = true;
  storyText.hidden = false;
  storySettingsFields.replaceChildren();
  storySave.disabled = true;
  storyDelete.disabled = true;
  storySettingsLoad.disabled = true;
  storySettingsSave.disabled = true;
  state.savedBaselines.story = "";
  setSaveState(storySaveState, "");
  renderValidationBox(storyValidation, [], "Create or select a story to edit its markdown.");
}

function storySettingPathLabel(path) {
  return path.map((part) => String(part)).join(".");
}

function storySettingInputValue(value) {
  if (value === undefined) return "";
  if (value === null) return "null";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function isStorySettingCsvList(path, value) {
  if (!Array.isArray(value) || !value.every((item) => typeof item === "string")) {
    return false;
  }
  const textPath = storySettingPathLabel(path);
  return textPath === "compiler_profiles.local_render.negative_text_terms"
    || /^dialog(?:ue)?_styles\.\d+\.(?:avoid|layout_rules)$/.test(textPath);
}

function renderStorySettingField(path, value) {
  const label = document.createElement("label");
  const caption = document.createElement("span");
  caption.textContent = storySettingPathLabel(path);
  label.append(caption);
  const longText = typeof value === "string" && (value.length > 100 || value.includes("\n"));
  const csvList = isStorySettingCsvList(path, value);
  const control = document.createElement(longText ? "textarea" : "input");
  control.value = csvList ? value.join(", ") : storySettingInputValue(value);
  control.dataset.storySettingPath = JSON.stringify(path);
  control.dataset.storySettingType = csvList ? "csv" : value === null || Array.isArray(value) || (value && typeof value === "object") ? "json" : typeof value;
  label.append(control);
  return label;
}

function appendStorySettingFields(container, value, path = []) {
  if (Array.isArray(value)) {
    if (isStorySettingCsvList(path, value)) {
      container.append(renderStorySettingField(path, value));
      return;
    }
    if (!value.length) {
      container.append(renderStorySettingField(path, value));
      return;
    }
    value.forEach((item, index) => appendStorySettingFields(container, item, [...path, index]));
    return;
  }
  if (value && typeof value === "object") {
    const keys = Object.keys(value);
    if (!keys.length) {
      container.append(renderStorySettingField(path, value));
      return;
    }
    keys.forEach((key) => appendStorySettingFields(container, value[key], [...path, key]));
    return;
  }
  container.append(renderStorySettingField(path, value));
}

function renderStorySettingsFields() {
  storySettingsFields.replaceChildren();
  if (!state.storySettings) {
    return;
  }
  appendStorySettingFields(storySettingsFields, state.storySettings);
}

function storySettingControlValue(control) {
  const value = control.value;
  if (control.dataset.storySettingType === "boolean") {
    return value.toLowerCase() === "true";
  }
  if (control.dataset.storySettingType === "number") {
    const numberValue = Number(value);
    return Number.isFinite(numberValue) ? numberValue : value;
  }
  if (control.dataset.storySettingType === "json") {
    return JSON.parse(value || "null");
  }
  if (control.dataset.storySettingType === "csv") {
    return value.split(",").map((item) => item.trim()).filter(Boolean);
  }
  return value;
}

function syncStorySettingsFields() {
  if (!state.storySettings) {
    return;
  }
  for (const control of storySettingsFields.querySelectorAll("[data-story-setting-path]")) {
    setPathValue(state.storySettings, JSON.parse(control.dataset.storySettingPath).join("."), storySettingControlValue(control));
  }
  storySettingsJson.value = JSON.stringify(state.storySettings, null, 2);
}

async function loadStorySettingsData(storySlug) {
  const payload = await fetchJson(`/api/stories/${encodeURIComponent(storySlug)}/settings`);
  state.storySettings = payload.data || {};
  storySettingsJson.value = JSON.stringify(state.storySettings, null, 2);
  renderStorySettingsFields();
  storySettingsSave.disabled = false;
}

async function saveStorySettingsData(storySlug) {
  syncStorySettingsFields();
  if (!state.storySettings) {
    return null;
  }
  const payload = await fetchJson(`/api/stories/${encodeURIComponent(storySlug)}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state.storySettings),
  });
  state.storySettings = payload.data || state.storySettings;
  storySettingsJson.value = JSON.stringify(state.storySettings, null, 2);
  renderStorySettingsFields();
  return payload;
}

async function loadStoryDetail(storySlug) {
  // Load one story markdown document into the editor.
  if (!storySlug) {
    clearStoryEditor();
    return;
  }
  storyEditorTitle.textContent = "Loading story...";
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(storySlug)}`);
    state.storyDetail = payload.document || null;
    state.selectedStorySlug = state.storyDetail?.story?.slug || storySlug;
    renderStoryTable();
    storyEditorTitle.textContent = state.storyDetail?.story?.title || "Story";
    storyText.value = state.storyDetail?.text || "";
    storySettingsJson.hidden = true;
    storyText.hidden = false;
    storySave.disabled = !state.storyDetail;
    storyDelete.disabled = !state.storyDetail;
    storySettingsLoad.disabled = !state.storyDetail;
    storySettingsSave.disabled = true;
    if (state.storyDetail) {
      await loadStorySettingsData(state.selectedStorySlug);
    }
    renderValidationBox(storyValidation, state.storyDetail?.validation_errors || [], "Story markdown is valid.");
    state.savedBaselines.story = storySnapshot();
    setSaveState(storySaveState, "Saved", "saved");
  } catch (error) {
    clearStoryEditor();
    showStoryMessage(error.message, "error");
  }
}

async function selectStory(storySlug) {
  // Select one story and refresh the current page context.
  if (storySlug === state.selectedStorySlug) return;
  await runGuardedTransition(async () => {
    state.selectedStorySlug = storySlug;
    renderStoryTable();
    renderSceneStoryOptions();
    if (document.querySelector("#stories-page").classList.contains("active")) {
      await loadStoryDetail(storySlug);
    }
    if (document.querySelector("#scenes-page").classList.contains("active")) {
      await loadScenesPage();
    }
  });
}

async function createStory() {
  // Create a new story from the shared template.
  const title = storyNewTitle.value.trim();
  if (!title) {
    showStoryMessage("Story title is required.", "error");
    return;
  }
  storyCreate.disabled = true;
  showStoryMessage("Creating story...");
  try {
    const payload = await fetchJson(`/api/stories?${new URLSearchParams({ title }).toString()}`, { method: "POST" });
    state.stories = payload.stories || state.stories;
    updateStoryGitWarning(payload.has_story_changes);
    state.storyDetail = payload.document || null;
    state.selectedStorySlug = state.storyDetail?.story?.slug || state.selectedStorySlug;
    storyNewTitle.value = "";
    renderStoryTable();
    renderSceneStoryOptions();
    if (state.storyDetail) {
      storyEditorTitle.textContent = state.storyDetail.story.title || "Story";
      storyText.value = state.storyDetail.text || "";
      storySave.disabled = false;
      storyDelete.disabled = false;
      storySettingsLoad.disabled = false;
      storySettingsSave.disabled = true;
      await loadStorySettingsData(state.selectedStorySlug);
      renderValidationBox(storyValidation, state.storyDetail.validation_errors || [], "Story markdown is valid.");
      state.savedBaselines.story = storySnapshot();
      setSaveState(storySaveState, "Saved", "saved");
    }
    showStoryMessage(payload.message || "Story created.");
  } catch (error) {
    showStoryMessage(error.message, "error");
  } finally {
    storyCreate.disabled = false;
  }
}

async function saveStory() {
  // Save the current story markdown document.
  if (!state.selectedStorySlug) {
    showStoryMessage("Select a story first.", "error");
    return;
  }
  storySave.disabled = true;
  showStoryMessage("Saving story...");
  try {
    const settingsPayload = await saveStorySettingsData(state.selectedStorySlug);
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}`, {
      method: "PUT",
      headers: { "Content-Type": "text/markdown; charset=utf-8" },
      body: storyText.value || "",
    });
    state.stories = payload.stories || state.stories;
    updateStoryGitWarning(payload.has_story_changes);
    state.storyDetail = payload.document || null;
    state.selectedStorySlug = state.storyDetail?.story?.slug || state.selectedStorySlug;
    renderStoryTable();
    renderSceneStoryOptions();
    renderZineStoryOptions();
    renderValidationBox(storyValidation, state.storyDetail?.validation_errors || [], "Story markdown is valid.");
    showStoryMessage(settingsPayload ? "Story and settings saved." : (payload.message || "Story saved."));
    state.savedBaselines.story = storySnapshot();
    setSaveState(storySaveState, "Saved", "saved");
    return true;
  } catch (error) {
    showStoryMessage(error.message, "error");
    setSaveState(storySaveState, "Error", "error");
    return false;
  } finally {
    storySave.disabled = false;
  }
}

async function loadStorySettings() {
  if (!state.selectedStorySlug) {
    showStoryMessage("Select a story first.", "error");
    return;
  }
  try {
    await loadStorySettingsData(state.selectedStorySlug);
    showStoryMessage("Story settings loaded.");
  } catch (error) {
    showStoryMessage(error.message, "error");
  }
}

async function saveStorySettings() {
  if (!state.selectedStorySlug) {
    showStoryMessage("Select a story first.", "error");
    return;
  }
  try {
    const payload = await saveStorySettingsData(state.selectedStorySlug);
    updateStoryGitWarning(payload?.has_story_changes);
    showStoryMessage(payload?.message || "Story settings saved.", "success");
    state.savedBaselines.story = storySnapshot();
    setSaveState(storySaveState, "Saved", "saved");
    return true;
  } catch (error) {
    showStoryMessage(error.message, "error");
    setSaveState(storySaveState, "Error", "error");
    return false;
  }
}

async function deleteStory() {
  // Confirm, commit current story files, then delete the selected story folder.
  if (!state.selectedStorySlug || !confirm(`Delete story ${state.selectedStorySlug} and all of its scenes?`)) {
    return;
  }
  storyDelete.disabled = true;
  storySave.disabled = true;
  showStoryMessage("Deleting story...");
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}`, { method: "DELETE" });
    state.stories = payload.stories || [];
    state.storyDetail = null;
    state.selectedStorySlug = state.stories[0]?.slug || null;
    state.selectedSceneSlug = null;
    state.scenes = [];
    updateStoryGitWarning(payload.has_story_changes);
    renderStoryTable();
    renderSceneStoryOptions();
    clearStoryEditor();
    if (storyGitOutput && payload.git) {
      applyStoryGitPayload(payload.git);
    }
    showStoryMessage(payload.message || "Story deleted.");
  } catch (error) {
    showStoryMessage(error.message, "error");
  } finally {
    storySave.disabled = !state.storyDetail;
    storyDelete.disabled = !state.storyDetail;
  }
}

async function runStoryGitAction(action) {
  // Run one story git action and report command output in the Stories page.
  const buttons = [storyGitStatus, storyGitPull, storyGitCommit];
  buttons.forEach((button) => {
    button.disabled = true;
  });
  storyGitOutput.textContent = `Running git ${action}...`;
  try {
    const payload = await fetchJson(`/api/stories/git/${action}`, { method: "POST" });
    applyStoryGitPayload(payload);
  } catch (error) {
    storyGitOutput.textContent = error.message;
    showStoryMessage(error.message, "error");
  } finally {
    buttons.forEach((button) => {
      button.disabled = false;
    });
  }
}

function renderSceneStoryOptions() {
  // Keep the scene page story selector aligned with the loaded story list.
  const values = state.stories.map((story) => story.slug);
  sceneStorySelect.replaceChildren(...values.map((value) => option(value, state.stories.find((story) => story.slug === value)?.title || value)));
  if (state.selectedStorySlug && values.includes(state.selectedStorySlug)) {
    sceneStorySelect.value = state.selectedStorySlug;
  } else if (values.length) {
    state.selectedStorySlug = values[0];
    sceneStorySelect.value = values[0];
  } else {
    state.selectedStorySlug = null;
  }
}

function clearSceneEditor() {
  // Reset the scene editor when no story or scene is selected.
  state.sceneDetail = null;
  state.selectedSceneSlug = null;
  state.scenes = [];
  sceneTableBody.replaceChildren();
  sceneEditorTitle.textContent = "Select a scene";
  sceneText.value = "";
  sceneSave.disabled = true;
  sceneStageRender.disabled = true;
  sceneBuilderOpen.disabled = true;
  sceneDelete.disabled = true;
  sceneToggleImage.disabled = true;
  state.savedBaselines.scene = "";
  setSaveState(sceneSaveState, "");
  sceneImagePanel.hidden = true;
  sceneImagePreview.removeAttribute("src");
  closeSceneBuilder();
  renderValidationBox(sceneValidation, [], "Select a story, then create or open a scene.");
}

function updateSceneImageToggle() {
  const imagePath = state.sceneDetail?.image_path || "";
  const hasImage = Boolean(state.sceneDetail?.image_exists && imagePath);
  sceneToggleImage.disabled = !hasImage;
  if (!hasImage) {
    sceneImagePanel.hidden = true;
    sceneImagePreview.removeAttribute("src");
  } else if (!sceneImagePanel.hidden) {
    sceneImagePreview.src = fileUrl(imagePath, Date.now().toString());
  }
}

async function loadScenesPage() {
  // Load the selected story, scene list, and image picker for the Scenes page.
  if (!state.stories.length) {
    await loadStories();
  }
  renderSceneStoryOptions();
  if (!state.selectedStorySlug) {
    clearSceneEditor();
    await loadSceneImageReferences();
    sceneStatus.textContent = "No story selected.";
    return;
  }
  sceneStatus.textContent = "Loading scenes...";
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes`);
    state.scenes = payload.scenes || [];
    if (state.selectedSceneSlug && !state.scenes.some((item) => item.slug === state.selectedSceneSlug)) {
      state.selectedSceneSlug = null;
    }
    if (!state.selectedSceneSlug && state.scenes.length) {
      state.selectedSceneSlug = state.scenes[0].slug;
    }
    renderSceneTable();
    sceneStatus.textContent = `${state.scenes.length} scene(s)`;
    if (state.selectedSceneSlug) {
      await loadSceneDetail(state.selectedStorySlug, state.selectedSceneSlug);
    } else {
      clearSceneEditor();
      renderSceneTable();
    }
    await loadSceneImageReferences();
  } catch (error) {
    clearSceneEditor();
    sceneStatus.textContent = "Load failed.";
    showSceneMessage(error.message, "error");
  }
}

function renderSceneTable() {
  // Render the scene list for the selected story.
  sceneTableBody.replaceChildren();
  if (!state.scenes.length) {
    renderEmptyRow(sceneTableBody, 2, state.selectedStorySlug ? "No scenes exist in this story." : "Select a story to view scenes.");
    return;
  }
  for (const scene of state.scenes) {
    const row = document.createElement("tr");
    for (const value of [scene.title, basename(scene.path || "")]) {
      const cell = document.createElement("td");
      cell.textContent = value || "";
      row.append(cell);
    }
    makeSelectableRow(row, scene.title || scene.slug, scene.slug === state.selectedSceneSlug, () => selectScene(scene.slug));
    sceneTableBody.append(row);
  }
}

async function loadSceneDetail(storySlug, sceneSlug) {
  // Load one scene markdown document into the scene editor.
  if (!storySlug || !sceneSlug) {
    clearSceneEditor();
    return;
  }
  sceneEditorTitle.textContent = "Loading scene...";
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(storySlug)}/scenes/${encodeURIComponent(sceneSlug)}`);
    state.sceneDetail = payload.document || null;
    state.selectedSceneSlug = state.sceneDetail?.scene?.slug || sceneSlug;
    renderSceneTable();
    sceneEditorTitle.textContent = state.sceneDetail?.scene?.title || "Scene";
    sceneText.value = state.sceneDetail?.text || "";
    sceneSave.disabled = !state.sceneDetail;
    sceneStageRender.disabled = !state.sceneDetail;
    sceneBuilderOpen.disabled = !state.sceneDetail;
    sceneDelete.disabled = !state.sceneDetail;
    closeSceneBuilder();
    updateSceneImageToggle();
    renderValidationBox(sceneValidation, state.sceneDetail?.validation_errors || [], "Scene markdown is valid.");
    state.savedBaselines.scene = sceneSnapshot();
    setSaveState(sceneSaveState, "Saved", "saved");
  } catch (error) {
    clearSceneEditor();
    showSceneMessage(error.message, "error");
  }
}

async function selectScene(sceneSlug) {
  // Select one scene within the currently selected story.
  if (sceneSlug === state.selectedSceneSlug) return;
  await runGuardedTransition(async () => {
    state.selectedSceneSlug = sceneSlug;
    renderSceneTable();
    await loadSceneDetail(state.selectedStorySlug, sceneSlug);
  });
}

async function createScene() {
  // Create a new scene markdown file in the selected story folder.
  const sceneName = sceneNewName.value.trim();
  if (!state.selectedStorySlug) {
    showSceneMessage("Select or create a story first.", "error");
    return;
  }
  if (!sceneName) {
    showSceneMessage("Scene name is required.", "error");
    return;
  }
  sceneCreate.disabled = true;
  showSceneMessage("Creating scene...");
  try {
    const payload = await fetchJson(
      `/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes?${new URLSearchParams({ scene_name: sceneName }).toString()}`,
      { method: "POST" },
    );
    state.scenes = payload.scenes || state.scenes;
    updateStoryGitWarning(payload.has_story_changes);
    state.sceneDetail = payload.document || null;
    state.selectedSceneSlug = state.sceneDetail?.scene?.slug || state.selectedSceneSlug;
    sceneNewName.value = "";
    renderSceneTable();
    if (state.sceneDetail) {
      sceneEditorTitle.textContent = state.sceneDetail.scene.title || "Scene";
      sceneText.value = state.sceneDetail.text || "";
      sceneSave.disabled = false;
      sceneStageRender.disabled = false;
      sceneBuilderOpen.disabled = false;
      sceneDelete.disabled = false;
      updateSceneImageToggle();
      renderValidationBox(sceneValidation, state.sceneDetail.validation_errors || [], "Scene markdown is valid.");
      state.savedBaselines.scene = sceneSnapshot();
      setSaveState(sceneSaveState, "Saved", "saved");
    }
    showSceneMessage(payload.message || "Scene created.");
  } catch (error) {
    showSceneMessage(error.message, "error");
  } finally {
    sceneCreate.disabled = false;
  }
}

async function saveScene() {
  // Save the current scene markdown document.
  if (!state.selectedStorySlug || !state.selectedSceneSlug) {
    showSceneMessage("Select a scene first.", "error");
    return;
  }
  sceneSave.disabled = true;
  showSceneMessage("Saving scene...");
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}`, {
      method: "PUT",
      headers: { "Content-Type": "text/markdown; charset=utf-8" },
      body: sceneText.value || "",
    });
    state.scenes = payload.scenes || state.scenes;
    updateStoryGitWarning(payload.has_story_changes);
    state.sceneDetail = payload.document || null;
    state.selectedSceneSlug = state.sceneDetail?.scene?.slug || state.selectedSceneSlug;
    renderSceneTable();
    renderValidationBox(sceneValidation, state.sceneDetail?.validation_errors || [], "Scene markdown is valid.");
    updateSceneImageToggle();
    showSceneMessage(payload.message || "Scene saved.");
    state.savedBaselines.scene = sceneSnapshot();
    setSaveState(sceneSaveState, "Saved", "saved");
    return true;
  } catch (error) {
    showSceneMessage(error.message, "error");
    setSaveState(sceneSaveState, "Error", "error");
    return false;
  } finally {
    sceneSave.disabled = false;
  }
}

async function deleteScene() {
  // Confirm, commit current story files, then delete the selected scene markdown and image.
  if (!state.selectedStorySlug || !state.selectedSceneSlug || !confirm(`Delete scene ${state.selectedSceneSlug}?`)) {
    return;
  }
  sceneDelete.disabled = true;
  sceneSave.disabled = true;
  sceneStageRender.disabled = true;
  sceneBuilderOpen.disabled = true;
  showSceneMessage("Deleting scene...");
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}`, {
      method: "DELETE",
    });
    state.scenes = payload.scenes || [];
    state.selectedSceneSlug = state.scenes[0]?.slug || null;
    state.sceneDetail = null;
    updateStoryGitWarning(payload.has_story_changes);
    renderSceneTable();
    if (payload.git) {
      applyStoryGitPayload(payload.git);
    }
    if (state.selectedSceneSlug) {
      await loadSceneDetail(state.selectedStorySlug, state.selectedSceneSlug);
    } else {
      clearSceneEditor();
      renderSceneTable();
    }
    showSceneMessage(payload.message || "Scene deleted.");
  } catch (error) {
    showSceneMessage(error.message, "error");
  } finally {
    sceneSave.disabled = !state.sceneDetail;
    sceneStageRender.disabled = !state.sceneDetail;
    sceneBuilderOpen.disabled = !state.sceneDetail;
    sceneDelete.disabled = !state.sceneDetail;
  }
}

async function stageSceneRender() {
  if (!state.selectedStorySlug || !state.selectedSceneSlug) {
    showSceneMessage("Select a scene first.", "error");
    return;
  }
  sceneStageRender.disabled = true;
  sceneSave.disabled = true;
  sceneBuilderOpen.disabled = true;
  showSceneMessage("Staging scene render...");
  try {
    const payload = await fetchJson(
      `/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/stage-render`,
      { method: "POST" },
    );
    const askId = payload.task?.ask_id || null;
    showSceneMessage(payload.message || "Scene render staged.");
    await activatePage("render-console", { skipAutosave: true });
    await loadRenderConsoleTasks(askId);
  } catch (error) {
    showSceneMessage(error.message, "error");
  } finally {
    sceneStageRender.disabled = false;
    sceneSave.disabled = false;
    sceneBuilderOpen.disabled = !state.sceneDetail;
  }
}

function toggleSceneImage() {
  const imagePath = state.sceneDetail?.image_path || "";
  if (!state.sceneDetail?.image_exists || !imagePath) {
    return;
  }
  if (sceneImagePanel.hidden) {
    sceneImagePreview.src = fileUrl(imagePath, Date.now().toString());
    sceneImagePanel.hidden = false;
  } else {
    sceneImagePanel.hidden = true;
    sceneImagePreview.removeAttribute("src");
  }
}

function openSceneImageFullscreen() {
  if (!sceneImagePanel.hidden && sceneImagePreview.src) {
    openFullscreenImage(sceneImagePreview.src, sceneImagePreview.alt || "Scene render");
  }
}

const zineSlotInputs = {
  front: zineFront,
  page_1: zinePage1,
  page_2: zinePage2,
  page_3: zinePage3,
  page_4: zinePage4,
  page_5: zinePage5,
  page_6: zinePage6,
  back: zineBack,
};

function renderZineStoryOptions() {
  const selected = state.zineStorySlug || state.stories[0]?.slug || "";
  zineStorySelect.replaceChildren(
    ...state.stories.map((story) => option(story.slug, story.title || story.slug)),
  );
  state.zineStorySlug = state.stories.some((story) => story.slug === selected)
    ? selected
    : state.stories[0]?.slug || null;
  zineStorySelect.value = state.zineStorySlug || "";
  zineFillStory.disabled = !state.zineStorySlug;
}

function setZineSpread(oddPage, enabled) {
  const evenPage = oddPage + 1;
  const oddInput = zineSlotInputs[`page_${oddPage}`];
  const evenInput = zineSlotInputs[`page_${evenPage}`];
  const checkbox = oddPage === 1 ? zineSpread1 : oddPage === 3 ? zineSpread3 : zineSpread5;
  checkbox.checked = enabled;
  evenInput.disabled = enabled;
  if (enabled) {
    evenInput.value = "";
  } else if (!evenInput.value.trim() && oddInput.value.trim()) {
    evenInput.value = oddInput.value.trim();
  }
}

function syncZineSpreadControls() {
  for (const oddPage of [1, 3, 5]) {
    const evenInput = zineSlotInputs[`page_${oddPage + 1}`];
    const enabled = !evenInput.value.trim();
    const checkbox = oddPage === 1 ? zineSpread1 : oddPage === 3 ? zineSpread3 : zineSpread5;
    checkbox.checked = enabled;
    evenInput.disabled = enabled;
  }
}

function clearZineEditor() {
  state.selectedZineSlug = null;
  state.zineDocument = null;
  zineEditorTitle.textContent = "New Zine";
  zineName.value = "";
  for (const input of Object.values(zineSlotInputs)) {
    input.value = "";
    input.disabled = false;
  }
  for (const checkbox of [zineSpread1, zineSpread3, zineSpread5]) {
    checkbox.checked = false;
  }
  zineEdit.disabled = true;
  zineRegenerate.disabled = true;
  zineDelete.disabled = true;
  zineSave.textContent = "Create Zine";
  zinePreviewSection.hidden = true;
  zinePreview.removeAttribute("src");
  renderZineTable();
  showZineMessage("");
  state.savedBaselines.zine = zineSnapshot();
}

function renderZineTable() {
  zineTableBody.replaceChildren();
  if (!state.zines.length) {
    renderEmptyRow(zineTableBody, 2, "No zines exist. Create a zine to begin.");
    return;
  }
  for (const zine of state.zines) {
    const row = document.createElement("tr");
    for (const value of [zine.name, zine.slug]) {
      const cell = document.createElement("td");
      cell.textContent = value || "";
      row.append(cell);
    }
    makeSelectableRow(row, zine.name || zine.slug, zine.slug === state.selectedZineSlug, () => selectZine(zine.slug));
    zineTableBody.append(row);
  }
}

function renderZineDocument(document) {
  state.zineDocument = document;
  state.selectedZineSlug = document?.zine?.slug || null;
  const metadata = document?.metadata || {};
  zineEditorTitle.textContent = metadata.zine_name || "Zine";
  zineName.value = metadata.zine_name || "";
  for (const [key, input] of Object.entries(zineSlotInputs)) {
    input.value = metadata.slots?.[key] || "";
  }
  syncZineSpreadControls();
  zineEdit.disabled = false;
  zineRegenerate.disabled = false;
  zineDelete.disabled = false;
  zineSave.textContent = "Save Zine";
  if (document?.zine?.image_exists && document.zine.image_path) {
    zinePreview.src = fileUrl(document.zine.image_path, Date.now().toString());
    zinePreviewSection.hidden = false;
  } else {
    zinePreviewSection.hidden = true;
    zinePreview.removeAttribute("src");
  }
  renderZineTable();
  state.savedBaselines.zine = zineSnapshot();
}

async function loadZineStorySources() {
  state.zineStorySlug = zineStorySelect.value || state.zineStorySlug;
  state.zineStorySources = [];
  zineSceneOptions.replaceChildren();
  if (!state.zineStorySlug) {
    zineFillStory.disabled = true;
    return;
  }
  try {
    const payload = await fetchJson(`/api/zines/story-scenes/${encodeURIComponent(state.zineStorySlug)}`);
    state.zineStorySources = payload.scenes || [];
    zineSceneOptions.replaceChildren(...state.zineStorySources.map((scene) => {
      const item = document.createElement("option");
      item.value = scene.tag;
      item.label = scene.title || scene.scene_slug;
      return item;
    }));
    zineFillStory.disabled = !state.zineStorySources.length;
  } catch (error) {
    zineFillStory.disabled = true;
    showZineMessage(error.message, "error");
  }
}

async function loadZines() {
  zineStatus.textContent = "Loading zines...";
  try {
    if (!state.stories.length) {
      await loadStories();
    }
    renderZineStoryOptions();
    await loadZineStorySources();
    const payload = await fetchJson("/api/zines");
    state.zines = payload.zines || [];
    if (state.selectedZineSlug && !state.zines.some((item) => item.slug === state.selectedZineSlug)) {
      state.selectedZineSlug = null;
    }
    if (!state.selectedZineSlug && state.zines.length) {
      state.selectedZineSlug = state.zines[0].slug;
    }
    renderZineTable();
    if (state.selectedZineSlug) {
      await selectZine(state.selectedZineSlug, { skipGuard: true });
    } else {
      clearZineEditor();
    }
    zineStatus.textContent = `${state.zines.length} zine${state.zines.length === 1 ? "" : "s"}`;
  } catch (error) {
    zineStatus.textContent = "Load failed.";
    showZineMessage(error.message, "error");
  }
}

async function selectZine(slug, options = {}) {
  if (slug === state.selectedZineSlug && state.zineDocument?.zine?.slug === slug) return;
  const select = async () => {
    state.selectedZineSlug = slug;
    renderZineTable();
    try {
      const payload = await fetchJson(`/api/zines/${encodeURIComponent(slug)}`);
      renderZineDocument(payload.document);
      const sceneTag = Object.values(payload.document?.metadata?.slots || {})
        .find((value) => String(value).startsWith("{{SCENE:"));
      const storyMatch = String(sceneTag || "").match(/^\{\{SCENE:([^:}]+):/);
      if (storyMatch && state.stories.some((story) => story.slug === storyMatch[1])) {
        state.zineStorySlug = storyMatch[1];
        renderZineStoryOptions();
        await loadZineStorySources();
      }
      showZineMessage("");
    } catch (error) {
      showZineMessage(error.message, "error");
    }
  };
  if (options.skipGuard) {
    await select();
  } else {
    await runGuardedTransition(select);
  }
}

function fillZineFromStory() {
  const story = state.stories.find((item) => item.slug === state.zineStorySlug);
  if (!state.zineStorySources.length) {
    showZineMessage("The selected story has no readable scene images.", "error");
    return;
  }
  if (!zineName.value.trim()) {
    zineName.value = story?.title || state.zineStorySlug || "";
  }
  for (const input of Object.values(zineSlotInputs)) {
    input.value = "";
    input.disabled = false;
  }
  for (const checkbox of [zineSpread1, zineSpread3, zineSpread5]) {
    checkbox.checked = false;
  }
  const destinations = ["front", "page_1", "page_2", "page_3", "page_4", "page_5", "page_6", "back"];
  let destinationIndex = 0;
  let assigned = 0;
  for (const scene of state.zineStorySources) {
    if (destinationIndex >= destinations.length) break;
    const destination = destinations[destinationIndex];
    zineSlotInputs[destination].value = scene.tag;
    assigned += 1;
    const oddPage = destination === "page_1" ? 1 : destination === "page_3" ? 3 : destination === "page_5" ? 5 : 0;
    if (oddPage && Number(scene.width) > Number(scene.height)) {
      setZineSpread(oddPage, true);
      destinationIndex += 2;
    } else {
      destinationIndex += 1;
    }
  }
  syncZineSpreadControls();
  const remaining = state.zineStorySources.length - assigned;
  showZineMessage(remaining > 0 ? `Filled from story. ${remaining} scene image(s) were left unassigned.` : "Filled from story.");
}

function zinePayload() {
  return {
    zine_name: zineName.value.trim(),
    slots: Object.fromEntries(Object.entries(zineSlotInputs).map(([key, input]) => [key, input.value.trim()])),
  };
}

async function saveZine() {
  const currentSlug = state.selectedZineSlug;
  const isEdit = Boolean(currentSlug);
  zineSave.disabled = true;
  showZineMessage(isEdit ? "Saving zine..." : "Creating zine...");
  try {
    const payload = await fetchJson(isEdit ? `/api/zines/${encodeURIComponent(currentSlug)}` : "/api/zines", {
      method: isEdit ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(zinePayload()),
    });
    state.zines = payload.zines || state.zines;
    renderZineDocument(payload.document);
    zineStatus.textContent = `${state.zines.length} zine${state.zines.length === 1 ? "" : "s"}`;
    showZineMessage(payload.message || "Zine saved.");
    state.savedBaselines.zine = zineSnapshot();
    return true;
  } catch (error) {
    showZineMessage(error.message, "error");
    return false;
  } finally {
    zineSave.disabled = false;
  }
}

async function regenerateZine() {
  if (!state.selectedZineSlug) return;
  zineRegenerate.disabled = true;
  showZineMessage("Regenerating zine...");
  try {
    const payload = await fetchJson(`/api/zines/${encodeURIComponent(state.selectedZineSlug)}/regenerate`, { method: "POST" });
    renderZineDocument(payload.document);
    showZineMessage(payload.message || "Zine regenerated.");
  } catch (error) {
    showZineMessage(error.message, "error");
  } finally {
    zineRegenerate.disabled = false;
  }
}

async function deleteZine() {
  if (!state.selectedZineSlug || !confirm(`Delete zine ${state.selectedZineSlug}?`)) return;
  const slug = state.selectedZineSlug;
  try {
    const payload = await fetchJson(`/api/zines/${encodeURIComponent(slug)}`, { method: "DELETE" });
    state.zines = payload.zines || [];
    clearZineEditor();
    if (state.zines.length) {
      await selectZine(state.zines[0].slug, { skipGuard: true });
    }
    zineStatus.textContent = `${state.zines.length} zine${state.zines.length === 1 ? "" : "s"}`;
    showZineMessage(payload.message || "Zine deleted.");
  } catch (error) {
    showZineMessage(error.message, "error");
  }
}

function closeSceneBuilder() {
  state.sceneBuilderOpen = false;
  state.sceneBuilder = null;
  state.selectedBuilderPlacementId = null;
  state.selectedBuilderElementId = null;
  sceneBuilderPanel.replaceChildren();
  sceneBuilderStatus.textContent = "";
  sceneBuilderPrevious.disabled = true;
  sceneBuilderNext.disabled = true;
  showSceneBuilderMessage("");
}

function updateSceneBuilderNavigation() {
  const index = state.scenes.findIndex((scene) => scene.slug === state.selectedSceneSlug);
  sceneBuilderPrevious.disabled = index <= 0;
  sceneBuilderNext.disabled = index < 0 || index >= state.scenes.length - 1;
}

async function navigateSceneBuilder(offset) {
  if (!state.selectedStorySlug || !state.selectedSceneSlug) return;
  let index = state.scenes.findIndex((scene) => scene.slug === state.selectedSceneSlug);
  if (index < 0) {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes`);
    state.scenes = payload.scenes || [];
    index = state.scenes.findIndex((scene) => scene.slug === state.selectedSceneSlug);
  }
  const target = state.scenes[index + offset];
  if (!target) return;
  if (state.sceneBuilder && await saveSceneBuilder(true) === null) return;
  state.selectedSceneSlug = target.slug;
  await loadSceneDetail(state.selectedStorySlug, target.slug);
  await openSceneBuilder();
}

async function returnToScenesFromBuilder() {
  await saveSceneBuilder(true);
  closeSceneBuilder();
  await activatePage("scenes", { skipAutosave: true });
}

function builderSelectedPlacement() {
  return (state.sceneBuilder?.placements || []).find((item) => item.id === state.selectedBuilderPlacementId) || null;
}

function builderSelectedElement() {
  return (state.sceneBuilder?.scene_elements || []).find((item) => item.id === state.selectedBuilderElementId) || null;
}

function builderElementOptions(selected = "") {
  const elements = state.sceneBuilder?.scene_elements || [];
  return `<option value=""></option>` + elements.map((element) => {
    const value = element.id || "";
    return `<option value="${escapeHtml(value)}"${value === selected ? " selected" : ""}>${escapeHtml(element.display_name || value)}</option>`;
  }).join("");
}

function builderElementLabel(elementId) {
  const element = (state.sceneBuilder?.scene_elements || []).find((item) => item.id === elementId);
  return element?.display_name || elementId || "";
}

function builderNormalizeId(value) {
  return String(value || "").replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "scene_element";
}

function builderSyncControls() {
  let elementTypeChangedToProp = false;
  for (const control of sceneBuilderPanel.querySelectorAll("[data-builder-field]")) {
    setPathValue(state.sceneBuilder, control.dataset.builderField, control.type === "number" ? Number(control.value || 0) : control.value);
  }
  const element = builderSelectedElement();
  if (element) {
    for (const control of sceneBuilderPanel.querySelectorAll("[data-builder-element-field]")) {
      const field = control.dataset.builderElementField;
      if (field === "id" && control.value && control.value !== element.id) {
        const oldId = element.id;
        element.id = control.value;
        state.selectedBuilderElementId = control.value;
        for (const placement of state.sceneBuilder.placements || []) {
          if (placement.scene_element_id === oldId) placement.scene_element_id = control.value;
          if (placement.gaze_target_element_id === oldId) placement.gaze_target_element_id = control.value;
          if (placement.interaction_target_element_id === oldId) placement.interaction_target_element_id = control.value;
        }
        for (const interaction of state.sceneBuilder.interactions || []) {
          if (interaction.subject_element_id === oldId) interaction.subject_element_id = control.value;
          if (interaction.target_element_id === oldId) interaction.target_element_id = control.value;
        }
      } else {
        if (field === "element_type" && control.value === "Prop" && element.element_type !== "Prop") {
          elementTypeChangedToProp = true;
        }
        if (field.includes(".")) {
          setPathValue(element, field, control.value);
        } else {
          element[field] = control.value;
        }
      }
    }
    if (element.element_type === "Backdrop") {
      const placement = builderPlacementForElement(element.id);
      if (placement) placement.position_within_cell = "";
    }
  }
  for (const control of sceneBuilderPanel.querySelectorAll("[data-builder-interaction]")) {
    const interaction = state.sceneBuilder.interactions[Number(control.dataset.builderInteraction)];
    if (interaction) {
      interaction[control.dataset.builderInteractionField] = control.value;
    }
  }
  for (const control of sceneBuilderPanel.querySelectorAll("[data-builder-dialogue]")) {
    const dialogue = state.sceneBuilder.dialogue[Number(control.dataset.builderDialogue)];
    if (dialogue) {
      const field = control.dataset.builderDialogueField;
      if (field === "max_lines") {
        dialogue[field] = Number(control.value || 0);
      } else {
        dialogue[field] = control.value;
      }
    }
  }
  const placement = builderSelectedPlacement();
  if (placement) {
    const placementElement = builderSelectedElement();
    for (const control of sceneBuilderPanel.querySelectorAll("[data-builder-placement-field]")) {
      const field = control.dataset.builderPlacementField;
      if (field === "position_within_cell" && placementElement?.element_type === "Backdrop") {
        placement.position_within_cell = "";
      } else if (field.includes(".")) {
        setPathValue(placement, field, control.type === "number" ? Number(control.value || 0) : control.value);
      } else {
        placement[field] = control.type === "number" ? Number(control.value || 0) : control.value;
      }
    }
    if (elementTypeChangedToProp) placement.position_within_cell = "None";
    if (placement.position_within_cell === "None") {
      state.sceneBuilder.setup.composition.left_to_right = (state.sceneBuilder.setup.composition.left_to_right || []).filter((item) => item !== placement.scene_element_id);
    }
  }
}

function builderApplyChange(event) {
  if (!state.sceneBuilder) {
    return;
  }
  builderSyncControls();
  if (event?.target?.id === "builder-composition-element") {
    return;
  }
  renderSceneBuilder();
}

function builderPlacementForElement(elementId) {
  return (state.sceneBuilder?.placements || []).find((item) => item.scene_element_id === elementId) || null;
}

function builderCreatePlacementForElement(element) {
  return {
    id: `placement_${Date.now()}`,
    scene_element_id: element.id,
    position_within_cell: element.element_type === "Backdrop" ? "" : element.element_type === "Prop" ? "None" : "center",
    depth: element.element_type === "Backdrop" ? "background" : "midground",
    frame_coverage: "",
    distance_from_camera: "",
    visual_scale: "",
    pose: { summary: "", temporary_condition: "", gaze_target_element_id: "", expression: "", left_arm_action: "", right_arm_action: "", leg_foot_detail: "", balance_weight_detail: "" },
    motion: { state: "stationary", direction_screen: "", cue: "" },
    placement_notes: "",
  };
}

function builderResourceTypeOptions(selected = "Character") {
  const options = state.sceneBuilderOptions.resource_type || [
    { value: "Character", label: "Character" },
    { value: "Person", label: "Person" },
    { value: "Place", label: "Place" },
    { value: "Object", label: "Object" },
    { value: "Scene-Only", label: "Scene-Only" },
  ];
  return options.map((item) => `<option value="${escapeHtml(item.value)}"${item.value === selected ? " selected" : ""}>${escapeHtml(item.label)}</option>`).join("");
}

function builderAuxCategoryForResourceType(resourceType) {
  return (state.sceneBuilderOptions.resource_type || []).find((item) => item.value === resourceType)?.category || "";
}

function builderElementTypeForResourceType(resourceType) {
  if (resourceType === "Place") return "Backdrop";
  if (resourceType === "Object" || resourceType === "Scene-Only") return "Prop";
  return "Character";
}

function builderUpdateElementModalSections() {
  const resourceType = builderElementResourceType.value || "Character";
  builderElementCharacterSection.hidden = resourceType !== "Character";
  builderElementAuxSection.hidden = !builderAuxCategoryForResourceType(resourceType);
  builderElementSceneSection.hidden = resourceType !== "Scene-Only";
}

async function builderLoadElementCostumes() {
  const character = builderElementCharacter.value || "";
  const phase = builderElementPhase.value || "";
  builderElementCostume.replaceChildren();
  state.builderElementCostumes = [];
  if (!character || !phase) return;
  const params = new URLSearchParams({ character, phase });
  const payload = await fetchJson(`/api/costumes?${params.toString()}`);
  state.builderElementCostumes = payload.costumes || [];
  state.builderCostumesByCharacterPhase[`${character}\n${phase}`] = state.builderElementCostumes;
  setSelectOptionsWithLabels(builderElementCostume, [
    { value: "", label: "(No costume)" },
    ...state.builderElementCostumes.map((item) => ({ value: item.name || "", label: item.name || "" })),
  ]);
}

async function builderLoadSelectedElementCostumes(element = builderSelectedElement()) {
  if (element?.resource_type !== "Character" || !element.character || !element.phase) return;
  const key = `${element.character}\n${element.phase}`;
  if (state.builderCostumesByCharacterPhase[key]) return;
  const params = new URLSearchParams({ character: element.character, phase: element.phase });
  const payload = await fetchJson(`/api/costumes?${params.toString()}`);
  state.builderCostumesByCharacterPhase[key] = payload.costumes || [];
}

function builderCostumeOptions(element) {
  const key = `${element.character || ""}\n${element.phase || ""}`;
  const names = (state.builderCostumesByCharacterPhase[key] || []).map((item) => item.name || "").filter(Boolean);
  if (element.costume && !names.includes(element.costume)) names.unshift(element.costume);
  return [
    `<option value=""${element.costume ? "" : " selected"}>(No costume)</option>`,
    ...names.map((name) => `<option value="${escapeHtml(name)}"${name === element.costume ? " selected" : ""}>${escapeHtml(name)}</option>`),
  ].join("");
}

async function builderLoadElementAuxResources() {
  const category = builderAuxCategoryForResourceType(builderElementResourceType.value || "");
  builderElementAux.replaceChildren();
  if (!category) return;
  if (!state.builderElementAuxResources[category]) {
    const payload = await fetchJson(`/api/auxiliary-resources?${new URLSearchParams({ category }).toString()}`);
    state.builderElementAuxResources[category] = payload.resources || [];
  }
  setSelectOptionsWithLabels(builderElementAux, state.builderElementAuxResources[category].map((item) => ({ value: item.resource_id, label: item.label || item.resource_id })));
}

async function openBuilderElementDialog() {
  setSelectOptionsWithLabels(builderElementResourceType, (state.sceneBuilderOptions.resource_type || []).map((item) => ({ value: item.value, label: item.label })));
  builderElementResourceType.value = "Character";
  setSelectOptions(builderElementCharacter, state.characters || []);
  builderElementCharacter.value = state.character || state.characters[0] || "";
  setSelectOptions(builderElementPhase, state.phasesByCharacter[builderElementCharacter.value] || []);
  builderElementPhase.value = state.phase || builderElementPhase.options[0]?.value || "";
  builderElementSceneName.value = "";
  builderUpdateElementModalSections();
  await builderLoadElementCostumes();
  await builderLoadElementAuxResources();
  builderElementModal.showModal();
  builderElementResourceType.focus();
}

function builderAddElementFromDialog() {
  const index = (state.sceneBuilder.scene_elements || []).length + 1;
  const resourceType = builderElementResourceType.value || "Character";
  const category = builderAuxCategoryForResourceType(resourceType);
  const resource = category ? (state.builderElementAuxResources[category] || []).find((item) => item.resource_id === builderElementAux.value) : null;
  const displayName = resourceType === "Character"
    ? builderElementCharacter.value
    : resourceType === "Scene-Only"
      ? builderElementSceneName.value.trim()
      : resource?.label || "";
  if (!displayName) {
    showSceneBuilderMessage("Display name is required.", "error");
    return;
  }
  const baseId = self.crypto?.randomUUID ? `${builderNormalizeId(displayName)}_${self.crypto.randomUUID().slice(0, 8)}` : `${builderNormalizeId(displayName)}_${Date.now()}`;
  const element = {
    id: index === 1 ? builderNormalizeId(displayName) : baseId,
    display_name: displayName,
    resource_type: resourceType,
    element_type: builderElementTypeForResourceType(resourceType),
    character: resourceType === "Character" ? builderElementCharacter.value : "",
    phase: resourceType === "Character" ? builderElementPhase.value : "",
    costume: resourceType === "Character" ? builderElementCostume.value : "",
    aux_category: category,
    aux_resource_id: resource?.resource_id || "",
    reference_images: [],
    element_visual_override: "",
    fallback_visual_description: "",
    notes: "",
  };
  state.sceneBuilder.scene_elements.push(element);
  state.sceneBuilder.placements.push(builderCreatePlacementForElement(element));
  state.selectedBuilderElementId = element.id;
  state.selectedBuilderPlacementId = builderPlacementForElement(element.id)?.id || null;
  builderElementModal.close();
  renderSceneBuilder();
}

function builderRemoveSelectedElement() {
  const element = builderSelectedElement();
  if (!element) {
    return;
  }
  const hasLinks = (state.sceneBuilder.placements || []).some((item) => item.scene_element_id === element.id)
    || (state.sceneBuilder.interactions || []).some((item) => item.subject_element_id === element.id || item.target_element_id === element.id);
  if (hasLinks && !window.confirm("Delete this element and its linked placements/interactions?")) {
    return;
  }
  state.sceneBuilder.scene_elements = (state.sceneBuilder.scene_elements || []).filter((item) => item.id !== element.id);
  state.sceneBuilder.placements = (state.sceneBuilder.placements || []).filter((item) => item.scene_element_id !== element.id);
  state.sceneBuilder.interactions = (state.sceneBuilder.interactions || []).filter((item) => item.subject_element_id !== element.id && item.target_element_id !== element.id);
  state.sceneBuilder.setup.composition.left_to_right = (state.sceneBuilder.setup.composition.left_to_right || []).filter((item) => item !== element.id);
  state.selectedBuilderElementId = state.sceneBuilder.scene_elements[0]?.id || null;
  state.selectedBuilderPlacementId = builderPlacementForElement(state.selectedBuilderElementId)?.id || null;
  renderSceneBuilder();
}

function builderDuplicateSelectedElement() {
  const element = builderSelectedElement();
  if (!element) return;
  const copy = JSON.parse(JSON.stringify(element));
  copy.id = `${element.id || "element"}_copy_${Date.now()}`;
  copy.display_name = `${element.display_name || element.id || "Element"} Copy`;
  state.sceneBuilder.scene_elements.push(copy);
  state.selectedBuilderElementId = copy.id;
  state.selectedBuilderPlacementId = null;
  renderSceneBuilder();
}

function builderAddInteraction() {
  state.sceneBuilder.interactions.push({ subject_element_id: "", relationship: "looking at", target_element_id: "", note: "" });
  renderSceneBuilder();
}

function builderDeleteInteraction(index) {
  state.sceneBuilder.interactions = (state.sceneBuilder.interactions || []).filter((_, itemIndex) => itemIndex !== index);
  renderSceneBuilder();
}

function builderAddDialogue() {
  state.sceneBuilder.dialogue = state.sceneBuilder.dialogue || [];
  const selectedElement = builderSelectedElement();
  state.sceneBuilder.dialogue.push({
    id: `dialogue_${Date.now()}`,
    speaker_element_id: selectedElement?.id || "",
    text: "",
    target_element_id: "",
    pointer_target: "speaker mouth",
    max_lines: 3,
    notes: "",
  });
  renderSceneBuilder();
}

function builderDeleteDialogue(index) {
  state.sceneBuilder.dialogue = (state.sceneBuilder.dialogue || []).filter((_, itemIndex) => itemIndex !== index);
  renderSceneBuilder();
}

function builderRenderElements() {
  const rows = (state.sceneBuilder.scene_elements || []).map((element) => {
    const placement = builderPlacementForElement(element.id);
    const position = placement?.position_within_cell || "—";
    const depth = position === "None" ? "None" : placement?.depth || "—";
    return `
      <button type="button" class="scene-builder-element-row ${element.id === state.selectedBuilderElementId ? "selected" : ""}" data-builder-select-element="${escapeHtml(element.id || "")}">
        <span>${escapeHtml(element.display_name || element.id || "")}</span>
        <small>${escapeHtml(element.element_type || "")} | Position: ${escapeHtml(position)} | Depth: ${escapeHtml(depth)}</small>
      </button>
    `;
  }).join("");
  return `
    <div class="scene-builder-card">
      <h4>Scene Elements</h4>
      <div class="button-row compact">
        <button type="button" data-builder-action="add-element">Add Element</button>
        <button type="button" data-builder-action="delete-element">Delete Selected</button>
        <button type="button" data-builder-action="duplicate-element">Duplicate</button>
      </div>
      <div class="scene-builder-element-list">${rows || "<p>No elements have been added yet.</p>"}</div>
    </div>
  `;
}

function builderRenderElementEditor() {
  const element = builderSelectedElement();
  if (!element) {
    return `<div class="scene-builder-card"><h4>Selected Element</h4><p>Select or add a scene element.</p></div>`;
  }
  const referenceTag = element.reference_images?.[0]?.tag || "";
  const reference = (state.sceneBuilderReferences || []).find((item) => item.tag === referenceTag);
  const referenceThumbnail = reference?.thumbnail_path
    ? `<img class="scene-builder-reference-thumbnail fullscreen-image-trigger" src="${fileUrl(reference.thumbnail_path)}" alt="${escapeHtml(reference.label || referenceTag)}">`
    : "";
  return `
    <div class="scene-builder-card">
      <h4>Selected Element</h4>
      <div class="scene-builder-fields">
        <label>${builderCaption("Display name", "scene_elements[].display_name")}<input value="${escapeHtml(element.display_name || "")}" data-builder-element-field="display_name"></label>
        <label>${builderCaption("Resource type", "scene_elements[].resource_type")}<select data-builder-element-field="resource_type">${builderResourceTypeOptions(element.resource_type || "Character")}</select></label>
        <label>${builderCaption("Type", "scene_elements[].element_type")}<select data-builder-element-field="element_type"><option value="Character"${element.element_type === "Character" ? " selected" : ""}>Character</option><option value="Monster"${element.element_type === "Monster" ? " selected" : ""}>Monster</option><option value="Prop"${element.element_type === "Prop" ? " selected" : ""}>Prop</option><option value="Backdrop"${element.element_type === "Backdrop" ? " selected" : ""}>Backdrop</option></select></label>
        ${element.resource_type === "Character" ? `<label>${builderCaption("Costume", "scene_elements[].costume")}<select data-builder-element-field="costume">${builderCostumeOptions(element)}</select></label>` : ""}
        <div class="scene-builder-reference-field full">${referenceThumbnail}<label>${builderCaption("Reference tag", "scene_elements[].reference_images[].tag")}<span class="inline-field"><input value="${escapeHtml(referenceTag)}" data-builder-element-field="reference_images.0.tag"><button type="button" data-builder-action="pick-image-tag">Search</button></span></label></div>
        <label class="full">${builderCaption("(Element visual override) Element Override: ...", "scene_elements[].element_visual_override")}<textarea data-builder-element-field="element_visual_override">${escapeHtml(element.element_visual_override || "")}</textarea></label>
        <label class="full">${builderCaption("(Fallback visual description) Visual description: ...", "scene_elements[].fallback_visual_description")}<textarea data-builder-element-field="fallback_visual_description">${escapeHtml(element.fallback_visual_description || "")}</textarea></label>
        <label class="full">${builderCaption("Notes", "scene_elements[].notes")}<textarea data-builder-element-field="notes">${escapeHtml(element.notes || "")}</textarea></label>
      </div>
    </div>
  `;
}

function builderRenderPlacementEditor() {
  const placement = builderSelectedPlacement();
  const element = builderSelectedElement();
  const placementTitle = `Placement for ${element?.display_name || element?.id || "Selected Element"}`;
  if (!placement) {
    return `<div class="scene-builder-card"><h4>${escapeHtml(placementTitle)}</h4><p>Select or add a scene element.</p></div>`;
  }
  const showActing = !element || ["Character", "Monster"].includes(element.element_type || "Character");
  const isBackdrop = element?.element_type === "Backdrop";
  placement.motion = placement.motion || { state: "stationary", direction_screen: "", cue: "" };
  if (isBackdrop) placement.position_within_cell = "";
  const placementDisabled = placement.position_within_cell === "None" ? " disabled" : "";
  return `
    <div class="scene-builder-card">
      <h4>${escapeHtml(placementTitle)}</h4>
      <div class="scene-builder-fields">
        <label>${builderCaption("Position", "placements[].position_within_cell")}<select data-builder-placement-field="position_within_cell"${isBackdrop ? " disabled" : ""}>${builderOptionHtml("position_within_cell", isBackdrop ? "" : placement.position_within_cell || "center")}</select></label>
        <label>${builderCaption("Depth", "placements[].depth")}<select data-builder-placement-field="depth"${placementDisabled}>${builderOptionHtml("depth", placement.depth || "midground")}</select></label>
        <label class="full">${builderCaption("World Position", "placements[].world_position")}<input value="${escapeHtml(placement.world_position || "")}" data-builder-placement-field="world_position"${placementDisabled}></label>
        ${showActing ? `
          <label class="full">${builderCaption("(Pose) Element [pose] in the selected region.", "placements[].pose.summary")}<input list="builder-pose-list" value="${escapeHtml(placement.pose?.summary || "")}" data-builder-placement-field="pose.summary"${placementDisabled}></label>
          <label>${builderCaption("(Gaze target) Element looks directly at ...", "placements[].pose.gaze_target_element_id")}<select data-builder-placement-field="pose.gaze_target_element_id"${placementDisabled}>${builderElementOptions(placement.pose?.gaze_target_element_id || "")}</select></label>
          <label>${builderCaption("(Expression) Comma-separated expression instructions.", "placements[].pose.expression")}<input list="builder-expression-list" value="${escapeHtml(placement.pose?.expression || "")}" data-builder-placement-field="pose.expression"${placementDisabled}></label>
        ` : ""}
        <label>${builderCaption("Motion", "placements[].motion.state")}<select data-builder-placement-field="motion.state"${placementDisabled}><option value="stationary"${placement.motion.state !== "moving" ? " selected" : ""}>Stationary</option><option value="moving"${placement.motion.state === "moving" ? " selected" : ""}>Moving</option></select></label>
        <label>${builderCaption("(Movement direction) Element is visibly moving ... on screen.", "placements[].motion.direction_screen")}<select data-builder-placement-field="motion.direction_screen"${placementDisabled || placement.motion.state !== "moving" ? " disabled" : ""}>${["", "left", "right", "toward camera", "away from camera", "up", "down", "up-left", "up-right", "down-left", "down-right"].map((value) => `<option value="${value}"${value === (placement.motion.direction_screen || "") ? " selected" : ""}>${value}</option>`).join("")}</select></label>
        <label class="full">${builderCaption("(Motion cue) Element is visibly moving, ...", "placements[].motion.cue")}<input value="${escapeHtml(placement.motion.cue || "")}" data-builder-placement-field="motion.cue"${placementDisabled}></label>
        <label class="full">${builderCaption("Notes", "placements[].placement_notes")}<textarea data-builder-placement-field="placement_notes"${placementDisabled}>${escapeHtml(placement.placement_notes || "")}</textarea></label>
      </div>
    </div>
  `;
}

function builderRenderDialogueEditor() {
  const rows = (state.sceneBuilder.dialogue || []).map((dialogue, index) => `
    <div class="scene-builder-dialogue-entry">
      <div class="review-header">
        <h4>Dialogue ${index + 1}</h4>
        <button type="button" data-builder-action="delete-dialogue" data-builder-dialogue-index="${index}">Delete</button>
      </div>
      <div class="scene-builder-fields">
        <label>${builderCaption("(Speaker) ... says exactly: [text]", "dialogue[].speaker_element_id")}<select data-builder-dialogue="${index}" data-builder-dialogue-field="speaker_element_id">${builderElementOptions(dialogue.speaker_element_id || "")}</select></label>
        <label>${builderCaption("(Target) Dialogue is directed toward ...", "dialogue[].target_element_id")}<select data-builder-dialogue="${index}" data-builder-dialogue-field="target_element_id">${builderElementOptions(dialogue.target_element_id || "")}</select></label>
        <label class="full">${builderCaption("(Text) Speaker says exactly: \"...\"", "dialogue[].text")}<textarea data-builder-dialogue="${index}" data-builder-dialogue-field="text">${escapeHtml(dialogue.text || "")}</textarea></label>
        <label>${builderCaption("(Pointer target) Aim dialogue-panel pointer at ...", "dialogue[].pointer_target")}<input value="${escapeHtml(dialogue.pointer_target || "")}" data-builder-dialogue="${index}" data-builder-dialogue-field="pointer_target"></label>
        <label>${builderCaption("(Max lines) Wrap dialogue in no more than ... lines.", "dialogue[].max_lines")}<input type="number" min="1" value="${escapeHtml(dialogue.max_lines || 3)}" data-builder-dialogue="${index}" data-builder-dialogue-field="max_lines"></label>
        <label class="full">${builderCaption("Special Instructions", "dialogue[].notes")}<textarea data-builder-dialogue="${index}" data-builder-dialogue-field="notes">${escapeHtml(dialogue.notes || "")}</textarea></label>
      </div>
    </div>
  `).join("");
  return `
    <div class="scene-builder-card">
      <div class="review-header">
        <h4>Dialogue</h4>
        <button type="button" data-builder-action="add-dialogue">Add Dialogue</button>
      </div>
      ${rows || "<p>No dialogue entries.</p>"}
    </div>
  `;
}

function builderRenderEnvironment() {
  return `
    <div class="scene-builder-card">
      <h4>Environment</h4>
      <div class="scene-builder-fields">
        ${builderField("setup.environment.location", "(Location) The scene takes place...", "", true)}
        ${builderField("setup.environment.lighting", "(Lighting) Lighting: ...")}
        ${builderField("setup.environment.mood", "(Mood) Mood: ...")}
        ${builderField("setup.environment.weather_or_atmosphere", "(Weather/Atmosphere) Atmosphere: ...", "", true)}
        ${builderField("setup.environment.general_foreground_notes", "(General foreground notes) Rendered as a bullet: ...", "", true, "textarea")}
        ${builderField("setup.environment.general_background_notes", "(General background notes) Rendered as a bullet: ...", "", true, "textarea")}
      </div>
    </div>
  `;
}

function builderRenderComposition() {
  const composition = state.sceneBuilder.setup?.composition || { focal_point: "", left_to_right: [], composition_notes: "" };
  state.sceneBuilder.setup.composition = composition;
  const suppressedIds = new Set((state.sceneBuilder.placements || []).filter((placement) => placement.position_within_cell === "None").map((placement) => placement.scene_element_id));
  composition.left_to_right = (composition.left_to_right || []).filter((elementId) => !suppressedIds.has(elementId));
  const selectable = (state.sceneBuilder.scene_elements || []).filter((element) => element.element_type !== "Backdrop" && !suppressedIds.has(element.id) && !composition.left_to_right.includes(element.id));
  const ordered = composition.left_to_right.map((elementId, index) => `<li>${escapeHtml(builderElementLabel(elementId))}<span class="button-row compact"><button type="button" data-builder-action="composition-up" data-builder-composition-index="${index}">Up</button><button type="button" data-builder-action="composition-down" data-builder-composition-index="${index}">Down</button><button type="button" data-builder-action="composition-remove" data-builder-composition-index="${index}">Remove</button></span></li>`).join("");
  return `
    <div class="scene-builder-card">
      <h4>Composition</h4>
      <div class="scene-builder-fields">
        ${builderField("setup.composition.focal_point", "(Primary focal point) Primary focal point: ...", "", true)}
        <label class="full">${builderCaption("Left-to-Right Visual Read", "setup.composition.left_to_right")}<span class="inline-field"><select id="builder-composition-element"><option value=""></option>${selectable.map((element) => `<option value="${escapeHtml(element.id)}">${escapeHtml(element.display_name || element.id)}</option>`).join("")}</select><button type="button" data-builder-action="composition-add">Add</button></span></label>
        <ol class="full">${ordered || "<li>No elements selected.</li>"}</ol>
        ${builderField("setup.composition.composition_notes", "(Composition notes) Rendered as a bullet: ...", "", true, "textarea")}
      </div>
    </div>
  `;
}

function builderRenderInteractions() {
  const interactions = (state.sceneBuilder.interactions || []).map((interaction, index) => `
    <tr>
      <td><select data-builder-interaction="${index}" data-builder-interaction-field="subject_element_id">${builderElementOptions(interaction.subject_element_id || "")}</select></td>
      <td><select data-builder-interaction="${index}" data-builder-interaction-field="relationship">${builderOptionHtml("relationship", interaction.relationship || "")}</select></td>
      <td><select data-builder-interaction="${index}" data-builder-interaction-field="target_element_id">${builderElementOptions(interaction.target_element_id || "")}</select></td>
      <td><input value="${escapeHtml(interaction.note || "")}" data-builder-interaction="${index}" data-builder-interaction-field="note"></td>
      <td><button type="button" class="danger-action scene-builder-delete-interaction" data-builder-action="delete-interaction" data-builder-interaction-index="${index}" aria-label="Delete interaction" title="Delete interaction">×</button></td>
    </tr>
  `).join("");
  return `
    <div class="scene-builder-card">
      <h4>Interactions</h4>
      <button type="button" data-builder-action="add-interaction">Add Interaction</button>
      <table class="scene-builder-table"><thead><tr><th>${builderCaption("subject", "interactions[].subject_element_id")}</th><th>${builderCaption("relationship", "interactions[].action")}</th><th>${builderCaption("target", "interactions[].target_element_id")}</th><th>${builderCaption("note", "interactions[].notes")}</th><th></th></tr></thead><tbody>${interactions}</tbody></table>
      <label class="full">${builderCaption("(Custom Interactions) Each line renders as: - ...", "custom_interactions")}<textarea data-builder-field="custom_interactions">${escapeHtml(state.sceneBuilder.custom_interactions || "")}</textarea></label>
    </div>
  `;
}

function builderRenderOutputs() {
  return `
    <div class="scene-builder-card">
      <h4>Render Settings / Validation</h4>
      ${builderField("render_settings.final_image_prompt.output_path", "Final prompt path", "", true)}
      ${builderField("render_settings.scene_render_ir.output_path", "Scene IR path", "", true)}
      ${builderField("render_settings.local_render_brief.output_path", "Local brief path", "", true)}
      ${builderField("render_settings.local_render_prompt.output_path", "Local prompt path", "", true)}
      <label class="full">JSON Preview<textarea class="scene-builder-output" readonly>${escapeHtml(JSON.stringify(state.sceneBuilder, null, 2))}</textarea></label>
    </div>
  `;
}

function builderRenderOverrides() {
  return `
    <div class="scene-builder-card">
      <h4>Overrides</h4>
      <div class="scene-builder-fields">
        ${builderField("final_image_prompt_overrides.anatomical_requirements", "Anatomical Requirements override", "", true, "textarea")}
        ${builderField("final_image_prompt_overrides.avoid", "Avoid override", "", true, "textarea")}
        ${builderField("final_image_prompt_overrides.high_risk_elements", "High-Risk Elements override", "", true, "textarea")}
        ${builderField("final_image_prompt_overrides.final_verification", "Final Verification override", "", true, "textarea")}
      </div>
    </div>
  `;
}

function builderRenderDatalists() {
  return `
    <datalist id="builder-pose-list">${builderOptions("pose").map((value) => `<option value="${escapeHtml(value)}"></option>`).join("")}</datalist>
    <datalist id="builder-gaze-list">${builderOptions("gaze").map((value) => `<option value="${escapeHtml(value)}"></option>`).join("")}</datalist>
    <datalist id="builder-expression-list">${builderOptions("expression").map((value) => `<option value="${escapeHtml(value)}"></option>`).join("")}</datalist>
  `;
}

function renderSceneBuilder() {
  if (!state.sceneBuilder) {
    return;
  }
  builderHelpSequence = 0;
  const warnings = state.sceneBuilder._validation_warnings || [];
  const warningMarkup = warnings.length
    ? `<div class="scene-builder-warnings"><strong>Validation warnings</strong><ul>${warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul></div>`
    : "";
  state.sceneBuilderRendering = true;
  sceneBuilderPanel.innerHTML = `
    ${builderRenderDatalists()}
    <div class="scene-builder-toolbar">
      <strong>Scene Builder</strong>
      <span>${escapeHtml(state.sceneBuilder?.scene?.name || "")}</span>
      <span>${escapeHtml(state.sceneBuilder?.scene?.slug || "")}.scene.json</span>
      <button type="button" class="scene-builder-continue" data-builder-action="continue-from">Continue from...</button>
      <button type="button" class="primary-action" data-builder-action="save">Save JSON</button>
      <button type="button" class="scene-builder-render" data-builder-action="render">Render</button>
      ${state.scenePromptAnalysis?.complete ? '<button type="button" class="scene-builder-analysis-view complete" data-builder-action="view-analysis" aria-label="View prompt analysis" title="View prompt analysis">&#128065;</button>' : ""}
      ${warningMarkup}
    </div>
    <div class="scene-builder-grid">
      <section class="scene-builder-section">
        <h3>Setup</h3>
        <div class="scene-builder-fields">
          ${builderField("scene.name", "Scene name", "", true)}
          ${builderField("scene.story_settings_path", "Story settings path", "", true)}
          ${builderField("scene.associated_png_path", "Associated .png path", "", true)}
          ${builderField("scene.story_beat", "(Story Beat) Rendered as a bullet: ...", "", true, "textarea")}
          ${builderField("scene.author_notes", "Notes", "", true, "textarea")}
        </div>
        <h3>Canvas</h3>
        <div class="scene-builder-fields">
          ${builderField("setup.canvas.orientation", "Orientation", "orientation")}
          ${builderField("setup.canvas.aspect_ratio", "Aspect ratio", "aspect_ratio")}
        </div>
        ${builderRenderComposition()}
        <h3>Environment</h3>
        ${builderRenderEnvironment()}
      </section>
      <section class="scene-builder-section">
        ${builderRenderPlacementEditor()}
        ${builderRenderDialogueEditor()}
        ${builderRenderInteractions()}
      </section>
      <section class="scene-builder-section">
        ${builderRenderElements()}
        ${builderRenderElementEditor()}
        ${builderRenderOverrides()}
        ${builderRenderOutputs()}
      </section>
    </div>
  `;
  state.sceneBuilderRendering = false;
}

async function openSceneBuilder() {
  if (!state.selectedStorySlug || !state.selectedSceneSlug) {
    showSceneBuilderMessage("Select a scene first.", "error");
    return;
  }
  sceneBuilderOpen.disabled = true;
  sceneBuilderStatus.textContent = `${state.selectedStorySlug} / ${state.selectedSceneSlug}`;
  updateSceneBuilderNavigation();
  showSceneBuilderMessage("Loading Scene Builder...");
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/builder`);
    const document = payload.document || {};
    if (document.blocked) {
      showSceneBuilderMessage(document.error || "Scene Builder JSON is blocked.", "error");
      return;
    }
    state.sceneBuilder = document.data || {};
    state.sceneBuilderOptions = payload.options || {};
    state.sceneBuilderReferences = payload.references || [];
    state.scenePromptAnalysis = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/prompt-analysis`);
    state.selectedBuilderPlacementId = state.sceneBuilder.placements?.[0]?.id || null;
    state.selectedBuilderElementId = state.sceneBuilder.placements?.[0]?.scene_element_id || state.sceneBuilder.scene_elements?.[0]?.id || null;
    state.sceneBuilderOpen = true;
    await builderLoadSelectedElementCostumes();
    renderSceneBuilder();
    updateSceneBuilderNavigation();
    state.savedBaselines.sceneBuilder = sceneBuilderSnapshot();
    showSceneBuilderMessage(state.sceneBuilder._migrated_from_schema_version ? "This scene used an older Scene Builder schema and has been migrated to v2. Save to update the JSON file." : "Scene Builder loaded.", "success");
  } catch (error) {
    showSceneBuilderMessage(error.message, "error");
  } finally {
    sceneBuilderOpen.disabled = !state.sceneDetail;
  }
}

async function activateSceneBuilderPage() {
  if (!state.selectedStorySlug || !state.selectedSceneSlug) {
    showSceneMessage("Select a scene first.", "error");
    return;
  }
  await activatePage("scene-builder");
}

async function saveSceneBuilder(autosave = false) {
  if (!state.sceneBuilder || !state.selectedStorySlug || !state.selectedSceneSlug) {
    return;
  }
  builderSyncControls();
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/builder`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.sceneBuilder),
    });
    state.sceneBuilder = payload.document?.data || state.sceneBuilder;
    state.sceneBuilder._validation_warnings = payload.document?.validation_warnings || state.sceneBuilder._validation_warnings || [];
    updateStoryGitWarning(payload.has_story_changes);
    renderSceneBuilder();
    state.savedBaselines.sceneBuilder = sceneBuilderSnapshot();
    if (!autosave) {
      showSceneBuilderMessage(payload.message || "Scene Builder saved.", "success");
    }
    return payload;
  } catch (error) {
    showSceneBuilderMessage(error.message, "error");
    return null;
  }
}

async function openBuilderContinueDialog() {
  if (!state.selectedStorySlug || !state.selectedSceneSlug) {
    return;
  }
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes`);
    const scenes = (payload.scenes || []).filter((scene) => scene.slug !== state.selectedSceneSlug);
    builderContinueScene.replaceChildren(...scenes.map((scene) => {
      const option = document.createElement("option");
      option.value = scene.slug;
      option.textContent = scene.title;
      return option;
    }));
    if (!scenes.length) {
      showSceneBuilderMessage("No other scenes are available to continue from.", "error");
      return;
    }
    builderContinueModal.showModal();
    builderContinueScene.focus();
  } catch (error) {
    showSceneBuilderMessage(error.message, "error");
  }
}

function closeBuilderContinueDialog() {
  builderContinueModal.close();
}

async function continueSceneBuilderFrom() {
  const sourceSceneSlug = builderContinueScene.value;
  if (!sourceSceneSlug) {
    return;
  }
  const saved = await saveSceneBuilder(true);
  if (!saved) {
    return;
  }
  try {
    const params = new URLSearchParams({ source_scene_slug: sourceSceneSlug });
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/builder/continue-from?${params.toString()}`, {
      method: "POST",
    });
    updateStoryGitWarning(payload.has_story_changes);
    closeBuilderContinueDialog();
    await openSceneBuilder();
    showSceneBuilderMessage(payload.message || "Continued from selected scene.", "success");
  } catch (error) {
    showSceneBuilderMessage(error.message, "error");
  }
}

async function renderSceneBuilderScene() {
  if (!state.sceneBuilder || !state.selectedStorySlug || !state.selectedSceneSlug) {
    return;
  }
  const saved = await saveSceneBuilder(true);
  if (!saved) {
    return;
  }
  showSceneBuilderMessage("Staging scene render...", "info");
  try {
    const payload = await fetchJson(
      `/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/stage-render`,
      { method: "POST" },
    );
    const askId = payload.task?.ask_id || null;
    await activatePage("render-console", { skipAutosave: true });
    await loadRenderConsoleTasks(askId);
  } catch (error) {
    showSceneBuilderMessage(error.message, "error");
  }
}

async function analyzeScenePrompt() {
  const saved = await saveSceneBuilder(true);
  if (!saved) return;
  try {
    state.scenePromptAnalysis = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/prompt-analysis`, { method: "POST" });
    renderSceneBuilder();
    showSceneBuilderMessage(state.scenePromptAnalysis.message || "AI prompt analysis queued.", "success");
  } catch (error) {
    showSceneBuilderMessage(error.message, "error");
  }
}

async function viewScenePromptAnalysis() {
  if (state.scenePromptAnalysis?.complete && state.scenePromptAnalysis.result_path) {
    openPromptAnalysisDialog(state.selectedStorySlug, state.selectedSceneSlug);
    return;
  }
  if (!state.scenePromptAnalysis?.pending) {
    showSceneBuilderMessage("No AI prompt analysis has been requested.", "info");
    return;
  }
  try {
    state.scenePromptAnalysis = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/prompt-analysis/harvest`, { method: "POST" });
    renderSceneBuilder();
    showSceneBuilderMessage(state.scenePromptAnalysis.message || "AI answers harvested.", "success");
  } catch (error) {
    showSceneBuilderMessage(error.message, "error");
  }
}

async function generateSceneBuilder() {
  if (!state.sceneBuilder) {
    return;
  }
  builderSyncControls();
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/builder/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.sceneBuilder),
    });
    state.sceneBuilder = payload.data || state.sceneBuilder;
    renderSceneBuilder();
  } catch (error) {
    showSceneBuilderMessage(error.message, "error");
  }
}

async function exportSceneBuilderMarkdown() {
  if (!state.sceneBuilder) {
    return;
  }
  builderSyncControls();
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/builder/export-markdown`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.sceneBuilder),
    });
    state.sceneDetail = payload.document || state.sceneDetail;
    state.sceneBuilder = payload.builder?.data || state.sceneBuilder;
    sceneText.value = state.sceneDetail?.text || sceneText.value;
    updateStoryGitWarning(payload.has_story_changes);
    renderValidationBox(sceneValidation, state.sceneDetail?.validation_errors || [], "Scene markdown is valid.");
    renderSceneBuilder();
    showSceneBuilderMessage(payload.message || "Scene Builder markdown exported.", "success");
  } catch (error) {
    showSceneBuilderMessage(error.message, "error");
  }
}

sceneBuilderPanel.addEventListener("input", () => {
  if (!state.sceneBuilder || state.sceneBuilderRendering) {
    return;
  }
  builderSyncControls();
  updateDirtyIndicators();
});
sceneBuilderPanel.addEventListener("change", builderApplyChange);
sceneBuilderPanel.addEventListener("click", (event) => {
  const referenceImage = event.target.closest(".scene-builder-reference-thumbnail");
  if (referenceImage) {
    event.preventDefault();
    event.stopPropagation();
    openFullscreenImage(referenceImage.src, referenceImage.alt || "Reference image");
    return;
  }
  const helpTarget = event.target.closest("[data-builder-help]");
  if (helpTarget) {
    event.preventDefault();
    event.stopPropagation();
    const helpText = document.getElementById(helpTarget.getAttribute("aria-controls"));
    const willOpen = Boolean(helpText?.hidden);
    if (helpText) helpText.hidden = !willOpen;
    helpTarget.setAttribute("aria-expanded", willOpen ? "true" : "false");
    return;
  }
  const target = event.target.closest("[data-builder-action], [data-builder-select-element]");
  if (!target) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  if (target.dataset.builderSelectElement) {
    state.selectedBuilderElementId = target.dataset.builderSelectElement;
    state.selectedBuilderPlacementId = builderPlacementForElement(state.selectedBuilderElementId)?.id || state.selectedBuilderPlacementId;
    renderSceneBuilder();
    builderLoadSelectedElementCostumes().then(() => renderSceneBuilder()).catch((error) => showSceneBuilderMessage(error.message, "error"));
  } else {
    const action = target.dataset.builderAction;
    if (action === "continue-from") openBuilderContinueDialog();
    if (action === "add-element") openBuilderElementDialog();
    if (action === "duplicate-element") builderDuplicateSelectedElement();
    if (action === "delete-element") builderRemoveSelectedElement();
    if (action === "pick-image-tag") openBuilderImagePicker();
    if (action === "add-interaction") builderAddInteraction();
    if (action === "delete-interaction") builderDeleteInteraction(Number(target.dataset.builderInteractionIndex));
    if (action === "add-dialogue") builderAddDialogue();
    if (action === "delete-dialogue") builderDeleteDialogue(Number(target.dataset.builderDialogueIndex));
    if (action.startsWith("composition-")) {
      builderSyncControls();
      const composition = state.sceneBuilder.setup.composition;
      const index = Number(target.dataset.builderCompositionIndex);
      if (action === "composition-add") {
        const elementId = sceneBuilderPanel.querySelector("#builder-composition-element")?.value;
        if (elementId && !composition.left_to_right.includes(elementId)) composition.left_to_right.push(elementId);
      }
      if (action === "composition-remove") composition.left_to_right.splice(index, 1);
      if (action === "composition-up" && index > 0) [composition.left_to_right[index - 1], composition.left_to_right[index]] = [composition.left_to_right[index], composition.left_to_right[index - 1]];
      if (action === "composition-down" && index < composition.left_to_right.length - 1) [composition.left_to_right[index + 1], composition.left_to_right[index]] = [composition.left_to_right[index], composition.left_to_right[index + 1]];
      renderSceneBuilder();
    }
    if (action === "save") saveSceneBuilder(false);
    if (action === "export") exportSceneBuilderMarkdown();
    if (action === "render") renderSceneBuilderScene();
    if (action === "view-analysis") viewScenePromptAnalysis();
  }
});

builderContinueCancel.addEventListener("click", closeBuilderContinueDialog);
builderContinueConfirm.addEventListener("click", continueSceneBuilderFrom);

async function loadImagePickerReferences(picker) {
  picker.status.textContent = "Loading references...";
  const params = new URLSearchParams();
  if (picker.character.value) {
    params.set("character", picker.character.value);
  }
  if (picker.search.value.trim()) {
    params.set("text_filter", picker.search.value.trim());
  }
  try {
    const payload = await fetchJson(`/api/scene-image-picker?${params.toString()}`);
    picker.setRows(payload.rows || []);
    renderImagePickerTable(picker);
    picker.status.textContent = `${picker.rows().length} reference(s)`;
  } catch (error) {
    picker.status.textContent = "Load failed.";
    picker.onError(error);
  }
}

function renderImagePickerTable(picker) {
  picker.tableBody.replaceChildren();
  const rows = picker.rows();
  if (!rows.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = picker.labelOnly ? 1 : 3;
    cell.textContent = "No references found.";
    row.append(cell);
    picker.tableBody.append(row);
    return;
  }
  for (const item of rows) {
    const row = document.createElement("tr");
    const labelCell = document.createElement("td");
    labelCell.textContent = item.label || "";
    if (picker.labelOnly) {
      row.append(labelCell);
    } else {
      const tagCell = document.createElement("td");
      tagCell.textContent = item.tag || "";
      const sourceCell = document.createElement("td");
      sourceCell.textContent = [item.character, item.phase, item.pipeline].filter(Boolean).join(" | ") || item.kind || "";
      row.append(tagCell, labelCell, sourceCell);
    }
    makeSelectableRow(row, item.label || item.tag || "reference", false, () => picker.onSelect(item));
    picker.tableBody.append(row);
  }
}

const sceneImagePicker = {
  character: scenePickerCharacter,
  search: scenePickerSearch,
  status: scenePickerStatus,
  tableBody: scenePickerTableBody,
  rows: () => state.sceneImageReferences,
  setRows: (rows) => { state.sceneImageReferences = rows; },
  onSelect: async (item) => {
    await copyText(item.tag || "", `Copied ${item.tag || "tag"}.`);
    showSceneMessage(`Copied ${item.tag || "tag"}.`, "success");
  },
  onError: (error) => showSceneMessage(error.message, "error"),
};

const builderImagePicker = {
  labelOnly: true,
  character: builderImagePickerCharacter,
  search: builderImagePickerSearch,
  status: builderImagePickerStatus,
  tableBody: builderImagePickerTableBody,
  rows: () => state.builderImagePickerReferences,
  setRows: (rows) => { state.builderImagePickerReferences = rows; },
  onSelect: async (item) => {
    const element = builderSelectedElement();
    if (!element) {
      return;
    }
    await copyText(item.tag || "", `Copied ${item.tag || "tag"}.`);
    element.reference_images = element.reference_images || [];
    element.reference_images[0] = element.reference_images[0] || { roles: ["visual reference"], ignore: ["source pose", "source background", "source framing"], notes: "" };
    element.reference_images[0].tag = item.tag || "";
    builderImagePickerModal.close();
    renderSceneBuilder();
    showSceneBuilderMessage(`Selected ${item.tag || "image tag"}.`, "success");
  },
  onError: (error) => showSceneBuilderMessage(error.message, "error"),
};

async function loadSceneImageReferences() {
  await loadImagePickerReferences(sceneImagePicker);
}

function openBuilderImagePicker() {
  builderSyncControls();
  const element = builderSelectedElement();
  if (!element) {
    return;
  }
  builderImagePickerSearch.value = element.resource_type === "Character"
    ? [element.character || element.display_name, element.phase, element.costume].filter(Boolean).join(" ")
    : element.display_name || "";
  state.builderImagePickerSearch = builderImagePickerSearch.value;
  builderImagePickerModal.showModal();
  builderImagePickerSearch.focus();
  loadImagePickerReferences(builderImagePicker);
}

function updateAuxiliaryResourceCategoryDisplay() {
  // Keep the editor header matched to the currently filtered resource category.
  const selected = auxResourceCategory.options[auxResourceCategory.selectedIndex];
  auxResourceFormCategory.textContent = selected?.textContent || "Person";
}

function clearAuxiliaryResourceForm() {
  state.selectedAuxiliaryResourceId = null;
  state.selectedAuxiliaryImageId = null;
  state.auxiliaryResourceImageBlob = null;
  updateAuxiliaryResourceCategoryDisplay();
  auxResourceFormTitle.textContent = "Add Resource";
  auxResourceLabel.value = "";
  auxResourceEditTemplate.disabled = true;
  auxResourceImageLabel.value = "";
  auxResourceTag.textContent = "";
  auxResourceCopyTag.disabled = true;
  auxResourceImagePreview.hidden = true;
  auxResourceImagePreview.removeAttribute("src");
  auxResourceSave.textContent = "Save Resource";
  auxResourceSaveImage.textContent = "Save Image";
  auxResourceSaveImage.disabled = true;
  auxResourceFileInput.value = "";
  renderAuxiliaryResourceImages(null);
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
  auxResourceSaveImage.disabled = !state.selectedAuxiliaryResourceId;
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
    const labelCell = document.createElement("td");
    labelCell.textContent = resource.label || "";
    const folderCell = document.createElement("td");
    folderCell.textContent = resource.resource_id || "";
    row.append(labelCell, folderCell);
    makeSelectableRow(row, resource.label || resource.resource_id, resource.resource_id === state.selectedAuxiliaryResourceId, () => selectAuxiliaryResource(resource.resource_id));
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
  state.selectedAuxiliaryImageId = null;
  state.auxiliaryResourceImageBlob = null;
  updateAuxiliaryResourceCategoryDisplay();
  auxResourceFormTitle.textContent = "Update Resource";
  auxResourceLabel.value = resource.label || "";
  auxResourceEditTemplate.disabled = !resource.template_path;
  auxResourceSave.textContent = "Update Resource";
  auxResourceImageLabel.value = "";
  auxResourceTag.textContent = "";
  auxResourceCopyTag.disabled = true;
  auxResourceImagePreview.hidden = true;
  auxResourceImagePreview.removeAttribute("src");
  auxResourceSaveImage.textContent = "Save Image";
  auxResourceSaveImage.disabled = false;
  auxResourceFileInput.value = "";
  renderAuxiliaryResourceImages(resource);
  renderAuxiliaryResourceTable();
}

function renderAuxiliaryResourceImages(resource) {
  auxResourceImageList.replaceChildren();
  const images = resource?.images || [];
  if (!images.length) {
    auxResourceImageList.textContent = "No images.";
    return;
  }
  for (const imageRecord of images) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "aux-resource-image-row";
    button.classList.toggle("selected", imageRecord.image_id === state.selectedAuxiliaryImageId);
    const thumb = document.createElement("img");
    thumb.className = "aux-resource-thumb";
    thumb.alt = imageRecord.label || imageRecord.image_id || "";
    thumb.src = fileUrl(imageRecord.image_path, imageRecord.updated_at || "");
    const label = document.createElement("span");
    label.className = "aux-resource-image-label";
    label.textContent = imageRecord.label || imageRecord.image_id || "";
    const copy = document.createElement("span");
    copy.textContent = "Select";
    button.append(thumb, label, copy);
    button.addEventListener("click", () => selectAuxiliaryResourceImage(imageRecord.image_id));
    auxResourceImageList.append(button);
  }
}

async function openAuxiliaryResourceTemplate() {
  const resource = selectedAuxiliaryResource();
  if (!resource?.template_path) {
    return;
  }
  await openSourceEditorForSource(
    {
      source_kind: "auxiliary_resource_template",
      source_label: resource.label || resource.resource_id || "Aux Resource Template",
      source_path: resource.template_path,
    },
    showAuxResourceMessage,
  );
}

function selectedAuxiliaryResource() {
  return state.auxiliaryResources.find((item) => item.resource_id === state.selectedAuxiliaryResourceId) || null;
}

function selectedAuxiliaryImage() {
  const resource = selectedAuxiliaryResource();
  return (resource?.images || []).find((item) => item.image_id === state.selectedAuxiliaryImageId) || null;
}

function selectAuxiliaryResourceImage(imageId) {
  const resource = selectedAuxiliaryResource();
  const imageRecord = (resource?.images || []).find((item) => item.image_id === imageId);
  if (!resource || !imageRecord) {
    return;
  }
  state.selectedAuxiliaryImageId = imageRecord.image_id;
  state.auxiliaryResourceImageBlob = null;
  auxResourceImageLabel.value = imageRecord.label || "";
  auxResourceTag.textContent = imageRecord.tag || "";
  auxResourceCopyTag.disabled = !imageRecord.tag;
  auxResourceSaveImage.textContent = "Update Image";
  auxResourceSaveImage.disabled = false;
  auxResourceImagePreview.src = fileUrl(imageRecord.image_path, imageRecord.updated_at || "");
  auxResourceImagePreview.hidden = !imageRecord.image_path;
  auxResourceFileInput.value = "";
  renderAuxiliaryResourceImages(resource);
}

function newAuxiliaryResourceImage() {
  state.selectedAuxiliaryImageId = null;
  state.auxiliaryResourceImageBlob = null;
  auxResourceImageLabel.value = "";
  auxResourceTag.textContent = "";
  auxResourceCopyTag.disabled = true;
  auxResourceSaveImage.textContent = "Save Image";
  auxResourceSaveImage.disabled = !state.selectedAuxiliaryResourceId;
  auxResourceImagePreview.hidden = true;
  auxResourceImagePreview.removeAttribute("src");
  auxResourceFileInput.value = "";
  renderAuxiliaryResourceImages(selectedAuxiliaryResource());
}

async function saveAuxiliaryResource() {
  const label = auxResourceLabel.value.trim();
  if (!label) {
    showAuxResourceMessage("Label is required.", "error");
    return;
  }
  const isUpdate = Boolean(state.selectedAuxiliaryResourceId);
  const params = new URLSearchParams({
    category: auxResourceCategory.value || "person",
    label,
  });
  auxResourceSave.disabled = true;
  showAuxResourceMessage(isUpdate ? "Updating resource..." : "Creating resource...");
  try {
    const url = isUpdate
      ? `/api/auxiliary-resources/${encodeURIComponent(state.selectedAuxiliaryResourceId)}?${params.toString()}`
      : `/api/auxiliary-resources?${params.toString()}`;
    const payload = await fetchJson(url, {
      method: isUpdate ? "PUT" : "POST",
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
  if (!state.phaseComparison.pipeline) {
    state.phaseComparison.pipeline = "Character-Assembly";
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
    pipeline: phaseComparisonPipeline.value || state.phaseComparison.pipeline || "Character-Assembly",
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
    : ((payload.available_pipelines || []).includes(currentPipeline) ? currentPipeline : (((payload.available_pipelines || []).includes("Character-Assembly") ? "Character-Assembly" : "")));
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

async function loadPromptReviewTasks(preferredAskId = null) {
  promptReviewStatus.textContent = "Loading prompt reviews...";
  const payload = await fetchJson(`/api/render-console/tasks?${currentQuery().toString()}`);
  state.promptReviewTasks = payload.tasks || [];
  const taskIds = new Set(state.promptReviewTasks.map((task) => task.ask_id));
  state.selectedPromptReviewAskId =
    preferredAskId || state.selectedPromptReviewAskId || state.promptReviewTasks[0]?.ask_id || null;
  if (state.selectedPromptReviewAskId && !taskIds.has(state.selectedPromptReviewAskId)) {
    state.selectedPromptReviewAskId = state.promptReviewTasks[0]?.ask_id || null;
  }
  renderPromptReviewTaskTable();
  promptReviewStatus.textContent = `${state.promptReviewTasks.length} render prompt(s)`;
  if (state.selectedPromptReviewAskId) {
    await selectPromptReviewTask(state.selectedPromptReviewAskId);
  } else {
    clearPromptReview();
  }
}

function renderPromptReviewTaskTable() {
  renderAssetTaskTable(
    promptReviewTaskBody,
    state.promptReviewTasks,
    state.selectedPromptReviewAskId,
    selectPromptReviewTask,
    "No render prompts are waiting. Stage a render to create work.",
  );
}

async function selectPromptReviewTask(askId) {
  state.selectedPromptReviewAskId = askId;
  updateSelectableRows(promptReviewTaskBody, (row) => row.dataset.askId === state.selectedPromptReviewAskId);
  const detail = await fetchJson(`/api/render-console/tasks/${encodeURIComponent(askId)}?${currentQuery().toString()}`);
  renderPromptReview(detail);
}

function clearPromptReview() {
  state.promptReviewDetail = null;
  promptReviewTitle.textContent = "Select a prompt";
  promptPath.textContent = "";
  promptText.textContent = "";
  clearSourceInspector();
  promptReviewPrev.disabled = true;
  promptReviewNext.disabled = true;
  copyPromptButton.disabled = true;
  promptReviewSceneBuilder.hidden = true;
  promptReviewSceneBuilder.disabled = true;
  analyzePromptButton.disabled = true;
  viewPromptAnalysisButton.disabled = true;
}

function renderPromptReview(detail) {
  state.promptReviewDetail = detail;
  const task = detail.task;
  const storyLabel = detail.manifest?.story_slug && detail.manifest?.scene_slug
    ? `Story ${detail.manifest.story_slug} / ${detail.manifest.scene_slug}`
    : "";
  promptReviewTitle.textContent = storyLabel || `Asset ${task.asset_id ?? "unknown"} | ${task.expected_output || task.ask_id}`;
  promptPath.textContent = detail.prompt_path || "No prompt file found.";
  renderPromptText();
  copyPromptButton.disabled = !detail.prompt;
  promptReviewSceneBuilder.hidden = !storyLabel;
  promptReviewSceneBuilder.disabled = !storyLabel;
  analyzePromptButton.disabled = !storyLabel;
  viewPromptAnalysisButton.disabled = !storyLabel || !(detail.prompt_analysis?.pending || detail.prompt_analysis?.complete);
  viewPromptAnalysisButton.classList.toggle("complete", Boolean(detail.prompt_analysis?.complete));
  clearSourceInspector();
  updatePromptReviewNavigation();
}

function selectedPromptReviewScene() {
  const manifest = state.promptReviewDetail?.manifest || {};
  return manifest.story_slug && manifest.scene_slug
    ? { storySlug: manifest.story_slug, sceneSlug: manifest.scene_slug }
    : null;
}

async function analyzePromptReview() {
  const scene = selectedPromptReviewScene();
  if (!scene) return;
  analyzePromptButton.disabled = true;
  showPromptMessage("Queuing prompt analysis...");
  try {
    const analysis = await fetchJson(`/api/stories/${encodeURIComponent(scene.storySlug)}/scenes/${encodeURIComponent(scene.sceneSlug)}/prompt-analysis`, { method: "POST" });
    state.promptReviewDetail.prompt_analysis = analysis;
    renderPromptReview(state.promptReviewDetail);
    showPromptMessage(analysis.message || "AI prompt analysis queued.", "success");
  } catch (error) {
    showPromptMessage(error.message, "error");
  } finally {
    analyzePromptButton.disabled = false;
  }
}

async function viewPromptReviewAnalysis() {
  const scene = selectedPromptReviewScene();
  if (!scene) return;
  let analysis = state.promptReviewDetail?.prompt_analysis || {};
  if (analysis.complete && analysis.result_path) {
    openPromptAnalysisDialog(scene.storySlug, scene.sceneSlug);
    return;
  }
  try {
    analysis = await fetchJson(`/api/stories/${encodeURIComponent(scene.storySlug)}/scenes/${encodeURIComponent(scene.sceneSlug)}/prompt-analysis/harvest`, { method: "POST" });
    state.promptReviewDetail.prompt_analysis = analysis;
    renderPromptReview(state.promptReviewDetail);
    showPromptMessage(analysis.message || "AI answers harvested.", "success");
  } catch (error) {
    showPromptMessage(error.message, "error");
  }
}

function openPromptAnalysisDialog(storySlug, sceneSlug) {
  promptAnalysisFrame.src = `/api/stories/${encodeURIComponent(storySlug)}/scenes/${encodeURIComponent(sceneSlug)}/prompt-analysis/view`;
  promptAnalysisDialog.showModal();
}

function closePromptAnalysisDialog() {
  promptAnalysisDialog.close();
}

function renderPromptText() {
  const detail = state.promptReviewDetail;
  if (!detail) {
    promptText.replaceChildren();
    return;
  }
  const query = promptSearch.value.trim();
  const raw = detail.prompt || "";
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
  const source = fragments.find(
    (fragment) => lineNumber >= Number(fragment.prompt_start_line || 0) && lineNumber <= Number(fragment.prompt_end_line || 0),
  );
  if (source) return source;
  const manifest = state.promptReviewDetail?.manifest || {};
  return manifest.story_slug && manifest.scene_slug
    ? { source_kind: "scene_builder", source_label: "Scene Builder", editable: true, scene_builder: true }
    : null;
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
    auxiliary_template_section: "auxiliary",
    story_settings: "story",
    runtime_generated: "generated",
    scene_builder: "scene",
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
  sourceOpenEditor.disabled = !source || source.editable === false || (!source.source_path && !source.scene_builder);
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
  sourceEditorWarning.textContent = detail.warning || "";
  sourceEditorWarning.hidden = !detail.warning;
  state.savedBaselines.sourceEditor = sourceEditorSnapshot();
  setSaveState(sourceEditorSaveState, "Saved", "saved");
  showSourceEditorMessage("");
}

async function openSelectedSourceEditor() {
  if (!state.selectedSource) {
    return;
  }
  if (state.selectedSource.scene_builder) {
    const manifest = state.promptReviewDetail?.manifest || {};
    state.selectedStorySlug = manifest.story_slug || null;
    state.selectedSceneSlug = manifest.scene_slug || null;
    await activatePage("scene-builder", { skipAutosave: true });
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
    state.savedBaselines.sourceEditor = sourceEditorSnapshot();
    setSaveState(sourceEditorSaveState, "Saved", "saved");
    return true;
  } catch (error) {
    showSourceEditorMessage(error.message, "error");
    setSaveState(sourceEditorSaveState, "Error", "error");
    return false;
  } finally {
    sourceEditorSave.disabled = false;
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

function updatePromptReviewNavigation() {
  updateAssetTaskNavigation(
    state.promptReviewTasks,
    state.selectedPromptReviewAskId,
    promptReviewPrev,
    promptReviewNext,
  );
}

async function writeClipboardText(value) {
  const text = value || "";
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.append(textarea);
  textarea.focus();
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

async function copyText(value, label = "Copied.") {
  await writeClipboardText(value);
  showPromptMessage(label);
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
  if (!state.renderReviewTasks.length) {
    renderEmptyRow(renderReviewTaskBody, 3, "No render candidates are waiting. Complete a render to create review work.");
    return;
  }
  for (const task of state.renderReviewTasks) {
    const row = document.createElement("tr");
    row.dataset.assetId = task.asset_id;
    row.classList.toggle("selected", task.asset_id === state.selectedRenderReviewAssetId);
    for (const value of [task.asset_id, task.body_view, task.candidate_image_exists ? "CAMERA" : ""]) {
      const cell = document.createElement("td");
      cell.textContent = value ?? "";
      row.append(cell);
    }
    makeSelectableRow(row, `Asset ${task.asset_id}`, task.asset_id === state.selectedRenderReviewAssetId, () => selectRenderReviewAsset(task.asset_id));
    renderReviewTaskBody.append(row);
  }
}

async function selectRenderReviewAsset(assetId) {
  state.selectedRenderReviewAssetId = Number(assetId);
  updateSelectableRows(renderReviewTaskBody, (row) => Number(row.dataset.assetId) === state.selectedRenderReviewAssetId);
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

function renderReviewImage(container, path, exists, emptyText, altText, cacheKey = "", allowFullscreen = true) {
  container.replaceChildren();
  if (!exists || !path) {
    container.textContent = emptyText;
    return;
  }
  const image = document.createElement("img");
  image.alt = altText;
  image.src = fileUrl(path, cacheKey || Date.now().toString());
  image.title = path;
  if (allowFullscreen) {
    container.append(enableFullscreenImage(image));
  } else {
    container.append(image);
  }
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
  if (!state.turnaroundRows.length) {
    renderEmptyRow(turnaroundTableBody, 5, "No turnaround tasks exist for this character and phase.");
    return;
  }
  for (const rowData of state.turnaroundRows) {
    const row = document.createElement("tr");
    row.dataset.turnaroundId = rowData.turnaround_id;
    row.classList.toggle("selected", rowData.turnaround_id === state.selectedTurnaroundId);
    const actionCell = document.createElement("td");
    const generateButton = document.createElement("button");
    generateButton.type = "button";
    generateButton.className = "update-action";
    generateButton.textContent = "Generate";
    generateButton.disabled = !rowData.ready;
    generateButton.addEventListener("click", (event) => {
      event.stopPropagation();
      generateTurnaround(rowData.turnaround_id, Number(turnaroundDetectionTolerance.value || rowData.detection_tolerance || 50));
    });
    actionCell.append(generateButton);
    const promoteButton = document.createElement("button");
    promoteButton.type = "button";
    promoteButton.className = "primary-action";
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
    makeSelectableRow(row, rowData.label || rowData.turnaround_id, rowData.turnaround_id === state.selectedTurnaroundId, () => selectTurnaround(rowData.turnaround_id));
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
  promoteButton.className = "primary-action";
  promoteButton.textContent = "Promote";
  promoteButton.disabled = !aux.candidate_image_exists;
  promoteButton.addEventListener("click", (event) => {
    event.stopPropagation();
    promoteTurnaround(aux);
  });
  actionCell.append(promoteButton);

  const deleteButton = document.createElement("button");
  deleteButton.type = "button";
  deleteButton.className = "danger-action";
  deleteButton.textContent = "Delete";
  deleteButton.disabled = !aux.deletable;
  deleteButton.addEventListener("click", (event) => {
    event.stopPropagation();
    deletePartialTurnaround(aux.turnaround_id);
  });
  actionCell.append(deleteButton);

  row.append(labelCell, statusCell, countCell, actionCell, missingCell);
  makeSelectableRow(row, aux.label || aux.turnaround_id, aux.turnaround_id === state.selectedAuxiliaryTurnaroundId, () => selectAuxiliaryTurnaround(parentRow.turnaround_id, aux.turnaround_id));
  return row;
}

async function selectTurnaround(turnaroundId) {
  state.selectedTurnaroundId = turnaroundId;
  state.selectedAuxiliaryTurnaroundId = null;
  turnaroundPartialLabel.value = "";
  turnaroundPartialPercent.value = "45";
  turnaroundDetectionTolerance.value = "50";
  updateSelectableRows(turnaroundTableBody, (row) => row.dataset.turnaroundId === state.selectedTurnaroundId);
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
    cell.textContent = "No auxiliary turnaround sheets.";
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
    deleteButton.className = "danger-action";
    deleteButton.textContent = "Delete";
    deleteButton.disabled = !item.deletable;
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      deletePartialTurnaround(item.turnaround_id);
    });
    actionCell.append(deleteButton);
    row.append(labelCell, percentCell, actionCell);
    makeSelectableRow(row, item.label || item.turnaround_id, item.turnaround_id === state.selectedAuxiliaryTurnaroundId, () => {
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
    renderEmptyRow(tbody, Math.max(1, columns.length), "No items.");
    return;
  }
  for (const item of rows) {
    const row = document.createElement("tr");
    for (const column of columns) {
      const cell = document.createElement("td");
      const value = item[column] ?? "";
      if (/(?:^|_)(?:created|updated|responded)_at$/.test(column) && value !== "") {
        const time = document.createElement("time");
        time.dateTime = String(value);
        time.title = String(value);
        time.textContent = formatLocalTimestamp(value);
        cell.append(time);
      } else {
        cell.textContent = value;
      }
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
  const counts = payload.queue_counts || {};
  queueCounts.textContent =
    `Ask: ${counts.ask || 0} | Running: ${counts.running || 0} | Answer: ${counts.answer || 0}`;
  renderRows(queueAskTableBody, payload.queue?.ask || [], ["ask_id", "asset_id", "pipeline_stage", "worker_type", "task_type"]);
  renderRows(queueRunningTableBody, payload.queue?.running || [], ["ask_id", "asset_id", "worker_type", "task_type"]);
  renderRows(queueAnswerTableBody, payload.queue?.answer || [], ["ask_id", "asset_id", "status", "worker_id"]);
  renderRows(queueFailedTableBody, payload.queue?.failed || [], ["worker_id", "name"]);
  renderRows(manualRenderTableBody, payload.manual_render_asks || [], ["ask_id", "asset_id", "pipeline_stage", "task_type"]);
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
      button.type = "button";
      button.className = action === "stop" ? "danger-action" : "update-action";
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
  const profiles = payload.render_profiles || {};
  const stableProfile = automation.stable_matrix_profile || automation.local_render_preset || "body-reference-preview";
  const comfyProfile = automation.comfyui_profile || "comfyui-core-preview";
  setSelectOptions(settingLocalRenderPreset, profiles.stable_matrix?.length ? profiles.stable_matrix : [stableProfile]);
  setSelectOptions(settingComfyuiProfile, profiles.comfyui?.length ? profiles.comfyui : [comfyProfile]);
  settingLocalRenderBackend.value = automation.local_render_backend || "stable_matrix";
  settingLocalRenderPreset.value = stableProfile;
  settingComfyuiProfile.value = comfyProfile;
  settingLocalRenderForgeCouple.checked = (automation.stable_matrix_use_forge_couple ?? automation.local_render_use_forge_couple) !== false;
  setLocalRenderCheckpointValue(automation.stable_matrix_checkpoint || automation.local_render_checkpoint || "");
  settingLocalRenderPositiveGlobals.value = automation.stable_matrix_positive_prompt_globals || automation.local_render_positive_prompt_globals || "";
  settingLocalRenderNegativeGlobals.value = automation.stable_matrix_negative_prompt_globals || automation.local_render_negative_prompt_globals || "";
  setComfyuiCheckpointValue(automation.comfyui_checkpoint || "");
  settingComfyuiServerUrl.value = automation.comfyui_server_url || "http://127.0.0.1:8188";
  settingComfyuiPositiveGlobals.value = automation.comfyui_positive_prompt_globals || "";
  settingComfyuiNegativeGlobals.value = automation.comfyui_negative_prompt_globals || "";
  settingComfyuiPollSeconds.value = automation.comfyui_poll_seconds ?? 1;
  settingComfyuiTimeoutSeconds.value = automation.comfyui_timeout_seconds ?? 300;
  syncLocalRenderBackendPanels();
  settingZinePrintScale.value = Number(automation.zine_print_scale ?? 0.978).toFixed(4);
  settingZinePageMargin.value = automation.zine_page_margin ?? 4;
  settingZineWidth.value = automation.zine_width ?? 3300;
  updateZineMarginLimit();
  settingTurnaroundWidth.value = automation.turnaround_width ?? 3960;
  settingAiHarvestAuto.checked = Boolean(automation.ai_harvest_auto_enabled);
  settingAiHarvestInterval.value = automation.ai_harvest_interval_seconds ?? 300;
  setOllamaModelValue(automation.ai_prompt_analysis_model || "");
  settingAiPromptAnalysisFile.value = automation.ai_prompt_analysis_instructions_file || "";
  settingRenderBackend.value = automation.render_backend || "manual_chatgpt";
  pipelineConfigPaths.textContent = `Config: ${payload.config_path || ""} | Pipelines: ${payload.pipelines_path || ""}`;
  renderRows(projectConfigTableBody, payload.project_config_rows || [], ["Scope", "Setting", "Value"]);
  renderRows(pipelineStageTableBody, payload.pipeline_rows || [], ["pipeline", "step", "stage", "actor", "worker", "asset_count"]);
  const currentPipeline = batchRenderPipeline.value;
  setSelectOptions(batchRenderPipeline, payload.pipeline_names || []);
  if ((payload.pipeline_names || []).includes(currentPipeline)) {
    batchRenderPipeline.value = currentPipeline;
  }
  state.savedBaselines.settings = settingsSnapshot();
  setSaveState(settingsSaveState, "Saved", "saved");
  pipelineControlsStatus.textContent = "Ready";
}

function setLocalRenderCheckpointValue(value) {
  const checkpoint = value || "";
  if (checkpoint && !Array.from(settingLocalRenderCheckpoint.options).some((option) => option.value === checkpoint)) {
    settingLocalRenderCheckpoint.add(new Option(checkpoint, checkpoint));
  }
  settingLocalRenderCheckpoint.value = checkpoint;
}

function setOllamaModelValue(value) {
  const model = value || "";
  if (model && !Array.from(settingAiPromptAnalysisModel.options).some((option) => option.value === model)) {
    settingAiPromptAnalysisModel.add(new Option(model, model));
  }
  settingAiPromptAnalysisModel.value = model;
}

async function refreshOllamaModelOptions() {
  const current = settingAiPromptAnalysisModel.value || state.pipelineControls?.automation?.ai_prompt_analysis_model || "";
  try {
    const payload = await fetchJson("/api/ai-controls/ollama-models");
    setSelectOptions(settingAiPromptAnalysisModel, payload.models || []);
    setOllamaModelValue(current);
    showAiControlsMessage(
      `Loaded ${(payload.models || []).length} Ollama model(s)${payload.vision_filtered ? " with vision capability" : ""}.`,
    );
  } catch (error) {
    setOllamaModelValue(current);
    showAiControlsMessage(error.message, "error");
  }
}

function updateZineMarginLimit() {
  const width = Math.max(44, Number(settingZineWidth.value || 44));
  const maximum = Math.max(0, Math.floor((Math.floor(width / 4) - 1) / 2));
  settingZinePageMargin.max = String(maximum);
  zineMarginHelp.textContent = `Allowed range: 0–${maximum} pixels for the current width.`;
}

function humanizeHeading(value) {
  const raw = String(value || "");
  return raw
    .replaceAll("_", " ")
    .replace(/\b(ai|id|ids|pid|pids|url)\b/gi, (match) => match.toUpperCase())
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function setComfyuiCheckpointValue(value) {
  const checkpoint = value || "";
  if (checkpoint && !Array.from(settingComfyuiCheckpoint.options).some((option) => option.value === checkpoint)) {
    settingComfyuiCheckpoint.add(new Option(checkpoint, checkpoint));
  }
  settingComfyuiCheckpoint.value = checkpoint;
}

function syncLocalRenderBackendPanels() {
  const useComfyui = settingLocalRenderBackend.value === "comfyui";
  stableMatrixSettings.hidden = useComfyui;
  comfyuiSettings.hidden = !useComfyui;
}

async function refreshLocalRenderCheckpointOptions() {
  const current = settingLocalRenderCheckpoint.value || state.pipelineControls?.automation?.local_render_checkpoint || "";
  showLocalImageConfigMessage("Refreshing checkpoints...");
  try {
    const params = new URLSearchParams({
      preset: settingLocalRenderPreset.value || "body-reference-preview",
      backend: "stable_matrix",
    });
    const payload = await fetchJson(`/api/local-image/checkpoints?${params.toString()}`);
    const items = [{ value: "", label: "" }, ...(payload.checkpoints || []).map((item) => ({ value: item.title, label: item.title }))];
    setSelectOptionsWithLabels(settingLocalRenderCheckpoint, items);
    setLocalRenderCheckpointValue(current);
    showLocalImageConfigMessage(`Loaded ${(payload.checkpoints || []).length} checkpoints.`);
  } catch (error) {
    showLocalImageConfigMessage(error.message, "error");
  }
}

async function refreshComfyuiCheckpointOptions() {
  const current = settingComfyuiCheckpoint.value || state.pipelineControls?.automation?.comfyui_checkpoint || "";
  showLocalImageConfigMessage("Refreshing ComfyUI checkpoints...");
  try {
    const params = new URLSearchParams({
      preset: settingComfyuiProfile.value || "comfyui-core-preview",
      backend: "comfyui",
    });
    const payload = await fetchJson(`/api/local-image/checkpoints?${params.toString()}`);
    const items = [{ value: "", label: "" }, ...(payload.checkpoints || []).map((item) => ({ value: item.title, label: item.title }))];
    setSelectOptionsWithLabels(settingComfyuiCheckpoint, items);
    setComfyuiCheckpointValue(current);
    showLocalImageConfigMessage(`Loaded ${(payload.checkpoints || []).length} ComfyUI checkpoints.`);
  } catch (error) {
    showLocalImageConfigMessage(error.message, "error");
  }
}

function automationPayloadFromForm() {
  return {
    local_render_backend: settingLocalRenderBackend.value,
    local_render_preset: settingLocalRenderPreset.value,
    local_render_positive_prompt_globals: settingLocalRenderPositiveGlobals.value,
    local_render_negative_prompt_globals: settingLocalRenderNegativeGlobals.value,
    local_render_use_forge_couple: settingLocalRenderForgeCouple.checked,
    local_render_checkpoint: settingLocalRenderCheckpoint.value,
    stable_matrix_profile: settingLocalRenderPreset.value,
    stable_matrix_positive_prompt_globals: settingLocalRenderPositiveGlobals.value,
    stable_matrix_negative_prompt_globals: settingLocalRenderNegativeGlobals.value,
    stable_matrix_use_forge_couple: settingLocalRenderForgeCouple.checked,
    stable_matrix_checkpoint: settingLocalRenderCheckpoint.value,
    comfyui_profile: settingComfyuiProfile.value,
    comfyui_server_url: settingComfyuiServerUrl.value,
    comfyui_checkpoint: settingComfyuiCheckpoint.value,
    comfyui_positive_prompt_globals: settingComfyuiPositiveGlobals.value,
    comfyui_negative_prompt_globals: settingComfyuiNegativeGlobals.value,
    comfyui_poll_seconds: Number(settingComfyuiPollSeconds.value || 0),
    comfyui_timeout_seconds: Number(settingComfyuiTimeoutSeconds.value || 0),
    zine_print_scale: Number(settingZinePrintScale.value || 0),
    zine_page_margin: Number(settingZinePageMargin.value || 0),
    zine_width: Number(settingZineWidth.value || 0),
    turnaround_width: Number(settingTurnaroundWidth.value || 0),
    ai_harvest_auto_enabled: settingAiHarvestAuto.checked,
    ai_harvest_interval_seconds: Number(settingAiHarvestInterval.value || 0),
    ai_prompt_analysis_model: settingAiPromptAnalysisModel.value,
    ai_prompt_analysis_instructions_file: settingAiPromptAnalysisFile.value,
    render_backend: settingRenderBackend.value,
  };
}

async function saveAutomationSettings(event) {
  event?.preventDefault?.();
  const showMessage = document.querySelector("#pipeline-controls-page").classList.contains("active")
    ? showPipelineControlsMessage
    : document.querySelector("#local-image-config-page").classList.contains("active")
      ? showLocalImageConfigMessage
      : showAiControlsMessage;
  showMessage("Saving...");
  try {
    const payload = await fetchJson(`/api/pipeline-controls/automation?${currentQuery().toString()}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(automationPayloadFromForm()),
    });
    renderPipelineControls(payload);
    showMessage(payload.message || "Settings saved.");
    state.savedBaselines.settings = settingsSnapshot();
    setSaveState(settingsSaveState, "Saved", "saved");
    return true;
  } catch (error) {
    showMessage(error.message, "error");
    setSaveState(settingsSaveState, "Error", "error");
    return false;
  }
}

async function runBatchRenderReset() {
  const pipeline = batchRenderPipeline.value;
  if (!pipeline) {
    return;
  }
  showPipelineControlsMessage("Previewing affected assets...");
  const params = currentQuery();
  params.set("pipeline_name", pipeline);
  params.set("include_locked", batchIncludeLocked.checked ? "true" : "false");
  try {
    const preview = await fetchJson(`/api/pipeline-controls/batch-render-reset/preview?${params.toString()}`);
    const counts = preview.counts || {};
    renderRows(batchRenderResultTableBody, preview.items || [], [
      "asset_id",
      "before_stage",
      "before_actor",
      "before_state",
      "status",
      "message",
    ]);
    if (!counts.affected) {
      showPipelineControlsMessage(`Nothing to reset: ${counts.skipped || 0} skipped, ${counts.locked || 0} locked.`, "warning");
      return;
    }
    const confirmed = await confirmAction(
      "Reset pipeline assets",
      `Reset ${pipeline} assets for ${state.character} / ${state.phase} to RENDER? Affected: ${counts.affected}; skipped: ${counts.skipped || 0}; locked: ${counts.locked || 0}. This clears queued render items and existing render outputs.`,
      "Reset Assets",
    );
    if (!confirmed) {
      showPipelineControlsMessage("Batch reset cancelled.");
      return;
    }
    showPipelineControlsMessage("Resetting assets...");
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
  renderAssetTaskTable(
    renderConsoleTaskBody,
    state.renderConsoleTasks,
    state.selectedRenderConsoleAskId,
    selectRenderConsoleTask,
    "No manual render tasks are waiting.",
  );
}

async function selectRenderConsoleTask(askId) {
  state.selectedRenderConsoleAskId = askId;
  updateSelectableRows(renderConsoleTaskBody, (row) => row.dataset.askId === state.selectedRenderConsoleAskId);
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
  renderConsoleLocalTest.disabled = true;
  renderConsoleCopyLocalApiParams.disabled = true;
  renderConsoleLocalApiPopover.hidden = true;
  renderConsoleLocalApiText.value = "";
  renderConsoleClearLocalTest.disabled = true;
  renderConsoleLocalStatus.textContent = "";
  renderRenderConsoleLocalTestRender(null);
  renderConsoleImagePreview.hidden = true;
  renderConsoleImagePreview.removeAttribute("src");
  renderConsoleSaveImage.disabled = true;
  renderConsoleAnswerComment.value = "";
  renderConsoleSceneBuilder.hidden = true;
  renderConsoleSceneBuilder.disabled = true;
  renderConsoleReviewPrompt.disabled = true;
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
  const storyLabel = detail.manifest?.story_slug && detail.manifest?.scene_slug
    ? `Story ${detail.manifest.story_slug} / ${detail.manifest.scene_slug}`
    : "";
  renderConsoleTitle.textContent = storyLabel || `Asset ${task.asset_id ?? "unknown"} | ${task.expected_output || task.ask_id}`;
  consoleAskId.textContent = task.ask_id;
  consoleAssetLabel.textContent = storyLabel || `Asset ${task.asset_id ?? "unknown"} | ${task.character} / ${task.phase}`;
  consolePipelineLabel.textContent = `${task.pipeline} | ${task.pipeline_stage}`;
  consoleExpectedOutput.textContent = task.expected_output || "";
  const helperText = detail.gpt_helper_prompt?.text || "";
  renderConsoleHelperText.value = helperText;
  renderConsoleHelperPanel.hidden = !detail.gpt_helper_prompt?.source;
  renderConsoleSaveHelper.disabled = !detail.gpt_helper_prompt?.source;
  renderConsoleCopyHelper.disabled = !helperText;
  renderConsolePrompt.value = detail.prompt || "";
  const isScene = Boolean(detail.manifest?.story_slug && detail.manifest?.scene_slug);
  renderConsoleSceneBuilder.hidden = !isScene;
  renderConsoleSceneBuilder.disabled = !isScene;
  renderConsoleReviewPrompt.disabled = !detail.prompt;
  renderConsoleCopyPrompt.disabled = !detail.prompt;
  renderConsoleFailTask.disabled = false;
  const localPrompt = detail.local_prompt || {};
  renderConsoleLocalTest.disabled = !localPrompt.supports_local_test_render;
  renderConsoleCopyLocalApiParams.disabled = !localPrompt.local_api_call_exists;
  renderConsoleClearLocalTest.disabled = !localPrompt.latest_local_test_render;
  const localRenderState = localPrompt.local_render_status?.state || "";
  renderConsoleLocalStatus.textContent = [localPrompt.supports_local_test_render ? "Local prompt: READY" : "Local prompt: DISABLED", localRenderState ? `Local render: ${localRenderState}` : ""]
    .filter(Boolean)
    .join(" | ");
  renderRenderConsoleLocalTestRender(localPrompt.latest_local_test_render);
  renderConsoleReferenceFiles(detail.reference_files || []);
  updateRenderConsoleNavigation();
}

function renderRenderConsoleLocalTestRender(path) {
  renderConsoleLocalTestRender.replaceChildren();
  if (!path) {
    renderConsoleLocalTestRender.textContent = "No local test render.";
    renderConsoleClearLocalTest.disabled = true;
    return;
  }
  const image = document.createElement("img");
  image.alt = "Latest local test render";
  image.src = fileUrl(path, Date.now().toString());
  image.title = path;
  renderConsoleLocalTestRender.append(enableFullscreenImage(image));
  renderConsoleClearLocalTest.disabled = false;
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
  updateAssetTaskNavigation(
    state.renderConsoleTasks,
    state.selectedRenderConsoleAskId,
    renderConsolePrev,
    renderConsoleNext,
  );
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

async function runRenderConsoleLocalAction(action) {
  if (!state.selectedRenderConsoleAskId) {
    return;
  }
  renderConsoleLocalStatus.textContent = "Queueing local test image...";
  renderConsoleLocalTest.disabled = true;
  renderConsoleClearLocalTest.disabled = true;
  try {
    const payload = await fetchJson(
      `/api/render-console/tasks/${encodeURIComponent(state.selectedRenderConsoleAskId)}/${action}?${currentQuery().toString()}`,
      { method: "POST" },
    );
    renderRenderConsoleDetail(payload);
    showRenderConsoleMessage(payload.message || "Action complete.");
    if (action === "local-test-render") {
      startRenderConsoleHarvestTimer();
    }
  } catch (error) {
    renderConsoleLocalStatus.textContent = error.message;
    showRenderConsoleMessage(error.message, "error");
  }
}

function stopRenderConsoleHarvestTimer() {
  if (state.renderConsoleHarvestTimer) {
    window.clearInterval(state.renderConsoleHarvestTimer);
  }
  state.renderConsoleHarvestTimer = null;
  state.renderConsoleHarvestRunsRemaining = 0;
}

async function runRenderConsoleHarvestTick() {
  if (state.renderConsoleHarvestRunsRemaining <= 0) {
    stopRenderConsoleHarvestTimer();
    return;
  }
  state.renderConsoleHarvestRunsRemaining -= 1;
  try {
    await fetchJson("/api/ai-controls/harvest", { method: "POST" });
    if (state.selectedRenderConsoleAskId) {
      await selectRenderConsoleTask(state.selectedRenderConsoleAskId);
    }
    const remaining = state.renderConsoleHarvestRunsRemaining;
    renderConsoleLocalStatus.textContent = remaining
      ? `Harvested AI answers. Next harvest in 60 seconds.`
      : "Harvested AI answers. Auto-harvest stopped.";
  } catch (error) {
    renderConsoleLocalStatus.textContent = error.message;
    showRenderConsoleMessage(error.message, "error");
  }
  if (state.renderConsoleHarvestRunsRemaining <= 0) {
    stopRenderConsoleHarvestTimer();
  }
}

function startRenderConsoleHarvestTimer() {
  stopRenderConsoleHarvestTimer();
  state.renderConsoleHarvestRunsRemaining = 2;
  renderConsoleLocalStatus.textContent = "Local render queued. Auto-harvest will run twice, every 60 seconds.";
  state.renderConsoleHarvestTimer = window.setInterval(runRenderConsoleHarvestTick, 60000);
}

async function clearRenderConsoleLocalTest() {
  if (!state.selectedRenderConsoleAskId) {
    return;
  }
  renderConsoleLocalStatus.textContent = "Clearing local test image...";
  renderConsoleLocalTest.disabled = true;
  renderConsoleClearLocalTest.disabled = true;
  try {
    const payload = await fetchJson(
      `/api/render-console/tasks/${encodeURIComponent(state.selectedRenderConsoleAskId)}/local-test-render?${currentQuery().toString()}`,
      { method: "DELETE" },
    );
    renderRenderConsoleDetail(payload);
    showRenderConsoleMessage(payload.message || "Local test image cleared.");
  } catch (error) {
    renderConsoleLocalStatus.textContent = error.message;
    showRenderConsoleMessage(error.message, "error");
  }
}

async function loadLocalImageReviewTasks(preferredAskId = null) {
  localImageReviewStatus.textContent = "Loading render tasks...";
  const payload = await fetchJson(`/api/render-console/tasks?${currentQuery().toString()}`);
  state.localImageReviewTasks = payload.tasks || [];
  const askIds = new Set(state.localImageReviewTasks.map((task) => task.ask_id));
  state.selectedLocalImageReviewAskId =
    preferredAskId || state.selectedLocalImageReviewAskId || state.localImageReviewTasks[0]?.ask_id || null;
  if (state.selectedLocalImageReviewAskId && !askIds.has(state.selectedLocalImageReviewAskId)) {
    state.selectedLocalImageReviewAskId = state.localImageReviewTasks[0]?.ask_id || null;
  }
  renderLocalImageReviewTaskTable();
  localImageReviewStatus.textContent = `${state.localImageReviewTasks.length} render task(s)`;
  if (state.selectedLocalImageReviewAskId) {
    await selectLocalImageReviewTask(state.selectedLocalImageReviewAskId);
  } else {
    clearLocalImageReview();
  }
}

function renderLocalImageReviewTaskTable() {
  renderAssetTaskTable(
    localImageReviewTaskBody,
    state.localImageReviewTasks,
    state.selectedLocalImageReviewAskId,
    selectLocalImageReviewTask,
    "No local-image render tasks are waiting.",
  );
}

async function selectLocalImageReviewTask(askId) {
  state.selectedLocalImageReviewAskId = askId;
  updateSelectableRows(localImageReviewTaskBody, (row) => row.dataset.askId === askId);
  const detail = await fetchJson(
    `/api/local-image-review/tasks/${encodeURIComponent(askId)}?${currentQuery().toString()}`,
  );
  renderLocalImageReviewDetail(detail);
}

function clearLocalImageReview() {
  state.localImageReviewDetail = null;
  localImageReviewTitle.textContent = "Select a render task";
  localImageReviewMessage.textContent = "";
  localImageReviewClear.disabled = true;
  localImageReviewGenerate.disabled = true;
  localImageReviewGenerateAllModels.disabled = true;
  localImageReviewPrev.disabled = true;
  localImageReviewNext.disabled = true;
  renderLocalImageReviewGallery([]);
}

function renderLocalImageReviewDetail(detail) {
  state.localImageReviewDetail = detail;
  const task = detail.task;
  const storyLabel = detail.manifest?.story_slug && detail.manifest?.scene_slug
    ? `Story ${detail.manifest.story_slug} / ${detail.manifest.scene_slug}`
    : "";
  localImageReviewTitle.textContent =
    storyLabel || `Asset ${task.asset_id ?? "unknown"} | ${task.expected_output || task.ask_id}`;
  localImageReviewClear.disabled = false;
  localImageReviewGenerate.disabled = !detail.supports_local_test_render;
  localImageReviewGenerateAllModels.disabled = !detail.supports_local_test_render;
  const queueState = detail.local_render_status?.state || "";
  localImageReviewMessage.textContent = [
    `${detail.images?.length || 0} local image(s)`,
    queueState ? `Queue: ${queueState}` : "",
  ].filter(Boolean).join(" | ");
  renderLocalImageReviewGallery(detail.images || []);
  updateLocalImageReviewNavigation();
}

function renderLocalImageReviewGallery(images) {
  localImageReviewGallery.replaceChildren();
  if (!images.length) {
    const empty = document.createElement("div");
    empty.className = "image-placeholder";
    empty.textContent = "No local images.";
    localImageReviewGallery.append(empty);
    return;
  }
  for (const item of images) {
    const card = document.createElement("article");
    card.className = "local-image-review-card";
    const image = document.createElement("img");
    image.alt = item.name || "Local test render";
    image.src = fileUrl(item.path, item.modified_at || Date.now().toString());
    image.title = item.path;
    const preview = document.createElement("div");
    preview.className = "local-image-review-preview";
    preview.append(enableFullscreenImage(image));
    const caption = document.createElement("p");
    const generation = {
      stable_matrix: "Stable Matrix",
      comfyui: "ComfyUI",
    }[item.image_generation] || String(item.image_generation || "").replaceAll("_", " ");
    caption.textContent = [
      `Image Generation: ${generation || "Unknown"}`,
      `Render Profile: ${item.render_profile || "Unknown"}`,
      `Checkpoint: ${item.checkpoint || "Unknown"}`,
    ].join(" · ");
    card.append(preview, caption);
    localImageReviewGallery.append(card);
  }
}

function updateLocalImageReviewNavigation() {
  updateAssetTaskNavigation(
    state.localImageReviewTasks,
    state.selectedLocalImageReviewAskId,
    localImageReviewPrev,
    localImageReviewNext,
  );
}

async function generateLocalImageReviewImages() {
  if (!state.selectedLocalImageReviewAskId) {
    return;
  }
  localImageReviewGenerate.disabled = true;
  localImageReviewClear.disabled = true;
  localImageReviewMessage.textContent = "Queueing local images...";
  const params = currentQuery();
  params.set("count", localImageReviewCount.value || "1");
  try {
    const payload = await fetchJson(
      `/api/local-image-review/tasks/${encodeURIComponent(state.selectedLocalImageReviewAskId)}/images?${params.toString()}`,
      { method: "POST" },
    );
    renderLocalImageReviewDetail(payload);
    localImageReviewMessage.textContent = payload.message || "Local images queued.";
    startLocalImageReviewHarvestTimer();
  } catch (error) {
    localImageReviewMessage.textContent = error.message;
  } finally {
    localImageReviewGenerate.disabled = !state.localImageReviewDetail?.supports_local_test_render;
    localImageReviewClear.disabled = !state.localImageReviewDetail;
  }
}

async function generateLocalImageReviewImagesForAllModels() {
  if (!state.selectedLocalImageReviewAskId) {
    return;
  }
  localImageReviewGenerate.disabled = true;
  localImageReviewGenerateAllModels.disabled = true;
  localImageReviewClear.disabled = true;
  localImageReviewMessage.textContent = "Refreshing checkpoints and queueing local images...";
  const params = currentQuery();
  params.set("count", localImageReviewCount.value || "1");
  try {
    if (settingLocalRenderBackend.value === "comfyui") {
      await refreshComfyuiCheckpointOptions();
    } else {
      await refreshLocalRenderCheckpointOptions();
    }
    const payload = await fetchJson(
      `/api/local-image-review/tasks/${encodeURIComponent(state.selectedLocalImageReviewAskId)}/images/all-checkpoints?${params.toString()}`,
      { method: "POST" },
    );
    renderLocalImageReviewDetail(payload);
    localImageReviewMessage.textContent = payload.message || "Local images queued for all models.";
    startLocalImageReviewHarvestTimer();
  } catch (error) {
    localImageReviewMessage.textContent = error.message;
  } finally {
    const disabled = !state.localImageReviewDetail?.supports_local_test_render;
    localImageReviewGenerate.disabled = disabled;
    localImageReviewGenerateAllModels.disabled = disabled;
    localImageReviewClear.disabled = !state.localImageReviewDetail;
  }
}

async function clearLocalImageReviewImages() {
  if (!state.selectedLocalImageReviewAskId) {
    return;
  }
  const count = state.localImageReviewDetail?.images?.length || 0;
  const label = state.localImageReviewDetail?.task?.display_label || state.selectedLocalImageReviewAskId;
  if (!count) {
    localImageReviewMessage.textContent = "No local images to clear.";
    return;
  }
  if (!await confirmAction(
    "Clear local images",
    `Clear ${count} local image(s) for ${label}? This permanently deletes the generated images.`,
    "Clear Images",
  )) {
    return;
  }
  localImageReviewClear.disabled = true;
  localImageReviewMessage.textContent = "Clearing local images...";
  try {
    const payload = await fetchJson(
      `/api/local-image-review/tasks/${encodeURIComponent(state.selectedLocalImageReviewAskId)}/images?${currentQuery().toString()}`,
      { method: "DELETE" },
    );
    renderLocalImageReviewDetail(payload);
    localImageReviewMessage.textContent = payload.message || "Local images cleared.";
  } catch (error) {
    localImageReviewMessage.textContent = error.message;
  } finally {
    localImageReviewClear.disabled = !state.localImageReviewDetail;
  }
}

async function archiveHarvestedAiAnswers() {
  const count = state.aiControls?.harvested_answer_count || 0;
  if (!count) {
    showAiControlsMessage("No harvested answer folders are available to archive.");
    return;
  }
  if (await confirmAction(
    "Archive harvested answers",
    `Archive ${count} harvested answer folder(s)? Unharvested answers are not affected.`,
    "Archive Answers",
  )) {
    await runAiControlsAction("/api/ai-controls/archive-harvested");
  }
}

function stopLocalImageReviewHarvestTimer() {
  if (state.localImageReviewHarvestTimer) {
    window.clearInterval(state.localImageReviewHarvestTimer);
  }
  state.localImageReviewHarvestTimer = null;
  state.localImageReviewHarvestRunsRemaining = 0;
}

async function runLocalImageReviewHarvestTick() {
  if (state.localImageReviewHarvestRunsRemaining <= 0 || !state.selectedLocalImageReviewAskId) {
    stopLocalImageReviewHarvestTimer();
    return;
  }
  state.localImageReviewHarvestRunsRemaining -= 1;
  try {
    await fetchJson("/api/ai-controls/harvest", { method: "POST" });
    await selectLocalImageReviewTask(state.selectedLocalImageReviewAskId);
    if (!state.localImageReviewDetail?.local_render_status?.state) {
      stopLocalImageReviewHarvestTimer();
    }
  } catch (error) {
    localImageReviewMessage.textContent = error.message;
  }
}

function startLocalImageReviewHarvestTimer() {
  stopLocalImageReviewHarvestTimer();
  state.localImageReviewHarvestRunsRemaining = 40;
  state.localImageReviewHarvestTimer = window.setInterval(runLocalImageReviewHarvestTick, 30000);
}

async function saveAuxiliaryResourceImage() {
  const resource = selectedAuxiliaryResource();
  const imageLabel = auxResourceImageLabel.value.trim();
  if (!resource) {
    showAuxResourceMessage("Select or save a resource first.", "error");
    return;
  }
  if (!imageLabel) {
    showAuxResourceMessage("Image name is required.", "error");
    return;
  }
  if (!state.selectedAuxiliaryImageId && !state.auxiliaryResourceImageBlob) {
    showAuxResourceMessage("Image is required.", "error");
    return;
  }
  const params = new URLSearchParams({
    category: auxResourceCategory.value || "person",
    image_label: imageLabel,
    original_image_id: state.selectedAuxiliaryImageId || "",
  });
  const blob = state.auxiliaryResourceImageBlob || new Blob([]);
  auxResourceSaveImage.disabled = true;
  showAuxResourceMessage(state.selectedAuxiliaryImageId ? "Updating image..." : "Saving image...");
  try {
    const payload = await fetchJson(`/api/auxiliary-resources/${encodeURIComponent(resource.resource_id)}/images?${params.toString()}`, {
      method: "PUT",
      headers: { "Content-Type": blob.type || "application/octet-stream" },
      body: blob,
    });
    state.auxiliaryResources = payload.resources || state.auxiliaryResources;
    state.selectedAuxiliaryResourceId = payload.resource?.resource_id || resource.resource_id;
    const saved = payload.resource?.images?.find((item) => item.label === imageLabel) || payload.resource?.images?.[0];
    const savedImageId = saved?.image_id || state.selectedAuxiliaryImageId;
    state.auxiliaryResourceImageBlob = null;
    renderAuxiliaryResourceTable();
    selectAuxiliaryResource(state.selectedAuxiliaryResourceId);
    if (savedImageId) {
      selectAuxiliaryResourceImage(savedImageId);
    }
    showAuxResourceMessage(payload.message || "Image saved.");
  } catch (error) {
    showAuxResourceMessage(error.message, "error");
  } finally {
    auxResourceSaveImage.disabled = !state.selectedAuxiliaryResourceId;
  }
}

async function copyRenderConsoleLocalApiParams() {
  if (!state.selectedRenderConsoleAskId) {
    return;
  }
  renderConsoleCopyLocalApiParams.disabled = true;
  try {
    const payload = await fetchJson(
      `/api/render-console/tasks/${encodeURIComponent(state.selectedRenderConsoleAskId)}/local-test-render/api-params?${currentQuery().toString()}`,
    );
    renderConsoleLocalApiText.value = payload.text || "";
    renderConsoleLocalApiPopover.hidden = false;
    showRenderConsoleMessage(`Loaded ${payload.path || "Stable_Matrix_API_Call.json"}.`);
  } catch (error) {
    showRenderConsoleMessage(error.message, "error");
  } finally {
    renderConsoleCopyLocalApiParams.disabled = false;
  }
}

async function copyDisplayedRenderConsoleLocalApiParams() {
  await writeClipboardText(renderConsoleLocalApiText.value || "");
  showRenderConsoleMessage("Local image API parameters copied.");
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
  if (!state.manifestTasks.length) {
    renderEmptyRow(manifestTaskBody, 3, "No manifest tasks are waiting. Advance an asset to MANIFEST to create work.");
    return;
  }
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
    makeSelectableRow(row, `Asset ${task.asset_id}`, task.asset_id === state.selectedManifestAssetId, () => selectManifestAsset(task.asset_id));
    manifestTaskBody.append(row);
  }
}

async function selectManifestAsset(assetId) {
  state.selectedManifestAssetId = Number(assetId);
  updateSelectableRows(manifestTaskBody, (row) => Number(row.dataset.assetId) === state.selectedManifestAssetId);
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
  const requestedCharacter = characterSelect.value;
  const previousCharacter = state.character || "";
  characterSelect.disabled = true;
  const allowed = await guardCurrentEditor();
  characterSelect.disabled = false;
  if (!allowed) {
    characterSelect.value = previousCharacter;
    return;
  }
  characterSelect.value = requestedCharacter;
  state.character = requestedCharacter;
  state.phase = null;
  saveStoredContext();
  state.selectedAssetId = null;
  state.selectedPromptReviewAskId = null;
  state.selectedRenderReviewAssetId = null;
  state.selectedRenderConsoleAskId = null;
  state.selectedLocalImageReviewAskId = null;
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
  if (document.querySelector("#local-image-review-page").classList.contains("active")) {
    await loadLocalImageReviewTasks();
  }
});

phaseSelect.addEventListener("change", async () => {
  const requestedPhase = phaseSelect.value;
  const previousPhase = state.phase || "";
  phaseSelect.disabled = true;
  const allowed = await guardCurrentEditor();
  phaseSelect.disabled = false;
  if (!allowed) {
    phaseSelect.value = previousPhase;
    return;
  }
  phaseSelect.value = requestedPhase;
  state.phase = requestedPhase;
  saveStoredContext();
  updateHeaderFitmentPreview();
  state.selectedAssetId = null;
  state.selectedPromptReviewAskId = null;
  state.selectedRenderReviewAssetId = null;
  state.selectedRenderConsoleAskId = null;
  state.selectedLocalImageReviewAskId = null;
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
  if (document.querySelector("#local-image-review-page").classList.contains("active")) {
    await loadLocalImageReviewTasks();
  }
});

for (const button of actionButtons) {
  button.addEventListener("click", () => runAssetAction(button.dataset.action));
}

newCharacterButton.addEventListener("click", startNewCharacter);
newPhaseButton.addEventListener("click", startNewPhase);
toolbarTodoButton.addEventListener("click", openTodoDialog);
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
    closeToolbarSettingsMenu(true);
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeToolbarSettingsMenu(true);
  }
});
todoForm.addEventListener("submit", saveTodo);
todoDialog.addEventListener("close", () => {
  persistTodo().catch((error) => {
    console.error("Unable to save To Do text.", error);
  });
});
todoDialog.addEventListener("click", (event) => {
  if (event.target === todoDialog) {
    todoDialog.close();
  }
});
promptAnalysisClose.addEventListener("click", closePromptAnalysisDialog);
promptAnalysisDialog.addEventListener("click", (event) => {
  if (event.target === promptAnalysisDialog) {
    closePromptAnalysisDialog();
  }
});
promptAnalysisDialog.addEventListener("close", () => {
  promptAnalysisFrame.removeAttribute("src");
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
storyCreate.addEventListener("click", createStory);
storySave.addEventListener("click", saveStory);
storySettingsLoad.addEventListener("click", loadStorySettings);
storySettingsSave.addEventListener("click", saveStorySettings);
storyDelete.addEventListener("click", deleteStory);
storyGitStatus.addEventListener("click", () => runStoryGitAction("status"));
storyGitPull.addEventListener("click", () => runStoryGitAction("pull"));
storyGitCommit.addEventListener("click", () => runStoryGitAction("commit"));
sceneStorySelect.addEventListener("change", async () => {
  const requestedStory = sceneStorySelect.value || null;
  const previousStory = state.selectedStorySlug;
  sceneStorySelect.disabled = true;
  const allowed = await guardCurrentEditor();
  sceneStorySelect.disabled = false;
  if (!allowed) {
    sceneStorySelect.value = previousStory || "";
    return;
  }
  state.selectedStorySlug = requestedStory;
  state.selectedSceneSlug = null;
  await loadScenesPage();
});
sceneCreate.addEventListener("click", createScene);
sceneSave.addEventListener("click", saveScene);
sceneDelete.addEventListener("click", deleteScene);
sceneStageRender.addEventListener("click", stageSceneRender);
sceneBuilderOpen.addEventListener("click", activateSceneBuilderPage);
sceneToggleImage.addEventListener("click", toggleSceneImage);
enableFullscreenImage(sceneImagePreview, () => ({
  sceneSlug: state.selectedSceneSlug,
  scenes: state.scenes,
  storySlug: state.selectedStorySlug,
}));
zineNew.addEventListener("click", () => runGuardedTransition(clearZineEditor));
zineEdit.addEventListener("click", () => zineName.focus());
zineSave.addEventListener("click", saveZine);
zineRegenerate.addEventListener("click", () => runGuardedTransition(regenerateZine));
zineDelete.addEventListener("click", () => runGuardedTransition(deleteZine));
zineStorySelect.addEventListener("change", async () => {
  state.zineStorySlug = zineStorySelect.value || null;
  await loadZineStorySources();
});
zineFillStory.addEventListener("click", fillZineFromStory);
zineSpread1.addEventListener("change", () => setZineSpread(1, zineSpread1.checked));
zineSpread3.addEventListener("change", () => setZineSpread(3, zineSpread3.checked));
zineSpread5.addEventListener("change", () => setZineSpread(5, zineSpread5.checked));
enableFullscreenImage(zinePreview);
enableFullscreenImage(auxResourceImagePreview);
fullscreenImageClose.addEventListener("click", closeFullscreenImage);
fullscreenImagePrevious.addEventListener("click", () => navigateFullscreenScene(-1));
fullscreenImageNext.addEventListener("click", () => navigateFullscreenScene(1));
fullscreenImageOverlay.addEventListener("keydown", (event) => {
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    navigateFullscreenScene(-1);
  } else if (event.key === "ArrowRight") {
    event.preventDefault();
    navigateFullscreenScene(1);
  }
});
fullscreenImageOverlay.addEventListener("click", (event) => {
  if (event.button === 0 && event.target === fullscreenImageOverlay) {
    closeFullscreenImage();
  }
});
fullscreenImageOverlay.addEventListener("close", () => {
  resetFullscreenCrop();
  resetFullscreenNavigation();
  fullscreenImage.removeAttribute("src");
  fullscreenImage.alt = "";
});
fullscreenImageOverlay.addEventListener("contextmenu", (event) => {
  event.preventDefault();
});
fullscreenImageOverlay.addEventListener("pointerdown", (event) => {
  if (event.button !== 2 || !fullscreenImageOverlay.open) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  fullscreenCropStart = fullscreenImagePoint(event);
  fullscreenCropEnd = fullscreenCropStart;
  fullscreenCropPointerId = event.pointerId;
  fullscreenImageOverlay.setPointerCapture(event.pointerId);
  updateFullscreenCropBox();
});
fullscreenImageOverlay.addEventListener("pointermove", (event) => {
  if (fullscreenCropPointerId !== event.pointerId) {
    return;
  }
  event.preventDefault();
  fullscreenCropEnd = fullscreenImagePoint(event);
  updateFullscreenCropBox();
});
fullscreenImageOverlay.addEventListener("pointerup", async (event) => {
  if (fullscreenCropPointerId !== event.pointerId) {
    return;
  }
  event.preventDefault();
  fullscreenCropEnd = fullscreenImagePoint(event);
  try {
    await copyFullscreenCrop();
  } catch (error) {
    showAuxResourceMessage(`Unable to copy image snip: ${error.message}`, "error");
  } finally {
    resetFullscreenCrop();
    fullscreenImageOverlay.releasePointerCapture(event.pointerId);
  }
});
scenePickerCharacter.addEventListener("change", () => {
  state.scenePickerCharacter = scenePickerCharacter.value || "";
  loadSceneImageReferences();
});
scenePickerSearch.addEventListener("input", () => {
  state.scenePickerSearch = scenePickerSearch.value || "";
  loadSceneImageReferences();
});
scenePickerRefresh.addEventListener("click", loadSceneImageReferences);
builderImagePickerCharacter.addEventListener("change", () => loadImagePickerReferences(builderImagePicker));
builderImagePickerSearch.addEventListener("input", () => {
  state.builderImagePickerSearch = builderImagePickerSearch.value || "";
  loadImagePickerReferences(builderImagePicker);
});
builderImagePickerRefresh.addEventListener("click", () => loadImagePickerReferences(builderImagePicker));
builderImagePickerClose.addEventListener("click", () => {
  builderImagePickerModal.close();
});
builderElementResourceType.addEventListener("change", async () => {
  builderUpdateElementModalSections();
  await builderLoadElementAuxResources();
});
builderElementCharacter.addEventListener("change", async () => {
  setSelectOptions(builderElementPhase, state.phasesByCharacter[builderElementCharacter.value] || []);
  await builderLoadElementCostumes();
});
builderElementPhase.addEventListener("change", builderLoadElementCostumes);
builderElementCancel.addEventListener("click", () => {
  builderElementModal.close();
});
builderElementAdd.addEventListener("click", builderAddElementFromDialog);
auxResourceCategory.addEventListener("change", () => {
  clearAuxiliaryResourceForm();
  loadAuxiliaryResources();
});
auxResourceSearch.addEventListener("input", refreshAuxiliaryResourceTable);
auxResourceAdd.addEventListener("click", clearAuxiliaryResourceForm);
auxResourceEditTemplate.addEventListener("click", openAuxiliaryResourceTemplate);
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
auxResourceNewImage.addEventListener("click", newAuxiliaryResourceImage);
auxResourceSaveImage.addEventListener("click", saveAuxiliaryResourceImage);
auxResourceClear.addEventListener("click", clearAuxiliaryResourceForm);
auxResourceCopyTag.addEventListener("click", () => copyText(auxResourceTag.textContent || "", "Resource tag copied."));
phaseComparisonCharacter.addEventListener("change", () => {
  state.phaseComparison.character = phaseComparisonCharacter.value;
  state.phaseComparison.pipeline = "Character-Assembly";
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
copyPromptButton.addEventListener("click", () => copyText(state.promptReviewDetail?.prompt || "", "Prompt copied."));
promptReviewSceneBuilder.addEventListener("click", async () => {
  const scene = selectedPromptReviewScene();
  if (!scene) return;
  state.selectedStorySlug = scene.storySlug;
  state.selectedSceneSlug = scene.sceneSlug;
  await activatePage("scene-builder", { skipAutosave: true });
});
copyCondensedButton.addEventListener("click", () => copyText(condensedText.value, "Condensed prompt copied."));
analyzePromptButton.addEventListener("click", analyzePromptReview);
viewPromptAnalysisButton.addEventListener("click", viewPromptReviewAnalysis);
sourceOpenEditor.addEventListener("click", openSelectedSourceEditor);
sourceEditorSave.addEventListener("click", saveSourceEditor);
promptReviewPrev.addEventListener("click", () => {
  selectAdjacentAssetTask(state.promptReviewTasks, state.selectedPromptReviewAskId, -1, selectPromptReviewTask);
});
promptReviewNext.addEventListener("click", () => {
  selectAdjacentAssetTask(state.promptReviewTasks, state.selectedPromptReviewAskId, 1, selectPromptReviewTask);
});
promptReviewRefresh.addEventListener("click", () => loadPromptReviewTasks());
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
refreshAiControlsButton.addEventListener("click", async () => {
  await loadAiControls();
  await loadPipelineControls();
});
harvestAiButton.addEventListener("click", () => runAiControlsAction("/api/ai-controls/harvest"));
archiveHarvestedAiButton.addEventListener("click", archiveHarvestedAiAnswers);
openRenderConsoleTab.addEventListener("click", () => {
  document.querySelector('.tab[data-page="render-console"]').click();
});
automationForm.addEventListener("submit", saveAutomationSettings);
automationForm.addEventListener("input", updateDirtyIndicators);
automationForm.addEventListener("change", updateDirtyIndicators);
settingZineWidth.addEventListener("input", updateZineMarginLimit);
for (const control of document.querySelectorAll('[form="automation-form"]')) {
  control.addEventListener("input", updateDirtyIndicators);
  control.addEventListener("change", updateDirtyIndicators);
}
refreshLocalRenderCheckpoints.addEventListener("click", refreshLocalRenderCheckpointOptions);
refreshOllamaModels.addEventListener("click", refreshOllamaModelOptions);
settingLocalRenderPreset.addEventListener("change", refreshLocalRenderCheckpointOptions);
refreshComfyuiCheckpoints.addEventListener("click", refreshComfyuiCheckpointOptions);
settingComfyuiProfile.addEventListener("change", refreshComfyuiCheckpointOptions);
settingLocalRenderBackend.addEventListener("change", syncLocalRenderBackendPanels);
sceneBuilderPrevious.addEventListener("click", () => navigateSceneBuilder(-1));
sceneBuilderNext.addEventListener("click", () => navigateSceneBuilder(1));
batchRenderResetButton.addEventListener("click", runBatchRenderReset);
renderConsoleRefresh.addEventListener("click", () => loadRenderConsoleTasks());
renderConsoleSceneBuilder.addEventListener("click", async () => {
  const manifest = state.renderConsoleDetail?.manifest || {};
  if (!manifest.story_slug || !manifest.scene_slug) return;
  state.selectedStorySlug = manifest.story_slug;
  state.selectedSceneSlug = manifest.scene_slug;
  await activatePage("scene-builder", { skipAutosave: true });
});
renderConsoleReviewPrompt.addEventListener("click", async () => {
  const askId = state.renderConsoleDetail?.task?.ask_id;
  if (!askId) return;
  await activatePage("prompt-review", { skipAutosave: true });
  await loadPromptReviewTasks(askId);
});
renderConsoleCopyPrompt.addEventListener("click", async () => {
  await writeClipboardText(state.renderConsoleDetail?.prompt || "");
  showRenderConsoleMessage("Prompt copied.");
});
renderConsoleSaveHelper.addEventListener("click", saveRenderConsoleHelperPrompt);
renderConsoleHelperText.addEventListener("input", () => {
  renderConsoleCopyHelper.disabled = !renderConsoleHelperText.value;
});
renderConsoleCopyHelper.addEventListener("click", async () => {
  await writeClipboardText(renderConsoleHelperText.value || "");
  showRenderConsoleMessage("GPT helper prompt copied.");
});
renderConsoleLocalTest.addEventListener("click", () => runRenderConsoleLocalAction("local-test-render"));
renderConsoleCopyLocalApiParams.addEventListener("click", copyRenderConsoleLocalApiParams);
renderConsoleLocalApiCopy.addEventListener("click", copyDisplayedRenderConsoleLocalApiParams);
document.addEventListener("click", (event) => {
  if (
    !renderConsoleLocalApiPopover.hidden
    && !renderConsoleLocalApiPopover.contains(event.target)
    && event.target !== renderConsoleCopyLocalApiParams
  ) {
    renderConsoleLocalApiPopover.hidden = true;
  }
});
renderConsoleClearLocalTest.addEventListener("click", clearRenderConsoleLocalTest);
localImageReviewRefresh.addEventListener("click", () => loadLocalImageReviewTasks());
localImageReviewClear.addEventListener("click", clearLocalImageReviewImages);
localImageReviewGenerate.addEventListener("click", generateLocalImageReviewImages);
localImageReviewGenerateAllModels.addEventListener("click", generateLocalImageReviewImagesForAllModels);
localImageReviewPrev.addEventListener("click", () => {
  selectAdjacentAssetTask(state.localImageReviewTasks, state.selectedLocalImageReviewAskId, -1, selectLocalImageReviewTask);
});
localImageReviewNext.addEventListener("click", () => {
  selectAdjacentAssetTask(state.localImageReviewTasks, state.selectedLocalImageReviewAskId, 1, selectLocalImageReviewTask);
});
storyText.addEventListener("input", updateDirtyIndicators);
storySettingsFields.addEventListener("input", updateDirtyIndicators);
storySettingsFields.addEventListener("change", updateDirtyIndicators);
sceneText.addEventListener("input", updateDirtyIndicators);
sourceEditorText.addEventListener("input", updateDirtyIndicators);
for (const control of [zineName, ...Object.values(zineSlotInputs), zineSpread1, zineSpread3, zineSpread5]) {
  control.addEventListener("input", updateDirtyIndicators);
  control.addEventListener("change", updateDirtyIndicators);
}
window.addEventListener("beforeunload", (event) => {
  if (
    (state.savedBaselines.story && storySnapshot() !== state.savedBaselines.story)
    || (state.savedBaselines.scene && sceneSnapshot() !== state.savedBaselines.scene)
    || (state.savedBaselines.sceneBuilder && sceneBuilderSnapshot() !== state.savedBaselines.sceneBuilder)
    || (state.savedBaselines.sourceEditor && sourceEditorSnapshot() !== state.savedBaselines.sourceEditor)
    || (state.savedBaselines.zine && zineSnapshot() !== state.savedBaselines.zine)
    || (state.savedBaselines.settings && settingsSnapshot() !== state.savedBaselines.settings)
  ) {
    event.preventDefault();
    event.returnValue = "";
  }
});
renderConsolePrev.addEventListener("click", () => {
  selectAdjacentAssetTask(state.renderConsoleTasks, state.selectedRenderConsoleAskId, -1, selectRenderConsoleTask);
});
renderConsoleNext.addEventListener("click", () => {
  selectAdjacentAssetTask(state.renderConsoleTasks, state.selectedRenderConsoleAskId, 1, selectRenderConsoleTask);
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
  for (const status of document.querySelectorAll(".status-text")) {
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    status.setAttribute("aria-atomic", "true");
  }
  for (const heading of document.querySelectorAll("th")) {
    const raw = heading.textContent.trim();
    heading.title = raw;
    heading.textContent = humanizeHeading(raw);
  }
  sourceEditorText.placeholder = "Open an editable source from Prompt Inspection.";
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
