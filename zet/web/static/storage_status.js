/* Storage recovery continues independently of the currently selected workspace. */
(() => {
  let pending = false;
  const banner = document.createElement("div");
  banner.setAttribute("role", "status");
  banner.hidden = true;
  banner.style.cssText = "padding:12px;background:#fff1c2;color:#442f00;position:sticky;top:0;z-index:1000";
  document.body.prepend(banner);
  async function poll() {
    if (pending) return;
    pending = true;
    try {
      const response = await fetch("/api/storage/status");
      if (!response.ok) return;
      const status = await response.json();
      banner.hidden = status.available;
      if (!status.available) {
        const attention = Object.values(status.resources || {}).find(resource => resource.status === "RECOVERY_REQUIRED");
        const recovering = Object.values(status.resources || {}).some(resource => resource.status === "RECOVERING");
        banner.textContent = attention ? `Library storage needs attention: ${attention.error}. Restore the authoritative catalog to resume.` : recovering ? "Storage is reconnecting. Unfinished work will resume automatically." :
          "Paused — storage unavailable. Unfinished work will resume automatically. Reconnect the drive if needed.";
      }
    } catch (_) { /* Existing connection indicators own server connectivity. */ }
    finally { pending = false; }
  }
  void poll();
  setInterval(poll, 2000);
})();
