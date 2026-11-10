const active = new Set(['SUBMITTING', 'QUEUED', 'RUNNING', 'DISPATCHING', 'TRANSFERRING', 'RECONCILING']);
export const isNarrativeActive = status => active.has(status);
const assemblyModes = [
  ['finish_composite', 'Finish placed composite'],
  ['assemble_references', 'Assemble from references'],
  ['harmonize_composite', 'Harmonize placed composite'],
];
const action = (key, label, options = {}) => ({key, label, ...options});
const review = ['review'];

export function narrativeBoardModel({detail, scopeKey, revision, drafts, busy, llmSubmitting,
  models, defaultModel, sizing, sizingError, imageUrl, artifactUrl, reviewedId, pendingInterviews}) {
  const value = key => drafts.get(key) ?? detail[key] ?? '';
  const assembly = detail.kind === 'assembly';
  const pinned = detail.kind === 'backdrop' && detail.source_snapshot?.image_file;
  const unmodified = pinned && detail.backdrop_link_mode === 'unmodified';
  const reference = pinned && detail.backdrop_link_mode === 'reference';
  const settings = detail.backdrop_adaptation || {};
  const localOnly = unmodified || (reference && ['crop', 'unchanged'].includes(settings.operation));
  const jobs = Object.values(detail.jobs);
  const writing = jobs.filter(job => ['generate', 'synthesize'].includes(job.kind)).at(-1);
  const working = jobs.filter(job => isNarrativeActive(job.status));
  const llmBusy = llmSubmitting || working.some(job => job.kind !== 'image');
  const busyReason = busy ? 'Another action is in progress.' : '';
  const authorReason = busyReason || (unmodified ? 'Use the local reuse action for this backdrop.'
    : llmBusy ? 'Wait for the illustrator to finish.' : '');
  const renderReason = authorReason || (localOnly ? 'Use the local backdrop action.'
    : sizingError || (!value('prompt').trim() ? 'Enter or write a prompt first.'
    : assembly && !drafts.has('prompt') && (detail.prompt_provenance?.assembly_mode || 'finish_composite') !== value('assembly_mode')
      ? 'Write or edit the prompt for this assembly mode.' : ''));
  const empty = detail.slots.includes(null) || detail.slots.some(id => !id);
  const lockedId = detail.slots.find(id => detail.candidates[id]?.locked);
  const luna = detail.luna_review || {};
  const slots = detail.slots.map((id, index) => {
    const item = detail.candidates[id];
    const complete = item?.status === 'COMPLETE' && item.image;
    const running = isNarrativeActive(item?.status);
    const protectedImage = id && (id === detail.selected_id || item?.locked);
    const held = lockedId && lockedId !== id ? 'Unlock the current image first.' : '';
    const needsText = assembly && item?.scene_text_pending;
    const replaceReason = busyReason || (running ? 'Wait for this render to finish.'
      : protectedImage ? 'Clear the protected image before replacing it.' : renderReason);
    const actions = ['draft', 'final'].map(mode => action('regen-' + mode,
      mode === 'draft' ? 'Regen Draft' : 'Regen Final', {mode, disabledReason: replaceReason}));
    if (!item) return {key: String(index + 1), actions};
    const local = ['crop', 'unchanged'].includes(item.backdrop_adaptation?.operation) && item.source_snapshot;
    const request = item.render_request || {};
    const captured = request.inputs || [];
    const recorded = request.settings || {};
    const savedPrompt = request.prompt ?? item.prompt;
    const inputs = captured.map((input, i) => ({
      label: input.label || input.role || 'Reference ' + (i + 1),
      marker: input.marker || (savedPrompt?.includes('<image' + (input.image_index ?? i + 1) + '>')
        ? '<image' + (input.image_index ?? i + 1) + '>' : undefined),
      url: input.path ? artifactUrl('candidates/' + id + '/inputs/' + (i + 1)) + '&delivery=inline' : undefined,
    }));
    const version = item.scene_text_final?.image || item.image;
    const candidate = {
      id, quality: item.render_mode || 'draft', status: item.status, elapsedSeconds: item.render_duration_seconds,
      locked: item.locked, error: item.error, prompt: savedPrompt,
      negativePrompt: request.negative_prompt ?? recorded.negative_prompt,
      earlierPrompt: Boolean(complete && !local && item.source_change_fyi),
      image: version ? {url: imageUrl(id), label: 'Slot ' + (index + 1) + ' candidate', version} : undefined,
      inputs,
      notices: [needsText && 'Scene text changes pending', local && (item.backdrop_adaptation.operation === 'crop' ? 'Local crop' : 'Local reuse')].filter(Boolean),
      renderSettings: [
        ['Quality', recorded.render_mode ?? item.render_mode], ['Aspect ratio', recorded.aspect_ratio ?? item.aspect_ratio],
        ['Width', recorded.width ?? item.width], ['Height', recorded.height ?? item.height],
        ['Seed', request.seed ?? item.seed], ['Assembly mode', assemblyModes.find(([key]) => key === item.assembly_mode)?.[1]],
        ['Profile', recorded.profile], ['Steps', recorded.steps], ['CFG', recorded.cfg],
        ['Sampler', recorded.sampler_name], ['Scheduler', recorded.scheduler], ['Denoise', recorded.denoise],
      ].filter(([, value]) => value != null && value !== '').map(([label, value]) => ({label, value})),
      provenance: [
        item.prompt_provenance?.model, item.prompt_provenance?.edited && 'Manually edited',
        item.source_snapshot && [item.source_snapshot.scene_title, item.source_snapshot.title, item.backdrop_adaptation?.operation].filter(Boolean).join(' · '),
        item.assembly_snapshot?.layers?.filter(layer => layer.visible).map(layer => layer.label).join(' · '),
      ].filter(Boolean),
    };
    const ready = complete ? '' : 'Wait for a completed image.';
    actions.push(action('select', 'Select', {disabledReason: busyReason || ready || held || (id === detail.selected_id ? 'Already selected.' : '')}));
    actions.push(action(item.locked ? 'unlock' : 'lock', item.locked ? 'Unlock' : 'Lock', {
      disabledReason: busyReason || (item.locked ? '' : ready || held || (needsText ? 'Confirm scene text first.' : '')),
    }));
    if (item.status === 'FAILED') actions.push(action('retry', 'Retry', {disabledReason: busyReason}));
    if (complete && candidate.quality === 'draft' && !item.locked) actions.push(action('upscale', 'Upscale Draft', {disabledReason: busyReason}));
    actions.push(action('clear', 'Clear slot', {role: 'danger-text-action', disabledReason: busyReason || (running ? 'Wait for this render to finish.' : '')}));
    if (assembly) actions.push(action('edit-text', 'Edit Text', {placement: review, disabledReason: busyReason || ready || (item.locked ? 'Unlock this image before editing.' : '')}));
    actions.push(action('inventory', 'View in Inventory', {placement: review, disabledReason: busyReason || (!item.locked || !item.image ? 'Lock this image to view it in Inventory.' : '')}));
    actions.push(action('capture-task', 'Create task', {placement: review}));
    return {key: String(index + 1), candidate, actions};
  });
  const extra = [];
  const item = detail.candidates[reviewedId];
  const snapshot = item?.assembly_snapshot;
  if (snapshot && (snapshot.has_composite ?? (snapshot.assembly_mode || 'finish_composite') === 'finish_composite')) {
    const url = artifactUrl('candidates/' + reviewedId + '/composite');
    extra.push({key: 'composite:' + reviewedId, label: 'Raw composite', image: {url, label: 'Frozen raw composite'}});
  }
  if (detail.kind === 'backdrop' && item?.source_snapshot) {
    const index = item.render_request?.inputs?.findIndex(input => input.role === 'backdrop source');
    const input = slots.find(slot => slot.candidate?.id === reviewedId)?.candidate.inputs[index];
    if (input?.url) extra.push({key: 'backdrop:' + reviewedId, label: 'Captured backdrop', image: {url: input.url, label: input.label}});
  }
  const unlockedOthers = slots.filter(slot => slot.candidate && !slot.candidate.locked && slot.candidate.id !== detail.selected_id);
  const actions = [
    action('synthesize', 'Write Prompt', {group: 'prompt', role: 'primary', disabledReason: authorReason}),
    action('luna-review', 'Luna Review', {group: 'luna', disabledReason: busyReason || (luna.status === 'RUNNING' ? 'Review is running.' :
      slots.some(slot => slot.candidate?.status === 'COMPLETE' && slot.candidate.image) ? '' : 'Generate an image first.')}),
    action('delete-drafts', 'Delete Drafts', {group: 'bulk', role: 'danger-text-action', disabledReason: busyReason ||
      (slots.some(slot => slot.candidate?.quality === 'draft') ? '' : 'No Draft images.')}),
    action('delete-non-selected', 'Delete Non-Selected', {group: 'bulk', role: 'danger-text-action', disabledReason: busyReason ||
      (!unlockedOthers.length ? 'No non-selected images.' : unlockedOthers.some(slot => isNarrativeActive(slot.candidate.status)) ? 'Wait for active renders.' : '')}),
  ];
  if (reference && !localOnly) for (const mode of ['draft', 'final']) {
    actions.push(action('apply-' + mode, mode === 'draft' ? 'Apply Draft' : 'Apply Final', {group: 'render', mode,
      disabledReason: authorReason || sizingError || (!empty ? 'Requires one empty slot.' : '')}));
  }
  if (reference || unmodified) {
    const crop = reference && settings.crop_enabled;
    actions.push(action(crop ? 'crop' : 'reuse', crop ? 'Use Unmodified Crop' : 'Use Unmodified Image',
      {group: 'render', disabledReason: busyReason || (!empty ? 'Requires one empty slot.' : '')}));
  }
  const promptStatus = [
    working.includes(writing) && 'Writing prompt…',
    writing?.status === 'FAILED' && writing.error,
    pendingInterviews && 'Write Prompt uses saved, applied interview inputs.',
    detail.prompt_provenance?.model && 'Saved prompt: ' + detail.prompt_provenance.model,
    (detail.prompt_provenance?.edited || drafts.has('prompt')) && 'Manually edited',
  ].filter(Boolean).join(' · ');
  const renderStatus = [
    working.some(job => job.kind === 'image') && 'Image renders in progress.',
    detail.kind !== 'subscene' && 'Scene aspect ratio: ' + detail.scene_canvas,
    ...Object.entries(sizing).map(([mode, size]) => (mode === 'final' ? 'Final ' : 'Draft ') + size.width + ' × ' + size.height),
    reference && 'Apply writes a fresh prompt. Render shortcuts use the saved prompt.',
  ].filter(Boolean).join(' · ');
  return {scope: {key: scopeKey, title: detail.title}, revision, slots, selectedId: detail.selected_id,
    actions, comparisons: extra,
    lunaReview: {status: luna.status, criteria: luna.prompt, error: luna.error,
      entries: Object.fromEntries((['COMPLETE', 'OBSOLETE'].includes(luna.status) ? luna.entries || [] : [])
        .map((entry, index) => [entry.candidate_id, {rank: index + 1, assessment: entry.review}]))},
    renderControls: {promptFields: [{key: 'prompt_model', label: 'Prompt model', type: 'text',
      placeholder: 'Default: ' + defaultModel, value: value('prompt_model'), suggestions: models}],
    fields: [
      ...(!unmodified ? [{key: 'prompt', label: 'Final Qwen prompt', type: 'textarea', value: value('prompt'), disabled: llmBusy}] : []),
      ...(detail.kind === 'subscene' ? [{key: 'aspect_ratio', label: 'Canvas size aspect ratio', type: 'text', value: value('aspect_ratio')}] : []),
      ...(assembly ? [{key: 'assembly_mode', label: 'Assembly mode', type: 'select', value: value('assembly_mode'),
        options: assemblyModes.map(([value, label]) => ({value, label}))}] : []),
    ], readiness: {draft: renderReason, final: renderReason}, promptStatus, renderStatus}};
}
