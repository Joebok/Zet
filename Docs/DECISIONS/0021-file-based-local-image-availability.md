# 0021 — Existing files admit local character image review
Status: accepted
Date: 2026-10-16

## Context
Elder/Youth Tsaeytte Head-Image renders existed, but interrupted candidate commits
and strict receipt/hash admission prevented ranking. Joe explicitly directed that
existing images remain usable despite stale checksum and absolute-path metadata.
Read-only inspection found 143 stale absolute image references in 34 JSON records
whose exact universe-relative files exist under the current library root.

## Decision
Local character batch ranking/advice uses current-candidate file availability.
Explicit Re-evaluate refreshes missing or outdated candidate hashes and interrupted
render status under the run lock. Old receipts/requests are not required. Candidate
identity, attempt, cancellation and evaluation ownership still fence publication;
hashes still identify stale ranking results and changed inputs.

Typed legacy absolute paths resolve to the current universe root when their exact
universe-relative suffix names an existing file/directory. Only recognized library
folders qualify; foreign universes, traversal and ambiguous mappings are not
guessed. There is no basename or recursive image search. Versionless records retain
task-relative names; subsequent normal writes save resolved library paths portably.

## Tradeoffs and consequences
An existing file can be reviewed even when its original render receipt has expired
or its saved checksum is wrong. Reading a moved file does not require a bulk live
library rewrite. A genuinely absent file remains unavailable. Immutable published
locks, queue output inventories, execution outcomes and other workflows' harvest
admission are unchanged. This supersedes only local batch advice availability in
[ADR 0017](0017-image-harvest-admission.md) and the explicit-only old-root read
restriction in [ADR 0011](0011-portable-library-references.md).

## Validation
Disposable isolated copies of both reported batches ranked eight existing images
each with prepared responses, including absent requests/receipts and stale hashes.
Replacement/cancellation/missing-file rejection and versioned/legacy path behavior
passed; all 143 audited relocatable references resolved to their exact current files.
Maintained E2E and production rollout results are recorded in the
[implementation plan](../../plans/active/file-based-image-review-and-recovery.md).

## Owners
[image_harvest_service](../../zet/services/image_harvest_service.py),
[PathService](../../zet/services/path_service.py),
[LibraryReferenceService](../../zet/services/library_reference_service.py),
[local characters](../COMPONENTS/LOCAL_CHARACTERS.md).
