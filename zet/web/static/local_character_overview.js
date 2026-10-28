(() => {
  let context = null;
  let timer = null;
  let generation = 0;
  let loading = false;
  let snapshot = "";
  const outcomes = new Map();
  const pending = new Set();
  const host = () => document.querySelector("#local-overview-groups");
  const status = () => document.querySelector("#local-overview-status");
  const keyFor = (slot) => JSON.stringify([slot.character, slot.phase, slot.name]);
  const pathFor = (slot, action) => `/api/local/character-overview/${[slot.character, slot.phase, slot.name].map(encodeURIComponent).join("/")}/${action}`;

  function make(tag, className, text) {
    const node = document.createElement(tag);
    node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function render(data) {
    const focused = document.activeElement;
    const focusKey = focused?.closest("[data-slot]")?.dataset.slot;
    const focusAction = focused?.dataset.action;
    const rows = (data.rows || []).map((row) => {
      const section = make("section", "overview-group");
      section.append(make("h2", "", `${row.character} · ${row.phase}`));
      const grid = make("div", "overview-slots");
      for (const item of row.costumes || []) {
        const slot = {...item, character: row.character, phase: row.phase};
        const key = keyFor(slot);
        const card = make("article", "overview-slot");
        card.dataset.slot = key;
        card.append(make("h3", "", slot.name));
        if (slot.image_url) {
          const image = make("img", "overview-image");
          const url = new URL(slot.image_url, location.origin);
          url.searchParams.set("universe_id", context.universeId);
          image.src = url.href;
          image.alt = `Locked front view · ${row.character} · ${row.phase} · ${slot.name}`;
          image.loading = "lazy";
          card.append(image);
        } else card.append(make("div", "overview-placeholder", "No locked front image"));
        const state = slot.image_url ? "Locked" : slot.message || ({
          IDLE: "Ready to generate.", QUEUED: "Queued.",
          RUNNING: `Working on ${slot.pipeline}…`, CANCELLED: "Stopped. Start again to retry.",
        }[slot.state] || slot.state);
        card.append(make("p", `overview-state${slot.state === "ERROR" ? " error" : ""}`, state));
        const actions = make("div", "button-row");
        const active = ["RUNNING", "QUEUED"].includes(slot.state);
        if (active || !slot.image_url) {
          const action = active ? "stop" : "autogenerate";
          const button = make("button", active ? "neutral-action" : "primary-action",
            active ? "Stop" : ["ERROR", "CANCELLED", "STOPPED"].includes(slot.state) ? "Try again" : "Autogenerate");
          button.type = "button";
          button.dataset.action = action;
          button.disabled = pending.has(key);
          button.addEventListener("click", () => void act(slot, action, button));
          actions.append(button);
        }
        if (slot.run_id && slot.pipeline) {
          const review = make("a", "navigation-action", "Review batch");
          const params = new URLSearchParams({page: `local-${slot.pipeline}`, local_batch: slot.run_id,
            character: row.character, phase: row.phase, universe_id: context.universeId});
          if (slot.pipeline === "costume-dressing") params.set("local_costume", slot.name);
          review.href = `/?${params}`;
          actions.append(review);
        }
        const outcome = outcomes.get(key);
        const message = make("p", `overview-outcome${outcome?.error ? " error" : ""}`, outcome?.text || "");
        message.setAttribute("role", "status");
        card.append(actions, message);
        grid.append(card);
      }
      if (!grid.children.length) grid.append(make("p", "muted", "No costumes for this phase."));
      section.append(grid);
      return section;
    });
    host().replaceChildren(...(rows.length ? rows : [make("p", "muted", "No characters or phases were found.")]));
    if (focusKey && focusAction) {
      const card = [...host().querySelectorAll("[data-slot]")].find((node) => node.dataset.slot === focusKey);
      card?.querySelector(`[data-action="${focusAction}"]`)?.focus({preventScroll: true});
    }
  }

  async function refresh() {
    if (!context || loading || pending.size) return;
    const current = generation;
    loading = true;
    try {
      const data = await context.fetchJson("/api/local/character-overview", {headers: {"X-Zet-Universe": context.universeId}});
      if (current !== generation || pending.size) return;
      const next = JSON.stringify(data);
      if (next !== snapshot) { render(data); snapshot = next; }
      status().textContent = "Overview refreshes automatically while this page is open.";
      status().classList.remove("error");
    } catch (error) {
      if (current !== generation) return;
      status().textContent = error.message;
      status().classList.add("error");
    } finally { if (current === generation) loading = false; }
  }

  async function act(slot, action, button) {
    const key = keyFor(slot);
    if (!context || pending.has(key)) return;
    const current = generation;
    const request = context;
    const message = button.closest("[data-slot]").querySelector(".overview-outcome");
    pending.add(key);
    button.disabled = true;
    message.classList.remove("error");
    message.textContent = action === "stop" ? "Requesting stop…" : "Queuing generation…";
    try {
      await request.fetchJson(pathFor(slot, action), {method: "POST", headers: {"X-Zet-Universe": request.universeId}});
      if (current !== generation) return;
      outcomes.set(key, {text: action === "stop" ? "Stop requested." : "Generation request accepted."});
    } catch (error) {
      if (current !== generation) return;
      outcomes.set(key, {text: `Could not confirm the action. ${error.message}`, error: true});
    } finally {
      if (current === generation) {
        const outcome = outcomes.get(key);
        message.textContent = outcome?.text || "";
        message.classList.toggle("error", Boolean(outcome?.error));
        button.disabled = false;
        pending.delete(key);
        snapshot = "";
        await refresh();
      }
    }
  }

  window.ZetLocalCharacterOverview = {
    activate(options) {
      this.deactivate();
      context = options;
      host().replaceChildren();
      status().textContent = "Loading…";
      status().classList.remove("error");
      void refresh();
      timer = setInterval(refresh, 2500);
    },
    deactivate() {
      clearInterval(timer);
      generation += 1;
      context = null;
      loading = false;
      snapshot = "";
      outcomes.clear();
      pending.clear();
    },
  };
})();
