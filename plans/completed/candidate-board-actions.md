# Candidate Board action alignment
Status: complete
Related issue/specification: user request in Codex conversation

## Goal
Align Character Asset Container and Narrative candidate-board actions with one shared toolbar and behavior: Draft 1/4 (blue), Final 1/4 (green), Delete Drafts (red outline), and Delete Non-Selected (solid red/white). Remove Narrative duplicate render-count, Generate Draft/Final and Refresh controls. Delete Non-Selected preserves the currently selected or locked candidate and clears other slots.

## Current behavior
`candidate_board.js` shares slot actions and card markup, but Character places four render buttons in `index.html` and Narrative duplicates render actions in two locations plus a count input and Refresh. Narrative already has protected Draft deletion preview/commit. Character Asset Containers have only per-slot clear actions and no bulk clear route. Active character boards are the five pipelines hosted by Character Asset Container.

## Desired behavior
One shared toolbar renderer and consistent styling/dispatch affordance on both board types. Bulk deletion previews affected selection/lock effects and server rechecks current state before commit. Selected or locked slots are retained; active render slots cannot be cleared. Delete Drafts retains its existing Narrative protected preview behavior.

## Impact analysis
- UI: `candidate_board.js`, `character_asset_container.js`, `narrative.js`, `index.html`, `narrative.css`.
- API/domain: `character_asset_container_router.py`, `character_asset_container_service.py`; Narrative service behavior may need a selected/locked preservation option for non-selected cleanup.
- Knowledge owners: `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, `Docs/COMPONENTS/NARRATIVE.md`, `Docs/COMPONENTS/DASHBOARD_UI.md`, `Docs/CODE_MAP.md`.
- Tests: existing approved E2E baseline only; no permanent scenario additions.

## Invariants and constraints
Preserve slot membership and ownership, revision fences, lock integrity, active-job ownership, and state-bound protected-effect confirmation. Do not add dependencies or permanent tests. Keep API and service business logic out of the web layer.

## Implementation steps
### WP1 — Shared toolbar and matching controls
- Dependencies: none.
- Files/interfaces: shared renderer in `candidate_board.js`; Character/Narrative adapters and board template/styles.
- Work: render one row with four generation buttons and two cleanup buttons; route generation through existing workflow calls; remove duplicate Narrative controls.
- Acceptance: both board types expose identical labels/order and colors, in one wrapping-capable toolbar row.
- Validation: inspect rendered markup, `node --check` changed JS, `git diff --check`.
- Status: complete.

### WP2 — Protected Delete Non-Selected action
- Dependencies: WP1.
- Files/interfaces: Character Container service/router and Narrative generation service/router if needed, shared UI confirmation dispatch.
- Work: preview protected selected/locked effects, fence the commit to preview token/revision, preserve the selected/locked candidate, clear eligible remaining slots, refuse active work.
- Acceptance: both workflow APIs preserve selected/locked slots, clear other eligible slots, and reject stale/changed preview commits.
- Validation: source-level contract inspection and existing approved baseline; no new maintained tests.
- Status: complete. Character bulk deletes use a shared preview/commit service with a complete container-state token and revision; Narrative non-selected deletion uses a record-state token. Active affected slots are refused, and selected/locked slots are preserved by Non-Selected cleanup.

### WP3 — Documentation and closeout
- Dependencies: WP1–WP2.
- Files/interfaces: affected component docs, code map, this plan.
- Work: record the shared toolbar/action behavior and observed verification; archive plan.
- Acceptance: docs reflect current owners and validation limits.
- Validation: final diff review and `git diff --check`.
- Status: complete.

## Validation
`node --check` passed for the four changed JavaScript modules; Python AST parsing passed for both changed services and routers; `git diff --check` passed. The approved E2E baseline was not run. No permanent tests or scenarios were added.

## Risks and alternatives
Bulk cleanup must remain atomic relative to board revision and must never silently remove selected/locked images. If Narrative's current draft-delete endpoint is not naturally reusable for non-selected cleanup, add a narrowly scoped service action rather than deleting candidates through repeated per-slot HTTP calls.

## Progress and decisions
Initial inspection found shared card markup but duplicated board-level controls. Narrative Draft deletion already uses protected-effect previews; Character does not have a bulk preview/commit path.

Implemented one renderer in `candidate_board.js` and consumed it from both adapters. Character Draft deletion includes per-effect selected/locked approval; Character and Narrative Non-Selected deletion preview exact candidates and keep selected/locked candidates. Character commits also require the preview revision. Removed Narrative's duplicated render buttons, count input, and Refresh button from the generation panel. Bumped static module/style cache keys. Updated the Character and Narrative component docs and code map.

## Final results
Both candidate board types present the same six controls and colors. Non-Selected cleanup preserves selected/locked candidates; affected active work blocks the cleanup. Syntax, AST, and diff checks passed. E2E behavior and visual layout were not exercised in a browser.
