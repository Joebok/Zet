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

const promptReviewSceneBuilder = document.querySelector("#prompt-review-scene-builder");

const settingAiSceneBuilderModel = document.querySelector("#setting-ai-scene-builder-model");

const storySaveState = document.querySelector("#story-save-state");

const sceneSaveState = document.querySelector("#scene-save-state");

const storyStatus = document.querySelector("#story-status");

const storyOverviewMetrics = document.querySelector("#story-overview-metrics");

const storyOverviewScenes = document.querySelector("#story-overview-scenes");

const storyPhoneViewer = document.querySelector("#story-phone-viewer");

const storyPhoneViewerTitle = document.querySelector("#story-phone-viewer-title");

const storyPhoneViewerState = document.querySelector("#story-phone-viewer-state");

const storyPhoneViewerImage = document.querySelector("#story-phone-viewer-image");

const storyPhonePrevious = document.querySelector("#story-phone-previous");

const storyPhoneNext = document.querySelector("#story-phone-next");

const storyPhonePosition = document.querySelector("#story-phone-position");

const storyMessage = document.querySelector("#story-message");

const storyTableBody = document.querySelector("#story-table tbody");

const storyEditorTitle = document.querySelector("#story-editor-title");

const storySave = document.querySelector("#story-save");

const storyView = document.querySelector("#story-view");

const storyScenes = document.querySelector("#story-scenes");

const storyRenameTitle = document.querySelector("#story-rename-title");

const storyRename = document.querySelector("#story-rename");

const storyDelete = document.querySelector("#story-delete");

const storyNewTitle = document.querySelector("#story-new-title");

const storyCreate = document.querySelector("#story-create");

const storyValidation = document.querySelector("#story-validation");

const storyText = document.querySelector("#story-text");

const storySettingsJson = document.querySelector("#story-settings-json");

const storySettingsFields = document.querySelector("#story-settings-fields");

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

const sceneRenameTitle = document.querySelector("#scene-rename-title");

const sceneRename = document.querySelector("#scene-rename");

const sceneMoveStory = document.querySelector("#scene-move-story");

const sceneMove = document.querySelector("#scene-move");

const sceneValidation = document.querySelector("#scene-validation");

const sceneImagePanel = document.querySelector("#scene-image-panel");

const sceneImagePreview = document.querySelector("#scene-image-preview");

const sceneImageCandidateLink = document.querySelector("#scene-image-candidate-link");

const sceneBuilderStatus = document.querySelector("#scene-builder-status");

const sceneBuilderPrevious = document.querySelector("#scene-builder-previous");

const sceneBuilderNext = document.querySelector("#scene-builder-next");

const sceneBuilderMessage = document.querySelector("#scene-builder-message");

const sceneBuilderPanel = document.querySelector("#scene-builder-panel");

const sceneBuilderContextDialog = document.querySelector("#scene-builder-context-dialog");

const sceneBuilderContextClose = document.querySelector("#scene-builder-context-close");

const sceneBuilderContextContent = document.querySelector("#scene-builder-context-content");

const sceneBuilderInterviewModal = document.querySelector("#scene-builder-interview-modal");

const sceneBuilderInterviewClose = document.querySelector("#scene-builder-interview-close");

const sceneBuilderInterviewStatus = document.querySelector("#scene-builder-interview-status");

const sceneBuilderInterviewNarrativeLabel = document.querySelector("#scene-builder-interview-narrative-label");

const sceneBuilderInterviewNarrative = document.querySelector("#scene-builder-interview-narrative");

const sceneBuilderInterviewQuestions = document.querySelector("#scene-builder-interview-questions");

const sceneBuilderInterviewCancel = document.querySelector("#scene-builder-interview-cancel");

const sceneBuilderInterviewNext = document.querySelector("#scene-builder-interview-next");

const sceneBuilderInterviewApply = document.querySelector("#scene-builder-interview-apply");

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

const builderElementNewAux = document.querySelector("#builder-element-new-aux");

const builderElementNewAuxForm = document.querySelector("#builder-element-new-aux-form");

const builderElementNewAuxLabel = document.querySelector("#builder-element-new-aux-label");

const builderElementNewAuxCancel = document.querySelector("#builder-element-new-aux-cancel");

const builderElementNewAuxSave = document.querySelector("#builder-element-new-aux-save");

const builderElementNewAuxStatus = document.querySelector("#builder-element-new-aux-status");

const builderElementSceneSection = document.querySelector("#builder-element-scene-section");

const builderElementSubsceneSection = document.querySelector("#builder-element-subscene-section");

const builderElementSceneName = document.querySelector("#builder-element-scene-name");

const builderElementCancel = document.querySelector("#builder-element-cancel");

const builderElementAdd = document.querySelector("#builder-element-add");

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

const sceneText = document.querySelector("#scene-text");

const scenePickerCharacter = document.querySelector("#scene-picker-character");

const scenePickerSearch = document.querySelector("#scene-picker-search");

const scenePickerRefresh = document.querySelector("#scene-picker-refresh");

const scenePickerStatus = document.querySelector("#scene-picker-status");

const scenePickerTableBody = document.querySelector("#scene-picker-table tbody");

function builderOptions(name) {
  return state.sceneBuilderOptions?.[name] || [];
}

function builderOptionHtml(name, selected = "") {
  const options = builderOptions(name);
  const values = name === "aspect_ratio" && selected && !options.includes(selected) ? [...options, selected] : options;
  return values.map((value) => `<option value="${escapeHtml(value)}"${value === selected ? " selected" : ""}>${escapeHtml(value)}</option>`).join("");
}

function builderHelpPath(path) {
  return String(path || "").replace(/\.\d+(?=\.|$)/g, "[]");
}

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

function renderStoryPhoneViewer() {
  const scenes = state.workspaceSummary.story?.scenes || [];
  const scene = selectedStoryOverviewScene();
  storyPhoneViewerImage.replaceChildren();
  storyPhoneViewerTitle.textContent = scene?.title || "No scene selected";
  storyPhoneViewerState.textContent = scene?.image_state || "Not rendered";
  storyPhoneViewerState.className = `status-badge ${scene?.candidate_pending ? "review" : scene?.image_path ? "ready" : ""}`;
  const index = scene ? scenes.findIndex((item) => item.slug === scene.slug) : -1;
  storyPhonePosition.textContent = index >= 0 ? `${index + 1} of ${scenes.length}` : "No scenes";
  storyPhonePrevious.disabled = index <= 0;
  storyPhoneNext.disabled = index < 0 || index >= scenes.length - 1;
  if (!scene?.image_path) {
    storyPhoneViewerImage.textContent = scene ? "No image has been rendered for this scene." : "Add a scene to begin.";
    return;
  }
  const image = document.createElement("img");
  image.src = fileUrl(scene.image_path, `${scene.slug}|${scene.image_state}`);
  image.alt = `${scene.title} ${scene.image_state.toLowerCase()} image`;
  storyPhoneViewerImage.append(enableFullscreenImage(image, () => ({
    storySlug: state.selectedStorySlug,
    sceneSlug: scene.slug,
    scenes,
    document: {
      candidate_pending: scene.candidate_pending,
      story: { slug: state.selectedStorySlug },
      scene: { slug: scene.slug },
    },
  })));
}

function renderStoryOverview() {
  const summary = state.workspaceSummary.story;
  storyOverviewMetrics.replaceChildren();
  storyOverviewScenes.replaceChildren();
  if (!summary?.story_slug) {
    renderStoryPhoneViewer();
    storyOverviewMetrics.append(overviewMetric(0, "Scenes"));
    return;
  }
  renderStoryPhoneViewer();
  storyOverviewMetrics.append(
    overviewMetric(summary.scene_count, "Scenes"),
    overviewMetric(summary.locked_count, "Locked images"),
    overviewMetric(summary.candidate_count, "Candidates to review"),
    overviewMetric(summary.unrendered_count, "Not rendered"),
  );
  for (const scene of summary.scenes || []) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "story-overview-scene";
    card.classList.toggle("selected", scene.slug === state.selectedSceneSlug);
    card.dataset.sceneSlug = scene.slug;
    if (scene.image_path) {
      const image = document.createElement("img");
      image.src = fileUrl(scene.image_path, `${scene.slug}|${scene.image_state}`);
      image.alt = `${scene.title} ${scene.image_state.toLowerCase()} image`;
      card.append(image);
    } else {
      const empty = document.createElement("div");
      empty.className = "story-overview-scene-empty";
      empty.textContent = "No image";
      card.append(empty);
    }
    const title = document.createElement("strong");
    title.textContent = scene.title;
    const imageState = document.createElement("span");
    imageState.textContent = scene.candidate_pending ? `● ${scene.image_state}` : scene.image_state;
    card.append(title, imageState);
    card.addEventListener("click", () => void selectStoryScene(state.selectedStorySlug, scene.slug, {
      destination: "scene-builder",
    }));
    storyOverviewScenes.append(card);
  }
}

async function startNewStory() {
  state.workspace = "story";
  await activatePage("stories", { skipAutosave: true });
  storyNewTitle.focus();
}

async function startNewScene() {
  state.workspace = "story";
  if (!state.selectedStorySlug) {
    await activatePage("stories", { skipAutosave: true });
    storyNewTitle.focus();
    return;
  }
  await activatePage("scenes", { skipAutosave: true });
  sceneNewName.focus();
}

function sceneBuilderSnapshot() {
  if (state.sceneBuilder && activePageName() === "scene-builder") {
    builderSyncControls();
  }
  return JSON.stringify(state.sceneBuilder || null);
}

function builderSubsceneFromData(data, targetId) {
  return (data?.subscenes || []).find((item) => item.id === targetId) || null;
}

function builderTargetIsDirty(targetId = state.activeBuilderRenderTarget || "main") {
  if (!state.savedBaselines.sceneBuilder) return false;
  if (targetId === "main") return sceneBuilderSnapshot() !== state.savedBaselines.sceneBuilder;
  builderSyncControls();
  const baseline = savedSceneBuilderData();
  return JSON.stringify({
    subscene: builderSubsceneFromData(state.sceneBuilder, targetId),
    dialogue: builderDialogueRowsForTarget(state.sceneBuilder, targetId),
  }) !== JSON.stringify({
    subscene: builderSubsceneFromData(baseline, targetId),
    dialogue: builderDialogueRowsForTarget(baseline, targetId),
  });
}

async function saveStoryBeforeNavigation() {
  if (!state.selectedStorySlug || !state.storyDetail) {
    return true;
  }
  return saveStory();
}

