const root = document.querySelector('#narrative-root');
const message = document.querySelector('#narrative-message');
const params = new URLSearchParams(location.search);
let universe = params.get('universe_id') || '';
let route = {};
let detail = null;
let dirty = new Set();
let saveTimer = null;
let saveChain = Promise.resolve();
let busy = false;
let pollBusy = false;
let slotSignature = '';
let elementDraft = null;
let modelOptions = {model:'general:latest', codex_models:[]};
let knownModels = [];
let historySignature = '';
let interviewReplies = 0;
let llmSubmitting = false;
let layerDrag = null;
let brush = null;
let reviewCandidate = null;
let sourcePicker = null;
const active = new Set(['SUBMITTING', 'QUEUED', 'RUNNING', 'DISPATCHING']);
const visualFields = ['setting', 'camera', 'perspective', 'lighting', 'style'];
const targetFields = ['title', 'narrative', 'staging', 'physical_context', 'framing', 'width', 'height', 'prompt', 'interview_model', 'prompt_model', 'assembly_mode'];
const assemblyModeName = mode => mode === 'assemble_references' ? 'Assemble from references' : 'Finish placed composite';
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const title = key => key.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());
const label = (key, value, textarea = true, name = title(key)) => `<label class="narrative-field">${esc(name)}${textarea
  ? `<textarea data-field="${key}" id="narrative-${key}">${esc(value)}</textarea>`
  : `<input data-field="${key}" id="narrative-${key}" ${['width','height'].includes(key) ? 'type="number" step="32" min="256" max="4096"' : ''} value="${esc(value)}">`}</label>`;

function status(text, error = false) { message.textContent = text; message.classList.toggle('error', error); }
function href(next) {
  const query = new URLSearchParams({universe_id: universe});
  for (const [key, value] of Object.entries(next)) if (value) query.set(key, value);
  return `/narrative?${query}`;
}
function link(text, next) { return `<a href="${esc(href(next))}" data-navigate>${esc(text)}</a>`; }
function base() {
  let value = `/api/narrative/stories/${route.story}`;
  if (route.scene) value += `/scenes/${route.scene}`;
  if (route.target) value += `/targets/${route.target}`;
  return value;
}
function imageUrl(id, target = route.target) {
  return `/api/narrative/stories/${route.story}/scenes/${route.scene}/targets/${target}/candidates/${id}/image?universe_id=${encodeURIComponent(universe)}`;
}
function assetUrl(id) { return `/api/narrative/library/${encodeURIComponent(id)}/image?universe_id=${encodeURIComponent(universe)}`; }
function artifactUrl(suffix) { return `${base()}/${suffix}?universe_id=${encodeURIComponent(universe)}`; }
function modelName(provenance) { return provenance?.model || 'Model not recorded'; }
function copyPromptButton(id) {
  return `<button type="button" class="narrative-copy-prompt" data-copy-prompt="${id}" aria-label="Copy prompt to clipboard" title="Copy prompt to clipboard" ${detail.candidates[id].prompt ? '' : 'disabled'}>⧉</button>`;
}
function layerUrl(layer,kind='cutout') {
  let revision=0;
  for (const char of JSON.stringify([layer.candidate_id,layer.cutout,layer.tolerance,layer.strokes])) revision=(revision*31+char.charCodeAt(0))>>>0;
  return artifactUrl(`layers/${layer.id}/image`)+`&kind=${kind}&revision=${revision}`;
}

function modelControl(key) {
  return `<label class="narrative-field">${title(key)}<input data-field="${key}" id="narrative-${key}" list="narrative-model-options" value="${esc(detail[key])}" placeholder="Default: ${esc(modelOptions.model)}"></label>`;
}
async function loadModels() {
  const url = base();
  try {
    const result = await api('/api/ai-controls/ollama-models');
    if (base() !== url) return;
    knownModels = result.models || [];
    const errorNode = document.querySelector('#narrative-model-error');
    if (errorNode) errorNode.textContent = '';
  } catch (error) { const errorNode = document.querySelector('#narrative-model-error'); if (base() === url && errorNode) errorNode.textContent = error.message; }
  const list = document.querySelector('#narrative-model-options');
  if (list) list.innerHTML = [...new Set([modelOptions.model,...knownModels,...modelOptions.codex_models,detail.interview_model,detail.prompt_model])].filter(Boolean).map(name=>`<option value="${esc(name)}"></option>`).join('');
}

async function api(url, method = 'GET', data) {
  const response = await fetch(url, {method, headers: {'Content-Type':'application/json', 'x-zet-universe':universe},
    ...(data !== undefined ? {body: JSON.stringify(data)} : {})});
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 409 && result.detail?.protected_images) {
      const images = result.detail.protected_images;
      if (!confirm(`Delete these selected or locked images?\n\n${images.map(image => image.label).join('\n')}`)) return null;
      return api(url, method, {...data, confirm_ids: images.map(image => image.id)});
    }
    throw new Error(typeof result.detail === 'string' ? result.detail : JSON.stringify(result.detail || result));
  }
  return result;
}

async function action(callback) {
  if (busy) return;
  busy = true;
  let actionError = '';
  renderImageReview();
  root.querySelectorAll('button, #narrative-target-select').forEach(control => { control.disabled = true; });
  try { await callback(); } catch (error) { actionError = error.message; status(error.message, true); }
  finally {
    busy = false; root.querySelectorAll('button, #narrative-target-select').forEach(control => { control.disabled = false; }); if (route.target && detail) updateLive(); renderImageReview();
    const reviewError = document.querySelector('#narrative-review-error');
    if (reviewError) reviewError.textContent = actionError;
  }
}

async function navigate(next, push = true) {
  await save();
  const url = typeof next === 'string' ? next : href(next);
  if (push) history.pushState({}, '', url);
  await loadPage();
}

