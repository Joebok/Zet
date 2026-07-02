# FastAPI Dashboard Migration Plan

## Goal

Replace the Streamlit dashboard with a conventional FastAPI-served web UI using normal HTML, CSS, JavaScript, and JSON APIs.

This is an all-or-none direction for the main Zet dashboard. Streamlit can remain temporarily during migration, but the target state is one primary Zet web UI.

The existing Python backend services remain the source of truth. The migration should not rewrite pipeline logic, queue logic, prompt compilation, asset state transitions, or render handling into JavaScript.

## UI Stack

Target stack:

```text
FastAPI
Jinja/static HTML where useful
Vanilla CSS
Vanilla JavaScript with fetch/AJAX
Existing Zet Python services
```

Avoid a heavy frontend framework until there is a concrete need.

## Design Principles

- One click should do one predictable thing.
- Tables should support normal browser interaction without Streamlit rerun surprises.
- Pages should use JSON endpoints backed by services.
- UI-specific formatting can live in the web layer.
- Business logic belongs in services.
- Existing Render Console behavior should be folded into the main Zet web UI instead of remaining a separate app long term.

## Post-Migration Additions

### Head-Fitment Manifest Picker

Head-fitment uses a Manifest page to choose explicit image reference slots before prompt/render work continues.

Implemented:

- Head-Fitment assets at `MANIFEST / PYTHON` appear as manifest tasks.
- Locked Body-Reference images are available as body-reference slot choices.
- Headshot reference images can be selected from or uploaded to `Reference_Images/Headshots/`.
- Saved selections are stored in `asset.reference_files`.
- Manual ChatGPT render asks for Head-Fitment include those references in `ask_manifest.json.reference_files`.

## Milestones

### Milestone 0 - Plan And Direction - Complete

- Record the decision to migrate off Streamlit for the main dashboard.
- Document the target UI stack and migration boundaries.
- Keep Streamlit available until replacement pages are complete.

Completed:

- Added this migration plan.
- Recorded FastAPI plus vanilla HTML/CSS/JavaScript as the target UI direction.
- Confirmed the existing Python service layer remains the source of truth.

### Milestone 1 - FastAPI Web Shell And Assets Read View - Complete

- Add a new `zet/web` FastAPI app.
- Add shared CSS and JavaScript.
- Add character/phase loading.
- Add an Assets page with a normal HTML table.
- Implement single-click row selection.
- Show selected asset details and image/path summaries.
- Add read-only APIs:
  - `GET /api/context`
  - `GET /api/assets`
  - `GET /api/assets/{asset_id}`

Completed:

- Added `zet/web`.
- Added `run_zet_web.bat`.
- Added a FastAPI app shell with normal static HTML/CSS/JavaScript.
- Added character/phase selectors.
- Added an Assets page using a native HTML table.
- Added single-click row selection without Streamlit reruns.
- Added read-only context, asset list, and asset detail APIs.

### Milestone 2 - Assets Actions - Complete

- Add service-backed buttons to the Assets page:
  - Stage AI Ask
  - Run Current Worker
  - Run Housekeeping
  - Retry AI
  - Regenerate
  - Promote to LOCKED
- Add API endpoints for those actions.
- Preserve action messages without page-state surprises.
- Keep selection stable after action refreshes.

Completed:

- Added service-backed asset action APIs:
  - `POST /api/assets/{asset_id}/stage-ai-ask`
  - `POST /api/assets/{asset_id}/run-current-worker`
  - `POST /api/assets/{asset_id}/run-housekeeping`
  - `POST /api/assets/{asset_id}/retry-ai`
  - `POST /api/assets/{asset_id}/regenerate`
  - `POST /api/assets/{asset_id}/promote-to-locked`
- Wired AJAX buttons on the Assets page.
- Added action-message display without full page reloads.
- Added button enable/disable rules based on selected asset state.
- Kept table selection stable after action refreshes.

### Milestone 3 - Prompt Review - Complete

- Add Prompt Review page.
- Show full prompt with readable scrolling.
- Add search and copy.
- Add condensed prompt viewer.
- Add local test render button and image preview.
- Add Approve / Fail.
- Add Previous / Next across review tasks.

Completed:

