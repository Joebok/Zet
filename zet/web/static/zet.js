const state = {
  characters: [],
  phasesByCharacter: {},
  character: null,
  phase: null,
  assets: [],
  selectedAssetId: null,
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
  state.selectedAssetId = preferredAssetId || state.selectedAssetId || state.assets[0]?.asset_id || null;
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
}

function setupTabs() {
  for (const button of document.querySelectorAll(".tab")) {
    button.addEventListener("click", () => {
      for (const item of document.querySelectorAll(".tab")) {
        item.classList.toggle("active", item === button);
      }
      const page = button.dataset.page;
      document.querySelector("#assets-page").classList.toggle("active", page === "assets");
      document.querySelector("#placeholder-page").classList.toggle("active", page !== "assets");
      placeholderTitle.textContent = button.textContent;
    });
  }
}

characterSelect.addEventListener("change", async () => {
  state.character = characterSelect.value;
  state.phase = null;
  state.selectedAssetId = null;
  updatePhaseSelect();
  await loadAssets();
});

phaseSelect.addEventListener("change", async () => {
  state.phase = phaseSelect.value;
  state.selectedAssetId = null;
  await loadAssets();
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
