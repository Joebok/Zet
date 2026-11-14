window.mountCharacterWizard = function ({fetchJson, scope, manual, accepted, templateEditor}) {
  const dialog = document.querySelector("#character-wizard");
  const find = (selector) => dialog.querySelector(selector);
  const command = (name) => find(`[data-command="${name}"]`);
  const intake = find("[data-intake]");
  const markdown = find("[data-markdown]");
  const species = find("[data-wizard-species]");
  const status = find("[data-status]");
  const resume = find("[data-resume]");
  const endpoint = "/api/character-wizard";
  const files = new Map();
  const previews = new Map();
  let generation = 0;
  let context, mode, session, model, timer;
  let pending = false;
  const sectionReview = find("[data-section-review]");

  function sectionEdits() {
    const data = {sections: {}, head_sections: {}};
    for (const input of sectionReview.querySelectorAll("[data-draft-field]")) {
      if (input.value === input.dataset.saved) continue;
      const group = input.dataset.draftField;
      if (input.dataset.section) data[group][input.dataset.section] = input.value;
      else data[group] = input.value;
    }
    return data;
  }

  function draftInput(input, field, value, edits, section) {
    input.dataset.draftField = field;
    if (section) input.dataset.section = section;
    input.dataset.saved = value;
    input.value = (section ? edits[field]?.[section] : edits[field]) ?? value;
  }

  function labeledInput(label, input) {
    const wrapper = document.createElement("label");
    wrapper.textContent = label;
    wrapper.append(input);
    return wrapper;
  }

  function sectionButton(label, action, section) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.dataset.command = action;
    button.dataset.section = section;
    return button;
  }

  function renderSections(value, edits) {
    const running = value.status === "RUNNING";
    const applying = value.status === "APPLYING";
    sectionReview.hidden = applying;
    const facts = find("[data-facts]");
    const directions = Object.fromEntries([...facts.querySelectorAll("[data-section-direction]")]
      .map(input => [input.dataset.sectionDirection, input.value]));
    facts.replaceChildren();
    for (const [name, entry] of Object.entries(value.sections)) {
      const panel = document.createElement("fieldset");
      panel.dataset.fact = name;
      const legend = document.createElement("legend");
      legend.textContent = entry.label;
      const state = document.createElement("p");
      state.dataset.factStatus = "";
      state.textContent = entry.blocked ? "Edit this section in Template Editor." : stateLabel(entry.status);
      panel.append(legend, state);
      if (entry.selected) {
        const input = document.createElement("textarea");
        input.rows = 5;
        draftInput(input, "sections", entry.text, edits, name);
        panel.append(labeledInput(entry.label + " facts", input));
        if (entry.notice) {
          const notice = document.createElement("p");
          notice.textContent = entry.notice;
          panel.append(notice);
        }
        if (entry.proposal !== null) {
          const proposal = document.createElement("textarea");
          proposal.readOnly = true;
          proposal.rows = 4;
          proposal.value = entry.proposal;
          panel.append(labeledInput("Proposed replacement", proposal),
            sectionButton("Apply replacement", "apply-proposal", name),
            sectionButton("Dismiss replacement", "dismiss-proposal", name));
        }
        const direction = document.createElement("input");
        direction.dataset.sectionDirection = name;
        direction.value = directions[name] || "";
        const refine = sectionButton("Refine section", "refine", name);
        refine.disabled = running;
        panel.append(labeledInput("Refinement direction", direction), refine);
        if (entry.status === "ATTENTION") {
          const retry = sectionButton("Retry section", "retry-section", name);
          retry.disabled = running;
          panel.append(retry);
        }
      }
      facts.append(panel);
    }
    command("template-editor").hidden = !value.template_path;
    const select = find("[data-section-species]");
    select.replaceChildren(new Option("Choose Species", ""),
      ...value.species.sort((a, b) => a.label.localeCompare(b.label)).map(item => new Option(item.label, item.id)));
    draftInput(select, "species_id", value.species_id, edits);
    const gender = find("[data-gender]");
    draftInput(gender, "gender", value.gender, edits);
    gender.disabled = !value.gender_editable;
    find("[data-head-starter]").hidden = value.mode !== "create";
    find("[data-head-sections]").replaceChildren(...Object.entries(value.head_sections).map(([name, entry]) => {
      const input = document.createElement("textarea");
      input.rows = 4;
      draftInput(input, "head_sections", entry.text, edits, name);
      return labeledInput(entry.label, input);
    }));
    command("preview").disabled = running;
    const preview = value.preview_ready || applying;
    find("[data-review]").hidden = !preview;
    markdown.readOnly = true;
    markdown.value = value.markdown;
    find("[data-errors]").textContent = value.errors.join("\n");
    for (const name of ["answer", "retry", "save", "revise"]) command(name).hidden = true;
    command("accept").hidden = !preview;
    command("abandon").hidden = applying;
    command("accept").textContent = value.mode === "create" ? "Create character" : "Update Character.md";
    species.closest("label").hidden = true;
    find("[data-direction]").closest("label").hidden = true;
    showDraftActions();
  }

  function stateLabel(state) {
    return ({WAITING: "Waiting", QUEUED: "Queued", RUNNING: "Running", READY: "Ready",
      ATTENTION: "Needs attention", SKIPPED: "Skipped"})[state] || "";
  }

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
    if (session?.version === 2) {
      const edits = sectionEdits();
      const dirty = Object.entries(edits).some(([key, value]) =>
        ["sections", "head_sections"].includes(key) ? Object.keys(value).length : true);
      command("accept").disabled = pending || dirty || Boolean(session.errors.length);
      return;
    }
    const changed = session && markdown.value !== session.markdown;
    command("save").disabled = !changed && !session?.errors.length;
    command("revise").disabled = changed;
    command("accept").disabled = changed || Boolean(session?.errors.length);
  }

  function render(value, edits = {}) {
    session = value;
    intake.hidden = true;
    find("[data-session]").hidden = false;
    find("[data-resume-label]").hidden = true;
    const running = value.status === "RUNNING";
    const draft = value.status === "DRAFT";
    const questions = value.status === "QUESTIONS";
    dialog.querySelector("h2").textContent = `Character Wizard · ${value.character} / ${value.phase}`;
    find("[data-style]").textContent = [value.style && `Universe style: ${value.style}`, value.model].filter(Boolean).join(" · ");
    notice(value.error || (value.version === 2 && value.status === "RUNNING" ? "Interview in progress." : ({
      RUNNING: "Waiting for the interview…", QUESTIONS: "Answer the questions to continue.",
      DRAFT: "Review Character.md before accepting.", APPLYING: "Resume saving the approved draft.",
    }[value.status] || "")), Boolean(value.error));
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
    sectionReview.hidden = true;
    species.closest("label").hidden = false;
    find("[data-direction]").closest("label").hidden = false;
    markdown.readOnly = false;
    find("[data-review]").hidden = !draft;
    markdown.value = value.markdown;
    species.replaceChildren(new Option("Choose Species", ""), ...(value.species || [])
      .sort((a, b) => a.label.localeCompare(b.label)).map(item => new Option(item.label, item.id)));
    species.value = value.species_id || "";
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
    if (value.version === 2) renderSections(value, edits);
    else showDraftActions();
    if (running) poll(value.id, generation);
  }

  const speciesField = /^(Species|Species \/ Ancestry|Character Race|Race|Ancestry):[^\r\n]*/gim;
  species.addEventListener("change", () => {
    const line = "Species: `" + species.value + "`";
    let written = false;
    const end = markdown.value.search(/^\s*<!--\s*ZET:BEGIN\b/im);
    const header = end < 0 ? markdown.value : markdown.value.slice(0, end);
    const updated = header.replace(speciesField, () => {
      if (written) return "";
      written = true;
      return line;
    });
    markdown.value = (written ? updated : line + "\n" + updated) + markdown.value.slice(header.length);
    showDraftActions();
  });

  function poll(id, token) {
    clearTimeout(timer);
    if (document.hidden) return;
    timer = setTimeout(async () => {
      if (!current(token)) return;
      try {
        const progress = await fetchJson(`${endpoint}/${id}/progress`);
        if (!current(token)) return;
        if (pending) return poll(id, token);
        if (progress.status === "RUNNING" && progress.revision === session.revision) {
          for (const [name, state] of Object.entries(progress.section_states || {})) {
            if (!session.sections[name].blocked) find(`[data-fact="${name}"] [data-fact-status]`).textContent = stateLabel(state);
          }
          poll(id, token);
        } else {
          const value = await fetchJson(`${endpoint}/${id}`);
          if (current(token) && !pending) render(value, sectionEdits());
          else if (current(token)) poll(id, token);
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
    find("[data-facts]").replaceChildren();
    intake.reset();
    find("[data-section-choice]").hidden = mode !== "edit";
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
      const metadata = find("[data-intake-metadata]");
      metadata.hidden = metadata.disabled = mode !== "create";
      if (mode === "create") {
        intake.elements.species_id.replaceChildren(new Option("Choose Species", ""),
          ...options.species.sort((a, b) => a.label.localeCompare(b.label)).map(item => new Option(item.label, item.id)));
        intake.elements.gender.replaceChildren(new Option("Choose Gender Presentation", ""),
          ...options.gender_options.map(value => new Option(value, value)));
      }
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
    if (mode === "edit") form.set("sections", [...find("[data-section-choice]")
      .querySelectorAll("input:checked")].map(input => input.value).join(","));
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
  sectionReview.addEventListener("input", showDraftActions);
  async function sectionAction(name, button, token) {
    if (pending) return;
    const section = button.dataset.section;
    const edits = sectionEdits();
    const data = {revision: session.revision};
    let action = name;
    if (name === "retry-section" || name === "refine") {
      action = name === "refine" ? name : "retry";
      data.section = section;
      data.text = edits.sections[section] ?? session.sections[section].text;
      data.direction = find(`[data-section-direction="${section}"]`).value;
    } else if (name === "apply-proposal" || name === "dismiss-proposal") {
      action = "save-sections";
      data.dismiss = [section];
      if (name === "apply-proposal") data.sections = {[section]: session.sections[section].proposal};
    } else if (name === "save-sections" || name === "preview") {
      Object.assign(data, edits);
    }
    pending = true;
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
      else {
        const remaining = sectionEdits();
        for (const group of ["sections", "head_sections"]) {
          for (const [key, saved] of Object.entries(data[group] || {})) {
            if (edits[group][key] === remaining[group][key] || remaining[group][key] === saved) delete remaining[group][key];
          }
        }
        for (const field of ["species_id", "gender"]) {
          if (Object.hasOwn(data, field) && remaining[field] === data[field]) delete remaining[field];
        }
        render(value, remaining);
      }
    } catch (error) {
      if (current(token)) notice(error.message, true);
    } finally {
      pending = false;
      if (current(token)) {
        button.disabled = false;
        showDraftActions();
      }
    }
  }

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
      const value = await window.ZetModelPicker.open({value: model, required: ["vision"]});
      if (current(token) && value) command("model").textContent = model = value;
      return;
    }
    if (session?.version === 2) {
      if (name === "template-editor") {
        dialog.close();
        return templateEditor(session.template_path);
      }
      return sectionAction(name, event.target.closest("[data-command]"), token);
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
