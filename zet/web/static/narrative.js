/** Mounted Narrative editor; all listeners and polling belong to this mount. */
export async function mountNarrative(host, requestedUniverse = '', onContext = null) {
let disposed = false;
let pollTimer = null;
let restoreProvider = null;
const events = new AbortController();
function listen(target, type, callback, options = {}) {
  target.addEventListener(type, callback, {...options, signal: events.signal});
}
const root = host.querySelector('#narrative-root');
root.replaceChildren();
const message = host.querySelector('#narrative-message');
const params = new URLSearchParams(location.search);
let universe = requestedUniverse || params.get('universe_id') || '';
let route = {story:params.get('story'),scene:params.get('scene'),target:params.get('target')};
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
let interviewReviewId = null;
const interviewChoices = new Map();
let llmSubmitting = false;
let layerDrag = null;
let brush = null;
let reviewCandidate = null;
let sourcePicker = null;
let contextState = 'loading';
let contextLabels = {};
let candidateRestorePending = params.get('task_context') === '1';
const active = new Set(['SUBMITTING', 'QUEUED', 'RUNNING', 'DISPATCHING']);
const visualFields = ['setting', 'camera', 'perspective', 'lighting', 'style'];
const targetFields = ['universe_style_variant', 'title', 'narrative', 'staging', 'physical_context', 'use_transparent_background', 'framing', 'width', 'height', 'prompt', 'interview_model', 'prompt_model', 'assembly_mode'];
const assemblyModeName = mode => ({assemble_references:'Assemble from references', harmonize_composite:'Harmonize placed composite'}[mode] || 'Finish placed composite');
const fieldValue = field => field.type === 'checkbox' ? field.checked : field.value;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const title = key => key.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());
const targetsWithAssemblyLast = targets => [...targets.filter(target => target.kind !== 'assembly'), ...targets.filter(target => target.kind === 'assembly')];
const label = (key, value, textarea = true, name = title(key)) => {
  const helpKey = key.startsWith('override_') || visualFields.includes(key) ? 'visual_context' : key;
  const help = detail?.field_purposes?.[helpKey];
  const inputOnly = route.target && ['title','width','height'].includes(key);
  return `<label class="narrative-field">${esc(name)}${help ? '<small class="narrative-field-role">Interview input · Interview may propose changes</small>' : inputOnly ? '<small class="narrative-field-role">Interview input · Edited here only</small>' : key === 'prompt' ? '<small class="narrative-field-role">Prompt output · Editable before rendering</small>' : ''}${textarea
  ? `<textarea data-field="${key}" id="narrative-${key}">${esc(value)}</textarea>`
  : `<input data-field="${key}" id="narrative-${key}" ${['width','height'].includes(key) ? 'type="number" step="32" min="256" max="4096"' : ''} value="${esc(value)}">`}${help ? `<small class="narrative-field-help">${esc(help)}</small>` : ''}</label>`;
};

