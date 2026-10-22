# 0029 — Recoverable local asset publication
Status: accepted
Date: 2026-10-22

## Context
Local character locks update authoritative entity-catalog rows and a separate
universe-local `local_assets.json`. SQLite cannot transact with that JSON file.
Previously a chain could leave approved catalog rows behind when a later image or
the local state write failed. Individual publication also split classification,
status restoration and logical-reference changes across transactions.

## Decision
Stage image bytes, then apply every catalog mutation for a chain in one SQLite
transaction. Commit a `catalog_publication_receipts` row keyed by a 32-character
operation ID with the asset IDs published or reused. Before entering that
transaction, journal the previous local state. In the transaction's pre-commit
callback, journal the intended next state and atomically write it to the local
workspace. Recovery checks the receipt: a committed operation finishes publishing
the next local state; an uncommitted operation restores the previous state and
removes only newly created final files listed in its staging plan. Startup recovery
and local-state reads run this recovery under the workspace lock.

## Rationale
The receipt is the durable authority for whether catalog publication committed.
Writing next local state before the catalog commit avoids a committed catalog row
without its prepared local projection; a failed commit restores the saved prior
state. The journal makes either interruption point replayable without archiving
reused assets or changing their existing origin identities.

## Alternatives and tradeoffs
SQLite and filesystem JSON do not share an atomic transaction. Keeping a separate
journal/receipt adds recovery state and schema migration, but allows idempotent
recovery after process interruption. Automatically compensating by archiving
catalog rows was rejected because an operation may reuse rows and logical
references already consumed elsewhere.

## Consequences
Entity catalog schema version 4 adds the publication receipt table. Local lock
JSON remains schema version 1. Old catalogs back up before migration. Inventory
publication labels are supplied by batch metadata or a descriptive character,
phase, pipeline and view fallback; historical labels are not rewritten.

## Related code and documentation
[LocalAssetPublicationRecoveryService](../../zet/services/local_asset_publication_recovery_service.py),
[LocalAssetStoreService](../../zet/services/local_asset_store_service.py),
[EntityLibraryService](../../zet/services/entity_library_service.py),
[EntityLibraryRepository](../../zet/repositories/entity_library_repository.py),
[library](../COMPONENTS/LIBRARY.md), [data model](../DATA_MODEL.md), and
[remediation plan](../../plans/completed/code-review-remediation.md).