async function loadPage() {
  document.querySelector('#image-dialog').close();
  reviewCandidate = null;
  clearTimeout(saveTimer);
  const query = new URLSearchParams(location.search);
  route = {story:query.get('story'), scene:query.get('scene'), target:query.get('target')};
  dirty = new Set(); slotSignature = ''; historySignature = ''; interviewReplies = 0;
  document.querySelector('#narrative-home').href = href({});
  status('Loading…');
  if (!route.story) {
    detail = null;
    const stories = await api('/api/narrative/stories');
    root.innerHTML = `<div class="narrative-stories-heading"><h1>Narrative Scenes</h1><button id="new-story-button" class="primary">New Story</button></div>
      <div class="narrative-grid">${stories.map(story => `<article class="narrative-card"><h2>${link(story.title, {story:story.id})}</h2><p>${esc(story.brief)}</p>
        <div class="narrative-story-scenes">${story.scenes.map(scene => {
          const assembly = scene.final_assembly;
          const destination = {story:story.id,scene:scene.id,...(assembly ? {target:assembly.target_id} : {})};
          const image = assembly ? `/api/narrative/stories/${story.id}/scenes/${scene.id}/targets/${assembly.target_id}/candidates/${assembly.candidate_id}/image?universe_id=${encodeURIComponent(universe)}` : '';
          return `<a class="narrative-story-scene" href="${esc(href(destination))}" data-navigate>
            ${assembly ? `<img class="narrative-story-thumbnail" src="${esc(image)}" alt="Selected final assembly for ${esc(scene.title)}" loading="lazy">` : `<span class="narrative-story-thumbnail narrative-story-placeholder" role="img" aria-label="No selected final assembly for ${esc(scene.title)}"></span>`}
            <span>${esc(scene.title)}</span></a>`;
        }).join('')}</div></article>`).join('')}</div>`;
    document.querySelector('#narrative-breadcrumb').textContent = 'New narrative workflow';
  } else if (!route.scene) {
    detail = await api(base());
    root.innerHTML = `<h1>${esc(detail.title)}</h1><section class="narrative-card">${label('title',detail.title,false)}${label('brief',detail.brief)}
      <div class="narrative-actions"><button data-action="save">Save story</button><button class="danger" data-action="delete">Delete story</button></div></section>
      <section class="narrative-card"><h2>New scene</h2><form id="new-scene" class="narrative-inline"><input aria-label="Scene title" name="title" required placeholder="Scene title"><button class="primary">Create scene</button></form></section>
      <div class="narrative-grid">${detail.scenes.map(scene => `<article class="narrative-card"><h2>${link(scene.title,{story:route.story,scene:scene.id})}</h2><p>${esc(scene.intent)}</p></article>`).join('')}</div>`;
    document.querySelector('#narrative-breadcrumb').innerHTML = link('Stories',{});
  } else if (!route.target) {
    const [loaded, story] = await Promise.all([api(base()), api(`/api/narrative/stories/${route.story}`)]);
    detail = loaded;
    root.innerHTML = `<h1>${esc(detail.title)}</h1><div class="narrative-editor"><section class="narrative-card"><h2>Shared scene direction</h2>
      ${label('title',detail.title,false)}${label('intent',detail.intent)}${visualFields.map(key=>label(key,detail[key])).join('')}${label('canvas',detail.canvas,false)}
      <div class="narrative-actions"><button data-action="save">Save scene</button><button class="danger" data-action="delete">Delete scene</button></div></section><div>
      <section class="narrative-card"><h2>Subscenes and backdrops</h2><form id="new-target" class="narrative-inline">
        <input aria-label="Target title" name="title" required placeholder="Title"><select name="kind" aria-label="Target kind"><option value="subscene">Subscene</option><option value="backdrop">Backdrop</option></select><button class="primary">Create and edit</button></form>
        ${detail.targets.some(target=>target.kind==='assembly') ? '' : '<button data-action="create-assembly">Create final assembly</button>'}
        <div class="narrative-actions"><button data-action="reference-backdrop">Reference backdrop from another scene</button><button data-action="import-subscene">Import subscene from another scene</button></div>
        ${detail.targets.map(target=>`<article class="narrative-card narrative-target-card" data-target-id="${target.id}"><h3>${link(target.title,{...route,target:target.id})}</h3><p class="narrative-muted">${esc(target.kind)}${target.selected_id ? ' · Image selected' : ''}</p>
          ${target.selected_id ? `<a href="${esc(href({...route,target:target.id}))}" data-navigate><img class="narrative-target-preview" src="${esc(imageUrl(target.selected_id,target.id))}" alt="Selected image for ${esc(target.title)}"></a>` : ''}</article>`).join('')}</section>
      <section class="narrative-card"><h2>Scene elements</h2><button data-action="new-element">Add element</button><div id="narrative-elements">${elementsHtml(detail.elements,false)}</div></section></div></div>`;
    document.querySelector('#narrative-breadcrumb').innerHTML = link('Stories',{})+' / '+link(story.title,{story:route.story});
  } else {
    const [loaded, targets, story] = await Promise.all([api(base()), api(`/api/narrative/stories/${route.story}/scenes/${route.scene}/targets`), api(`/api/narrative/stories/${route.story}`)]);
    detail = loaded;
    renderTarget(targets);
    document.querySelector('#narrative-breadcrumb').innerHTML = link('Stories',{})+' / '+link(story.title,{story:route.story})+' / '+link(detail.scene_title,{story:route.story,scene:route.scene})+' / '+esc(detail.title);
  }
  document.body.dataset.narrativeReady = 'true';
  status('Ready');
}

function elementsHtml(elements, target) {
  return elements.map(element=>`<article class="narrative-reference">
    ${element.asset_id ? `<img src="${esc(assetUrl(element.asset_id))}" alt="${esc(element.name)} reference">` : ''}
    <div><h3>${esc(element.name)}</h3><p class="narrative-muted">${esc(element.kind)} · ${esc(element.reference_role)}</p><p>${esc(element.appearance)}</p>
      ${element.reference_error ? `<p class="error">${esc(element.reference_error)}</p>` : ''}
      <div class="narrative-actions"><button data-edit-element="${element.id}">Edit</button>
      <button data-${target ? 'remove' : 'delete'}-element="${element.id}">${target ? 'Remove from subscene' : 'Delete element'}</button></div></div></article>`).join('') || '<p class="narrative-muted">No elements assigned.</p>';
}

function assemblyHtml() {
  return `<section class="narrative-card"><h2>Sources and placement</h2><label class="narrative-field">Add source<select id="assembly-source">${detail.assembly_sources.map(source=>`<option value="${source.id}">${esc(source.title)} · ${source.kind}</option>`).join('')}</select></label>
    <button data-action="add-layer">Add selected image</button><p class="narrative-muted">Choose a completed image below if the source has no selection. Drag groups on the preview; use the corner handle to resize.</p>
    <div id="assembly-layers"></div><div id="assembly-canvas" style="aspect-ratio:${detail.width}/${detail.height}"></div>
    <div class="narrative-actions"><button data-action="preview-composite">Refresh raw composite</button><button id="assembly-download" data-action="download-composite">Download raw composite</button></div>
    <img id="assembly-raw" alt="Raw composite preview" hidden></section>`;
}

function layerField(layer, key, labelText, step = '.01') {
  return `<label>${labelText}<input type="number" step="${step}" data-layer="${layer.id}" data-layer-field="${key}" value="${layer[key]}"></label>`;
}

function renderLayers() {
  const container = document.querySelector('#assembly-layers');
  if (!container) return;
  container.innerHTML = detail.layers.map(layer=>{
    const source = detail.assembly_sources.find(item=>item.id===layer.target_id);
    const options = source?.candidates || [];
    return `<article class="narrative-layer"><h3>${esc(layer.label)}</h3><img class="narrative-layer-thumb" src="${esc(layerUrl(layer))}" alt="${esc(layer.label)} cutout">
      <label>Candidate<select data-layer="${layer.id}" data-layer-field="candidate_id">${options.some(candidate=>candidate.id===layer.candidate_id) ? '' : `<option value="${layer.candidate_id}">Pinned image</option>`}${options.map(candidate=>`<option value="${candidate.id}" ${candidate.id===layer.candidate_id ? 'selected' : ''}>Slot ${candidate.slot}</option>`).join('')}</select></label>
      <button data-current-selection="${layer.id}">Use current selection</button>
      <div class="narrative-layer-controls"><label>Role<select data-layer="${layer.id}" data-layer-field="role"><option value="group" ${layer.role==='group'?'selected':''}>Group</option>${layer.source_kind==='backdrop'?`<option value="base" ${layer.role==='base'?'selected':''}>Base backdrop</option>`:''}</select></label>
      <label><input type="checkbox" data-layer="${layer.id}" data-layer-field="visible" ${layer.visible?'checked':''}> Visible</label>
      ${layer.role==='base' ? `<label>Backdrop fit<select data-layer="${layer.id}" data-layer-field="fit">${['cover','contain'].map(value=>`<option ${value===layer.fit?'selected':''}>${value}</option>`).join('')}</select></label>` : `
      ${layerField(layer,'x','X')}${layerField(layer,'y','Y')}${layerField(layer,'scale','Width / canvas')}${layerField(layer,'z','Depth','1')}
      <label>Cutout<select data-layer="${layer.id}" data-layer-field="cutout">${['auto','alpha','opaque'].map(value=>`<option ${value===layer.cutout?'selected':''}>${value}</option>`).join('')}</select></label>${layerField(layer,'tolerance','Background tolerance','1')}`}</div>
      <div class="narrative-actions">${layer.role==='group' ? `<button data-mask-layer="${layer.id}">Keep / remove corrections</button>` : ''}<button data-remove-layer="${layer.id}">Remove layer</button></div></article>`;
  }).join('');
  renderPlacement();
}

function renderPlacement() {
  const canvas = document.querySelector('#assembly-canvas');
  if (!canvas) return;
  canvas.style.aspectRatio = `${detail.width}/${detail.height}`;
  canvas.innerHTML = detail.layers.filter(layer=>layer.visible).sort((a,b)=>a.role==='base'?-1:b.role==='base'?1:a.z-b.z).map(layer=>layer.role==='base'
    ? `<img class="assembly-base" src="${esc(layerUrl(layer,'source'))}" style="object-fit:${layer.fit}" alt="${esc(layer.label)} backdrop">`
    : `<div class="assembly-placement" data-drag-layer="${layer.id}" style="left:${layer.x*100}%;top:${layer.y*100}%;width:${layer.scale*100}%"><img draggable="false" src="${esc(layerUrl(layer))}" alt="${esc(layer.label)} placed group"><span class="assembly-resize" data-resize-layer="${layer.id}" aria-label="Resize ${esc(layer.label)}"></span></div>`).join('');
}

function layersChanged() {
  dirty.add('layers'); status('Saving changes…'); clearTimeout(saveTimer);
  saveTimer = setTimeout(()=>save().catch(error=>status(error.message,true)),700);
}

