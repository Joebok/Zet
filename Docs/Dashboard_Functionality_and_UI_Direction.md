# Zet Dashboard Functionality And UI Direction

## Purpose

This document captures what the dashboard does, what has moved to the FastAPI web UI, and what remains legacy or deferred.

The backend is service-oriented and remains the source of truth. Dashboard actions call Python service methods through `ZetApp`, `AssetRef`, or focused services. The main dashboard has moved to FastAPI plus HTML/CSS/JavaScript so high-frequency workflow screens behave like normal web pages.

## Current Primary Dashboard

The primary dashboard is:

```text
zet/web/app.py
```

Launch it with:

```text
dashboard.bat
```

or:

```text
run_zet_web.bat
```

The FastAPI dashboard currently covers:

- `Assets`
- `Prompt Review`
- `Render Review`
- `Render Console`
- `AI Controls`
- `Pipeline Controls`

The Template Editor is intentionally deferred while the body-reference authoring workflow is reconsidered.

## Retired Dashboards

The old Streamlit dashboard and standalone Render Console have been retired. The FastAPI dashboard in `zet/web/` is the only supported dashboard surface.

Do not add new workflow functionality to the retired surfaces.

## Assets Page

The Assets page is the primary process overview.

It shows:

- asset table
- selected asset summary
- candidate image
- locked image
- raw asset JSON
- derived paths
- housekeeping `_stage.txt`
- housekeeping `_history.log`

Asset table quality-of-life behavior:

- `pipeline_stage` displays a camera marker when a prompt review or render review has an image ready.
- Row selection drives the detail panel.
- The stage column is now plain text, not a browser link, because Streamlit `LinkColumn` opened new tabs.

Current issue:

- Row selection can require two clicks. The first click may leave or reset the selected detail row to `asset_id = 1`; the second click selects the desired row.
- This appears to come from the interaction between `st.dataframe(on_select="rerun")`, session-state fallback selection, and Streamlit's rerun model.
- This is not a backend problem. It is a UI-framework fit problem.

Asset page buttons:

- `Open Prompt Review`
- `Stage AI Ask`
- `Run Current Worker`
- `Run Housekeeping`
- `Retry AI`
- `Regenerate`
- `Promote to LOCKED`

Most of these call backend services through `AssetRef`.

Dashboard-local logic on this page:

- building display rows with `asset_to_row`
- detecting whether a review image is ready with `review_image_ready`
- converting a dataframe selection event into an asset id
- choosing fallback selected asset behavior
- formatting worker poll summaries
- showing action messages after reruns

## Prompt Review Page

Prompt Review is an active workflow page for:

```text
pipeline_stage = PROMPT_REVIEW
actor = HUMAN_AGENT
```

It shows:

- prompt path
- prompt condense status
- condensed prompt popover/text area
- full prompt viewer
- search within prompt
- copy prompt button
- latest local test render
- Generate Local Test Image button
- Approve button
- Fail button
- Previous / Next navigation across prompt-review assets

Backend calls:

- `PromptReviewService.get_context`
- `PromptReviewService.generate_local_test_render`
- `PromptReviewService.approve`
- `PromptReviewService.fail`

Dashboard-local logic:

- HTML prompt viewer and copy button
- prompt search highlighting
- prompt review navigation state
- Streamlit session/query-param coordination after approve/fail

Planned source-attribution and source-edit routing for compiled prompt text is tracked in:

```text
Docs/Prompt_Source_Attribution_and_Editing_Plan.md
```

## Template Editor

The Template Editor inspects and edits prompt template sections.

It uses helper functions from:

```text
Scripts/Template_Section_Editor.py
```

It handles:

- loading prompt task bundles
- selecting a pipeline
- selecting a view when a bundle has view-specific sections
- editing section text
- saving template sections

This page is still more script-helper driven than service driven.

## AI Controls

AI Controls is both an operations page and a status page.

Controls:

- Harvest AI Answers
- Stop Proxy
- Resume Proxy
- Send Monitor Test
- Start / Stop / Restart manageable local processes

Status areas:

