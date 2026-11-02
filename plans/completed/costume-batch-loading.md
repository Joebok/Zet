# Costume batch loading recovery
Status: complete

## Goal and verified behavior
Restore existing Costume-Dressing images and empty Final slots while retaining
per-view prerequisite gates. The hosted detail API returns all 38 Draft images,
eight views, and Final FRONT eligibility for batch 937aebc986f842d28be76ca6f456fb8b.
The shared controller increments its detail request fence on a mode change,
discarding a pending mode-independent response without starting another load.
Reactivation also skips recovery when context is unchanged after deactivation.

## Impact and constraints
Only the shared browser controller and its UI component documentation need edits.
No storage/schema, lock, reference-selection, backend, or queue changes are needed.
Existing unrelated working-tree changes, including edits in this controller, must
be preserved. Relevant owners: Docs/COMPONENTS/DASHBOARD_UI.md,
Docs/COMPONENTS/LOCAL_CHARACTERS.md, Docs/INVARIANTS.md, Docs/CODE_MAP.md.
The existing backend already enforces Final prerequisites per view.

## Luna sized work packets
### WP1 — Preserve and recover batch detail loads
- Dependencies: none.
- Files: zet/web/static/local_asset_pipeline.js.
- Work: retain mode-independent pending detail on quality changes; resume loading
  when reactivating an interrupted page; distinguish loading/failure from absence.
- Acceptance: changing quality while loading still displays the chosen batch;
  reopening after interrupted loading recovers; context/request fences remain.
- Validation: disposable Chromium checks using captured read-only batch detail;
  node --check zet/web/static/local_asset_pipeline.js.
- Status: complete.

### WP2 — Validate and document
- Dependencies: WP1.
- Files: Docs/COMPONENTS/DASHBOARD_UI.md and this plan.
- Acceptance: 38 Draft images remain visible, eight Final view galleries and empty
  selections display, only ready Final views enable generation.
- Validation: disposable delayed-response browser checks; approved S2 via
  npm.cmd run test:e2e -- --grep character-to-costume; git diff --check.
- Status: complete.

## Validation and limits
No permanent tests or live model calls. Production data is read-only. Local
changes require deployment before changing the hosted page; no deployment or
restart is authorized by this fix.

## Observed validation and final results
- Read-only hosted inspection confirmed 38/38 Draft images and Final FRONT
  eligibility. Waiting for the original detail request without changing modes
  eventually displayed the Draft images; no library recovery was needed.
- `node test-results/check-costume-loading.cjs` reproduced the cancelled-load bug
  with the prior fencing behavior. The fixed controller passed delayed-load mode
  changes, all eight Final selection cards and 64 empty candidate slots, only
  FRONT generation enabled, switching back to all 38 Draft candidates, interrupted
  page reactivation and explicit retrieval-failure feedback. The disposable
  harness uses captured detail and local templates/scripts; it makes no live
  model calls or production writes. Its first runs exposed harness stubbing,
  line-ending and selector errors, which were corrected before the passing run.
- `npm.cmd run test:e2e -- --grep character-to-costume` passed all four approved
  scenarios (45.6s). The repository wrapper did not forward the grep filter;
  the full approved baseline ran, including S2 (10.6s).
- JavaScript syntax, `git diff --check` and final diff inspection passed.
- Updated the UI component owner. Architecture, data, invariants, workflow and
  code-map responsibilities are unchanged; no ADR or further knowledge edits
  are needed. Existing unrelated edits were preserved, including those in the
  shared controller. No new maintained tests or dependencies were added.
- Hosted deployment/restart remains a separate action requiring authorization.