- Added Prompt Review task and detail APIs.
- Added Prompt Review page in the FastAPI UI.
- Added prompt search, copy prompt, condensed prompt dialog, and copy condensed prompt.
- Added local test render action and latest render image display.
- Added Approve / Fail actions.
- Added Previous / Next navigation across prompt-review tasks.

### Milestone 4 - Render Review

- [x] Add Render Review page.
- [x] Show candidate image and render metadata.
- [x] Add Promote to LOCKED.
- [x] Add fail paths:
  - Fail to Render
  - Fail to Regenerate
- [x] Add Previous / Next across render-review tasks.

Completed:

- Added Render Review task and detail APIs.
- Added Render Review page in the FastAPI UI.
- Added candidate image display through the local file endpoint.
- Moved Promote to LOCKED into the render review workflow.
- Added Fail to RENDER, which clears the current candidate image and stages a fresh render ask.
- Added Fail to REGENERATE, which reuses the existing full regeneration path.
- Added Previous / Next navigation across render-review tasks.

### Milestone 5 - AI Controls

- [x] Replace AI Controls in the FastAPI UI.
- [x] Show queue counts and tables.
- [x] Show process status and controls.
- [x] Show monitor tests and responses.
- [x] Show proxy stop/resume controls.
- [x] Show manual render task counts.
- [x] Move remaining AI Controls aggregation out of Streamlit-only code where appropriate.

Completed:

- Added an AI Controls snapshot API.
- Added harvest, monitor test, proxy stop/resume, and process action APIs.
- Added the FastAPI AI Controls page with queue, manual render, process, and monitor tables.
- Kept process management behind the existing `ProcessService`.
- Added regression coverage for the snapshot and monitor-test APIs.

### Milestone 6 - Pipeline Controls

- [x] Replace Pipeline Controls in the FastAPI UI.
- [x] Show project automation settings.
- [x] Edit safe config toggles.
- [x] Show pipeline stage/actor/worker table.
- [x] Support batch render reset.

Completed:

- Added Pipeline Controls snapshot, automation-save, and batch-render-reset APIs.
- Added editable project automation settings to the FastAPI UI.
- Added read-only pipeline stage/actor/worker visibility with asset counts.
- Added batch render reset controls and result reporting.
- Reused `PipelineControlService` and `AssetService` rather than moving workflow logic into the UI.
- Added regression coverage for settings save and batch reset APIs.

### Milestone 7 - Template Editor - Deferred

- Replace Template Editor.
- Move script-helper behavior behind service/API boundaries where useful.
- Preserve view-specific section editing.

Deferred:

- Template Editor migration is intentionally paused while body-reference template/editing ideas are being reconsidered.
- Do not port the current editor blindly until the desired body-reference authoring workflow is clearer.

### Milestone 8 - Merge Render Console

- [x] Fold the existing Render Console into the main Zet web app.
- [x] Preserve paste/drop/file-picker behavior.
- [x] Preserve task navigation.
- [ ] Retire separate Render Console launcher once merged.

Completed:

- Added namespaced render-console APIs to the main FastAPI app.
- Added a Render Console tab to the dashboard.
- Preserved manual render task navigation, prompt copy, image paste/drop/file picker, save answer, and fail task behavior.
- Reused `RenderConsoleQueue` for all filesystem queue operations.
- Changed AI Controls to open the in-dashboard Render Console tab.
- Added regression coverage for task listing, prompt detail, and saving an image answer.

Remaining:

- Keep the standalone Render Console launcher temporarily for fallback while the integrated page settles.

### Milestone 9 - Retire Streamlit

- [x] Confirm the FastAPI UI covers all dashboard functions except the intentionally deferred Template Editor.
- [x] Update launch scripts to start the FastAPI UI as the main dashboard.
- [x] Move Streamlit dashboard to legacy/diagnostic status.
- [x] Update docs and process controls.

Completed:

- `dashboard.bat` now launches the FastAPI dashboard through `run_zet_web.bat`.
- Added `run_streamlit_dashboard.bat` for the legacy Streamlit dashboard.
- Updated process controls to show `Zet Web Dashboard` as the primary dashboard process.
- Updated AI service startup scripts so they no longer start the standalone Render Console by default.
- Left the standalone Render Console launcher available as temporary fallback.

## Near-Term Recommendation

Start with Milestone 1 and make the Assets page feel solid. If the asset table becomes reliably single-click and the detail panel feels natural, continue page-by-page until Streamlit is no longer needed.
