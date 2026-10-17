# 0019 — Failed AI job deletion retains a local fence
Status: accepted locally
Date: 2026-10-16

## Context
AI Queue merges shared payloads, producer-local records and receipts. Users need
to permanently remove retained harvest/recovery failures, including records whose
ownership metadata is damaged or missing. A folder deletion alone leaves other
evidence visible and allows late sync or continuation replay to recreate the job
or apply an unwanted answer.

## Decision
AIJobCleanupService owns explicit deletion, exposed through ZetApp and a confirmed
queue action. It accepts only HARVEST_FAILED/RECOVERY_REQUIRED identities, refuses
explicit foreign producer evidence, queued/running or linked paths, and deletes known
job-scoped queue/state paths under coordinator and common job locks. Library
images, domain workflow records and shared lock files are preserved.

Before deleting payloads, commit a minimal hashed producer-local DeletedJobs
marker. Activity, collection, adoption and publication fence that identity.
Incomplete deletion remains visible with its error and supports retry. Completed
markers survive payload cleanup; a new workflow attempt needs a new job identity.

## Rationale and tradeoffs
Keeping no evidence would allow stale answers to reappear or apply. A small local
marker prevents replay without retaining prompts or answer artifacts. Missing
ownership metadata no longer blocks cleanup of an eligible row. Explicit foreign
producer evidence still prevents deleting another machine's work. Workflow records
remain with their domain rather than being recursively deleted from diagnostic
output paths.

## Consequences and validation
Collection/publication entry points must honor DeletedJobs. Synced payloads that
arrive after completed cleanup are ignored and can be removed by repeating DELETE.
Replacement execution is an explicit new workflow attempt. Disposable isolated
checks cover cleanup/refusal/partial retry and browser confirmation/reload. The four
approved fast scenarios remain unchanged and pass; no live queue was cleaned.

## Related code and documentation
- [Cleanup service](../../zet/services/ai_job_cleanup_service.py)
- [Job repository](../../zet/repositories/ai_job_repository.py)
- [Shared AI jobs](../COMPONENTS/AI_JOBS.md#deleting-retained-failures)
