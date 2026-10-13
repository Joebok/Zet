/* Shared browser intake form. Only explicit providers supply report context. */
(() => {
  const key = "zet.task-draft.v1";
  const dialog = document.querySelector("#task-capture-dialog");
  const form = document.querySelector("#task-capture-form");
  const el = (name) => document.querySelector(`#task-capture-${name}`);
  const fields = { type: "type", title: "title", description: "description",
    expected_behavior: "expected", actual_behavior: "actual", reproduction_steps: "reproduction", success_criteria: "success" };
  let provider = null;
  let draft = null;
  let busy = false;
  let readingImages = false;
  let storageError = false;
  let unreadableDraft = false;
  let metadata = null;
  let metadataRequest = null;
  let generation = 0;
  let selectedControl = null;
  document.addEventListener("focusin", (event) => { if (!dialog.contains(event.target) && event.target.id && !event.target.id.startsWith("toolbar-")) selectedControl = event.target.id; });
  let previewTimer = null;
  let previewGeneration = 0;

  function newRequestId() {
    if (typeof globalThis.crypto?.randomUUID === "function") return globalThis.crypto.randomUUID();
    const bytes = new Uint8Array(16);
    if (typeof globalThis.crypto?.getRandomValues === "function") {
      globalThis.crypto.getRandomValues(bytes);
    } else {
      for (let index = 0; index < bytes.length; index++) bytes[index] = Math.floor(Math.random() * 256);
    }
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }

  function message(text) {
    el("status").textContent = text + (storageError ? " Browser storage is unavailable; keep this tab open to retain the draft." : "");
  }

  function save() {
    try {
      if (draft) localStorage.setItem(key, JSON.stringify(draft));
      else localStorage.removeItem(key);
      storageError = false;
    } catch {
      storageError = true;
    }
  }

  function restore() {
    if (draft) return; // Preserve in-memory edits when browser storage failed.
    let raw;
    try {
      raw = localStorage.getItem(key);
    } catch {
      storageError = true;
      return; // A fresh report can still be retained in this tab.
    }
    try {
      if (!raw) return;
      const value = JSON.parse(raw);
      if (![1, 2].includes(value.version) || !value.report?.request_id || !value.report?.context ||
          !Object.keys(fields).filter((name) => name !== "success_criteria").every((name) => typeof value.report[name] === "string") ||
          (value.delivery && JSON.stringify(value.delivery) !== JSON.stringify(value.report))) {
        throw new Error("Invalid draft");
      }
      if (value.screenshots !== undefined && (!Array.isArray(value.screenshots) || value.screenshots.length > 4 ||
          value.screenshots.some((item) => !item || typeof item.filename !== "string" ||
            !["image/png", "image/jpeg", "image/webp"].includes(item.content_type) ||
            typeof item.content_base64 !== "string" || item.content_base64.length > 4 * Math.ceil(5 * 1024 * 1024 / 3) ||
            (item.attachment_id && !/^attachment-[0-9a-f]{32}$/.test(item.attachment_id))))) throw new Error("Invalid screenshots");
      draft = value;
      draft.legacy = value.version === 1;
      unreadableDraft = false;
    } catch {
      // Do not silently overwrite an unreadable saved report.
      unreadableDraft = true;
      message("The saved draft could not be read. Discard it explicitly to start a new report.");
    }
  }

  async function configuration() {
    if (!metadataRequest) {
      metadataRequest = (async () => {
        const response = await fetch("/api/tasks/config");
        if (!response.ok) throw new Error("Unable to load task configuration. Close and reopen to retry.");
        metadata = await response.json();
        const board = document.querySelector("#toolbar-github-issues");
        if (!metadata.issues_url) { if (board) board.hidden = true; return metadata; }
        const url = new URL(metadata.issues_url);
        if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) throw new Error("Invalid GitHub issues URL.");
        if (board) { board.href = url.href; board.hidden = false; }
        return metadata;
      })().finally(() => { metadataRequest = null; });
    }
    return metadataRequest;
  }

  function capturedContext() {
    const context = provider ? provider() : {
      page_id: "dashboard", page_name: "Zet dashboard", source_url: window.location.origin + "/",
      universe_id: null, selections: {},
    };
    return JSON.parse(JSON.stringify({ ...context, version: 1,
      captured_at: new Date().toISOString(), zet_revision: metadata?.zet_revision || null,
      viewport: { width: window.innerWidth, height: window.innerHeight, device_pixel_ratio: window.devicePixelRatio },
      selected_control: selectedControl }));
  }

  function render() {
    const locked = busy || readingImages || Boolean(draft?.delivery) || Boolean(draft?.legacy);
    for (const [name, id] of Object.entries(fields)) {
      el(id).value = draft?.report[name] || (name === "type" ? "bug" : "");
      el(id).disabled = locked || !draft;
    }
    el("bug-details").hidden = draft?.report.type !== "bug";
    el("start-codex").checked = draft?.report.start_codex !== false;
    el("start-codex").disabled = locked || !draft;
    el("context").textContent = draft ? JSON.stringify(draft.report.context, null, 2) : "";
    el("refresh").disabled = locked || !draft;
    el("new").disabled = busy || readingImages;
    el("files").disabled = locked || !draft;
    el("paste").setAttribute("aria-disabled", String(locked || !draft));
    renderScreenshots(locked);
    el("submit").disabled = busy || readingImages || !draft || Boolean(draft.capturePending) || !metadata?.configured || Boolean(draft?.legacy);
    el("convert").hidden = !draft?.legacy;
    el("submit").textContent = draft?.delivery ? "Retry submission" : draft?.report.start_codex === false ? "Save for later" : "Create task";
    schedulePreview();
  }

  function renderScreenshots(locked) {
    el("screenshots").replaceChildren();
    (draft?.screenshots || []).forEach((image, index) => {
      const row = document.createElement("li");
      const preview = document.createElement("img");
      preview.src = `data:${image.content_type};base64,${image.content_base64}`;
      preview.alt = image.filename;
      const label = document.createElement("span");
      label.textContent = image.filename + (image.attachment_id ? " Ã‚Â· uploaded" : " Ã‚Â· saved in draft");
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Remove";
      remove.disabled = locked;
      remove.addEventListener("click", () => {
        if (busy || readingImages || draft?.delivery) return;
        draft.screenshots.splice(index, 1);
        save();
        render();
        message("Screenshot removed from this draft.");
      });
      row.append(preview, label, remove);
      el("screenshots").append(row);
    });
  }

  async function addScreenshots(files) {
    if (!draft || draft.delivery || busy || readingImages) return;
    readingImages = true;
    const current = draft;
    render();
    try {
      const additions = [];
      if ((draft.screenshots || []).length + files.length > 4) throw new Error("Choose at most four screenshots.");
      for (const file of files) {
        const suffixes = { "image/png": ["png"], "image/jpeg": ["jpg", "jpeg"], "image/webp": ["webp"] };
        if (!suffixes[file.type]) throw new Error("Choose PNG, JPEG, or WebP screenshots.");
        if (!file.size || file.size > 5 * 1024 * 1024) throw new Error("Each screenshot must contain an image of at most 5 MiB.");
        const filename = file.name || `pasted-screenshot.${suffixes[file.type][0]}`;
        if (filename.length > 240 || /[\\/\x00-\x1f\x7f]/.test(filename) ||
            !suffixes[file.type].includes(filename.split(".").pop().toLowerCase())) throw new Error("Screenshot filename must match its image type.");
        const encoded = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result);
          reader.onerror = () => reject(new Error("Could not read the screenshot."));
          reader.readAsDataURL(file);
        });
        const image = { filename, content_type: file.type, content_base64: encoded.split(",", 2)[1] };
        if ([...(draft.screenshots || []), ...additions].some((item) => item.filename === image.filename &&
            item.content_type === image.content_type && item.content_base64 === image.content_base64)) throw new Error("This screenshot is already in the draft.");
        additions.push(image);
      }
      if (draft !== current) return;
      draft.screenshots = [...(draft.screenshots || []), ...additions];
      save();
      message("Screenshots saved with the local draft. Review them before submitting.");
    } catch (error) { message(error.message); }
    finally { readingImages = false; el("files").value = ""; render(); }
  }

  el("files").addEventListener("change", (event) => void addScreenshots([...event.target.files]));
  form.addEventListener("paste", (event) => {
    const files = [...(event.clipboardData?.items || [])].filter((item) => item.kind === "file").map((item) => item.getAsFile()).filter(Boolean);
    if (files.length) { event.preventDefault(); void addScreenshots(files); }
  });

  function schedulePreview() {
    clearTimeout(previewTimer);
    const token = ++previewGeneration;
    if (!draft || draft.legacy || !metadata?.configured) { el("preview").textContent = "Enter a title to preview the public GitHub issue."; return; }
    previewTimer = setTimeout(async () => {
      try {
        const report = JSON.parse(JSON.stringify(draft.delivery || draft.report));
        report.attachment_ids = [];
        const response = await fetch("/api/tasks/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(report) });
        const result = await response.json();
        if (token !== previewGeneration) return;
        el("preview").textContent = response.ok ? result.body : (typeof result.detail === "string" ? result.detail : "Preview unavailable.");
      } catch { if (token === previewGeneration) el("preview").textContent = "Preview unavailable; your draft is retained."; }
    }, 250);
  }

  el("convert").addEventListener("click", () => {
    if (!draft?.legacy || !metadata?.repository) return;
    if (!confirm(`Convert this draft to a public issue in ${metadata.repository}? An earlier Kanban delivery may already exist. The original draft will be backed up in this browser.`)) return;
    try { localStorage.setItem(`zet.task-draft.kanban-backup.${draft.report.request_id}`, JSON.stringify(draft)); }
    catch { message("Could not preserve the original Kanban draft. Free browser storage before converting."); return; }
    draft = { version: 2, report: { ...draft.report, request_id: newRequestId(), repository: metadata.repository, success_criteria: "", start_codex: true },
      screenshots: (draft.screenshots || []).map(({ attachment_id, ...image }) => image) };
    delete draft.report.project_id;
    delete draft.report.allow_auto_plan_approval;
    save(); render();
    message("Draft converted. Review the public issue preview before submitting.");
  });

  async function postDraft(url, payload) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 65000);
    try {
      const response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload), signal: controller.signal });
      const receipt = await response.json();
      if (!response.ok) throw new Error(typeof receipt.detail === "string" ? receipt.detail : `Delivery failed (${response.status}).`);
      return { response, receipt };
    } finally { clearTimeout(timer); }
  }

  async function capture() {
    // Capture selections synchronously before any asynchronous configuration request.
    const token = ++generation;
    const context = capturedContext();
    if (!draft) {
      draft = { version: 2, report: { request_id: newRequestId(), type: "bug", title: "", description: "",
        expected_behavior: "", actual_behavior: "", reproduction_steps: "", success_criteria: "", start_codex: true, context } };
    } else {
      draft.report.context = context;
    }
    draft.capturePending = true;
    save();
    render();
    try {
      const config = await configuration();
      if (token !== generation || !draft || draft.delivery) return;
      draft.report.context.zet_revision = config.zet_revision;
      if (config.repository) draft.report.repository = config.repository;
      draft.capturePending = false;
      save();
      message(config.configured ? "Draft saved locally. Review the captured context before creating the task."
        : "Set GitHub.Repository on the Zet host before submitting. Your draft is retained.");
    } catch (error) {
      message(error.message);
    }
    render();
  }

  async function open() {
    if (dialog.open) return;
    el("ticket").hidden = true;
    restore();
    dialog.showModal();
    if (!draft && !unreadableDraft) {
      await capture();
    } else {
      render();
      try {
        const config = await configuration();
        if (draft?.capturePending) {
          draft.report.context.zet_revision = config.zet_revision;
          if (config.repository && !draft.report.repository && !draft.legacy) draft.report.repository = config.repository;
          draft.capturePending = false;
          save();
        }
        if (draft) message(draft.legacy ? "This saved Kanban draft has not been sent to GitHub. Convert it explicitly below; its original copy will be retained." : !config.configured
          ? "Set GitHub.Repository on the Zet host before submitting. Your draft is retained."
          : draft.delivery
          ? "Delivery was attempted. Retry sends the exact saved report; editing is locked to avoid duplicate tickets."
          : "Saved draft restored with its original context. Refresh context explicitly to replace it.");
      } catch (error) {
        message(error.message);
      }
      render();
    }
  }

  form.addEventListener("input", () => {
    if (!draft || draft.delivery || busy) return;
    for (const [name, id] of Object.entries(fields)) draft.report[name] = el(id).value;
    el("bug-details").hidden = draft.report.type !== "bug";
    save();
    schedulePreview();
    if (storageError) message("Draft retained in this tab.");
  });

  el("start-codex").addEventListener("change", () => {
    if (!draft || draft.delivery || busy) return;
    draft.report.start_codex = el("start-codex").checked;
    save();
    render();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy || readingImages || !draft || draft.legacy || draft.capturePending || !metadata?.configured) return;
    if (!draft.delivery) {
      // Hidden bug fields must not be sent for feature/improvement reports.
      if (draft.report.type !== "bug") {
        for (const name of ["expected_behavior", "actual_behavior", "reproduction_steps"]) draft.report[name] = "";
      }
      if (!draft.report.repository) draft.report.repository = metadata.repository;
      draft.delivery = JSON.parse(JSON.stringify(draft.report));
      save();
    }
    busy = true;
    render();
    message("Submitting the saved reportÃ¢â‚¬Â¦");
    try {
      for (const screenshot of draft.screenshots || []) {
        if (screenshot.attachment_id) continue;
        message(`Uploading ${screenshot.filename}Ã¢â‚¬Â¦`);
        const { response, receipt } = await postDraft("/api/tasks/attachments", {
          request_id: draft.delivery.request_id, repository: draft.delivery.repository,
          filename: screenshot.filename, content_type: screenshot.content_type, content_base64: screenshot.content_base64,
        });
        if (![200, 201].includes(response.status) || !/^attachment-[0-9a-f]{32}$/.test(receipt.attachment_id) ||
            typeof receipt.created !== "boolean" || receipt.created !== (response.status === 201) ||
            receipt.filename !== screenshot.filename || receipt.content_type !== screenshot.content_type) throw new Error("Invalid screenshot receipt.");
        screenshot.attachment_id = receipt.attachment_id;
        save();
      }
      const report = JSON.parse(JSON.stringify(draft.delivery));
      if (draft.screenshots?.length) report.attachment_ids = draft.screenshots.map((item) => item.attachment_id);
      message("Submitting the saved reportÃ¢â‚¬Â¦");
      const { response, receipt } = await postDraft("/api/tasks", report);
      const url = new URL(receipt.issue_url);
      if (![200, 201].includes(response.status) || !Number.isInteger(receipt.issue_number) || receipt.issue_number < 1 || receipt.repository !== draft.delivery.repository ||
          typeof receipt.created !== "boolean" || receipt.created !== (response.status === 201) ||
          url.origin !== "https://github.com" || url.pathname !== `/${receipt.repository}/issues/${receipt.issue_number}` || url.search || url.hash || url.username || url.password) throw new Error("Invalid task receipt.");
      draft = null;
      ++generation;
      save();
      el("ticket").href = url.href;
      el("ticket").hidden = false;
      message(`GitHub issue #${receipt.issue_number} created. Open task to view it.`);
    } catch (error) {
      message(`${error.name === "AbortError" ? "Task delivery timed out." : error.message} Draft retained. Retry with the same request ID.`);
    } finally {
      busy = false;
      render();
    }
  });

  el("close").addEventListener("click", () => dialog.close());
  el("refresh").addEventListener("click", () => { if (!busy && !readingImages && !draft?.delivery) void capture(); });
  el("new").addEventListener("click", () => {
    if (!confirm(draft?.delivery
      ? "Delivery may already have created a ticket. Discarding and submitting a new report can create a duplicate. Discard this draft?"
      : "Discard this local draft and start a new report?")) return;
    draft = null;
    unreadableDraft = false;
    ++generation;
    save();
    el("ticket").hidden = true;
    void capture();
  });
  document.querySelector("#toolbar-create-task").addEventListener("click", () => void open());
  const notices = new Set();
  window.ZetTaskCapture = { registerProvider: (callback) => { const previous = provider; provider = callback; return () => { if (provider === callback) provider = previous; }; }, open,
    notice(text) {
      notices.add(text);
      const banner = document.querySelector("#task-context-notice");
      banner.textContent = [...notices].join(" ");
      banner.hidden = false;
    } };
  void configuration().catch(() => { /* Opening the form surfaces configuration failures. */ });
})();
