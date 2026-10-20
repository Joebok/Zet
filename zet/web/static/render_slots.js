/** Shared presentation only. Server services own allocation and protection. */
window.ZetRenderSlots = {
  countControl(emptyCount, onGenerate, { disabled = false, reason = "" } = {}) {
    const group = document.createElement("div");
    group.className = "button-row compact render-slot-add";
    const label = document.createElement("label");
    const caption = document.createElement("span"); caption.className = "render-slot-count-label";
    caption.textContent = "Additional renders"; label.append(caption);
    const input = document.createElement("input");
    input.type = "number"; input.min = "1"; input.max = String(Math.max(1, emptyCount)); input.value = "1";
    input.disabled = disabled || !emptyCount;
    label.append(input);
    const button = document.createElement("button");
    button.type = "button"; button.textContent = "Add renders";
    button.disabled = disabled || !emptyCount; button.title = reason || (emptyCount ? "Fill empty slots" : "All slots are occupied");
    button.addEventListener("click", () => {
      if (input.reportValidity()) onGenerate(Number(input.value));
    });
    group.append(label, button);
    if (reason) {
      const explanation = document.createElement("small"); explanation.textContent = reason; group.append(explanation);
    }
    return group;
  },
};
