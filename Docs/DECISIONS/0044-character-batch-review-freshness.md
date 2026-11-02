# 0044 — Character batch review freshness and frozen publication inputs

Status: accepted (2026-11-02). Implementation validation is recorded in the
[completed plan](../../plans/completed/character-pipeline-batch-and-view-pages.md).

## Decision

Character rankings are advice for one view and render mode. Committing a new
image queue for that view/mode makes saved advice stale. Changing a selected
FRONT, a locked Draft comparison, a master, or a reference does not stale a
completed ranking. An in-flight evaluation still has to match its captured
inputs before its result can commit. Re-evaluate stays available in the UI and
reports current eligibility when attempted.

New image asks check the chosen master baseline and freeze the prompt and ordered
reference bytes at preparation. Explicit **Use current masters** selects a new
batch revision and reports each requested view, including blockers. Comparison
reports are requested explicitly. A finished selected image can be published
after a later upstream selection change when its required frozen references
remain provable. Missing or altered frozen bytes, a changed selected output,
foreign ownership and circular lineage remain action-time failures.

## Consequences

Batch and view reads need no live-master or recursive lineage comparison. The
summary and single-view projections stay narrow; historical differences are
available through manual reports. Publication retains recorded dependency hashes
as provenance even when an upstream current selection has moved on.

## Verification

The approved fast E2E suite and disposable checks are recorded in
[Testing](../Testing.md#character-batchview-pages-2026-11-02). Legacy lineage
branches, all populated view layouts and live-scale responsiveness were not
fully verified in this implementation; see the completed plan for those limits.
