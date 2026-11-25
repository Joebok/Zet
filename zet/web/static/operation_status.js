(() => {
  const labels = Object.freeze({
    submitting: "Submitting", queued: "Queued", running: "Running", success: "Complete",
    complete: "Complete", error: "Failed", failed: "Failed", unknown: "Status unknown", paused: "Paused",
  });

  function render(node, operation) {
    const status = String(operation?.status || "").toLowerCase();
    const label = labels[status];
    node.dataset.status = label ? status : "message";
    node.classList.toggle("error", status === "error" || status === "failed");
    const message = operation?.message || "";
    node.textContent = label && message ? `${label}: ${message}` : label || message;
  }

  window.ZetOperationStatus = { render };
})();
