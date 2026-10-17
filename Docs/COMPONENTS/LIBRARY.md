# Library, universes, and discovery

This component owns library service interactions. [DATA_MODEL](../DATA_MODEL.md) owns store layouts and identifiers; [INVARIANTS](../INVARIANTS.md) owns isolation/integrity contracts.

## Entry points and responsibilities

- [UniverseService](../../zet/services/universe_service.py): discover/select/create universes and bind configuration. [ZetApp.from_config](../../zet/app.py) constructs the bound services. [create_app](../../zet/web/app.py) caches per-universe apps and binds requests through header/query context.
- [EntityLibraryService](../../zet/services/entity_library_service.py) and [EntityLibraryRepository](../../zet/repositories/entity_library_repository.py): authoritative images, entities/variants, reference sets, descriptors/facets/tags, stable logical references, usage, merge/archive/replace workflows. [LibraryDeletionService](../../zet/services/library_deletion_service.py) coordinates removal with local workflow sources and the entity catalog.
- [ImageCatalogService](../../zet/services/image_catalog_service.py) and [ImageCatalogRepository](../../zet/repositories/image_catalog_repository.py): a separate record-oriented catalog combining managed metadata and existing pipeline/story images. It remains wired into app/story reference services; entity SQLite has not replaced every catalog consumer.
- [LibraryIndexService](../../zet/services/library_index_service.py)/`LibraryIndexReconciler` and [LibraryIndexRepository](../../zet/repositories/library_index_repository.py): derived local generations for dashboard paging, source payload reuse, errors, work/history, and compilation dependency fingerprints. `ZetApp._indexed_list_rows` supplies additional list rows; record catalog writes call `refresh_library_index`.

## Inputs, outputs, and flow

Configuration selects a library container; a universe descriptor binds the creative root. Imports/publications validate image bytes and store image metadata/relationships. Logical references provide durable consumer bindings. Story reference resolution combines entity and record/pipeline sources into [ImageReferenceRow](../../zet/models/story.py) data, including availability/reason and source identity. Local approved character images are published through [LocalAssetStoreService](../../zet/services/local_asset_store_service.py).

Reconciliation scans authored/queue sources, fingerprints content, reuses cached parses, records malformed sources as errors, builds a generation, and publishes it for queries. Replacement snapshots become visible transactionally; successful publication retains the newly active generation and prunes obsolete parsed-source revisions and compilation dependencies. Completed summaries are deduplicated by job ID and limited to configured retention (seven days by default). Index file free pages are returned to the OS only by explicit offline compaction; ordinary publication bounds rows, while `manage_storage --compact-indexes` performs `integrity_check` and `VACUUM`. HTTP results retain cursor/generation/freshness behavior; rebuilding a cache is different from migrating the record catalog or backing up entity SQLite.

## Failure modes and extension points

Library-owned typed JSON path fields are stored in portable format version 1 relative to the owning universe and resolved by the shared [LibraryReferenceService](../../zet/services/library_reference_service.py). The offline [normalizer](../../zet/scripts/normalize_library_references.py) applies explicit old-root mappings and verifies records without constructing `ZetApp`; run it only after compatible readers are deployed and Zet/harvesters are stopped. See [DATA_MODEL](../DATA_MODEL.md) and [ADR 0011](../DECISIONS/0011-portable-library-references.md).

- Wrong universe/request context can target the wrong store; queue/results must remain owned by the bound universe.
- Older or incomplete record catalogs fail validation with a migration instruction. Entity initialization can migrate an older database with a backup; it rejects a newer unsupported version.
- Usage protection can block archive/replace/merge operations. Preserve logical-reference semantics and operation previews rather than bypassing protections with raw SQL/file deletion.
- Pipeline reconciliation deactivates logical references in the same transaction when it archives their images. Active logical-reference writes reject archived image targets; the preview-first `zet.scripts.repair_archived_reference` command handles an explicitly verified existing mismatch without initializing or synchronizing the app.
- Inventory synchronization restores an archived local publication only when its origin key and exact ID-addressed image path match a current verified lock and its stored bytes still match the checksum. It restores references still bound to that image in the same transaction; historical duplicate publications remain archived. Explicit relocking also restores a verified existing publication before costume classification. Fixing paths alone does not change previously archived catalog statuses.
- Phase and costume deletion preserve current Narrative consumers; a blocked costume deletion reports each Story/Scene reference and links to the editable scene when its record IDs resolve.
- Derived index corruption or stale generations can affect discovery while authored files remain intact. Inspect error/freshness reporting before choosing a rebuild; the machine-local index lives under configured `Storage.Root/Indexes`, outside Git/Dropbox and the authored library. The rebuild CLI uses the configured universe binding; indexes remain disposable and are not copied during storage cutover.
- Add new reusable library actions in focused services and expose them through existing app/router patterns. Add indexed discovery kinds through source scanning and list providers; inspect pagination/freshness contracts in source and obtain approval for any new coverage. Do not make candidates searchable approved images merely by adding them to a folder scan.

