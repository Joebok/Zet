/** Image-card presentation only. Workflow handlers and eligibility stay with callers. */
(() => {
  const paths = {
    review: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    select: '<circle cx="12" cy="12" r="9"/><path d="m7 12 3 3 7-7"/>',
    unselect: '<circle cx="12" cy="12" r="9"/><path d="M8 12h8"/>',
    regenerate: '<path d="M20 7v5h-5M4 17v-5h5M6 6a8 8 0 0 1 13 2M18 18a8 8 0 0 1-13-2"/>',
    retry: '<path d="M3 4v6h6M4 9a8 8 0 1 1 0 7"/>',
    clear: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>',
    lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4M12 14v3"/>',
    unlock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 7-2M12 14v3"/>',
    download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
    copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
    save: '<path d="M4 3h13l4 4v14H3V3h1ZM7 3v6h10V3M7 21v-8h10v8"/>',
    previous: '<path d="m15 5-7 7 7 7"/>',
    next: '<path d="m9 5 7 7-7 7"/>',
    up: '<path d="m5 15 7-7 7 7"/>',
    down: '<path d="m5 9 7 7 7-7"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    generate: '<path d="M12 3v18M3 12h18"/>',
    refine: '<path d="m4 20 4-1L20 7l-3-3L5 16l-1 4ZM14 7l3 3"/>',
    task: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V2h6v2M9 10h6M9 14h6M9 18h3"/>',
    import: '<path d="M12 3v12m-5-5 5 5 5-5M3 14v7h18v-7M17 5h4M19 3v4"/>',
    details: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v1"/>',
  };
  const scopes = [
    '.local-pipeline-candidate', '.local-pipeline-selected-card',
    '.local-pipeline-review-dialog', '.image-generation-result', '.image-generation-review',
    '.image-generation-reference-controls', '.mc-slot-actions', '.mc-review', '.mc-reference',
    '.narrative-slot', '#image-dialog', '.inventory-card-actions', '.fullscreen-image-overlay',
    '#character-phone-viewer', '.character-refinement .refinement-layout > section:first-child',
    '.image-card-actions', '.render-image-viewer', '.image-catalog-managed-buttons',
    '#entity-library-preview-actions', '#turnaround-aux-table',
  ].join(',');
  const standaloneControls = [
    '#phase-comparison-prev', '#phase-comparison-next', '#turnaround-save-partial',
    '#entity-library-modify-generated', '#entity-library-replace', '#entity-library-delete',
    '#image-generation-review-import', '#image-generation-review-update',
  ].join(',');
  function actionFor(label) {
    const value = label.toLowerCase();
    if (/unselect/.test(value)) return 'unselect';
    if (/selected|select|use this image/.test(value)) return 'select';
    if (/unlock/.test(value)) return 'unlock';
    if (/lock/.test(value)) return 'lock';
    if (/regenerat|regen/.test(value)) return 'regenerate';
    if (/retry/.test(value)) return 'retry';
    if (/clear|delete|remove|discard|archive/.test(value)) return 'clear';
    if (/download/.test(value)) return 'download';
    if (/copied/.test(value)) return 'select';
    if (/copy/.test(value)) return 'copy';
    if (/save/.test(value)) return 'save';
    if (/close|cancel/.test(value)) return 'close';
    if (/rank up/.test(value)) return 'up';
    if (/rank down/.test(value)) return 'down';
    if (/prev|^‹$|^<$/.test(value)) return 'previous';
    if (/next|^›$|^>$/.test(value)) return 'next';
    if (/create task/.test(value)) return 'task';
    if (/refine|edit|modify|replace|partial/.test(value)) return 'refine';
    if (/add to|update.*inventory|import/.test(value)) return 'import';
    if (/generate|add renders/.test(value)) return 'generate';
    if (/review|inspect|compare|full.size/.test(value)) return 'review';
    return 'details';
  }
  function decorate(control, action, label) {
    if (!control) return control;
    label = label || control.getAttribute('aria-label') || control.textContent.trim();
    action = action || actionFor(label);
    const current = control.querySelector(':scope > svg[data-card-icon]');
    const reason = control.title !== control.dataset.imageTitle ? control.title : control.dataset.imageReason || '';
    const title = reason && reason !== label ? `${label} · ${reason}` : label;
    if (control.title !== title) control.title = title;
    control.dataset.imageTitle = title;
    control.dataset.imageReason = reason;
    if (current && control.dataset.imageAction === action && control.dataset.imageLabel === label) return control;
    control.classList.add('image-icon-action');
    control.dataset.imageAction = action;
    control.dataset.imageLabel = label;
    control.setAttribute('aria-label', label);
    control.innerHTML = `<svg data-card-icon aria-hidden="true" focusable="false" viewBox="0 0 24 24">${paths[action] || paths.details}</svg>`;
    const text = document.createElement('span');
    text.className = 'image-action-label'; text.textContent = label;
    control.append(text);
    return control;
  }
  function scan(root = document) {
    const controls = root.querySelectorAll(`${scopes.split(',').map(scope => `${scope.trim()} button, ${scope.trim()} a`).join(',')},${standaloneControls}`);
    for (const control of controls) {
      if (control.querySelector('img,input') || control.closest('.character-phone-links') || control.classList.contains('image-card-text-control')) continue;
      const current = control.querySelector(':scope > svg[data-card-icon]');
      // Callers may replace text when a dynamic action changes. Read that new label.
      const label = current ? control.dataset.imageLabel : control.dataset.imageAction
        ? control.textContent.trim() || control.getAttribute('aria-label')
        : control.getAttribute('aria-label') || control.textContent.trim();
      if (label) decorate(control, current ? control.dataset.imageAction : undefined, label);
    }
  }
  window.ZetImageCardUI = { decorate, scan };
  let scheduled = false;
  const observer = new MutationObserver(records => {
    if (!records.some(record => record.type === 'childList' || ['title', 'aria-label'].includes(record.attributeName))) return;
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => { scheduled = false; scan(); });
  });
  observer.observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['title', 'aria-label'] });
  scan();
})();
