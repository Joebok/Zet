import {mountCandidateBoard, confirmCandidateDeletion} from "./candidate_board_component.js?v=20261110-deselect-action";
import {renderProposalComparison} from "./interview_proposals.js";

const $ = id => document.getElementById(id);
const page = $("minor-characters-page");
const bridge = window.zetQuickCharacterWizard;
const form = $("mc-authoring");
let sharedBoard;
const escape = value => String(value ?? "").replace(/[&<>"']/g, char =>
  ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"})[char]);
let character, universe, entryAsset, timer;
let view = "", busy = false, model = "", epoch = 0, mutation = 0;
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
    <h2>${escape(row.name)}</h2><a data-mc-route href="${escape(routeUrl(row.character_id))}">Open Asset Container</a>
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
  if (view) renderBoard(current);
  else renderContainer();
}
function renderContainer() {
  for (const [key,value] of Object.entries({...character.fields, name:character.name}))
    form.elements.namedItem(key).value = edits.get(key) ?? value;
  form.elements.namedItem("name").required = true;
  $("mc-assets").innerHTML = cards(character.character_id, character.assets);
  $("mc-source-status").textContent = character.source?.label || character.source_error || "Choose an Inventory image.";
  const intake = character.intake_job;
  const hasBlankFields = Object.values(character.fields).some(value => !value.trim());
  $("mc-intake").disabled = !character.source || !hasBlankFields || intake?.status === "RUNNING";
  $("mc-intake-status").textContent = intake?.error || {
    RUNNING: "Analyzing the source image…",
    COMPLETE: `Saved to the template: ${(intake?.applied_fields || []).join(", ")}.`,
  }[intake?.status] || "";
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
  const renderReason = referenceReason() || (!current.prompt_current ? "Write or save the prompt for the current inputs." : "");
  const actions = [];
  const add = (key, label, group, disabledReason, role, placement = ["controls"]) =>
    actions.push({key, label, group, placement, disabledReason, role});
  const items = current.slots.filter(Boolean).map(id => current.candidates[id]);
  const completed = item => item.status === "COMPLETE" && item.image;
  add("write-prompt", "Write Prompt", "prompt", authorReason);
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
    const otherLocked = locked && locked !== item ? "Unlock the current image first." : "";
    const ready = active || (!item.image ? "Wait for a completed image." : "");
    if (!item.locked) action(selected ? "unselect" : "select", selected ? active || otherLocked : ready || otherLocked);
    action(item.locked ? "unlock" : "lock", ready || otherLocked);
    if (item.image && item.render_mode === "draft") action("upscale", active || (item.locked ? "Unlock this image first." : ""));
    if (item.status === "FAILED") action("retry", item.render_request ? "" : "The original render request is unavailable.");
    action("clear", active || (item.locked ? "Unlock this image before clearing its slot." : ""));
    if (completed(item)) slot.actions.push({key:"interview-candidate",label:"Interview this candidate",disabledReason:authorReason,placement:["review"]});
    const request = item.render_request || {}, settings = request.settings || {};
    const earlierDraft = item.render_mode === "final" && settings.render_mode === "draft";
    const version = encodeURIComponent(item.image_version || item.id);
    slot.candidate = {id, quality:item.render_mode, status:item.status, locked:item.locked,
      image:imageDescriptor(item, view), thumbnail:imageDescriptor(item, view, "thumbnail"),
      elapsedSeconds:item.render_duration_seconds, error:item.error,
      notices:[item.source_change_fyi && "Earlier source or prompt.", earlierDraft && "Showing original Draft evidence. The upscale request was not retained."].filter(Boolean),
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
  const promptStatus = job?.action === "write-prompt"
    ? job.error || ({RUNNING:"Writing prompt…", COMPLETE:"Prompt written."}[job.status] ?? "")
    : "";
  return {scope:{key:promptKey(), title:character.name, view:current.label}, revision:character.revision, slots, actions,
    selectedId:current.selected_id, comparisons,
    comparisonDefaults:["selected", comparisons[0]?.key].filter(Boolean),
    lunaReview:{status:luna?.status, error:luna?.error, criteria:luna?.prompt || current.luna_criteria,
      entries:Object.fromEntries((luna?.entries || []).map((entry, index) => [entry.candidate_id, {rank:index+1, assessment:entry.review}]))},
    renderControls:{fields:[
      {key:"prompt", label:"Prompt text", type:"textarea", value:promptDrafts.get(promptKey()) ?? current.prompt_body ?? ""},
      {key:"aspect_ratio", label:"Aspect ratio", type:"text", value:edits.get("aspect_ratio") ?? current.aspect_ratio},
    ], readiness:{draft:renderReason, final:renderReason}, promptStatus,
    renderStatus:renderReason || (view === "STYLE" ? character.source.label : "Render reference · Locked Style Alignment")},
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
  form.elements.namedItem("name").required = false;
  for (const [key,value] of Object.entries({refinement:current.refinement, style_alignment_changes:current.style_alignment_changes ?? ""}))
    form.elements.namedItem(key).value = edits.get(key) ?? value;
  $("mc-style-changes").hidden = view !== "STYLE";
  $("mc-refinement").hidden = view === "STYLE";
  const evidence = $("mc-evidence"), previousEvidence = evidence.value;
  evidence.replaceChildren(new Option("None", ""), ...current.slots.filter(id => current.candidates[id]?.status === "COMPLETE" && current.candidates[id]?.image)
    .map(id => new Option(`Slot ${current.candidates[id].slot}`, id)));
  if ([...evidence.options].some(option => option.value === previousEvidence)) evidence.value = previousEvidence;
  $("mc-interview").disabled = Boolean(authoringReason(current));
  publishBoard(current);
  const job = current.text_job;
  const proposals = job?.review?.proposals;
  $("mc-proposals").hidden = !proposals;
  const proposalChoices = Object.fromEntries([...$("mc-proposals").querySelectorAll("select")].map(select => [select.dataset.proposal, select.value]));
  $("mc-proposals").innerHTML = proposals ? `<div id="mc-proposal-form"><h2>Review interview proposals</h2>${
    proposals.map(row => `<article class="narrative-proposal"><h3>${escape(row.field === "style_alignment_changes" ? "Source-to-reference changes" : row.field)}</h3><p>${escape(row.reason)}</p>${renderProposalComparison(row, escape)}
      <label>Decision<select data-proposal="${escape(row.id)}"><option value="reject">Reject</option><option value="accept">Accept</option></select></label></article>`).join("")
      || "<p>No field changes proposed.</p>"}<button type="button" data-apply-proposals>Apply</button></div>` : "";
  for (const select of $("mc-proposals").querySelectorAll("select")) {
    if (proposalChoices[select.dataset.proposal]) select.value = proposalChoices[select.dataset.proposal];
  }
  $("mc-authoring-status").textContent = [
    job?.action === "interview" && (job.error || (job.status === "RUNNING" ? "Interview in progress…" : "")),
    job?.applied_fields?.length ? `Applied to template: ${job.applied_fields.map(field => field === "style_alignment_changes" ? "Source-to-reference changes" : field).join(", ")}.` : "",
  ].filter(Boolean).join(" ");
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
      accepted = await author("interview", {candidate_id:candidateId});
      if (accepted) {
        $("mc-evidence").value = candidateId;
        await sharedBoard?.closeReview();
        if (isCurrent()) $("mc-feedback").focus();
      }
    } else if (key.startsWith("delete-")) {
      accepted = await bulk(key.slice(7), isCurrent);
    } else if (key.startsWith("render-") || key.startsWith("regen-")) {
      accepted = await change(asset()+"/generate", {count:count ?? 1, render_mode:mode,
        ...(slotKey ? {slot:Number(slotKey), expected_candidate_id:expectedOccupant} : {})});
    } else {
      const selected = current.selected_id === candidateId;
      if (key === "clear" && selected && !window.confirm("Clear the selected image?")) return cancelled;
      accepted = await change(asset()+"/candidates/"+candidateId+"/"+key, {confirm_selected:selected});
    }
    if (!accepted || !isCurrent()) return cancelled;
    const messages = {"save-settings":"Settings saved.", "save-prompt":"Prompt saved.", lock:view === "STYLE" ? "Locked privately." : "Locked and published."};
    return {status:"success", message:messages[key]};
  } catch (error) {
    if (!isCurrent()) return cancelled;
    try {
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
function author(action, extra = {}) {
  return change(asset()+"/authoring/"+action,{model,feedback:$("mc-feedback").value,candidate_id:$("mc-evidence").value,...extra});
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
  if ("applyProposals" in data) return run(()=>author("apply", {
    job_id: board().text_job.id,
    choices: Object.fromEntries([...$("mc-proposals").querySelectorAll("select")].map(select => [select.dataset.proposal, select.value])),
  }));
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
$("mc-intake").onclick=()=>run(()=>change(base()+"/intake",{}));
$("mc-interview").onclick=()=>run(()=>author("interview"));
$("mc-view").addEventListener("change", event => run(() => navigate(character.character_id, event.target.value)));
$("mc-model").onclick=async()=>{
  const value=await window.ZetModelPicker.open({value:model,required:["vision"],allowDefault:true});
  if (value !== null) {model=value; $("mc-model").textContent=model || "Use configured default";}
};
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
