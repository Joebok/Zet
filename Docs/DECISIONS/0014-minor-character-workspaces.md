# 0014 - Persistent Minor Character workspaces

Status: accepted for local implementation, 2026-10-15.

## Context

The Quick Character Wizard's dialog and separate drafts made visual iteration awkward. Joe wants one named workspace per Minor Character, independent of existing character/phase pipelines, with inputs beside candidate/reference comparisons. Selection must enable subsequent generation without publishing images.

## Decision

`MinorCharacterService` extends the existing wizard engine and retains its universe-local `_state/QuickCharacterWizard` store and IDs. Names are unique after trimming/case folding. Version 2 records gain optional workspace fields rather than introducing a catalog migration. Existing active and published sessions are adopted; published sessions remain editable with their prior publications retained as locks. Duplicate legacy names expose the newest workspace and most recent per-view locks; superseded records become aliases when the canonical workspace is edited, without merging candidate histories or deleting their files.

Selection and locking are independent per view. A selected front drives other views; locking publishes only the chosen view into Inventory. Front alone is sufficient. Replacing a lock changes the current reference-set association but preserves immutable previously published assets. Other view selections/locks survive front reselection. Minor Character assets use candidate-based IDs and carry their workspace owner in provenance. Current Inventory sets use distinct labels to coexist with other named reference sets.

Automatic suggestions run in a separate advisory work lane and do not hold the character's rendering queue. A completed image is selectable/lockable and can drive the next render while its review is pending or failed. Interrupted suggestions can be left unfinished without losing the image.

Original references retain entry order and stable IDs. Primary identity controls analysis order; the comparison reference controls only the display. Reference replacement retains previous snapshots for submitted jobs. Candidates freeze their rendering inputs so subsequent input edits do not discard results or change submitted work. The shared original-pixel reconstruction policy and universe isolation remain unchanged.

`/api/minor-characters` exposes the ongoing workspace. The former wizard routes delegate to the same service as compatibility adapters; the dialog and draft picker are replaced by the list/editor page. Existing character/phase prerequisites are not applied to this page. Automated review remains optional advice, with no requirement for model approval, three-view completion or formal locking before generating another view.

## Consequences and verification

Persisted selection and lock data is retained internally, without exposing a history-management process. Current catalog publication is separate from mutable workspace inputs. The former wizard engine remains reusable for rendering/analysis; library writes stay in the existing publication service.

See the [completed implementation plan](../../plans/completed/minor-characters-workspace.md) and [local character component](../COMPONENTS/LOCAL_CHARACTERS.md). Disposable service/browser checks exercise this workspace; the maintained three E2E scenarios provide regression checks, not live image-quality coverage.

Prompt iterations own four nullable render slots. Additional renders and regeneration replay the submitted payload with fresh seeds; refinements start new iterations. Clearing/replacing board membership retains candidate files and selection/lock associations. This prevents later form edits from silently changing an older iteration's prompt. Legacy candidates adopt individual boards. Full-size review compares the designated original with rendered slots in the current iteration and permits selection directly.
