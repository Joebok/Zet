/** Browser presentation. The subscriber owns requests and authoritative board data. */
const escape = value => String(value ?? '').replace(/[&<>"']/g, char =>
  ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'})[char]);
const qualities = ['draft', 'final'];
let nextBoardId = 0;
const actionOrder = ['select', 'unselect', 'lock', 'unlock', 'inventory-add', 'inventory-update', 'retry', 'upscale', 'cancel', 'regen-draft', 'regen-final', 'download', 'clear'];
const glyphs = {'regen-draft':'regenerate', 'regen-final':'regenerate',
  'inventory-add':'inventory', 'inventory-update':'inventory'};
const slotLabels = {select:'Select', unselect:'Deselect', lock:'Lock', unlock:'Unlock', retry:'Retry', upscale:'Upscale Draft', clear:'Clear slot'};
const bulkLabels = {'delete-drafts':'Delete Drafts', 'delete-non-selected':'Delete Non-Selected'};
const selectedKey = 'selected';

export function confirmCandidateDeletion(key, board, slots, activeSlots, effects) {
  if (!slots.length) return null;
  const label = bulkLabels[key];
  const ordered = values => [...values].sort((a, b) => a - b).join(', ');
  const active = activeSlots.length
    ? ` Active Draft work in slots ${ordered(activeSlots)} will be cancelled. Backend renders already running may finish, and their results will be discarded.` : '';
  return window.confirmProtectedEffects(`${label}?`, `${board}. Clear slots ${ordered(slots)}.${active} Inventory copies are retained.`,
    effects, label, {individual:true});
}
const imageKey = image => JSON.stringify([image?.url, image?.version]);
const reviewStatusLabels = {RUNNING:'Started', COMPLETE:'Finish', OBSOLETE:'Outdated', FAILED:'Failed', INTERRUPTED:'Interrupted'};

function button(label, command, key = '') {
  const glyph = {copy:'copy', 'comparison-previous':'previous', 'comparison-next':'next'}[command];
  return `<button type="button" data-command="${command}" data-key="${escape(key)}"
    ${glyph ? `data-glyph="${glyph}" data-label="${escape(label)}"` : ''}>${escape(label)}</button>`;
}

export function mountCandidateBoard({boardHost, dialogHost}, initialModel, adapter) {
  const boardId = ++nextBoardId;
  const events = new AbortController();
  const listen = (node, type, handler, options = {}) =>
    node.addEventListener(type, handler, {...options, signal: events.signal});
  const board = document.createElement('section');
  board.className = 'zet-candidate-board';
  board.innerHTML = `<section aria-label="Render Controls" class="zcb-controls">
    <h2>Render Controls</h2><div data-part="authoring"></div><div data-part="fields"></div>
    <div data-part="toolbar"></div><div data-part="board-status"></div>
  </section><div class="zcb-grid" data-part="grid"></div>`;
  const dialog = document.createElement('dialog');
  dialog.className = 'zet-candidate-review';
  dialog.setAttribute('aria-label', 'Review candidate');
  dialog.innerHTML = `<header><h2 data-part="title"></h2>
    ${button('Previous candidate','previous')}${button('Next candidate','next')}
    ${button('Close review','close')}</header>
    <div class="zcb-review-layout">
      <div class="zcb-pictures"><figure data-part="comparison" hidden></figure><figure data-part="image"></figure></div>
      <aside><div class="zcb-tools">
        ${button('Zoom In','zoom-in')}${button('Zoom Out','zoom-out')}${button('Reset Zoom','zoom-reset')}
      </div><div data-part="rail">
        <div data-part="review-actions"></div><div data-part="review-status" role="status"></div>
        <details><summary>Compare with</summary><div data-part="choices"></div></details>
        <div data-part="assessment"></div><div data-part="details"></div>
      </div></aside>
    </div>`;
  boardHost.append(board);
  dialogHost.append(dialog);
  const part = (root, name) => root.querySelector(`[data-part="${name}"]`);
  const view = name => part(dialog, name);
  const grid = part(board, 'grid');
  const zoom = window.ZetReviewImageZoom.attach(dialog, () => [...dialog.querySelectorAll('.zcb-pictures img')]);
  const cards = new Map();
  const imageErrors = new WeakMap();
  const pending = new Set();
  const feedback = new Map();
  const failedComparisons = new Set();
  let model, candidateId, origin, originSlot, chosen, activeComparison;
  let scopeEpoch = 0, reviewEpoch = 0;
  let disposed = false;

  function patch(node, html) {
    if (node.dataset.markup === html) return;
    const focused = document.activeElement;
    const token = node.contains(focused) && [focused.dataset.command, focused.dataset.key, focused.name, focused.tagName];
    const selection = token && focused.selectionStart != null
      ? [focused.selectionStart, focused.selectionEnd] : null;
    const disclosures = [...node.querySelectorAll('details')].map(details => [details.querySelector('summary')?.textContent, details.open]);
    node.innerHTML = html;
    node.dataset.markup = html;
    for (const details of node.querySelectorAll('details')) {
      const state = disclosures.find(([summary]) => summary === details.querySelector('summary')?.textContent);
      if (state) details.open = state[1];
    }
    const replacement = token && [...node.querySelectorAll('button,input,select,textarea,summary,.zcb-action[tabindex]')].find(control =>
      control.dataset.command === token[0] && control.dataset.key === token[1] && control.name === token[2] &&
      control.tagName === token[3] && (focused.type !== 'radio' || control.value === focused.value)
    );
    if (replacement) {
      if (replacement.name && replacement.type !== 'radio') {
        replacement.value = focused.value;
        if (replacement.type === 'checkbox') replacement.checked = focused.checked;
        if (selection) replacement.setSelectionRange(...selection);
      }
      replacement.focus({preventScroll:true});
    }
  }

  function decorate(root) {
    for (const control of root.querySelectorAll('[data-glyph]')) {
      window.ZetImageCardUI.decorate(control, control.dataset.glyph, control.dataset.label);
    }
  }

  const notify = (type, data = {}) => adapter.onEvent?.({type, scopeKey:model.scope.key, candidateId, ...data});
  const slotFor = id => model.slots.find(slot => slot.candidate?.id === id);
  const reviewable = () => model.slots.filter(slot => slot.candidate && slot.candidate.reviewable !== false);
  const command = name => dialog.querySelector(`[data-command="${name}"]`);
  function scopeActions(slot, surface) {
    const actions = (slot ? slot.actions : model.actions)?.filter(action => !action.placement || action.placement.includes(surface)) || [];
    if (!slot) return actions;
    const standard = actions.map(action => slotLabels[action.key] ? {
      ...action, label:slotLabels[action.key], role:action.key === 'clear' ? 'danger-text-action' : undefined,
    } : action);
    if (slot.cancelAttempt && surface === 'card') {
      standard.push({key:'cancel', label:'Cancel', disabledReason:slot.replacementBlock});
    }
    if (!slot.candidate && surface !== 'card') return standard;
    const candidate = slot.candidate;
    if (candidate?.image && candidate.quality !== 'final') {
      const disabledReason = slot.replacementBlock || (slot.renderActive ? 'Wait for the render to finish.'
        : candidate.locked ? 'Unlock this image first.'
        : candidate.status !== 'COMPLETE' ? 'Wait for a completed Draft image.' : '');
      standard.push({key:'upscale', label:slotLabels.upscale, disabledReason});
    }
    const protectedImage = slot.candidate && (slot.candidate.locked || slot.candidate.id === model.selectedId);
    const blocked = slot.replacementBlock || (slot.renderActive ? 'Wait for the render to finish.'
      : protectedImage ? 'Clear the protected image before replacing it.' : '');
    for (const mode of qualities) {
      const quality = mode === 'draft' ? 'Draft' : 'Final';
      standard.push({key:`regen-${mode}`, mode, count:1,
        label:slot.candidate ? `Regen ${quality}` : `Generate ${quality} here`,
        disabledReason:blocked || model.renderControls?.readiness?.[mode]});
    }
    return standard;
  }
  const pendingKey = (key, slot) => JSON.stringify([slot?.key, slot?.candidate?.id, key]);

  function boardActions() {
    const controls = model.renderControls || {};
    const empty = model.slots.filter(slot => !slot.candidate).length;
    const render = qualities.flatMap(mode => [1, 4].map(count => {
      const key = `render-${mode}-${count}`;
      const readiness = controls.readiness?.[key] || controls.readiness?.[mode];
      return {key, mode, count, label:`${mode === 'draft' ? 'Draft' : 'Final'} ${count}`,
        disabledReason: empty < count ? `Requires ${count} empty slots.` : readiness};
    }));
    const actions = [...new Map([
      ...scopeActions(null, 'controls'),
      ...(model.actions || []).filter(action => action.placement?.includes('settings')),
    ].map(action => [action.key, action])).values()];
    const occupied = model.slots.filter(slot => slot.candidate);
    const bulk = Object.entries(bulkLabels).map(([key, label]) => {
      const drafts = key === 'delete-drafts';
      const targets = occupied.filter(({candidate}) => drafts ? candidate.quality !== 'final'
        : candidate.id !== model.selectedId && !candidate.locked);
      return {key, label, group:'bulk', role:'danger-text-action',
        disabledReason: model.bulkBlock || (!targets.length ? 'No candidates to delete.'
          : !drafts && targets.some(slot => slot.renderActive) ? 'Wait for the affected renders to settle.' : '')};
    });
    return [...actions.filter(action => action.group === 'prompt'), ...render,
      ...actions.filter(action => action.group !== 'prompt'), ...bulk];
  }

  function actionMarkup(action, slot) {
    const busy = pending.has(pendingKey(action.key, slot));
    const reason = action.disabledReason || (busy ? 'Working…' : '');
    const glyph = action.glyph || glyphs[action.key] || (actionOrder.includes(action.key) && action.key !== 'cancel' ? action.key : '');
    const renderGlyph = action.key.startsWith('render-') && qualities.includes(action.mode)
      ? window.ZetImageCardUI.iconMarkup('regenerate') : '';
    const tooltip = (slot || action.group === 'bulk') && reason ? escape(`${action.label} · ${reason}`) : '';
    return `<span class="zcb-action" ${tooltip ? `title="${tooltip}" role="group" aria-label="${tooltip}" tabindex="0" data-key="${escape(action.key)}"` : ''}><button type="button" data-command="action" data-key="${escape(action.key)}"
      class="${escape(action.role || '')}" data-quality="${escape(action.mode)}"
      ${glyph ? `data-glyph="${escape(glyph)}" data-label="${escape(action.label)}"` : ''}
      ${reason ? 'disabled' : ''}>${renderGlyph}${escape(action.label)}</button>
      ${reason && !tooltip ? `<small>${escape(reason)}</small>` : ''}</span>`;
  }

  function showFeedback(node, result) {
    node.classList.toggle('error', result?.status === 'error');
    node.textContent = result?.message || '';
  }

  function renderControls() {
    const controls = model.renderControls || {};
    const fields = controls.fields || [];
    const host = part(board, 'fields');
    const fieldMarkup = field => {
      const attrs = `name="${escape(field.key)}" ${field.disabled ? 'disabled' : ''}`;
      if (field.type === 'radio') {
        return `<fieldset class="zcb-radio-group"><legend>${escape(field.label)}</legend>${(field.options || []).map(option =>
          `<label><input ${attrs} type="radio" value="${escape(option.value)}">${escape(option.label)}</label>`).join('')}</fieldset>`;
      }
      const list = `zcb-${boardId}-${escape(field.key)}`;
      const input = field.type === 'textarea' ? `<textarea ${attrs}></textarea>`
        : field.type === 'select' ? `<select ${attrs}>${(field.options || []).map(option =>
          `<option value="${escape(option.value)}">${escape(option.label)}</option>`).join('')}</select>`
          : `<input ${attrs} type="${field.type === 'checkbox' ? 'checkbox' : 'text'}" placeholder="${escape(field.placeholder)}" ${field.suggestions ? `list="${list}"` : ''}>`;
      return `<label>${escape(field.label)}${input}</label>${field.suggestions ?
        `<datalist id="${list}">${field.suggestions.map(value => `<option value="${escape(value)}"></option>`).join('')}</datalist>` : ''}`;
    };
    const actions = boardActions();
    const settingsActions = actions.filter(action => action.placement?.includes('settings'));
    const authoring = part(board, 'authoring');
    const split = Boolean(controls.promptFields);
    patch(authoring, split ? `<section aria-label="Prompt authoring"><h3>Prompt authoring</h3>
      ${controls.promptFields.map(fieldMarkup).join('')}<div class="zcb-tools">${actions.filter(action => action.group === 'prompt').map(action => actionMarkup(action)).join('')}</div>
      <p role="status"></p><div role="status"></div></section>` : '');
    if (split) {
      const [status, outcome] = authoring.querySelectorAll('[role="status"]');
      status.textContent = controls.promptStatus || '';
      showFeedback(outcome, feedback.get('prompt'));
      decorate(authoring);
    }
    patch(host, fields.length || settingsActions.length ? `<details><summary>Prompt and render settings</summary>
      ${fields.length ? `<div class="zcb-fields ${controls.fieldsLayout === 'inline' ? 'zcb-fields-inline' : ''}">${fields.map(fieldMarkup).join('')}</div>` : ''}
      ${settingsActions.length ? `<div class="zcb-tools zcb-settings-actions">${settingsActions.map(action => actionMarkup(action)).join('')}</div>` : ''}</details>` : '');
    const fieldsByName = new Map([...(controls.promptFields || []), ...fields].map(field => [field.key, field]));
    for (const control of board.querySelectorAll('[name]')) {
      const field = fieldsByName.get(control.name);
      if (!field) continue;
      if (field.type === 'radio') control.checked = control.value === String(field.value ?? '');
      else if (control !== document.activeElement) {
        if (field.type === 'checkbox') control.checked = Boolean(field.value);
        else if (control.value !== String(field.value ?? '')) control.value = field.value ?? '';
      }
    }
    const toolbar = part(board, 'toolbar');
    patch(toolbar, `<div class="zcb-tools">${actions.filter(action => (!action.placement || action.placement.includes('controls')) && action.group !== 'bulk' && (!split || action.group !== 'prompt')).map(action => actionMarkup(action)).join('')}
      <div class="zcb-bulk">${actions.filter(action => action.group === 'bulk').map(action => actionMarkup(action)).join('')}</div></div>`);
    decorate(toolbar);
    const status = part(board, 'board-status');
    const luna = model.lunaReview;
    const startError = feedback.get('luna');
    const reviewStatus = startError?.status === 'error' ? 'Failed' : reviewStatusLabels[luna?.status] || 'Not started';
    const reviewNote = startError?.status === 'error' ? startError.message
      : luna?.status === 'OBSOLETE' ? 'Ranking obsolete: candidate images changed'
      : luna?.status === 'FAILED' ? luna.error : '';
    patch(status, `${split ? '' : `<p role="status">${escape(controls.promptStatus)}</p>`}<p role="status">${escape(controls.renderStatus)}</p>
      ${luna || actions.some(action => action.group === 'luna' || action.key === 'luna-review')
        ? `<p role="status">Review Status: ${reviewStatus}${reviewNote ? ` · ${escape(reviewNote)}` : ''}</p>` : ''}
      ${model.lunaReview?.criteria ? `<details><summary>Review criteria</summary><pre>${escape(model.lunaReview.criteria)}</pre></details>` : ''}
      ${split ? '' : '<div role="status" data-feedback="prompt"></div>'}<div role="status" data-feedback="render"></div>
      <div role="status" data-feedback="bulk"></div>`);
    for (const node of status.querySelectorAll('[data-feedback]')) showFeedback(node, feedback.get(node.dataset.feedback));
  }

  function renderImage(host, image, fallback, onError) {
    const key = JSON.stringify([imageKey(image), image ? null : fallback]);
    if (host.dataset.imageKey === key) {
      const img = host.querySelector('img');
      if (img && img.alt !== (image.label || '')) img.alt = image.label || '';
      return;
    }
    host.dataset.imageKey = key;
    host.replaceChildren();
    const placeholder = document.createElement('span');
    placeholder.className = 'zcb-placeholder';
    placeholder.textContent = image ? 'Image unavailable' : fallback;
    placeholder.hidden = Boolean(image);
    host.append(placeholder);
    if (!image) return;
    const img = document.createElement('img');
    img.alt = image.label || '';
    imageErrors.set(img, () => {
      img.hidden = true;
      placeholder.hidden = false;
      onError?.();
    });
    if (!dialog.contains(host)) img.loading = 'lazy';
    img.src = image.url;
    host.append(img);
  }

  for (const root of [board, dialog]) listen(root, 'error', event => imageErrors.get(event.target)?.(), {capture:true});
  listen(dialog, 'load', syncZoom, {capture:true});

  function statusMarkup(candidate) {
    if (!candidate) return 'Empty';
    const rank = model.lunaReview?.entries?.[candidate.id]?.rank;
    const quality = candidate.quality === 'final' ? 'Final' : 'Draft';
    const status = String(candidate.status || '').toLowerCase();
    return [`<span class="narrative-render-mode-pill ${quality.toLowerCase()}">${quality}</span>`,
      status !== 'complete' ? escape(status) : '',
      typeof candidate.elapsedSeconds === 'number' && Number.isFinite(candidate.elapsedSeconds)
        ? `${Number.isInteger(candidate.elapsedSeconds) ? candidate.elapsedSeconds : candidate.elapsedSeconds.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')}s` : '',
      candidate.id === model.selectedId ? 'Selected' : '',
      candidate.locked ? `<span class="zcb-lock" title="Locked">${window.ZetImageCardUI.iconMarkup('lock')}<span class="zcb-visually-hidden">Locked</span></span>` : '',
      rank ? `Luna ${model.lunaReview.status === 'OBSOLETE' ? 'previous ' : ''}#${escape(rank)}` : '',
      candidate.earlierPrompt ? '<span class="status-badge review" title="The saved prompt changed after this image was made.">Earlier prompt</span>' : ''
    ].filter(Boolean).join(' · ');
  }

  function candidateActions(slot, surface) {
    const order = key => actionOrder.includes(key) ? actionOrder.indexOf(key) : actionOrder.length - 2.5;
    return scopeActions(slot, surface).slice().sort((left, right) => order(left.key) - order(right.key))
      .map(action => actionMarkup(action, slot)).join('');
  }

  function renderGrid() {
    for (const [key, card] of cards) {
      if (!model.slots.some(slot => slot.key === key)) { card.remove(); cards.delete(key); }
    }
    model.slots.forEach((slot, index) => {
      let card = cards.get(slot.key);
      if (!card) {
        card = document.createElement('article');
        card.dataset.slot = slot.key;
        card.innerHTML = `<h3></h3><button type="button" data-command="open" class="zcb-thumbnail"></button>
          <p data-part="state"></p><p data-part="notice"></p><div class="zcb-tools" data-part="actions"></div>
          <div role="status" data-part="feedback"></div>`;
        cards.set(slot.key, card);
      }
      if (grid.children[index] !== card) grid.insertBefore(card, grid.children[index] || null);
      const candidate = slot.candidate;
      const label = `Review slot ${index + 1}`;
      const canReview = candidate && candidate.reviewable !== false;
      card.querySelector('h3').textContent = `Slot ${index + 1}`;
      card.classList.toggle('is-selected', Boolean(candidate && candidate.id === model.selectedId));
      const preview = card.querySelector('.zcb-thumbnail');
      preview.setAttribute('aria-label', label);
      preview.disabled = !canReview;
      renderImage(preview, candidate?.thumbnail || candidate?.image, candidate ? 'No image available' : 'Empty slot');
      patch(part(card, 'state'), statusMarkup(candidate));
      part(card, 'notice').textContent = [candidate?.error, ...(candidate?.notices || [])].filter(Boolean).join(' · ');
      const actions = part(card, 'actions');
      patch(actions, `${canReview ? `<button type="button" data-command="open" data-glyph="review" data-label="${label}">${label}</button>` : ''}
        ${candidateActions(slot, 'card')}`);
      decorate(actions);
      showFeedback(part(card, 'feedback'), feedback.get(pendingKey('card', slot)));
    });
  }

  function comparisons() {
    const selected = slotFor(model.selectedId)?.candidate;
    const options = [{key:selectedKey, label:selected?.image
      ? `Selected · ${selected.quality === 'final' ? 'Final' : 'Draft'} · Slot ${model.slots.indexOf(slotFor(selected.id)) + 1}`
      : 'Selected · No image available', image:selected?.image}];
    const seen = new Set(options.map(option => imageKey(option.image)));
    for (const option of model.comparisons || []) {
      const key = imageKey(option.image);
      if (option.image && !seen.has(key)) { options.push(option); seen.add(key); }
    }
    return options;
  }

  function syncZoom() {
    if (dialog.open) zoom.sync(JSON.stringify([candidateId, imageKey(slotFor(candidateId)?.candidate?.image)]));
  }

  function renderReview() {
    const slot = slotFor(candidateId);
    if (!dialog.open || !slot) return;
    const candidate = slot.candidate;
    const list = reviewable();
    const position = list.indexOf(slot);
    const slotNumber = model.slots.indexOf(slot) + 1;
    patch(view('title'), [model.scope.title, model.scope.view, `Slot ${slotNumber} · ${position + 1} of ${list.length}`]
      .filter(Boolean).map(escape).join(' · ') + ' · ' + statusMarkup(candidate));
    command('previous').disabled = pending.size > 0 || position <= 0;
    command('next').disabled = pending.size > 0 || position >= list.length - 1;
    command('close').disabled = pending.size > 0;
    const options = comparisons();
    const defaults = (model.comparisonDefaults || []).filter(key =>
      options.some(option => option.key === key && option.image && !failedComparisons.has(imageKey(option.image))));
    const keys = chosen ?? (defaults.length ? defaults : [selectedKey]);
    const selected = keys.map(key => options.find(option => option.key === key)).filter(Boolean);
    if (!selected.some(option => option.key === activeComparison)) activeComparison = selected[0]?.key;
    const compare = selected.find(option => option.key === activeComparison);
    const comparison = view('comparison');
    comparison.hidden = !compare;
    const compareImage = compare?.image && !failedComparisons.has(imageKey(compare.image)) ? compare.image : undefined;
    renderImage(comparison, compareImage, '', () => {
      failedComparisons.add(imageKey(compare.image));
      renderReview();
    });
    if (compareImage) {
      let caption = comparison.querySelector('figcaption');
      if (!caption) {
        caption = document.createElement('figcaption');
        comparison.append(caption);
      }
      caption.textContent = compare.label;
    }
    renderImage(view('image'), candidate.image, candidate.error || 'No image available');
    syncZoom();
    const choices = view('choices');
    patch(choices, `${button('No comparison','no-comparison')}
      ${options.map(option => {
        const failed = failedComparisons.has(imageKey(option.image));
        return `<label><input type="checkbox" name="${escape(option.key)}" data-comparison
          ${keys.includes(option.key) ? 'checked' : ''}>
          ${escape(option.label)}${failed ? ' · Image unavailable' : ''}</label>`;
      }).join('')}
      ${compare ? `<p>${escape(compare.label)}</p>` : ''}
      ${selected.length > 1 ? button('Previous comparison','comparison-previous') + button('Next comparison','comparison-next') : ''}`);
    decorate(choices);
    const actions = view('review-actions');
    patch(actions, `<div class="zcb-tools">${candidateActions(slot, 'review')}</div>`);
    decorate(actions);
    showFeedback(view('review-status'), feedback.get(pendingKey('review', slot)));
    const assessment = model.lunaReview?.entries?.[candidate.id];
    patch(view('assessment'), `${assessment ? `<h3>Luna ${model.lunaReview.status === 'OBSOLETE' ? 'previous ' : ''}rank ${escape(assessment.rank)}</h3><p>${escape(assessment.assessment)}</p>` : ''}
      ${candidate.humanAssessment ? `<p>Human assessment · ${escape(candidate.humanAssessment)}</p>` : ''}`);
    const details = view('details');
    const disclosure = (item, label, copy = false) => `<details><summary>${escape(label)}</summary>
      ${copy && item.prompt ? button('Copy prompt','copy') : ''}<pre>${escape(item.prompt || 'Prompt not recorded')}</pre>
      ${item.negativePrompt ? `<p>Negative prompt</p><pre>${escape(item.negativePrompt)}</pre>` : ''}
      <ol>${(item.inputs || []).map(input => {
        const text = escape([input.marker, input.label].filter(Boolean).join(' '));
        return `<li>${input.url ? `<a href="${escape(input.url)}" target="_blank" rel="noopener">${text}</a>` : text}</li>`;
      }).join('')}</ol>
      ${item.renderSettings?.length ? `<h3>Render settings</h3><dl>${item.renderSettings.map(({label, value}) =>
        `<dt>${escape(label)}</dt><dd>${escape(value)}</dd>`).join('')}</dl>` : ''}
      ${(item.provenance || []).map(line => `<p>${escape(line)}</p>`).join('')}</details>`;
    patch(details, `${disclosure(candidate, 'Candidate prompt and ordered inputs', true)}
      <p>${escape([candidate.error, ...(candidate.notices || [])].filter(Boolean).join(' · '))}</p>`);
    decorate(details);
  }

  function render() {
    renderControls();
    renderGrid();
    renderReview();
  }

  function changeCandidate(id) {
    candidateId = id;
    reviewEpoch++;
    const disclosure = view('details').querySelector('details');
    if (disclosure) disclosure.open = false;
    view('rail').parentElement.scrollTop = 0;
    renderReview();
  }

  async function canLeave(nextId) {
    if (pending.size) return false;
    const epoch = reviewEpoch;
    const scope = scopeEpoch;
    const current = () => !disposed && scope === scopeEpoch && epoch === reviewEpoch;
    try {
      const allowed = await adapter.beforeReviewLeave?.({scopeKey:model.scope.key, candidateId, nextId});
      return current() && allowed !== false;
    } catch (error) {
      if (current()) {
        feedback.set(pendingKey('review', slotFor(candidateId)), {status:'error', message:error.message || String(error)});
        renderReview();
      }
      return false;
    }
  }

  async function openReview(id, from) {
    if (disposed || !reviewable().some(slot => slot.candidate.id === id)) return;
    if (dialog.open) {
      if (candidateId !== id && await canLeave(id) && reviewable().some(slot => slot.candidate.id === id)) {
        changeCandidate(id);
        notify('candidate-change');
      }
      return;
    }
    origin = from || document.activeElement;
    originSlot = slotFor(id).key;
    dialog.showModal();
    changeCandidate(id);
    command('close').focus();
    notify('review-open');
  }

  function moveReview(direction) {
    if (!dialog.open) return;
    const list = reviewable();
    const next = list[list.indexOf(slotFor(candidateId)) + direction];
    if (next) return openReview(next.candidate.id);
  }

  function finishReview(restoreFocus = true) {
    if (!dialog.open) return;
    dialog.close();
    zoom.reset();
    reviewEpoch++;
    notify('review-close');
    candidateId = undefined;
    if (restoreFocus) {
      const card = cards.get(originSlot);
      const matchingControl = [...(card?.querySelectorAll('button:not(:disabled)') || [])].find(control =>
        control.dataset.command === origin?.dataset.command && control.dataset.key === origin?.dataset.key &&
        control.dataset.glyph === origin?.dataset.glyph);
      const fallback = matchingControl || card?.querySelector('button:not(:disabled)') ||
        board.querySelector('button:not(:disabled)');
      (origin?.isConnected && !origin.disabled ? origin : fallback)?.focus({preventScroll:true});
    }
    origin = originSlot = undefined;
  }

  async function closeReview() {
    if (dialog.open && await canLeave(undefined)) finishReview();
  }

  function setComparisons(keys) {
    if (disposed) return;
    chosen = [...keys];
    activeComparison = undefined;
    renderReview();
    notify('comparison-change', {keys:chosen.slice(), activeKey:activeComparison});
  }

  function moveComparison(direction) {
    const keys = [...view('choices').querySelectorAll('[data-comparison]:checked')].map(input => input.name);
    activeComparison = keys[(keys.indexOf(activeComparison) + direction + keys.length) % keys.length];
    renderReview();
    notify('comparison-change', {keys, activeKey:activeComparison});
  }

  async function invoke(control, surface, slot) {
    const actions = surface === 'controls' ? boardActions() : scopeActions(slot, surface);
    const action = actions.find(item => item.key === control.dataset.key);
    if (!action || action.disabledReason) return;
    const key = pendingKey(action.key, slot);
    if (pending.has(key)) return;
    const epoch = scopeEpoch;
    const review = reviewEpoch;
    const target = surface === 'controls' ? action.group || (action.key === 'luna-review' ? 'luna' : 'render')
      : pendingKey(surface, slot);
    const intent = {key:action.key, origin:surface, scopeKey:model.scope.key, revision:model.revision,
      candidateId:slot?.candidate?.id, slotKey:slot?.key, expectedOccupant:slot ? slot.candidate?.id ?? null : undefined,
      mode:action.mode, count:action.count, value:action.value, expectedAttempt:slot?.cancelAttempt,
      fields:Object.fromEntries([...board.querySelectorAll('[name]:not([type="radio"]:not(:checked))')].map(field =>
        [field.name, field.type === 'checkbox' ? field.checked : field.value]))};
    pending.add(key);
    if (target === 'luna') feedback.delete(target);
    else feedback.set(target, {message:`${action.label}…`});
    render();
    let result;
    try { result = await adapter.onAction(intent); }
    catch (error) { result = {status:'error', message:error.message || String(error)}; }
    if (disposed || epoch !== scopeEpoch) return;
    pending.delete(key);
    if (result?.status === 'cancelled' || (target === 'luna' && result?.status !== 'error')) feedback.delete(target);
    else feedback.set(target, result);
    render();
    if (result?.status === 'success' && result.reviewCandidateId && dialog.open && review === reviewEpoch) {
      await openReview(result.reviewCandidateId);
    }
  }

  listen(board, 'click', event => {
    const control = event.target.closest('button[data-command]');
    if (!control || control.disabled) return;
    const card = control.closest('[data-slot]');
    const slot = card && model.slots.find(item => String(item.key) === card.dataset.slot);
    if (control.dataset.command === 'open') void openReview(slot.candidate.id, control);
    if (control.dataset.command === 'action') void invoke(control, card ? 'card' : 'controls', slot);
  });
  listen(board, 'input', event => {
    const {name, type, checked, value} = event.target;
    adapter.onEdit?.({scopeKey:model.scope.key, field:name, value:type === 'checkbox' ? checked : value});
  });
  listen(dialog, 'change', event => {
    if (event.target.matches('[data-comparison]')) {
      setComparisons([...view('choices').querySelectorAll('[data-comparison]:checked')].map(input => input.name));
    }
  });
  listen(dialog, 'click', async event => {
    const control = event.target.closest('button[data-command]');
    if (!control || control.disabled) return;
    switch (control.dataset.command) {
      case 'previous': return moveReview(-1);
      case 'next': return moveReview(1);
      case 'close': return closeReview();
      case 'action': return invoke(control, 'review', slotFor(candidateId));
      case 'no-comparison': return setComparisons([]);
      case 'comparison-previous': return moveComparison(-1);
      case 'comparison-next': return moveComparison(1);
      case 'zoom-in': return zoom.step(1);
      case 'zoom-out': return zoom.step(-1);
      case 'zoom-reset': return zoom.reset();
      case 'copy': {
        const slot = slotFor(candidateId);
        const epoch = scopeEpoch;
        const key = pendingKey('review', slot);
        try {
          await navigator.clipboard.writeText(slot.candidate.prompt);
          if (!disposed && epoch === scopeEpoch) feedback.set(key, {message:'Prompt copied.'});
        } catch (error) {
          if (!disposed && epoch === scopeEpoch) feedback.set(key, {status:'error', message:error.message});
        }
        return renderReview();
      }
    }
  });
  listen(dialog, 'cancel', event => { event.preventDefault(); void closeReview(); });
  listen(dialog, 'keydown', event => {
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey ||
        event.target.closest('input,select,textarea,[contenteditable],[data-part="choices"]')) return;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      void moveReview(event.key === 'ArrowLeft' ? -1 : 1);
    }
  });

  function update(next) {
    if (disposed) return;
    const oldIndex = model?.slots.indexOf(slotFor(candidateId)) ?? -1;
    if (model && model.scope.key !== next.scope.key) {
      finishReview(false);
      scopeEpoch++;
      chosen = activeComparison = undefined;
      failedComparisons.clear();
      pending.clear();
      feedback.clear();
      cards.clear();
      grid.replaceChildren();
      patch(part(board, 'fields'), '');
    }
    model = next;
    if (dialog.open && !reviewable().includes(slotFor(candidateId))) {
      const available = reviewable();
      const replacement = available.find(slot => model.slots.indexOf(slot) >= oldIndex) || available.at(-1);
      if (replacement) { changeCandidate(replacement.candidate.id); notify('candidate-change'); }
      else finishReview();
    }
    render();
  }

  for (const [name, glyph] of [['previous','previous'], ['next','next'], ['close','close']]) {
    const control = command(name);
    window.ZetImageCardUI.decorate(control, glyph, control.textContent);
  }
  update(initialModel);
  return {update, openReview, moveReview, closeReview, setComparisons, resetZoom:() => zoom.reset(),
    dispose() {
      if (disposed) return;
      disposed = true;
      finishReview(false);
      events.abort();
      zoom.dispose();
      board.remove();
      dialog.remove();
    }};
}
