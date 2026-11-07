# 0048 — Character image production uses Asset Containers
Status: accepted
Date: 2026-11-06

## Context

Character pipelines used batch runs, mode-specific working state, progression,
ranking and an Activity list. The operator workflow is moving to the shared image
production pattern in [Image Production Abstraction](../../Docs-Joe/Image%20Production%20Abstraction.md)
and Narrative boards: one stable eight-slot Candidate Board per target view.
Character pipelines still need their existing compilers and explicit source
choices, while Assembly and Dressing retain stricter reference prerequisites.

## Decision

Each universe, character, phase and pipeline has a persistent Asset Container;
Costume Dressing adds the canonical costume. Each view has exactly one mixed
Draft/Final Candidate Board. The operator prepares, dispatches, reviews, selects,
locks and clears images on that board. A lock of either quality publishes the
image to Inventory. Cross-container inputs require a current selected lock and
approved publication. New source listings use container locks; legacy state is
read only for migration and saved-reference compatibility.

Both Narrative and Character send frozen image requests through
`ImageProductionService`. This shared boundary validates render identity,
publishes AI_Proxy image asks, recovers matching Character attempts, and validates
and collects completed images. Pipeline services continue to persist their own
candidate and job state and place returned images in their slots.

The board side of Inventory publication is journaled beside the container.
Recovery uses the catalog receipt to distinguish commit from rollback, and it
must preserve a board revision newer than the journal's committed snapshot. A
recovered lock cannot overwrite a later selection, unlock, or clear.

Costume rename retains the container ID and board while moving its storage to
the new canonical costume slug and rewriting paths captured beneath that
container. Rename waits for active candidates and unresolved publication
journals to settle. Costume deletion includes board-published Inventory assets
in the explicit deletion preview and archives the container with its candidate
evidence.

Character batch routes and operation summaries are not mounted. Startup does not
resume legacy character runs. The Batches page, Run All Remaining and Character
Activity staging are retired. Legacy files remain intact for import verification
and rollback; the migration CLI is dry-run by default and never applies to the
live library without a reviewed report, verified backup, quiescence and explicit
approval.

Head containers can retain distinct Draft and Final phase-change source choices
inside the container's shared source settings. A new candidate uses the choice for
its requested quality. Sources can be managed uploads or current locked/published
FRONT candidates from another phase. Migration copies an available upload into
the target container and imports a locked-phase choice only when its source maps
to an imported current Final FRONT; otherwise the choice and reason remain in
migration metadata for review. This preserves source intent without restoring
quality-specific boards or accepting an unlocked legacy image as a source.

Template improvement is an optional container authoring action grounded in one
finished board candidate. Store the copied evidence and proposal under that
container, preserve the submitted prompt and ordered inputs, validate the
proposed Character.md, and show a preview compiled for the same view using the
candidate's captured inputs. The operator explicitly accepts through the shared
source editor with a master revision check. This changes only future requests;
it does not create an automatic trial render or gate board work.

## Rationale

The Asset Container is the persistent workflow identity; batch membership is no
longer part of the operator's production sequence. A single mixed-quality board
keeps slot identity stable while quality belongs to each candidate. Keeping source
resolution at the container boundary preserves character-specific prerequisites
without reintroducing batch progression or automatic rendering.

## Alternatives and tradeoffs

Keeping legacy batch endpoints mounted would let old UI paths create and resume
work that the new operator workflow cannot represent. Keeping legacy locks in
ordinary current-source listings could also make an empty new container appear
ready from old state. Both behaviors are retired. Migration preserves valid
current Final publications; Draft-only history does not seed a board.

## Consequences

- `CharacterAssetContainerService` owns new persistent board and source state.
- `ImageProductionService` owns shared image request transport and result collection.
- `LocalAssetSourceService.list_sources` defaults to current container locks;
  `include_all=True` remains a compatibility read for saved legacy keys.
- Legacy batches are not automatically migrated or deleted. Applying a reviewed
  report is a separate live-library operation.
- Disposable Narrative and Character browser lifecycle checks are recorded in
  the completed migration plan.

## Related code and documentation

- [Character Asset Container service](../../zet/services/character_asset_container_service.py)
- [Character migration service](../../zet/services/character_container_migration_service.py)
- [Completed character pipeline migration plan](../../plans/completed/character-image-production-workflow.md)
- [Local Characters](../COMPONENTS/LOCAL_CHARACTERS.md)
- [Dashboard UI](../COMPONENTS/DASHBOARD_UI.md)