async function saveSceneBeforeNavigation() {
  if (!state.selectedStorySlug || !state.selectedSceneSlug || !sceneDocumentMatches()) {
    return true;
  }
  setSaveState(sceneSaveState, "Saving", "saving");
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}`, {
      method: "PUT",
      headers: { "Content-Type": "text/markdown; charset=utf-8" },
      body: sceneText.value || "",
    });
    setCanonicalSceneCollection(state.selectedStorySlug, payload.scenes || state.scenes);
    updateStoryGitWarning(payload.has_story_changes);
    state.sceneDetail = payload.document || null;
    state.selectedSceneSlug = state.sceneDetail?.scene?.slug || state.selectedSceneSlug;
    sceneEditorTitle.textContent = state.sceneDetail?.scene?.title || "Scene";
    sceneRenameTitle.value = state.sceneDetail?.scene?.title || "";
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

function renderStoryTable() {
  // Render the shared stories list.
  storyTableBody.replaceChildren();
  if (!state.stories.length) {
    renderEmptyRow(storyTableBody, 2, "No stories exist. Add a story to begin.");
    return;
  }
  state.stories.forEach((story, index) => {
    const row = document.createElement("tr");
    row.dataset.storySlug = story.slug;
    const cell = document.createElement("td");
    cell.textContent = story.title || "";
    row.append(cell);
    row.append(orderControls(story.title || story.slug, index, state.stories.length, (offset) => reorderStory(index, offset)));
    makeSelectableRow(row, story.title || story.slug, story.slug === state.selectedStorySlug, () => selectStory(story.slug));
    storyTableBody.append(row);
  });
}

async function reorderStory(index, offset) {
  const target = index + offset;
  if (target < 0 || target >= state.stories.length) return;
  const slugs = state.stories.map((story) => story.slug);
  [slugs[index], slugs[target]] = [slugs[target], slugs[index]];
  try {
    const payload = await fetchJson("/api/stories/order", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slugs }),
    });
    state.stories = payload.stories || state.stories;
    updateStoryGitWarning(payload.has_story_changes);
    renderStoryTable();
    renderSceneStoryOptions();
    renderZineStoryOptions();
    showStoryMessage(payload.message || "Story order saved.");
  } catch (error) {
    showStoryMessage(error.message, "error");
  }
}

function clearStoryEditor() {
  // Reset the story editor when nothing is selected.
  state.storyDetail = null;
  state.storySettings = null;
  storyEditorTitle.textContent = "Select a story";
  storyText.value = "";
  storyRenameTitle.value = "";
  storySettingsJson.value = "";
  storySettingsJson.hidden = true;
  storyText.hidden = false;
  storySettingsFields.replaceChildren();
  storySave.disabled = true;
  storyView.disabled = true;
  storyScenes.disabled = true;
  storyRename.disabled = true;
  storyDelete.disabled = true;
  state.savedBaselines.story = "";
  setSaveState(storySaveState, "");
  renderValidationBox(storyValidation, [], "Create or select a story to edit its markdown.");
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

function renderStorySettingsFields() {
  storySettingsFields.replaceChildren();
  if (!state.storySettings) {
    return;
  }
  const readOnlyFields = [];
  appendStorySettingFields(storySettingsFields, state.storySettings, [], readOnlyFields);
  readOnlyFields.forEach(([path, value]) => storySettingsFields.append(renderReadOnlyStorySetting(path, value)));
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
    saveStoredStoryContext();
    renderHeaderStoryContext();
    renderStoryTable();
    storyEditorTitle.textContent = state.storyDetail?.story?.title || "Story";
    storyRenameTitle.value = state.storyDetail?.story?.title || "";
    storyText.value = state.storyDetail?.text || "";
    storySettingsJson.hidden = true;
    storyText.hidden = false;
    storySave.disabled = !state.storyDetail;
    storyView.disabled = !state.storyDetail;
    storyScenes.disabled = !state.storyDetail;
    storyRename.disabled = !state.storyDetail;
    storyDelete.disabled = !state.storyDetail;
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
      storyRenameTitle.value = state.storyDetail.story.title || "";
      storyText.value = state.storyDetail.text || "";
      storySave.disabled = false;
      storyView.disabled = false;
      storyScenes.disabled = false;
      storyRename.disabled = false;
      storyDelete.disabled = false;
      await loadStorySettingsData(state.selectedStorySlug);
      renderValidationBox(storyValidation, state.storyDetail.validation_errors || [], "Story markdown is valid.");
      state.savedBaselines.story = storySnapshot();
      setSaveState(storySaveState, "Saved", "saved");
    }
    showStoryMessage(payload.message || "Story created.");
    await loadWorkspaceSummary();
  } catch (error) {
    showStoryMessage(error.message, "error");
  } finally {
    storyCreate.disabled = false;
  }
}

async function renameStory() {
  if (!state.selectedStorySlug) return;
  const title = storyRenameTitle.value.trim();
  if (!title) {
    showStoryMessage("Story title is required.", "error");
    return;
  }
  if (!(await guardCurrentEditor())) return;
  storyRename.disabled = true;
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    state.stories = payload.stories || state.stories;
    state.storyDetail = payload.document || state.storyDetail;
    updateStoryGitWarning(payload.has_story_changes);
    storyEditorTitle.textContent = state.storyDetail?.story?.title || title;
    storyRenameTitle.value = state.storyDetail?.story?.title || title;
    storyText.value = state.storyDetail?.text || storyText.value;
    await loadStorySettingsData(state.selectedStorySlug);
    renderStoryTable();
    renderSceneStoryOptions();
    renderZineStoryOptions();
    state.savedBaselines.story = storySnapshot();
    showStoryMessage(payload.message || "Story renamed.");
    await loadWorkspaceSummary();
  } catch (error) {
    showStoryMessage(error.message, "error");
  } finally {
    storyRename.disabled = !state.storyDetail;
  }
}

async function saveStory() {
  // Save the current story markdown and settings documents.
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
    storyEditorTitle.textContent = state.storyDetail?.story?.title || "Story";
    storyRenameTitle.value = state.storyDetail?.story?.title || "";
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
    await loadWorkspaceSummary();
  } catch (error) {
    showStoryMessage(error.message, "error");
  } finally {
    storySave.disabled = !state.storyDetail;
    storyDelete.disabled = !state.storyDetail;
  }
}

function clearSceneEditor() {
  // Reset the scene editor when no story or scene is selected.
  state.sceneDetail = null;
  state.loadedSceneContext = { storySlug: "", sceneSlug: "" };
  state.loadedBuilderContext = { storySlug: "", sceneSlug: "" };
  state.requestedSceneContext = { storySlug: "", sceneSlug: "" };
  state.selectedSceneSlug = null;
  state.scenes = [];
  state.sceneCollection = { storySlug: state.selectedStorySlug || "", items: [] };
  sceneTableBody.replaceChildren();
  sceneEditorTitle.textContent = "Select a scene";
  sceneText.value = "";
  sceneRenameTitle.value = "";
  sceneSave.disabled = true;
  sceneStageRender.disabled = true;
  sceneBuilderOpen.disabled = true;
  sceneDelete.disabled = true;
  sceneToggleImage.disabled = true;
  sceneRename.disabled = true;
  sceneMove.disabled = true;
  state.savedBaselines.scene = "";
  setSaveState(sceneSaveState, "");
  sceneImagePanel.hidden = true;
  sceneImagePreview.removeAttribute("src");
  sceneImageCandidateLink.hidden = true;
  sceneImageCandidateLink.removeAttribute("href");
  closeSceneBuilder();
  renderValidationBox(sceneValidation, [], "Select a story, then create or open a scene.");
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
    setCanonicalSceneCollection(state.selectedStorySlug, payload.scenes || []);
    if (state.selectedSceneSlug && !canonicalSceneCollection().some((item) => item.slug === state.selectedSceneSlug)) {
      state.selectedSceneSlug = null;
    }
    if (!state.selectedSceneSlug && canonicalSceneCollection().length) {
      state.selectedSceneSlug = canonicalSceneCollection()[0].slug;
    }
    state.requestedSceneContext = { storySlug: state.selectedStorySlug || "", sceneSlug: state.selectedSceneSlug || "" };
    saveStoredStoryContext();
    renderHeaderStoryContext();
    renderSceneTable();
    sceneStatus.textContent = `${state.scenes.length} scene(s)`;
    if (state.selectedSceneSlug) {
      await loadSceneDetail(state.selectedStorySlug, state.selectedSceneSlug);
    } else {
      clearSceneEditor();
      renderSceneTable();
    }
    await loadSceneImageReferences();
    await loadWorkspaceSummary();
  } catch (error) {
    if (isRequestCancellation(error)) return;
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
  state.scenes.forEach((scene, index) => {
    const row = document.createElement("tr");
    row.dataset.sceneSlug = scene.slug;
    const cell = document.createElement("td");
    cell.textContent = scene.title || "";
    row.append(cell);
    row.append(orderControls(scene.title || scene.slug, index, state.scenes.length, (offset) => reorderScene(index, offset)));
    makeSelectableRow(row, scene.title || scene.slug, scene.slug === state.selectedSceneSlug, () => selectScene(scene.slug));
    sceneTableBody.append(row);
  });
}

async function reorderScene(index, offset) {
  const target = index + offset;
  if (target < 0 || target >= state.scenes.length || !state.selectedStorySlug) return;
  const slugs = state.scenes.map((scene) => scene.slug);
  [slugs[index], slugs[target]] = [slugs[target], slugs[index]];
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/order`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slugs }),
    });
    setCanonicalSceneCollection(state.selectedStorySlug, payload.scenes || state.scenes);
    updateStoryGitWarning(payload.has_story_changes);
    renderSceneTable();
    showSceneMessage(payload.message || "Scene order saved.");
  } catch (error) {
    showSceneMessage(error.message, "error");
  }
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
    setCanonicalSceneCollection(state.selectedStorySlug, payload.scenes || state.scenes);
    updateStoryGitWarning(payload.has_story_changes);
    state.sceneDetail = payload.document || null;
    state.selectedSceneSlug = state.sceneDetail?.scene?.slug || state.selectedSceneSlug;
    state.requestedSceneContext = {
      storySlug: state.selectedStorySlug || "",
      sceneSlug: state.selectedSceneSlug || "",
    };
    state.loadedSceneContext = { ...state.requestedSceneContext };
    sceneEditorTitle.textContent = state.sceneDetail?.scene?.title || "Scene";
    sceneRenameTitle.value = state.sceneDetail?.scene?.title || "";
    sceneNewName.value = "";
    renderSceneTable();
    if (state.sceneDetail) {
      sceneEditorTitle.textContent = state.sceneDetail.scene.title || "Scene";
      sceneRenameTitle.value = state.sceneDetail.scene.title || "";
      sceneText.value = state.sceneDetail.text || "";
      updateSceneContextControls();
      renderSceneStoryOptions();
      updateSceneImageToggle();
      renderValidationBox(sceneValidation, state.sceneDetail.validation_errors || [], "Scene markdown is valid.");
      state.savedBaselines.scene = sceneSnapshot();
      setSaveState(sceneSaveState, "Saved", "saved");
    }
    showSceneMessage(payload.message || "Scene created.");
    await loadWorkspaceSummary();
  } catch (error) {
    showSceneMessage(error.message, "error");
  } finally {
    sceneCreate.disabled = false;
  }
}

