(() => {
  "use strict";
  const bridge = window.zetQuickCharacterWizard;
  const $ = id => document.getElementById(id);
  if (!bridge || !$("minor-characters-page")) return;
  const fields = {name:"mc-name", style_mode:"mc-style", framing:"mc-framing",
    preserve:"mc-preserve", changes:"mc-changes", notes:"mc-notes", model:"mc-model",
    description:"mc-description", identity:"mc-identity", proposals:"mc-proposals",
    primary_reference_id:"mc-primary", comparison_reference_id:"mc-comparison-reference"};
  let character = null, universe = "", characters = [], references = [], entryAsset = null;
  let patch = {}, saving = null, saveTimer = null, pollTimer = null, pending = false, generation = 0;
  let view = "STYLE", preview = "", referenceSignature = "";
  let feedback = "", feedbackDirty = false;
  const suggestions = new Map();
  let comparisonId = "";
  const slotPending = new Set();
  const element = (tag, text = "", cls = "") => { const n = document.createElement(tag); n.textContent = text; if (cls) n.className = cls; return n; };
  const button = (text, action, run = act) => { const b = element("button", text); b.type = "button"; b.addEventListener("click", () => run(action)); return b; };
  const url = value => value + (value.includes("?") ? "&" : "?") + "universe_id=" + encodeURIComponent(universe);
  const message = (text, error = false) => { $("mc-message").textContent = text; $("mc-message").classList.toggle("error", error); };
  const label = value => ({STYLE:"Style alignment", FRONT:"Front", FRONT_LEFT_3_4:"Front left 3/4",
    FRONT_RIGHT_3_4:"Front right 3/4", LEFT_PROFILE:"Left profile", RIGHT_PROFILE:"Right profile"})[value] || value;
  async function api(path = "", method = "GET", body) {
    if (universe !== bridge.universe()) throw new Error("The active universe changed. Reopen Minor Characters.");
    return bridge.fetchJson("/api/minor-characters" + path, {method, bindToPage:false,
      ...(body === undefined ? {} : {headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)})});
  }
  async function act(operation) {
    if (pending) return;
    pending = true; updateButtons();
    try { await operation(); } catch (error) { message(error.message, true); }
    finally { pending = false; if (character) renderImages(); updateButtons(); }
  }
  function route(id, replace = false) {
    const target = new URL(location.href); target.searchParams.set("page", "minor-characters");
    if (id) target.searchParams.set("minor_character", id); else target.searchParams.delete("minor_character");
    if (target.href !== location.href) history[replace ? "replaceState" : "pushState"]({}, "", target);
  }
  function changed(key, value) {
    patch[key] = value; clearTimeout(saveTimer); message("Saving…");
    saveTimer = setTimeout(() => flush().catch(error => message(error.message, true)), 450);
  }
  async function flush() {
    clearTimeout(saveTimer);
    if (saving) { await saving; return flush(); }
    if (!character || !Object.keys(patch).length) return;
    const data = {...patch}, id = character.character_id;
    saving = api(`/${id}`, "PATCH", data).then(({character:next}) => {
      if (character?.character_id !== id) return;
      for (const key of Object.keys(data)) if (patch[key] === data[key]) delete patch[key];
      if (patch.board_edit) patch.board_edit.revision = next.boards[patch.board_edit.view].revision;
      if (data.references && !patch.references) references = next.references;
      show(next); message("Saved");
    }).finally(() => { saving = null; });
    await saving;
    if (Object.keys(patch).length) await flush();
  }
  async function refreshList() {
    characters = (await api()).characters;
    $("mc-list").replaceChildren(); $("mc-continue-choice").replaceChildren();
    $("mc-character-picker").replaceChildren(...characters.map(item => new Option(item.name, item.character_id)));
    for (const item of characters) {
      const card = element("article", "", "mc-list-card");
      card.append(element("strong", item.name, "mc-list-name"));
      const image = button("", () => open(item.character_id)); image.className = "mc-list-image";
      image.setAttribute("aria-label", `Edit ${item.name}`);
      if (item.locked.FRONT) { const img = document.createElement("img"); img.src = url(item.locked.FRONT.image_url); img.alt = `${item.name} locked front`; img.loading = "lazy"; image.append(img); }
      else image.append(element("span", "No locked front", "mc-no-front"));
      const edit = button("Edit", () => open(item.character_id));
      edit.setAttribute("aria-label", `Edit ${item.name}`);
      const remove=button("Delete",()=>deleteCharacter(item.character_id,item.name));
      remove.className="danger";remove.setAttribute("aria-label",`Delete ${item.name}`);
      const actions = element("div", "", "button-row mc-list-actions"); actions.append(edit, remove);
      card.append(image, actions); $("mc-list").append(card);
      $("mc-continue-choice").add(new Option(item.name, item.character_id));
    }
    if (!characters.length) $("mc-list").append(element("p", "Create your first Minor Character."));
    $("mc-continue").disabled = !characters.length;
    nameMatch();
  }
  function nameMatch() {
    const key = $("mc-new-name").value.trim().toLocaleLowerCase();
    const found = characters.find(c => c.name.trim().toLocaleLowerCase() === key);
    $("mc-name-match").replaceChildren();
    if (found) $("mc-name-match").append(button(`Open existing ${found.name}`, () => open(found.character_id)));
  }
  async function list() {
    await flush(); generation++; clearTimeout(pollTimer); character = null; patch = {}; feedbackDirty = false; route("");
    $("mc-editor").hidden = true; $("mc-character-picker-label").hidden = true; $("mc-review").close(); $("mc-list-panel").hidden = false;
    $("mc-inventory-entry").hidden = !entryAsset; await refreshList(); message("");
  }
  async function open(id) {
    $("mc-review").close(); comparisonId = "";
    await flush(); generation++; clearTimeout(pollTimer); patch = {}; feedback = ""; feedbackDirty = false; suggestions.clear();
    const result = await api(`/${id}`); character = result.character;
    references = character.references; referenceSignature = "";
    view = character.views.includes(character.active_view) ? character.active_view : "STYLE";
    preview = character.preview_candidate_id || ""; route(character.character_id);
    $("mc-list-panel").hidden = true; $("mc-editor").hidden = false; $("mc-character-picker-label").hidden = false;
    $("mc-character-picker").value = character.character_id;
    show(character); message("");
  }
  async function deleteCharacter(id, name) {
    if (!window.confirm(`Delete Minor Character “${name}”? Published Inventory images will be kept.`)) return;
    await flush();generation++;clearTimeout(pollTimer);
    await api(`/${id}`,"DELETE");
    $("mc-review").close();character=null;patch={};entryAsset=null;
    await list();message(`Deleted ${name}.`);
  }
  function imageFigure(source, caption) {
    const figure = element("figure"); const img = document.createElement("img"); img.src = url(source); img.alt = caption;
    figure.append(img, element("figcaption", caption)); return figure;
  }
  function awaitingResponse() {
    return Boolean(character?.busy || character?.candidates.some(candidate => candidate.status === "REVIEWING"));
  }
  function referencePayload() {
    return references.map(r => ({...(r.reference_id ? {reference_id:r.reference_id} : {}),
      ...(r.image ? {image:r.image} : !r.reference_id ? {asset_id:r.asset_id} : {}), caption:r.caption}));
  }
  function drawReferences() {
    const signature = JSON.stringify(references);
    if (signature === referenceSignature || $("mc-references").contains(document.activeElement)) return;
    referenceSignature = signature; $("mc-references").replaceChildren();
    references.forEach((ref, index) => {
      const card = element("section", "", "mc-reference");
      if (ref.url || ref.image) { const img = document.createElement("img"); img.src = ref.image || url(ref.url); img.alt = `Reference ${index+1}`; card.append(img); }
      card.append(element("figcaption", ref.caption, "mc-reference-caption"), button("Remove", async () => { references.splice(index, 1); referenceSignature = ""; changed("references", referencePayload()); drawReferences(); await flush(); }));
      $("mc-references").append(card);
    });
  }
  function show(next) {
    const edit=patch.board_edit, previous=edit && character?.boards[edit.view], incoming=edit && next.boards[edit.view];
    if (previous && incoming && previous.template_candidate_id===incoming.template_candidate_id
        && incoming.revision>=edit.revision) edit.revision=incoming.revision;
    character = next;
    if (!patch.references) references = character.references;
    for (const [key, id] of Object.entries(fields)) {
      if (["primary_reference_id","comparison_reference_id"].includes(key)) continue;
      if (key === "model") {
        const control = $(id), value = patch.model ?? character.model ?? "";
        if (value && ![...control.options].some(option => option.value === value)) control.add(new Option(`${value} (unavailable)`, value));
        control.value = value;
        window.ZetModelPicker?.sync(control);
        continue;
      }
      if (!(key in patch) && document.activeElement !== $(id)) $(id).value = key === "proposals" ? character.proposals.join("\n") : character[key] || "";
    }
    for (const [key, id] of [["primary_reference_id","mc-primary"],["comparison_reference_id","mc-comparison-reference"]]) {
      const picker = $(id); picker.replaceChildren(...references.filter(r=>r.reference_id).map((r,i)=>new Option(`Reference ${i+1} · ${r.caption}`,r.reference_id)));
      picker.value = patch[key] || character[key];
    }
    drawReferences();
    $("mc-style-text").textContent = character.target_brief?.style?.text || "";
    $("mc-questions").replaceChildren();
    for (const question of character.questions) $("mc-questions").append(element("p", question));
    if (character.questions.length) $("mc-questions").append(element("p",
      "To answer these questions, enter your choices in Additional direction above and correct any conflicting instructions. Then click Analyze references below. Once analysis finishes, click Generate style alignment on the Style alignment tab to create an image using the updated description.", "muted"));
    if (!patch.board_edit) {
      const edit = board()?.edit;
      if (!feedbackDirty) feedback = edit?.instructions || "";
      if (edit?.candidate_id) suggestions.set(edit.candidate_id, new Set(edit.item_ids));
    }
    renderImages(); updateButtons();
    if (character.job.error) message(character.job.error, true);
    clearTimeout(pollTimer);
    if (awaitingResponse() && $("minor-characters-page").classList.contains("active")) {
      const id = character.character_id, current = generation;
      pollTimer = setTimeout(async () => {
        try { const result = await api(`/${id}`); if (current === generation && character?.character_id === id) show(result.character); }
        catch (error) { message(error.message, true); }
      }, 1800);
    }
  }
  function choice() { return character?.candidates.find(c=>c.candidate_id===preview && c.view===view); }
  function board() { return character?.boards[view]; }
  function occupied() { return (board()?.slots || []).map(id=>character.candidates.find(c=>c.candidate_id===id)).filter(c=>c?.image_url); }
  function persistEdit() {
    const source = choice()?.candidate_id || board()?.edit.candidate_id || "";
    changed("board_edit", {view, revision:board().revision, candidate_id:source,
      item_ids:[...(suggestions.get(source) || [])], instructions:feedback});
  }
  async function selectCandidate(id = preview) {
    await flush(); show((await api(`/${character.character_id}/select`,"POST",{candidate_id:id,revision:board().revision})).character);
  }
  async function slotAction(action, slot, count = 1) {
    const id=character.character_id, target=view, current=generation, key=`${id}:${target}:${slot ?? "add"}`;
    if (slotPending.has(key)) return;
    slotPending.add(key); renderImages();
    try {
      await flush();
      const result=await api(`/${id}/boards/${target}/slots/action`,"POST",{action,slot,count,revision:board().revision});
      if (character?.character_id===id && current===generation) show(result.character);
    } catch (error) { message(error.message,true); }
    finally { slotPending.delete(key); if (character?.character_id===id) {renderImages();updateButtons();} }
  }
  async function lockCandidate(candidate) {
    await flush();
    const locked=character.locked[candidate.view]?.candidate_id===candidate.candidate_id;
    show((await api(`/${character.character_id}/${locked ? "unlock" : "lock"}`,"POST",{view:candidate.view,candidate_id:candidate.candidate_id,revision:board().revision})).character);
    message(locked ? "View unlocked. Saved Inventory images are retained." : candidate.view==="STYLE" ? "Style alignment locked." : "Locked image saved to Inventory.");
  }
  function lockControl(candidate) {
    const locked=character.locked[candidate.view]?.candidate_id===candidate.candidate_id;
    const title=`${locked ? "Unlock" : "Lock"} ${label(candidate.view).toLowerCase()}`;
    const control=button(locked ? "🔒 Unlock" : "🔓 Lock",()=>lockCandidate(candidate));
    control.title=title;control.setAttribute("aria-label",title);control.setAttribute("aria-pressed",String(locked));
    control.disabled=pending || slotPending.size>0;
    return control;
  }
  function comparisons() {
    const result = [], seen = new Set();
    const add = (id, source, caption, checksum) => {
      if (!source || seen.has(checksum || id)) return;
      seen.add(checksum || id); result.push({id, source, caption});
    };
    const original = references.find(r=>r.reference_id===(patch.comparison_reference_id || character.comparison_reference_id)) || references[0];
    if (original) add(original.reference_id, original.url, "Designated original", original.checksum);
    const addCandidate = (id, caption) => {
      const candidate = character.candidates.find(c=>c.candidate_id===id);
      if (candidate) add(id, candidate.image_url, caption, candidate.sha256);
    };
    if (view==="STYLE") {
      for (const id of character.boards.STYLE.slots) addCandidate(id,"Style-alignment candidate");
    } else {
      addCandidate(character.selected.STYLE,"Selected style alignment");
      for (const other of character.views.filter(v=>v!=="STYLE" && v!==view)) addCandidate(character.selected[other],`Selected ${label(other).toLowerCase()}`);
    }
    return result;
  }
  function renderReview() {
    if (!$("mc-review").open) return;
    const list = occupied(), candidate = choice(), index = list.findIndex(c=>c.candidate_id===preview);
    const previous=$("mc-review-prev"), next=$("mc-review-next");
    $("mc-review-navigation").append(previous,next);
    $("mc-review-pair").replaceChildren();
    const sources = comparisons();
    const ref = sources.find(r=>r.id===comparisonId) || sources[0];
    comparisonId = ref?.id || "";
    if (ref) {
      const figure=imageFigure(ref.source,ref.caption), arrows=element("div","","button-row mc-comparison-arrows");
      for (const [text,direction] of [["‹",-1],["›",1]]) {
        const arrow=button(text,()=>{
          comparisonId=sources[(sources.indexOf(ref)+direction+sources.length)%sources.length].id;
          renderReview();
        }, operation=>operation());
        arrow.setAttribute("aria-label",direction<0 ? "Previous comparison image" : "Next comparison image");
        arrow.disabled=sources.length<2; arrows.append(arrow);
      }
      figure.append(arrows); $("mc-review-pair").append(figure);
    }
    if (candidate?.image_url && index>=0) {
      const figure=imageFigure(candidate.image_url,`${character.name} · ${label(view)} · Slot ${board().slots.indexOf(preview)+1}`);
      const select=button(character.selected[view]===preview ? "Selected" : "Select",()=>selectCandidate(candidate.candidate_id));
      select.classList.add("primary-action");
      select.disabled=pending || character.selected[view]===preview;
      const actions=element("div","","button-row mc-review-actions");actions.append(previous,select);
      if (candidate.can_lock) {
        actions.append(lockControl(candidate));
      }
      actions.append(next);figure.append(actions);$("mc-review-pair").append(figure);
    }
    previous.disabled=index<=0;next.disabled=index<0 || index>=list.length-1;
  }
  function navigateReview(direction) {
    const list=occupied(), index=list.findIndex(c=>c.candidate_id===preview), next=list[index+direction];
    if (next) { previewCandidate(next.candidate_id); renderImages(); updateButtons(); }
  }
  function previewCandidate(id) {
    if (preview!==id) { feedback=board().edit.candidate_id===id ? board().edit.instructions : ""; feedbackDirty=false; }
    preview=id;changed("preview_candidate_id",preview);persistEdit();
  }
  function inspect(id = preview) {
    previewCandidate(id);renderImages(); if (!$("mc-review").open) $("mc-review").showModal(); renderReview();
  }
  function renderImages() {
    if (!character.views.includes(view)) view="STYLE";
    const current=board();
    if (!current?.slots.includes(preview)) preview=current?.slots.find(id=>id===character.selected[view]) || current?.slots.find(Boolean) || "";
    $("mc-tabs").replaceChildren();
    for (const target of character.views) {
      const tab=button(label(target),async()=>{
        await flush();view=target;preview="";comparisonId="";feedback=character.boards[target]?.edit.instructions || "";feedbackDirty=false;
        changed("active_view",view);show(character);
      });
      tab.disabled=target!=="STYLE" && !character.selected.STYLE && !character.boards[target]?.slots.some(Boolean);
      tab.title=tab.disabled ? "Select a style-alignment image first" : "";
      tab.setAttribute("role","tab");tab.setAttribute("aria-selected",String(view===target));$("mc-tabs").append(tab);
    }
    $("mc-stage-status").textContent=label(view)+(view==="STYLE" ? " · Select a style image to enable views" : current?.mode==="true_up" ? " · True-ups" : " · View alignment: select an image, then continue");
    $("mc-restart").textContent=`Restart ${label(view)}`;
    $("mc-slots").replaceChildren();$("mc-add-renders").replaceChildren();
    for(let slot=0;slot<4;slot++) {
      const candidate=character.candidates.find(c=>c.candidate_id===current?.slots[slot]);
      const card=element("section","","mc-slot");card.append(element("strong",`Slot ${slot+1}`));
      card.addEventListener("click",event=>{
        if (!candidate?.image_url || event.target.closest("button")) return;
        previewCandidate(candidate.candidate_id);renderImages();updateButtons();
      });
      card.classList.toggle("mc-slot-preview",candidate?.candidate_id===preview);
      if(candidate && current.prior_selection_id===candidate.candidate_id) card.append(element("span","Prior selection","mc-prior-selection"));
      if(candidate?.image_url) {
        const thumb=button("",()=>inspect(candidate.candidate_id));thumb.className="mc-slot-image";thumb.title="Inspect full size";
        const img=document.createElement("img");img.src=url(candidate.image_url);img.alt=`Slot ${slot+1} candidate`;thumb.append(img);card.append(thumb);
      } else if (!candidate) card.append(element("p", "Empty", "image-card-state"));
      if (candidate?.error) card.append(element("p", candidate.error, "error"));
      const controls=element("div","","button-row mc-slot-actions");
      const submitting=slotPending.size>0;
      const regen=button(candidate ? "Regenerate" : "Generate",async()=>{
        if(candidate) previewCandidate(candidate.candidate_id);
        await slotAction("regenerate",slot);
      },operation=>operation());
      regen.disabled=pending || submitting || !current?.template_candidate_id;
      const clear=button("Clear slot",async()=>{
        if(candidate) previewCandidate(candidate.candidate_id);
        await slotAction("clear",slot);
      },operation=>operation());clear.disabled=pending || submitting || !candidate;
      const select=button(candidate && character.selected[view]===candidate.candidate_id ? "Selected" : "Select",async()=>{
        previewCandidate(candidate.candidate_id);await selectCandidate(candidate.candidate_id);
      });select.disabled=pending || !candidate?.image_url;
      clear.classList.add("danger-text-action");
      if (!candidate) regen.classList.add("primary-action");
      else if (character.selected[view] !== candidate.candidate_id) select.classList.add("primary-action");
      card.classList.toggle("is-selected", Boolean(candidate && character.selected[view] === candidate.candidate_id));
      card.dataset.state = !candidate ? "empty" : character.locked[view]?.candidate_id === candidate.candidate_id ? "locked" : character.selected[view] === candidate.candidate_id ? "selected" : candidate.status === "FAILED" ? "failed" : candidate.image_url ? "available" : "pending";
      if (candidate) card.append(element("p", `${candidate.status.toLowerCase()}${character.selected[view] === candidate.candidate_id ? " · Selected" : ""}${character.locked[view]?.candidate_id === candidate.candidate_id ? " · Locked" : ""}`, "muted image-card-state"));
      if (regen.disabled) card.append(element("p", pending || submitting ? "An operation is in progress." : "Select an alignment image to enable rendering.", "slot-action-reason muted"));
      controls.append(select);
      if(candidate?.can_lock) {
        controls.append(lockControl(candidate));
      }
      controls.append(regen,clear);
      card.append(controls);$("mc-slots").append(card);
    }
    if(current?.template_candidate_id) $("mc-add-renders").append(window.ZetRenderSlots.countControl(current.slots.filter(id=>!id).length,count=>slotAction("add",undefined,count),{disabled:pending || slotPending.size>0}));
    const candidate=choice(), source=candidate || current?.findings;
    $("mc-feedback").value=feedback;
    $("mc-current-prompt").textContent=current?.prompt || "";
    $("mc-current-prompt-panel").hidden=!current?.prompt;
    $("mc-suggestions-title").textContent=candidate ? `Suggested changes · Slot ${current.slots.indexOf(preview)+1}` : "Suggested changes";
    $("mc-findings").replaceChildren();
    if(source?.comparison) {
      $("mc-findings").append(element("p",source.review));
      const id=candidate?.candidate_id || current.edit.candidate_id;
      const selected=suggestions.get(id) || new Set();suggestions.set(id,selected);
      for(const item of source.comparison.items) {
        const row=element("div","","qc-finding");row.append(element("strong",item.feature),element("p",`Expected: ${item.expected}`),element("p",`Observed: ${item.observed}`));
        if(item.correction) {
          const labelNode=element("label",item.correction),input=document.createElement("input");input.type="checkbox";input.checked=selected.has(item.id);
          input.addEventListener("change",()=>{input.checked ? selected.add(item.id) : selected.delete(item.id);persistEdit();});labelNode.prepend(input);row.append(labelNode);
        }
        $("mc-findings").append(row);
      }
    } else $("mc-findings").append(element("p",source?.review || source?.error || (candidate?.status==="REVIEWING" ? "Suggested changes are being prepared. Selection and custom refinement remain available." : "Inspect a candidate to see suggested changes.")));
    renderReview();
  }
  function updateButtons() {
    const busy = pending || character?.busy;
    const current=board();
    $("mc-generate").textContent=view==="STYLE" ? "Generate style alignment" : "Generate view alignment";
    $("mc-generate-help").textContent=view==="STYLE" ? "Establish style and character details without requiring an official view. Select an image before generating views." : "Uses only the selected style image and a short orientation prompt. A new alignment replaces this view's working board.";
    $("mc-generate").disabled=!character || busy || (view==="STYLE" ? !references.length : !character.selected.STYLE);
    $("mc-refine").disabled=!character || busy || (!choice()?.image_url && !current?.edit.candidate_id) || (view!=="STYLE" && current?.mode!=="true_up");
    $("mc-refine").title=view!=="STYLE" && current?.mode!=="true_up" ? "Select an aligned image and continue to true-ups first" : "";
    $("mc-continue-true-ups").hidden=view==="STYLE" || current?.mode==="true_up";
    $("mc-continue-true-ups").disabled=busy || !current?.can_continue;
    $("mc-undo").disabled=busy || !current?.can_undo;
    $("mc-restart").disabled=busy || !character || (view==="STYLE" ? !references.length : !character.selected.STYLE);
    $("mc-analyze").disabled = !character || busy || !references.length;
    $("mc-add-reference").disabled = pending || references.length>=3;
    $("mc-upload-trigger").disabled = references.length>=3;
    $("mc-upload").disabled = references.length>=3;
    $("mc-delete").disabled=pending || !character;
    if (character) renderReview();
  }
  async function addReference(reference) {
    if (references.length>=3) throw new Error("Use up to three original references.");
    references.push(reference); referenceSignature=""; changed("references",referencePayload()); drawReferences(); await flush();
  }
  async function upload(file) {
    if (!file || !["image/png","image/jpeg","image/webp"].includes(file.type) || file.size>20*1024*1024) throw new Error("Choose a PNG, JPEG or WEBP image up to 20 MiB.");
    const image = await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error("Could not read image."));reader.readAsDataURL(file);});
    await addReference({image,caption:file.name || "Identity and appearance reference"});
  }
  async function generateImage(refine) {
    await flush();
    const source=choice()?.candidate_id || board().edit.candidate_id;
    const result=await api(`/${character.character_id}/generate`,"POST",{view,revision:board().revision,
      ...(refine ? {candidate_id:source,instructions:feedback,item_ids:[...(suggestions.get(source)||[])]} : {})});
    feedbackDirty=false;
    preview=result.character.boards[view].template_candidate_id;show(result.character);
  }
  async function boardAction(action) {
    await flush();
    const result=await api(`/${character.character_id}/boards/${view}/${action}`,"POST",{revision:board().revision});
    preview="";show(result.character);
  }
  function viewWorkStarted() {
    return character.views.some(target=>{
      if (target==="STYLE") return false;
      const current=character.boards[target];
      return Boolean(current?.template_candidate_id || current?.slots.some(Boolean) || current?.selected_id
        || current?.mode==="true_up" || current?.can_undo);
    });
  }
  async function restartCurrentOperation() {
    const target=view, confirmViews=target==="STYLE" && viewWorkStarted();
    if (confirmViews && !window.confirm("Restarting Style alignment will discard all view images and revisions. Continue?")) return;
    await flush();
    const result=await api(`/${character.character_id}/boards/${target}/restart`,"POST",{
      revision:board().revision, confirm_views_discarded:confirmViews});
    patch={}; feedback=""; feedbackDirty=false; suggestions.clear(); comparisonId="";
    view=target; preview=target==="STYLE" ? "" : result.character.boards[target].template_candidate_id;
    show(result.character);
  }
  async function load() {
    if (universe!==bridge.universe()) { generation++; clearTimeout(pollTimer); character=null; patch={}; universe=bridge.universe(); entryAsset=null; }
    const options = await api("/options"); $("mc-model").replaceChildren(...options.models.map(m=>new Option(m,m)));
    await refreshList();
    const requested = new URL(location.href).searchParams.get("minor_character");
    if (requested) { if (character?.character_id!==requested) await open(requested); else show(character); }
    else await list();
  }
  async function fromInventory() {
    const asset=bridge.selectedAsset(); if (!asset) throw new Error("Choose an Inventory image first.");
    universe=bridge.universe(); const owner=await api(`/owner/${encodeURIComponent(asset.asset_id)}`);
    if (owner.character_id) { route(owner.character_id); await bridge.activatePage("minor-characters"); return; }
    await flush(); entryAsset=asset; character=null; route(""); await bridge.activatePage("minor-characters");
    $("mc-new-name").value=asset.label || ""; $("mc-entry-image").src=bridge.fileUrl(asset.image_path); $("mc-inventory-entry").hidden=false; nameMatch();
  }
  for (const [key,id] of Object.entries(fields)) $(id).addEventListener("input",()=>{
    let value=$(id).value; if (key==="proposals") value=value.split("\n").map(s=>s.trim()).filter(Boolean);
    changed(key,value);
    if (key==="comparison_reference_id") renderImages();
    if (key==="name") { const match=characters.find(c=>c.character_id!==character?.character_id && c.name.trim().toLocaleLowerCase()===value.trim().toLocaleLowerCase());
      $("mc-rename-match").replaceChildren(); if(match) $("mc-rename-match").append(button(`Open existing ${match.name}`,async()=>{delete patch.name;await open(match.character_id);})); }
  });
  $("mc-feedback").addEventListener("input",()=>{feedback=$("mc-feedback").value;feedbackDirty=true;persistEdit();});
  $("mc-new-name").addEventListener("input",nameMatch);
  $("mc-create-form").addEventListener("submit",event=>{event.preventDefault();act(async()=>{
    const result=await api("","POST",{name:$("mc-new-name").value}); const asset=entryAsset;
    await open(result.character.character_id);
    if(asset && !result.character.existing) await addReference({asset_id:asset.asset_id,caption:asset.label || "Identity reference"});
    entryAsset=null; if(result.character.existing) message("Opened the existing Minor Character.");
  });});
  $("mc-continue-true-ups").addEventListener("click",()=>act(()=>boardAction("continue")));
  $("mc-undo").addEventListener("click",()=>act(()=>boardAction("undo")));
  $("mc-restart").addEventListener("click",()=>act(restartCurrentOperation));
  $("mc-delete").addEventListener("click",()=>act(()=>deleteCharacter(character.character_id,character.name)));
  $("mc-continue").addEventListener("click",()=>act(async()=>{entryAsset=null;await open($("mc-continue-choice").value);}));
  $("mc-character-picker").addEventListener("change",event=>act(()=>open(event.target.value)));
  $("mc-generate").addEventListener("click",()=>act(()=>generateImage(false)));
  $("mc-refine").addEventListener("click",()=>act(()=>generateImage(true)));
  $("mc-review-close").addEventListener("click",()=>$("mc-review").close());
  $("mc-review-prev").addEventListener("click",()=>navigateReview(-1));
  $("mc-review-next").addEventListener("click",()=>navigateReview(1));
  document.addEventListener("keydown",event=>{
    if ($("mc-review").open && ["ArrowLeft","ArrowRight"].includes(event.key) && !["INPUT","TEXTAREA","SELECT"].includes(event.target.tagName)) {
      event.preventDefault(); navigateReview(event.key==="ArrowLeft" ? -1 : 1);
    }
  });
  $("mc-analyze").addEventListener("click",()=>act(async()=>{await flush();show((await api(`/${character.character_id}/analyze`,"POST",{})).character);}));
  $("mc-add-reference").addEventListener("click",()=>act(()=>bridge.openLibraryPicker(asset=>act(()=>addReference({asset_id:asset.asset_id,caption:asset.label || "Identity reference"})))));
  $("mc-upload-trigger").addEventListener("click",()=>$("mc-upload").click());
  $("mc-upload").addEventListener("change",()=>act(async()=>{await upload($("mc-upload").files[0]);$("mc-upload").value="";}));
  window.ZetImageInput.attach($("mc-paste"), $("mc-upload"));
  $("mc-paste").addEventListener("click",()=>$("mc-paste").focus());
  $("mc-paste").addEventListener("paste",event=>{const item=[...(event.clipboardData?.items||[])].find(i=>i.type.startsWith("image/"));if(item){event.preventDefault();act(()=>upload(item.getAsFile()));}});
  $("quick-character-wizard-open").addEventListener("click",()=>act(async()=>{route("");await bridge.activatePage("minor-characters");}));
  $("quick-character-wizard-from-asset").addEventListener("click",()=>act(fromInventory));
  window.zetMinorCharacters={load,flush,navigateList:async()=>{await flush();route("");},characterId:()=>character?.character_id || ""};
})();