async function editMask(layerId) {
  await save();
  const dialog = document.querySelector('#membership-dialog');
  dialog.innerHTML = `<h2>Correct source cutout</h2><p>Paint over the original source. Green keeps pixels; red removes them.</p><div class="narrative-inline"><label>Brush<select id="mask-mode"><option value="keep">Keep</option><option value="remove">Remove</option></select></label><label>Radius<input id="mask-radius" type="number" value="0.02" min="0.001" max="0.5" step="0.005"></label></div><canvas id="mask-canvas" data-mask-source="${layerId}"></canvas><div class="narrative-actions"><button id="mask-apply">Save corrections</button><button id="mask-reset">Reset corrections</button><button data-close="membership-dialog">Close</button></div>`;
  dialog.showModal();
  await drawMask(layerId);
}

async function drawMask(layerId) {
  const canvas = document.querySelector('#mask-canvas');
  const image = new Image();
  image.src = artifactUrl(`layers/${layerId}/image`)+'&kind=overlay&revision='+Date.now();
  image.onerror = ()=>{ image.onerror=null; image.src=artifactUrl(`layers/${layerId}/image`)+'&kind=source'; };
  await new Promise(resolve=>{image.onload=resolve;});
  canvas.width=image.naturalWidth; canvas.height=image.naturalHeight;
  canvas.getContext('2d').drawImage(image,0,0);
}

function paintMask(event) {
  const canvas = event.target;
  const layer = detail.layers.find(item=>item.id===canvas.dataset.maskSource);
  const rect = canvas.getBoundingClientRect();
  const stroke = {mode:document.querySelector('#mask-mode').value, radius:Number(document.querySelector('#mask-radius').value),
    x:Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),y:Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))};
  if (!Number.isFinite(stroke.radius)||stroke.radius<.001||stroke.radius>.5) return;
  layer.strokes.push(stroke);
  const context=canvas.getContext('2d'); context.fillStyle=stroke.mode==='keep'?'rgba(25,185,80,.5)':'rgba(220,40,60,.5)';
  context.beginPath();context.arc(stroke.x*canvas.width,stroke.y*canvas.height,stroke.radius*Math.max(canvas.width,canvas.height),0,Math.PI*2);context.fill();
  layersChanged();
}

document.addEventListener('pointerdown',event=>{
  if (event.target.matches('#mask-canvas')) {brush=event.pointerId;event.target.setPointerCapture(event.pointerId);paintMask(event);return;}
  const node=event.target.closest('[data-drag-layer]');
  if (!node) return;
  const layer=detail.layers.find(item=>item.id===node.dataset.dragLayer);
  layerDrag={node,layer,px:event.clientX,py:event.clientY,x:layer.x,y:layer.y,scale:layer.scale,resize:Boolean(event.target.dataset.resizeLayer),pointer:event.pointerId};
  node.setPointerCapture(event.pointerId);event.preventDefault();
});
document.addEventListener('pointermove',event=>{
  if (brush===event.pointerId && event.target.matches('#mask-canvas')) {paintMask(event);return;}
  if (!layerDrag || layerDrag.pointer!==event.pointerId) return;
  const drag=layerDrag, rect=document.querySelector('#assembly-canvas').getBoundingClientRect();
  if (drag.resize) drag.layer.scale=Math.max(.01,Math.min(4,drag.scale+(event.clientX-drag.px)/rect.width));
  else {drag.layer.x=Math.max(-2,Math.min(2,drag.x+(event.clientX-drag.px)/rect.width));drag.layer.y=Math.max(-2,Math.min(2,drag.y+(event.clientY-drag.py)/rect.height));}
  for (const key of ['x','y','scale']) drag.layer[key]=Math.round(drag.layer[key]*10000)/10000;
  drag.node.style.left=`${drag.layer.x*100}%`;drag.node.style.top=`${drag.layer.y*100}%`;drag.node.style.width=`${drag.layer.scale*100}%`;
  for(const key of ['x','y','scale']) {const input=root.querySelector(`[data-layer="${drag.layer.id}"][data-layer-field="${key}"]`);input.value=drag.layer[key];}
  layersChanged();
});
document.addEventListener('pointerup',event=>{if (brush===event.pointerId) brush=null;if(layerDrag?.pointer===event.pointerId) layerDrag=null;});
document.addEventListener('pointercancel',()=>{brush=null;layerDrag=null;});

function sourceTextHtml(source) {
  return `<details><summary>Source inputs and prompt</summary>
    <h3>Generation inputs</h3><pre>${esc(source.generation_inputs ? JSON.stringify(source.generation_inputs,null,2) : 'Generation inputs not recorded')}</pre>
    <h3>Exact source prompt</h3><pre>${esc(source.prompt || 'Prompt not recorded')}</pre>
    <h3>Current source authoring text</h3><pre>${esc(JSON.stringify(source.current_inputs,null,2))}</pre></details>`;
}

function sourcePanelHtml() {
  if (detail.kind === 'assembly') return '';
  const source = detail.source_snapshot;
  const backdrop = detail.kind === 'backdrop';
  const settings = detail.backdrop_adaptation || {};
  const crop = settings.crop || {};
  if (!backdrop && !source?.target_id) return '';
  return `<section class="narrative-card" id="narrative-source-panel"><h2>${backdrop ? 'Backdrop source and adaptation' : 'Imported subscene source'}</h2>
    ${backdrop ? '<button data-action="attach-backdrop">Attach source backdrop</button>' : ''}
    ${source?.target_id ? `<p>Pinned from ${esc(source.story_title)} / ${link(source.scene_title,{story:source.story_id,scene:source.scene_id,target:source.target_id})} · ${esc(source.title)}</p>
      ${sourceTextHtml(source)}${backdrop ? `<div class="narrative-actions"><button data-action="refresh-backdrop">Use current source selection</button><button data-action="copy-source-current">Copy current source inputs</button>${source.generation_inputs ? '<button data-action="copy-source-generation">Copy generation inputs</button>' : ''}</div>
      <p class="narrative-muted">Copies the recorded source inputs into this backdrop. Refresh replaces only the pinned source; existing images and destination edits remain.</p>
      <label class="narrative-field">Backdrop operation<select id="backdrop-operation" data-adaptation="operation">${[['edit','Other edits'],['unchanged','Use unchanged'],['crop','Crop'],['expand','Expand'],['viewpoint','Change viewpoint']].map(([value,name])=>`<option value="${value}" ${(settings.operation||'edit')===value?'selected':''}>${name}</option>`).join('')}</select></label>
      <label class="narrative-field">Adaptation direction<textarea id="backdrop-direction" data-adaptation="direction" placeholder="Describe the new view or what to add">${esc(settings.direction||'')}</textarea></label>
      <label class="narrative-field">Expand toward<select data-adaptation="expand_side" id="backdrop-expand-side">${['left','right','top','bottom','all'].map(side=>`<option ${(settings.expand_side||'right')===side?'selected':''}>${side}</option>`).join('')}</select></label>
      <p class="narrative-muted">Use Width and Height above for the output dimensions. Expansion and changed viewpoints use generation and can reinterpret detail.</p>
      <div class="narrative-crop-stage" id="backdrop-crop-stage"><img id="backdrop-source-image" src="${esc(artifactUrl('source-image'))}&revision=${esc(source.snapshot_id)}" alt="Pinned source backdrop"><div id="backdrop-crop-box"></div></div>
      <div class="narrative-grid">${[['center_x','Horizontal crop center',0,1,.01,.5],['center_y','Vertical crop center',0,1,.01,.5],['zoom','Crop zoom',1,20,.1,1]].map(([key,name,min,max,step,value])=>`<label class="narrative-field">${name}<input type="range" id="backdrop-crop-${key}" data-crop="${key}" min="${min}" max="${max}" step="${step}" value="${crop[key]??value}"></label>`).join('')}</div>
      <div class="narrative-actions"><button data-action="reuse-backdrop">Use unchanged image</button><button data-action="crop-backdrop">Create cropped image</button><button data-action="preview-crop">Preview crop</button></div>
      <img id="backdrop-crop-preview" class="narrative-source-preview" hidden alt="Crop output preview">
      <p class="narrative-muted">Unchanged reuse and cropping create local candidates without generation. Use the interview and prompt controls below to generate an adaptation.</p>` : ''}` : '<p>No source attached.</p>'}</section>`;
}

