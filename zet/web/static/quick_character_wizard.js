(() => {
  "use strict";
  const bridge = window.zetQuickCharacterWizard;
  const $ = (id) => document.getElementById(id);
  const dialog = $("quick-character-wizard-dialog");
  if (!bridge || !dialog) return;
  const base = "/api/quick-character-wizard";
  let session = null;
  let slots = [];
  let timer = null;
  let universe = "";
  let dirty = false;
  let pending = false;
  let epoch = 0;
  const refinements = new Map();
  const history = new Map();
  const answers = new Map();

  function node(tag, text = "", className = "") {
    const item = document.createElement(tag);
    if (text) item.textContent = text;
    if (className) item.className = className;
    return item;
  }
  function message(text, error = false) {
    $("qc-message").textContent = text;
    $("qc-message").classList.toggle("error", error);
  }
  function imageUrl(url) {
    return url + (url.includes("?") ? "&" : "?") + "universe_id=" + encodeURIComponent(universe);
  }
  async function api(path = "", method = "GET", body) {
    if (bridge.universe() !== universe) {
      dialog.close();
      throw new Error("The active universe changed. Reopen the wizard.");
    }
    return bridge.fetchJson(base + path, { method, bindToPage: false,
      ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }) });
  }
  async function act(operation) {
    if (pending) return;
    pending = true;
    updateButtons();
    try { await operation(); }
    catch (error) { message(error.message, true); }
    finally { pending = false; updateButtons(); }
  }
  function releaseSlots() {
    for (const slot of slots) if (slot.objectUrl) URL.revokeObjectURL(slot.objectUrl);
  }
  async function setFile(index, file) {
    if (!file || !["image/png", "image/jpeg", "image/webp"].includes(file.type)) throw new Error("Choose a PNG, JPEG or WEBP image.");
    if (file.size > 20 * 1024 * 1024) throw new Error("References must be 20 MiB or smaller.");
    const encoded = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error("Unable to read reference image."));
      reader.readAsDataURL(file);
    });
    if (slots[index].objectUrl) URL.revokeObjectURL(slots[index].objectUrl);
    slots[index].reference = { image: encoded };
    slots[index].objectUrl = URL.createObjectURL(file);
    slots[index].preview.src = slots[index].objectUrl;
    slots[index].preview.hidden = false;
  }
  function setAsset(index, asset) {
    if (asset.status === "archived") throw new Error("Choose an available library image.");
    const slot = slots[index];
    if (slot.objectUrl) URL.revokeObjectURL(slot.objectUrl);
    slot.reference = { asset_id: asset.asset_id };
    slot.preview.src = bridge.fileUrl(asset.image_path);
    slot.preview.hidden = false;
    slot.caption.value = asset.label || "Identity reference";
  }
  function buildSlots() {
    releaseSlots();
    slots = [];
    $("qc-reference-slots").replaceChildren();
    for (let index = 0; index < 3; index++) {
      const card = node("section", "", "qc-card qc-reference-slot");
      card.append(node("h3", `Reference ${index + 1}`));
      const primaryLabel = node("label", "Primary identity ");
      const primary = node("input");
      primary.type = "radio"; primary.name = "qc-primary"; primary.value = String(index); primary.checked = index === 0;
      primaryLabel.prepend(primary); card.append(primaryLabel);
      const preview = node("img"); preview.hidden = true; preview.alt = `Reference ${index + 1}`; card.append(preview);
      const file = node("input"); file.type = "file"; file.accept = "image/png,image/jpeg,image/webp"; file.setAttribute("aria-label", `Upload reference ${index + 1}`);
      file.addEventListener("change", () => act(() => setFile(index, file.files[0]))); card.append(file);
      const paste = node("div", "Click here and paste an image", "paste-zone"); paste.tabIndex = 0;
      paste.setAttribute("aria-label", `Paste reference ${index + 1}`);
      paste.addEventListener("click", () => paste.focus());
      paste.addEventListener("paste", (event) => {
        const image = [...(event.clipboardData?.items || [])].find((item) => item.type.startsWith("image/"));
        if (image) { event.preventDefault(); act(() => setFile(index, image.getAsFile())); }
      });
      card.append(paste);
      const pick = node("button", "Choose from library"); pick.type = "button";
      pick.addEventListener("click", () => act(() => bridge.openLibraryPicker((asset) => setAsset(index, asset))));
      const clear = node("button", "Remove"); clear.type = "button";
      clear.addEventListener("click", () => { if (slots[index].objectUrl) URL.revokeObjectURL(slots[index].objectUrl); slots[index].reference = null; preview.hidden = true; file.value = ""; });
      card.append(pick, clear);
      const captionLabel = node("label", "What to preserve or use");
      const caption = node("textarea"); caption.rows = 2; caption.setAttribute("aria-label", `Reference ${index + 1} caption`); captionLabel.append(caption); card.append(captionLabel);
      slots.push({ reference: null, caption, preview, objectUrl: null });
      $("qc-reference-slots").append(card);
    }
  }
  function reset() {
    epoch++; clearTimeout(timer); session = null; dirty = false;
    refinements.clear(); history.clear(); answers.clear();
    $("qc-name").value = ""; $("qc-notes").value = "";
    $("qc-framing").value = "full_body"; $("qc-side").value = "left";
    $("qc-intake").hidden = false; $("qc-draft").hidden = true;
    $("qc-publication").replaceChildren();
    buildSlots(); message(""); updateButtons();
  }
  async function loadSessions() {
    const payload = await api();
    $("qc-sessions").replaceChildren(new Option("Choose a draft", ""));
    for (const item of payload.sessions) $("qc-sessions").add(new Option(`${item.name} · ${item.status.toLowerCase().replaceAll("_", " ")}`, item.session_id));
  }
  async function open(asset = null) {
    universe = bridge.universe(); reset(); dialog.showModal();
    if (asset) { $("qc-name").value = asset.label || ""; setAsset(0, asset); }
    await loadSessions();
  }
  function terminal() { return session && ["ACCEPTED", "ABANDONED"].includes(session.status); }
  function updateButtons() {
    const blocked = pending || Boolean(session?.busy) || Boolean(terminal());
    for (const id of ["qc-save-draft", "qc-reanalyze", "qc-answer", "qc-description", "qc-identity", "qc-proposed-details", "qc-approved"])
      $(id).disabled = blocked;
    if (session?.questions.length) for (const id of ["qc-save-draft", "qc-description", "qc-identity", "qc-proposed-details", "qc-approved"])
      $(id).disabled = true;
    $("qc-create").disabled = pending;
    $("qc-new").disabled = pending;
    $("qc-resume").disabled = pending;
    $("qc-abandon").disabled = pending || Boolean(terminal());
    $("qc-accept").disabled = blocked || dirty || !session?.proposals_approved || !session.views.every((v) => session.selected[v]);
    for (const button of $("qc-views").querySelectorAll("button"))
      button.disabled = blocked || button.dataset.available !== "true" || (dirty && button.dataset.select === "true");
  }
  async function saveDraft() {
    const response = await api(`/${session.session_id}/draft`, "PATCH", { revision_id: session.revision_id,
      description: $("qc-description").value, identity: $("qc-identity").value,
      proposals: $("qc-proposed-details").value.split("\n").map((text) => text.trim()).filter(Boolean), proposals_approved: $("qc-approved").checked });
    dirty = false; showSession(response.session);
  }
  async function renderView(view, refine = false, candidateId = "") {
    if (dirty || !session.proposals_approved) await saveDraft();
    const response = await api(`/${session.session_id}/${refine ? "refine" : "render"}`, "POST", {
      revision_id: session.revision_id, view, instructions: refinements.get(view) || "", candidate_id: candidateId });
    history.delete(view); showSession(response.session);
  }
  function actionButton(text, available, operation, select = false) {
    const button = node("button", text); button.type = "button";
    button.dataset.available = String(available); button.dataset.select = String(select);
    button.addEventListener("click", () => act(operation)); return button;
  }
  function renderViews() {
    $("qc-views").replaceChildren();
    for (const view of session.views) {
      const card = node("section", "", "qc-card"); card.dataset.view = view;
      card.append(node("h3", view.replace("_3_4", " 3/4").replaceAll("_", " ").toLowerCase()));
      const candidates = session.candidates.filter((c) => c.view === view);
      const choice = candidates.find((c) => c.candidate_id === history.get(view)) || candidates.at(-1);
      if (candidates.length) {
        const picker = node("select"); picker.setAttribute("aria-label", `${view} candidate history`);
        for (const [index, c] of candidates.entries()) picker.add(new Option(`Attempt ${index + 1} · ${c.stale ? "stale" : c.status.toLowerCase().replaceAll("_", " ")}${session.selected[view] === c.candidate_id ? " · approved" : ""}`, c.candidate_id));
        picker.value = choice.candidate_id;
        picker.addEventListener("change", () => { history.set(view, picker.value); renderViews(); updateButtons(); }); card.append(picker);
        if (choice.image_url) { const img = node("img"); img.src = imageUrl(choice.image_url); img.alt = `${session.name} ${view}`; card.append(img); }
        card.append(node("p", choice.error || choice.review || choice.status.toLowerCase().replaceAll("_", " ")));
        if (choice.refinements.length) { const list = node("ul"); choice.refinements.forEach((text) => list.append(node("li", text))); card.append(list); }
        if (session.selected[view] === choice.candidate_id) { card.classList.add("qc-selected"); card.append(node("p", "Approved")); }
        card.append(actionButton(view === "FRONT" ? "Approve front" : "Approve view", choice.status === "READY" && !choice.stale && choice.revision_id === session.revision_id,
          async () => showSession((await api(`/${session.session_id}/select`, "POST", { revision_id: session.revision_id, candidate_id: choice.candidate_id })).session), true));
        if (choice.status === "REVIEW_FAILED") card.append(actionButton("Retry image review", !choice.stale && choice.revision_id === session.revision_id,
          async () => showSession((await api(`/${session.session_id}/review`, "POST", { revision_id: session.revision_id, candidate_id: choice.candidate_id })).session)));
      }
      const allowed = !session.questions.length && Boolean(session.description) && (view === "FRONT" || Boolean(session.selected.FRONT));
      card.append(actionButton(candidates.length ? "Generate another" : "Generate view", allowed, () => renderView(view)));
      const label = node("label", "Refinement instructions"); const textarea = node("textarea"); textarea.rows = 2; textarea.value = refinements.get(view) || "";
      textarea.setAttribute("aria-label", `${view} refinement`); textarea.addEventListener("input", () => refinements.set(view, textarea.value)); label.append(textarea); card.append(label);
      card.append(actionButton("Refine this view", allowed && Boolean(choice) && !choice.stale && ["READY", "REVIEW_FAILED"].includes(choice.status), () => renderView(view, true, choice.candidate_id)));
      $("qc-views").append(card);
    }
  }
  function showSession(value) {
    const initial = session?.session_id !== value.session_id;
    const changed = session?.revision_id !== value.revision_id;
    session = value;
    $("qc-intake").hidden = true; $("qc-draft").hidden = false;
    if (!dirty || changed) {
      dirty = false;
      $("qc-description").value = session.description;
      $("qc-identity").value = session.identity;
      $("qc-proposed-details").value = session.proposals.join("\n");
      $("qc-approved").checked = session.proposals_approved;
    }
    $("qc-source-images").replaceChildren();
    for (const [index, ref] of session.references.entries()) {
      const card = node("figure", "", "qc-card"); const img = node("img"); img.src = imageUrl(ref.url); img.alt = ref.caption;
      card.append(img, node("figcaption", `${index === 0 ? "Primary identity · " : ""}${ref.caption}`)); $("qc-source-images").append(card);
    }
    for (const [id, items] of [["qc-observations", session.observations], ["qc-proposals", session.proposals]]) {
      $(id).replaceChildren(); (items.length ? items : ["None"]).forEach((text) => $(id).append(node("li", text)));
    }
    $("qc-questions").replaceChildren();
    for (const question of session.questions) {
      const label = node("label", question); const input = node("textarea"); input.value = answers.get(question) || "";
      input.addEventListener("input", () => answers.set(question, input.value)); label.append(input); $("qc-questions").append(label);
    }
    $("qc-answer").hidden = !session.questions.length;
    renderViews();
    $("qc-publication").replaceChildren();
    if (session.publication) {
      $("qc-publication").append(node("p", "Three character views saved to the library."));
      for (const [view, id] of Object.entries(session.publication.asset_ids)) {
        const link = node("a", `Open ${view.replace("_3_4", " 3/4").replaceAll("_", " ").toLowerCase()}`); link.href = "#";
        link.addEventListener("click", (event) => { event.preventDefault(); dialog.close(); bridge.openAsset(id).catch((error) => message(error.message, true)); });
        $("qc-publication").append(link, node("p", session.publication.tags[view]));
      }
      const link = node("a", "Open reference set"); link.href = "#";
      link.addEventListener("click", (event) => { event.preventDefault(); dialog.close(); bridge.openSet(session.publication.set_id); }); $("qc-publication").append(link);
    }
    const latest = session.views.map((view) => session.candidates.filter((c) => c.view === view && !c.stale && c.revision_id === session.revision_id).at(-1));
    const error = terminal() ? "" : session.job.error || latest.find((c) => c?.status === "FAILED")?.error;
    message(error || (session.busy ? "Working… You can close and resume this draft." : session.status.toLowerCase().replaceAll("_", " ")), Boolean(error));
    updateButtons(); clearTimeout(timer);
    if (initial) { $("qc-close").focus({ preventScroll: true }); dialog.scrollTop = 0; }
    if (session.busy && dialog.open) {
      const sid = session.session_id, currentEpoch = epoch;
      timer = setTimeout(async () => {
        try { const response = await api(`/${sid}`); if (epoch === currentEpoch && dialog.open) showSession(response.session); }
        catch (error) { message(error.message + " Close and resume to reconnect.", true); }
      }, 2000);
    }
  }
  for (const id of ["qc-description", "qc-identity", "qc-proposed-details", "qc-approved"]) $(id).addEventListener("input", () => { dirty = true; updateButtons(); });
  $("quick-character-wizard-open").addEventListener("click", () => act(() => open()));
  $("quick-character-wizard-from-asset").addEventListener("click", () => act(() => {
    const asset = bridge.selectedAsset();
    if (!asset) throw new Error("Choose a library image first.");
    return open(asset);
  }));
  async function closeDraft() {
    if (session && dirty && !terminal()) await saveDraft();
    dialog.close();
  }
  $("qc-close").addEventListener("click", () => act(closeDraft));
  dialog.addEventListener("cancel", (event) => { event.preventDefault(); act(closeDraft); });
  dialog.addEventListener("close", () => { epoch++; clearTimeout(timer); });
  $("qc-new").addEventListener("click", () => reset());
  $("qc-resume").addEventListener("click", () => act(async () => {
    const sid = $("qc-sessions").value;
    if (!sid) throw new Error("Choose a saved draft.");
    epoch++; dirty = false; history.clear(); answers.clear(); showSession((await api(`/${sid}`)).session);
  }));
  $("qc-create").addEventListener("click", () => act(async () => {
    const references = slots.flatMap((slot, index) => slot.reference ? [{ ...slot.reference, caption: slot.caption.value.trim(), slotIndex: index }] : []);
    const primary = Number(dialog.querySelector('input[name="qc-primary"]:checked')?.value);
    const primaryIndex = references.findIndex((ref) => ref.slotIndex === primary);
    if (!$("qc-name").value.trim()) throw new Error("Character name is required.");
    if (!references.length) throw new Error("Add at least one reference image.");
    if (references.some((ref) => !ref.caption)) throw new Error("Describe what each reference conveys.");
    if (primaryIndex < 0) throw new Error("Choose a supplied image as primary identity.");
    showSession((await api("", "POST", { name: $("qc-name").value, notes: $("qc-notes").value,
      framing: $("qc-framing").value, side: $("qc-side").value, primary_index: primaryIndex,
      references: references.map(({ slotIndex, ...ref }) => ref) })).session);
    await loadSessions();
  }));
  $("qc-save-draft").addEventListener("click", () => act(saveDraft));
  $("qc-reanalyze").addEventListener("click", () => act(async () => showSession((await api(`/${session.session_id}/generate`, "POST", { revision_id: session.revision_id })).session)));
  $("qc-answer").addEventListener("click", () => act(async () => showSession((await api(`/${session.session_id}/answers`, "POST", {
    revision_id: session.revision_id, answers: session.questions.map((question) => ({ question, answer: answers.get(question) || "" })) })).session)));
  $("qc-accept").addEventListener("click", () => act(async () => {
    showSession((await api(`/${session.session_id}/accept`, "POST", { revision_id: session.revision_id })).session);
    await bridge.refreshLibrary(); await loadSessions();
  }));
  $("qc-abandon").addEventListener("click", () => act(async () => {
    showSession((await api(`/${session.session_id}/abandon`, "POST", { revision_id: session.revision_id })).session);
    await loadSessions();
  }));
})();
