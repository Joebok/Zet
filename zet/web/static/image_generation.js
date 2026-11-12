import {mountCandidateBoard, confirmCandidateDeletion} from "./candidate_board_component.js?v=20261111-generation-controls";

const api = "/api/image-generation";
const assets = api + "/assets";
const active = status => ["QUEUED", "RUNNING", "DISPATCHING"].includes(status);
const candidateId = item => item && item.requestId + ":" + item.index;
const post = (request, url, payload) => request(url, {
  method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload),
});

export function createAsset(request, name, inputs = {}, recoveryId) {
  return post(request, assets, {name, inputs, recovery_id:recoveryId});
}

export function readImage(file) {
  if (!file || file.size > 20 * 1024 * 1024) throw new Error("Choose an image of 20 MiB or smaller.");
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function legacyInputs(universe) {
  try {
    return JSON.parse(localStorage.getItem("zet:image-generation:" + universe)
      || localStorage.getItem("zet:image-generation") || "null");
  } catch { return null; }
}

async function recoverReferences(universe, legacy) {
  if (!indexedDB.databases || !(await indexedDB.databases()).some(db => db.name === "zet-image-generation")) return [];
  const db = await new Promise((resolve, reject) => {
    const opening = indexedDB.open("zet-image-generation", 1);
    opening.onsuccess = () => resolve(opening.result);
    opening.onerror = () => reject(opening.error);
  });
  try {
    const store = db.transaction("state").objectStore("state");
    const get = key => new Promise((resolve, reject) => {
      const request = store.get(key);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    const data = await Promise.all([...Array(10)].map((_, i) => get(universe + ":reference-" + i))
      .concat(get(universe + ":reference")));
    return data.slice(0, 10).map((image, i) => ({
      image:image || (i === 0 ? data[10] : "") || "",
      label:legacy.referenceLabels?.[i] || (i === 0 ? legacy.referenceName : "") || "",
      metadata:legacy.referenceMetadata?.[i] || {},
    }));
  } finally { db.close(); }
}

export function setup({fetchJson, universe, style, confirmProtectedEffects, openGeneratedInventory, pickImage, fileUrl}) {
  const root = document.querySelector("#image-generation-page");
  const el = key => root.querySelector("[data-ig-" + key + "]");
  let data, model, component, scope = 0, owner, timer, saveTimer, saving, dirty = false;
  let reviewed, analysis, report, busy = false, options;
  const status = message => { el("status").textContent = message; };
  const endpoint = (operation = "") => assets + "/" + data.asset_id + (operation ? "/" + operation : "");
  const imageUrl = url => url + (url.includes("?") ? "&" : "?") + "universe_id=" + encodeURIComponent(owner);
  const live = token => token === scope && owner === universe();
  const selection = () => data?.slots[data.selected_slot];
  const author = () => data.authoring;
  const refinement = () => data.refinement;

  function url(assetId) {
    const params = new URLSearchParams({page:"image-generation", universe_id:universe()});
    if (assetId) params.set("generation_asset", assetId);
    return "/?" + params;
  }

  function result(index) {
    const assignment = data?.slots[index];
    if (!assignment) return null;
    const job = data.jobs.find(item => item.request_id === assignment.requestId);
    const image = job?.images.find(item => item.index === assignment.index);
    return {assignment, job, image:image && {...image, url:imageUrl(image.url)},
      child:job?.results.find(item => item.index === assignment.index)};
  }

  function render() {
    if (!data) return;
    el("title").textContent = " - " + data.name;
    el("references").hidden = data.inputs.mode !== "img2img";
    const input = data.inputs;
    const selected = result(data.selected_slot);
    const readiness = !input.prompt?.trim() ? "Enter a prompt."
      : input.mode === "img2img" && !input.reference_images?.some(ref => ref.image) ? "Add a reference image."
      : input.mode === "img2img" && input.reference_images?.some(ref => ref.image && !ref.label?.trim()) ? "Label each reference image." : "";
    const field = (key, label, type, choices) => ({
      key, label, type, value:input[key] ?? ({mode:"txt2img", aspect_ratio:"1:1", universe_style_variant:"canonical"}[key] || ""),
      options:choices?.map(([value, label]) => ({value, label})),
    });
    model = {
      scope:{key:owner + ":" + data.asset_id, title:data.name}, revision:data.revision,
      selectedId:candidateId(selection()),
      renderControls:{
        promptFields:[field("prompt", "Prompt", "textarea"), field("negative_prompt", "Negative prompt", "textarea")],
        fields:[field("mode", "Generation mode", "radio", [["txt2img", "Text to image"], ["img2img", "Image to image"]]),
          field("aspect_ratio", "Aspect ratio", "text"),
          field("universe_style_variant", "Universe style", "select", [["canonical", "Canonical"], ["environmental", "Environmental"]])],
        readiness:{draft:readiness, final:readiness}, renderStatus:data.busy ? "Renders in progress" : "",
      },
      actions:[
        {key:"style", label:"Add Universe art style", group:"prompt"},
        {key:"reconstruct", label:"Reconstruct selected image in universe style", group:"prompt",
          disabledReason:selected?.image ? "" : "Select a completed candidate."},
        {key:"compare", label:"Compare selected reconstruction", group:"prompt",
          disabledReason:selected?.job?.reconstruction?.target_hash ? "" : "Select a reconstructed image."},
        {key:"references", label:"Manage reference images", placement:["settings"], disabledReason:input.mode === "img2img" ? "" : "Choose Image to image."},
      ],
      slots:data.slots.map((item, index) => {
        const entry = result(index);
        const key = index + 1;
        if (!entry) return {key};
        const {job, child, image} = entry;
        const upscale = data.upscales?.[index];
        const state = image ? "COMPLETE" : child?.status || job?.status || "FAILED";
        const running = Boolean(upscale?.request_id) || active(state);
        const selected = index === data.selected_slot;
        const descriptor = image && {url:image.url, label:"Candidate in slot " + key};
        const settings = job?.render_sizing;
        return {key, renderActive:running, candidate:{
          id:candidateId(item), quality:item.quality, status:state, error:upscale?.error || child?.error || job?.error,
          notices:upscale?.request_id ? ["Upscaling Draft to Final."] : [],
          thumbnail:descriptor, image:descriptor, prompt:job?.prompt, negativePrompt:job?.negative_prompt,
          inputs:(job?.reference_labels || []).map((label, i) => ({label, url:imageUrl(
            api + "/jobs/" + item.requestId + "/references/" + i)})),
          renderSettings:settings ? [{label:"Dimensions", value:settings.width + " × " + settings.height}] : [],
        }, actions:[
          ...(image || selected ? [{key:selected ? "unselect" : "select"}] : []),
          ...(image ? [{key:"inventory-add", label:"Add to Image Inventory"},
            ...(job.source_asset_id ? [{key:"inventory-update", label:"Update Image Inventory"}] : []),
            {key:"capture", label:"Create task", placement:["review"]}] : []),
          ...(!image && !running && job?.retryable ? [{key:"retry"}] : []),
          {key:"clear", disabledReason:running ? "Wait for the render to finish." : selected ? "Deselect this candidate first." : ""},
        ]};
      }),
    };
    if (component) component.update(model);
    else component = mountCandidateBoard({boardHost:el("board"), dialogHost:el("dialog")}, model, {
      onAction, onEdit:({field, value}) => {
        data.inputs[field] = value;
        if (field === "mode") delete data.inputs.render_config;
        if (field === "universe_style_variant") delete data.inputs.universe_style;
        markDirty();
        render();
      },
      onEvent:({type, candidateId}) => {
        if (type === "review-close") reviewed = null;
        else if (type === "review-open" || type === "candidate-change") reviewed = candidateId;
      },
    });
    renderAuthoring();
    renderRefinement();
    schedulePoll();
  }

  function showPanel(key) {
    const panel = el(key);
    panel.open = true;
    panel.scrollIntoView({block:"nearest"});
  }

  function markDirty() {
    dirty = true;
    status("Unsaved changes");
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveWhenIdle, 450);
  }

  function saveWhenIdle() {
    if (busy) saveTimer = setTimeout(saveWhenIdle, 450);
    else void flush();
  }

  async function flush() {
    clearTimeout(saveTimer);
    if (saving) {
      if (!await saving) return false;
      return flush();
    }
    if (!dirty || !data) return true;
    if (owner !== universe()) return false;
    dirty = false;
    const token = scope;
    const payload = {expected_revision:data.revision, inputs:data.inputs,
      authoring:data.authoring, refinement:data.refinement};
    saving = post(fetchJson, endpoint("save"), payload).then(next => {
      if (live(token)) {
        if (dirty) next = {...next, inputs:data.inputs, authoring:data.authoring, refinement:data.refinement};
        data = next;
        status(dirty ? "Unsaved changes" : "Saved to library");
        render();
      }
      return true;
    }).catch(error => {
      if (live(token)) { dirty = true; status(error.message + " Your edits are still in the editor."); }
      return false;
    }).finally(() => { saving = null; });
    return saving;
  }

  function leave() {
    scope += 1;
    clearTimeout(timer);
    clearTimeout(saveTimer);
    component?.dispose();
    component = data = analysis = report = reviewed = null;
    options = null;
    busy = dirty = false;
  }

  function link(name, assetId, anchor = document.createElement("a")) {
    anchor.href = url(assetId);
    anchor.textContent = name;
    anchor.onclick = event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      void enter(assetId, true);
    };
    return anchor;
  }

  async function enter(assetId, navigate = false) {
    if (!await flush()) return;
    leave();
    owner = universe();
    link("Image Generation", null, el("back"));
    el("title").textContent = "";
    const token = scope;
    if (navigate) history.pushState({}, "", url(assetId));
    else if (assetId || new URLSearchParams(location.search).has("generation_asset")) history.replaceState({}, "", url(assetId));
    el("gallery").hidden = Boolean(assetId);
    el("asset").hidden = !assetId;
    status("");
    try {
      if (assetId) {
        const next = await fetchJson(assets + "/" + encodeURIComponent(assetId));
        if (!live(token)) return;
        data = next;
        el("authoring").open = false;
        el("true-up").open = false;
        el("references").open = false;
        renderReferences();
        render();
        await refreshAdvisory(token);
      } else {
        el("cards").replaceChildren();
        el("assets").replaceChildren();
        const {assets:records} = await fetchJson(assets);
        if (!live(token)) return;
        for (const item of records) {
          const row = document.createElement("li");
          row.append(link(item.name, item.asset_id));
          el("assets").append(row);
          if (!item.selected) continue;
          const card = link(item.name, item.asset_id);
          const image = document.createElement("img");
          image.alt = "";
          image.loading = "lazy";
          image.src = imageUrl(api + "/jobs/" + item.selected.requestId + "/images/" + item.selected.index);
          card.prepend(image);
          el("cards").append(card);
        }
        el("recover").hidden = !legacyInputs(owner);
      }
    } catch (error) { if (live(token)) status(error.message); }
  }

  async function update(operation, payload, token = scope) {
    const next = await post(fetchJson, endpoint(operation), {...payload, expected_revision:data.revision});
    if (live(token)) {
      if (dirty) Object.assign(next, {inputs:data.inputs, authoring:data.authoring, refinement:data.refinement});
      data = next;
      render();
    }
  }

  async function deleteItems(key) {
    const token = scope;
    const preview = await post(fetchJson, endpoint(key + "-preview"), {});
    if (!live(token)) return false;
    const effects = preview.effects.map(effect => ({...effect, preview_url:imageUrl(effect.image_url)}));
    const approved = key === "delete-asset"
      ? await confirmProtectedEffects("Delete asset?", data.name + " will be removed. Inventory copies are retained.", effects,
        "Delete asset", {individual:true})
      : await confirmCandidateDeletion(key, data.name, preview.slots, preview.active_slots, effects);
    if (approved === null || !live(token)) return false;
    if (key === "delete-asset") {
      await post(fetchJson, endpoint(key), {preview, approved, expected_revision:preview.revision});
      if (live(token)) await enter(null, true);
    } else await update(key, {preview, approved}, token);
    return true;
  }

  async function onAction(intent) {
    if (busy || !data) return {status:"cancelled"};
    const token = scope;
    const entry = result(Number(intent.slotKey) - 1);
    const expected = entry?.assignment || null;
    const slot = intent.slotKey ? {slot:Number(intent.slotKey), expected_assignment:expected} : {};
    if (intent.expectedOccupant !== undefined && intent.expectedOccupant !== candidateId(expected)) return {status:"cancelled"};
    if (intent.key === "inventory-add") {
      openGeneratedInventory(entry, {url:endpoint(intent.key) + "?universe_id=" + encodeURIComponent(owner), payload:slot});
      return {status:"cancelled"};
    }
    if (intent.key === "capture") {
      void window.ZetTaskCapture.open();
      return {status:"cancelled"};
    }
    if (intent.key === "references") { showPanel("references"); return {status:"cancelled"}; }
    busy = true;
    try {
      if (intent.key === "style") {
        const text = style(data.inputs.universe_style_variant);
        if (!text?.trim()) throw new Error("The universe has no style for this variant.");
        const old = data.inputs.managed_style || "";
        const prompt = data.inputs.prompt || "";
        const prefix = text.trim() + "\n\n";
        data.inputs.prompt = prefix + (old && prompt.startsWith(old) ? prompt.slice(old.length) : prompt);
        data.inputs.managed_style = prefix;
        markDirty();
        render();
        return {status:"success", message:"Universe style added."};
      }
      if (!await flush() || !live(token)) return {status:"cancelled"};
      if (intent.key === "reconstruct") {
        author().source = {selected_result:selection(), label:"Selected candidate"};
        markDirty();
        showPanel("authoring");
        await analyze();
        return {status:"success", message:"Reconstruction analysis started."};
      }
      if (intent.key === "compare") {
        const expectedSelection = selection();
        const started = await post(fetchJson, endpoint("compare"), {selected_result:expectedSelection});
        if (!live(token)) return {status:"cancelled"};
        Object.assign(refinement(), {report_id:started.id, task_id:started.task_id, selected_id:candidateId(expectedSelection), item_ids:[]});
        report = started;
        markDirty();
        showPanel("true-up");
        render();
        return {status:"success", message:"Comparison started."};
      }
      if (intent.key === "inventory-update") {
        if (await confirmProtectedEffects("Update Image Inventory?", "Replace the original Inventory image with this candidate.", [], "Update")) {
          await post(fetchJson, endpoint(intent.key), slot);
          return {status:"success", message:"Inventory image updated."};
        }
        return {status:"cancelled"};
      }
      if (intent.key.startsWith("delete-")) return {status:await deleteItems(intent.key) ? "success" : "cancelled"};
      const operation = intent.key.startsWith("render-") ? "generate"
        : intent.key.startsWith("regen-") ? expected ? "regenerate" : "generate" : intent.key;
      await update(operation, {...slot, count:intent.count, render_mode:intent.mode || expected?.quality || "draft"}, token);
      return {status:"success"};
    } finally { if (live(token)) { busy = false; schedulePoll(); } }
  }

  function schedulePoll() {
    clearTimeout(timer);
    if (!data || document.hidden || !(data.busy || active(analysis?.status) || active(report?.status))) return;
    timer = setTimeout(async () => {
      const token = scope;
      try {
        if (!dirty && !saving && !busy && data.busy) {
          const previous = data;
          const progress = await fetchJson(endpoint("progress"));
          if (!live(token) || data !== previous || dirty || busy) return;
          const jobs = new Map(progress.jobs.map(job => [job.request_id, job]));
          const settles = data.jobs.some(previous => {
            const next = jobs.get(previous.request_id);
            return next?.results.some(child => !active(child.status) &&
              previous.results.find(item => item.index === child.index)?.status !== child.status);
          });
          if (progress.revision !== data.revision || settles || !progress.busy) {
            const next = await fetchJson(endpoint());
            if (!live(token) || data !== previous || dirty || busy) return;
            data = next;
          } else {
            data.jobs = data.jobs.map(job => ({...job, ...jobs.get(job.request_id)}));
          }
        }
        if (live(token)) await refreshAdvisory(token);
      } catch (error) { if (live(token)) status(error.message); }
      finally { if (live(token)) schedulePoll(); }
    }, 2500);
  }

  async function refreshAdvisory(token) {
    if (!data) return;
    const id = author().job_id;
    const reportId = refinement().report_id;
    const taskId = refinement().task_id;
    if (id && (analysis?.id !== id || active(analysis.status))) {
      const next = await fetchJson(api + "/reconstructions/" + id);
      if (live(token) && author().job_id === id) analysis = next;
    }
    if (reportId && (report?.id !== reportId || active(report.status))) {
      const next = await fetchJson(api + "/reconstructions/" + taskId + "/reports/" + reportId);
      if (live(token) && refinement().report_id === reportId) report = next;
    }
    if (live(token)) render();
  }

  function fill(key, value) {
    if (document.activeElement !== el(key) && el(key).value !== (value || "")) el(key).value = value || "";
  }

  function renderAuthoring() {
    const state = author();
    el("source").textContent = state.source?.label || "Choose a reconstruction source.";
    for (const key of ["model", "notes", "preserve", "changes"]) fill(key, state[key] || (key === "model" ? options?.default_model : ""));
    fill("draft", state.edited_prompt ?? (analysis?.id === state.job_id ? analysis?.prompt : ""));
    el("analysis").textContent = analysis?.id === state.job_id && analysis
      ? [analysis.error || analysis.status, ...(analysis.uncertainties || []), ...(analysis.target?.questions || [])].join(" · ")
      : state.job_id ? "Loading analysis…" : "";
    el("use").disabled = analysis?.status !== "READY";
    el("analyze").disabled = !state.source || Boolean(state.job_id && (analysis?.id !== state.job_id || active(analysis?.status)));
  }

  function renderRefinement() {
    const state = refinement();
    const current = state.selected_id === candidateId(selection()) && report?.id === state.report_id ? report : null;
    el("report").textContent = current ? current.error || current.summary || current.status : "Compare the selected reconstruction to see findings.";
    fill("corrections", state.instructions);
    fill("quality", state.quality || "draft");
    const image = current && result(data.selected_slot)?.image;
    const comparison = el("comparison");
    comparison.hidden = !image;
    if (image && comparison.dataset.report !== current.id) {
      comparison.dataset.report = current.id;
      el("original").src = imageUrl(api + "/reconstructions/" + state.task_id + "/sources/0");
      el("compared").src = image.url;
    }
    const findings = el("findings");
    if (findings.dataset.report !== current?.id + ":" + current?.status) {
      findings.dataset.report = current?.id + ":" + current?.status;
      findings.replaceChildren();
      for (const item of current?.items || []) {
        if (!item.correction) continue;
        const label = document.createElement("label");
        const input = document.createElement("input");
        input.type = "checkbox";
        input.checked = state.item_ids?.includes(item.id);
        input.onchange = () => {
          const items = new Set(refinement().item_ids || []);
          if (input.checked) items.add(item.id); else items.delete(item.id);
          refinement().item_ids = [...items];
          markDirty();
        };
        label.append(input, item.correction);
        findings.append(label);
      }
    }
    el("correct").disabled = !current || active(current.status) || !data.slots.some(item => !item);
  }

  async function analyze() {
    const token = scope;
    if (!author().source || !await flush() || !live(token)) return;
    const {source, model, notes, preserve, changes} = author();
    await update("analyze", {...source, model, notes, preserve, changes,
      universe_style_variant:data.inputs.universe_style_variant}, token);
    if (live(token)) await refreshAdvisory(token);
  }

  function renderReferences() {
    const list = el("reference-list");
    list.replaceChildren();
    for (let index = 0; index < 10; index += 1) {
      const ref = data.inputs.reference_images?.[index] || {};
      const card = document.createElement("article");
      card.className = "image-generation-reference-controls";
      if (ref.image) {
        const image = document.createElement("img");
        image.src = ref.image;
        image.alt = ref.label || "Reference " + (index + 1);
        image.className = "image-generation-reference-thumb";
        card.append(image);
      }
      const label = document.createElement("input");
      label.value = ref.label || "";
      label.placeholder = "Reference " + (index + 1);
      label.setAttribute("aria-label", label.placeholder + " label");
      const edit = patch => {
        const refs = data.inputs.reference_images ||= [];
        while (refs.length <= index) refs.push({});
        refs[index] = {...refs[index], ...patch};
        markDirty();
        render();
      };
      label.oninput = () => edit({label:label.value});
      const upload = document.createElement("input");
      upload.type = "file";
      upload.accept = "image/*";
      upload.setAttribute("aria-label", "Upload " + label.placeholder);
      const load = async file => {
        const token = scope;
        const image = await readImage(file);
        if (!live(token)) return;
        edit({image, label:label.value || "image " + (index + 1), metadata:{}});
        renderReferences();
      };
      upload.onchange = () => { if (upload.files[0]) void run(() => load(upload.files[0])); };
      const paste = document.createElement("button");
      paste.type = "button";
      window.ZetImageCardUI.decorate(paste, "paste", "Focus to paste " + label.placeholder);
      paste.onpaste = event => {
        const file = [...event.clipboardData.files].find(file => file.type.startsWith("image/"));
        if (file) { event.preventDefault(); void run(() => load(file)); }
      };
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Remove";
      remove.hidden = !ref.image;
      remove.onclick = () => { edit({image:"", metadata:{}}); renderReferences(); };
      const pick = document.createElement("button");
      pick.type = "button";
      window.ZetImageCardUI.decorate(pick, "inventory", "Choose Inventory image");
      pick.onclick = () => {
        const token = scope;
        void run(() => pickImage(item => run(async () => {
          const {asset} = await fetchJson("/api/entity-library/assets/" + encodeURIComponent(item.asset_id));
          const response = await fetch(fileUrl(asset.image_path, asset.checksum));
          if (!response.ok) throw new Error("Unable to read the Inventory reference.");
          const image = await readImage(await response.blob());
          if (!live(token)) return;
          edit({image, label:label.value || asset.label || "image " + (index + 1), metadata:{}});
          renderReferences();
        })));
      };
      const actions = document.createElement("div");
      actions.className = "button-row";
      actions.append(pick, paste, remove);
      card.append(label, upload, actions);
      list.append(card);
    }
  }

  const run = async work => {
    try { await work(); } catch (error) { status(error.message); }
  };
  const click = (key, work) => { el(key).onclick = () => void run(work); };
  click("new", async () => {
    const name = prompt("Name the Image Generation asset");
    if (name?.trim()) await enter((await createAsset(fetchJson, name)).asset_id, true);
  });
  click("recover", async () => {
    const legacy = legacyInputs(owner);
    if (!legacy) return;
    const token = scope;
    const refs = await recoverReferences(owner, legacy);
    if (!live(token)) return;
    const recoveryId = localStorage.getItem("zet:image-generation-recovery:" + owner) || crypto.randomUUID();
    localStorage.setItem("zet:image-generation-recovery:" + owner, recoveryId);
    const created = await createAsset(fetchJson, "Recovered browser inputs", {
      prompt:legacy.prompt, negative_prompt:legacy.negativePrompt, mode:legacy.mode,
      aspect_ratio:legacy.aspectRatio, reference_images:refs, source_asset_id:legacy.sourceAssetId,
      source_checksum:legacy.sourceChecksum, universe_style_variant:legacy.universeStyleVariant,
      universe_style:legacy.universeStyleSnapshot, render_config:legacy.renderConfig, managed_style:legacy.managedStyle,
      reconstruction:legacy.reconstruction,
    }, recoveryId);
    if (live(token)) await enter(created.asset_id, true);
  });
  click("refresh", async () => {
    if (!dirty) return enter(data.asset_id);
    const choice = prompt("Unsaved edits conflict with a saved version. Enter RELOAD to discard local edits, or OVERWRITE to save this editor's inputs over the latest version.");
    if (choice === "RELOAD") {
      dirty = false;
      await enter(data.asset_id);
    } else if (choice === "OVERWRITE") {
      const token = scope;
      const next = await fetchJson(endpoint());
      if (!live(token)) return;
      data.revision = next.revision;
      await flush();
    }
  });
  click("rename", async () => {
    const name = prompt("Rename asset", data.name);
    if (name?.trim() && await flush()) await update("save", {name});
  });
  click("delete", async () => { if (await flush()) await deleteItems("delete-asset"); });
  click("pick", () => {
    const token = scope;
    return pickImage(item => {
      if (!live(token)) return;
      author().source = {asset_id:item.asset_id, label:item.label || "Inventory image"};
      markDirty();
      render();
    });
  });
  async function setUploadedSource(file) {
    const token = scope;
    const image = await readImage(file);
    if (!live(token)) return;
    author().source = {image, label:file.name || "Pasted source"};
    markDirty();
    render();
  }
  el("upload").onchange = () => {
    const file = el("upload").files[0];
    el("upload").value = "";
    if (file) void run(() => setUploadedSource(file));
  };
  window.ZetImageCardUI.decorate(el("pick"), "inventory");
  window.ZetImageCardUI.decorate(el("paste"), "paste");
  el("paste").onpaste = event => {
    const file = [...event.clipboardData.files].find(file => file.type.startsWith("image/"));
    if (file) { event.preventDefault(); void run(() => setUploadedSource(file)); }
  };
  for (const key of ["model", "notes", "preserve", "changes", "draft"]) {
    el(key).oninput = () => { author()[key === "draft" ? "edited_prompt" : key] = el(key).value; markDirty(); };
  }
  for (const [key, field] of [["corrections", "instructions"], ["quality", "quality"]]) {
    el(key).oninput = () => { refinement()[field] = el(key).value; markDirty(); };
  }
  click("analyze", analyze);
  click("use", async () => {
    const prompt = el("draft").value;
    if (!prompt.trim() || analysis?.status !== "READY") return;
    if (author().selected_result && candidateId(author().selected_result) !== candidateId(selection())) {
      throw new Error("The selected source changed. Start a new reconstruction.");
    }
    const provenance = Object.fromEntries(["id", "version", "model", "source", "style", "instruction_version",
      "content_prompt", "uncertainties", "notes", "target", "target_hash"].map(key => [key, analysis[key]]));
    Object.assign(data.inputs, {mode:"txt2img", prompt, reconstruction:{...provenance, prompt},
      source_asset_id:"", source_checksum:"", managed_style:""});
    delete data.inputs.render_config;
    markDirty();
    render();
    await flush();
  });
  click("correct", async () => {
    if (!await flush()) return;
    const token = scope;
    const {task_id, report_id, item_ids, instructions, quality} = refinement();
    await post(fetchJson, endpoint("correct"), {task_id, report_id, item_ids:item_ids || [], instructions:instructions || "",
      selected_result:selection(), render_mode:quality || "draft", aspect_ratio:data.inputs.aspect_ratio || "1:1"});
    if (live(token)) { data = await fetchJson(endpoint()); if (live(token)) render(); }
  });
  el("authoring").ontoggle = () => {
    if (!data || options || !el("authoring").open) return;
    const token = scope;
    void run(async () => {
      const next = await fetchJson(api + "/reconstructions/options");
      if (!live(token)) return;
      options = next;
      el("model").replaceChildren(...options.models.map(model => new Option(model, model)));
      renderAuthoring();
    });
  };
  document.addEventListener("visibilitychange", () => {
    if (!data || document.hidden || !live(scope)) return;
    schedulePoll();
    if (!data.busy && !dirty && !saving && !busy) void run(async () => {
      const token = scope;
      const previous = data;
      const next = await fetchJson(endpoint());
      if (!live(token) || data !== previous || dirty || busy) return;
      data = next;
      renderReferences();
      await refreshAdvisory(token);
    });
  });
  return {enter, leave, flush, assetId:() => data?.asset_id,
    inventoryAdded:payload => status(payload.duplicate ? "This candidate is already in Image Inventory." : "Added to Image Inventory."),
    taskContext:() => {
      const index = reviewed ? data?.slots.findIndex(item => candidateId(item) === reviewed) : data?.selected_slot;
      const item = data?.slots[index];
      return item ? {run:{state:"selected", id:item.requestId, label:item.requestId},
        candidate:{state:"selected", id:candidateId(item), label:"Slot " + (index + 1)}} : {};
    },
  };
}