function drawCropBox() {
  const image = document.querySelector('#backdrop-source-image');
  const box = document.querySelector('#backdrop-crop-box');
  if (!image?.naturalWidth || !box) return;
  const ratio = Number(document.querySelector('#narrative-width').value) / Number(document.querySelector('#narrative-height').value);
  const imageRatio = image.naturalWidth / image.naturalHeight;
  const zoom = Number(document.querySelector('#backdrop-crop-zoom').value);
  const width = Math.min(1,ratio/imageRatio)/zoom;
  const height = width*imageRatio/ratio;
  const x = Math.min(1-width/2,Math.max(width/2,Number(document.querySelector('#backdrop-crop-center_x').value)));
  const y = Math.min(1-height/2,Math.max(height/2,Number(document.querySelector('#backdrop-crop-center_y').value)));
  Object.assign(box.style,{left:`${(x-width/2)*100}%`,top:`${(y-height/2)*100}%`,width:`${width*100}%`,height:`${height*100}%`});
}

async function chooseNarrativeSource(kind, attach = false) {
  await save();
  const sources = await api('/api/narrative/sources?kind='+kind);
  const destination = await api(`/api/narrative/stories/${route.story}/scenes/${route.scene}`);
  sourcePicker = {kind,attach,sources:sources.filter(source=>source.scene_id!==route.scene || source.story_id!==route.story),elements:destination.elements};
  const stories = [...new Map(sourcePicker.sources.map(source=>[source.story_id,source.story_title])).entries()];
  const dialog = document.querySelector('#narrative-source-dialog');
  dialog.innerHTML = `<h2>${kind==='backdrop'?'Reference backdrop':'Import subscene'}</h2><form id="narrative-source-form">
    <label class="narrative-field">Source story<select id="source-story">${stories.map(([id,name])=>`<option value="${id}" ${id===route.story?'selected':''}>${esc(name)}</option>`).join('')}</select></label>
    <label class="narrative-field">Source scene and target<select id="source-target"></select></label>
    <label class="narrative-field">Source candidate<select id="source-candidate"></select></label>
    <div id="source-preview"></div><p class="error" id="source-picker-error" role="status"></p>
    ${attach ? '' : '<label class="narrative-field">New target title<input id="source-title" required></label><label><input id="source-copy-context" type="checkbox"> Copy source visual context as local overrides</label>'}
    <div class="narrative-actions"><button class="primary" id="source-apply">${attach?'Attach pinned source':kind==='backdrop'?'Create referenced backdrop':'Import subscene'}</button><button type="button" data-close="narrative-source-dialog">Cancel</button></div></form>`;
  dialog.showModal();
  await populateSourceTargets();
}

async function populateSourceTargets() {
  const story = document.querySelector('#source-story').value;
  const targets = sourcePicker.sources.filter(source=>source.story_id===story);
  document.querySelector('#source-target').innerHTML = targets.map(source=>`<option value="${source.target_id}">${esc(source.scene_title)} · ${esc(source.title)}</option>`).join('');
  await populateSourceCandidates();
}

function chosenSource() {
  const source = sourcePicker.sources.find(source=>source.target_id===document.querySelector('#source-target').value);
  return source ? {story_id:source.story_id,scene_id:source.scene_id,target_id:source.target_id,candidate_id:document.querySelector('#source-candidate').value || null} : null;
}

async function populateSourceCandidates() {
  const source = sourcePicker.sources.find(source=>source.target_id===document.querySelector('#source-target').value);
  document.querySelector('#source-candidate').innerHTML = '<option value="">'+(sourcePicker.kind==='subscene'?'Text only / no image needed':'Choose a completed candidate')+'</option>'+(source?.candidates||[]).map(candidate=>`<option value="${candidate.id}" ${candidate.id===source.selected_id?'selected':''}>Slot ${candidate.slot}${candidate.id===source.selected_id?' · Selected':''}</option>`).join('');
  await previewNarrativeSource();
}

async function previewNarrativeSource() {
  const choice = chosenSource();
  const picker = sourcePicker;
  picker.preview = null;
  document.querySelector('#source-preview').innerHTML = '';
  document.querySelector('#source-picker-error').textContent = '';
  document.querySelector('#source-apply').disabled = true;
  if (!choice) {document.querySelector('#source-picker-error').textContent='No sources in another scene.';return;}
  if (picker.kind==='backdrop' && !choice.candidate_id) {document.querySelector('#source-picker-error').textContent='Choose a completed source candidate.';return;}
  const request = JSON.stringify(choice);
  const preview = await api('/api/narrative/sources/preview','POST',choice);
  if (sourcePicker!==picker || request!==JSON.stringify(chosenSource())) return;
  picker.preview = preview;
  document.querySelector('#source-preview').innerHTML = `${preview.candidate_id ? `<img class="narrative-source-preview" alt="Source candidate preview" src="/api/narrative/stories/${choice.story_id}/scenes/${choice.scene_id}/targets/${choice.target_id}/candidates/${preview.candidate_id}/image?universe_id=${encodeURIComponent(universe)}">` : ''}${sourceTextHtml(preview)}
    ${picker.kind==='subscene' ? `<h3>Imported elements</h3>${preview.current_inputs.elements.map(element=>`<label class="narrative-field">${esc(element.name)}<select data-source-element="${element.id}"><option value="">Create independent local copy</option>${picker.elements.map(local=>`<option value="${local.id}">Use existing: ${esc(local.name)}</option>`).join('')}</select></label>`).join('')}` : ''}`;
  const name = document.querySelector('#source-title');
  if (name) name.value = preview.title;
  document.querySelector('#source-apply').disabled = false;
}

function adaptationChanged() {
  detail.backdrop_adaptation = {operation:document.querySelector('#backdrop-operation').value,
    direction:document.querySelector('#backdrop-direction').value,expand_side:document.querySelector('#backdrop-expand-side').value,
    crop:Object.fromEntries(['center_x','center_y','zoom'].map(key=>[key,Number(document.querySelector(`#backdrop-crop-${key}`).value)]))};
  dirty.add('backdrop_adaptation');
  clearTimeout(saveTimer);saveTimer=setTimeout(()=>save().catch(error=>status(error.message,true)),700);
  drawCropBox();
}

function renderTarget(targets) {
  const backdrop = detail.kind === 'backdrop';
  const assembly = detail.kind === 'assembly';
  root.innerHTML = `<h1 class="narrative-target-heading"><select id="narrative-target-select" aria-label="Scene page">${targets.map(target=>`<option value="${target.id}" ${target.id === route.target ? 'selected' : ''}>${esc(target.title)} · ${title(target.kind)}</option>`).join('')}</select></h1>
    <div class="narrative-editor"><div><section class="narrative-card"><h2>${backdrop ? 'Environment direction' : 'The moment'}</h2>
      ${label('title',detail.title,false)}${label('narrative',detail.narrative,true,backdrop ? 'Describe the environment' : 'Describe what is happening')}
      ${label('staging',detail.staging,true,backdrop ? 'Environment composition' : 'Interaction and staging')}${label('physical_context',detail.physical_context)}
      ${label('framing',detail.framing,false)}<div class="narrative-grid">${label('width',detail.width,false)}${label('height',detail.height,false)}</div>
      <div class="narrative-actions"><button data-action="save">Save inputs</button><button class="danger" data-action="delete">Delete ${assembly ? 'assembly' : backdrop ? 'backdrop' : 'subscene'}</button></div></section>
    ${sourcePanelHtml()}
    ${assembly ? assemblyHtml() : `<section class="narrative-card"><h2>Participants and references</h2><div id="narrative-elements">${elementsHtml(detail.elements,true)}</div>
      <div class="narrative-actions"><button data-action="assign-elements">Assign scene elements</button><button data-action="new-element">New element / library reference</button></div></section>`}
    <section class="narrative-card"><h2>Shared visual context</h2><dl class="narrative-context">${visualFields.map(key=>`<dt>${title(key)}</dt><dd>${esc(detail.inherited_context[key] || 'Not specified')}</dd>`).join('')}</dl>
      <details><summary>Local overrides</summary>${visualFields.map(key=>label(`override_${key}`,detail.visual_overrides[key] || '',true,`${title(key)} override (blank inherits)`)).join('')}</details></section>
    <section class="narrative-card"><h2>Interview</h2>${modelControl('interview_model')}<p class="narrative-muted" id="narrative-interview-effective"></p><p id="narrative-interview-status" role="status" aria-live="polite"></p><div id="narrative-interview" class="narrative-history"></div>
      <label class="narrative-field">Answer or direct a revision<textarea id="narrative-direction" placeholder="Describe what is happening, answer a question, or ask for a change."></textarea></label>
      <div class="narrative-actions"><button class="primary" data-action="interview">Continue interview</button><button data-action="rerun_interview">Re-run last interview</button></div><p class="narrative-muted">Answers are optional. Edit directly or generate whenever you are ready.</p></section></div>
    <div><section class="narrative-card"><h2>Prompt and generation</h2>${assembly ? `<label class="narrative-field">Assembly mode<select id="narrative-assembly_mode" data-field="assembly_mode"><option value="finish_composite" ${detail.assembly_mode==='finish_composite'?'selected':''}>Finish placed composite</option><option value="assemble_references" ${detail.assembly_mode==='assemble_references'?'selected':''}>Assemble from references</option></select></label><p id="narrative-assembly-help" class="narrative-muted"></p><p id="narrative-assembly-prompt-warning" class="error" role="status"></p>` : ''}${modelControl('prompt_model')}<p class="narrative-muted" id="narrative-prompt-effective"></p>
      <datalist id="narrative-model-options"></datalist><p id="narrative-model-error" class="error"></p>
      ${label('prompt',detail.prompt,true,'Final Qwen prompt')}<p id="narrative-prompt-origin" class="narrative-muted"></p>
      <details><summary>Previous prompt outputs</summary><select id="narrative-prompt-history" aria-label="Previous prompt outputs"></select><pre id="narrative-prompt-preview"></pre><button data-action="use-prompt">Use this prompt</button></details>
      <div class="narrative-actions"><button data-action="synthesize">Write prompt</button><button data-action="rerun_prompt">Re-run last prompt</button><button class="primary" data-action="generate" data-count="1">Generate 1 from inputs</button><button class="primary" data-action="generate" data-count="4">Generate 4 from inputs</button></div>
      <div class="narrative-actions"><button data-action="render" data-count="1">Render edited prompt · 1</button><button data-action="render" data-count="4">Render edited prompt · 4</button><button data-action="refresh">Refresh</button></div>
      <p class="narrative-muted">Generate from inputs writes a new prompt and renders it. Render edited prompt sends the text above exactly as entered.</p>
      <div id="narrative-job-status" role="status" aria-live="polite"></div></section>
    <section class="narrative-card"><h2>Images</h2><div id="narrative-slots" class="narrative-slots"></div></section></div></div>`;
  updateLive();
  loadModels();
  if (assembly) renderLayers();
  const sourceImage = document.querySelector('#backdrop-source-image');
  if (sourceImage) { sourceImage.addEventListener('load',drawCropBox); drawCropBox(); }
}

