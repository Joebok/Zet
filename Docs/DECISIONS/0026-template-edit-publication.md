# 0026 — Publish and reconcile production template edits
Status: accepted
Date: 2026-10-20

## Context
Confirmed governing-template promotion writes tracked repository masters in the
running release. Deployment correctly blocks those edits, but local filesystem
reconciliation is unavailable to a remote dashboard user.

## Decision
Explicit publication freezes five eligible templates into stable version-1
receipts. A separate checkout applies the snapshot onto main, validates with the
approved isolated baseline and publishes one branch/PR per operation. The operator
merges. Deployment refreshes merge proof, verifies target merge ancestry/published
blobs against unchanged captures, then rechecks under the master-promotion fence.
Live templates, HEAD and index remain intact, including for rollback.

## Rationale and tradeoffs
Committing in production changes revision identity without proving a merge.
Restoring files interrupts accepted prompt behavior and weakens rollback. Ignoring
arbitrary dirty files loses protection. Exact receipts restrict the exception.
Conflicts, empty PR diffs and later target changes remain conservative blockers.
Capture/published hashes can differ after clean application of upstream changes.

## Consequences
Existing Git/gh credentials and declared baseline dependencies must be available.
Interrupted delivery retries retained checkpoints; failed attempts are kept rather
than reset. First installation needs separately authorized preservation, merge and
reconciliation for the old controller. No library migration, production dependency
or maintained test scenario is added.

## Sources
- [Publication service](../../zet/services/template_publication_service.py)
- [Shared guards](../../zet/services/template_publication_core.py)
- [Deployment controller](../../zet/scripts/deploy_release.py)
- [Operator workflow](../GitHub_Task_Workflow.md#accepted-template-edits-and-update-recovery)
