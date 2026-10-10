(() => {
  const page = document.querySelector("#local-batch-status-page");
  const groupsHost = document.querySelector("#local-batch-status-groups");
  const message = document.querySelector("#local-batch-status-message");
  const refreshButton = document.querySelector("#local-batch-status-refresh");
  let timer = null;
  let inFlight = false;
  let batches = [];
  let loadState = "loading";
  let selectedRun = new URLSearchParams(window.location.search).get("task_batch") || "";

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
    const universe = document.querySelector("#universe-select").value;
    if (universe) params.set("task_universe", universe);
    return `${window.location.pathname}?${params.toString()}`;
  }

  function appendField(host, label, value, className = "") {
    if (!value) return;
    const field = document.createElement("span");
    field.className = `batch-status-field ${className}`.trim();
    field.dataset.label = label;
    field.textContent = value;
    host.append(field);
  }

  function renderBatch(batch) {
    const card = document.createElement("article");
    card.className = `batch-status-card${batch.pipeline === "scene" ? " batch-status-scene" : ""}`;
    card.dataset.runId = batch.run_id;
    if (batch.run_id === selectedRun) card.setAttribute("aria-current", "true");

    const title = document.createElement("h3");
    const link = document.createElement("a");
    link.href = directBatchUrl(batch);
    link.textContent = [batch.story_slug || batch.character, batch.scene_slug || batch.phase, batch.batch_name || batch.run_id.slice(0, 8)]
      .filter(Boolean)
      .join("/");
    title.append(link);

    const fields = document.createElement("div");
    fields.className = "batch-status-fields";
    const pipelineClasses = [
      "batch-status-pipeline",
      `pipeline-${batch.pipeline}`,
    ];
    if (batch.status !== "RUNNING") pipelineClasses.push("is-muted");
    appendField(fields, "Pipeline", batch.pipeline_label, pipelineClasses.join(" "));
    appendField(fields, "Costume", batch.costume);
    appendField(fields, "Current view", batch.current_view);
    card.append(title, fields);
    if (pipelinePages[batch.pipeline]) {
      const report = document.createElement("button");
      report.type = "button";
      report.textContent = "Create task";
      report.addEventListener("click", () => {
        selectedRun = batch.run_id;
        for (const item of groupsHost.querySelectorAll("[data-run-id]")) {
          if (item.dataset.runId === selectedRun) item.setAttribute("aria-current", "true");
          else item.removeAttribute("aria-current");
        }
        void window.ZetTaskCapture.open();
      });
      card.append(report);
    }
    if (batch.pipeline === "scene" && batch.status === "READY_TO_PUBLISH") {
      const review = document.createElement("a");
      const url = new URL(directBatchUrl(batch), window.location.href);
      url.searchParams.set("publication_review", "1");
      review.href = url.toString();
      review.className = "batch-status-review-link";
      review.textContent = "Review & Publish";
      card.append(review);
    }
    return card;
  }

  function render(payload) {
    groupsHost.replaceChildren();
    const groups = payload.groups || [];
    batches = groups.flatMap((group) => group.batches || []);
    if (selectedRun && !batches.some((batch) => batch.run_id === selectedRun)) {
      window.ZetTaskCapture.notice(`Recorded batch "${selectedRun}" is unavailable on the Batches page.`);
    }
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
    loadState = "loading";
    refreshButton.disabled = true;
    message.textContent = "Loading batch status…";
    try {
      const response = await fetch("/api/local/batch-status", { headers: { Accept: "application/json",
        "X-Zet-Universe": document.querySelector("#universe-select").value } });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || response.statusText || "Request failed");
      if (page.classList.contains("active")) { loadState = "selected"; render(payload); }
    } catch (error) {
      groupsHost.replaceChildren();
      loadState = "unavailable";
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
    taskContext() {
      if (!selectedRun) return { selections: {}, parameters: {} };
      const batch = batches.find((item) => item.run_id === selectedRun);
      const selection = { state: loadState === "selected" ? batch ? "selected" : "unavailable" : loadState,
        id: selectedRun, label: batch?.batch_name || selectedRun };
      const selections = { batch: { ...selection }, run: { ...selection } };
      const parameters = { task_batch: selectedRun };
      if (batch && pipelinePages[batch.pipeline]) {
        selections.pipeline = { state: selection.state, id: batch.pipeline, label: batch.pipeline_label || batch.pipeline };
        for (const name of ["character", "phase", "costume"]) {
          if (batch[name]) selections[name] = { state: selection.state, id: batch[name], label: batch[name] };
        }
      }
      return { selections, parameters };
    },
  };
})();
