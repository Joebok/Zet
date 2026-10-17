# 0011 — Portable library references
Status: accepted
Exact moved-universe read resolution updated by [ADR 0021](0021-file-based-local-image-availability.md).
Date: 2026-10-14

## Context
Library-owned JSON records persisted absolute paths. Moving or renaming a library therefore left character candidates, locks, Narrative snapshots, and related sources pointed at the former root. `config.toml` already selects the new library location, but configuration cannot repair persisted absolute references. References are distributed among independent storage owners and include historical prose and transport data that must not be rewritten indiscriminately.

## Decision
Persist explicitly typed library-owned paths as forward-slash paths relative to the owning universe, with a path-format marker independent of workflow and review versions. Resolve them through a shared codec backed by the configured universe root. Keep external paths, document/job-relative filenames, repository templates, IDs, and logical reference keys under their existing owners. Accept legacy records and absolute paths during transition, but map former roots only through an offline updater supplied with explicit old roots. Reject unsupported path-format versions, traversal, and foreign-universe records.

The updater applies atomically per record, verifies operational references and saved image hashes, records a compact report, and marks a universe converted only after the complete scan and route verification succeeds. It runs only while Zet servers and harvesters are stopped and never edits shared transport bundles or backup payloads.

## Rationale
Universe-relative references survive moving the configured container and also survive renaming the container itself. One shared conversion boundary prevents storage owners from inventing different relocation rules. Explicit old-root mappings avoid ambiguous basename guessing. Version checks prevent an older release from silently opening converted records; recovery requiring an older reader uses the retained library copy.

## Alternatives and tradeoffs
Retaining absolute paths requires rewriting every saved record on each move. A symlink or junction preserves old paths but leaves machine-specific dependencies and does not repair queue routes or copied libraries. Rewriting every string that resembles a path would corrupt historical prose, document-relative names, and immutable transport artifacts.

## Consequences
Storage-owning services must encode on writes and decode before filesystem access. API/service shapes continue to expose resolved paths, so runtime response objects must not be written back directly. Production conversion remains a separate rollout after compatible readers and writers are deployed. Existing data is converted with `zet.scripts.normalize_library_references`; the command refuses to proceed while Zet servers or harvesters run.

## Related code and documentation
[LibraryReferenceService](../../zet/services/library_reference_service.py), [PathService](../../zet/services/path_service.py), [migration service](../../zet/services/library_reference_migration_service.py), [normalizer CLI](../../zet/scripts/normalize_library_references.py), [DATA_MODEL](../DATA_MODEL.md), [INVARIANTS](../INVARIANTS.md), and [portable-path plan](../../plans/active/portable-library-paths.md).
