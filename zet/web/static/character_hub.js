(() => {
  const $ = (selector) => document.querySelector(selector);
  const state = {generation: 0, context: null, renaming: false, notice: null};
  function sameScope(a, b) { return a && b && a.character === b.character && a.phase === b.phase && a.universeId === b.universeId; }
  function renderStatus(context, fallback = `${context.character} · ${context.phase}`) {
    const notice = sameScope(state.notice?.context, context) ? state.notice : null;
    const status = $("#character-overview-status");
    status.textContent = notice?.message || fallback;
    status.className = notice ? `action-message ${notice.kind}` : "status-text";
  }
  function showNotice(context, message, kind = "info") {
    state.notice = {context, message, kind};
    if (sameScope(state.context, context)) renderStatus(context);
  }
  const baseImages = $("#character-base-images");
  const labels = {"body-reference":"Body-Reference", "head-image-edit":"Head-Image (Edit)", "character-assembly":"Character Assembly", "costume-dressing":"Costume-Dressing"};
  function prefKey() { const c=state.context; return `zet:character-hub:${c.universeId}:${c.character}:${c.phase}`; }
  function saveDisclosure(event) { if (!state.context) return; try { const p=JSON.parse(localStorage.getItem(prefKey())||"{}"); p[event.target.id]=event.target.open; localStorage.setItem(prefKey(),JSON.stringify(p)); } catch {} }
  function route(group, item) { const p=new URLSearchParams({page:"character-asset-container",character:state.context.character,phase:state.context.phase,universe_id:state.context.universeId,pipeline:group.pipeline,view:item.view}); if(group.costume)p.set("costume",group.costume); return `/?${p}`; }
  function imageRoute(group,item) { const p=new URLSearchParams({character:state.context.character,phase:state.context.phase,universe_id:state.context.universeId,view:item.view}); if(group.costume)p.set("costume",group.costume); return `/api/local/character-overview/image/${encodeURIComponent(group.pipeline)}?${p}`; }
  function renderGroup(group) {
    const images = group.views.filter(item => item.thumbnail_url).map(item => ({src: imageRoute(group, item), alt: `Locked ${item.view}`}));
    const section=document.createElement("section"); section.className="character-hub-group";
    const title=document.createElement("div"); title.className="character-hub-group-title";
    const h=document.createElement("h3"); h.textContent=group.label; title.append(h);
    if(group.pipeline==="costume-dressing") { const edit=document.createElement("button"); edit.textContent="Edit costume template"; edit.setAttribute("aria-label",`Edit costume template: ${group.label}`); edit.onclick=()=>window.ZetSourceEditor?.open({source_path:group.template_path,source_label:group.label,editable:true},()=>{}); title.append(edit); }
    section.append(title); const grid=document.createElement("div"); grid.className="character-hub-grid";
    for(const item of group.views) { const card=document.createElement("div"); card.className="character-hub-card"; const name=document.createElement("a"); name.href=route(group,item); name.textContent=item.view; name.setAttribute("aria-label",`Open ${group.label} ${item.view} workspace`); card.append(name); if(item.thumbnail_url){const button=document.createElement("button");button.type="button";button.className="character-hub-image-button";const img=document.createElement("img");img.src=item.thumbnail_url;img.alt=`Open locked ${item.view} full screen`;img.loading="lazy";button.append(img);button.onclick=()=>state.context.openImage?.(imageRoute(group,item),`Locked ${item.view}`,{images});card.append(button);}else{const empty=document.createElement("span");empty.textContent="No locked image";card.append(empty);} grid.append(card); }
    section.append(grid); return section;
  }
  async function activate(options) {
    const changed=!state.context||state.context.character!==options.character||state.context.phase!==options.phase||state.context.universeId!==options.universeId;
    state.context=options; const generation=++state.generation; if(!options.character||!options.phase)return;
    const key=prefKey(); let prefs={}; try{prefs=JSON.parse(localStorage.getItem(key)||"{}");}catch{}
    const setup=$("#character-setup-details"), costumes=$("#character-costumes-details");
    baseImages.open = prefs[baseImages.id] ?? false;
    if(changed){setup.open=true;costumes.open=true;}
    if(prefs[setup.id]!==undefined)setup.open=prefs[setup.id]; if(prefs[costumes.id]!==undefined)costumes.open=prefs[costumes.id];
    try { const data=await options.fetchJson(`/api/local/character-overview?character=${encodeURIComponent(options.character)}&phase=${encodeURIComponent(options.phase)}&universe_id=${encodeURIComponent(options.universeId)}`); if(generation!==state.generation)return;
      $("#character-setup-forms").hidden=data.ready; const editTemplate=$("#onboarding-edit-template"); editTemplate.hidden=!data.character_template_path; editTemplate.disabled=!data.character_template_path;
      editTemplate.onclick=(event)=>{event.preventDefault();event.stopPropagation();if(data.character_template_path)window.ZetSourceEditor?.open({source_path:data.character_template_path,source_label:`${data.character} / ${data.phase} - Character.md`,editable:true},()=>{});};
      setup.open=data.ready?(prefs[setup.id]??false):true;
      renderStatus(options, `${data.character} · ${data.phase}`);
      $("#character-base-groups").replaceChildren(...data.groups.filter(g=>g.pipeline!=="costume-dressing").map(renderGroup));
      $("#character-costume-groups").replaceChildren(...data.groups.filter(g=>g.pipeline==="costume-dressing").map(g=>{g.template_path=g.template_path||"";return renderGroup(g);}));
      return true;
    } catch(error){ if(generation===state.generation)renderStatus(options, error.message); return false; }
  }
  $("#character-setup-details").addEventListener("toggle",saveDisclosure); $("#character-costumes-details").addEventListener("toggle",saveDisclosure);
  baseImages.addEventListener("toggle",saveDisclosure);
  $("#character-overview-delete-phase").addEventListener("click",async()=>{
    if(!state.context)return;
    const c=state.context,button=$("#character-overview-delete-phase");button.disabled=true;
    try{const query=new URLSearchParams({character:c.character,phase:c.phase,universe_id:c.universeId});const result=await window.ZetConfirmedImageMutation(`/api/character-phase?${query}`,{method:"DELETE"},`Move ${c.character} / ${c.phase} and its assets to deleted storage?`);if(result){$("#character-overview-status").textContent=result.message||"Phase archived.";await c.refresh?.();}}
    catch(error){$("#character-overview-status").textContent=error.message;}finally{button.disabled=false;}
  });
  $("#character-overview-delete-character").addEventListener("click",async()=>{
    const c=state.context;if(!c||!window.confirm(`Move ${c.character} and every phase and asset to deleted storage?`))return;
    try{const snapshot=await c.fetchJson("/api/context"),phases=snapshot.phases_by_character?.[c.character]||[];const result=await window.ZetConfirmedImageMutation(`/api/character?character=${encodeURIComponent(c.character)}`,{method:"DELETE",headers:{"Content-Type":"application/json"},body:JSON.stringify({expected_phases:phases})},`Archive ${c.character} and all its phases?`);if(result){const url=new URL(location.href);url.searchParams.delete("character");url.searchParams.delete("phase");history.replaceState({},"",url);location.reload();}}
    catch(error){$("#character-overview-status").textContent=error.message;}
  });
  for(const [scope,id] of [["character","#character-overview-rename-character"],["phase","#character-overview-rename-phase"]]){
    $(id).addEventListener("click", async () => {
      const c = state.context;
      if (!c || state.renaming) return;
      const current = c[scope];
      const next = window.prompt(`Rename ${scope}`, current)?.trim();
      if (!next || next === current) return;
      state.renaming = true;
      const controls = [...document.querySelectorAll(
        '#character-select, #phase-select, #universe-select, [id^="character-overview-rename-"], [id^="character-overview-delete-"]'
      )].map(control => ({control, disabled: control.disabled}));
      controls.forEach(({control}) => { control.disabled = true; });
      const button = $(id), label = button.textContent;
      button.textContent = "Renaming…";
      button.setAttribute("aria-busy", "true");
      showNotice(c, `Renaming ${scope} "${current}" to "${next}". Updating files and saved references; please wait…`);
      let renamedContext = null;
      try {
        const result = await c.fetchJson("/api/local/character-overview/rename", {
          method: "POST", bindToPage: false,
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({character: c.character, phase: c.phase, new_name: next, scope}),
        });
        renamedContext = {...c, character: result.character, phase: result.phase};
        if (sameScope(state.context, c)) state.context = renamedContext;
        showNotice(renamedContext, "Rename saved. Refreshing character and phase selections…");
        const refreshed = await c.onRenamed(result, c);
        if (refreshed === false) throw new Error("The overview could not be refreshed.");
        showNotice(renamedContext, `${scope === "character" ? "Character" : "Phase"} renamed from "${current}" to "${result[scope]}". Rename complete.`, "success");
      } catch (error) {
        showNotice(renamedContext || c, renamedContext
          ? `Rename completed, but the dashboard could not refresh: ${error.message} Refresh the page to load the updated selections.`
          : `Could not confirm rename completion: ${error.message} Refresh the page to check the current name before trying again.`, "error");
      } finally {
        state.renaming = false;
        controls.forEach(({control, disabled}) => { control.disabled = disabled; });
        button.textContent = label;
        button.removeAttribute("aria-busy");
      }
    });
  }
  window.ZetCharacterHub={activate};
})();