function updateLive() {
  const history = document.querySelector('#narrative-interview');
  if (!history) return;
  const jobs = Object.values(detail.jobs);
  const signatureHistory = JSON.stringify([detail.interview, jobs.filter(job=>job.kind!=='image').map(job=>[job.id,job.status,job.result])]);
  if (signatureHistory !== historySignature) {
    const replies = detail.interview.filter(item=>item.role === 'assistant').length;
    const newReply = Boolean(historySignature) && replies > interviewReplies;
    interviewReplies = replies;
    historySignature = signatureHistory;
    history.innerHTML = detail.interview.map(item=>`<article class="narrative-history-entry"><p><strong>${item.role === 'user' ? 'You' : `Illustrator · ${esc(modelName(item.provenance))}`}</strong><br>${esc(item.text || 'Draft updated. Continue editing or generate.')}</p>${item.draft ? `<details><summary>Generated draft</summary><dl>${Object.entries(item.draft).map(([key,value])=>`<dt>${title(key)}</dt><dd>${esc(value)}</dd>`).join('')}</dl></details>` : ''}</article>`).join('');
    if (newReply) {
      const latest = history.lastElementChild;
      latest.classList.add('narrative-new-reply');
      history.scrollTop = latest.offsetTop;
      const notice = document.querySelector('#narrative-interview-status');
      notice.textContent = 'New interview answer received — shown below.';
      notice.className = 'narrative-complete';
    }
    const select = document.querySelector('#narrative-prompt-history');
    const value = select.value;
    select.innerHTML = '<option value="">Choose a previous prompt</option>'+jobs.filter(job=>['synthesize','generate'].includes(job.kind)&&typeof job.result==='string').map((job,index)=>`<option value="${job.id}">${index+1} · ${esc(modelName(job.provenance))}${detail.kind==='assembly' ? ' · '+assemblyModeName(job.detail.assembly_mode) : ''}</option>`).join('');
    select.value = value;
  }
  document.querySelector('#narrative-prompt-origin').textContent = `${modelName(detail.prompt_provenance)}${detail.prompt_provenance?.edited || dirty.has('prompt') ? ' · Manually edited' : ''}`;
  if (detail.kind === 'assembly') {
    const mode = document.querySelector('#narrative-assembly_mode').value;
    const stale = !dirty.has('prompt') && (detail.prompt_provenance?.assembly_mode || 'finish_composite') !== mode;
    document.querySelector('#narrative-assembly-help').textContent = mode === 'assemble_references'
      ? 'Qwen assembles original sources using placement and depth instructions. Cutout corrections affect the placement preview and composite finishing. Exact placement may vary. Up to ten visible sources.'
      : 'Qwen finishes the placed composite; seam and shadow blending preserves subject pixels.';
    document.querySelector('#narrative-assembly-prompt-warning').textContent = stale && detail.prompt ? 'This prompt belongs to another assembly mode. Write or edit the prompt before rendering.' : '';
    for (const button of root.querySelectorAll('[data-action="render"]')) button.disabled = stale;
  }
  for (const type of ['interview','prompt']) document.querySelector(`#narrative-${type}-effective`).textContent = `Next run: ${document.querySelector(`#narrative-${type}_model`).value || modelOptions.model}`;
  const working = jobs.filter(job=>active.has(job.status));
  const llmWorking = llmSubmitting || working.some(job=>job.kind !== 'image');
  const prompt = document.querySelector('#narrative-prompt');
  if (llmWorking && document.activeElement === prompt) prompt.blur();
  prompt.disabled = llmWorking;
  prompt.setAttribute('aria-busy', String(llmWorking));
  const promptActions = ['interview','rerun_interview','synthesize','rerun_prompt','generate','render','use-prompt'];
  for (const button of root.querySelectorAll('[data-action]')) {
    if (promptActions.includes(button.dataset.action)) button.disabled = busy || llmWorking || (['generate','render'].includes(button.dataset.action) && detail.kind==='backdrop' && detail.source_snapshot?.image_file && ['crop','unchanged'].includes(detail.backdrop_adaptation?.operation)) || (button.dataset.action === 'render' && Boolean(document.querySelector('#narrative-assembly-prompt-warning')?.textContent));
  }
  const interviewJob = working.find(job=>job.kind === 'interview');
  if (interviewJob) {
    const notice = document.querySelector('#narrative-interview-status');
    notice.textContent = `Interview ${interviewJob.status.toLowerCase()} · Waiting for an answer…`;
    notice.className = 'narrative-pending';
  } else if (document.querySelector('#narrative-interview-status').className === 'narrative-pending') {
    document.querySelector('#narrative-interview-status').textContent = '';
    document.querySelector('#narrative-interview-status').className = '';
  }
  const lastAuthorJob = jobs.filter(job=>job.kind !== 'image').at(-1);
  const failures = lastAuthorJob?.status === 'FAILED' ? [lastAuthorJob] : [];
  document.querySelector('#narrative-job-status').innerHTML = `<p class="${working.length || llmSubmitting ? 'narrative-pending' : 'narrative-muted'}">${working.length ? working.map(job=>`${esc(job.kind)}: ${esc(job.status.toLowerCase())}${job.kind !== 'image' ? ' · '+esc(job.model || 'Model not recorded') : ''}`).join(' · ') : llmSubmitting ? 'Submitting LLM request…' : 'Ready'}${llmWorking ? ' · Final prompt is unavailable until the LLM finishes.' : ''}</p>`+
    failures.filter(job=>job.kind !== 'image').map(job=>`<div class="narrative-failure">${esc(modelName(job.provenance))} · ${esc(job.error)} <button data-retry-job="${job.id}">Retry</button></div>`).join('');
  const signature = JSON.stringify([detail.slots,detail.candidates,detail.selected_id]);
  if (signature === slotSignature) return;
  slotSignature = signature;
  document.querySelector('#narrative-slots').innerHTML = detail.slots.map((id,index)=>{
    const candidate = id ? detail.candidates[id] : null;
    return `<article class="narrative-slot ${id && id === detail.selected_id ? 'selected' : ''}"><h3>Slot ${index+1}</h3>
      ${candidate?.image ? `<img src="${esc(imageUrl(id))}" alt="Slot ${index+1} candidate" data-review="${id}">` : `<div class="placeholder">${esc(candidate?.status.toLowerCase() || 'Empty')}</div>`}
      ${candidate ? `<p class="narrative-muted">${esc(candidate.status.toLowerCase())}${id === detail.selected_id ? ' · Selected' : ''}${candidate.locked ? ' · Locked' : ''}</p>
      ${candidate.error ? `<p class="error">${esc(candidate.error)}</p>` : ''}
      <details><summary><span>Prompt and source</span> ${copyPromptButton(id)}</summary><p>${esc(modelName(candidate.prompt_provenance))}${candidate.prompt_provenance?.edited ? ' · Manually edited' : ''}${candidate.assembly_snapshot ? ' · '+assemblyModeName(candidate.assembly_mode) : ''}</p><pre>${esc(candidate.prompt || 'Prompt not recorded')}</pre>${candidate.assembly_snapshot ? `${(candidate.assembly_snapshot.has_composite ?? (candidate.assembly_snapshot.assembly_mode || 'finish_composite')==='finish_composite') ? `<a href="${esc(artifactUrl(`candidates/${id}/composite`))}" target="_blank">Compare raw composite</a>` : ''}<p>${candidate.assembly_snapshot.layers.filter(layer=>layer.visible).map(layer=>esc(layer.label)).join(' · ')}</p>` : ''}</details>
      <div class="narrative-actions narrative-review-actions">${candidate.image ? `<button data-candidate="${id}" data-candidate-action="select">Select</button>` : ''}
      ${candidate.source_snapshot ? `<p class="narrative-muted">Source: ${esc(candidate.source_snapshot.scene_title)} · ${esc(candidate.source_snapshot.title)} · ${esc(candidate.backdrop_adaptation?.operation||'edit')}</p>` : ''}
      ${!candidate.locked && id !== detail.selected_id ? candidate.status === 'FAILED' && (candidate.assembly_snapshot || candidate.source_snapshot) ? `<button data-candidate="${id}" data-candidate-action="retry">Retry</button>` : `<button data-render-slot="${index+1}">${candidate.status === 'FAILED' ? 'Retry' : 'Regen'}</button>` : ''}
      <button data-candidate="${id}" data-candidate-action="clear">Clear</button>${candidate.image ? `<button data-candidate="${id}" data-candidate-action="${candidate.locked ? 'unlock' : 'lock'}">${candidate.locked ? 'Unlock' : 'Lock'}</button>` : ''}</div>`
      : `<div class="narrative-actions"><button data-render-slot="${index+1}">Generate</button></div>`}</article>`;
  }).join('');
  renderImageReview();
}

