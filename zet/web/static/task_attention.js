/* Task attention is read-only; questions/reviews are answered on GitHub. */
(() => {
  const button = document.querySelector("#toolbar-task-attention");
  if (!button) return;
  const panel = document.createElement("dialog");
  panel.className = "task-capture-dialog";
  panel.setAttribute("aria-labelledby", "task-attention-heading");
  const title = document.createElement("h2");
  title.id = "task-attention-heading";
  title.textContent = "Tasks and updates";
  const list = document.createElement("ul");
  const usage = document.createElement("p");
  const worker = document.createElement("p");
  const close = document.createElement("button");
  close.type = "button";
  close.textContent = "Close";
  close.addEventListener("click", () => panel.close());
  panel.append(title, worker, usage, list, close);
  document.body.append(panel);
  let lastSignature = null;
  let refreshing = false;
  function render(value) {
    const items = [...(value.items || [])];
    const deploy = value.deployment;
    const publication = deploy?.local_edits?.publication;
    if (publication?.id) items.push({ id: "template-publication", kind: "templates",
      title: `Template PR: ${publication.state}${publication.error ? ` — ${publication.error}` : ""}. Open Restart for recovery controls.`,
      ...(publication.pr_url ? { url: publication.pr_url } : {}) });
    if (deploy?.local_edits?.files?.some((file) => !file.reconciled)) items.push({ id: "template-edits", kind: "update",
      title: "Local tracked edits block updating. Open Restart to review and publish eligible template edits." });
    if (deploy?.update_available) items.push({ id: "deployment-update", kind: "update", title: "Merged changes are available. Use Restart → Update and restart to install them." });
    if (["failed", "rolled-back", "recovery-required"].includes(deploy?.operation?.state)) {
      items.push({ id: "deployment-failure", kind: "failure", title: `Update ${deploy.operation.state}: ${deploy.operation.error || deploy.operation.recovery_error || "inspect deployment status"}` });
    }
    const signature = JSON.stringify(items.map((item) => [item.id, item.title]));
    if (signature !== lastSignature) {
      button.textContent = items.length ? `Tasks · ${items.length}` : "Tasks";
      button.title = items.length ? "Action or status needs your attention" : "No task action needed";
      lastSignature = signature;
    }
    worker.textContent = value.worker?.checked_at ? `Worker: ${value.worker.state} · last checked ${new Date(value.worker.checked_at * 1000).toLocaleString()}` : "Worker not yet available; submitted issues remain queued.";
    usage.textContent = value.usage?.known ? value.usage.windows.map((window) => `${window.bucket}: ${Math.round(window.remaining_percent)}% remaining${window.resets_at ? `, resets ${new Date(window.resets_at * 1000).toLocaleString()}` : ""}`).join(" · ") : "Usage limits unknown.";
    list.replaceChildren();
    for (const item of items) {
      const row = document.createElement("li");
      if (item.url) {
        const url = new URL(item.url);
        if (url.origin !== "https://github.com") continue;
        const link = document.createElement("a");
        link.href = url.href; link.target = "_blank"; link.rel = "noopener";
        link.textContent = `${item.kind}: ${item.title}`;
        row.append(link);
      } else row.textContent = item.title;
      list.append(row);
    }
    if (!items.length) { const row = document.createElement("li"); row.textContent = "No action needed."; list.append(row); }
  }
  async function refresh() {
    if (refreshing) return;
    refreshing = true;
    try {
      const response = await fetch("/api/tasks/status", { cache: "no-store" });
      if (!response.ok) throw new Error();
      render(await response.json());
    } catch { button.textContent = "Tasks · unavailable"; }
    finally { refreshing = false; }
  }
  button.addEventListener("click", () => { void refresh(); panel.showModal(); });
  setInterval(() => { if (!document.hidden) void refresh(); }, 30000);
  void refresh();
})();
