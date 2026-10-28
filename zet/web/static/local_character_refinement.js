/* Dedicated image-only character refinement workspace. */
(() => {
  const params = new URLSearchParams(location.search);
  const pipeline = params.get("pipeline"), runId = params.get("run_id"), view = params.get("view");
  const universe = params.get("universe_id") || "", costume = params.get("costume") || "";
  const $ = id => document.getElementById(`refine-${id}`);
  let data, current = "original", loading = false, acting = false, serial = 0, analysisSignature = "", comparisonsSignature = "";
  const key = `character-refinement:${universe}:${pipeline}:${runId}:${view}`;
  let draft = {};
  try { draft = JSON.parse(localStorage.getItem(key) || "{}"); } catch (_) { /* Ignore unavailable saved drafts. */ }
  function saveDraft() {
    draft = { operation: $("operation").value, guideView: $("guide-view").value, guideScope: $("guide-scope").value, current, feedback: $("feedback").value, model: $("model").value,
      comparisons: [...$("comparisons").querySelectorAll("input:checked")].map(input => input.value),
      itemIds: [...$("analysis").querySelectorAll("input:checked")].map(input => input.value), analysisId: data?.analysis?.id };
    try { localStorage.setItem(key, JSON.stringify(draft)); } catch (_) { /* Controls remain usable without storage. */ }
  }
  function endpoint(suffix = "") {
    const query = new URLSearchParams({ universe_id: universe });
    if (costume) query.set("costume", costume);
    return `/api/local/${encodeURIComponent(pipeline)}/runs/${encodeURIComponent(runId)}/refinements/${data.session_id}${suffix}?${query}`;
  }
  async function request(url, payload) {
    const response = await fetch(url, { method: payload === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json", "X-Zet-Universe": universe },
      body: payload === undefined ? undefined : JSON.stringify(payload) });
    const value = await response.json();
    if (!response.ok) throw new Error(value.detail || "Refinement request failed.");
    return value;
  }
  function message(value, error = false) { $("message").textContent = value; $("message").classList.toggle("error", error); }
  function el(tag, text = "") { const element = document.createElement(tag); element.textContent = text; return element; }
  function render() {
    if (!data) return;
    const options = $("attempt"); options.replaceChildren();
    for (const [index, attempt] of data.attempts.entries()) options.add(new Option(`${index ? `Refinement ${index}` : "Original selection"} · ${attempt.status}${attempt.adopted_candidate_id ? " · used" : ""}`, attempt.id));
    if (!data.attempts.some(attempt => attempt.id === current)) current = "original";
    options.value = current;
    const attempt = data.attempts.find(attempt => attempt.id === current);
    const image = $("image"); image.hidden = !attempt.image_available;
    if (attempt.image_available) {
      const src = endpoint(`/images/${encodeURIComponent(current)}`);
      if (image.getAttribute("src") !== src) image.src = src;
    }
    $("attempt-status").textContent = attempt.error || (attempt.image_available ? "Choose corrections or enter feedback to make another targeted edit." : attempt.status);
    $("use").disabled = acting || !attempt.image_available || !data.can_adopt;
    $("retry").hidden = attempt.status !== "FAILED"; $("retry").disabled = acting;
    $("edit").disabled = acting || !attempt.image_available;
    $("analyze").disabled = acting || !attempt.image_available || data.analysis.status === "RUNNING";
    if (!data.can_adopt) message("The batch selection changed elsewhere. These attempts remain available; open refinement from the current selection to adopt a result.", true);
    const nextComparisons = JSON.stringify(data.comparisons);
    if (comparisonsSignature !== nextComparisons) {
      const checked = comparisonsSignature ? [...$("comparisons").querySelectorAll("input:checked")].map(input => input.value) : draft.comparisons;
      $("comparisons").replaceChildren(el("legend", "Selected views to include in analysis"));
      for (const comparison of data.comparisons) {
        const label = el("label"), input = el("input"); input.type = "checkbox"; input.value = comparison.view;
        input.checked = checked ? checked.includes(comparison.view) : true;
        const image = el("img"); image.alt = `Selected ${comparison.view}`; image.loading = "lazy";
        const query = new URLSearchParams({ universe_id: universe, costume });
        image.src = `/api/local/${encodeURIComponent(pipeline)}/runs/${encodeURIComponent(runId)}/images/${encodeURIComponent(comparison.candidate_id)}?${query}`;
        label.append(input, document.createTextNode(comparison.view.replaceAll("_", " ")), image);
        input.addEventListener("change", saveDraft); $("comparisons").append(label);
      }
      if (!data.comparisons.length) $("comparisons").append(el("p", "No other selected images yet. Analyze this image on its own."));
      comparisonsSignature = nextComparisons;
    }
    if (pipeline === "head-image-edit") {
      $("guide-controls").hidden = false;
      const guide = $("guide-view"), selectedGuide = guide.value || draft.guideView || "";
      const signature = JSON.stringify(data.comparisons);
      if (guide.dataset.signature !== signature) {
        guide.replaceChildren(new Option("None — text-only correction", ""));
        for (const item of data.comparisons) guide.add(new Option(`Selected ${item.view.replaceAll("_", " ")}`, item.view));
        guide.value = [...guide.options].some(option => option.value === selectedGuide) ? selectedGuide : "";
        guide.dataset.signature = signature;
      }
      const hair = $("operation").value === "rear_hair";
      $("operation").querySelector('[value="rear_hair"]').disabled = !["BACK_LEFT_3_4", "BACK_RIGHT_3_4"].includes(view);
      guide.disabled = hair;
      $("guide-scope").disabled = hair;
      if (hair) guide.value = "BACK";
      if (hair && !data.comparisons.some(item => item.view === "BACK")) $("edit").disabled = true;
    }
    const analysis = data.analysis;
    const signature = JSON.stringify([analysis, current]);
    if (signature !== analysisSignature) {
      const section = $("analysis"); section.replaceChildren();
      if (analysis.attempt_id === current) {
        section.append(el("h2", "Suggested corrections"), el("p", analysis.error || analysis.report?.summary || "Analyzing…"));
        for (const item of analysis.report?.items || []) {
          const row = el("section"), label = el("label"), input = el("input"); input.type = "checkbox"; input.value = item.id;
          input.disabled = !item.correction;
          input.checked = !input.disabled && draft.analysisId === analysis.id && (draft.itemIds || []).includes(item.id);
          label.append(input, document.createTextNode(item.feature));
          row.append(label, el("p", item.evidence), el("p", item.correction || "No visible correction suggested."));
          input.addEventListener("change", saveDraft); section.append(row);
        }
        if (analysis.inputs?.length) section.append(el("p", `Analysis used: ${analysis.inputs.map(input => input.view).join(", ")}`));
      } else section.append(el("p", "Choose comparison views, then analyze this attempt. Custom feedback can be used directly."));
      analysisSignature = signature;
    }
  }
  async function action(operation, payload) {
    if (acting) return;
    acting = true; serial++;
    const status = $(operation === "analyze" ? "analysis-message" : operation === "edit" ? "edit-message" : "image-message");
    status.classList.remove("error");
    status.textContent = operation === "analyze" ? "Requesting analysis…" : operation === "adopt" ? "Updating selected image…" : "Requesting refinement…";
    status.setAttribute("aria-busy", "true");
    for (const id of ["use", "edit", "analyze", "retry"]) $(id).disabled = true;
    try {
      saveDraft(); data = await request(endpoint(`/${operation}`), payload);
      status.textContent = operation === "analyze" ? "Analysis request accepted." : operation === "adopt" ? "Selected image updated." : "Refinement request accepted. The attempt status shows progress.";
      if (operation === "edit" || operation === "retry") current = data.attempts.at(-1).id;
      if (operation === "adopt") message("Selected image updated. Return to the batch to Continue or publish it.");
      render(); saveDraft();
    } catch (error) { status.textContent = error.message; status.classList.add("error"); }
    finally { status.removeAttribute("aria-busy"); acting = false; render(); }
  }
  $("operation").value = draft.operation || "correction";
  $("guide-scope").value = draft.guideScope || "";
  for (const id of ["operation", "guide-view", "guide-scope"]) $(id).addEventListener("change", () => { saveDraft(); render(); });
  $("feedback").value = draft.feedback || ""; $("model").value = draft.model || "";
  current = draft.current || "original";
  $("feedback").addEventListener("input", saveDraft); $("model").addEventListener("input", saveDraft);
  $("attempt").addEventListener("change", () => { current = $("attempt").value; render(); saveDraft(); });
  $("analyze").addEventListener("click", () => action("analyze", { attempt_id: current, model: $("model").value,
    comparison_views: [...$("comparisons").querySelectorAll("input:checked")].map(input => input.value) }));
  $("edit").addEventListener("click", () => action("edit", { attempt_id: current, operation_id: crypto.randomUUID(),
    analysis_id: data.analysis.id, item_ids: [...$("analysis").querySelectorAll("input:checked")].map(input => input.value), instructions: $("feedback").value, operation: $("operation").value, guide_view: $("guide-view").value, guide_scope: $("guide-scope").value }));
  $("retry").addEventListener("click", () => action("retry", { attempt_id: current }));
  $("use").addEventListener("click", () => action("adopt", { attempt_id: current, expected_selected_id: data.adopted_candidate_id || data.base_candidate_id }));
  async function initialize() {
    if (!["body-reference", "head-image", "head-image-edit", "character-assembly", "costume-dressing"].includes(pipeline) || !runId || !view || !universe) throw new Error("Open refinement from a selected image in its batch.");
    const query = new URLSearchParams({ universe_id: universe, costume });
    data = await request(`/api/local/${pipeline}/runs/${encodeURIComponent(runId)}/views/${encodeURIComponent(view)}/refinement?${query}`, {});
    const batch = await request(`/api/local/${pipeline}/runs/${encodeURIComponent(runId)}?${query}`);
    const back = new URLSearchParams({ page: `local-${pipeline}`, local_batch: runId,
      universe_id: universe, character: batch.character, phase: batch.phase });
    if (costume) back.set("local_costume", costume);
    $("return").href = `/?${back}`;
    $("title").textContent = `${batch.character} · ${view.replaceAll("_", " ")} refinement`;
    window.ZetModelPicker?.attach($("model"), { required: ["vision"], allowDefault: true });
    render();
    setInterval(async () => {
      if (loading || acting || document.hidden) return;
      loading = true;
      const initial = serial;
      try { const value = await request(endpoint()); if (serial === initial) { data = value; render(); } } catch (error) { message(error.message, true); }
      finally { loading = false; }
    }, 2000);
  }
  void initialize().catch(error => message(error.message, true));
})();
