/* Explicit page providers share only navigation and universe handling. */
(() => {
  const route = new URLSearchParams(location.search);
  const recorded = route.get("task_context") === "1";
  let universe = null;
  const ready = (async () => {
    try {
      const response = await fetch("/api/universes");
      if (!response.ok) throw new Error("Universe lookup failed.");
      const value = await response.json();
      const requested = recorded ? route.get("task_universe") : null;
      universe = value.universes?.some((item) => item.universe_id === requested) ? requested : value.selected_universe_id;
      if (requested && requested !== universe) window.ZetTaskCapture.notice(`Recorded universe "${requested}" is unavailable. Showing the current universe.`);
    } catch {
      window.ZetTaskCapture.notice("Universe context is unavailable. Reload to retry before creating a task.");
    }
  })();
  window.ZetAuxiliaryTasks = {
    ready,
    route,
    recorded,
    selection(id, label = id, available = true, loading = false, failed = false) {
      if (!id) return { state: loading ? "loading" : failed ? "unavailable" : "absent" };
      return { state: loading ? "loading" : available ? "selected" : "unavailable", id, label: label || id };
    },
    async fetch(url, options = {}) {
      await ready;
      const headers = new Headers(options.headers);
      if (universe) headers.set("X-Zet-Universe", universe);
      return fetch(url, { ...options, headers });
    },
    image(url) {
      const source = new URL(url, location.origin);
      if (universe) source.searchParams.set("universe_id", universe);
      return source.pathname + source.search;
    },
    restoreSelect(node, parameter) {
      const id = recorded ? route.get(parameter) : null;
      if (!id) return;
      if ([...node.options].some((option) => option.value === id)) node.value = id;
      else window.ZetTaskCapture.notice(`Recorded ${parameter.replaceAll("_", " ")} "${id}" is unavailable. The page is open.`);
    },
    install(pageId, pageName, read) {
      window.ZetTaskCapture.registerProvider(() => {
        const { selections, parameters = {} } = read();
        const source = new URL(location.pathname, location.origin);
        source.searchParams.set("task_context", "1");
        if (universe) source.searchParams.set("task_universe", universe);
        for (const [key, value] of Object.entries(parameters)) if (value) source.searchParams.set(key, value);
        return { page_id: pageId, page_name: pageName, source_url: source.href, universe_id: universe, selections };
      });
    },
  };
})();
