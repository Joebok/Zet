(() => {
  let dialog, search, status, results, resolveSelection, onSelection, requestGeneration = 0;
  const escape = value => String(value ?? "").replace(/[&<>"']/g, character =>
    ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"})[character]);

  function ensureDialog() {
    if (dialog) return;
    dialog = document.createElement("dialog");
    dialog.className = "image-inventory-picker";
    dialog.setAttribute("aria-labelledby", "image-inventory-picker-title");
    dialog.innerHTML = `<header><h2 id="image-inventory-picker-title">Choose from Image Inventory</h2><button type="button" data-close>Close</button></header>
      <form data-search><label>Search inventory<input type="search" data-query></label><button type="submit">Search</button></form>
      <p data-status role="status" aria-live="polite"></p><div data-results class="image-inventory-picker-results"></div>`;
    document.body.append(dialog);
    search = dialog.querySelector("[data-search]");
    status = dialog.querySelector("[data-status]");
    results = dialog.querySelector("[data-results]");
    search.addEventListener("submit", event => { event.preventDefault(); void load(); });
    dialog.querySelector("[data-close]").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => { resolveSelection?.(null); resolveSelection = null; onSelection = null; });
  }

  async function load() {
    const generation = ++requestGeneration;
    const params = new URLSearchParams({q:dialog.querySelector("[data-query]").value.trim(), limit:"50"});
    status.textContent = "Searching Image Inventory…";
    results.replaceChildren();
    try {
      const response = await fetch(`/api/image-catalog?${params}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Unable to search Image Inventory.");
      if (generation !== requestGeneration) return;
      const items = payload.items || [];
      status.textContent = `${items.length} of ${payload.total ?? items.length} images shown.`;
      if (!items.length) { results.textContent = "No images match. Try another search."; return; }
      const fragment = document.createDocumentFragment();
      for (const item of items) {
        const card = document.createElement("article");
        const image = document.createElement("img");
        const imagePath = item.thumbnail_path || item.image_path;
        if (imagePath) { const params = new URLSearchParams({path:imagePath}); image.src = `/api/file?${params}`; }
        image.alt = ""; image.loading = "lazy";
        const title = document.createElement("strong"); title.textContent = item.label || item.tag || "Untitled image";
        const detail = document.createElement("small");
        detail.textContent = [item.source_type, item.character, item.phase, item.costume, item.tag].filter(Boolean).join(" · ");
        const choose = document.createElement("button"); choose.type = "button"; choose.textContent = "Choose image";
        choose.addEventListener("click", async () => {
          try { await onSelection(item); resolveSelection?.(item); resolveSelection = null; dialog.close(); }
          catch (error) { status.textContent = `Image was not added: ${error.message}`; }
        });
        card.append(image, title, detail, choose); fragment.append(card);
      }
      results.replaceChildren(fragment);
    } catch (error) {
      if (generation !== requestGeneration) return;
      status.textContent = `Image Inventory unavailable: ${error.message}`;
    }
  }

  async function open({onSelect} = {}) {
    ensureDialog();
    if (typeof onSelect !== "function") throw new TypeError("Image Inventory selection needs a workflow handler.");
    onSelection = onSelect;
    dialog.querySelector("[data-query]").value = "";
    const selection = new Promise(resolve => { resolveSelection = resolve; });
    dialog.showModal();
    dialog.querySelector("[data-query]").focus();
    void load();
    return selection;
  }

  window.ZetImageInventoryPicker = {open};
})();
