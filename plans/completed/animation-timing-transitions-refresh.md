# Animation timing, transitions, refresh, and ordering
Status: complete

## Goal and constraints
Implement the user-approved animation plan, preserving locked sources, revision fencing, existing edits, and the approved testing baseline. Update only the Celestial Sphere animation once; add no migration machinery or permanent tests.

## Work packets
- WP1: Fix 100% text endpoint timing and graph in `narrative.js`. Browser and syntax checks passed. Status: complete.
- WP2: Add positional version-2 transitions and timeline validation/resolution in the animation model and service. Disposable resolver checks passed. Status: complete.
- WP3: Render timed boundary transitions and white fades in the HTML compiler. Chromium checked the white midpoint and preview. Status: complete.
- WP4: Add revision-fenced scene refresh and content-based snapshots in the animation service and Narrative router. Chromium checked refresh and stale rejection. Status: complete.
- WP5: Add transition rows, scene ordering, refresh and input increments in Narrative UI. Disposable browser journey passed. Status: complete.
- WP6: Back up and convert the identified Celestial Sphere animation, update relevant documentation and ADR, run the approved E2E baseline and diff checks. Status: complete.

## Progress and decisions
The prior plan specifies detailed acceptance criteria and transition behavior. Existing story-animation plan remains active for unrelated work.

## Final results
Four fast E2E scenarios passed in 44.3s. Disposable Chromium journeys passed, including text endpoint, transition editing, white midpoint, reorder, refresh, stale revision, preview and download. Resolver checks covered overlap, cut holds, invalid overlaps and empty timelines. The production animation was backed up, converted from revision 78 to 79, read and compiled to HTML. Physical devices, live render services and exhaustive transition pixels were not tested. No permanent scenario was added.
