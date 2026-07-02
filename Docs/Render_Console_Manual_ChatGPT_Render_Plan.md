# Render Console Manual ChatGPT Render Plan

## Goal

Add a manual ChatGPT render path that uses Zet's existing filesystem AI queue. Zet should be able to queue final image render tasks, present them in a purpose-built Render Console, let a human use ChatGPT normally, accept a pasted/generated image back into the console, and then let the existing harvester advance the asset.

This is not a ChatGPT browser automation project. The human remains in control of ChatGPT. Zet provides the cockpit, queue state, prompt/reference material, clipboard helpers, and answer-folder writing.

## Deployment Assumption

The Render Console will be a small FastAPI/HTML web app hosted by the main Zet machine.

Primary deployment path:

```text
main Zet machine
  uvicorn render console
  shared AI queue
  shared project files

other workstations
  access console over Tailscale
  use ChatGPT in their browser
  paste completed image back into console
```

Tailscale is the intended network boundary. The console should be reachable only by machines in the user's Tailscale group.

## Queue Contract

Add a manual render ask type:

```json
{
  "worker_type": "manual_chatgpt_render",
  "task_type": "render",
  "manual": true,
  "asset_id": 1,
  "character": "Tsaeytte",
  "phase": "Adult",
  "pipeline": "Body-Reference",
  "pipeline_stage": "RENDER",
  "prompt_file": "Final_Image_Prompt.md",
  "expected_output": "Body-Reference_Front.png",
  "render_preset": "chatgpt-manual",
  "reference_files": []
}
```

The answer folder should remain compatible with the current harvester:

```text
Answer/Ask_Asset_1_RENDER_.../
  ask_manifest.json
  answer_manifest.json
  Body-Reference_Front.png
```

Successful answer manifest:

```json
{
  "version": 1,
  "ask_id": "Ask_Asset_1_RENDER_...",
  "asset_id": 1,
  "ollama_attempt_id": "20260701_...",
  "worker_id": "manual-chatgpt-render-console",
  "status": "SUCCESS",
  "expected_output": "Body-Reference_Front.png",
  "started_at": "...",
  "completed_at": "...",
  "elapsed_seconds": 0,
  "error_type": "",
  "error_message": ""
}
```

Failure answer manifest:

```json
{
  "status": "ERROR",
  "error_type": "MANUAL_RENDER_FAILED",
  "error_message": "..."
}
```

## Claiming Model

Automated workers need claim folders because multiple workers may compete for a job. Manual ChatGPT render tasks do not need the same claim lifecycle.

For manual render asks:

- Leave the task in `Ask/` until the console saves an answer.
- The console may write `manual_status.json` for human visibility.
- When the human saves a result, move/copy the ask folder into `Answer/` with the output image and `answer_manifest.json`.
- Remove the original `Ask/` folder after the answer folder is complete.

This keeps manual rendering simple while preserving the existing harvester contract.

## Render Console UX

The Render Console should show one pending manual render task at a time.

Task display:

- asset id
- character / phase
- pipeline / stage
- body view / head view
- expected output filename
- prompt file name
- prompt text
- reference images or files
- source ask path
- target answer path

Actions:

- Copy prompt
- Copy output filename
- Copy reference image path
- Copy reference image when browser support allows
- Open ChatGPT
- Previous task
- Next task
- Paste/Drop returned image
- Save image answer
- Fail task

Paste support:

- Primary: `Ctrl+V` image paste into a drop zone.
- Secondary: drag/drop image file.
- Fallback: file picker.

After saving:

- preview the saved image
- write answer manifest
- move task to `Answer/`
- advance to next pending manual render task

## FastAPI Shape

Suggested package:

```text
zet/render_console/
  __init__.py
  app.py
  queue.py
  templates/
    index.html
  static/
    render_console.js
    render_console.css
```

Suggested endpoints:

```text
GET  /
GET  /api/tasks
GET  /api/tasks/{ask_id}
GET  /api/tasks/{ask_id}/prompt
GET  /api/tasks/{ask_id}/reference/{index}
POST /api/tasks/{ask_id}/answer-image
POST /api/tasks/{ask_id}/fail
POST /api/tasks/{ask_id}/manual-status
```

