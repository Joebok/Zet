# 0007 — Stable render slots and durable Image Generation workspace
Status: accepted
Date: 2026-10-12

## Context
Narrative displays arriving images automatically. Character galleries previously contained only planned candidates, staged updates behind Refresh, and stopped polling during review. Image Generation already displayed eight positions, but browser storage owned their assignments and selection; results were appended in completion order.

## Decision
Use eight fixed positions per character view and one eight-slot Image Generation workspace per universe. Keep candidate/job identity independent of position. Shared presentation controls expose Generate, Add renders, Select/Unselect, Regenerate, Clear and render Retry; pipeline services continue owning prerequisite, gate, ranking, lock, publication and source semantics. Narrative records remain independent.

Character specifications retain initial definitions and slot maps. Run state owns changed maps, added candidate definitions, detached identities and targeted supplemental work. Added definitions survive existing rerun resets through the shared candidate merger. Each replacement gets a new candidate ID; clear detaches without removing historical bytes. Older views above capacity remain visible as legacy galleries and can be reduced explicitly.

Image Generation persists assignments and selection in `_state/ImageGeneration/workspace.json`, over existing persisted jobs. New job images occupy their child index rather than completion order. Submitted prompt/reference inputs and seeds persist for Retry. Generate/Regen use the current prompt; optional character Recompile builds it from current templates first, while prior asks keep their frozen inputs. The browser imports only job bindings recognized by that universe, once into an empty board; authored draft inputs remain browser-local and are universe-scoped.

## Rationale and tradeoffs
Stable positions let Joe compare candidates without ranking moving images. Distinct replacement identities prevent late old results from populating current slots. Retained artifacts preserve provenance and snapshots at the cost of disk usage; clearing a slot is not physical history deletion. After Joe’s follow-up correction, slot actions remain available while other renders run. An independent character slot collector uses a separate lock and persists pending identities; state transactions and unique candidate identities fence cleared/replaced outputs. Whole-batch destructive operations remain blocked while independent slot work is pending. There is no new event transport or production dependency.

## Consequences and validation
Character detail/summary, execution, advisory review and restart recovery consume merged active candidates. Superseded evaluations cannot apply to changed slot contents. Body ranking waits for gate eligibility before comparing survivors. Existing source refresh/recompile and lock/publication behavior remain separate actions.

The approved three-scenario fast suite passed after core integration and again after the follow-up slot fixes (3 tests, 23.0 seconds). Python compilation, JavaScript syntax checks and git diff --check also passed. Joe approved and the agent ran disposable checks for the reported deep-link, layout, current-prompt/Recompile and overlapping-slot issues, including Image Generation containment at three widths. These checks use prepared images/rankings. Full Body/Head generation and general restart recovery remain outside maintained coverage; no live rendering is implied.

## Related code and documentation
- [Slot contract](../../zet/services/render_slot_service.py), [character action boundary](../../zet/services/local_image_workflow_service.py)
- [Image Generation workspace](../../zet/services/image_generation_workspace_service.py), [generator](../../zet/services/ad_hoc_image_generation_service.py)
- [Local characters](../COMPONENTS/LOCAL_CHARACTERS.md), [data model](../DATA_MODEL.md), [testing policy](../Testing.md)
- [Implementation plan](../../plans/completed/standard-render-slots.md)
