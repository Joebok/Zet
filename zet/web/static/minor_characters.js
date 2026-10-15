(() => {
  "use strict";
  const bridge = window.zetQuickCharacterWizard;
  const $ = id => document.getElementById(id);
  if (!bridge || !$("minor-characters-page")) return;
  const fields = {name:"mc-name", style_mode:"mc-style", framing:"mc-framing", side:"mc-side",
    preserve:"mc-preserve", changes:"mc-changes", notes:"mc-notes", model:"mc-model",
    description:"mc-description", identity:"mc-identity", proposals:"mc-proposals",
    primary_reference_id:"mc-primary", comparison_reference_id:"mc-comparison-reference"};
  let character = null, universe = "", characters = [], references = [], entryAsset = null;
  let patch = {}, saving = null, saveTimer = null, pollTimer = null, pending = false, generation = 0;
  let view = "FRONT", preview = "", referenceSignature = "";
  let waitingForCandidate = null;
  let iterationId = "";
  const feedback = new Map(), suggestions = new Map();
  const element = (tag, text = "", cls = "") => { const n = document.createElement(tag); n.textContent = text; if (cls) n.className = cls; return n; };
  const button = (text, action) => { const b = element("button", text); b.type = "button"; b.addEventListener("click", () => act(action)); return b; };
  const url = value => value + (value.includes("?") ? "&" : "?") + "universe_id=" + encodeURIComponent(universe);
  const message = (text, error = false) => { $("mc-message").textContent = text; $("mc-message").classList.toggle("error", error); };
  const label = value => value === "FRONT" ? "Front" : value.includes("3_4") ? "Three-quarter" : "Profile";
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
    history[replace ? "replaceState" : "pushState"]({}, "", target);
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
      if (data.references && !patch.references) references = next.references;
      show(next); message("Saved");
    }).finally(() => { saving = null; });
    await saving;
    if (Object.keys(patch).length) await flush();
  }
  async function refreshList() {
    characters = (await api()).characters;
    $("mc-list").replaceChildren(); $("mc-continue-choice").replaceChildren();
    for (const item of characters) {
      const row = button("", () => open(item.character_id)); row.className = "mc-list-row";
      if (item.locked.FRONT) { const img = document.createElement("img"); img.src = url(item.locked.FRONT.image_url); img.alt = `${item.name} locked front`; row.append(img); }
      else row.append(element("span", "No locked front", "mc-no-front"));
      row.append(element("strong", item.name)); $("mc-list").append(row);
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
    await flush(); generation++; clearTimeout(pollTimer); character = null; patch = {}; route("");
    $("mc-editor").hidden = true; $("mc-back").hidden = true; $("mc-list-panel").hidden = false;
    $("mc-inventory-entry").hidden = !entryAsset; await refreshList(); message("");
  }
  async function open(id) {
    $("mc-review").close(); iterationId = "";
    await flush(); generation++; clearTimeout(pollTimer); patch = {}; feedback.clear(); suggestions.clear();
    const result = await api(`/${id}`); character = result.character;
    references = character.references; referenceSignature = "";
    view = character.views.includes(character.active_view) ? character.active_view : "FRONT";
    preview = character.preview_candidate_id || ""; iterationId=character.active_iteration_id || ""; route(character.character_id);
    $("mc-list-panel").hidden = true; $("mc-editor").hidden = false; $("mc-back").hidden = false;
    show(character); message("");
  }
  function imageFigure(source, caption) {
    const figure = element("figure"); const img = document.createElement("img"); img.src = url(source); img.alt = caption;
    figure.append(img, element("figcaption", caption)); return figure;
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
      const caption = document.createElement("textarea"); caption.value = ref.caption; caption.rows = 2; caption.setAttribute("aria-label", `Reference ${index+1} role`);
      caption.addEventListener("input", () => { ref.caption = caption.value; changed("references", referencePayload()); });
      card.append(caption, button("Remove", async () => { references.splice(index, 1); referenceSignature = ""; changed("references", referencePayload()); drawReferences(); await flush(); }));
      $("mc-references").append(card);
    });
  }
  function show(next) {
    character = next;
    if (!patch.references) references = character.references;
    for (const [key, id] of Object.entries(fields)) {
      if (["primary_reference_id","comparison_reference_id"].includes(key)) continue;
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
    renderImages(); updateButtons();
    if (character.job.error) message(character.job.error, true);
    clearTimeout(pollTimer);
    if ((character.busy || character.candidates.some(c=>c.status==="REVIEWING")) && $("minor-characters-page").classList.contains("active")) {
      const id = character.character_id, current = generation;
      pollTimer = setTimeout(async () => {
        try { const result = await api(`/${id}`); if (current === generation && character?.character_id === id) show(result.character); }
        catch (error) { message(error.message, true); }
      }, 1800);
    }
  }
  function choice() { return character?.candidates.find(c=>c.candidate_id===preview && c.view===view); }
  function iteration() { return character?.iterations.find(i=>i.iteration_id===iterationId && i.view===view); }
  function occupied() { return (iteration()?.slots || []).map(id=>character.candidates.find(c=>c.candidate_id===id)).filter(c=>c?.image_url); }
  async function selectCandidate(id = preview) {
    await flush(); show((await api(`/${character.character_id}/select`,"POST",{candidate_id:id})).character);
  }
  async function slotAction(action, slot, count = 1) {
    await flush(); show((await api(`/${character.character_id}/iterations/${iterationId}/slots`,"POST",{action,slot,count})).character);
  }
  function renderReview() {
    if (!$("mc-review").open) return;
    const list = occupied(), candidate = choice(), index = list.findIndex(c=>c.candidate_id===preview);
    const ref = references.find(r=>r.reference_id===(patch.comparison_reference_id || character.comparison_reference_id)) || references[0];
    $("mc-review-pair").replaceChildren();
    if (ref?.url) $("mc-review-pair").append(imageFigure(ref.url,"Original reference"));
    if (candidate?.image_url && index>=0) {
      const figure = imageFigure(candidate.image_url,`${character.name} · ${label(view)} · ${index+1} of ${list.length}`);
      const select = button(character.selected[view]===preview ? "Selected candidate" : "Select candidate",()=>selectCandidate(candidate.candidate_id));
      select.disabled = pending || character.selected[view]===preview; figure.append(select); $("mc-review-pair").append(figure);
    }
    $("mc-review-prev").disabled = index<=0;
    $("mc-review-next").disabled = index<0 || index>=list.length-1;
  }
  function navigateReview(direction) {
    const list=occupied(), index=list.findIndex(c=>c.candidate_id===preview), next=list[index+direction];
    if (next) { preview=next.candidate_id; changed("preview_candidate_id",preview); renderImages(); updateButtons(); }
  }
  function inspect(id = preview) {
    preview=id; changed("preview_candidate_id",preview); renderImages(); if (!$("mc-review").open) $("mc-review").showModal(); renderReview();
  }
  function renderImages() {
    if (!character.views.includes(view)) view = "FRONT";
    const candidates = character.candidates.filter(c=>c.view===view);
    if (waitingForCandidate?.view===view && candidates.length>waitingForCandidate.count) {
      preview=candidates.at(-1).candidate_id; iterationId=candidates.at(-1).iteration_id;
      waitingForCandidate=null; changed("preview_candidate_id",preview); changed("active_iteration_id",iterationId);
    }
    const iterations=character.iterations.filter(i=>i.view===view);
    if (choice() && (waitingForCandidate===null) && !iteration()) iterationId=choice().iteration_id;
    if (!iteration()) iterationId=iterations.at(-1)?.iteration_id || "";
    if (!iteration()?.slots.includes(preview)) preview=iteration()?.slots.find(id=>id===character.selected[view]) || iteration()?.slots.find(Boolean) || "";
    $("mc-tabs").replaceChildren();
    for (const target of character.views) {
      const tab = button(label(target), async () => { view = target; preview = ""; iterationId=""; renderImages(); changed("active_view", view); changed("preview_candidate_id", preview); updateButtons(); });
      tab.setAttribute("role", "tab"); tab.setAttribute("aria-selected", String(view===target)); $("mc-tabs").append(tab);
    }
    $("mc-candidates").replaceChildren();
    for (const [index, item] of iterations.entries()) {
      const candidate=character.candidates.find(c=>c.candidate_id===(item.slots.find(id=>id===character.selected[view]) || item.slots.find(Boolean) || item.template_candidate_id));
      const tile = button("", async () => { iterationId=item.iteration_id; preview=item.slots.find(Boolean) || ""; renderImages(); changed("active_iteration_id",iterationId); changed("preview_candidate_id", preview); updateButtons(); });
      tile.className = "mc-candidate"; tile.setAttribute("aria-label", `Iteration ${index+1}`); tile.setAttribute("aria-pressed",String(iterationId===item.iteration_id));
      if (candidate.image_url) { const img = document.createElement("img"); img.src = url(candidate.image_url); img.alt = `${label(view)} candidate`; tile.append(img); }
      else tile.append(element("span", candidate.status.toLowerCase().replaceAll("_"," ")));
      tile.append(element("span",`Iteration ${index+1}`));
      if (item.slots.includes(character.selected[view])) tile.append(element("span","Selected"));
      if (item.slots.includes(character.locked[view]?.candidate_id)) tile.append(element("span","Locked"));
      $("mc-candidates").append(tile);
    }
    $("mc-slots").replaceChildren(); $("mc-add-renders").replaceChildren();
    const board=iteration();
    for (let slot=0;slot<4;slot++) {
      const candidate=character.candidates.find(c=>c.candidate_id===board?.slots[slot]);
      const card=element("section","","mc-slot"); card.append(element("strong",`Slot ${slot+1}`));
      if (candidate?.image_url) {
        const thumb=button("",()=>inspect(candidate.candidate_id)); thumb.className="mc-slot-image";
        const img=document.createElement("img"); img.src=url(candidate.image_url); img.alt=`Slot ${slot+1} candidate`; thumb.append(img); card.append(thumb);
        const select=button(character.selected[view]===candidate.candidate_id ? "Selected" : "Select",()=>selectCandidate(candidate.candidate_id));
        select.disabled=pending; card.append(select);
      } else card.append(element("p",candidate ? candidate.error || candidate.status.toLowerCase() : "Empty"));
      const controls=element("div","","button-row");
      const regen=button("Regenerate",()=>slotAction("regenerate",slot)); regen.disabled=pending || character.busy || !board;
      const clear=button("Clear",()=>slotAction("clear",slot)); clear.disabled=pending || !candidate || ["QUEUING","QUEUED","RUNNING"].includes(candidate.status);
      controls.append(regen,clear); card.append(controls); $("mc-slots").append(card);
    }
    if (board) $("mc-add-renders").append(window.ZetRenderSlots.countControl(board.slots.filter(id=>!id).length,count=>act(()=>slotAction("add",undefined,count)),{disabled:pending || character.busy}));
    const candidate = choice(); const refId = patch.comparison_reference_id || character.comparison_reference_id;
    const reference = references.find(r=>r.reference_id===refId) || references[0];
    $("mc-comparison").replaceChildren();
    if (reference?.url) $("mc-comparison").append(imageFigure(reference.url, "Original reference"));
    else $("mc-comparison").append(element("p", "Add an original reference on the left."));
    if (candidate?.image_url) $("mc-comparison").append(imageFigure(candidate.image_url, `${character.name} · ${label(view)}`));
    else $("mc-comparison").append(element("p", candidate ? "Generating image…" : "Generate an image to compare here."));
    $("mc-feedback").value = feedback.get(view) || "";
    $("mc-candidate-status").textContent = candidate?.error || (character.busy ? "Working…" : candidate?.image_url ? "Choose this image or try another change." : "");
    $("mc-findings").replaceChildren();
    if (candidate?.comparison) {
      $("mc-findings").append(element("p", candidate.review));
      const selected = suggestions.get(preview) || new Set(); suggestions.set(preview, selected);
      for (const item of candidate.comparison.items) {
        const row = element("div", "", "qc-finding"); row.append(element("strong",item.feature),element("p",`Expected: ${item.expected}`),element("p",`Observed: ${item.observed}`));
        if (item.correction) { const labelNode = element("label",item.correction); const input = document.createElement("input"); input.type="checkbox"; input.checked=selected.has(item.id);
          input.addEventListener("change",()=>input.checked ? selected.add(item.id) : selected.delete(item.id)); labelNode.prepend(input); row.append(labelNode); }
        $("mc-findings").append(row);
      }
    } else if (candidate?.review) $("mc-findings").append(element("p", candidate.review));
    $("mc-open-locked").hidden = !character.locked[view];
    $("mc-inspect").disabled = !candidate?.image_url;
    renderReview();
  }
  function updateButtons() {
    const busy = pending || character?.busy;
    $("mc-generate").textContent = "Generate " + label(view).toLowerCase();
    $("mc-generate").disabled = !character || busy || !references.length || (view!=="FRONT" && !character.selected.FRONT);
    $("mc-refine").disabled = !character || busy || !choice()?.image_url;
    $("mc-select").disabled = pending || !choice()?.image_url;
    $("mc-lock").disabled = pending || !choice()?.image_url || character?.selected[view]!==preview;
    $("mc-analyze").disabled = !character || busy || !references.length;
    $("mc-add-reference").disabled = pending || references.length>=3; $("mc-upload").disabled = references.length>=3;
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
    waitingForCandidate={view,count:character.candidates.filter(c=>c.view===view).length};
    const result = await api(`/${character.character_id}/generate`,"POST",{view,
      ...(refine ? {candidate_id:preview,instructions:feedback.get(view)||"",item_ids:[...(suggestions.get(preview)||[])]} : {})});
    const latest=result.character.candidates.filter(c=>c.view===view).at(-1);
    preview = latest?.candidate_id || ""; iterationId=latest?.iteration_id || ""; show(result.character);
    changed("active_iteration_id",iterationId);
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
  $("mc-feedback").addEventListener("input",()=>feedback.set(view,$("mc-feedback").value));
  $("mc-new-name").addEventListener("input",nameMatch);
  $("mc-create-form").addEventListener("submit",event=>{event.preventDefault();act(async()=>{
    const result=await api("","POST",{name:$("mc-new-name").value}); const asset=entryAsset;
    await open(result.character.character_id);
    if(asset && !result.character.existing) await addReference({asset_id:asset.asset_id,caption:asset.label || "Identity reference"});
    entryAsset=null; if(result.character.existing) message("Opened the existing Minor Character.");
  });});
  $("mc-back").addEventListener("click",()=>act(list));
  $("mc-continue").addEventListener("click",()=>act(async()=>{entryAsset=null;await open($("mc-continue-choice").value);}));
  $("mc-generate").addEventListener("click",()=>act(()=>generateImage(false)));
  $("mc-refine").addEventListener("click",()=>act(()=>generateImage(true)));
  $("mc-select").addEventListener("click",()=>act(()=>selectCandidate()));
  $("mc-inspect").addEventListener("click",()=>inspect());
  $("mc-review-close").addEventListener("click",()=>$("mc-review").close());
  $("mc-review-prev").addEventListener("click",()=>navigateReview(-1));
  $("mc-review-next").addEventListener("click",()=>navigateReview(1));
  document.addEventListener("keydown",event=>{
    if ($("mc-review").open && ["ArrowLeft","ArrowRight"].includes(event.key) && !["INPUT","TEXTAREA","SELECT"].includes(event.target.tagName)) {
      event.preventDefault(); navigateReview(event.key==="ArrowLeft" ? -1 : 1);
    }
  });
  $("mc-lock").addEventListener("click",()=>act(async()=>{await flush();show((await api(`/${character.character_id}/lock`,"POST",{view})).character);message("Locked image saved to Inventory.");}));
  $("mc-open-locked").addEventListener("click",()=>act(async()=>{const id=character.locked[view].asset_id;await flush();await bridge.activatePage("auxiliary-resources");await bridge.openAsset(id);}));
  $("mc-analyze").addEventListener("click",()=>act(async()=>{await flush();show((await api(`/${character.character_id}/analyze`,"POST",{})).character);}));
  $("mc-add-reference").addEventListener("click",()=>act(()=>bridge.openLibraryPicker(asset=>act(()=>addReference({asset_id:asset.asset_id,caption:asset.label || "Identity reference"})))));
  $("mc-upload").addEventListener("change",()=>act(async()=>{await upload($("mc-upload").files[0]);$("mc-upload").value="";}));
  $("mc-paste").addEventListener("click",()=>$("mc-paste").focus());
  $("mc-paste").addEventListener("paste",event=>{const item=[...(event.clipboardData?.items||[])].find(i=>i.type.startsWith("image/"));if(item){event.preventDefault();act(()=>upload(item.getAsFile()));}});
  $("quick-character-wizard-open").addEventListener("click",()=>act(async()=>{route("");await bridge.activatePage("minor-characters");}));
  $("quick-character-wizard-from-asset").addEventListener("click",()=>act(fromInventory));
  window.zetMinorCharacters={load,flush,characterId:()=>character?.character_id || ""};
})();
