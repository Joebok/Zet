# Governing template review UI
Status: complete
Related specification: Joe's character-pipeline UI request, 2026-10-20.

## Goal
Allow skipping analysis, restarting from current master sources, editing proposed
templates in a separate window, and understanding batch/master/pending state.
Place decisions after their evidence and add Start Front Renders at the end.

## Current behavior
`local_template_improvement.js` reloads saved records with Refresh revisions;
it never restarts compilation. `LocalTemplateRevisionService.start` implicitly
inherits the active overlay. Manual edits require a second acceptance step.
Actions precede findings/diffs, and source editing is embedded in the listing.

## Desired behavior
Skip freezes and compiles current masters without AI, accepting them for the batch.
Restart captures current masters without inherited batch edits. Save proposed
compiles a READY child without changing masters or switching batch inputs.
Corrections use a checkbox column. Version actions follow diffs, with no parent
diff listing. Status before compiled prompts explains pending and applied work.
Start Front Renders uses the existing FRONT continuation action.

## Impact analysis
Service: `zet/services/local_template_revision_service.py` (additive request flags
and revision metadata, existing storage/locks/compiler/promotion contracts).
UI: `zet/web/static/local_template_improvement.js`, `zet.css`, and integration in
`local_asset_pipeline.js`; template asset versions in `index.html` if necessary.
Documentation owners: LOCAL_CHARACTERS, DATA_MODEL, INVARIANTS, CODE_MAP, Testing.
S2 covers existing acceptance/render progression; disposable checks cover new UI
and service paths. No maintained tests or dependencies are added.

## Invariants and constraints
Frozen versions, universe ownership, queued inputs, published images, and explicit
conflict-checked master promotion are preserved. Use isolated fixtures/prepared
responses only; no normal-library writes or live inference.

## Implementation steps
### WP1 — Explicit master baseline and compilation
- Dependencies: none.
- Files/interfaces: LocalTemplateRevisionService.start/activate/detail.
- Work: add from_master/skip_analysis modes; compile manual proposals to READY;
  expose authoritative usage/promotion status and clear skip provenance.
- Acceptance: skip permits Continue without AI; restart ignores active overlay;
  saving leaves master and active version unchanged until explicit application.
- Validation: disposable isolated service checks; Python AST.
- Status: complete.

### WP2 — Review layout and separate proposal editor
- Dependencies: WP1.
- Files/interfaces: local_template_improvement.js, zet.css, index.html.
- Work: compact instructions, checkbox column, action order, popup editor,
  persistent status summary, explicit reload explanation.
- Acceptance: Save proposed refreshes diff; no implicit master write; pending
  decisions/edits and active/master scope are clear before compiled prompts.
- Validation: JS syntax and disposable browser checks at desktop/narrow sizes.
- Status: complete.

### WP3 — FRONT handoff, knowledge and validation
- Dependencies: WP1/WP2.
- Files/interfaces: local_asset_pipeline.js integration, affected docs, this plan.
- Work: reuse FRONT continuation; run approved S2 and focused disposable checks;
  update verified documentation and review final diff.
- Acceptance: bottom action has the same gate and behavior as Continue FRONT.
- Validation: `npm.cmd run test:e2e -- --grep character-to-costume`;
  `git diff --check` and final diff inspection.
- Status: complete.

## Risks and alternatives
Browser popup blockers need actionable feedback. Editors must reject saving after
batch/universe/version changes and retain drafts across polling. Current master
drift must be distinguished from the captured diff baseline. Existing partial
promotion errors remain visible and retryable.

## Progress and decisions
- Confirmed Refresh revisions only GETs stored results.
- Saving manually edited sources will synchronously compile a READY proposal;
  activation and master promotion remain separate explicit actions.
- Added read-only active/accepted usage metadata; additive flags require no
  migration. Existing compiler, storage and master promotion owners are retained.
- Popup drafts survive polling. Saves reject a changed context/viewed version;
  late GET results are ignored across mutations and version selection changes.
- Reused continuation readiness and `perform("proceed")` for the bottom action.
- Source diffs remain relative to the captured baseline; status compares current
  masters separately and reports drift. Master promotion still uses its journal.
- No significant responsibility moved, so no new ADR was needed; affected code
  map, component, data, invariant and testing documentation were synchronized.

## Validation
- `npm.cmd run test:e2e -- --grep character-to-costume`: S2 passed (20.4s with
  startup; scenario 13.3s).
- `node test-results/governing-template-review-check.mjs`: disposable private
  fixture/API/Chromium check passed, including eight-view Body/Head/Assembly skip,
  no skip AI jobs, popup save/polling, diff/action order, batch-only activation,
  explicit fixture-character promotion, unchanged project master bytes, master
  restart, selected acceptance, stale editor/active-version rejection and actual
  FRONT continuation. Desktop/800px/390px bounds passed; screenshots inspected.
- Initial disposable-check failures reflected fixture limitations: all-view
  Assembly creation lacked non-FRONT prerequisite locks; comparisons needed
  normalized source newlines; reset retains authored character edits and local job
  history; action messages can change during polling. Corrected the disposable
  setup/assertions without altering maintained tests or production behavior.
- Python AST, `node --check` for both changed browser modules, `git diff --check`
  and final diff review passed.

## Final results
Completed all three work packets. Skip/restart, compact review layout, separate
proposal editing, scope/pending status and bottom FRONT action are implemented.
Existing images, history and queued inputs remain frozen; master promotion stays
explicit. No permanent tests, dependencies, live AI calls, normal-library writes
or deployment were added. Native-device popup behavior remains unverified; blocked
popups produce an actionable message in the dashboard.
