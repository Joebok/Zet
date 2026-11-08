(() => {
  const $ = (selector) => document.querySelector(selector);
  const state = {generation: 0, context: null};
  const baseImages = $("#character-base-images");
  const labels = {"body-reference":"Body-Reference", "head-image-edit":"Head-Image (Edit)", "head-image":"Head-Image (Construct)", "character-assembly":"Character Assembly", "costume-dressing":"Costume-Dressing"};
  function prefKey() { const c=state.context; return `zet:character-hub:${c.universeId}:${c.character}:${c.phase}`; }
  function saveDisclosure(event) { if (!state.context) return; try { const p=JSON.parse(localStorage.getItem(prefKey())||"{}"); p[event.target.id]=event.target.open; localStorage.setItem(prefKey(),JSON.stringify(p)); } catch {} }
  function route(group, item) { const p=new URLSearchParams({page:"character-asset-container",character:state.context.character,phase:state.context.phase,universe_id:state.context.universeId,pipeline:group.pipeline,view:item.view}); if(group.costume)p.set("costume",group.costume); return `/?${p}`; }
  function renderGroup(group) {
    const section=document.createElement("section"); section.className="character-hub-group";
    const title=document.createElement("div"); title.className="character-hub-group-title";
    const h=document.createElement("h3"); h.textContent=group.label; title.append(h);
    if(group.pipeline==="costume-dressing") { const edit=document.createElement("button"); edit.textContent="Edit costume template"; edit.onclick=()=>window.ZetSourceEditor?.open({source_path:group.template_path,source_label:group.label,editable:true},()=>{}); title.append(edit); }
    section.append(title); const grid=document.createElement("div"); grid.className="character-hub-grid";
    for(const item of group.views) { const a=document.createElement("a"); a.className="character-hub-card"; a.href=route(group,item); const name=document.createElement("strong"); name.textContent=item.view; a.append(name); if(item.thumbnail_url){const img=document.createElement("img");img.src=item.thumbnail_url;img.alt=`Locked ${item.view}`;img.loading="lazy";a.append(img);}else{const empty=document.createElement("span");empty.textContent="No locked image";a.append(empty);} grid.append(a); }
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
      $("#character-setup-forms").hidden=data.ready; $("#onboarding-edit-template").hidden=!data.ready||!data.character_template_path;
      setup.open=data.ready?(prefs[setup.id]??false):true;
      $("#character-overview-status").textContent=`${data.character} · ${data.phase}`;
      $("#character-base-groups").replaceChildren(...data.groups.filter(g=>g.pipeline!=="costume-dressing").map(renderGroup));
      $("#character-costume-groups").replaceChildren(...data.groups.filter(g=>g.pipeline==="costume-dressing").map(g=>{g.template_path=g.template_path||"";return renderGroup(g);}));
    } catch(error){ if(generation===state.generation)$("#character-overview-status").textContent=error.message; }
  }
  $("#character-setup-details").addEventListener("toggle",saveDisclosure); $("#character-costumes-details").addEventListener("toggle",saveDisclosure);
  baseImages.addEventListener("toggle",saveDisclosure);
  window.ZetCharacterHub={activate};
})();