function status(text, error = false) { if (disposed) return; message.textContent = text; message.classList.toggle('error', error); }
function href(next) {
  const query = new URLSearchParams({universe_id: universe});
  for (const [key, value] of Object.entries(next)) if (value) query.set(key, value);
  return `/?page=narrative&workspace=story&${query}`;
}
function link(text, next) { return `<a href="${esc(href(next))}" data-navigate>${esc(text)}</a>`; }
function base() {
  let value = `/api/narrative/stories/${route.story}`;
  if (route.scene) value += `/scenes/${route.scene}`;
  if (route.target) value += `/targets/${route.target}`;
  return value;
}
function imageUrl(id, target = route.target) {
  return `/api/narrative/stories/${route.story}/scenes/${route.scene}/targets/${target}/candidates/${id}/finished-image?universe_id=${encodeURIComponent(universe)}&revision=${encodeURIComponent(detail?.candidates?.[id]?.scene_text_final?.image || "original")}`;
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
function enableModelPickers() {
  for (const field of root.querySelectorAll('input[list="narrative-model-options"]')) {
    let previousValue = null;
    const revealOptions = () => {
      const key = field.dataset.field;
      if (field.value && !dirty.has(key) && field.value === detail[key]) {
        previousValue = field.value;
        field.value = '';
      }
    };
    listen(field,'focus',revealOptions);
    listen(field,'pointerdown',revealOptions);
    listen(field,'input',()=>{ previousValue = null; });
    listen(field,'blur',()=>{
      if (previousValue !== null && !field.value) field.value = previousValue;
      previousValue = null;
    });
  }
}
async function loadModels() {
  const url = base();
  try {
    const result = await api('/api/ai-controls/ollama-models');
    if (base() !== url) return;
    knownModels = result.models || [];
    const errorNode = host.querySelector('#narrative-model-error');
    if (errorNode) errorNode.textContent = '';
  } catch (error) { const errorNode = host.querySelector('#narrative-model-error'); if (base() === url && errorNode) errorNode.textContent = error.message; }
  if (!detail || base() !== url) return;
  const list = host.querySelector('#narrative-model-options');
  if (list) list.innerHTML = [...new Set([modelOptions.model,...knownModels,...modelOptions.codex_models,detail.interview_model,detail.prompt_model])].filter(Boolean).map(name=>`<option value="${esc(name)}"></option>`).join('');
}

async function api(url, method = 'GET', data) {
  const response = await fetch(url, {method, signal: events.signal, headers: {'Content-Type':'application/json', 'x-zet-universe':universe},
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
  if (disposed) return;
  if (busy) return;
  busy = true;
  let actionError = '';
  renderImageReview();
  root.querySelectorAll('button, #narrative-target-select').forEach(control => { control.disabled = true; });
  try { await callback(); } catch (error) { actionError = error.message; status(error.message, true); }
  finally {
    if (disposed) return;
    busy = false; root.querySelectorAll('button, #narrative-target-select').forEach(control => { control.disabled = false; });
    if (route.story && !route.scene) updateSceneOrderControls();
    if (route.target && detail) updateLive(); renderImageReview();
    const reviewError = host.querySelector('#narrative-review-error');
    if (reviewError) reviewError.textContent = actionError;
    const interviewError = host.querySelector('#narrative-interview-review-error');
    if (interviewError) interviewError.textContent = actionError;
  }
}

function renderStoryScenes(scenes) {
  const grid = root.querySelector('#narrative-story-scenes');
  if (!grid) return;
  grid.innerHTML = scenes.map((scene, index) => {
    const assembly = scene.final_assembly;
    const image = assembly ? `/api/narrative/stories/${route.story}/scenes/${scene.id}/targets/${assembly.target_id}/candidates/${assembly.candidate_id}/finished-image?universe_id=${encodeURIComponent(universe)}` : '';
    return `<article class="narrative-card narrative-scene-card"><h2>${link(scene.title,{story:route.story,scene:scene.id})}</h2>
      ${assembly ? `<a href="${esc(href({story:route.story,scene:scene.id,target:assembly.target_id}))}" data-navigate><img class="narrative-story-thumbnail" src="${esc(image)}" alt="Selected final assembly for ${esc(scene.title)}" loading="lazy"></a>` : `<span class="narrative-story-thumbnail narrative-story-placeholder" role="img" aria-label="No selected final assembly for ${esc(scene.title)}"></span>`}
      <p>${esc(scene.intent)}</p><div class="narrative-actions"><button type="button" data-move-scene="${scene.id}" data-direction="-1" ${index===0?'disabled':''}>Move earlier</button><button type="button" data-move-scene="${scene.id}" data-direction="1" ${index===scenes.length-1?'disabled':''}>Move later</button></div></article>`;
  }).join('');
}

function updateSceneOrderControls() {
  root.querySelectorAll('[data-move-scene]').forEach(button => {
    const index = detail.scenes.findIndex(scene => scene.id === button.dataset.moveScene);
    const destination = index + Number(button.dataset.direction);
    button.disabled = busy || index < 0 || destination < 0 || destination >= detail.scenes.length;
  });
}

async function navigate(next, push = true) {
  await save();
  const url = typeof next === 'string' ? next : href(next);
  if (push) history.pushState({}, '', url);
  await loadPage();
}

async function loadPage() {
  if (disposed) return;
  contextState = 'loading';
  document.body.dataset.narrativeReady = 'false';
  root.replaceChildren();
  contextLabels = {};
  detail = null;
  try {
    await loadPageContent();
    if (disposed) return;
    await onContext?.({...route});
    contextState = 'selected';
    const recorded = new URLSearchParams(location.search).get('task_candidate');
    if (candidateRestorePending && recorded && route.target) {
      candidateRestorePending = false;
      if (detail?.candidates?.[recorded]?.image) {
        reviewCandidate = recorded;
        host.querySelector('#image-dialog').showModal();
        renderImageReview();
      } else window.ZetTaskCapture.notice(`Recorded candidate "${recorded}" is unavailable. The target is open.`);
    }
  } catch (error) {
    contextState = 'unavailable';
    if (new URLSearchParams(location.search).get('task_context') !== '1') throw error;
    root.innerHTML = '<h1>Narrative selection unavailable</h1><p>Open the parent workspace to choose an available selection.</p>';
    host.querySelector('#narrative-breadcrumb').innerHTML = link('Stories',{})
      + (route.story ? ' / '+link('Story',{story:route.story}) : '')
      + (route.scene ? ' / '+link('Scene',{story:route.story,scene:route.scene}) : '');
    window.ZetTaskCapture.notice('The recorded narrative selection could not be restored. '+error.message);
    status(error.message,true);
    document.body.dataset.narrativeReady = 'true';
  }
}

async function loadPageContent() {
  host.querySelector('#image-dialog').close();
  host.querySelector('#narrative-interview-review').close();
  interviewReviewId = null;
  reviewCandidate = null;
  clearTimeout(saveTimer);
  const query = new URLSearchParams(location.search);
  route = {story:query.get('story'), scene:query.get('scene'), target:query.get('target')};
  dirty = new Set(); slotSignature = ''; historySignature = ''; interviewReplies = 0;
  host.querySelector('#narrative-home').href = href({});
  status('Loading…');
  if (!route.story) {
    detail = null;
    const stories = await api('/api/narrative/stories');
    root.innerHTML = `<div class="narrative-stories-heading"><h1>Narrative Scenes</h1><button id="new-story-button" class="primary">New Story</button></div>
      <div class="narrative-grid">${stories.map(story => `<article class="narrative-card"><h2>${link(story.title, {story:story.id})}</h2><p>${esc(story.brief)}</p>
        <div class="narrative-story-scenes">${story.scenes.map(scene => {
          const assembly = scene.final_assembly;
          const destination = {story:story.id,scene:scene.id,...(assembly ? {target:assembly.target_id} : {})};
          const image = assembly ? `/api/narrative/stories/${story.id}/scenes/${scene.id}/targets/${assembly.target_id}/candidates/${assembly.candidate_id}/finished-image?universe_id=${encodeURIComponent(universe)}` : '';
          return `<a class="narrative-story-scene" href="${esc(href(destination))}" data-navigate>
            ${assembly ? `<img class="narrative-story-thumbnail" src="${esc(image)}" alt="Selected final assembly for ${esc(scene.title)}" loading="lazy">` : `<span class="narrative-story-thumbnail narrative-story-placeholder" role="img" aria-label="No selected final assembly for ${esc(scene.title)}"></span>`}
            <span>${esc(scene.title)}</span></a>`;
        }).join('')}</div></article>`).join('')}</div>`;
    host.querySelector('#narrative-breadcrumb').textContent = 'Stories';
  } else if (!route.scene) {
    detail = await api(base());
    contextLabels.story = detail.title;
    root.innerHTML = `<h1>${esc(detail.title)}</h1><section class="narrative-card">${label('title',detail.title,false)}${label('brief',detail.brief)}<button type="button" id="scene-text-story-style">Scene text style</button>
      <div class="narrative-actions"><button data-action="save">Save story</button><button class="danger" data-action="delete">Delete story</button></div></section>
      <section class="narrative-card"><h2>Story animation</h2><p>Create a silent animation from locked final assemblies. Camera motion and confirmed text visibility can be edited per shot.</p><button type="button" id="open-story-animation">Open Animation workspace</button><div id="story-animation-workspace" hidden></div></section>
      <section class="narrative-card"><h2>New scene</h2><form id="new-narrative-scene" class="narrative-inline"><input aria-label="Scene title" name="title" required placeholder="Scene title"><button class="primary">Create scene</button></form></section>
      <div class="narrative-grid" id="narrative-story-scenes"></div>`;
    renderStoryScenes(detail.scenes);
    host.querySelector('#scene-text-story-style')?.addEventListener('click',()=>window.ZetSceneText.style({universe,story:route.story}));
    host.querySelector('#open-story-animation')?.addEventListener('click', () => action(async () => {
      const panel=host.querySelector('#story-animation-workspace'); panel.hidden=false;
      const [animations,sources]=await Promise.all([api(`${base()}/animations`),api(`/api/narrative/stories/${route.story}/animation-sources`)]);
      const animation=animations[0]||await api(`${base()}/animations`,'POST',{name:'New animation',aspect_ratio:'16:9'});
      let doc=await api(`${base()}/animations/${animation.id}`); let shots=doc.spec.shots;
      const render=()=>{panel.innerHTML=`<h3>${esc(doc.spec.name)}</h3><p>Locked sources only. Scene text enters as fixed screen layers.</p><div>${sources.map(s=>`<button type="button" data-bind-source="${esc(s.id)}">Add ${esc(s.title)}${s.lettered?' (lettered)':''}</button>`).join(' ')}</div><ol>${shots.map((s,i)=>`<li>${esc(doc.assets[s.source_id]?.title||s.source_id)} <label>Duration ms <input data-shot-duration="${i}" type="number" min="100" value="${s.duration_ms}"></label><label>Camera X <input data-camera-x="${i}" type="number" min="0" max="1" step=".01" value="${s.camera?.[0]?.x??.5}"></label><label>Camera Y <input data-camera-y="${i}" type="number" min="0" max="1" step=".01" value="${s.camera?.[0]?.y??.5}"></label><label>Zoom <input data-camera-zoom="${i}" type="number" min="1" step=".1" value="${s.camera?.[0]?.zoom??1}"></label><label>Transition <select data-transition="${i}"><option value="cut">Cut</option><option value="dissolve" ${s.transition?.type==='dissolve'?'selected':''}>Dissolve</option><option value="fade-through-black" ${s.transition?.type==='fade-through-black'?'selected':''}>Fade through black</option></select></label>${(doc.assets[s.source_id]?.text_entries||[]).map(e=>`<label>${esc(e.text)} fade (ms) <input data-text-fade="${i}" data-text-id="${esc(e.id)}" type="number" min="0" value="0"></label>`).join('')} <button data-remove-shot="${i}">Remove</button></li>`).join('')}</ol><div class="narrative-actions"><button id="save-animation">Save</button><button id="preview-animation">Preview</button><a id="export-animation" href="/api/narrative/stories/${route.story}/animations/${animation.id}/html?universe_id=${encodeURIComponent(universe)}">Download HTML</a></div><iframe title="Animation preview" sandbox="allow-scripts" style="width:100%;height:520px;border:0"></iframe>`;
        panel.querySelectorAll('[data-bind-source]').forEach(b=>b.onclick=async()=>{doc=await api(`${base()}/animations/${animation.id}/sources`,'POST',{source_id:b.dataset.bindSource});const id=Object.keys(doc.assets).at(-1);shots.push({id:crypto.randomUUID(),source_id:id,duration_ms:8000,camera:[{time_ms:0,x:.5,y:.5,zoom:1}],text:{},transition:{type:'cut',duration_ms:0}});render()});
        panel.querySelectorAll('[data-remove-shot]').forEach(b=>b.onclick=()=>{shots.splice(Number(b.dataset.removeShot),1);render()});
        panel.querySelector('#save-animation').onclick=async()=>{shots.forEach((s,i)=>{s.duration_ms=Number(panel.querySelector(`[data-shot-duration="${i}"]`).value);s.camera=[{time_ms:0,x:Number(panel.querySelector(`[data-camera-x="${i}"]`).value),y:Number(panel.querySelector(`[data-camera-y="${i}"]`).value),zoom:Number(panel.querySelector(`[data-camera-zoom="${i}"]`).value)}];s.transition={type:panel.querySelector(`[data-transition="${i}"]`).value,duration_ms:panel.querySelector(`[data-transition="${i}"]`).value==='cut'?0:1000};const fade=panel.querySelector(`[data-text-fade="${i}"]`);if(fade&&Number(fade.value)>0){const textId=fade.dataset.textId;s.text[textId]=[{time_ms:0,opacity:0},{time_ms:Number(fade.value),opacity:1}]}});doc=await api(`${base()}/animations/${animation.id}`,'PUT',{revision:doc.revision,spec:{...doc.spec,shots}});shots=doc.spec.shots;render()};
        panel.querySelector('#preview-animation').onclick=()=>{panel.querySelector('iframe').src=`/api/narrative/stories/${route.story}/animations/${animation.id}/html?universe_id=${encodeURIComponent(universe)}&preview=1`};
      };render();
    }));
    host.querySelector('#narrative-breadcrumb').innerHTML = link('Stories',{});
  } else if (!route.target) {
    const [loaded, story] = await Promise.all([api(base()), api(`/api/narrative/stories/${route.story}`)]);
    detail = loaded;
    contextLabels = {story:story.title, scene:detail.title};
    root.innerHTML = `<h1>${esc(detail.title)}</h1><div class="narrative-editor"><section class="narrative-card"><h2>Shared scene direction</h2>
      ${label('title',detail.title,false)}${label('intent',detail.intent)}${visualFields.map(key=>label(key,detail[key])).join('')}${label('canvas',detail.canvas,false)}
      <label><input type="checkbox" data-field="use_universe_style" ${detail.use_universe_style ? 'checked' : ''}> Use universe style</label>
      <label>Universe style<select data-field="universe_style_variant"><option value="canonical" ${detail.universe_style_variant==='canonical'?'selected':''}>Canonical</option><option value="environmental" ${detail.universe_style_variant==='environmental'?'selected':''}>Environmental</option></select></label>
      <p class="narrative-muted">When checked, the universe style replaces the saved scene style above. Local target style overrides still apply. Write Prompt adopts changes.</p>
      <p class="narrative-muted">Universe style: ${esc(detail.universe_style?.text || 'No universe style set.')}</p>
      <div class="narrative-actions"><button data-action="save">Save scene</button><button class="danger" data-action="delete">Delete scene</button></div>
      ${detail.migration?.kind ? `<div class="narrative-migration-note"><p>Migrated starting point — review inputs before generating.</p>${(detail.migration.review_issues || []).map(issue=>`<p>${esc(issue)}</p>`).join('')}</div>` : ''}
      ${detail.legacy_image?.asset_id ? `<figure class="narrative-legacy-image"><figcaption>Legacy image</figcaption><a href="${esc(artifactUrl('legacy-image'))}" target="_blank" rel="noopener"><img src="${esc(artifactUrl('legacy-image'))}" alt="Legacy image for ${esc(detail.title)}" loading="lazy"></a></figure>` : ''}</section><div>
      <section class="narrative-card"><h2>Subscenes and backdrops</h2><form id="new-target" class="narrative-inline">
        <input aria-label="Target title" name="title" required placeholder="Title"><select name="kind" aria-label="Target kind"><option value="subscene">Subscene</option><option value="backdrop">Backdrop</option></select><button class="primary">Create and edit</button></form>
        ${detail.targets.some(target=>target.kind==='assembly') ? '' : '<button data-action="create-assembly">Create final assembly</button>'}
        <div class="narrative-actions"><button data-action="reference-backdrop">Reference backdrop from another scene</button><button data-action="import-subscene">Import subscene from another scene</button></div>
        ${targetsWithAssemblyLast(detail.targets).map(target=>`<article class="narrative-card narrative-target-card" data-target-id="${target.id}"><h3>${link(target.title,{...route,target:target.id})}</h3><p class="narrative-muted">${esc(target.kind)}${target.selected_id ? ' · Image selected' : ''}</p>
          ${target.selected_id ? `<a href="${esc(href({...route,target:target.id}))}" data-navigate><img class="narrative-target-preview" src="${esc(imageUrl(target.selected_id,target.id))}" alt="Selected image for ${esc(target.title)}"></a>` : ''}</article>`).join('')}</section>
      <section class="narrative-card"><h2>Scene elements</h2><button data-action="new-element">Add element</button><div id="narrative-elements">${elementsHtml(detail.elements,false)}</div></section></div></div>`;
    host.querySelector('#narrative-breadcrumb').innerHTML = link('Stories',{})+' / '+link(story.title,{story:route.story});
  } else {
    const [loaded, targets, story] = await Promise.all([api(base()), api(`/api/narrative/stories/${route.story}/scenes/${route.scene}/targets`), api(`/api/narrative/stories/${route.story}`)]);
    detail = loaded;
    contextLabels = {story:story.title, scene:detail.scene_title, render_target:detail.title};
    renderTarget(targets);
    host.querySelector('#narrative-breadcrumb').innerHTML = link('Stories',{})+' / '+link(story.title,{story:route.story})+' / '+link(detail.scene_title,{story:route.story,scene:route.scene})+' / '+esc(detail.title);
  }
  document.body.dataset.narrativeReady = 'true';
  status('Ready');
}

function elementsHtml(elements, target) {
  return elements.map(element=>`<article class="narrative-reference">
    ${(element.reference?.asset_id || element.asset_id) ? `<img src="${esc(assetUrl(element.reference?.asset_id || element.asset_id))}" alt="${esc(element.name)} reference">` : ''}
    <div><h3>${esc(element.name)}</h3><p class="narrative-muted">${esc(element.kind)} · ${esc(element.reference_role)}</p><small class="narrative-field-role">Name and reference metadata: interview input · Edited here only</small><small class="narrative-field-role">Appearance: interview input · Interview may propose changes</small><p>${esc(element.appearance)}</p>
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
  const container = host.querySelector('#assembly-layers');
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
  const canvas = host.querySelector('#assembly-canvas');
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
  const dialog = host.querySelector('#membership-dialog');
  dialog.innerHTML = `<h2>Correct source cutout</h2><p>Paint over the original source. Green keeps pixels; red removes them.</p><div class="narrative-inline"><label>Brush<select id="mask-mode"><option value="keep">Keep</option><option value="remove">Remove</option></select></label><label>Radius<input id="mask-radius" type="number" value="0.02" min="0.001" max="0.5" step="0.005"></label></div><canvas id="mask-canvas" data-mask-source="${layerId}"></canvas><div class="narrative-actions"><button id="mask-apply">Save corrections</button><button id="mask-reset">Reset corrections</button><button data-close="membership-dialog">Close</button></div>`;
  dialog.showModal();
  await drawMask(layerId);
}

async function drawMask(layerId) {
  const canvas = host.querySelector('#mask-canvas');
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
  const stroke = {mode:host.querySelector('#mask-mode').value, radius:Number(host.querySelector('#mask-radius').value),
    x:Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),y:Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))};
  if (!Number.isFinite(stroke.radius)||stroke.radius<.001||stroke.radius>.5) return;
  layer.strokes.push(stroke);
  const context=canvas.getContext('2d'); context.fillStyle=stroke.mode==='keep'?'rgba(25,185,80,.5)':'rgba(220,40,60,.5)';
  context.beginPath();context.arc(stroke.x*canvas.width,stroke.y*canvas.height,stroke.radius*Math.max(canvas.width,canvas.height),0,Math.PI*2);context.fill();
  layersChanged();
}

listen(host,'pointerdown',event=>{
  if (event.target.matches('#mask-canvas')) {brush=event.pointerId;event.target.setPointerCapture(event.pointerId);paintMask(event);return;}
  const node=event.target.closest('[data-drag-layer]');
  if (!node) return;
  const layer=detail.layers.find(item=>item.id===node.dataset.dragLayer);
  layerDrag={node,layer,px:event.clientX,py:event.clientY,x:layer.x,y:layer.y,scale:layer.scale,resize:Boolean(event.target.dataset.resizeLayer),pointer:event.pointerId};
  node.setPointerCapture(event.pointerId);event.preventDefault();
});
listen(host,'pointermove',event=>{
  if (brush===event.pointerId && event.target.matches('#mask-canvas')) {paintMask(event);return;}
  if (!layerDrag || layerDrag.pointer!==event.pointerId) return;
  const drag=layerDrag, rect=host.querySelector('#assembly-canvas').getBoundingClientRect();
  if (drag.resize) drag.layer.scale=Math.max(.01,Math.min(4,drag.scale+(event.clientX-drag.px)/rect.width));
  else {drag.layer.x=Math.max(-2,Math.min(2,drag.x+(event.clientX-drag.px)/rect.width));drag.layer.y=Math.max(-2,Math.min(2,drag.y+(event.clientY-drag.py)/rect.height));}
  for (const key of ['x','y','scale']) drag.layer[key]=Math.round(drag.layer[key]*10000)/10000;
  drag.node.style.left=`${drag.layer.x*100}%`;drag.node.style.top=`${drag.layer.y*100}%`;drag.node.style.width=`${drag.layer.scale*100}%`;
  for(const key of ['x','y','scale']) {const input=root.querySelector(`[data-layer="${drag.layer.id}"][data-layer-field="${key}"]`);input.value=drag.layer[key];}
  layersChanged();
});
listen(host,'pointerup',event=>{if (brush===event.pointerId) brush=null;if(layerDrag?.pointer===event.pointerId) layerDrag=null;});
listen(host,'pointercancel',()=>{brush=null;layerDrag=null;});

function sourceTextHtml(source) {
  return `<details><summary>Source inputs and prompt</summary>
    <h3>Generation inputs</h3><pre>${esc(source.generation_inputs ? JSON.stringify(source.generation_inputs,null,2) : 'Generation inputs not recorded')}</pre>
    <h3>Exact source prompt</h3><pre>${esc(source.prompt || 'Prompt not recorded')}</pre>
    <h3>Current source authoring text</h3><pre>${esc(JSON.stringify(source.current_inputs,null,2))}</pre></details>`;
}

function sourcePanelHtml() {
  if (detail.kind === 'assembly') return '';
  const source = detail.source_snapshot;
  if (detail.kind !== 'backdrop') return source?.target_id ? `<section class="narrative-card"><h2>Imported subscene source</h2><p>Pinned from ${esc(source.story_title)} / ${link(source.scene_title,{story:source.story_id,scene:source.scene_id,target:source.target_id})} · ${esc(source.title)}</p>${sourceTextHtml(source)}</section>` : '';
  const settings = detail.backdrop_adaptation || {}, crop = settings.crop || {};
  const mode = detail.backdrop_link_mode || 'reference';
  return `<section class="narrative-card" id="narrative-source-panel"><h2>Backdrop source</h2>
    <button data-action="attach-backdrop">${source?.target_id ? 'Change source backdrop' : 'Attach source backdrop'}</button>
    ${source?.target_id ? `<p>Pinned from ${esc(source.story_title)} / ${link(source.scene_title,{story:source.story_id,scene:source.scene_id,target:source.target_id})} · ${esc(source.title)}</p>
    ${sourceTextHtml(source)}
    <label class="narrative-field">How to use the source<select id="backdrop-link-mode">${[['unmodified','Use unmodified'],['reference','Reference'],['regenerate','Regenerate']].map(([v,n])=>`<option value="${v}" ${mode===v?'selected':''}>${n}</option>`).join('')}</select></label>
    <div data-source-mode="regenerate"><div class="narrative-actions"><button data-action="copy-source-current">Copy current source inputs</button>${source.generation_inputs ? '<button data-action="copy-source-generation">Copy generation inputs</button>' : ''}</div><p>Copying replaces destination inputs and creates local visual overrides. Then edit manually or use the interview. The source image is not supplied to generation.</p></div>
    <div data-source-mode="unmodified"><button data-action="reuse-backdrop">Use Unmodified Image</button></div>
    <div data-source-mode="reference"><button data-action="refresh-backdrop">Use current source selection</button>
    <label class="narrative-field">Crop<select id="backdrop-crop-enabled" data-adaptation="crop_enabled"><option value="no">No</option><option value="yes" ${settings.crop_enabled?'selected':''}>Yes</option></select></label>
    <div id="backdrop-crop-controls"><p>${esc(settings.crop_notice || 'Select an exact source region. Output dimensions do not change this crop.')}</p>
    <div class="narrative-crop-stage" id="backdrop-crop-stage"><img id="backdrop-source-image" src="${esc(artifactUrl('source-image'))}&revision=${esc(source.snapshot_id)}" alt="Pinned source backdrop"><div id="backdrop-crop-box"><span data-crop-resize="true"></span></div></div>
    <div class="narrative-grid">${['x','y','width','height'].map(key=>`<label class="narrative-field">Crop ${key}<input type="number" step="1" min="${['x','y'].includes(key)?0:1}" id="backdrop-crop-${key}" data-crop="${key}" value="${crop[key]??(['width','height'].includes(key)?source['image_'+key]:0)}"></label>`).join('')}</div>
    <button data-action="preview-crop">Preview crop</button><img id="backdrop-crop-preview" class="narrative-source-preview" hidden alt="Crop output preview"></div>
    <button id="backdrop-local-action" data-action="${settings.crop_enabled?'crop-backdrop':'reuse-backdrop'}">${settings.crop_enabled?'Use Unmodified Crop':'Use Unmodified Image'}</button>
    <label class="narrative-field">Backdrop operation<select id="backdrop-operation" data-adaptation="operation">${[['edit','Other edits'],['expand','Expand'],['viewpoint','Change viewpoint']].map(([v,n])=>`<option value="${v}" ${(settings.operation||'edit')===v?'selected':''}>${n}</option>`).join('')}</select></label>
    <label class="narrative-field">Adaptation direction<textarea id="backdrop-direction" data-adaptation="direction">${esc(settings.direction||'')}</textarea></label>
    <label class="narrative-field" id="backdrop-expand-control">Expand toward<select data-adaptation="expand_side" id="backdrop-expand-side">${['left','right','top','bottom','all'].map(side=>`<option ${(settings.expand_side||'right')===side?'selected':''}>${side}</option>`).join('')}</select></label>
    <button class="primary" data-action="apply-backdrop-operation">Apply operation</button><p>Writes a fresh prompt and generates one image from the ${settings.crop_enabled?'crop':'full source'}. Scene settings and applied interview edits supply the changes. Generated edits may reinterpret pixels.</p></div>
    <p>After changing the mode, crop or operation, use Write Prompt to update existing prompt text. Render sends the entered prompt.</p>` : '<p>No source attached.</p>'}</section>`;
}

function sourceVisibility() {
  const mode = detail.source_snapshot?.image_file ? detail.backdrop_link_mode : null;
  host.querySelectorAll('[data-source-mode]').forEach(el=>{el.hidden=el.dataset.sourceMode!==mode;});
  const crop = host.querySelector('#backdrop-crop-controls');
  if (crop) crop.hidden = !detail.backdrop_adaptation?.crop_enabled;
  const expand = host.querySelector('#backdrop-expand-control');
  if (expand) expand.hidden = detail.backdrop_adaptation?.operation !== 'expand';
  const local = host.querySelector('#backdrop-local-action');
  if (local) {local.dataset.action=detail.backdrop_adaptation?.crop_enabled?'crop-backdrop':'reuse-backdrop';local.textContent=detail.backdrop_adaptation?.crop_enabled?'Use Unmodified Crop':'Use Unmodified Image';}
  host.querySelectorAll('.narrative-direction-settings > div > section:not(#narrative-source-panel), .narrative-generation-settings').forEach(el=>{el.hidden=mode==='unmodified';});
}

function drawCropBox() {
  const image=host.querySelector('#backdrop-source-image'), box=host.querySelector('#backdrop-crop-box');
  if (!image?.naturalWidth || !box) return;
  const c=detail.backdrop_adaptation.crop;
  Object.assign(box.style,{left:`${c.x/image.naturalWidth*100}%`,top:`${c.y/image.naturalHeight*100}%`,width:`${c.width/image.naturalWidth*100}%`,height:`${c.height/image.naturalHeight*100}%`});
}
let cropDrag=null;
listen(host,'pointerdown',event=>{
  const box=event.target.closest('#backdrop-crop-box');
  if(!box) return;
  event.preventDefault();box.setPointerCapture(event.pointerId);
  cropDrag={pointer:event.pointerId,x:event.clientX,y:event.clientY,crop:{...detail.backdrop_adaptation.crop},resize:!!event.target.dataset.cropResize};
});
listen(host,'pointermove',event=>{
  if(!cropDrag || cropDrag.pointer!==event.pointerId) return;
  const image=host.querySelector('#backdrop-source-image'), bounds=image.getBoundingClientRect(), sw=image.naturalWidth, sh=image.naturalHeight;
  const dx=Math.round((event.clientX-cropDrag.x)*sw/bounds.width),dy=Math.round((event.clientY-cropDrag.y)*sh/bounds.height),c={...cropDrag.crop};
  if(cropDrag.resize){c.width=Math.max(1,Math.min(sw-c.x,c.width+dx));c.height=Math.max(1,Math.min(sh-c.y,c.height+dy));}
  else {c.x=Math.max(0,Math.min(sw-c.width,c.x+dx));c.y=Math.max(0,Math.min(sh-c.height,c.y+dy));}
  for(const key of ['x','y','width','height'])host.querySelector('#backdrop-crop-'+key).value=c[key];
  adaptationChanged();
});
listen(host,'pointerup',()=>{cropDrag=null;});listen(host,'pointercancel',()=>{cropDrag=null;});

async function chooseNarrativeSource(kind, attach = false) {
  await save();
  const sources = await api('/api/narrative/sources?kind='+kind);
  const destination = await api(`/api/narrative/stories/${route.story}/scenes/${route.scene}`);
  sourcePicker = {kind,attach,sources:sources.filter(source=>source.scene_id!==route.scene || source.story_id!==route.story),elements:destination.elements};
  const stories = [...new Map(sourcePicker.sources.map(source=>[source.story_id,source.story_title])).entries()];
  const dialog = host.querySelector('#narrative-source-dialog');
  dialog.innerHTML = `<h2>${kind==='backdrop'?'Reference backdrop':'Import subscene'}</h2><form id="narrative-source-form">
    <label class="narrative-field">Source story<select id="source-story">${stories.map(([id,name])=>`<option value="${id}" ${id===route.story?'selected':''}>${esc(name)}</option>`).join('')}</select></label>
    <label class="narrative-field">Source scene and target<select id="source-target"></select></label>
    <label class="narrative-field">Source candidate<select id="source-candidate"></select></label>
    <div id="source-preview"></div><p class="error" id="source-picker-error" role="status"></p>
    ${attach ? '' : '<label class="narrative-field">New target title<input id="source-title" required></label><label><input id="source-copy-context" type="checkbox"> Copy source visual context as local overrides</label>'}
    <div class="narrative-actions"><button class="primary" id="source-apply">${attach?'Attach pinned source':kind==='backdrop'?'Create referenced backdrop':'Import subscene'}</button><button type="button" data-close="narrative-source-dialog">Cancel</button></div></form>`;
  if (kind === 'backdrop') { const copyContext=host.querySelector('#source-copy-context'); if(copyContext)copyContext.parentElement.hidden=true; }
  dialog.showModal();
  await populateSourceTargets();
}

async function populateSourceTargets() {
  const story = host.querySelector('#source-story').value;
  const targets = sourcePicker.sources.filter(source=>source.story_id===story);
  host.querySelector('#source-target').innerHTML = targets.map(source=>`<option value="${source.target_id}">${esc(source.scene_title)} · ${esc(source.title)}</option>`).join('');
  await populateSourceCandidates();
}

function chosenSource() {
  const source = sourcePicker.sources.find(source=>source.target_id===host.querySelector('#source-target').value);
  return source ? {story_id:source.story_id,scene_id:source.scene_id,target_id:source.target_id,candidate_id:host.querySelector('#source-candidate').value || null} : null;
}

async function populateSourceCandidates() {
  const source = sourcePicker.sources.find(source=>source.target_id===host.querySelector('#source-target').value);
  host.querySelector('#source-candidate').innerHTML = '<option value="">'+(sourcePicker.kind==='subscene'?'Text only / no image needed':'Choose a completed candidate')+'</option>'+(source?.candidates||[]).map(candidate=>`<option value="${candidate.id}" ${candidate.id===source.selected_id?'selected':''}>Slot ${candidate.slot}${candidate.id===source.selected_id?' · Selected':''}</option>`).join('');
  await previewNarrativeSource();
}

async function previewNarrativeSource() {
  const choice = chosenSource();
  const picker = sourcePicker;
  picker.preview = null;
  host.querySelector('#source-preview').innerHTML = '';
  host.querySelector('#source-picker-error').textContent = '';
  host.querySelector('#source-apply').disabled = true;
  if (!choice) {host.querySelector('#source-picker-error').textContent='No sources in another scene.';return;}
  if (picker.kind==='backdrop' && !choice.candidate_id) {host.querySelector('#source-picker-error').textContent='Choose a completed source candidate.';return;}
  const request = JSON.stringify(choice);
  const preview = await api('/api/narrative/sources/preview','POST',choice);
  if (sourcePicker!==picker || request!==JSON.stringify(chosenSource())) return;
  picker.preview = preview;
  host.querySelector('#source-preview').innerHTML = `${preview.candidate_id ? `<img class="narrative-source-preview" alt="Source candidate preview" src="/api/narrative/stories/${choice.story_id}/scenes/${choice.scene_id}/targets/${choice.target_id}/candidates/${preview.candidate_id}/image?universe_id=${encodeURIComponent(universe)}">` : ''}${sourceTextHtml(preview)}
    ${picker.kind==='subscene' ? `<h3>Imported elements</h3>${preview.current_inputs.elements.map(element=>`<label class="narrative-field">${esc(element.name)}<select data-source-element="${element.id}"><option value="">Create independent local copy</option>${picker.elements.map(local=>`<option value="${local.id}">Use existing: ${esc(local.name)}</option>`).join('')}</select></label>`).join('')}` : ''}`;
  const name = host.querySelector('#source-title');
  if (name) name.value = preview.title;
  host.querySelector('#source-apply').disabled = false;
}

function adaptationChanged() {
  detail.backdrop_adaptation = {...detail.backdrop_adaptation,operation:host.querySelector('#backdrop-operation').value,
    direction:host.querySelector('#backdrop-direction').value,expand_side:host.querySelector('#backdrop-expand-side').value,
    crop_enabled:host.querySelector('#backdrop-crop-enabled').value==='yes',
    crop:Object.fromEntries(['x','y','width','height'].map(key=>[key,Number(host.querySelector(`#backdrop-crop-${key}`).value)]))};
  dirty.add('backdrop_adaptation');
  clearTimeout(saveTimer);saveTimer=setTimeout(()=>save().catch(error=>status(error.message,true)),700);
  const preview=host.querySelector('#backdrop-crop-preview');if(preview)preview.hidden=true;
  sourceVisibility();drawCropBox();
}

function renderTarget(targets) {
  const backdrop = detail.kind === 'backdrop';
  const assembly = detail.kind === 'assembly';
  const viewingImages = window.matchMedia("(max-width: 1360px)").matches && detail.slots.some(id => id && detail.candidates[id]?.image);
  root.innerHTML = `<h1 class="narrative-target-heading"><select id="narrative-target-select" aria-label="Scene page">${targetsWithAssemblyLast(targets).map(target=>`<option value="${target.id}" ${target.id === route.target ? 'selected' : ''}>${esc(target.title)} · ${title(target.kind)}</option>`).join('')}</select></h1>
    <div class="narrative-editor narrative-target-editor ${viewingImages ? 'has-images' : ''}"><details class="narrative-direction-settings" ${viewingImages ? '' : 'open'}><summary>Scene direction and references</summary><div>${sourcePanelHtml()}<section class="narrative-card"><h2>${backdrop ? 'Environment direction' : 'The moment'}</h2>
      <label>Universe style<select data-field="universe_style_variant"><option value="inherit" ${detail.universe_style_variant==='inherit'?'selected':''}>Inherit scene</option><option value="canonical" ${detail.universe_style_variant==='canonical'?'selected':''}>Canonical</option><option value="environmental" ${detail.universe_style_variant==='environmental'?'selected':''}>Environmental</option></select></label>
      ${label('title',detail.title,false)}${label('narrative',detail.narrative,true,backdrop ? 'Describe the environment' : 'Describe what is happening')}
      ${label('staging',detail.staging,true,backdrop ? 'Environment composition' : 'Interaction and staging')}${label('physical_context',detail.physical_context)}
      ${detail.kind === 'subscene' ? `<label><input type="checkbox" id="narrative-use_transparent_background" data-field="use_transparent_background" ${detail.use_transparent_background ? 'checked' : ''}> Use transparent background</label><p class="narrative-muted">Interview and Write Prompt use transparency instead of visible scenery, including Setting. Camera, subject lighting and required supports still apply. Use Write Prompt to update existing prompt text; Render sends your edited prompt exactly as entered.</p>` : ''}
      ${label('framing',detail.framing,false)}<div class="narrative-grid">${label('width',detail.width,false)}${label('height',detail.height,false)}</div>
      <div class="narrative-actions"><button data-action="save">Save inputs</button><button class="danger" data-action="delete">Delete ${assembly ? 'assembly' : backdrop ? 'backdrop' : 'subscene'}</button></div></section>
    ${assembly ? `<section class="narrative-card"><h2>Scene text</h2><button data-action="scene-text" ${detail.selected_id?"":"disabled"}>Edit selected image text</button><button data-action="scene-text-raw">Edit raw composite text draft</button></section>`+assemblyHtml() : `<section class="narrative-card"><h2>Participants and references</h2><div id="narrative-elements">${elementsHtml(detail.elements,true)}</div>
      <div class="narrative-actions"><button data-action="assign-elements">Assign scene elements</button><button data-action="new-element">New element / library reference</button></div></section>`}
    <section class="narrative-card"><h2>Shared visual context</h2><p class="narrative-muted">Interview input · Interview may propose changes. Shared values apply across this scene; local overrides replace them for this target.</p>
      <p class="narrative-muted">Style source: ${esc(detail.style_source || 'saved scene')}</p>
      <dl class="narrative-context">${visualFields.map(key=>`<dt>${title(key)} · Shared</dt><dd data-shared-visual="${key}"></dd><dt>${title(key)} · Effective</dt><dd data-effective-visual="${key}"></dd>`).join('')}</dl>
      <details><summary id="narrative-overrides-summary">Local overrides</summary>${visualFields.map(key=>label(`override_${key}`,detail.visual_overrides[key] || '',true,`${title(key)} override (blank inherits)`)).join('')}<button data-action="save">Save inputs</button></details></section>
    <section class="narrative-card"><h2>Interview</h2>${modelControl('interview_model')}<p class="narrative-muted" id="narrative-interview-effective"></p><p id="narrative-interview-status" role="status" aria-live="polite"></p><div id="narrative-interview" class="narrative-history"></div>
      <label class="narrative-field">Answer or direct a revision<textarea id="narrative-direction" placeholder="Describe what is happening, answer a question, or ask for a change."></textarea></label>
      <div class="narrative-actions"><button class="primary" data-action="interview">Continue interview</button><button data-action="rerun_interview">Re-run last interview</button></div><div id="narrative-pending-reviews"></div><p class="narrative-muted">Interview revisions are proposals until you Apply them. Answers are optional; edit directly or generate whenever you are ready.</p></section></div>
    </details><div class="narrative-output"><details class="narrative-card narrative-generation-settings" ${viewingImages ? '' : 'open'}><summary>Prompt and generation</summary>${assembly ? `<label class="narrative-field">Assembly mode<select id="narrative-assembly_mode" data-field="assembly_mode"><option value="finish_composite" ${detail.assembly_mode==='finish_composite'?'selected':''}>Finish placed composite</option><option value="assemble_references" ${detail.assembly_mode==='assemble_references'?'selected':''}>Assemble from references</option><option value="harmonize_composite" ${detail.assembly_mode==='harmonize_composite'?'selected':''}>Harmonize placed composite</option></select></label><p id="narrative-assembly-help" class="narrative-muted"></p><p id="narrative-assembly-prompt-warning" class="error" role="status"></p>` : ''}${modelControl('prompt_model')}<p class="narrative-muted" id="narrative-prompt-effective"></p>
      <datalist id="narrative-model-options"></datalist><p id="narrative-model-error" class="error"></p>
      ${label('prompt',detail.prompt,true,'Final Qwen prompt')}<p id="narrative-prompt-origin" class="narrative-muted"></p>
      <details><summary>Previous prompt outputs</summary><select id="narrative-prompt-history" aria-label="Previous prompt outputs"></select><pre id="narrative-prompt-preview"></pre></details>
      <div class="narrative-actions"><button class="primary" data-action="synthesize">Write Prompt</button></div><p id="narrative-prompt-pending" class="narrative-muted"></p>
      <div class="narrative-actions"><button class="primary" data-action="render" data-count="1">Render 1</button><button class="primary" data-action="render" data-count="4">Render 4</button><button data-action="refresh">Refresh</button></div>
      <p class="narrative-muted">Write Prompt replaces the prompt above. Render sends that text exactly as entered.</p>
      <div id="narrative-job-status" role="status" aria-live="polite"></div></details>
    <section id="narrative-images-card" class="narrative-card"><h2>Images</h2><div id="narrative-slots" class="narrative-slots"></div></section></div></div>`;
  sourceVisibility();
  enableModelPickers();
  updateLive();
  loadModels();
  if (assembly) renderLayers();
  const sourceImage = host.querySelector('#backdrop-source-image');
  if (sourceImage) { listen(sourceImage,'load',drawCropBox); drawCropBox(); }
}

function pendingInterviews() {
  return Object.values(detail.jobs).filter(job=>job.status === 'COMPLETE' && job.review?.status === 'pending');
}

function reviewChoices(job) {
  const key = `${universe}:${base()}:${job.id}`;
  if (!interviewChoices.has(key)) interviewChoices.set(key, Object.fromEntries(job.review.proposals.map(row=>[row.id, {action:row.scope === 'visual' ? 'override' : 'accept', explicit:false}])));
  return interviewChoices.get(key);
}

function openInterviewReview(id) {
  if (!detail.jobs[id]?.review || detail.jobs[id].review.status !== 'pending') return;
  interviewReviewId = id;
  renderInterviewReview();
  const dialog = host.querySelector('#narrative-interview-review');
  if (!dialog.open) dialog.showModal();
}

function renderInterviewReview() {
  const job = detail.jobs[interviewReviewId];
  if (!job?.review) return;
  const choices = reviewChoices(job);
  const review = job.review;
  host.querySelector('#narrative-interview-review').innerHTML = `<h2 id="interview-review-title">Review interview proposals</h2>
    <p class="narrative-muted">Choose whole-field replacements below. Nothing changes until Apply.</p>
    ${review.conflicts.length ? `<section><h3>Conflicts and resolutions</h3>${review.conflicts.map(text=>`<p>${esc(text)}</p>`).join('')}</section>` : ''}
    ${review.questions.length ? `<section><h3>Questions for the next interview</h3>${review.questions.map(text=>`<p>${esc(text)}</p>`).join('')}</section>` : ''}
    <div class="narrative-actions"><button data-review-bulk="override">Accept All (override)</button><button data-review-bulk="shared">Accept All (shared)</button><button data-review-bulk="reject">Reject All</button></div>
    <p class="narrative-muted">Bulk choices affect only rows you have not explicitly chosen.</p>
    ${review.proposals.map(row=>`<article class="narrative-proposal" data-proposal-id="${row.id}"><h3>${esc(row.element_name ? row.element_name+' · Appearance notes' : title(row.field))}</h3>
      <p>${esc(row.reason)}</p>${row.scope === 'appearance' ? '<p class="narrative-muted">Shared appearance: affects every subscene using this element.</p>' : ''}
      ${row.scope === 'visual' ? `<p class="narrative-muted">Shared: ${esc(job.detail.inherited_context?.[row.field] || 'Not specified')}<br>Local override: ${esc(job.detail.visual_overrides?.[row.field] || 'None — inherits shared')}</p>` : ''}
      <div class="narrative-proposal-comparison"><section><h4>Old${row.scope === 'visual' ? ' · Effective' : ''}</h4><pre>${esc(row.old)}</pre></section><section><h4>New</h4><pre>${esc(row.text)}</pre></section></div>
      <div class="narrative-actions" role="group" aria-label="${esc(row.element_name || title(row.field))} action">${(row.scope === 'visual' ? ['override','shared','reject'] : ['accept','reject']).map(choice=>`<button data-proposal="${row.id}" data-proposal-choice="${choice}" aria-pressed="${choices[row.id].action === choice}">${title(choice)}</button>`).join('')}</div></article>`).join('') || '<p>No field changes proposed.</p>'}
    <div class="narrative-actions narrative-review-footer"><button class="primary" data-apply-interview="${job.id}">Apply</button><button data-close="narrative-interview-review">Close</button></div>
    <p id="narrative-interview-review-error" class="error" role="status"></p>`;
}

function refreshVisualContext() {
  const overrides = visualFields.filter(key=>Boolean(host.querySelector(`[data-field="override_${key}"]`)?.value));
  host.querySelector('#narrative-overrides-summary').textContent = `Local overrides${overrides.length ? ` · ${overrides.length}: ${overrides.map(title).join(', ')}` : ' · None'}`;
  for (const key of visualFields) {
    const override = host.querySelector(`[data-field="override_${key}"]`).value;
    host.querySelector(`[data-shared-visual="${key}"]`).textContent = detail.inherited_context[key] || 'Not specified';
    const transparent = detail.kind === 'subscene' && host.querySelector('#narrative-use_transparent_background')?.checked;
    host.querySelector(`[data-effective-visual="${key}"]`).textContent = key === 'setting' && transparent
      ? `Visible scenery suppressed · Use transparent background. Saved setting: ${override || detail.inherited_context[key] || 'Not specified'} · ${override ? 'Local override' : 'Shared'}`
      : `${override || detail.inherited_context[key] || 'Not specified'} · ${override ? 'Local override' : 'Shared'}`;
  }
}

function promptIndicator(candidate) {
  if (!candidate?.image || candidate.status !== 'COMPLETE') return '';
  const operation = candidate.backdrop_adaptation?.operation;
  if (candidate.source_snapshot && ['crop','unchanged'].includes(operation)) return `<span class="narrative-prompt-indicator">${operation === 'crop' ? 'Local crop' : 'Local reuse'}</span>`;
  if (typeof candidate.prompt !== 'string' || !candidate.prompt) return '<span class="narrative-prompt-indicator">Prompt not recorded</span>';
  const normalize = text=>text.replace(/\r\n?/g,'\n');
  const current = host.querySelector('#narrative-prompt')?.value ?? detail.prompt;
  return normalize(candidate.prompt) === normalize(current) ? '' : '<span class="narrative-prompt-indicator" title="Rendered with a different prompt than the current prompt." aria-label="Rendered with a different prompt than the current prompt.">Different prompt</span>';
}

function updatePromptIndicators() {
  for (const node of host.querySelectorAll('[data-prompt-indicator]')) {
    const html = promptIndicator(detail.candidates[node.dataset.promptIndicator]);
    if (node.innerHTML !== html) node.innerHTML = html;
  }
}

function updateLive() {
  if (disposed) return;
  const history = host.querySelector('#narrative-interview');
  if (!history) return;
  const jobs = Object.values(detail.jobs);
  refreshVisualContext();
  const pending = pendingInterviews();
  host.querySelector('#narrative-pending-reviews').innerHTML = pending.map(job=>`<button data-interview-review="${job.id}">Review interview proposals · ${job.review.proposals.length} changes</button>`).join('');
  host.querySelector('#narrative-prompt-pending').textContent = pending.length ? `${pending.length} interview review${pending.length === 1 ? '' : 's'} pending. Write Prompt uses saved, applied inputs.` : '';
  const signatureHistory = JSON.stringify([detail.interview, jobs.filter(job=>job.kind!=='image').map(job=>[job.id,job.status,job.result,job.review?.status])]);
  if (signatureHistory !== historySignature) {
    const replies = detail.interview.filter(item=>item.role === 'assistant').length;
    const newReply = Boolean(historySignature) && replies > interviewReplies;
    interviewReplies = replies;
    historySignature = signatureHistory;
    history.innerHTML = detail.interview.map(item=>`<article class="narrative-history-entry"><p><strong>${item.role === 'user' ? 'You' : `Illustrator · ${esc(modelName(item.provenance))}`}</strong><br>${esc(item.text || (item.draft ? 'Draft updated.' : item.role === 'assistant' ? 'Interview proposals received.' : 'Continue the interview.'))}</p>${(item.conflicts || []).map(text=>`<p>${esc(text)}</p>`).join('')}${item.draft ? `<details><summary>Generated draft</summary><dl>${Object.entries(item.draft).map(([key,value])=>`<dt>${title(key)}</dt><dd>${esc(value)}</dd>`).join('')}</dl></details>` : ''}</article>`).join('');
    if (newReply) {
      const latest = history.lastElementChild;
      latest.classList.add('narrative-new-reply');
      history.scrollTop = latest.offsetTop;
      const notice = host.querySelector('#narrative-interview-status');
      notice.textContent = 'New interview proposals received — ready for review.';
      notice.className = 'narrative-complete';
      if (pending.length) openInterviewReview(pending.at(-1).id);
    }
    const select = host.querySelector('#narrative-prompt-history');
    const value = select.value;
    select.innerHTML = '<option value="">Choose a previous prompt</option>'+jobs.filter(job=>['synthesize','generate'].includes(job.kind)&&typeof job.result==='string').map((job,index)=>`<option value="${job.id}">${index+1} · ${esc(modelName(job.provenance))}${detail.kind==='assembly' ? ' · '+assemblyModeName(job.detail.assembly_mode) : ''}</option>`).join('');
    select.value = value;
  }
  host.querySelector('#narrative-prompt-origin').textContent = `${modelName(detail.prompt_provenance)}${detail.prompt_provenance?.edited || dirty.has('prompt') ? ' · Manually edited' : ''}`;
  if (detail.kind === 'assembly') {
    const mode = host.querySelector('#narrative-assembly_mode').value;
    const stale = !dirty.has('prompt') && (detail.prompt_provenance?.assembly_mode || 'finish_composite') !== mode;
    host.querySelector('#narrative-assembly-help').textContent = mode === 'assemble_references'
      ? 'Qwen assembles original sources using placement and depth instructions. Cutout corrections affect the placement preview and composite modes. Exact placement may vary. Up to ten visible sources.'
      : mode === 'harmonize_composite'
        ? 'Qwen harmonizes the placed composite, including cutout corrections, lighting, color, edges and ground contact. The full generated image is retained; subject appearance can change and placement may drift.'
        : 'Qwen finishes the placed composite; seam and shadow blending preserves subject pixels.';
    host.querySelector('#narrative-assembly-prompt-warning').textContent = stale && detail.prompt ? 'This prompt belongs to another assembly mode. Write or edit the prompt before rendering.' : '';
    for (const button of root.querySelectorAll('[data-action="render"]')) button.disabled = stale;
  }
  for (const type of ['interview','prompt']) host.querySelector(`#narrative-${type}-effective`).textContent = `Next run: ${host.querySelector(`#narrative-${type}_model`).value || modelOptions.model}`;
  const working = jobs.filter(job=>active.has(job.status));
  const llmWorking = llmSubmitting || working.some(job=>job.kind !== 'image');
  const prompt = host.querySelector('#narrative-prompt');
  if (llmWorking && document.activeElement === prompt) prompt.blur();
  prompt.disabled = llmWorking;
  prompt.setAttribute('aria-busy', String(llmWorking));
  const promptActions = ['interview','rerun_interview','synthesize','render'];
  for (const button of root.querySelectorAll('[data-action]')) {
    if (promptActions.includes(button.dataset.action)) button.disabled = busy || llmWorking || (button.dataset.action === 'render' && detail.kind==='backdrop' && detail.source_snapshot?.image_file && ['crop','unchanged'].includes(detail.backdrop_adaptation?.operation)) || (button.dataset.action === 'render' && Boolean(host.querySelector('#narrative-assembly-prompt-warning')?.textContent));
  }
  const interviewJob = working.find(job=>job.kind === 'interview');
  if (interviewJob) {
    const notice = host.querySelector('#narrative-interview-status');
    notice.textContent = `Interview ${interviewJob.status.toLowerCase()} · Waiting for an answer…`;
    notice.className = 'narrative-pending';
  } else if (host.querySelector('#narrative-interview-status').className === 'narrative-pending') {
    host.querySelector('#narrative-interview-status').textContent = '';
    host.querySelector('#narrative-interview-status').className = '';
  }
  const lastAuthorJob = jobs.filter(job=>job.kind !== 'image').at(-1);
  const failures = lastAuthorJob?.status === 'FAILED' ? [lastAuthorJob] : [];
  host.querySelector('#narrative-job-status').innerHTML = `<p class="${working.length || llmSubmitting ? 'narrative-pending' : 'narrative-muted'}">${working.length ? working.map(job=>`${esc(job.kind)}: ${esc(job.status.toLowerCase())}${job.kind !== 'image' ? ' · '+esc(job.model || 'Model not recorded') : ''}`).join(' · ') : llmSubmitting ? 'Submitting LLM request…' : 'Ready'}${llmWorking ? ' · Final prompt is unavailable until the LLM finishes.' : ''}</p>`+
    failures.filter(job=>job.kind !== 'image').map(job=>`<div class="narrative-failure">${esc(modelName(job.provenance))} · ${esc(job.error)}${job.kind === 'interview' ? ` <button data-retry-job="${job.id}">Retry</button>` : ''}</div>`).join('');
  updatePromptIndicators();
  const signature = JSON.stringify([detail.slots,detail.candidates,detail.selected_id]);
  if (signature === slotSignature) return;
  slotSignature = signature;
  host.querySelector('#narrative-slots').innerHTML = detail.slots.map((id,index)=>{
    const candidate = id ? detail.candidates[id] : null;
    return `<article class="narrative-slot ${id && id === detail.selected_id ? 'selected' : ''}" data-state="${candidate?.locked ? 'locked' : id && id === detail.selected_id ? 'selected' : candidate?.status === 'FAILED' ? 'failed' : candidate?.image ? 'available' : candidate ? 'pending' : 'empty'}"><h3>Slot ${index+1} <span data-prompt-indicator="${id || ''}">${promptIndicator(candidate)}</span></h3>
      ${candidate?.image ? `<img src="${esc(imageUrl(id))}" alt="Slot ${index+1} candidate" data-review="${id}">` : `<div class="placeholder">${candidate ? '' : 'Empty'}</div>`}
      ${candidate ? `<p class="narrative-muted image-card-state">${esc(candidate.status.toLowerCase())}${id === detail.selected_id ? ' · Selected' : ''}${candidate.locked ? ' · Locked' : ''}${candidate.scene_text_pending ? ' · Scene text changes pending' : ''}</p>
      ${candidate.error ? `<p class="error">${esc(candidate.error)}</p>` : ''}
      <div class="narrative-actions narrative-review-actions"><button data-review="${id}" aria-label="Review slot ${index+1}">Review</button>${candidate.image ? `<button data-candidate="${id}" data-candidate-action="select" class="${id !== detail.selected_id ? 'primary' : ''}" ${id === detail.selected_id ? 'disabled' : ''}>${id === detail.selected_id ? 'Selected' : 'Select'}</button>` : ''}
      ${!candidate.locked && id !== detail.selected_id ? `<button data-render-slot="${index+1}">${candidate.status === 'FAILED' ? 'Retry' : 'Regenerate'}</button>` : ''}
      <button data-candidate="${id}" data-candidate-action="clear" class="danger-text-action">Clear slot</button>${candidate.image ? `<button data-candidate="${id}" data-candidate-action="${candidate.locked ? 'unlock' : 'lock'}">${candidate.locked ? 'Unlock' : 'Lock'}</button>` : ''}</div>`
      : `<div class="narrative-actions"><button class="primary" data-render-slot="${index+1}">Generate</button></div>`}</article>`;
  }).join('');
  renderImageReview();
}

function reviewImages() {
  // Occupied slots retain prompt/source inspection even before an image exists.
  return detail?.slots.filter(id=>id && detail.candidates[id]) || [];
}

function renderImageReview() {
  if (disposed) return;
  const dialog = host.querySelector('#image-dialog');
  if (!dialog.open) return;
  const images = reviewImages();
  if (!images.length) { dialog.close(); reviewCandidate = null; return; }
  if (!images.includes(reviewCandidate)) reviewCandidate = images[0];
  const candidate = detail.candidates[reviewCandidate];
  const index = images.indexOf(reviewCandidate);
  const selected = reviewCandidate === detail.selected_id;
  const image = host.querySelector('#review-image');
  image.hidden = !candidate.image;
  if (candidate.image) image.src = imageUrl(reviewCandidate);
  else image.removeAttribute('src');
  let placeholder = image.parentElement.querySelector('.image-review-placeholder');
  if (!placeholder) {
    placeholder = document.createElement('p'); placeholder.className = 'image-review-placeholder';
    placeholder.textContent = 'No image available yet.'; image.after(placeholder);
  }
  placeholder.hidden = Boolean(candidate.image);
  host.querySelector('#review-image').alt = `Slot ${candidate.slot} candidate`;
  host.querySelector('#narrative-review-prev').disabled = busy || index === 0;
  host.querySelector('#narrative-review-next').disabled = busy || index === images.length - 1;
  if(!dialog.querySelector('[data-clean-view]')){const toggle=document.createElement('button');toggle.dataset.cleanView='';toggle.textContent='Hide review controls';toggle.onclick=()=>{const clean=dialog.classList.toggle('narrative-clean-view');toggle.textContent=clean?'Show review controls':'Hide review controls';};dialog.append(toggle);}
  const panel = host.querySelector('#narrative-review-panel');
  const sameCandidate = panel.dataset.candidate === reviewCandidate;
  const focusedAction = panel.contains(document.activeElement) ? document.activeElement.dataset.imageAction : "";
  const previousDetails = panel.querySelector('details');
  const detailsOpen = sameCandidate && previousDetails?.open;
  const detailsScroll = sameCandidate ? panel.scrollTop : 0;
  panel.dataset.candidate = reviewCandidate;
  panel.innerHTML = `<h2>${esc(detail.title)} · Slot ${candidate.slot} <span data-prompt-indicator="${reviewCandidate}">${promptIndicator(candidate)}</span></h2>
    <p class="local-pipeline-review-position">${index+1} of ${images.length} · ${esc(candidate.status.toLowerCase())}${selected ? ' · Selected' : ''}${candidate.locked ? ' · Locked' : ''}${candidate.scene_text_pending ? ' · Scene text changes pending' : ''}</p>
    <div class="button-row compact local-pipeline-review-actions">
      ${detail.kind==='assembly' ? `<button data-scene-text-candidate="${reviewCandidate}" ${candidate.locked?"disabled":""}>Edit text</button>` : ''}<button class="primary" data-candidate="${reviewCandidate}" data-candidate-action="select" ${busy || selected || !candidate.image ? 'disabled' : ''}>Select</button>
      <button data-render-slot="${candidate.slot}" ${busy || selected || candidate.locked ? 'disabled' : ''}>Regenerate</button>
      <button class="danger" data-candidate="${reviewCandidate}" data-candidate-action="clear" ${busy ? 'disabled' : ''}>Clear slot</button>
      <button data-candidate="${reviewCandidate}" data-candidate-action="${candidate.locked ? 'unlock' : 'lock'}" ${busy || !candidate.image ? 'disabled' : ''}>${candidate.locked ? 'Unlock' : 'Lock'}</button>
    </div>
    <p class="error" role="status" id="narrative-review-error"></p>
    ${candidate.error ? `<p class="error">${esc(candidate.error)}</p>` : ''}
    <details ${detailsOpen ? 'open' : ''}><summary>Prompt and source ${copyPromptButton(reviewCandidate)}</summary><p class="narrative-muted">${esc(modelName(candidate.prompt_provenance))}${candidate.prompt_provenance?.edited ? ' · Manually edited' : ''}${candidate.assembly_snapshot ? ' · '+assemblyModeName(candidate.assembly_mode) : ''}</p>
    <pre>${esc(candidate.prompt || 'Prompt not recorded')}</pre>
    ${candidate.source_snapshot ? `<p class="narrative-muted">Source: ${esc(candidate.source_snapshot.scene_title)} · ${esc(candidate.source_snapshot.title)} · ${esc(candidate.backdrop_adaptation?.operation || 'edit')}</p>` : ''}
    ${candidate.assembly_snapshot ? `${(candidate.assembly_snapshot.has_composite ?? (candidate.assembly_snapshot.assembly_mode || 'finish_composite')==='finish_composite') ? `<a href="${esc(artifactUrl(`candidates/${reviewCandidate}/composite`))}" target="_blank">Compare raw composite</a>` : ''}<p>${candidate.assembly_snapshot.layers.filter(layer=>layer.visible).map(layer=>esc(layer.label)).join(' · ')}</p>` : ''}
    </details>`;
  window.ZetImageCardUI.scan(panel);
  if (sameCandidate && focusedAction) [...panel.querySelectorAll("button,a")]
    .find(button => button.dataset.imageAction === focusedAction)?.focus({ preventScroll: true });
  panel.scrollTop = detailsScroll;
}

function mergeTarget(updated) {
  if (dirty.has('layers') || layerDrag || brush) updated.layers = detail.layers;
  if (dirty.has('backdrop_adaptation') || cropDrag) updated.backdrop_adaptation = detail.backdrop_adaptation;
  for (const key of targetFields) {
    const field = root.querySelector(`[data-field="${key}"]`);
    if (field && !dirty.has(key) && (document.activeElement !== field || field.disabled)) {
      if (field.type === 'checkbox') field.checked = updated[key];
      else field.value = updated[key];
    }
  }
  for (const key of visualFields) {
    const field = root.querySelector(`[data-field="override_${key}"]`);
    if (field && !dirty.has(`override_${key}`) && document.activeElement !== field) field.value = updated.visual_overrides[key] || '';
  }
  if (JSON.stringify(detail.elements) !== JSON.stringify(updated.elements)) {
    const list = root.querySelector('#narrative-elements');
    if (list) list.innerHTML = elementsHtml(updated.elements,true);
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
    if (field) payload[key] = ['width','height'].includes(key) ? Number(field.value) : fieldValue(field);
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
      if (field && String(fieldValue(field)) === String(value)) dirty.delete(key);
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
  if (disposed) return;
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
  const direction = host.querySelector('#narrative-direction');
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
  const dialog = host.querySelector('#element-dialog');
  dialog.innerHTML = `<h2>${id ? 'Edit' : 'New'} element</h2><form id="element-form">
    <label class="narrative-field">Name<input name="name" required value="${esc(elementDraft.name)}"></label>
    <label class="narrative-field">Type<select name="kind">${['subject','prop','environment'].map(kind=>`<option ${kind===elementDraft.kind ? 'selected' : ''}>${kind}</option>`).join('')}</select></label>
    <label class="narrative-field">Appearance notes<small class="narrative-field-role">Interview input · Interview may propose changes · Shared across subscenes</small><textarea name="appearance">${esc(elementDraft.appearance)}</textarea><small class="narrative-field-help">${esc(scene.field_purposes.appearance)}</small></label>
    <label class="narrative-field">Reference role<select name="reference_role">${['appearance','costume','object shape','environment','style'].map(role=>`<option ${role===elementDraft.reference_role ? 'selected' : ''}>${role}</option>`).join('')}</select></label>
    <p id="element-reference-label">${elementDraft.reference_key ? 'Current reference: '+esc(elementDraft.reference_key) : elementDraft.asset_id ? 'Reference image attached' : 'Text only — no reference image'}</p>
    <div class="narrative-actions"><button type="button" id="choose-reference">Choose library image</button><button type="button" id="remove-reference">Remove reference</button></div>
    <div class="narrative-actions"><button class="primary">Save element</button><button type="button" data-close="element-dialog">Cancel</button></div></form>`;
  dialog.showModal();
}

async function librarySearch() {
  const query = host.querySelector('#library-query').value;
  const assets = await api('/api/narrative/library?q='+encodeURIComponent(query));
  host.querySelector('#library-results').innerHTML = assets.map(asset=>`<button type="button" data-library-asset="${esc(asset.asset_id)}" data-label="${esc(asset.label)}" data-reference-key="${esc(asset.reference_key || '')}"><img src="${esc(assetUrl(asset.asset_id))}" alt="${esc(asset.label)}"><span>${esc(asset.label)}</span></button>`).join('') || '<p>No matching images.</p>';
}

async function assignElements() {
  await save();
  const scene = await api(`/api/narrative/stories/${route.story}/scenes/${route.scene}`);
  const dialog = host.querySelector('#membership-dialog');
  dialog.innerHTML = `<h2>Assign elements to ${esc(detail.title)}</h2><form id="membership-form"><div class="narrative-membership-list">${scene.elements.map(element=>`<label class="narrative-membership-row"><input type="checkbox" name="element" value="${element.id}" ${detail.element_ids.includes(element.id) ? 'checked' : ''}> <span>${esc(element.name)} · ${esc(element.kind)}</span></label>`).join('') || '<p>Create an element first.</p>'}</div><div class="narrative-actions"><button class="primary">Save assignments</button><button type="button" data-close="membership-dialog">Cancel</button></div></form>`;
  dialog.showModal();
}

listen(host,'input',event=>{
  if (event.target.id==='backdrop-link-mode') return;
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

listen(host,'change',event=>{
  if (event.target.id==='backdrop-link-mode') {const mode=event.target.value;action(async()=>{await save();await api(base(),'PATCH',{backdrop_link_mode:mode});await loadPage();});return;}
  if (event.target.id==='source-story') {populateSourceTargets().catch(error=>status(error.message,true));return;}
  if (event.target.id==='source-target') {populateSourceCandidates().catch(error=>status(error.message,true));return;}
  if (event.target.id==='source-candidate') {previewNarrativeSource().catch(error=>status(error.message,true));return;}
  if (event.target.id==='narrative-prompt-history') {host.querySelector('#narrative-prompt-preview').textContent=detail.jobs[event.target.value]?.result||'';return;}
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

listen(host,'click',event=>{
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
  if (button.dataset.moveScene) {
    const from = detail.scenes.findIndex(scene => scene.id === button.dataset.moveScene);
    const to = from + Number(button.dataset.direction);
    if (from < 0 || to < 0 || to >= detail.scenes.length) return;
    action(async()=>{
      await save();
      const scenes = [...detail.scenes];
      [scenes[from], scenes[to]] = [scenes[to], scenes[from]];
      await api(base(),'PATCH',{scene_ids:scenes.map(scene=>scene.id)});
      detail.scenes = scenes;
      renderStoryScenes(scenes);
      root.querySelector(`[data-move-scene="${scenes[to].id}"][data-direction="${button.dataset.direction}"]`)?.focus();
      status('Scene order saved');
    });
    return;
  }
  if (button.dataset.interviewReview) { openInterviewReview(button.dataset.interviewReview); return; }
  if (button.dataset.proposalChoice) {
    const choices = reviewChoices(detail.jobs[interviewReviewId]);
    choices[button.dataset.proposal] = {action:button.dataset.proposalChoice, explicit:true};
    for (const control of button.parentElement.querySelectorAll('button')) control.setAttribute('aria-pressed',String(control === button));
    return;
  }
  if (button.dataset.reviewBulk) {
    const job = detail.jobs[interviewReviewId], choices = reviewChoices(job);
    for (const row of job.review.proposals) if (!choices[row.id].explicit) choices[row.id].action = button.dataset.reviewBulk === 'reject' ? 'reject' : row.scope === 'visual' ? button.dataset.reviewBulk : 'accept';
    renderInterviewReview(); return;
  }
  if (button.dataset.applyInterview) {
    action(async()=>{
      const job = detail.jobs[button.dataset.applyInterview];
      const choices = Object.fromEntries(Object.entries(reviewChoices(job)).map(([id,choice])=>[id,choice.action]));
      await save();
      mergeTarget(await api(base()+'/interview-review','POST',{job_id:job.id, choices}));
      host.querySelector('#narrative-interview-review').close();
      interviewReviewId = null;
      status('Interview choices applied');
    });
    return;
  }
  if (button.id === 'new-story-button') {
    host.querySelector('#new-narrative-story').reset();
    host.querySelector('#story-dialog').showModal(); return;
  }
  if (button.matches('[data-navigate]') || button.id === 'narrative-home') {
    event.preventDefault(); action(()=>navigate(button.href)); return;
  }
  if (button.dataset.review) {
    reviewCandidate = button.dataset.review;
    delete host.querySelector('#narrative-review-panel').dataset.candidate;
    host.querySelector('#image-dialog').showModal(); renderImageReview(); return;
  }
  if (button.id === 'narrative-review-prev' || button.id === 'narrative-review-next') {
    const images = reviewImages();
    const index = images.indexOf(reviewCandidate) + (button.id === 'narrative-review-prev' ? -1 : 1);
    if (!busy && images[index]) { reviewCandidate = images[index]; renderImageReview(); }
    return;
  }
  if (button.dataset.libraryAsset) {
    elementDraft.reference_key = button.dataset.referenceKey || '';
    elementDraft.asset_id = elementDraft.reference_key ? '' : button.dataset.libraryAsset;
    const form = host.querySelector('#element-form');
    if (!form.elements.name.value) form.elements.name.value = button.dataset.label;
    host.querySelector('#element-reference-label').textContent = button.dataset.label + (elementDraft.reference_key ? ' · Current costume reference' : '');
    host.querySelector('#library-dialog').close(); return;
  }
  if (button.id === 'choose-reference') {
    const dialog = host.querySelector('#library-dialog');
    dialog.innerHTML = `<h2>Choose a reference image</h2><form id="library-search" class="narrative-inline"><input id="library-query" aria-label="Search library" placeholder="Character, costume, prop or place"><button>Search</button><button type="button" data-close="library-dialog">Close</button></form><div id="library-results" class="narrative-library-grid"></div>`;
    dialog.querySelector('#library-query').value = host.querySelector('#element-form').elements.name.value.trim();
    dialog.showModal(); librarySearch().catch(error=>status(error.message,true)); return;
  }
  if (button.id === 'remove-reference') {
    elementDraft.asset_id = ''; elementDraft.reference_key = ''; host.querySelector('#element-reference-label').textContent = 'Text only — no reference image'; return;
  }
  if(button.dataset.sceneTextCandidate){void window.ZetSceneText.open({base:base(),universe,candidate:button.dataset.sceneTextCandidate,done:async result=>{detail=result;updateLive();}}).catch(error=>status(error.message,true));return;}
  if (!['editElement','removeElement','deleteElement','candidate','renderSlot','retryJob','action','currentSelection','maskLayer','removeLayer'].some(key=>button.dataset[key])&&!['mask-apply','mask-reset'].includes(button.id)) return;
  action(async()=>{
    if (button.id==='mask-apply'||button.id==='mask-reset') {
      const id=host.querySelector('#mask-canvas').dataset.maskSource;
      if(button.id==='mask-reset') {detail.layers.find(item=>item.id===id).strokes=[];layersChanged();}
      await save();await drawMask(id);renderLayers();
    } else if (button.dataset.maskLayer) await editMask(button.dataset.maskLayer);
    else if (button.dataset.removeLayer) {detail.layers=detail.layers.filter(item=>item.id!==button.dataset.removeLayer);layersChanged();await save();renderLayers();}
    else if (button.dataset.currentSelection) {
      await save();
      const layerId=button.dataset.currentSelection;
      const sourceId=detail.layers.find(item=>item.id===layerId).target_id;
      const scene=await api(`/api/narrative/stories/${route.story}/scenes/${route.scene}/targets/${sourceId}`);
      if(!scene.selected_id) throw new Error('Select a source image first.');
      const layer=detail.layers.find(item=>item.id===layerId);
      layer.candidate_id=scene.selected_id;layer.strokes=[];layersChanged();await save();renderLayers();
    } else if (button.dataset.editElement) await editElement(button.dataset.editElement);
    else if (button.dataset.removeElement) {
      await save(); await api(base(),'PATCH',{element_ids:detail.element_ids.filter(id=>id!==button.dataset.removeElement)}); await loadPage();
    } else if (button.dataset.deleteElement) {
      await api(`${base()}/elements/${button.dataset.deleteElement}`,'DELETE'); await loadPage();
    } else if (button.dataset.candidate) {
      await save();
      if (button.dataset.candidateAction === 'lock' && Object.entries(detail.candidates).some(([id, candidate]) => id !== button.dataset.candidate && candidate.locked)) {
        if (!confirm('An image is already locked for this subscene. Lock this image and unlock all other images for this subscene?')) return;
      }
      if(detail.kind==='assembly' && (detail.scene_text?.length || detail.candidates[button.dataset.candidate]?.scene_text_final) && !(detail.candidates[button.dataset.candidate]?.locked && !detail.candidates[button.dataset.candidate]?.scene_text_pending) && button.dataset.candidateAction==='select'){await window.ZetSceneText.open({base:base(),universe,candidate:button.dataset.candidate,done:async result=>{detail=result;updateLive();}});return;}
      const result = await api(base()+`/candidates/${button.dataset.candidate}`,'POST',{action:button.dataset.candidateAction});
      if (result) { detail=result; updateLive(); status('Updated'); }
    } else if (button.dataset.renderSlot) await start('render',1,Number(button.dataset.renderSlot));
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
        case 'apply-backdrop-operation': await start('generate',1);break;
        case 'preview-crop': {await save();const image=host.querySelector('#backdrop-crop-preview');image.src=artifactUrl('crop-preview')+'&revision='+Date.now();image.hidden=false;break;}
        case 'scene-text': if(!detail.selected_id)throw Error('Select an image first.'); await save(); await window.ZetSceneText.open({base:base(),universe,candidate:detail.selected_id,done:async result=>{detail=result;updateLive();reviewCandidate=detail.selected_id;if(!host.querySelector('#image-dialog').open)host.querySelector('#image-dialog').showModal();renderImageReview();}});break;
        case 'scene-text-raw': await save(); await window.ZetSceneText.open({base:base(),universe,done:async()=>loadPage()});break;
        case 'create-assembly': {await save();const target=await api(base()+'/targets','POST',{title:'Final assembly',kind:'assembly'});await navigate({...route,target:target.id});break;}
        case 'add-layer': {
          await save();const source=detail.assembly_sources.find(item=>item.id===host.querySelector('#assembly-source').value);
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
            const image=host.querySelector('#assembly-raw');if(image.dataset.blob) URL.revokeObjectURL(image.dataset.blob);image.src=URL.createObjectURL(blob);image.dataset.blob=image.src;image.hidden=false;
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

listen(host,'submit',event=>{
  if (event.target.id === 'task-capture-form') return;
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
          await api(`/api/narrative/stories/${route.story}/scenes/${route.scene}/references`,'POST',{source,title:host.querySelector('#source-title').value,
            copy_visual_context:host.querySelector('#source-copy-context').checked,
            element_mappings:Object.fromEntries([...form.querySelectorAll('[data-source-element]')].map(select=>[select.dataset.sourceElement,select.value]))});
        host.querySelector('#narrative-source-dialog').close();sourcePicker=null;
        await navigate({...route,target:result.id});break;
      }
      case 'new-narrative-story': { const story=await api('/api/narrative/stories','POST',fields); host.querySelector('#story-dialog').close(); await navigate({story:story.id}); break; }
      case 'new-narrative-scene': { await save(); const scene=await api(base()+'/scenes','POST',fields); await navigate({...route,scene:scene.id}); break; }
      case 'new-target': { await save(); const target=await api(base()+'/targets','POST',fields); await navigate({...route,target:target.id}); break; }
      case 'element-form': {
        const url = `/api/narrative/stories/${route.story}/scenes/${route.scene}/elements`;
        const element=await api(url+(elementDraft.id ? '/'+elementDraft.id : ''),elementDraft.id ? 'PATCH' : 'POST',{...fields,asset_id:elementDraft.asset_id,reference_key:elementDraft.asset_id ? '' : elementDraft.reference_key || ''});
        if (route.target && !detail.element_ids.includes(element.id)) await api(base(),'PATCH',{element_ids:[...detail.element_ids,element.id]});
        host.querySelector('#element-dialog').close(); await loadPage(); break;
      }
      case 'membership-form': {
        await api(base(),'PATCH',{element_ids:new FormData(form).getAll('element')});
        host.querySelector('#membership-dialog').close(); await loadPage(); break;
      }
    }
  });
});


listen(host.querySelector('#narrative-universe'),'change',event=>action(async()=>{
  await save(); universe=event.target.value; await navigate({});
}));
listen(window,'beforeunload',event=>{ if(dirty.size) {event.preventDefault(); event.returnValue='';} });

async function initialize() {
  const universes = await api('/api/universes');
  const recordedUniverse = params.get('task_universe');
  if (recordedUniverse && universes.universes.some(item=>item.universe_id===recordedUniverse)) universe=recordedUniverse;
  else if (recordedUniverse) window.ZetTaskCapture.notice(`Recorded universe "${recordedUniverse}" is unavailable. Showing the current universe.`);
  universe ||= universes.selected_universe_id;
  host.querySelector('#narrative-universe').innerHTML = universes.universes.map(item=>`<option value="${esc(item.universe_id)}" ${item.universe_id===universe ? 'selected' : ''}>${esc(item.name)}</option>`).join('');
  const options = await api('/api/narrative/options');
  modelOptions = options;
  host.querySelector('#narrative-model').textContent = `${options.model} · ${options.renderer}`;
  await loadPage();
  pollTimer = setInterval(poll,2000);
}
restoreProvider = window.ZetTaskCapture.registerProvider(() => {
  const selections = {};
  const source = new URL('/?page=narrative&workspace=story',location.origin);
  source.searchParams.set('task_context','1');
  if (universe) source.searchParams.set('task_universe',universe);
  for (const name of ['story','scene']) {
    if (route[name]) {
      selections[name] = {state:contextState,id:route[name],label:contextLabels[name] || route[name]};
      source.searchParams.set(name,route[name]);
    }
  }
  if (route.target) {
    selections.render_target = {state:contextState,id:route.target,label:contextLabels.render_target || route.target};
    if (detail?.kind==='subscene') selections.subscene = {...selections.render_target};
    source.searchParams.set('target',route.target);
    const id = host.querySelector('#image-dialog').open ? reviewCandidate : detail?.selected_id
      || new URLSearchParams(location.search).get('task_candidate');
    if (id) {
      const candidate = detail?.candidates?.[id];
      selections.candidate = {state:contextState==='selected' ? candidate ? 'selected' : 'unavailable' : contextState,
        id,label:candidate ? `Slot ${candidate.slot}` : id};
      source.searchParams.set('task_candidate',id);
    }
  }
  return {page_id:'narrative',page_name:'Narrative Scenes',source_url:source.href,universe_id:universe || null,selections,
    workflow_status: contextState==='selected' ? Object.values(detail?.jobs || {}).slice(-4).map(job=>`${job.kind}: ${job.status}`).join(' · ') || 'Ready' : contextState};
});
listen(host.querySelector('#narrative-review-task'),'click',()=>void window.ZetTaskCapture.open());
try {
  await initialize();
} catch (error) {
  disposed = true; clearInterval(pollTimer); clearTimeout(saveTimer); events.abort(); restoreProvider?.();
  throw error;
}
return {
  async unmount() {
    if (disposed) return;
    await save();
    disposed = true;
    clearInterval(pollTimer); clearTimeout(saveTimer); events.abort();
    restoreProvider?.();
    for (const dialog of host.querySelectorAll('dialog[open]')) dialog.close();
    for (const image of host.querySelectorAll('[data-blob]')) URL.revokeObjectURL(image.dataset.blob);
  }
};

}
