# Portable library references and existing-library update
Status: implementation complete; acceptance validation incomplete
Related issue/specification: user-approved implementation plan in the Codex task.

## Goal

Persist library-owned file references relative to the owning universe and resolve them from the configured roots. Provide an offline, apply-and-verify command for converting existing library records and typed producer-local routes. Do not update the live library or restart production in this implementation.

## Current behavior

`PathService.resolve_path` accepts absolute paths and limited library-relative forms, but local character services persist absolute paths and frequently consume them with `Path(...)` directly. Local asset locks, Narrative job snapshots, image-catalog records, and queue routes also store or carry absolute paths. Production uses per-release `config.runtime.toml`; the active config already points at E:.

A read-only scan of the copied Moonsea universe found approximately 10,900 occurrences of the old C: path in operational and historical JSON records, chiefly `PipelineCandidates`, `NarrativeStories`, `Characters`, and `_state`. Inspected entity catalog path-bearing tables had no such references. Existing approved E2E baseline is S1–S3; permanent coverage additions require explicit approval.

## Desired behavior

- Library-owned references are serialized relative to their owning universe; runtime services resolve them through one shared path codec using bound config.
- Legacy absolute paths remain readable until normalized. Explicit source-root mappings are required for migration; path guessing by basename is forbidden.
- An offline command processes all configured universes and owned route roots, converts supported operational fields atomically, verifies them, and reports unresolved operational references. It writes no backup payloads and makes no live production changes.
- Converted data cannot be opened by a release that only understands the legacy path format.

## Impact analysis

Primary owners: `zet/services/path_service.py`, local Body/Head and Assembly/Dressing services, `zet/services/local_asset_store_service.py`, Narrative repository/services, character metadata services, image catalog and image generation services, `zet/services/file_proxy_client.py`, `zet/services/ai_queue_lifecycle_service.py`, deployment services/scripts, and a new `zet/services/library_reference_migration_service.py` plus `zet/scripts/normalize_library_references.py`.

Persistence affected: pipeline specs/states/manifests, locked-asset records, Narrative job snapshots, typed character/catalog/image-generation records, and producer-local routes. No catalog SQLite image-path column was found in the inspected schema. Documentation owners: DATA_MODEL, INVARIANTS, COMPONENTS/LOCAL_CHARACTERS, COMPONENTS/LIBRARY, COMPONENTS/NARRATIVE, COMPONENTS/QUEUES, DEVELOPMENT, CODE_MAP, and DECISIONS.

## Invariants and constraints

Preserve universe isolation, path containment, image checksums, image bytes, locks, selections, reference order, queue producer/attempt ownership, and immutable transport bundles. Do not rewrite free-text/history or backups/deleted records. Stop active Zet and harvester processes before applying the updater. Do not mutate live queue bundles consumed by workers. Use disposable validation; add no permanent scenarios, dependencies, or live rendering. Keep each step within its named responsibility and use one agent.

## Implementation steps

### WP1 — Shared path codec
- Dependencies: none.
- Files/interfaces: `PathService`, `Scripts/Library_Paths.py`; add a focused library reference codec only if it keeps path-field ownership explicit.
- Work: add serialization and resolution against the bound universe root; define explicit allowed path-field/base selectors; support current and explicit legacy roots, Windows/POSIX separators, safe traversal rejection, and a portable-path format marker independent of workflow/review versions.
- Acceptance: moved/renamed roots resolve without basename guessing; external, project-relative, document-relative, and job-relative paths keep their distinct owners; invalid/foreign paths are rejected.
- Validation: disposable path-codec checks on Windows-style and POSIX-style strings, containment, multiple universes, and legacy reads.
- Status: implementation complete. Disposable checks passed for moved/renamed roots, legacy Windows root mapping, traversal and foreign-universe rejection, and no basename guessing.

### WP2 — Body and Head storage
- Dependencies: WP1.
- Files/interfaces: `local_body_reference_service.py`, `local_head_image_service.py`, `render_slot_service.py` or their focused persistence helpers.
- Work: normalize candidate image, prompt/source, gate-output, frozen-input, and dependency-manifest paths on persisted reads/writes, including state access paths that bypass detail serializers.
- Acceptance: API/service behavior still sees usable filesystem paths; newly saved library-owned references are relative; hashes and review state remain unchanged.
- Validation: disposable seeded Body/Head records can read, update, serve, and verify image references after relocating the fixture.
- Status: implementation complete. Body/Head reads and writes use the codec, including state, candidate, prompt, gate, answer and frozen JSON records. Disposable shared run-state and source-hash checks passed.

### WP3 — Assembly/Dressing and locks
- Dependencies: WP1–2.
- Files/interfaces: `local_character_asset_pipeline_service.py`, `local_asset_store_service.py`, slot and prompt-improvement persistence helpers.
- Work: normalize candidates, sources, locked images, local-asset locks, snapshots, supplemental slots, and state while preserving checksums, selection/lock state, and attempt fencing.
- Acceptance: after relocation, candidates and verified locks resolve under the configured universe; existing S2 behavior remains intact.
- Validation: disposable Assembly-to-Dressing flow and relocation checks for candidates, references, locks, and slots.
- Status: implementation complete. Assembly/Dressing, local asset locks and shared slot/prompt-improvement writers use the codec. Approved S2 passed in the latest baseline; checksum/selection-state disposable checks passed.

