# Library, universes, and discovery

This component owns library service interactions. [DATA_MODEL](../DATA_MODEL.md) owns store layouts and identifiers; [INVARIANTS](../INVARIANTS.md) owns isolation/integrity contracts.

## Entry points and responsibilities

- [UniverseService](../../zet/services/universe_service.py): discover/select/create universes and bind configuration. [ZetApp.from_config](../../zet/app.py) constructs the bound services. [create_app](../../zet/web/app.py) caches per-universe apps and binds requests through header/query context.
- [EntityLibraryService](../../zet/services/entity_library_service.py) and [EntityLibraryRepository](../../zet/repositories/entity_library_repository.py): authoritative images, entities/variants, reference sets, descriptors/facets/tags, stable logical references, usage, merge/archive/replace workflows. [LibraryDeletionService](../../zet/services/library_deletion_service.py) coordinates removal with local workflow sources and the entity catalog.
- [ImageCatalogService](../../zet/services/image_catalog_service.py) and [ImageCatalogRepository](../../zet/repositories/image_catalog_repository.py): a separate record-oriented catalog combining managed metadata and existing pipeline/story images. It remains wired into app/story reference services; entity SQLite has not replaced every catalog consumer.
- [LibraryIndexService](../../zet/services/library_index_service.py)/`LibraryIndexReconciler` and [LibraryIndexRepository](../../zet/repositories/library_index_repository.py): derived local generations for dashboard paging, source payload reuse, errors, work/history, and compilation dependency fingerprints. `ZetApp._indexed_list_rows` supplies additional list rows; record catalog writes call `refresh_library_index`.

## Inputs, outputs, and flow

Configuration selects a library container; a universe descriptor binds the creative root. Imports/publications validate image bytes and store image metadata/relationships. Logical references provide durable consumer bindings. Story reference resolution combines entity and record/pipeline sources into [ImageReferenceRow](../../zet/models/story.py) data, including availability/reason and source identity. Local approved character images are published through [LocalAssetStoreService](../../zet/services/local_asset_store_service.py).

Reconciliation scans authored/queue sources, fingerprints content, reuses cached parses, records malformed sources as errors, builds a generation, and publishes it for queries. HTTP results expose cursor/generation/freshness information; rebuilding a cache is different from migrating the record catalog or backing up entity SQLite.

## Failure modes and extension points

- Wrong universe/request context can target the wrong store; queue/results must remain owned by the bound universe.
- Older or incomplete record catalogs fail validation with a migration instruction. Entity initialization can migrate an older database with a backup; it rejects a newer unsupported version.
- Usage protection can block archive/replace/merge operations. Preserve logical-reference semantics and operation previews rather than bypassing protections with raw SQL/file deletion.
- Derived index corruption or stale generations can affect discovery while authored files remain intact. Inspect error/freshness reporting before choosing an authorized rebuild; CLI scripts do not universally bind a universe through `ZetApp`.
- Add new reusable library actions in focused services and expose them through existing app/router patterns. Add indexed discovery kinds through source scanning and list providers; inspect pagination/freshness contracts in source and obtain approval for any new coverage. Do not make candidates searchable approved images merely by adding them to a folder scan.

## Tests and design evidence

[Testing](../Testing.md#approved-fast-scenarios) owns current validation. S1 exercises source authoring and seeded Narrative image display; S2 consumes prerequisites and publishes local locks. Neither proves full entity import/merge/archive, usages, schema migration, universe lifecycle, or derived-index integrity/pagination. No dedicated catalog/index scenario remains; inspect source contracts and obtain approval before adding coverage.

[ADR 0001](../DECISIONS/0001-library-authority-and-derived-index.md) records store boundaries; [ADR 0006](../DECISIONS/0006-atomic-image-inventory-edits.md) records preferred-reference and atomic editor-save behavior. [Library Structure](../../Docs-Joe/Library%20Structure.md) is a preserved proposal, not a complete description of current implementation.

## Narrative consumers and legacy imports

Narrative scene/target JSON participates in entity usage discovery. Live element
asset IDs, logical keys and legacy-image bindings protect catalog images; archived
source documents in migration provenance are not live consumers. Authoring changes
refresh usages. Phase/costume deletion checks Narrative consumers before moving files.

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
