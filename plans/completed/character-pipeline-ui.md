# Character pipeline UI and restart improvements
Status: complete

## Goal and constraints
Implement the approved character pipeline UI and mode-specific restart plan for all five pipelines. Preserve universe isolation, other-mode data, lock ownership, and attempt fencing. Do not dispatch renders on restart. No new permanent tests or dependencies.

## Work packets
- WP1 — Mode-specific restart service: clear only the selected mode; preserve other-mode state, observations, and Inventory. Complete; isolated checks covered Draft and Final locks.
- WP2 — Restart preview and confirmation APIs: revalidate affected locks and sources; refresh upstream inputs; optionally adopt current masters. Complete; isolated service and route checks passed for all five pipelines.
- WP3 — Shared batch toolbar and creation modal: name on creation, action menu, restart confirmation. Complete; disposable browser checks passed.
- WP4 — Consolidate live status and generation controls. Complete; success acknowledgements expire and errors remain visible.
- WP5 — Image-first view sections and action groups: gallery, references, collapsed tools, Stage menu, remove seed control, danger styling. Complete; desktop and narrow browser checks passed.
- WP6 — Selected image review navigation: read-only mode, keyboard and focus behavior. Complete; disposable browser check passed.
- WP7 — Remove prompt improvement package export while retaining observations; update affected documentation and ADR. Complete.

## Validation
Run disposable isolated checks, focused existing S2 and approved fast E2E baseline, syntax checks, `git diff --check`, and review the final diff. No live rendering.

## Progress and decisions
The existing batch rerun dispatches render work; restart requires a separate action. Mode-specific sources, lock ownership and shared template revisions require careful coordination.

Package export UI, route and assembly code have been removed; observation code remains. The creation dialog now includes an optional name persisted by the adapters. Success messages clear after five seconds; Draft delete actions use danger styling; the Stage menu is overlaid and placed before Post Render Adjustments. View galleries default open, the seed selector is removed, and the per-view Recompile setting is scoped to Regen view. Selected thumbnails open a viewing-only sequence with arrow navigation. These UI changes still need disposable browser validation. WP1 and WP2 have not been implemented; the existing Re-run batch action still queues renders. WP3–WP6 remain incomplete, including the grouped batch controls and full image-first ordering.

The approved fast E2E baseline passed all four scenarios (43.1 seconds). These scenarios do not specifically exercise the new dialog or selected-image viewer. JavaScript syntax, Python AST parsing, and `git diff --check` passed.

Follow-up: the shared view gallery now precedes reference images and the render tools are collapsed; generation controls sit beside the batch status and occasional batch actions are grouped. A read-only `restart-preview` API and `LocalCharacterBatchRestartService` preflight identify active work, current mode locks, upstream inputs and a state/source fingerprint. Disposable fake-workflow checks covered lock reporting, state-token changes and active work. The destructive transition, confirmation UI, and recompile integration are not yet implemented; Re-run remains unchanged and queues renders. Source refresh and confirmation preflight need isolated end-to-end verification before use.

The approved fast E2E baseline passed again after the follow-up (4 scenarios, 44.9 seconds). JavaScript syntax, Python AST and `git diff --check` passed. The current code map contains invalid UTF-8 and could not be updated with the normal patch tool; preserve its encoding and update it when completing the remaining work.

Joe corrected the code-map encoding; the S1-S4 sentence is consistent with Testing.md and was preserved. `LocalCharacterBatchRestartService.clear_mode` now provides an internal, preview-fenced mode-clearing transition. It is deliberately not exposed through the router while source-refresh and recompile preparation remain incomplete; it needs isolated validation before integration. The code map now identifies the service and its incomplete boundary.

A disposable fake-store check exercised Final-mode clearing, preservation of the Draft selection and human observations, stale AI observation fencing, removal of the affected local image, and lock clearing. It does not verify real catalog or cross-process failure recovery. The approved fast suite passed all four scenarios (43.8 seconds); the requested grep argument was not applied by the repository runner, which ran the full baseline. Syntax and diff checks passed.

## Final results
Re-start now uses a preview and confirmation, validates source and state fingerprints, refreshes locked phase sources, optionally accepts current masters, clears the selected mode and stays idle. Assembly and Dressing resolve their upstream locks when preparing new renders. Existing Re-run endpoints remain for compatibility. The shared UI has the requested modal, status arrangement, image-first views, collapsed render tools, and selected-image review.

The approved fast E2E baseline passed all four scenarios (44.7 seconds). Isolated service checks covered current-master compilation on all five pipelines; a real Draft-lock route check covered stale confirmation rejection and clearing; a real Final-lock check verified preservation of published Inventory and the Draft board. Disposable Chromium checks covered the creation modal, selected-image arrow navigation, collapsed tools, Stage height at desktop and narrow widths, and restart confirmation with no render submission. The first isolated Body check succeeded functionally but its temporary-directory cleanup failed because the fixture changed the working directory; the corrected checks completed successfully. The regression runner initially found the isolated browser server still using port 8765; its owned process was stopped and the rerun passed. No live models, normal-library writes, permanent tests, or dependencies were added. Physical touch interaction and cross-process failure injection remain unverified.
