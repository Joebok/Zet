/* Shared, transient zoom for images inside candidate review dialogs. */
(function () {
  const states = new WeakMap();
  function styleControls(root) {
    const labels = {"zoom in":"Zoom In", "zoom out":"Zoom Out", "reset zoom":"Reset Zoom"};
    for (const control of root.querySelectorAll("button")) {
      const label = labels[(control.getAttribute("aria-label") || control.textContent.trim()).toLowerCase()];
      if (!label) continue;
      control.classList.add("review-zoom-control", "image-card-text-control");
      control.textContent = label;
      control.setAttribute("aria-label", label);
      control.title = label;
    }
  }
  function attach(dialog, getImages) {
    if (!dialog) return;
    styleControls(dialog);
    const state = {scale: 1, x: .5, y: .5, panX: 0, panY: 0, key: "", pointers: new Map(), gesture: null};
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
        img.style.transform = `translate(${state.panX}px, ${state.panY}px) scale(${state.scale})`;
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
    dialog.addEventListener("pointerdown", event => {
      const img = event.target.closest?.(".review-zoom-viewport img");
      if (!img || !images().includes(img) || event.button !== 0) return;
      const box = img.closest(".review-zoom-viewport");
      state.pointers.set(event.pointerId, {x:event.clientX, y:event.clientY});
      try { box.setPointerCapture(event.pointerId); } catch {}
      if (state.pointers.size === 1 && state.scale > 1) {
        state.gesture = {type:"pan", pointerId:event.pointerId, x:event.clientX, y:event.clientY, panX:state.panX, panY:state.panY};
      } else if (state.pointers.size === 2) {
        const points = [...state.pointers.values()];
        state.gesture = {type:"pinch", distance:Math.max(1, Math.hypot(points[0].x-points[1].x, points[0].y-points[1].y)), scale:state.scale};
      }
      if (state.gesture) event.preventDefault();
    }, {signal:events.signal});
    dialog.addEventListener("pointermove", event => {
      if (!state.pointers.has(event.pointerId) || !state.gesture) return;
      state.pointers.set(event.pointerId, {x:event.clientX, y:event.clientY});
      const img = event.target.closest?.(".review-zoom-viewport img") || images()[0];
      const box = img?.closest(".review-zoom-viewport");
      if (!box) return;
      if (state.gesture.type === "pan" && state.gesture.pointerId === event.pointerId) {
        state.panX = state.gesture.panX + event.clientX - state.gesture.x;
        state.panY = state.gesture.panY + event.clientY - state.gesture.y;
        const rect = box.getBoundingClientRect();
        const fit = Math.min(rect.width / img.naturalWidth, rect.height / img.naturalHeight);
        const maxX = Math.max(0, (img.naturalWidth * fit * state.scale - rect.width) / 2);
        const maxY = Math.max(0, (img.naturalHeight * fit * state.scale - rect.height) / 2);
        state.panX = Math.max(-maxX, Math.min(maxX, state.panX));
        state.panY = Math.max(-maxY, Math.min(maxY, state.panY));
      } else if (state.gesture.type === "pinch" && state.pointers.size > 1) {
        const points = [...state.pointers.values()];
        const distance = Math.max(1, Math.hypot(points[0].x-points[1].x, points[0].y-points[1].y));
        state.scale = Math.max(1, Math.min(4, state.gesture.scale * distance / state.gesture.distance));
      }
      event.preventDefault(); apply();
    }, {passive:false, signal:events.signal});
    const finishPointer = event => {
      state.pointers.delete(event.pointerId);
      if (state.pointers.size < 2) state.gesture = state.scale > 1 && state.pointers.size === 1
        ? (() => { const [pointerId, point] = [...state.pointers.entries()][0]; return {type:"pan", pointerId, x:point.x, y:point.y, panX:state.panX, panY:state.panY}; })()
        : null;
    };
    dialog.addEventListener("pointerup", finishPointer, {signal:events.signal});
    dialog.addEventListener("pointercancel", finishPointer, {signal:events.signal});
    dialog.addEventListener("close", () => { if (!dialog.open) reset(dialog); }, {signal: events.signal});
    return {sync(key, resetOnChange = true) {
      if (resetOnChange && key !== state.key) { state.scale = 1; state.x = .5; state.y = .5; state.panX = 0; state.panY = 0; }
      state.key = key; apply();
    }, reset() { reset(dialog); }, step(direction) {
      if (!images().length) return;
      state.scale = Math.max(1, Math.min(4, state.scale * 1.25 ** direction));
      if (state.scale === 1) state.panX = state.panY = 0;
      apply();
    }, dispose() {
      events.abort();
      reset(dialog);
      states.delete(dialog);
    }};
  }
  function reset(dialog) {
    const state = states.get(dialog); if (!state) return;
    state.scale = 1; state.x = .5; state.y = .5; state.panX = state.panY = 0; state.pointers.clear(); state.gesture = null;
    dialog.querySelectorAll(".review-zoom-viewport img").forEach(img => { img.style.transform = ""; img.style.transformOrigin = ""; });
  }
  let standalone;
  function openStandalone(src, alt = "Image") {
    if (!src) return;
    if (!standalone) {
      const dialog = document.createElement("dialog"); dialog.className = "fullscreen-image-overlay standalone-image-viewer";
      const tools = document.createElement("div"); tools.className = "fullscreen-image-tools";
      const image = document.createElement("img"); image.alt = "";
      const empty = document.createElement("p"); empty.className = "fullscreen-image-empty"; empty.hidden = true;
      const zoom = attach(dialog, () => [image]);
      const button = (action, label, text, callback) => {
        const control = document.createElement("button"); control.type = "button"; control.textContent = text;
        control.setAttribute("aria-label", label); control.title = label;
        if (action) window.ZetImageCardUI?.decorate(control, action, label);
        control.addEventListener("click", callback); tools.append(control); return control;
      };
      button(null, "Zoom in", "+", () => zoom.step(1));
      button(null, "Zoom out", "−", () => zoom.step(-1));
      button(null, "Reset zoom", "Reset", () => zoom.reset());
      const close = button("close", "Close image", "Close", () => dialog.close());
      close.classList.add("fullscreen-image-close");
      dialog.append(tools, image, empty); document.body.append(dialog);
      styleControls(dialog);
      dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });
      image.addEventListener("load", () => {
        empty.hidden = true; image.hidden = false;
        const viewport = image.closest(".review-zoom-viewport"), ratio = image.naturalWidth / image.naturalHeight;
        viewport.style.width = `min(100vw, ${image.naturalWidth}px, calc(100vh * ${ratio}))`;
        viewport.style.height = `min(100vh, ${image.naturalHeight}px, calc(100vw / ${ratio}))`;
        zoom.sync(image.src);
      });
      image.addEventListener("error", () => {
        image.hidden = true; empty.textContent = "Image unavailable. Close the viewer and try again."; empty.hidden = false;
      });
      standalone = {dialog, image, empty, zoom};
    }
    standalone.image.hidden = false; standalone.empty.hidden = true;
    standalone.image.alt = alt; standalone.image.src = src; standalone.zoom.sync(src);
    standalone.dialog.showModal();
  }
  function enableStandalone(image) {
    if (!image || image.dataset.fullscreenViewerBound) return image;
    image.dataset.fullscreenViewerBound = "true"; image.tabIndex = 0; image.setAttribute("role", "button");
    image.setAttribute("aria-label", `Open full screen: ${image.alt || "image"}`);
    image.addEventListener("click", () => openStandalone(image.currentSrc || image.src, image.alt));
    image.addEventListener("keydown", event => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault(); openStandalone(image.currentSrc || image.src, image.alt);
    });
    return image;
  }
  window.ZetReviewImageZoom = {attach, openStandalone, enableStandalone};
})();
