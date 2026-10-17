# 0020 — Configured machine storage and bounded retention
Status: accepted
Date: 2026-10-16

## Context

Zet's derived library indexes accumulated complete generations and obsolete parsed
sources under `%LOCALAPPDATA%/Zet/Indexes`; the index family measured 104.48 GB.
Producer-local request, receipt and routing state also used a separately computed
AppData path. Zet is a personal creative tool; detailed completed-work history is
not an audit record, while active work, unresolved failures, replay fences and
image-admission proof still matter.

## Decision

Configure all machine-local Zet areas under one `[Storage].Root`, with relative
children for indexes, queue state, migration reports and task workflow state.
Windows production uses `E:/Zet/AppData`; other platforms and older configs retain
their previous default. Keep seven days of completed details. Successful index
publication keeps one active generation and only current parsed-source revisions.
Daily maintenance compacts safe completed queue state and preserves small replay
and image evidence. Shared queue transport and universe-owned creative data keep
their existing roots and ownership.

## Rationale

One explicit root makes disk usage and relocation understandable. Indexes can be
rebuilt from authored/library and queue sources, so copying generations carries
large redundant snapshots without preserving authority. Recent summaries are
already small compared with the index files; old prompts and diagnostics add no
required product behavior. Seven days keeps recent activity useful without turning
the queue into a long-term history system.

## Alternatives and tradeoffs

- Copy existing indexes: rejected because they contain repeated complete snapshots
  and obsolete sources; rebuilding preserves the active derived view and avoids
  transporting 104 GB.
- Vacuum on every publication: rejected because large offline compaction stalls
  routine use. Row pruning is transactional; explicit offline VACUUM returns free
  pages to disk when needed.
- Delete every old receipt: rejected because receipts fence duplicate publication
  and may prove successful image admission. Compact these while retaining identity
  and required image checksums.

## Consequences

Consumers resolve local state through `StoragePathService`; missing configured
drives fail rather than silently writing to C:. Completed local queue details age
out after seven days only when a successful receipt confirms completion. Unknown,
failed, or unowned work and lock files remain protected. Reports and a quiescent
cutover manifest are read-only; copy and source removal require explicit review.
Authoritative `catalog.sqlite3`, authored library files/images, shared AI queue
transport, runtime release state, and universe-owned workflow records are not
retention targets.

## Related code and documentation

[StoragePathService](../../zet/services/storage_path_service.py),
[StorageMaintenanceService](../../zet/services/storage_maintenance_service.py),
[LibraryIndexRepository](../../zet/repositories/library_index_repository.py),
[manage_storage](../../zet/scripts/manage_storage.py), [DATA_MODEL](../DATA_MODEL.md),
[QUEUES](../COMPONENTS/QUEUES.md), [AI_JOBS](../COMPONENTS/AI_JOBS.md), and the
[active plan](../../plans/active/machine-storage-relocation-and-retention.md).