Suggested launcher:

```text
run_render_console.bat
```

Default run command:

```text
python3 -B -m zet.render_console.app --config config.toml
```

## Configuration

Add:

```toml
[Render]
Backend = "manual_chatgpt"

[RenderConsole]
Host = "127.0.0.1"
Port = 8090
RequireToken = false
Token = ""
```

For Tailscale deployment:

```toml
[RenderConsole]
Host = "0.0.0.0"
Port = 8090
```

Or bind directly to the machine's Tailscale IP if preferred.

## HTTPS Over Tailscale

Add a dedicated milestone for HTTPS over Tailscale.

Desired outcome:

```text
https://<tailscale-machine-name>.<tailnet-name>.ts.net:8090
```

Reasons:

- Browser clipboard APIs are more capable and reliable in secure contexts.
- The Render Console will be used from multiple machines.
- Tailscale provides a private network boundary while HTTPS provides browser trust and transport security.

Implementation research items:

- Confirm the active Tailscale MagicDNS name for the Zet host.
- Enable or document Tailscale HTTPS certificates.
- Decide whether uvicorn serves TLS directly or a small reverse proxy terminates TLS.
- Update `run_render_console.bat` or a companion PowerShell script to use the HTTPS configuration.
- Document firewall and Tailscale ACL expectations.

## Milestones

### Milestone 0 - Planning

- Write and commit this implementation plan.

### Milestone 1 - Manual Render Queue Contract - Complete

- Add config for render backend selection.
- Add `manual_chatgpt_render` ask generation when an asset enters `RENDER`.
- Use `Final_Image_Prompt.md` for manual ChatGPT render asks.
- Preserve condensed prompt use for local image render backends.
- Preserve the current ComfyUI/local render path behind config.
- Add tests or a smoke script for manifest generation.

Completed in commit after Milestone 0:

- `[Render].Backend` config added.
- `manual_chatgpt_render` ask generation added for Body-Reference `RENDER`.
- Existing local image render remains available when backend is not `manual_chatgpt`.
- Manual ChatGPT render asks use `Final_Image_Prompt.md`; local image render asks can still use `Condensed_Image_Prompt.md`.

### Milestone 2 - Render Console Skeleton - Complete

- Add FastAPI app.
- Add minimal HTML page.
- Load config and queue root.
- List pending `manual_chatgpt_render` asks.
- Show current task with Previous / Next navigation.

Completed:

- Added `zet/render_console`.
- Added FastAPI app skeleton.
- Added queue reader for pending `manual_chatgpt_render` asks.
- Added minimal HTML/JS/CSS console with Previous / Next navigation.
- Added `run_render_console.bat`.
- Added `fastapi` and `uvicorn` to requirements.

### Milestone 3 - Prompt And Reference Console

- Display prompt text.
- Add copy prompt button.
- Show reference files/images.
- Add copy path/copy filename helpers.
- Add Open ChatGPT button/link.

### Milestone 4 - Pasted Image Answer Flow - Complete

- Add paste/drop/file-picker image input.
- Preview pasted image.
- Save image as `expected_output`.
- Write `answer_manifest.json`.
- Move task from `Ask/` to `Answer/`.
- Verify existing harvester advances the asset to `RENDER_REVIEW`.

Completed:

- Added paste zone, drag/drop support, file-picker fallback, and image preview.
- Added `POST /api/tasks/{ask_id}/answer-image`.
- Saving writes the expected output image and compatible `answer_manifest.json`.
- Saving moves the manual render task from `Ask/` to `Answer/`.
- Queue-layer smoke test verified the write/move behavior.

### Milestone 5 - Failure Flow - Complete

- Add Fail task form.
- Write error answer manifest.
- Move task to `Answer/`.
- Verify existing harvester blocks the asset with useful error text.

Completed:

- Added Render Console fail panel with a reason field.
- Added `POST /api/tasks/{ask_id}/fail`.
- Failing writes a compatible `ERROR` answer manifest with `MANUAL_RENDER_FAILED`.
- Failing moves the task from `Ask/` to `Answer/`.
- Queue-layer smoke test verified the failed-answer write/move behavior.

