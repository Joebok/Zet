/* Live activity is read from the durable job feed, never inferred from an empty table. */
(() => {
  let timer = null, request = null, cursor = null, rows = [], generation = 0;
  const filters = { universe_filter: "ai-filter-universe", provider: "ai-filter-provider", workflow: "ai-filter-workflow", status: "ai-filter-status" };
  const active = () => document.querySelector("#ai-controls-page")?.classList.contains("active");
  function render() {
    const body = document.querySelector("#ai-jobs-table tbody");
    body.replaceChildren();
    for (const item of rows) {
      const row = document.createElement("tr");
      row.dataset.jobId = item.ask_id;
      for (const value of [item.universe_id, [item.workflow, item.target].filter(Boolean).join(" / "), item.task_type || item.ask_id,
        `${item.provider || ""} · ${item.model || ""}`, item.status, item.created_at, item.details]) {
        const cell = document.createElement("td"); cell.textContent = value || ""; row.append(cell);
      }
      if (item.workflow_url) {
        const link = document.createElement("a"); link.href = item.workflow_url; link.textContent = row.children[1].textContent;
        row.children[1].replaceChildren(link);
      }
      body.append(row);
    }
    document.querySelector("#ai-jobs-more").hidden = !cursor;
  }
  async function load(more = false) {
    if (!active() || request) return;
    const version = generation;
    const controller = new AbortController(); request = controller;
    const status = document.querySelector("#ai-jobs-status");
    if (!rows.length) status.textContent = "Loading AI activity…";
    const params = new URLSearchParams();
    for (const [key, id] of Object.entries(filters)) { const value = document.getElementById(id)?.value; if (value) params.set(key, value); }
    if (more && cursor) params.set("cursor", cursor);
    try {
      const response = await fetch(`/api/ai/jobs?${params}`, { signal: controller.signal });
      if (!response.ok) throw new Error((await response.json()).detail || `Queue unavailable (${response.status})`);
      const payload = await response.json();
      if (version !== generation || !active()) return;
      rows = more ? [...rows, ...payload.items.filter(item => !rows.some(old => old.ask_id === item.ask_id))] : payload.items;
      cursor = payload.next_cursor;
      for (const [name, id] of [["universes", "ai-filter-universe"], ["workflows", "ai-filter-workflow"]]) {
        const select = document.getElementById(id), previous = select.value;
        select.replaceChildren(new Option(name === "universes" ? "All universes" : "All workflows", ""),
          ...(payload.facets?.[name] || []).map(value => new Option(value, value)));
        select.value = previous;
      }
      render();
      document.querySelector("#queue-counts").textContent = Object.entries(payload.counts || {}).map(([name, count]) => `${name}: ${count}`).join(" | ") || "No recorded AI activity";
      const recent = document.querySelector("#recent-harvest-table tbody");
      recent.replaceChildren();
      for (const item of payload.recent_harvests || []) {
        const row = document.createElement("tr");
        for (const value of [item.harvested_at, item.ask_id, item.task_type, item.asset_id, item.status, item.details]) {
          const cell = document.createElement("td"); cell.textContent = value ?? ""; row.append(cell);
        }
        recent.append(row);
      }
      document.querySelector("#recent-harvest-count").textContent = `${(payload.recent_harvests || []).length} recent harvested job(s)`;
      status.textContent = rows.length ? `${payload.total} job(s) · Updated ${new Date().toLocaleTimeString()}` : "No AI jobs match these filters.";
    } catch (error) {
      if (error.name !== "AbortError") status.textContent = `${rows.length ? "Showing previous activity. " : ""}Queue unavailable: ${error.message}`;
    } finally { if (request === controller) request = null; }
  }
  function stop() { generation++; clearInterval(timer); timer = null; request?.abort(); request = null; }
  function start() { stop(); void load(); timer = setInterval(() => { if (!document.hidden) void load(); }, 2000); }
  document.addEventListener("visibilitychange", () => { if (!document.hidden && active()) void load(); });
  for (const id of Object.values(filters)) document.getElementById(id)?.addEventListener("change", () => { generation++; request?.abort(); request = null; cursor = null; void load(); });
  document.querySelector("#ai-jobs-more")?.addEventListener("click", () => void load(true));
  document.querySelector("#refresh-ai-controls")?.addEventListener("click", () => void load());
  window.ZetAIQueue = { start, stop, refresh: load };
})();
