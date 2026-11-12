window.mountSpeciesSettings = function () {
  const panel = document.querySelector("#species-settings");
  const find = selector => panel.querySelector(selector);
  const form = find("[data-species-form]");
  const list = find("[data-species-list]");
  const edit = find("[data-species-edit]");
  const add = find("[data-species-add]");
  const reload = find("[data-species-reload]");
  const status = find("[data-species-status]");
  let universe, catalog, create, generation = 0;

  async function request(method, body) {
    const response = await fetch("/api/species?universe_id=" + encodeURIComponent(universe), {
      method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) {
      const detail = payload.detail;
      const error = new Error(detail?.message || detail || "Species request failed.");
      error.field = detail?.field;
      throw error;
    }
    return payload;
  }

  function showCatalog(value, selected) {
    catalog = value;
    list.replaceChildren(...Object.entries(value.species)
      .sort(([, a], [, b]) => a.label.localeCompare(b.label))
      .map(([id, entry]) => new Option(entry.label, id)));
    if (selected && Object.hasOwn(value.species, selected)) list.value = selected;
    edit.disabled = !list.value;
    add.disabled = false;
  }

  function showForm(id) {
    create = !id;
    const entry = catalog.species[id];
    const rules = entry?.body_reference;
    for (const error of panel.querySelectorAll("[data-species-error]")) error.textContent = "";
    form.elements.id.value = id || "";
    form.elements.id.readOnly = !create;
    form.elements.label.value = entry?.label || "";
    form.elements.aliases.value = (entry?.aliases || []).join("\n");
    form.elements.positive.value = (rules?.positive || []).join("\n");
    form.elements.negative.value = (rules?.negative || []).join("\n");
    find("[data-species-views]").replaceChildren(...catalog.views.map(view => {
      const label = document.createElement("label");
      label.textContent = view.replaceAll("_", " ");
      const input = document.createElement("textarea");
      input.dataset.view = view;
      input.rows = 2;
      input.value = (rules?.view_instructions[view] || []).join("\n");
      label.append(input);
      return label;
    }));
    form.hidden = false;
    (create ? form.elements.id : form.elements.label).focus();
  }

  async function load(keepDraft = false) {
    const token = ++generation;
    edit.disabled = add.disabled = reload.disabled = true;
    if (!keepDraft) form.hidden = true;
    status.textContent = "Loading Species…";
    try {
      const result = await request("GET");
      if (token !== generation) return;
      showCatalog(result, list.value);
      status.textContent = keepDraft && !form.hidden
        ? "Catalog reloaded. Check your unsaved changes before saving." : "";
    } catch (error) {
      if (token === generation) status.textContent = error.message;
    } finally {
      if (token === generation) reload.disabled = false;
    }
  }

  edit.onclick = () => showForm(list.value);
  add.onclick = () => showForm("");
  reload.onclick = () => load(true);
  find("[data-species-cancel]").onclick = () => { form.hidden = true; };
  form.onsubmit = async event => {
    event.preventDefault();
    const token = generation;
    const submit = event.submitter || form.querySelector("[type=submit]");
    const fields = form.elements;
    const lines = input => input.value.split("\n").map(line => line.trim()).filter(Boolean);
    const id = fields.id.value.trim();
    for (const error of panel.querySelectorAll("[data-species-error]")) error.textContent = "";
    const viewInstructions = {};
    for (const input of form.querySelectorAll("[data-view]")) {
      const guidance = lines(input);
      if (guidance.length) viewInstructions[input.dataset.view] = guidance;
    }
    submit.disabled = true;
    edit.disabled = add.disabled = reload.disabled = true;
    try {
      const result = await request("PUT", {revision: catalog.revision, id, create, entry: {
        label: fields.label.value.trim(), aliases: lines(fields.aliases), body_reference: {
          positive: lines(fields.positive), negative: lines(fields.negative), view_instructions: viewInstructions,
        },
      }});
      if (token !== generation) return;
      showCatalog({...result, views: catalog.views}, id);
      form.hidden = true;
      status.textContent = "Species saved.";
    } catch (error) {
      if (token !== generation) return;
      const field = [...panel.querySelectorAll("[data-species-error]")]
        .find(element => element.dataset.speciesError === error.field);
      if (field) field.textContent = error.message;
      if (field?.closest("details")) field.closest("details").open = true;
      status.textContent = field ? "Check the highlighted field." : error.message;
    } finally {
      submit.disabled = false;
      if (token === generation) edit.disabled = add.disabled = reload.disabled = false;
    }
  };

  return id => {
    universe = id;
    return load();
  };
};