### Milestone 6 - Launchers And LAN/Tailscale Hosting - Complete

- Add `run_render_console.bat`.
- Add optional PowerShell launcher.
- Document how to bind to localhost, all interfaces, or Tailscale IP.
- Confirm access from another Tailscale machine.

Completed:

- Added `run_render_console.bat`.
- Added `run_render_console.ps1`.
- Updated `run_ai_services.bat` and `run_ai_services.ps1` to start the Render Console alongside the unified proxy worker and auto harvester.
- Render Console bind host and port are controlled by `[RenderConsole]` in `config.toml`.
- Local-only default:

```toml
[RenderConsole]
Host = "127.0.0.1"
Port = 8090
```

- Tailscale/LAN option:

```toml
[RenderConsole]
Host = "0.0.0.0"
Port = 8090
```

Access from another Tailscale machine using the Zet host's Tailscale name or IP:

```text
http://<zet-host-tailnet-name>:8090
http://100.x.y.z:8090
```

Windows firewall may need to allow inbound connections to the configured port.

### Milestone 7 - HTTPS Over Tailscale

- Enable HTTPS access over Tailscale.
- Verify clipboard button behavior from the Tailscale URL.
- Keep paste/drop/file-picker fallback even if direct clipboard writes are browser-dependent.
- Document setup steps.

### Milestone 8 - Dashboard Integration - Complete

- Add `Open Render Console` link/button from AI Controls or Assets.
- Add visual indicator for pending manual render tasks.
- Add docs for the full manual render workflow.

Completed:

- Added AI Controls link to the configured Render Console URL.
- Added pending `manual_chatgpt_render` task count.
- Added pending manual render task table.

### Milestone 9 - Process Management - Complete

- Add a single process-control surface for the local Zet service set:
  - dashboard
  - unified proxy worker
  - auto harvester
  - render console
- Show whether each expected process is running.
- Show PID, command, host/port where relevant, and last known activity.
- Provide Start / Stop / Restart controls where safe.
- Avoid duplicate worker and harvester instances unless explicitly requested.
- Prefer a single launcher/supervisor script over scattered console windows.
- Preserve readable logs for each service.

Completed:

- Added `ProcessService` for expected Zet service status.
- Added AI Controls process table with running state, duplicate count, PIDs, manageability, and command lines.
- Added Start / Stop / Restart controls for:
  - unified proxy worker
  - auto harvester
  - render console
- Dashboard is shown as status-only to avoid self-termination from inside the Streamlit process.
- Process detection is currently lightweight and command-line based.

### Milestone 10 - Render Review Page

- Add a dedicated `RENDER_REVIEW` page similar to Prompt Review.
- Show the candidate image prominently.
- Show relevant prompt/render metadata.
- Include Previous / Next navigation across render-review assets.
- Move `Promote to LOCKED` from the Assets detail controls into Render Review.
- Add two Fail actions:
  - `Fail to Render`: send the asset back to `RENDER` so the assigned render agent queues and performs the render again.
  - `Fail to Regenerate`: treat the asset as needing upstream rework and reset it through the regeneration path.
- Keep the Assets table as the status overview rather than the main review workflow.

### Milestone 11 - Pipeline And Automation Controls

- Add dashboard visibility for configured pipeline stages, actors, and worker modules.
- Show active render backend and manual/local render settings.
- Show automation toggles:
  - prompt condense enabled
  - auto queue local preview after condense
  - render backend
  - auto harvester enabled/interval
- Allow editing safe config toggles from the UI.
- Keep deeper structural pipeline edits guarded by validation before writing `Pipelines.json`.
- Make it clear which settings are project config vs character/phase pipeline config.

## Open Questions

- Should manual render tasks be generated for all pipelines or only Body-Reference first?
- Which reference files should be attached for Body-Reference final render?
- Should the Render Console support batch completion from a grid later, or remain one-task-at-a-time?
- Should completed manual render answers be archived after harvesting?
- Should process supervision live inside Zet, or should Zet generate scripts for an external supervisor?
- Should Render Review offer a default fail button, or require the human to explicitly choose `Fail to Render` vs `Fail to Regenerate` every time?
