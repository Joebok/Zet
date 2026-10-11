# 0001 — Separate authored library authority from derived discovery

Status: current implemented boundary; retrospective.
Record date: 2026-10-11. Historical decision dates are unknown.

## Context

Zet now has authoritative entity-centered image SQLite, a retained record image catalog, and a separate machine-local library index. Calling all three a "catalog" can cause an agent to choose a destructive or irrelevant rebuild/migration operation.

## Decision

Treat universe `catalog.sqlite3` plus `images/` as authoritative entity image state. Treat record `ImageCatalog/` as separately persisted metadata still used by current services. Treat `LibraryIndexRepository`'s local database as derived discovery/history/dependency state rebuilt from sources. Index roots must stay outside Git and Dropbox.

## Rationale

Repository class contracts explicitly identify the entity store as authoritative and the index as rebuildable/machine-local; index root validation enforces its placement. [Library Structure](../../Docs-Joe/Library%20Structure.md) gives intent for entity/asset/reference/usage separation. A complete historical explanation for coexistence of the two authored catalog systems is unknown.

## Alternatives and tradeoffs

No evidence establishes that one unified store was rejected in a documented decision. As retrospective analysis, coexistence introduces coordination/callback and naming complexity but retains current consumers; unifying stores would be a separate migration task, not a documentation fix.

## Consequences

Trace library writes through their owning repository/service and index callbacks. Preserve stable references and usage protections. Do not delete or regenerate authored SQLite using cache recovery guidance. Distinguish format migrations from discovery reconciliation and confirm CLI universe binding before executing either.

## Related code and documentation

[EntityLibraryRepository](../../zet/repositories/entity_library_repository.py), [ImageCatalogRepository](../../zet/repositories/image_catalog_repository.py), [LibraryIndexRepository](../../zet/repositories/library_index_repository.py), [LibraryIndexService](../../zet/services/library_index_service.py), [ZetApp.from_config](../../zet/app.py), [library component](../COMPONENTS/LIBRARY.md), [data model](../DATA_MODEL.md).

Verification update after V5 recovery: use [Testing](../Testing.md) for approved scenarios and explicit coverage gaps. The original dedicated Python tests were retired; their evidence is available with `git show 2d0e1a9:tests/<filename>.py`, not as current runnable checks.
