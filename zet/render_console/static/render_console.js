let tasks = [];
let currentIndex = 0;
let currentPrompt = "";

const emptyState = document.getElementById("empty-state");
const taskPanel = document.getElementById("task-panel");
const taskCount = document.getElementById("task-count");
const positionLabel = document.getElementById("position-label");
const previousButton = document.getElementById("previous-button");
const nextButton = document.getElementById("next-button");
const refreshButton = document.getElementById("refresh-button");
const copyPromptButton = document.getElementById("copy-prompt-button");
const promptText = document.getElementById("prompt-text");

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

function setText(id, value) {
  document.getElementById(id).textContent = value || "";
}

async function showTask(index) {
  currentIndex = index;
  const task = tasks[currentIndex];
  const detail = await fetchJson(`/api/tasks/${encodeURIComponent(task.ask_id)}`);
  currentPrompt = detail.prompt || "";

  setText("ask-id", detail.task.ask_id);
  setText("asset-label", `Asset ${detail.task.asset_id ?? "unknown"} | ${detail.task.character} / ${detail.task.phase}`);
  setText("pipeline-label", `${detail.task.pipeline} | ${detail.task.pipeline_stage}`);
  setText("expected-output", detail.task.expected_output);
  promptText.value = currentPrompt;

  positionLabel.textContent = `Task ${currentIndex + 1} of ${tasks.length}`;
  previousButton.disabled = currentIndex === 0;
  nextButton.disabled = currentIndex >= tasks.length - 1;
}

async function loadTasks() {
  const payload = await fetchJson("/api/tasks");
  tasks = payload.tasks || [];
  taskCount.textContent = `${tasks.length} manual render task${tasks.length === 1 ? "" : "s"} waiting`;

  if (!tasks.length) {
    emptyState.hidden = false;
    taskPanel.hidden = true;
    return;
  }

  emptyState.hidden = true;
  taskPanel.hidden = false;
  currentIndex = Math.min(currentIndex, tasks.length - 1);
  await showTask(currentIndex);
}

previousButton.addEventListener("click", () => {
  if (currentIndex > 0) {
    showTask(currentIndex - 1);
  }
});

nextButton.addEventListener("click", () => {
  if (currentIndex < tasks.length - 1) {
    showTask(currentIndex + 1);
  }
});

refreshButton.addEventListener("click", () => {
  loadTasks().catch((error) => {
    taskCount.textContent = `Refresh failed: ${error.message}`;
  });
});

copyPromptButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(currentPrompt);
  copyPromptButton.textContent = "Copied";
  setTimeout(() => {
    copyPromptButton.textContent = "Copy Prompt";
  }, 1400);
});

loadTasks().catch((error) => {
  taskCount.textContent = `Load failed: ${error.message}`;
});
