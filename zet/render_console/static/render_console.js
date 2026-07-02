let tasks = [];
let currentIndex = 0;
let currentPrompt = "";
let currentImageBlob = null;

const emptyState = document.getElementById("empty-state");
const taskPanel = document.getElementById("task-panel");
const taskCount = document.getElementById("task-count");
const positionLabel = document.getElementById("position-label");
const previousButton = document.getElementById("previous-button");
const nextButton = document.getElementById("next-button");
const refreshButton = document.getElementById("refresh-button");
const copyPromptButton = document.getElementById("copy-prompt-button");
const promptText = document.getElementById("prompt-text");
const pasteZone = document.getElementById("paste-zone");
const fileInput = document.getElementById("file-input");
const imagePreview = document.getElementById("image-preview");
const saveImageButton = document.getElementById("save-image-button");
const saveStatus = document.getElementById("save-status");
const failReason = document.getElementById("fail-reason");
const failTaskButton = document.getElementById("fail-task-button");
const failStatus = document.getElementById("fail-status");

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
  clearImageSelection();
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

function clearImageSelection() {
  currentImageBlob = null;
  imagePreview.hidden = true;
  imagePreview.removeAttribute("src");
  saveImageButton.disabled = true;
  saveStatus.textContent = "";
  failReason.value = "";
  failStatus.textContent = "";
}

function setImageSelection(blob) {
  if (!blob || !blob.type.startsWith("image/")) {
    saveStatus.textContent = "Clipboard or file did not contain an image.";
    return;
  }
  currentImageBlob = blob;
  imagePreview.src = URL.createObjectURL(blob);
  imagePreview.hidden = false;
  saveImageButton.disabled = false;
  saveStatus.textContent = `Ready to save ${Math.round(blob.size / 1024)} KB image.`;
}

function imageBlobFromPasteEvent(event) {
  const items = event.clipboardData?.items || [];
  for (const item of items) {
    if (item.type.startsWith("image/")) {
      return item.getAsFile();
    }
  }
  return null;
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

pasteZone.addEventListener("paste", (event) => {
  const blob = imageBlobFromPasteEvent(event);
  if (blob) {
    event.preventDefault();
    setImageSelection(blob);
  }
});

pasteZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  pasteZone.classList.add("drag-over");
});

pasteZone.addEventListener("dragleave", () => {
  pasteZone.classList.remove("drag-over");
});

pasteZone.addEventListener("drop", (event) => {
  event.preventDefault();
  pasteZone.classList.remove("drag-over");
  const file = event.dataTransfer?.files?.[0];
  setImageSelection(file);
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  setImageSelection(file);
});

saveImageButton.addEventListener("click", async () => {
  if (!currentImageBlob || !tasks[currentIndex]) {
    return;
  }
  const task = tasks[currentIndex];
  saveImageButton.disabled = true;
  saveStatus.textContent = "Saving image answer...";
  try {
    const response = await fetch(`/api/tasks/${encodeURIComponent(task.ask_id)}/answer-image`, {
      method: "POST",
      headers: {
        "Content-Type": currentImageBlob.type || "application/octet-stream",
      },
      body: currentImageBlob,
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `${response.status} ${response.statusText}`);
    }
    const payload = await response.json();
    saveStatus.textContent = `Saved answer: ${payload.answer_path}`;
    tasks = payload.remaining_tasks || [];
    if (!tasks.length) {
      taskCount.textContent = "0 manual render tasks waiting";
      emptyState.hidden = false;
      taskPanel.hidden = true;
      return;
    }
    currentIndex = Math.min(currentIndex, tasks.length - 1);
    await showTask(currentIndex);
  } catch (error) {
    saveStatus.textContent = `Save failed: ${error.message}`;
    saveImageButton.disabled = false;
  }
});

failTaskButton.addEventListener("click", async () => {
  if (!tasks[currentIndex]) {
    return;
  }
  if (!window.confirm("Fail this manual render task? The asset will be blocked when harvested.")) {
    return;
  }
  const task = tasks[currentIndex];
  failTaskButton.disabled = true;
  failStatus.textContent = "Writing failed answer...";
  try {
    const response = await fetch(`/api/tasks/${encodeURIComponent(task.ask_id)}/fail`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ reason: failReason.value || "" }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `${response.status} ${response.statusText}`);
    }
    const payload = await response.json();
    failStatus.textContent = `Failed answer written: ${payload.answer_path}`;
    tasks = payload.remaining_tasks || [];
    if (!tasks.length) {
      taskCount.textContent = "0 manual render tasks waiting";
      emptyState.hidden = false;
      taskPanel.hidden = true;
      return;
    }
    currentIndex = Math.min(currentIndex, tasks.length - 1);
    await showTask(currentIndex);
  } catch (error) {
    failStatus.textContent = `Fail failed: ${error.message}`;
  } finally {
    failTaskButton.disabled = false;
  }
});

loadTasks().catch((error) => {
  taskCount.textContent = `Load failed: ${error.message}`;
});
