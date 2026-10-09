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
const active = new Set(['SUBMITTING', 'QUEUED', 'RUNNING', 'DISPATCHING']);
const visualFields = ['setting', 'camera', 'perspective', 'lighting', 'style'];
const targetFields = ['title', 'narrative', 'staging', 'physical_context', 'framing', 'width', 'height', 'prompt'];
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
  root.querySelectorAll('button, #narrative-target-select').forEach(control => { control.disabled = true; });
  try { await callback(); } catch (error) { status(error.message, true); }
  finally { busy = false; root.querySelectorAll('button, #narrative-target-select').forEach(control => { control.disabled = false; }); }
}

async function navigate(next, push = true) {
  await save();
  const url = typeof next === 'string' ? next : href(next);
  if (push) history.pushState({}, '', url);
  await loadPage();
}

async function loadPage() {
  clearTimeout(saveTimer);
  const query = new URLSearchParams(location.search);
  route = {story:query.get('story'), scene:query.get('scene'), target:query.get('target')};
  dirty = new Set(); slotSignature = '';
  document.querySelector('#narrative-home').href = href({});
  status('Loading…');
  if (!route.story) {
    detail = null;
    const stories = await api('/api/narrative/stories');
    root.innerHTML = `<h1>Narrative Scenes</h1><section class="narrative-card"><h2>New story</h2>
      <form id="new-story"><label class="narrative-field">Title<input name="title" required></label>
      <label class="narrative-field">Story brief<textarea name="brief"></textarea></label><button class="primary">Create story</button></form></section>
      <div class="narrative-grid">${stories.map(story => `<article class="narrative-card"><h2>${link(story.title, {story:story.id})}</h2><p>${esc(story.brief)}</p></article>`).join('')}</div>`;
    document.querySelector('#narrative-breadcrumb').textContent = 'New narrative workflow';
  } else if (!route.scene) {
    detail = await api(base());
    root.innerHTML = `<h1>${esc(detail.title)}</h1><section class="narrative-card">${label('title',detail.title,false)}${label('brief',detail.brief)}
      <div class="narrative-actions"><button data-action="save">Save story</button><button class="danger" data-action="delete">Delete story</button></div></section>
      <section class="narrative-card"><h2>New scene</h2><form id="new-scene" class="narrative-inline"><input aria-label="Scene title" name="title" required placeholder="Scene title"><button class="primary">Create scene</button></form></section>
      <div class="narrative-grid">${detail.scenes.map(scene => `<article class="narrative-card"><h2>${link(scene.title,{story:route.story,scene:scene.id})}</h2><p>${esc(scene.intent)}</p></article>`).join('')}</div>`;
    document.querySelector('#narrative-breadcrumb').innerHTML = link('Stories',{});
  } else if (!route.target) {
    detail = await api(base());
    root.innerHTML = `<h1>${esc(detail.title)}</h1><div class="narrative-editor"><section class="narrative-card"><h2>Shared scene direction</h2>
      ${label('title',detail.title,false)}${label('intent',detail.intent)}${visualFields.map(key=>label(key,detail[key])).join('')}${label('canvas',detail.canvas,false)}
      <div class="narrative-actions"><button data-action="save">Save scene</button><button class="danger" data-action="delete">Delete scene</button></div></section><div>
      <section class="narrative-card"><h2>Subscenes and backdrops</h2><form id="new-target" class="narrative-inline">
        <input aria-label="Target title" name="title" required placeholder="Title"><select name="kind" aria-label="Target kind"><option value="subscene">Subscene</option><option value="backdrop">Backdrop</option></select><button class="primary">Create and edit</button></form>
        ${detail.targets.map(target=>`<article class="narrative-card narrative-target-card" data-target-id="${target.id}"><h3>${link(target.title,{...route,target:target.id})}</h3><p class="narrative-muted">${esc(target.kind)}${target.selected_id ? ' · Image selected' : ''}</p>
          ${target.selected_id ? `<a href="${esc(href({...route,target:target.id}))}" data-navigate><img class="narrative-target-preview" src="${esc(imageUrl(target.selected_id,target.id))}" alt="Selected image for ${esc(target.title)}"></a>` : ''}</article>`).join('')}</section>
      <section class="narrative-card"><h2>Scene elements</h2><button data-action="new-element">Add element</button><div id="narrative-elements">${elementsHtml(detail.elements,false)}</div></section></div></div>`;
    document.querySelector('#narrative-breadcrumb').innerHTML = link('Stories',{})+' / '+link('Story',{story:route.story});
  } else {
    const [loaded, targets] = await Promise.all([api(base()), api(`/api/narrative/stories/${route.story}/scenes/${route.scene}/targets`)]);
    detail = loaded;
    renderTarget(targets);
    document.querySelector('#narrative-breadcrumb').innerHTML = link('Stories',{})+' / '+link('Story',{story:route.story})+' / '+link(detail.scene_title,{story:route.story,scene:route.scene})+' / '+esc(detail.title);
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

function renderTarget(targets) {
  const backdrop = detail.kind === 'backdrop';
  root.innerHTML = `<h1 class="narrative-target-heading"><select id="narrative-target-select" aria-label="Subscene or backdrop">${targets.map(target=>`<option value="${target.id}" ${target.id === route.target ? 'selected' : ''}>${esc(target.title)} · ${title(target.kind)}</option>`).join('')}</select></h1>
    <div class="narrative-editor"><div><section class="narrative-card"><h2>${backdrop ? 'Environment direction' : 'The moment'}</h2>
      ${label('title',detail.title,false)}${label('narrative',detail.narrative,true,backdrop ? 'Describe the environment' : 'Describe what is happening')}
      ${label('staging',detail.staging,true,backdrop ? 'Environment composition' : 'Interaction and staging')}${label('physical_context',detail.physical_context)}
      ${label('framing',detail.framing,false)}<div class="narrative-grid">${label('width',detail.width,false)}${label('height',detail.height,false)}</div>
      <div class="narrative-actions"><button data-action="save">Save inputs</button><button class="danger" data-action="delete">Delete ${backdrop ? 'backdrop' : 'subscene'}</button></div></section>
    <section class="narrative-card"><h2>Participants and references</h2><div id="narrative-elements">${elementsHtml(detail.elements,true)}</div>
      <div class="narrative-actions"><button data-action="assign-elements">Assign scene elements</button><button data-action="new-element">New element / library reference</button></div></section>
    <section class="narrative-card"><h2>Shared visual context</h2><dl class="narrative-context">${visualFields.map(key=>`<dt>${title(key)}</dt><dd>${esc(detail.inherited_context[key] || 'Not specified')}</dd>`).join('')}</dl>
      <details><summary>Local overrides</summary>${visualFields.map(key=>label(`override_${key}`,detail.visual_overrides[key] || '',true,`${title(key)} override (blank inherits)`)).join('')}</details></section>
    <section class="narrative-card"><h2>Interview</h2><div id="narrative-interview" class="narrative-history"></div>
      <label class="narrative-field">Answer or direct a revision<textarea id="narrative-direction" placeholder="Describe what is happening, answer a question, or ask for a change."></textarea></label>
      <button class="primary" data-action="interview">Continue interview</button><p class="narrative-muted">Answers are optional. Edit directly or generate whenever you are ready.</p></section></div>
    <div><section class="narrative-card"><h2>Prompt and generation</h2>${label('prompt',detail.prompt,true,'Final Qwen prompt')}
      <div class="narrative-actions"><button data-action="synthesize">Write prompt</button><button class="primary" data-action="generate" data-count="1">Generate 1 from inputs</button><button class="primary" data-action="generate" data-count="4">Generate 4 from inputs</button></div>
      <div class="narrative-actions"><button data-action="render" data-count="1">Render edited prompt · 1</button><button data-action="render" data-count="4">Render edited prompt · 4</button><button data-action="refresh">Refresh</button></div>
      <p class="narrative-muted">Generate from inputs writes a new prompt and renders it. Render edited prompt sends the text above exactly as entered.</p>
      <div id="narrative-job-status" role="status" aria-live="polite"></div></section>
    <section class="narrative-card"><h2>Images</h2><div id="narrative-slots" class="narrative-slots"></div></section></div></div>`;
  updateLive();
}

function updateLive() {
  const history = document.querySelector('#narrative-interview');
  if (!history) return;
  history.innerHTML = detail.interview.map(item=>`<p><strong>${item.role === 'user' ? 'You' : 'Illustrator'}</strong><br>${esc(item.text || 'Draft updated. Continue editing or generate.')}</p>`).join('');
  const jobs = Object.values(detail.jobs);
  const working = jobs.filter(job=>active.has(job.status));
  const lastAuthorJob = jobs.filter(job=>job.kind !== 'image').at(-1);
  const failures = lastAuthorJob?.status === 'FAILED' ? [lastAuthorJob] : [];
  document.querySelector('#narrative-job-status').innerHTML = `<p class="narrative-muted">${working.length ? working.map(job=>`${esc(job.kind)}: ${esc(job.status.toLowerCase())}`).join(' · ') : 'Ready'}</p>`+
    failures.filter(job=>job.kind !== 'image').map(job=>`<div class="narrative-failure">${esc(job.error)} <button data-retry-job="${job.id}">Retry</button></div>`).join('');
  const signature = JSON.stringify([detail.slots,detail.candidates,detail.selected_id]);
  if (signature === slotSignature) return;
  slotSignature = signature;
  document.querySelector('#narrative-slots').innerHTML = detail.slots.map((id,index)=>{
    const candidate = id ? detail.candidates[id] : null;
    return `<article class="narrative-slot ${id && id === detail.selected_id ? 'selected' : ''}"><h3>Slot ${index+1}</h3>
      ${candidate?.image ? `<img src="${esc(imageUrl(id))}" alt="Slot ${index+1} candidate" data-review="${id}">` : `<div class="placeholder">${esc(candidate?.status.toLowerCase() || 'Empty')}</div>`}
      ${candidate ? `<p class="narrative-muted">${esc(candidate.status.toLowerCase())}${id === detail.selected_id ? ' · Selected' : ''}${candidate.locked ? ' · Locked' : ''}</p>
      ${candidate.error ? `<p class="error">${esc(candidate.error)}</p>` : ''}
      <div class="narrative-actions">${candidate.image ? `<button data-candidate="${id}" data-candidate-action="select">Select</button><button data-candidate="${id}" data-candidate-action="${candidate.locked ? 'unlock' : 'lock'}">${candidate.locked ? 'Unlock' : 'Lock'}</button><a href="${esc(imageUrl(id)+'&download=true')}">Download</a>` : ''}
      ${!candidate.locked && id !== detail.selected_id ? `<button data-render-slot="${index+1}">${candidate.status === 'FAILED' ? 'Retry' : 'Regenerate'}</button>` : ''}
      <button data-candidate="${id}" data-candidate-action="clear">Clear</button></div>`
      : `<div class="narrative-actions"><button data-render-slot="${index+1}">Generate</button></div>`}</article>`;
  }).join('');
}

function mergeTarget(updated) {
  for (const key of targetFields) {
    const field = root.querySelector(`[data-field="${key}"]`);
    if (field && !dirty.has(key) && document.activeElement !== field) field.value = updated[key];
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
    for (const key of changed) {
      const field = root.querySelector(`[data-field="${key}"]`);
      const value = key.startsWith('override_') ? payload.visual_overrides[key.slice(9)] : payload[key];
      if (field && String(field.value) === String(value)) dirty.delete(key);
    }
    Object.assign(detail,updated);
    const option = root.querySelector(`#narrative-target-select option[value="${updated.id}"]`);
    if (option) option.textContent = `${updated.title} · ${title(updated.kind)}`;
    status(dirty.size ? 'Saving changes…' : 'Saved');
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

async function start(actionName, count = 1, slot) {
  await save();
  status(actionName === 'render' ? 'Queueing images…' : 'Queueing illustrator…');
  const direction = document.querySelector('#narrative-direction');
  const result = await api(base()+'/jobs','POST',{action:actionName,count, ...(slot ? {slot} : {}),message:direction?.value || ''});
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
  if (!event.target.dataset.field) return;
  dirty.add(event.target.dataset.field);
  status('Saving changes…'); clearTimeout(saveTimer);
  saveTimer = setTimeout(()=>save().catch(error=>status(error.message,true)),700);
});

document.addEventListener('change',event=>{
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
  if (button.dataset.close) { document.getElementById(button.dataset.close).close(); return; }
  if (button.matches('[data-navigate]') || button.id === 'narrative-home') {
    event.preventDefault(); action(()=>navigate(button.href)); return;
  }
  if (button.dataset.review) {
    document.querySelector('#review-image').src = imageUrl(button.dataset.review);
    document.querySelector('#image-dialog').showModal(); return;
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
  if (!['editElement','removeElement','deleteElement','candidate','renderSlot','retryJob','action'].some(key=>button.dataset[key])) return;
  action(async()=>{
    if (button.dataset.editElement) await editElement(button.dataset.editElement);
    else if (button.dataset.removeElement) {
      await save(); await api(base(),'PATCH',{element_ids:detail.element_ids.filter(id=>id!==button.dataset.removeElement)}); await loadPage();
    } else if (button.dataset.deleteElement) {
      await api(`${base()}/elements/${button.dataset.deleteElement}`,'DELETE'); await loadPage();
    } else if (button.dataset.candidate) {
      await save(); const result = await api(base()+`/candidates/${button.dataset.candidate}`,'POST',{action:button.dataset.candidateAction});
      if (result) { detail=result; updateLive(); status('Updated'); }
    } else if (button.dataset.renderSlot) await start(root.querySelector('#narrative-prompt').value.trim() ? 'render' : 'generate',1,Number(button.dataset.renderSlot));
    else if (button.dataset.retryJob) {
      const job = detail.jobs[button.dataset.retryJob]; await start(job.kind,job.candidate_ids?.length === 4 ? 4 : 1);
    } else {
      switch (button.dataset.action) {
        case 'save': await save(); status('Saved'); break;
        case 'delete': {
          await save(); const result = await api(base(),'DELETE',{});
          if (result) await navigate(route.target ? {story:route.story,scene:route.scene} : route.scene ? {story:route.story} : {});
          break;
        }
        case 'new-element': await editElement(); break;
        case 'assign-elements': await assignElements(); break;
        case 'interview': case 'synthesize': case 'generate': case 'render': await start(button.dataset.action,Number(button.dataset.count || 1)); break;
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
      case 'new-story': { const story=await api('/api/narrative/stories','POST',fields); await navigate({story:story.id}); break; }
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
  document.querySelector('#narrative-model').textContent = `${options.model} · ${options.renderer}`;
  await loadPage();
  setInterval(poll,2000);
}
initialize().catch(error=>status(error.message,true));
