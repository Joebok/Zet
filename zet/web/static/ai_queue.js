/* Live activity is read from the durable job feed, never inferred from an empty table. */
(() => {
  let timer = null, request = null, cursor = null, rows = [], generation = 0;
  let deletingJobId = "", actionError = "", renderPending = false;
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
  function ageLabel(seconds) {
    if (seconds == null || seconds === "" || !Number.isFinite(Number(seconds))) return "Age unavailable";
    const age = Math.max(0, Number(seconds));
    if (age < 60) return "Just now";
    if (age < 3600) return `${Math.floor(age / 60)} min ago`;
    if (age < 86400) return `${Math.floor(age / 3600)} hr ago`;
    return `${Math.floor(age / 86400)} days ago`;
  }
  function statusLabel(status) {
    return ({
      QUEUED: "Queued", HELD: "Held", RUNNING: "Running", AWAITING_HARVEST: "Awaiting collection",
      HARVESTING: "Collecting", TRANSFERRING: "Transferring", RECONCILING: "Checking recovery",
      RECOVERING: "Recovering", PAUSED_STORAGE: "Paused: storage unavailable", HARVEST_FAILED: "Collection failed",
      RECOVERY_REQUIRED: "Recovery required", FAILED: "Failed", COMPLETE: "Complete", SUPERSEDED: "Superseded", MANUAL: "Manual task",
    })[status] || String(status || "Unknown").replaceAll("_", " ").toLowerCase();
  }
  function jobDetails(item) {
    const box = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = [item.failure_stage && `Failure at ${item.failure_stage}`, item.exception_type, item.recovery_action]
      .filter(Boolean).join(" · ") || "Request and status details";
    box.append(summary);
    const list = document.createElement("dl");
    for (const [label, value] of [
      ["Message", item.details], ["Failure stage", item.failure_stage], ["Exception", item.exception_type],
      ["Affected path", item.affected_path], ["Failed at", item.failed_at && createdAt(item.failed_at)],
      ["Recovery stage", item.recovery_stage], ["Current attempt", item.current_attempt_id],
      ["Last recovered", item.last_recovered_at && createdAt(item.last_recovered_at)],
      ["Recovery guidance", item.recovery_action],
    ]) {
      if (!value) continue;
      const term = document.createElement("dt"), description = document.createElement("dd");
      term.textContent = label; description.textContent = window.ZetPipelineMessage(value);
      list.append(term, description);
    }
    if (list.childElementCount) box.append(list);
    return box;
  }
  async function copyId(item) {
    const status = document.querySelector("#ai-job-copy-status");
    try { await window.writeClipboardText(item.ask_id); status.textContent = "Job ID copied to clipboard."; }
    catch { status.textContent = "Could not copy job ID. Check clipboard permissions."; }
  }
  function render(preserveFocus = false) {
    const body = document.querySelector("#ai-jobs-table tbody");
    if (preserveFocus && body.contains(document.activeElement)) { renderPending = true; return; }
    renderPending = false;
    body.replaceChildren();
    for (const item of rows) {
      const row = document.createElement("tr");
      row.dataset.jobId = item.ask_id;
      const universe = document.createElement("td"); universe.textContent = item.universe_id || "";
      const statusCell = document.createElement("td");
      const statusText = document.createElement("span");
      statusText.className = `ai-job-state ${["FAILED", "HARVEST_FAILED", "RECOVERY_REQUIRED"].includes(item.status) ? "historic-failure" : ["COMPLETE", "SUPERSEDED"].includes(item.status) ? "historic-complete" : "current"}`;
      statusText.textContent = statusLabel(item.status);
      statusCell.append(statusText);
      const targetCell = document.createElement("td");
      const target = document.createElement("span"); target.textContent = workflowTarget(item);
      if (item.workflow_url) {
        const link = document.createElement("a"); link.href = item.workflow_url; link.setAttribute("aria-label", `Open owning workflow for ${workflowTarget(item)}`);
        link.append(target); targetCell.append(link);
      } else targetCell.append(target);
      const mode = document.createElement("td"); mode.textContent = ({ draft: "Draft", final: "Final" })[item.render_mode] || "\u2014";
      const model = document.createElement("td"); model.textContent = `${item.provider || ""} · ${item.model || ""}`;
      const created = document.createElement("td");
      const time = document.createElement("time");
      if (item.created_at) time.dateTime = item.created_at;
      time.title = createdAt(item.created_at); time.textContent = ageLabel(item.age_seconds); created.append(time);
      const detailCell = document.createElement("td"); detailCell.append(jobDetails(item));
      row.append(universe, statusCell, targetCell, mode, model, created, detailCell);
      const idCell = document.createElement("td");
      const idLink = document.createElement("a"); idLink.href = "#"; idLink.textContent = "ID";
      idLink.setAttribute("aria-label", `Copy job ID ${item.ask_id}`);
      idLink.addEventListener("click", event => { event.preventDefault(); void copyId(item); });
      idCell.append(idLink); row.append(idCell);
      if (["HARVEST_FAILED", "RECOVERY_REQUIRED"].includes(item.status)) {
        const status = document.createElement("div"); status.className = "ai-job-status";
        const label = document.createElement("span"); label.textContent = deleteErrors.get(item.ask_id) || (deletingJobId === item.ask_id ? "Deleting this retained job…" : item.recovery_action || "Review this retained failure.");
        const button = document.createElement("button");
        button.type = "button"; button.textContent = "Delete job"; button.disabled = Boolean(deletingJobId);
        button.addEventListener("click", () => void deleteJob(item));
        status.append(label, button);
        statusCell.append(status);
      }
      body.append(row);
    }
    document.querySelector("#ai-jobs-more").hidden = !cursor;
  }
  const deleteErrors = new Map();
  async function deleteJob(item) {
    if (deletingJobId || !window.confirm(`Permanently delete AI job ${item.ask_id}?\n\nThis removes its queue files, prompts, answers and local recovery records. Library images and workflow records are preserved. The answer cannot be recovered.`)) return;
    deletingJobId = item.ask_id; deleteErrors.delete(item.ask_id); actionError = "";
    generation++; request?.abort(); request = null;
    render();
    document.querySelector("#ai-jobs-status").textContent = `Deleting retained job ${item.ask_id}…`;
    try {
      const response = await fetch(`/api/ai/jobs/${encodeURIComponent(item.ask_id)}`, { method: "DELETE" });
      if (!response.ok) throw new Error((await response.json()).detail || `Delete failed (${response.status})`);
      cursor = null;
      rows = rows.filter(row => row.ask_id !== item.ask_id);
    } catch (error) {
      actionError = `Delete failed: ${error.message}`;
      deleteErrors.set(item.ask_id, actionError);
    } finally {
      deletingJobId = "";
      render();
      await load();
    }
  }
  async function load(more = false, quiet = false) {
    if (!active() || request || deletingJobId) return;
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
        const choices = (payload.facets?.[name] || []).map(value => [String(value), name === "workflows" ? window.ZetPipelineLabel(value) : String(value)]);
        const current = [...select.options].slice(1).map(option => [option.value, option.textContent]);
        if (JSON.stringify(choices) !== JSON.stringify(current)) {
          select.replaceChildren(new Option(name === "universes" ? "All universes" : "All workflows", ""),
            ...choices.map(([value, label]) => new Option(label, value)));
          select.value = previous;
        }
      }
      render(quiet);
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
  function start() { stop(); void load(); timer = setInterval(() => { if (!document.hidden) void load(false, true); }, 2000); }
  document.addEventListener("visibilitychange", () => { if (!document.hidden && active()) void load(false, true); });
  for (const id of Object.values(filters)) document.getElementById(id)?.addEventListener("change", () => { generation++; request?.abort(); request = null; cursor = null; void load(); });
  document.querySelector("#ai-jobs-more")?.addEventListener("click", () => void load(true));
  document.querySelector("#refresh-ai-controls")?.addEventListener("click", () => void load());
  document.querySelector("#ai-jobs-table tbody")?.addEventListener("focusout", () => setTimeout(() => {
    if (renderPending && !document.querySelector("#ai-jobs-table tbody")?.contains(document.activeElement)) render();
  }, 0));
  window.ZetAIQueue = { start, stop, refresh: load };
})();
