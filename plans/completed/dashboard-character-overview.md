# Dashboard character overview
Status: complete

## Goal and current behavior
Mount the standalone Local Character Overview in the dashboard as Overview. Move
the existing onboarding page to Assets → Character Overview. Remove per-card
task buttons and standalone header links. Autogenerate currently sequences legacy
Head-Image and leaves Assembly's head source at its legacy default.

## Impact and constraints
Owners: overview service, dashboard template/controller/styles, standalone route;
documentation: Dashboard UI, Local Characters and code map. Preserve existing
working changes, universe isolation, locked images, job ownership and human review
pauses. No dependencies, production writes, live AI calls or permanent new tests.

## Work packets
### WP1 — Mount overview and navigation
- Files: index.html, zet.js, local_character_overview.js, zet.css, app.py.
- Dependencies: none.
- Work: native dashboard page, scoped cards, lifecycle polling, legacy redirect.
- Acceptance: Overview opens cards; Assets begins with Character Overview; no card
  task controls or standalone header navigation; universe-bound requests/images.
- Validation: JavaScript syntax; disposable isolated browser inspection.
- Status: complete.

### WP2 — Edited head automation
- Files: local_character_overview_service.py.
- Dependencies: none.
- Work: Head-Image Edit stage, explicit Assembly source, legacy job handling and
  compatible batch reuse without replacing existing locks.
- Acceptance: new/resumed automation uses edited heads and respects review gates.
- Validation: disposable isolated service checks; approved E2E baseline.
- Status: complete.

### WP3 — Verify and document
- Files: affected component docs, code map, this plan; existing S1 navigation helper.
- Dependencies: WP1/WP2.
- Acceptance: relevant checks pass, final diff reviewed, knowledge synchronized.
- Validation: npm.cmd run test:e2e; git diff --check.
- Status: complete.

## Validation and limits
S1 covers setup navigation; S2 covers legacy Assembly/Dressing publication. Neither
proves new overview automation or live artistic quality. Use disposable prepared
checks for changed contracts; do not add maintained scenarios.

## Progress and decisions
- Mounted a native page/controller with scoped CSS; removed the standalone template
  and redirected its URL while retaining query context. Existing setup route IDs
  remain valid; the S1 helper now opens Assets → Character Overview on desktop.
- Real isolated creation exposed a pre-existing costume-qualified Assembly lookup
  bug. Assembly calls now omit costume, and only Dressing uses costume qualification.
- New jobs freeze edited-head intent. Legacy recovery cancels only owned work
  through existing fences and rechecks locks. Legacy Assembly locks require an
  explicit unlock; existing Dressing locks remain complete. Downstream reuse checks
  head ancestry rather than silently adopting old batches.
- Preserved unrelated bulk-lock edits and documentation present during this work.

## Final results
- `npm.cmd run test:e2e`: all four approved scenarios passed (final: 44.1 seconds;
  earlier: 41.1 seconds). A rerun initially found the disposable server on port
  8765; stopped that owned fixture server and reran successfully.
- Disposable Chromium: desktop/390px mount, Assets setup navigation, removed card
  task buttons, universe-scoped POST, duplicate-submit fencing, local feedback,
  legacy redirect and zero page errors passed. Screenshots inspected; corrected
  inherited grid styling that wrapped the generation label.
- Disposable service checks: real Head-Image Edit creation and human-review pause,
  edited Assembly snapshots, compatible Assembly/Dressing reuse, preserved legacy
  locks, new stage order and legacy job recovery passed, using prepared images and
  isolated library/queue storage.
- Changed Python AST, JavaScript syntax and `git diff --check` passed. Final diff
  reviewed. No new maintained scenarios/dependencies or live AI/render calls.
- Updated Dashboard UI, Local Characters and code map. Live artistic quality and
  physical-device behavior remain unverified; no implementation blocker remains.
