(() => {
  const pagePipelines = {
    "local-body-reference": "body-reference",
    "local-head-image": "head-image",
    "local-character-assembly": "character-assembly",
    "local-costume-dressing": "costume-dressing",
  };
  const $ = (id) => document.getElementById(`local-pipeline-${id}`);
  const statusLabels = {
    QUEUED: "Queued", PREFLIGHT: "Checking inputs", RUNNING: "Running", STOPPING: "Stopping",
    REEVALUATING: "Re-evaluating", READY_FOR_VIEWS: "Ready for other views",
    AWAITING_FRONT_ANCHOR: "Awaiting FRONT selection", AWAITING_HUMAN_SELECTION: "Awaiting selection",
    REVIEW_REQUIRED: "Review required", COMPLETE: "Complete", CANCELLED: "Stopped",
    STOPPED: "Stopped", INTERRUPTED: "Interrupted", ERROR: "Error", PENDING: "Pending",
    WAITING_FOR_GATES: "Waiting for gates", GATE_REJECTED: "Gate rejected", FAILED: "Failed",
  };
  const activeStatuses = new Set(["PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING"]);
  const state = { pipeline: "", generation: 0, run: null, runs: [], reviewCandidates: [], reviewIndex: -1,
    gatePolicies: {}, frontSourcePath: "", poll: null, previewGeneration: 0, contextKey: "", compareOpposite: false,
    polledRun: null, pollInFlight: false, renderedSelections: {} };

  function contextKey() {
    return `${document.querySelector("#character-select").value}\u0000${document.querySelector("#phase-select").value}`;
  }

  function isCostume() { return state.pipeline === "costume-dressing"; }
  function hasSharedAssetRouter() { return ["character-assembly", "costume-dressing"].includes(state.pipeline); }
  function baseUrl() { return `/api/local/${state.pipeline}`; }
  function selectedCostume() { return $("costume")?.value || ""; }
  function gateRegistry() {
    if (state.pipeline === "character-assembly") return "local-character-assembly";
    if (state.pipeline === "costume-dressing") return "local-costume-dressing";
    return state.pipeline;
  }

  function query(extra = {}) {
    const params = new URLSearchParams({
      character: document.querySelector("#character-select").value,
      phase: document.querySelector("#phase-select").value,
      ...extra,
    });
    if (isCostume()) params.set("costume", selectedCostume());
    return `?${params.toString()}`;
  }

  async function request(path, options = {}) {
    const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || response.statusText || "Request failed");
    return data;
  }

  function setStatus(message, error = false) {
    $("status").textContent = message || "";
    $("status").classList.toggle("error", error);
    $("status").classList.toggle("success", !error && Boolean(message));
  }

  function busy(run = state.run) { return Boolean(run && activeStatuses.has(run.status)); }

  function unstartedViews(run) {
    return (run?.views || []).filter((view) => view !== "FRONT" && (() => {
      const candidates = (run.candidates || []).filter((candidate) => candidate.view === view);
      return candidates.length > 0 && candidates.every((candidate) => candidate.status === "PENDING" && !candidate.image_path);
    })());
  }

  function route(action, runId = state.run?.run_id || "", view = "", candidateId = "") {
    const id = encodeURIComponent(runId);
    const encodedView = encodeURIComponent(view);
    const candidate = encodeURIComponent(candidateId);
    switch (action) {
      case "preview": return `${baseUrl()}/preview`;
      case "runs": return `${baseUrl()}/runs${query()}`;
      case "create": return `${baseUrl()}/runs`;
      case "detail": return `${baseUrl()}/runs/${id}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "image": return `${baseUrl()}/runs/${id}/images/${candidate}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "rename": return `${baseUrl()}/runs/${id}/name${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "start": return `${baseUrl()}/runs/${id}/start${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "resume": return `${baseUrl()}/runs/${id}/resume${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "stop": return `${baseUrl()}/runs/${id}/stop${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "rerun": return `${baseUrl()}/runs/${id}/rerun${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "reevaluate": return `${baseUrl()}/runs/${id}/reevaluate${query()}`;
      case "delete": return `${baseUrl()}/runs/${id}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "rerun-view": return `${baseUrl()}/runs/${id}/views/${encodedView}/rerun${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "rerun-failed": return `${baseUrl()}/runs/${id}/rerun-failed${query({ view })}`;
      case "rank": return `${baseUrl()}/runs/${id}/views/${encodedView}/rank${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "move-rank": return `${baseUrl()}/runs/${id}/views/${encodedView}/ranking/move${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "select": return `${baseUrl()}/runs/${id}/views/${encodedView}/select${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "review": return `${baseUrl()}/runs/${id}/candidates/${candidate}/review${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "retry": return `${baseUrl()}/runs/${id}/candidates/${candidate}/retry${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "lock": return `${baseUrl()}/runs/${id}/views/${encodedView}/lock${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "unlock": return `${baseUrl()}/runs/${id}/views/${encodedView}/unlock${query()}`;
      case "proceed": return `${baseUrl()}/runs/${id}/views/FRONT/proceed${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "prompt": return `${baseUrl()}/runs/${id}/review-spec/${encodedView}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "image-prompt": return `${baseUrl()}/runs/${id}/image-prompt/${encodedView}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "gate-prompt": return `${baseUrl()}/runs/${id}/views/${encodedView}/gates/${encodeURIComponent(candidate)}/prompt${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      case "source": return `${baseUrl()}/runs/${id}/sources/${encodedView}/${encodeURIComponent(candidate)}${isCostume() ? `?costume=${encodeURIComponent(selectedCostume())}` : ""}`;
      default: throw new Error(`Unsupported Local workflow action: ${action}`);
    }
  }

  function payload() {
    return {
      character: document.querySelector("#character-select").value,
      phase: document.querySelector("#phase-select").value,
      costume: isCostume() ? selectedCostume() : "",
      front_count: Number($("front-count").value),
      other_count: Number($("other-count").value),
      use_front_anchor: hasSharedAssetRouter() ? $("use-anchor").checked : state.pipeline === "body-reference" || state.pipeline === "head-image",
      front_source_path: state.frontSourcePath,
    };
  }

  function setBusyControls() {
    const run = state.run;
    const isBusy = busy(run);
    $("start").hidden = !run;
    $("start").disabled = isBusy || !["QUEUED", "INTERRUPTED", "STOPPED"].includes(run?.status);
    $("start").textContent = ["INTERRUPTED", "STOPPED"].includes(run?.status) ? "Resume batch" : "Start batch";
    $("stop").hidden = !isBusy;
    $("stop").disabled = !isBusy;
    $("rerun").disabled = !run || isBusy;
    $("reevaluate").disabled = !run || isBusy || !(run.candidates || []).some((item) => item.image_path);
    $("delete").disabled = !run || isBusy;
    $("rename").hidden = !run;
    $("proceed").hidden = !run;
    $("proceed").disabled = isBusy || run?.status === "READY_FOR_VIEWS"
      || !run?.front_anchor || !unstartedViews(run).length;
    $("lineup").hidden = state.pipeline !== "body-reference" || !run || !Object.keys(run.selected_views || {}).length;
  }

  function gateLabel(record, policy) {
    if (record?.status === "DISABLED" || policy === "Disabled") return "Disabled";
    if (record?.status === "STALE") return "Stale";
    if (record?.verdict === "FALSE") return "Passed";
    if (record?.verdict === "TRUE" || (policy === "Warning" && record?.status === "FAILED")) return policy === "Warning" ? "Warning" : "Rejected";
    return statusLabels[record?.status] || record?.status || "Pending";
  }

  function addLink(parent, label, href) {
    const link = document.createElement("a");
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = label;
    parent.append(link);
  }

  function renderGateSettings(data) {
    state.gatePolicies = data.statuses || {};
    const host = $("gate-settings");
    host.replaceChildren();
    for (const [key] of Object.entries(data.gates || {})) {
      const label = document.createElement("label");
      label.className = "local-pipeline-gate-setting";
      const name = document.createElement("span");
      name.textContent = key.replaceAll("_", " ");
      const select = document.createElement("select");
      for (const value of ["Disabled", "Warning", "Active"]) select.add(new Option(value, value));
      select.value = state.gatePolicies[key] || "Disabled";
      select.addEventListener("change", async () => {
        try {
          const updated = await request(`/api/local-gates/${gateRegistry()}/${encodeURIComponent(key)}`, {
            method: "PUT", body: JSON.stringify({ status: select.value }),
          });
          state.gatePolicies = updated.statuses || state.gatePolicies;
          if (state.run) render();
        } catch (error) { setStatus(error.message, true); }
      });
      label.append(name, select);
      host.append(label);
    }
  }

  async function loadGateSettings(generation) {
    const data = await request(`/api/local-gates/${gateRegistry()}`);
    if (generation === state.generation) renderGateSettings(data);
  }

  function gateSummary(candidate) {
    const gates = { ...Object.fromEntries(Object.keys(state.gatePolicies).map((key) => [key, {}])), ...(candidate.gates || {}) };
    return Object.entries(gates).map(([key, record]) => {
      const policy = record.policy_status || state.gatePolicies[key];
      const labelText = gateLabel(record, policy);
      const line = document.createElement("p");
      line.className = "local-pipeline-gate-result";
      const label = document.createElement("strong");
      label.textContent = key.replaceAll("_", " ");
      const result = document.createElement("span");
      result.className = "local-pipeline-gate-icon";
      if (labelText === "Disabled") {
        result.classList.add("muted");
        result.textContent = "n/a";
      } else if (labelText === "Passed") {
        result.classList.add("success-text");
        result.textContent = "✓";
        result.setAttribute("aria-label", "Passed");
      } else if (labelText === "Warning") {
        result.classList.add("warning-text");
        result.textContent = "⚠";
        result.setAttribute("aria-label", "Warning gate failed");
      } else if (["Rejected", "Failed"].includes(labelText)) {
        result.classList.add("error-text");
        result.textContent = "✕";
        result.setAttribute("aria-label", "Failed");
      } else if (labelText === "Pending") {
        result.classList.add("muted");
        result.textContent = "◷";
        result.setAttribute("aria-label", "Pending");
      } else {
        result.classList.add("muted");
        result.textContent = labelText;
      }
      result.title = labelText;
      line.append(label, result);
      if (labelText !== "Disabled") {
        const prompt = document.createElement("a");
        prompt.href = route("gate-prompt", state.run.run_id, candidate.view, key);
        prompt.target = "_blank";
        prompt.rel = "noopener";
        prompt.className = "local-pipeline-prompt-link";
        prompt.textContent = "▤";
        prompt.setAttribute("aria-label", `${key.replaceAll("_", " ")} prompt`);
        prompt.title = "View prompt";
        line.append(prompt);
      }
      return line;
    });
  }

  function imageUrl(candidate) { return route("image", state.run.run_id, "", candidate.candidate_id); }

  function addButton(host, text, action, { disabled = false, primary = false, view = "", candidate = "" } = {}) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    button.dataset.localAction = action;
    button.dataset.view = view;
    button.dataset.candidate = candidate;
    button.disabled = disabled;
    if (primary) button.classList.add("primary-action");
    host.append(button);
    return button;
  }

  function renderSelectedViews(run) {
    const host = $("selected");
    host.replaceChildren();
    const selected = run.selected_views || {};
    const assets = Object.values(run.local_assets || {});
    const lockNotice = document.createElement("p");
    lockNotice.className = "local-pipeline-lock-notice";
    lockNotice.setAttribute("role", "status");
    lockNotice.textContent = "Locked images for this pipeline in another batch.";
    lockNotice.hidden = true;
    host.append(lockNotice);
    for (const view of run.views || []) {
      const article = document.createElement("article");
      article.className = "local-pipeline-selected-card";
      const title = document.createElement("h2");
      title.textContent = view;
      article.append(title);
      const candidate = (run.candidates || []).find((item) => item.candidate_id === selected[view] && item.image_path);
      if (!candidate) {
        const empty = document.createElement("p");
        empty.className = "muted";
        empty.textContent = "No image selected";
        article.append(empty);
      } else {
        const image = document.createElement("img");
        image.loading = "lazy";
        image.src = imageUrl(candidate);
        image.alt = `Selected ${view} candidate ${candidate.candidate_id}`;
        article.append(image);
        const asset = assets.find((item) => item.view === view && String(item.pipeline || "").toLowerCase() === state.pipeline
          && String(item.qualifier || "") === (isCostume() ? run.costume || "" : ""));
        const locked = Boolean(asset?.locked && asset.candidate_id === candidate.candidate_id
          && asset.batch_id === run.run_id);
        const lockedInAnotherBatch = Boolean(asset?.locked && asset.batch_id !== run.run_id);
        if (lockedInAnotherBatch) lockNotice.hidden = false;
        const lockState = document.createElement("p");
        lockState.className = locked ? "success-text" : "muted";
        lockState.textContent = locked ? "Locked local asset" : "Selected · not locked";
        article.append(lockState);
        const controls = document.createElement("div");
        controls.className = "button-row compact";
        addButton(controls, locked ? "Unlock" : "Lock", locked ? "unlock" : "lock",
          { view, disabled: lockedInAnotherBatch });
        if (!locked) addButton(controls, "Unselect", "unselect", { view, candidate: candidate.candidate_id });
        article.append(controls);
      }
      host.append(article);
    }
    host.hidden = !run.views?.length;
  }

  function renderCandidate(view, candidate, ranking, run) {
    const card = document.createElement("article");
    const selected = run.selected_views?.[view] === candidate.candidate_id;
    card.className = `local-pipeline-candidate${selected ? " is-selected" : ""}`;
    card.dataset.view = view;
    card.dataset.candidate = candidate.candidate_id;
    const heading = document.createElement("h3");
    heading.textContent = candidate.candidate_id;
    card.append(heading);
    if (candidate.image_path) {
      const imageButton = document.createElement("button");
      imageButton.className = "local-pipeline-candidate-image";
      imageButton.dataset.localAction = "review";
      imageButton.dataset.candidate = candidate.candidate_id;
      const image = document.createElement("img");
      image.loading = "lazy";
      image.src = imageUrl(candidate);
      image.alt = `${view} candidate ${candidate.candidate_id}`;
      imageButton.append(image);
      card.append(imageButton);
    } else {
      const pending = document.createElement("p");
      pending.textContent = statusLabels[candidate.status] || candidate.status || "Waiting";
      card.append(pending);
    }
    const status = document.createElement("p");
    status.className = "muted";
    const rank = (ranking.ordered_candidate_ids || []).indexOf(candidate.candidate_id);
    status.textContent = `${statusLabels[candidate.status] || candidate.status || "Unknown"}${rank >= 0 ? ` · Rank #${rank + 1}` : ""}`;
    card.append(status);
    for (const line of gateSummary(candidate)) card.append(line);
    const human = document.createElement("p");
    human.className = "muted";
    human.textContent = `Human ${candidate.human_review?.decision || "undecided"}`;
    card.append(human);
    const controls = document.createElement("div");
    controls.className = "button-row compact local-pipeline-candidate-controls";
    if (state.pipeline === "body-reference") {
      if (candidate.image_path) addButton(controls, "Review", "review", { disabled: busy(run), view, candidate: candidate.candidate_id });
    } else {
      if (candidate.image_path) addButton(controls, "Review", "review", { disabled: busy(run), view, candidate: candidate.candidate_id });
      const humanDecision = candidate.human_review?.decision || "undecided";
      const canSelect = rank >= 0 && !selected && !busy(run)
        && (!candidate.rejection_gate || humanDecision === "keep")
        && humanDecision !== "reject" && (view !== "FRONT" || humanDecision === "keep");
      if (canSelect) addButton(controls, "Select", "select", { primary: true, view, candidate: candidate.candidate_id });
      if (["FAILED", "GATE_REJECTED"].includes(candidate.status)) addButton(controls, "Retry", "retry", { disabled: busy(run), view, candidate: candidate.candidate_id });
    }
    if (controls.childElementCount) card.append(controls);
    return card;
  }

  function renderViews(run) {
    const host = $("views");
    const previousOpen = new Map(Array.from(host.querySelectorAll("details.local-pipeline-view"), (details) => [details.dataset.view, details.open]));
    host.replaceChildren();
    for (const view of run.views || []) {
      const candidates = (run.candidates || []).filter((candidate) => candidate.view === view);
      const details = document.createElement("details");
      details.className = "local-pipeline-view";
      details.dataset.view = view;
      const selected = run.selected_views?.[view] || "";
      const selectionChanged = Object.hasOwn(state.renderedSelections, view) && state.renderedSelections[view] !== selected;
      details.open = selectionChanged && selected ? false : (previousOpen.has(view) ? previousOpen.get(view) : !selected);
      const summary = document.createElement("summary");
      const heading = document.createElement("strong");
      heading.textContent = `${view} · ${run.selected_views?.[view] || "not selected"} · ${candidates.filter((item) => item.image_path).length}/${candidates.length} images`;
      summary.append(heading);
      const ranking = run.rankings?.[view] || {};
      const viewActions = document.createElement("span");
      viewActions.className = "button-row compact";
      const viewReady = view === "FRONT" || run.use_front_anchor === false || Boolean(run.front_anchor);
      addButton(viewActions, "Re-run view", "rerun-view", { disabled: busy(run) || !viewReady || !candidates.length, view });
      addButton(viewActions, "Re-run failed", "rerun-failed", { disabled: busy(run) || !viewReady || !candidates.some((item) => ["FAILED", "GATE_REJECTED"].includes(item.status)), view });
      addButton(viewActions, "Re-evaluate", "reevaluate-view", { disabled: busy(run) || !viewReady || !candidates.some((item) => item.image_path), view });
      addButton(viewActions, ranking.status === "COMPLETE" ? "Re-rank" : "Rank survivors", "rank", { disabled: busy(run) || !viewReady || !candidates.some((item) => item.image_path), view });
      summary.append(viewActions);
      details.append(summary);
      if (hasSharedAssetRouter()) {
        const roles = state.pipeline === "character-assembly"
          ? ["body_reference", "head_image"]
          : ["character_assembly"];
        const sources = document.createElement("div");
        sources.className = "local-pipeline-sources";
        for (const role of roles) {
          const figure = document.createElement("figure");
          const caption = document.createElement("figcaption");
          caption.textContent = role.replaceAll("_", " ");
          const image = document.createElement("img");
          image.loading = "lazy";
          image.alt = caption.textContent;
          image.src = route("source", run.run_id, view, role);
          figure.append(caption, image);
          sources.append(figure);
        }
        details.append(sources);
      }
      const links = document.createElement("p");
      links.className = "muted";
      addLink(links, "Review specification", route("prompt", run.run_id, view));
      links.append(document.createTextNode(" · "));
      addLink(links, "Image prompt", route("image-prompt", run.run_id, view));
      details.append(links);
      const gallery = document.createElement("div");
      gallery.className = "local-pipeline-gallery";
      candidates.sort((left, right) => {
        const order = ranking.ordered_candidate_ids || [];
        return (order.indexOf(left.candidate_id) < 0 ? Infinity : order.indexOf(left.candidate_id))
          - (order.indexOf(right.candidate_id) < 0 ? Infinity : order.indexOf(right.candidate_id));
      });
      for (const candidate of candidates) gallery.append(renderCandidate(view, candidate, ranking, run));
      details.append(gallery);
      host.append(details);
    }
    state.renderedSelections = { ...(run.selected_views || {}) };
  }

  function updateRefreshButton() {
    const button = $("refresh");
    const hasRun = Boolean(state.run?.run_id);
    const hasNewImages = Boolean(state.polledRun);
    button.disabled = hasRun && !hasNewImages;
    button.textContent = hasNewImages ? "Refresh · New images available" : "Refresh";
  }

  function render() {
    const run = state.run;
    if (!run) {
      $("summary").textContent = "No batch selected. Check requirements and create a new batch.";
      $("rename").hidden = true;
      $("selected").replaceChildren();
      $("selected").hidden = true;
      $("views").replaceChildren();
      state.renderedSelections = {};
      state.polledRun = null;
      updateRefreshButton();
      setBusyControls();
      return;
    }
    const progress = run.page_summary || {};
    const completed = progress.completed_count ?? run.complete_count ?? (run.candidates || []).filter((item) => item.image_path).length;
    $("summary").textContent = `${run.character} · ${run.phase}${run.costume ? ` · ${run.costume}` : ""} · ${run.run_id} · ${completed}/${run.candidate_count || (run.candidates || []).length} images · ${statusLabels[run.status] || run.status}${run.front_anchor ? ` · FRONT ${run.front_anchor}` : ""}${progress.stale_selections?.length ? ` · stale selections ${progress.stale_selections.join(", ")}` : ""}`;
    if (state.pipeline === "body-reference" && run.set_report?.coherent) {
      $("summary").textContent += ` · lineup ${Object.values(run.set_report.coherent).every(Boolean) ? "coherent" : "needs review"}`;
    }
    if (document.activeElement !== $("batch-name")) $("batch-name").value = run.batch_name || "";
    setBusyControls();
    renderSelectedViews(run);
    renderViews(run);
    updateRefreshButton();
  }

  async function loadRun(runId, generation = state.generation) {
    if (!runId) { state.run = null; render(); return; }
    const loaded = await request(route("detail", runId));
    if (generation !== state.generation || contextKey() !== state.contextKey) return;
    state.run = loaded;
    state.polledRun = null;
    render();
  }

  async function pollForImages(runId, generation = state.generation) {
    if (state.pollInFlight || !state.run || state.run.run_id !== runId) return;
    state.pollInFlight = true;
    try {
      const latest = await request(route("detail", runId));
      if (generation !== state.generation || state.run?.run_id !== runId) return;
      const knownImages = new Map((state.run.candidates || []).filter((item) => item.image_path).map((item) => [item.candidate_id, item.image_path]));
      const hasNewImage = (latest.candidates || []).some((item) => item.image_path && knownImages.get(item.candidate_id) !== item.image_path);
      if (hasNewImage) {
        state.polledRun = latest;
        updateRefreshButton();
      }
    } catch (_) {
      // Poll failures are transient; the next interval will retry.
    } finally {
      state.pollInFlight = false;
    }
  }

  async function refreshRuns(preferred = "", generation = state.generation) {
    state.runs = (await request(route("runs"))).runs || [];
    if (generation !== state.generation) return;
    const select = $("runs");
    select.replaceChildren();
    for (const run of state.runs) {
      select.add(new Option(`${run.batch_name || run.run_id} · ${statusLabels[run.status] || run.status} · ${run.run_id}`, run.run_id));
    }
    if (!state.runs.length) select.add(new Option("No batches for this character, phase, and costume", ""));
    const current = state.run?.run_id;
    const chosen = [preferred, current].find((id) => id && state.runs.some((run) => run.run_id === id)) || state.runs[0]?.run_id || "";
    select.value = chosen;
    await loadRun(chosen, generation);
  }

  async function readiness() {
    const generation = ++state.previewGeneration;
    $("create").disabled = true;
    $("readiness").textContent = "Checking required inputs…";
    try {
      const result = await request(route("preview"), { method: "POST", body: JSON.stringify(payload()) });
      if (generation !== state.previewGeneration) return;
      const blockers = result.blocking_reasons || [];
      const canCreate = result.can_create !== false && blockers.length === 0;
      $("readiness").textContent = blockers.length ? blockers.join(" · ")
        : `${result.candidate_count || ""} candidates across ${(result.views || []).length} views. ${canCreate ? "Ready to create." : "Resolve requirements first."}`;
      $("create").disabled = !canCreate;
    } catch (error) {
      if (generation !== state.previewGeneration) return;
      $("readiness").textContent = error.message;
      $("create").disabled = true;
    }
  }

  async function refreshContext() {
    state.generation += 1;
    state.contextKey = contextKey();
    state.run = null;
    state.polledRun = null;
    state.renderedSelections = {};
    state.frontSourcePath = "";
    $("source-preview").textContent = "No FRONT reference selected.";
    $("source-file").value = "";
    $("source-remove").hidden = true;
    try {
      await loadCostumes();
      await Promise.all([refreshRuns("", state.generation), readiness()]);
    } catch (error) { setStatus(error.message, true); }
  }

  async function loadCostumes() {
    if (!isCostume()) return;
    const generation = state.generation;
    const pipeline = state.pipeline;
    const character = document.querySelector("#character-select").value;
    const phase = document.querySelector("#phase-select").value;
    const data = await request(`/api/costumes?${new URLSearchParams({ character, phase })}`);
    if (generation !== state.generation || pipeline !== state.pipeline || contextKey() !== state.contextKey) return;
    const select = $("costume");
    const previous = select.value;
    select.replaceChildren(...(data.costumes || []).map((item) => new Option(item.name, item.name)));
    if (!select.options.length) select.add(new Option("No costumes available", ""));
    if (Array.from(select.options).some((item) => item.value === previous)) select.value = previous;
  }

  function configurePipeline(pipeline) {
    state.pipeline = pipeline;
    state.generation += 1;
    state.contextKey = contextKey();
    state.run = null;
    state.frontSourcePath = "";
    document.querySelector("#local-pipeline-title").textContent = {
      "body-reference": "Body-Reference", "head-image": "Head-Image",
      "character-assembly": "Character-Assembly", "costume-dressing": "Costume-Dressing",
    }[pipeline];
    $("costume-label").hidden = !isCostume();
    $("anchor-option").hidden = !hasSharedAssetRouter();
    if (hasSharedAssetRouter()) $("use-anchor").checked = false;
    $("source-option").hidden = pipeline !== "head-image";
    $("lineup").hidden = true;
    $("source-remove").hidden = true;
    $("source-preview").textContent = "No FRONT reference selected.";
    $("runs").replaceChildren(new Option("Loading batches…", ""));
    $("views").replaceChildren();
    $("selected").replaceChildren();
    setStatus("");
    if (state.poll) clearInterval(state.poll);
    state.poll = setInterval(() => {
      if (state.pipeline === pipeline && document.querySelector("#local-pipeline-page").classList.contains("active") && state.run?.run_id && !$("review-dialog").open) {
        void pollForImages(state.run.run_id, state.generation);
      }
    }, 5000);
    const generation = state.generation;
    void refreshContext().then(() => loadGateSettings(state.generation)).catch((error) => setStatus(error.message, true));
  }

  async function uploadHeadSource(file) {
    if (!file) return;
    const context = { character: document.querySelector("#character-select").value, phase: document.querySelector("#phase-select").value };
    if (busy()) { setStatus("Stop the current batch before changing its reference image.", true); return; }
    try {
      const response = await fetch(`/api/local/head-image/sources?${new URLSearchParams({ ...context, filename: file.name || "pasted-reference.png" })}`, {
        method: "POST", headers: { "Content-Type": file.type || "application/octet-stream" }, body: file,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Could not upload the reference image.");
      state.frontSourcePath = data.path || "";
      $("source-preview").replaceChildren();
      const image = document.createElement("img");
      image.src = URL.createObjectURL(file);
      image.alt = "Selected FRONT reference";
      $("source-preview").append(image);
      $("source-remove").hidden = false;
      if (state.run) {
        const update = await request(`${baseUrl()}/runs/${encodeURIComponent(state.run.run_id)}/source`, {
          method: "PUT", body: JSON.stringify({ source_path: state.frontSourcePath }),
        });
        state.frontSourcePath = "";
        await refreshRuns(update.run_id);
        setStatus("Reference saved to this batch. Generated images and reviews were cleared; start the batch to regenerate.");
      } else setStatus("Reference saved for the next batch.");
    } catch (error) { setStatus(error.message, true); }
  }

  async function perform(action, view = "", candidateId = "", body = undefined) {
    const method = action === "rename" || action === "lineup"
      ? "PUT" : action === "delete" ? "DELETE" : "POST";
    let path;
    if (action === "local-analysis") path = `${baseUrl()}/runs/${encodeURIComponent(state.run.run_id)}/candidates/${encodeURIComponent(candidateId)}/local-analysis`;
    else if (action === "luna-analysis") path = `${baseUrl()}/runs/${encodeURIComponent(state.run.run_id)}/candidates/${encodeURIComponent(candidateId)}/luna-analysis`;
    else if (action === "queue-render") path = `${baseUrl()}/runs/${encodeURIComponent(state.run.run_id)}/candidates/${encodeURIComponent(candidateId)}/render`;
    else if (action === "lineup") path = `${baseUrl()}/runs/${encodeURIComponent(state.run.run_id)}/lineups/front-conditioned`;
    else if (action === "reevaluate-view") path = `${baseUrl()}/runs/${encodeURIComponent(state.run.run_id)}/reevaluate${query({ view })}`;
    else path = route(action, state.run?.run_id, view, candidateId);
    const result = await request(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });
    if (action === "delete") {
      state.run = null;
      await refreshRuns();
      setStatus("Batch deleted.");
      return;
    }
    if (["start", "resume", "stop", "rank", "local-analysis", "luna-analysis", "queue-render", "retry", "rerun", "rerun-view", "rerun-failed", "reevaluate", "reevaluate-view", "proceed"].includes(action)) {
      setStatus(action === "stop" ? "Stop requested." : "Work queued.");
    } else if (action === "lock" || action === "unlock" || action === "select" || action === "unselect") {
      setStatus("Selection updated.");
    } else if (action === "lineup") setStatus("Selected views saved as the FRONT-conditioned lineup.");
    if (action === "rerun" || action === "rerun-view" || action === "rerun-failed" || action === "reevaluate" || action === "reevaluate-view" || action === "proceed") {
      state.run = result;
      state.polledRun = null;
      render();
    } else await loadRun(state.run?.run_id);
  }

  function orderedReviewCandidates() {
    const candidates = (state.run?.candidates || []).filter((item) => item.image_path);
    const views = state.run?.views || [];
    return candidates.sort((left, right) => {
      const viewOrder = views.indexOf(left.view) - views.indexOf(right.view);
      if (viewOrder) return viewOrder;
      const order = state.run?.rankings?.[left.view]?.ordered_candidate_ids || [];
      return order.indexOf(left.candidate_id) - order.indexOf(right.candidate_id);
    });
  }

  function renderReview() {
    const candidate = state.reviewCandidates[state.reviewIndex];
    if (!candidate) return;
    const run = state.run;
    const oppositeViews = {
      LEFT_PROFILE: "RIGHT_PROFILE", RIGHT_PROFILE: "LEFT_PROFILE",
      FRONT_LEFT_3_4: "FRONT_RIGHT_3_4", FRONT_RIGHT_3_4: "FRONT_LEFT_3_4",
      BACK_LEFT_3_4: "BACK_RIGHT_3_4", BACK_RIGHT_3_4: "BACK_LEFT_3_4",
    };
    const oppositeView = oppositeViews[candidate.view];
    const selectedViews = run.selected_views || {};
    const candidates = run.candidates || [];
    const frontId = run.front_anchor || selectedViews.FRONT;
    const front = candidates.find((item) => item.candidate_id === frontId && item.view === "FRONT" && item.image_path);
    const oppositeId = oppositeView && selectedViews[oppositeView];
    const opposite = oppositeId && candidates.find((item) => item.candidate_id === oppositeId
      && item.view === oppositeView && item.image_path);
    const toggleLabel = $("review-toggle-label");
    const toggle = $("review-toggle");
    toggleLabel.hidden = !oppositeView;
    toggle.disabled = !opposite;
    toggle.checked = state.compareOpposite && Boolean(opposite);
    const comparison = toggle.checked ? opposite : front;
    $("review-compare-title").textContent = toggle.checked ? `Selected ${oppositeView}` : "Selected FRONT";
    const compareImage = $("review-compare-image");
    if (comparison) {
      compareImage.src = imageUrl(comparison);
      compareImage.alt = `${toggle.checked ? `Selected ${oppositeView}` : "Selected FRONT"} ${comparison.candidate_id}`;
      compareImage.hidden = false;
      $("review-compare-empty").hidden = true;
    } else {
      compareImage.removeAttribute("src");
      compareImage.hidden = true;
      $("review-compare-empty").hidden = false;
      $("review-compare-empty").textContent = "No selected FRONT image is available for comparison.";
    }
    $("review-image").src = imageUrl(candidate);
    $("review-image").alt = `${candidate.view} candidate ${candidate.candidate_id}`;
    const panel = $("review-panel");
    panel.replaceChildren();
    const title = document.createElement("h2");
    title.textContent = candidate.candidate_id;
    const view = document.createElement("p");
    view.className = "local-pipeline-review-position";
    view.textContent = `${candidate.view} · ${state.reviewIndex + 1} of ${state.reviewCandidates.length} · ${statusLabels[candidate.status] || candidate.status}`;
    const info = document.createElement("p");
    info.className = "local-pipeline-review-meta muted";
    const metadata = [candidate.method && `Method: ${candidate.method}`, candidate.seed && `Seed: ${candidate.seed}`].filter(Boolean);
    if (candidate.rejection_gate) metadata.push(`Rejected by: ${candidate.rejection_gate}`);
    info.textContent = metadata.join(" · ");
    const decision = document.createElement("fieldset");
    decision.className = "decision-options local-pipeline-decision-options";
    const legend = document.createElement("legend");
    legend.textContent = "Human decision";
    decision.append(legend);
    const savedDecision = candidate.human_review?.decision === "pass" ? "keep"
      : candidate.human_review?.decision === "fail" ? "reject" : candidate.human_review?.decision || "undecided";
    for (const [value, label] of [["undecided", "Undecided"], ["keep", "Pass"], ["reject", "Fail"]]) {
      const wrapper = document.createElement("label");
      wrapper.className = "decision-option";
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = "local-human-decision";
      radio.value = value;
      radio.checked = savedDecision === value;
      wrapper.append(radio, document.createTextNode(label));
      decision.append(wrapper);
    }
    const notesLabel = document.createElement("label");
    notesLabel.textContent = "Notes";
    const notes = document.createElement("textarea");
    notes.value = candidate.human_review?.notes || "";
    notesLabel.append(notes);
    const save = document.createElement("button");
    save.className = "primary-action";
    save.textContent = "Save review";
    save.addEventListener("click", async () => {
      const selected = decision.querySelector("input:checked")?.value || "undecided";
      try {
        await perform("review", candidate.view, candidate.candidate_id, { decision: selected, notes: notes.value });
        state.reviewCandidates = orderedReviewCandidates();
        state.reviewIndex = state.reviewCandidates.findIndex((item) => item.candidate_id === candidate.candidate_id);
        renderReview();
      } catch (error) { setStatus(error.message, true); }
    });
    const select = document.createElement("button");
    select.textContent = "Select this image";
    select.disabled = selectedViews[candidate.view] === candidate.candidate_id
      || !(run.rankings?.[candidate.view]?.ordered_candidate_ids || []).includes(candidate.candidate_id);
    select.addEventListener("click", async () => {
      try {
        await perform("select", candidate.view, candidate.candidate_id, { candidate_id: candidate.candidate_id });
        state.reviewCandidates = orderedReviewCandidates();
        state.reviewIndex = state.reviewCandidates.findIndex((item) => item.candidate_id === candidate.candidate_id);
        renderReview();
      } catch (error) { setStatus(error.message, true); }
    });
    const content = document.createElement("section");
    content.className = "local-pipeline-review-content";
    for (const line of gateSummary(candidate)) content.append(line);
    const ranking = run.rankings?.[candidate.view] || {};
    const rankingOrder = ranking.luna_ordered_candidate_ids || ranking.ordered_candidate_ids || [];
    const rankingPosition = rankingOrder.indexOf(candidate.candidate_id);
    const adjustedOrder = ranking.ordered_candidate_ids || [];
    const adjustedPosition = adjustedOrder.indexOf(candidate.candidate_id);
    const rankEntry = (ranking.entries || []).find((item) => item.candidate_id === candidate.candidate_id);
    const rankingInfo = document.createElement("p");
    rankingInfo.className = "local-pipeline-review-explanation";
    rankingInfo.textContent = rankingPosition >= 0
      ? `Luna rank #${rankingPosition + 1}${rankEntry?.reason ? ` · ${rankEntry.reason}` : ""}`
      : ranking.status === "STALE" ? `Luna ranking stale · ${ranking.stale_reason || "Review inputs changed"}`
        : ranking.status === "FAILED" ? `Luna ranking failed · ${ranking.error || "No details available"}` : "Luna ranking: not ranked";
    const analysis = document.createElement("div");
    analysis.className = "local-pipeline-review-analyses";
    if (state.pipeline === "body-reference") {
      for (const [provider, titleText] of [["local", "Local review"], ["luna", "Luna review"]]) {
        const result = candidate.analyses?.[provider];
        const row = document.createElement("p");
        row.className = "local-pipeline-review-explanation";
        const status = result ? (result.pass === true && !result.uncertain ? "Pass" : result.uncertain ? "Uncertain" : "Fail")
          : provider === "local" ? candidate.local_job?.status || "Pending" : candidate.luna_status || "Pending";
        const reason = result?.failure_reason || (result?.failure_categories || []).join(", ") || result?.evidence
          || (provider === "luna" && candidate.luna_error) || (provider === "local" && candidate.local_job?.error) || "";
        row.textContent = `${titleText}: ${status}${reason ? ` · ${reason}` : ""}`;
        analysis.append(row);
      }
    }
    const actions = document.createElement("div");
    actions.className = "button-row compact local-pipeline-review-actions";
    actions.append(save);
    if (!select.disabled) actions.append(select);
    if (adjustedPosition >= 0) {
      const up = document.createElement("button");
      up.type = "button";
      up.textContent = "Rank up";
      up.disabled = adjustedPosition <= 0;
      up.addEventListener("click", async () => {
        try {
          await perform("move-rank", candidate.view, candidate.candidate_id, { candidate_id: candidate.candidate_id, direction: "up" });
          state.reviewCandidates = orderedReviewCandidates();
          state.reviewIndex = state.reviewCandidates.findIndex((item) => item.candidate_id === candidate.candidate_id);
          renderReview();
        } catch (error) { setStatus(error.message, true); }
      });
      const down = document.createElement("button");
      down.type = "button";
      down.textContent = "Rank down";
      down.disabled = adjustedPosition >= adjustedOrder.length - 1;
      down.addEventListener("click", async () => {
        try {
          await perform("move-rank", candidate.view, candidate.candidate_id, { candidate_id: candidate.candidate_id, direction: "down" });
          state.reviewCandidates = orderedReviewCandidates();
          state.reviewIndex = state.reviewCandidates.findIndex((item) => item.candidate_id === candidate.candidate_id);
          renderReview();
        } catch (error) { setStatus(error.message, true); }
      });
      actions.append(up, down);
    }
    panel.append(title, view);
    if (info.textContent) panel.append(info);
    panel.append(content, rankingInfo, analysis, decision, notesLabel, actions);
    $("review-prev").disabled = state.reviewIndex <= 0;
    $("review-next").disabled = state.reviewIndex >= state.reviewCandidates.length - 1;
  }

  function openReview(candidateId) {
    state.reviewCandidates = orderedReviewCandidates();
    state.reviewIndex = state.reviewCandidates.findIndex((item) => item.candidate_id === candidateId);
    if (state.reviewIndex < 0) return;
    state.compareOpposite = false;
    renderReview();
    $("review-dialog").showModal();
  }

  async function handleAction(button) {
    const action = button.dataset.localAction;
    const view = button.dataset.view;
    const candidateId = button.dataset.candidate || button.closest?.("[data-candidate]")?.dataset.candidate || "";
    if (action === "review") { openReview(candidateId); return; }
    if (["delete", "rerun", "rerun-view", "rerun-failed", "unselect", "unlock"].includes(action)) {
      const prompts = {
        delete: "Delete this batch and its run-owned files?", rerun: "Re-run the batch? This replaces generated images and reviews.",
        "rerun-view": `Replace all ${view} candidates?`, "rerun-failed": `Re-run failed ${view} candidates?`,
        unselect: `Unselect ${view}?`, unlock: `Unlock the local ${view} asset?`,
      };
      if (!window.confirm(prompts[action])) return;
    }
    if (action === "lineup") {
      const selections = { ...(state.run.selected_views || {}) };
      await perform(action, "", "", { selections });
      return;
    }
    if (action === "rank-up" || action === "rank-down") {
      const ordered = state.run.rankings?.[view]?.ordered_candidate_ids || [];
      const position = ordered.indexOf(candidateId);
      if (position < 0) return;
      await perform("move-rank", view, candidateId, { candidate_id: candidateId, direction: action === "rank-up" ? "up" : "down" });
      return;
    }
    await perform(action, view, candidateId, action === "rename" ? { batch_name: $("batch-name").value } : action === "select" || action === "unselect" ? { candidate_id: action === "unselect" ? "" : candidateId } : undefined);
  }

  function bind() {
    $("refresh").addEventListener("click", () => {
      if (state.polledRun && state.polledRun.run_id === state.run?.run_id) {
        state.run = state.polledRun;
        state.polledRun = null;
        render();
        setStatus("New images loaded.");
        return;
      }
      void Promise.all([refreshRuns(), readiness()]).catch((error) => setStatus(error.message, true));
    });
    $("preview").addEventListener("click", () => void readiness());
    $("create").addEventListener("click", async () => {
      try {
        const created = await request(route("create"), { method: "POST", body: JSON.stringify(payload()) });
        state.frontSourcePath = "";
        if (hasSharedAssetRouter()) $("use-anchor").checked = false;
        await refreshRuns(created.run_id);
        if (hasSharedAssetRouter()) void readiness();
        setStatus("Queued batch created. Start it when ready.");
      } catch (error) { setStatus(error.message, true); await readiness(); }
    });
    $("rename").addEventListener("submit", async (event) => { event.preventDefault(); await handleAction({ dataset: { localAction: "rename" } }).catch((error) => setStatus(error.message, true)); });
    $("runs").addEventListener("change", () => void loadRun($("runs").value).catch((error) => setStatus(error.message, true)));
    $("costume").addEventListener("change", () => void refreshContext());
    $("front-count").addEventListener("change", () => void readiness());
    $("other-count").addEventListener("change", () => void readiness());
    $("use-anchor").addEventListener("change", () => void readiness());
    $("start").addEventListener("click", () => void perform(["INTERRUPTED", "STOPPED"].includes(state.run?.status) ? "resume" : "start").catch((error) => setStatus(error.message, true)));
    $("stop").addEventListener("click", () => void perform("stop").catch((error) => setStatus(error.message, true)));
    $("rerun").addEventListener("click", () => void handleAction({ dataset: { localAction: "rerun" } }).catch((error) => setStatus(error.message, true)));
    $("reevaluate").addEventListener("click", () => void perform("reevaluate").catch((error) => setStatus(error.message, true)));
    $("delete").addEventListener("click", () => void handleAction({ dataset: { localAction: "delete" } }).catch((error) => setStatus(error.message, true)));
    $("proceed").addEventListener("click", () => void perform("proceed").catch((error) => setStatus(error.message, true)));
    $("lineup").addEventListener("click", () => void handleAction({ dataset: { localAction: "lineup" } }).catch((error) => setStatus(error.message, true)));
    $("source-file").addEventListener("change", () => void uploadHeadSource($("source-file").files?.[0]));
    $("source-paste").addEventListener("paste", (event) => {
      const file = Array.from(event.clipboardData?.items || []).map((item) => item.getAsFile()).find(Boolean);
      if (!file) return;
      event.preventDefault();
      void uploadHeadSource(file);
    });
    $("source-remove").addEventListener("click", async () => {
      state.frontSourcePath = "";
      $("source-file").value = "";
      $("source-preview").textContent = "No FRONT reference selected.";
      $("source-remove").hidden = true;
      if (state.run) {
        try {
          const updated = await request(`${baseUrl()}/runs/${encodeURIComponent(state.run.run_id)}/source`, { method: "PUT", body: JSON.stringify({ source_path: "" }) });
          await refreshRuns(updated.run_id);
        } catch (error) { setStatus(error.message, true); }
      }
    });
    for (const host of [$("views"), $("selected")]) host.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-local-action]");
      if (button?.closest("summary")) {
        event.preventDefault();
        event.stopPropagation();
      }
      if (button) void handleAction(button).catch((error) => setStatus(error.message, true));
    });
    $("review-close").addEventListener("click", () => $("review-dialog").close());
    $("review-toggle").addEventListener("change", () => { state.compareOpposite = $("review-toggle").checked; renderReview(); });
    $("review-prev").addEventListener("click", () => { state.reviewIndex -= 1; renderReview(); });
    $("review-next").addEventListener("click", () => { state.reviewIndex += 1; renderReview(); });
  }

  async function activate(page) {
    const pipeline = pagePipelines[page];
    if (!pipeline) return;
    if (pipeline === state.pipeline) {
      if (contextKey() !== state.contextKey) await refreshContext();
      return;
    }
    configurePipeline(pipeline);
  }

  function deactivate() {
    state.generation += 1;
    state.previewGeneration += 1;
  }

  bind();
  document.querySelector("#character-select").addEventListener("change", () => {
    if (state.pipeline && document.querySelector("#local-pipeline-page").classList.contains("active")) setTimeout(() => void refreshContext(), 0);
  });
  document.querySelector("#phase-select").addEventListener("change", () => {
    if (state.pipeline && document.querySelector("#local-pipeline-page").classList.contains("active")) setTimeout(() => void refreshContext(), 0);
  });
  window.ZetLocalAssetPipeline = { activate, deactivate };
})();
