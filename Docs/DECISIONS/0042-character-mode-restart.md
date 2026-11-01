# 0042 — Character batch restart is mode-scoped

Status: accepted locally, 2026-11-01.

The character dashboard offers Draft and Final boards in the same batch. The
former whole-batch Re-run action submitted renders and did not match the desired
operation of preparing a clean board for later work.

Re-start clears candidates, selections and locks only in the displayed mode after
a preview and state/source fingerprint check. It preserves the other board and
published Inventory copies, retains written observations, fences stale evaluations,
and never submits renders. When requested, Recompile adopts the current masters
through the existing skip-improvement workflow; Assembly compiles directly.
Phase-change source snapshots refresh for the chosen mode. Assembly and Dressing
continue to resolve their current upstream locks when preparing each new render.

`LocalCharacterBatchRestartService` owns the transition; the shared local router
and dashboard expose it. Existing regeneration APIs remain available. Validation
and known limits are recorded in the character pipeline UI plan.
