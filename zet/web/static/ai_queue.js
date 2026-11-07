/* Live activity is read from the durable job feed, never inferred from an empty table. */
(() => {
  let timer = null, request = null, cursor = null, rows = [], generation = 0;
  let deleting = false, actionError = "";
  const filters = { universe_filter: "ai-filter-universe", provider: "ai-filter-provider", workflow: "ai-filter-workflow", status: "ai-filter-status" };
  const active = () => document.querySelector("#ai-controls-page")?.classList.contains("active");
  function workflowTarget(item) {
    const owner = item.owner || {}, titles = item.queue_titles || {};
    if (item.workflow === "Narrative" || owner.narrative_story_id) {
      const parts = [titles.story, titles.scene, titles.target].filter(Boolean);
      return parts.length ? ["Narrative", ...parts].join(" / ") : "Narrative / Target via status link";
    }
    const pipeline = owner.pipeline || item.workflow;
    const labels = { "costume-dressing": "Costume Dressing", "character-assembly": "Character Assembly", "body-reference": "Body Reference", "head-image": "Head Image", "head-image-edit": "Head Image Edit" };
    const costume = String(owner.costume || "").replace(/[_-]+/g, " ");
    return [labels[pipeline] || window.ZetPipelineLabel(pipeline), owner.character, owner.phase, costume, owner.view].filter(Boolean).join(" / ") || item.target || "";
  }
  function createdAt(value) {
    const date = value ? new Date(value) : null;
    return date && Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(date) : "\u2014";
  }
  async function copyId(item) {
    const status = document.querySelector("#ai-job-copy-status");
    try { await window.writeClipboardText(item.ask_id); status.textContent = "Job ID copied to clipboard."; }
    catch { status.textContent = "Could not copy job ID. Check clipboard permissions."; }
  }
  function render() {
    const body = document.querySelector("#ai-jobs-table tbody");
    body.replaceChildren();
    for (const item of rows) {
      const row = document.createElement("tr");
      row.dataset.jobId = item.ask_id;
      for (const value of [item.universe_id, ({ PAUSED_STORAGE: "Paused — storage unavailable", RECOVERING: "Recovering" })[item.status] || item.status, workflowTarget(item),
        ({ draft: "Draft", final: "Final" })[item.render_mode] || "\u2014", `${item.provider || ""} · ${item.model || ""}`, createdAt(item.created_at),
        [item.failure_stage && `Stage: ${item.failure_stage}`, window.ZetPipelineMessage(item.details),
          item.age_seconds != null && `Age: ${Math.floor(item.age_seconds / 60)} min`, item.recovery_action].filter(Boolean).join(" Â· ")]) {
        const cell = document.createElement("td"); cell.textContent = value || ""; row.append(cell);
      }
      const idCell = document.createElement("td");
      const idLink = document.createElement("a"); idLink.href = "#"; idLink.textContent = "ID";
      idLink.setAttribute("aria-label", `Copy job ID ${item.ask_id}`);
      idLink.addEventListener("click", event => { event.preventDefault(); void copyId(item); });
      idCell.append(idLink); row.append(idCell);
      if (item.workflow_url) {
        const link = document.createElement("a"); link.href = item.workflow_url; link.textContent = row.children[1].textContent;
        row.children[1].replaceChildren(link);
      }
      if (["HARVEST_FAILED", "RECOVERY_REQUIRED"].includes(item.status)) {
        const status = document.createElement("div"); status.className = "ai-job-status";
        const label = document.createElement("span"); label.append(...row.children[1].childNodes);
        const button = document.createElement("button");
        button.type = "button"; button.textContent = "Delete job"; button.disabled = deleting;
        button.addEventListener("click", () => void deleteJob(item));
        status.append(label, button);
        row.children[1].replaceChildren(status);
      }
      body.append(row);
    }
    document.querySelector("#ai-jobs-more").hidden = !cursor;
  }
  async function deleteJob(item) {
    if (deleting || !window.confirm(`Permanently delete AI job ${item.ask_id}?\n\nThis removes its queue files, prompts, answers and local recovery records. Library images and workflow records are preserved. The answer cannot be recovered.`)) return;
    deleting = true; actionError = "";
    generation++; request?.abort(); request = null;
    render();
    document.querySelector("#ai-jobs-status").textContent = `Deleting ${item.ask_id}â€¦`;
    try {
      const response = await fetch(`/api/ai/jobs/${encodeURIComponent(item.ask_id)}`, { method: "DELETE" });
      if (!response.ok) throw new Error((await response.json()).detail || `Delete failed (${response.status})`);
      cursor = null;
    } catch (error) {
      actionError = `Delete failed: ${error.message}`;
    } finally {
      deleting = false;
      render();
      await load();
    }
  }
  async function load(more = false) {
    if (!active() || request || deleting) return;
    const version = generation;
    const controller = new AbortController(); request = controller;
    const status = document.querySelector("#ai-jobs-status");
    if (!rows.length) status.textContent = "Loading AI activityâ€¦";
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
          ...(payload.facets?.[name] || []).map(value => new Option(name === "workflows" ? window.ZetPipelineLabel(value) : value, value)));
        select.value = previous;
      }
      render();
      document.querySelector("#queue-counts").textContent = (payload.stale ? "Storage unavailable; counts unknown. Work will resume automatically." : Object.entries(payload.counts || {}).map(([name, count]) => `${name}: ${count}`).join(" | ") || "No recorded AI activity");
      const recent = document.querySelector("#recent-harvest-table tbody");
      recent.replaceChildren();
      for (const item of payload.recent_harvests || []) {
        const row = document.createElement("tr");
        for (const value of [item.harvested_at, item.ask_id, item.task_type, item.asset_id, item.status, window.ZetPipelineMessage(item.details)]) {
          const cell = document.createElement("td"); cell.textContent = value ?? ""; row.append(cell);
        }
        recent.append(row);
      }
      document.querySelector("#recent-harvest-count").textContent = `${(payload.recent_harvests || []).length} recent harvested job(s)`;
      const refreshed = payload.updated_at ? `Updated ${new Date(payload.updated_at).toLocaleTimeString()}` : "Loading activity snapshot…";
      status.textContent = actionError || payload.refresh_error || (payload.refreshing ? "Refreshing activity…" : rows.length ? `${payload.total} job(s) · ${refreshed}` : `No AI jobs match these filters. ${refreshed}`);
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
