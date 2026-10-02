(() => {
  const page = document.querySelector("#local-batch-status-page");
  const groupsHost = document.querySelector("#local-batch-status-groups");
  const message = document.querySelector("#local-batch-status-message");
  const refreshButton = document.querySelector("#local-batch-status-refresh");
  let timer = null;
  let inFlight = false;

  const pipelinePages = {
    "body-reference": "local-body-reference",
    "head-image": "local-head-image",
    "character-assembly": "local-character-assembly",
    "costume-dressing": "local-costume-dressing",
  };

  function directBatchUrl(batch) {
    if (batch.href) return batch.href;
    const params = new URLSearchParams({
      page: pipelinePages[batch.pipeline] || "local-batch-status",
      character: batch.character,
      phase: batch.phase,
      local_batch: batch.run_id,
    });
    if (batch.pipeline === "costume-dressing" && batch.costume) params.set("local_costume", batch.costume);
    return `${window.location.pathname}?${params.toString()}`;
  }

  function appendField(host, label, value) {
    if (!value) return;
    const field = document.createElement("span");
    field.className = "batch-status-field";
    field.dataset.label = label;
    field.textContent = value;
    host.append(field);
  }

  function renderBatch(batch) {
    const card = document.createElement("article");
    card.className = "batch-status-card";

    const title = document.createElement("h3");
    const link = document.createElement("a");
    link.href = directBatchUrl(batch);
    link.textContent = [batch.story_slug || batch.character, batch.scene_slug || batch.phase, batch.batch_name || batch.run_id.slice(0, 8)]
      .filter(Boolean)
      .join("/");
    title.append(link);

    const fields = document.createElement("div");
    fields.className = "batch-status-fields";
    appendField(fields, "Pipeline", batch.pipeline_label);
    appendField(fields, "Costume", batch.costume);
    appendField(fields, "Current view", batch.current_view);
    card.append(title, fields);
    return card;
  }

  function render(payload) {
    groupsHost.replaceChildren();
    const groups = payload.groups || [];
    if (!groups.length) {
      message.textContent = "No active or actionable batches.";
      return;
    }
    message.textContent = `${payload.batch_count || 0} active or actionable batch${payload.batch_count === 1 ? "" : "es"}.`;
    for (const group of groups) {
      const section = document.createElement("section");
      section.className = "batch-status-group";
      const heading = document.createElement("h2");
      heading.textContent = `${group.label} (${(group.batches || []).length})`;
      const list = document.createElement("div");
      list.className = "batch-status-list";
      for (const batch of group.batches || []) list.append(renderBatch(batch));
      section.append(heading, list);
      groupsHost.append(section);
    }
  }

  async function refresh() {
    if (inFlight || !page.classList.contains("active") || document.hidden) return;
    inFlight = true;
    refreshButton.disabled = true;
    message.textContent = "Loading batch status…";
    try {
      const response = await fetch("/api/local/batch-status", { headers: { Accept: "application/json" } });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || response.statusText || "Request failed");
      if (page.classList.contains("active")) render(payload);
    } catch (error) {
      groupsHost.replaceChildren();
      message.textContent = `Could not load batch status: ${error.message}`;
    } finally {
      inFlight = false;
      refreshButton.disabled = false;
    }
  }

  function stopPolling() {
    if (timer) window.clearInterval(timer);
    timer = null;
  }

  function startPolling() {
    stopPolling();
    if (!page.classList.contains("active") || document.hidden) return;
    void refresh();
    timer = window.setInterval(() => void refresh(), 3000);
  }

  refreshButton.addEventListener("click", () => void refresh());
  document.addEventListener("visibilitychange", startPolling);

  window.ZetLocalBatchStatus = {
    activate: startPolling,
    deactivate: stopPolling,
  };
})();
