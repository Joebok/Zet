(() => {
  const button = document.getElementById("local-operations-button");
  const panel = document.getElementById("local-operations-panel");
  const message = document.getElementById("local-operations-message");
  const list = document.getElementById("local-operations-list");
  const active = new Set(["SUBMITTING", "QUEUED", "PREPARING", "WAITING"]);
  const errors = new Set(["FAILED", "RECOVERY_REQUIRED", "UNKNOWN", "BLOCKED", "PARTIAL"]);
  const pages = {"body-reference": "local-body-reference", "head-image": "local-head-image",
    "head-image-edit": "local-head-image-edit", "character-assembly": "local-character-assembly",
    "costume-dressing": "local-costume-dressing"};
  const storageKey = "zet.pending-character-operations.v1";
  let rows = [], refreshing = false;
  const submitting = new Set();

  function pending() {
    try { const value = JSON.parse(localStorage.getItem(storageKey) || "[]"); return Array.isArray(value) ? value : []; }
    catch (_) { return []; }
  }
  function savePending(items) { try { localStorage.setItem(storageKey, JSON.stringify(items)); return true; } catch (_) { return false; } }
  function forget(id) { savePending(pending().filter(item => item.operation_id !== id)); }
  function normalizedId(value) { return String(value || "").replaceAll("-", "").toLowerCase(); }
  function newOperationId() {
    if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
    return Array.from(bytes, value => value.toString(16).padStart(2, "0")).join("");
  }
  function allRows() {
    const known = new Set(rows.flatMap(row => [row.id, ...(row.aliases || [])]).map(normalizedId));
    const visible = rows.filter(row => active.has(row.status) || errors.has(row.status));
    return [...visible, ...pending().filter(item => !known.has(normalizedId(item.operation_id))).map(item => {
      const activeSubmission = submitting.has(normalizedId(item.operation_id));
      return {id: item.operation_id, request: item, status: activeSubmission ? "SUBMITTING" : "UNKNOWN",
        stage: activeSubmission ? "Submitting…" : "Submission not confirmed — check status before retrying"};
    })];
  }
  function batchLink(request) {
    const params = new URLSearchParams({page: pages[request.pipeline] || "local-batch-status",
      character: request.character || "", phase: request.phase || "", local_batch: request.run_id,
      render_mode: request.render_mode || "draft", task_universe: request.universe_id});
    if (request.costume) params.set("local_costume", request.costume);
    if (request.view) params.set("local_view", request.view);
    return `${location.pathname}?${params}`;
  }
  function render() {
    const visibleRows = allRows();
    const activeCount = visibleRows.filter(row => active.has(row.status)).length;
    const errorCount = visibleRows.filter(row => errors.has(row.status)).length;
    button.textContent = `Activity${activeCount || errorCount ? ` (${activeCount} running${errorCount ? ` · ${errorCount} attention` : ""})` : ""}`;
    message.textContent = visibleRows.length ? "Character preparation and actions needing attention" : "No active character preparation or actions needing attention.";
    list.replaceChildren();
    for (const row of visibleRows) {
      const item = document.createElement("div"); item.className = "local-operation-item";
      const title = document.createElement("strong");
      const request = row.request || {};
      title.textContent = [request.universe_id, request.character, request.phase, request.batch_name || request.run_id,
        request.pipeline, request.render_mode, String(request.action || "").replaceAll("_", " "), request.view].filter(Boolean).join(" · ");
      const status = document.createElement("div"); status.textContent = row.stage || row.status;
      const error = row.error || row.result?.error;
      if (error) status.textContent += `: ${error}`;
      const blocked = {...(row.result?.blocked_views || {}), ...(row.result?.errors || {})};
      if (Object.keys(blocked).length) status.textContent += ` — ${Object.entries(blocked).map(([view, reason]) => `${view}: ${reason}`).join(" · ")}`;
      const link = document.createElement("a"); link.href = batchLink(request); link.textContent = "Open batch";
      item.append(title, status, link); list.append(item);
      if (errors.has(row.status) && row.status !== "UNKNOWN") {
        const dismiss = document.createElement("button"); dismiss.type = "button"; dismiss.textContent = "Dismiss";
        dismiss.addEventListener("click", () => void dismissError(row.id, dismiss));
        item.append(dismiss);
      }
    }
    window.dispatchEvent(new CustomEvent("zet-local-operations", {detail: visibleRows}));
  }
  async function refresh() {
    if (refreshing || document.hidden) return;
    refreshing = true;
    try {
      const response = await fetch("/api/local/operations?limit=100");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      rows = (await response.json()).operations || []; render();
    } catch (_) { message.textContent = "Could not refresh activity. Previously shown actions may be out of date."; }
    finally { refreshing = false; }
  }
  async function post(payload) {
    const response = await fetch("/api/local/operations", {method: "POST", headers: {"Content-Type": "application/json", "X-Zet-Universe": payload.universe_id}, body: JSON.stringify(payload)});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status >= 400 && response.status < 500 && response.status !== 408 && response.status !== 429) forget(payload.operation_id);
      const detail = data.detail;
      throw new Error(typeof detail === "string" ? detail : detail?.message || `HTTP ${response.status}`);
    }
    forget(payload.operation_id);
    rows = [data, ...rows.filter(row => row.id !== data.id)]; render();
    return data;
  }
  async function submit(payload) {
    const previous = pending().find(item => item.universe_id === payload.universe_id && item.pipeline === payload.pipeline
      && item.run_id === payload.run_id && item.action === payload.action);
    let value;
    if (previous) {
      const {operation_id, ...prior} = previous;
      if (JSON.stringify(prior) !== JSON.stringify(payload)) throw new Error("A previous submission has an unknown outcome. Check Activity before changing its inputs.");
      value = previous;
    } else {
      value = {...payload, operation_id: newOperationId()};
      if (!savePending([...pending(), value])) throw new Error("Could not retain the submission ID in this browser.");
    }
    submitting.add(normalizedId(value.operation_id));
    render();
    try { return await post(value); }
    finally { submitting.delete(normalizedId(value.operation_id)); render(); }
  }
  async function recoverPending() {
    for (const payload of pending()) {
      try {
        const response = await fetch(`/api/local/operations/${encodeURIComponent(payload.operation_id)}`);
        if (response.ok) { forget(payload.operation_id); continue; }
        if (response.status === 404) await post(payload);
      } catch (_) { /* Keep the same ID for a later status check. */ }
    }
    await refresh();
  }
  async function dismissError(id, control) {
    control.disabled = true;
    try {
      const response = await fetch(`/api/local/operations/${encodeURIComponent(id)}/dismiss`, {method: "POST"});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      rows = rows.filter(row => normalizedId(row.id) !== normalizedId(id));
      render();
    } catch (error) {
      control.disabled = false;
      message.textContent = `Could not dismiss error: ${error.message}`;
    }
  }
  function closePanel() {
    panel.hidden = true;
    button.setAttribute("aria-expanded", "false");
  }
  function onNavigation() {
    closePanel();
    void recoverPending();
  }
  button.addEventListener("click", () => {
    panel.hidden = !panel.hidden; button.setAttribute("aria-expanded", String(!panel.hidden));
    if (!panel.hidden) { positionPanel(); void refresh(); }
  });
  function positionPanel() {
    if (panel.hidden) return;
    const rect = button.getBoundingClientRect();
    panel.style.top = `${Math.min(rect.bottom + 4, Math.max(8, innerHeight - 100))}px`;
    panel.style.right = `${Math.max(8, innerWidth - rect.right)}px`;
  }
  window.addEventListener("resize", positionPanel);
  document.getElementById("local-operations-refresh").addEventListener("click", () => void recoverPending());
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !panel.hidden) { panel.hidden = true; button.setAttribute("aria-expanded", "false"); button.focus(); }
  });
  document.addEventListener("visibilitychange", () => { if (!document.hidden) void recoverPending(); });
  window.ZetLocalOperations = {submit, refresh, rows: allRows, onNavigation};
  void recoverPending();
})();
