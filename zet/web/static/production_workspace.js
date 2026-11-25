const storageKey = "zet.production-preparation-open";

export function mountProductionWorkspace({root, title, context = [], preparation = [], activity = [], results = []}) {
  const shell = document.createElement("section");
  shell.className = "production-workspace";
  shell.innerHTML = `<div class="production-workspace-context"></div><div class="production-operation-summary"></div>
    <div class="production-workspace-layout"><details class="production-preparation"><summary>Preparation</summary><div class="production-preparation-content"></div></details>
    <section class="production-workspace-results" aria-label="Candidates and render controls"></section></div>`;
  const place = (host, nodes) => nodes.filter(Boolean).forEach(node => host.append(node));
  place(shell.querySelector(".production-workspace-context"), [title, ...context]);
  place(shell.querySelector(".production-preparation-content"), preparation);
  place(shell.querySelector(".production-operation-summary"), activity);
  place(shell.querySelector(".production-workspace-results"), results);
  const preparationPanel = shell.querySelector(".production-preparation");
  let scope = "";
  preparationPanel.addEventListener("toggle", () => {
    shell.dataset.preparationOpen = String(preparationPanel.open);
  });
  preparationPanel.querySelector("summary").addEventListener("click", () => setTimeout(() => {
    if (!scope) return;
    const saved = JSON.parse(sessionStorage.getItem(storageKey) || "{}");
    saved[scope] = preparationPanel.open;
    sessionStorage.setItem(storageKey, JSON.stringify(saved));
  }, 0));
  root.append(shell);

  return {
    element: shell,
    setScope(nextScope, defaultOpen) {
      nextScope = String(nextScope || "default");
      if (nextScope === scope) return;
      scope = nextScope;
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || "{}");
      if (Object.hasOwn(saved, scope)) preparationPanel.open = Boolean(saved[scope]);
      else preparationPanel.open = Boolean(defaultOpen);
      shell.dataset.preparationOpen = String(preparationPanel.open);
    },
  };
}
