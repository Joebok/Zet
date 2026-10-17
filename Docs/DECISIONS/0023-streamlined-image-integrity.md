# 0023 — Available images, managed versions and verified handoffs
Status: accepted
Date: 2026-10-17

## Context
Joe explicitly approved reducing recurring integrity checks: existing files at
expected locations should remain usable after manual replacement or history
retention. The important checks are correct AI handoffs and resolution of required
references. Recorded usages are useful observations, not continuously verified
deletion vetoes. The implementation follows the approved
[plan](../../plans/completed/streamlined-image-integrity.md).

## Decision
- Use recorded lock/publication identity plus permanent file availability. Do not
  require retained batch/candidate history, receipts, or matching file hashes.
- Record hashes during Zet writes/request preparation as managed versions and
  captured-input metadata. Preserve candidate/attempt/revision/selection fencing.
- Separate cheap queue inspection from admission: verify inventory bytes while
  transferring into local staging, atomically publish local admission, then reuse
  it. Retain producer, universe, original request, destination and binding checks.
- Update usages per changed consumer, journal pending work in existing local
  recovery storage, and replay it independently of primary saves. Check/rebuild
  actions are explicit; unreadable consumers retain prior observations.
- Require metadata-version confirmation before archive/phase/costume deletion;
  show recorded consumers and allow confirmed removal. Preserve surviving authored
  bindings; unresolved references fail only an operation that actually needs them.
- Coalesce index refresh requests on the existing background reconciler; retain
  the last good generation. Image dependencies use availability/managed metadata.

## Rationale and tradeoffs
Manual edits are trusted. The application does not provide chain of custody or
ongoing anti-tampering proof. This eliminates repeated large file reads and global
usage scans. Derived usage information can lag or miss external edits until an
explicit rebuild. Small-library saves can still pay recovery/transaction overhead;
there is no universal wall-clock performance guarantee.

This supersedes the image-availability/receipt/hash policing portions of ADRs
0017 and 0021, and the recurring byte-verification assumptions of ADRs 0011/0013.
Queue ownership, actual transfer checks, schema versions, ordered inputs,
retention success receipts, and offline migration/transfer tooling remain.

## Owners and validation
[ImageUsageService](../../zet/services/image_usage_service.py) owns observations,
[image deletion service](../../zet/services/image_deletion_service.py) owns shared
confirmation, and the existing domain/publication/AI/index services own their
boundaries. See [library](../COMPONENTS/LIBRARY.md) and
[invariants](../INVARIANTS.md). S1-S4 remain the maintained baseline; disposable
checks cover the revised failure/confirmation behavior and local measurements.
No new permanent tests, dependencies, live inference or production-library changes.
