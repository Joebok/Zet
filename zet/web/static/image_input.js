/** Touch clipboard access feeds the same file-input path as choosing a file. */
(() => {
  const attached = new WeakMap();
  function attach(zone, input, {onInventory} = {}) {
    if (!zone || !input || attached.has(zone)) return;
    const controls = document.createElement("div");
    controls.className = "image-input-actions";
    const paste = document.createElement("button");
    paste.type = "button";
    paste.textContent = "Paste image";
    const choose = document.createElement("button");
    choose.type = "button";
    choose.textContent = "Choose image";
    const inventory = document.createElement("button");
    inventory.type = "button";
    inventory.textContent = "Image Inventory";
    inventory.hidden = typeof onInventory !== "function";
    const status = document.createElement("span");
    status.className = "image-input-status";
    status.setAttribute("role", "status");
    controls.append(paste, choose, inventory, status);
    zone.after(controls);
    zone.removeAttribute("contenteditable");
    zone.setAttribute("role", "group");
    zone.tabIndex = 0;
    zone.addEventListener("click", () => zone.focus({ preventScroll: true }));
    const label = input.parentElement;
    controls.setAttribute("role", "group");
    controls.setAttribute("aria-label", input.getAttribute("aria-label") || zone.getAttribute("aria-label") || input.labels?.[0]?.textContent.trim() || "Image input");
    const nested = zone.contains(input);
    zone.textContent = "Paste an image or choose a file.";
    if (nested) zone.append(input);
    input.hidden = true;
    if (!nested && label?.tagName === "LABEL" && label.children.length === 1) label.hidden = true;
    let reading = false;
    const locked = () => input.disabled || zone.getAttribute("aria-disabled") === "true";
    const sync = () => {
      paste.disabled = choose.disabled = inventory.disabled = locked() || reading;
      controls.hidden = zone.hidden;
    };
    choose.addEventListener("click", () => { if (!locked()) { status.textContent = ""; input.click(); } });
    inventory.addEventListener("click", async () => {
      if (locked() || reading || typeof onInventory !== "function") return;
      status.textContent = "";
      inventory.disabled = true;
      const context = contextKey();
      try {
        const item = await window.ZetImageInventoryPicker.open({onSelect: async selected => {
          if (!zone.isConnected || locked() || context !== contextKey()) throw new Error("The workspace changed. Choose an image again in the current input.");
          await onInventory(selected);
        }});
        if (item) status.textContent = `${item.label || item.tag || "Image"} selected from Image Inventory.`;
      } catch (error) {
        status.textContent = `Unable to select from Image Inventory: ${error.message}`;
      } finally {
        inventory.disabled = locked();
      }
    });
    const contextKey = () => [location.href, ...["universe-select", "character-select", "phase-select"].map(id => document.getElementById(id)?.value || "")].join("\u0000");
    paste.addEventListener("click", async () => {
      if (locked() || reading) return;
      status.textContent = "";
      if (!window.isSecureContext || !navigator.clipboard?.read) {
        status.textContent = "Image paste is unavailable here. Choose an image instead.";
        return;
      }
      reading = true;
      const context = contextKey();
      sync();
      try {
        // Start the read in the tap handler, before any asynchronous work.
        const items = await navigator.clipboard.read();
        for (const item of items) {
          const type = item.types.find(type => type.startsWith("image/"));
          if (!type) continue;
          const blob = await item.getType(type);
          if (!zone.isConnected || locked()) return;
          if (context !== contextKey()) {
            status.textContent = "The workspace changed. Paste again into the current image input.";
            return;
          }
          const suffix = type === "image/jpeg" ? "jpg" : type.split("/")[1].replace(/[^a-z0-9]/gi, "") || "png";
          const transfer = new DataTransfer();
          transfer.items.add(new File([blob], `pasted-image.${suffix}`, { type }));
          input.files = transfer.files;
          input.dispatchEvent(new Event("change", { bubbles: true }));
          status.textContent = "Pasted image received. Check the preview or page message.";
          return;
        }
        status.textContent = "The clipboard has no image. Copy an image or choose a file.";
      } catch (error) {
        status.textContent = error.name === "NotAllowedError" || error.name === "AbortError"
          ? "Paste was not allowed or was dismissed. Try again and allow Paste, or choose an image."
          : "Unable to read this image. Try choosing an image instead.";
      } finally {
        reading = false;
        sync();
      }
    });
    const observer = new MutationObserver(sync);
    observer.observe(input, { attributes: true, attributeFilter: ["disabled"] });
    observer.observe(zone, { attributes: true, attributeFilter: ["aria-disabled", "hidden"] });
    attached.set(zone, controls);
    sync();
  }
  window.ZetImageInput = { attach };
})();
