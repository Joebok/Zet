/* Shared browser intake form. Only explicit providers supply report context. */
(() => {
  const key = "zet.task-draft.v1";
  const dialog = document.querySelector("#task-capture-dialog");
  const form = document.querySelector("#task-capture-form");
  const el = (name) => document.querySelector(`#task-capture-${name}`);
  const fields = { type: "type", title: "title", description: "description",
    expected_behavior: "expected", actual_behavior: "actual", reproduction_steps: "reproduction" };
  let provider = null;
  let draft = null;
  let busy = false;
  let storageError = false;
  let unreadableDraft = false;
  let metadata = null;
  let metadataRequest = null;
  let generation = 0;

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
      if (value.version !== 1 || !value.report?.request_id || !value.report?.context ||
          !Object.keys(fields).every((name) => typeof value.report[name] === "string") ||
          (value.delivery && JSON.stringify(value.delivery) !== JSON.stringify(value.report))) {
        throw new Error("Invalid draft");
      }
      draft = value;
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
        const board = document.querySelector("#toolbar-open-board");
        const url = new URL(metadata.board_url);
        if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) throw new Error("Invalid board URL.");
        board.href = url.href;
        board.hidden = false;
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
      captured_at: new Date().toISOString(), zet_revision: metadata?.zet_revision || null }));
  }

  function render() {
    const locked = busy || Boolean(draft?.delivery);
    for (const [name, id] of Object.entries(fields)) {
      el(id).value = draft?.report[name] || (name === "type" ? "bug" : "");
      el(id).disabled = locked || !draft;
    }
    el("bug-details").hidden = draft?.report.type !== "bug";
    el("context").textContent = draft ? JSON.stringify(draft.report.context, null, 2) : "";
    el("refresh").disabled = locked || !draft;
    el("new").disabled = busy;
    el("submit").disabled = busy || !draft || Boolean(draft.capturePending) || !metadata?.configured;
    el("submit").textContent = draft?.delivery ? "Retry submission" : "Create task";
  }

  async function capture() {
    // Capture selections synchronously before any asynchronous configuration request.
    const token = ++generation;
    const context = capturedContext();
    if (!draft) {
      draft = { version: 1, report: { request_id: crypto.randomUUID(), type: "bug", title: "", description: "",
        expected_behavior: "", actual_behavior: "", reproduction_steps: "", context } };
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
      if (config.project_id) draft.report.project_id = config.project_id;
      draft.capturePending = false;
      save();
      message(config.configured ? "Draft saved locally. Review the captured context before creating the task."
        : "Set Kanban.ProjectID in config.toml and restart Zet before submitting. Your draft is retained.");
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
          if (config.project_id && !draft.report.project_id) draft.report.project_id = config.project_id;
          draft.capturePending = false;
          save();
        }
        if (draft) message(!config.configured
          ? "Set Kanban.ProjectID in config.toml and restart Zet before submitting. Your draft is retained."
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
    if (storageError) message("Draft retained in this tab.");
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy || !draft || draft.capturePending || !metadata?.configured) return;
    if (!draft.delivery) {
      // Hidden bug fields must not be sent for feature/improvement reports.
      if (draft.report.type !== "bug") {
        for (const name of ["expected_behavior", "actual_behavior", "reproduction_steps"]) draft.report[name] = "";
      }
      if (!draft.report.project_id) draft.report.project_id = metadata.project_id;
      draft.delivery = JSON.parse(JSON.stringify(draft.report));
      save();
    }
    busy = true;
    render();
    message("Submitting the saved report…");
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 65000);
    try {
      const response = await fetch("/api/tasks", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft.delivery), signal: controller.signal });
      const receipt = await response.json();
      if (!response.ok) throw new Error(typeof receipt.detail === "string" ? receipt.detail : `Task creation failed (${response.status}).`);
      const url = new URL(receipt.board_url);
      if (![200, 201].includes(response.status) || !/^task-[0-9a-f]{8}$/.test(receipt.task_id) ||
          typeof receipt.created !== "boolean" || receipt.created !== (response.status === 201) ||
          url.origin !== new URL(metadata.board_url).origin || url.pathname !== "/" ||
          url.search !== `?task_id=${receipt.task_id}` || url.hash || url.username || url.password) throw new Error("Invalid task receipt.");
      draft = null;
      ++generation;
      save();
      el("ticket").href = url.href;
      el("ticket").hidden = false;
      message(`Task ${receipt.task_id} created. Open task to view it on the board.`);
    } catch (error) {
      message(`${error.name === "AbortError" ? "Task delivery timed out." : error.message} Draft retained. Retry with the same request ID.`);
    } finally {
      clearTimeout(timer);
      busy = false;
      render();
    }
  });

  el("close").addEventListener("click", () => dialog.close());
  el("refresh").addEventListener("click", () => { if (!busy && !draft?.delivery) void capture(); });
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
  window.ZetTaskCapture = { registerProvider: (callback) => { provider = callback; }, open,
    notice(text) {
      notices.add(text);
      const banner = document.querySelector("#task-context-notice");
      banner.textContent = [...notices].join(" ");
      banner.hidden = false;
    } };
  void configuration().catch(() => { /* Opening the form surfaces configuration failures. */ });
})();
