/* Shared capability-aware model selection. Original controls retain form contracts. */
(() => {
  let catalog = null;
  let pending = null;
  const attached = new WeakMap();
  const known = {
    "setting-codex-default-model": { providers: ["codex"], bareCodex: true },
    "setting-image-prompt-generation-model": { required: ["vision"] },
    "setting-costume-wizard-model": { required: ["vision"] },
    "setting-quick-character-wizard-model": { required: ["vision"] },
    "image-reconstruction-model": { required: ["vision"] },
    "mc-model": { required: ["vision"] },
  };
  const dialog = document.createElement("dialog");
  dialog.id = "ai-model-picker";
  dialog.className = "ai-model-picker";
  dialog.innerHTML = `<form method="dialog"><h2>Select AI model</h2>
    <p data-model-status role="status"></p>
    <label>Codex<select data-provider="codex" aria-label="Codex model"></select></label>
    <label>Ollama<select data-provider="ollama" aria-label="Ollama model"></select></label>
    <p data-model-error role="alert"></p><div class="button-row">
    <button type="button" data-model-refresh>Refresh models</button>
    <button type="button" data-model-default>Use configured default</button>
    <button value="cancel">Cancel</button><button type="button" data-model-apply>Apply</button>
    </div></form>`;
  document.body.append(dialog);
  const dropdowns = [...dialog.querySelectorAll("[data-provider]")];
  let resolve = null;
  let options = {};
  function eligible(item) {
    return (options.providers || ["codex", "ollama"]).includes(item.provider)
      && (options.required || []).every(capability => (item.capabilities || []).includes(capability));
  }
  async function load(refresh = false) {
    const response = await fetch("/api/ai/models", { method: refresh ? "POST" : "GET" });
    if (!response.ok) throw new Error((await response.json()).detail || "Model catalog unavailable");
    catalog = await response.json();
    return catalog;
  }
  function render(value) {
    for (const control of dropdowns) {
      const provider = control.dataset.provider;
      control.replaceChildren(new Option("Choose a model", ""));
      for (const item of (catalog?.models || []).filter(item => item.provider === provider && eligible(item))
        .sort((a, b) => a.name.localeCompare(b.name))) control.add(new Option(item.name, item.id));
      control.value = [...control.options].some(item => item.value === value) ? value : "";
      control.disabled = !(options.providers || ["codex", "ollama"]).includes(provider);
    }
    const unavailable = value && !(catalog?.models || []).some(item => item.id === value && eligible(item));
    dialog.querySelector("[data-model-error]").textContent = unavailable
      ? `Saved selection ${value} is unavailable or incompatible. Choose a compatible model.`
      : !(catalog?.models || []).some(eligible) ? "No compatible models are cached. Refresh AI_Proxy's catalog." : "";
    dialog.querySelector("[data-model-status]").textContent = catalog?.refreshed_at
      ? `Catalog: ${catalog.refreshed_at}${catalog.stale ? " · cached; provider discovery unavailable" : ""}`
      : "No cached catalog. Start AI_Proxy and refresh models.";
    dialog.querySelector("[data-model-default]").hidden = !options.allowDefault;
  }
  function finish(value) {
    const callback = resolve;
    resolve = null;
    dialog.close();
    callback?.(value);
  }
  dropdowns.forEach(control => control.addEventListener("change", () => {
    if (control.value) dropdowns.filter(other => other !== control).forEach(other => { other.value = ""; });
    dialog.querySelector("[data-model-error]").textContent = "";
  }));
  dialog.querySelector("[data-model-apply]").addEventListener("click", () => {
    const values = dropdowns.map(control => control.value).filter(Boolean);
    if (values.length !== 1) {
      dialog.querySelector("[data-model-error]").textContent = "Select one compatible model.";
      return;
    }
    finish(values[0]);
  });
  dialog.querySelector("[data-model-default]").addEventListener("click", () => finish(""));
  dialog.addEventListener("close", () => { if (resolve) { const callback = resolve; resolve = null; callback(null); } });
  dialog.querySelector("[data-model-refresh]").addEventListener("click", async () => {
    try {
      await load(true);
      render(dropdowns.map(control => control.value).find(Boolean) || "");
      dialog.querySelector("[data-model-status]").textContent += " · refresh requested; AI_Proxy updates the shared catalog in the background";
    } catch (error) { dialog.querySelector("[data-model-error]").textContent = error.message; }
  });
  async function open(settings = {}) {
    if (resolve) finish(null);
    options = settings;
    const answer = new Promise(callback => { resolve = callback; });
    render(settings.value || "");
    dialog.showModal();
    try { await (pending ||= load().finally(() => { pending = null; })); render(settings.value || ""); }
    catch (error) { dialog.querySelector("[data-model-error]").textContent = error.message; }
    return answer;
  }
  function attach(control, settings = {}) {
    if (attached.has(control)) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "navigation-action ai-model-control";
    button.dataset.modelFor = control.id;
    control.hidden = true;
    control.after(button);
    const sync = () => { button.textContent = control.value || "Use configured default"; button.disabled = control.disabled; };
    button.addEventListener("click", async () => {
      const value = await open({ ...settings, value: settings.bareCodex && control.value ? `codex:${control.value}` : control.value });
      if (value === null) return;
      const selected = settings.bareCodex ? value.replace(/^codex:/, "") : value;
      if (control.tagName === "SELECT" && ![...control.options].some(item => item.value === selected)) control.add(new Option(selected, selected));
      control.value = selected;
      control.dispatchEvent(new Event("input", { bubbles: true }));
      control.dispatchEvent(new Event("change", { bubbles: true }));
      sync();
    });
    control.addEventListener("change", sync);
    new MutationObserver(sync).observe(control, { childList: true, subtree: true, attributes: true });
    attached.set(control, button);
    sync();
  }
  function discover() {
    document.querySelectorAll('select[id^="setting-"][id$="-model"], #image-reconstruction-model, #mc-model, input[list="narrative-model-options"], [data-ai-model-picker]').forEach(control => {
      const narrative = control.matches('input[list="narrative-model-options"]');
      const gate = /gate|review|analysis|description/.test(control.id) || control.hasAttribute("data-ai-vision");
      attach(control, { ...(gate ? { required: ["vision"] } : {}), ...(known[control.id] || {}), ...(narrative ? { allowDefault: true } : {}) });
    });
  }
  window.ZetModelPicker = { open, attach, refresh: () => load(true) };
  new MutationObserver(discover).observe(document.body, { childList: true, subtree: true });
  discover();
})();
