# 0005 — Narrative dashboard and legacy scene retirement
Status: accepted
Date: 2026-10-12

## Context
Scene Builder, its local batches, and Narrative had separate authoring and render
lifecycles. The approved plan makes Narrative the dashboard story workflow and
migrates the 28 authored First Day/Phlan Adventures scenes from current V5 copies.

## Decision
Mount Narrative in the dashboard; keep `/api/narrative` and redirect `/narrative`.
Adventure Log Candidates import semantic briefs as Narrative stubs. Logical keys
bind current exact-view costumes; other inputs bind independent library assets.
Historical final images are immutable, independent catalog assets displayed below
scene save/delete controls, never selected Narrative candidates or completed finals.

Migration is an offline, explicitly scoped, reviewed-image operation with stable
IDs, backups, reservations, atomic files and a journal. It creates backdrops,
subject subscenes and assembly inputs without prompts, jobs, candidates or layers.
Unavailable sources stay visible review issues. Changed candidate briefs are
compared and acknowledged without replacing authored inputs or images.

Retired execution paths are removed/fenced. Late owned answers are retained as
superseded without publication. Dedicated geometry and its Three.js dependency
move outside runtime into an offline archive for possible future Narrative work.

## Rationale and tradeoffs
This follows Joe's approved direction and preserves useful creative history without
pretending legacy scenes form working Narrative pipelines. Keeping logical costume
bindings permits later preferred-image updates while submitted jobs retain frozen
bytes. Keeping full source documents in provenance preserves information omitted
from preliminary authoring fields. Five managed-image PNGs could not be recovered;
their historical record labels and review issues are retained instead.

## Consequences and verification
Narrative owns active stories and scene outputs used by summaries/discovery/zines.
Legacy image tags retain narrow read-only compatibility. Narrative usages protect
referenced catalog assets, including phase/costume deletion preflight. Selected/
locked Narrative outputs keep their existing deletion and snapshot contracts.

The three approved fast E2E scenarios remain unchanged and pass through the
dashboard redirect. Migration, Candidates review/idempotency, archival integrity
and legacy-image preservation received separate disposable/manual verification;
these checks do not expand the maintained test suite. Live rendering was not run.

## Related implementation
- [Narrative component](../COMPONENTS/NARRATIVE.md)
- [Retirement/archive guide](../../Archive/scene-builder/README.md)
- [Migration service](../../zet/services/narrative_migration_service.py)
- [Candidates service](../../zet/services/narrative_candidate_import_service.py)
- [Completed implementation plan](../../plans/completed/narrative-scene-retirement.md)