function reviewImages() {
  return detail?.slots.filter(id=>id && detail.candidates[id]?.image) || [];
}

function renderImageReview() {
  const dialog = document.querySelector('#image-dialog');
  if (!dialog.open) return;
  const images = reviewImages();
  if (!images.length) { dialog.close(); reviewCandidate = null; return; }
  if (!images.includes(reviewCandidate)) reviewCandidate = images[0];
  const candidate = detail.candidates[reviewCandidate];
  const index = images.indexOf(reviewCandidate);
  const selected = reviewCandidate === detail.selected_id;
  document.querySelector('#review-image').src = imageUrl(reviewCandidate);
  document.querySelector('#review-image').alt = `Slot ${candidate.slot} candidate`;
  document.querySelector('#narrative-review-prev').disabled = busy || index === 0;
  document.querySelector('#narrative-review-next').disabled = busy || index === images.length - 1;
  document.querySelector('#narrative-review-panel').innerHTML = `<h2>${esc(detail.title)} · Slot ${candidate.slot}</h2>
    <p class="local-pipeline-review-position">${index+1} of ${images.length} · ${esc(candidate.status.toLowerCase())}${selected ? ' · Selected' : ''}${candidate.locked ? ' · Locked' : ''}</p>
    <div class="button-row compact local-pipeline-review-actions">
      <button class="primary" data-candidate="${reviewCandidate}" data-candidate-action="select" ${busy || selected ? 'disabled' : ''}>Select</button>
      <button data-render-slot="${candidate.slot}" ${busy || selected || candidate.locked ? 'disabled' : ''}>Regen</button>
      <button class="danger" data-candidate="${reviewCandidate}" data-candidate-action="clear" ${busy ? 'disabled' : ''}>Clear</button>
      <button data-candidate="${reviewCandidate}" data-candidate-action="${candidate.locked ? 'unlock' : 'lock'}" ${busy ? 'disabled' : ''}>${candidate.locked ? 'Unlock' : 'Lock'}</button>
    </div>
    <p class="error" role="status" id="narrative-review-error"></p>
    <h3>Prompt and source ${copyPromptButton(reviewCandidate)}</h3><p class="narrative-muted">${esc(modelName(candidate.prompt_provenance))}${candidate.prompt_provenance?.edited ? ' · Manually edited' : ''}</p>
    <pre>${esc(candidate.prompt || 'Prompt not recorded')}</pre>`;
}

function mergeTarget(updated) {
  if (dirty.has('layers') || layerDrag || brush) updated.layers = detail.layers;
  if (dirty.has('backdrop_adaptation')) updated.backdrop_adaptation = detail.backdrop_adaptation;
  for (const key of targetFields) {
    const field = root.querySelector(`[data-field="${key}"]`);
    if (field && !dirty.has(key) && (document.activeElement !== field || field.disabled)) field.value = updated[key];
  }
  detail = updated;
  updateLive();
}

async function save() {
  clearTimeout(saveTimer);
  if (!detail || !dirty.size) { await saveChain; return; }
  const url = base();
  const payload = {};
  const changed = [...dirty];
  for (const key of changed) {
    if (key === 'layers') { payload.layers = structuredClone(detail.layers); continue; }
    if (key === 'backdrop_adaptation') { payload.backdrop_adaptation = structuredClone(detail.backdrop_adaptation); continue; }
    if (key.startsWith('override_')) continue;
    const field = root.querySelector(`[data-field="${key}"]`);
    if (field) payload[key] = ['width','height'].includes(key) ? Number(field.value) : field.value;
  }
  if (changed.some(key=>key.startsWith('override_'))) {
    payload.visual_overrides = Object.fromEntries(visualFields.map(key=>[key,root.querySelector(`[data-field="override_${key}"]`).value]));
  }
  const operation = saveChain.catch(()=>{}).then(async()=>{
    const updated = await api(url,'PATCH',payload);
    if (base() !== url) return;
    const pendingLayers = dirty.has('layers') && JSON.stringify(detail.layers) !== JSON.stringify(payload.layers) ? detail.layers : null;
    const pendingAdaptation = dirty.has('backdrop_adaptation') && JSON.stringify(detail.backdrop_adaptation) !== JSON.stringify(payload.backdrop_adaptation) ? detail.backdrop_adaptation : null;
    for (const key of changed) {
      if (key === 'layers') { if (!pendingLayers) dirty.delete(key); continue; }
      if (key === 'backdrop_adaptation') { if (!pendingAdaptation) dirty.delete(key); continue; }
      const field = root.querySelector(`[data-field="${key}"]`);
      const value = key.startsWith('override_') ? payload.visual_overrides[key.slice(9)] : payload[key];
      if (field && String(field.value) === String(value)) dirty.delete(key);
    }
    Object.assign(detail,updated);
    if (pendingLayers) detail.layers = pendingLayers;
    if (pendingAdaptation) detail.backdrop_adaptation = pendingAdaptation;
    const option = root.querySelector(`#narrative-target-select option[value="${updated.id}"]`);
    if (option) option.textContent = `${updated.title} · ${title(updated.kind)}`;
    status(dirty.size ? 'Saving changes…' : 'Saved');
    if (route.target) updateLive();
  });
  saveChain = operation;
  await operation;
}

async function poll() {
  if (!route.target || pollBusy || busy) return;
  pollBusy = true;
  const url = base();
  try {
    const updated = await api(url);
    if (base() !== url) return;
    mergeTarget(updated);
  } catch (error) { status(error.message,true); }
  finally { pollBusy = false; }
}

