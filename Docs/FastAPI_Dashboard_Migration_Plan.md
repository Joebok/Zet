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

### Milestone 3 - Prompt Review

- Add Prompt Review page.
- Show full prompt with readable scrolling.
- Add search and copy.
- Add condensed prompt viewer.
- Add local test render button and image preview.
- Add Approve / Fail.
- Add Previous / Next across review tasks.

### Milestone 4 - Render Review

- Add Render Review page.
- Show candidate image, locked image, prompt/render metadata.
- Add Promote to LOCKED.
- Add fail paths:
  - Fail to Render
  - Fail to Regenerate
- Add Previous / Next across render-review tasks.

### Milestone 5 - AI Controls

- Replace AI Controls in the FastAPI UI.
- Show queue counts and tables.
- Show process status and controls.
- Show monitor tests and responses.
- Show proxy stop/resume controls.
- Show manual render task counts.
- Move remaining AI Controls aggregation out of Streamlit-only code where appropriate.

### Milestone 6 - Pipeline Controls

- Replace Pipeline Controls in the FastAPI UI.
- Show project automation settings.
- Edit safe config toggles.
- Show pipeline stage/actor/worker table.
- Support batch render reset.

### Milestone 7 - Template Editor

- Replace Template Editor.
- Move script-helper behavior behind service/API boundaries where useful.
- Preserve view-specific section editing.

### Milestone 8 - Merge Render Console

- Fold the existing Render Console into the main Zet web app.
- Preserve paste/drop/file-picker behavior.
- Preserve task navigation.
- Retire separate Render Console launcher once merged.

### Milestone 9 - Retire Streamlit

- Confirm the FastAPI UI covers all dashboard functions.
- Update launch scripts to start the FastAPI UI as the main dashboard.
- Move Streamlit dashboard to legacy/diagnostic status or remove it.
- Update docs and process controls.

## Near-Term Recommendation

Start with Milestone 1 and make the Assets page feel solid. If the asset table becomes reliably single-click and the detail panel feels natural, continue page-by-page until Streamlit is no longer needed.
