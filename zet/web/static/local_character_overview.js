(() => {
  let context = null;
  let generation = 0;
  let loading = false;
  const host = () => document.querySelector("#local-overview-groups");
  const status = () => document.querySelector("#local-overview-status");

  function make(tag, className, text) {
    const node = document.createElement(tag);
    node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function render(data) {
    const rows = (data.rows || []).map((row) => {
      const section = make("section", "overview-group");
      section.append(make("h2", "", `${row.character} · ${row.phase}`));
      const grid = make("div", "overview-slots");
      for (const slot of row.costumes || []) {
        const card = make("article", "overview-slot");
        card.append(make("h3", "", slot.name));
        if (slot.image_url) {
          const image = make("img", "overview-image");
          const url = new URL(slot.image_url, location.origin);
          url.searchParams.set("universe_id", context.universeId);
          image.src = url.href;
          image.alt = `Locked FRONT · ${row.character} · ${row.phase} · ${slot.name}`;
          image.loading = "lazy";
          card.append(image);
        } else card.append(make("div", "overview-placeholder", "No locked FRONT image"));
        const summary = slot.image_url
          ? `${slot.render_mode === "final" ? "Final" : "Draft"} · Locked`
          : slot.message;
        card.append(make("p", "overview-state", summary));
        grid.append(card);
      }
      if (!grid.children.length) grid.append(make("p", "muted", "No costumes for this phase."));
      section.append(grid);
      return section;
    });
    host().replaceChildren(...(rows.length ? rows : [make("p", "muted", "No characters or phases were found.")]));
  }

  async function refresh() {
    if (!context || loading || document.hidden) return;
    const current = generation;
    loading = true;
    status().textContent = "Loading current published images…";
    status().classList.remove("error");
    try {
      const data = await context.fetchJson("/api/local/character-overview", {
        headers: {"X-Zet-Universe": context.universeId},
      });
      if (current !== generation) return;
      render(data);
      status().textContent = "Read-only view. Generate and review candidates from Assets → Costume Dressing.";
    } catch (error) {
      if (current !== generation) return;
      status().textContent = error.message;
      status().classList.add("error");
    } finally {
      if (current === generation) loading = false;
    }
  }

  document.querySelector("#local-overview-refresh").addEventListener("click", () => void refresh());
  document.addEventListener("visibilitychange", () => { if (!document.hidden && context) void refresh(); });
  window.ZetLocalCharacterOverview = {
    activate(options) {
      this.deactivate();
      context = options;
      host().replaceChildren();
      void refresh();
    },
    deactivate() {
      generation += 1;
      context = null;
      loading = false;
    },
  };
})();