async function start(actionName, count = 1, slot, retryJobId) {
  await save();
  status(actionName === 'render' ? 'Queueing images…' : 'Queueing illustrator…');
  const direction = document.querySelector('#narrative-direction');
  const replay = actionName.startsWith('rerun_') ? Object.values(detail.jobs).filter(job=>actionName==='rerun_interview' ? job.kind==='interview' : ['synthesize','generate'].includes(job.kind)).at(-1) : null;
  if (actionName.startsWith('rerun_') && !replay) throw new Error('Run an interview or write a prompt first.');
  llmSubmitting = actionName !== 'render';
  updateLive();
  let result;
  try {
    result = await api(base()+'/jobs','POST',{action:actionName,count, ...(slot ? {slot} : {}),...(replay ? {job_id:replay.id} : {}),...(retryJobId ? {retry_job_id:retryJobId} : {}),message:direction?.value || ''});
  } finally { llmSubmitting = false; updateLive(); }
  mergeTarget(result);
  if (actionName === 'interview' && direction) direction.value = '';
  const lastJob = Object.values(result.jobs).at(-1);
  status(lastJob?.status === 'FAILED' ? lastJob.error : 'Queued. You can keep editing.', lastJob?.status === 'FAILED');
}

async function editElement(id) {
  await save();
  const scene = await api(`/api/narrative/stories/${route.story}/scenes/${route.scene}`);
  elementDraft = id ? {...scene.elements.find(item=>item.id===id)} : {name:'',kind:'subject',asset_id:'',appearance:'',reference_role:'appearance'};
  const dialog = document.querySelector('#element-dialog');
  dialog.innerHTML = `<h2>${id ? 'Edit' : 'New'} element</h2><form id="element-form">
    <label class="narrative-field">Name<input name="name" required value="${esc(elementDraft.name)}"></label>
    <label class="narrative-field">Type<select name="kind">${['subject','prop','environment'].map(kind=>`<option ${kind===elementDraft.kind ? 'selected' : ''}>${kind}</option>`).join('')}</select></label>
    <label class="narrative-field">Appearance notes<textarea name="appearance">${esc(elementDraft.appearance)}</textarea></label>
    <label class="narrative-field">Reference role<select name="reference_role">${['appearance','costume','object shape','environment','style'].map(role=>`<option ${role===elementDraft.reference_role ? 'selected' : ''}>${role}</option>`).join('')}</select></label>
    <p id="element-reference-label">${elementDraft.asset_id ? 'Reference image attached' : 'Text only — no reference image'}</p>
    <div class="narrative-actions"><button type="button" id="choose-reference">Choose library image</button><button type="button" id="remove-reference">Remove reference</button></div>
    <div class="narrative-actions"><button class="primary">Save element</button><button type="button" data-close="element-dialog">Cancel</button></div></form>`;
  dialog.showModal();
}

async function librarySearch() {
  const query = document.querySelector('#library-query').value;
  const assets = await api('/api/narrative/library?q='+encodeURIComponent(query));
  document.querySelector('#library-results').innerHTML = assets.map(asset=>`<button type="button" data-library-asset="${esc(asset.asset_id)}" data-label="${esc(asset.label)}"><img src="${esc(assetUrl(asset.asset_id))}" alt="${esc(asset.label)}"><span>${esc(asset.label)}</span></button>`).join('') || '<p>No matching images.</p>';
}

async function assignElements() {
  await save();
  const scene = await api(`/api/narrative/stories/${route.story}/scenes/${route.scene}`);
  const dialog = document.querySelector('#membership-dialog');
  dialog.innerHTML = `<h2>Assign elements to ${esc(detail.title)}</h2><form id="membership-form">${scene.elements.map(element=>`<p><label><input type="checkbox" name="element" value="${element.id}" ${detail.element_ids.includes(element.id) ? 'checked' : ''}> ${esc(element.name)} · ${esc(element.kind)}</label></p>`).join('') || '<p>Create an element first.</p>'}<div class="narrative-actions"><button class="primary">Save assignments</button><button type="button" data-close="membership-dialog">Cancel</button></div></form>`;
  dialog.showModal();
}

document.addEventListener('input',event=>{
  if (event.target.dataset.adaptation || event.target.dataset.crop) { adaptationChanged();updateLive();return; }
  if (event.target.dataset.layerField) {
    const key=event.target.dataset.layerField;
    if (['candidate_id','role','fit','cutout','visible'].includes(key)) return;
    const layer=detail.layers.find(item=>item.id===event.target.dataset.layer);layer[key]=Number(event.target.value);
    layersChanged();renderPlacement();return;
  }
  if (!event.target.dataset.field) return;
  dirty.add(event.target.dataset.field);
  status('Saving changes…'); clearTimeout(saveTimer);
  saveTimer = setTimeout(()=>save().catch(error=>status(error.message,true)),700);
  if(route.target) updateLive();
  if (['width','height'].includes(event.target.dataset.field)) drawCropBox();
});

document.addEventListener('change',event=>{
  if (event.target.id==='source-story') {populateSourceTargets().catch(error=>status(error.message,true));return;}
  if (event.target.id==='source-target') {populateSourceCandidates().catch(error=>status(error.message,true));return;}
  if (event.target.id==='source-candidate') {previewNarrativeSource().catch(error=>status(error.message,true));return;}
  if (event.target.id==='narrative-prompt-history') {document.querySelector('#narrative-prompt-preview').textContent=detail.jobs[event.target.value]?.result||'';return;}
  if (event.target.dataset.layerField) {
    const layer=detail.layers.find(item=>item.id===event.target.dataset.layer),key=event.target.dataset.layerField;
    layer[key]=key==='visible'?event.target.checked:['candidate_id','role','fit','cutout'].includes(key)?event.target.value:Number(event.target.value);
    if(key==='candidate_id') layer.strokes=[];
    if(key==='role') layer.cutout=layer.role==='base'?'opaque':'auto';
    layersChanged();action(async()=>{await save();renderLayers();});return;
  }
  if (event.target.id !== 'narrative-target-select') return;
  const target = event.target.value;
  action(async()=>{
    try { await navigate({...route,target}); }
    catch (error) { event.target.value = route.target; throw error; }
  });
});

