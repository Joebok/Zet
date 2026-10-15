# Minor Characters workspace

Status: local implementation complete and validated, 2026-10-15. Not deployed in this implementation pass.

## Goal and decisions

Replace the wizard dialog with universe-scoped named Minor Characters and a full-page editor. One ongoing workspace per trimmed/case-insensitive name. Inputs left; view tabs, candidates and designated-original/candidate comparison right. Comparison reference defaults to first entered, is display-only and independent of primary identity. Selection advances generation; per-view locking immediately publishes to Inventory. Front alone is sufficient. Selecting another front retains side selections/locks. Inputs affect future generation without deleting existing candidates/locks or changing submitted work. Reuse shared reconstruction/true-up; no new major-character pipeline, dependencies or permanent tests.

## Evidence and impact

Current QuickCharacterWizard records live under `_state/QuickCharacterWizard`, are terminal after publication, reorder primary references and require all three views. Reuse that store/IDs and engine; extend it through a focused MinorCharacter service and API. Existing publication must support immutable per-candidate assets and one current set association per view. Affected knowledge: architecture/code map, local characters, data model, library, invariants and ADR. Existing three E2E scenarios cover regression only; disposable service/browser journeys cover this feature.

## Luna-sized packets

1. Persistent named workspace: service over current storage; create/rename/autosave, reference identities/order/comparison picker and legacy adoption. Acceptance: one named workspace opens after reload, including published legacy sessions. Validation: disposable service/API checks.
2. Selection and locking (depends on 1): separate selected/locked mappings, selected-front generation, per-view publication/replacement and retained previous outputs. Acceptance: front-only lock and further edits; side choices survive front changes. Validation: isolated catalog/service journey.
3. List/navigation (depends on 1): Minor Characters page, name-first creation, routes and links. Acceptance: list thumbnail comes only from locked front; new/open/rename/deep-link work. Validation: disposable browser journey.
4. Editor (depends on 1-3): left inputs, right tabs/thumbnails/comparison, preview vs select vs lock, autosave and optional suggestions. Acceptance: reference switch changes display only; refresh restores workspace; small-window layout usable. Validation: browser journey/screenshots.
5. Inventory handoff (depends on 3-4): published image opens owner; other images offer create/continue; remove dialog/resume picker. Acceptance: same workspace from both entries without silent reference replacement. Validation: browser/API.
6. Documentation and verification (depends on 1-5): synchronize knowledge, record outcomes, run syntax/diff checks and existing `npm.cmd run test:e2e`; no maintained coverage expansion. Move this plan to completed after local implementation/validation. Release promotion is separate from implementation.

## Progress

- Inspected current wizard service/router/publication/UI, navigation, plan conventions and relevant architecture/component/code-map documentation. Working tree was clean at start.
- Packets 1-5 implemented locally. MinorCharacterService extends the existing engine/store; the old routes address the same ongoing service. Named records use additive version-2 fields for existing-reader compatibility, not a new catalog schema. Legacy aliases preserve old records/files. Submitted inputs remain frozen and prior reference snapshots are retained.
- Selection and per-view locking are independent; front-only locks, replacement publication, retained side selections and owner reopening work in isolated checks. Current reference-set labels include the workspace's short ID to avoid collisions with unrelated Inventory sets or a workspace's former name.
- Full-page list/editor replaces the dialog. Desktop uses inputs left and images right; view tabs/thumbnails separate preview from selection and locking. Display-only reference changes persist independently of primary identity. Autosave flushes before navigation/universe changes; missing character/phase prerequisites do not block this page.
- Disposable `python3 -B test-results/minor-character-check.py` passed named singleton creation, reference switching without analysis, selected-front side generation, per-view lock/replacement, retained side choices, in-flight input edits, reopen/adoption and legacy duplicate-name aliasing. No permanent tests added.
- Disposable browser journey passed name-first creation, autosave/rename/reopen, preview/select/lock, unlocked-front side generation, retained locks and side choices, comparison persistence, full-size links, Inventory owner/create/continue handoff and desktop/850px/640px layout. Screenshots were inspected. It exposed/fixed public candidate URL loss after reopening, narrow toolbar/upload containment, and catalog set-name collisions after name reuse. Fixture state was reset between complete runs.
- Approved `npm.cmd run test:e2e` passed all 3 existing scenarios (26.9s) before final focused hardening. Final syntax/diff/service/browser checks and documentation synchronization are being completed. No live rendering, normal-library migration, production publication or deployment has been performed in this implementation pass.

## Final results

All six packets are complete locally. The wizard dialog and script are retired; the ongoing Minor Characters service, API, list/editor, selected/locked separation and Inventory handoffs are implemented. Affected architecture, component, data, invariant and code-map documentation is synchronized; ADR 0014 records the durable design. Original non-UTF8 local-character documentation bytes were preserved.

- Final `python3 -B test-results/minor-character-check.py`: passed. Additional checks cover a deliberately delayed advisory review while a side render completes, source-style reference ordering independent of display choice, stable URLs after replacing all references, legacy duplicate aliases and selected-front/per-view publication. A transient Windows read/atomic-write collision observed during fast polling was corrected by sharing per-workspace read/write locks; global workspace scans occur outside individual workspace locks.
- Final disposable browser journey: passed with real loaded-image assertions for both comparison images and the chosen reference's stable ID. Inventory owner/create/continue handoffs, first/optional views, custom feedback, preview/select/lock, autosave/rename/refresh, locked list thumbnail and desktop/850px/640px screenshots passed; screenshots inspected and no page errors recorded. Fixture processes stopped afterward.
- Advisory review runs in a separate background lane and cannot hold the render queue or gate selection/locking. Candidate inputs remain immutable for submitted work; comparison choice does not trigger analysis. No automatic correction loop or history-management UI was added.
- Approved `npm.cmd run test:e2e`: all 3 scenarios passed in final full runs (26.7s). The final narrow workspace-lock helper adjustment was also verified by the complete disposable service journey. Python AST, JavaScript syntax and `git diff --check` passed.
- No maintained tests, production dependencies, live model/render calls, normal-library changes, commits, pushes or deployment were added/performed for this implementation. Existing reconstruction/true-up services and catalog schema remain in use.
