# AI Queue Display Details
Status: complete
Related issue/specification: none

## Goal
Show meaningful workflow targets and render modes in the AI Queue, display creation time to the minute, and make the job ID available through a copy link. Preserve the existing request cadence and queue ownership.

## Current behavior
`AIQueueQueryService` builds rows from existing ask manifests and compact retained-job records. Character jobs retain character, phase, costume slug, view, and their frozen render request. Narrative queue manifests retain stable IDs but not authored titles. `ai_queue.js` polls the existing endpoint every two seconds and displays task type where users need target/mode information.

## Desired behavior
Character rows include a readable workflow, costume, and view. Narrative rows use captured story, scene, and target titles. Mode shows Draft or Final when available. Created shows local date and time to the minute. The ID is only exposed by a copy control. Older Narrative jobs without title metadata use `Narrative / Target via status link`.

## Invariants and constraints
Derive labels only from metadata already read during queue discovery. Do not add requests, filesystem reads, queue migrations, or polling cadence changes. Keep durable navigation IDs, ownership and request data intact. Recent Harvests remains unchanged.

## Implementation steps
### WP1 — Capture Narrative display titles
- Dependencies: none.
- Files/interfaces: `narrative_generation_service.py`, `narrative_proxy_service.py`.
- Work: Snapshot story, scene, and target titles with each new Narrative job. Carry the snapshot to child image jobs and upscales, then include the display path in published manifests.
- Acceptance: New Narrative asks contain the captured title path and retain the same navigation IDs.
- Validation: Disposable inspection of generated manifests and existing S3 workflow.
- Status: complete.

### WP2 — Project compact display metadata
- Dependencies: WP1.
- Files/interfaces: `ai_queue_metadata_service.py`, `ai_queue_query_service.py`, `storage_health_service.py`.
- Work: Project titles, costume, view, and mode from already-read manifests into cached rows and recovery journals. Format display values without changing workflow links or filters.
- Acceptance: Active, retained, receipt, and stale-storage rows preserve available display metadata without additional I/O during queue polling.
- Validation: Disposable metadata projection and queue API checks.
- Status: complete.

### WP3 — Update Queue UI and component documentation
- Dependencies: WP2.
- Files/interfaces: `ai_queue.js`, `index.html`, `AI_JOBS.md`.
- Work: Replace Task with Mode, add copy-only ID, format Created to the minute, announce copy outcome, and document the display contract.
- Acceptance: Queue columns and copy link work by pointer and keyboard. Existing status links and Recent Harvests remain functional.
- Validation: Approved fast E2E baseline, disposable browser checks, JavaScript syntax and diff checks.
- Status: complete.

## Validation
Run `npm.cmd run test:e2e`, focused disposable checks for new fields and clipboard interaction, `node --check` on changed JavaScript, and `git diff --check`.

## Progress and decisions
Older Narrative rows use their status link when they lack titles. No title backfill or queue migration is planned.

## Final results
Implemented queue display metadata, title capture, minute-only local timestamps, and copy-only job IDs. `npm.cmd run test:e2e` passed all four approved fast scenarios (41.4 seconds). Focused metadata projection checks passed for Narrative titles and Draft/Final modes. Python compile checks, `node --check zet/web/static/ai_queue.js`, and `git diff --check` passed. Disposable mouse/keyboard clipboard checks were not run separately.
