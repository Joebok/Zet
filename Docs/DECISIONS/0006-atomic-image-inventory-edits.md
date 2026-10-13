# 0006 — Atomic image inventory edits and preferred references

Status: accepted
Date: 2026-10-12

## Context

The image editor previously saved fields, descriptors, and references through separate requests. It could leave partial updates, and asynchronous detail reloads could replace newer input. Search selected the first active reference alphabetically, so changing a key in the editor did not reliably change the displayed tag. Repeated metadata requests also synchronized pipeline inventory independently.

## Decision

Store `assets.preferred_reference_key` in entity catalog schema 3. Backfill approved images with the active key that the prior alphabetical selection displayed. An empty value explicitly selects the direct asset tag. Changing preference leaves older active aliases intact. Editor metadata, organization links, asset descriptors, and preferred-reference updates use one PATCH and one SQLite transaction. Detail reads are targeted; inventory search and reconciliation own pipeline discovery.

## Rationale

Existing templates and scenes may use earlier keys, so preference is separate from alias lifetime. A single transaction prevents partial edits. Search retains the current compatibility behavior after migration while allowing the editor to choose a different displayed key.

## Alternatives and tradeoffs

Continuing to infer preference from alphabetical order cannot represent an explicit user choice. Deactivating the previous key would break consumers that still use it. The entity catalog schema migration requires backup and backfill; it does not change reference-key resolution for existing consumers.

## Consequences

Editor PATCH validates key collisions and reports the saved canonical asset. Existing logical-reference management routes retain their reassignment behavior. If derived-index reconciliation fails after the catalog transaction commits, the API returns the saved asset with a refresh warning. Search refreshes when returning from the editor; editor fields are not populated by job-status polling.

## Related code and documentation

[EntityLibraryRepository](../../zet/repositories/entity_library_repository.py),
[EntityLibraryService](../../zet/services/entity_library_service.py),
[ZetApp](../../zet/app.py), [entity library API](../../zet/web/app.py),
[dashboard](../../zet/web/static/zet.js), [Library](../COMPONENTS/LIBRARY.md),
[Data model](../DATA_MODEL.md), [Invariants](../INVARIANTS.md), and
[implementation plan](../../plans/completed/image-inventory-save-navigation.md).
