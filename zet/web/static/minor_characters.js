import {candidateActions, renderBoardActions, renderCandidateBoard, reviewInputs, reviewPosition} from "./candidate_board.js?v=20261107-board-toolbar";
import {renderProposalComparison} from "./interview_proposals.js";

const $ = id => document.getElementById(id);
const page = $("minor-characters-page");
const bridge = window.zetQuickCharacterWizard;
const form = $("mc-authoring");
const dialog = $("mc-review");
window.ZetReviewImageZoom.attach(dialog, () => [...dialog.querySelectorAll(".narrative-review-images img")]);
const escape = value => String(value ?? "").replace(/[&<>"']/g, char =>
  ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"})[char]);
let character, universe, entryAsset, timer, reviewId;
let view = "STYLE", busy = false, model = "", epoch = 0;
const edits = new Map();
const board = () => character.boards[view];
const base = () => "/" + character.character_id;
const asset = () => base() + "/assets/" + view;
const media = (cid, part = "image") => scoped("/api/minor-characters" + asset() + "/candidates/" + cid + "/" + part);
const scoped = path => path + "?universe_id=" + encodeURIComponent(universe);
const api = (path, method = "GET", body) => bridge.fetchJson("/api/minor-characters" + path, {
  method, bindToPage:false, ...(body === undefined ? {} : {
    headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)
  })
});
const promptDrafts = new Map();
const promptKey = () => [universe, character?.character_id, view].join(":");

function route(id) {
  const url = new URL(location.href);
  url.searchParams.set("page", "minor-characters");
  if (id) url.searchParams.set("minor_character", id);
  else url.searchParams.delete("minor_character");
  history.replaceState(history.state, "", url);
}
function message(text, error = false) {
  $("mc-message").textContent = text;
  $("mc-message").classList.toggle("error", error);
}
function adopt(value) {
  character = value;
  render();
}
async function run(action) {
  if (busy) return;
  clearTimeout(timer);
  busy = true;
  message("");
  try { await action(); }
  catch (error) { message(error.message, true); }
  finally { busy = false; schedule(); }
}
async function flush(savePrompt = false) {
  if ((!edits.size && !savePrompt) || !character || universe !== bridge.universe()) return;
  const submitted = new Map(edits);
  const data = Object.fromEntries(submitted);
  if (savePrompt) data.prompt = form.elements.namedItem("prompt").value;
  data.view = view;
  data.template_hash = character.template_hash;
  data.revision = character.revision;
  const result = await api(base(), "PATCH", data);
  for (const [key, value] of submitted) if (edits.get(key) === value) edits.delete(key);
  if (savePrompt) promptDrafts.delete(promptKey());
  adopt(result.character);
}
async function change(path, data) {
  await flush();
  const result = await api(path, "POST", {...data, revision:character.revision, template_hash:character.template_hash});
  adopt(result.character);
}
async function open(id) {
  await flush();
  route(id);
  view = "STYLE";
  adopt((await api("/" + id)).character);
}
async function load() {
  clearTimeout(timer);
  epoch++;
  const next = bridge.universe();
  if (universe !== next) { character = null; edits.clear(); }
  universe = next;
  $("mc-editor").hidden = true;
  $("mc-list-panel").hidden = false;
  const {characters} = await api("");
  $("mc-list").innerHTML = characters.map(row =>
    `<button data-open="${escape(row.character_id)}" ${row.needs_migration ? "disabled" : ""}>${escape(row.name)}${row.needs_migration ? " · Migration required" : ""}</button>`).join("");
  const id = new URL(location.href).searchParams.get("minor_character");
  if (id) await open(id);
  else character = null;
  schedule();
}
function schedule() {
  clearTimeout(timer);
  if (!character || busy || document.hidden || !page.classList.contains("active")) return;
  const current = board();
  if (!Object.values(current.candidates).some(item => ["SUBMITTING","QUEUED","RUNNING"].includes(item.status))
      && current.text_job?.status !== "RUNNING" && current.luna_review?.status !== "RUNNING") return;
  const token = epoch, path = asset(), id = base();
  timer = setTimeout(async () => {
    try {
      const progress = await api(path + "/progress");
      if (epoch !== token || !character || asset() !== path || busy || universe !== bridge.universe()) return;
      if (progress.revision !== character.revision) {
        const {character:value} = await api(id);
        if (epoch === token && !busy && asset() === path && (!edits.size || value.template_hash === character.template_hash)) adopt(value);
      }
    } catch (error) { if (epoch === token) message(error.message, true); }
    finally { schedule(); }
  }, 1800);
}
function render() {
  $("mc-editor").hidden = false;
  $("mc-list-panel").hidden = true;
  const current = board();
  $("mc-assets").innerHTML = '<button type="button" data-list>All Minor Characters</button>' +
    Object.entries(character.boards).map(([id, item]) =>
      `<button type="button" data-view="${id}" aria-pressed="${view === id}">${escape(item.label)}</button>`).join("");
  for (const [key,value] of Object.entries({...character.fields, name:character.name,
    refinement:current.refinement, prompt:promptDrafts.get(promptKey()) ?? current.prompt_body ?? "", aspect_ratio:current.aspect_ratio})) form.elements.namedItem(key).value = edits.get(key) ?? value;
  $("mc-refinement").hidden = view === "STYLE";
  $("mc-source-status").textContent = character.source?.label || character.source_error || "Choose an Inventory image.";
  const evidence = $("mc-evidence"), previousEvidence = evidence.value;
  evidence.replaceChildren(new Option("None", ""), ...current.slots.filter(id => current.candidates[id]?.status === "COMPLETE")
    .map(id => new Option(`Slot ${current.candidates[id].slot}`, id)));
  if ([...evidence.options].some(option => option.value === previousEvidence)) evidence.value = previousEvidence;
  $("mc-render-prompt").textContent = current.prompt;
  $("mc-source-image").hidden = !character.source;
  if (character.source) $("mc-source-image").src = scoped(character.source.url);
  const style = character.boards.STYLE;
  const hasReference = view === "STYLE" ? !!character.source : !!style.candidates[style.selected_id]?.locked;
  $("mc-reference-status").textContent = hasReference
    ? (view === "STYLE" ? character.source.label : "Render reference · Locked Style Alignment")
    : (view === "STYLE" ? "Choose a source image." : "Lock a Style Alignment candidate before preparing this view.");
  $("mc-write").disabled = $("mc-interview").disabled =
    !hasReference || (view === "STYLE" && !character.canonical_style_ready) || current.text_job?.status === "RUNNING";
  $("mc-save-prompt").disabled = $("mc-write").disabled;
  $("mc-board-actions").innerHTML = renderBoardActions(current.luna_review?.prompt);
  $("mc-board-actions").querySelectorAll('[data-board-action="render"]').forEach(button => {
    button.disabled = !hasReference || !current.prompt_current ||
      current.slots.filter(id => !id).length < Number(button.dataset.count);
  });
  renderCandidateBoard({host:$("mc-board"), slots:current.slots, candidates:current.candidates,
    selectedId:current.selected_id, escape, imageUrl:cid=>media(cid), lunaReview:current.luna_review,
    promptIndicator:item=>item?.source_change_fyi ? "Earlier source or prompt" : "",
    renderActions:(item,index)=>candidateActions({id:item?.id || "", candidate:item, slot:index+1,
      selected:!!item && item.id === current.selected_id, escape,
      busy:!!item && ["SUBMITTING","QUEUED","RUNNING"].includes(item.status),
      canReplace:hasReference && !!current.prompt_current && (!item || (!item.locked && item.id !== current.selected_id)),
      canClear:!item?.locked})});
  const job = current.text_job;
  const proposals = job?.review?.proposals;
  $("mc-proposals").hidden = !proposals;
  const proposalChoices = Object.fromEntries([...$("mc-proposals").querySelectorAll("select")].map(select => [select.dataset.proposal, select.value]));
  $("mc-proposals").innerHTML = proposals ? `<div id="mc-proposal-form"><h2>Review interview proposals</h2>${
    proposals.map(row => `<article class="narrative-proposal"><h3>${escape(row.field)}</h3><p>${escape(row.reason)}</p>${renderProposalComparison(row, escape)}
      <label>Decision<select data-proposal="${escape(row.id)}"><option value="reject">Reject</option><option value="accept">Accept</option></select></label></article>`).join("")
      || "<p>No field changes proposed.</p>"}<button type="button" data-apply-proposals>Apply</button></div>` : "";
  for (const select of $("mc-proposals").querySelectorAll("select")) {
    if (proposalChoices[select.dataset.proposal]) select.value = proposalChoices[select.dataset.proposal];
  }
  $("mc-authoring-status").textContent = [
    view === "STYLE" && !character.canonical_style_ready ? "Set the canonical art style in Universe Settings." : "",
    job?.error || (job?.status === "RUNNING" ? "Authoring in progress…" : ""),
    job?.applied_fields?.length ? `Applied to template: ${job.applied_fields.join(", ")}.` : "",
    current.prompt && !current.prompt_current ? "Inputs changed. Write Prompt or save the prompt for the current inputs." : "",
  ].filter(Boolean).join(" ");
  if (current.luna_review?.error) message(current.luna_review.error, true);
  if (dialog.open) renderReview();
}
function renderReview() {
  const current = board(), item = current.candidates[reviewId];
  if (!item) { dialog.close(); return; }
  const ids = current.slots.filter(Boolean), index = ids.indexOf(reviewId);
  const other = current.selected_id !== reviewId ? current.selected_id : null;
  const ranking = current.luna_review?.entries?.find(row=>row.candidate_id === reviewId);
  dialog.innerHTML = `<form method="dialog"><button>Close</button></form><h2>${reviewPosition(item,index,ids.length,current.selected_id === reviewId)}</h2>
    <button data-review="${ids[index-1] || ""}" ${index === 0 ? "disabled" : ""}>Previous</button>
    <button data-review="${ids[index+1] || ""}" ${index === ids.length-1 ? "disabled" : ""}>Next</button>
    <div class="narrative-review-images">${other && current.candidates[other].image ? `<img src="${media(other)}" alt="Selected comparison" width="300">` : ""}
    ${item.image ? `<img src="${media(reviewId)}" alt="Candidate" width="350">` : ""}</div>
    <pre>${escape(item.prompt)}</pre>${reviewInputs(item.render_request?.inputs, n=>media(reviewId,"inputs/"+n),escape)}
    ${ranking ? `<p>${escape(ranking.review || "")}</p>` : ""}
    ${candidateActions({id:reviewId,candidate:item,selected:reviewId===current.selected_id,slot:item.slot,escape,
      busy:["SUBMITTING","QUEUED","RUNNING"].includes(item.status),review:true,canReplace:false,canClear:!item.locked})}
    ${item.status === "COMPLETE" ? '<button data-evidence>Interview this candidate</button>' : ""}`;
}
async function bulk(kind) {
  await flush();
  const path = asset() + "/bulk/" + kind;
  const preview = await api(path + "/preview","POST");
  const ids = await window.confirmProtectedEffects("Delete candidates?", `Clear ${preview.slots.length} candidate slots.`,
    preview.protected_effects.map(effect => ({...effect, preview_url:media(effect.candidate_id)})), "Delete");
  if (ids === null || ids === false) return;
  adopt((await api(path,"POST",{revision:preview.revision, approved_effects:ids})).character);
}
async function setSource(source) {
  await flush();
  adopt((await api(base(),"PATCH",{revision:character.revision,template_hash:character.template_hash,source})).character);
}
function author(action, extra = {}) {
  return change(asset()+"/authoring/"+action,{model,feedback:$("mc-feedback").value,candidate_id:$("mc-evidence").value,...extra});
}
page.addEventListener("click", event => {
  const button = event.target.closest("button");
  if (!button || button.disabled) return;
  const data = button.dataset;
  if (data.open) return run(()=>open(data.open));
  if ("list" in data) return run(async()=>{await flush(); route(""); await load();});
  if (data.view) return run(async()=>{await flush(); view=data.view; $("mc-feedback").value=""; render();});
  if (data.review) { reviewId=data.review; renderReview(); if (!dialog.open) dialog.showModal(); return; }
  if ("applyProposals" in data) return run(()=>author("apply", {
    job_id: board().text_job.id,
    choices: Object.fromEntries([...$("mc-proposals").querySelectorAll("select")].map(select => [select.dataset.proposal, select.value])),
  }));
  if ("evidence" in data) return run(async()=>{dialog.close(); await author("interview",{candidate_id:reviewId});});
  if (data.renderSlot) return run(()=>change(asset()+"/generate",{slot:Number(data.renderSlot),render_mode:data.mode,
    expected_candidate_id:board().slots[Number(data.renderSlot)-1]}));
  if (data.candidateAction) return run(async()=>{
    const selected = board().selected_id === data.candidate;
    if (data.candidateAction === "clear" && selected && !window.confirm("Clear the selected image?")) return;
    await change(asset()+"/candidates/"+data.candidate+"/"+data.candidateAction,{confirm_selected:selected});
  });
  if (data.boardAction === "render") return run(()=>change(asset()+"/generate",{count:Number(data.count),render_mode:data.mode}));
  if (data.boardAction === "delete-drafts") return run(()=>bulk("drafts"));
  if (data.boardAction === "delete-non-selected") return run(()=>bulk("non-selected"));
  if (data.boardAction === "luna-review") return run(()=>author("luna-review"));
});
form.addEventListener("input", event => {
  if (event.target.name === "prompt") promptDrafts.set(promptKey(), event.target.value);
  else if (event.target.name) edits.set(event.target.name, event.target.value);
});
page.addEventListener("submit",event=>{
  if (event.target.method === "dialog") return;
  event.preventDefault();
  if (event.target === form) return run(flush);
  if (event.target.id === "mc-create-form") return run(async()=>{
    const result=await api("","POST",{name:$("mc-new-name").value});
    await open(result.character.character_id);
    if (entryAsset) { await setSource({asset_id:entryAsset.asset_id,label:entryAsset.label}); entryAsset=null; }
  });
});
$("mc-write").onclick=()=>run(async()=>{ await author("write-prompt"); promptDrafts.delete(promptKey()); render(); });
$("mc-interview").onclick=()=>run(()=>author("interview"));
$("mc-save-prompt").onclick=()=>run(()=>flush(true));
$("mc-model").onclick=async()=>{
  const value=await window.ZetModelPicker.open({value:model,required:["vision"],allowDefault:true});
  if (value !== null) {model=value; $("mc-model").textContent=model || "Use configured default";}
};
$("mc-add-reference").onclick=()=>bridge.openLibraryPicker(item=>run(()=>setSource({asset_id:item.asset_id,label:item.label})));
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
  navigateList:async()=>{await flush();route("");},characterId:()=>character?.character_id || ""};

document.addEventListener("visibilitychange", () => {
  if (document.hidden) clearTimeout(timer);
  else if (character && !edits.size && page.classList.contains("active")) {
    void run(async()=>adopt((await api(base())).character));
  }
});
