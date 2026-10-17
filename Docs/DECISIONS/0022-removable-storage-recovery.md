# 0022 — Local recovery evidence and subscriber-owned fresh attempts

Status: accepted 2026-10-17.

## Context

The library, derived indexes, queue, and ordinary Zet request state can share a
removable E: volume. A journal on that volume cannot coordinate its own outage.
Interrupted runners and proxy restart failures previously required manual retries.
Joe approved automatic recovery of unfinished work, including unknown-cause
interruptions, while retaining cancellations, human decisions and locked images.

## Decision

Keep data on its configured paths. Store compact health/identity, continuation and
replacement-attempt evidence on fixed local storage. Treat unavailable roots as a
pause, require stable reconnection, and use the same reconciliation during startup
and polling. Never publish an incomplete index or recreate an observed catalog.

Keep one execution per transport attempt: Zet creates new attempts from verified
frozen inputs behind a stable logical request ID. AI_Proxy owns worker/backend
fencing and retained execution outcomes. Success is collected before considering
another execution. Content errors and missing immutable inputs are not outage retries.

## Consequences and evidence

Both applications need the updated recovery interfaces. Old envelopes remain
readable; no library relocation or schema migration is required. Local evidence
does not confer distributed ownership. Manual external ComfyUI ambiguity remains
held; normal managed recovery can stop only its own verified backend.

[Storage recovery](../COMPONENTS/STORAGE_RECOVERY.md) owns implementation details
and validation boundaries. Existing scenario coverage is unchanged; real hardware
disconnects and live inference remain separate operational validation.
