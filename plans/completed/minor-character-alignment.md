# Minor Character alignment and true-ups
Status: complete
Date: 2026-10-15
Related specification: Joe's approved plan in this chat.

## Goal and desired behavior
Style reconstruction/refinement precedes independent front/three-quarter/profile alignment from the selected style image. Select an aligned view before true-ups. Alignment images never lock. Replace iteration history with four current slots per stage, same-slot prior-selection carry, and one prompt-state-only undo per board. Comparison arrows loop through the designated original and style candidates, or original/selected style/other selected views. Main Minor Characters navigation opens the list.

## Initial behavior and impact
MinorCharacterService extends the wizard engine, stores version-2 sessions, and allocates historical iteration boards. Shared reconstruction composes character/style/view context together; angled views depend on selected front. The page displays iteration cards and a separate All Minor Characters button. Existing locks and original-pixel analysis-only reconstruction policy must survive.

## Packets
- WP1 — Board state. MinorCharacterService: workflow version, current boards, selection, revision, undo. Initialize fresh workspaces only; do not migrate or load retired workspace records. Validate disposable serialization. Status: complete.
- WP2 — Generation/review. Minor-character prompt composition and wizard integration: style-only initial reconstruction, one-reference short view prompts, scoped true-ups and advisory stage-aware reviews. Validate frozen prepared requests. Depends WP1. Status: complete.
- WP3 — Refinement/undo. MinorCharacterService: same-slot carry, one undo snapshot, persisted feedback/findings/choices, empty boards on undo, late-result fencing. Validate disposable transitions/reload/failures. Depends WP1–2. Status: complete.
- WP4 — API/publication. Minor router and publication guard: stage actions and expected board revision; enforce selection and lock gates at the backend boundary. Validate disposable API calls. Depends WP1–3. Status: complete.
- WP5 — UI. Minor JS/template/CSS: stage tabs, continue/undo, current slots, prior badge, looping comparison arrows. Validate syntax and isolated browser journey. Depends WP4. Status: complete.
- WP6 — Navigation/docs/regression. Main navigation opens list; preserve deep links/history/Inventory handoffs. Update affected knowledge and ADR, run npm.cmd run test:e2e, syntax checks, git diff --check and inspect final diff. Depends WP5. Status: complete.

## Constraints and defaults
One agent, no new dependencies/permanent tests/live renders/deployment. Original source pixels remain analysis-only in universe reconstruction. Private frozen source snapshots may remain for reproducibility but discarded images cannot be restored to slots. Existing Inventory locks remain immutable. Re-selecting style affects new alignment, not existing view boards. Undo is one level per board, without redo or restored images. Carrying alignment never makes it lockable.

## Validation
Use disposable private storage, prepared model/render responses, and browser checks for uncovered workflow contracts. Existing S1–S3 are regression coverage only. Artistic acceptance remains Joe's. Python 3 verified via python3 before implementation.

## Progress and decisions
- Planning inspected Docs/INDEX, CODE_MAP, component/data/invariant/testing docs and authoritative services/UI. Working tree initially clean.
- Affected documentation owners: LOCAL_CHARACTERS, PROMPTS, DATA_MODEL, INVARIANTS, ARCHITECTURE, CODE_MAP; new ADR supersedes historical iteration/front-anchor rules.

## Final results
- Implemented stage prompts/selection gates, current boards, same-slot prior-selection carry, one-level recipe/supporting-state undo, revision and membership fencing, looping comparison controls and main-list navigation.
- New responsibility owner: zet/services/minor_character_workflow_service.py, shared by MinorCharacterService and its existing wizard engine. Router/UI invoke focused backend actions; publication independently rejects alignment images.
- User clarification removed all adoption/migration work. Retired workspace files are untouched and excluded from discovery; no backwards compatibility is promised.
- python3 -B test-results/alignment-check.py passed expanded prepared-response service/API checks: initial style reconstruction, selected-style-independent views, short prompts/one reference, frozen style intent, alignment lock rejection, generated true-up publication, repeated same-slot carry, undo/replay/alternate corrections, current-only image access, failed-review continuation, stale revisions and late results. Fixtures use private library/queue/index state.
- node test-results/alignment-browser.mjs passed Chromium journey, including gates, selection/carry, true-up lock controls, undo/choices/reload, carousel wrapping, image loading, list navigation and edits during delayed autosave. No page errors. Desktop/800px screenshots inspected.
- npm.cmd run test:e2e: all 3 approved scenarios passed (27.7s); no permanent tests added. Earlier baseline also passed (29.2s).
- Changed Python files passed AST parsing; changed dashboard scripts passed node --check; git diff --check passed. Final diff inspected for unintended changes.
- Updated affected architecture/component/prompt/data/invariant/code-map/testing knowledge and ADR 0015; marked preceding ADR rules superseded.
- No live generation, production deployment, new dependencies, or external writes. Joe still judges artistic results.

- During validation, a delayed autosave exposed editing/selection response ordering; pending edits now retain the current board revision and the disposable browser journey verifies the fix.
