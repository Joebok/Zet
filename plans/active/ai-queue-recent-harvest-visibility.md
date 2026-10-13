# AI Queue Recent Harvest Visibility
Status: active
Related issue/specification: [Joebok/Zet #44](https://github.com/Joebok/Zet/issues/44)

## Goal
Keep recently completed AI jobs visible in the AI Queue after refresh, including during the interval before the derived library index catches up. Preserve the original report: active, queued, and recently harvested jobs should be listed. Do not inspect or mutate production queue data.

## Current behavior
The AI Controls page fetches `/api/ai-controls` for live Ask/Running/Answer rows, then `/api/ai-controls/recent-harvests` for recent completions. The recent endpoint reads only `query_job_history` from the derived library index. `ZetApp.recent_ai_harvests()` already combines indexed results with producer-local queue receipts, but the route bypasses that method. Joe's trusted reply identifies completed ask `Ask_Render_Task_LOCAL_RENDER_20261013_130922_261771_65610fad602e4fb7b7a0f0ac2fc3bf93` and describes the refresh/autoharvester symptom. The attached empty-page screenshot is retained in ignored `test-results/issue-44-empty-ai-queue.png` (SHA-256 `C33A15EA5AC1B091F1DA433FCC1A968CEBA88E733AFA58F680024303E5F4C6B2`).

## Desired behavior
The recent-harvest list includes current local receipts even if they have not yet been indexed, while retaining indexed/archive history and the existing response shape used by the UI.

## Impact analysis
- `zet/web/app.py`: recent-harvest HTTP route and its pagination metadata.
- `zet/app.py`: existing `recent_ai_harvests` combines index rows and local receipts.
- `Docs/COMPONENTS/QUEUES.md`: document the dashboard's two sources for recent history.
- No storage schema or queue ownership changes. No permanent tests are authorized; use the existing helper validation and disposable fixture only.

## Invariants and constraints
- Use only the prepared disposable fixture; do not read the normal library or shared queue.
- Preserve queue ownership, receipt data, index authority, and current API/UI field names.
- No live models/rendering, new dependencies, or permanent test scenarios.

## Implementation steps
### WP1 — Include recent receipts in AI Queue history
- Dependencies: none.
- Files/interfaces: `zet/web/app.py`, `Docs/COMPONENTS/QUEUES.md`.
- Work: route the initial recent-harvest page through the existing ZetApp merge, preserving the paged index response metadata and UI's `items` field; document the receipt/index sources.
- Acceptance: current local receipts appear in `items` immediately after completion, indexed history remains available, and the UI contract stays unchanged.
- Validation: helper `validate --token <token>` (approved S1–S3 and `git diff --check`); inspect final diff and endpoint behavior against the disposable fixture.
- Status: complete.

## Validation
Run the helper's revision-bound validation only after committing. No new or live checks.

## Risks and alternatives
The endpoint exposes a cursor but the current AI Queue client requests only the first page. Preserve existing pagination metadata; do not broaden the UI or index contract.

## Progress and decisions
- 2026-10-13: reconciled issue #44, received the trusted ask ID/screenshot reply, and confirmed the endpoint bypasses the existing receipt/index merge. Helper evidence rejected the comment attachment because it is not the repository's pinned capture URL; downloaded the public trusted screenshot into ignored `test-results` and recorded its SHA-256. The screenshot has no supplied digest to compare against.
- 2026-10-13: updated the first recent-history page to include the existing ZetApp receipt/index merge while keeping later index cursor pages, and documented the source behavior. Validation remains pending.

## Final results
Pending implementation and validation.
