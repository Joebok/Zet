# 0046 - Narrative mixed-quality image board
Status: accepted locally
Date: 2026-11-05

## Decision
Narrative scenes use one eight-slot board, selection and lock across Draft and
Final images. Render quality is candidate metadata and is chosen for each new
request. Draft images remain eligible for selection, locking and downstream use.
The shared board allocation policy is mode-independent; other pipelines retain
their own storage until explicitly migrated.

Legacy Narrative targets convert with a dry-run report and a complete target
backup. Conversion prefers selected and locked candidates, with Final winning
conflicting old choices. It preserves live candidate bindings where possible,
stops when more than eight protected/bound candidates exist, and never converts
a target with active work. Excess candidates and their owned artifacts are
removed only after backup. This decision supersedes ADR 0039's independent-board
rule for Narrative only.

## Consequences
Quality remains frozen on submitted requests and retries. Source pickers use the
one selection; frozen downstream snapshots remain unchanged. Draft cleanup still
requires state-bound approval for affected selections and locks.
