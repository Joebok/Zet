import {mountCandidateBoard, confirmCandidateDeletion} from "./candidate_board_component.js?v=20261115-candidate-identities";
import {renderProposalAcceptance, renderProposalComparison} from "./interview_proposals.js";
import {mountProductionWorkspace} from "./production_workspace.js?v=20261124-workspace-shell";

const $ = id => document.getElementById(id);
const page = $("minor-characters-page");
const bridge = window.zetQuickCharacterWizard;
const form = $("mc-authoring");
let sharedBoard;
let productionWorkspace;
const escape = value => String(value ?? "").replace(/[&<>"']/g, char =>
  ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"})[char]);
let character, universe, entryAsset, timer;
let view = "", busy = false, epoch = 0, mutation = 0;
const modelOverrides = new Map(Object.entries(JSON.parse(sessionStorage.getItem("mc-model-overrides") || "{}")));
let saving;
const edits = new Map();
const board = () => character.boards[view];
const base = () => "/" + character.character_id;
const asset = () => base() + "/assets/" + view;
const media = (cid, part = "image", assetView = view) =>
  scoped("/api/minor-characters" + base() + "/assets/" + assetView + "/candidates/" + cid + "/" + part);
const scoped = path => path + "?universe_id=" + encodeURIComponent(universe);
const api = (path, method = "GET", body) => bridge.fetchJson("/api/minor-characters" + path, {
  method, bindToPage:false, ...(body === undefined ? {} : {
    headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)
  })
});
const promptDrafts = new Map();
const pendingWrites = new Map();
const promptKey = () => [universe, character?.character_id, view].join(":");
const renderActive = status => ["SUBMITTING", "QUEUED", "RUNNING"].includes(status);
const modelKey = () => JSON.stringify([universe, character?.character_id]);
const selectedModel = () => modelOverrides.get(modelKey()) || "";
const modelLabel = job => job.effective_model || "Model not recorded";
const pendingReview = current => current.text_job?.status === "COMPLETE" && current.text_job.review?.proposals.length;

async function chooseModel() {
  const key = modelKey();
  const value = await window.ZetModelPicker.open({value:selectedModel(),required:["vision"],allowDefault:true});
  if (value === null) return;
  modelOverrides.set(key, value);
  sessionStorage.setItem("mc-model-overrides", JSON.stringify(Object.fromEntries(modelOverrides)));
  if (key === modelKey()) $("mc-authoring-model").textContent = value || "Use configured default";
}

function routeUrl(id, assetView) {
  const params = new URLSearchParams({page:"minor-characters", universe_id:universe});
  if (id) params.set("minor_character", id);
  if (id && assetView) params.set("view", assetView);
  const taskUniverse = new URLSearchParams(location.search).get("task_universe");
  if (taskUniverse) params.set("task_universe", taskUniverse);
  return "?" + params;
}
function route(id, assetView, replace = false) {
  const url = routeUrl(id, assetView);
  if (location.search !== url) history[replace ? "replaceState" : "pushState"]({}, "", url);
}
function message(text, error = false) {
  $("mc-message").textContent = text;
  $("mc-message").classList.toggle("error", error);
}
function adopt(value) {
  character = value;
  const key = promptKey(), pending = pendingWrites.get(key), job = board()?.text_job;
  if (pending && (job?.id !== pending.id || job.status !== "RUNNING")) {
    if (job?.id === pending.id && job.status === "COMPLETE" && promptDrafts.get(key) === pending.draft)
      promptDrafts.delete(key);
    pendingWrites.delete(key);
  }
  render();
}
async function run(action) {
  if (busy) return;
  clearTimeout(timer);
  busy = true;
  mutation++;
  message("");
  try { await action(); }
  catch (error) { message(error.message, true); }
  finally { busy = false; schedule(); }
}
async function flush(savePrompt = false) {
  if (saving) await saving;
  if ((!edits.size && !savePrompt) || !character || universe !== bridge.universe()) return;
  const token = epoch, id = base(), key = promptKey(), draft = promptDrafts.get(key);
  const submitted = new Map(edits);
  const data = Object.fromEntries(submitted);
  if (savePrompt) data.prompt = draft ?? board().prompt_body ?? "";
  if (view) data.view = view;
  data.template_hash = character.template_hash;
  data.revision = character.revision;
  mutation++;
  saving = (async () => {
    const result = await api(id, "PATCH", data);
    if (token !== epoch || universe !== bridge.universe()) return;
    for (const [field, value] of submitted) if (edits.get(field) === value) edits.delete(field);
    if (savePrompt && promptDrafts.get(key) === draft) promptDrafts.delete(key);
    adopt(result.character);
  })();
  try { await saving; }
  finally { saving = null; schedule(); }
}
async function change(path, data) {
  const token = epoch;
  await flush();
  if (token !== epoch || universe !== bridge.universe()) return false;
  const result = await api(path, "POST", {...data, revision:character.revision, template_hash:character.template_hash});
  if (token !== epoch || universe !== bridge.universe()) return false;
  adopt(result.character);
  return true;
}
function disposeBoard() {
  sharedBoard?.dispose();
  sharedBoard = undefined;
}
async function navigate(id, assetView) {
  await flush();
  route(id, assetView);
  await load();
}
async function renameCharacter(id, name) {
  const next = window.prompt("Rename Minor Character", name);
  if (next === null || next.trim() === name) return;
  const current = character?.character_id === id ? character : (await api("/" + encodeURIComponent(id))).character;
  const result = await api("/" + encodeURIComponent(id), "PATCH", {
    name:next, revision:current.revision, template_hash:current.template_hash,
  });
  if (character?.character_id === id) adopt(result.character);
  else await load();
  message("Minor Character renamed.");
}
async function deleteCharacter(id, name) {
  const preview = await api("/" + encodeURIComponent(id) + "/delete-preview", "POST", {});
  const dialog = document.createElement("dialog");
  dialog.className = "protected-effects-dialog";
  const title = document.createElement("h2"); title.textContent = "Delete " + name + "?";
  const description = document.createElement("p"); description.textContent = "This removes the workspace. Published Inventory images and their references are kept.";
  const form = document.createElement("form"); form.method = "dialog";
  const checks = [];
  for (const effect of preview.protected_effects) {
    const label = document.createElement("label"), input = document.createElement("input");
    input.type = "checkbox"; checks.push(input); label.append(input);
    if (effect.image_url) { const image = document.createElement("img"); image.src = scoped(effect.image_url); image.alt = "Affected image preview"; label.append(image); }
    label.append(document.createTextNode(effect.label)); form.append(label);
  }
  const actions = document.createElement("div"); actions.className = "button-row";
  const cancel = document.createElement("button"); cancel.value = "cancel"; cancel.textContent = "Cancel";
  const all = document.createElement("button"); all.type = "button"; all.textContent = "Approve all";
  all.onclick = () => { checks.forEach(check => { check.checked = true; }); confirm.disabled = false; };
  const confirm = document.createElement("button"); confirm.value = "confirm"; confirm.textContent = "Delete workspace"; confirm.className = "danger-action"; confirm.disabled = checks.length > 0;
  checks.forEach(check => check.onchange = () => { confirm.disabled = checks.some(item => !item.checked); });
  actions.append(cancel); if (checks.length) actions.append(all); actions.append(confirm); form.append(actions);
  dialog.append(title, description, form); document.body.append(dialog);
  try {
    dialog.showModal();
    await new Promise(resolve => dialog.addEventListener("close", resolve, {once:true}));
    if (dialog.returnValue !== "confirm") return;
  } finally { dialog.remove(); }
  await api("/" + encodeURIComponent(id), "DELETE", {...preview, approved_effects:preview.protected_effects.map(effect => effect.id)});
  if (character?.character_id === id) { character = null; route(""); }
  await load();
  message(name + " deleted.");
}
function cards(id, assets) {
  return assets.map(item => {
    const href = escape(routeUrl(id, item.view));
    const label = item.view === "STYLE" ? "Style" : item.label;
    const preview = item.thumbnail_url
      ? `<img loading="lazy" src="${escape(scoped(item.thumbnail_url))}" alt="Locked ${escape(label)}">`
      : `<span>No locked image</span>`;
    const status = item.thumbnail_url
      ? `<small><span class="narrative-render-mode-pill ${item.render_mode === "final" ? "final" : "draft"}">${item.render_mode === "final" ? "Final" : "Draft"}</span> · Locked</small>`
      : "";
    return `<a data-mc-route class="mc-asset-card" href="${href}"><strong>${escape(label)}</strong>${preview}${status}</a>`;
  }).join("");
}
async function load() {
  clearTimeout(timer);
  const token = epoch;
  const next = bridge.universe();
  if (universe !== next) { character = null; edits.clear(); }
  else {
    try { await flush(); }
    catch (error) {
      if (token === epoch) route(character.character_id, view, true);
      throw error;
    }
  }
  if (token !== epoch) return;
  const requestEpoch = ++epoch;
  disposeBoard();
  universe = next;
  character = null;
  view = "";
  $("mc-feedback").value = $("mc-evidence").value = "";
  $("mc-proposals").replaceChildren();
  message("");
  $("mc-editor").hidden = true;
  $("mc-list-panel").hidden = true;
  const params = new URLSearchParams(location.search);
  const id = params.get("minor_character"), requested = params.get("view");
  let unavailable = "";
  if (id) {
    try {
      const result = await api("/" + encodeURIComponent(id));
      if (requestEpoch !== epoch || next !== bridge.universe()) return;
      if (requested && !Object.hasOwn(result.character.boards, requested)) {
        message("That asset is unavailable. Showing its collection.", true);
        route(id, "", true);
      } else view = requested || "";
      adopt(result.character);
      schedule();
      return;
    } catch (error) {
      if (requestEpoch !== epoch || next !== bridge.universe()) return;
      unavailable = error.message;
    }
  }
  const {characters} = await api("");
  if (requestEpoch !== epoch || next !== bridge.universe()) return;
  if (unavailable) {
    route("", "", true);
    message(unavailable, true);
  }
  $("mc-page-title").textContent = "Minor Characters";
  $("mc-list").innerHTML = characters.map(row => `<section class="control-panel">
    <h2>${escape(row.name)}</h2><div class="button-row"><a data-mc-route href="${escape(routeUrl(row.character_id))}">Open Asset Container</a>
    <button type="button" data-mc-rename="${escape(row.character_id)}" data-name="${escape(row.name)}">Rename</button>
    <button type="button" class="danger-action" data-mc-delete="${escape(row.character_id)}" data-name="${escape(row.name)}">Delete</button></div>
    <div class="mc-asset-cards" aria-label="${escape(row.name)} assets">${cards(row.character_id, row.assets)}</div></section>`).join("") || "<p>No Minor Characters yet.</p>";
  $("mc-list-panel").hidden = false;
}
function schedule() {
  clearTimeout(timer);
  if (!character || busy || saving || document.hidden || !page.classList.contains("active")) return;
  const current = board();
  if (view ? (!Object.values(current.candidates).some(item => renderActive(item.status))
      && current.text_job?.status !== "RUNNING" && current.luna_review?.status !== "RUNNING")
      : character.intake_job?.status !== "RUNNING") return;
  const token = epoch, sequence = mutation, id = base(), path = view ? asset() + "/progress" : id + "/intake";
  const currentPoll = () => epoch === token && mutation === sequence && !busy && !saving &&
    universe === bridge.universe() && page.classList.contains("active") && !document.hidden;
  timer = setTimeout(async () => {
    try {
      const progress = await api(path);
      if (!currentPoll() || progress.revision < character.revision) return;
      const ids = view ? current.slots.filter(Boolean) : [];
      const settled = view
        ? ids.length !== Object.keys(progress.candidates).length ||
          ids.some(cid => !Object.hasOwn(progress.candidates, cid) ||
            (current.candidates[cid].status !== progress.candidates[cid] && !renderActive(progress.candidates[cid]))) ||
          current.text_job?.status !== (progress.text ?? undefined) ||
          current.luna_review?.status !== (progress.review ?? undefined)
        : progress.status !== "RUNNING";
      if (settled) {
        const {character:value} = await api(id);
        if (!currentPoll() || value.revision < progress.revision || value.revision < character.revision) return;
        const intakeSaved = character.intake_job?.status === "RUNNING" &&
          value.intake_job?.id === character.intake_job.id &&
          value.intake_job.saved_template_hash === value.template_hash;
        if (!edits.size || value.template_hash === character.template_hash || intakeSaved) adopt(value);
      } else if (view) {
        let changed = false;
        for (const cid of ids) {
          if (current.candidates[cid].status === progress.candidates[cid]) continue;
          current.candidates[cid].status = progress.candidates[cid];
          changed = true;
        }
        if (changed) publishBoard(current);
      }
    } catch (error) { if (currentPoll()) message(error.message, true); }
    finally { if (currentPoll()) schedule(); }
  }, 1800);
}
function render() {
  $("mc-editor").hidden = false;
  $("mc-rename").onclick = () => run(() => renameCharacter(character.character_id, character.name));
  $("mc-delete").onclick = () => run(() => deleteCharacter(character.character_id, character.name));
  $("mc-authoring-model").textContent = selectedModel() || "Use configured default";
  $("mc-list-panel").hidden = true;
  const current = board();
  $("mc-back").href = routeUrl(view ? character.character_id : "");
  $("mc-back").textContent = view ? "Back to Asset Container" : "All Minor Characters";
  $("mc-page-title").textContent = current ? `Minor Character - ${character.name}` : character.name;
  $("mc-view-wrap").hidden = !view;
  if (view) {
    $("mc-view").replaceChildren(...Object.entries(character.boards).map(([key, item]) => {
      const option = document.createElement("option");
      option.value = key;
      option.textContent = key === "STYLE" ? "Style" : item.label;
      option.selected = key === view;
      return option;
    }));
  }
  $("mc-container").hidden = Boolean(view);
  $("mc-board-authoring").hidden = $("mc-board-panel").hidden = !view;
  if (view) {
    if (!productionWorkspace) productionWorkspace = mountProductionWorkspace({
      root:$('mc-authoring'), title:$('mc-page-title'),
      context:[$('mc-back'), $('mc-view-wrap'), $('mc-rename').parentElement, $('mc-authoring-model').parentElement],
      preparation:[$('mc-container'), $('mc-board-authoring')],
      activity:[$('mc-message')], results:[$('mc-board-panel')],
    });
    productionWorkspace.setScope(promptKey(), false);
    renderBoard(current);
  }
  else renderContainer();
}
function renderContainer() {
  for (const [key,value] of Object.entries(character.fields))
    form.elements.namedItem(key).value = edits.get(key) ?? value;
  $("mc-assets").innerHTML = cards(character.character_id, character.assets);
  $("mc-source-status").textContent = character.source?.label || character.source_error || "Choose an Inventory image.";
  const intake = character.intake_job;
  const hasBlankFields = Object.values(character.fields).some(value => !value.trim());
  $("mc-intake").disabled = !character.source || !hasBlankFields || intake?.status === "RUNNING";
  const intakeStatus = intake?.error || {
    RUNNING: "Analyzing the source image…",
    COMPLETE: `Saved to the template: ${(intake?.applied_fields || []).join(", ")}.`,
  }[intake?.status] || "";
  $("mc-intake-status").textContent = intake ? [intakeStatus, modelLabel(intake)].filter(Boolean).join(" · ") : intakeStatus;
  $("mc-source-image").hidden = !character.source;
  if (character.source) $("mc-source-image").src = scoped(character.source.url);
}
function referenceReason() {
  const style = character.boards.STYLE;
  if (view === "STYLE") {
    if (!character.source) return character.source_error || "Choose a source image.";
    if (!character.canonical_style_ready) return "Set the canonical art style in Universe Settings.";
  } else if (!style.candidates[style.selected_id]?.locked) {
    return "Lock a Style Alignment candidate before preparing this view.";
  }
  return "";
}

function authoringReason(current) {
  return referenceReason() || (current.text_job?.status === "RUNNING" ? "Authoring is in progress." : "");
}

function imageDescriptor(item, assetView, part = "image") {
  if (!item?.image) return undefined;
  const version = item.image_version || item.id;
  return {url:media(item.id, part, assetView) + "&v=" + encodeURIComponent(version),
    label:`${character.boards[assetView].label} slot ${item.slot}`, version};
}

function boardModel(current) {
  const authorReason = authoringReason(current);
  const promptReady = Boolean(current.prompt_current);
  const hasPrompt = Boolean(current.prompt_body?.trim());
  const promptLabel = hasPrompt ? "Update Prompt" : "Write Prompt";
  const promptState = promptReady ? "Prompt ready for current inputs."
    : hasPrompt ? "Preparation changed. Update prompt, then render."
    : "Write or save a prompt for the current inputs.";
  const renderReason = referenceReason() || (!promptReady ? promptState : "");
  const actions = [];
  const add = (key, label, group, disabledReason, role, placement = ["controls"]) =>
    actions.push({key, label, group, placement, disabledReason, role});
  const items = current.slots.filter(Boolean).map(id => current.candidates[id]);
  const completed = item => item.status === "COMPLETE" && item.image;
  add("write-prompt", promptLabel, "prompt", authorReason || (pendingReview(current) ? "Review or dismiss the interview suggestions before updating the prompt." : ""));
  add("save-prompt", "Save Prompt", "prompt", authorReason);
  add("save-settings", "Save settings", "render", "", undefined, ["settings"]);
  const luna = current.luna_review;
  add("luna-review", "Luna Review", "luna", luna?.status === "RUNNING" ? "Luna Review is running."
    : !items.some(completed) ? "Generate a completed candidate first." : "");
  const locked = items.find(item => item.locked);
  const slots = current.slots.map((id, index) => {
    const item = current.candidates[id], slot = {key:String(index+1), actions:[]};
    const action = (key, disabledReason) => slot.actions.push({key, disabledReason});
    const active = item && renderActive(item.status) ? "Wait for the render to finish." : "";
    const selected = id && id === current.selected_id;
    if (!item) return slot;
    slot.renderActive = Boolean(active);
    slot.cancelAttempt = item.status === "QUEUED" && item.ask_id ? item.attempt_id : null;
    const otherLocked = locked && locked !== item ? "Unlock the current image first." : "";
    const ready = active || (!item.image ? "Wait for a completed image." : "");
    if (!item.locked) action(selected ? "unselect" : "select", selected ? active || otherLocked : ready || otherLocked);
    action(item.locked ? "unlock" : "lock", ready || otherLocked);
    if (item.status === "FAILED") action("retry", item.render_request ? "" : "The original render request is unavailable.");
    action("clear", active || (item.locked ? "Unlock this image before clearing its slot." : ""));
    if (completed(item)) slot.actions.push({key:"interview-candidate",label:"Interview this candidate",disabledReason:authorReason,placement:["review"]});
    const request = item.render_request || {}, settings = request.settings || {};
    const earlierDraft = item.render_mode === "final" && settings.render_mode === "draft";
    const version = encodeURIComponent(item.image_version || item.id);
    slot.candidate = {id, quality:item.render_mode, status:item.status, locked:item.locked,
      image:imageDescriptor(item, view), thumbnail:imageDescriptor(item, view, "thumbnail"),
      earlierPrompt:item.earlier_prompt, elapsedSeconds:item.render_duration_seconds, error:item.error,
      notices:[item.source_change_fyi && "Saved source differs from current source.", earlierDraft && "Showing original Draft evidence. The upscale request was not retained."].filter(Boolean),
      prompt:request.prompt ?? item.prompt,
      inputs:(request.inputs || []).map((input, index) => ({
        label:[input.label || input.role || "Reference", input.view, input.render_mode === "final" ? "Final" : input.render_mode === "draft" ? "Draft" : ""].filter(Boolean).join(" · "),
        marker:input.marker || ((request.prompt || "").includes(`<image${index + 1}>`) ? `<image${index + 1}>` : undefined),
        url:media(id, "inputs/" + (index + 1)) + "&delivery=inline&v=" + version,
      })),
      renderSettings:[["Aspect ratio", settings.aspect_ratio], ["Dimensions", settings.width && settings.height && `${settings.width} × ${settings.height}`],
        ["Checkpoint", settings.checkpoint]].filter(([, value]) => value).map(([label, value]) => ({label, value})),
    };
    return slot;
  });
  const comparisons = [];
  if (view === "STYLE" && character.source) comparisons.push({key:"original", label:"Original Inventory source",
    image:{url:scoped(character.source.url) + "&v=" + encodeURIComponent(character.source.asset_id),
      label:character.source.label}});
  if (view !== "STYLE") for (const [otherView, other] of Object.entries(character.boards)) {
    if (otherView === view) continue;
    const item = other.candidates[other.selected_id];
    if (!item?.image || (otherView === "STYLE" && !item.locked)) continue;
    comparisons.push({key:`${otherView}:${item.id}`, image:imageDescriptor(item, otherView),
      label:`${other.label} · Slot ${item.slot} · ${item.render_mode === "draft" ? "Draft" : "Final"} · ${item.locked ? "Locked" : "Selected"}`});
  }
  const job = current.text_job;
  const style = character.boards.STYLE;
  const selectedStyle = style.candidates[style.selected_id];
  const lockedStyle = selectedStyle?.locked ? selectedStyle : Object.values(style.candidates).find(item => item.locked);
  const promptStatus = [job?.action === "write-prompt"
    ? job.error || ({RUNNING:"Writing prompt…", COMPLETE:"Prompt updated."}[job.status] ?? "")
    : "", promptState, job?.action === "write-prompt" ? modelLabel(job) : ""].filter(Boolean).join(" · ");
  return {scope:{key:promptKey(), title:character.name, view:current.label}, revision:character.revision, slots, actions,
    selectedId:current.selected_id, comparisons,
    comparisonDefaults:["selected", comparisons[0]?.key].filter(Boolean),
    lunaReview:{status:luna?.status, error:luna?.error, criteria:luna?.prompt || current.luna_criteria,
      entries:Object.fromEntries((luna?.entries || []).map((entry, index) => [entry.candidate_id, {rank:index+1, assessment:entry.review}]))},
    renderControls:{aspectRatio:{value:edits.get("aspect_ratio") ?? current.aspect_ratio},fields:[
      {key:"prompt", label:"Prompt text", type:"textarea", value:promptDrafts.get(promptKey()) ?? current.prompt_body ?? ""},
    ], readiness:{draft:renderReason, final:renderReason}, promptStatus,
    renderStatus:renderReason || (view === "STYLE" ? `Source reference · ${character.source.label}` : `Locked Style reference · slot ${lockedStyle?.slot ?? ""}`)},
  };
}

function publishBoard(current) {
  const data = boardModel(current);
  if (sharedBoard) sharedBoard.update(data);
  else sharedBoard = mountCandidateBoard({boardHost:$("mc-board"), dialogHost:$("mc-dialog-host")}, data, {
    onEdit({scopeKey, field, value}) {
      if (scopeKey !== promptKey()) return;
      if (field === "prompt") promptDrafts.set(scopeKey, value);
      else edits.set(field, value);
    },
    onAction:boardAction,
  });
}

function renderBoard(current) {
  for (const [key,value] of Object.entries({refinement:current.refinement, style_alignment_changes:current.style_alignment_changes ?? ""}))
    form.elements.namedItem(key).value = edits.get(key) ?? value;
  $("mc-style-changes").hidden = view !== "STYLE";
  $("mc-refinement").hidden = view === "STYLE";
  const evidence = $("mc-evidence"), previousEvidence = evidence.value;
  evidence.replaceChildren(new Option("None", ""), ...current.slots.filter(id => current.candidates[id]?.status === "COMPLETE" && current.candidates[id]?.image)
    .map(id => new Option(`Slot ${current.candidates[id].slot}`, id)));
  if ([...evidence.options].some(option => option.value === previousEvidence)) evidence.value = previousEvidence;
  $("mc-interview").disabled = Boolean(authoringReason(current) || pendingReview(current));
  $("mc-improvement").hidden = false;
  $("mc-improvement-title").textContent = view === "STYLE" ? "Style improvement" : `${current.label} improvement`;
  const style = character.boards.STYLE;
  const styleCandidate = style.candidates[style.selected_id];
  const lockedStyle = styleCandidate?.locked ? styleCandidate : Object.values(style.candidates).find(item => item.locked);
  $("mc-reference-status").textContent = view === "STYLE"
    ? `Style reference · ${character.source?.label || "Source unavailable"}`
    : `${current.label} reference · ${lockedStyle ? `Style slot ${lockedStyle.slot} (locked)` : "Style image not locked"}`;
  $("mc-front-link").hidden = view !== "STYLE" || !lockedStyle;
  $("mc-front-link").href = routeUrl(character.character_id,"FRONT");
  $("mc-style-link").hidden = view === "STYLE" || Boolean(lockedStyle);
  $("mc-style-link").href = routeUrl(character.character_id,"STYLE");
  publishBoard(current);
  const job = current.text_job;
  const proposals = job?.review?.proposals;
  $("mc-proposals").hidden = !proposals;
  const proposalChoices = Object.fromEntries([...$("mc-proposals").querySelectorAll("[data-proposal]")].map(control => [control.dataset.proposal, control.checked]));
  $("mc-proposals").innerHTML = proposals ? `<div id="mc-proposal-form"><h2>Review interview proposals</h2>${
    proposals.map((row,index) => `<article class="narrative-proposal"><h3>${escape(row.field === "style_alignment_changes" ? "Source-to-reference changes" : row.field)}</h3><p>${escape(row.reason)}</p>${renderProposalComparison(row, escape)}
      ${renderProposalAcceptance(row.id, row.field, Boolean(proposalChoices[row.id]), escape)}</article>`).join("")
      || "<p>No field changes proposed.</p>"}<button type="button" data-apply-proposals>Apply accepted changes</button><button type="button" data-dismiss-proposals>Dismiss suggestions</button></div>` : "";
  for (const control of $("mc-proposals").querySelectorAll("[data-proposal]")) {
    control.checked = Boolean(proposalChoices[control.dataset.proposal]);
  }
  $("mc-authoring-status").textContent = [
    job?.action === "interview" && (job.error || (job.status === "RUNNING" ? "Interview in progress…" : "")),
    job?.applied_fields?.length ? `Applied to template: ${job.applied_fields.map(field => field === "style_alignment_changes" ? "Source-to-reference changes" : field).join(", ")}.` : "",
    job?.action === "interview" ? modelLabel(job) : "",
    job?.applied_fields?.length && !current.prompt_current ? "Use Write Prompt to update the render prompt." : "",
  ].filter(Boolean).join(" ");
  const rankingModel = current.luna_review?.model;
  $("mc-ranking-model").hidden = !rankingModel;
  $("mc-ranking-model").textContent = rankingModel ? `Luna Review model · ${rankingModel}` : "";
  const selected = current.candidates[current.selected_id];
  $("mc-inventory-link").hidden = view === "STYLE" || !selected?.locked || !selected.inventory_asset_id;
}

async function bulk(kind, isCurrent) {
  await flush();
  if (!isCurrent()) return false;
  const path = asset() + "/bulk/" + kind;
  const preview = await api(path + "/preview","POST");
  if (!isCurrent()) return false;
  if (preview.revision !== character.revision) throw new Error("The board changed. Refresh and try again.");
  const ids = await confirmCandidateDeletion("delete-" + kind, board().label, preview.slots, preview.active_slots,
    preview.protected_effects.map(effect => ({
      ...effect,
      label:effect.label + (effect.inventory_asset_id ? ` · Inventory image ${effect.inventory_asset_id} will be retained` : ""),
      preview_url:media(effect.candidate_id),
    })));
  if (ids === null || ids === false || !isCurrent()) return false;
  const result = await api(path,"POST",{revision:preview.revision, approved_effects:ids});
  if (!isCurrent()) return false;
  adopt(result.character);
  return true;
}

async function boardAction(intent) {
  const cancelled = {status:"cancelled"};
  if (busy || saving || intent.scopeKey !== promptKey()) return cancelled;
  const token = epoch;
  const isCurrent = () => token === epoch && intent.scopeKey === promptKey() && universe === bridge.universe();
  clearTimeout(timer);
  busy = true;
  mutation++;
  try {
    const current = board();
    const {key, candidateId, slotKey, expectedOccupant, mode, count} = intent;
    if (intent.revision !== character.revision ||
        (slotKey && current.slots[Number(slotKey)-1] !== expectedOccupant)) {
      throw new Error("The board changed. Refresh and try again.");
    }
    let accepted;
    if (key === "save-settings" || key === "save-prompt") {
      await flush(key === "save-prompt");
      accepted = isCurrent();
    } else if (key === "write-prompt") {
      const previous = promptDrafts.get(intent.scopeKey);
      accepted = await author(key);
      if (accepted) pendingWrites.set(intent.scopeKey, {id:board().text_job.id, draft:previous});
    } else if (key === "luna-review") {
      accepted = await author(key);
    } else if (key === "interview-candidate") {
      // The board releases its pending action before the public close method can succeed.
      requestAnimationFrame(async () => {
        if (!isCurrent()) return;
        await sharedBoard?.closeReview();
        if (!isCurrent()) return;
        $("mc-improvement").open = true;
        $("mc-evidence").value = candidateId;
        $("mc-feedback").focus();
      });
      return cancelled;
    } else if (key.startsWith("delete-")) {
      accepted = await bulk(key.slice(7), isCurrent);
    } else if (key.startsWith("render-") || key.startsWith("regen-")) {
      accepted = await change(asset()+"/generate", {count:count ?? 1, render_mode:mode,
        ...(slotKey ? {slot:Number(slotKey), expected_candidate_id:expectedOccupant} : {})});
    } else {
      const selected = current.selected_id === candidateId;
      if (key === "clear" && selected && !window.confirm("Clear the selected image?")) return cancelled;
      accepted = await change(asset()+"/candidates/"+candidateId+"/"+key, {confirm_selected:selected, expected_attempt_id:intent.expectedAttempt});
    }
    if (!accepted || !isCurrent()) return cancelled;
    const messages = {cancel:"Render cancelled.", "save-settings":"Settings saved.", "save-prompt":"Prompt saved.", lock:view === "STYLE" ? "Locked privately." : "Locked and published."};
    return {status:"success", message:messages[key]};
  } catch (error) {
    if (!isCurrent()) return cancelled;
    try {
      if (key === "cancel") await api(asset()+"/progress").catch(() => {});
      if (!isCurrent()) return cancelled;
      const {character:value} = await api(base());
      if (isCurrent() && value.revision >= character.revision &&
          (!edits.size || value.template_hash === character.template_hash)) adopt(value);
    } catch { /* Keep the original action error. */ }
    return {status:"error", message:error.message};
  } finally {
    busy = false;
    schedule();
  }
}
async function setSource(source) {
  const token = epoch;
  await flush();
  if (token !== epoch) return;
  const result = await api(base(),"PATCH",{revision:character.revision,template_hash:character.template_hash,source});
  if (token === epoch) adopt(result.character);
}
const sourceImportInput = $("mc-source-import-file");
const sourceImportZone = $("mc-source-import-zone");
const sourceImportLabel = $("mc-source-import-label");
const sourceImportPreview = $("mc-source-import-preview");
const sourceImportButton = $("mc-source-import-use");
const sourceImportStatus = $("mc-source-import-status");
let sourceImportFile, sourceImportUrl;
window.ZetImageInput?.attach(sourceImportZone, sourceImportInput);
sourceImportInput.addEventListener("change", () => {
  sourceImportFile = sourceImportInput.files?.[0] || null;
  if (sourceImportUrl) URL.revokeObjectURL(sourceImportUrl);
  sourceImportUrl = sourceImportFile ? URL.createObjectURL(sourceImportFile) : null;
  sourceImportPreview.hidden = !sourceImportFile;
  if (sourceImportFile) {
    sourceImportPreview.src = sourceImportUrl;
    if (!sourceImportLabel.value.trim()) sourceImportLabel.value = sourceImportFile.name.replace(/\.[^.]+$/, "");
  }
  sourceImportButton.disabled = !sourceImportFile;
  sourceImportStatus.textContent = sourceImportFile ? "Ready to import. Importing adds this image to Image Inventory." : "";
});
sourceImportButton.addEventListener("click", () => run(async () => {
  const token = epoch;
  const file = sourceImportFile;
  const label = sourceImportLabel.value.trim();
  if (!file || !label) throw new Error("Choose an image and enter its Inventory label.");
  sourceImportButton.disabled = true;
  sourceImportStatus.textContent = "Importing image and setting it as this workspace's source…";
  try {
    const params = new URLSearchParams({label});
    const response = await fetch(`/api/entity-library/assets?${params}`, {method:"POST", headers:{"Content-Type":file.type}, body:file});
    const payload = await response.json();
    if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Image import failed.");
    if (!payload.asset?.asset_id) throw new Error("Import succeeded but returned no usable image identity.");
    if (token !== epoch || !page.classList.contains("active")) return;
    await setSource({asset_id:payload.asset.asset_id, label:payload.asset.label || label});
    sourceImportStatus.textContent = `${payload.message || "Image imported."} It is now the workspace source.`;
    sourceImportInput.value = "";
    sourceImportFile = null;
    sourceImportButton.disabled = true;
    sourceImportPreview.hidden = true;
    if (sourceImportUrl) URL.revokeObjectURL(sourceImportUrl);
    sourceImportUrl = null;
  } catch (error) {
    sourceImportStatus.textContent = error.message;
    sourceImportButton.disabled = !sourceImportFile;
    throw error;
  } finally { sourceImportButton.disabled = !sourceImportFile; }
}));
function author(action, extra = {}) {
  return change(asset()+"/authoring/"+action,{model:selectedModel(),feedback:$("mc-feedback").value,candidate_id:$("mc-evidence").value,...extra});
}
page.addEventListener("click", event => {
  const link = event.target.closest("a[data-mc-route]");
  if (link && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
    event.preventDefault();
    const params = new URL(link.href).searchParams;
    return run(()=>navigate(params.get("minor_character"), params.get("view")));
  }
  const control = event.target.closest("button");
  if (!control || control.disabled) return;
  const data = control.dataset;
  if (data.mcRename) return run(() => renameCharacter(data.mcRename, data.name));
  if (data.mcDelete) return run(() => deleteCharacter(data.mcDelete, data.name));
  if ("applyProposals" in data) return run(()=>author("apply", {
    job_id: board().text_job.id,
    choices: Object.fromEntries([...$("mc-proposals").querySelectorAll("[data-proposal]")].map(control => [control.dataset.proposal, control.checked ? "accept" : "reject"])),
  }));
  if ("dismissProposals" in data) return run(()=>author("dismiss", {job_id:board().text_job.id}));
});
page.addEventListener("error", event => {
  const preview = event.target.closest?.("[data-mc-preview]");
  if (preview) {
    preview.hidden = true;
    preview.nextElementSibling.hidden = false;
  }
}, true);
form.addEventListener("input", event => {
  if (event.target.name) edits.set(event.target.name, event.target.value);
});
page.addEventListener("submit",event=>{
  if (event.target.method === "dialog") return;
  event.preventDefault();
  if (event.target === form) return run(flush);
  if (event.target.id === "mc-create-form") return run(async()=>{
    const token = epoch;
    const result=await api("","POST",{name:$("mc-new-name").value});
    if (token !== epoch || !page.classList.contains("active")) return;
    await navigate(result.character.character_id);
    if (entryAsset) { await setSource({asset_id:entryAsset.asset_id,label:entryAsset.label}); entryAsset=null; }
  });
});
$("mc-intake").onclick=()=>run(()=>change(base()+"/intake",{model:selectedModel()}));
$("mc-interview").onclick=()=>run(()=>author("interview"));
$("mc-view").addEventListener("change", event => run(() => navigate(character.character_id, event.target.value)));
$("mc-authoring-model").onclick = chooseModel;
$("mc-inventory-link").onclick = () => run(async () => {
  const token = epoch;
  await flush();
  if (token !== epoch) return;
  const current = board();
  const item = current.candidates[current.selected_id];
  if (view !== "STYLE" && item?.locked && item.inventory_asset_id) {
    window.dispatchEvent(new CustomEvent("zet:open-inventory-image", {detail:{assetId:item.inventory_asset_id, universe}}));
  }
});
$("mc-add-reference").onclick=()=>{
  const token = epoch;
  return bridge.openLibraryPicker(item=>{
    if (token === epoch && page.classList.contains("active"))
      return run(()=>setSource({asset_id:item.asset_id,label:item.label}));
  });
};
$("quick-character-wizard-open").onclick=()=>run(async()=>{route(""); await bridge.activatePage("minor-characters");});
$("quick-character-wizard-from-asset").onclick=()=>run(async()=>{
  const item=bridge.selectedAsset();
  if (!item) throw new Error("Choose an Inventory image first.");
  universe=bridge.universe();
  const owner=await api("/owner/"+encodeURIComponent(item.asset_id));
  entryAsset=owner.character_id ? null : item;
  route(owner.character_id);
  await bridge.activatePage("minor-characters");
  if (entryAsset) $("mc-new-name").value=item.label || "";
});
window.zetMinorCharacters={load:()=>load().catch(error=>message(error.message,true)),flush,
  navigateList:async()=>{await flush();route("");},
  leave:()=>{epoch++;clearTimeout(timer);disposeBoard();},
  characterId:()=>character?.character_id || ""};

document.addEventListener("visibilitychange", () => {
  if (document.hidden) clearTimeout(timer);
  else if (!edits.size && page.classList.contains("active")) {
    void run(async()=>{
      if (!character) return load();
      const token = epoch;
      const result = await api(base());
      if (token === epoch) adopt(result.character);
    });
  } else {
    schedule();
  }
});