- process table
- proxy stop state
- Render Console link
- manual ChatGPT render task count
- manual render task table
- queue counts
- Ask table
- Claimed table
- Answer table
- Failed table
- monitor test request table
- monitor response table

Backend/service calls:

- `app.harvest_ai_answers`
- `app.activate_proxy_stop`
- `app.resume_proxy_stop`
- `app.issue_monitor_test`
- `app.process_statuses`
- `app.start_process`
- `app.stop_process`
- `app.restart_process`
- `app.queue_snapshot`
- `app.list_monitor_responses`

Dashboard-local logic:

- filtering manual render asks out of the queue snapshot
- formatting process rows
- formatting monitor response rows
- reading monitor request folders directly for request display
- computing and displaying queue counts
- constructing the Render Console URL

Most queue state is now exposed by services, but AI Controls still owns some presentation-side aggregation and direct filesystem display.

## Pipeline Controls

Pipeline Controls shows project settings and character/phase pipeline definitions.

It can edit safe project config values:

- `PromptCondense.Enabled`
- `PromptCondense.Model`
- `PromptCondense.PromptFile`
- `LocalRender.AutoQueueAfterCondense`
- `LocalRender.Preset`
- `AIHarvest.AutoEnabled`
- `AIHarvest.IntervalSeconds`
- `Render.Backend`

It shows `Pipelines.json` as a read-only table:

- pipeline
- stage order
- actor
- worker
- current asset count at each stage

Batch action:

- Set all assets in a selected pipeline back to `RENDER`
- Skip locked assets by default
- Skip upstream/not-render-ready assets rather than erroring
- Clear stale queue items and old render outputs for affected assets
- Stage fresh render asks

Backend calls:

- `PipelineControlService.snapshot`
- `PipelineControlService.save_automation_settings`
- `AssetService.reset_pipeline_assets_to_render`

## Render Console

The Render Console is already a separate FastAPI/HTML app:

```text
zet/render_console/
```

It handles manual ChatGPT render tasks from the filesystem AI queue.

Important proven behavior:

- conventional browser UI
- task-to-task navigation
- prompt display
- image paste/drop/file picker
- save answer image back to queue
- fail task

This has been smoother for the manual render workflow than forcing everything through Streamlit.

## Dashboard Direction

The Streamlit assessment phase is complete. The FastAPI dashboard is now the supported workflow console for assets, prompt review, render console, image review, AI controls, and pipeline controls.

Recommended direction:

1. Add new workflow pages to `zet/web/`.
2. Add JSON endpoints that expose service-backed state instead of putting workflow logic directly in browser code.
3. Move dashboard-local aggregation into services when it is not purely display formatting.
4. Keep the working backend as the center of gravity.

## Candidate API Surface

Near-term API endpoints could include:

```text
GET  /api/assets?character=...&phase=...
GET  /api/assets/{asset_id}
POST /api/assets/{asset_id}/stage-ai-ask
POST /api/assets/{asset_id}/run-housekeeping
POST /api/assets/{asset_id}/retry-ai
POST /api/assets/{asset_id}/regenerate
POST /api/assets/{asset_id}/promote-to-locked

GET  /api/prompt-review/tasks
GET  /api/prompt-review/{asset_id}
POST /api/prompt-review/{asset_id}/approve
POST /api/prompt-review/{asset_id}/fail
POST /api/prompt-review/{asset_id}/local-test-render

GET  /api/ai/queue-snapshot
POST /api/ai/harvest
POST /api/ai/stop
POST /api/ai/resume
POST /api/ai/monitor-test

GET  /api/pipeline-controls
POST /api/pipeline-controls/project-settings
POST /api/pipeline-controls/reset-to-render
```

The Render Console already proves the pattern.

## Current Cleanup Candidates

Keep these out of `zet/web/app.py` when convenient:

- `review_image_ready`
- manual render ask filtering/counting
- monitor request folder formatting
- queue count summary
- selected asset fallback behavior
- prompt-review navigation list

Add service-level snapshots for:

- Assets page overview
- AI Controls overview
- Prompt Review task list
- Render Review task list

Those snapshots would be usable by Streamlit today and a FastAPI frontend later.