### WP4 — Other library consumers
- Dependencies: WP1.
- Files/interfaces: Narrative repository/generation/assembly, identity/turnaround services, image catalog, ad-hoc image-generation state.
- Work: normalize only typed library-owned path fields at their owning persistence boundaries. Keep Narrative record-relative filenames, entity IDs, blob addressing, immutable image bytes, and historical prose intact.
- Acceptance: saved Narrative snapshots, character metadata, catalog sources, and image-generation records resolve after relocation without changing API record shape.
- Validation: disposable S1/S3 flows and targeted moved-fixture checks.
- Status: implementation complete. Narrative, catalog, identity/turnaround, ad-hoc generation and typed prompt source hashes use storage-boundary conversion. A standalone Narrative relocation check was not separately run.

### WP5 — Queue routes into the library
- Dependencies: WP1.
- Files/interfaces: `file_proxy_client.py`, `ai_queue_lifecycle_service.py`, harvester route application.
- Work: serialize supported library output destinations relative to a declared universe in producer-local routes; resolve before result application; preserve existing absolute routes during transition. Do not change shared immutable asks/answers or external AI Proxy.
- Acceptance: eligible queued results still apply after library relocation; foreign-universe and stale-attempt protections remain active.
- Validation: disposable route/result delivery after moving the fixture, plus owner/fence rejection checks.
- Status: implementation complete. Producer-local route write/read and owner checks use the codec. Disposable route resolution and full updater route conversion passed.

### WP6 — Offline apply-and-verify command
- Dependencies: WP1–5.
- Files/interfaces: new `LibraryReferenceMigrationService` and `zet.scripts.normalize_library_references` command.
- Work: load ConfigService and universe descriptors without constructing ZetApp; process recognized operational JSON fields in all configured universes; accept repeated `--old-library-root` and `--route-root`; scan configured local and legacy route stores; use atomic per-file writes and a compact resumable progress/result record with no backup payloads. Exclude backups, deleted folders, historical journals, logs, free-text errors, and immutable transport artifacts. Verify path existence/hash when required, report exact unresolved fields, and mark each universe complete only after verification. Refuse concurrent updates and require affected server/harvesters stopped.
- Acceptance: idempotent rerun; interrupted runs resume; malformed, ambiguous, unsupported, and missing operational references return nonzero with actionable diagnostics; command default applies then verifies.
- Validation: disposable migration with interrupted write, rerun, hashes/bytes preserved, and already-normalized records unchanged.
- Status: implementation complete. Disposable full apply/verify, image-hash verification, route conversion, completion marker, fingerprint report, untyped historical-occurrence count and byte-stable idempotent rerun passed. Live process-quiescence behavior was not exercised against production; the command checks it before any mutation.

### WP7 — Compatibility, documentation, and completion
- Dependencies: WP1–6.
- Files/interfaces: `deployment_service.py`, `deploy_release.py`/runtime checks as required; affected Docs and a short ADR; this plan.
- Work: ensure converted libraries cannot be started by an old reader or rolled back by code alone. Document command invocation, quiescence, compatibility and recovery using the user's retained copy. Record exact implementation validation, update owned documentation, and move this plan to `plans/completed/` only after acceptance.
- Acceptance: deployment refuses incompatible library format; docs accurately describe stored references and updater; final diff contains no unrelated changes.
- Validation: disposable compatibility check; approved `npm run test:e2e`; `git diff --check`; final diff review.
- Status: implementation and documentation complete. Compatibility checks, ADR and rollout instructions are present. `npm run test:e2e` passed all 3 scenarios once before the final shared-writer updates; the latest run passed S2/S3 but S1 timed out because the Narrative list returned an ID different from the fixture context and its detail returned 404. This needs investigation before archiving the plan.

## Validation

Use disposable fixtures only. Demonstrate moving a fixture library, making the original unavailable, changing config, and verifying image display/source resolution, locks, Narrative snapshots, and queued result application. Verify post-restart writes remain relative and a second relocation needs only config. Verify idempotence and preservation of bytes, bindings, order, and decisions. Run the approved three-scenario E2E baseline and `git diff --check`. Production endpoint/lock checks and migration are a separate rollout after review; no live migration or production restart is authorized here.

## Risks and alternatives

Some of the roughly 10,900 old-root strings are historical or point to pre-migration layouts; only typed operational fields are eligible for conversion. Missing or ambiguous active references must be reported and left unchanged rather than guessed. An older release cannot read converted references, so apply only after compatible code is installed and use the retained library copy for old-release recovery.

## Progress and decisions

- User selected a direct offline apply-and-verify command without preview or backup payloads.
- Existing config already selects E: in both development and active production release.
- Initial repository state was clean. No live library/queue files changed.
- Implemented path format version 1, owning storage boundaries, producer-local routes, offline updater, release checks and the affected documentation.
- Python 3.14.6 compile, disposable relocation/updater checks, and `git diff --check` passed. No permanent tests, scenarios, dependencies or live renders were added.
- The final approved baseline's S1 mismatch is unresolved, so the plan remains active and is not archived as complete.
- No live library or shared queue data was changed; production restart and migration remain separate rollout actions.