## Tests and design evidence

[Testing](../Testing.md#approved-fast-scenarios) owns current validation. S1 exercises source authoring and seeded Narrative image display; S2 consumes prerequisites and publishes local locks. Neither proves full entity import/merge/archive, usages, schema migration, universe lifecycle, or derived-index integrity/pagination. No dedicated catalog/index scenario remains; inspect source contracts and obtain approval before adding coverage.

[ADR 0001](../DECISIONS/0001-library-authority-and-derived-index.md) records store boundaries; [ADR 0006](../DECISIONS/0006-atomic-image-inventory-edits.md) records preferred-reference and atomic editor-save behavior. [Library Structure](../../Docs-Joe/Library%20Structure.md) is a preserved proposal, not a complete description of current implementation.

## Narrative consumers and legacy imports

Narrative scene/target JSON participates in entity usage discovery. Live element
asset IDs, logical keys and legacy-image bindings protect catalog images; archived
source documents in migration provenance are not live consumers. Authoring changes
refresh usages. Phase/costume deletion checks current Narrative consumers before moving files. Costume deletion selects literal costume-qualified local origins (slug or display name) and exact character/phase/costume catalog classifications; older checksum-only origins require classification and must never imply ownership of every costume in a phase. The same selected asset IDs govern protection and purge. A blocked costume delete includes each Story/Scene title, reference locator and a Narrative scene link when the authored records can be resolved; unreadable records retain their usage path and locator in the reported context.

Migration imports use `legacy_scene` and `legacy_reference` origins and stable origin
keys; character pipeline reconciliation cannot obsolete them. Imports preserve bytes,
checksums and provenance. Scene deletion removes its usage, not the historical image
asset. The authoritative catalog is backed up before apply; the derived index remains
rebuildable and is not a substitute for that backup. Five old managed-image records
were found in old-library Git but their PNGs were absent from both working files and
Git; they remain visible migration review issues.

Image detail reads use targeted catalog queries. Search owns pipeline-image
synchronization; entity, variant, set, and facet option reads do not independently
repeat that scan. Editor PATCH saves metadata, organization, asset descriptors, and
preferred reference together, then refreshes usages and the derived index once.
Preference changes retain prior active keys so existing consumers continue to resolve.

The [2026-10-14 reference audit](../../plans/completed/costume-reference-integrity.md)
records the costume deletion fix and read-only live catalog findings. Its two usage
tracking defects were addressed in the [entity usage integrity plan](../../plans/completed/entity-usage-reference-integrity.md): paired usages remain anchored
to their direct asset, and refresh reports invalid endpoints while retaining valid
ones. The audit also records an active key bound to an archived image in the live
catalog; that pre-existing record was not repaired by the code change.

## Reconstruction imports (2026-10-14)

Image Generation reconstruction imports use the existing new-asset flow. They retain analysis source identity/hash, model, extracted content, destination style, final render prompt and result seed. Analysis provenance does not set the editable-source/replacement binding and cannot update a pipeline lock through the source-update action. Existing checksum deduplication still applies. See [data model](../DATA_MODEL.md#style-and-reconstruction-records-2026-10-14).

V2 imports also retain target and correction ancestry. Quick Character publication keeps original evidence under its `source` set role and approved transformed images under explicit view roles; an axe-bearing original is not an approved axe-free output. Provenance records actual candidate correction/report/seed data. No automatic replacement, preferred-key update or pipeline lock mutation accompanies reconstruction/true-up.

Minor Character workspaces separate working selection from explicit per-view Inventory locking. A front can be locked without other views. Locking a replacement changes the current reference-set role association and preserves previous assets; selecting or editing workspace inputs does not change Inventory. Published assets reopen their owning workspace. Source evidence remains distinct from output views. See [ADR 0014](../DECISIONS/0014-minor-character-workspaces.md).

## Unavailable volume integrity (2026-10-17)
Root identity/availability checks and observed-catalog markers prevent replacing missing authoritative state. SQLite opens observed catalogs in existing-file mode. Derived index scans propagate unreadable directories/sources and retain the committed generation when a scan is incomplete. A missing/corrupt catalog requires restoration, independently of index rebuilds. See [storage recovery](STORAGE_RECOVERY.md).
