# Scene Builder and 3D layout archive

Archived on 2026-10-12 when Narrative became the active dashboard story workflow.
This directory is outside the active Python package and served static directory.
No archived module, browser script, geometry compiler or Three.js asset is loaded
by the running dashboard. See [manifest](manifest.json) for file hashes and the
original Git revision.

## Preserved implementation

- `zet/models/scene_layout.py`: SceneLayout3D, pawn and camera records.
- `zet/services/scene_layout_service.py`, `scene_layout_planner.py`,
  `scene_background_service.py`, `scene_spatial_contract.py`: measurement,
  projection, parent-frame grouping, background framing and spatial guidance.
- `zet/web/static/scene_layout.js`, `scene_layout_framing.js`, and vendor Three.js:
  interactive stage/camera controls, undo/redo and framing math.
- `layout-ui.html`, `layout-dashboard-bridge.js`, `layout-styles.css`: integration
  controls and styles. Style comments name original source locations; recover
  surrounding media-query context from the recorded revision when restoring.
- Dedicated scene compiler/render/review/batch/interview services and experimental
  utilities are also retained. `app-facade.py`, `web-routes.py`, and dashboard
  fragments are historical integration excerpts, not executable entry points.

## Future Narrative integration

Restore only the needed geometry capability into a focused reusable service and
a mountable editor. Do not reconnect StoryService or revive the retired queue,
interview, review, or render-target lifecycle. Narrative IDs, backdrop/subscene
membership, library bindings, frozen jobs and assembly sources remain authoritative.

The original layout uses meters internally, imperial measurements at the UI, and
layout version 3 immediate-parent coordinate frames. Membership conversion preserves
world placement; camera projection governs scale, facing, overlap and ground joins.
Saved legacy layouts are preserved in the source libraries, migration provenance
and migration backup; they were not converted into Narrative coordinates.

Three.js was version 0.186.1. Its package metadata and MIT license are retained
here. Reintroducing a production dependency or adding geometry tests requires
Joe's approval. There is no maintained runnable geometry test suite in this archive.

## Data and rollback

The migration manifest is [Legacy_Narrative_Migration.json](../../Config/Legacy_Narrative_Migration.json).
The offline command is `python3 -B -m zet.scripts.migrate_narrative_scenes`:
`prepare`/`dry-run` are read-only; `apply`/`resume` require the dashboard stopped;
`verify` checks destination counts, ordering, memberships and image checksums.
Every mode requires explicit source, destination, legacy-library, manifest and
universe arguments. It does not construct ZetApp or dispatch model/render work.

Moonsea's `_state/NarrativeMigration/journal.json` records the backup location and
reserved/completed scene IDs. The backup contains the pre-migration SQLite catalog,
existing Narrative stories, and the two complete legacy source story folders.
Original libraries and other legacy stories remain unchanged. The empty Collision
draft has an additional archival copy under `_state/NarrativeMigration/archive`.

For rollback, stop the dashboard and first back up any subsequent user changes.
Use the journal to identify migration-owned records/assets. Restore the catalog and
Narrative snapshot only when doing so will not erase later work; otherwise remove
only migration-owned additions through a reviewed selective rollback. Imported
image files are independent catalog assets and must not be deleted blindly.
