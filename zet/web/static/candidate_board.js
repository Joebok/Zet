/** Shared Candidate Board card presentation. Pipelines inject their slot actions. */
export function renderCandidateBoard({host, slots, candidates, selectedId, escape, imageUrl,
  promptIndicator = () => '', renderSlotActions = () => ''}) {
  host.innerHTML = slots.map((id, index) => {
    const candidate = id ? candidates[id] : null;
    const state = candidate?.locked ? 'locked' : id && id === selectedId ? 'selected' :
      candidate?.status === 'FAILED' ? 'failed' : candidate?.image ? 'available' : candidate ? 'pending' : 'empty';
    const image = candidate?.image
      ? `<img src="${escape(imageUrl(id))}" alt="Slot ${index + 1} candidate" data-review="${id}">`
      : `<div class="placeholder">${candidate ? '' : 'Empty'}</div>`;
    const metadata = candidate
      ? `<p class="narrative-muted image-card-state"><span class="narrative-render-mode-pill ${candidate.render_mode === 'final' ? 'final' : 'draft'}">${candidate.render_mode === 'final' ? 'Final' : 'Draft'}</span> · ${escape(candidate.status.toLowerCase())}${id === selectedId ? ' · Selected' : ''}${candidate.locked ? ' · Locked' : ''}${candidate.scene_text_pending ? ' · Scene text changes pending' : ''}</p>`
      : '';
    const review = candidate
      ? `<div class="narrative-actions narrative-review-actions"><button data-review="${id}" aria-label="Review slot ${index + 1}">Review</button>${candidate.image ? `<button data-candidate="${id}" data-candidate-action="select" class="${id !== selectedId ? 'primary' : ''}" ${id === selectedId ? 'disabled' : ''}>${id === selectedId ? 'Selected' : 'Select'}</button>` : ''}${candidate.status === 'FAILED' ? `<button data-candidate="${id}" data-candidate-action="retry">Retry</button>` : ''}${renderSlotActions(candidate, index)}<button data-candidate="${id}" data-candidate-action="clear" class="danger-text-action">Clear slot</button>${candidate.image ? `<button data-candidate="${id}" data-candidate-action="${candidate.locked ? 'unlock' : 'lock'}">${candidate.locked ? 'Unlock' : 'Lock'}</button>` : ''}</div>`
      : `<div class="narrative-actions">${renderSlotActions(null, index)}</div>`;
    return `<article class="narrative-slot ${id && id === selectedId ? 'selected' : ''}" data-state="${state}"><h3 class="render-mode-heading">Slot ${index + 1} <span data-prompt-indicator="${id || ''}">${promptIndicator(candidate)}</span></h3>${image}${metadata}${candidate?.error ? `<p class="error">${escape(candidate.error)}</p>` : ''}${review}</article>`;
  }).join('');
}


export function reviewDecisions({id, candidate, selected, busy = false, escape}) {
  const action = (name, label, disabled = false) =>
    `<button type="button" data-candidate="${escape(id)}" data-candidate-action="${name}" ${disabled ? 'disabled' : ''}>${label}</button>`;
  return action('select', 'Select', busy || selected || !candidate.image) +
    action(candidate.locked ? 'unlock' : 'lock', candidate.locked ? 'Unlock' : 'Lock', busy || !candidate.image) +
    (candidate.status === 'FAILED' ? action('retry', 'Retry', busy) : '');
}

export function reviewPosition(candidate, index, count, selected) {
  return `${index + 1} of ${count} · ${candidate.render_mode === 'final' ? 'Final' : 'Draft'} · ${candidate.status.toLowerCase()}${selected ? ' · Selected' : ''}${candidate.locked ? ' · Locked' : ''}`;
}


export function reviewInputs(inputs, url, escape) {
  if (!inputs?.length) return "";
  return `<ol>${inputs.map((input, index) => `<li><a href="${escape(url(index + 1))}" target="_blank" rel="noopener">${escape(input.role || input.label || "Reference")}</a></li>`).join("")}</ol>`;
}
