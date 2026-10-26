# 0034 — AI job deletion commits before background cleanup
Status: accepted locally
Date: 2026-10-26
Supersedes ADR 0019's synchronous cleanup and visible incomplete-deletion behavior.

## Context
The confirmed Delete job action could fail because unrelated background collection
held the coordinator lock beyond its one-second deadline. Incomplete disk cleanup
also restored an explicitly deleted job to the activity feed.

## Decision and rationale
AIJobCleanupService validates an eligible retained failure and atomically commits
its existing DeletedJobs fence independently of collection locks. That commitment
is successful deletion for the user. Queries hide pending deletions. Coordinator
sweeps retry pending disk cleanup under the existing coordinator and common job
locks, retaining errors in the marker. Restart resumes pending cleanup.

## Alternatives and tradeoffs
Increasing lock timeouts would still expose collection contention to Delete.
Removing disk files without locks risks racing active collectors. Deferred cleanup
preserves serialization, but payloads may remain until the coordinator and storage
are available. A handler already applying an answer may finish before observing
the fence; deletion does not roll back library/domain writes. Storage errors that
prevent committing the marker still fail the deletion request.

## Consequences and validation
Ownership, active Ask/Running checks, identity validation and path confinement
remain in place. Library images, workflow records and lock files survive cleanup.
No new maintained tests or dependencies. Disposable temporary-storage checks cover
held locks, file cleanup failure, restart retry and immediate snapshot removal;
the four fast E2E scenarios remain representative workflow regressions.
