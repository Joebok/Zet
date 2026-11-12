window.mountCharacterWizard = function ({fetchJson, scope, manual, accepted}) {
  const dialog = document.querySelector("#character-wizard");
  const find = (selector) => dialog.querySelector(selector);
  const command = (name) => find(`[data-command="${name}"]`);
  const intake = find("[data-intake]");
  const markdown = find("[data-markdown]");
  const status = find("[data-status]");
  const resume = find("[data-resume]");
  const endpoint = "/api/character-wizard";
  const files = new Map();
  const previews = new Map();
  let generation = 0;
  let context, mode, session, model, timer;

  function current(token) {
    return dialog.open && generation === token && scope().universe === context.universe;
  }

  function notice(message, error = false) {
    status.textContent = message;
    status.classList.toggle("error", error);
  }

  function preview(slot, file) {
    if (previews.has(slot)) URL.revokeObjectURL(previews.get(slot));
    previews.delete(slot);
    files.delete(slot);
    const image = find(`[data-preview="${slot}"]`);
    image.removeAttribute("src");
    image.hidden = !file;
    find(`[data-clear-reference="${slot}"]`).hidden = !file;
    if (!file) return;
    const url = URL.createObjectURL(file);
    files.set(slot, file);
    previews.set(slot, url);
    image.src = url;
  }

  function showDraftActions() {
    const changed = session && markdown.value !== session.markdown;
    command("save").disabled = !changed;
    command("revise").disabled = changed;
    command("accept").disabled = changed || Boolean(session?.errors.length);
  }

  function render(value) {
    session = value;
    intake.hidden = true;
    find("[data-session]").hidden = false;
    find("[data-resume-label]").hidden = true;
    const running = value.status === "RUNNING";
    const draft = value.status === "DRAFT";
    const questions = value.status === "QUESTIONS";
    dialog.querySelector("h2").textContent = `Character Wizard · ${value.character} / ${value.phase}`;
    find("[data-style]").textContent = [value.style && `Universe style: ${value.style}`, value.model].filter(Boolean).join(" · ");
    notice(value.error || ({
      RUNNING: "Waiting for the interview…", QUESTIONS: "Answer the questions to continue.",
      DRAFT: "Review Character.md before accepting.", APPLYING: "Resume saving the approved draft.",
    }[value.status] || ""), Boolean(value.error));
    const imageRow = find("[data-images]");
    imageRow.replaceChildren();
    for (const item of value.images) {
      const image = document.createElement("img");
      image.className = "costume-wizard-preview";
      image.alt = item.caption || `Reference ${item.slot}`;
      image.src = `${endpoint}/${value.id}/images/${item.slot}?universe_id=${encodeURIComponent(context.universe)}`;
      imageRow.append(image);
    }
    const history = find("[data-history]");
    history.replaceChildren();
    if (value.history.length) {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = "Interview history";
      details.append(summary);
      for (const turn of value.history) {
        const entry = document.createElement("p");
        entry.textContent = Array.isArray(turn) ? turn.map(([q, a]) => `${q}\n${a}`).join("\n\n") : turn;
        entry.style.whiteSpace = "pre-wrap";
        details.append(entry);
      }
      history.append(details);
    }
    const inputs = find("[data-questions]");
    inputs.replaceChildren();
    if (questions) for (const question of value.questions) {
      const label = document.createElement("label");
      label.textContent = question;
      label.append(document.createElement("textarea"));
      inputs.append(label);
    }
    find("[data-review]").hidden = !draft;
    markdown.value = value.markdown;
    find("[data-direction]").value = "";
    find("[data-errors]").textContent = value.errors.join("\n");
    find("[data-diff-panel]").hidden = value.mode !== "edit";
    find("[data-diff]").textContent = (value.diff || []).flatMap((row) => {
      if (row.kind === "gap") return ["…"];
      if (row.kind === "equal") return [`  ${row.master_text}`];
      return [row.master_line && `- ${row.master_text}`, row.proposed_line && `+ ${row.proposed_text}`].filter(Boolean);
    }).join("\n") || "No changes from the saved template.";
    for (const [name, visible] of Object.entries({
      answer: questions, retry: value.status === "FAILED", save: draft, revise: draft,
      accept: draft || value.status === "APPLYING", abandon: value.status !== "APPLYING",
    })) command(name).hidden = !visible;
    command("accept").textContent = value.mode === "create" ? "Create character" : "Update Character.md";
    showDraftActions();
    if (running) poll(value.id, generation);
  }

  function poll(id, token) {
    clearTimeout(timer);
    if (document.hidden) return;
    timer = setTimeout(async () => {
      if (!current(token)) return;
      try {
        const progress = await fetchJson(`${endpoint}/${id}/progress`);
        if (!current(token)) return;
        if (progress.status === "RUNNING") poll(id, token);
        else {
          const value = await fetchJson(`${endpoint}/${id}`);
          if (current(token)) render(value);
        }
      } catch (error) {
        if (current(token)) {
          notice(error.message, true);
          poll(id, token);
        }
      }
    }, 1800);
  }

  async function open(nextMode) {
    const token = ++generation;
    mode = nextMode;
    context = scope();
    session = null;
    intake.reset();
    for (let slot = 1; slot <= 3; slot++) preview(slot, null);
    intake.elements.character.value = mode === "edit" ? context.character : "";
    intake.elements.phase.value = mode === "edit" ? context.phase : "Adult";
    intake.elements.character.readOnly = intake.elements.phase.readOnly = mode === "edit";
    command("manual").hidden = mode !== "create";
    dialog.querySelector("h2").textContent = "Character Wizard";
    find("[data-style]").textContent = "";
    find("[data-session]").hidden = true;
    find("[data-resume-label]").hidden = true;
    intake.hidden = true;
    notice("Loading Character Wizard…");
    if (!dialog.open) dialog.showModal();
    try {
      const query = new URLSearchParams({mode, character: context.character, phase: context.phase});
      const options = await fetchJson(`${endpoint}?${query}`);
      if (!current(token)) return;
      model = options.model;
      command("model").textContent = model;
      find("[data-fallback]").hidden = mode !== "create" || Boolean(options.style);
      find("[data-style]").textContent = options.style ? `Universe style: ${options.style}` : "";
      resume.replaceChildren(new Option("Start a new interview", ""), ...options.sessions.map(
        (item) => new Option(`${item.character} / ${item.phase} · ${item.status}`, item.id)));
      find("[data-resume-label]").hidden = !options.sessions.length;
      intake.hidden = false;
      notice(mode === "create" ? "Add one to three reference images." : "You can add up to three reference images.");
    } catch (error) {
      if (current(token)) notice(error.message, true);
    }
  }

  resume.addEventListener("change", async () => {
    if (!resume.value) return;
    const token = generation;
    try {
      const value = await fetchJson(`${endpoint}/${resume.value}`);
      if (current(token)) render(value);
    } catch (error) {
      if (current(token)) notice(error.message, true);
    }
  });

  for (let slot = 1; slot <= 3; slot++) {
    const input = intake.elements[`image${slot}`];
    input.addEventListener("change", () => preview(slot, input.files[0]));
    find(`[data-clear-reference="${slot}"]`).addEventListener("click", () => {
      input.value = "";
      preview(slot, null);
    });
    const paste = find(`[data-paste="${slot}"]`);
    paste.addEventListener("click", () => notice("Press Ctrl+V to paste an image into this slot."));
    paste.addEventListener("paste", (event) => {
      const image = [...event.clipboardData.files].find((file) => file.type.startsWith("image/"));
      if (image) {
        event.preventDefault();
        input.value = "";
        preview(slot, image);
        notice(`Image pasted into reference ${slot}.`);
      }
    });
  }

  intake.addEventListener("submit", async (event) => {
    event.preventDefault();
    const token = generation;
    if (mode === "create" && !files.size) return notice("Add at least one reference image.", true);
    const form = new FormData(intake);
    for (let slot = 1; slot <= 3; slot++) {
      form.delete(`image${slot}`);
      if (files.has(slot)) form.set(`image${slot}`, files.get(slot));
    }
    form.set("mode", mode);
    form.set("model", model);
    event.submitter.disabled = true;
    try {
      const value = await fetchJson(endpoint, {method: "POST", body: form});
      if (current(token)) render(value);
    } catch (error) {
      if (current(token)) notice(error.message, true);
    } finally {
      event.submitter.disabled = false;
    }
  });

  markdown.addEventListener("input", showDraftActions);
  dialog.addEventListener("click", async (event) => {
    const name = event.target.closest("[data-command]")?.dataset.command;
    if (!name) return;
    if (name === "close") return dialog.close();
    if (name === "manual") {
      dialog.close();
      return manual();
    }
    const token = generation;
    if (name === "model") {
      const value = await window.ZetModelPicker.open({value: model, required: ["vision", "structured_json"]});
      if (current(token) && value) command("model").textContent = model = value;
      return;
    }
    const action = ["answer", "revise"].includes(name) ? "continue" : name;
    const data = {revision: session.revision};
    if (name === "answer") data.answers = [...find("[data-questions]").querySelectorAll("textarea")].map((input) => input.value);
    if (name === "revise") data.direction = find("[data-direction]").value;
    if (name === "save") data.markdown = markdown.value;
    const button = command(name);
    button.disabled = true;
    try {
      const value = await fetchJson(`${endpoint}/${session.id}/${action}`, {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data),
      });
      if (!current(token)) return;
      if (value.status === "ACCEPTED") {
        dialog.close();
        await accepted(value);
      } else if (value.status === "ABANDONED") await open(mode);
      else render(value);
    } catch (error) {
      if (current(token)) notice(error.message, true);
    } finally {
      button.disabled = false;
      if (current(token) && session) showDraftActions();
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (dialog.open && session?.status === "RUNNING") poll(session.id, generation);
  });
  dialog.addEventListener("close", () => {
    if (dialog.open) return;
    generation++;
    clearTimeout(timer);
    for (let slot = 1; slot <= 3; slot++) preview(slot, null);
  });
  return {open, close: () => dialog.close()};
};
