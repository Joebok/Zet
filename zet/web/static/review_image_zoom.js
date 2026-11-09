/* Shared, transient zoom for images inside candidate review dialogs. */
(function () {
  const states = new WeakMap();
  function attach(dialog, getImages) {
    if (!dialog) return;
    const state = {scale: 1, x: .5, y: .5, key: ""};
    const events = new AbortController();
    states.set(dialog, state);
    function prepare() {
      for (const img of getImages() || []) {
        if (!(img instanceof HTMLImageElement) || img.closest(".review-zoom-viewport")) continue;
        const box = document.createElement("span"); box.className = "review-zoom-viewport";
        if (img.naturalWidth && img.naturalHeight) box.style.aspectRatio = `${img.naturalWidth} / ${img.naturalHeight}`;
        img.before(box); box.append(img);
      }
    }
    const images = () => (getImages() || []).filter(img => img instanceof HTMLImageElement && img.isConnected && img.complete && img.naturalWidth);
    function apply() {
      prepare();
      for (const img of images()) {
        const box = img.closest(".review-zoom-viewport");
        if (!box) continue;
        img.style.transformOrigin = `${state.x * 100}% ${state.y * 100}%`;
        img.style.transform = `scale(${state.scale})`;
      }
    }
    dialog.addEventListener("wheel", event => {
      if (!dialog.open || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
      const img = event.target.closest?.(".review-zoom-viewport img");
      if (!img || !images().includes(img)) return;
      const box = img.closest(".review-zoom-viewport");
      const r = box.getBoundingClientRect();
      const baseX = (event.clientX - r.left - (1 - state.scale) * state.x * r.width) / state.scale;
      const baseY = (event.clientY - r.top - (1 - state.scale) * state.y * r.height) / state.scale;
      const fit = Math.min(r.width / img.naturalWidth, r.height / img.naturalHeight);
      const artworkWidth = img.naturalWidth * fit, artworkHeight = img.naturalHeight * fit;
      const scale = state.scale * Math.exp(-event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? r.height : 1) / 500);
      const next = Math.max(1, Math.min(4, scale));
      if (next === state.scale) return;
      const x = (baseX - (r.width - artworkWidth) / 2) / artworkWidth;
      const y = (baseY - (r.height - artworkHeight) / 2) / artworkHeight;
      if (x < 0 || x > 1 || y < 0 || y > 1) return;
      state.x = Math.max(0, Math.min(1, x)); state.y = Math.max(0, Math.min(1, y)); state.scale = next;
      event.preventDefault(); apply();
    }, {passive: false, signal: events.signal});
    dialog.addEventListener("close", () => { if (!dialog.open) reset(dialog); }, {signal: events.signal});
    return {sync(key, resetOnChange = true) {
      if (resetOnChange && key !== state.key) { state.scale = 1; state.x = .5; state.y = .5; }
      state.key = key; apply();
    }, reset() { reset(dialog); }, step(direction) {
      if (!images().length) return;
      state.scale = Math.max(1, Math.min(4, state.scale * 1.25 ** direction));
      apply();
    }, dispose() {
      events.abort();
      reset(dialog);
      states.delete(dialog);
    }};
  }
  function reset(dialog) {
    const state = states.get(dialog); if (!state) return;
    state.scale = 1; state.x = .5; state.y = .5;
    dialog.querySelectorAll(".review-zoom-viewport img").forEach(img => { img.style.transform = ""; img.style.transformOrigin = ""; });
  }
  window.ZetReviewImageZoom = {attach};
})();
