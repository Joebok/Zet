# Storage outages and automatic recovery

Implemented for the approved 2026-10-17 fault-tolerance plan. The configured
library, application storage/indexes, and shared queue remain in place, including
on E:. Recovery does not substitute an empty library or move its contents to C:.

## Owners and local evidence

- [storage_health_service.py](../../zet/services/storage_health_service.py) probes
  configured roots every two seconds and requires two successful probes separated
  by two seconds after a failure. Observed directory/volume identities must match.
  Required authoritative catalogs are checked through closed read-only SQLite
  connections. Confirmed corruption is `RECOVERY_REQUIRED`, not an index rebuild.
- Recovery metadata lives under `Runtime.Root/state/StorageRecovery`, or the
  machine-local `ZetRecovery/StorageRecovery` directory when Runtime.Root is unset. It must not
  reside on the monitored removable volume. Root identities, compact request
  metadata, attempt reservations, and registered continuation arguments survive
  loss of application storage. Prompts, images and queue bundles stay on their
  existing paths. Shared queue/library locks resolve to stable local OS locks.
- [storage_recovery_service.py](../../zet/services/storage_recovery_service.py)
  owns recurring per-universe recovery, used by web startup and the common
  coordinator/standalone harvester. Health polling is two seconds; batch discovery
  is bounded to once per ten seconds per host, with a process-shared recovery
  lease and runner eligibility checked again when an executor starts.

Local locks coordinate hosts on this machine; they do not provide distributed
queue safety. The one-assigned-proxy-per-queue contract still applies.

Probes run in at most one background thread per monitor. A device call taking more
than one second pauses its resource without holding the status lock or spawning
more probe workers. Independent verified resources remain usable. The ten most
recent outage causes remain in diagnostic history when active errors clear. Exclusive local
identity markers prevent competing startup hosts from replacing the first root
observation. Fast fixtures keep recovery metadata under their own Runtime folder.
When a direct root stat briefly reports `FileNotFoundError`, `require()` forces a
fresh full probe before classifying the root as disappeared; a successful probe
and stat keep it available, while a confirmed missing root still pauses recovery.

## Execution, collection, and continuation

[AIAttemptRecoveryService](../../zet/services/ai_attempt_recovery_service.py)
keeps the original logical job identity while reserving a fresh transport ID for
a verified interrupted/storage-failed execution. AI_Proxy never executes the same
transport attempt twice. Recovery checks receipts and retained answers first;
successful execution with an interrupted publication/collection is collected
without generating again.

Replacement asks contain verified frozen input bytes, original seed/options and
ordered bindings. Their identity changes are inventoried before atomic publication.
A durable reservation precedes publication, so repeated sweeps/process restarts
reuse the same pending replacement. Backoff is capped at thirty seconds. Verified
replacement results are materialized as producer-local logical answers; shared
envelopes remain immutable. Child attempt rows do not become independent UI tasks.
The original failed bundle is retained under local queue `RecoveryAttempts`.

Existing native asks and retained `PROXY_INTERRUPTED` outcomes can use this path
while their owning work remains current. Missing/changed frozen inputs, malformed
records, absent routes, genuine provider/content failures, and unresolved ownership
require attention. Recovery does not invent missing historical requests.

[AIWorkflowService](../../zet/services/ai_workflow_service.py) journals registered
continuation identity/arguments locally before saving its normal application copy.
Waiting, running and storage-paused continuations resume on polling/restart. Domain
revision, cancellation, current candidate and publication fences still apply.
Image Generation saves child reservation IDs and submission intent before dispatch;
Narrative saves text requests before publication and reattaches submitting jobs.

Body, Head, Assembly and Dressing recover orphaned runners using persisted targets
and operation mode. Supplemental slots, overview jobs and Run All Remaining retain
their own ownership. Recovery preserves completed images, locks, explicit stops,
cancellations, selections, and waits for human input or prerequisites.

Native ComfyUI reconciliation remains AI_Proxy-owned. A managed ambiguous execution
is fenced by verified owned-backend shutdown before new local admission; an
unresolved external backend remains held with intervention guidance. Cloud work
and independent resources continue.
Surviving worker hosts retain local execution ownership or cloud capacity across a
proxy restart. Exited Windows processes are distinguished from still-open process
handles; a stale proxy lock does not block recovery merely because a launcher kept
the old process handle. Reserved launches are fenced before abandonment.

## Dashboard and startup

`GET /api/storage/status` reports availability and per-resource cause. Queue
inspection/activity adds logical/current attempt identity, recovery stage and time.
`PAUSED_STORAGE` and `RECOVERING` are nonterminal; `HELD` can identify an unsettled
backend. During outages, compact local activity is explicitly stale and counts are
unknown, not zero. The dashboard displays a storage banner and retains known work.
Storage-dependent API actions return HTTP 503 with `Retry-After: 2`.

[storage_bootstrap_service.py](../../zet/services/storage_bootstrap_service.py)
provides a waiting dashboard if initialization cannot access storage. It initializes
normal services after recovery and forwards requests without restarting the server.
The standalone harvester likewise waits before constructing storage-dependent
services. Startup and recurring reconciliation use the same backend recovery owner.

## Catalog and index integrity

An observed authoritative `catalog.sqlite3` is never silently recreated after it
disappears. Existing catalogs open in SQLite read/write-existing mode; missing or
corrupt catalogs need restoration. This is distinct from rebuilding a derived index.

Index scans propagate unreadable sources/directories and check availability before
and after snapshot construction. A failed/incomplete scan does not publish a new
generation or invalidate dependencies from missing-volume evidence. Atomic writes,
optional workflow reads and request/receipt readers propagate unavailable storage;
short Windows replacement locks are retried without treating records as absent.

## Verification boundary

The approved four Zet E2E scenarios and six AI_Proxy scenarios remain the maintained
baseline. Isolated disposable checks cover fresh-attempt/logical result recovery,
root identity and reconnect probes, offline bootstrap with real ZetApp construction,
incomplete index publication, missing authoritative catalogs, and local continuation
intent, lost child-state commits, runner stop/completion rechecks, stalled probes,
and surviving-worker lane/capacity fencing with successful publication after restart.
They do not establish physical E: disconnect behavior or live provider
settlement. No live drive, model, or production queue is used for these checks.