async function renameScene() {
  if (!state.selectedStorySlug || !state.selectedSceneSlug || !sceneDocumentMatches()) return;
  const title = sceneRenameTitle.value.trim();
  if (!title) {
    showSceneMessage("Scene title is required.", "error");
    return;
  }
  if (!(await guardCurrentEditor())) return;
  sceneRename.disabled = true;
  try {
    const payload = await fetchJson(
      `/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      },
    );
    setCanonicalSceneCollection(state.selectedStorySlug, payload.scenes || state.scenes);
    state.sceneDetail = payload.document || state.sceneDetail;
    updateStoryGitWarning(payload.has_story_changes);
    sceneEditorTitle.textContent = state.sceneDetail?.scene?.title || title;
    sceneRenameTitle.value = state.sceneDetail?.scene?.title || title;
    sceneText.value = state.sceneDetail?.text || sceneText.value;
    renderSceneTable();
    state.savedBaselines.scene = sceneSnapshot();
    showSceneMessage(payload.message || "Scene renamed.");
    await loadWorkspaceSummary();
  } catch (error) {
    showSceneMessage(error.message, "error");
  } finally {
    updateSceneContextControls();
  }
}

async function moveScene() {
  if (!state.selectedStorySlug || !state.selectedSceneSlug || !sceneMoveStory.value || !sceneDocumentMatches()) return;
  if (!(await guardCurrentEditor())) return;
  const sourceStorySlug = state.selectedStorySlug;
  const sceneSlug = state.selectedSceneSlug;
  const targetStorySlug = sceneMoveStory.value;
  if (!confirm(`Move ${sceneSlug} to ${targetStorySlug}?`)) return;
  sceneMove.disabled = true;
  try {
    const payload = await fetchJson(
      `/api/stories/${encodeURIComponent(sourceStorySlug)}/scenes/${encodeURIComponent(sceneSlug)}/move`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_story_slug: targetStorySlug }),
      },
    );
    state.selectedStorySlug = targetStorySlug;
    state.selectedSceneSlug = sceneSlug;
    setCanonicalSceneCollection(targetStorySlug, payload.target_scenes || []);
    state.sceneDetail = payload.document || null;
    updateStoryGitWarning(payload.has_story_changes);
    renderSceneStoryOptions();
    renderSceneTable();
    await loadSceneDetail(targetStorySlug, sceneSlug);
    showSceneMessage(payload.message || "Scene moved.");
    await loadWorkspaceSummary();
  } catch (error) {
    showSceneMessage(error.message, "error");
  } finally {
    renderSceneStoryOptions();
  }
}

async function saveScene() {
  // Save the current scene markdown document.
  if (!state.selectedStorySlug || !state.selectedSceneSlug || !sceneDocumentMatches()) {
    showSceneMessage("Wait for the requested scene to finish loading before saving.", "error");
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
    setCanonicalSceneCollection(state.selectedStorySlug, payload.scenes || state.scenes);
    updateStoryGitWarning(payload.has_story_changes);
    state.sceneDetail = payload.document || null;
    state.selectedSceneSlug = state.sceneDetail?.scene?.slug || state.selectedSceneSlug;
    sceneEditorTitle.textContent = state.sceneDetail?.scene?.title || "Scene";
    sceneRenameTitle.value = state.sceneDetail?.scene?.title || "";
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
    updateSceneContextControls();
  }
}

async function deleteScene() {
  // Confirm, commit current story files, then delete the selected scene markdown and image.
  if (!state.selectedStorySlug || !state.selectedSceneSlug || !sceneDocumentMatches()
      || !confirm(`Delete scene ${state.selectedSceneSlug}?`)) {
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
    setCanonicalSceneCollection(state.selectedStorySlug, payload.scenes || []);
    state.selectedSceneSlug = canonicalSceneCollection()[0]?.slug || null;
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
    await loadWorkspaceSummary();
  } catch (error) {
    showSceneMessage(error.message, "error");
  } finally {
    updateSceneContextControls();
  }
}

async function stageSceneRender() {
  await activatePage("scene-batches");
}

function sceneBuilderNavigationLabel(document = null) {
  const storySlug = state.selectedStorySlug || "";
  const sceneSlug = state.selectedSceneSlug || "";
  const storyTitle = document?.story?.title
    || state.stories.find((story) => story.slug === storySlug)?.title
    || storySlug;
  const sceneTitle = document?.scene?.title
    || canonicalSceneCollection(storySlug).find((scene) => scene.slug === sceneSlug)?.title
    || state.sceneBuilder?.scene?.name
    || sceneSlug;
  return [storyTitle, sceneTitle].filter(Boolean).join(" / ");
}

function builderSelectedPlacement() {
  return (state.sceneBuilder?.placements || []).find((item) => item.id === state.selectedBuilderPlacementId) || null;
}

function builderSelectedElement() {
  return (state.sceneBuilder?.scene_elements || []).find((item) => item.id === state.selectedBuilderElementId) || null;
}

function builderActiveSubscene() {
  if (state.activeBuilderRenderTarget === "main") return null;
  return (state.sceneBuilder?.subscenes || []).find((item) => item.id === state.activeBuilderRenderTarget) || null;
}

function builderSubsceneColor(subsceneOrId) {
  const subscene = typeof subsceneOrId === "string"
    ? (state.sceneBuilder?.subscenes || []).find((item) => item.id === subsceneOrId)
    : subsceneOrId;
  if (!subscene || subscene.id === "main") return "";
  if (BUILDER_SUBSCENE_COLORS.includes(subscene.ui_color)) return subscene.ui_color;
  const index = Math.max(0, (state.sceneBuilder?.subscenes || []).findIndex((item) => item.id === subscene.id));
  return BUILDER_SUBSCENE_COLORS[index % BUILDER_SUBSCENE_COLORS.length];
}

function builderSubsceneStyle(subsceneOrId) {
  const color = builderSubsceneColor(subsceneOrId);
  return color ? ` style="--subscene-color: ${color}"` : "";
}

function builderRenderSubsceneColorPalette(subscene) {
  const selected = builderSubsceneColor(subscene);
  return `<div class="scene-builder-color-field full"><span>Sub-scene color</span><div class="scene-builder-color-palette" role="group" aria-label="Sub-scene color">${BUILDER_SUBSCENE_COLORS.map((color, index) => `<button type="button" class="${color === selected ? "selected" : ""}" data-builder-action="set-subscene-color" data-subscene-color="${color}" style="--swatch-color: ${color}" aria-label="Color ${index + 1}" aria-pressed="${color === selected}"></button>`).join("")}</div></div>`;
}

function builderSubsceneForAnchor(elementId) {
  return (state.sceneBuilder?.subscenes || []).find(
    (item) => item.kind === "element" && item.anchor_element_id === elementId,
  ) || null;
}

function builderTargetParentId(subscene) {
  if (!subscene || subscene.kind !== "element") return "main";
  const anchor = (state.sceneBuilder?.scene_elements || []).find((item) => item.id === subscene.anchor_element_id);
  return anchor?.subscene_id || "main";
}

function builderTargetDepth(targetId, seen = new Set()) {
  if (!targetId || targetId === "main") return 0;
  const target = (state.sceneBuilder?.subscenes || []).find((item) => item.id === targetId);
  if (!target || target.kind !== "element") return 0;
  if (seen.has(targetId)) return 99;
  seen.add(targetId);
  return builderTargetDepth(builderTargetParentId(target), seen) + 1;
}

function builderTargetChildren(targetId) {
  return (state.sceneBuilder?.subscenes || []).filter((item) => builderTargetParentId(item) === targetId);
}

function builderTargetPath(targetId) {
  const path = [];
  const seen = new Set();
  let currentId = targetId;
  while (currentId && currentId !== "main" && !seen.has(currentId)) {
    seen.add(currentId);
    const current = (state.sceneBuilder?.subscenes || []).find((item) => item.id === currentId);
    if (!current) break;
    path.unshift(current);
    currentId = builderTargetParentId(current);
  }
  return path;
}

function builderCanMoveElementToTarget(element, targetId) {
  const owned = builderSubsceneForAnchor(element?.id);
  if (!owned) return true;
  if (targetId === owned.id) return false;
  const descendants = new Set();
  const visit = (parentId) => {
    for (const child of builderTargetChildren(parentId)) {
      if (child.kind !== "element" || descendants.has(child.id)) continue;
      descendants.add(child.id);
      visit(child.id);
    }
  };
  visit(owned.id);
  if (descendants.has(targetId)) return false;
  const deepest = Math.max(builderTargetDepth(owned.id), ...[...descendants].map((id) => builderTargetDepth(id)));
  const subtreeHeight = deepest - builderTargetDepth(owned.id) + 1;
  return builderTargetDepth(targetId) + subtreeHeight <= 3;
}

function builderActiveTargetStatus() {
  return (state.sceneBuilderRenderTargets || []).find((item) => item.render_target_id === state.activeBuilderRenderTarget) || null;
}

function builderElementIsEditable(element) {
  return state.activeBuilderRenderTarget === "main" || element?.subscene_id === state.activeBuilderRenderTarget;
}

function builderElementOptions(selected = "") {
  const activeSubscene = builderActiveSubscene();
  const elements = (state.sceneBuilder?.scene_elements || []).filter(
    (element) => !activeSubscene || element.subscene_id === activeSubscene.id,
  );
  return `<option value=""></option>` + elements.map((element) => {
    const value = element.id || "";
    return `<option value="${escapeHtml(value)}"${value === selected ? " selected" : ""}>${escapeHtml(element.display_name || value)}</option>`;
  }).join("");
}

function builderAllElementOptions(selected = "") {
  return `<option value=""></option>` + (state.sceneBuilder?.scene_elements || []).map((element) => {
    const value = element.id || "";
    return `<option value="${escapeHtml(value)}"${value === selected ? " selected" : ""}>${escapeHtml(element.display_name || value)}</option>`;
  }).join("");
}

function builderDialogueTarget(dialogue) {
  return dialogue?.subscene_id || "main";
}

function builderDialogueRowsForTarget(data, targetId) {
  return (data?.dialogue || []).map((item, index) => ({ item, index }))
    .filter(({ item }) => targetId === "main" || builderDialogueTarget(item) === targetId);
}

function builderDialogueChanges(current, baseline) {
  const now = current?.dialogue || [];
  const before = baseline?.dialogue || [];
  const key = (item) => JSON.stringify(item);
  const rows = Array.from({ length: before.length + 1 }, () => Array(now.length + 1).fill(0));
  for (let i = before.length - 1; i >= 0; i -= 1) {
    for (let j = now.length - 1; j >= 0; j -= 1) {
      rows[i][j] = key(before[i]) === key(now[j])
        ? rows[i + 1][j + 1] + 1
        : Math.max(rows[i + 1][j], rows[i][j + 1]);
    }
  }
  const matchedBefore = new Set();
  const matchedNow = new Set();
  let i = 0;
  let j = 0;
  while (i < before.length && j < now.length) {
    if (key(before[i]) === key(now[j])) {
      matchedBefore.add(i); matchedNow.add(j); i += 1; j += 1;
    } else if (rows[i + 1][j] >= rows[i][j + 1]) i += 1;
    else j += 1;
  }
  const remainingBefore = before.map((_, index) => index).filter((index) => !matchedBefore.has(index));
  const remainingNow = now.map((_, index) => index).filter((index) => !matchedNow.has(index));
  const upserts = [];
  remainingNow.forEach((currentIndex, offset) => {
    const originalIndex = remainingBefore[offset];
    upserts.push({ index: originalIndex ?? before.length + currentIndex - remainingNow[0], dialogue: now[currentIndex] });
  });
  return {
    upserts,
    delete_indices: remainingBefore.slice(remainingNow.length),
  };
}

function builderDialogueTargetOptions(selected = "main") {
  const main = `<option value=""${selected === "main" ? " selected" : ""}>Full Scene</option>`;
  const targets = (state.sceneBuilder?.subscenes || []).map((item) =>
    `<option value="${escapeHtml(item.id)}"${selected === item.id ? " selected" : ""}>${escapeHtml(item.name || item.id)}</option>`
  ).join("");
  return main + targets;
}

function builderElementLabel(elementId) {
  const element = (state.sceneBuilder?.scene_elements || []).find((item) => item.id === elementId);
  return element?.display_name || elementId || "";
}

function builderNormalizeId(value) {
  return String(value || "").replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "scene_element";
}

function builderSyncSubsceneControls() {
  const activeSubscene = builderActiveSubscene();
  if (!activeSubscene) return;
  const nameControl = sceneBuilderPanel.querySelector("[data-builder-subscene-name]");
  if (nameControl) activeSubscene.name = nameControl.value;
  activeSubscene.prompt_overrides = activeSubscene.prompt_overrides || {};
  for (const control of sceneBuilderPanel.querySelectorAll("[data-builder-subscene-field]")) {
    activeSubscene.prompt_overrides[control.dataset.builderSubsceneField] = control.value;
  }
  if (activeSubscene.kind === "element") {
    activeSubscene.setup = activeSubscene.setup || {};
    for (const control of sceneBuilderPanel.querySelectorAll("[data-builder-element-subscene-field]")) {
      setPathValue(activeSubscene.setup, control.dataset.builderElementSubsceneField, control.value);
    }
  }
}

function builderSyncControls() {
  builderSyncSubsceneControls();
  let elementTypeChangedToProp = false;
  for (const control of sceneBuilderPanel.querySelectorAll("[data-builder-field]")) {
    setPathValue(state.sceneBuilder, control.dataset.builderField, control.type === "number" ? Number(control.value || 0) : control.value);
  }
  const changedDialogueSpeakers = new Set();
  const element = builderSelectedElement();
  const previousElementSubscene = element?.subscene_id || "";
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
    if (element.subscene_id !== previousElementSubscene) {
      for (const dialogue of state.sceneBuilder.dialogue || []) {
        if (dialogue.speaker_element_id === element.id) {
          dialogue.subscene_id = element.subscene_id || "";
          changedDialogueSpeakers.add(dialogue);
        }
      }
    }
    for (const control of sceneBuilderPanel.querySelectorAll("[data-builder-reference-field]")) {
      const reference = (element.reference_images || [])[Number(control.dataset.builderReferenceIndex)];
      if (!reference) continue;
      const field = control.dataset.builderReferenceField;
      if (field === "label" && control.readOnly) continue;
      if (field === "primary_prompt_source") {
        reference[field] = control.checked;
        if (control.checked) {
          (element.reference_images || []).forEach((other, otherIndex) => {
            if (otherIndex !== Number(control.dataset.builderReferenceIndex)) other.primary_prompt_source = false;
          });
        }
        continue;
      }
      reference[field] = ["roles", "preserve", "change", "ignore"].includes(field)
        ? control.value.split(",").map((value) => value.trim()).filter(Boolean)
        : control.value;
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
      if (field === "speaker_element_id" && dialogue[field] !== control.value) {
        changedDialogueSpeakers.add(dialogue);
      }
      if (field === "subscene_id" && !control.value && !Object.hasOwn(dialogue, field)) continue;
      if (field === "panel_placement" && control.value === "auto" && !Object.hasOwn(dialogue, field)) continue;
      if (field === "max_lines") {
        dialogue[field] = Number(control.value || 0);
      } else {
        dialogue[field] = control.value;
      }
    }
  }
  for (const dialogue of changedDialogueSpeakers) {
    const speaker = (state.sceneBuilder.scene_elements || []).find((item) => item.id === dialogue.speaker_element_id);
    dialogue.subscene_id = speaker?.subscene_id || "";
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
  const changedElement = builderSelectedElement();
  const changedField = event?.target?.dataset?.builderElementField || "";
  if (changedElement && changedField === "resource_type") {
    changedElement.element_type = builderElementTypeForResourceType(changedElement.resource_type);
    changedElement.reference_images = [];
    if (changedElement.resource_type === "Character") {
      changedElement.aux_category = "";
      changedElement.aux_resource_id = "";
      const matchingCharacter = (state.characters || []).find((item) => item.toLowerCase() === (changedElement.display_name || "").toLowerCase()) || "";
      changedElement.character = matchingCharacter;
      changedElement.phase = (state.phasesByCharacter[matchingCharacter] || [])[0] || "";
    } else {
      changedElement.character = "";
      changedElement.phase = "";
      changedElement.costume = "";
    }
  }
  if (changedElement && changedField === "character") {
    changedElement.phase = (state.phasesByCharacter[changedElement.character] || [])[0] || "";
    changedElement.costume = "";
    changedElement.reference_images = [];
  }
  if (changedElement && changedField === "phase") {
    changedElement.costume = "";
    changedElement.reference_images = [];
  }
  if (event?.target?.id === "builder-composition-element" || event?.target?.matches("input, textarea")) {
    return;
  }
  if (changedField === "subscene_id") {
    renderSceneBuilder();
    return;
  }
  renderSceneBuilder();
  if (changedElement && ["resource_type", "character", "phase"].includes(changedField)) {
    builderLoadSelectedElementCostumes(changedElement).then(() => renderSceneBuilder()).catch((error) => showSceneBuilderMessage(error.message, "error"));
  }
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
    pose: { summary: "", gaze_target_element_id: "", expression: "" },
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
  if (resourceType === "Object" || resourceType === "Scene-Only" || resourceType === "Subscene") return "Prop";
  return "Character";
}

function builderUpdateElementModalSections() {
  const resourceType = builderElementResourceType.value || "Character";
  builderElementCharacterSection.hidden = resourceType !== "Character";
  builderElementAuxSection.hidden = !builderAuxCategoryForResourceType(resourceType);
  builderElementSceneSection.hidden = resourceType !== "Scene-Only";
  builderElementSubsceneSection.hidden = resourceType !== "Subscene";
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

async function builderLoadSelectedElementCostumes(element = builderSelectedElement(), options = {}) {
  if (element?.resource_type !== "Character" || !element.character || !element.phase) return;
  const key = `${element.character}\n${element.phase}`;
  if (state.builderCostumesByCharacterPhase[key]) return;
  const params = new URLSearchParams({ character: element.character, phase: element.phase });
  const payload = await fetchJson(`/api/costumes?${params.toString()}`, options);
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
    const payload = await fetchJson("/api/image-catalog/reference-sets");
    state.builderElementAuxResources[category] = (payload.reference_sets || [])
      .filter((item) => item.legacy_category === category)
      .map((item) => ({ resource_id: item.reference_set_id, label: item.label }));
  }
  setSelectOptionsWithLabels(builderElementAux, state.builderElementAuxResources[category].map((item) => ({ value: item.resource_id, label: item.label || item.resource_id })));
}

async function openBuilderElementDialog() {
  setSelectOptionsWithLabels(builderElementResourceType, [
    ...(state.sceneBuilderOptions.resource_type || []).map((item) => ({ value: item.value, label: item.label })),
    { value: "Subscene", label: "Subscene" },
  ]);
  builderElementResourceType.value = "Character";
  setSelectOptionsWithLabels(builderElementCharacter, [
    { value: "", label: "(No linked character)" },
    ...(state.characters || []).map((name) => ({ value: name, label: name })),
  ]);
  builderElementCharacter.value = "";
  setSelectOptions(builderElementPhase, state.phasesByCharacter[builderElementCharacter.value] || []);
  builderElementPhase.value = "";
  builderElementSceneName.value = "";
  closeBuilderElementAuxForm();
  builderUpdateElementModalSections();
  await builderLoadElementCostumes();
  await builderLoadElementAuxResources();
  builderElementModal.showModal();
  builderElementResourceType.focus();
}

async function builderAddElementFromDialog() {
  const index = (state.sceneBuilder.scene_elements || []).length + 1;
  const resourceType = builderElementResourceType.value || "Character";
  const isSubscene = resourceType === "Subscene";
  const category = builderAuxCategoryForResourceType(resourceType);
  const resource = category ? (state.builderElementAuxResources[category] || []).find((item) => item.resource_id === builderElementAux.value) : null;
  const displayName = builderElementSceneName.value.trim() || (resourceType === "Character" ? builderElementCharacter.value : resource?.label || "");
  if (!displayName) {
    showSceneBuilderMessage("Display name is required.", "error");
    builderElementSceneName.focus();
    builderElementSceneName.reportValidity();
    return;
  }
  const baseId = self.crypto?.randomUUID ? `${builderNormalizeId(displayName)}_${self.crypto.randomUUID().slice(0, 8)}` : `${builderNormalizeId(displayName)}_${Date.now()}`;
  const element = {
    id: index === 1 ? builderNormalizeId(displayName) : baseId,
    display_name: displayName,
    resource_type: isSubscene ? "Scene-Only" : resourceType,
    element_type: builderElementTypeForResourceType(resourceType),
    character: resourceType === "Character" ? builderElementCharacter.value : "",
    phase: resourceType === "Character" && builderElementCharacter.value ? builderElementPhase.value : "",
    costume: resourceType === "Character" && builderElementCharacter.value ? builderElementCostume.value : "",
    aux_category: category,
    reference_set_id: resource?.resource_id || "",
    reference_images: [],
    element_visual_override: "",
    fallback_visual_description: "",
    notes: "",
    subscene_id: state.activeBuilderRenderTarget === "main" ? "" : state.activeBuilderRenderTarget,
  };
  state.sceneBuilder.scene_elements.push(element);
  const placement = builderCreatePlacementForElement(element);
  if (isSubscene) placement.position_within_cell = "center";
  state.sceneBuilder.placements.push(placement);
  state.selectedBuilderElementId = element.id;
  state.selectedBuilderPlacementId = builderPlacementForElement(element.id)?.id || null;
  builderElementModal.close();
  renderSceneBuilder();
  if (isSubscene) {
    if (await saveSceneBuilder({ fullScene: true })) await enableSelectedElementSubscene(element.id);
  }
}

function builderRemoveSelectedElement() {
  const element = builderSelectedElement();
  if (!element) {
    return;
  }
  if (builderSubsceneForAnchor(element.id)) {
    showSceneBuilderMessage("Disable does not remove an element sub-scene. The anchor cannot be deleted while it owns a sub-scene.", "error");
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
    subscene_id: selectedElement?.subscene_id || "",
    text: "",
    target_element_id: "",
    pointer_target: "speaker mouth",
    panel_placement: "auto",
    max_lines: 3,
    notes: "",
  });
  renderSceneBuilder();
}

function builderDeleteDialogue(index) {
  state.sceneBuilder.dialogue = (state.sceneBuilder.dialogue || []).filter((_, itemIndex) => itemIndex !== index);
  renderSceneBuilder();
}

function builderReferenceIdentity(reference) {
  if (reference?.tag) return reference.tag;
  if (reference?.asset_id) return `{{LIB:ASSET:${reference.asset_id}}}`;
  if (reference?.reference_key) return `{{LIB:REF:${reference.reference_key}}}`;
  return "";
}

function builderRenderElements() {
  const activeSubscene = builderActiveSubscene();
  const visibleElements = (state.sceneBuilder.scene_elements || []).filter(
    (element) => !activeSubscene || state.showBuilderContextElements || element.subscene_id === activeSubscene.id,
  );
  const rows = visibleElements.map((element) => {
    const placement = builderPlacementForElement(element.id);
    const position = placement?.position_within_cell || "—";
    const depth = position === "None" ? "None" : placement?.depth || "—";
    const referenceTags = (element.reference_images || []).map(builderReferenceIdentity).filter(Boolean);
    const linkedReferenceCount = referenceTags.filter((tag) => (state.sceneBuilderReferences || []).some((item) => item.tag === tag)).length;
    const referenceKnown = Boolean(referenceTags.length && linkedReferenceCount === referenceTags.length);
    const referenceStatus = !referenceTags.length ? "No references" : referenceKnown ? `${referenceTags.length} reference(s) linked` : `${linkedReferenceCount}/${referenceTags.length} references linked`;
    return `
      <button type="button" class="scene-builder-element-row ${element.id === state.selectedBuilderElementId ? "selected" : ""} ${activeSubscene && element.subscene_id !== activeSubscene.id ? "context-only" : ""} ${element.subscene_id ? "subscene-member" : ""}" data-builder-select-element="${escapeHtml(element.id || "")}"${builderSubsceneStyle(element.subscene_id)}>
        <span class="scene-builder-element-name">${escapeHtml(element.display_name || element.id || "")}</span>
        <span class="scene-builder-element-meta"><span>${escapeHtml(element.element_type || "")}</span><span class="reference-status ${referenceKnown ? "complete" : ""}">${escapeHtml(referenceStatus)}</span></span>
        <small>Position: ${escapeHtml(position)} · Depth: ${escapeHtml(depth)} · Render: ${escapeHtml(element.subscene_id || "Full Scene")}</small>
      </button>
    `;
  }).join("");
  return `
    <div class="scene-builder-card">
      <div class="review-header">
        <div>
          <span class="eyebrow">Build the cast</span>
          <h4>Scene Elements</h4>
        </div>
        ${activeSubscene ? "" : '<button type="button" class="primary-action" data-builder-action="add-element">Add Element</button>'}
      </div>
      ${activeSubscene ? `<label class="builder-context-toggle"><input type="checkbox" data-builder-action="toggle-context-elements"${state.showBuilderContextElements ? " checked" : ""}> Show other elements as context</label>` : ""}
      <div class="scene-builder-element-list">${rows || "<p>No elements have been added yet.</p>"}</div>
    </div>
  `;
}

function builderRenderSubsceneElementsSummary() {
  const activeSubscene = builderActiveSubscene();
  const members = (state.sceneBuilder.scene_elements || []).filter(
    (element) => element.subscene_id === activeSubscene?.id,
  );
  const rows = members.map((element) => {
    const placement = builderPlacementForElement(element.id);
    return `<li><strong>${escapeHtml(element.display_name || element.id)}</strong><small>${escapeHtml(element.element_type || "")} · ${escapeHtml(placement?.position_within_cell || "No position")} · ${escapeHtml(placement?.depth || "No depth")}</small></li>`;
  }).join("");
  return `<div class="scene-builder-card">
    <span class="eyebrow">Subscene contents</span>
    <h4>Elements rendered in ${escapeHtml(activeSubscene?.name || activeSubscene?.id || "this subscene")}</h4>
    <p>Element identity, placement, membership, and interactions are full-scene values. Edit them from Full Scene.</p>
    <button type="button" data-builder-action="select-render-target" data-render-target-id="main">Edit elements in Full Scene</button>
    <ul class="scene-builder-subscene-element-summary">${rows || "<li>No elements are assigned to this subscene.</li>"}</ul>
  </div>`;
}

function builderRenderElementEditor() {
  const element = builderSelectedElement();
  if (!element) {
    return `<section class="scene-builder-editor-section"><h5>Identity and reference</h5><p>Select or add a scene element.</p></section>`;
  }
  element.reference_images = element.reference_images || [];
  const referenceEditors = element.reference_images.map((imageReference, index) => {
    const referenceTag = builderReferenceIdentity(imageReference);
    const reference = (state.sceneBuilderReferences || []).find((item) => item.tag === referenceTag);
    const libraryReference = !imageReference.tag && (imageReference.asset_id || imageReference.reference_key);
    const referenceThumbnail = reference?.thumbnail_path
      ? `<span class="scene-builder-reference-preview"><img class="scene-builder-reference-thumbnail fullscreen-image-trigger" src="${fileUrl(reference.thumbnail_path)}" alt="${escapeHtml(reference.label || referenceTag)}" data-story-slug="${escapeHtml(reference.story_slug || "")}" data-scene-slug="${escapeHtml(reference.scene_slug || "")}" data-candidate-pending="${reference.candidate_pending ? "true" : "false"}">${reference.candidate_pending ? `<a class="candidate-pending-overlay" href="${sceneImageReviewUrl(reference.story_slug, reference.scene_slug)}">Candidate Image Pending</a>` : ""}</span>`
      : "";
    return `<div class="scene-builder-reference-field full" data-builder-reference-row="${index}">
      ${referenceThumbnail}
      <div>
        <label>${builderCaption(libraryReference ? `Reference ${index + 1} image` : `Reference ${index + 1} tag`, libraryReference ? "scene_elements[].reference_images[].asset_id" : "scene_elements[].reference_images[].tag")}<span class="inline-field"><input value="${escapeHtml(libraryReference ? (reference?.label || referenceTag) : referenceTag)}" data-builder-reference-field="${libraryReference ? "label" : "tag"}" data-builder-reference-index="${index}"${libraryReference ? " readonly" : ""}><button type="button" data-builder-action="pick-image-tag" data-builder-reference-index="${index}">Search</button>${reference?.catalog_id ? `<button type="button" data-builder-action="open-catalog-item" data-catalog-id="${escapeHtml(reference.catalog_id)}">Edit metadata</button>` : ""}</span></label>
        <label>Roles (comma-separated)<input value="${escapeHtml((imageReference.roles || []).join(", "))}" data-builder-reference-field="roles" data-builder-reference-index="${index}"></label>
        <label class="checkbox-field"><input type="checkbox" data-builder-reference-field="primary_prompt_source" data-builder-reference-index="${index}"${imageReference.primary_prompt_source ? " checked" : ""}> Use as primary prompt source</label>
        <label>Preserve (comma-separated)<input value="${escapeHtml((imageReference.preserve || []).join(", "))}" data-builder-reference-field="preserve" data-builder-reference-index="${index}"></label>
        <label>Change (comma-separated)<input value="${escapeHtml((imageReference.change || []).join(", "))}" data-builder-reference-field="change" data-builder-reference-index="${index}"></label>
        <label>Ignore (comma-separated)<input value="${escapeHtml((imageReference.ignore || []).join(", "))}" data-builder-reference-field="ignore" data-builder-reference-index="${index}"></label>
        <label>Notes<textarea data-builder-reference-field="notes" data-builder-reference-index="${index}">${escapeHtml(imageReference.notes || "")}</textarea></label>
        ${reference ? `<small>${escapeHtml(reference.semantic_category || reference.kind || "")} · ${escapeHtml(String(reference.description_status || "").replaceAll("_", " "))}</small>` : ""}
        ${(element.resolved_source_sections?.reference_warnings || []).map((warning) => `<small class="action-message warning">${escapeHtml(warning)}</small>`).join("")}
        <span class="button-row compact"><button type="button" data-builder-action="reference-up" data-builder-reference-index="${index}"${index === 0 ? " disabled" : ""}>Up</button><button type="button" data-builder-action="reference-down" data-builder-reference-index="${index}"${index === element.reference_images.length - 1 ? " disabled" : ""}>Down</button><button type="button" data-builder-action="reference-remove" data-builder-reference-index="${index}">Remove</button></span>
      </div>
    </div>`;
  }).join("");
  const characterOptions = `<option value=""></option>` + (state.characters || []).map((character) => `<option value="${escapeHtml(character)}"${character === element.character ? " selected" : ""}>${escapeHtml(character)}</option>`).join("");
  const phaseOptions = `<option value=""></option>` + (state.phasesByCharacter[element.character] || []).map((phase) => `<option value="${escapeHtml(phase)}"${phase === element.phase ? " selected" : ""}>${escapeHtml(phase)}</option>`).join("");
  return `
    <section class="scene-builder-editor-section">
      <h5>Identity and reference</h5>
      <div class="scene-builder-fields">
        <label>${builderCaption("Display name", "scene_elements[].display_name")}<input value="${escapeHtml(element.display_name || "")}" data-builder-element-field="display_name"></label>
        <label>${builderCaption("Resource type", "scene_elements[].resource_type")}<select data-builder-element-field="resource_type">${builderResourceTypeOptions(element.resource_type || "Character")}</select></label>
        <label>${builderCaption("Type", "scene_elements[].element_type")}<select data-builder-element-field="element_type"><option value="Character"${element.element_type === "Character" ? " selected" : ""}>Character</option><option value="Monster"${element.element_type === "Monster" ? " selected" : ""}>Monster</option><option value="Prop"${element.element_type === "Prop" ? " selected" : ""}>Prop</option><option value="Backdrop"${element.element_type === "Backdrop" ? " selected" : ""}>Backdrop</option></select></label>
        ${element.resource_type === "Character" ? `<label>${builderCaption("Character", "scene_elements[].character")}<select data-builder-element-field="character">${characterOptions}</select></label>` : ""}
        ${element.resource_type === "Character" ? `<label>${builderCaption("Phase", "scene_elements[].phase")}<select data-builder-element-field="phase">${phaseOptions}</select></label>` : ""}
        ${element.resource_type === "Character" ? `<label>${builderCaption("Costume", "scene_elements[].costume")}<select data-builder-element-field="costume">${builderCostumeOptions(element)}</select></label>` : ""}
        ${referenceEditors}
        <div class="full"><button type="button" data-builder-action="reference-add">Add reference</button></div>
        <label class="full">${builderCaption("(Element visual override) Element Override: ...", "scene_elements[].element_visual_override")}<textarea data-builder-element-field="element_visual_override">${escapeHtml(element.element_visual_override || "")}</textarea></label>
        <label class="full">${builderCaption("(Fallback visual description) Visual description: ...", "scene_elements[].fallback_visual_description")}<textarea data-builder-element-field="fallback_visual_description">${escapeHtml(element.fallback_visual_description || "")}</textarea></label>
      </div>
    </section>
  `;
}

function builderRenderPlacementEditor() {
  const placement = builderSelectedPlacement();
  const element = builderSelectedElement();
  const placementTitle = `Placement for ${element?.display_name || element?.id || "Selected Element"}`;
  if (!placement) {
    return `<section class="scene-builder-editor-section"><h5>${escapeHtml(placementTitle)}</h5><p>Select or add a scene element.</p></section>`;
  }
  const showActing = !element || ["Character", "Monster"].includes(element.element_type || "Character");
  const isBackdrop = element?.element_type === "Backdrop";
  placement.motion = placement.motion || { state: "stationary", direction_screen: "", cue: "" };
  if (isBackdrop) placement.position_within_cell = "";
  const placementDisabled = placement.position_within_cell === "None" ? " disabled" : "";
  return `
    <section class="scene-builder-editor-section">
      <h5>Placement and acting</h5>
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
        <label class="full">${builderCaption("Placement instructions — included in prompt", "placements[].placement_notes")}<textarea data-builder-placement-field="placement_notes"${placementDisabled}>${escapeHtml(placement.placement_notes || "")}</textarea></label>
      </div>
    </section>
  `;
}

function builderRenderElementWorkspace() {
  if (builderActiveSubscene()) return builderRenderSubsceneElementsSummary();
  const element = builderSelectedElement();
  if (!element) {
    return `<div class="scene-builder-card scene-builder-element-workspace"><h4>Element workspace</h4>${builderRenderElementEditor()}</div>`;
  }
  const activeSubscene = builderActiveSubscene();
  const editable = builderElementIsEditable(element);
  const membershipOptions = [
    ...(builderCanMoveElementToTarget(element, "main") ? [`<option value=""${element.subscene_id ? "" : " selected"}>Full Scene</option>`] : []),
    ...(state.sceneBuilder.subscenes || []).filter((item) => builderCanMoveElementToTarget(element, item.id)).map((item) => `<option value="${escapeHtml(item.id)}"${element.subscene_id === item.id ? " selected" : ""}>${escapeHtml(item.name || item.id)}</option>`),
  ].join("");
  return `
    <div class="scene-builder-card scene-builder-element-workspace ${element.subscene_id ? "subscene-member" : ""}"${builderSubsceneStyle(element.subscene_id)}>
      <div class="review-header">
        <div>
          <span class="eyebrow">Selected element</span>
          <h4>${escapeHtml(element.display_name || element.id || "Element")}</h4>
        </div>
        <details class="scene-builder-element-menu">
          <summary aria-label="Selected element actions" title="Selected element actions">•••</summary>
          <div class="scene-builder-menu-panel">
            ${builderSubsceneForAnchor(element.id) ? "" : `<button type="button" data-builder-action="enable-element-subscene" data-element-id="${escapeHtml(element.id)}">Create subscene from this element</button>`}
            <button type="button" data-builder-action="duplicate-element">Duplicate</button>
            <button type="button" class="danger-action" data-builder-action="delete-element">Delete</button>
          </div>
        </details>
      </div>
      <div class="scene-builder-fields">
        <label>Render in<select data-builder-element-field="subscene_id">${membershipOptions}</select></label>
        ${activeSubscene && !editable ? `<p class="full">This element is visible for composition context. Move it into ${escapeHtml(activeSubscene.name || activeSubscene.id)} to edit it here.</p>` : ""}
      </div>
      <div class="scene-builder-element-editor">
        <fieldset${editable ? "" : " disabled"}>
          ${builderRenderElementEditor()}
          ${builderRenderPlacementEditor()}
        </fieldset>
      </div>
    </div>
  `;
}

function builderRenderDialogueEditor() {
  const activeSubscene = builderActiveSubscene();
  const targetId = activeSubscene?.id || "main";
  const rows = builderDialogueRowsForTarget(state.sceneBuilder, targetId).map(({ item: dialogue, index }) => `
    <div class="scene-builder-dialogue-entry">
      <div class="review-header">
        <h4>Dialogue ${index + 1}</h4>
        ${!activeSubscene && builderDialogueTarget(dialogue) !== "main" ? `<span${builderSubsceneStyle(dialogue.subscene_id)}>${escapeHtml((state.sceneBuilder.subscenes || []).find((item) => item.id === dialogue.subscene_id)?.name || dialogue.subscene_id)}</span>` : ""}
        <button type="button" data-builder-action="delete-dialogue" data-builder-dialogue-index="${index}">Delete</button>
      </div>
      <div class="scene-builder-fields">
        <label>${builderCaption("(Speaker) ... says exactly: [text]", "dialogue[].speaker_element_id")}<select data-builder-dialogue="${index}" data-builder-dialogue-field="speaker_element_id">${builderAllElementOptions(dialogue.speaker_element_id || "")}</select></label>
        <label>${builderCaption("(Target) Dialogue is directed toward ...", "dialogue[].target_element_id")}<select data-builder-dialogue="${index}" data-builder-dialogue-field="target_element_id">${builderAllElementOptions(dialogue.target_element_id || "")}</select></label>
        <label>Render in<select data-builder-dialogue="${index}" data-builder-dialogue-field="subscene_id">${builderDialogueTargetOptions(builderDialogueTarget(dialogue))}</select><small>Moving the speaker later resets this assignment.</small></label>
        <label>Panel placement<select data-builder-dialogue="${index}" data-builder-dialogue-field="panel_placement">
          <option value="auto"${!dialogue.panel_placement || dialogue.panel_placement === "auto" ? " selected" : ""}>Automatic</option>
          <option value="left"${dialogue.panel_placement === "left" ? " selected" : ""}>Left of speaker</option>
          <option value="right"${dialogue.panel_placement === "right" ? " selected" : ""}>Right of speaker</option>
          <option value="above"${dialogue.panel_placement === "above" ? " selected" : ""}>Above speaker</option>
          <option value="below"${dialogue.panel_placement === "below" ? " selected" : ""}>Below speaker</option>
        </select></label>
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
      ${activeSubscene ? `<p>Dialogue assigned to ${escapeHtml(activeSubscene.name || activeSubscene.id)}.</p>` : "<p>Dialogue assigned to subscenes is labeled here.</p>"}
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
    <div class="scene-builder-card scene-layout-launch-card">
      <div><h4>3D Layout</h4><p>Place scene elements in feet and inches, set independent body and head facing, and inspect the fixed render camera.</p></div>
      <button type="button" class="primary-action" data-layout-open>Open 3D Layout</button>
    </div>
  `;
}

function builderRenderInteractions(memberOnly = false) {
  const activeSubscene = builderActiveSubscene();
  const members = new Set((state.sceneBuilder.scene_elements || []).filter((item) => item.subscene_id === activeSubscene?.id).map((item) => item.id));
  const interactionRows = (state.sceneBuilder.interactions || []).map((interaction, index) => ({ interaction, index })).filter(
    ({ interaction }) => !memberOnly || (members.has(interaction.subject_element_id) && members.has(interaction.target_element_id)),
  );
  const interactions = interactionRows.map(({ interaction, index }) => `
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

function builderRenderOverrides() {
  return `
    <details class="scene-builder-card scene-builder-advanced">
      <summary>Advanced Overrides</summary>
      <div class="scene-builder-fields">
        ${builderField("final_image_prompt_overrides.anatomical_requirements", "Anatomical Requirements override", "", true, "textarea")}
        ${builderField("final_image_prompt_overrides.avoid", "Avoid override", "", true, "textarea")}
        ${builderField("final_image_prompt_overrides.high_risk_elements", "High-Risk Elements override", "", true, "textarea")}
        ${builderField("final_image_prompt_overrides.final_verification", "Final Verification override", "", true, "textarea")}
      </div>
    </details>
  `;
}

function builderRenderTechnicalDetails() {
  const scene = state.sceneBuilder.scene || {};
  return `
    <details class="scene-builder-technical-details">
      <summary>Technical Details</summary>
      <dl>
        <dt>Scene JSON</dt><dd><code>${escapeHtml(scene.slug || "")}.scene.json</code></dd>
        <dt>Story settings</dt><dd><code>${escapeHtml(scene.story_settings_path || "Not set")}</code></dd>
        <dt>Scene image</dt><dd><code>${escapeHtml(scene.associated_png_path || "Not set")}</code></dd>
      </dl>
    </details>
  `;
}

function builderRenderMoreMenu() {
  const analysisAction = state.scenePromptAnalysis?.complete || state.scenePromptAnalysis?.pending
    ? "view-analysis"
    : "analyze-prompt";
  const activeSubscene = builderActiveSubscene();
  const renderDisabled = !sceneDocumentMatches();
  const renderLabel = "Open Scene Renders";
  const saveLabel = activeSubscene ? "Save Subscene" : "Save Full Scene";
  return `
    <details class="scene-builder-more">
      <summary><span class="builder-more-desktop-label">More</span><span class="builder-more-responsive-label">Actions</span></summary>
      <div class="scene-builder-menu-panel">
        <button type="button" class="builder-responsive-action" data-builder-action="save">${saveLabel}</button>
        ${activeSubscene ? '<button type="button" class="builder-responsive-action" data-builder-action="cancel-subscene">Cancel Subscene Edits</button>' : ""}
        <button type="button" class="builder-responsive-action primary-action" data-builder-action="render"${renderDisabled ? " disabled" : ""}>${escapeHtml(renderLabel)}</button>
        <button type="button" data-builder-action="continue-from">Continue From…</button>
        <button type="button" data-builder-action="open-page" data-builder-page="scene-batches">Scene Render Slots</button>
        <button type="button" data-builder-action="open-page" data-builder-page="scenes">Scene Management</button>
        <button type="button" data-builder-action="open-page" data-builder-page="local-batch-status">Local Assets</button>
        ${builderRenderTechnicalDetails()}
      </div>
    </details>
  `;
}

function builderRenderSectionSwitcher() {
  return `<div class="builder-section-switcher" role="tablist" aria-label="Builder section">${BUILDER_RESPONSIVE_SECTIONS.map(([value, label]) => `<button type="button" role="tab" aria-selected="${value === state.builderResponsiveSection}" data-builder-action="builder-section" data-builder-section="${value}">${label}</button>`).join("")}</div>`;
}

function builderPhoneSectionToggle(value, label) {
  const expanded = value === state.builderResponsiveSection;
  return `<button type="button" class="builder-phone-section-toggle" aria-expanded="${expanded}" aria-controls="builder-panel-${value}" data-builder-action="builder-section" data-builder-section="${value}">${label}<span aria-hidden="true">${expanded ? "−" : "+"}</span></button>`;
}

function builderRenderDatalists() {
  return `
    <datalist id="builder-pose-list">${builderOptions("pose").map((value) => `<option value="${escapeHtml(value)}"></option>`).join("")}</datalist>
    <datalist id="builder-gaze-list">${builderOptions("gaze").map((value) => `<option value="${escapeHtml(value)}"></option>`).join("")}</datalist>
    <datalist id="builder-expression-list">${builderOptions("expression").map((value) => `<option value="${escapeHtml(value)}"></option>`).join("")}</datalist>
  `;
}

function builderRenderAnalysisAction() {
  const analysis = state.scenePromptAnalysis || {};
  const action = analysis.complete || analysis.pending ? "view-analysis" : "analyze-prompt";
  const label = analysis.complete ? "View latest analysis" : analysis.pending ? "Check analysis" : "Run analysis";
  return `<button type="button" class="scene-builder-analysis-action" data-builder-action="${action}">${label}</button>`;
}

function builderRenderImportStatus() {
  if (!state.sceneBuilder?.source_provenance) return "";
  const blockers = state.sceneBuilderReadiness?.blockers || [];
  const needsAttention = Boolean(blockers.length);
  const attentionReason = blockers.join("\n");
  return `<span class="scene-builder-import-status">
    ${needsAttention ? `<span class="status-badge needs-attention" title="${escapeHtml(attentionReason)}" aria-label="Needs attention: ${escapeHtml(blockers.join("; "))}">Needs attention</span>` : ""}
    <button type="button" data-builder-action="candidate-details">Imported candidate details</button>
  </span>`;
}

function sceneBuilderInterviewCheckpointKey() {
  return `zet:scene-interview:${encodeURIComponent(state.selectedStorySlug)}:${encodeURIComponent(state.selectedSceneSlug)}`;
}

sceneBuilderInterviewNarrative.addEventListener("input", checkpointSceneBuilderInterview);

sceneBuilderInterviewQuestions.addEventListener("input", checkpointSceneBuilderInterview);

function openSceneBuilderInterview(seed = null, restart = false) {
  if (!state.sceneBuilder) return;
  builderSyncControls();
  state.sceneBuilderInterview = null;
  state.sceneBuilderInterviewSeed = seed || null;
  sceneBuilderInterviewNarrative.value = seed?.narrative || "";
  let checkpoint = null;
  try {
    if (restart) {
      const key = sceneBuilderInterviewCheckpointKey();
      const previous = localStorage.getItem(key);
      if (previous) localStorage.setItem(`${key}:previous`, previous);
      localStorage.removeItem(key);
    }
    else checkpoint = JSON.parse(localStorage.getItem(sceneBuilderInterviewCheckpointKey()) || "null");
  } catch (error) {
    showSceneBuilderMessage(`Unable to restore interview progress: ${error.message}`, "error");
  }
  if (checkpoint) {
    state.sceneBuilderInterview = checkpoint.payload;
    state.sceneBuilderInterviewSeed = checkpoint.seed;
    sceneBuilderInterviewNarrative.value = checkpoint.narrative || "";
  }
  renderSceneBuilderInterview(state.sceneBuilderInterview);
  for (const control of sceneBuilderInterviewQuestions.querySelectorAll("[data-interview-answer]")) {
    control.value = checkpoint?.answers?.[control.dataset.interviewAnswer] || "";
  }
  sceneBuilderInterviewModal.showModal();
  sceneBuilderInterviewNarrative.focus();
}

function builderRenderTargetControls() {
  const subscenes = state.sceneBuilder.subscenes || [];
  const background = subscenes.find((item) => item.id === "background");
  const targetButton = (item, depth) => `<button type="button" class="${state.activeBuilderRenderTarget === item.id ? "selected" : ""} ${item.id === "main" ? "" : "subscene-target"}" aria-label="${escapeHtml(item.name)} · ${item.kind === "element" ? "element" : item.id === "main" ? "full scene" : "background"}${item.enabled === false ? " (off)" : ""}" data-builder-action="select-render-target" data-render-target-id="${escapeHtml(item.id)}" data-target-depth="${depth}"${builderSubsceneStyle(item)}>${depth ? `${"↳ ".repeat(depth)}` : ""}${escapeHtml(item.name)} <small>${item.id === "main" ? "Full Scene" : item.kind === "element" ? "Element" : "Background"}</small>${item.enabled === false ? " (off)" : ""}</button>`;
  const renderChildren = (parentId, seen = new Set()) => builderTargetChildren(parentId).map((item) => {
    if (seen.has(item.id)) return "";
    const nextSeen = new Set(seen);
    nextSeen.add(item.id);
    const depth = item.kind === "element" ? builderTargetDepth(item.id) : 0;
    return targetButton(item, depth) + renderChildren(item.id, nextSeen);
  }).join("");
  const tabs = targetButton({ id: "main", name: "Full Scene", enabled: true }, 0) + renderChildren("main");
  const breadcrumbs = builderTargetPath(state.activeBuilderRenderTarget).map((item) => escapeHtml(item.name || item.id)).join(" › ");
  const activeSubscene = builderActiveSubscene();
  const toggle = !background
    ? `<button type="button" data-builder-action="enable-background">Use background sub-render</button>`
    : background.enabled
      ? `<button type="button" data-builder-action="disable-subscene" data-render-target-id="background">Turn off background sub-render</button>`
      : `<button type="button" data-builder-action="enable-background">Turn on background sub-render</button>`;
  const elementToggle = activeSubscene?.kind === "element"
    ? activeSubscene.enabled
      ? `<button type="button" data-builder-action="disable-subscene" data-render-target-id="${escapeHtml(activeSubscene.id)}">Turn off element sub-render</button>`
      : `<button type="button" data-builder-action="enable-element-subscene" data-element-id="${escapeHtml(activeSubscene.anchor_element_id || "")}">Turn on element sub-render</button>`
    : "";
  return `<div class="scene-builder-target-bar"><div class="button-row compact scene-builder-target-tree" role="tablist" aria-label="Render target">${tabs}</div>${breadcrumbs ? `<small class="scene-builder-target-breadcrumb">Full Scene › ${breadcrumbs}</small>` : ""}<div class="button-row compact"><button type="button" data-builder-action="add-subscene">Add background sub-render</button>${toggle}${elementToggle}</div></div>`;
}

function builderRenderTargetStatus() {
  const subscene = builderActiveSubscene();
  const status = builderActiveTargetStatus();
  if (!subscene) return "";
  const image = status?.locked_exists && status.locked_image_path
    ? `<img class="scene-builder-target-thumbnail fullscreen-image-trigger" src="${fileUrl(status.locked_image_path)}" alt="${escapeHtml(subscene.name)} locked image">`
    : "";
  const tag = `{{SCENE_RENDER:${state.selectedStorySlug}:${state.selectedSceneSlug}:${subscene.id}}}`;
  return `<div class="scene-builder-card scene-builder-target-status">
    ${image}<div><strong>${status?.locked_exists ? "Previously rendered image" : "No previous image"}</strong>
    <p>${subscene.kind === "element" ? "This target can be used as an image reference in its parent render." : "This target can be used in the Full Scene render."}</p>
    <code>${escapeHtml(tag)}</code></div>
  </div>`;
}

function builderRenderSubsceneSettings() {
  const subscene = builderActiveSubscene();
  if (!subscene) return "";
  const setup = state.sceneBuilder.setup || {};
  const environment = setup.environment || {};
  const overrides = subscene.prompt_overrides || {};
  const field = (key, label, textarea = false) => `<label class="full">${escapeHtml(label)}${textarea
    ? `<textarea data-builder-subscene-field="${key}">${escapeHtml(overrides[key] || "")}</textarea>`
    : `<input value="${escapeHtml(overrides[key] || "")}" data-builder-subscene-field="${key}">`}</label>`;
  if (subscene.kind === "element") {
    const targetSetup = subscene.setup || {};
    const canvas = targetSetup.canvas || {};
    const composition = targetSetup.composition || {};
    const targetEnvironment = targetSetup.environment || {};
    const anchor = (state.sceneBuilder.scene_elements || []).find((item) => item.id === subscene.anchor_element_id) || {};
    const members = (state.sceneBuilder.scene_elements || []).filter((item) => item.subscene_id === subscene.id);
    const placement = (state.sceneBuilder.placements || []).find((item) => item.scene_element_id === anchor.id) || {};
    const parent = (state.sceneBuilder.subscenes || []).find((item) => item.id === anchor.subscene_id);
    const environmentField = (key, label) => {
      const policy = targetEnvironment[key] || { mode: "inherit", value: "" };
      return `<div class="full scene-builder-inheritance-field"><label>${escapeHtml(label)} mode<select data-builder-element-subscene-field="environment.${key}.mode"><option value="inherit"${policy.mode === "inherit" ? " selected" : ""}>Inherit from parent</option><option value="override"${policy.mode === "override" ? " selected" : ""}>Override</option><option value="omit"${policy.mode === "omit" ? " selected" : ""}>Omit</option></select></label><label>${escapeHtml(label)} value<input value="${escapeHtml(policy.value || "")}" data-builder-element-subscene-field="environment.${key}.value"${policy.mode === "override" ? "" : " disabled"}></label></div>`;
    };
    return `<div class="scene-builder-card">
      <h4>${escapeHtml(subscene.name)} element reference</h4>
      <p><strong>Target element:</strong> ${escapeHtml(anchor.display_name || anchor.id || subscene.anchor_element_id)}</p>
      <p><strong>Members:</strong> ${escapeHtml(members.map((item) => item.display_name || item.id).join(", ") || "No elements assigned")}</p>
      <p><strong>Inherited placement:</strong> ${escapeHtml([placement.position_within_cell, placement.depth, parent?.name || (anchor.subscene_id ? anchor.subscene_id : "Full Scene")].filter(Boolean).join(" · ") || "Set on the parent scene")}</p>
      <p>${escapeHtml(anchor.element_visual_override || anchor.fallback_visual_description || "The target element's description and references define the overall subject.")}</p>
      <div class="scene-builder-fields">
        <label class="full">Sub-scene name<input value="${escapeHtml(subscene.name || "")}" data-builder-subscene-name></label>
        ${builderRenderSubsceneColorPalette(subscene)}
        <label>Orientation<select data-builder-element-subscene-field="canvas.orientation">${builderOptionHtml("orientation", canvas.orientation || "landscape")}</select></label>
        <label>Aspect ratio<select data-builder-element-subscene-field="canvas.aspect_ratio">${builderOptionHtml("aspect_ratio", canvas.aspect_ratio || "16:9")}</select></label>
        <label class="full">Primary focal point<input value="${escapeHtml(composition.focal_point || "")}" data-builder-element-subscene-field="composition.focal_point"></label>
        <label class="full">Composition notes<textarea data-builder-element-subscene-field="composition.composition_notes">${escapeHtml(composition.composition_notes || "")}</textarea></label>
        <label class="full">Independent location<textarea data-builder-element-subscene-field="environment.location">${escapeHtml(targetEnvironment.location || "")}</textarea></label>
        ${environmentField("lighting", "Lighting")}
        ${environmentField("mood", "Mood")}
        ${environmentField("weather_or_atmosphere", "Weather / atmosphere")}
        <label class="full">General foreground notes<textarea data-builder-element-subscene-field="environment.general_foreground_notes">${escapeHtml(targetEnvironment.general_foreground_notes || "")}</textarea></label>
        <label class="full">General background notes<textarea data-builder-element-subscene-field="environment.general_background_notes">${escapeHtml(targetEnvironment.general_background_notes || "")}</textarea></label>
      </div>
    </div>`;
  }
  const members = (state.sceneBuilder.scene_elements || []).filter((item) => item.subscene_id === subscene.id);
  return `<div class="scene-builder-card">
    <h4>${escapeHtml(subscene.name)} prompt</h4>
    <p><strong>Members:</strong> ${escapeHtml(members.map((item) => item.display_name || item.id).join(", ") || "No elements assigned")}</p>
    <p>Canvas, art style, location, lighting, mood, and atmosphere are inherited from Full Scene. Edit those universal values there; changing them invalidates this lock.</p>
    <dl><dt>Canvas</dt><dd>${escapeHtml(setup.canvas?.orientation || "landscape")} ${escapeHtml(setup.canvas?.aspect_ratio || "16:9")}</dd><dt>Location</dt><dd>${escapeHtml(environment.location || "—")}</dd><dt>Lighting</dt><dd>${escapeHtml(environment.lighting || "—")}</dd></dl>
    <div class="scene-builder-fields">
      <label class="full">Sub-scene name<input value="${escapeHtml(subscene.name || "")}" data-builder-subscene-name></label>
      ${builderRenderSubsceneColorPalette(subscene)}
      ${field("focal_point", "Primary focal point")}
      ${field("composition_notes", "Composition notes", true)}
      ${field("general_foreground_notes", "General foreground notes", true)}
      ${field("general_background_notes", "General background notes", true)}
    </div>
  </div>`;
}

function builderRenderImportContext() {
  const provenance = state.sceneBuilder?.source_provenance;
  if (!provenance) return "";
  const readiness = state.sceneBuilderReadiness || {};
  const constraints = provenance.constraints || {};
  const blockers = readiness.blockers || [];
  const exact = constraints.exact_details || [];
  const continuity = constraints.continuity_requirements || [];
  return `
    <section class="scene-builder-card">
      <span class="eyebrow">Imported candidate</span>
      <h3>${escapeHtml(provenance.candidate_id || "Scene candidate")} · ${escapeHtml(readiness.status || "draft")}</h3>
      ${blockers.length ? `<p><strong>Needs attention:</strong> ${blockers.map((item) => escapeHtml(item)).join(" · ")}</p>` : "<p>Ready for manual review and rendering.</p>"}
      ${exact.length ? `<p><strong>Exact details:</strong> ${exact.map((item) => escapeHtml(item)).join(" · ")}</p>` : ""}
      ${continuity.length ? `<details><summary>Continuity requirements</summary><ul>${continuity.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></details>` : ""}
    </section>
  `;
}

function openSceneBuilderContext() {
  const content = builderRenderImportContext();
  if (!content) return;
  sceneBuilderContextContent.innerHTML = content;
  sceneBuilderContextDialog.showModal();
}

async function openSceneBuilder(preferredRenderTargetId = "main") {
  state.sceneBuilderLoadState = "loading";
  state.requestedBuilderTargetId = preferredRenderTargetId;
  if (!state.selectedStorySlug || !state.selectedSceneSlug) {
    showSceneBuilderMessage("Select a scene first.", "error");
    return;
  }
  const storySlug = state.selectedStorySlug;
  const sceneSlug = state.selectedSceneSlug;
  const selection = beginSelection("scene-builder");
  const selectionMatches = () => selectionIsCurrent(selection)
    && state.selectedStorySlug === storySlug
    && state.selectedSceneSlug === sceneSlug
    && state.requestedSceneContext.storySlug === storySlug
    && state.requestedSceneContext.sceneSlug === sceneSlug;
  sceneBuilderOpen.disabled = true;
  sceneBuilderStatus.textContent = sceneBuilderNavigationLabel();
  updateSceneBuilderNavigation();
  showSceneBuilderMessage("Loading Scene Builder...");
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(storySlug)}/scenes/${encodeURIComponent(sceneSlug)}/builder?include_references=false`, {
      signal: selection.controller.signal,
    });
    if (!selectionMatches()) return;
    const document = payload.document || {};
    if (document.blocked) {
      state.sceneBuilderLoadState = "unavailable";
      showSceneBuilderMessage(document.error || "Scene Builder JSON is blocked.", "error");
      return;
    }
    const loadedBuilderContext = {
      storySlug: document.story?.slug || storySlug,
      sceneSlug: document.scene?.slug || sceneSlug,
    };
    sceneBuilderStatus.textContent = sceneBuilderNavigationLabel(document);
    if (!state.sceneDetail || !sceneDocumentMatches()) {
      state.loadedSceneContext = { ...loadedBuilderContext };
    }
    state.sceneBuilder = document.data || {};
    state.sceneBuilderRenderTargets = document.render_targets || [];
    state.sceneBuilderReadiness = document.readiness || null;
    state.sceneBuilderOptions = payload.options || {};
    state.sceneBuilderReferences = [];
    state.activeBuilderRenderTarget = preferredRenderTargetId === "main"
      || (state.sceneBuilder.subscenes || []).some((item) => item.id === preferredRenderTargetId)
      ? preferredRenderTargetId
      : "main";
    const restoringTask = builderTaskRestorePending && taskStoryRoute.get("story_slug") === storySlug && taskStoryRoute.get("scene_slug") === sceneSlug;
    if (restoringTask && preferredRenderTargetId !== state.activeBuilderRenderTarget) {
      window.ZetTaskCapture.notice(`Recorded render target "${preferredRenderTargetId}" is unavailable. Showing the main scene.`);
    }
    state.selectedBuilderPlacementId = state.sceneBuilder.placements?.[0]?.id || null;
    state.selectedBuilderElementId = state.sceneBuilder.placements?.[0]?.scene_element_id || state.sceneBuilder.scene_elements?.[0]?.id || null;
    const recordedElement = taskStoryRoute.get("task_element");
    if (restoringTask && recordedElement) {
      if (state.sceneBuilder.scene_elements?.some((item) => item.id === recordedElement)) state.selectedBuilderElementId = recordedElement;
      else window.ZetTaskCapture.notice(`Recorded editor element "${recordedElement}" is unavailable.`);
    }
    if (restoringTask) builderTaskRestorePending = false;
    state.builderResponsiveSection = "elements";
    state.sceneBuilderOpen = true;
    state.loadedBuilderContext = loadedBuilderContext;
    state.sceneBuilderLoadState = "selected";
    renderSceneBuilder();
    state.savedBaselines.sceneBuilder = sceneBuilderSnapshot();
    updateDirtyIndicators();
    updateSceneBuilderNavigation();
    showSceneBuilderMessage("Scene Builder loaded. Loading image references and analysis…", "info");
    void Promise.allSettled([
      fetchJson("/api/scene-image-picker", { signal: selection.controller.signal }),
      loadScenePromptAnalysis(state.activeBuilderRenderTarget, { signal: selection.controller.signal }),
      builderLoadSelectedElementCostumes(builderSelectedElement(), { signal: selection.controller.signal }),
    ]).then((results) => {
      if (!selectionMatches()) return;
      const [references] = results;
      if (references.status === "fulfilled") state.sceneBuilderReferences = references.value.rows || [];
      renderSceneBuilder();
      const failed = results.some((result) => result.status === "rejected");
      showSceneBuilderMessage(failed
        ? "Scene Builder is ready; some secondary data could not be loaded."
        : state.sceneBuilder._migrated_from_schema_version
          ? "This scene used an older Scene Builder schema and has been migrated to v2. Save to update the JSON file."
          : "Scene Builder loaded.", failed ? "info" : "success");
    });
  } catch (error) {
    showSceneBuilderMessage(error.message, "error");
    if (selectionMatches()) state.sceneBuilderLoadState = "unavailable";
  } finally {
    updateSceneContextControls();
  }
}

async function activateSceneBuilderPage() {
  if (!state.selectedStorySlug || !state.selectedSceneSlug) {
    showSceneMessage("Select a scene first.", "error");
    return;
  }
  await selectStoryScene(state.selectedStorySlug, state.selectedSceneSlug, {
    destination: "scene-builder",
    renderTargetId: state.activeBuilderRenderTarget || "main",
  });
}

async function saveSceneBuilder({ fullScene = false } = {}) {
  if (!state.sceneBuilder || !state.selectedStorySlug || !state.selectedSceneSlug || !sceneDocumentMatches()) {
    showSceneBuilderMessage("Wait for the requested scene to finish loading before saving.", "error");
    return;
  }
  builderSyncControls();
  const targetId = state.activeBuilderRenderTarget || "main";
  const activeSubscene = fullScene ? null : builderActiveSubscene();
  const baselineData = savedSceneBuilderData();
  try {
    const endpoint = activeSubscene
      ? `/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/builder/subscenes/${encodeURIComponent(targetId)}`
      : `/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/builder`;
    const payload = await fetchJson(endpoint, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(activeSubscene ? {
        subscene: activeSubscene,
        expected_revision: state.sceneBuilder._revision || 0,
        dialogue_changes: builderDialogueChanges(state.sceneBuilder, baselineData),
      } : state.sceneBuilder),
    });
    if (activeSubscene) {
      const persistedData = payload.document?.data;
      const persistedSubscene = builderSubsceneFromData(persistedData, targetId);
      replaceBuilderSubscene(state.sceneBuilder, targetId, persistedSubscene);
      const baseline = savedSceneBuilderData();
      replaceBuilderSubscene(baseline, targetId, persistedSubscene);
      baseline.dialogue = JSON.parse(JSON.stringify(persistedData?.dialogue || baseline.dialogue || []));
      if (persistedData && Object.hasOwn(persistedData, "_revision")) {
        state.sceneBuilder._revision = persistedData._revision;
        baseline._revision = persistedData._revision;
      }
      state.savedBaselines.sceneBuilder = JSON.stringify(baseline);
    } else {
      state.sceneBuilder = payload.document?.data || state.sceneBuilder;
      state.savedBaselines.sceneBuilder = sceneBuilderSnapshot();
    }
    state.sceneBuilderRenderTargets = payload.document?.render_targets || state.sceneBuilderRenderTargets;
    state.sceneBuilderReadiness = payload.document?.readiness || null;
    state.sceneBuilder._validation_warnings = payload.document?.validation_warnings || state.sceneBuilder._validation_warnings || [];
    updateStoryGitWarning(payload.has_story_changes);
    renderSceneBuilder();
    updateDirtyIndicators();
    showSceneBuilderMessage(payload.message || `${activeSubscene ? "Subscene" : "Scene Builder"} saved.`, "success");
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

async function continueSceneBuilderFrom() {
  const sourceSceneSlug = builderContinueScene.value;
  if (!sourceSceneSlug) {
    return;
  }
  if (!requireSavedSceneBuilder("continuing from another scene")) return;
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

async function disableSceneSubscene(targetId) {
  if (!targetId || !state.selectedStorySlug || !state.selectedSceneSlug) return;
  if (!requireSavedSceneBuilder("disabling this subscene")) return;
  try {
    const payload = await fetchJson(`/api/stories/${encodeURIComponent(state.selectedStorySlug)}/scenes/${encodeURIComponent(state.selectedSceneSlug)}/subscenes/${encodeURIComponent(targetId)}/disable`, { method: "POST" });
    state.sceneBuilder = payload.document?.data || state.sceneBuilder;
    state.sceneBuilderRenderTargets = payload.document?.render_targets || [];
    state.activeBuilderRenderTarget = builderTargetParentId((state.sceneBuilder.subscenes || []).find((item) => item.id === targetId)) || "main";
    state.selectedBuilderElementId = state.sceneBuilder.scene_elements?.find((item) => !item.subscene_id || item.subscene_id === state.activeBuilderRenderTarget)?.id || null;
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
    openFullscreenImage(referenceImage.src, referenceImage.alt || "Reference image", {
      document: {
        candidate_pending: referenceImage.dataset.candidatePending === "true",
        image_exists: true,
        story: { slug: referenceImage.dataset.storySlug || "" },
        scene: { slug: referenceImage.dataset.sceneSlug || "" },
      },
    });
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
    const selectedElement = builderSelectedElement();
    const costumeKey = `${selectedElement?.character || ""}\n${selectedElement?.phase || ""}`;
    if (selectedElement?.resource_type === "Character" && selectedElement.character && selectedElement.phase && !state.builderCostumesByCharacterPhase[costumeKey]) {
      builderLoadSelectedElementCostumes(selectedElement).then(() => renderSceneBuilder()).catch((error) => showSceneBuilderMessage(error.message, "error"));
    }
  } else {
    const action = target.dataset.builderAction;
    if (action === "builder-section") setBuilderResponsiveSection(target.dataset.builderSection);
    if (action === "select-render-target") {
      selectSceneBuilderTarget(target.dataset.renderTargetId || "main");
    }
    if (action === "toggle-context-elements") {
      state.showBuilderContextElements = !state.showBuilderContextElements;
      renderSceneBuilder();
    }
    if (action === "add-subscene") addSceneBuilderSubscene();
    if (action === "set-subscene-color") {
      builderSyncControls();
      const subscene = builderActiveSubscene();
      if (subscene && BUILDER_SUBSCENE_COLORS.includes(target.dataset.subsceneColor)) {
        subscene.ui_color = target.dataset.subsceneColor;
        renderSceneBuilder();
      }
    }
    if (action === "enable-background") setBackgroundSubsceneEnabled(true);
    if (action === "disable-subscene") {
      const targetId = target.dataset.renderTargetId || "background";
      if (targetId === "background") setBackgroundSubsceneEnabled(false);
      else disableSceneSubscene(targetId);
    }
    if (action === "enable-element-subscene") enableSelectedElementSubscene(target.dataset.elementId || "");
    if (action === "open-element-subscene") {
      selectSceneBuilderTarget(target.dataset.renderTargetId || "main");
    }
    if (action === "interview") restartSceneBuilderInterview();
    if (action === "candidate-details") openSceneBuilderContext();
    if (action === "continue-from") openBuilderContinueDialog();
    if (action === "add-element") openBuilderElementDialog();
    if (action === "duplicate-element") builderDuplicateSelectedElement();
    if (action === "delete-element") builderRemoveSelectedElement();
    if (action === "reference-add") {
      builderSyncControls();
      const element = builderSelectedElement();
      element.reference_images = element.reference_images || [];
      element.reference_images.push({ tag: "", roles: [], preserve: [], change: [], ignore: [], notes: "" });
      renderSceneBuilder();
    }
    if (["reference-up", "reference-down", "reference-remove"].includes(action)) {
      builderSyncControls();
      const references = builderSelectedElement()?.reference_images || [];
      const index = Number(target.dataset.builderReferenceIndex);
      if (action === "reference-remove") references.splice(index, 1);
      if (action === "reference-up" && index > 0) [references[index - 1], references[index]] = [references[index], references[index - 1]];
      if (action === "reference-down" && index < references.length - 1) [references[index + 1], references[index]] = [references[index], references[index + 1]];
      renderSceneBuilder();
    }
    if (action === "pick-image-tag") openBuilderImagePicker(Number(target.dataset.builderReferenceIndex || 0));
    if (action === "open-catalog-item") {
      const catalogId = target.dataset.catalogId || "";
      activatePage("auxiliary-resources", { skipAutosave: true, preferredCatalogId: catalogId });
    }
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
    if (action === "save") saveSceneBuilder();
    if (action === "cancel-subscene") cancelSceneBuilderSubsceneEdits();
    if (action === "export") exportSceneBuilderMarkdown();
    if (action === "render") renderSceneBuilderScene();
    if (action === "analyze-prompt") analyzeScenePrompt();
    if (action === "view-analysis") viewScenePromptAnalysis();
    if (action === "open-page" && target.dataset.builderPage) activatePage(target.dataset.builderPage);
  }
});

builderContinueCancel.addEventListener("click", closeBuilderContinueDialog);

builderContinueConfirm.addEventListener("click", continueSceneBuilderFrom);

sceneBuilderInterviewClose.addEventListener("click", () => sceneBuilderInterviewModal.close());

sceneBuilderInterviewCancel.addEventListener("click", () => sceneBuilderInterviewModal.close());

sceneBuilderInterviewNext.addEventListener("click", runSceneBuilderInterview);

sceneBuilderInterviewApply.addEventListener("click", applySceneBuilderInterview);

sceneCandidateSource.addEventListener("change", async () => {
  state.selectedSceneCandidateSource = sceneCandidateSource.value;
  state.selectedSceneCandidateId = null;
  await loadSceneCandidates();
});

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
    const element = builderSelectedElement();
    if (!element) {
      return;
    }
    if (mode === "logical" && !item.logical_reference?.reference_key) {
      showSceneBuilderMessage("This image has no active preferred reference key.", "error");
      return;
    }
    element.reference_images = element.reference_images || [];
    const index = Number(state.builderReferenceIndex || 0);
    element.reference_images[index] = element.reference_images[index] || { roles: ["visual reference"], ignore: ["source pose", "source background", "source framing"], notes: "" };
    const selectedReference = element.reference_images[index];
    delete selectedReference.tag;
    delete selectedReference.asset_id;
    delete selectedReference.reference_key;
    selectedReference[mode === "logical" ? "reference_key" : "asset_id"] = mode === "logical"
      ? item.logical_reference?.reference_key || ""
      : item.asset_id || "";
    selectedReference.set_id = builderImagePickerSet.value || item.logical_reference?.set_id || "";
    selectedReference.primary_prompt_source = !element.reference_images.some((reference, refIndex) => refIndex !== index && reference.primary_prompt_source);
    const referenceTag = mode === "logical"
      ? `{{LIB:REF:${item.logical_reference.reference_key}}}`
      : `{{LIB:ASSET:${item.asset_id}}}`;
    state.sceneBuilderReferences = [
      ...(state.sceneBuilderReferences || []).filter((reference) => reference.tag !== referenceTag),
      { ...item, tag: referenceTag, label: item.label || item.file_name, kind: "entity-library" },
    ];
    if (!element.reference_images[index].roles?.length) {
      element.reference_images[index].roles = ["visual reference"];
    }
    builderImagePickerModal.close();
    renderSceneBuilder();
    showSceneBuilderMessage(`Selected ${item.file_name || "image"}.`, "success");
  },
  onError: (error) => showSceneBuilderMessage(error.message, "error"),
};

function openBuilderImagePicker(referenceIndex = 0) {
  builderSyncControls();
  const element = builderSelectedElement();
  if (!element) {
    return;
  }
  state.builderReferenceIndex = referenceIndex;
  builderImagePickerSearch.value = element.resource_type === "Character"
    ? [element.character || element.display_name, element.phase, element.costume].filter(Boolean).join(" ")
    : element.display_name || "";
  builderImagePickerMode.value = element.resource_type === "Character" && element.costume ? "logical" : "asset";
  state.builderImagePickerSearch = builderImagePickerSearch.value;
  builderImagePickerModal.showModal();
  builderImagePickerSearch.focus();
  loadEntityLibraryPickerFilters(element).then(() => loadImagePickerReferences(builderImagePicker)).catch((error) => {
    builderImagePickerStatus.textContent = "Filter options failed to load.";
    showSceneBuilderMessage(error.message, "error");
  });
}

const ollamaModelControls = () => [
  settingAiAssetWorkflowModel,
  settingPromptCondenseModel,
  settingAiPromptAnalysisModel,
  settingAiImageDescriptionModel,
  settingImagePromptGenerationModel,
  settingCostumeWizardModel,
  settingQuickCharacterWizardModel,
  settingAiSceneBuilderModel,
  settingLocalBodyReferenceFaceGateModel,
  settingLocalBodyReferenceReviewModel,
];

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

storyPhonePrevious.addEventListener("click", () => moveStoryPhoneScene(-1));

storyPhoneNext.addEventListener("click", () => moveStoryPhoneScene(1));

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

sceneBuilderContextClose.addEventListener("click", () => sceneBuilderContextDialog.close());

sceneBuilderContextDialog.addEventListener("click", (event) => {
  if (event.target === sceneBuilderContextDialog) sceneBuilderContextDialog.close();
});

sceneBuilderContextDialog.addEventListener("close", () => {
  sceneBuilderContextContent.replaceChildren();
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

storyCreate.addEventListener("click", createStory);

storySave.addEventListener("click", saveStory);

storyView.addEventListener("click", openStoryViewer);

storyScenes.addEventListener("click", openStoryScenes);

storyRename.addEventListener("click", renameStory);

storyDelete.addEventListener("click", deleteStory);

storyGitStatus.addEventListener("click", () => runStoryGitAction("status"));

storyGitPull.addEventListener("click", () => runStoryGitAction("pull"));

storyGitCommit.addEventListener("click", () => runStoryGitAction("commit"));

sceneStorySelect.addEventListener("change", async () => {
  const requestedStory = sceneStorySelect.value || null;
  sceneStorySelect.disabled = true;
  const changed = await selectStoryScene(requestedStory, null);
  sceneStorySelect.disabled = false;
  if (changed === false) sceneStorySelect.value = state.selectedStorySlug || "";
});

sceneCreate.addEventListener("click", createScene);

sceneSave.addEventListener("click", saveScene);

sceneRename.addEventListener("click", renameScene);

sceneMove.addEventListener("click", moveScene);

sceneDelete.addEventListener("click", deleteScene);

sceneStageRender.addEventListener("click", stageSceneRender);

sceneBuilderOpen.addEventListener("click", activateSceneBuilderPage);

sceneToggleImage.addEventListener("click", toggleSceneImage);

enableFullscreenImage(sceneImagePreview, () => ({
  sceneSlug: state.selectedSceneSlug,
  scenes: state.scenes,
  storySlug: state.selectedStorySlug,
  document: state.sceneDetail,
}));

zineStorySelect.addEventListener("change", async () => {
  state.zineStorySlug = zineStorySelect.value || null;
  await loadZineStorySources();
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

builderElementNewAux.addEventListener("click", () => {
  builderElementNewAuxForm.hidden = false;
  builderElementNewAuxLabel.focus();
});

builderElementNewAuxCancel.addEventListener("click", closeBuilderElementAuxForm);

builderElementNewAuxSave.addEventListener("click", createBuilderElementAuxResource);

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

promptReviewSceneBuilder.addEventListener("click", async () => {
  const scene = selectedPromptReviewScene();
  if (!scene) return;
  await selectStoryScene(scene.storySlug, scene.sceneSlug, {
    destination: "scene-builder",
    renderTargetId: scene.renderTargetId || "main",
  });
});

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

sceneBuilderPrevious.addEventListener("click", () => navigateSceneBuilder(-1));

sceneBuilderNext.addEventListener("click", () => navigateSceneBuilder(1));

renderConsoleSceneBuilder.addEventListener("click", async () => {
  const manifest = state.renderConsoleDetail?.manifest || {};
  if (!manifest.story_slug || !manifest.scene_slug) return;
  await selectStoryScene(manifest.story_slug, manifest.scene_slug, {
    destination: "scene-builder",
    renderTargetId: manifest.render_target_id || "main",
  });
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

storyText.addEventListener("input", updateDirtyIndicators);

storySettingsFields.addEventListener("input", updateDirtyIndicators);

storySettingsFields.addEventListener("change", updateDirtyIndicators);

sceneText.addEventListener("input", updateDirtyIndicators);

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

window.addEventListener("popstate", () => {
  void (async () => {
    const params = new URLSearchParams(window.location.search);
    const page = params.get("page") || state.lastWorkspacePages[state.workspace] || "scenes";
    const story = params.get("story_slug") || state.selectedStorySlug;
    const scene = params.get("scene_slug") || null;
    const allowed = await guardCurrentEditor();
    if (!allowed) {
      syncBrowserRoute({ replace: true });
      return;
    }
    if (pageWorkspace(page) === "story" || PRODUCTION_PAGES.has(page)) {
      await selectStoryScene(story, scene, {
        skipGuard: true,
        fromHistory: true,
        updateHistory: false,
        destination: page,
        renderTargetId: params.get("render_target_id") || "main",
      });
    } else {
      await activatePage(page, { skipAutosave: true, fromHistory: true, updateHistory: false });
    }
  })().catch((error) => showActionMessage(`Unable to restore navigation context: ${error.message}`, "error"));
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
    source_url: source.href, universe_id: state.universeId || null, selections };
});

window.zetSceneLayout = {
  drafts: new Map(),
  current() {
    const activeTarget = state.activeBuilderRenderTarget || "main";
    const definition = (state.sceneBuilder?.subscenes || []).find((item) => item.id === activeTarget);
    return {
      storySlug: state.selectedStorySlug,
      sceneSlug: state.selectedSceneSlug,
      data: state.sceneBuilder,
      activeTarget,
      layout: this.drafts.get(activeTarget) || (activeTarget === "main" ? state.sceneBuilder?.layout_3d : definition?.layout_3d),
    };
  },
  setLayout(layout) {
    if (!state.sceneBuilder) return;
    const targetId = state.activeBuilderRenderTarget || "main";
    this.drafts.set(targetId, layout);
    if (targetId === "main") state.sceneBuilder.layout_3d = layout;
    else {
      const definition = (state.sceneBuilder.subscenes || []).find((item) => item.id === targetId);
      if (definition) definition.layout_3d = layout;
    }
    updateDirtyIndicators();
  },
  setActiveTarget(targetId) {
    state.activeBuilderRenderTarget = targetId || "main";
    updateDirtyIndicators();
  },
  async save() {
    const session = this.current();
    const targetId = session.activeTarget || "main";
    const response = await fetch(`/api/stories/${encodeURIComponent(session.storySlug)}/scenes/${encodeURIComponent(session.sceneSlug)}/builder/3d-layout?target_id=${encodeURIComponent(targetId)}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ layout_3d: this.drafts.get(targetId) || session.layout || state.sceneBuilder.layout_3d, expected_revision: state.sceneBuilder._revision || 0 }),
    });
    const payload = await response.json();
    if (!response.ok) { showSceneBuilderMessage(payload.detail || "Unable to save 3D layout.", "error"); return false; }
    const saved = payload.document?.data;
    if (saved) {
      state.sceneBuilder._revision = saved._revision;
      const baseline = savedSceneBuilderData() || {};
      baseline._revision = saved._revision;
      const definition = (state.sceneBuilder.subscenes || []).find((item) => item.id === targetId);
      if (targetId === "main") {
        state.sceneBuilder.layout_3d = this.drafts.get(targetId);
        baseline.layout_3d = saved.layout_3d;
        for (const savedDefinition of saved.subscenes || []) {
          const baseDefinition = (baseline.subscenes || []).find((item) => item.id === savedDefinition.id);
          if (baseDefinition) baseDefinition.layout_3d = savedDefinition.layout_3d;
          const currentDefinition = (state.sceneBuilder.subscenes || []).find((item) => item.id === savedDefinition.id);
          if (currentDefinition) currentDefinition.layout_3d = savedDefinition.layout_3d;
        }
      } else if (definition) {
        definition.layout_3d = this.drafts.get(targetId);
        const baseDefinition = (baseline.subscenes || []).find((item) => item.id === targetId);
        if (baseDefinition) baseDefinition.layout_3d = definition.layout_3d;
      }
      this.drafts.delete(targetId);
      state.savedBaselines.sceneBuilder = JSON.stringify(baseline);
    }
    updateDirtyIndicators();
    showSceneBuilderMessage(payload.message || "3D layout saved.", "success");
    return true;
  },
  isEditingFullScene() {
    return !builderActiveSubscene();
  },
};

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
    // Its usual Scene Builder page may be hidden while the library is active.
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
