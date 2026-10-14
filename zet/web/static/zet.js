const state = {
  universeId: "",
  universeGeneration: 0,
  universes: [],
  universeSettingsId: "",
  savedUniverseArtStyle: "",
  workspace: "character",
  activePageId: "",
  productionWorkSummary: { current: {}, project: {} },
  productionWorkRequest: 0,
  productionWorkTimer: null,
  productionWorkPromise: null,
  productionWorkRefreshPending: false,
  pageGeneration: 0,
  pageController: null,
  localRunAllCampaignId: "",
  localRunAllTimer: null,
  selectionGenerations: {},
  selectionControllers: {},
  workspaceSummary: { character: null, story: null },
  lastWorkspacePages: { character: "onboarding", local: "local-overview", story: "scenes" },
  characters: [],
  phasesByCharacter: {},
  onboardingStatuses: {},
  headerPreviews: {},
  onboardingOptions: { species_ancestry: [], gender_presentation: [] },
  onboardingMode: null,
  templateManuals: [],
  selectedTemplateManual: "character",
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
  promptAnalysisTasks: [],
  promptAnalysisRequest: 0,
  promptAnalysisDialogContext: null,
  renderReviewTasks: [],
  selectedRenderReviewKey: null,
  renderReviewDetail: null,
  aiControls: null,
  pipelineControls: null,
  pipelineInspections: [],
  pipelineInspectionFiles: [],
  selectedPipelineInspectionId: null,
  selectedPipelineInspectionFileId: null,
  pipelineInspectionContent: "",
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
  identityKeySourceLocalKey: null,
  localAssetSources: [],
  identityKeyPreview: null,
  costumes: [],
  selectedCostumeSlug: null,
  costumeWizard: null,
  sceneAppearances: [],
  selectedSceneAppearanceId: null,
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
  sceneCollection: { storySlug: "", items: [] },
  selectedSceneSlug: null,
  requestedSceneContext: { storySlug: "", sceneSlug: "" },
  loadedSceneContext: { storySlug: "", sceneSlug: "" },
  loadedBuilderContext: { storySlug: "", sceneSlug: "" },
  sceneDetail: null,
  zines: [],
  selectedZineSlug: null,
  zineLoadState: "absent",
  zineDocument: null,
  zineStorySlug: null,
  zineStorySources: [],
  sceneImageReferences: [],
  scenePickerCharacter: "",
  scenePickerSearch: "",
  sceneBuilder: null,
  sceneBuilderReadiness: null,
  sceneBuilderOptions: {},
  sceneBuilderReferences: [],
  sceneBuilderRenderTargets: [],
  activeBuilderRenderTarget: "main",
  sceneBuilderLoadState: "absent",
  requestedBuilderTargetId: "main",
  showBuilderContextElements: true,
  sceneBuilderOpen: false,
  sceneBuilderInterview: null,
  sceneBuilderInterviewSeed: null,
  sceneCandidateSources: [],
  sceneCandidates: [],
  sceneCandidatesLoadState: "absent",
  selectedSceneCandidateSource: null,
  selectedSceneCandidateId: null,
  selectedSceneCandidateStorySlug: null,
  selectedBuilderPlacementId: null,
  selectedBuilderElementId: null,
  sceneBuilderRendering: false,
  builderResponsiveSection: "elements",
  builderImagePickerReferences: [],
  builderImagePickerSearch: "",
  builderReferenceIndex: 0,
  builderElementAuxResources: {},
  builderElementCostumes: [],
  builderCostumesByCharacterPhase: {},
  imageCatalogItems: [],
  imageCatalogLoaded: false,
  imageCatalogOrganization: { collections: [], keywords: [] },
  imageCatalogReferenceSets: [],
  imageCatalogImportBlob: null,
  entityLibraryImportBlob: null,
  entityLibraryReplacementBlob: null,
  imageCatalogReplaceBlob: null,
  imageCatalogAddBlob: null,
  selectedImageCatalogId: null,
  selectedImageCatalogIds: [],
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
  navigationRequest: 0,
  transitionPromise: null,
};


const taskStoryRoute = new URLSearchParams(window.location.search);
let sceneCandidateRestorePending = taskStoryRoute.get("task_context") === "1" && taskStoryRoute.get("page") === "scene-candidates";
let builderTaskRestorePending = taskStoryRoute.get("task_context") === "1" && taskStoryRoute.get("page") === "scene-builder";
let zineTaskRestorePending = taskStoryRoute.get("task_context") === "1" && taskStoryRoute.get("page") === "zine";


let startupRecoveryTimer = null;
const universeSelect = document.querySelector("#universe-select");
const universeSettingsForm = document.querySelector("#universe-settings-form");
const universeSettingsArtStyle = document.querySelector("#universe-settings-art-style");
const universeCreateForm = document.querySelector("#universe-create-form");

const LAST_CONTEXT_STORAGE_KEY = "zet:last-character-phase";
const LAST_STORY_CONTEXT_STORAGE_KEY = "zet:last-story-scene";
const WORKSPACE_STORAGE_KEY = "zet:workspace-preferences";
const HIDE_BASE_IMAGES_STORAGE_KEY = "zet:asset-hide-base-images";
const IMAGE_GENERATION_STORAGE_KEY = "zet:image-generation";

const CHARACTER_PAGES = new Set(["onboarding", "identity-keys", "turnarounds", "costumes", "phase-comparison"]);
const STORY_PAGES = new Set(["narrative", "scene-candidates", "zine"]);
const LOCAL_PAGES = new Set([
  "local-overview", "local-batch-status", "local-body-reference", "local-head-image", "local-character-assembly",
  "local-costume-dressing", "local-identity-keys", "local-turnarounds", "local-costumes",
  "local-scene-appearances", "local-expressions", "local-comparison",
]);
const LOCAL_ASSET_PAGES = new Set([
  "local-body-reference", "local-head-image", "local-character-assembly", "local-costume-dressing",
]);
const PRODUCTION_PAGES = new Set(["prompt-review"]);
const IMAGE_GENERATION_SLOT_COUNT = 8;
const IMAGE_GENERATION_REFERENCE_COUNT = 10;
let imageGenerationSlots = Array(IMAGE_GENERATION_SLOT_COUNT).fill(null);
let imageGenerationReferenceSlots = Array.from({length: IMAGE_GENERATION_REFERENCE_COUNT}, () => ({label: "", data: ""}));
let imageGenerationSelectedSlot = -1;
let imageGenerationJobIds = [];
const imageGenerationJobs = new Map();
let imageGenerationPending = false;

const characterSelect = document.querySelector("#character-select");
const imageGenerationForm = document.querySelector("#image-generation-form");
const imageGenerationTxt2img = document.querySelector("#image-generation-txt2img");
const imageGenerationImg2img = document.querySelector("#image-generation-img2img");
const imageGenerationReferenceSlotsElement = document.querySelector("#image-generation-reference-slots");
const imageGenerationReferenceList = document.querySelector("#image-generation-reference-list");
const imageGenerationPrompt = document.querySelector("#image-generation-prompt");
const imageGenerationNegative = document.querySelector("#image-generation-negative");
const imageGenerationWidth = document.querySelector("#image-generation-width");
const imageGenerationHeight = document.querySelector("#image-generation-height");
const imageGenerationSubmit = document.querySelector("#image-generation-submit");
const imageGenerationFill = document.querySelector("#image-generation-fill");
const imageGenerationClear = document.querySelector("#image-generation-clear");
const imageGenerationProgress = document.querySelector("#image-generation-progress");
const imageGenerationMessage = document.querySelector("#image-generation-message");
const imageGenerationModel = document.querySelector("#image-generation-model");
const imageGenerationResultsGrid = document.querySelector("#image-generation-results-grid");
const imageGenerationReview = document.querySelector("#image-generation-review");
const imageGenerationReviewImage = document.querySelector("#image-generation-review-image");
const imageGenerationReviewCount = document.querySelector("#image-generation-review-count");
const imageGenerationReviewPrompt = document.querySelector("#image-generation-review-prompt");
const imageGenerationReviewNegative = document.querySelector("#image-generation-review-negative");
const imageGenerationReviewPrevious = document.querySelector("#image-generation-review-previous");
const imageGenerationReviewNext = document.querySelector("#image-generation-review-next");
const imageGenerationReviewClose = document.querySelector("#image-generation-review-close");
const imageGenerationReviewSelect = document.querySelector("#image-generation-review-select");
const imageGenerationReviewRetry = document.querySelector("#image-generation-review-retry");
const imageGenerationReviewClear = document.querySelector("#image-generation-review-clear");
const imageGenerationReviewImport = document.querySelector("#image-generation-review-import");
const imageGenerationReviewUpdate = document.querySelector("#image-generation-review-update");
const imageGenerationSource = document.querySelector("#image-generation-source");
let imageGenerationMode = "txt2img";
let imageGenerationReviewIndex = -1;
let entityLibraryImportGeneration = null;
let imageGenerationOptionsLoaded = false;
const phaseSelect = document.querySelector("#phase-select");
const deletePhaseButton = document.querySelector("#delete-phase");
const headerStorySelect = document.querySelector("#header-story-select");
const headerSceneSelect = document.querySelector("#header-scene-select");
const characterContext = document.querySelector("#character-context");
const storyContext = document.querySelector("#story-context");
const workspaceCharacter = document.querySelector("#workspace-character");
const workspaceLocal = document.querySelector("#workspace-local");
const workspaceStory = document.querySelector("#workspace-story");
const characterNavigation = document.querySelector("#character-navigation");
const localNavigation = document.querySelector("#local-navigation");
const localAssetsButton = document.querySelector("#local-assets-button");
const localAssetsMenu = document.querySelector("#local-assets-menu");
const storyNavigation = document.querySelector("#story-navigation");
const responsiveSectionMenu = document.querySelector("#responsive-section-menu");
const characterProductionMenu = document.querySelector("#character-production-menu");
const storyProductionMenu = document.querySelector("#story-production-menu");
const newMenuButton = document.querySelector("#new-menu-button");
const newMenu = document.querySelector("#new-menu");
const newCharacterButton = document.querySelector("#new-character");
const newPhaseButton = document.querySelector("#new-phase");
const newStoryButton = document.querySelector("#new-story");
const newSceneButton = document.querySelector("#new-scene");
const headerFitmentPreview = document.querySelector("#header-fitment-preview");
const toolbarRestartZet = document.querySelector("#toolbar-restart-zet");
const toolbarSettingsButton = document.querySelector("#toolbar-settings-button");
const toolbarSettingsMenu = document.querySelector("#toolbar-settings-menu");
const toolbarLocalCharacterOverview = document.querySelector("#toolbar-local-character-overview");
const toolbarGateTestRig = document.querySelector("#toolbar-gate-test-rig");
const toolbarHarvestAi = document.querySelector("#toolbar-harvest-ai");
const helpMenuButton = document.querySelector("#help-menu-button");
const helpMenu = document.querySelector("#help-menu");
const helpStatus = document.querySelector("#help-status");
const templateManualSelect = document.querySelector("#template-manual-select");
const templateManualCopy = document.querySelector("#template-manual-copy");
const templateManualDownload = document.querySelector("#template-manual-download");
const templateManualContent = document.querySelector("#template-manual-content");
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
const onboardingAddHeadImages = document.querySelector("#onboarding-add-head-images");
const onboardingTitle = document.querySelector("#onboarding-title");
const onboardingStatusList = document.querySelector("#onboarding-status-list");
const onboardingValidation = document.querySelector("#onboarding-validation");
const characterWorkflow = document.querySelector("#character-workflow");
const characterOverviewMetrics = document.querySelector("#character-overview-metrics");
const characterRecommendedLabel = document.querySelector("#character-recommended-label");
const characterRecommendedAction = document.querySelector("#character-recommended-action");
const characterSetupDetails = document.querySelector("#character-setup-details");
const characterPhoneViewer = document.querySelector("#character-phone-viewer");
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
const promptAnalysisTaskList = document.querySelector("#prompt-analysis-task-list");
const promptReviewTitle = document.querySelector("#prompt-review-title");
const promptReviewMessage = document.querySelector("#prompt-review-message");
const promptSearch = document.querySelector("#prompt-search");
const promptPath = document.querySelector("#prompt-path");
const promptText = document.querySelector("#prompt-text");

const promptReviewRenderConsole = document.querySelector("#prompt-review-render-console");
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
const renderDiscardCandidateButton = document.querySelector("#render-discard-candidate");
const renderFailRenderButton = document.querySelector("#render-fail-render");
const renderFailRegenerateButton = document.querySelector("#render-fail-regenerate");
const renderStageText = document.querySelector("#render-stage-text");
const renderHistoryText = document.querySelector("#render-history-text");
const renderReviewComment = document.querySelector("#render-review-comment");
const renderCommentSave = document.querySelector("#render-comment-save");
const aiControlsStatus = document.querySelector("#ai-controls-status");
const aiControlsMessage = document.querySelector("#ai-controls-message");
const localImageConfigStatus = document.querySelector("#local-image-config-status");
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
const recentHarvestCount = document.querySelector("#recent-harvest-count");
const recentHarvestTableBody = document.querySelector("#recent-harvest-table tbody");
const pipelineControlsStatus = document.querySelector("#pipeline-controls-status");
const pipelineControlsMessage = document.querySelector("#pipeline-controls-message");
const pipelineInspectionStatus = document.querySelector("#pipeline-inspection-status");
const pipelineInspectionMessage = document.querySelector("#pipeline-inspection-message");
const pipelineInspectionSearch = document.querySelector("#pipeline-inspection-search");
const pipelineInspectionList = document.querySelector("#pipeline-inspection-list");
const pipelineInspectionFilesTitle = document.querySelector("#pipeline-inspection-files-title");
const pipelineInspectionFiles = document.querySelector("#pipeline-inspection-files");
const pipelineInspectionPath = document.querySelector("#pipeline-inspection-path");
const pipelineInspectionCopy = document.querySelector("#pipeline-inspection-copy");
const pipelineInspectionOpenFolder = document.querySelector("#pipeline-inspection-open-folder");
const pipelineInspectionText = document.querySelector("#pipeline-inspection-text");
const pipelineInspectionImage = document.querySelector("#pipeline-inspection-image");
const pipelineInspectionEmpty = document.querySelector("#pipeline-inspection-empty");
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
const settingAiPromptAnalysisAutoQueueOnRender = document.querySelector("#setting-ai-prompt-analysis-auto-queue-on-render");
const settingAiAssetWorkflowModel = document.querySelector("#setting-ai-asset-workflow-model");
const settingCodexDefaultModel = document.querySelector("#setting-codex-default-model");
const settingPromptCondenseModel = document.querySelector("#setting-prompt-condense-model");
const settingAiPromptAnalysisModel = document.querySelector("#setting-ai-prompt-analysis-model");
const settingAiImageDescriptionModel = document.querySelector("#setting-ai-image-description-model");
const settingImagePromptGenerationModel = document.querySelector("#setting-image-prompt-generation-model");
const settingCostumeWizardModel = document.querySelector("#setting-costume-wizard-model");
const settingQuickCharacterWizardModel = document.querySelector("#setting-quick-character-wizard-model");

const settingLocalBodyReferenceFaceGateModel = document.querySelector("#setting-local-body-reference-face-gate-model");
const settingLocalBodyReferenceReviewModel = document.querySelector("#setting-local-body-reference-review-model");
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


const settingsSaveState = document.querySelector("#settings-save-state");
const unsavedChangesDialog = document.querySelector("#unsaved-changes-dialog");
const unsavedChangesMessage = document.querySelector("#unsaved-changes-message");
const confirmationDialog = document.querySelector("#confirmation-dialog");
const confirmationTitle = document.querySelector("#confirmation-title");
const confirmationMessage = document.querySelector("#confirmation-message");
const confirmationConfirm = document.querySelector("#confirmation-confirm");
const promptAnalysisDialog = document.querySelector("#prompt-analysis-dialog");
const promptAnalysisClose = document.querySelector("#prompt-analysis-close");
const promptAnalysisFrame = document.querySelector("#prompt-analysis-frame");
const promptAnalysisSecondOpinion = document.querySelector("#prompt-analysis-second-opinion");
const promptAnalysisActionMessage = document.querySelector("#prompt-analysis-action-message");
const renderConsoleStatus = document.querySelector("#render-console-status");
const renderConsoleRefinementMetrics = document.querySelector("#render-console-refinement-metrics");
const renderConsoleRefinementGroups = document.querySelector("#render-console-refinement-groups");
const renderConsoleTaskBody = document.querySelector("#render-console-task-table tbody");
const renderConsolePrev = document.querySelector("#render-console-prev");
const renderConsoleNext = document.querySelector("#render-console-next");
const renderConsoleRefresh = document.querySelector("#render-console-refresh");
const renderConsolePublicationsRefresh = document.querySelector("#render-console-publications-refresh");
const renderConsolePublications = document.querySelector("#render-console-publications");
const renderConsoleTitle = document.querySelector("#render-console-title");
const renderConsoleReviewPrompt = document.querySelector("#render-console-review-prompt");
const renderConsoleCopyPrompt = document.querySelector("#render-console-copy-prompt");
const renderConsoleMessage = document.querySelector("#render-console-message");
const consoleAskId = document.querySelector("#console-ask-id");
const consoleAssetLabel = document.querySelector("#console-asset-label");
const consolePipelineLabel = document.querySelector("#console-pipeline-label");
const consoleExpectedOutput = document.querySelector("#console-expected-output");
const renderConsolePrompt = document.querySelector("#render-console-prompt");
const renderConsoleLocalTest = document.querySelector("#render-console-local-test");
const renderConsoleLocalProfileField = document.querySelector("#render-console-local-profile-field");
const renderConsoleLocalProfile = document.querySelector("#render-console-local-profile");
const renderConsoleQwenPromptField = document.querySelector("#render-console-qwen-prompt-field");
const renderConsoleQwenPrompt = document.querySelector("#render-console-qwen-prompt");
const renderConsoleCopyLocalApiParams = document.querySelector("#render-console-copy-local-api-params");
const renderConsoleLocalApiPopover = document.querySelector("#render-console-local-api-popover");
const renderConsoleLocalApiText = document.querySelector("#render-console-local-api-text");
const renderConsoleLocalApiCopy = document.querySelector("#render-console-local-api-copy");
const renderConsoleClearLocalTest = document.querySelector("#render-console-clear-local-test");
const renderConsoleLocalStatus = document.querySelector("#render-console-local-status");
const renderConsoleQwenWarnings = document.querySelector("#render-console-qwen-warnings");
const renderConsoleLocalTestRender = document.querySelector("#render-console-local-test-render");
const renderConsolePasteZone = document.querySelector("#render-console-paste-zone");
const renderConsoleFileInput = document.querySelector("#render-console-file-input");
const renderConsoleImagePreview = document.querySelector("#render-console-image-preview");
const renderConsoleSaveImage = document.querySelector("#render-console-save-image");
const renderConsoleSaveStatus = document.querySelector("#render-console-save-status");
const renderConsoleAnswerComment = document.querySelector("#render-console-answer-comment");
const renderConsoleRefinementRequired = document.querySelector("#render-console-refinement-required");
const renderConsoleRefinementFields = document.querySelector("#render-console-refinement-fields");
const renderConsoleRefinementCount = document.querySelector("#render-console-refinement-count");
const renderConsoleRefinementNote = document.querySelector("#render-console-refinement-note");
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
const manifestBodySection = document.querySelector("#manifest-body-section");
const manifestHeadHeading = document.querySelector("#manifest-head-heading");
const bodyReferenceSelect = document.querySelector("#body-reference-select");
const headshotReferenceSelect = document.querySelector("#headshot-reference-select");
const headshotUpload = document.querySelector("#headshot-upload");
const headshotPasteZone = document.querySelector("#headshot-paste-zone");
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
const identityKeySource = document.querySelector("#identity-key-source");
const identityKeyOriginal = document.querySelector("#identity-key-original");
const identityKeyPreview = document.querySelector("#identity-key-preview");
const costumeStatus = document.querySelector("#costume-status");
const costumeMessage = document.querySelector("#costume-message");
const costumeTableBody = document.querySelector("#costume-table tbody");
const costumeAddNew = document.querySelector("#costume-add-new");
const costumeDelete = document.querySelector("#costume-delete");
const costumeFormTitle = document.querySelector("#costume-form-title");
const costumeName = document.querySelector("#costume-name");
const costumeTemplateFileWrap = document.querySelector("#costume-template-file-wrap");
const costumeTemplateFile = document.querySelector("#costume-template-file");
const costumeCreate = document.querySelector("#costume-create");
const costumePreviewSection = document.querySelector("#costume-preview-section");
const costumePreview = document.querySelector("#costume-preview");
const costumeWizardDialog = document.querySelector("#costume-wizard-dialog");
const costumeWizardOpen = document.querySelector("#costume-wizard-open");
const costumeWizardClose = document.querySelector("#costume-wizard-close");
const costumeWizardContext = document.querySelector("#costume-wizard-context");
const costumeWizardMessage = document.querySelector("#costume-wizard-message");
const costumeWizardResume = document.querySelector("#costume-wizard-resume");
const costumeWizardResumeButton = document.querySelector("#costume-wizard-resume-button");
const costumeWizardName = document.querySelector("#costume-wizard-name");
const costumeWizardExtra = document.querySelector("#costume-wizard-extra");
const costumeWizardIntake = document.querySelector("#costume-wizard-intake");
const costumeWizardWorkspace = document.querySelector("#costume-wizard-workspace");
const costumeWizardCreate = document.querySelector("#costume-wizard-create");
const costumeWizardGenerate = document.querySelector("#costume-wizard-generate");
const costumeWizardQuestions = document.querySelector("#costume-wizard-questions");
const costumeWizardAnswer = document.querySelector("#costume-wizard-answer");
const costumeWizardMarkdown = document.querySelector("#costume-wizard-markdown");
const costumeWizardReview = document.querySelector("#costume-wizard-review");
const costumeWizardErrors = document.querySelector("#costume-wizard-errors");
const costumeWizardSave = document.querySelector("#costume-wizard-save");
const costumeWizardTest = document.querySelector("#costume-wizard-test");
const costumeWizardAccept = document.querySelector("#costume-wizard-accept");
const costumeWizardTestResult = document.querySelector("#costume-wizard-test-result");
const costumeWizardRefinement = document.querySelector("#costume-wizard-refinement");
const costumeWizardRefine = document.querySelector("#costume-wizard-refine");
const costumeWizardAbandon = document.querySelector("#costume-wizard-abandon");
let costumeWizardPollTimer = null;
const sceneAppearanceStatus = document.querySelector("#scene-appearance-status");
const sceneAppearanceMessage = document.querySelector("#scene-appearance-message");
const sceneAppearanceTableBody = document.querySelector("#scene-appearance-table tbody");
const sceneAppearanceAddNew = document.querySelector("#scene-appearance-add-new");
const sceneAppearanceFormTitle = document.querySelector("#scene-appearance-form-title");
const sceneAppearanceId = document.querySelector("#scene-appearance-id");
const sceneAppearanceName = document.querySelector("#scene-appearance-name");
const sceneAppearanceCostume = document.querySelector("#scene-appearance-costume");
const sceneAppearanceInstructions = document.querySelector("#scene-appearance-instructions");
const sceneAppearanceReferences = document.querySelector("#scene-appearance-references");
const sceneAppearanceSave = document.querySelector("#scene-appearance-save");
const sceneAppearancePreviewSection = document.querySelector("#scene-appearance-preview-section");
const sceneAppearancePreview = document.querySelector("#scene-appearance-preview");
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

























const storyGitWarning = document.querySelector("#story-git-warning");
const startupRecoveryStatus = document.querySelector("#startup-recovery-status");





















const sceneCandidateStatus = document.querySelector("#scene-candidate-status");
const sceneCandidateMessage = document.querySelector("#scene-candidate-message");
const sceneCandidateSource = document.querySelector("#scene-candidate-source");
const sceneCandidateFilter = document.querySelector("#scene-candidate-filter");
const sceneCandidateRefresh = document.querySelector("#scene-candidate-refresh");
const sceneCandidateSourceMeta = document.querySelector("#scene-candidate-source-meta");
const sceneCandidateList = document.querySelector("#scene-candidate-list");
const sceneCandidateDetail = document.querySelector("#scene-candidate-detail");



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






























































const fullscreenImageOverlay = document.createElement("dialog");
const builderImagePickerModal = document.querySelector("#builder-image-picker-modal");
const builderImagePickerClose = document.querySelector("#builder-image-picker-close");
const builderImagePickerCharacter = document.querySelector("#builder-image-picker-character");
const builderImagePickerEntity = document.querySelector("#builder-image-picker-entity");
const builderImagePickerVariant = document.querySelector("#builder-image-picker-variant");
const builderImagePickerSet = document.querySelector("#builder-image-picker-set");
const builderImagePickerFacet = document.querySelector("#builder-image-picker-facet");
const builderImagePickerMode = document.querySelector("#builder-image-picker-mode");
const builderImagePickerIncludeBase = document.querySelector("#builder-image-picker-include-base");
const builderImagePickerSource = document.querySelector("#builder-image-picker-source");
const builderImagePickerCategory = document.querySelector("#builder-image-picker-category");
const builderImagePickerStatusFilter = document.querySelector("#builder-image-picker-status");
const builderImagePickerSearch = document.querySelector("#builder-image-picker-search");
const builderImagePickerRefresh = document.querySelector("#builder-image-picker-refresh");
const builderImagePickerStatus = document.querySelector("#builder-image-picker-status");
const builderImagePickerTableBody = document.querySelector("#builder-image-picker-table tbody");
const builderImagePicker = {
  library: true,
  labelOnly: true,
  character: builderImagePickerCharacter,
  search: builderImagePickerSearch,
  includeBase: builderImagePickerIncludeBase,
  source: builderImagePickerSource,
  category: builderImagePickerCategory,
  statusFilter: builderImagePickerStatusFilter,
  status: builderImagePickerStatus,
  tableBody: builderImagePickerTableBody,
  rows: () => state.builderImagePickerReferences,
  setRows: (rows) => { state.builderImagePickerReferences = rows; },
  onSelect: async (item, mode = "asset") => {
    if (quickCharacterLibrarySelection) {
      const select = quickCharacterLibrarySelection;
      quickCharacterLibrarySelection = null;
      builderImagePickerModal.close();
      await select(item);
      return;
    }
  },
  onError: (error) => showActionMessage(error.message, "error"),
};
const ollamaModelControls = () => [
  settingAiAssetWorkflowModel,
  settingPromptCondenseModel,
  settingAiPromptAnalysisModel,
  settingAiImageDescriptionModel,
  settingImagePromptGenerationModel,
  settingCostumeWizardModel,
  settingQuickCharacterWizardModel,
  settingLocalBodyReferenceFaceGateModel,
  settingLocalBodyReferenceReviewModel,
];
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
const fullscreenCandidateLink = document.createElement("a");
fullscreenCandidateLink.className = "candidate-pending-overlay fullscreen-candidate-pending";
fullscreenCandidateLink.textContent = "Candidate Image Pending";
fullscreenCandidateLink.hidden = true;
const fullscreenCropBox = document.createElement("div");
fullscreenCropBox.className = "fullscreen-crop-box";
fullscreenCropBox.hidden = true;
fullscreenImageOverlay.append(
  fullscreenImageClose,
  fullscreenImagePrevious,
  fullscreenImage,
  fullscreenImageEmpty,
  fullscreenImageNext,
  fullscreenCandidateLink,
  fullscreenCropBox,
);
document.body.append(fullscreenImageOverlay);
const auxResourceMessage = document.querySelector("#aux-resource-message");
const entityLibrarySearch = document.querySelector("#entity-library-search");
const entityLibraryFilterEntity = document.querySelector("#entity-library-filter-entity");
const entityLibraryFilterType = document.querySelector("#entity-library-filter-type");
const entityLibraryFilterVariant = document.querySelector("#entity-library-filter-variant");
const entityLibraryFilterSet = document.querySelector("#entity-library-filter-set");
const entityLibraryFilterFacet = document.querySelector("#entity-library-filter-facet");
const entityLibraryFilterStatus = document.querySelector("#entity-library-filter-status");
const entityLibraryFilterOrigin = document.querySelector("#entity-library-filter-origin");
const entityLibraryIncludeObsolete = document.querySelector("#entity-library-include-obsolete");
const entityLibraryRefresh = document.querySelector("#entity-library-refresh");
const entityLibraryCount = document.querySelector("#entity-library-count");
const entityLibraryResults = document.querySelector("#entity-library-results");
const entityLibraryFile = document.querySelector("#entity-library-file");
const entityLibraryNewLabel = document.querySelector("#entity-library-new-label");
const entityLibraryGenerationPrompts = document.querySelector("#entity-library-generation-prompts");
const entityLibraryImportPrompt = document.querySelector("#entity-library-import-prompt");
const entityLibraryImportNegativePrompt = document.querySelector("#entity-library-import-negative-prompt");
const entityLibraryGeneratedEntity = document.querySelector("#entity-library-generated-entity");
const entityLibraryGeneratedRole = document.querySelector("#entity-library-generated-role");
const entityLibraryGeneratedProvenance = document.querySelector("#entity-library-generated-provenance");
const entityLibraryImport = document.querySelector("#entity-library-import");
const entityLibraryImportStatus = document.querySelector("#entity-library-import-status");
const entityLibraryPaste = document.querySelector("#entity-library-paste");
const entityLibraryEntityName = document.querySelector("#entity-library-entity-name");
const entityLibraryEntityType = document.querySelector("#entity-library-entity-type");
const entityLibraryEntityCreate = document.querySelector("#entity-library-entity-create");
const entityLibraryVariantEntity = document.querySelector("#entity-library-variant-entity");
const entityLibraryVariantName = document.querySelector("#entity-library-variant-name");
const entityLibraryVariantType = document.querySelector("#entity-library-variant-type");
const entityLibraryVariantCreate = document.querySelector("#entity-library-variant-create");
const entityLibraryRelationSource = document.querySelector("#entity-library-relation-source");
const entityLibraryRelationTarget = document.querySelector("#entity-library-relation-target");
const entityLibraryRelationType = document.querySelector("#entity-library-relation-type");
const entityLibraryRelationCreate = document.querySelector("#entity-library-relation-create");
const entityLibrarySetName = document.querySelector("#entity-library-set-name");
const entityLibrarySetType = document.querySelector("#entity-library-set-type");
const entityLibrarySetSelect = document.querySelector("#entity-library-set-select");
const entityLibrarySetCreate = document.querySelector("#entity-library-set-create");
const entityLibrarySetSave = document.querySelector("#entity-library-set-save");
const entityLibrarySetDelete = document.querySelector("#entity-library-set-delete");
const entityLibraryPrevious = document.querySelector("#entity-library-previous");
const entityLibraryNext = document.querySelector("#entity-library-next");
const entityLibraryPageStatus = document.querySelector("#entity-library-page-status");
const entityLibraryEditorTitle = document.querySelector("#entity-library-editor-title");
const entityLibraryPreview = document.querySelector("#entity-library-preview");
const entityLibraryEditLabel = document.querySelector("#entity-library-edit-label");
const entityLibraryEditPrompt = document.querySelector("#entity-library-edit-prompt");
const entityLibraryEditNegativePrompt = document.querySelector("#entity-library-edit-negative-prompt");
const entityLibraryGeneratePrompt = document.querySelector("#entity-library-generate-prompt");
const entityLibraryPromptStatus = document.querySelector("#entity-library-prompt-status");
const entityLibraryGenerateIdentity = document.querySelector("#entity-library-generate-identity");
const entityLibraryIdentityStatus = document.querySelector("#entity-library-identity-status");
const entityLibraryModifyGenerated = document.querySelector("#entity-library-modify-generated");
const entityLibraryModifyStatus = document.querySelector("#entity-library-modify-status");
const entityLibraryEditNotes = document.querySelector("#entity-library-edit-notes");
const entityLibraryEditStatus = document.querySelector("#entity-library-edit-status");
const entityLibraryEditEntities = document.querySelector("#entity-library-edit-entities");
const entityLibraryEditSets = document.querySelector("#entity-library-edit-sets");
const entityLibraryEditFacets = document.querySelector("#entity-library-edit-facets");
const entityLibraryEditTags = document.querySelector("#entity-library-edit-tags");
const entityLibraryEditIdentity = document.querySelector("#entity-library-edit-identity");
const entityLibraryEditCostume = document.querySelector("#entity-library-edit-costume");
const entityLibraryEditReference = document.querySelector("#entity-library-edit-reference");
const entityLibrarySave = document.querySelector("#entity-library-save");
const entityLibraryReplacementFile = document.querySelector("#entity-library-replacement-file");
const entityLibraryReplacementPaste = document.querySelector("#entity-library-replacement-paste");
const entityLibraryReplace = document.querySelector("#entity-library-replace");
const entityLibraryDelete = document.querySelector("#entity-library-delete");
const entityLibraryBack = document.querySelector("#entity-library-back");
const entityLibraryEditorStateMessage = document.querySelector("#entity-library-editor-state");
const entityLibraryRetryLoad = document.querySelector("#entity-library-retry-load");
const entityLibraryUsages = document.querySelector("#entity-library-usages");
const entityLibraryLogicalReferences = document.querySelector("#entity-library-logical-references");
const entityLibraryDescriptorOwnerType = document.querySelector("#entity-library-descriptor-owner-type");
const entityLibraryDescriptorOwner = document.querySelector("#entity-library-descriptor-owner");
const entityLibraryDescriptorType = document.querySelector("#entity-library-descriptor-type");
const entityLibraryDescriptorText = document.querySelector("#entity-library-descriptor-text");
const entityLibraryDescriptorSave = document.querySelector("#entity-library-descriptor-save");
let entityLibrarySelectedAsset = null;
let entityLibraryMetadata = { entities: [], variants: [], sets: [] };
let entityLibraryPageOffset = 0;
let entityLibraryTotal = 0;
let entityLibraryPageItemCount = 0;
let entityLibraryCurrentView = "search";
let entityLibraryMergePreview = null;
let entityLibraryOrganizerSelectedId = "";
let entityLibrarySavedSnapshot = "";
let entityLibraryEditorState = "idle";
let entityLibrarySavePromise = null;
let entityLibraryLoadingAssetId = "";
let entityLibrarySearchGeneration = 0;
let entityLibrarySearchStale = true;
const ENTITY_LIBRARY_PAGE_SIZE = 10;
const entityLibraryOrganizer = document.querySelector("#entity-library-organizer");
const entityLibrarySearchForm = document.querySelector("#entity-library-search-form");
const entityLibraryClearFilters = document.querySelector("#entity-library-clear-filters");
const entityLibraryActiveFilterCount = document.querySelector("#entity-library-active-filter-count");
const entityLibraryImportDialog = document.querySelector("#entity-library-import-dialog");
const entityLibraryImportDialogContent = document.querySelector("#entity-library-import-dialog-content");
const entityLibraryImportPreview = document.querySelector("#entity-library-import-preview");
const entityLibraryMergeDialog = document.querySelector("#entity-library-merge-dialog");
const entityLibraryMergeContent = document.querySelector("#entity-library-merge-content");
const entityLibraryMergeConfirm = document.querySelector("#entity-library-merge-confirm");
const imageCatalogSearch = document.querySelector("#image-catalog-search");
const imageCatalogSource = document.querySelector("#image-catalog-source");
const imageCatalogCategory = document.querySelector("#image-catalog-category");
const imageCatalogStatus = document.querySelector("#image-catalog-status");
const imageCatalogCollection = document.querySelector("#image-catalog-collection");
const imageCatalogKeyword = document.querySelector("#image-catalog-keyword");
const imageCatalogCharacter = document.querySelector("#image-catalog-character");
const imageCatalogPhase = document.querySelector("#image-catalog-phase");
const imageCatalogCostume = document.querySelector("#image-catalog-costume");
const imageCatalogPipeline = document.querySelector("#image-catalog-pipeline");
const imageCatalogStory = document.querySelector("#image-catalog-story");
const imageCatalogScene = document.querySelector("#image-catalog-scene");
const imageCatalogSubscene = document.querySelector("#image-catalog-subscene");
const imageCatalogIncludeBase = document.querySelector("#image-catalog-include-base");
const imageCatalogRefresh = document.querySelector("#image-catalog-refresh");
const imageCatalogClearFilters = document.querySelector("#image-catalog-clear-filters");
const imageCatalogCount = document.querySelector("#image-catalog-count");
const imageCatalogGrid = document.querySelector("#image-catalog-grid");
const imageCatalogBulk = document.querySelector("#image-catalog-bulk");
const imageCatalogEditorTitle = document.querySelector("#image-catalog-editor-title");
const imageCatalogPreview = document.querySelector("#image-catalog-preview");
const imageCatalogSourceDetail = document.querySelector("#image-catalog-source-detail");
const imageCatalogEditCategory = document.querySelector("#image-catalog-edit-category");
const imageCatalogEditCollections = document.querySelector("#image-catalog-edit-collections");
const imageCatalogEditKeywords = document.querySelector("#image-catalog-edit-keywords");
const imageCatalogIdentityMode = document.querySelector("#image-catalog-identity-mode");
const imageCatalogIdentityText = document.querySelector("#image-catalog-identity-text");
const imageCatalogCostumeMode = document.querySelector("#image-catalog-costume-mode");
const imageCatalogCostumeText = document.querySelector("#image-catalog-costume-text");
const imageCatalogSave = document.querySelector("#image-catalog-save");
const imageCatalogAi = document.querySelector("#image-catalog-ai");
const imageCatalogAiCheck = document.querySelector("#image-catalog-ai-check");
const imageCatalogAiStatus = document.querySelector("#image-catalog-ai-status");
const imageCatalogAiReview = document.querySelector("#image-catalog-ai-review");
const imageCatalogAiIdentity = document.querySelector("#image-catalog-ai-identity");
const imageCatalogAiCostume = document.querySelector("#image-catalog-ai-costume");
const imageCatalogAiApprove = document.querySelector("#image-catalog-ai-approve");
const imageCatalogAiReject = document.querySelector("#image-catalog-ai-reject");
const imageCatalogNewCollection = document.querySelector("#image-catalog-new-collection");
const imageCatalogAddCollection = document.querySelector("#image-catalog-add-collection");
const imageCatalogNewKeyword = document.querySelector("#image-catalog-new-keyword");
const imageCatalogAddKeyword = document.querySelector("#image-catalog-add-keyword");
const imageCatalogOrganizationList = document.querySelector("#image-catalog-organization-list");
const imageCatalogSelectedCount = document.querySelector("#image-catalog-selected-count");
const imageCatalogBulkCategory = document.querySelector("#image-catalog-bulk-category");
const imageCatalogBulkSet = document.querySelector("#image-catalog-bulk-set");
const imageCatalogBulkCollections = document.querySelector("#image-catalog-bulk-collections");
const imageCatalogBulkKeywords = document.querySelector("#image-catalog-bulk-keywords");
const imageCatalogBulkApply = document.querySelector("#image-catalog-bulk-apply");
const imageCatalogBulkClear = document.querySelector("#image-catalog-bulk-clear");
const imageCatalogImportZone = document.querySelector("#image-catalog-import-zone");
const imageCatalogImportFile = document.querySelector("#image-catalog-import-file");
const imageCatalogImportLabel = document.querySelector("#image-catalog-import-label");
const imageCatalogImportCategory = document.querySelector("#image-catalog-import-category");
const imageCatalogImportSet = document.querySelector("#image-catalog-import-set");
const imageCatalogImportSave = document.querySelector("#image-catalog-import-save");
const imageCatalogImportStatus = document.querySelector("#image-catalog-import-status");
const imageCatalogSetSelect = document.querySelector("#image-catalog-set-select");
const imageCatalogSetLabel = document.querySelector("#image-catalog-set-label");
const imageCatalogSetIdentity = document.querySelector("#image-catalog-set-identity");
const imageCatalogSetCostume = document.querySelector("#image-catalog-set-costume");
const imageCatalogSetNew = document.querySelector("#image-catalog-set-new");
const imageCatalogSetSave = document.querySelector("#image-catalog-set-save");
const imageCatalogSetDelete = document.querySelector("#image-catalog-set-delete");
const imageCatalogManagedActions = document.querySelector("#image-catalog-managed-actions");
const imageCatalogManagedLabel = document.querySelector("#image-catalog-managed-label");
const imageCatalogManagedSet = document.querySelector("#image-catalog-managed-set");
const imageCatalogAdd = document.querySelector("#image-catalog-add");
const imageCatalogAddUpload = document.querySelector("#image-catalog-add-upload");
const imageCatalogAddZone = document.querySelector("#image-catalog-add-zone");
const imageCatalogAddFile = document.querySelector("#image-catalog-add-file");
const imageCatalogAddLabel = document.querySelector("#image-catalog-add-label");
const imageCatalogAddStatus = document.querySelector("#image-catalog-add-status");
const imageCatalogAddSubmit = document.querySelector("#image-catalog-add-submit");
const imageCatalogReplaceUpload = document.querySelector("#image-catalog-replace-upload");
const imageCatalogReplaceZone = document.querySelector("#image-catalog-replace-zone");
const imageCatalogReplaceFile = document.querySelector("#image-catalog-replace-file");
const imageCatalogReplaceStatus = document.querySelector("#image-catalog-replace-status");
const imageCatalogReplaceSubmit = document.querySelector("#image-catalog-replace-submit");
const imageCatalogReplace = document.querySelector("#image-catalog-replace");
const imageCatalogDelete = document.querySelector("#image-catalog-delete");
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

class RequestCancelledError extends Error {
  constructor() {
    super("Request cancelled");
    this.name = "RequestCancelledError";
  }
}

function isRequestCancellation(error) {
  return error?.name === "AbortError" || error?.name === "RequestCancelledError";
}

function beginPageLoad(page) {
  state.pageController?.abort();
  for (const controller of Object.values(state.selectionControllers)) controller.abort();
  state.selectionControllers = {};
  state.pageGeneration += 1;
  state.pageController = new AbortController();
  return { page, generation: state.pageGeneration, controller: state.pageController };
}

function pageLoadIsCurrent(load) {
  return load.generation === state.pageGeneration && !load.controller.signal.aborted;
}

function beginSelection(kind) {
  state.selectionControllers[kind]?.abort();
  const generation = (state.selectionGenerations[kind] || 0) + 1;
  const controller = new AbortController();
  state.selectionGenerations[kind] = generation;
  state.selectionControllers[kind] = controller;
  return { kind, generation, controller };
}

function selectionIsCurrent(selection) {
  return selection.generation === state.selectionGenerations[selection.kind]
    && state.selectionControllers[selection.kind] === selection.controller
    && !selection.controller.signal.aborted;
}

function setBusy(container, busy) {
  if (!container) return;
  const next = Math.max(0, (busyCounts.get(container) || 0) + (busy ? 1 : -1));
  busyCounts.set(container, next);
  if (next) container.setAttribute("aria-busy", "true");
  else container.removeAttribute("aria-busy");
}

async function fetchJson(url, options = {}) {
  const busyTarget = document.querySelector("main > .page.active");
  const { bindToPage = true, pageGeneration = state.pageGeneration, ...fetchOptions } = options;
  if (bindToPage && !fetchOptions.signal && state.pageController) {
    fetchOptions.signal = state.pageController.signal;
  }
  setBusy(busyTarget, true);
  const requestUniverse = state.universeId;
  try {
    const headers = new Headers(fetchOptions.headers || {});
    if (requestUniverse) headers.set("X-Zet-Universe", requestUniverse);
    fetchOptions.headers = headers;
    const response = await fetch(url, fetchOptions);
    if (bindToPage && pageGeneration !== state.pageGeneration) throw new RequestCancelledError();
    if (requestUniverse && requestUniverse !== state.universeId) throw new RequestCancelledError();
    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      let structuredDetail = null;
      try {
        const payload = await response.json();
        if (Array.isArray(payload.detail)) {
          detail = payload.detail
            .map((item) => item?.msg ? `${(item.loc || []).join(".")}: ${item.msg}` : JSON.stringify(item))
            .join("; ");
        } else if (payload.detail && typeof payload.detail === "object") {
          structuredDetail = payload.detail;
          detail = JSON.stringify(payload.detail);
        } else {
          detail = payload.detail || detail;
        }
      } catch {
        // Keep HTTP detail.
      }
      const error = new Error(detail);
      if (structuredDetail) error.detail = structuredDetail;
      throw error;
    }
    const payload = await response.json();
    if (bindToPage && pageGeneration !== state.pageGeneration) throw new RequestCancelledError();
    if (requestUniverse && requestUniverse !== state.universeId) throw new RequestCancelledError();
    return payload;
  } catch (error) {
    if (fetchOptions.signal?.aborted || isRequestCancellation(error)) throw new RequestCancelledError();
    throw error;
  } finally {
    setBusy(busyTarget, false);
  }
}

function fileUrl(path, cacheKey = "") {
  const params = new URLSearchParams({ path });
  if (state.universeId) params.set("universe_id", state.universeId);
  if (cacheKey) {
    params.set("v", cacheKey);
  }
  return `/api/file?${params.toString()}`;
}

function sceneImageReviewUrl(storySlug, sceneSlug) {
  return `?${new URLSearchParams({
    page: "render-review",
    review_kind: "scene",
    story_slug: storySlug,
    scene_slug: sceneSlug,
  }).toString()}`;
}

function setCandidatePendingLink(link, document) {
  const pending = Boolean(document?.candidate_pending);
  link.hidden = !pending;
  if (pending) {
    link.href = sceneImageReviewUrl(document.story?.slug, document.scene?.slug);
  } else {
    link.removeAttribute("href");
  }
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

function setImageGenerationMode(mode) {
  imageGenerationMode = mode;
  const editing = mode === "img2img";
  imageGenerationTxt2img.setAttribute("aria-pressed", String(!editing));
  imageGenerationImg2img.setAttribute("aria-pressed", String(editing));
  imageGenerationTxt2img.classList.toggle("primary-action", !editing);
  imageGenerationImg2img.classList.toggle("primary-action", editing);
  imageGenerationReferenceSlotsElement.hidden = !editing;
}

function renderImageGenerationReferenceSlots() {
  imageGenerationReferenceList.replaceChildren();
  for (let index = 0; index < IMAGE_GENERATION_REFERENCE_COUNT; index += 1) {
    const reference = imageGenerationReferenceSlots[index] || {label: "", data: ""};
    const slot = document.createElement("div");
    slot.className = "image-generation-reference-slot";
    if (index === 0) slot.id = "image-generation-reference-field";
    const label = document.createElement("label");
    label.textContent = `Prompt label · Image ${index + 1}`;
    const labelInput = document.createElement("input");
    labelInput.type = "text";
    labelInput.maxLength = 120;
    labelInput.placeholder = index === 0 ? "e.g. the character's face" : "e.g. the blue embroidered coat";
    labelInput.value = reference.label || "";
    labelInput.setAttribute("aria-label", `Prompt label for reference image ${index + 1}`);
    labelInput.addEventListener("input", () => {
      imageGenerationReferenceSlots[index].label = labelInput.value;
      saveImageGenerationState();
    });
    label.append(labelInput);
    const controls = document.createElement("div");
    controls.className = "image-generation-reference-controls";
    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = "image/png,image/jpeg,image/webp";
    if (index === 0) fileInput.id = "image-generation-reference";
    fileInput.setAttribute("aria-label", `Choose reference image ${index + 1}`);
    fileInput.addEventListener("change", async () => {
      const file = fileInput.files[0];
      if (!file || !file.type.startsWith("image/")) return;
      try {
        imageGenerationReferenceSlots[index].label ||= `image ${index + 1}`;
        imageGenerationReferenceSlots[index].data = await readImageGenerationReference(file);
        renderImageGenerationReferenceSlots();
        await saveImageGenerationReferences();
        saveImageGenerationState();
      } catch (error) {
        showMessageElement(imageGenerationMessage, error.message || "Unable to save the reference image.", "error");
      }
    });
    controls.append(fileInput);
    if (reference.data) {
      const preview = document.createElement("img");
      preview.src = reference.data;
      preview.alt = `Reference image ${index + 1}: ${reference.label || "unlabeled"}`;
      preview.className = "image-generation-reference-thumb";
      controls.append(preview);
      const clear = document.createElement("button");
      clear.type = "button";
      clear.textContent = "Remove";
      clear.addEventListener("click", async () => {
        imageGenerationReferenceSlots[index].data = "";
        renderImageGenerationReferenceSlots();
        await saveImageGenerationReferences();
        saveImageGenerationState();
      });
      controls.append(clear);
    } else {
      const paste = document.createElement("div");
      paste.className = "paste-zone image-generation-reference-paste";
      paste.tabIndex = 0;
      paste.setAttribute("role", "button");
      paste.setAttribute("aria-label", `Paste reference image ${index + 1}`);
      paste.textContent = "Click to select, then press Ctrl+V to paste";
      paste.addEventListener("click", () => paste.focus());
      paste.addEventListener("paste", async (event) => {
        const imageItem = Array.from(event.clipboardData?.items || []).find((item) => item.type.startsWith("image/"));
        const file = imageItem?.getAsFile();
        if (!file) return;
        event.preventDefault();
        try {
          imageGenerationReferenceSlots[index].label ||= `image ${index + 1}`;
          imageGenerationReferenceSlots[index].data = await readImageGenerationReference(file);
          renderImageGenerationReferenceSlots();
          await saveImageGenerationReferences();
          saveImageGenerationState();
        } catch (error) {
          showMessageElement(imageGenerationMessage, error.message || "Unable to save the reference image.", "error");
        }
      });
      controls.append(paste);
    }
    slot.append(label, controls);
    imageGenerationReferenceList.append(slot);
  }
}

function saveImageGenerationState() {
  try {
    window.localStorage.setItem(`${IMAGE_GENERATION_STORAGE_KEY}:${state.universeId}`, JSON.stringify({
      mode: imageGenerationMode,
      prompt: imageGenerationPrompt.value,
      negativePrompt: imageGenerationNegative.value,
      width: imageGenerationWidth.value,
      height: imageGenerationHeight.value,
      referenceLabels: imageGenerationReferenceSlots.map((reference) => reference.label),
      sourceAssetId: imageGenerationSource.dataset.assetId || "",
      sourceChecksum: imageGenerationSource.dataset.checksum || "",
    }));
  } catch (error) {
    showMessageElement(imageGenerationMessage, "Unable to save Image Generation state in this browser.", "warning");
  }
}

function openImageGenerationDatabase() {
  return new Promise((resolve, reject) => {
    const request = window.indexedDB.open("zet-image-generation", 1);
    request.addEventListener("upgradeneeded", () => request.result.createObjectStore("state"), { once: true });
    request.addEventListener("success", () => resolve(request.result), { once: true });
    request.addEventListener("error", () => reject(request.error), { once: true });
  });
}

async function saveImageGenerationReferences() {
  const database = await openImageGenerationDatabase();
  await new Promise((resolve, reject) => {
    const transaction = database.transaction("state", "readwrite");
    const store = transaction.objectStore("state");
    imageGenerationReferenceSlots.forEach((reference, index) => {
      const key = `${state.universeId}:reference-${index}`;
      if (reference.data) store.put(reference.data, key);
      else store.delete(key);
    });

    transaction.addEventListener("complete", resolve, { once: true });
    transaction.addEventListener("error", () => reject(transaction.error), { once: true });
  });
  database.close();
}

async function restoreImageGenerationInputs() {
  imageGenerationSlots = Array(8).fill(null);
  imageGenerationSelectedSlot = -1; imageGenerationJobIds = []; imageGenerationJobs.clear();
  imageGenerationPrompt.value = ""; imageGenerationNegative.value = "";
  imageGenerationSource.dataset.assetId = ""; imageGenerationSource.dataset.checksum = ""; imageGenerationSource.hidden = true;
  imageGenerationReferenceSlots = Array.from({length: IMAGE_GENERATION_REFERENCE_COUNT}, () => ({label: "", data: ""}));
  let saved = null;
  try {
    saved = JSON.parse(window.localStorage.getItem(`${IMAGE_GENERATION_STORAGE_KEY}:${state.universeId}`) || window.localStorage.getItem(IMAGE_GENERATION_STORAGE_KEY) || "null");
  } catch {
    window.localStorage.removeItem(`${IMAGE_GENERATION_STORAGE_KEY}:${state.universeId}`);
    return;
  }
  if (saved && typeof saved === "object") {
    imageGenerationPrompt.value = saved.prompt || "";
    imageGenerationNegative.value = saved.negativePrompt || "";
    if (saved.width) imageGenerationWidth.value = saved.width;
    if (saved.height) imageGenerationHeight.value = saved.height;
    if (Array.isArray(saved.referenceLabels)) {
      imageGenerationReferenceSlots.forEach((reference, index) => { reference.label = saved.referenceLabels[index] || ""; });
    } else if (saved.referenceName) {
      imageGenerationReferenceSlots[0].label = saved.referenceName;
    }
    if (Array.isArray(saved.slots) && saved.slots.length === IMAGE_GENERATION_SLOT_COUNT) {
      imageGenerationSlots = saved.slots;
      imageGenerationSelectedSlot = Number.isInteger(saved.selectedSlot) ? saved.selectedSlot : -1;
      imageGenerationJobIds = Array.isArray(saved.jobIds) ? saved.jobIds : [];
    } else if (saved.requestId) {
      imageGenerationSlots = Array.from({length: IMAGE_GENERATION_SLOT_COUNT}, (_, index) =>
        index < 4 ? {requestId: saved.requestId, index} : null);
      imageGenerationJobIds = [saved.requestId];
    }
    imageGenerationSource.dataset.assetId = saved.sourceAssetId || "";
    imageGenerationSource.dataset.checksum = saved.sourceChecksum || "";
    imageGenerationSource.hidden = !saved.sourceAssetId;
    if (saved.sourceAssetId) imageGenerationSource.textContent = "Updating an image from the Image Inventory";
    setImageGenerationMode(saved.mode === "img2img" ? "img2img" : "txt2img");
  }
  try {
    const database = await openImageGenerationDatabase();
    const store = database.transaction("state", "readonly").objectStore("state");
    imageGenerationReferenceSlots = await Promise.all(imageGenerationReferenceSlots.map((reference, index) => new Promise((resolve, reject) => {
      const request = store.get(`${state.universeId}:reference-${index}`);
      request.addEventListener("success", () => resolve({...reference, data: request.result || ""}), { once: true });
      request.addEventListener("error", () => reject(request.error), { once: true });
    })));
    if (!imageGenerationReferenceSlots.some((reference) => reference.data)) {
      const legacy = await new Promise((resolve, reject) => {
        const request = store.get(`${state.universeId}:reference`);
        request.addEventListener("success", () => resolve(request.result || ""), { once: true });
        request.addEventListener("error", () => reject(request.error), { once: true });
      });
      if (legacy) imageGenerationReferenceSlots[0].data = legacy;
    }
    database.close();
    renderImageGenerationReferenceSlots();
  } catch {
    showMessageElement(imageGenerationMessage, "Unable to restore the saved reference image in this browser.", "warning");
  }
}

let imageGenerationWorkspaceTimer = null;
let imageGenerationWorkspacePolling = false;
let imageGenerationWorkspaceUniverse = "";
let imageGenerationWorkspaceSignature = "";
let imageGenerationWorkspaceBusy = false;

function applyImageGenerationWorkspace(board) {
  imageGenerationSlots = board.slots;
  imageGenerationSelectedSlot = board.selected_slot ?? -1;
  imageGenerationJobIds = [...new Set(board.slots.filter(Boolean).map(item => item.requestId))];
  imageGenerationJobs.clear();
  (board.jobs || []).forEach(job => imageGenerationJobs.set(job.request_id, {...job, images: (job.images || []).map(image => ({...image, url: `${image.url}${image.url.includes("?") ? "&" : "?"}universe_id=${encodeURIComponent(state.universeId)}`}))}));
  imageGenerationWorkspaceBusy = board.busy;
  const signature = JSON.stringify(board);
  if (signature !== imageGenerationWorkspaceSignature) {
    imageGenerationWorkspaceSignature = signature;
    renderImageGenerationStatus();
  }
}

async function restoreImageGenerationJob() {
  const universe = state.universeId;
  if (imageGenerationWorkspaceUniverse !== universe) {
    imageGenerationWorkspaceSignature = "";
    let legacy = null;
    try { legacy = JSON.parse(window.localStorage.getItem(IMAGE_GENERATION_STORAGE_KEY) || "null"); } catch { /* Ignore invalid historical browser state. */ }
    const board = await fetchJson("/api/image-generation/workspace/import", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({slots: legacy?.slots || imageGenerationSlots, selected_slot: legacy?.selectedSlot ?? -1})});
    applyImageGenerationWorkspace(board);
    imageGenerationWorkspaceUniverse = universe;
  } else await pollImageGenerationWorkspace();
  clearInterval(imageGenerationWorkspaceTimer);
  imageGenerationWorkspaceTimer = setInterval(() => void pollImageGenerationWorkspace(), 2000);
}

async function pollImageGenerationWorkspace() {
  if (imageGenerationWorkspacePolling || imageGenerationPending || !document.querySelector("#image-generation-page").classList.contains("active")) return;
  imageGenerationWorkspacePolling = true;
  try { applyImageGenerationWorkspace(await fetchJson("/api/image-generation/workspace")); }
  catch (error) { if (!isRequestCancellation(error)) showMessageElement(imageGenerationMessage, `Unable to check renders: ${error.message}. Retrying automatically.`, "error"); }
  finally { imageGenerationWorkspacePolling = false; }
}

async function imageGenerationSlotAction(operation, slot, inputs) {
  if (imageGenerationPending) return;
  imageGenerationPending = true;
  renderImageGenerationStatus();
  try {
    const count = Number(document.querySelector("#image-generation-count").value);
    const board = await fetchJson(`/api/image-generation/workspace/${operation}`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({...(slot === undefined ? {} : {slot: slot + 1, expected_assignment: imageGenerationSlots[slot]}), count, ...(inputs ? {inputs} : {})})});
    applyImageGenerationWorkspace(board);
    showMessageElement(imageGenerationMessage, "", "info");
  } catch (error) { if (!isRequestCancellation(error)) showMessageElement(imageGenerationMessage, error.message, "error"); }
  finally { imageGenerationPending = false; renderImageGenerationStatus(); }
}

function readImageGenerationReference(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(String(reader.result || "")), { once: true });
    reader.addEventListener("error", () => reject(new Error("Unable to read the reference image.")), { once: true });
    reader.readAsDataURL(file);
  });
}

function imageGenerationDimensionFromSource(value) {
  const dimension = Number(value);
  if (!Number.isFinite(dimension) || dimension <= 0) return null;
  return Math.min(4096, Math.max(256, Math.round(dimension / 32) * 32));
}

async function modifyEntityLibraryImageWithGenerator() {
  const asset = entityLibrarySelectedAsset;
  if (!asset || asset.origin === "pipeline" || asset.status === "archived") return;
  try {
    const response = await fetch(fileUrl(asset.image_path, asset.checksum));
    if (!response.ok) throw new Error("Unable to read the selected inventory image.");
    const blob = await response.blob();
    const data = await readImageGenerationReference(new File([blob], asset.file_name, { type: asset.mime_type }));
    await runGuardedTransition(async () => {
      await loadImageGenerationOptions();
      imageGenerationReview.close();
      imageGenerationSource.textContent = "Updating " + (asset.label || asset.file_name);
      imageGenerationSource.hidden = false;
      imageGenerationSource.dataset.assetId = asset.asset_id;
      imageGenerationSource.dataset.checksum = asset.checksum;
      imageGenerationReferenceSlots = Array.from({length: IMAGE_GENERATION_REFERENCE_COUNT}, () => ({label: "", data: ""}));
      imageGenerationReferenceSlots[0] = {label: "source image", data};
      renderImageGenerationReferenceSlots();
      imageGenerationPrompt.value = asset.prompt || "";
      imageGenerationNegative.value = asset.negative_prompt || "";
      const sourceWidth = imageGenerationDimensionFromSource(asset.width);
      const sourceHeight = imageGenerationDimensionFromSource(asset.height);
      if (sourceWidth) imageGenerationWidth.value = sourceWidth;
      if (sourceHeight) imageGenerationHeight.value = sourceHeight;
      setImageGenerationMode("img2img");
      saveImageGenerationState();
      await saveImageGenerationReferences();
      await activatePage("image-generation", { skipAutosave: true });
    });
  } catch (error) {
    entityLibraryModifyStatus.textContent = error.message;
  }
}

function imageGenerationResult(slotIndex) {
  const assignment = imageGenerationSlots[slotIndex];
  const job = assignment && imageGenerationJobs.get(assignment.requestId);
  const image = job?.images?.find((item) => item.index === assignment.index);
  return image ? {assignment, job, image} : null;
}

function imageGenerationReviewableSlots() {
  return imageGenerationSlots.map((_, index) => index).filter((index) => imageGenerationResult(index));
}

function renderImageGenerationReview() {
  if (!imageGenerationReview.open) return;
  const slots = imageGenerationReviewableSlots();
  if (!slots.includes(imageGenerationReviewIndex)) { imageGenerationReview.close(); return; }
  const {job, image} = imageGenerationResult(imageGenerationReviewIndex);
  const position = slots.indexOf(imageGenerationReviewIndex);
  imageGenerationReviewImage.src = image.url;
  imageGenerationReviewImage.alt = `Generated image in slot ${imageGenerationReviewIndex + 1}`;
  imageGenerationReviewCount.textContent = `Slot ${imageGenerationReviewIndex + 1} · ${position + 1} of ${slots.length}`;
  imageGenerationReviewPrompt.textContent = job.prompt || "";
  imageGenerationReviewNegative.textContent = job.negative_prompt || "";
  imageGenerationReviewPrevious.disabled = position === 0;
  imageGenerationReviewNext.disabled = position === slots.length - 1;
  imageGenerationReviewSelect.textContent = imageGenerationSelectedSlot === imageGenerationReviewIndex ? "Unselect" : "Select";
  imageGenerationReviewRetry.disabled = imageGenerationPending || imageGenerationSelectedSlot === imageGenerationReviewIndex;
  imageGenerationReviewClear.disabled = imageGenerationReviewRetry.disabled;
  imageGenerationReviewRetry.title = imageGenerationSelectedSlot === imageGenerationReviewIndex ? "Unselect this image before regenerating it." : "";
  imageGenerationReviewClear.title = imageGenerationSelectedSlot === imageGenerationReviewIndex ? "Unselect this image before clearing it." : "";
  const add = document.querySelector("#image-generation-review-add");
  if (!add.contains(document.activeElement)) add.replaceChildren(window.ZetRenderSlots.countControl(imageGenerationSlots.filter(item => !item).length, count => {
    document.querySelector("#image-generation-count").value = count;
    void submitImageGenerationForSlots();
  }, {disabled: imageGenerationPending}));
}

function openImageGenerationReview(slotIndex) {
  imageGenerationReviewIndex = slotIndex;
  if (!imageGenerationReview.open) imageGenerationReview.showModal();
  renderImageGenerationReview();
}

async function openImageGenerationImportDialog() {
  const result = imageGenerationResult(imageGenerationSelectedSlot);
  if (!result) return;
  const {assignment, job, image} = result;
  entityLibraryImportGeneration = { requestId: assignment.requestId, index: assignment.index };
  state.entityLibraryImportBlob = null;
  entityLibraryFile.value = "";
  entityLibraryNewLabel.value = (job.prompt || "").trim().slice(0, 80) || "Generated image";
  entityLibraryGeneratedProvenance.value = "Image Generation job " + assignment.requestId + ", result " + (assignment.index + 1);
  entityLibraryGenerationPrompts.hidden = false;
  entityLibraryImportPrompt.textContent = job.prompt || "";
  entityLibraryImportNegativePrompt.textContent = job.negative_prompt || "";
  entityLibraryPaste.textContent = "Using selected Image Generation result";
  entityLibraryImportStatus.textContent = "";
  entityLibraryImport.disabled = !entityLibraryNewLabel.value.trim();
  entityLibraryImportPreview.src = image.url;
  entityLibraryImportPreview.hidden = false;
  await activatePage("auxiliary-resources", { skipAutosave: true });
  entityLibraryImportDialog.showModal();
}

async function generateEntityImagePrompt() {
  const asset = entityLibrarySelectedAsset;
  if (!asset) return;
  const editorSelectionController = state.selectionControllers["entity-library-asset"];
  const previousPrompt = entityLibraryEditPrompt.value;
  const previousNegative = entityLibraryEditNegativePrompt.value;
  entityLibraryGeneratePrompt.disabled = true;
  entityLibraryPromptStatus.textContent = "Analyzing image…";
  try {
    const started = await fetchJson("/api/entity-library/assets/" + encodeURIComponent(asset.asset_id) + "/generate-prompt", { method: "POST" });
    let job = started;
    while (job.status === "RUNNING") {
      await new Promise((resolve) => setTimeout(resolve, 650));
      job = await fetchJson("/api/entity-library/prompt-generation/" + encodeURIComponent(started.job_id));
    }
    if (job.status !== "COMPLETE") throw new Error(job.error || "Image prompt generation failed.");
    if (entityLibrarySelectedAsset?.asset_id !== asset.asset_id
      || state.selectionControllers["entity-library-asset"] !== editorSelectionController
      || editorSelectionController?.signal.aborted) return;
    if (entityLibraryEditPrompt.value === previousPrompt && !previousPrompt.trim()) {
      entityLibraryEditPrompt.value = job.draft.prompt || "";
    }
    if (entityLibraryEditNegativePrompt.value === previousNegative && !previousNegative.trim()) {
      entityLibraryEditNegativePrompt.value = job.draft.negative_prompt || "";
    }
    entityLibraryPromptStatus.textContent = "Draft added to unchanged empty prompt fields. Save image to keep it.";
  } catch (error) {
    if (entityLibrarySelectedAsset?.asset_id === asset.asset_id
      && state.selectionControllers["entity-library-asset"] === editorSelectionController) {
      entityLibraryPromptStatus.textContent = error.message;
    }
  } finally {
    if (entityLibraryEditorState === "ready" && entityLibrarySelectedAsset?.asset_id === asset.asset_id
      && state.selectionControllers["entity-library-asset"] === editorSelectionController) {
      entityLibraryGeneratePrompt.disabled = Boolean(entityLibraryEditPrompt.value.trim() && entityLibraryEditNegativePrompt.value.trim());
    }
  }
}

async function generateEntityIdentity() {
  const asset = entityLibrarySelectedAsset;
  if (!asset) return;
  const editorSelectionController = state.selectionControllers["entity-library-asset"];
  const previousText = entityLibraryEditIdentity.value;
  entityLibraryGenerateIdentity.disabled = true;
  entityLibraryIdentityStatus.textContent = "Analyzing image with Luna…";
  try {
    const started = await fetchJson(`/api/entity-library/assets/${encodeURIComponent(asset.asset_id)}/generate-identity`, { method: "POST" });
    let job = started;
    while (job.status === "RUNNING") {
      await new Promise((resolve) => setTimeout(resolve, 650));
      job = await fetchJson(`/api/entity-library/prompt-generation/${encodeURIComponent(started.job_id)}`);
    }
    if (job.status !== "COMPLETE") throw new Error(job.error || "Identity generation failed.");
    if (entityLibrarySelectedAsset?.asset_id !== asset.asset_id
      || state.selectionControllers["entity-library-asset"] !== editorSelectionController
      || editorSelectionController?.signal.aborted) return;
    if (entityLibraryEditIdentity.value !== previousText) {
      entityLibraryIdentityStatus.textContent = `The field changed during analysis. Luna's draft: ${job.draft.identity}`;
      return;
    }
    entityLibraryEditIdentity.value = job.draft.identity;
    entityLibraryIdentityStatus.textContent = "Identity draft added. Save image to keep it.";
  } catch (error) {
    if (entityLibrarySelectedAsset?.asset_id === asset.asset_id
      && state.selectionControllers["entity-library-asset"] === editorSelectionController) {
      entityLibraryIdentityStatus.textContent = error.message;
    }
  } finally {
    if (entityLibrarySelectedAsset?.asset_id === asset.asset_id
      && state.selectionControllers["entity-library-asset"] === editorSelectionController) {
      entityLibraryGenerateIdentity.disabled = asset.status === "archived";
    }
  }
}

const imageGenerationTerminalStatuses = new Set(["COMPLETE", "PARTIAL", "FAILED", "ERROR"]);

function renderImageGenerationStatus() {
  const busy = imageGenerationPending;
  const emptyCount = imageGenerationSlots.filter(item => !item).length;
  imageGenerationSubmit.disabled = busy || !emptyCount;
  imageGenerationFill.disabled = busy || !emptyCount;
  imageGenerationClear.disabled = busy || imageGenerationSelectedSlot >= 0 || !imageGenerationSlots.some(Boolean);
  imageGenerationClear.title = imageGenerationSelectedSlot >= 0 ? "Unselect the image before clearing all slots." : "";
  const completed = imageGenerationReviewableSlots().length;
  imageGenerationProgress.textContent = `${completed} of ${IMAGE_GENERATION_SLOT_COUNT} slots filled`;
  const selected = imageGenerationResult(imageGenerationSelectedSlot);
  imageGenerationReviewImport.disabled = !selected;
  imageGenerationReviewUpdate.hidden = !imageGenerationSource.dataset.assetId;
  imageGenerationReviewUpdate.disabled = !selected || !selected.job.source_asset_id;
  const nextGrid = document.createElement("div");
  for (let index = 0; index < IMAGE_GENERATION_SLOT_COUNT; index += 1) {
    const result = imageGenerationResult(index);
    const assignment = imageGenerationSlots[index];
    const job = assignment && imageGenerationJobs.get(assignment.requestId);
    const card = document.createElement("figure");
    card.className = `image-generation-result${index === imageGenerationSelectedSlot ? " is-selected" : ""}`;
    const title = document.createElement("figcaption");
    title.textContent = `Slot ${index + 1}${index === imageGenerationSelectedSlot ? " · Selected" : ""}`;
    card.append(title);
    if (result) {
      const preview = document.createElement("button");
      preview.type = "button";
      preview.className = "image-generation-result-preview";
      preview.setAttribute("aria-label", `Review slot ${index + 1}`);
      preview.addEventListener("click", () => openImageGenerationReview(index));
      const image = document.createElement("img");
      image.src = result.image.url;
      image.alt = `Generated image in slot ${index + 1}`;
      image.loading = "lazy";
      preview.append(image);
      card.append(preview);
      const controls = document.createElement("div");
      controls.className = "button-row compact";
      const review = document.createElement("button");
      review.type = "button";
      review.textContent = "Review";
      review.addEventListener("click", () => openImageGenerationReview(index));
      const download = document.createElement("a");
      download.href = `${result.image.url}${result.image.url.includes("?") ? "&" : "?"}download=true`;
      download.download = `zet-image-slot-${index + 1}`;
      download.textContent = "Download";
      const select = document.createElement("button"); select.type = "button"; select.textContent = index === imageGenerationSelectedSlot ? "Unselect" : "Select";
      select.addEventListener("click", () => void imageGenerationSlotAction(index === imageGenerationSelectedSlot ? "unselect" : "select", index));
      const regenerate = document.createElement("button"); regenerate.type = "button"; regenerate.textContent = "Regen";
      regenerate.disabled = busy || index === imageGenerationSelectedSlot;
      regenerate.addEventListener("click", () => void imageGenerationSlotAction("regenerate", index, currentImageGenerationInputs()));
      const clear = document.createElement("button"); clear.type = "button"; clear.textContent = "Clear";
      clear.disabled = regenerate.disabled;
      clear.addEventListener("click", () => void imageGenerationSlotAction("clear", index));
      controls.append(review, select, regenerate, clear, download);
      card.append(controls);
    } else {
      const status = document.createElement("p");
      const child = assignment && job?.results?.find(item => item.index === assignment.index);
      status.textContent = assignment ? child?.status || (job && imageGenerationTerminalStatuses.has(job.status) ? "FAILED" : job?.status || "Loading") : "Empty";
      card.append(status);
      if (child?.error || job?.error) { const error = document.createElement("p"); error.className = "error"; error.textContent = child?.error || job.error; card.append(error); }
      const retry = assignment && (child?.status === "FAILED" || imageGenerationTerminalStatuses.has(job?.status));
      const action = document.createElement("button"); action.type = "button"; action.textContent = assignment ? (retry ? "Retry" : "Regen") : "Generate"; action.disabled = busy;
      action.addEventListener("click", () => assignment ? void imageGenerationSlotAction(retry ? "retry" : "regenerate", index, retry ? undefined : currentImageGenerationInputs()) : void submitImageGenerationForSlots([index]));
      card.append(action);
      if (index === imageGenerationSelectedSlot) { const unselect = document.createElement("button"); unselect.type = "button"; unselect.textContent = "Unselect"; unselect.addEventListener("click", () => void imageGenerationSlotAction("unselect", index)); card.append(unselect); }
      if (assignment) { const clear = document.createElement("button"); clear.type = "button"; clear.textContent = "Clear"; clear.disabled = busy || index === imageGenerationSelectedSlot; clear.addEventListener("click", () => void imageGenerationSlotAction("clear", index)); card.append(clear); }
    }
    nextGrid.append(card);
  }
  [...nextGrid.children].forEach((card, index) => {
    const previous = imageGenerationResultsGrid.children[index];
    if (!previous) imageGenerationResultsGrid.append(card);
    else if (previous.outerHTML !== card.outerHTML) {
      const focused = document.activeElement;
      const text = previous.contains(focused) ? focused.textContent : null;
      previous.replaceWith(card);
      if (text) [...card.querySelectorAll("button,a")].find(button => button.textContent === text)?.focus();
    }
  });
  renderImageGenerationReview();
}

async function submitImageGenerationForSlots(slotIndexes) {
  if (imageGenerationPending) return;
  const references = imageGenerationMode === "img2img"
    ? imageGenerationReferenceSlots.map((reference, index) => ({...reference, index})).filter((reference) => reference.data)
    : [];
  if (imageGenerationMode === "img2img") {
    if (!references.length) {
      showMessageElement(imageGenerationMessage, "Choose at least one reference image for img2img.", "error");
      return;
    }
    const unlabeled = references.find((reference) => !reference.label.trim());
    if (unlabeled) {
      showMessageElement(imageGenerationMessage, `Enter a prompt label for reference image ${unlabeled.index + 1}.`, "error");
      return;
    }
  }
  await imageGenerationSlotAction("generate", slotIndexes?.length === 1 ? slotIndexes[0] : undefined, currentImageGenerationInputs());
}

function currentImageGenerationInputs() {
  const references = imageGenerationMode === "img2img" ? imageGenerationReferenceSlots.filter(reference => reference.data) : [];
  return {
    mode: imageGenerationMode, prompt: imageGenerationPrompt.value, negative_prompt: imageGenerationNegative.value,
    width: Number(imageGenerationWidth.value), height: Number(imageGenerationHeight.value),
    reference_images: references.map(({label, data}) => ({label: label.trim(), image: data})),
    source_asset_id: imageGenerationSource.dataset.assetId || "", source_checksum: imageGenerationSource.dataset.checksum || "",
  };
}

function submitImageGeneration(event) {
  event.preventDefault();
  void submitImageGenerationForSlots();
}

async function clearImageGenerationResults() {
  await imageGenerationSlotAction("clear_all");
}

async function loadImageGenerationOptions() {
  if (!imageGenerationOptionsLoaded || imageGenerationWorkspaceUniverse !== state.universeId) {
    try {
      const payload = await fetchJson("/api/image-generation/options", { bindToPage: false });
      imageGenerationModel.textContent = `${payload.model} · ${payload.checkpoint}`;
      imageGenerationWidth.value = payload.default_width || 1024;
      imageGenerationHeight.value = payload.default_height || 1024;
      imageGenerationOptionsLoaded = true;
      await restoreImageGenerationInputs();
    } catch (error) {
      showMessageElement(imageGenerationMessage, `Unable to load generation settings: ${error.message}`, "error");
    }
  }
  await restoreImageGenerationJob();
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

function showCostumeReferenceConflict(detail) {
  showCostumeMessage(detail.message || "Narrative references prevent deleting this costume.", "error");
  const references = Array.isArray(detail.references) ? detail.references : [];
  if (!references.length) return;

  const list = document.createElement("ul");
  for (const reference of references) {
    const item = document.createElement("li");
    const label = [reference.story_title, reference.scene_title, reference.target_title]
      .filter(Boolean)
      .join(" / ");
    if (reference.story_id && reference.scene_id) {
      const link = document.createElement("a");
      const params = new URLSearchParams({
        page: "narrative",
        workspace: "story",
        universe_id: state.universeId || "",
        story_slug: reference.story_id,
        scene_slug: reference.scene_id,
      });
      link.href = `/?${params.toString()}`;
      link.textContent = label || "Open Narrative scene";
      item.append(link);
    } else {
      item.textContent = label || reference.consumer_id || "Narrative scene reference";
    }
    const context = [reference.reference_key, reference.asset_id, reference.locator]
      .filter(Boolean)
      .join(" · ");
    if (context) {
      const details = document.createElement("span");
      details.textContent = ` — ${context}`;
      item.append(details);
    }
    list.append(item);
  }
  costumeMessage.append(list);
}

function showSceneAppearanceMessage(message, kind = "info") {
  showMessageElement(sceneAppearanceMessage, message, kind);
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

function orderControls(label, index, count, onMove) {
  const cell = document.createElement("td");
  const previous = document.createElement("button");
  previous.type = "button";
  previous.textContent = "↑";
  previous.setAttribute("aria-label", `Move ${label} up`);
  previous.disabled = index === 0;
  previous.addEventListener("click", () => onMove(-1));
  const next = document.createElement("button");
  next.type = "button";
  next.textContent = "↓";
  next.setAttribute("aria-label", `Move ${label} down`);
  next.disabled = index === count - 1;
  next.addEventListener("click", () => onMove(1));
  cell.className = "order-controls";
  cell.append(previous, next);
  return cell;
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
  const label = document.createElement("span");
  label.className = "asset-task-label";
  label.textContent = task.display_label || (task.asset_id != null ? `Asset ${task.asset_id}` : task.ask_id);
  cell.append(label);
  if (task.display_subtext) {
    const subtext = document.createElement("small");
    subtext.className = "asset-task-subtext";
    subtext.textContent = task.display_subtext;
    cell.append(subtext);
  }
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





const SCENE_BUILDER_HELP = {
  "scene.name": "Human-readable scene title.",
  "scene.story_settings_path": "Path to the companion .story.json file containing story-wide art style, dialogue style, and compiler defaults.",
  "scene.associated_png_path": "Path where the rendered image for this scene should be stored or found.",
  "scene.story_beat": "One sentence describing the visual moment or change the image must communicate. Describe what is happening now, not the surrounding plot.",
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
  "scene_elements[].resource_type": "Where this element comes from: Character, a reference-set type, or Scene-Only.",
  "scene_elements[].element_type": "Type of visible thing: Character, Monster, Prop, or Backdrop.",
  "scene_elements[].reference_images[].tag": "Resolvable image reference tag used by Zet, such as {{ASSET:...}}, {{IMAGE:...}}, or a legacy {{AUX:...}} tag.",
  "scene_elements[].element_visual_override": "Element-specific visual override. Use only for temporary scene-specific changes.",
  "scene_elements[].fallback_visual_description": "Short local visual description used only if no canonical source or reference is available.",
  "scene_elements[].notes": "Private notes for this element in this scene.",
  "placements[].position_within_cell": "Position inside the grid cell, or None to suppress placement output for this element.",
  "placements[].depth": "Depth layer: foreground, midground, background, or distant background.",
  "placements[].world_position": "Location within the scene, such as \"at the edge of the pit\" or \"inside the doorway.\"",
  "placements[].pose.summary": "Describe the visible body pose or action in the finished frame; don't repeat screen position, gaze, expression, or story history.",
  "placements[].pose.gaze_target_element_id": "Element ID that this element is looking at.",
  "placements[].pose.expression": "Facial expression or visible emotional state.",
  "setup.composition.focal_point": "The person, action, or visual relationship viewers should notice first.",
  "setup.composition.left_to_right": "Order the important visible elements as the viewer should encounter them from the left side of the image to the right.",
  "setup.composition.composition_notes": "Use only for shared framing, spacing, overlap, or visual constraints not captured by subject and interaction fields.",
  "placements[].motion.state": "Whether this element is still or visibly moving in the scene.",
  "placements[].motion.direction_screen": "The direction the element is visibly moving within the finished image.",
  "placements[].motion.cue": "A short visual description showing movement, such as trailing hair, a lifted foot, flying fabric, falling debris, or a blurred limb.",
  "placements[].placement_notes": "Use only for a distinct visible staging constraint absent from position, pose, gaze, expression, and interaction fields. Describe the final frame, not how the subject arrived there.",
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
};



let builderHelpSequence = 0;





function closeFullscreenImage() {
  resetFullscreenCrop();
  resetFullscreenNavigation();
  if (fullscreenImageOverlay.open) {
    fullscreenImageOverlay.close();
  }
  fullscreenImage.removeAttribute("src");
  fullscreenImage.alt = "";
  fullscreenCandidateLink.hidden = true;
  fullscreenCandidateLink.removeAttribute("href");
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

function showFullscreenSceneDocument(document, scene) {
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
  setCandidatePendingLink(fullscreenCandidateLink, document);
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
    showFullscreenSceneDocument(document, scene);
  } finally {
    updateFullscreenNavigation();
  }
}

async function openStoryViewer() {
  if (!state.selectedStorySlug) return;
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes`);
    const scenes = payload.scenes || [];
    if (!scenes.length) {
      showStoryMessage("This story has no scenes.");
      return;
    }
    const scene = scenes[0];
    const detail = await fetchJson(
      `/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(scene.slug)}`,
    );
    resetFullscreenNavigation();
    fullscreenSceneNavigation = { index: 0, scenes, storySlug: state.selectedStorySlug };
    showFullscreenSceneDocument(detail.document || {}, scene);
    updateFullscreenNavigation();
    resetFullscreenCrop();
    fullscreenImageOverlay.showModal();
    fullscreenImageClose.focus();
  } catch (error) {
    showStoryMessage(error.message, "error");
  }
}

function openFullscreenImage(src, alt = "", options = {}) {
  if (!src) {
    return;
  }
  resetFullscreenNavigation();
  fullscreenCandidateLink.hidden = true;
  fullscreenCandidateLink.removeAttribute("href");
  fullscreenImage.src = src;
  fullscreenImage.alt = alt;
  if (options.document) {
    setCandidatePendingLink(fullscreenCandidateLink, options.document);
  }
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
  const params = new URLSearchParams();
  if (state.character) {
    params.set("character", state.character);
  }
  if (state.phase) {
    params.set("phase", state.phase);
  }
  return params;
}

function productionQuery() {
  return new URLSearchParams();
}

function productionSummaryQuery() {
  const params = new URLSearchParams({ workspace: state.workspace });
  if (state.workspace === "story") {
    if (state.selectedStorySlug) params.set("story_slug", state.selectedStorySlug);
    if (state.selectedSceneSlug) params.set("scene_slug", state.selectedSceneSlug);
  } else {
    if (state.character) params.set("character", state.character);
    if (state.phase) params.set("phase", state.phase);
  }
  return params;
}

function renderProductionWorkSummary() {
  const project = state.productionWorkSummary.project || {};
  for (const badge of document.querySelectorAll("[data-production-count]")) {
    const count = Number(project[badge.dataset.productionCount] || 0);
    badge.textContent = count > 99 ? "99+" : String(count);
    badge.hidden = count === 0;
    const label = badge.dataset.productionCount === "image_review_waiting" ? "images waiting" : "tasks waiting";
    badge.setAttribute("aria-label", `${count} ${label} project-wide`);
  }
  const analysisPending = Number(project.analysis_pending || 0);
  for (const badge of document.querySelectorAll("[data-analysis-pending]")) {
    badge.textContent = `↻${analysisPending > 99 ? "99+" : analysisPending}`;
    badge.hidden = analysisPending === 0;
    badge.title = `${analysisPending} prompt analysis task(s) running`;
  }
  for (const menu of [characterProductionMenu, storyProductionMenu].filter(Boolean)) {
    const waitingAreas = [project.prompt_available]
      .filter((count) => Number(count || 0) > 0).length;
    menu.options[0].textContent = waitingAreas ? `Production · ${waitingAreas} waiting ▾` : "Production ▾";
    const labels = {
      "prompt-review": menu === storyProductionMenu ? "Prompt / Analysis" : "Prompts",
    };
    for (const [value, key] of [["prompt-review", "prompt_available"]]) {
      const item = Array.from(menu.options).find((option) => option.value === value);
      if (item) item.textContent = `${labels[value]}${Number(project[key] || 0) ? ` · ${project[key]}` : ""}`;
    }
  }
  renderResponsiveSectionMenu();
}

async function refreshProductionWorkSummary() {
  if (document.hidden || state.workspace === "local") {
    if (state.productionWorkTimer) window.clearTimeout(state.productionWorkTimer);
    state.productionWorkTimer = null;
    return null;
  }
  if (state.productionWorkPromise) {
    state.productionWorkRefreshPending = true;
    return state.productionWorkPromise;
  }
  const request = ++state.productionWorkRequest;
  const query = productionSummaryQuery().toString();
  state.productionWorkPromise = (async () => {
    try {
      const payload = await fetchJson(`/api/production-work-summary?${query}`, { bindToPage: false });
      if (request !== state.productionWorkRequest || query !== productionSummaryQuery().toString()) {
        state.productionWorkRefreshPending = true;
        return null;
      }
      state.productionWorkSummary = payload;
      renderProductionWorkSummary();
      return payload;
    } catch (error) {
      if (!isRequestCancellation(error)) console.error("Unable to refresh production work summary.", error);
      return null;
    } finally {
      state.productionWorkPromise = null;
      const refreshAgain = state.productionWorkRefreshPending;
      state.productionWorkRefreshPending = false;
      if (refreshAgain && !document.hidden) {
        window.queueMicrotask(() => void refreshProductionWorkSummary());
      } else {
        scheduleProductionWorkSummary();
      }
    }
  })();
  return state.productionWorkPromise;
}

function scheduleProductionWorkSummary(delay = 45000) {
  if (state.productionWorkTimer) window.clearTimeout(state.productionWorkTimer);
  state.productionWorkTimer = null;
  if (document.hidden || state.workspace === "local" || document.body.dataset.dashboardReady !== "true") return;
  state.productionWorkTimer = window.setTimeout(() => {
    state.productionWorkTimer = null;
    void refreshProductionWorkSummary();
  }, delay);
}

async function reloadActiveProductionPage() {
  const page = activePageName();
  if (page === "prompt-review") await loadPromptReviewTasks();
  if (page === "render-review") await loadRenderReviewTasks();
  if (page === "render-console") await loadRenderConsoleTasks();
  if (page === "local-image-review") await loadLocalImageReviewTasks();
  await refreshProductionWorkSummary();
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

function loadStoredStoryContext() {
  try {
    const data = JSON.parse(window.localStorage.getItem(LAST_STORY_CONTEXT_STORAGE_KEY) || "{}");
    return {
      story: String(data?.story || ""),
      scene: String(data?.scene || ""),
    };
  } catch {
    return { story: "", scene: "" };
  }
}

function saveStoredStoryContext() {
  try {
    window.localStorage.setItem(
      LAST_STORY_CONTEXT_STORAGE_KEY,
      JSON.stringify({ story: state.selectedStorySlug || "", scene: state.selectedSceneSlug || "" }),
    );
  } catch {
    // Ignore storage failures and keep the app usable.
  }
}

function loadStoredWorkspacePreferences() {
  try {
    const raw = window.localStorage.getItem(WORKSPACE_STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    const pages = data?.pages || {};
    return {
      workspace: data?.workspace === "story" ? "story" : "character",
      pages: {
        character: CHARACTER_PAGES.has(canonicalDashboardPage(pages.character)) || LOCAL_PAGES.has(pages.character) || PRODUCTION_PAGES.has(pages.character)
          ? canonicalDashboardPage(pages.character)
          : "onboarding",
        local: "onboarding",
        story: STORY_PAGES.has(pages.story) || PRODUCTION_PAGES.has(pages.story)
          ? pages.story
          : "scenes",
      },
    };
  } catch {
    return null;
  }
}

function saveWorkspacePreferences() {
  try {
    window.localStorage.setItem(
      WORKSPACE_STORAGE_KEY,
      JSON.stringify({ workspace: state.workspace, pages: state.lastWorkspacePages }),
    );
  } catch {
    // Ignore storage failures and keep the app usable.
  }
}

function pageWorkspace(page) {
  if (page === "local-batch-status") return null;
  if (["universes", "universe-create", "universe-settings"].includes(page)) return null;
  if (CHARACTER_PAGES.has(page)) return "character";
  if (LOCAL_PAGES.has(page)) return "character";
  if (STORY_PAGES.has(page)) return "story";
  return null;
}

function canonicalDashboardPage(page) {
  return ({
    "local-overview": "onboarding", assets: "local-batch-status", manifest: "local-batch-status",
    "scene-appearances": "local-batch-status", expressions: "local-batch-status",
    "local-identity-keys": "identity-keys", "local-turnarounds": "turnarounds",
    "local-costumes": "costumes", "local-comparison": "phase-comparison",
    "local-scene-appearances": "local-batch-status", "local-expressions": "local-batch-status",
    "local-image-review": "local-batch-status",
    "render-console": "narrative", "render-review": "narrative",
    stories: "narrative", scenes: "narrative", "scene-builder": "narrative", "scene-batches": "narrative",
  })[page] || page;
}

function renderHeaderStoryContext() {
  headerStorySelect.replaceChildren(option('', 'Stories'), ...state.stories.map(story=>option(story.id,story.title)));
  const params = new URLSearchParams(location.search);
  const storyId = params.get('story') || state.selectedStorySlug;
  headerStorySelect.value = storyId || '';
  const story = state.stories.find(story=>story.id===storyId);
  headerSceneSelect.replaceChildren(option('', 'Scenes'), ...(story?.scenes || []).map(scene=>option(scene.id,scene.title)));
  headerSceneSelect.value = params.get('scene') || '';

}
const RESPONSIVE_WORKSPACE_PAGES = {
  character: [
    ["onboarding", "Overview"], ["local-body-reference", "Assets"], ["identity-keys", "Identity Keys"],
    ["turnarounds", "Turnarounds"], ["costumes", "Costumes"], ["phase-comparison", "Phase Comparison"],
  ],
  story: [
    ["narrative", "Stories"], ["scene-candidates", "Candidates"], ["zine", "Zines"],
  ],
};

const RESPONSIVE_TOOL_PAGES = [
  ["local-batch-status", "Batches"],
  ["image-generation", "Image Generation"],
  ["auxiliary-resources", "Image Inventory"], ["template-editor", "Template Editor"], ["ai-controls", "AI Queue"],
  ["pipeline-controls", "Pipeline Controls"],
  ["help", "Template Instruction Manuals"],
];

function renderResponsiveSectionMenu(selectedPage = activePageName() || state.lastWorkspacePages[state.workspace]) {
  responsiveSectionMenu.replaceChildren();
  const sectionGroup = document.createElement("optgroup");
  sectionGroup.label = state.workspace === "story" ? "Story Telling" : state.workspace === "local" ? "Local" : "Character Development";
  const countKeys = { "prompt-review": "prompt_available", "render-console": "render_waiting", "render-review": "image_review_waiting" };
  for (const [value, label] of RESPONSIVE_WORKSPACE_PAGES[state.workspace]) {
    const count = Number(state.productionWorkSummary.project?.[countKeys[value]] || 0);
    sectionGroup.append(option(value, `${label}${count ? ` · ${count}` : ""}`));
  }
  const toolsGroup = document.createElement("optgroup");
  toolsGroup.label = "Tools";
  for (const [value, label] of RESPONSIVE_TOOL_PAGES) toolsGroup.append(option(value, label));
  responsiveSectionMenu.append(sectionGroup, toolsGroup);
  responsiveSectionMenu.value = Array.from(responsiveSectionMenu.options).some((item) => item.value === selectedPage) ? selectedPage : "";
}

function syncResponsiveChrome() {
  toolbarSettingsButton.textContent = window.matchMedia("(max-width: 600px)").matches ? "More ▾" : "Tools ▾";
  renderResponsiveSectionMenu();
}

function applyWorkspaceChrome() {
  const storyActive = state.workspace === "story";
  const localActive = false;
  workspaceCharacter.setAttribute("aria-pressed", !storyActive ? "true" : "false");
  workspaceLocal?.setAttribute("aria-pressed", "false");
  workspaceStory.setAttribute("aria-pressed", storyActive ? "true" : "false");
  characterContext.hidden = storyActive;
  storyContext.hidden = !storyActive;
  characterNavigation.hidden = storyActive;
  localNavigation.hidden = true;
  storyNavigation.hidden = !storyActive;
  headerFitmentPreview.hidden = storyActive || !headerFitmentPreview.getAttribute("src");
  for (const item of newMenu.querySelectorAll("[data-workspace-item]")) {
    item.hidden = item.dataset.workspaceItem !== state.workspace
      && !(localActive && item.dataset.workspaceItem === "character");
  }
  renderHeaderStoryContext();
  syncResponsiveChrome();
}

function rememberPage(page) {
  state.activePageId = page;
  const workspace = pageWorkspace(page);
  if (workspace) {
    state.workspace = workspace;
    state.lastWorkspacePages[workspace] = page;
  } else if (PRODUCTION_PAGES.has(page)) {
    state.lastWorkspacePages[state.workspace] = page;
  }
  saveStoredStoryContext();
  saveWorkspacePreferences();
  applyWorkspaceChrome();
}

async function switchWorkspace(workspace) {
  if (workspace === state.workspace) return true;
  return runGuardedTransition(async () => {
    const navigationRequest = ++state.navigationRequest;
    const workspaceTransitionGeneration = state.pageGeneration;
    state.workspace = workspace;
    applyWorkspaceChrome();
    if (workspace === "story" && !state.stories.length) {
      await loadStories();
      if (navigationRequest !== state.navigationRequest || workspaceTransitionGeneration !== state.pageGeneration) return false;
    }
    const fallback = workspace === "character" ? "onboarding" : workspace === "local" ? "local-overview" : (state.selectedStorySlug ? "scenes" : "stories");
    const target = state.lastWorkspacePages[workspace] || fallback;
    await activatePage(target, { skipAutosave: true });
  });
}

async function navigateSceneWorkflow(destination) {
  if (!state.selectedStorySlug || !state.selectedSceneSlug) return;
  await selectStoryScene(state.selectedStorySlug, state.selectedSceneSlug, {
    skipGuard: true,
    renderTargetId: state.activeBuilderRenderTarget || "main",
    ...(destination === "locked-image" ? {} : { destination }),
  });
  if (destination === "locked-image") {
    const detail = await fetchJson(
      `/api/render-review/scenes/${encodeURIComponent(state.selectedStorySlug)}/${encodeURIComponent(state.selectedSceneSlug)}`,
    );
    if (!detail.locked_exists || !detail.locked_image_path) {
      throw new Error("This scene does not have a locked image yet.");
    }
    openFullscreenImage(fileUrl(detail.locked_image_path, Date.now().toString()), `${detail.title || state.selectedSceneSlug} locked image`);
    return;
  }
}

function overviewMetric(value, label) {
  const item = document.createElement("div");
  item.className = "overview-metric";
  const strong = document.createElement("strong");
  strong.textContent = String(value);
  const caption = document.createElement("span");
  caption.textContent = label;
  item.append(strong, caption);
  return item;
}

function renderCharacterOverview() {
  const summary = state.onboardingMode ? null : state.workspaceSummary.character;
  renderCharacterPhoneViewer();
  characterWorkflow.replaceChildren();
  characterOverviewMetrics.replaceChildren();
  if (!summary) {
    characterRecommendedLabel.textContent = "Edit character setup";
    characterRecommendedAction.dataset.destination = "onboarding";
    return;
  }
  for (const step of summary.steps || []) {
    const item = document.createElement("li");
    item.classList.toggle("complete", Boolean(step.complete));
    const label = document.createElement("span");
    label.className = "step-label";
    label.textContent = step.label;
    const progress = document.createElement("span");
    progress.className = "step-state";
    progress.textContent = step.complete
      ? "✓ Complete"
      : step.total > 0 ? `○ ${step.current} of ${step.total}` : "○ Not started";
    item.append(label, progress);
    characterWorkflow.append(item);
  }
  characterOverviewMetrics.append(
    overviewMetric(`${summary.base_reference_locked}/${summary.base_reference_total}`, "Base references locked"),
    overviewMetric(`${summary.head_image_locked}/${summary.head_image_total}`, "Head images locked"),
    overviewMetric(`${summary.assembly_locked}/${summary.assembly_total}`, "Assembly views locked"),
    overviewMetric(summary.identity_count, "Identity keys"),
    overviewMetric(summary.turnaround_count, "Locked turnarounds"),
    overviewMetric(summary.costume_count, "Costumes"),
    overviewMetric(summary.expression_count, "Expressions"),
  );
  characterRecommendedLabel.textContent = summary.recommended_action;
  characterRecommendedAction.dataset.destination = summary.recommended_destination;
}

function renderCharacterPhoneViewer() {
  characterPhoneViewer.replaceChildren();
  const isDraft = Boolean(state.onboardingMode);
  const character = isDraft ? onboardingCharacter.value.trim() : state.character;
  const phase = isDraft ? onboardingPhase.value.trim() : state.phase;
  const preview = isDraft ? null : state.headerPreviews?.[state.character]?.[state.phase] || null;
  const heading = document.createElement("div");
  heading.className = "phone-viewer-heading";
  const title = document.createElement("h2");
  title.textContent = [character, phase].filter(Boolean).join(" · ") || "New character";
  heading.append(title);
  const imageHost = document.createElement("div");
  imageHost.className = "phone-viewer-image";
  if (preview?.image_path) {
    const image = document.createElement("img");
    image.src = fileUrl(preview.image_path, preview.updated_at || Date.now().toString());
    image.alt = `${title.textContent} reference`;
    imageHost.append(enableFullscreenImage(image));
  } else {
    imageHost.textContent = isDraft ? "Character folder has not been created yet." : "No locked character reference yet.";
  }
  const navigation = document.createElement("div");
  navigation.className = "phone-viewer-navigation character-phone-links";
  for (const [page, label] of [["assets", "References"], ["costumes", "Costumes"], ["turnarounds", "Turnarounds"]]) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "navigation-action";
    button.dataset.characterViewPage = page;
    button.textContent = label;
    navigation.append(button);
  }
  characterPhoneViewer.append(heading, imageHost, navigation);
}

function selectedStoryOverviewScene() {
  const scenes = state.workspaceSummary.story?.scenes || [];
  return scenes.find((scene) => scene.slug === state.selectedSceneSlug) || scenes[0] || null;
}



function moveStoryPhoneScene(delta) {
  const scenes = canonicalSceneCollection(state.selectedStorySlug);
  const current = selectedStoryOverviewScene();
  const index = scenes.findIndex((scene) => scene.slug === current?.slug);
  const next = scenes[index + delta];
  if (!next) return;
  void selectStoryScene(state.selectedStorySlug, next.slug);
}



async function loadWorkspaceSummary(options = {}) {
  const params = currentQuery();
  if (state.selectedStorySlug) params.set('story_slug', state.selectedStorySlug);
  const payload = await fetchJson(`/api/workspace-summary?${params}`, options);
  state.workspaceSummary = {character:payload.character || null,story:payload.story || null};
  renderCharacterOverview(); renderHeaderStoryContext();
}
function loadStoredAssetFilters() {
  // Keep the base-image visibility preference across browser sessions.
  state.assetFilters.hideBaseImages = window.localStorage.getItem(HIDE_BASE_IMAGES_STORAGE_KEY) === "true";
  assetFilterHideBase.checked = state.assetFilters.hideBaseImages;
}

function saveStoredAssetFilters() {
  window.localStorage.setItem(HIDE_BASE_IMAGES_STORAGE_KEY, state.assetFilters.hideBaseImages ? "true" : "false");
}

function updateStartupRecoveryStatus(recovery) {
  const status = String(recovery?.status || "complete");
  startupRecoveryStatus.dataset.status = status;
  startupRecoveryStatus.textContent = status === "running"
    ? (recovery.message || "Restoring saved image review jobs…")
    : status === "error" ? `Image review recovery needs attention: ${recovery.message || "unknown error"}` : "";
  startupRecoveryStatus.hidden = !["running", "error"].includes(status);
  if (status === "running") {
    if (!startupRecoveryTimer) {
      startupRecoveryTimer = window.setTimeout(() => void pollStartupRecoveryStatus(), 5000);
    }
  } else if (startupRecoveryTimer) {
    window.clearTimeout(startupRecoveryTimer);
    startupRecoveryTimer = null;
  }
}

async function pollStartupRecoveryStatus() {
  startupRecoveryTimer = null;
  try {
    const health = await fetchJson("/api/health");
    updateStartupRecoveryStatus(health.recovery);
  } catch {
    updateStartupRecoveryStatus({ status: "running", message: "Checking saved image review jobs…" });
  }
}

async function loadContext() {
  const payload = await fetchJson("/api/context");
  updateStartupRecoveryStatus(payload.recovery);
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
  setSelectOptionsWithLabels(builderImagePickerCharacter, [{ value: "", label: "All Characters" }, ...state.characters.map((item) => ({ value: item, label: item }))]);
  setSelectOptions(onboardingSpecies, state.onboardingOptions.species_ancestry || []);
  setSelectOptions(onboardingGender, state.onboardingOptions.gender_presentation || []);
  if (state.auxiliaryResourceCategories.length) {
  }
  updatePhaseSelect();
  saveStoredContext();
  renderOnboarding();
  applyWorkspaceChrome();
}

function updateHeaderFitmentPreview() {
  // Show the locked Front-Left-3-4 Head-Image when this phase has one.
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
    headerFitmentPreview.hidden = state.workspace === "story";
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

function selectedLocalPhaseReady() {
  return Boolean(selectedOnboardingStatus()?.template_ready);
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
- The draft markdown file named Character.md${templatePath ? ` from ${templatePath}` : ""}
- The Character Template Instructions manual from Zet Help
- One or more reference images for the character/phase

Your task:
Fill out Character.md using the attached reference image(s) and the metadata below, then return the completed template as a downloadable markdown file named Character.md.

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
- Return the completed markdown file itself, suitable for saving directly as Character.md.
- Keep prompt language factual, visual, and render-facing.
- Avoid story, personality, mood, scene action, and narrative.
- Do not add technical modesty or fitment-clothing instructions; Zet supplies those globally.
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
  const isDraft = Boolean(state.onboardingMode);
  const status = isDraft ? null : selectedOnboardingStatus();
  const ready = !isDraft && selectedPhaseReady();
  for (const button of characterNavigation.querySelectorAll(".workflow-tab")) {
    const page = button.dataset.page || "";
    button.disabled = !ready && page !== "phase-comparison";
  }
  onboardingStatus.textContent = isDraft ? "New character — not created yet" : ready ? "Ready for character production" : "Setup incomplete";
  const characterName = isDraft ? onboardingCharacter.value.trim() : status?.character_name || state.character || "";
  const phaseName = isDraft ? onboardingPhase.value.trim() : state.phase || "";
  onboardingTitle.textContent = [characterName, phaseName].filter(Boolean).join(" / ") || "New Character";
  if (!isDraft) {
    onboardingCharacter.value = characterName;
    onboardingPhase.value = phaseName;
    setSelectValueCaseInsensitive(onboardingSpecies, status?.species_ancestry || onboardingSpecies.value);
    setSelectValueCaseInsensitive(onboardingGender, status?.gender_presentation || onboardingGender.value);
    onboardingArtStyle.value = status?.canonical_art_style || onboardingArtStyle.value || "";
  }
  onboardingDownloadTemplate.hidden = !status?.template_path;
  onboardingAddHeadImages.disabled = !status?.assets_exists || !status?.pipelines_exists;
  if (status?.template_path) {
    onboardingDownloadTemplate.href = downloadFileUrl(status.template_path);
    onboardingDownloadTemplate.download = "Character.md";
  }
  updateOnboardingHelperPrompt(status?.template_path || "");
  onboardingStatusList.replaceChildren();
  if (isDraft) {
    const rows = [
      ["Character", characterName || "Not entered"],
      ["Phase", phaseName || "Not entered"],
      ["Folder", "Not created until template upload"],
    ];
    for (const [label, value] of rows) {
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      dd.textContent = value;
      onboardingStatusList.append(dt, dd);
    }
    onboardingValidation.textContent = "Upload the completed Character.md to create this character.";
  } else if (status) {
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
  renderCharacterOverview();
}

async function refreshCurrentContext() {
  await loadContext();
  if (selectedPhaseReady()) {
    await loadAssets();
  }
  await loadWorkspaceSummary();
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

async function startNewPhase() {
  state.workspace = "character";
  state.onboardingMode = "new-phase";
  await activatePage("onboarding", { skipAutosave: true });
  characterSetupDetails.open = true;
  onboardingCharacter.value = state.character || "";
  onboardingPhase.value = "";
  onboardingArtStyle.value = "";
  renderOnboarding();
  prefillOnboarding(state.character || "", state.phase || "").catch((error) => showOnboardingMessage(error.message, "error"));
}

async function startNewCharacter() {
  state.workspace = "character";
  state.onboardingMode = "new-character";
  await activatePage("onboarding", { skipAutosave: true });
  characterSetupDetails.open = true;
  onboardingCharacter.value = "";
  onboardingPhase.value = "Adult";
  onboardingArtStyle.value = "";
  if (onboardingSpecies.options.length) {
    onboardingSpecies.selectedIndex = 0;
  }
  if (onboardingGender.options.length) {
    onboardingGender.selectedIndex = 0;
  }
  renderOnboarding();
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
    state.onboardingMode = null;
    showOnboardingMessage(payload.message || "Draft saved.");
    await refreshCurrentContext();
    const templatePath = payload.draft?.template_path;
    if (templatePath) {
      onboardingDownloadTemplate.href = downloadFileUrl(templatePath);
      onboardingDownloadTemplate.download = "Character.md";
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
    showOnboardingMessage("Choose a Character.md file first.", "error");
    return;
  }
  try {
    const character = onboardingCharacter.value.trim();
    const phase = onboardingPhase.value.trim();
    if (!character || !phase) {
      showOnboardingMessage("Character and phase are required.", "error");
      return;
    }
    const params = new URLSearchParams({
      character,
      phase,
      create_only: state.onboardingMode ? "true" : "false",
    });
    const payload = await fetchJson(`/api/onboarding/template?${params.toString()}`, {
      method: "POST",
      headers: { "Content-Type": file.type || "text/markdown" },
      body: file,
    });
    state.character = payload.status?.character || character;
    state.phase = payload.status?.phase || phase;
    state.onboardingMode = null;
    showOnboardingMessage(payload.message || "Template uploaded.");
    await refreshCurrentContext();
    renderOnboarding();
    if (payload.status?.complete) {
      activatePage("assets");
    }
    onboardingTemplateFile.value = "";
  } catch (error) {
    showOnboardingMessage(error.message, "error");
  }
}

function canonicalSceneCollection(storySlug = state.selectedStorySlug) {
  if (state.sceneCollection.storySlug === storySlug) return state.sceneCollection.items || [];
  return [];
}

function setCanonicalSceneCollection(storySlug, scenes) {
  const items = Array.isArray(scenes) ? scenes.slice() : [];
  state.sceneCollection = { storySlug: storySlug || "", items };
  if (storySlug === state.selectedStorySlug) state.scenes = items.slice();
}

function sceneDocumentMatches(storySlug = state.selectedStorySlug, sceneSlug = state.selectedSceneSlug) {
  const document = state.sceneDetail;
  const builderMatches = state.loadedBuilderContext.storySlug === storySlug
    && state.loadedBuilderContext.sceneSlug === sceneSlug;
  return Boolean(
    (document || state.sceneBuilder)
    && state.loadedSceneContext.storySlug === storySlug
    && state.loadedSceneContext.sceneSlug === sceneSlug
    && (document ? document.story?.slug === storySlug && document.scene?.slug === sceneSlug : builderMatches)
    && state.requestedSceneContext.storySlug === storySlug
    && state.requestedSceneContext.sceneSlug === sceneSlug,
  );
}

function updateSceneContextControls() {
  const ready = sceneDocumentMatches();
  const enabled = Boolean(state.selectedStorySlug && state.selectedSceneSlug && ready);
  sceneSave.disabled = !enabled;
  sceneStageRender.disabled = !enabled;
  sceneBuilderOpen.disabled = !enabled;
  sceneDelete.disabled = !enabled;
  sceneRename.disabled = !enabled;
  sceneMove.disabled = !enabled;
  return ready;
}

function clearRequestedSceneDocument(message = "Loading scene...") {
  state.sceneDetail = null;
  state.loadedSceneContext = { storySlug: "", sceneSlug: "" };
  state.loadedBuilderContext = { storySlug: "", sceneSlug: "" };
  state.savedBaselines.scene = "";
  sceneEditorTitle.textContent = message;
  sceneText.value = "";
  sceneRenameTitle.value = "";
  setSaveState(sceneSaveState, "");
  closeSceneBuilder();
  updateSceneContextControls();
}

function browserRouteUrl() {
  const params = new URLSearchParams();
  const page = activePageName();
  if (page === 'narrative') {
    const current = new URLSearchParams(location.search);
    current.set('page','narrative'); current.set('workspace','story');
    if (state.universeId) current.set('universe_id',state.universeId);
    return '/?'+current;
  }
  if (page) params.set("page", page);
  if (page === "scene-batches") {
    const batch = new URLSearchParams(window.location.search).get("batch");
    if (batch) params.set("batch", batch);
  }
  if (LOCAL_ASSET_PAGES.has(page)) {
    const currentParams = new URLSearchParams(window.location.search);
    for (const key of ["character", "phase", "local_batch", "local_costume"]) {
      const value = currentParams.get(key);
      if (value) params.set(key, value);
    }
  }
  if (state.workspace === "story") {
    if (state.selectedStorySlug) params.set("story_slug", state.selectedStorySlug);
    if (state.selectedSceneSlug) params.set("scene_slug", state.selectedSceneSlug);
    if (page === "scene-builder" && state.activeBuilderRenderTarget && state.activeBuilderRenderTarget !== "main") {
      params.set("render_target_id", state.activeBuilderRenderTarget);
    }
  }
  const query = params.toString();
  return `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`;
}

function syncBrowserRoute({ replace = false } = {}) {
  const url = browserRouteUrl();
  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (url === current) return;
  window.history[replace ? "replaceState" : "pushState"]({}, "", url);
}

async function addMissingHeadImages() {
  if (!state.character || !state.phase) return;
  try {
    const payload = await fetchJson(`/api/onboarding/head-images?${currentQuery().toString()}`, { method: "POST" });
    showOnboardingMessage(payload.message || "Head-Image foundation updated.");
    await refreshCurrentContext();
  } catch (error) {
    showOnboardingMessage(error.message, "error");
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
    ["Body-Reference", "Head-Image", "Character-Assembly"].includes(asset?.pipeline || "") &&
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
      asset.costume_or_expression,
      asset.asset_state,
      asset.pipeline_stage_display,
      asset.actor_display || asset.actor,
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
  if (window.matchMedia("(max-width: 600px)").matches) state.assetDetailMode = "locked";
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
    asset.pipeline_stage_display || asset.pipeline_stage,
    asset.actor_display || asset.actor,
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
    if (action === "keep-locked") {
      enabled = enabled && lockedExists && (asset.asset_state !== "LOCKED" || asset.pipeline_stage !== "LOCKED");
      button.hidden = !enabled;
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
  if (state.activePageId) return state.activePageId;
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



function savedSceneBuilderData() {
  try {
    return JSON.parse(state.savedBaselines.sceneBuilder || "null");
  } catch (_error) {
    return null;
  }
}





function replaceBuilderSubscene(data, targetId, subscene) {
  const index = (data?.subscenes || []).findIndex((item) => item.id === targetId);
  if (index >= 0 && subscene) data.subscenes[index] = JSON.parse(JSON.stringify(subscene));
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
  if (page === "universe-settings" && universeSettingsArtStyle.value !== state.savedUniverseArtStyle) {
    return {
      name: "Universe settings",
      autosave: false,
      save: saveUniverseSettings,
      discard: () => { universeSettingsArtStyle.value = state.savedUniverseArtStyle; },
    };
  }
  if (page === "stories" && state.storyDetail && storySnapshot() !== state.savedBaselines.story) {
    return {
      name: "story",
      save: saveStoryBeforeNavigation,
      discard: () => { state.savedBaselines.story = storySnapshot(); },
    };
  }
  if (page === "scenes" && state.sceneDetail && sceneSnapshot() !== state.savedBaselines.scene) {
    return {
      name: "scene",
      save: saveSceneBeforeNavigation,
      discard: () => { state.savedBaselines.scene = sceneSnapshot(); },
    };
  }
  if (page === "auxiliary-resources" && entityLibraryCurrentView === "detail" && entityLibrarySelectedAsset
    && entityLibraryEditorSnapshot() !== entityLibrarySavedSnapshot) {
    return {
      name: "image details",
      save: saveEntityLibraryAsset,
      discard: () => applyEntityLibraryEditorSnapshot(JSON.parse(entityLibrarySavedSnapshot || "{}")),
    };
  }
  if (page === "scene-builder" && state.sceneBuilder && sceneBuilderSnapshot() !== state.savedBaselines.sceneBuilder) {
    return {
      name: "Scene Builder",
      save: async () => Boolean(await saveSceneBuilder({ fullScene: true })),
      discard: () => { state.savedBaselines.sceneBuilder = sceneBuilderSnapshot(); },
    };
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
  if (activePageName() === "auxiliary-resources" && entityLibraryCurrentView === "detail" && entityLibrarySavePromise) {
    return Boolean(await entityLibrarySavePromise);
  }
  const guard = editorGuardForPage();
  if (!guard) return true;
  unsavedChangesMessage.textContent = `Save changes to ${guard.name} before continuing?`;
  unsavedChangesDialog.returnValue = "cancel";
  const choice = await dialogResult(unsavedChangesDialog);
  if (choice === "cancel") return false;
  if (choice === "discard") {
    guard.discard?.();
    updateDirtyIndicators();
    return true;
  }
  let saved = false;
  try {
    saved = await guard.save();
  } catch (error) {
    if (activePageName() === "auxiliary-resources") {
      setEntityLibraryEditorState("ready", `Save failed: ${error.message}`);
      entityLibraryEditorStateMessage.classList.add("error");
    }
  }
  updateDirtyIndicators();
  return Boolean(saved) && !editorGuardForPage();
}

async function runGuardedTransition(action) {
  const previous = state.transitionPromise;
  const execute = () => guardCurrentEditor();
  const current = previous
    ? previous.catch(() => false).then(execute)
    : execute();
  state.transitionPromise = current;
  try {
    const allowed = await current;
    if (!allowed) return false;
    return (await action()) !== false;
  } finally {
    if (state.transitionPromise === current) {
      state.transitionPromise = null;
    }
  }
}





async function saveBeforePageNavigation(nextPage) {
  const currentPage = activePageName();
  if (currentPage === nextPage) {
    return true;
  }
  return guardCurrentEditor();
}

function renderTemplateManual() {
  const manual = state.templateManuals.find((item) => item.id === state.selectedTemplateManual) || state.templateManuals[0];
  if (!manual) {
    helpStatus.textContent = "No manuals available.";
    templateManualContent.replaceChildren();
    return;
  }
  state.selectedTemplateManual = manual.id;
  templateManualSelect.value = manual.id;
  templateManualContent.innerHTML = manual.html;
  templateManualDownload.href = manual.download_url;
  templateManualDownload.download = manual.filename;
  helpStatus.textContent = manual.title;
}

async function loadTemplateManuals() {
  if (!state.templateManuals.length) {
    const payload = await fetchJson("/api/help/template-manuals");
    state.templateManuals = payload.manuals || [];
    templateManualSelect.replaceChildren(...state.templateManuals.map((item) => option(item.id, item.title)));
  }
  renderTemplateManual();
}

async function openTemplateManual(manualId) {
  state.selectedTemplateManual = manualId;
  try {
    await activatePage("help", { skipAutosave: true });
  } catch (error) {
    showActionMessage(`Unable to open Template Instruction Manuals: ${error.message}`, "error");
  }
}

async function activatePage(page, options = {}) {
  const retiredPage = ["render-console", "render-review"].includes(page);
  const retiredRoute = new URLSearchParams(window.location.search);
  page = canonicalDashboardPage(page);
  if (PRODUCTION_PAGES.has(page) && state.workspace !== "story") {
    state.workspace = "story";
    applyWorkspaceChrome();
    if (!state.stories.length) await loadStories();
  }
  state.navigationRequest += 1;
  const hasRequestedLocalBatch = LOCAL_ASSET_PAGES.has(page)
    && (Boolean(new URLSearchParams(window.location.search).get("local_batch"))
      || new URLSearchParams(window.location.search).get("task_context") === "1");
  const phaseReady = LOCAL_ASSET_PAGES.has(page) ? selectedLocalPhaseReady() : selectedPhaseReady();
  if (
    !phaseReady
    && !hasRequestedLocalBatch
    && ((state.workspace === "character"
      && ((CHARACTER_PAGES.has(page) && !["onboarding", "phase-comparison"].includes(page)) || PRODUCTION_PAGES.has(page)))
      || LOCAL_ASSET_PAGES.has(page))
  ) {
    page = "onboarding";
  }
  if (!options.skipAutosave && !(await saveBeforePageNavigation(page))) {
    if (characterProductionMenu) characterProductionMenu.value = PRODUCTION_PAGES.has(activePageName()) ? activePageName() : "";
    if (storyProductionMenu) storyProductionMenu.value = PRODUCTION_PAGES.has(activePageName()) ? activePageName() : "";
    return false;
  }
  const narrativeNavigation = state.navigationRequest;
  if (window.zetNarrativePending) await window.zetNarrativePending.catch(()=>null);
  if (narrativeNavigation !== state.navigationRequest) return false;
  if (window.zetNarrativeMount) {
    await window.zetNarrativeMount.unmount();
    window.zetNarrativeMount = null;
  }
  const pageLoad = beginPageLoad(page);
  rememberPage(page);
  document.querySelector('#narrative-page').classList.toggle('active', page === 'narrative');
  for (const button of document.querySelectorAll(".tab")) {
    button.classList.toggle("active", button.dataset.page === page);
  }
  if (characterProductionMenu) characterProductionMenu.classList.toggle("active", false);
  storyProductionMenu?.classList.toggle("active", PRODUCTION_PAGES.has(page) && state.workspace === "story");
  if (characterProductionMenu) characterProductionMenu.value = "";
  if (storyProductionMenu) storyProductionMenu.value = PRODUCTION_PAGES.has(page) && state.workspace === "story" ? page : "";
  document.querySelector("#onboarding-page").classList.toggle("active", page === "onboarding" || page === "local-overview");
  document.querySelector("#universes-page").classList.toggle("active", page === "universes");
  document.querySelector("#universe-create-page").classList.toggle("active", page === "universe-create");
  document.querySelector("#universe-settings-page").classList.toggle("active", page === "universe-settings");
  document.querySelector("#assets-page").classList.toggle("active", false);
  document.querySelector("#manifest-page").classList.toggle("active", page === "manifest");
  document.querySelector("#prompt-review-page").classList.toggle("active", page === "prompt-review");
  document.querySelector("#render-review-page").classList.toggle("active", page === "render-review");
  document.querySelector("#turnarounds-page").classList.toggle("active", page === "turnarounds");
  document.querySelector("#identity-keys-page").classList.toggle("active", page === "identity-keys");
  document.querySelector("#auxiliary-resources-page").classList.toggle("active", page === "auxiliary-resources");
  document.querySelector("#phase-comparison-page").classList.toggle("active", page === "phase-comparison");
  document.querySelector("#costumes-page").classList.toggle("active", page === "costumes");
  document.querySelector("#scene-appearances-page").classList.toggle("active", page === "scene-appearances");
  document.querySelector("#expressions-page").classList.toggle("active", page === "expressions");
  document.querySelector("#scene-candidates-page").classList.toggle("active", page === "scene-candidates");
  document.querySelector("#zine-page").classList.toggle("active", page === "zine");
  document.querySelector("#ai-controls-page").classList.toggle("active", page === "ai-controls");
  document.querySelector("#image-generation-page").classList.toggle("active", page === "image-generation");
  if (page !== "image-generation") clearInterval(imageGenerationWorkspaceTimer);
  document.querySelector("#local-image-config-page").classList.toggle("active", page === "local-image-config");
  document.querySelector("#pipeline-controls-page").classList.toggle("active", page === "pipeline-controls");
  document.querySelector("#pipeline-inspection-page").classList.toggle("active", page === "pipeline-inspection");
  document.querySelector("#render-console-page").classList.toggle("active", page === "render-console");
  document.querySelector("#local-image-review-page").classList.toggle("active", page === "local-image-review");
  document.querySelector("#template-editor-page").classList.toggle("active", page === "template-editor");
  document.querySelector("#help-page").classList.toggle("active", page === "help");
  document.querySelector("#local-pipeline-page").classList.toggle("active", LOCAL_ASSET_PAGES.has(page));
  document.querySelector("#local-stub-page").classList.toggle("active", LOCAL_PAGES.has(page) && !LOCAL_ASSET_PAGES.has(page) && page !== "local-overview" && page !== "local-batch-status");
  document.querySelector("#local-batch-status-page").classList.toggle("active", page === "local-batch-status");
  localAssetsButton.classList.toggle("active", LOCAL_ASSET_PAGES.has(page));
  if (LOCAL_ASSET_PAGES.has(page)) {
    const labels = {
      "local-body-reference": "Body-Reference",
      "local-head-image": "Head-Image",
      "local-character-assembly": "Character-Assembly",
      "local-costume-dressing": "Costume-Dressing",
    };
    document.querySelector("#local-pipeline-title").textContent = labels[page];
  }
  if (LOCAL_PAGES.has(page) && !LOCAL_ASSET_PAGES.has(page) && page !== "local-overview") {
    const labels = {
      "local-identity-keys": "Identity Keys",
      "local-turnarounds": "Turnarounds",
      "local-costumes": "Costumes",
      "local-scene-appearances": "Scene Appearances",
      "local-expressions": "Expressions",
      "local-comparison": "Comparison",
    };
    document.querySelector("#local-stub-title").textContent = labels[page];
  }
  document.querySelector("#placeholder-page").classList.toggle(
    "active",
    !document.querySelector(".page.active:not(#placeholder-page)"),
  );
  if (LOCAL_ASSET_PAGES.has(page)) window.ZetLocalAssetPipeline?.activate(page);
  else window.ZetLocalAssetPipeline?.deactivate();
  if (page === "local-batch-status") window.ZetLocalBatchStatus?.activate();
  else window.ZetLocalBatchStatus?.deactivate();
  renderResponsiveSectionMenu(page);
  if (options.updateHistory !== false && !options.fromHistory) syncBrowserRoute();
  const activeButton = Array.from(document.querySelectorAll(".tab")).find((button) => button.dataset.page === page);
  placeholderTitle.textContent = activeButton?.textContent || "Page";
  try {
  if (page === "image-generation") {
    setImageGenerationMode(imageGenerationMode);
    await loadImageGenerationOptions();
  }
  if (page === "prompt-review") {
    await loadPromptReviewTasks(options.preferredAskId || null);
  }
  if (page === "manifest") {
    await loadManifestTasks();
  }
  if (page === "render-review") {
    await loadRenderReviewTasks(options.preferredReviewKey || null);
  }
  if (page === "turnarounds") {
    await loadTurnarounds();
  }
  if (page === "identity-keys") {
    await loadIdentityKeys();
  }
  if (page === "auxiliary-resources") {
    await loadEntityLibraryInventory();
  }
  if (page === "phase-comparison") {
    initializePhaseComparisonControls();
    await loadPhaseComparison();
  }
  if (page === "costumes") {
    await loadCostumes();
  }
  if (page === "scene-appearances") {
    await loadSceneAppearances();
  }
  if (page === "expressions") {
    await loadExpressions();
  }
  if (page === 'narrative') {
    const params = new URLSearchParams(location.search);
    if (!params.get('story') && params.get('story_slug')) {
      try {
        const mapped = await fetchJson(`/api/narrative/legacy-location?story_slug=${encodeURIComponent(params.get('story_slug'))}&scene_slug=${encodeURIComponent(params.get('scene_slug') || '')}`);
        params.set('story',mapped.story_id);
        if (mapped.scene_id) params.set('scene',mapped.scene_id);
        params.delete('story_slug'); params.delete('scene_slug');
        history.replaceState({}, '', '/?'+params);
      } catch (error) { window.ZetTaskCapture.notice(error.message); }
    }
    const {mountNarrative} = await import('/static/narrative.js?v=20261013-github');
    if (!pageLoadIsCurrent(pageLoad)) return false;
    const pending = mountNarrative(document.querySelector('#narrative-page'), state.universeId, async next=>{
      const requested = location.search;
      await loadStories(next.story);
      if (requested !== location.search) return;
      state.selectedStorySlug = next.story || null;
      state.selectedSceneSlug = next.scene || null;
      renderHeaderStoryContext(); saveStoredStoryContext();
    });
    window.zetNarrativePending = pending;
    try {
      const mounted = await pending;
      if (!pageLoadIsCurrent(pageLoad)) { await mounted.unmount(); return false; }
      window.zetNarrativeMount = mounted;
    } finally {
      if (window.zetNarrativePending === pending) window.zetNarrativePending = null;
    }
  }
  if (page === "scene-candidates") {
    await loadSceneCandidates();
  }
  if (page === "zine") {
    await loadZines();
  }
  if (page === "pipeline-controls") {
    await loadPipelineControls();
  }
  if (page === "pipeline-inspection") {
    await loadPipelineInspections();
  }
  if (page === "local-image-config") {
    await loadAiControls();
    await loadPipelineControls();
    await refreshOllamaModelOptions();
  }
  if (page === "render-console") {
    await loadRenderConsoleTasks(options.preferredAskId || null);
  }
  if (page === "local-image-review") {
    await loadLocalImageReviewTasks();
  }
  if (page === "onboarding") {
    renderOnboarding();
    await loadWorkspaceSummary();
  }
  if (page === "universes") await loadUniverseList();
  if (page === "universe-settings") {
    try {
      await loadUniverseSettings(options.universeId || state.universeId);
    } catch (error) {
      setUniverseMessage("universe-settings-message", error.message, "error");
    }
  }
  if (page === "universe-create") {
    universeCreateForm.reset();
    setUniverseMessage("universe-create-message", "", "");
  }
  if (page === "help") {
    await loadTemplateManuals();
  }
  } catch (error) {
    if (!isRequestCancellation(error)) throw error;
  }
  if (!pageLoadIsCurrent(pageLoad)) return true;
  // Badge counts are supplemental navigation chrome.  Updating them can scan
  // project-wide queues, so do not hold the newly selected page open on it.
  void refreshProductionWorkSummary();
  return true;
}

function setupTabs() {
  for (const menu of [characterProductionMenu, storyProductionMenu].filter(Boolean)) {
    menu.addEventListener("change", async () => {
      const page = menu.value;
      if (!page) return;
      const changed = await runGuardedTransition(() => activatePage(page, { skipAutosave: true }));
      if (!changed) menu.value = PRODUCTION_PAGES.has(activePageName()) ? activePageName() : "";
    });
  }
  for (const button of document.querySelectorAll("button.tab")) {
    button.addEventListener("click", async () => {
      if (!button.dataset.page) return;
      closeNewMenu();
      if (button.dataset.page === "identity-keys") {
        state.identityKeyMode = "list";
      }
      closeToolbarSettingsMenu();
      closeHelpMenu();
      try {
        const changed = await runGuardedTransition(() => activatePage(button.dataset.page, {
          skipAutosave: true,
          universeId: button.dataset.universeId || "",
        }));
        if (changed && (LOCAL_ASSET_PAGES.has(button.dataset.page) || button.dataset.page === "local-batch-status")) {
          localAssetsMenu.hidden = true;
          localAssetsButton.setAttribute("aria-expanded", "false");
        }
      } catch (error) {
        showActionMessage(`Unable to open ${button.textContent.trim()}: ${error.message}`, "error");
      }
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

function toggleNewMenu() {
  const isHidden = newMenu.hidden;
  newMenu.hidden = !isHidden;
  newMenuButton.setAttribute("aria-expanded", isHidden ? "true" : "false");
  if (isHidden) newMenu.querySelector("button:not([hidden])")?.focus();
}

function closeNewMenu(returnFocus = false) {
  const wasOpen = !newMenu.hidden;
  newMenu.hidden = true;
  newMenuButton.setAttribute("aria-expanded", "false");
  if (returnFocus && wasOpen) newMenuButton.focus();
}

async function harvestAiFromToolbar() {
  // Run the AI harvest action without navigating away from the current page.
  closeToolbarSettingsMenu();
  toolbarHarvestAi.disabled = true;
  toolbarSettingsButton.textContent = "Working…";
  try {
    await runAiControlsAction("/api/ai-controls/harvest");
  } finally {
    toolbarHarvestAi.disabled = false;
    toolbarSettingsButton.textContent = "Tools ▾";
  }
}

async function loadIdentityKeys() {
  if (!state.character || !state.phase) {
    identityKeyStatus.textContent = "No character/phase selected.";
    return;
  }
  identityKeyStatus.textContent = "Loading Identity Keys...";
  const [payload, sourcePayload] = await Promise.all([
    fetchJson(`/api/identity-keys?${currentQuery().toString()}`),
    fetchJson(`/api/local-asset-sources?${currentQuery().toString()}`),
  ]);
  state.identityKeys = payload.identity_keys || [];
  state.localAssetSources = sourcePayload.sources || [];
  renderIdentityKeySources();
  renderIdentityKeyTable();
  identityKeyStatus.textContent = `${state.identityKeys.length} Identity Key(s)`;
  if (state.identityKeyMode === "list") {
    clearIdentityKeyUpdate();
  }
}

function renderIdentityKeySources(selected = identityKeySource.value) {
  const options = [option("", "Select a locked local image")];
  for (const item of state.localAssetSources) {
    const label = [item.pipeline, item.view, item.costume].filter(Boolean).join(" · ");
    options.push(option(item.source_key, label));
  }
  identityKeySource.replaceChildren(...options);
  identityKeySource.value = state.localAssetSources.some((item) => item.source_key === selected) ? selected : "";
  state.identityKeySourceLocalKey = identityKeySource.value || null;
  state.identityKeySourceAssetId = null;
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
  state.identityKeySourceLocalKey = null;
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
  state.identityKeySourceLocalKey = item.source_local_key || null;
  const source = state.localAssetSources.find((candidate) => candidate.source_key === state.identityKeySourceLocalKey);
  identityKeySource.value = source?.source_key || "";
  identityKeyTitle.textContent = item.identity_key_id ? `Identity Key | ${item.label}` : `New Identity Key | ${item.label || "Local source"}`;
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
  identityKeyCreatePreview.disabled = !source;
  identityKeySave.disabled = !source;
}

async function selectIdentityKey(identityKeyId) {
  const item = state.identityKeys.find((key) => key.identity_key_id === identityKeyId);
  if (!item) {
    return;
  }
  state.selectedIdentityKeyId = identityKeyId;
  state.identityKeySourceAssetId = item.source_asset_id;
  state.identityKeySourceLocalKey = item.source_local_key || null;
  identityKeySource.value = state.identityKeySourceLocalKey || "";
  state.identityKeyPreview = null;
  renderIdentityKeyTable();
  renderIdentityKeyUpdate(item);
}

async function createIdentityKeyPreview() {
  const sourceLocalKey = state.identityKeySourceLocalKey;
  if (!sourceLocalKey) {
    return;
  }
  showIdentityKeyMessage("Creating Identity Key preview...");
  identityKeyCreatePreview.disabled = true;
  try {
    const payload = await fetchJson(`/api/identity-keys/preview?${currentQuery().toString()}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_local_key: sourceLocalKey,
        identity_key_id: state.selectedIdentityKeyId,
        label: identityKeyLabel.value || "",
        crop_percent: Number(identityKeyPercent.value || 0),
      }),
    });
    state.identityKeyPreview = payload.preview;
    const item = state.selectedIdentityKeyId
      ? state.identityKeys.find((key) => key.identity_key_id === state.selectedIdentityKeyId)
      : {
          source_local_key: sourceLocalKey,
          source_image_path: payload.preview?.source_image_path,
          label: identityKeyLabel.value || "",
          crop_percent: Number(identityKeyPercent.value || 0),
        };
    renderIdentityKeyUpdate(item || {});
    showIdentityKeyMessage("Identity Key preview created.");
  } catch (error) {
    showIdentityKeyMessage(error.message, "error");
  } finally {
    identityKeyCreatePreview.disabled = !state.identityKeySourceLocalKey;
  }
}

async function saveIdentityKey() {
  const sourceLocalKey = state.identityKeySourceLocalKey;
  if (!sourceLocalKey) {
    return;
  }
  showIdentityKeyMessage("Saving Identity Key...");
  identityKeySave.disabled = true;
  try {
    const payload = await fetchJson(`/api/identity-keys?${currentQuery().toString()}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_local_key: sourceLocalKey,
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
    identityKeySave.disabled = !state.identityKeySourceLocalKey;
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
    renderEmptyRow(costumeTableBody, 3, "No costumes exist for this character and phase.");
    return;
  }
  for (const costume of state.costumes) {
    const row = document.createElement("tr");
    row.dataset.costumeSlug = costume.slug;
    row.classList.toggle("selected", costume.slug === state.selectedCostumeSlug);
    const nameCell = document.createElement("td");
    nameCell.textContent = costume.name || "";
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
    row.append(nameCell, pathCell, actionCell);
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
  costumeDelete.hidden = !isUpdate;
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

async function deleteSelectedCostume() {
  const costume = selectedCostume();
  if (!costume || !state.character || !state.phase) return;
  if (!window.confirm(`Move ${costume.name} and all of its templates and character assets to the library deleted folder?`)) return;
  costumeDelete.disabled = true;
  showCostumeMessage("Moving costume to deleted storage...");
  try {
    const payload = await fetchJson(`/api/costumes/${encodeURIComponent(costume.slug)}?${currentQuery().toString()}`, { method: "DELETE" });
    state.costumes = payload.costumes || [];
    state.selectedCostumeSlug = null;
    costumeName.value = "";
    costumeTemplateFile.value = "";
    renderCostumeTable();
    renderCostumeEditor();
    showCostumeMessage(payload.message || "Costume moved to deleted storage.");
    await loadAssets();
  } catch (error) {
    if (error.detail?.references) showCostumeReferenceConflict(error.detail);
    else showCostumeMessage(error.message, "error");
  } finally {
    costumeDelete.disabled = false;
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

function showCostumeWizardMessage(message, kind = "info") {
  costumeWizardMessage.hidden = !message;
  costumeWizardMessage.textContent = message || "";
  costumeWizardMessage.className = `action-message ${kind}`.trim();
}

function setCostumeWizardSession(session) {
  state.costumeWizard = session;
  costumeWizardContext.textContent = `${session.character} / ${session.phase} · ${session.status || "Draft"}`;
  costumeWizardIntake.hidden = Boolean(session.markdown || session.session_id);
  costumeWizardWorkspace.hidden = !session.session_id;
  costumeWizardMarkdown.value = session.markdown || "";
  const draftReview = [session.draft_review || "", ...(session.refinements || []).map((item) => `Suggested refinement: ${item}`)]
    .filter(Boolean).join("\n\n");
  costumeWizardReview.hidden = !draftReview;
  costumeWizardReview.textContent = draftReview;
  const errors = session.validation_errors || [];
  costumeWizardErrors.hidden = !errors.length;
  costumeWizardErrors.textContent = errors.join("\n");
  costumeWizardQuestions.replaceChildren();
  const questions = session.questions || [];
  questions.forEach((question, index) => {
    const label = document.createElement("label");
    label.textContent = question;
    const input = document.createElement("textarea");
    input.rows = 2;
    input.dataset.questionIndex = String(index);
    label.append(input);
    costumeWizardQuestions.append(label);
  });
  costumeWizardAnswer.hidden = !questions.length;
  costumeWizardGenerate.hidden = !(session.status === "FAILED" && !session.markdown);
  const running = session.job?.status === "RUNNING";
  costumeWizardGenerate.disabled = running;
  costumeWizardTestResult.replaceChildren();
  const renders = session.test_renders || [];
  costumeWizardTestResult.hidden = !renders.length;
  renders.forEach((render, index) => {
    const card = document.createElement("article");
    const heading = document.createElement("strong");
    heading.textContent = `Front test ${index + 1}${render.revision_id === session.revision_id ? " · current draft" : " · earlier draft"}`;
    const image = document.createElement("img");
    image.src = `${render.image_url}?v=${encodeURIComponent(render.render_id)}`;
    image.alt = `Costume Wizard front test render ${index + 1}`;
    const review = document.createElement("p");
    review.textContent = render.review || "The test render is ready for review.";
    card.append(heading, image, review);
    if ((render.refinements || []).length) {
      const suggestions = document.createElement("p");
      suggestions.textContent = `Suggested refinements:\n${render.refinements.map((item) => `• ${item}`).join("\n")}`;
      card.append(suggestions);
    }
    costumeWizardTestResult.append(card);
  });
  costumeWizardMarkdown.disabled = running;
  costumeWizardCreate.disabled = running;
  costumeWizardAnswer.disabled = running;
  costumeWizardSave.disabled = running || !session.markdown;
  costumeWizardTest.disabled = running || !session.markdown;
  costumeWizardAccept.disabled = running || !session.markdown || errors.length > 0;
  costumeWizardRefine.disabled = running || !session.markdown;
  costumeWizardAbandon.disabled = session.status === "ACCEPTED" || session.status === "ABANDONED";
  if (running) {
    showCostumeWizardMessage(`${session.job?.kind === "render" ? "Rendering and reviewing" : "Analyzing references and drafting"}…`);
    scheduleCostumeWizardPoll(session.session_id);
  } else if (session.job?.status === "FAILED") {
    showCostumeWizardMessage(session.job.error || "The wizard task failed. Review the draft and retry.", "error");
  } else if (session.status === "NEEDS_INPUT") {
    showCostumeWizardMessage("Answer the questions below to continue drafting.");
  } else if (session.markdown && !errors.length) {
    showCostumeWizardMessage("Draft is ready. Save, test, or accept this revision.");
  }
}

function scheduleCostumeWizardPoll(sessionId) {
  clearTimeout(costumeWizardPollTimer);
  costumeWizardPollTimer = setTimeout(async () => {
    try {
      const payload = await fetchJson(`/api/costume-wizard/${encodeURIComponent(sessionId)}`);
      setCostumeWizardSession(payload.session);
    } catch (error) {
      showCostumeWizardMessage(error.message, "error");
    }
  }, 1800);
}

async function loadCostumeWizardSessions() {
  const params = currentQuery();
  const payload = await fetchJson(`/api/costume-wizard?${params.toString()}`);
  costumeWizardResume.replaceChildren(option("", "New costume draft"));
  for (const session of payload.sessions || []) {
    costumeWizardResume.append(option(session.session_id, `${session.name} · ${session.status}`));
  }
}

function clearCostumeWizardIntake() {
  costumeWizardName.value = "";
  costumeWizardExtra.value = "";
  for (const slot of document.querySelectorAll(".costume-wizard-image-slot")) {
    slot.querySelector(".costume-wizard-file").value = "";
    slot.querySelector(".costume-wizard-caption").value = "";
    slot.querySelector(".costume-wizard-preview").removeAttribute("src");
    slot.querySelector(".costume-wizard-preview").hidden = true;
  }
  state.costumeWizard = null;
  costumeWizardWorkspace.hidden = true;
  costumeWizardIntake.hidden = false;
}

async function openCostumeWizard() {
  clearCostumeWizardIntake();
  costumeWizardContext.textContent = `${state.character || ""} / ${state.phase || ""}`;
  showCostumeWizardMessage("");
  costumeWizardDialog.showModal();
  try {
    await loadCostumeWizardSessions();
  } catch (error) {
    showCostumeWizardMessage(error.message, "error");
  }
}

async function resumeCostumeWizard() {
  const sessionId = costumeWizardResume.value;
  if (!sessionId) return;
  try {
    const payload = await fetchJson(`/api/costume-wizard/${encodeURIComponent(sessionId)}`);
    costumeWizardIntake.hidden = true;
    costumeWizardName.value = payload.session.name || "";
    setCostumeWizardSession(payload.session);
  } catch (error) {
    showCostumeWizardMessage(error.message, "error");
  }
}

async function createCostumeWizardDraft() {
  const name = costumeWizardName.value.trim();
  if (!name) return showCostumeWizardMessage("Costume name is required.", "error");
  const form = new FormData();
  form.set("name", name);
  form.set("extra_info", costumeWizardExtra.value);
  let count = 0;
  for (const slot of document.querySelectorAll(".costume-wizard-image-slot")) {
    const file = slot.querySelector(".costume-wizard-file").files?.[0];
    const caption = slot.querySelector(".costume-wizard-caption").value.trim();
    if (file) {
      count += 1;
      if (!caption) return showCostumeWizardMessage(`Describe what reference image ${slot.dataset.slot} conveys.`, "error");
      form.set(`image_${slot.dataset.slot}`, file, file.name);
      form.set(`caption_${slot.dataset.slot}`, caption);
    }
  }
  if (!count) return showCostumeWizardMessage("Add at least one reference image.", "error");
  costumeWizardCreate.disabled = true;
  try {
    const params = currentQuery();
    const payload = await fetchJson(`/api/costume-wizard?${params.toString()}`, { method: "POST", body: form });
    costumeWizardIntake.hidden = true;
    costumeWizardName.value = payload.session.name || name;
    setCostumeWizardSession(payload.session);
    await loadCostumeWizardSessions();
  } catch (error) {
    showCostumeWizardMessage(error.message, "error");
    costumeWizardCreate.disabled = false;
  }
}

async function submitCostumeWizardAnswers() {
  const session = state.costumeWizard;
  if (!session) return;
  const answers = Array.from(costumeWizardQuestions.querySelectorAll("textarea[data-question-index]"))
    .map((input) => ({ question: session.questions[Number(input.dataset.questionIndex)], answer: input.value.trim() }));
  if (answers.some((item) => !item.answer)) return showCostumeWizardMessage("Answer each question to continue.", "error");
  try {
    const payload = await fetchJson(`/api/costume-wizard/${encodeURIComponent(session.session_id)}/answers`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answers }),
    });
    setCostumeWizardSession(payload.session);
  } catch (error) { showCostumeWizardMessage(error.message, "error"); }
}

async function retryCostumeWizardDraft() {
  const session = state.costumeWizard;
  if (!session) return;
  try {
    const payload = await fetchJson(`/api/costume-wizard/${encodeURIComponent(session.session_id)}/generate`, { method: "POST" });
    setCostumeWizardSession(payload.session);
  } catch (error) { showCostumeWizardMessage(error.message, "error"); }
}

async function saveCostumeWizardDraft() {
  const session = state.costumeWizard;
  if (!session) return;
  try {
    const payload = await fetchJson(`/api/costume-wizard/${encodeURIComponent(session.session_id)}/draft`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ revision_id: session.revision_id, markdown: costumeWizardMarkdown.value }),
    });
    setCostumeWizardSession(payload.session);
    showCostumeWizardMessage("Draft saved.");
  } catch (error) { showCostumeWizardMessage(error.message, "error"); }
}

async function testCostumeWizardDraft() {
  const session = state.costumeWizard;
  if (!session) return;
  try {
    if (costumeWizardMarkdown.value !== session.markdown) await saveCostumeWizardDraft();
    const current = state.costumeWizard;
    const payload = await fetchJson(`/api/costume-wizard/${encodeURIComponent(current.session_id)}/render`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ revision_id: current.revision_id }),
    });
    setCostumeWizardSession(payload.session);
  } catch (error) { showCostumeWizardMessage(error.message, "error"); }
}

async function applyCostumeWizardRefinements() {
  const session = state.costumeWizard;
  if (!session) return;
  try {
    const payload = await fetchJson(`/api/costume-wizard/${encodeURIComponent(session.session_id)}/refine`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ revision_id: session.revision_id, instructions: costumeWizardRefinement.value }),
    });
    setCostumeWizardSession(payload.session);
    costumeWizardRefinement.value = "";
  } catch (error) { showCostumeWizardMessage(error.message, "error"); }
}

async function acceptCostumeWizardDraft() {
  const session = state.costumeWizard;
  if (!session) return;
  try {
    if (costumeWizardMarkdown.value !== session.markdown) await saveCostumeWizardDraft();
    const current = state.costumeWizard;
    const payload = await fetchJson(`/api/costume-wizard/${encodeURIComponent(current.session_id)}/accept`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ revision_id: current.revision_id }),
    });
    state.costumes = payload.costumes || state.costumes;
    state.selectedCostumeSlug = payload.costume?.slug || null;
    renderCostumeTable();
    renderCostumeEditor();
    costumeWizardDialog.close();
    showCostumeMessage(payload.message || "Costume accepted.");
  } catch (error) { showCostumeWizardMessage(error.message, "error"); }
}

async function abandonCostumeWizard() {
  const session = state.costumeWizard;
  if (!session) { costumeWizardDialog.close(); return; }
  try {
    await fetchJson(`/api/costume-wizard/${encodeURIComponent(session.session_id)}/abandon`, { method: "POST" });
    clearTimeout(costumeWizardPollTimer);
    costumeWizardDialog.close();
    showCostumeMessage("Costume Wizard draft abandoned.");
  } catch (error) { showCostumeWizardMessage(error.message, "error"); }
}

for (const slot of document.querySelectorAll(".costume-wizard-image-slot")) {
  const fileInput = slot.querySelector(".costume-wizard-file");
  const pasteZone = slot.querySelector(".costume-wizard-paste");
  const preview = slot.querySelector(".costume-wizard-preview");
  const showPreview = (file) => {
    if (!file) return;
    preview.src = URL.createObjectURL(file);
    preview.hidden = false;
  };
  fileInput.addEventListener("change", () => showPreview(fileInput.files?.[0]));
  pasteZone.addEventListener("click", () => pasteZone.focus());
  pasteZone.addEventListener("paste", (event) => {
    const item = Array.from(event.clipboardData?.items || []).find((entry) => entry.type.startsWith("image/"));
    const file = item?.getAsFile();
    if (!file) return;
    event.preventDefault();
    const transfer = new DataTransfer();
    transfer.items.add(new File([file], `pasted-costume-${slot.dataset.slot}.png`, { type: file.type || "image/png" }));
    fileInput.files = transfer.files;
    showPreview(fileInput.files[0]);
  });
}

costumeWizardOpen.addEventListener("click", openCostumeWizard);
costumeWizardClose.addEventListener("click", () => { clearTimeout(costumeWizardPollTimer); costumeWizardDialog.close(); });
costumeWizardResumeButton.addEventListener("click", resumeCostumeWizard);
costumeWizardCreate.addEventListener("click", createCostumeWizardDraft);
costumeWizardGenerate.addEventListener("click", retryCostumeWizardDraft);
costumeWizardAnswer.addEventListener("click", submitCostumeWizardAnswers);
costumeWizardSave.addEventListener("click", saveCostumeWizardDraft);
costumeWizardTest.addEventListener("click", testCostumeWizardDraft);
costumeWizardRefine.addEventListener("click", applyCostumeWizardRefinements);
costumeWizardAccept.addEventListener("click", acceptCostumeWizardDraft);
costumeWizardAbandon.addEventListener("click", abandonCostumeWizard);

function sceneAppearanceReferenceLines(references) {
  return (references || []).map((item) => `${item.role || ""} | ${item.label || ""} | ${item.tag || ""}`).join("\n");
}

function parseSceneAppearanceReferences() {
  return sceneAppearanceReferences.value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line) => {
    const parts = line.split("|").map((part) => part.trim());
    if (parts.length !== 3 || parts.some((part) => !part)) {
      throw new Error(`Invalid supporting reference line: ${line}`);
    }
    return { role: parts[0], label: parts[1], tag: parts[2] };
  });
}

function selectedSceneAppearance() {
  return state.sceneAppearances.find((item) => item.appearance_id === state.selectedSceneAppearanceId) || null;
}

function fillSceneAppearanceCostumes(selected = "") {
  const names = state.costumes.map((item) => item.name).filter(Boolean);
  sceneAppearanceCostume.replaceChildren(...names.map((name) => option(name, name)));
  sceneAppearanceCostume.value = selected && names.includes(selected) ? selected : (names[0] || "");
}

function renderSceneAppearanceTable() {
  sceneAppearanceTableBody.replaceChildren();
  if (!state.sceneAppearances.length) {
    renderEmptyRow(sceneAppearanceTableBody, 5, "No Scene Appearances exist for this character and phase.");
    return;
  }
  for (const appearance of state.sceneAppearances) {
    const row = document.createElement("tr");
    row.classList.toggle("selected", appearance.appearance_id === state.selectedSceneAppearanceId);
    const nameCell = document.createElement("td");
    nameCell.textContent = appearance.name || appearance.appearance_id;
    const costumeCell = document.createElement("td");
    costumeCell.textContent = appearance.costume || "";
    const countCell = document.createElement("td");
    countCell.textContent = appearance.asset_count ?? 0;
    const pathCell = document.createElement("td");
    pathCell.textContent = basename(appearance.path || "");
    pathCell.title = appearance.path || "";
    const actionCell = document.createElement("td");
    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.textContent = "Edit";
    editButton.addEventListener("click", (event) => {
      event.stopPropagation();
      selectSceneAppearance(appearance.appearance_id);
    });
    const openButton = document.createElement("button");
    openButton.type = "button";
    openButton.textContent = "Open";
    openButton.disabled = !appearance.source?.source_path;
    openButton.addEventListener("click", (event) => {
      event.stopPropagation();
      if (appearance.source?.source_path) {
        openSourceEditorForSource(appearance.source, showSceneAppearanceMessage);
      }
    });
    actionCell.append(editButton, openButton);
    row.append(nameCell, costumeCell, countCell, pathCell, actionCell);
    makeSelectableRow(row, appearance.name || appearance.appearance_id, appearance.appearance_id === state.selectedSceneAppearanceId, () => selectSceneAppearance(appearance.appearance_id));
    sceneAppearanceTableBody.append(row);
  }
}

function clearSceneAppearanceForm() {
  state.selectedSceneAppearanceId = null;
  sceneAppearanceId.value = "";
  sceneAppearanceId.disabled = false;
  sceneAppearanceName.value = "";
  sceneAppearanceInstructions.value = "";
  sceneAppearanceReferences.value = "";
  fillSceneAppearanceCostumes();
  renderSceneAppearanceEditor();
  renderSceneAppearanceTable();
}

function selectSceneAppearance(appearanceId) {
  state.selectedSceneAppearanceId = appearanceId;
  const appearance = selectedSceneAppearance();
  sceneAppearanceId.value = appearance?.appearance_id || "";
  sceneAppearanceName.value = appearance?.name || "";
  sceneAppearanceInstructions.value = appearance?.instructions || "";
  sceneAppearanceReferences.value = sceneAppearanceReferenceLines(appearance?.supporting_references);
  fillSceneAppearanceCostumes(appearance?.costume || "");
  renderSceneAppearanceEditor();
  renderSceneAppearanceTable();
}

function renderSceneAppearanceEditor() {
  const appearance = selectedSceneAppearance();
  const isUpdate = Boolean(appearance);
  sceneAppearanceFormTitle.textContent = isUpdate ? "Update Scene Appearance" : "Add Scene Appearance";
  sceneAppearanceSave.textContent = isUpdate ? "Update Scene Appearance" : "Save Scene Appearance";
  sceneAppearanceId.disabled = isUpdate;
  sceneAppearancePreviewSection.hidden = !isUpdate;
  if (isUpdate) {
    renderReviewImage(
      sceneAppearancePreview,
      appearance.locked_preview_path,
      appearance.locked_preview_exists,
      "No locked turnaround.",
      "Locked Scene Appearance turnaround",
      appearance.path || appearance.name || "",
    );
  }
}

async function loadSceneAppearances() {
  if (!state.character || !state.phase) {
    sceneAppearanceStatus.textContent = "No character/phase selected.";
    return;
  }
  sceneAppearanceStatus.textContent = "Loading Scene Appearances...";
  if (!state.costumes.length) await loadCostumes();
  const payload = await fetchJson(`/api/scene-appearances?${currentQuery().toString()}`);
  state.sceneAppearances = payload.scene_appearances || [];
  if (state.selectedSceneAppearanceId && !state.sceneAppearances.some((item) => item.appearance_id === state.selectedSceneAppearanceId)) {
    state.selectedSceneAppearanceId = null;
  }
  renderSceneAppearanceTable();
  if (state.selectedSceneAppearanceId) selectSceneAppearance(state.selectedSceneAppearanceId);
  else clearSceneAppearanceForm();
  sceneAppearanceStatus.textContent = `${state.sceneAppearances.length} Scene Appearance set(s)`;
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

async function loadStories(selectSlug = state.selectedStorySlug, options = {}) {
  const stories = await fetchJson('/api/narrative/stories', options);
  state.stories = stories.map(story=>({...story,slug:story.id}));
  state.selectedStorySlug = state.stories.some(story=>story.id===selectSlug) ? selectSlug : state.stories[0]?.id || null;
  const story = state.stories.find(story=>story.id===state.selectedStorySlug);
  setCanonicalSceneCollection(story?.id || '', (story?.scenes || []).map(scene=>({...scene,slug:scene.id})));
  renderHeaderStoryContext();
  renderZineStoryOptions();
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



function storySettingPathLabel(path) {
  return path.map((part) => String(part)).join(".");
}

function storySettingInputValue(value) {
  if (value === undefined) return "";
  if (value === null) return "null";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

const readOnlyStorySettingPaths = new Set([
  "schema_version",
  "file_kind",
  "story.id",
  "story.title",
  "story.slug",
  "story.human_markdown_path",
  "metadata.created_at",
  "metadata.updated_at",
  "metadata.created_by",
]);

function renderReadOnlyStorySetting(path, value) {
  const field = document.createElement("div");
  field.className = "story-setting-readonly";
  field.textContent = `${storySettingPathLabel(path)}: ${storySettingInputValue(value)}`;
  return field;
}

function isStorySettingCsvList(path, value) {
  if (!Array.isArray(value) || !value.every((item) => typeof item === "string")) {
    return false;
  }
  const textPath = storySettingPathLabel(path);
  return textPath === "compiler_profiles.local_render.negative_text_terms"
    || /^dialog(?:ue)?_styles\.\d+\.(?:avoid|layout_rules)$/.test(textPath);
}



function appendStorySettingFields(container, value, path = [], readOnlyFields = []) {
  if (readOnlyStorySettingPaths.has(storySettingPathLabel(path))) {
    readOnlyFields.push([path, value]);
    return;
  }
  if (Array.isArray(value)) {
    if (isStorySettingCsvList(path, value)) {
      container.append(renderStorySettingField(path, value));
      return;
    }
    if (!value.length) {
      container.append(renderStorySettingField(path, value));
      return;
    }
    value.forEach((item, index) => appendStorySettingFields(container, item, [...path, index], readOnlyFields));
    return;
  }
  if (value && typeof value === "object") {
    const keys = Object.keys(value).filter((key) => !(path.length === 0 && key === "scene_index"));
    if (!keys.length) {
      container.append(renderStorySettingField(path, value));
      return;
    }
    keys.forEach((key) => appendStorySettingFields(container, value[key], [...path, key], readOnlyFields));
    return;
  }
  container.append(renderStorySettingField(path, value));
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
}





async function selectStory(storySlug) {
  // Select one story and refresh the current page context.
  if (storySlug === state.selectedStorySlug) return;
  await runGuardedTransition(async () => {
    state.selectedStorySlug = storySlug;
    state.selectedSceneSlug = null;
    state.scenes = [];
    saveStoredStoryContext();
    renderStoryTable();
    renderSceneStoryOptions();
    if (document.querySelector("#stories-page").classList.contains("active")) {
      await loadStoryDetail(storySlug);
    }
    if (document.querySelector("#scenes-page").classList.contains("active")) {
      await loadScenesPage();
    } else {
      await loadWorkspaceSummary();
    }
  });
}







async function openStoryScenes() {
  if (!state.selectedStorySlug) return;
  await activatePage("scenes");
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
  const destinations = state.stories.filter((story) => story.slug !== state.selectedStorySlug);
  sceneMoveStory.replaceChildren(...destinations.map((story) => option(story.slug, story.title || story.slug)));
  sceneMove.disabled = !sceneDocumentMatches() || !destinations.length;
  saveStoredStoryContext();
  renderHeaderStoryContext();
}



function updateSceneImageToggle() {
  const imagePath = state.sceneDetail?.image_path || "";
  const hasImage = Boolean(state.sceneDetail?.image_exists && imagePath);
  setCandidatePendingLink(sceneImageCandidateLink, state.sceneDetail);
  sceneToggleImage.disabled = !hasImage;
  if (!hasImage) {
    sceneImagePanel.hidden = true;
    sceneImagePreview.removeAttribute("src");
  } else if (!sceneImagePanel.hidden) {
    sceneImagePreview.src = fileUrl(imagePath, Date.now().toString());
  }
}







async function loadSceneDetail(storySlug, sceneSlug, selection = null) {
  // Load one scene markdown document into the scene editor.
  if (!storySlug || !sceneSlug) {
    clearSceneEditor();
    return;
  }
  const activeSelection = selection || beginSelection("story-scene");
  state.requestedSceneContext = { storySlug, sceneSlug };
  clearRequestedSceneDocument();
  state.selectedStorySlug = storySlug;
  state.selectedSceneSlug = sceneSlug;
  renderHeaderStoryContext();
  renderSceneTable();
  sceneEditorTitle.textContent = "Loading scene...";
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(storySlug)}/scenes/${encodeURIComponent(sceneSlug)}`, {
      signal: activeSelection.controller.signal,
    });
    if (!selectionIsCurrent(activeSelection) || state.requestedSceneContext.storySlug !== storySlug || state.requestedSceneContext.sceneSlug !== sceneSlug) {
      return;
    }
    state.sceneDetail = payload.document || null;
    state.loadedSceneContext = {
      storySlug: state.sceneDetail?.story?.slug || storySlug,
      sceneSlug: state.sceneDetail?.scene?.slug || sceneSlug,
    };
    saveStoredStoryContext();
    renderHeaderStoryContext();
    renderSceneTable();
    sceneEditorTitle.textContent = state.sceneDetail?.scene?.title || "Scene";
    sceneRenameTitle.value = state.sceneDetail?.scene?.title || "";
    sceneText.value = state.sceneDetail?.text || "";
    updateSceneContextControls();
    renderSceneStoryOptions();
    closeSceneBuilder();
    updateSceneImageToggle();
    renderValidationBox(sceneValidation, state.sceneDetail?.validation_errors || [], "Scene markdown is valid.");
    state.savedBaselines.scene = sceneSnapshot();
    setSaveState(sceneSaveState, "Saved", "saved");
  } catch (error) {
    if (isRequestCancellation(error)) return;
    if (!selectionIsCurrent(activeSelection)) return;
    state.loadedSceneContext = { storySlug: "", sceneSlug: "" };
    state.sceneDetail = null;
    updateSceneContextControls();
    sceneEditorTitle.textContent = "Scene unavailable";
    sceneText.value = "";
    sceneRenameTitle.value = "";
    state.savedBaselines.scene = "";
    showSceneMessage(error.message, "error");
  }
}

async function selectScene(sceneSlug) {
  await selectStoryScene(state.selectedStorySlug, sceneSlug);
}

async function selectStoryScene(storySlug, sceneSlug = null, options = {}) {
  const execute = async () => {
    const nextStory = storySlug || null;
    const storyChanged = nextStory !== state.selectedStorySlug;
    const selection = beginSelection("story-scene");
    state.selectionControllers["scene-builder"]?.abort();
    if (storyChanged) {
      state.selectedStorySlug = nextStory;
      state.selectedSceneSlug = null;
      state.requestedSceneContext = { storySlug: nextStory || "", sceneSlug: "" };
      state.loadedSceneContext = { storySlug: "", sceneSlug: "" };
      state.sceneDetail = null;
      state.scenes = [];
      state.sceneCollection = { storySlug: nextStory || "", items: [] };
      saveStoredStoryContext();
      renderHeaderStoryContext();
      if (nextStory) {
        await loadStories(nextStory, { signal: selection.controller.signal });
        if (!selectionIsCurrent(selection)) return false;
      }
    }

    const scenes = canonicalSceneCollection(nextStory);
    const nextScene = sceneSlug
      ? (scenes.some((item) => item.slug === sceneSlug) ? sceneSlug : scenes[0]?.slug || null)
      : scenes[0]?.slug || null;
    state.selectedStorySlug = nextStory;
    state.selectedSceneSlug = nextScene;
    state.requestedSceneContext = { storySlug: nextStory || "", sceneSlug: nextScene || "" };
    saveStoredStoryContext();
    renderHeaderStoryContext();
    renderStoryOverview();
    renderSceneTable();
    if (options.updateHistory !== false && !options.fromHistory
      && (!options.destination || activePageName() === options.destination)) {
      syncBrowserRoute();
    }

    if (nextStory && nextScene && !sceneDocumentMatches(nextStory, nextScene)) {
      await loadSceneDetail(nextStory, nextScene, selection);
    }
    if (options.destination) {
      await activatePage(options.destination, {
        skipAutosave: true,
        updateHistory: false,
        renderTargetId: options.renderTargetId || (options.destination === "scene-builder" ? state.activeBuilderRenderTarget : "main"),
        preferredAskId: options.preferredAskId,
        preferredReviewKey: options.destination === "render-review" ? `scene:${nextStory}:${nextScene}` : null,
      });
    } else if (activePageName() === "scene-builder" && nextScene) {
      await openSceneBuilder(options.renderTargetId || state.activeBuilderRenderTarget || "main");
    } else if (activePageName() === "scene-batches") {
      await window.SceneBatches.open({story: nextStory, scene: nextScene});
    } else if (PRODUCTION_PAGES.has(activePageName())) {
      await reloadActiveProductionPage();
    }
    if (options.updateHistory !== false && !options.fromHistory) syncBrowserRoute();
    return true;
  };
  return options.skipGuard ? execute() : runGuardedTransition(execute);
}













function toggleSceneImage() {
  const imagePath = state.sceneDetail?.image_path || "";
  if (!state.sceneDetail?.image_exists || !imagePath) {
    return;
  }
  if (sceneImagePanel.hidden) {
    sceneImagePreview.src = fileUrl(imagePath, Date.now().toString());
    setCandidatePendingLink(sceneImageCandidateLink, state.sceneDetail);
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
  state.zineLoadState = document ? "selected" : "absent";
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
    if (isRequestCancellation(error)) return;
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
    if (zineTaskRestorePending && taskStoryRoute.get("task_zine")) {
      const requested = taskStoryRoute.get("task_zine");
      if (state.zines.some(item=>item.slug===requested)) state.selectedZineSlug = requested;
      else window.ZetTaskCapture.notice(`Recorded zine "${requested}" is unavailable. Showing an available zine.`);
    }
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
    if (zineTaskRestorePending) {
      const story = taskStoryRoute.get("story_slug");
      if (state.stories.some(item=>item.slug===story)) { state.zineStorySlug = story; renderZineStoryOptions(); await loadZineStorySources(); }
      zineTaskRestorePending = false;
    }
    zineStatus.textContent = `${state.zines.length} zine${state.zines.length === 1 ? "" : "s"}`;
  } catch (error) {
    if (isRequestCancellation(error)) return;
    zineStatus.textContent = "Load failed.";
    showZineMessage(error.message, "error");
  }
}

async function selectZine(slug, options = {}) {
  if (slug === state.selectedZineSlug && state.zineDocument?.zine?.slug === slug) return;
  const select = async () => {
    state.selectedZineSlug = slug;
    state.zineLoadState = "loading";
    renderZineTable();
    try {
      const payload = await fetchJson(`/api/zines/${encodeURIComponent(slug)}`);
      if (state.selectedZineSlug !== slug) return;
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
      if (state.selectedZineSlug === slug) state.zineLoadState = "unavailable";
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
  state.loadedBuilderContext = { storySlug: "", sceneSlug: "" };
  state.sceneBuilderRenderTargets = [];
  state.activeBuilderRenderTarget = "main";
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
  const scenes = canonicalSceneCollection(state.selectedStorySlug);
  let index = scenes.findIndex((scene) => scene.slug === state.selectedSceneSlug);
  if (index < 0) {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes`);
    setCanonicalSceneCollection(state.selectedStorySlug, payload.scenes || []);
    index = canonicalSceneCollection(state.selectedStorySlug).findIndex((scene) => scene.slug === state.selectedSceneSlug);
  }
  const target = canonicalSceneCollection(state.selectedStorySlug)[index + offset];
  if (!target) return;
  await selectStoryScene(state.selectedStorySlug, target.slug, {
    destination: "scene-builder",
    renderTargetId: "main",
  });
}

async function returnToScenesFromBuilder() {
  if (!(await guardCurrentEditor())) return;
  closeSceneBuilder();
  await activatePage("scenes", { skipAutosave: true });
}





async function restartZetFromToolbar() {
  const dialog = document.createElement("dialog");
  dialog.className = "task-capture-dialog";
  const heading = document.createElement("h2"); heading.textContent = "Restart Zet";
  const status = document.createElement("p"); status.setAttribute("role", "status");
  const update = document.createElement("button"); update.textContent = "Update and restart";
  const restart = document.createElement("button"); restart.textContent = "Restart current version";
  const cancel = document.createElement("button"); cancel.textContent = "Cancel";
  dialog.append(heading, status, update, restart, cancel); document.body.append(dialog); dialog.showModal();
  cancel.onclick = () => dialog.close();
  dialog.addEventListener("close", () => dialog.remove(), { once: true });
  const deployment = await fetchJson("/api/deployment").catch(() => null);
  update.disabled = !deployment?.configured || deployment.role === "development";
  status.textContent = update.disabled ? "Updates are unavailable in this instance." : "Update installs merged main after isolated validation. Your library is preserved.";
  async function begin(updating) {
    const returnUrl = window.location.href;
    const before = await fetchJson("/api/health");
    update.disabled = restart.disabled = cancel.disabled = true;
    toolbarRestartZet.disabled = true;
    status.textContent = updating ? "Staging and validating the merged release…" : "Restarting Zet…";
    try {
      const operation = await fetchJson(updating ? "/api/deployment/update" : "/api/processes/restart-zet", { method: "POST" });
      const previousBoot = operation.previous_boot || before.boot_id;
      let expectedRevision = updating ? null : operation.expected_revision;
      let finished = !updating;
      const deadline = Date.now() + (updating ? 1200000 : 120000);
      while (Date.now() < deadline) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        if (updating) {
          let current = null;
          try {
            current = (await fetchJson("/api/deployment")).operation;
          } catch { /* Listener is restarting. */ }
          if (current?.id === operation.id) {
            status.textContent = `Update: ${current.state}`;
            expectedRevision = current.target_revision || expectedRevision;
            finished = current.state === "succeeded";
            if (["failed", "rolled-back", "recovery-required"].includes(current.state)) throw new Error(current.error || current.recovery_error || "Update failed; inspect Tasks for recovery details.");
          }
        }
        try {
          const health = await fetchJson("/api/health");
          if (finished && health.ready && health.boot_id !== previousBoot && health.revision === expectedRevision) {
            window.location.replace(returnUrl); return;
          }
        } catch { /* Listener is restarting. */ }
      }
      throw new Error("Restart has not reported the expected new boot and revision. Inspect Tasks or reload later.");
    } catch (error) {
      status.textContent = error.message;
      cancel.disabled = false;
      restart.disabled = false;
      toolbarRestartZet.disabled = false;
    }
  }
  update.onclick = () => void begin(true);
  restart.onclick = () => void begin(false);
}


const BUILDER_SUBSCENE_COLORS = ["#DDEAF4", "#E4E0F3", "#F3E1E7", "#F4E7D5", "#E2EEDC", "#DCEDEA"];

































































function closeBuilderElementAuxForm() {
  builderElementNewAuxForm.hidden = true;
  builderElementNewAuxLabel.value = "";
  builderElementNewAuxStatus.textContent = "";
}

async function createBuilderElementAuxResource() {
  const category = builderAuxCategoryForResourceType(builderElementResourceType.value || "");
  const label = builderElementNewAuxLabel.value.trim();
  if (!category || !label) {
    builderElementNewAuxStatus.textContent = "Resource label is required.";
    return;
  }
  builderElementNewAuxSave.disabled = true;
  builderElementNewAuxStatus.textContent = "Creating resource...";
  try {
    const payload = await fetchJson("/api/image-catalog/reference-sets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label, legacy_category: category }),
    });
    state.builderElementAuxResources[category] = null;
    await builderLoadElementAuxResources();
    builderElementAux.value = payload.reference_set?.reference_set_id || "";
    closeBuilderElementAuxForm();
  } catch (error) {
    builderElementNewAuxStatus.textContent = error.message;
  } finally {
    builderElementNewAuxSave.disabled = false;
  }
}











































const BUILDER_RESPONSIVE_SECTIONS = [
  ["scene", "Scene"],
  ["elements", "Elements"],
  ["dialogue", "Dialogue"],
  ["environment", "Environment"],
  ["advanced", "Advanced"],
];





function setBuilderResponsiveSection(section) {
  if (!BUILDER_RESPONSIVE_SECTIONS.some(([value]) => value === section)) return;
  state.builderResponsiveSection = section;
  sceneBuilderPanel.dataset.builderResponsiveSection = section;
  for (const button of sceneBuilderPanel.querySelectorAll('[data-builder-action="builder-section"]')) {
    const selected = button.dataset.builderSection === section;
    button.setAttribute(button.getAttribute("role") === "tab" ? "aria-selected" : "aria-expanded", selected ? "true" : "false");
    const indicator = button.querySelector("span[aria-hidden]");
    if (indicator) indicator.textContent = selected ? "−" : "+";
  }
}





function updateBuilderAnalysisActions() {
  const analysis = state.scenePromptAnalysis || {};
  const action = analysis.complete || analysis.pending ? "view-analysis" : "analyze-prompt";
  const label = analysis.complete ? "View latest analysis" : analysis.pending ? "Check analysis" : "Run analysis";
  for (const button of sceneBuilderPanel.querySelectorAll('[data-builder-action="analyze-prompt"], [data-builder-action="view-analysis"]')) {
    button.dataset.builderAction = action;
    if (button.classList.contains("scene-builder-analysis-action")) button.textContent = label;
  }
}



function showSceneCandidateMessage(message, type = "info") {
  sceneCandidateMessage.textContent = message || "";
  sceneCandidateMessage.className = `action-message ${type}`;
  sceneCandidateMessage.hidden = !message;
}

function selectedSceneCandidate() {
  return state.sceneCandidates.find((item) => item.candidate_id === state.selectedSceneCandidateId) || null;
}

function renderSceneCandidateStoryOptions() {
  const select = document.querySelector('#scene-candidate-story');
  if (!select) return;
  select.replaceChildren(...state.stories.map(story=>option(story.id,story.title)));
  select.value = state.selectedSceneCandidateStorySlug || state.stories[0]?.id || '';
  select.addEventListener('change',()=>{state.selectedSceneCandidateStorySlug=select.value;});
}
function renderSceneCandidateDetail() {
  const candidate = selectedSceneCandidate();
  if (!candidate) {sceneCandidateDetail.innerHTML='<p>Select a candidate.</p>';return;}
  const associations = candidate.imported_scenes || [];
  const fields = Object.entries(candidate.fields).map(([name,value])=>`<section><h3>${escapeHtml(name)}</h3><pre>${escapeHtml(Array.isArray(value)?value.join('\n'):value)}</pre></section>`).join('');
  sceneCandidateDetail.innerHTML=`<h2>${escapeHtml(candidate.title)}</h2><p>${escapeHtml(candidate.import_state.replaceAll('_',' '))}</p>
    ${(candidate.warnings || []).map(issue=>`<p>${escapeHtml(issue)}</p>`).join('')}
    ${associations.map((scene,index)=>`<p><a href="/?page=narrative&workspace=story&universe_id=${encodeURIComponent(state.universeId)}&story=${scene.story_id}&scene=${scene.scene_id}">${escapeHtml(scene.title)}</a>${candidate.import_state==='source_changed'?` <button type="button" data-review-candidate="${index}">Review source changes</button>`:''}</p>`).join('')}
    ${!associations.length ? '<label>Import into <select id="scene-candidate-story"></select></label><button id="scene-candidate-import" type="button">Import Narrative stub</button>' : ''}
    <button id="scene-candidate-pass" type="button">${candidate.import_state==='passed'?'Activate':'Pass'}</button>${fields}`;
  renderSceneCandidateStoryOptions();
  document.querySelector('#scene-candidate-import')?.addEventListener('click',importSelectedSceneCandidate);
  document.querySelector('#scene-candidate-pass')?.addEventListener('click',()=>setSelectedSceneCandidatePassed(candidate.import_state!=='passed'));
  for(const button of sceneCandidateDetail.querySelectorAll('[data-review-candidate]')) button.addEventListener('click',async()=>{
    const scene=associations[Number(button.dataset.reviewCandidate)];
    try {
      const url=`/api/narrative/candidates/${encodeURIComponent(candidate.source_key)}/${encodeURIComponent(candidate.candidate_id)}/review`;
      const data={story_id:scene.story_id,scene_id:scene.scene_id};
      const review=await fetchJson(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
      const panel=document.createElement('section');panel.className='candidate-source-review';
      const previous=document.createElement('pre');previous.textContent=JSON.stringify(review.previous,null,2);
      const incoming=document.createElement('pre');incoming.textContent=JSON.stringify(review.incoming,null,2);
      const note=document.createElement('p');note.textContent=review.message;
      const acknowledge=document.createElement('button');acknowledge.textContent='Acknowledge source changes';
      acknowledge.addEventListener('click',async()=>{try{await fetchJson(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...data,acknowledge:true})});await loadSceneCandidates();}catch(error){showSceneCandidateMessage(error.message,'error');}});
      panel.append(note,previous,incoming,acknowledge);button.closest('p').after(panel);button.disabled=true;
    }catch(error){showSceneCandidateMessage(error.message,'error');}
  });
}
function renderSceneCandidates() {
  const filter = sceneCandidateFilter.value || "in_progress";
  const candidates = state.sceneCandidates.filter((item) => filter === "in_progress"
    ? !["rendered", "passed"].includes(item.import_state)
    : item.import_state === filter);
  if (!candidates.some((item) => item.candidate_id === state.selectedSceneCandidateId)) {
    state.selectedSceneCandidateId = candidates[0]?.candidate_id || null;
  }
  sceneCandidateList.replaceChildren();
  for (const candidate of candidates) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `scene-candidate-card${candidate.candidate_id === state.selectedSceneCandidateId ? " active" : ""}`;
    button.innerHTML = `<strong>${escapeHtml(candidate.title)}</strong><small>${escapeHtml(candidate.session || candidate.candidate_id)}</small><span>${escapeHtml(candidate.import_state.replaceAll("_", " "))}</span>`;
    button.addEventListener("click", () => {
      state.selectedSceneCandidateId = candidate.candidate_id;
      renderSceneCandidates();
      renderSceneCandidateDetail();
    });
    sceneCandidateList.append(button);
  }
  if (!candidates.length) sceneCandidateList.innerHTML = "<p>No candidates match this filter.</p>";
  renderSceneCandidateDetail();
}

async function setSelectedSceneCandidatePassed(passed) {
  const candidate = selectedSceneCandidate();
  if (!candidate) return;
  showSceneCandidateMessage(passed ? "Passing candidate..." : "Activating candidate...");
  try {
    await fetchJson(`/api/narrative/candidates/${encodeURIComponent(candidate.source_key)}/${encodeURIComponent(candidate.candidate_id)}/passed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ passed }),
    });
    await loadSceneCandidates();
    showSceneCandidateMessage(passed ? "Candidate passed." : "Candidate activated.", "success");
  } catch (error) {
    showSceneCandidateMessage(error.message, "error");
  }
}

async function loadSceneCandidates() {
  sceneCandidateStatus.textContent='Loading candidates…';
  try {
    await loadStories();
    state.sceneCandidateSources=await fetchJson('/api/narrative/candidate-sources');
    state.selectedSceneCandidateSource ||= state.sceneCandidateSources[0]?.key;
    sceneCandidateSource.replaceChildren(...state.sceneCandidateSources.map(source=>option(source.key,source.label)));
    sceneCandidateSource.value=state.selectedSceneCandidateSource || '';
    const source=state.sceneCandidateSources.find(source=>source.key===state.selectedSceneCandidateSource);
    if(!source){state.sceneCandidates=[];renderSceneCandidates();return;}
    sceneCandidateSourceMeta.textContent=`${source.path} · read-only`;
    state.selectedSceneCandidateStorySlug ||= source.default_story_id || state.stories[0]?.id;
    state.sceneCandidates=await fetchJson(`/api/narrative/candidates?source_key=${encodeURIComponent(source.key)}`);
    state.sceneCandidatesLoadState='selected';
    sceneCandidateStatus.textContent=`${state.sceneCandidates.length} candidates`;
    renderSceneCandidates();
  }catch(error){showSceneCandidateMessage(error.message,'error');}
}
async function importSelectedSceneCandidate() {
  const candidate=selectedSceneCandidate();if(!candidate)return;
  try {
    const result=await fetchJson(`/api/narrative/candidates/${encodeURIComponent(candidate.source_key)}/${encodeURIComponent(candidate.candidate_id)}/import`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({story_id:document.querySelector('#scene-candidate-story')?.value})});
    history.pushState({},'',`/?page=narrative&workspace=story&universe_id=${encodeURIComponent(state.universeId)}&story=${result.story_id}&scene=${result.scene_id}`);
    await activatePage('narrative',{updateHistory:false});
  }catch(error){showSceneCandidateMessage(error.message,'error');}
}
function renderSceneBuilderInterview(payload = state.sceneBuilderInterview) {
  const started = Boolean(payload?.session);
  const questions = payload?.questions || [];
  sceneBuilderInterviewNarrativeLabel.hidden = started;
  sceneBuilderInterviewQuestions.innerHTML = questions.map((item, index) => `
    <label>
      ${escapeHtml(item.question || `Question ${index + 1}`)}
      <textarea rows="3" data-interview-answer="${escapeHtml(item.id || `question_${index + 1}`)}"></textarea>
    </label>
  `).join("");
  sceneBuilderInterviewStatus.textContent = !started
    ? "Paste a narrative description. The interview will infer technical Scene Builder details."
    : payload.complete
      ? `Complete · ${payload.total_phases || 0} focused passes`
      : `${payload.phase_label || "Analyzing"} · ${payload.completed_phases || 0} of ${payload.total_phases || 0} complete`;
  sceneBuilderInterviewNext.hidden = Boolean(payload?.complete);
  sceneBuilderInterviewNext.textContent = started ? "Continue" : "Begin Interview";
  sceneBuilderInterviewApply.hidden = !payload?.complete;
}



function checkpointSceneBuilderInterview() {
  const answers = {};
  for (const control of sceneBuilderInterviewQuestions.querySelectorAll("[data-interview-answer]")) {
    answers[control.dataset.interviewAnswer] = control.value;
  }
  try {
    localStorage.setItem(sceneBuilderInterviewCheckpointKey(), JSON.stringify({
      payload: state.sceneBuilderInterview,
      seed: state.sceneBuilderInterviewSeed,
      narrative: sceneBuilderInterviewNarrative.value,
      answers,
      revision: state.sceneBuilder?._revision || 0,
    }));
    return true;
  } catch (error) {
    sceneBuilderInterviewStatus.textContent = `Unable to save interview progress on this device: ${error.message}`;
    return false;
  }
}






async function restartSceneBuilderInterview(restart = false) {
  const provenance = state.sceneBuilder?.source_provenance || {};
  if (provenance.source_type !== "scene_candidate_markdown") {
    openSceneBuilderInterview(null, restart);
    return;
  }
  try {
    const seed = await fetchJson(
      `/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/builder/interview-seed`,
    );
    openSceneBuilderInterview(seed, restart);
  } catch (error) {
    showSceneBuilderMessage(error.message, "error");
  }
}

async function runSceneBuilderInterview() {
  if (!state.sceneBuilder || !state.selectedStorySlug || !state.selectedSceneSlug) return;
  const started = Boolean(state.sceneBuilderInterview?.session);
  const answers = {};
  if (started) {
    for (const control of sceneBuilderInterviewQuestions.querySelectorAll("[data-interview-answer]")) {
      answers[control.dataset.interviewAnswer] = control.value.trim();
    }
  }
  sceneBuilderInterviewNext.disabled = true;
  checkpointSceneBuilderInterview();
  sceneBuilderInterviewStatus.textContent = started ? "Processing clarification..." : "Identifying scene elements...";
  try {
    const base = `/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/builder/interview`;
    let payload = await fetchJson(started ? `${base}/step` : base, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(started
        ? { session: state.sceneBuilderInterview.session, answers }
        : {
            narrative: sceneBuilderInterviewNarrative.value,
            data: state.sceneBuilder,
            phases: state.sceneBuilderInterviewSeed?.phases || null,
          }),
    });
    state.sceneBuilderInterview = payload;
    renderSceneBuilderInterview(payload);
    if (!checkpointSceneBuilderInterview()) return;
    while (!payload.complete && !(payload.questions || []).length) {
      await new Promise((resolve) => requestAnimationFrame(resolve));
      sceneBuilderInterviewStatus.textContent = `Analyzing ${payload.phase_label || "scene"}...`;
      payload = await fetchJson(`${base}/step`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session: payload.session, answers: {} }),
      });
      state.sceneBuilderInterview = payload;
      renderSceneBuilderInterview(payload);
      if (!checkpointSceneBuilderInterview()) return;
    }
    sceneBuilderInterviewQuestions.querySelector("textarea")?.focus();
  } catch (error) {
    sceneBuilderInterviewStatus.textContent = error.message;
  } finally {
    sceneBuilderInterviewNext.disabled = false;
  }
}

async function applySceneBuilderInterview() {
  const draft = state.sceneBuilderInterview?.draft;
  if (!draft) return;
  if ((draft._revision || 0) !== (state.sceneBuilder?._revision || 0)) {
    showSceneBuilderMessage("The scene changed since this interview began. Your saved interview is preserved; restart from the current scene before applying.", "error");
    return;
  }
  state.sceneBuilder = draft;
  state.selectedBuilderElementId = draft.scene_elements?.[0]?.id || null;
  state.selectedBuilderPlacementId = draft.placements?.[0]?.id || null;
  renderSceneBuilder();
  sceneBuilderInterviewModal.close();
  showSceneBuilderMessage("Scene-Builder Interview applied. Save when you are ready to keep these changes.", "success");
}



async function selectSceneBuilderTarget(targetId) {
  const currentSubscene = builderActiveSubscene();
  if (currentSubscene && currentSubscene.id !== targetId && builderTargetIsDirty(currentSubscene.id)) {
    unsavedChangesMessage.textContent = `Save changes to subscene ${currentSubscene.name || currentSubscene.id} before switching render targets?`;
    unsavedChangesDialog.returnValue = "cancel";
    const choice = await dialogResult(unsavedChangesDialog);
    if (choice === "cancel") return;
    if (choice === "save") {
      if (!(await saveSceneBuilder())) return;
    } else {
      cancelSceneBuilderSubsceneEdits();
    }
  }
  state.activeBuilderRenderTarget = targetId || "main";
  state.scenePromptAnalysis = null;
  const active = builderActiveSubscene();
  state.selectedBuilderElementId = state.sceneBuilder.scene_elements?.find((item) => !active || item.subscene_id === active.id)?.id || active?.anchor_element_id || state.sceneBuilder.scene_elements?.[0]?.id || null;
  state.selectedBuilderPlacementId = builderPlacementForElement(state.selectedBuilderElementId)?.id || null;
  renderSceneBuilder();
  try {
    await loadScenePromptAnalysis(state.activeBuilderRenderTarget);
    updateBuilderAnalysisActions();
    syncBrowserRoute({ replace: true });
  } catch (error) {
    showSceneBuilderMessage(error.message, "error");
  }
}



async function relockCurrentSceneBuilderImage() {
  const targetId = state.activeBuilderRenderTarget || "main";
  if (targetId === "main" || !state.selectedStorySlug || !state.selectedSceneSlug) return;
  if (!requireSavedSceneBuilder("re-locking the current image")) return;
  try {
    const payload = await fetchJson(
      `/api/render-review/scenes/${encodeURIComponent(state.selectedStorySlug)}/${encodeURIComponent(state.selectedSceneSlug)}/targets/${encodeURIComponent(targetId)}/re-lock-current`,
      { method: "POST" },
    );
    const review = payload.review;
    state.sceneBuilderRenderTargets = (state.sceneBuilderRenderTargets || []).map((item) =>
      item.render_target_id === review?.render_target_id ? review : item
    );
    renderSceneBuilder();
    showSceneBuilderMessage(payload.message || "Current image re-locked.", "success");
  } catch (error) {
    showSceneBuilderMessage(error.message, "error");
  }
}



function renderSceneBuilder() {
  if (!state.sceneBuilder) {
    return;
  }
  builderHelpSequence = 0;
  const scene = state.sceneBuilder.scene || {};
  const importedCandidate = state.sceneBuilder.source_provenance?.source_type === "scene_candidate_markdown";
  const activeSubscene = builderActiveSubscene();
  const contextReady = sceneDocumentMatches();
  const renderDisabled = !contextReady;
  const renderLabel = "Open Scene Renders";
  const activeTargetLabel = activeSubscene ? `Subscene: ${activeSubscene.name || activeSubscene.id}` : "Full Scene";
  state.sceneBuilderRendering = true;
  sceneBuilderPanel.innerHTML = `
    ${builderRenderDatalists()}
    <div class="scene-builder-sticky-context">
      ${builderRenderTargetControls()}
      <div class="scene-builder-toolbar">
        <div class="scene-builder-title">
          <span class="eyebrow">Scene Builder</span>
          <strong>${escapeHtml(scene.name || scene.slug || "Untitled scene")}</strong>
          <span class="scene-builder-active-target">Editing ${escapeHtml(activeTargetLabel)}</span>
          <span id="scene-builder-save-state" class="save-state" aria-live="polite"></span>
          ${builderRenderImportStatus()}
        </div>
        <div class="scene-builder-primary-actions">
          <button type="button" data-builder-action="interview">${importedCandidate ? "Restart Interview" : "Interview"}</button>
          ${builderRenderAnalysisAction()}
          ${activeSubscene ? '<button type="button" data-builder-action="cancel-subscene">Cancel Subscene Edits</button>' : ""}
          <button type="button" class="scene-builder-save" data-builder-action="save"${contextReady ? "" : " disabled"}>${activeSubscene ? "Save Subscene" : "Save Full Scene"}</button>
          <button type="button" class="primary-action scene-builder-render" data-builder-action="render"${renderDisabled ? " disabled" : ""}>${escapeHtml(renderLabel)}</button>
          ${builderRenderMoreMenu()}
        </div>
      </div>
    </div>
    ${builderRenderTargetStatus()}
    ${builderRenderSectionSwitcher()}
    <div class="scene-builder-grid ${activeSubscene ? "subscene-active" : ""}"${builderSubsceneStyle(activeSubscene)}>
      ${builderPhoneSectionToggle("scene", "Scene")}
      <section id="builder-panel-scene" class="scene-builder-section scene-builder-foundation" data-builder-section-panel="scene" aria-label="Scene foundation">
        ${activeSubscene ? `<div class="scene-builder-card scene-builder-story-beat">
          <span class="eyebrow">Full-scene context</span>
          <h3>${escapeHtml(scene.name || scene.slug || "Untitled scene")}</h3>
          <p>${escapeHtml(scene.story_beat || "No story beat set.")}</p>
          <p class="status-text">Return to Full Scene to edit shared scene values.</p>
        </div><div class="scene-builder-card scene-layout-launch-card"><div><h4>3D Layout</h4><p>Arrange the members of this subscene at their measured sizes and set its independent camera.</p></div><button type="button" class="primary-action" data-layout-open>Open 3D Layout</button></div>${builderRenderSubsceneSettings()}` : `<div class="scene-builder-card scene-builder-story-beat">
          <span class="eyebrow">Scene foundation</span>
          <h3>Story Beat</h3>
          <div class="scene-builder-fields">
            ${builderField("scene.name", "Scene title", "", true)}
            ${builderField("scene.story_beat", "Story Beat — included in prompt", "", true, "textarea")}
          </div>
        </div>
        <div class="scene-builder-card">
          <h4>Canvas</h4>
          <div class="scene-builder-fields">
            ${builderField("setup.canvas.orientation", "Orientation", "orientation")}
            ${builderField("setup.canvas.aspect_ratio", "Aspect ratio", "aspect_ratio")}
          </div>
        </div>
        ${builderRenderComposition()}`}
      </section>
      ${builderPhoneSectionToggle("elements", "Elements")}
      <section id="builder-panel-elements" class="scene-builder-section scene-builder-elements" data-builder-section-panel="elements" aria-label="Element workspace">
        ${builderRenderElements()}${builderRenderElementWorkspace()}
      </section>
      ${builderPhoneSectionToggle("dialogue", "Dialogue")}
      <section id="builder-panel-dialogue" class="scene-builder-section scene-builder-relationships" data-builder-section-panel="dialogue" aria-label="Dialogue and relationships">
        ${builderRenderDialogueEditor()}${builderRenderInteractions()}
      </section>
      ${builderPhoneSectionToggle("environment", "Environment")}
      <section id="builder-panel-environment" class="scene-builder-section scene-builder-environment" data-builder-section-panel="environment" aria-label="Environment">
        ${activeSubscene ? `<div class="scene-builder-card"><h4>${activeSubscene.kind === "element" ? "Target environment" : "Inherited environment"}</h4><p>${activeSubscene.kind === "element" ? "Lighting, mood, and weather can inherit from the immediate parent, be overridden, or be omitted under Scene." : "Edit universal environment fields in Full Scene. Target-specific notes are available under Scene."}</p></div>` : builderRenderEnvironment()}
      </section>
      ${builderPhoneSectionToggle("advanced", "Advanced")}
      <section id="builder-panel-advanced" class="scene-builder-section scene-builder-advanced-panel" data-builder-section-panel="advanced" aria-label="Advanced overrides">
        ${activeSubscene ? '<div class="scene-builder-card"><h4>Advanced overrides</h4><p>Advanced overrides apply to the full scene. Return to Full Scene to edit them.</p></div>' : builderRenderOverrides()}
      </section>
    </div>
  `;
  setBuilderResponsiveSection(state.builderResponsiveSection);
  state.sceneBuilderRendering = false;
  updateDirtyIndicators();
}





async function loadScenePromptAnalysis(renderTargetId = state.activeBuilderRenderTarget || "main", options = {}) {
  const analysis = await fetchJson(
    `/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/prompt-analysis?render_target_id=${encodeURIComponent(renderTargetId)}`,
    options,
  );
  if (state.activeBuilderRenderTarget === renderTargetId) state.scenePromptAnalysis = analysis;
  return analysis;
}









function closeBuilderContinueDialog() {
  builderContinueModal.close();
}



function cancelSceneBuilderSubsceneEdits() {
  const targetId = state.activeBuilderRenderTarget || "main";
  if (targetId === "main") return;
  const savedSubscene = builderSubsceneFromData(savedSceneBuilderData(), targetId);
  if (!savedSubscene) return;
  replaceBuilderSubscene(state.sceneBuilder, targetId, savedSubscene);
  renderSceneBuilder();
  updateDirtyIndicators();
  showSceneBuilderMessage("Subscene edits canceled. Other Scene Builder changes were left untouched.", "info");
}

function requireSavedSceneBuilder(action) {
  builderSyncControls();
  if (!builderTargetIsDirty()) return true;
  updateDirtyIndicators();
  showSceneBuilderMessage(`Save ${builderActiveSubscene() ? "this subscene" : "the full scene"} before ${action}.`, "info");
  return false;
}

async function setBackgroundSubsceneEnabled(enabled) {
  if (!state.selectedStorySlug || !state.selectedSceneSlug) return;
  if (!requireSavedSceneBuilder(`${enabled ? "enabling" : "disabling"} the background subscene`)) return;
  const endpoint = enabled
    ? `/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/subscenes/background/enable`
    : `/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/subscenes/background/disable`;
  try {
    const payload = await fetchJson(endpoint, { method: "POST" });
    state.sceneBuilder = payload.document?.data || state.sceneBuilder;
    state.sceneBuilderRenderTargets = payload.document?.render_targets || [];
    state.activeBuilderRenderTarget = enabled ? "background" : "main";
    state.selectedBuilderElementId = state.sceneBuilder.scene_elements?.find((item) => !enabled || item.subscene_id === "background")?.id || state.sceneBuilder.scene_elements?.[0]?.id || null;
    state.selectedBuilderPlacementId = builderPlacementForElement(state.selectedBuilderElementId)?.id || null;
    updateStoryGitWarning(payload.has_story_changes);
    renderSceneBuilder();
    state.savedBaselines.sceneBuilder = sceneBuilderSnapshot();
    updateDirtyIndicators();
    showSceneBuilderMessage(payload.message, "success");
  } catch (error) {
    if (!isRequestCancellation(error)) showSceneBuilderMessage(error.message, "error");
  }
}

async function addSceneBuilderSubscene() {
  if (!state.selectedStorySlug || !state.selectedSceneSlug) return;
  if (!requireSavedSceneBuilder("adding a sub-scene")) return;
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/subscenes`, { method: "POST" });
    state.sceneBuilder = payload.document?.data || state.sceneBuilder;
    state.sceneBuilderRenderTargets = payload.document?.render_targets || [];
    state.activeBuilderRenderTarget = "main";
    updateStoryGitWarning(payload.has_story_changes);
    renderSceneBuilder();
    state.savedBaselines.sceneBuilder = sceneBuilderSnapshot();
    updateDirtyIndicators();
    showSceneBuilderMessage(payload.message, "success");
  } catch (error) {
    showSceneBuilderMessage(error.message, "error");
  }
}

async function enableSelectedElementSubscene(elementId = "") {
  const element = (state.sceneBuilder?.scene_elements || []).find((item) => item.id === elementId) || builderSelectedElement();
  if (!element || !state.selectedStorySlug || !state.selectedSceneSlug) return;
  if (!requireSavedSceneBuilder("creating an element subscene")) return;
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/subscenes/elements/${encodeURIComponent(element.id)}/enable`, { method: "POST" });
    state.sceneBuilder = payload.document?.data || state.sceneBuilder;
    state.sceneBuilderRenderTargets = payload.document?.render_targets || [];
    state.activeBuilderRenderTarget = payload.render_target_id || builderSubsceneForAnchor(element.id)?.id || "main";
    state.selectedBuilderElementId = state.sceneBuilder.scene_elements?.find((item) => item.subscene_id === state.activeBuilderRenderTarget)?.id || element.id;
    state.selectedBuilderPlacementId = builderPlacementForElement(state.selectedBuilderElementId)?.id || null;
    updateStoryGitWarning(payload.has_story_changes);
    renderSceneBuilder();
    state.savedBaselines.sceneBuilder = sceneBuilderSnapshot();
    updateDirtyIndicators();
    showSceneBuilderMessage(payload.message, "success");
  } catch (error) {
    showSceneBuilderMessage(error.message, "error");
  }
}



async function renderSceneBuilderScene() {
  if (!requireSavedSceneBuilder("opening Scene Renders")) return;
  await activatePage("scene-batches");
}

async function analyzeScenePrompt() {
  if (!requireSavedSceneBuilder("running prompt analysis")) return;
  const targetId = state.activeBuilderRenderTarget || "main";
  try {
    state.scenePromptAnalysis = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/prompt-analysis?render_target_id=${encodeURIComponent(targetId)}`, { method: "POST" });
    renderSceneBuilder();
    showSceneBuilderMessage(state.scenePromptAnalysis.message || "AI prompt analysis queued.", "success");
  } catch (error) {
    showSceneBuilderMessage(error.message, "error");
  }
}

async function viewScenePromptAnalysis() {
  const targetId = state.activeBuilderRenderTarget || "main";
  try {
    state.scenePromptAnalysis = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/prompt-analysis?render_target_id=${encodeURIComponent(targetId)}`);
    renderSceneBuilder();
    if (state.scenePromptAnalysis.complete && state.scenePromptAnalysis.result_path) {
      openPromptAnalysisDialog(state.selectedStorySlug, state.selectedSceneSlug, targetId);
      return;
    }
    if (!state.scenePromptAnalysis.pending) {
      await analyzeScenePrompt();
      return;
    }
    state.scenePromptAnalysis = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/prompt-analysis/harvest?render_target_id=${encodeURIComponent(targetId)}`, { method: "POST" });
    renderSceneBuilder();
    if (state.scenePromptAnalysis.complete && state.scenePromptAnalysis.result_path) {
      showSceneBuilderMessage("Prompt analysis is ready.", "success");
      openPromptAnalysisDialog(state.selectedStorySlug, state.selectedSceneSlug, targetId);
    } else {
      showSceneBuilderMessage(state.scenePromptAnalysis.error || "Analysis is still running. Check again after the AI worker finishes.", state.scenePromptAnalysis.error ? "error" : "info");
    }
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












sceneCandidateFilter.addEventListener("change", renderSceneCandidates);
sceneCandidateRefresh.addEventListener("click", loadSceneCandidates);
async function loadImagePickerReferences(picker) {
  picker.status.textContent = "Loading references...";
  const params = new URLSearchParams();
  if (picker.library) {
    if (picker.search.value.trim()) params.set("q", picker.search.value.trim());
    if (builderImagePickerEntity.value) params.set("entity_id", builderImagePickerEntity.value);
    if (builderImagePickerVariant.value) params.set("variant_id", builderImagePickerVariant.value);
    if (builderImagePickerSet.value) params.set("set_id", builderImagePickerSet.value);
    if (builderImagePickerFacet.value) {
      const [namespace, value] = builderImagePickerFacet.value.split("\u0000");
      params.set("facet_namespace", namespace || "");
      params.set("facet_value", value || "");
    }
    try {
      const payload = await fetchJson(`/api/entity-library/picker?${params.toString()}`);
      picker.setRows(payload.assets || []);
      renderImagePickerTable(picker);
      picker.status.textContent = `${picker.rows().length} approved image(s)`;
    } catch (error) {
      picker.status.textContent = "Load failed.";
      picker.onError(error);
    }
    return;
  }
  if (picker.character.value) {
    params.set("character", picker.character.value);
  }
  if (picker.search.value.trim()) {
    params.set("text_filter", picker.search.value.trim());
  }
  if (picker.includeBase?.checked) {
    params.set("include_base", "true");
  }
  if (picker.source?.value) {
    params.set("source_type", picker.source.value);
  }
  if (picker.category?.value) {
    params.set("semantic_category", picker.category.value);
  }
  if (picker.statusFilter?.value) {
    params.set("status", picker.statusFilter.value);
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
    if (picker.library) {
      const thumb = document.createElement("img");
      thumb.className = "aux-resource-thumb";
      thumb.src = fileUrl(item.thumbnail_path || item.image_path);
      thumb.alt = item.label || "Reference image";
      const title = document.createElement("span");
      const entityNames = (item.entities || []).map((entity) => [entity.name, entity.variant_name].filter(Boolean).join(" · ")).join(", ");
      title.textContent = `${item.label || entityNames || item.origin} · ${item.width || "?"}×${item.height || "?"}${item.descriptor_ready ? " · prompt ready" : " · prompt text missing"}`;
      labelCell.append(thumb, title);
      const actionCell = document.createElement("td");
      if (item.logical_reference) {
        const logicalButton = document.createElement("button");
        logicalButton.type = "button";
        logicalButton.textContent = `Use ${item.logical_reference.reference_key}`;
        logicalButton.addEventListener("click", (event) => {
          event.stopPropagation();
          picker.onSelect(item, "logical");
        });
        actionCell.append(logicalButton);
      }
      row.append(labelCell, actionCell);
      makeSelectableRow(row, item.file_name || "image asset", false, () => picker.onSelect(item, builderImagePickerMode.value || "asset"));
      picker.tableBody.append(row);
      continue;
    }
    if (picker.labelOnly && item.thumbnail_path) {
      const thumb = document.createElement("img");
      thumb.className = "aux-resource-thumb";
      thumb.src = fileUrl(item.thumbnail_path);
      thumb.alt = item.label || "Reference";
      const detail = document.createElement("span");
      detail.textContent = `${item.label || ""} · ${item.semantic_category || item.kind || ""} · ${String(item.description_status || "").replaceAll("_", " ")}`;
      labelCell.append(thumb, detail);
    } else {
      labelCell.textContent = item.label || "";
    }
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



let quickCharacterLibrarySelection = null;


async function loadSceneImageReferences() {
  await loadImagePickerReferences(sceneImagePicker);
}

async function loadEntityLibraryPickerFilters(element = null) {
  const [entityPayload, variantPayload, setPayload, facetPayload] = await Promise.all([
    fetchJson("/api/entity-library/entities"), fetchJson("/api/entity-library/variants"),
    fetchJson("/api/entity-library/sets"), fetchJson("/api/entity-library/facets"),
  ]);
  const entities = entityPayload.entities || [];
  setSelectOptionsWithLabels(builderImagePickerEntity, [
    { value: "", label: "All entities" },
    ...entities.map((item) => ({ value: item.entity_id, label: `${item.name} · ${item.entity_type}` })),
  ]);
  const entityQuery = String(element?.character || element?.display_name || "").trim().toLowerCase();
  builderImagePickerEntity.value = "";
  builderImagePickerVariant.value = "";
  builderImagePickerSet.value = "";
  builderImagePickerFacet.value = "";
  const matchingEntity = entities.find((item) => item.name.toLowerCase() === entityQuery);
  builderImagePickerEntity.value = matchingEntity?.entity_id || "";
  const variants = (variantPayload.variants || []).filter((item) => !builderImagePickerEntity.value || item.entity_id === builderImagePickerEntity.value);
  setSelectOptionsWithLabels(builderImagePickerVariant, [
    { value: "", label: "All variants" },
    ...variants.map((item) => ({ value: item.variant_id, label: `${item.name} · ${item.variant_type}` })),
  ]);
  setSelectOptionsWithLabels(builderImagePickerSet, [
    { value: "", label: "All reference sets" },
    ...(setPayload.sets || []).map((item) => ({ value: item.set_id, label: item.name })),
  ]);
  const facets = facetPayload.facets || [];
  const options = [...new Map(facets.map((item) => [`${item.namespace}\u0000${item.value}`, item])).values()];
  setSelectOptionsWithLabels(builderImagePickerFacet, [
    { value: "", label: "All facets" },
    ...options.map((item) => ({ value: `${item.namespace}\u0000${item.value}`, label: `${item.namespace}: ${item.value}` })),
  ]);
  const phaseQuery = String(element?.phase || "").trim().toLowerCase();
  builderImagePickerVariant.value = variants.find((item) => item.name.toLowerCase() === phaseQuery)?.variant_id || "";
}



function selectedImageCatalogItem() {
  return state.imageCatalogItems.find((item) => item.catalog_id === state.selectedImageCatalogId) || null;
}

function fillImageCatalogOrganizationSelect(select, entries, selectedLabels = []) {
  const selected = new Set(selectedLabels || []);
  select.replaceChildren();
  for (const entry of entries || []) {
    const option = document.createElement("option");
    option.value = entry.id || "";
    option.textContent = `${entry.label || entry.id} (${entry.usage_count || 0})`;
    option.selected = selected.has(entry.label);
    select.append(option);
  }
}

function renderImageCatalogOrganization() {
  const organization = state.imageCatalogOrganization || { collections: [], keywords: [] };
  const selected = selectedImageCatalogItem();
  fillImageCatalogOrganizationSelect(imageCatalogEditCollections, organization.collections, selected?.collections || []);
  fillImageCatalogOrganizationSelect(imageCatalogEditKeywords, organization.keywords, selected?.keywords || []);
  fillImageCatalogOrganizationSelect(imageCatalogBulkCollections, organization.collections);
  fillImageCatalogOrganizationSelect(imageCatalogBulkKeywords, organization.keywords);
  const currentCollection = imageCatalogCollection.value;
  const currentKeyword = imageCatalogKeyword.value;
  setSelectOptionsWithLabels(imageCatalogCollection, [{ value: "", label: "All collections" }, ...organization.collections.map((item) => ({ value: item.label, label: `${item.label} (${item.usage_count || 0})` }))]);
  setSelectOptionsWithLabels(imageCatalogKeyword, [{ value: "", label: "All keywords" }, ...organization.keywords.map((item) => ({ value: item.label, label: `${item.label} (${item.usage_count || 0})` }))]);
  imageCatalogCollection.value = currentCollection;
  imageCatalogKeyword.value = currentKeyword;
  imageCatalogOrganizationList.replaceChildren();
  for (const [kind, entries] of [["collections", organization.collections], ["keywords", organization.keywords]]) {
    const group = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = kind === "collections" ? "Collections: " : "Keywords: ";
    group.append(title);
    const help = document.createElement("small");
    help.textContent = "Click to rename; Shift-click to delete or merge. ";
    group.append(help);
    for (const entry of entries) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `${entry.label} (${entry.usage_count || 0})`;
      button.title = "Click to rename; Shift+click to delete";
      button.addEventListener("click", async (event) => {
        if (event.shiftKey) {
          if (!window.confirm(`Delete ${entry.label}? Image files will not be deleted.`)) return;
          const mergeLabel = window.prompt("Optional: enter another existing label to merge memberships into it, or leave blank to remove memberships.", "")?.trim() || "";
          const mergeTarget = entries.find((candidate) => candidate.label.toLowerCase() === mergeLabel.toLowerCase() && candidate.id !== entry.id);
          if (mergeLabel && !mergeTarget) {
            showAuxResourceMessage(`No ${kind === "collections" ? "collection" : "keyword"} named ${mergeLabel}.`, "error");
            return;
          }
          const params = new URLSearchParams();
          if (mergeTarget) params.set("merge_into", mergeTarget.id);
          await fetchJson(`/api/image-catalog/organization/${kind}/${encodeURIComponent(entry.id)}?${params.toString()}`, { method: "DELETE" });
        } else {
          const label = window.prompt(`Rename ${entry.label}`, entry.label);
          if (!label?.trim() || label.trim() === entry.label) return;
          await fetchJson(`/api/image-catalog/organization/${kind}/${encodeURIComponent(entry.id)}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ label: label.trim() }) });
        }
        await loadImageCatalogOrganization();
        await loadImageCatalog();
      });
      group.append(button);
    }
    imageCatalogOrganizationList.append(group);
  }
}

async function loadImageCatalogOrganization() {
  state.imageCatalogOrganization = await fetchJson("/api/image-catalog/organization");
  renderImageCatalogOrganization();
}

function imageCatalogQuery() {
  const params = new URLSearchParams();
  if (imageCatalogSearch.value.trim()) params.set("q", imageCatalogSearch.value.trim());
  if (imageCatalogSource.value) params.set("source_type", imageCatalogSource.value);
  if (imageCatalogCategory.value) params.set("semantic_category", imageCatalogCategory.value);
  if (imageCatalogStatus.value) params.set("status", imageCatalogStatus.value);
  if (imageCatalogCollection.value) params.set("collection", imageCatalogCollection.value);
  if (imageCatalogKeyword.value) params.set("keyword", imageCatalogKeyword.value);
  for (const [key, control] of [["character", imageCatalogCharacter], ["phase", imageCatalogPhase], ["costume", imageCatalogCostume], ["pipeline", imageCatalogPipeline], ["story_slug", imageCatalogStory], ["scene_slug", imageCatalogScene], ["subscene_id", imageCatalogSubscene]]) {
    if (control.value.trim()) params.set(key, control.value.trim());
  }
  params.set("include_base", imageCatalogIncludeBase.checked ? "true" : "false");
  return params;
}

function renderImageCatalogIdle(message = "Enter a search or choose filters, then refresh.") {
  state.imageCatalogLoaded = false;
  imageCatalogGrid.replaceChildren();
  const empty = document.createElement("div");
  empty.className = "image-catalog-empty";
  empty.innerHTML = "<strong>Images are loaded on demand.</strong><span>Use search or filters on the left, then choose Refresh images.</span>";
  imageCatalogGrid.append(empty);
  imageCatalogCount.textContent = message;
  imageCatalogBulk.hidden = true;
}

function markImageCatalogFiltersDirty() {
  renderImageCatalogIdle("Filters changed. Refresh to load matching images.");
}

function clearImageCatalogFilters() {
  imageCatalogSearch.value = "";
  for (const control of [imageCatalogSource, imageCatalogCategory, imageCatalogStatus, imageCatalogCollection, imageCatalogKeyword]) {
    control.value = "";
  }
  for (const control of [imageCatalogCharacter, imageCatalogPhase, imageCatalogCostume, imageCatalogPipeline, imageCatalogStory, imageCatalogScene, imageCatalogSubscene]) {
    control.value = "";
  }
  imageCatalogIncludeBase.checked = false;
  markImageCatalogFiltersDirty();
  imageCatalogSearch.focus();
}

function renderImageCatalog() {
  imageCatalogGrid.replaceChildren();
  imageCatalogCount.textContent = `${state.imageCatalogItems.length} selectable image(s)`;
  imageCatalogSelectedCount.textContent = `${state.selectedImageCatalogIds.length} selected`;
  imageCatalogBulk.hidden = state.selectedImageCatalogIds.length <= 1;
  imageCatalogBulkApply.disabled = state.selectedImageCatalogIds.length <= 1;
  if (!state.imageCatalogItems.length) {
    imageCatalogGrid.textContent = "No images match these filters.";
    return;
  }
  for (const item of state.imageCatalogItems) {
    const card = document.createElement("article");
    card.className = "image-catalog-card";
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `Edit ${item.label || item.tag || "catalog image"}`);
    card.classList.toggle("selected", item.catalog_id === state.selectedImageCatalogId);
    const select = document.createElement("input");
    select.type = "checkbox";
    select.checked = state.selectedImageCatalogIds.includes(item.catalog_id);
    select.setAttribute("aria-label", `Select ${item.label || item.tag} for bulk editing`);
    select.addEventListener("change", () => {
      state.selectedImageCatalogIds = select.checked
        ? [...new Set([...state.selectedImageCatalogIds, item.catalog_id])]
        : state.selectedImageCatalogIds.filter((value) => value !== item.catalog_id);
      renderImageCatalog();
    });
    const image = document.createElement("img");
    image.src = fileUrl(item.thumbnail_path);
    image.alt = item.label || "Catalog image";
    image.loading = "lazy";
    image.decoding = "async";
    const label = document.createElement("strong");
    label.textContent = item.label || item.tag;
    const source = document.createElement("small");
    source.textContent = `${item.source_type} · ${item.semantic_category} · ${String(item.description_status || "").replaceAll("_", " ")}`;
    card.append(select, image, label, source);
    card.addEventListener("click", () => selectImageCatalogItem(item.catalog_id));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectImageCatalogItem(item.catalog_id);
      }
    });
    select.addEventListener("click", (event) => event.stopPropagation());
    imageCatalogGrid.append(card);
  }
}

function selectImageCatalogItem(catalogId) {
  const item = state.imageCatalogItems.find((candidate) => candidate.catalog_id === catalogId);
  if (!item) return;
  beginSelection("image-catalog");
  state.selectedImageCatalogId = catalogId;
  imageCatalogEditorTitle.textContent = item.label || item.tag;
  imageCatalogPreview.src = fileUrl(item.image_path);
  imageCatalogPreview.hidden = false;
  imageCatalogSourceDetail.textContent = [item.source_type, item.character, item.phase, item.costume, item.pipeline, item.story_slug, item.scene_slug, item.subscene_id, item.tag].filter(Boolean).join(" · ");
  imageCatalogManagedActions.hidden = !item.is_managed;
  imageCatalogManagedLabel.value = item.managed_label || item.label || "";
  imageCatalogManagedSet.value = item.reference_set_id || "";
  imageCatalogAdd.disabled = !item.reference_set_id;
  imageCatalogAdd.title = item.reference_set_id ? "Add another image to this reference set" : "Assign this image to a reference set before adding another image";
  imageCatalogAddUpload.hidden = true;
  imageCatalogReplaceUpload.hidden = true;
  state.imageCatalogAddBlob = null;
  state.imageCatalogReplaceBlob = null;
  imageCatalogAddFile.value = "";
  imageCatalogReplaceFile.value = "";
  imageCatalogAddLabel.value = "";
  imageCatalogAddStatus.textContent = "Choose or paste an image.";
  imageCatalogReplaceStatus.textContent = "Choose or paste an image.";
  imageCatalogAddSubmit.disabled = true;
  imageCatalogReplaceSubmit.disabled = true;
  imageCatalogEditCategory.value = item.semantic_category;
  imageCatalogIdentityMode.value = item.identity_mode || "inherit";
  imageCatalogIdentityText.value = item.identity_override_text || "";
  imageCatalogCostumeMode.value = item.costume_mode || "not_applicable";
  imageCatalogCostumeText.value = item.costume_override_text || "";
  syncImageCatalogOverrideControls();
  imageCatalogAiIdentity.value = item.ai_draft_identity || "";
  imageCatalogAiCostume.value = item.ai_draft_costume || "";
  imageCatalogAiReview.hidden = item.description_status !== "ai_review_required";
  imageCatalogSave.disabled = false;
  imageCatalogAi.disabled = item.description_status === "ai_queued";
  imageCatalogAiCheck.disabled = item.description_status !== "ai_queued";
  if (item.description_status === "ai_queued") {
    showMessageElement(imageCatalogAiStatus, "AI image description initiated and awaiting an answer.", "info");
  } else if (item.description_status === "ai_review_required") {
    showMessageElement(imageCatalogAiStatus, "AI answer harvested. Review and approve the draft below.", "success");
  } else {
    showMessageElement(imageCatalogAiStatus, "", "info");
  }
  renderImageCatalogOrganization();
  renderImageCatalog();
}

function syncImageCatalogOverrideControls() {
  imageCatalogIdentityText.disabled = imageCatalogIdentityMode.value !== "override";
  imageCatalogCostumeText.disabled = imageCatalogCostumeMode.value !== "override";
}

async function loadEntityLibraryInventory() {
  const searchIsActive = entityLibraryCurrentView === "search";
  const searchRoot = document.querySelector("#entity-library-search-view");
  const searchControlStates = searchIsActive
    ? Array.from(searchRoot.querySelectorAll("input, select, button"), (control) => [control, control.disabled]) : [];
  const navigationControlStates = searchIsActive
    ? Array.from(document.querySelectorAll("[data-inventory-view]"), (control) => [control, control.disabled]) : [];
  if (searchIsActive) {
    entityLibraryCount.textContent = "Loading image inventory…";
    for (const [control] of searchControlStates) control.disabled = true;
    for (const [control] of navigationControlStates) control.disabled = true;
  }
  try {
    await loadEntityLibraryInventoryData();
  } catch (error) {
    if (searchIsActive) entityLibraryCount.textContent = `Could not load image inventory: ${error.message}`;
    throw error;
  } finally {
    if (searchIsActive) {
      for (const [control, wasDisabled] of searchControlStates) control.disabled = wasDisabled;
      for (const [control, wasDisabled] of navigationControlStates) control.disabled = wasDisabled;
      entityLibraryPrevious.disabled = entityLibraryPageOffset === 0 || entityLibraryTotal === 0;
      entityLibraryNext.disabled = entityLibraryPageOffset + entityLibraryPageItemCount >= entityLibraryTotal;
    }
  }
}

async function loadEntityLibraryInventoryData() {
  const selectedEntityIds = new Set(Array.from(entityLibraryEditEntities.selectedOptions || [], (item) => item.value));
  const selectedSetIds = new Set(Array.from(entityLibraryEditSets.selectedOptions || [], (item) => item.value));
  const selectedFilters = [entityLibraryFilterEntity, entityLibraryFilterType, entityLibraryFilterVariant,
    entityLibraryFilterSet, entityLibraryFilterFacet, entityLibraryFilterStatus, entityLibraryFilterOrigin]
    .map((control) => control.value);
  const searchLoaded = await searchEntityLibrary(true);
  if (searchLoaded === false) throw new Error("Image search could not be refreshed.");
  const [entitiesPayload, variantsPayload, setsPayload, facetsPayload] = await Promise.all([
    fetchJson("/api/entity-library/entities"), fetchJson("/api/entity-library/variants"),
    fetchJson("/api/entity-library/sets"), fetchJson("/api/entity-library/facets"),
  ]);
  const entities = entitiesPayload.entities || [];
  const variants = variantsPayload.variants || [];
  const sets = setsPayload.sets || [];
  const facets = facetsPayload.facets || [];
  entityLibraryMetadata = { entities, variants, sets, facets };
  setSelectOptionsWithLabels(entityLibraryGeneratedEntity, [
    { value: "", label: "General image import" }, ...entities.map((item) => ({ value: item.entity_id, label: `${item.name} · ${item.entity_type}` })),
  ]);
  setSelectOptionsWithLabels(entityLibraryFilterEntity, [
    { value: "", label: "All entities" }, ...entities.map((item) => ({ value: item.entity_id, label: item.name })),
  ]);
  const entityTypes = [...new Set(entities.map((item) => item.entity_type))].sort();
  setSelectOptionsWithLabels(entityLibraryFilterType, [
    { value: "", label: "All types" }, ...entityTypes.map((value) => ({ value, label: value })),
  ]);
  setSelectOptionsWithLabels(entityLibraryFilterVariant, [
    { value: "", label: "All variants" }, ...variants.map((item) => ({ value: item.variant_id, label: `${item.name} · ${item.variant_type}` })),
  ]);
  setSelectOptionsWithLabels(entityLibraryFilterSet, [
    { value: "", label: "All sets" }, ...sets.map((item) => ({ value: item.set_id, label: item.name })),
  ]);
  const selectedSetId = entityLibrarySetSelect.value;
  setSelectOptionsWithLabels(entityLibrarySetSelect, [
    { value: "", label: "Create a new set" },
    ...sets.map((item) => ({ value: item.set_id, label: `${item.name} (${item.assets?.length || 0})` })),
  ]);
  entityLibrarySetSelect.value = sets.some((item) => item.set_id === selectedSetId) ? selectedSetId : "";
  syncEntityLibrarySetEditor();
  const facetChoices = [...new Map(facets.map((item) => [`${item.namespace}\u0000${item.value}`, item])).values()];
  setSelectOptionsWithLabels(entityLibraryFilterFacet, [
    { value: "", label: "All facets" }, ...facetChoices.map((item) => ({ value: `${item.namespace}\u0000${item.value}`, label: `${item.namespace}: ${item.value}` })),
  ]);
  [entityLibraryFilterEntity, entityLibraryFilterType, entityLibraryFilterVariant,
    entityLibraryFilterSet, entityLibraryFilterFacet, entityLibraryFilterStatus, entityLibraryFilterOrigin]
    .forEach((control, index) => {
      if (Array.from(control.options).some((item) => item.value === selectedFilters[index])) {
        control.value = selectedFilters[index];
      }
    });
  setSelectOptionsWithLabels(entityLibraryEditEntities, entities.map((item) => ({ value: item.entity_id, label: `${item.name} · ${item.entity_type}` })));
  for (const optionItem of entityLibraryEditEntities.options) optionItem.selected = selectedEntityIds.has(optionItem.value);
  const entityOptions = entities.map((item) => ({ value: item.entity_id, label: item.name }));
  for (const select of [entityLibraryVariantEntity, entityLibraryRelationSource, entityLibraryRelationTarget]) {
    setSelectOptionsWithLabels(select, [{ value: "", label: "Choose entity" }, ...entityOptions]);
  }
  updateEntityLibraryDescriptorOwners();
  setSelectOptionsWithLabels(entityLibraryEditSets, sets.map((item) => ({ value: item.set_id, label: item.name })));
  for (const optionItem of entityLibraryEditSets.options) optionItem.selected = selectedSetIds.has(optionItem.value);
}

async function searchEntityLibrary(preserveOffset = false) {
  const requestGeneration = ++entityLibrarySearchGeneration;
  if (!preserveOffset) entityLibraryPageOffset = 0;
  const params = new URLSearchParams();
  const values = {
    q: entityLibrarySearch.value.trim(), entity_id: entityLibraryFilterEntity.value,
    entity_type: entityLibraryFilterType.value, variant_id: entityLibraryFilterVariant.value,
    set_id: entityLibraryFilterSet.value, status: entityLibraryFilterStatus.value,
    origin: entityLibraryFilterOrigin.value, include_obsolete: entityLibraryIncludeObsolete.checked ? "true" : "",
  };
  if (entityLibraryFilterFacet.value) {
    const [facet_namespace, facet_value] = entityLibraryFilterFacet.value.split("\u0000");
    values.facet_namespace = facet_namespace;
    values.facet_value = facet_value;
  }
  for (const [key, value] of Object.entries(values)) if (value) params.set(key, value);
  const activeFilters = Object.entries(values).filter(([key, value]) => key !== "q" && key !== "facet_value" && value);
  entityLibraryActiveFilterCount.textContent = activeFilters.length ? ` · ${activeFilters.length} active` : "";
  const chipContainer = document.querySelector("#entity-library-filter-chips");
  chipContainer.replaceChildren();
  const filterControls = { entity_id: entityLibraryFilterEntity, entity_type: entityLibraryFilterType, variant_id: entityLibraryFilterVariant, set_id: entityLibraryFilterSet, facet_namespace: entityLibraryFilterFacet, facet_value: entityLibraryFilterFacet, status: entityLibraryFilterStatus, origin: entityLibraryFilterOrigin, include_obsolete: entityLibraryIncludeObsolete };
  const chipLabels = new Map();
  if (entityLibraryFilterFacet.value) chipLabels.set("facet_namespace", entityLibraryFilterFacet.selectedOptions[0]?.textContent || entityLibraryFilterFacet.value.replace("\u0000", ":"));
  for (const [key, value] of activeFilters) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "inventory-filter-chip";
    const control = filterControls[key];
    chip.textContent = `${chipLabels.get(key) || control?.selectedOptions?.[0]?.textContent || (key === "include_obsolete" ? "Include obsolete images" : value)} ×`;
    chip.addEventListener("click", () => {
      if (key === "include_obsolete") control.checked = false;
      else if (control) control.value = "";
      searchEntityLibrary();
    });
    chipContainer.append(chip);
  }
  params.set("offset", String(entityLibraryPageOffset));
  params.set("limit", String(ENTITY_LIBRARY_PAGE_SIZE));
  entityLibraryCount.textContent = "Searching…";
  entityLibrarySearchStale = true;
  let payload;
  try {
    payload = await fetchJson(`/api/entity-library/assets?${params.toString()}`);
  } catch (error) {
    if (requestGeneration !== entityLibrarySearchGeneration) return;
    entityLibraryResults.replaceChildren();
    entityLibraryTotal = 0;
    entityLibraryPageItemCount = 0;
    entityLibraryCount.textContent = error.message || "Search failed. Try again.";
    entityLibraryCount.classList.add("inventory-error");
    entityLibraryPrevious.disabled = true;
    entityLibraryNext.disabled = true;
    return false;
  }
  if (requestGeneration !== entityLibrarySearchGeneration) return;
  entityLibrarySearchStale = false;
  entityLibraryCount.classList.remove("inventory-error");
  const assets = payload.assets || [];
  entityLibraryTotal = Number(payload.total || 0);
  entityLibraryPageItemCount = assets.length;
  if (!assets.length && entityLibraryPageOffset > 0 && entityLibraryPageOffset >= entityLibraryTotal) {
    entityLibraryPageOffset = Math.max(0, Math.floor((entityLibraryTotal - 1) / ENTITY_LIBRARY_PAGE_SIZE) * ENTITY_LIBRARY_PAGE_SIZE);
    return searchEntityLibrary(true);
  }
  entityLibraryResults.replaceChildren();
  for (const asset of assets) {
    const card = document.createElement("article");
    card.className = "image-catalog-card";
    const imageButton = document.createElement("button");
    imageButton.type = "button";
    imageButton.className = "inventory-card-image";
    imageButton.setAttribute("aria-label", `Preview ${asset.label || asset.file_name || "library image"}`);
    const img = document.createElement("img");
    img.src = fileUrl(asset.thumbnail_path || asset.image_path);
    img.alt = asset.label || "Library image";
    img.title = "Open full-size image";
    imageButton.addEventListener("click", () => {
      openFullscreenImage(fileUrl(asset.image_path), asset.label || asset.file_name || "Library image");
    });
    imageButton.append(img);
    const title = document.createElement("strong");
    title.textContent = asset.label || asset.file_name;
    const detail = document.createElement("span");
    detail.className = "inventory-card-subject";
    detail.textContent = [(asset.entities || []).map((item) => [item.name, item.variant_name].filter(Boolean).join(" · ")).join(", "), asset.origin].filter(Boolean).join(" · ") || "No subject linked";
    const badge = document.createElement("span");
    badge.className = `inventory-status inventory-status-${asset.status}`;
    badge.textContent = asset.status;
    const tag = asset.logical_reference?.reference_key
      ? `{{LIB:REF:${asset.logical_reference.reference_key}}}`
      : `{{LIB:ASSET:${asset.asset_id}}}`;
    const tagText = document.createElement("code");
    tagText.className = "inventory-card-tag";
    tagText.textContent = tag;
    tagText.title = tag;
    const actions = document.createElement("div");
    actions.className = "inventory-card-actions";
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "primary-action inventory-copy-tag";
    copy.textContent = "Copy tag";
    copy.addEventListener("click", async () => {
      try {
        await writeClipboardText(tag);
        copy.textContent = "Copied";
        copy.classList.add("inventory-copied");
        window.setTimeout(() => { copy.textContent = "Copy tag"; copy.classList.remove("inventory-copied"); }, 1600);
      } catch {
        window.prompt("Copy this image tag:", tag);
      }
    });
    const details = document.createElement("button");
    details.type = "button";
    details.className = "secondary-action";
    details.textContent = "Details";
    details.addEventListener("click", () => selectEntityLibraryAsset(asset.asset_id));
    actions.append(copy, details);
    card.append(imageButton, title, detail, badge, tagText, actions);
    entityLibraryResults.append(card);
  }
  const first = entityLibraryTotal ? entityLibraryPageOffset + 1 : 0;
  const last = Math.min(entityLibraryPageOffset + assets.length, entityLibraryTotal);
  entityLibraryCount.textContent = entityLibraryTotal ? `${entityLibraryTotal} image${entityLibraryTotal === 1 ? "" : "s"} · showing ${first}–${last}` : "No images match these filters. Try another search.";
  entityLibraryPageStatus.textContent = `Page ${entityLibraryTotal ? Math.floor(entityLibraryPageOffset / ENTITY_LIBRARY_PAGE_SIZE) + 1 : 1}`;
  entityLibraryPrevious.disabled = entityLibraryPageOffset === 0;
  entityLibraryNext.disabled = entityLibraryPageOffset + assets.length >= entityLibraryTotal;
  return true;
}

function updateEntityLibraryDescriptorOwners() {
  const ownerType = entityLibraryDescriptorOwnerType.value;
  const source = ownerType === "entity" ? entityLibraryMetadata.entities
    : ownerType === "variant" ? entityLibraryMetadata.variants
      : entityLibraryMetadata.sets;
  setSelectOptionsWithLabels(entityLibraryDescriptorOwner, [
    { value: "", label: "Choose owner" },
    ...source.map((item) => ({
      value: item.entity_id || item.variant_id || item.set_id,
      label: `${item.name || item.label}${item.variant_type ? ` · ${item.variant_type}` : ""}`,
    })),
  ]);
}

function activateInventoryView(view) {
  entityLibraryCurrentView = view;
  document.querySelectorAll("[data-inventory-view]").forEach((button) => {
    const active = button.dataset.inventoryView === view;
    button.classList.toggle("active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  document.querySelector("#entity-library-search-view").hidden = view !== "search";
  document.querySelector("#entity-library-detail-view").hidden = view !== "detail";
  document.querySelector("#entity-library-organizer-view").hidden = !["entities", "variants", "sets", "facets"].includes(view);
  if (["entities", "variants", "sets", "facets"].includes(view)) renderEntityLibraryOrganizer(view);
  if (view === "search" && entityLibrarySearchStale && entityLibraryEditorState !== "loading") {
    void searchEntityLibrary(true);
  }
}

function entityLibraryRowsFor(kind) {
  return kind === "entities" ? entityLibraryMetadata.entities
    : kind === "variants" ? entityLibraryMetadata.variants
      : kind === "sets" ? entityLibraryMetadata.sets : entityLibraryMetadata.facets;
}

const entityLibraryOrganizationLabels = {
  entities: ["Entities", "Entities are people, places, creatures, and objects represented by your images."],
  variants: ["Variants", "Variants describe a form, stage, or version of an entity."],
  sets: ["Reference sets", "Reference sets group images for a shared subject or purpose."],
  facets: ["Facets", "Facets are reusable, structured labels such as view:front."],
};

function organizerId(kind, item) {
  return item.entity_id || item.variant_id || item.set_id || item.facet_id;
}

function organizerTitle(kind, item) {
  return kind === "facets" ? `${item.namespace}:${item.value}`
    : item.name || item.label || item.value;
}

function renderEntityLibraryOrganizer(kind, selectedId = "") {
  entityLibraryOrganizerSelectedId = selectedId;
  const rows = entityLibraryRowsFor(kind) || [];
  const heading = entityLibraryOrganizationLabels[kind];
  const singular = ({ entities: "entity", variants: "variant", sets: "set", facets: "facet" })[kind];
  const query = (entityLibraryOrganizer.querySelector("#inventory-organizer-search")?.value || "").trim().toLowerCase();
  const filtered = rows.filter((item) => `${organizerTitle(kind, item)} ${item.entity_type || ""} ${item.entity_name || ""}`.toLowerCase().includes(query));
  const selected = selectedId ? rows.find((item) => organizerId(kind, item) === selectedId) : null;
  entityLibraryOrganizer.innerHTML = `
    <header class="inventory-section-heading"><div><h2>${escapeHtml(heading[0])}</h2><p>${escapeHtml(heading[1])}</p></div><button class="primary-action" data-organizer-action="new">Add ${singular}</button></header>
    <div class="inventory-organizer-layout">
      <section class="control-panel inventory-organization-list"><label>Find ${escapeHtml(kind)}<input id="inventory-organizer-search" type="search" value="${escapeHtml(query)}" placeholder="Filter this list"></label>
      <p class="status-text">${rows.length} ${kind}</p>
      <div role="list">${filtered.map((item) => `<button type="button" role="listitem" class="inventory-organization-row${selected && organizerId(kind, item) === selectedId ? " selected" : ""}" data-organizer-action="select" data-id="${escapeHtml(organizerId(kind, item))}"><strong>${escapeHtml(organizerTitle(kind, item))}</strong><span>${escapeHtml(kind === "entities" ? item.entity_type : kind === "variants" ? `${item.entity_name} · ${item.variant_type}` : kind === "sets" ? item.set_type : item.controlled ? "Controlled" : "Free-form")}</span><small>${Number(item.image_count ?? item.usage_count ?? 0)} images</small></button>`).join("") || '<p class="status-text">No matches. Create the first item with “Add”.</p>'}</div></section>
      <section class="control-panel inventory-organization-detail" id="inventory-organization-detail">${selected ? renderOrganizationRecord(singular, selected) : '<p class="status-text">Choose an item to review its details and available actions.</p>'}</section>
    </div>`;
  entityLibraryOrganizer.querySelector("#inventory-organizer-search")?.addEventListener("input", () => {
    const value = entityLibraryOrganizer.querySelector("#inventory-organizer-search").value;
    renderEntityLibraryOrganizer(kind, selectedId);
    const input = entityLibraryOrganizer.querySelector("#inventory-organizer-search");
    input.focus(); input.setSelectionRange(value.length, value.length);
  });
  entityLibraryOrganizer.querySelector("[name=member_search]")?.addEventListener("input", (event) => renderInventorySetMatches(event.target.value));
  if (kind === "entities" && selected) {
    fetchJson(`/api/entity-library/relations?entity_id=${encodeURIComponent(selectedId)}`).then((payload) => {
      const list = entityLibraryOrganizer.querySelector("#inventory-relationships-list");
      if (!list) return;
      list.innerHTML = `<ul>${(payload.relations || []).map((relation) => `<li>${escapeHtml(relation.source_name)} ${escapeHtml(relation.relation_type.replaceAll("_", " "))} ${escapeHtml(relation.target_name)} <button type="button" data-organizer-action="remove-relation" data-source="${escapeHtml(relation.source_entity_id)}" data-target="${escapeHtml(relation.target_entity_id)}" data-type="${escapeHtml(relation.relation_type)}">Remove</button></li>`).join("") || "<li>No relationships yet.</li>"}</ul>`;
    }).catch(() => {});
  }
}

function renderOrganizationRecord(kind, item, creating = false) {
  const plural = ({ entity: "entities", variant: "variants", set: "sets", facet: "facets" })[kind];
  const id = organizerId(kind, item) || "";
  const readOnlyType = !creating && kind === "entity" ? `<label>Type<input value="${escapeHtml(item.entity_type || "character")}" disabled></label>`
    : !creating && kind === "variant" ? `<label>Type<input value="${escapeHtml(item.variant_type || "form")}" disabled></label><label>Owner<input value="${escapeHtml(item.entity_name || "")}" disabled></label>` : "";
  const formFields = kind === "facet"
    ? `<label>Namespace<input name="namespace" value="${escapeHtml(item.namespace || "view")}" ${creating ? "" : "disabled"} required></label><label>Value<input name="value" value="${escapeHtml(item.value || "")}" required></label>`
    : `<label>Name<input name="name" value="${escapeHtml(item.name || "")}" required></label>${readOnlyType}<label>Description<input name="description" value="${escapeHtml(item.description || "")}"></label>${kind === "set" ? `<label>Purpose<input name="set_type" value="${escapeHtml(item.set_type || "general")}" required></label><label>Related entity<select name="entity_id"><option value="">No owner</option>${entityLibraryMetadata.entities.map((entity) => `<option value="${escapeHtml(entity.entity_id)}"${entity.entity_id === item.entity_id ? " selected" : ""}>${escapeHtml(entity.name)}</option>`).join("")}</select></label>` : ""}${creating && kind === "variant" ? `<label>Owner<select name="entity_id" required>${entityLibraryMetadata.entities.map((entity) => `<option value="${escapeHtml(entity.entity_id)}">${escapeHtml(entity.name)}</option>`).join("")}</select></label><label>Variant type<select name="variant_type"><option value="life_stage">Life stage</option><option value="form">Form</option><option value="state">State</option><option value="version">Version</option></select></label>` : ""}${creating && kind === "entity" ? `<label>Type<select name="entity_type">${["character", "person", "creature", "group", "location", "structure", "prop", "costume", "symbol"].map((type) => `<option value="${type}">${type}</option>`).join("")}</select></label>` : ""}`;
  const descriptors = ["human_description", "prompt_identity", "prompt_costume", "prompt_object", "prompt_background", "negative_guidance", "selection_notes"];
  const currentDescriptor = (item.descriptors || [])[0];
  const descriptorHTML = ["entity", "variant", "set"].includes(kind) && !creating
    ? `<details class="inventory-subsection"><summary>Shared prompt descriptors</summary><label>Descriptor<select name="descriptor_type">${descriptors.map((type) => `<option value="${type}"${type === currentDescriptor?.descriptor_type ? " selected" : ""}>${type.replaceAll("_", " ")}</option>`).join("")}</select></label><label>Text<textarea name="descriptor_text">${escapeHtml(currentDescriptor?.text || "")}</textarea></label><button type="button" data-organizer-action="save-descriptor">Save descriptor</button><ul>${(item.descriptors || []).map((d) => `<li>${escapeHtml(d.descriptor_type.replaceAll("_", " "))}</li>`).join("")}</ul></details>` : "";
  const relationshipHTML = kind === "entity" && !creating
    ? `<details class="inventory-subsection"><summary>Relationships</summary><div id="inventory-relationships-list"></div><label>Link to<select name="relation_target"><option value="">Choose entity</option>${entityLibraryMetadata.entities.filter((entity) => entity.entity_id !== id).map((entity) => `<option value="${escapeHtml(entity.entity_id)}">${escapeHtml(entity.name)} · ${escapeHtml(entity.entity_type)}</option>`).join("")}</select></label><label>Relationship<select name="relation_type"><option value="part_of">Part of</option><option value="variant_of">Variant of</option><option value="associated_with">Associated with</option></select></label><button type="button" data-organizer-action="add-relation">Link entities</button></details>` : "";
  const setMembers = kind === "set" && !creating ? `<details class="inventory-subsection"><summary>Images in this set (${item.assets?.length || 0})</summary><ul>${(item.assets || []).map((asset) => `<li>${escapeHtml(asset.label || asset.file_name)} <button type="button" data-organizer-action="remove-member" data-asset-id="${escapeHtml(asset.asset_id)}">Remove</button></li>`).join("")}</ul><label>Find an image to add<input name="member_search" type="search" placeholder="Search image labels"></label><div id="inventory-set-image-matches"></div></details>` : "";
  return `<button type="button" class="text-action" data-organizer-action="list">← Back to ${escapeHtml(plural)}</button><form id="inventory-record-form" data-kind="${kind}" data-id="${escapeHtml(id)}"><h2>${creating ? `New ${kind}` : escapeHtml(organizerTitle(plural, item))}</h2>${formFields}<div class="button-row"><button class="primary-action" type="submit">${creating ? "Create" : "Save changes"}</button>${!creating ? `<button type="button" data-organizer-action="view-images">View images (${Number(item.image_count ?? item.usage_count ?? 0)})</button><button type="button" data-organizer-action="merge">Merge into…</button><button type="button" class="danger-action" data-organizer-action="delete">${kind === "set" ? "Delete set" : "Delete if unused"}</button>` : ""}</div></form>${descriptorHTML}${relationshipHTML}${setMembers}<div id="inventory-record-message" class="status-text" role="status"></div>`;
}

async function inventoryFilteredSearch(overrides = {}) {
  for (const [key, value] of Object.entries(overrides)) {
    const control = document.querySelector(`#entity-library-filter-${key}`);
    if (control) control.value = value;
  }
  activateInventoryView("search");
  await searchEntityLibrary();
}

async function previewOrganizationMerge(kind, sourceId) {
  const rows = entityLibraryRowsFor(kind === "entity" ? "entities" : kind === "variant" ? "variants" : kind === "set" ? "sets" : "facets");
  const source = rows.find((item) => organizerId(kind === "entity" ? "entities" : kind === "variant" ? "variants" : kind === "set" ? "sets" : "facets", item) === sourceId);
  const candidates = rows.filter((item) => {
    if (organizerId(kind === "entity" ? "entities" : kind === "variant" ? "variants" : kind === "set" ? "sets" : "facets", item) === sourceId) return false;
    if (kind === "entity") return item.entity_type === source?.entity_type;
    if (kind === "variant") return item.entity_id === source?.entity_id && item.variant_type === source?.variant_type;
    if (kind === "facet") return item.namespace === source?.namespace;
    return true;
  });
  if (!candidates.length) return;
  const listKind = kind === "entity" ? "entities" : kind === "variant" ? "variants" : kind === "set" ? "sets" : "facets";
  entityLibraryMergeContent.innerHTML = `<p>Choose the record that should keep its ID and image tags.</p><label>Keep<select id="inventory-merge-target">${candidates.map((item) => `<option value="${escapeHtml(organizerId(listKind, item))}">${escapeHtml(organizerTitle(listKind, item))}</option>`).join("")}</select></label><button id="inventory-merge-preview" type="button" class="secondary-action">Preview merge</button>`;
  entityLibraryMergeConfirm.disabled = true;
  entityLibraryMergeConfirm.onclick = null;
  entityLibraryMergeDialog.showModal();
  entityLibraryMergeContent.querySelector("#inventory-merge-preview").addEventListener("click", async () => {
    const targetId = entityLibraryMergeContent.querySelector("#inventory-merge-target").value;
    try {
      const result = await fetchJson(`/api/entity-library/merges/${kind}/preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_id: sourceId, target_id: targetId }) });
      entityLibraryMergePreview = result.preview;
      renderOrganizationMergePreview(kind, sourceId, targetId, result.preview);
    } catch (error) { window.alert(error.message); }
  });
}

function renderOrganizationMergePreview(kind, sourceId, targetId, preview) {
  entityLibraryMergeContent.innerHTML = `<p>Merge <strong>${escapeHtml(preview.source.name || `${preview.source.namespace}:${preview.source.value}`)}</strong> into <strong>${escapeHtml(preview.target.name || `${preview.target.namespace}:${preview.target.value}`)}</strong>. ${preview.image_count} image or organization record(s) will be retained under the target.</p>${preview.conflicts.length ? preview.conflicts.map((conflict) => `<fieldset class="inventory-merge-conflict"><legend>${escapeHtml(conflict.label)}</legend><label><input type="radio" name="${escapeHtml(conflict.key)}" value="target"> Keep target: <span>${escapeHtml(String(conflict.target))}</span></label><label><input type="radio" name="${escapeHtml(conflict.key)}" value="source"> Use source: <span>${escapeHtml(String(conflict.source))}</span></label></fieldset>`).join("") : "<p>No conflicting values. The merge can be applied safely.</p>"}`;
  entityLibraryMergeConfirm.disabled = preview.conflicts.length > 0;
  entityLibraryMergeConfirm.onclick = async () => {
    const resolutions = {};
    for (const conflict of preview.conflicts) {
      const choice = entityLibraryMergeContent.querySelector(`input[name="${CSS.escape(conflict.key)}"]:checked`);
      if (!choice) return;
      resolutions[conflict.key] = choice.value;
    }
    entityLibraryMergeConfirm.disabled = true;
    try {
      await fetchJson(`/api/entity-library/merges/${kind}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_id: sourceId, target_id: targetId, token: preview.token, resolutions }) });
      entityLibraryMergeDialog.close();
      await loadEntityLibraryInventory();
      const page = kind === "entity" ? "entities" : kind === "variant" ? "variants" : kind === "set" ? "sets" : "facets";
      activateInventoryView(page);
    } catch (error) { window.alert(error.message); entityLibraryMergeConfirm.disabled = false; }
  };
  entityLibraryMergeContent.onchange = () => {
    entityLibraryMergeConfirm.disabled = preview.conflicts.some((conflict) => !entityLibraryMergeContent.querySelector(`input[name="${CSS.escape(conflict.key)}"]:checked`));
  };
}

async function handleOrganizationAction(event) {
  const button = event.target.closest("[data-organizer-action]");
  if (!button) return;
  const action = button.dataset.organizerAction;
  const form = button.closest("#inventory-record-form");
  const kindPlural = entityLibraryCurrentView;
  const kind = ({ entities: "entity", variants: "variant", sets: "set", facets: "facet" })[kindPlural];
  const id = form?.dataset.id || button.dataset.id || entityLibraryOrganizerSelectedId;
  const detailMessage = entityLibraryOrganizer.querySelector("#inventory-record-message");
  const report = (message) => { if (detailMessage) detailMessage.textContent = message; else window.alert(message); };
  try {
    if (action === "select") return renderEntityLibraryOrganizer(kindPlural, id);
    if (action === "list") return renderEntityLibraryOrganizer(kindPlural);
    if (action === "new") {
      renderEntityLibraryOrganizer(kindPlural);
      entityLibraryOrganizer.querySelector("#inventory-organization-detail").innerHTML = renderOrganizationRecord(kind, {}, true);
      return;
    }
    if (action === "view-images") {
      const filters = kind === "entity" ? { entity: id } : kind === "variant" ? { variant: id } : kind === "set" ? { set: id } : { facet: `${entityLibraryMetadata.facets.find((item) => item.facet_id === id)?.namespace}\u0000${entityLibraryMetadata.facets.find((item) => item.facet_id === id)?.value}` };
      return await inventoryFilteredSearch(filters);
    }
    if (action === "delete") {
      if (!window.confirm("Delete this organization record? Its images will be kept.")) return;
      const url = `/api/entity-library/${kindPlural}/${encodeURIComponent(id)}`;
      await fetchJson(url, { method: "DELETE" });
      await loadEntityLibraryInventory(); return activateInventoryView(kindPlural);
    }
    if (action === "merge") return previewOrganizationMerge(kind, id);
    if (action === "save-descriptor") {
      await fetchJson("/api/entity-library/descriptors", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ owner_type: kind, owner_id: id, descriptor_type: form.elements.descriptor_type.value, text: form.elements.descriptor_text.value }) });
      await loadEntityLibraryInventory(); return renderEntityLibraryOrganizer(kindPlural, id);
    }
    if (action === "add-relation") {
      if (!form.elements.relation_target.value) return;
      await fetchJson("/api/entity-library/relations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_entity_id: id, target_entity_id: form.elements.relation_target.value, relation_type: form.elements.relation_type.value }) });
      report("Relationship added."); return;
    }
    if (action === "remove-relation") {
      const params = new URLSearchParams({ source_entity_id: button.dataset.source, target_entity_id: button.dataset.target, relation_type: button.dataset.type });
      await fetchJson(`/api/entity-library/relations?${params}`, { method: "DELETE" });
      return loadEntityLibraryInventory().then(() => renderEntityLibraryOrganizer(kindPlural, id));
    }
    if (action === "remove-member") {
      await fetchJson(`/api/entity-library/sets/${encodeURIComponent(id)}/assets/${encodeURIComponent(button.dataset.assetId)}`, { method: "DELETE" });
      return loadEntityLibraryInventory().then(() => renderEntityLibraryOrganizer(kindPlural, id));
    }
    if (action === "add-member-image") {
      await fetchJson(`/api/entity-library/sets/${encodeURIComponent(id)}/assets/${encodeURIComponent(button.dataset.assetId)}`, { method: "POST" });
      return loadEntityLibraryInventory().then(() => renderEntityLibraryOrganizer(kindPlural, id));
    }
  } catch (error) { report(error.message); }
}

async function saveOrganizationRecord(event) {
  event.preventDefault();
  const form = event.target;
  if (!form.matches("#inventory-record-form")) return;
  const kind = form.dataset.kind;
  const id = form.dataset.id;
  const data = Object.fromEntries(new FormData(form));
  try {
    if (!id) {
      if (kind === "entity") await fetchJson("/api/entity-library/entities", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
      else if (kind === "variant") await fetchJson(`/api/entity-library/entities/${encodeURIComponent(data.entity_id)}/variants`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
      else if (kind === "set") await fetchJson("/api/entity-library/sets", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
      else await fetchJson("/api/entity-library/facets", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
    } else {
      const url = `/api/entity-library/${kind === "set" ? "sets" : `${kind}s`}/${encodeURIComponent(id)}`;
      await fetchJson(url, { method: kind === "set" ? "PUT" : "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
    }
    await loadEntityLibraryInventory();
    renderEntityLibraryOrganizer(kind === "entity" ? "entities" : kind === "variant" ? "variants" : kind === "set" ? "sets" : "facets");
  } catch (error) {
    const message = entityLibraryOrganizer.querySelector("#inventory-record-message");
    if (message) message.textContent = error.message; else window.alert(error.message);
  }
}

async function renderInventorySetMatches(query) {
  const target = entityLibraryOrganizer.querySelector("#inventory-set-image-matches");
  const form = entityLibraryOrganizer.querySelector("#inventory-record-form");
  if (!target || !form || !query.trim()) { if (target) target.replaceChildren(); return; }
  try {
    const params = new URLSearchParams({ q: query.trim(), limit: "10" });
    const payload = await fetchJson(`/api/entity-library/assets?${params}`);
    target.replaceChildren();
    for (const asset of payload.assets || []) {
      if (form.closest("#inventory-organization-detail") && !asset.sets?.some((set) => set.set_id === form.dataset.id)) {
        const button = document.createElement("button"); button.type = "button"; button.textContent = `Add ${asset.label || asset.file_name}`; button.dataset.organizerAction = "add-member-image"; button.dataset.assetId = asset.asset_id; target.append(button);
      }
    }
  } catch { target.textContent = "Could not search images."; }
}

function syncEntityLibrarySetEditor() {
  const selected = entityLibraryMetadata.sets.find((item) => item.set_id === entityLibrarySetSelect.value);
  entityLibrarySetName.value = selected?.name || "";
  entityLibrarySetType.value = selected?.set_type || "";
  entityLibrarySetCreate.hidden = Boolean(selected);
  entityLibrarySetSave.disabled = !selected;
  entityLibrarySetDelete.disabled = !selected;
  entityLibrarySetSave.textContent = "Save set";
}

async function saveEntityLibrarySet() {
  const setId = entityLibrarySetSelect.value;
  if (!setId || !entityLibrarySetName.value.trim()) return;
  try {
    await fetchJson(`/api/entity-library/sets/${encodeURIComponent(setId)}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: entityLibrarySetName.value, set_type: entityLibrarySetType.value || "general" }),
    });
    await loadEntityLibraryInventory();
    entityLibrarySetSelect.value = setId;
    syncEntityLibrarySetEditor();
    showAuxResourceMessage("Reference set saved.", "success");
  } catch (error) {
    showAuxResourceMessage(error.message, "error");
  }
}

async function deleteEntityLibrarySet() {
  const selected = entityLibraryMetadata.sets.find((item) => item.set_id === entityLibrarySetSelect.value);
  if (!selected) return;
  const count = selected.assets?.length || 0;
  const confirmation = count
    ? `Delete ${selected.name}? Its ${count} image link(s) will be removed; the images will stay in the library.`
    : `Delete the empty reference set ${selected.name}?`;
  if (!window.confirm(confirmation)) return;
  try {
    await fetchJson(`/api/entity-library/sets/${encodeURIComponent(selected.set_id)}`, { method: "DELETE" });
    entityLibrarySetSelect.value = "";
    await loadEntityLibraryInventory();
    showAuxResourceMessage(`Deleted ${selected.name}.`, "success");
  } catch (error) {
    showAuxResourceMessage(error.message, "error");
  }
}

function entityLibraryEditorSnapshot() {
  return JSON.stringify({
    asset_id: entityLibrarySelectedAsset?.asset_id || "",
    label: entityLibraryEditLabel.value,
    notes: entityLibraryEditNotes.value,
    status: entityLibraryEditStatus.value,
    entities: Array.from(entityLibraryEditEntities.selectedOptions, (item) => item.value),
    sets: Array.from(entityLibraryEditSets.selectedOptions, (item) => item.value),
    facets: entityLibraryEditFacets.value,
    tags: entityLibraryEditTags.value,
    identity: entityLibraryEditIdentity.value,
    costume: entityLibraryEditCostume.value,
    prompt: entityLibraryEditPrompt.value,
    negative_prompt: entityLibraryEditNegativePrompt.value,
    reference: entityLibraryEditReference.value,
  });
}

function applyEntityLibraryEditorSnapshot(snapshot) {
  if (!snapshot.asset_id || snapshot.asset_id !== entityLibrarySelectedAsset?.asset_id) return;
  entityLibraryEditLabel.value = snapshot.label;
  entityLibraryEditNotes.value = snapshot.notes;
  entityLibraryEditStatus.value = snapshot.status;
  for (const optionItem of entityLibraryEditEntities.options) optionItem.selected = snapshot.entities.includes(optionItem.value);
  for (const optionItem of entityLibraryEditSets.options) optionItem.selected = snapshot.sets.includes(optionItem.value);
  entityLibraryEditFacets.value = snapshot.facets;
  entityLibraryEditTags.value = snapshot.tags;
  entityLibraryEditIdentity.value = snapshot.identity;
  entityLibraryEditCostume.value = snapshot.costume;
  entityLibraryEditPrompt.value = snapshot.prompt;
  entityLibraryEditNegativePrompt.value = snapshot.negative_prompt;
  entityLibraryEditReference.value = snapshot.reference;
}

function setEntityLibraryEditorState(nextState, message = "") {
  entityLibraryEditorState = nextState;
  entityLibraryEditorStateMessage.textContent = message;
  entityLibraryEditorStateMessage.classList.toggle("error", nextState === "error");
  entityLibraryRetryLoad.hidden = nextState !== "error";
  const busy = nextState === "loading" || nextState === "saving";
  for (const control of document.querySelectorAll(".entity-library-editor input, .entity-library-editor select, .entity-library-editor textarea, .entity-library-editor button")) {
    if (control === entityLibraryRetryLoad) continue;
    control.disabled = busy || nextState !== "ready";
  }
  if (nextState === "ready" && entityLibrarySelectedAsset) {
    const archived = entityLibrarySelectedAsset.status === "archived";
    entityLibraryDelete.disabled = archived;
    entityLibraryReplace.disabled = archived || !(entityLibraryReplacementFile.files?.[0] || state.entityLibraryReplacementBlob);
    entityLibraryReplacementFile.disabled = archived;
    entityLibraryGeneratePrompt.disabled = archived || Boolean(entityLibraryEditPrompt.value && entityLibraryEditNegativePrompt.value);
    entityLibraryGenerateIdentity.disabled = archived;
    entityLibraryModifyGenerated.disabled = archived || entityLibrarySelectedAsset.origin === "pipeline";
    entityLibraryModifyGenerated.hidden = archived || entityLibrarySelectedAsset.origin === "pipeline";
  }
}

function renderEntityLibraryAsset(asset) {
  entityLibrarySelectedAsset = asset;
  entityLibraryEditorTitle.textContent = asset.label || asset.file_name;
  entityLibraryPreview.src = fileUrl(asset.image_path);
  entityLibraryPreview.hidden = false;
  entityLibraryPromptStatus.textContent = "";
  entityLibraryIdentityStatus.textContent = "";
  entityLibraryModifyStatus.textContent = "";
  entityLibraryEditLabel.value = asset.label || "";
  entityLibraryEditPrompt.value = asset.prompt || "";
  entityLibraryEditNegativePrompt.value = asset.negative_prompt || "";
  entityLibraryEditNotes.value = asset.notes || "";
  entityLibraryEditStatus.value = asset.status;
  const entityIds = (asset.entities || []).map((item) => item.entity_id);
  const setIds = (asset.sets || []).map((item) => item.set_id);
  for (const optionItem of entityLibraryEditEntities.options) optionItem.selected = entityIds.includes(optionItem.value);
  for (const optionItem of entityLibraryEditSets.options) optionItem.selected = setIds.includes(optionItem.value);
  entityLibraryEditFacets.value = (asset.facets || []).map((item) => `${item.namespace}:${item.value}`).join(", ");
  entityLibraryEditTags.value = (asset.tags || []).join(", ");
  entityLibraryEditIdentity.value = (asset.descriptors || []).find((item) => item.descriptor_type === "prompt_identity")?.text || "";
  entityLibraryEditCostume.value = (asset.descriptors || []).find((item) => item.descriptor_type === "prompt_costume")?.text || "";
  entityLibraryEditReference.value = asset.logical_reference?.reference_key || "";
  entityLibraryLogicalReferences.replaceChildren();
  for (const reference of asset.logical_references || []) {
    const row = document.createElement("li");
    const tag = document.createElement("code");
    tag.textContent = `{{LIB:REF:${reference.reference_key}}}`;
    const status = document.createElement("span");
    status.textContent = ` · ${reference.status}`;
    row.append(tag, status);
    entityLibraryLogicalReferences.append(row);
  }
  if (!asset.logical_references?.length) {
    const row = document.createElement("li");
    row.textContent = "No logical references.";
    entityLibraryLogicalReferences.append(row);
  }
  entityLibraryUsages.replaceChildren();
  for (const usage of asset.usages || []) {
    const row = document.createElement("li");
    row.textContent = `${usage.consumer_type}: ${usage.consumer_id} · ${usage.locator}`;
    entityLibraryUsages.append(row);
  }
  if (!asset.usages?.length) {
    const row = document.createElement("li");
    row.textContent = "No current consumers.";
    entityLibraryUsages.append(row);
  }
  entityLibrarySavedSnapshot = entityLibraryEditorSnapshot();
  entityLibrarySearchStale = true;
}

async function selectEntityLibraryAsset(assetId) {
  entityLibraryLoadingAssetId = assetId;
  const selection = beginSelection("entity-library-asset");
  activateInventoryView("detail");
  setEntityLibraryEditorState("loading", "Loading image details…");
  entityLibraryEditorTitle.textContent = "Loading image…";
  entityLibraryPreview.hidden = true;
  try {
    const payload = await fetchJson(`/api/entity-library/assets/${encodeURIComponent(assetId)}`, {
      bindToPage: false, signal: selection.controller.signal,
    });
    if (!selectionIsCurrent(selection)) return false;
    renderEntityLibraryAsset(payload.asset);
    setEntityLibraryEditorState("ready", "Image details loaded.");
    return true;
  } catch (error) {
    if (!selectionIsCurrent(selection) || isRequestCancellation(error)) return false;
    setEntityLibraryEditorState("error", `Could not load image details: ${error.message}`);
    return false;
  }
}

async function deleteEntityLibraryAsset() {
  const asset = entityLibrarySelectedAsset;
  if (!asset || asset.status === "archived") return;
  if (!window.confirm(`Archive ${asset.label || asset.file_name} from the image inventory? Its logical references will be deactivated. Current consumers must be updated first.`)) return;
  entityLibraryDelete.disabled = true;
  try {
    await fetchJson(`/api/entity-library/assets/${encodeURIComponent(asset.asset_id)}`, { method: "DELETE" });
    entityLibrarySelectedAsset = null;
    entityLibraryEditorTitle.textContent = "Select an image";
    entityLibraryPreview.hidden = true;
    entityLibraryBack.hidden = true;
    document.querySelector(".entity-library-layout").classList.remove("metadata-mode");
    await loadEntityLibraryInventory();
    showAuxResourceMessage("Image deleted from the inventory.", "success");
  } catch (error) {
    showAuxResourceMessage(error.message, "error");
    entityLibraryDelete.disabled = false;
  }
}

async function saveEntityLibraryAsset() {
  if (entityLibrarySavePromise) return entityLibrarySavePromise;
  const asset = entityLibrarySelectedAsset;
  if (!asset || entityLibraryEditorState !== "ready") return false;
  setEntityLibraryEditorState("saving", "Saving image…");
  const facets = entityLibraryEditFacets.value.split(",").map((entry) => entry.trim()).filter(Boolean).map((entry) => {
    const split = entry.indexOf(":");
    return { namespace: split < 0 ? "tag" : entry.slice(0, split).trim(), value: split < 0 ? entry : entry.slice(split + 1).trim(), controlled: split >= 0 };
  });
  const existingEntityLinks = new Map((asset.entities || []).map((item) => [item.entity_id, item]));
  const entityLinks = [...entityLibraryEditEntities.selectedOptions].map((optionItem) => ({
    entity_id: optionItem.value,
    role: existingEntityLinks.get(optionItem.value)?.role || "depicted_subject",
    variant_id: existingEntityLinks.get(optionItem.value)?.variant_id || null,
  }));
  const setIds = [...entityLibraryEditSets.selectedOptions].map((optionItem) => optionItem.value);
  const request = (async () => {
    try {
      const payload = await fetchJson(`/api/entity-library/assets/${encodeURIComponent(asset.asset_id)}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          label: entityLibraryEditLabel.value, notes: entityLibraryEditNotes.value,
          status: entityLibraryEditStatus.value, prompt: entityLibraryEditPrompt.value,
          negative_prompt: entityLibraryEditNegativePrompt.value, entity_links: entityLinks,
          set_ids: setIds, facets, tags: entityLibraryEditTags.value.split(",").map((tag) => tag.trim()).filter(Boolean),
          descriptors: { prompt_identity: entityLibraryEditIdentity.value, prompt_costume: entityLibraryEditCostume.value },
          preferred_reference_key: entityLibraryEditReference.value.trim(),
        }),
      });
      if (!payload.asset) throw new Error("The save response did not include the saved image.");
      renderEntityLibraryAsset(payload.asset);
      setEntityLibraryEditorState("ready", payload.refresh_warning || "Image saved.");
      if (payload.refresh_warning) entityLibraryEditorStateMessage.classList.add("error");
      return true;
    } catch (error) {
      setEntityLibraryEditorState("ready", `Save failed: ${error.message}`);
      entityLibraryEditorStateMessage.classList.add("error");
      return false;
    } finally {
      entityLibrarySavePromise = null;
    }
  })();
  entityLibrarySavePromise = request;
  return request;
}

async function loadImageCatalog() {
  imageCatalogCount.textContent = "Loading image inventory...";
  imageCatalogRefresh.disabled = true;
  imageCatalogRefresh.textContent = "Loading...";
  try {
    const payload = await fetchJson(`/api/image-catalog?${imageCatalogQuery().toString()}`);
    state.imageCatalogItems = payload.items || [];
    state.imageCatalogLoaded = true;
    state.selectedImageCatalogIds = state.selectedImageCatalogIds.filter((catalogId) => state.imageCatalogItems.some((item) => item.catalog_id === catalogId));
    if (state.selectedImageCatalogId && !state.imageCatalogItems.some((item) => item.catalog_id === state.selectedImageCatalogId)) {
      state.selectedImageCatalogId = null;
    }
    renderImageCatalog();
  } catch (error) {
    imageCatalogCount.textContent = "Load failed.";
    showAuxResourceMessage(error.message, "error");
  } finally {
    imageCatalogRefresh.disabled = false;
    imageCatalogRefresh.textContent = "Refresh images";
  }
}

async function saveImageCatalogItem() {
  const item = selectedImageCatalogItem();
  if (!item) return;
  const identity = { mode: imageCatalogIdentityMode.value, provenance: "manual" };
  const costume = { mode: imageCatalogCostumeMode.value, provenance: "manual" };
  if (identity.mode === "override") identity.approved_text = imageCatalogIdentityText.value;
  if (costume.mode === "override") costume.approved_text = imageCatalogCostumeText.value;
  const changes = {
    semantic_category: imageCatalogEditCategory.value,
    collection_ids: Array.from(imageCatalogEditCollections.selectedOptions, (option) => option.value),
    keyword_ids: Array.from(imageCatalogEditKeywords.selectedOptions, (option) => option.value),
    identity,
    costume,
  };
  if (item.is_managed) {
    changes.label = imageCatalogManagedLabel.value;
    changes.reference_set_id = imageCatalogManagedSet.value;
  }
  try {
    await fetchJson(`/api/image-catalog/${encodeURIComponent(item.catalog_id)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes) });
    await loadImageCatalogOrganization();
    await loadImageCatalog();
    selectImageCatalogItem(item.catalog_id);
    showAuxResourceMessage("Image metadata saved.", "success");
  } catch (error) {
    showAuxResourceMessage(error.message, "error");
  }
}

async function queueImageCatalogDescription() {
  const item = selectedImageCatalogItem();
  if (!item) return;
  const selection = beginSelection("image-catalog");
  const catalogId = item.catalog_id;
  imageCatalogAi.disabled = true;
  showMessageElement(imageCatalogAiStatus, "Initiating AI image description...", "info");
  try {
    const payload = await fetchJson(`/api/image-catalog/${encodeURIComponent(catalogId)}/ai-description`, { method: "POST" });
    if (!selectionIsCurrent(selection) || state.selectedImageCatalogId !== catalogId) return;
    const index = state.imageCatalogItems.findIndex((candidate) => candidate.catalog_id === catalogId);
    if (index >= 0) state.imageCatalogItems[index] = payload.item;
    selectImageCatalogItem(catalogId);
    showAuxResourceMessage(payload.message || "Image description job queued.", "success");
  } catch (error) {
    if (!selectionIsCurrent(selection) || isRequestCancellation(error)) return;
    imageCatalogAi.disabled = false;
    showMessageElement(imageCatalogAiStatus, error.message, "error");
    showAuxResourceMessage(error.message, "error");
  }
}

async function harvestImageCatalogDescription() {
  const item = selectedImageCatalogItem();
  if (!item) return;
  const selection = beginSelection("image-catalog");
  const catalogId = item.catalog_id;
  imageCatalogAiCheck.disabled = true;
  showMessageElement(imageCatalogAiStatus, "Checking for an AI answer...", "info");
  try {
    const payload = await fetchJson(`/api/image-catalog/${encodeURIComponent(catalogId)}/ai-description/harvest`, { method: "POST" });
    if (!selectionIsCurrent(selection) || state.selectedImageCatalogId !== catalogId) return;
    const index = state.imageCatalogItems.findIndex((candidate) => candidate.catalog_id === catalogId);
    if (index >= 0) state.imageCatalogItems[index] = payload.item;
    selectImageCatalogItem(catalogId);
    showAuxResourceMessage(payload.message, payload.item.description_status === "ai_review_required" ? "success" : "info");
  } catch (error) {
    if (!selectionIsCurrent(selection) || isRequestCancellation(error)) return;
    imageCatalogAiCheck.disabled = false;
    showMessageElement(imageCatalogAiStatus, error.message, "error");
    showAuxResourceMessage(error.message, "error");
  }
}

async function reviewImageCatalogDraft(approve) {
  const item = selectedImageCatalogItem();
  if (!item) return;
  const selection = beginSelection("image-catalog");
  const catalogId = item.catalog_id;
  const suffix = approve ? "approve" : "reject";
  const options = { method: "POST" };
  if (approve) {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify({ identity_text: imageCatalogAiIdentity.value, costume_text: imageCatalogAiCostume.value, costume_not_applicable: imageCatalogCostumeMode.value === "not_applicable" });
  }
  try {
    const payload = await fetchJson(`/api/image-catalog/${encodeURIComponent(catalogId)}/ai-description/${suffix}`, options);
    if (!selectionIsCurrent(selection) || state.selectedImageCatalogId !== catalogId) return;
    const index = state.imageCatalogItems.findIndex((candidate) => candidate.catalog_id === catalogId);
    if (index >= 0 && payload.item) state.imageCatalogItems[index] = payload.item;
    await loadImageCatalog();
    if (!selectionIsCurrent(selection) || state.selectedImageCatalogId !== catalogId) return;
    selectImageCatalogItem(catalogId);
    showAuxResourceMessage(approve ? "AI draft approved." : "AI draft rejected.", "success");
  } catch (error) {
    if (!selectionIsCurrent(selection) || isRequestCancellation(error)) return;
    showAuxResourceMessage(error.message, "error");
  }
}

async function addImageCatalogVocabulary(kind, input) {
  const label = input.value.trim();
  if (!label) return;
  try {
    await fetchJson(`/api/image-catalog/organization/${kind}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ label }) });
    input.value = "";
    await loadImageCatalogOrganization();
  } catch (error) {
    showAuxResourceMessage(error.message, "error");
  }
}

async function bulkUpdateImageCatalog() {
  if (!state.selectedImageCatalogIds.length) return;
  const changes = {};
  if (imageCatalogBulkCategory.value) changes.semantic_category = imageCatalogBulkCategory.value;
  if (imageCatalogBulkSet.value !== "__no_change__") changes.reference_set_id = imageCatalogBulkSet.value;
  const collectionIds = Array.from(imageCatalogBulkCollections.selectedOptions, (option) => option.value);
  const keywordIds = Array.from(imageCatalogBulkKeywords.selectedOptions, (option) => option.value);
  if (collectionIds.length) changes.collection_ids = collectionIds;
  if (keywordIds.length) changes.keyword_ids = keywordIds;
  if (!Object.keys(changes).length) return;
  try {
    await fetchJson("/api/image-catalog/bulk", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ catalog_ids: state.selectedImageCatalogIds, changes }) });
    await loadImageCatalogOrganization();
    await loadImageCatalog();
    showAuxResourceMessage(`Updated ${state.selectedImageCatalogIds.length} image(s).`, "success");
  } catch (error) {
    showAuxResourceMessage(error.message, "error");
  }
}

function fillReferenceSetSelect(select, selectedValue = "") {
  setSelectOptionsWithLabels(select, [
    { value: "", label: "No reference set" },
    ...state.imageCatalogReferenceSets.map((item) => ({ value: item.reference_set_id, label: `${item.label} (${item.image_count || 0})` })),
  ]);
  select.value = selectedValue || "";
}

async function loadImageCatalogReferenceSets() {
  const payload = await fetchJson("/api/image-catalog/reference-sets");
  state.imageCatalogReferenceSets = payload.reference_sets || [];
  fillReferenceSetSelect(imageCatalogImportSet, imageCatalogImportSet.value);
  fillReferenceSetSelect(imageCatalogManagedSet, selectedImageCatalogItem()?.reference_set_id || "");
  const bulkSet = imageCatalogBulkSet.value;
  setSelectOptionsWithLabels(imageCatalogBulkSet, [
    { value: "__no_change__", label: "No change" },
    { value: "", label: "No reference set" },
    ...state.imageCatalogReferenceSets.map((item) => ({ value: item.reference_set_id, label: item.label })),
  ]);
  imageCatalogBulkSet.value = Array.from(imageCatalogBulkSet.options).some((option) => option.value === bulkSet) ? bulkSet : "__no_change__";
  const selected = imageCatalogSetSelect.value;
  setSelectOptionsWithLabels(imageCatalogSetSelect, [
    { value: "", label: "New reference set" },
    ...state.imageCatalogReferenceSets.map((item) => ({ value: item.reference_set_id, label: `${item.label} (${item.image_count || 0})` })),
  ]);
  imageCatalogSetSelect.value = state.imageCatalogReferenceSets.some((item) => item.reference_set_id === selected) ? selected : "";
  renderSelectedReferenceSet();
}

function renderSelectedReferenceSet() {
  const item = state.imageCatalogReferenceSets.find((candidate) => candidate.reference_set_id === imageCatalogSetSelect.value);
  imageCatalogSetLabel.value = item?.label || "";
  imageCatalogSetIdentity.value = item?.identity_text || "";
  imageCatalogSetCostume.value = item?.costume_text || "";
  imageCatalogSetDelete.disabled = !item;
}

function setImageCatalogImportBlob(blob) {
  if (!blob || !["image/png", "image/jpeg", "image/webp", "image/gif"].includes(blob.type)) {
    imageCatalogImportStatus.textContent = "Choose a PNG, JPEG, WebP, or GIF image.";
    state.imageCatalogImportBlob = null;
    imageCatalogImportSave.disabled = true;
    return;
  }
  state.imageCatalogImportBlob = blob;
  if (!imageCatalogImportLabel.value && blob.name) {
    imageCatalogImportLabel.value = blob.name.replace(/\.[^.]+$/, "");
  }
  imageCatalogImportStatus.textContent = `${blob.name || "Pasted image"} ready to import.`;
  imageCatalogImportSave.disabled = false;
}

function setImageCatalogManagedBlob(mode, blob) {
  const isAdd = mode === "add";
  const stateKey = isAdd ? "imageCatalogAddBlob" : "imageCatalogReplaceBlob";
  const status = isAdd ? imageCatalogAddStatus : imageCatalogReplaceStatus;
  const submit = isAdd ? imageCatalogAddSubmit : imageCatalogReplaceSubmit;
  const label = isAdd ? imageCatalogAddLabel : null;
  if (!blob || !["image/png", "image/jpeg", "image/webp", "image/gif"].includes(blob.type)) {
    status.textContent = "Choose a PNG, JPEG, WebP, or GIF image.";
    state[stateKey] = null;
    submit.disabled = true;
    return;
  }
  state[stateKey] = blob;
  if (label && !label.value && blob.name) {
    label.value = blob.name.replace(/\.[^.]+$/, "");
  }
  status.textContent = `${blob.name || "Pasted image"} ready.`;
  submit.disabled = false;
}

function openImageCatalogManagedUpload(mode) {
  const isAdd = mode === "add";
  const panel = isAdd ? imageCatalogAddUpload : imageCatalogReplaceUpload;
  panel.hidden = false;
  (isAdd ? imageCatalogAddFile : imageCatalogReplaceFile).focus();
}

async function importImageCatalogImage() {
  const blob = state.imageCatalogImportBlob;
  const label = imageCatalogImportLabel.value.trim();
  if (!blob || !label) {
    showAuxResourceMessage("Choose an image and enter a label.", "error");
    return;
  }
  const params = new URLSearchParams({
    label,
    semantic_category: imageCatalogImportCategory.value,
    reference_set_id: imageCatalogImportSet.value,
  });
  imageCatalogImportSave.disabled = true;
  try {
    const payload = await fetchJson(`/api/image-catalog/imports?${params.toString()}`, { method: "POST", headers: { "Content-Type": blob.type }, body: blob });
    state.imageCatalogImportBlob = null;
    imageCatalogImportFile.value = "";
    imageCatalogImportLabel.value = "";
    imageCatalogImportStatus.textContent = "Choose or paste an image.";
    await loadImageCatalogReferenceSets();
    await loadImageCatalog();
    selectImageCatalogItem(payload.item.catalog_id);
    showAuxResourceMessage(payload.message, "success");
  } catch (error) {
    showAuxResourceMessage(error.message, "error");
    imageCatalogImportSave.disabled = false;
  }
}

async function replaceImageCatalogImage() {
  const item = selectedImageCatalogItem();
  const blob = state.imageCatalogReplaceBlob || imageCatalogReplaceFile.files?.[0];
  if (!item?.is_managed) return;
  if (!blob) {
    openImageCatalogManagedUpload("replace");
    return;
  }
  imageCatalogReplace.disabled = true;
  imageCatalogReplaceSubmit.disabled = true;
  try {
    const payload = await fetchJson(`/api/image-catalog/${encodeURIComponent(item.catalog_id)}/content`, { method: "PUT", headers: { "Content-Type": blob.type }, body: blob });
    await loadImageCatalog();
    selectImageCatalogItem(payload.item.catalog_id);
    showAuxResourceMessage(payload.message, "success");
  } catch (error) {
    imageCatalogReplace.disabled = false;
    imageCatalogReplaceSubmit.disabled = false;
    showAuxResourceMessage(error.message, "error");
  }
}

async function addImageCatalogImage() {
  const item = selectedImageCatalogItem();
  const blob = state.imageCatalogAddBlob || imageCatalogAddFile.files?.[0];
  const label = imageCatalogAddLabel.value.trim();
  const referenceSetId = imageCatalogManagedSet.value;
  if (!item?.is_managed) return;
  if (!referenceSetId) {
    showAuxResourceMessage("Assign this image to a reference set before adding another image.", "error");
    return;
  }
  if (!blob || !label) {
    showAuxResourceMessage("Choose an image and enter a label.", "error");
    return;
  }
  const params = new URLSearchParams({
    label,
    semantic_category: item.semantic_category,
    reference_set_id: referenceSetId,
  });
  imageCatalogAdd.disabled = true;
  imageCatalogAddSubmit.disabled = true;
  try {
    const payload = await fetchJson(`/api/image-catalog/imports?${params.toString()}`, { method: "POST", headers: { "Content-Type": blob.type }, body: blob });
    await loadImageCatalogReferenceSets();
    await loadImageCatalog();
    selectImageCatalogItem(payload.item.catalog_id);
    showAuxResourceMessage(payload.message, "success");
  } catch (error) {
    imageCatalogAdd.disabled = false;
    imageCatalogAddSubmit.disabled = false;
    showAuxResourceMessage(error.message, "error");
  }
}

async function deleteImageCatalogImage(force = false) {
  const item = selectedImageCatalogItem();
  if (!item?.is_managed || (!force && !window.confirm(`Delete ${item.label}? The file will be moved to catalog trash.`))) return;
  try {
    const payload = await fetchJson(`/api/image-catalog/${encodeURIComponent(item.catalog_id)}?force=${force}`, { method: "DELETE" });
    state.selectedImageCatalogId = null;
    imageCatalogManagedActions.hidden = true;
    imageCatalogPreview.hidden = true;
    await loadImageCatalogReferenceSets();
    await loadImageCatalog();
    showAuxResourceMessage(payload.message, "success");
  } catch (error) {
    let detail = null;
    try { detail = JSON.parse(error.message); } catch { /* use ordinary error */ }
    if (!force && detail?.references?.length && window.confirm(`${detail.message}\n\nDelete anyway and leave ${detail.references.length} broken reference(s)?`)) {
      await deleteImageCatalogImage(true);
      return;
    }
    showAuxResourceMessage(detail?.message || error.message, "error");
  }
}

async function saveImageCatalogReferenceSet() {
  const label = imageCatalogSetLabel.value.trim();
  if (!label) {
    showAuxResourceMessage("Reference set label is required.", "error");
    return;
  }
  const selected = imageCatalogSetSelect.value;
  const payload = { label, identity_text: imageCatalogSetIdentity.value, costume_text: imageCatalogSetCostume.value };
  try {
    const result = await fetchJson(selected ? `/api/image-catalog/reference-sets/${encodeURIComponent(selected)}` : "/api/image-catalog/reference-sets", {
      method: selected ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await loadImageCatalogReferenceSets();
    imageCatalogSetSelect.value = result.reference_set.reference_set_id;
    renderSelectedReferenceSet();
    await loadImageCatalog();
    showAuxResourceMessage(result.message, "success");
  } catch (error) {
    showAuxResourceMessage(error.message, "error");
  }
}

async function deleteImageCatalogReferenceSet() {
  const setId = imageCatalogSetSelect.value;
  if (!setId || !window.confirm("Delete this empty reference set?")) return;
  try {
    const payload = await fetchJson(`/api/image-catalog/reference-sets/${encodeURIComponent(setId)}`, { method: "DELETE" });
    imageCatalogSetSelect.value = "";
    await loadImageCatalogReferenceSets();
    showAuxResourceMessage(payload.message, "success");
  } catch (error) {
    showAuxResourceMessage(error.message, "error");
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
    if (isRequestCancellation(error)) return;
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
  clearPromptReview();
  promptReviewStatus.textContent = "Loading prompt reviews...";
  const payload = await fetchJson(`/api/render-console/tasks?${productionQuery().toString()}`);
  state.promptReviewTasks = payload.tasks || [];
  const taskIds = new Set(state.promptReviewTasks.map((task) => task.ask_id));
  state.selectedPromptReviewAskId =
    preferredAskId || state.selectedPromptReviewAskId || state.promptReviewTasks[0]?.ask_id || null;
  if (state.selectedPromptReviewAskId && !taskIds.has(state.selectedPromptReviewAskId)) {
    state.selectedPromptReviewAskId = state.promptReviewTasks[0]?.ask_id || null;
  }
  renderPromptReviewTaskTable();
  renderPromptAnalysisTaskList();
  promptReviewStatus.textContent = `${state.promptReviewTasks.length} render prompt(s)`;
  if (state.selectedPromptReviewAskId) {
    await selectPromptReviewTask(state.selectedPromptReviewAskId);
  } else {
    clearPromptReview();
  }
  void loadPromptAnalysisTasks();
  void refreshProductionWorkSummary();
}

async function loadPromptAnalysisTasks() {
  const request = ++state.promptAnalysisRequest;
  if (state.workspace !== "story") {
    state.promptAnalysisTasks = [];
    renderPromptAnalysisTaskList();
    return;
  }
  try {
    const analyses = await fetchJson(`/api/prompt-analysis/tasks?${productionQuery().toString()}`);
    if (request !== state.promptAnalysisRequest) return;
    state.promptAnalysisTasks = analyses.tasks || [];
    renderPromptAnalysisTaskList();
  } catch (error) {
    if (isRequestCancellation(error)) return;
    console.error("Unable to load prompt analyses.", error);
  }
}

function renderPromptAnalysisTaskList() {
  promptAnalysisTaskList.replaceChildren();
  if (!state.promptAnalysisTasks.length) {
    promptAnalysisTaskList.textContent = "No running or completed scene analyses.";
    return;
  }
  for (const task of state.promptAnalysisTasks) {
    const row = document.createElement("div");
    row.className = "production-task-item";
    const label = document.createElement("span");
    label.textContent = `${task.story_title || task.story_slug} / ${task.title || task.scene_slug}`;
    const action = document.createElement("button");
    action.type = "button";
    action.textContent = task.pending ? "Analysis running" : "View analysis";
    action.addEventListener("click", () => {
      if (task.pending) {
        void harvestPromptAnalysis(task.story_slug, task.scene_slug, task.render_target_id || "main");
      } else {
        void viewOrRunPromptAnalysis(task.story_slug, task.scene_slug, task.render_target_id || "main");
      }
    });
    row.append(label, action);
    promptAnalysisTaskList.append(row);
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
  const selection = beginSelection("prompt-review");
  state.selectedPromptReviewAskId = askId;
  updateSelectableRows(promptReviewTaskBody, (row) => row.dataset.askId === state.selectedPromptReviewAskId);
  try {
    const detail = await fetchJson(`/api/render-console/tasks/${encodeURIComponent(askId)}?${productionQuery().toString()}`, { signal: selection.controller.signal });
    if (selectionIsCurrent(selection) && state.selectedPromptReviewAskId === askId) renderPromptReview(detail);
  } catch (error) {
    if (!isRequestCancellation(error)) throw error;
  }
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
  promptReviewRenderConsole.disabled = true;
  analyzePromptButton.disabled = true;
  viewPromptAnalysisButton.disabled = true;
  viewPromptAnalysisButton.hidden = false;
  viewPromptAnalysisButton.classList.remove("complete", "pending");
  viewPromptAnalysisButton.title = "View prompt analysis";
  viewPromptAnalysisButton.setAttribute("aria-label", "View prompt analysis");
}

function renderPromptReview(detail) {
  state.promptReviewDetail = detail;
  const task = detail.task;
  const storyLabel = detail.manifest?.story_slug && detail.manifest?.scene_slug
    ? `Story ${task.story_title || detail.manifest.story_slug} / ${task.scene_title || detail.manifest.scene_slug}`
    : "";
  promptReviewTitle.textContent = storyLabel || `Asset ${task.asset_id ?? "unknown"} | ${task.expected_output || task.ask_id}`;
  const fullPromptPath = detail.prompt_path || "";
  promptPath.textContent = compactPath(fullPromptPath) || "No prompt file found.";
  promptPath.title = fullPromptPath;
  renderPromptText();
  copyPromptButton.disabled = !detail.prompt;
  promptReviewRenderConsole.disabled = !task.ask_id;
  analyzePromptButton.disabled = !storyLabel;
  analyzePromptButton.textContent = detail.prompt_analysis?.complete ? "Run analysis again" : (detail.prompt_analysis?.pending ? "Analysis running" : "Run analysis");
  viewPromptAnalysisButton.hidden = Boolean(detail.prompt_analysis?.pending && !detail.prompt_analysis?.complete);
  viewPromptAnalysisButton.disabled = !storyLabel || !detail.prompt_analysis?.complete;
  viewPromptAnalysisButton.classList.toggle("complete", Boolean(detail.prompt_analysis?.complete));
  viewPromptAnalysisButton.classList.toggle("pending", Boolean(detail.prompt_analysis?.pending && !detail.prompt_analysis?.complete));
  const analysisLabel = detail.prompt_analysis?.pending && !detail.prompt_analysis?.complete ? "Analysis running" : "View analysis";
  viewPromptAnalysisButton.textContent = analysisLabel;
  viewPromptAnalysisButton.title = analysisLabel;
  viewPromptAnalysisButton.setAttribute("aria-label", analysisLabel);
  clearSourceInspector();
  updatePromptReviewNavigation();
}

function selectedPromptReviewScene() {
  const manifest = state.promptReviewDetail?.manifest || {};
  return manifest.story_slug && manifest.scene_slug
    ? { storySlug: manifest.story_slug, sceneSlug: manifest.scene_slug, renderTargetId: manifest.render_target_id || "main" }
    : null;
}

async function analyzePromptReview() {
  const scene = selectedPromptReviewScene();
  if (!scene) return;
  if (state.promptReviewDetail?.prompt_analysis?.pending) {
    await harvestPromptAnalysis(scene.storySlug, scene.sceneSlug, scene.renderTargetId);
    return;
  }
  analyzePromptButton.disabled = true;
  showPromptMessage("Queuing prompt analysis...");
  try {
    const analysis = await fetchJson(`/api/stories/${encodeURIComponent(scene.storySlug)}/scenes/${encodeURIComponent(scene.sceneSlug)}/prompt-analysis?render_target_id=${encodeURIComponent(scene.renderTargetId)}`, { method: "POST" });
    state.promptReviewDetail.prompt_analysis = analysis;
    renderPromptReview(state.promptReviewDetail);
    showPromptMessage(analysis.message || "AI prompt analysis queued.", "success");
  } catch (error) {
    showPromptMessage(error.message, "error");
  } finally {
    if (state.promptReviewDetail) renderPromptReview(state.promptReviewDetail);
  }
}

async function harvestPromptAnalysis(storySlug, sceneSlug, renderTargetId = "main") {
  analyzePromptButton.disabled = true;
  showPromptMessage("Checking for a completed prompt analysis...");
  try {
    const analysis = await fetchJson(`/api/stories/${encodeURIComponent(storySlug)}/scenes/${encodeURIComponent(sceneSlug)}/prompt-analysis/harvest?render_target_id=${encodeURIComponent(renderTargetId)}`, { method: "POST" });
    const selected = selectedPromptReviewScene();
    if (selected && selected.storySlug === storySlug && selected.sceneSlug === sceneSlug && selected.renderTargetId === renderTargetId) {
      state.promptReviewDetail.prompt_analysis = analysis;
      renderPromptReview(state.promptReviewDetail);
    }
    await loadPromptAnalysisTasks();
    if (analysis.complete && analysis.result_path) {
      showPromptMessage("Prompt analysis is ready.", "success");
      openPromptAnalysisDialog(storySlug, sceneSlug, renderTargetId);
    } else {
      showPromptMessage(analysis.error || "Analysis is still running. Check again after the AI worker finishes.", analysis.error ? "error" : "info");
    }
    return analysis;
  } catch (error) {
    showPromptMessage(error.message, "error");
    return null;
  } finally {
    if (state.promptReviewDetail) renderPromptReview(state.promptReviewDetail);
  }
}

async function viewPromptReviewAnalysis() {
  const scene = selectedPromptReviewScene();
  if (!scene) return;
  await viewOrRunPromptAnalysis(scene.storySlug, scene.sceneSlug, scene.renderTargetId);
}

function compactPath(value) {
  const fullPath = String(value || "");
  if (!fullPath) return "";
  const parts = fullPath.split(/[\\/]+/).filter(Boolean);
  return parts.slice(-2).join(" / ") || fullPath;
}

function promptAnalysisViewUrl(storySlug, sceneSlug, renderTargetId = "main") {
  return `/api/stories/${encodeURIComponent(storySlug)}/scenes/${encodeURIComponent(sceneSlug)}/prompt-analysis/view?render_target_id=${encodeURIComponent(renderTargetId)}`;
}

function recordPromptAnalysisStatus(storySlug, sceneSlug, renderTargetId, analysis) {
  if (state.selectedStorySlug === storySlug && state.selectedSceneSlug === sceneSlug
      && state.activeBuilderRenderTarget === renderTargetId) {
    state.scenePromptAnalysis = analysis;
    if (state.sceneBuilderOpen) updateBuilderAnalysisActions();
  }
  const selected = selectedPromptReviewScene();
  if (selected && selected.storySlug === storySlug && selected.sceneSlug === sceneSlug
      && selected.renderTargetId === renderTargetId && state.promptReviewDetail) {
    state.promptReviewDetail.prompt_analysis = analysis;
    renderPromptReview(state.promptReviewDetail);
  }
}

async function viewOrRunPromptAnalysis(storySlug, sceneSlug, renderTargetId = "main") {
  try {
    let analysis = await fetchJson(`/api/stories/${encodeURIComponent(storySlug)}/scenes/${encodeURIComponent(sceneSlug)}/prompt-analysis?render_target_id=${encodeURIComponent(renderTargetId)}`);
    recordPromptAnalysisStatus(storySlug, sceneSlug, renderTargetId, analysis);
    if (analysis.complete && analysis.result_path) {
      openPromptAnalysisDialog(storySlug, sceneSlug, renderTargetId);
      return analysis;
    }
    if (analysis.pending) {
      analysis = await fetchJson(`/api/stories/${encodeURIComponent(storySlug)}/scenes/${encodeURIComponent(sceneSlug)}/prompt-analysis/harvest?render_target_id=${encodeURIComponent(renderTargetId)}`, { method: "POST" });
    } else {
      analysis = await fetchJson(`/api/stories/${encodeURIComponent(storySlug)}/scenes/${encodeURIComponent(sceneSlug)}/prompt-analysis?render_target_id=${encodeURIComponent(renderTargetId)}`, { method: "POST" });
    }
    recordPromptAnalysisStatus(storySlug, sceneSlug, renderTargetId, analysis);
    if (analysis.complete && analysis.result_path) {
      showPromptMessage("Prompt analysis is ready.", "success");
      openPromptAnalysisDialog(storySlug, sceneSlug, renderTargetId);
    } else {
      showPromptMessage(analysis.message || analysis.error || "AI prompt analysis queued.", analysis.error ? "error" : "success");
    }
    return analysis;
  } catch (error) {
    showPromptMessage(error.message, "error");
    return null;
  }
}

function showPromptAnalysisActionMessage(message, type = "info") {
  promptAnalysisActionMessage.textContent = message || "";
  promptAnalysisActionMessage.className = `action-message ${type}`;
  promptAnalysisActionMessage.hidden = !message;
}

function openPromptAnalysisDialog(storySlug, sceneSlug, renderTargetId = "main") {
  state.promptAnalysisDialogContext = { storySlug, sceneSlug, renderTargetId, secondOpinionPending: false };
  promptAnalysisSecondOpinion.textContent = "2nd Opinion";
  promptAnalysisSecondOpinion.disabled = false;
  showPromptAnalysisActionMessage("");
  promptAnalysisFrame.src = promptAnalysisViewUrl(storySlug, sceneSlug, renderTargetId);
  promptAnalysisDialog.showModal();
}

async function runPromptAnalysisSecondOpinion() {
  const context = state.promptAnalysisDialogContext;
  if (!context) return;
  promptAnalysisSecondOpinion.disabled = true;
  showPromptAnalysisActionMessage(
    context.secondOpinionPending ? "Checking the second opinion..." : "Queuing a second opinion..."
  );
  try {
    const endpoint = context.secondOpinionPending ? "harvest" : "second-opinion";
    const analysis = await fetchJson(
      `/api/stories/${encodeURIComponent(context.storySlug)}/scenes/${encodeURIComponent(context.sceneSlug)}/prompt-analysis/${endpoint}?render_target_id=${encodeURIComponent(context.renderTargetId)}`,
      { method: "POST" },
    );
    recordPromptAnalysisStatus(context.storySlug, context.sceneSlug, context.renderTargetId, analysis);
    if (analysis.complete && analysis.result_path) {
      context.secondOpinionPending = false;
      promptAnalysisFrame.src = `${promptAnalysisViewUrl(context.storySlug, context.sceneSlug, context.renderTargetId)}&refresh=${Date.now()}`;
      promptAnalysisSecondOpinion.textContent = "2nd Opinion";
      showPromptAnalysisActionMessage("Second opinion added.", "success");
    } else {
      context.secondOpinionPending = true;
      promptAnalysisSecondOpinion.textContent = "Check 2nd Opinion";
      showPromptAnalysisActionMessage(analysis.message || analysis.error || "Second opinion is running.", analysis.error ? "error" : "success");
    }
  } catch (error) {
    showPromptAnalysisActionMessage(error.message, "error");
  } finally {
    promptAnalysisSecondOpinion.disabled = false;
  }
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
    await activatePage("scene-builder", { skipAutosave: true, renderTargetId: manifest.render_target_id || "main" });
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
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("Clipboard access is unavailable.");
}

async function copyText(value, label = "Copied.") {
  await writeClipboardText(value);
  showPromptMessage(label);
}

async function loadRenderReviewTasks(preferredReviewKey = null) {
  renderReviewStatus.textContent = "Loading render reviews...";
  const payload = await fetchJson(`/api/render-review/tasks?${productionQuery().toString()}`);
  state.renderReviewTasks = payload.items || [];
  const taskKeys = new Set(state.renderReviewTasks.map((task) => task.review_key));
  state.selectedRenderReviewKey =
    preferredReviewKey || state.selectedRenderReviewKey || state.renderReviewTasks[0]?.review_key || null;
  if (state.selectedRenderReviewKey && !taskKeys.has(state.selectedRenderReviewKey)) {
    state.selectedRenderReviewKey = state.renderReviewTasks[0]?.review_key || null;
  }
  renderRenderReviewTaskTable();
  renderReviewStatus.textContent = `${state.renderReviewTasks.length} image(s) waiting`;
  if (state.selectedRenderReviewKey) {
    await selectRenderReview(state.selectedRenderReviewKey);
  } else {
    clearRenderReview();
  }
  refreshProductionWorkSummary();
}

function renderRenderReviewTaskTable() {
  renderReviewTaskBody.replaceChildren();
  if (!state.renderReviewTasks.length) {
    renderEmptyRow(renderReviewTaskBody, 1, "No render candidates are waiting. Complete a render to create review work.");
    return;
  }
  for (const task of state.renderReviewTasks) {
    const row = document.createElement("tr");
    row.dataset.reviewKey = task.review_key;
    row.classList.toggle("selected", task.review_key === state.selectedRenderReviewKey);
    const isScene = task.review_kind === "scene";
    const label = isScene ? `${task.title || task.scene_slug}${task.render_target_id && task.render_target_id !== "main" ? ` / ${task.render_target_label || task.render_target_id}` : ""}` : task.asset_id;
    const cell = document.createElement("td");
    const title = document.createElement("span");
    title.className = "review-task-title";
    title.textContent = label ?? "";
    const meta = document.createElement("span");
    meta.className = "review-task-meta";
    meta.textContent = `${isScene ? "Scene" : (task.body_view || "Asset")} · Candidate ready`;
    cell.append(title, meta);
    row.append(cell);
    makeSelectableRow(row, isScene ? `Scene ${label}` : `Asset ${task.asset_id}`, task.review_key === state.selectedRenderReviewKey, () => selectRenderReview(task.review_key));
    renderReviewTaskBody.append(row);
  }
}

function selectedRenderReviewTask() {
  return state.renderReviewTasks.find((task) => task.review_key === state.selectedRenderReviewKey) || null;
}

function renderReviewEndpoint(task, action = "") {
  const suffix = action ? `/${action}` : "";
  if (task.review_kind === "scene") {
    const targetSegment = task.render_target_id && task.render_target_id !== "main"
      ? `/targets/${encodeURIComponent(task.render_target_id)}`
      : "";
    return `/api/render-review/scenes/${encodeURIComponent(task.story_slug)}/${encodeURIComponent(task.scene_slug)}${targetSegment}${suffix}`;
  }
  const params = new URLSearchParams({ character: task.character, phase: task.phase });
  return `/api/render-review/${task.asset_id}${suffix}?${params.toString()}`;
}

async function selectRenderReview(reviewKey) {
  const selection = beginSelection("render-review");
  state.selectedRenderReviewKey = reviewKey;
  updateSelectableRows(renderReviewTaskBody, (row) => row.dataset.reviewKey === state.selectedRenderReviewKey);
  const task = selectedRenderReviewTask();
  if (!task) return;
  try {
    const detail = await fetchJson(renderReviewEndpoint(task), { signal: selection.controller.signal });
    if (selectionIsCurrent(selection) && state.selectedRenderReviewKey === reviewKey) renderRenderReview(detail);
  } catch (error) {
    if (!isRequestCancellation(error)) throw error;
  }
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
  renderDiscardCandidateButton.disabled = true;
  renderDiscardCandidateButton.hidden = false;
  renderFailRenderButton.disabled = true;
  renderFailRegenerateButton.disabled = true;
  renderFailRenderButton.textContent = "Fail to RENDER";
  renderFailRegenerateButton.hidden = false;
  renderStageText.closest("section").hidden = false;
  renderHistoryText.closest("section").hidden = false;
}

function renderRenderReview(detail) {
  state.renderReviewDetail = detail;
  const isScene = detail.review_kind === "scene";
  const asset = detail.asset || {};
  renderReviewTitle.textContent = isScene
    ? `${detail.title || detail.scene_slug} | ${detail.story_slug}${detail.render_target_id !== "main" ? ` | ${detail.render_target_label}` : ""}`
    : `Asset ${asset.asset_id} | ${asset.body_view}`;
  const fullCandidatePath = detail.candidate_image_path || "";
  renderReviewPath.textContent = compactPath(fullCandidatePath);
  renderReviewPath.title = fullCandidatePath;
  renderReviewComment.value = detail.render_review_comment || "";
  renderStageText.textContent = detail.stage_text || "No stage marker found.";
  renderHistoryText.textContent = detail.history_text || "No history found.";
  renderCandidateImage(detail);
  renderLockedImage(detail);
  const candidateExists = isScene ? detail.candidate_exists : detail.exists?.candidate_image;
  renderPromoteButton.disabled = !detail.is_reviewable || !candidateExists;
  renderDiscardCandidateButton.disabled = !detail.is_reviewable || !candidateExists || !detail.exists?.locked_image;
  renderDiscardCandidateButton.hidden = isScene;
  renderFailRenderButton.disabled = !detail.is_reviewable;
  renderFailRegenerateButton.disabled = !detail.is_reviewable;
  renderFailRenderButton.textContent = isScene ? "Discard Candidate" : "Fail to RENDER";
  renderFailRegenerateButton.hidden = isScene;
  renderStageText.closest("section").hidden = isScene;
  renderHistoryText.closest("section").hidden = isScene;
  renderCommentSave.disabled = !detail.is_reviewable;
  updateRenderReviewNavigation();
}

async function saveRenderReviewComment() {
  const task = selectedRenderReviewTask();
  if (!task) return;
  renderCommentSave.disabled = true;
  showRenderMessage("Saving comment...");
  try {
    const payload = await fetchJson(
      renderReviewEndpoint(task, "comment"),
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
  const isScene = detail.review_kind === "scene";
  renderReviewImage(
    candidateRender,
    detail.candidate_image_path,
    isScene ? detail.candidate_exists : detail.exists?.candidate_image,
    "No candidate image.",
    "Candidate render",
    detail.asset?.updated_at || "",
  );
}

function renderLockedImage(detail) {
  const isScene = detail.review_kind === "scene";
  renderReviewImage(
    lockedRender,
    detail.locked_image_path,
    isScene ? detail.locked_exists : detail.exists?.locked_image,
    "No locked image.",
    "Locked render",
    detail.asset?.updated_at || "",
  );
}

function updateRenderReviewNavigation() {
  const index = state.renderReviewTasks.findIndex((task) => task.review_key === state.selectedRenderReviewKey);
  renderReviewPrev.disabled = index <= 0;
  renderReviewNext.disabled = index < 0 || index >= state.renderReviewTasks.length - 1;
}

async function runRenderReviewAction(action) {
  const task = selectedRenderReviewTask();
  if (!task) return;
  const resolvedAction = task.review_kind === "scene" ? "discard-candidate" : action;
  const itemLabel = task.review_kind === "scene"
    ? `${task.title || task.scene_slug}`
    : `Asset ${task.asset_id}`;
  const labels = {
    "discard-candidate": ["Discard candidate", `Discard the candidate image for ${itemLabel}?`, "Discard Candidate"],
    "fail-to-render": ["Fail to RENDER", `Fail ${itemLabel} back to RENDER?`, "Fail to RENDER"],
    "fail-to-regenerate": ["Fail to REGENERATE", `Fail ${itemLabel} back to REGENERATE?`, "Fail to REGENERATE"],
  };
  const confirmation = labels[resolvedAction];
  if (confirmation && !await confirmAction(...confirmation)) return;
  showRenderMessage("Working...");
  try {
    const payload = await fetchJson(
      renderReviewEndpoint(task, resolvedAction),
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
  const task = selectedRenderReviewTask();
  if (!task) return;
  const replacingLockedImage = task.review_kind === "asset" && Boolean(state.renderReviewDetail?.exists?.locked_image);
  let endpoint = renderReviewEndpoint(task, "promote-to-locked");
  if (replacingLockedImage) {
    const confirmed = window.confirm("A locked image already exists for this asset. Replace it with the candidate image?");
    if (!confirmed) {
      return;
    }
    endpoint += "&replace_existing=true";
  }
  showRenderMessage("Working...");
  try {
    const payload = await fetchJson(
      endpoint,
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
  tbody.closest("table")?.classList.add("responsive-list-table");
  if (!rows || rows.length === 0) {
    renderEmptyRow(tbody, Math.max(1, columns.length), "No items.");
    return;
  }
  for (const item of rows) {
    const row = document.createElement("tr");
    for (const column of columns) {
      const cell = document.createElement("td");
      cell.dataset.label = humanizeHeading(column);
      const value = item[column] ?? "";
      if (/(?:^|_)(?:created|updated|responded|harvested)_at$/.test(column) && value !== "") {
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
  const status = activePageName() === "local-image-config" ? localImageConfigStatus : aiControlsStatus;
  status.textContent = "Loading processes and queues...";
  const payload = await fetchJson("/api/ai-controls");
  renderAiControls(payload);
  if (activePageName() === "ai-controls") {
    try {
      await loadRecentAiHarvests();
    } catch (error) {
      showAiControlsMessage(`Queue loaded, but recent history could not be loaded: ${error.message}`, "error");
    }
  }
}

function renderAiControls(payload) {
  state.aiControls = payload;
  const counts = payload.queue_counts || {};
  queueCounts.textContent =
    `Ask: ${counts.ask || 0} | Running: ${counts.running || 0} | Answer: ${counts.answer || 0}`;
  renderRows(queueAskTableBody, payload.queue?.ask || [], ["ask_id", "asset_id", "pipeline_stage", "worker_type", "task_type"]);
  renderRows(queueRunningTableBody, payload.queue?.running || [], ["ask_id", "asset_id", "worker_type", "task_type"]);
  renderRows(queueAnswerTableBody, payload.queue?.answer || [], ["ask_id", "asset_id", "status", "worker_id", "recovery"]);
  const codexJobs = payload.codex_jobs || [];
  const codexCounts = Object.fromEntries(["PENDING", "RUNNING", "COMPLETE", "FAILED"].map(
    (status) => [status, codexJobs.filter((job) => job.status === status).length]
  ));
  document.querySelector("#codex-job-counts").textContent =
    `Pending: ${codexCounts.PENDING} | Running: ${codexCounts.RUNNING} | Done: ${codexCounts.COMPLETE} | Failed: ${codexCounts.FAILED}`;
  renderRows(document.querySelector("#codex-jobs-table tbody"), codexJobs,
    ["run_id", "candidate_id", "character", "view", "status", "details"]);
  renderRows(manualRenderTableBody, payload.manual_render_asks || [], ["ask_id", "asset_id", "pipeline_stage", "task_type"]);
  manualRenderCount.textContent = `${(payload.manual_render_asks || []).length} manual render task(s) waiting`;
  renderProcessRows(payload.processes || []);
  aiControlsStatus.textContent = "Ready";
  if (activePageName() === "local-image-config") localImageConfigStatus.textContent = "Ready";
}

async function loadRecentAiHarvests() {
  const payload = await fetchJson("/api/ai-controls/recent-harvests");
  const rows = payload.items || [];
  renderRows(recentHarvestTableBody, rows, ["harvested_at", "ask_id", "task_type", "asset_id", "status", "details"]);
  recentHarvestCount.textContent = `${rows.length} recent harvested job(s)`;
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
  const showMessage = activePageName() === "local-image-config" ? showLocalImageConfigMessage : showAiControlsMessage;
  showMessage("Working...");
  try {
    const payload = await fetchJson(url, { method: "POST" });
    renderAiControls(payload);
    showMessage(payload.message || "Action complete.");
  } catch (error) {
    showMessage(error.message, "error");
  }
}

function selectedPipelineInspectionFile() {
  return state.pipelineInspectionFiles.find((item) => item.file_id === state.selectedPipelineInspectionFileId) || null;
}

function pipelineInspectionParams(fileId = "") {
  const params = new URLSearchParams({ pipeline_id: state.selectedPipelineInspectionId || "" });
  if (fileId) params.set("file_id", fileId);
  return params;
}

function flattenPipelineInspections(nodes = state.pipelineInspections) {
  return nodes.flatMap((node) => [node, ...flattenPipelineInspections(node.children || [])]);
}

function pipelineInspectionNodeMatches(node, search) {
  return !search
    || node.label.toLowerCase().includes(search)
    || (node.children || []).some((child) => pipelineInspectionNodeMatches(child, search));
}

function pipelineInspectionNodeContains(node, pipelineId) {
  return node.pipeline_id === pipelineId
    || (node.children || []).some((child) => pipelineInspectionNodeContains(child, pipelineId));
}

function appendPipelineInspectionNodes(nodes, container, search, ancestorMatches = false) {
  for (const item of nodes) {
    const selfMatches = ancestorMatches || !search || item.label.toLowerCase().includes(search);
    if (!selfMatches && !pipelineInspectionNodeMatches(item, search)) continue;
    if (item.children?.length) {
      const details = document.createElement("details");
      details.className = "inspection-tree-node";
      details.open = Boolean(search) || pipelineInspectionNodeContains(item, state.selectedPipelineInspectionId);
      const summary = document.createElement("summary");
      summary.textContent = item.label;
      const children = document.createElement("div");
      children.className = "inspection-tree-children";
      appendPipelineInspectionNodes(item.children, children, search, selfMatches);
      details.append(summary, children);
      container.append(details);
      continue;
    }
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = item.label;
    button.title = item.path || "";
    if (item.pipeline_id === state.selectedPipelineInspectionId) button.setAttribute("aria-current", "true");
    button.addEventListener("click", () => selectPipelineInspection(item.pipeline_id));
    container.append(button);
  }
}

function renderPipelineInspectionList() {
  const search = pipelineInspectionSearch.value.trim().toLowerCase();
  pipelineInspectionList.replaceChildren();
  appendPipelineInspectionNodes(state.pipelineInspections, pipelineInspectionList, search);
  if (!pipelineInspectionList.children.length) pipelineInspectionList.textContent = "No matching pipelines.";
}

function clearPipelineInspectionPreview(message = "Select a file to preview its contents.") {
  state.selectedPipelineInspectionFileId = null;
  state.pipelineInspectionContent = "";
  pipelineInspectionPath.textContent = "Select a file to inspect.";
  pipelineInspectionText.hidden = true;
  pipelineInspectionText.textContent = "";
  pipelineInspectionImage.hidden = true;
  pipelineInspectionImage.removeAttribute("src");
  pipelineInspectionEmpty.hidden = false;
  pipelineInspectionEmpty.textContent = message;
  pipelineInspectionCopy.disabled = true;
  pipelineInspectionOpenFolder.disabled = true;
}

function renderPipelineInspectionFiles() {
  pipelineInspectionFiles.replaceChildren();
  for (const item of state.pipelineInspectionFiles) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = item.file_id;
    button.title = item.path;
    if (item.file_id === state.selectedPipelineInspectionFileId) button.setAttribute("aria-current", "true");
    button.addEventListener("click", () => selectPipelineInspectionFile(item.file_id));
    pipelineInspectionFiles.append(button);
  }
  if (!state.pipelineInspectionFiles.length) pipelineInspectionFiles.textContent = "This pipeline has no files.";
}

async function loadPipelineInspections() {
  pipelineInspectionStatus.textContent = "Loading pipelines...";
  try {
    const payload = await fetchJson("/api/pipeline-inspection");
    state.pipelineInspections = payload.pipelines || [];
    if (!flattenPipelineInspections().some((item) => item.pipeline_id === state.selectedPipelineInspectionId)) {
      state.selectedPipelineInspectionId = null;
    }
    renderPipelineInspectionList();
    pipelineInspectionStatus.textContent = `${state.pipelineInspections.length} pipeline(s)`;
    if (state.selectedPipelineInspectionId) await selectPipelineInspection(state.selectedPipelineInspectionId);
  } catch (error) {
    if (isRequestCancellation(error)) return;
    pipelineInspectionStatus.textContent = "Unable to load pipelines";
    showMessageElement(pipelineInspectionMessage, error.message, "error");
  }
}

async function selectPipelineInspection(pipelineId) {
  state.selectedPipelineInspectionId = pipelineId;
  state.pipelineInspectionFiles = [];
  renderPipelineInspectionList();
  renderPipelineInspectionFiles();
  clearPipelineInspectionPreview("Select a file to preview its contents.");
  const pipeline = flattenPipelineInspections().find((item) => item.pipeline_id === pipelineId);
  pipelineInspectionFilesTitle.textContent = pipeline?.label || "Files";
  try {
    const payload = await fetchJson(`/api/pipeline-inspection/files?${pipelineInspectionParams().toString()}`);
    if (state.selectedPipelineInspectionId !== pipelineId) return;
    state.pipelineInspectionFiles = payload.files || [];
    renderPipelineInspectionFiles();
  } catch (error) {
    showMessageElement(pipelineInspectionMessage, error.message, "error");
  }
}

async function selectPipelineInspectionFile(fileId) {
  state.selectedPipelineInspectionFileId = fileId;
  state.pipelineInspectionContent = "";
  renderPipelineInspectionFiles();
  const file = selectedPipelineInspectionFile();
  if (!file) return;
  pipelineInspectionPath.textContent = file.path;
  pipelineInspectionOpenFolder.disabled = false;
  pipelineInspectionText.hidden = true;
  pipelineInspectionImage.hidden = true;
  pipelineInspectionEmpty.hidden = true;
  pipelineInspectionCopy.disabled = file.kind === "other";
  const params = pipelineInspectionParams(file.file_id);
  try {
    if (file.kind === "text") {
      const payload = await fetchJson(`/api/pipeline-inspection/text?${params.toString()}`);
      if (state.selectedPipelineInspectionId !== params.get("pipeline_id") || state.selectedPipelineInspectionFileId !== fileId) return;
      state.pipelineInspectionContent = payload.content || "";
      pipelineInspectionText.textContent = state.pipelineInspectionContent;
      pipelineInspectionText.hidden = false;
    } else if (file.kind === "image") {
      pipelineInspectionImage.src = `/api/pipeline-inspection/file?${params.toString()}`;
      pipelineInspectionImage.hidden = false;
    } else {
      pipelineInspectionEmpty.textContent = "Preview is available for Markdown, JSON, TXT, LOG, and image files.";
      pipelineInspectionEmpty.hidden = false;
    }
  } catch (error) {
    showMessageElement(pipelineInspectionMessage, error.message, "error");
  }
}

async function copyPipelineInspectionFile() {
  const file = selectedPipelineInspectionFile();
  if (!file) return;
  try {
    if (file.kind === "text") {
      await writeClipboardText(state.pipelineInspectionContent);
    } else if (file.kind === "image") {
      await pipelineInspectionImage.decode();
      const canvas = document.createElement("canvas");
      canvas.width = pipelineInspectionImage.naturalWidth;
      canvas.height = pipelineInspectionImage.naturalHeight;
      canvas.getContext("2d").drawImage(pipelineInspectionImage, 0, 0);
      const blob = await canvasBlob(canvas);
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
    }
    showMessageElement(pipelineInspectionMessage, "File contents copied.", "success");
  } catch (error) {
    showMessageElement(pipelineInspectionMessage, `Unable to copy file: ${error.message}`, "error");
  }
}

async function openPipelineInspectionFolder() {
  const file = selectedPipelineInspectionFile();
  if (!file) return;
  try {
    const payload = await fetchJson(
      `/api/pipeline-inspection/open-folder?${pipelineInspectionParams(file.file_id).toString()}`,
      { method: "POST" },
    );
    showMessageElement(pipelineInspectionMessage, `Opened ${payload.path}.`, "success");
  } catch (error) {
    showMessageElement(pipelineInspectionMessage, error.message, "error");
  }
}

async function loadPipelineControls() {
  pipelineControlsStatus.textContent = "Loading pipeline controls...";
  const params = activePageName() === "local-image-config" ? new URLSearchParams() : currentQuery();
  const payload = await fetchJson(`/api/pipeline-controls?${params.toString()}`);
  renderPipelineControls(payload);
}

function renderPipelineControls(payload) {
  state.pipelineControls = payload;
  const automation = payload.automation || {};
  const profiles = payload.render_profiles || {};
  const comfyProfile = automation.comfyui_profile || "comfyui-qwen-image-2-1-scene";
  setSelectOptions(settingComfyuiProfile, profiles.comfyui?.length ? profiles.comfyui : [comfyProfile]);
  settingLocalRenderBackend.value = "comfyui";
  settingComfyuiProfile.value = comfyProfile;
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
  settingAiPromptAnalysisAutoQueueOnRender.checked = Boolean(automation.ai_prompt_analysis_auto_queue_on_render);
  setOllamaModelValue(settingAiAssetWorkflowModel, automation.ai_asset_workflow_model || "");
  setCodexDefaultModelValue(settingCodexDefaultModel, automation.codex_default_model || "gpt-6-luna");
  setOllamaModelValue(settingPromptCondenseModel, automation.prompt_condense_model || "");
  setOllamaModelValue(settingAiPromptAnalysisModel, automation.ai_prompt_analysis_model || "");
  setOllamaModelValue(settingAiImageDescriptionModel, automation.ai_image_description_model || "");
  setOllamaModelValue(settingImagePromptGenerationModel, automation.ai_image_prompt_generation_model || "image-analysis:latest");
  setOllamaModelValue(settingCostumeWizardModel, automation.ai_costume_wizard_model || "codex:gpt-6-luna");
  setOllamaModelValue(settingQuickCharacterWizardModel, automation.ai_quick_character_wizard_model || "codex:gpt-6-luna");
  setOllamaModelValue(settingLocalBodyReferenceFaceGateModel, automation.local_body_reference_face_gate_model || "");
  setOllamaModelValue(settingLocalBodyReferenceReviewModel, automation.local_body_reference_review_model || "");
  settingAiPromptAnalysisFile.value = automation.ai_prompt_analysis_instructions_file || "";
  renderManagedLlmRoles(payload.managed_llm_roles || []);
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



function renderManagedLlmRoles(roles = []) {
  const byKey = new Map(roles.map((role) => [role.key, role]));
  for (const container of document.querySelectorAll("[data-llm-role]")) {
    const role = byKey.get(container.dataset.llmRole) || {};
    const description = container.querySelector(".managed-llm-description");
    const templates = container.querySelector(".managed-llm-templates");
    description.textContent = role.description || "";
    templates.replaceChildren();
    if (!(role.templates || []).length) {
      const note = document.createElement("span");
      note.className = "managed-llm-no-template";
      note.textContent = "Prompt assembled by the task; no reusable Markdown template.";
      templates.append(note);
      continue;
    }
    for (const template of role.templates) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `Edit ${template.label}`;
      button.title = template.path;
      button.addEventListener("click", () => {
        const sourcePath = role.key === "prompt_analysis"
          ? settingAiPromptAnalysisFile.value
          : template.path;
        openSourceEditorForSource({
          source_kind: "config_prompt_template",
          source_path: sourcePath,
          source_label: template.label,
          editable: true,
        }, showLocalImageConfigMessage);
      });
      const path = document.createElement("span");
      path.className = "managed-llm-template-path";
      path.textContent = template.display_path || template.path;
      templates.append(button, path);
    }
  }
}

function setCodexDefaultModelValue(control, value) {
  const model = value || "gpt-6-luna";
  if (model && !Array.from(control.options).some((option) => option.value === model)) {
    control.add(new Option(`${model} (saved configuration)`, model));
  }
  control.value = model;
}

function setOllamaModelValue(control, value) {
  const model = value || "";
  if (model && !Array.from(control.options).some((option) => option.value === model)) {
    control.add(new Option(model, model));
  }
  control.value = model;
}

async function refreshOllamaModelOptions(refresh = false) {
  const current = new Map(ollamaModelControls().map((control) => [control, control.value]));
  const addCodexPromptModels = (control) => {
    for (const model of ["gpt-6-luna", "gpt-6-sol", "gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra"]) {
      if (!Array.from(control.options).some((option) => option.value === "codex:" + model)) {
        control.add(new Option("Codex · " + model, "codex:" + model));
      }
    }
  };
  try {
    const payload = await fetchJson(refresh
      ? "/api/ai-controls/ollama-models/refresh"
      : "/api/ai-controls/ollama-models", { method: refresh ? "POST" : "GET" });
    for (const control of ollamaModelControls()) {
      setSelectOptions(control, control === settingImagePromptGenerationModel
        ? (payload.vision_models || []) : (payload.models || []));
      if ([settingImagePromptGenerationModel, settingCostumeWizardModel, settingQuickCharacterWizardModel].includes(control)) addCodexPromptModels(control);
      setOllamaModelValue(control, current.get(control));
    }
    const showMessage = activePageName() === "local-image-config" ? showLocalImageConfigMessage : showAiControlsMessage;
    showMessage(
      `Loaded ${(payload.models || []).length} Ollama model(s); ${(payload.vision_models || []).length} report vision capability.`,
    );
  } catch (error) {
    addCodexPromptModels(settingImagePromptGenerationModel);
    addCodexPromptModels(settingCostumeWizardModel);
    addCodexPromptModels(settingQuickCharacterWizardModel);
    setOllamaModelValue(settingImagePromptGenerationModel, current.get(settingImagePromptGenerationModel));
    setOllamaModelValue(settingCostumeWizardModel, current.get(settingCostumeWizardModel));
    setOllamaModelValue(settingQuickCharacterWizardModel, current.get(settingQuickCharacterWizardModel));
    const showMessage = activePageName() === "local-image-config" ? showLocalImageConfigMessage : showAiControlsMessage;
    showMessage(error.message, "error");
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
  stableMatrixSettings.hidden = true;
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
  showLocalImageConfigMessage("Refreshing ComfyUI models...");
  try {
    const params = new URLSearchParams({
      preset: settingComfyuiProfile.value || "comfyui-qwen-image-2-1-scene",
      backend: "comfyui",
    });
    const payload = await fetchJson(`/api/local-image/checkpoints?${params.toString()}`);
    const items = [{ value: "", label: "" }, ...(payload.checkpoints || []).map((item) => ({ value: item.title, label: item.title }))];
    setSelectOptionsWithLabels(settingComfyuiCheckpoint, items);
    const available = (payload.checkpoints || []).map((item) => item.title);
    const selected = settingComfyuiProfile.value === "comfyui-qwen-image-2-1-scene" && !available.includes(current)
      ? (available.includes(payload.default_model) ? payload.default_model : (available[0] || ""))
      : current;
    setComfyuiCheckpointValue(selected);
    showLocalImageConfigMessage(`Loaded ${(payload.checkpoints || []).length} ComfyUI models.`);
  } catch (error) {
    showLocalImageConfigMessage(error.message, "error");
  }
}

function automationPayloadFromForm() {
  return {
    local_render_backend: settingLocalRenderBackend.value,
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
    ai_prompt_analysis_auto_queue_on_render: settingAiPromptAnalysisAutoQueueOnRender.checked,
    ai_asset_workflow_model: settingAiAssetWorkflowModel.value,
    codex_default_model: settingCodexDefaultModel.value.trim(),
    prompt_condense_model: settingPromptCondenseModel.value,
    ai_prompt_analysis_model: settingAiPromptAnalysisModel.value,
    ai_image_description_model: settingAiImageDescriptionModel.value,
    ai_image_prompt_generation_model: settingImagePromptGenerationModel.value,
    ai_costume_wizard_model: settingCostumeWizardModel.value,
    ai_quick_character_wizard_model: settingQuickCharacterWizardModel.value,
    local_body_reference_face_gate_model: settingLocalBodyReferenceFaceGateModel.value,
    local_body_reference_review_model: settingLocalBodyReferenceReviewModel.value,
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
    const params = activePageName() === "local-image-config" ? new URLSearchParams() : currentQuery();
    const payload = await fetchJson(`/api/pipeline-controls/automation?${params.toString()}`, {
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
  renderConsoleReviewPrompt.disabled = true;
  renderConsoleSaveImage.disabled = true;
  renderConsoleFailTask.disabled = true;
  renderConsoleStatus.textContent = "Loading render tasks...";
  const [payload, metrics] = await Promise.all([
    fetchJson(`/api/render-console/tasks?${productionQuery().toString()}`),
    fetchJson("/api/render-console/refinement-metrics").catch(() => null),
  ]);
  renderRenderConsoleRefinementMetrics(metrics);
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
  refreshProductionWorkSummary();
}

async function loadRenderConsolePublications() {
  renderConsolePublications.textContent = "Inspecting publication bundles...";
  try {
    const payload = await fetchJson("/api/render-console/publications");
    renderConsolePublications.replaceChildren();
    const items = payload.publications || [];
    if (!items.length) {
      renderConsolePublications.textContent = "No durable publication intents or staging bundles found.";
      return;
    }
    for (const item of items) {
      const row = document.createElement("div");
      row.className = "publication-recovery-row";
      const summary = document.createElement("span");
      summary.textContent = `${item.ask_id}: ${item.status}${item.errors?.length ? ` — ${item.errors.join("; ")}` : ""}`;
      row.append(summary);
      if (item.recoverable) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = "Recover";
        button.addEventListener("click", async () => {
          button.disabled = true;
          try {
            const result = await fetchJson(
              `/api/render-console/publications/${encodeURIComponent(item.ask_id)}/recover`,
              { method: "POST" },
            );
            showRenderConsoleMessage(result.message || "Publication recovered.");
            await loadRenderConsoleTasks(item.ask_id);
            await loadRenderConsolePublications();
          } catch (error) {
            showRenderConsoleMessage(error.message, "error");
            button.disabled = false;
          }
        });
        row.append(button);
      }
      renderConsolePublications.append(row);
    }
  } catch (error) {
    renderConsolePublications.textContent = `Inspection failed: ${error.message}`;
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
  const selection = beginSelection("render-console");
  state.selectedRenderConsoleAskId = askId;
  renderConsoleReviewPrompt.disabled = true;
  renderConsoleSaveImage.disabled = true;
  renderConsoleFailTask.disabled = true;
  updateSelectableRows(renderConsoleTaskBody, (row) => row.dataset.askId === state.selectedRenderConsoleAskId);
  try {
    const detail = await fetchJson(`/api/render-console/tasks/${encodeURIComponent(askId)}?${productionQuery().toString()}`, { signal: selection.controller.signal });
    if (selectionIsCurrent(selection) && state.selectedRenderConsoleAskId === askId) renderRenderConsoleDetail(detail);
  } catch (error) {
    if (!isRequestCancellation(error)) throw error;
  }
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
  renderConsoleLocalProfileField.hidden = true;
  renderConsoleLocalProfile.replaceChildren();
  renderConsoleQwenPromptField.hidden = true;
  renderConsoleQwenPrompt.value = "";
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
  renderConsoleRefinementRequired.checked = false;
  renderConsoleRefinementFields.hidden = true;
  renderConsoleRefinementCount.value = "1";
  renderConsoleRefinementNote.value = "";
  renderConsoleReviewPrompt.disabled = true;
  renderConsoleCopyPrompt.disabled = true;
  renderConsolePrev.disabled = true;
  renderConsoleNext.disabled = true;
  renderConsoleFailTask.disabled = true;
  renderConsoleSaveStatus.textContent = "";
  renderConsoleFailStatus.textContent = "";
}

function renderRenderConsoleDetail(detail) {
  const previousAskId = state.renderConsoleDetail?.task?.ask_id;
  const previousProfile = renderConsoleLocalProfile.value;
  const previousQwenPrompt = renderConsoleQwenPrompt.value;
  state.renderConsoleDetail = detail;
  clearRenderConsoleImageSelection();
  const task = detail.task;
  const storyLabel = detail.manifest?.story_slug && detail.manifest?.scene_slug
    ? `Story ${task.story_title || detail.manifest.story_slug} / ${task.scene_title || detail.manifest.scene_slug}`
    : "";
  renderConsoleTitle.textContent = storyLabel || `Asset ${task.asset_id ?? "unknown"} | ${task.expected_output || task.ask_id}`;
  consoleAskId.textContent = task.ask_id;
  consoleAssetLabel.textContent = storyLabel || `Asset ${task.asset_id ?? "unknown"} | ${task.character} / ${task.phase}`;
  consolePipelineLabel.textContent = `${task.pipeline} | ${task.pipeline_stage}`;
  consoleExpectedOutput.textContent = task.expected_output || "";
  renderConsolePrompt.value = detail.prompt || "";
  const isScene = Boolean(detail.manifest?.story_slug && detail.manifest?.scene_slug);
  renderConsoleReviewPrompt.disabled = !detail.prompt;
  renderConsoleCopyPrompt.disabled = !detail.prompt;
  renderConsoleFailTask.disabled = false;
  const localPrompt = detail.local_prompt || {};
  const sceneTask = task.asset_id == null;
  renderConsoleLocalProfileField.hidden = !sceneTask;
  if (sceneTask) {
    const qwenProfile = "comfyui-qwen-image-2-1-scene";
    const configured = localPrompt.configured_local_profile || "";
    const profiles = [{ value: qwenProfile, label: "Qwen Image 2.1 (new scene)" }];
    if (configured && configured !== qwenProfile) {
      profiles.push({ value: configured, label: `Configured: ${configured}` });
    }
    setSelectOptionsWithLabels(renderConsoleLocalProfile, profiles);
    renderConsoleLocalProfile.value = previousAskId === task.ask_id
      && profiles.some((item) => item.value === previousProfile)
      ? previousProfile : (localPrompt.default_local_profile || qwenProfile);
  }
  renderConsoleQwenPrompt.value = previousAskId === task.ask_id
    && previousProfile === "comfyui-qwen-image-2-1-scene"
    ? previousQwenPrompt : (localPrompt.qwen_prompt || "");
  applyRenderConsoleLocalProfile();
  renderConsoleCopyLocalApiParams.disabled = !localPrompt.local_api_call_exists;
  renderConsoleClearLocalTest.disabled = !localPrompt.latest_local_test_render;
  renderRenderConsoleLocalTestRender(localPrompt.latest_local_test_render);
  renderConsoleReferenceFiles(detail.reference_files || []);
  renderRenderConsoleQwenWarnings(localPrompt.qwen_warnings || []);
  updateRenderConsoleNavigation();
}

function applyRenderConsoleLocalProfile() {
  const localPrompt = state.renderConsoleDetail?.local_prompt || {};
  const qwenSelected = !renderConsoleLocalProfileField.hidden
    && renderConsoleLocalProfile.value === "comfyui-qwen-image-2-1-scene";
  const supported = renderConsoleLocalProfileField.hidden
    ? localPrompt.supports_local_test_render
    : qwenSelected ? localPrompt.qwen_supports_local_test_render : localPrompt.configured_supports_local_test_render;
  renderConsoleQwenPromptField.hidden = !qwenSelected;
  renderConsoleQwenPrompt.disabled = qwenSelected && Boolean(localPrompt.qwen_error);
  renderConsoleLocalTest.disabled = !supported;
  const localRenderState = localPrompt.local_render_status?.state || "";
  const message = qwenSelected && localPrompt.qwen_error
    ? localPrompt.qwen_error : supported ? "Local prompt: READY" : "Local prompt: DISABLED";
  renderConsoleLocalStatus.textContent = [message, localRenderState ? `Local render: ${localRenderState}` : ""]
    .filter(Boolean).join(" | ");
}

function renderRenderConsoleQwenWarnings(warnings) {
  renderConsoleQwenWarnings.replaceChildren();
  for (const warning of warnings || []) {
    const item = document.createElement("li");
    item.textContent = `${warning.field || "Scene Builder"}: ${warning.message || "Review this prompt instruction."}`;
    renderConsoleQwenWarnings.append(item);
  }
  renderConsoleQwenWarnings.hidden = !renderConsoleQwenWarnings.childElementCount;
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
  for (const [offset, reference] of (referenceFiles || []).entries()) {
    const section = document.createElement("section");
    section.className = "reference-preview";
    const title = document.createElement("h3");
    const index = reference.image_index || offset + 1;
    const role = reference.prompt_role || reference.role || "reference";
    const label = reference.label || reference.tag || "Reference";
    title.textContent = `Image ${index} — ${role} — ${label}`;
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
  renderConsoleRefinementRequired.checked = false;
  renderConsoleRefinementFields.hidden = true;
  renderConsoleRefinementCount.value = "1";
  renderConsoleRefinementNote.value = "";
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

async function runRenderConsoleLocalAction(action) {
  if (!state.selectedRenderConsoleAskId) {
    return;
  }
  renderConsoleLocalStatus.textContent = "Queueing local test image...";
  renderConsoleLocalTest.disabled = true;
  renderConsoleClearLocalTest.disabled = true;
  try {
    const options = { method: "POST" };
    if (action === "local-test-render" && !renderConsoleLocalProfileField.hidden) {
      options.headers = { "Content-Type": "application/json" };
      const body = { render_profile: renderConsoleLocalProfile.value };
      if (!renderConsoleQwenPromptField.hidden) body.qwen_prompt = renderConsoleQwenPrompt.value;
      options.body = JSON.stringify(body);
    }
    const payload = await fetchJson(
      `/api/render-console/tasks/${encodeURIComponent(state.selectedRenderConsoleAskId)}/${action}?${productionQuery().toString()}`,
      options,
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
      `/api/render-console/tasks/${encodeURIComponent(state.selectedRenderConsoleAskId)}/local-test-render?${productionQuery().toString()}`,
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
  const payload = await fetchJson(`/api/render-console/tasks?${productionQuery().toString()}`);
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
  const selection = beginSelection("local-image-review");
  state.selectedLocalImageReviewAskId = askId;
  updateSelectableRows(localImageReviewTaskBody, (row) => row.dataset.askId === askId);
  try {
    const detail = await fetchJson(
      `/api/local-image-review/tasks/${encodeURIComponent(askId)}?${productionQuery().toString()}`,
      { signal: selection.controller.signal },
    );
    if (selectionIsCurrent(selection) && state.selectedLocalImageReviewAskId === askId) renderLocalImageReviewDetail(detail);
  } catch (error) {
    if (!isRequestCancellation(error)) throw error;
  }
}

function renderRenderConsoleRefinementMetrics(metrics) {
  renderConsoleRefinementMetrics.replaceChildren();
  renderConsoleRefinementGroups.textContent = "";
  if (!metrics) {
    renderConsoleRefinementMetrics.textContent = "Refinement statistics unavailable.";
    return;
  }
  const classified = Number(metrics.classified_count || 0);
  const cards = [
    [classified, "classified"],
    [classified ? `${Math.round(Number(metrics.first_pass_rate || 0) * 100)}%` : "—", "first pass"],
    [classified ? Number(metrics.average_additional_image_generations || 0).toFixed(2) : "—", "extra images / submission"],
    [Number(metrics.unknown_count || 0), "unknown since 2.5"],
  ];
  for (const [value, label] of cards) {
    const card = document.createElement("div");
    card.className = "overview-metric";
    const strong = document.createElement("strong");
    strong.textContent = String(value);
    const caption = document.createElement("span");
    caption.textContent = label;
    card.append(strong, caption);
    renderConsoleRefinementMetrics.append(card);
  }
  const groupText = (metrics.by_engine_profile || []).map((group) => {
    const rate = group.classified_count ? Math.round(Number(group.first_pass_rate || 0) * 100) : 0;
    return `${group.value}: ${group.classified_count} classified, ${rate}% first pass`;
  });
  const pipelineText = (metrics.by_pipeline || []).map((group) => {
    const rate = group.classified_count ? Math.round(Number(group.refinement_rate || 0) * 100) : 0;
    return `${group.value}: ${rate}% refined`;
  });
  renderConsoleRefinementGroups.textContent = [...groupText, ...pipelineText].join(" | ") || "No classified submissions yet.";
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
    ? `Story ${task.story_title || detail.manifest.story_slug} / ${task.scene_title || detail.manifest.scene_slug}`
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
      `Model: ${item.checkpoint || "Unknown"}`,
    ].join(" · ");
    card.append(preview, caption);
    if (item.prompt) {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = "Prompt used";
      const prompt = document.createElement("pre");
      prompt.textContent = item.prompt;
      details.append(summary, prompt);
      card.append(details);
    }
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
  const params = productionQuery();
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
  const params = productionQuery();
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
      `/api/local-image-review/tasks/${encodeURIComponent(state.selectedLocalImageReviewAskId)}/images?${productionQuery().toString()}`,
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

function toggleHelpMenu() {
  const isHidden = helpMenu.hidden;
  helpMenu.hidden = !isHidden;
  helpMenuButton.setAttribute("aria-expanded", isHidden ? "true" : "false");
  if (isHidden) helpMenu.querySelector("button")?.focus();
}

function closeHelpMenu(returnFocus = false) {
  const wasOpen = !helpMenu.hidden;
  helpMenu.hidden = true;
  helpMenuButton.setAttribute("aria-expanded", "false");
  if (returnFocus && wasOpen) helpMenuButton.focus();
}

async function copyRenderConsoleLocalApiParams() {
  if (!state.selectedRenderConsoleAskId) {
    return;
  }
  renderConsoleCopyLocalApiParams.disabled = true;
  try {
    const payload = await fetchJson(
      `/api/render-console/tasks/${encodeURIComponent(state.selectedRenderConsoleAskId)}/local-test-render/api-params?${productionQuery().toString()}`,
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
    const refinementRequired = renderConsoleRefinementRequired.checked;
    const additionalImageGenerations = refinementRequired
      ? Number.parseInt(renderConsoleRefinementCount.value, 10)
      : 0;
    if (refinementRequired && (!Number.isInteger(additionalImageGenerations) || additionalImageGenerations < 1)) {
      throw new Error("Enter at least 1 additional generated image.");
    }
    const params = productionQuery();
    params.set("render_comment", renderConsoleAnswerComment.value || "");
    params.set("refinement_required", refinementRequired ? "true" : "false");
    params.set("additional_image_generations", String(additionalImageGenerations));
    params.set("refinement_note", refinementRequired ? renderConsoleRefinementNote.value || "" : "");
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
    showRenderConsoleMessage(payload.harvest_warning || `Saved answer: ${payload.answer_path}`);
    state.renderConsoleTasks = payload.remaining_tasks || [];
    state.selectedRenderConsoleAskId = state.renderConsoleTasks[0]?.ask_id || null;
    renderRenderConsoleTaskTable();
    if (state.selectedRenderConsoleAskId) {
      await selectRenderConsoleTask(state.selectedRenderConsoleAskId);
    } else {
      clearRenderConsole();
      if (payload.scene_image_review?.candidate_exists) {
        activatePage("render-review", {
          preferredReviewKey: payload.scene_image_review.review_key,
        });
      }
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
  const label = state.renderConsoleDetail?.task?.display_label || state.selectedRenderConsoleAskId;
  if (!await confirmAction(
    "Fail render task",
    `Fail ${label}? The asset will be blocked when harvested.`,
    "Fail Task",
  )) {
    return;
  }
  renderConsoleFailTask.disabled = true;
  renderConsoleFailStatus.textContent = "Writing failed answer...";
  try {
    const response = await fetch(`/api/render-console/tasks/${encodeURIComponent(state.selectedRenderConsoleAskId)}/fail?${productionQuery().toString()}`, {
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
  const [headImagePayload, assemblyPayload] = await Promise.all([
    fetchJson(`/api/head-image-manifest/tasks?${currentQuery().toString()}`),
    fetchJson(`/api/character-assembly-manifest/tasks?${currentQuery().toString()}`),
  ]);
  state.manifestTasks = [...(headImagePayload.tasks || []), ...(assemblyPayload.tasks || [])];
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
    renderEmptyRow(manifestTaskBody, 4, "No manifest tasks are waiting. Advance an asset to MANIFEST to create work.");
    return;
  }
  for (const task of state.manifestTasks) {
    const row = document.createElement("tr");
    row.dataset.assetId = task.asset_id;
    row.classList.toggle("selected", task.asset_id === state.selectedManifestAssetId);
    const proxyJob = task.ai_proxy_status?.jobs?.[0];
    const proxyLabel = proxyJob
      ? `${proxyJob.display_state || proxyJob.state}${proxyJob.trusted_worker_backend ? ` · ${proxyJob.trusted_worker_backend}` : ""}${proxyJob.diagnostic ? ` · ${proxyJob.diagnostic}` : ""}`
      : "Ready";
    for (const value of [task.asset_id, task.pipeline, task.body_view, proxyLabel]) {
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
  const task = state.manifestTasks.find((item) => item.asset_id === state.selectedManifestAssetId);
  const route = task?.pipeline === "Head-Image"
    ? "head-image-manifest"
    : "character-assembly-manifest";
  const detail = await fetchJson(`/api/${route}/${state.selectedManifestAssetId}?${currentQuery().toString()}`);
  if (state.selectedManifestAssetId !== Number(assetId)) {
    return;
  }
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
  manifestBodySection.hidden = false;
  headshotUpload.hidden = false;
  headshotPasteZone.hidden = false;
  saveManifestReferencesButton.disabled = true;
  manifestPrev.disabled = true;
  manifestNext.disabled = true;
}

function renderManifest(detail) {
  state.manifestDetail = detail;
  const asset = detail.asset;
  const proxyStatus = detail.ai_proxy_status?.pending ? " | AI Proxy pending" : "";
  manifestTitle.textContent = `Asset ${asset.asset_id} | ${asset.body_view} / ${asset.head_view}${proxyStatus}`;
  const isHeadImage = asset.pipeline === "Head-Image";
  const isCharacterAssembly = asset.pipeline === "Character-Assembly";
  manifestBodySection.hidden = isHeadImage;
  manifestHeadHeading.textContent = isHeadImage ? "Required Source Image" : "Head Image";
  headshotUpload.hidden = isCharacterAssembly;
  headshotPasteZone.hidden = isCharacterAssembly;
  fillReferenceSelect(bodyReferenceSelect, detail.body_reference_options || [], detail.selected_body_reference?.path || "");
  const headOptions = isHeadImage
    ? (detail.source_options || [])
    : (detail.head_image_options || []);
  const selectedHeadPath = isHeadImage
    ? (detail.selected_source?.path || "")
    : (detail.selected_head_image?.path || "");
  fillReferenceSelect(headshotReferenceSelect, headOptions, selectedHeadPath);
  manifestReferenceJson.textContent = JSON.stringify(detail.reference_files || [], null, 2);
  bodyReferenceSelect.disabled = !detail.is_manifest_editable;
  headshotReferenceSelect.disabled = !detail.is_manifest_editable;
  headshotUpload.disabled = !detail.is_manifest_editable;
  headshotPasteZone.tabIndex = detail.is_manifest_editable ? 0 : -1;
  headshotPasteZone.setAttribute("aria-disabled", detail.is_manifest_editable ? "false" : "true");
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
  renderImagePreview(headshotReferencePreview, headshotReferenceSelect.value, "No head image selected.");
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
    const isHeadImage = state.manifestDetail?.asset?.pipeline === "Head-Image";
    const isCharacterAssembly = state.manifestDetail?.asset?.pipeline === "Character-Assembly";
    const route = isHeadImage
      ? `/api/head-image-manifest/${state.selectedManifestAssetId}/source`
      : (isCharacterAssembly
        ? `/api/character-assembly-manifest/${state.selectedManifestAssetId}/references`
        : `/api/character-assembly-manifest/${state.selectedManifestAssetId}/references`);
    const payload = await fetchJson(
      `${route}?${currentQuery().toString()}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(isHeadImage ? {
          source_path: headshotReferenceSelect.value,
        } : isCharacterAssembly ? {
          body_reference_path: bodyReferenceSelect.value,
          head_image_path: headshotReferenceSelect.value,
        } : {
          body_reference_path: bodyReferenceSelect.value,
          head_image_path: headshotReferenceSelect.value,
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

async function uploadHeadshotReference(file = headshotUpload.files?.[0]) {
  if (!file) {
    return;
  }
  const isHeadImage = state.manifestDetail?.asset?.pipeline === "Head-Image";
  showManifestMessage(isHeadImage ? "Uploading Head-Image source..." : "Uploading legacy headshot override...");
  const params = currentQuery();
  params.set("filename", file.name);
  try {
    const uploadRoute = "/api/head-image-sources";
    const payload = await fetchJson(`${uploadRoute}?${params.toString()}`, {
      method: "POST",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file,
    });
    showManifestMessage(`Uploaded ${payload.name}.`);
    const selectedBodyReferencePath = bodyReferenceSelect.value;
    await selectManifestAsset(state.selectedManifestAssetId);
    bodyReferenceSelect.value = selectedBodyReferencePath;
    headshotReferenceSelect.value = payload.path;
    updateManifestPreviews();
  } catch (error) {
    showManifestMessage(error.message, "error");
  } finally {
    headshotUpload.value = "";
  }
}







for (const button of actionButtons) {
  button.addEventListener("click", () => runAssetAction(button.dataset.action));
}

workspaceCharacter.addEventListener("click", () => switchWorkspace("character"));
workspaceLocal?.addEventListener("click", () => switchWorkspace("local"));
workspaceStory.addEventListener("click", () => switchWorkspace("story"));
const localRunAllButton = document.querySelector("#local-run-all-remaining");
const localRunAllStatus = document.querySelector("#local-run-all-status");

function renderLocalRunAllStatus(campaign) {
  const progress = campaign.progress || {};
  const running = Number(progress.RUNNING || 0);
  const waiting = Number(progress.WAITING_FOR_SELECTION || 0);
  const waitingReferences = Number(progress.WAITING_FOR_REFERENCE || 0);
  const failed = Number(progress.FAILED || 0);
  const complete = Number(progress.COMPLETE || 0);
  const total = Number(campaign.batch_count || (campaign.batches || []).length);
  const imageCounts = `${campaign.images_complete || 0} images ready · ${campaign.images_remaining || 0} remaining`;
  const batchCounts = `${running} running · ${waiting} waiting for selection · ${waitingReferences} waiting for references · ${failed} failed · ${complete}/${total} complete`;
  const details = (campaign.batches || []).filter((item) => ["FAILED", "WAITING_FOR_SELECTION", "WAITING_FOR_REFERENCE"].includes(item.result)
    || item.review_error)
    .slice(0, 4).map((item) => `${item.character} ${item.phase}${item.costume ? ` · ${item.costume}` : ""}: ${item.review_error
      ? `Advisory review: ${item.review_error}` : item.message || item.error || item.result.replaceAll("_", " ").toLowerCase()}`);
  const campaignLabel = campaign.status === "COMPLETE" ? "Run all Remaining finished."
    : campaign.status === "FAILED" ? `Run all Remaining failed: ${campaign.error || "see campaign details."}`
      : "Run all Remaining is active.";
  localRunAllStatus.textContent = [campaignLabel, imageCounts, batchCounts, ...details].join("\n");
  localRunAllStatus.hidden = false;
}

async function pollLocalRunAll(campaignId) {
  try {
    const campaign = await fetchJson(`/api/local/run-all-remaining/${encodeURIComponent(campaignId)}`, { bindToPage: false });
    if (state.localRunAllCampaignId !== campaignId) return;
    renderLocalRunAllStatus(campaign);
    if (["QUEUED", "RUNNING", "RECOVERING"].includes(campaign.status)) {
      state.localRunAllTimer = window.setTimeout(() => void pollLocalRunAll(campaignId), 3000);
    } else {
      state.localRunAllTimer = null;
      localRunAllButton.disabled = false;
    }
  } catch (error) {
    localRunAllStatus.textContent = `Could not read run-all progress: ${error.message}`;
    localRunAllStatus.hidden = false;
    state.localRunAllTimer = window.setTimeout(() => void pollLocalRunAll(campaignId), 6000);
  }
}



localAssetsButton.addEventListener("click", (event) => {
  event.stopPropagation();
  localAssetsMenu.hidden = !localAssetsMenu.hidden;
  localAssetsButton.setAttribute("aria-expanded", String(!localAssetsMenu.hidden));
  if (!localAssetsMenu.hidden) {
    const rect = localAssetsButton.getBoundingClientRect();
    localAssetsMenu.style.left = `${Math.max(8, rect.left)}px`;
    localAssetsMenu.style.top = `${rect.bottom + 6}px`;
  }
  if (!localAssetsMenu.hidden) localAssetsMenu.querySelector("button")?.focus();
});
localAssetsMenu.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  localAssetsMenu.hidden = true;
  localAssetsButton.setAttribute("aria-expanded", "false");
  localAssetsButton.focus();
});
document.addEventListener("click", (event) => {
  if (!event.target.closest(".local-assets-menu")) {
    localAssetsMenu.hidden = true;
    localAssetsButton.setAttribute("aria-expanded", "false");
  }
});
responsiveSectionMenu.addEventListener("change", async () => {
  const page = responsiveSectionMenu.value;
  if (!page) return;
  if (!(await runGuardedTransition(() => activatePage(page, { skipAutosave: true })))) {
    renderResponsiveSectionMenu();
  }
});
characterPhoneViewer.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-character-view-page]");
  if (!button) return;
  await runGuardedTransition(() => activatePage(button.dataset.characterViewPage, { skipAutosave: true }));
});


window.matchMedia("(max-width: 600px)").addEventListener("change", syncResponsiveChrome);

newMenuButton.addEventListener("click", (event) => {
  event.stopPropagation();
  toggleNewMenu();
});
newCharacterButton.addEventListener("click", () => runGuardedTransition(async () => {
  closeNewMenu();
  await startNewCharacter();
}));
newPhaseButton.addEventListener("click", () => runGuardedTransition(async () => {
  closeNewMenu();
  await startNewPhase();
}));
newStoryButton.addEventListener('click',async()=>{
  closeNewMenu();
  history.pushState({},'',`/?page=narrative&workspace=story&universe_id=${encodeURIComponent(state.universeId)}`);
  await activatePage('narrative',{updateHistory:false});
  document.querySelector('#story-dialog').showModal();
});
newSceneButton.addEventListener('click',async()=>{
  closeNewMenu();
  const story = new URLSearchParams(location.search).get('story') || state.selectedStorySlug;
  if (!story) { showActionMessage('Create or select a story first.','error'); return; }
  history.pushState({},'',`/?page=narrative&workspace=story&universe_id=${encodeURIComponent(state.universeId)}&story=${story}`);
  await activatePage('narrative',{updateHistory:false});
  document.querySelector('#new-narrative-scene input').focus();
});


characterRecommendedAction.addEventListener("click", () => runGuardedTransition(async () => {
  const destination = characterRecommendedAction.dataset.destination || "onboarding";
  await activatePage(destination, { skipAutosave: true });
  if (destination === "onboarding") characterSetupDetails.open = true;
}));
toolbarRestartZet.addEventListener("click", restartZetFromToolbar);
toolbarLocalCharacterOverview.addEventListener("click", () => {
  window.location.assign("/local-character-overview");
  closeToolbarSettingsMenu();
});

toolbarGateTestRig.addEventListener("click", () => {
  window.location.assign("/gate-test-rig");
  closeToolbarSettingsMenu();
});

toolbarSettingsButton.addEventListener("click", (event) => {
  event.stopPropagation();
  toggleToolbarSettingsMenu();
});
helpMenuButton.addEventListener("click", (event) => {
  event.stopPropagation();
  toggleHelpMenu();
});
toolbarHarvestAi.addEventListener("click", (event) => {
  event.stopPropagation();
  harvestAiFromToolbar();
});
document.addEventListener("click", (event) => {
  if (!toolbarSettingsMenu.hidden && !toolbarSettingsMenu.contains(event.target) && event.target !== toolbarSettingsButton) {
    closeToolbarSettingsMenu(true);
  }
  if (!helpMenu.hidden && !helpMenu.contains(event.target) && event.target !== helpMenuButton) {
    closeHelpMenu(true);
  }
  if (!newMenu.hidden && !newMenu.contains(event.target) && event.target !== newMenuButton) {
    closeNewMenu();
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeToolbarSettingsMenu(true);
    closeHelpMenu(true);
    closeNewMenu(true);
  }
});
promptAnalysisClose.addEventListener("click", closePromptAnalysisDialog);
promptAnalysisSecondOpinion.addEventListener("click", runPromptAnalysisSecondOpinion);
promptAnalysisDialog.addEventListener("click", (event) => {
  if (event.target === promptAnalysisDialog) {
    closePromptAnalysisDialog();
  }
});




onboardingSaveDraft.addEventListener("click", saveOnboardingDraft);
onboardingCopyGptPrompt.addEventListener("click", () => copyText(onboardingGptPrompt.value, "ChatGPT prompt copied."));


onboardingSpecies.addEventListener("change", () => updateOnboardingHelperPrompt());
onboardingGender.addEventListener("change", () => updateOnboardingHelperPrompt());
onboardingArtStyle.addEventListener("input", () => updateOnboardingHelperPrompt());
onboardingUploadTemplate.addEventListener("click", uploadOnboardingTemplate);
onboardingAddHeadImages.addEventListener("click", addMissingHeadImages);


for (const button of document.querySelectorAll(".open-template-manual")) {
  button.addEventListener("click", () => openTemplateManual(button.dataset.manual));
}
assetFilterTodo.addEventListener("change", applyAssetFilters);
assetFilterHideBase.addEventListener("change", applyAssetFilters);
assetFilterPipeline.addEventListener("change", applyAssetFilters);
assetDetailStatusMode.addEventListener("click", () => setAssetDetailMode("status"));
assetDetailImageMode.addEventListener("click", () => setAssetDetailMode("locked"));
createIdentityFromAssetButton.addEventListener("click", startIdentityKeyFromSelectedAsset);



identityKeyCreatePreview.addEventListener("click", createIdentityKeyPreview);
identityKeySave.addEventListener("click", saveIdentityKey);

costumeAddNew.addEventListener("click", clearCostumeForm);
costumeDelete.addEventListener("click", deleteSelectedCostume);
costumeCreate.addEventListener("click", saveCostume);
sceneAppearanceAddNew.addEventListener("click", clearSceneAppearanceForm);

expressionAddNew.addEventListener("click", clearExpressionForm);
expressionCreate.addEventListener("click", saveExpression);



















zineNew.addEventListener("click", () => runGuardedTransition(clearZineEditor));
zineEdit.addEventListener("click", () => zineName.focus());
zineSave.addEventListener("click", saveZine);
zineRegenerate.addEventListener("click", () => runGuardedTransition(regenerateZine));
zineDelete.addEventListener("click", () => runGuardedTransition(deleteZine));

zineFillStory.addEventListener("click", fillZineFromStory);
zineSpread1.addEventListener("change", () => setZineSpread(1, zineSpread1.checked));
zineSpread3.addEventListener("change", () => setZineSpread(3, zineSpread3.checked));
zineSpread5.addEventListener("change", () => setZineSpread(5, zineSpread5.checked));
enableFullscreenImage(zinePreview);
enableFullscreenImage(imageCatalogPreview);
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
  fullscreenCandidateLink.hidden = true;
  fullscreenCandidateLink.removeAttribute("href");
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







entityLibrarySearchForm.addEventListener("submit", (event) => { event.preventDefault(); searchEntityLibrary().catch((error) => { entityLibraryCount.textContent = error.message; }); });
entityLibraryPrevious.addEventListener("click", () => {
  entityLibraryPageOffset = Math.max(0, entityLibraryPageOffset - ENTITY_LIBRARY_PAGE_SIZE);
  searchEntityLibrary(true).catch((error) => { entityLibraryCount.textContent = error.message; });
});
entityLibraryNext.addEventListener("click", () => {
  entityLibraryPageOffset += ENTITY_LIBRARY_PAGE_SIZE;
  searchEntityLibrary(true).catch((error) => { entityLibraryCount.textContent = error.message; });
});
for (const control of [entityLibraryFilterEntity, entityLibraryFilterType, entityLibraryFilterVariant, entityLibraryFilterSet, entityLibraryFilterFacet, entityLibraryFilterStatus, entityLibraryFilterOrigin, entityLibraryIncludeObsolete]) {
  control.addEventListener("change", () => searchEntityLibrary().catch((error) => { entityLibraryCount.textContent = error.message; }));
}
entityLibrarySearch.addEventListener("keydown", (event) => {
  if (event.key === "Enter") searchEntityLibrary().catch((error) => { entityLibraryCount.textContent = error.message; });
});
entityLibraryClearFilters.addEventListener("click", () => {
  entityLibrarySearch.value = "";
  for (const control of [entityLibraryFilterEntity, entityLibraryFilterType, entityLibraryFilterVariant, entityLibraryFilterSet, entityLibraryFilterFacet, entityLibraryFilterStatus, entityLibraryFilterOrigin]) control.value = "";
  entityLibraryIncludeObsolete.checked = false;
  entityLibraryFilterFacet.value = "";
  entityLibraryPageOffset = 0;
  searchEntityLibrary();
});
document.querySelectorAll("[data-inventory-view]").forEach((button) => button.addEventListener("click", async () => {
  if (entityLibraryCurrentView === "detail" && !(await guardCurrentEditor())) return;
  activateInventoryView(button.dataset.inventoryView);
}));
entityLibraryOrganizer.addEventListener("click", handleOrganizationAction);
entityLibraryOrganizer.addEventListener("submit", saveOrganizationRecord);
document.querySelector("#entity-library-open-import").addEventListener("click", () => entityLibraryImportDialog.showModal());
document.querySelector("#entity-library-close-import").addEventListener("click", () => entityLibraryImportDialog.close());
entityLibraryImportDialog.addEventListener("close", () => {
  entityLibraryImportGeneration = null;
  entityLibraryGenerationPrompts.hidden = true;
  entityLibraryImportPreview.hidden = true;
  entityLibraryImportPreview.removeAttribute("src");
});
document.querySelector("#entity-library-merge-cancel").addEventListener("click", () => entityLibraryMergeDialog.close());
entityLibraryMergeDialog.addEventListener("click", (event) => { if (event.target === entityLibraryMergeDialog) entityLibraryMergeDialog.close(); });
const importPanel = document.querySelector(".entity-library-sidebar > section");
if (importPanel) {
  importPanel.classList.add("inventory-import-panel");
  entityLibraryImportDialogContent.prepend(importPanel);
  const heading = document.createElement("h2"); heading.textContent = "Add an image to the library"; importPanel.prepend(heading);
}



entityLibraryEntityCreate.addEventListener("click", async () => {
  try {
    await fetchJson("/api/entity-library/entities", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: entityLibraryEntityName.value, entity_type: entityLibraryEntityType.value }) });
    entityLibraryEntityName.value = "";
    await loadEntityLibraryInventory();
  } catch (error) { window.alert(error.message); }
});
entityLibrarySetCreate.addEventListener("click", async () => {
  try {
    const payload = await fetchJson("/api/entity-library/sets", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: entityLibrarySetName.value, set_type: entityLibrarySetType.value || "general" }) });
    entityLibrarySetName.value = "";
    entityLibrarySetType.value = "";
    await loadEntityLibraryInventory();
    entityLibrarySetSelect.value = payload.set?.set_id || "";
    syncEntityLibrarySetEditor();
  } catch (error) { window.alert(error.message); }
});
entityLibrarySetSelect.addEventListener("change", syncEntityLibrarySetEditor);
entityLibrarySetSave.addEventListener("click", saveEntityLibrarySet);
entityLibrarySetDelete.addEventListener("click", deleteEntityLibrarySet);
entityLibraryVariantCreate.addEventListener("click", async () => {
  if (!entityLibraryVariantEntity.value || !entityLibraryVariantName.value.trim()) return;
  try {
    await fetchJson(`/api/entity-library/entities/${encodeURIComponent(entityLibraryVariantEntity.value)}/variants`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: entityLibraryVariantName.value, variant_type: entityLibraryVariantType.value }),
    });
    entityLibraryVariantName.value = "";
    await loadEntityLibraryInventory();
  } catch (error) { window.alert(error.message); }
});
entityLibraryRelationCreate.addEventListener("click", async () => {
  if (!entityLibraryRelationSource.value || !entityLibraryRelationTarget.value) return;
  try {
    await fetchJson("/api/entity-library/relations", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_entity_id: entityLibraryRelationSource.value, target_entity_id: entityLibraryRelationTarget.value, relation_type: entityLibraryRelationType.value }),
    });
    await loadEntityLibraryInventory();
  } catch (error) { window.alert(error.message); }
});
entityLibraryDescriptorOwnerType.addEventListener("change", updateEntityLibraryDescriptorOwners);
entityLibraryDescriptorSave.addEventListener("click", async () => {
  if (!entityLibraryDescriptorOwner.value || !entityLibraryDescriptorText.value.trim()) return;
  try {
    await fetchJson("/api/entity-library/descriptors", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        owner_type: entityLibraryDescriptorOwnerType.value,
        owner_id: entityLibraryDescriptorOwner.value,
        descriptor_type: entityLibraryDescriptorType.value,
        text: entityLibraryDescriptorText.value,
      }),
    });
    entityLibraryDescriptorText.value = "";
    await loadEntityLibraryInventory();
  } catch (error) { window.alert(error.message); }
});
entityLibrarySave.addEventListener("click", async () => {
  await saveEntityLibraryAsset();
});
entityLibraryRetryLoad.addEventListener("click", () => {
  if (entityLibraryLoadingAssetId) void selectEntityLibraryAsset(entityLibraryLoadingAssetId);
});
entityLibraryDelete.addEventListener("click", deleteEntityLibraryAsset);



entityLibraryBack.addEventListener("click", async () => {
  if (!(await guardCurrentEditor())) return;
  activateInventoryView("search");
});















imageCatalogImportZone.addEventListener("paste", (event) => {
  const blob = imageBlobFromPasteEvent(event);
  if (blob) {
    event.preventDefault();
    setImageCatalogImportBlob(blob);
  }
});
imageCatalogImportZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  imageCatalogImportZone.classList.add("drag-over");
});
imageCatalogImportZone.addEventListener("dragleave", () => imageCatalogImportZone.classList.remove("drag-over"));
imageCatalogImportZone.addEventListener("drop", (event) => {
  event.preventDefault();
  imageCatalogImportZone.classList.remove("drag-over");
  setImageCatalogImportBlob(event.dataTransfer?.files?.[0]);
});
imageCatalogImportFile.addEventListener("change", () => setImageCatalogImportBlob(imageCatalogImportFile.files?.[0]));
imageCatalogImportSave.addEventListener("click", importImageCatalogImage);
imageCatalogSetSelect.addEventListener("change", renderSelectedReferenceSet);
imageCatalogSetNew.addEventListener("click", () => {
  imageCatalogSetSelect.value = "";
  renderSelectedReferenceSet();
  imageCatalogSetLabel.focus();
});
imageCatalogSetSave.addEventListener("click", saveImageCatalogReferenceSet);
imageCatalogSetDelete.addEventListener("click", deleteImageCatalogReferenceSet);
imageCatalogAdd.addEventListener("click", () => openImageCatalogManagedUpload("add"));
imageCatalogAddFile.addEventListener("change", () => setImageCatalogManagedBlob("add", imageCatalogAddFile.files?.[0]));
imageCatalogReplaceFile.addEventListener("change", () => setImageCatalogManagedBlob("replace", imageCatalogReplaceFile.files?.[0]));
for (const [zone, mode] of [[imageCatalogAddZone, "add"], [imageCatalogReplaceZone, "replace"]]) {
  zone.addEventListener("paste", (event) => {
    const blob = imageBlobFromPasteEvent(event);
    if (blob) {
      event.preventDefault();
      setImageCatalogManagedBlob(mode, blob);
    }
  });
  zone.addEventListener("dragover", (event) => {
    event.preventDefault();
    zone.classList.add("drag-over");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    zone.classList.remove("drag-over");
    setImageCatalogManagedBlob(mode, event.dataTransfer?.files?.[0]);
  });
}
imageCatalogReplaceSubmit.addEventListener("click", replaceImageCatalogImage);
imageCatalogAddSubmit.addEventListener("click", addImageCatalogImage);
imageCatalogReplace.addEventListener("click", replaceImageCatalogImage);
imageCatalogDelete.addEventListener("click", () => deleteImageCatalogImage(false));






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



copyCondensedButton.addEventListener("click", () => copyText(condensedText.value, "Condensed prompt copied."));
analyzePromptButton.addEventListener("click", analyzePromptReview);
viewPromptAnalysisButton.addEventListener("click", viewPromptReviewAnalysis);
sourceOpenEditor.addEventListener("click", openSelectedSourceEditor);
sourceEditorSave.addEventListener("click", saveSourceEditor);


promptReviewRefresh.addEventListener("click", () => loadPromptReviewTasks());
renderPromoteButton.addEventListener("click", promoteRenderReview);
renderDiscardCandidateButton.addEventListener("click", () => runRenderReviewAction("discard-candidate"));
renderFailRenderButton.addEventListener("click", () => runRenderReviewAction("fail-to-render"));
renderFailRegenerateButton.addEventListener("click", () => runRenderReviewAction("fail-to-regenerate"));
renderCommentSave.addEventListener("click", saveRenderReviewComment);
turnaroundSavePartial.addEventListener("click", savePartialTurnaround);


refreshAiControlsButton.addEventListener("click", async () => {
  await loadAiControls();
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
refreshOllamaModels.addEventListener("click", () => refreshOllamaModelOptions(true));
settingLocalRenderPreset.addEventListener("change", refreshLocalRenderCheckpointOptions);
refreshComfyuiCheckpoints.addEventListener("click", refreshComfyuiCheckpointOptions);
settingComfyuiProfile.addEventListener("change", refreshComfyuiCheckpointOptions);
settingLocalRenderBackend.addEventListener("change", syncLocalRenderBackendPanels);


batchRenderResetButton.addEventListener("click", runBatchRenderReset);
renderConsoleRefresh.addEventListener("click", () => loadRenderConsoleTasks());
renderConsolePublicationsRefresh.addEventListener("click", loadRenderConsolePublications);



renderConsoleLocalTest.addEventListener("click", () => runRenderConsoleLocalAction("local-test-render"));
renderConsoleLocalProfile.addEventListener("change", applyRenderConsoleLocalProfile);
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
for (const control of [imageCatalogSource, imageCatalogCategory, imageCatalogStatus, imageCatalogCollection, imageCatalogKeyword, imageCatalogIncludeBase]) {
  control.addEventListener("change", markImageCatalogFiltersDirty);
}
for (const control of [imageCatalogCharacter, imageCatalogPhase, imageCatalogCostume, imageCatalogPipeline, imageCatalogStory, imageCatalogScene, imageCatalogSubscene]) {
  control.addEventListener("input", markImageCatalogFiltersDirty);
}
imageCatalogSearch.addEventListener("input", markImageCatalogFiltersDirty);
imageCatalogSearch.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    loadImageCatalog();
  }
});
imageCatalogClearFilters.addEventListener("click", clearImageCatalogFilters);
imageCatalogRefresh.addEventListener("click", async () => {
  await loadImageCatalogOrganization();
  await loadImageCatalog();
});
imageCatalogSave.addEventListener("click", saveImageCatalogItem);
imageCatalogIdentityMode.addEventListener("change", syncImageCatalogOverrideControls);
imageCatalogCostumeMode.addEventListener("change", syncImageCatalogOverrideControls);
imageCatalogAi.addEventListener("click", queueImageCatalogDescription);
imageCatalogAiCheck.addEventListener("click", harvestImageCatalogDescription);
imageCatalogAiApprove.addEventListener("click", () => reviewImageCatalogDraft(true));
imageCatalogAiReject.addEventListener("click", () => reviewImageCatalogDraft(false));
imageCatalogAddCollection.addEventListener("click", () => addImageCatalogVocabulary("collections", imageCatalogNewCollection));
imageCatalogAddKeyword.addEventListener("click", () => addImageCatalogVocabulary("keywords", imageCatalogNewKeyword));
imageCatalogBulkApply.addEventListener("click", bulkUpdateImageCatalog);

entityLibraryModifyGenerated.addEventListener("click", modifyEntityLibraryImageWithGenerator);
entityLibraryGeneratePrompt.addEventListener("click", generateEntityImagePrompt);
entityLibraryGenerateIdentity.addEventListener("click", generateEntityIdentity);
imageGenerationReviewPrevious.addEventListener("click", () => {
  const slots = imageGenerationReviewableSlots();
  imageGenerationReviewIndex = slots[Math.max(0, slots.indexOf(imageGenerationReviewIndex) - 1)];
  renderImageGenerationReview();
});
imageGenerationReviewNext.addEventListener("click", () => {
  const slots = imageGenerationReviewableSlots();
  imageGenerationReviewIndex = slots[Math.min(slots.length - 1, slots.indexOf(imageGenerationReviewIndex) + 1)];
  renderImageGenerationReview();
});
imageGenerationReviewClose.addEventListener("click", () => imageGenerationReview.close());
imageGenerationReviewSelect.addEventListener("click", () => void imageGenerationSlotAction(imageGenerationSelectedSlot === imageGenerationReviewIndex ? "unselect" : "select", imageGenerationReviewIndex));
imageGenerationReviewRetry.addEventListener("click", () => void imageGenerationSlotAction("regenerate", imageGenerationReviewIndex, currentImageGenerationInputs()));
imageGenerationReviewClear.addEventListener("click", async () => {
  const slots = imageGenerationReviewableSlots();
  const position = slots.indexOf(imageGenerationReviewIndex);
  const next = slots[position + 1] ?? slots[position - 1];
  await imageGenerationSlotAction("clear", imageGenerationReviewIndex);
  if (next !== undefined && !imageGenerationReview.open) openImageGenerationReview(next);
});
imageGenerationReviewImport.addEventListener("click", openImageGenerationImportDialog);
imageGenerationReviewUpdate.addEventListener("click", async () => {
  const selected = imageGenerationResult(imageGenerationSelectedSlot);
  if (!selected?.job.source_asset_id) return;
  imageGenerationReviewUpdate.disabled = true;
  try {
    const result = await fetchJson("/api/image-generation/jobs/" + encodeURIComponent(selected.assignment.requestId) + "/images/" + selected.assignment.index + "/apply", { method: "POST" });
    await activatePage("auxiliary-resources", { skipAutosave: true });
    await selectEntityLibraryAsset(result.asset.asset_id);
    showAuxResourceMessage("Image updated in the inventory.", "success");
  } catch (error) {
    showMessageElement(imageGenerationMessage, error.message, "error");
  } finally {
    imageGenerationReviewUpdate.disabled = false;
  }
});
document.addEventListener("keydown", (event) => {
  if (!imageGenerationReview.open || /^(INPUT|TEXTAREA|SELECT)$/.test(event.target?.tagName || "")) return;
  if (event.key === "ArrowLeft" && !imageGenerationReviewPrevious.disabled) imageGenerationReviewPrevious.click();
  if (event.key === "ArrowRight" && !imageGenerationReviewNext.disabled) imageGenerationReviewNext.click();
});
imageGenerationTxt2img.addEventListener("click", () => { setImageGenerationMode("txt2img"); saveImageGenerationState(); });
imageGenerationImg2img.addEventListener("click", () => { setImageGenerationMode("img2img"); saveImageGenerationState(); });
imageGenerationForm.addEventListener("submit", submitImageGeneration);
imageGenerationFill.addEventListener("click", () => void submitImageGenerationForSlots());
imageGenerationClear.addEventListener("click", clearImageGenerationResults);
renderImageGenerationReferenceSlots();
for (const input of [imageGenerationPrompt, imageGenerationNegative, imageGenerationWidth, imageGenerationHeight]) {
  input.addEventListener("input", saveImageGenerationState);
  input.addEventListener("change", saveImageGenerationState);
}






sourceEditorText.addEventListener("input", updateDirtyIndicators);
for (const control of [zineName, ...Object.values(zineSlotInputs), zineSpread1, zineSpread3, zineSpread5]) {
  control.addEventListener("input", updateDirtyIndicators);
  control.addEventListener("change", updateDirtyIndicators);
}



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
renderConsoleRefinementRequired.addEventListener("change", () => {
  renderConsoleRefinementFields.hidden = !renderConsoleRefinementRequired.checked;
  if (renderConsoleRefinementRequired.checked) renderConsoleRefinementCount.focus();
});
renderConsoleFailTask.addEventListener("click", failRenderConsoleTask);
bodyReferenceSelect.addEventListener("change", updateManifestPreviews);
headshotReferenceSelect.addEventListener("change", updateManifestPreviews);
headshotUpload.addEventListener("change", () => uploadHeadshotReference());
headshotPasteZone.addEventListener("paste", (event) => {
  if (headshotPasteZone.getAttribute("aria-disabled") === "true") return;
  const file = imageBlobFromPasteEvent(event);
  if (file) {
    event.preventDefault();
    uploadHeadshotReference(file);
  }
});
saveManifestReferencesButton.addEventListener("click", saveManifestReferences);


pipelineInspectionSearch.addEventListener("input", renderPipelineInspectionList);
pipelineInspectionCopy.addEventListener("click", copyPipelineInspectionFile);
pipelineInspectionOpenFolder.addEventListener("click", openPipelineInspectionFolder);

function annotateResponsiveTables(root = document) {
  for (const table of root.querySelectorAll("table")) {
    const labels = Array.from(table.querySelectorAll(":scope > thead th"), (heading) => heading.textContent.trim());
    if (!labels.length) continue;
    table.classList.add("responsive-list-table");
    for (const row of table.querySelectorAll(":scope > tbody > tr")) {
      for (const [index, cell] of Array.from(row.children).entries()) {
        cell.dataset.label = labels[index] || "Item";
      }
    }
  }
}

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
  annotateResponsiveTables();
  new MutationObserver(() => annotateResponsiveTables()).observe(document.querySelector("main"), {
    childList: true,
    subtree: true,
  });
  sourceEditorText.placeholder = "Open an editable source from Prompt Inspection.";
  setupTabs();
  await loadUniverses();
  const startupLoad = beginPageLoad(null);
  loadStoredAssetFilters();
  try {
    const workspacePreferences = loadStoredWorkspacePreferences();
    const storyContext = loadStoredStoryContext();
    if (workspacePreferences) {
      state.workspace = workspacePreferences.workspace;
      state.lastWorkspacePages = workspacePreferences.pages;
    }
    state.selectedStorySlug = storyContext.story || null;
    state.selectedSceneSlug = storyContext.scene || null;
    await loadContext();
    if (!pageLoadIsCurrent(startupLoad)) return;
    const initialRouteParams = new URLSearchParams(window.location.search);
    const isLocalBatchRoute = Boolean(initialRouteParams.get("local_batch"))
      && LOCAL_ASSET_PAGES.has(initialRouteParams.get("page"));
    const routeCharacter = initialRouteParams.get("character");
    const routePhase = initialRouteParams.get("phase");
    if (initialRouteParams.get("task_context") === "1") {
      if (routeCharacter && !state.characters.includes(routeCharacter)) {
        window.ZetTaskCapture.notice(`Recorded character "${routeCharacter}" is unavailable. Showing the current available selection.`);
      } else if (routePhase && !(state.phasesByCharacter[routeCharacter || state.character] || []).includes(routePhase)) {
        window.ZetTaskCapture.notice(`Recorded phase "${routePhase}" is unavailable. Showing an available phase.`);
      }
    }
    if (routeCharacter && state.characters.includes(routeCharacter)) {
      state.character = routeCharacter;
      const routePhases = state.phasesByCharacter[routeCharacter] || [];
      state.phase = routePhase && routePhases.includes(routePhase) ? routePhase : routePhases[0] || null;
      characterSelect.value = state.character;
      updatePhaseSelect();
      saveStoredContext();
    }
    if (!isLocalBatchRoute) {
      try {
        await loadAssets();
      } catch (error) {
        if (isRequestCancellation(error)) throw error;
        assetStatus.textContent = error.message;
      }
    }
    if (!pageLoadIsCurrent(startupLoad)) return;
    await loadStories(state.selectedStorySlug);
    if (!pageLoadIsCurrent(startupLoad)) return;
    const params = new URLSearchParams(window.location.search);
    const routeStory = params.get("story_slug");
    const routeScene = params.get("scene_slug");
    if (params.get("task_context") === "1" && routeStory && !state.stories.some((item) => item.slug === routeStory)) {
      window.ZetTaskCapture.notice(`Recorded story "${routeStory}" is unavailable. Showing an available story.`);
    }
    if (routeStory && state.stories.some((item) => item.slug === routeStory)) {
      state.selectedStorySlug = routeStory;
      await loadWorkspaceSummary();
      const routeScenes = canonicalSceneCollection(routeStory);
      if (params.get("task_context") === "1" && routeScene && !routeScenes.some((item) => item.slug === routeScene)) {
        window.ZetTaskCapture.notice(`Recorded scene "${routeScene}" is unavailable. Showing an available scene.`);
      }
      state.selectedSceneSlug = routeScene && routeScenes.some((item) => item.slug === routeScene)
        ? routeScene
        : routeScenes[0]?.slug || null;
      state.requestedSceneContext = { storySlug: routeStory, sceneSlug: state.selectedSceneSlug || "" };
      saveStoredStoryContext();
    }
    if (params.get("page") === "render-review") {
      const preferredReviewKey = params.get("review_kind") === "scene"
        ? `scene:${params.get("story_slug") || ""}:${params.get("scene_slug") || ""}`
        : null;
      await activatePage("render-review", { skipAutosave: true, preferredReviewKey });
    } else if (params.get("page")) {
      await activatePage(params.get("page"), {
        skipAutosave: true,
        fromHistory: true,
        updateHistory: false,
        renderTargetId: params.get("render_target_id") || "main",
      });
    } else if (workspacePreferences) {
      await activatePage(state.lastWorkspacePages[state.workspace], { skipAutosave: true });
    } else if (!selectedPhaseReady()) {
      state.workspace = "character";
      await activatePage("onboarding", { skipAutosave: true });
    } else if (!storyContext.story) {
      state.workspace = "story";
      await activatePage("stories", { skipAutosave: true });
    } else {
      state.workspace = "story";
      await activatePage(storyContext.scene ? "scenes" : "stories", { skipAutosave: true });
    }
  } catch (error) {
    if (!isRequestCancellation(error)) assetStatus.textContent = error.message;
  } finally {
    document.body.dataset.dashboardReady = "true";
    scheduleProductionWorkSummary();
  }
}

function setUniverseMessage(id, message, kind = "info") {
  const target = document.getElementById(id);
  if (!target) return;
  target.textContent = message;
  target.className = `action-message ${kind}`.trim();
  target.hidden = !message;
}

async function loadUniverses() {
  const response = await fetch("/api/universes");
  if (!response.ok) throw new Error(`Unable to load universes (${response.status}).`);
  const payload = await response.json();
  const requested = new URLSearchParams(window.location.search).get("task_universe");
  if (requested && (payload.universes || []).some((item) => item.universe_id === requested)) {
    payload.selected_universe_id = requested;
  } else if (requested) {
    window.ZetTaskCapture.notice(`Recorded universe "${requested}" is unavailable. Showing the current universe.`);
  }
  state.universeId = payload.selected_universe_id || "";
  state.universes = payload.universes || [];
  universeSelect.replaceChildren(...state.universes.map((universe) => {
    const option = document.createElement("option");
    option.value = universe.universe_id;
    option.textContent = universe.name;
    return option;
  }));
  universeSelect.value = state.universeId;
}

async function loadUniverseList() {
  await loadUniverses();
  const list = document.querySelector("#universe-list");
  list.replaceChildren();
  for (const universe of state.universes) {
    const row = document.createElement("article");
    row.className = "universe-list-row";
    const details = document.createElement("div");
    const title = document.createElement("h2");
    title.textContent = universe.name;
    const style = document.createElement("p");
    style.textContent = universe.canonical_art_style || "No canonical art style set.";
    details.append(title, style);
    const actions = document.createElement("div");
    actions.className = "button-row compact";
    const settings = document.createElement("button");
    settings.type = "button";
    settings.textContent = "Settings";
    settings.className = "tab";
    settings.dataset.page = "universe-settings";
    settings.dataset.universeId = universe.universe_id;
    settings.addEventListener("click", () => runGuardedTransition(() => activatePage("universe-settings", {
      skipAutosave: true,
      universeId: universe.universe_id,
    })));
    actions.append(settings);
    if (universe.universe_id !== state.universeId) {
      const select = document.createElement("button");
      select.type = "button";
      select.textContent = "Select Universe";
      select.addEventListener("click", () => selectUniverse(universe.universe_id));
      actions.append(select);
    } else {
      const selected = document.createElement("span");
      selected.textContent = "Selected";
      actions.append(selected);
    }
    row.append(details, actions);
    list.append(row);
  }
  if (!state.universes.length) list.textContent = "No universes yet.";
}

async function loadUniverseSettings(universeId) {
  const response = await fetch(`/api/universes/${encodeURIComponent(universeId)}`);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "Unable to load universe settings.");
  const universe = payload.universe;
  state.universeSettingsId = universe.universe_id;
  state.savedUniverseArtStyle = universe.canonical_art_style || "";
  universeSettingsArtStyle.value = state.savedUniverseArtStyle;
  document.querySelector("#universe-settings-title").textContent = `${universe.name} Settings`;
  document.querySelector("#universe-settings-select").hidden = universe.universe_id === state.universeId;
  setUniverseMessage("universe-settings-message", "", "");
}

async function saveUniverseSettings() {
  const response = await fetch(`/api/universes/${encodeURIComponent(state.universeSettingsId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ canonical_art_style: universeSettingsArtStyle.value }),
  });
  const payload = await response.json();
  if (!response.ok) {
    setUniverseMessage("universe-settings-message", payload.detail || "Unable to save universe settings.", "error");
    return false;
  }
  state.savedUniverseArtStyle = payload.universe.canonical_art_style || "";
  setUniverseMessage("universe-settings-message", "Settings saved.", "success");
  return true;
}

async function selectUniverse(universeId) {
  const response = await fetch("/api/universes/select", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Zet-Universe": state.universeId },
    body: JSON.stringify({ universe_id: universeId }),
  });
  const payload = await response.json();
  if (!response.ok) {
    setUniverseMessage("universes-message", payload.detail || "Unable to select universe.", "error");
    return;
  }
  window.location.reload();
}



universeSettingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await saveUniverseSettings();
});









// Main-dashboard context is an allowlist, never a copy of application state.


document.querySelector("#image-generation-review-task").addEventListener("click",()=>void window.ZetTaskCapture.open());

sceneCandidateSource.addEventListener("change", async () => {
  state.selectedSceneCandidateSource = sceneCandidateSource.value;
  state.selectedSceneCandidateId = null;
  await loadSceneCandidates();
});
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
  state.onboardingMode = null;
  state.character = requestedCharacter;
  state.phase = null;
  saveStoredContext();
  state.selectedAssetId = null;
  state.selectedPromptReviewAskId = null;
  state.selectedRenderReviewKey = null;
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
  if (document.querySelector("#scene-appearances-page").classList.contains("active")) {
    await loadSceneAppearances();
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
  await loadWorkspaceSummary();
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
  state.onboardingMode = null;
  state.phase = requestedPhase;
  saveStoredContext();
  updateHeaderFitmentPreview();
  state.selectedAssetId = null;
  state.selectedPromptReviewAskId = null;
  state.selectedRenderReviewKey = null;
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
  if (document.querySelector("#scene-appearances-page").classList.contains("active")) {
    await loadSceneAppearances();
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
  await loadWorkspaceSummary();
});
deletePhaseButton.addEventListener("click", async () => {
  if (!state.character || !state.phase) return;
  if (!window.confirm(`Move ${state.character} / ${state.phase} and all templates and character assets to the library deleted folder?`)) return;
  deletePhaseButton.disabled = true;
  showActionMessage("Moving phase to deleted storage...");
  try {
    const payload = await fetchJson(`/api/character-phase?${currentQuery().toString()}`, { method: "DELETE" });
    state.phase = null;
    await refreshCurrentContext();
    if (document.querySelector("#costumes-page").classList.contains("active") && state.phase) await loadCostumes();
    showActionMessage(payload.message || "Character phase moved to deleted storage.");
  } catch (error) {
    showActionMessage(error.message, "error");
  } finally {
    deletePhaseButton.disabled = false;
  }
});
localRunAllButton.addEventListener("click", async () => {
  localRunAllButton.disabled = true;
  localRunAllStatus.textContent = "Starting or reconnecting to the library-wide run…";
  localRunAllStatus.hidden = false;
  try {
    const campaign = await fetchJson("/api/local/run-all-remaining", { method: "POST", bindToPage: false });
    state.localRunAllCampaignId = campaign.campaign_id;
    if (state.localRunAllTimer) window.clearTimeout(state.localRunAllTimer);
    renderLocalRunAllStatus(campaign);
    localRunAllButton.disabled = false;
    void pollLocalRunAll(campaign.campaign_id);
  } catch (error) {
    localRunAllStatus.textContent = `Could not start run-all: ${error.message}`;
    localRunAllStatus.hidden = false;
    localRunAllButton.disabled = false;
  }
});
headerStorySelect.addEventListener('change',async()=>{
  const params=new URLSearchParams({page:'narrative',workspace:'story',universe_id:state.universeId});
  if(headerStorySelect.value)params.set('story',headerStorySelect.value);
  history.pushState({},'','/?'+params);await activatePage('narrative',{updateHistory:false});
});
headerSceneSelect.addEventListener('change',async()=>{
  const params=new URLSearchParams({page:'narrative',workspace:'story',universe_id:state.universeId,story:headerStorySelect.value});
  if(headerSceneSelect.value)params.set('scene',headerSceneSelect.value);
  history.pushState({},'','/?'+params);await activatePage('narrative',{updateHistory:false});
});
promptAnalysisDialog.addEventListener("close", () => {
  promptAnalysisFrame.removeAttribute("src");
  state.promptAnalysisDialogContext = null;
  showPromptAnalysisActionMessage("");
});
onboardingCharacter.addEventListener("input", () => {
  updateOnboardingHelperPrompt();
  if (state.onboardingMode) renderOnboarding();
});
onboardingPhase.addEventListener("input", () => {
  updateOnboardingHelperPrompt();
  if (state.onboardingMode) renderOnboarding();
});
templateManualSelect.addEventListener("change", () => {
  state.selectedTemplateManual = templateManualSelect.value;
  renderTemplateManual();
});
templateManualCopy.addEventListener("click", () => {
  const manual = state.templateManuals.find((item) => item.id === state.selectedTemplateManual);
  if (manual) copyText(manual.markdown, "Template manual copied.");
});
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
identityKeySource.addEventListener("change", () => {
  state.identityKeySourceLocalKey = identityKeySource.value || null;
  state.identityKeySourceAssetId = null;
  state.identityKeyPreview = null;
  identityKeyCreatePreview.disabled = !state.identityKeySourceLocalKey;
  identityKeySave.disabled = !state.identityKeySourceLocalKey;
});
sceneAppearanceSave.addEventListener("click", saveSceneAppearance);
zineStorySelect.addEventListener("change", async () => {
  state.zineStorySlug = zineStorySelect.value || null;
  await loadZineStorySources();
});
builderImagePickerCharacter.addEventListener("change", () => loadImagePickerReferences(builderImagePicker));
builderImagePickerEntity.addEventListener("change", async () => {
  const payload = await fetchJson(`/api/entity-library/variants?entity_id=${encodeURIComponent(builderImagePickerEntity.value)}`);
  setSelectOptionsWithLabels(builderImagePickerVariant, [
    { value: "", label: "All variants" },
    ...(payload.variants || []).map((item) => ({ value: item.variant_id, label: `${item.name} · ${item.variant_type}` })),
  ]);
  await loadImagePickerReferences(builderImagePicker);
});
for (const control of [builderImagePickerVariant, builderImagePickerSet, builderImagePickerFacet]) {
  control.addEventListener("change", () => loadImagePickerReferences(builderImagePicker));
}
builderImagePickerMode.addEventListener("change", () => loadImagePickerReferences(builderImagePicker));
entityLibraryFile.addEventListener("change", () => {
  state.entityLibraryImportBlob = null;
  entityLibraryPaste.textContent = entityLibraryFile.files?.[0]?.name || "Or click here and paste an image";
  entityLibraryImport.disabled = !entityLibraryImportGeneration && !(entityLibraryFile.files?.[0] || state.entityLibraryImportBlob) || !entityLibraryNewLabel.value.trim();
});
entityLibraryNewLabel.addEventListener("input", () => {
  entityLibraryImport.disabled = !entityLibraryImportGeneration && !(entityLibraryFile.files?.[0] || state.entityLibraryImportBlob) || !entityLibraryNewLabel.value.trim();
});
entityLibraryImport.addEventListener("click", async () => {
  const file = state.entityLibraryImportBlob || entityLibraryFile.files?.[0];
  const label = entityLibraryNewLabel.value.trim();
  if ((!file && !entityLibraryImportGeneration) || !label) return;
  entityLibraryImport.disabled = true;
  entityLibraryImportStatus.textContent = "Adding image…";
  try {
    if (entityLibraryImportGeneration) {
      const { requestId, index } = entityLibraryImportGeneration;
      const payload = await fetchJson("/api/image-generation/jobs/" + encodeURIComponent(requestId) + "/images/" + index + "/import", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label, entity_id: entityLibraryGeneratedEntity.value,
          reference_role: entityLibraryGeneratedRole.value, provenance: entityLibraryGeneratedProvenance.value.trim() }),
      });
      entityLibraryImportGeneration = null;
      entityLibraryImportDialog.close();
      entityLibraryFile.value = "";
      state.entityLibraryImportBlob = null;
      entityLibraryPaste.textContent = "Or click here and paste an image";
      entityLibraryNewLabel.value = "";
      entityLibraryGeneratedProvenance.value = "";
      entityLibraryGenerationPrompts.hidden = true;
      entityLibraryImportStatus.textContent = payload.duplicate ? "This generated image is already in the library." : "Image added.";
      await activatePage("auxiliary-resources", { skipAutosave: true });
      await loadEntityLibraryInventory();
      if (payload.asset?.asset_id) await selectEntityLibraryAsset(payload.asset.asset_id);
      return;
    }
    const generated = Boolean(entityLibraryGeneratedEntity.value);
    entityLibraryGenerationPrompts.hidden = true;
    const endpoint = generated ? "/api/entity-library/assets/generated" : "/api/entity-library/assets";
    const query = new URLSearchParams({ label });
    if (generated) {
      query.set("entity_id", entityLibraryGeneratedEntity.value);
      query.set("reference_role", entityLibraryGeneratedRole.value);
      query.set("provenance", entityLibraryGeneratedProvenance.value.trim());
    }
    const response = await fetch(`${endpoint}?${query}`, {
      method: "POST", headers: { "Content-Type": file.type || "application/octet-stream" }, body: file,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Could not add the image.");
    entityLibraryFile.value = "";
    state.entityLibraryImportBlob = null;
    entityLibraryPaste.textContent = "Or click here and paste an image";
    entityLibraryNewLabel.value = "";
    entityLibraryGeneratedProvenance.value = "";
    entityLibraryImportStatus.textContent = payload.message || "Image added.";
    await loadEntityLibraryInventory();
    if (payload.asset?.asset_id) await selectEntityLibraryAsset(payload.asset.asset_id);
  } catch (error) {
    entityLibraryImportStatus.textContent = error.message;
  } finally {
    entityLibraryImport.disabled = (!entityLibraryImportGeneration && !(entityLibraryFile.files?.[0] || state.entityLibraryImportBlob)) || !entityLibraryNewLabel.value.trim();
  }
});
entityLibraryReplacementFile.addEventListener("change", () => {
  state.entityLibraryReplacementBlob = null;
  entityLibraryReplacementPaste.textContent = entityLibraryReplacementFile.files?.[0]?.name || "Or click here and paste a replacement image";
  entityLibraryReplace.disabled = !entityLibrarySelectedAsset || !(entityLibraryReplacementFile.files?.[0] || state.entityLibraryReplacementBlob);
});
entityLibraryReplace.addEventListener("click", async () => {
  const file = state.entityLibraryReplacementBlob || entityLibraryReplacementFile.files?.[0];
  if (!file || !entityLibrarySelectedAsset) return;
  entityLibraryReplace.disabled = true;
  try {
    const response = await fetch(`/api/entity-library/assets/${encodeURIComponent(entityLibrarySelectedAsset.asset_id)}/image`, {
      method: "PUT", headers: { "Content-Type": file.type || "application/octet-stream" }, body: file,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Could not replace the image.");
    entityLibraryReplacementFile.value = "";
    state.entityLibraryReplacementBlob = null;
    entityLibraryReplacementPaste.textContent = "Or click here and paste a replacement image";
    await loadEntityLibraryInventory();
    await selectEntityLibraryAsset(payload.asset.asset_id);
  } catch (error) {
    window.alert(error.message);
  } finally {
    entityLibraryReplace.disabled = !entityLibrarySelectedAsset || !(entityLibraryReplacementFile.files?.[0] || state.entityLibraryReplacementBlob);
  }
});
for (const [zone, kind] of [[entityLibraryPaste, "import"], [entityLibraryReplacementPaste, "replacement"]]) {
  zone.addEventListener("paste", (event) => {
    const blob = imageBlobFromPasteEvent(event);
    if (!blob) return;
    event.preventDefault();
    if (kind === "import") {
      state.entityLibraryImportBlob = blob;
      entityLibraryFile.value = "";
      entityLibraryPaste.textContent = `${blob.name || "Pasted image"} ready`;
      entityLibraryImport.disabled = !entityLibraryNewLabel.value.trim();
    } else {
      state.entityLibraryReplacementBlob = blob;
      entityLibraryReplacementFile.value = "";
      entityLibraryReplacementPaste.textContent = `${blob.name || "Pasted image"} ready`;
      entityLibraryReplace.disabled = !entityLibrarySelectedAsset;
    }
  });
  zone.addEventListener("dragover", (event) => {
    event.preventDefault();
    zone.classList.add("drag-over");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    zone.classList.remove("drag-over");
    const blob = event.dataTransfer?.files?.[0];
    if (!blob?.type.startsWith("image/")) return;
    if (kind === "import") {
      state.entityLibraryImportBlob = blob;
      entityLibraryFile.value = "";
      entityLibraryPaste.textContent = `${blob.name || "Image"} ready`;
      entityLibraryImport.disabled = !entityLibraryNewLabel.value.trim();
    } else {
      state.entityLibraryReplacementBlob = blob;
      entityLibraryReplacementFile.value = "";
      entityLibraryReplacementPaste.textContent = `${blob.name || "Image"} ready`;
      entityLibraryReplace.disabled = !entityLibrarySelectedAsset;
    }
  });
}
builderImagePickerIncludeBase.addEventListener("change", () => loadImagePickerReferences(builderImagePicker));
builderImagePickerSource.addEventListener("change", () => loadImagePickerReferences(builderImagePicker));
builderImagePickerCategory.addEventListener("change", () => loadImagePickerReferences(builderImagePicker));
builderImagePickerStatusFilter.addEventListener("change", () => loadImagePickerReferences(builderImagePicker));
builderImagePickerSearch.addEventListener("input", () => {
  state.builderImagePickerSearch = builderImagePickerSearch.value || "";
  loadImagePickerReferences(builderImagePicker);
});
builderImagePickerRefresh.addEventListener("click", () => loadImagePickerReferences(builderImagePicker));
builderImagePickerClose.addEventListener("click", () => {
  builderImagePickerModal.close();
});
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
copyPromptButton.addEventListener("click", () => copyText(state.promptReviewDetail?.prompt || "", "Prompt copied."));
promptReviewRenderConsole.addEventListener("click", async () => {
  const askId = state.promptReviewDetail?.task?.ask_id;
  if (!askId) return;
  await activatePage("render-console", { skipAutosave: true, preferredAskId: askId });
});
promptReviewPrev.addEventListener("click", () => {
  selectAdjacentAssetTask(state.promptReviewTasks, state.selectedPromptReviewAskId, -1, selectPromptReviewTask);
});
promptReviewNext.addEventListener("click", () => {
  selectAdjacentAssetTask(state.promptReviewTasks, state.selectedPromptReviewAskId, 1, selectPromptReviewTask);
});
renderReviewPrev.addEventListener("click", () => {
  const index = state.renderReviewTasks.findIndex((task) => task.review_key === state.selectedRenderReviewKey);
  if (index > 0) {
    selectRenderReview(state.renderReviewTasks[index - 1].review_key);
  }
});
renderReviewNext.addEventListener("click", () => {
  const index = state.renderReviewTasks.findIndex((task) => task.review_key === state.selectedRenderReviewKey);
  if (index >= 0 && index < state.renderReviewTasks.length - 1) {
    selectRenderReview(state.renderReviewTasks[index + 1].review_key);
  }
});

renderConsoleReviewPrompt.addEventListener("click", async () => {
  const askId = state.renderConsoleDetail?.task?.ask_id;
  if (!askId) return;
  await activatePage("prompt-review", { skipAutosave: true, preferredAskId: askId });
});
renderConsoleCopyPrompt.addEventListener("click", async () => {
  await writeClipboardText(state.renderConsoleDetail?.prompt || "");
  showRenderConsoleMessage("Prompt copied.");
});
imageCatalogBulkClear.addEventListener("click", () => {
  state.selectedImageCatalogIds = [];
  renderImageCatalog();
});
localImageReviewPrev.addEventListener("click", () => {
  selectAdjacentAssetTask(state.localImageReviewTasks, state.selectedLocalImageReviewAskId, -1, selectLocalImageReviewTask);
});
localImageReviewNext.addEventListener("click", () => {
  selectAdjacentAssetTask(state.localImageReviewTasks, state.selectedLocalImageReviewAskId, 1, selectLocalImageReviewTask);
});
renderConsolePrev.addEventListener("click", () => {
  selectAdjacentAssetTask(state.renderConsoleTasks, state.selectedRenderConsoleAskId, -1, selectRenderConsoleTask);
});
renderConsoleNext.addEventListener("click", () => {
  selectAdjacentAssetTask(state.renderConsoleTasks, state.selectedRenderConsoleAskId, 1, selectRenderConsoleTask);
});
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
universeCreateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = universeCreateForm.querySelector('[type="submit"]');
  submit.disabled = true;
  try {
    const response = await fetch("/api/universes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: document.querySelector("#universe-create-name").value,
        canonical_art_style: document.querySelector("#universe-create-art-style").value,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Unable to create universe.");
    await loadUniverses();
    state.universeSettingsId = payload.universe.universe_id;
    await activatePage("universe-settings", { skipAutosave: true, universeId: state.universeSettingsId });
  } catch (error) {
    setUniverseMessage("universe-create-message", error.message, "error");
  } finally {
    submit.disabled = false;
  }
});
document.querySelector("#universe-settings-select").addEventListener("click", () => {
  void runGuardedTransition(() => selectUniverse(state.universeSettingsId));
});
universeSelect.addEventListener("change", async () => {
  const nextUniverseId = universeSelect.value;
  if (!nextUniverseId || nextUniverseId === state.universeId) return;
  universeSelect.disabled = true;
  try {
    const changed = await runGuardedTransition(() => selectUniverse(nextUniverseId));
    if (!changed) universeSelect.value = state.universeId;
  } catch (error) {
    universeSelect.value = state.universeId;
    showActionMessage(`Unable to change universe: ${error.message}`, "error");
  } finally {
    universeSelect.disabled = false;
  }
});
window.addEventListener('popstate',()=>{
  const page=new URLSearchParams(location.search).get('page') || 'onboarding';
  void activatePage(page,{skipAutosave:true,fromHistory:true,updateHistory:false}).catch(error=>showActionMessage(error.message,'error'));
});
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && document.body.dataset.dashboardReady === "true") {
    void refreshProductionWorkSummary();
  } else if (document.hidden && state.productionWorkTimer) {
    window.clearTimeout(state.productionWorkTimer);
    state.productionWorkTimer = null;
  }
});
window.ZetTaskCapture.registerProvider(() => {
  const page = activePageName() || "onboarding";
  const selections = {};
  const source = new URL("/", window.location.origin);
  source.searchParams.set("page", page);
  source.searchParams.set("task_context", "1");
  if (state.universeId) source.searchParams.set("task_universe", state.universeId);
  if (CHARACTER_PAGES.has(page) || LOCAL_ASSET_PAGES.has(page)) {
    const selection = (id, available, select) => {
      if (!id) return { state: document.body.dataset.dashboardReady === "true" ? "absent" : "loading" };
      return { state: available ? "selected" : "unavailable", id,
        label: select.value === id ? select.selectedOptions[0]?.textContent || id : id };
    };
    selections.character = selection(state.character, state.characters.includes(state.character), characterSelect);
    selections.phase = selection(state.phase, (state.phasesByCharacter[state.character] || []).includes(state.phase), phaseSelect);
    if (state.character) source.searchParams.set("character", state.character);
    if (state.phase) source.searchParams.set("phase", state.phase);
  }
  const local = LOCAL_ASSET_PAGES.has(page) ? window.ZetLocalAssetPipeline?.taskContext(page)
    : page === "local-batch-status" ? window.ZetLocalBatchStatus?.taskContext() : null;
  if (local) {
    Object.assign(selections, local.selections);
    for (const [key, value] of Object.entries(local.parameters)) source.searchParams.set(key, value);
  }
  if (STORY_PAGES.has(page) || PRODUCTION_PAGES.has(page)) {
    const storyId = page === "scene-candidates" ? state.selectedSceneCandidateStorySlug || state.selectedStorySlug
      : page === "zine" ? state.zineStorySlug : state.selectedStorySlug;
    const story = state.stories.find((item) => item.slug === storyId);
    selections.story = storyId ? {state:story ? "selected" : "unavailable",id:storyId,label:story?.title || storyId} : {state:"absent"};
    if (storyId) source.searchParams.set("story_slug",storyId);
    if (page === "zine" && state.selectedZineSlug) {
      const id = state.selectedZineSlug;
      selections.zine = {state:state.zineLoadState,id,label:state.zineDocument?.zine?.slug === id ? state.zineDocument.metadata?.zine_name || id : id};
      source.searchParams.set("task_zine",id);
    }
    if (["scenes", "scene-builder", "scene-batches", "prompt-review"].includes(page)) {
      const id = state.selectedSceneSlug;
      const scene = canonicalSceneCollection(storyId).find((item) => item.slug === id);
      selections.scene = id ? {state:scene ? "selected" : "unavailable",id,label:scene?.title || id} : {state:"absent"};
      if (id) source.searchParams.set("scene_slug",id);
    }
    if (page === "scene-builder") {
      const ready = state.sceneBuilderLoadState === "selected" && state.loadedBuilderContext.storySlug === storyId && state.loadedBuilderContext.sceneSlug === state.selectedSceneSlug;
      const id = ready ? state.activeBuilderRenderTarget : state.requestedBuilderTargetId;
      const target = ready ? state.sceneBuilder?.subscenes?.find((item) => item.id === id) : null;
      selections.render_target = {state:ready ? id === "main" || target ? "selected" : "unavailable" : state.sceneBuilderLoadState === "unavailable" ? "unavailable" : "loading",id,label:target?.name || target?.title || id};
      if (target) selections.subscene = {...selections.render_target};
      source.searchParams.set("render_target_id",id);
      const element = ready ? state.sceneBuilder?.scene_elements?.find((item) => item.id === state.selectedBuilderElementId) : null;
      if (element) { selections.editor_element = {state:"selected",id:element.id,label:element.name || element.id}; source.searchParams.set("task_element",element.id); }
      if (element) {
        for (const name of ["character","phase","costume"]) {
          if (typeof element[name] === "string" && element[name]) selections[name] = {state:"selected",id:element[name],label:element[name]};
        }
      }
    }
    if (page === "scene-candidates") {
      const id = state.selectedSceneCandidateId || (sceneCandidateRestorePending ? taskStoryRoute.get("task_candidate") : null);
      const candidate = state.sceneCandidates.find((item) => item.candidate_id === id);
      if (id) {
        selections.candidate = {state:state.sceneCandidatesLoadState === "selected" ? candidate ? "selected" : "unavailable" : state.sceneCandidatesLoadState,id,label:candidate?.title || id};
        source.searchParams.set("task_candidate",id);
      }
      if (state.selectedSceneCandidateSource) source.searchParams.set("task_source",state.selectedSceneCandidateSource);
    }
    if (page === "scene-batches") {
      const batch = window.SceneBatches?.taskContext();
      if (batch) { Object.assign(selections,batch.selections); for (const [key,value] of Object.entries(batch.parameters)) source.searchParams.set(key,value); }
    }
  }
  if (page === "image-generation") {
    const slotIndex = imageGenerationReview.open ? imageGenerationReviewIndex : imageGenerationSelectedSlot;
    const result = imageGenerationResult(slotIndex);
    if (result) {
      const requestId = result.assignment.requestId;
      selections.run = {state:"selected",id:requestId,label:requestId};
      selections.candidate = {state:"selected",id:`${requestId}:${result.assignment.index}`,label:`Result ${result.assignment.index + 1} · slot ${slotIndex + 1}`};
    }
  }
  return { page_id: page,
    page_name: LOCAL_ASSET_PAGES.has(page) ? document.querySelector("#local-pipeline-title").textContent.trim()
      : document.querySelector(`#${page}-page h1`)?.textContent?.trim() || page,
    source_url: source.href, universe_id: state.universeId || null, selections, workflow_status: local?.workflow_status || null };
});
window.zetQuickCharacterWizard = {
  fetchJson,
  selectedAsset: () => entityLibrarySelectedAsset,
  universe: () => state.universeId,
  fileUrl,
  refreshLibrary: loadEntityLibraryInventory,
  openAsset: selectEntityLibraryAsset,
  openSet: async (setId) => { await loadEntityLibraryInventory(); activateInventoryView("sets"); renderEntityLibraryOrganizer("sets", setId); },
  openLibraryPicker: async (onSelect) => {
    quickCharacterLibrarySelection = onSelect;
    // The shared library dialog is independent of the active workspace.
    const parent = builderImagePickerModal.parentNode;
    const next = builderImagePickerModal.nextSibling;
    document.body.append(builderImagePickerModal);
    builderImagePickerModal.addEventListener("close", () => parent.insertBefore(builderImagePickerModal, next), { once: true });
    builderImagePickerSearch.value = "";
    builderImagePickerMode.value = "asset";
    builderImagePickerModal.showModal();
    await loadEntityLibraryPickerFilters();
    await loadImagePickerReferences(builderImagePicker);
  },
};
builderImagePickerModal.addEventListener("close", () => { quickCharacterLibrarySelection = null; });

async function saveSceneAppearance() {
  const selected = selectedSceneAppearance();
  const appearanceId = sceneAppearanceId.value.trim();
  const payload = {
    appearance_id: appearanceId,
    name: sceneAppearanceName.value.trim(),
    costume: sceneAppearanceCostume.value,
    instructions: sceneAppearanceInstructions.value.trim(),
    supporting_references: [],
  };
  try {
    payload.supporting_references = parseSceneAppearanceReferences();
  } catch (error) {
    showSceneAppearanceMessage(error.message, "error");
    return;
  }
  showSceneAppearanceMessage(selected ? "Updating Scene Appearance..." : "Creating Scene Appearance...");
  sceneAppearanceSave.disabled = true;
  try {
    const path = selected
      ? `/api/scene-appearances/${encodeURIComponent(selected.appearance_id)}?${currentQuery().toString()}`
      : `/api/scene-appearances?${currentQuery().toString()}`;
    const result = await fetchJson(path, {
      method: selected ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.sceneAppearances = result.scene_appearances || state.sceneAppearances;
    state.assets = result.assets || state.assets;
    state.selectedSceneAppearanceId = result.scene_appearance?.appearance_id || appearanceId;
    selectSceneAppearance(state.selectedSceneAppearanceId);
    renderAssetTable();
    showSceneAppearanceMessage(result.message || "Scene Appearance saved.");
  } catch (error) {
    showSceneAppearanceMessage(error.message, "error");
  } finally {
    sceneAppearanceSave.disabled = false;
  }
}

window.addEventListener('beforeunload',event=>{
  if ((state.savedBaselines.sourceEditor && sourceEditorSnapshot()!==state.savedBaselines.sourceEditor)
      || (state.savedBaselines.zine && zineSnapshot()!==state.savedBaselines.zine)
      || (state.savedBaselines.settings && settingsSnapshot()!==state.savedBaselines.settings)) {
    event.preventDefault();event.returnValue='';
  }
});
main();



// A narrow dashboard bridge keeps wizard presentation in its own module.