document.addEventListener('click',event=>{
  const button = event.target.closest('button,a,img[data-review]');
  if (!button) return;
  if (button.dataset.copyPrompt) {
    event.preventDefault();
    navigator.clipboard.writeText(detail.candidates[button.dataset.copyPrompt].prompt).then(()=>{
      button.textContent = '✓';
      button.title = 'Prompt copied';
      status('Prompt copied to clipboard');
      setTimeout(()=>{button.textContent = '⧉'; button.title = 'Copy prompt to clipboard';},2000);
    }).catch(error=>status(`Unable to copy prompt: ${error.message}`,true));
    return;
  }
  if (button.dataset.close) { document.getElementById(button.dataset.close).close(); return; }
  if (button.id === 'new-story-button') {
    document.querySelector('#new-story').reset();
    document.querySelector('#story-dialog').showModal(); return;
  }
  if (button.matches('[data-navigate]') || button.id === 'narrative-home') {
    event.preventDefault(); action(()=>navigate(button.href)); return;
  }
  if (button.dataset.review) {
    reviewCandidate = button.dataset.review;
    document.querySelector('#image-dialog').showModal(); renderImageReview(); return;
  }
  if (button.id === 'narrative-review-prev' || button.id === 'narrative-review-next') {
    const images = reviewImages();
    const index = images.indexOf(reviewCandidate) + (button.id === 'narrative-review-prev' ? -1 : 1);
    if (!busy && images[index]) { reviewCandidate = images[index]; renderImageReview(); }
    return;
  }
  if (button.dataset.libraryAsset) {
    elementDraft.asset_id = button.dataset.libraryAsset;
    const form = document.querySelector('#element-form');
    if (!form.elements.name.value) form.elements.name.value = button.dataset.label;
    document.querySelector('#element-reference-label').textContent = button.dataset.label;
    document.querySelector('#library-dialog').close(); return;
  }
  if (button.id === 'choose-reference') {
    const dialog = document.querySelector('#library-dialog');
    dialog.innerHTML = `<h2>Choose a reference image</h2><form id="library-search" class="narrative-inline"><input id="library-query" aria-label="Search library" placeholder="Character, costume, prop or place"><button>Search</button><button type="button" data-close="library-dialog">Close</button></form><div id="library-results" class="narrative-library-grid"></div>`;
    dialog.showModal(); librarySearch().catch(error=>status(error.message,true)); return;
  }
  if (button.id === 'remove-reference') {
    elementDraft.asset_id = ''; document.querySelector('#element-reference-label').textContent = 'Text only — no reference image'; return;
  }
  if (!['editElement','removeElement','deleteElement','candidate','renderSlot','retryJob','action','currentSelection','maskLayer','removeLayer'].some(key=>button.dataset[key])&&!['mask-apply','mask-reset'].includes(button.id)) return;
  action(async()=>{
    if (button.id==='mask-apply'||button.id==='mask-reset') {
      const id=document.querySelector('#mask-canvas').dataset.maskSource;
      if(button.id==='mask-reset') {detail.layers.find(item=>item.id===id).strokes=[];layersChanged();}
      await save();await drawMask(id);renderLayers();
    } else if (button.dataset.maskLayer) await editMask(button.dataset.maskLayer);
    else if (button.dataset.removeLayer) {detail.layers=detail.layers.filter(item=>item.id!==button.dataset.removeLayer);layersChanged();await save();renderLayers();}
    else if (button.dataset.currentSelection) {
      const layer=detail.layers.find(item=>item.id===button.dataset.currentSelection);
      const scene=await api(`/api/narrative/stories/${route.story}/scenes/${route.scene}/targets/${layer.target_id}`);
      if(!scene.selected_id) throw new Error('Select a source image first.');
      layer.candidate_id=scene.selected_id;layer.strokes=[];layersChanged();await save();renderLayers();
    } else if (button.dataset.editElement) await editElement(button.dataset.editElement);
    else if (button.dataset.removeElement) {
      await save(); await api(base(),'PATCH',{element_ids:detail.element_ids.filter(id=>id!==button.dataset.removeElement)}); await loadPage();
    } else if (button.dataset.deleteElement) {
      await api(`${base()}/elements/${button.dataset.deleteElement}`,'DELETE'); await loadPage();
    } else if (button.dataset.candidate) {
      await save(); const result = await api(base()+`/candidates/${button.dataset.candidate}`,'POST',{action:button.dataset.candidateAction});
      if (result) { detail=result; updateLive(); status('Updated'); }
    } else if (button.dataset.renderSlot) await start(root.querySelector('#narrative-prompt').value.trim() ? 'render' : 'generate',1,Number(button.dataset.renderSlot));
    else if (button.dataset.retryJob) {
      const job = detail.jobs[button.dataset.retryJob]; await start(job.kind,job.candidate_ids?.length === 4 ? 4 : 1,undefined,job.detail.kind==='assembly' || job.detail.source_snapshot?.image_file ? job.id : undefined);
    } else {
      switch (button.dataset.action) {
        case 'reference-backdrop': case 'attach-backdrop': await chooseNarrativeSource('backdrop',button.dataset.action==='attach-backdrop');break;
        case 'import-subscene': await chooseNarrativeSource('subscene');break;
        case 'refresh-backdrop': case 'copy-source-current': case 'copy-source-generation': case 'reuse-backdrop': case 'crop-backdrop': {
          await save();
          const request = {'refresh-backdrop':{action:'refresh'},'copy-source-current':{action:'copy_inputs',basis:'current'},'copy-source-generation':{action:'copy_inputs',basis:'generation'},'reuse-backdrop':{action:'reuse'},'crop-backdrop':{action:'crop'}}[button.dataset.action];
          await api(base()+'/backdrop-source','POST',request);await loadPage();break;
        }
        case 'preview-crop': {await save();const image=document.querySelector('#backdrop-crop-preview');image.src=artifactUrl('crop-preview')+'&revision='+Date.now();image.hidden=false;break;}
        case 'create-assembly': {await save();const target=await api(base()+'/targets','POST',{title:'Final assembly',kind:'assembly'});await navigate({...route,target:target.id});break;}
        case 'use-prompt': {await save();const id=document.querySelector('#narrative-prompt-history').value;if(!id) throw new Error('Choose a previous prompt.');await api(base(),'PATCH',{use_prompt_job:id});mergeTarget(await api(base()));break;}
        case 'add-layer': {
          await save();const source=detail.assembly_sources.find(item=>item.id===document.querySelector('#assembly-source').value);
          if(!source?.candidates.length) throw new Error('Generate a completed source image first.');
          detail.layers.push({target_id:source.id,candidate_id:source.selected_id||source.candidates[0].id,role:source.kind==='backdrop'&&!detail.layers.some(layer=>layer.role==='base')?'base':'group',x:.1,y:.2,scale:.4,z:detail.layers.length});
          layersChanged();await save();renderLayers();break;
        }
        case 'download-composite': case 'preview-composite': {
          await save();const response=await fetch(artifactUrl('composite'));if(!response.ok){const value=await response.json();throw new Error(value.detail);}
          const blob=await response.blob();
          if(button.dataset.action==='download-composite') {
            const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='composite.png';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);
          } else {
            const image=document.querySelector('#assembly-raw');if(image.dataset.blob) URL.revokeObjectURL(image.dataset.blob);image.src=URL.createObjectURL(blob);image.dataset.blob=image.src;image.hidden=false;
          }
          break;
        }
        case 'save': await save(); status('Saved'); break;
        case 'delete': {
          await save(); const result = await api(base(),'DELETE',{});
          if (result) await navigate(route.target ? {story:route.story,scene:route.scene} : route.scene ? {story:route.story} : {});
          break;
        }
        case 'new-element': await editElement(); break;
        case 'assign-elements': await assignElements(); break;
        case 'interview': case 'synthesize': case 'generate': case 'render': case 'rerun_interview': case 'rerun_prompt': await start(button.dataset.action,Number(button.dataset.count || 1)); break;
        case 'refresh': await save(); mergeTarget(await api(base())); status('Updated'); break;
      }
    }
  });
});

document.addEventListener('submit',event=>{
  event.preventDefault();
  const form = event.target;
  if (form.id === 'library-search') { librarySearch().catch(error=>status(error.message,true)); return; }
  action(async()=>{
    const fields = Object.fromEntries(new FormData(form));
    switch (form.id) {
      case 'narrative-source-form': {
        await save();
        if (!sourcePicker.preview) throw new Error('Choose an available source first.');
        const source=chosenSource();
        if(sourcePicker.kind==='backdrop'&&!source.candidate_id) throw new Error('Choose a completed source candidate.');
        const result=sourcePicker.attach ? await api(base()+'/backdrop-source','POST',{action:'attach',source}) :
          await api(`/api/narrative/stories/${route.story}/scenes/${route.scene}/references`,'POST',{source,title:document.querySelector('#source-title').value,
            copy_visual_context:document.querySelector('#source-copy-context').checked,
            element_mappings:Object.fromEntries([...form.querySelectorAll('[data-source-element]')].map(select=>[select.dataset.sourceElement,select.value]))});
        document.querySelector('#narrative-source-dialog').close();sourcePicker=null;
        await navigate({...route,target:result.id});break;
      }
      case 'new-story': { const story=await api('/api/narrative/stories','POST',fields); document.querySelector('#story-dialog').close(); await navigate({story:story.id}); break; }
      case 'new-scene': { await save(); const scene=await api(base()+'/scenes','POST',fields); await navigate({...route,scene:scene.id}); break; }
      case 'new-target': { await save(); const target=await api(base()+'/targets','POST',fields); await navigate({...route,target:target.id}); break; }
      case 'element-form': {
        const url = `/api/narrative/stories/${route.story}/scenes/${route.scene}/elements`;
        const element=await api(url+(elementDraft.id ? '/'+elementDraft.id : ''),elementDraft.id ? 'PATCH' : 'POST',{...fields,asset_id:elementDraft.asset_id});
        if (route.target && !detail.element_ids.includes(element.id)) await api(base(),'PATCH',{element_ids:[...detail.element_ids,element.id]});
        document.querySelector('#element-dialog').close(); await loadPage(); break;
      }
      case 'membership-form': {
        await api(base(),'PATCH',{element_ids:new FormData(form).getAll('element')});
        document.querySelector('#membership-dialog').close(); await loadPage(); break;
      }
    }
  });
});

window.addEventListener('popstate',()=>{ action(async()=>{ await save(); await loadPage(); }); });
document.querySelector('#narrative-universe').addEventListener('change',event=>action(async()=>{
  await save(); universe=event.target.value; await navigate({});
}));
window.addEventListener('beforeunload',event=>{ if(dirty.size) {event.preventDefault(); event.returnValue='';} });

async function initialize() {
  const universes = await api('/api/universes');
  universe ||= universes.selected_universe_id;
  document.querySelector('#narrative-universe').innerHTML = universes.universes.map(item=>`<option value="${esc(item.universe_id)}" ${item.universe_id===universe ? 'selected' : ''}>${esc(item.name)}</option>`).join('');
  const options = await api('/api/narrative/options');
  modelOptions = options;
  document.querySelector('#narrative-model').textContent = `${options.model} · ${options.renderer}`;
  await loadPage();
  setInterval(poll,2000);
}
initialize().catch(error=>status(error.message,true));
