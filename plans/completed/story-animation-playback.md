# Story animation playback repair
Status: complete (local implementation and artifact; hosted rollout awaits authorization)

## Goal
Make scene addition, default preview and standalone HTML playback work; produce an
animation of The Celestial Sphere's first three scenes without changing its source art.

## Current behavior
`narrative.js` selects the last asset key after binding instead of matching source
identity. Added shots remain client-only until Save; preview/export read saved
instructions, and the HTML route always returns an attachment. Live read-only
inspection found three pinned sources and an empty saved timeline.

## Desired behavior
The clicked scene is added even when already pinned. Preview/download save current
controls first, report errors, and contain all scene images and lettering. Preview
renders inline; offline HTML plays the three ordered scenes with default settings.

## Impact analysis
Owners: `zet/web/static/narrative.js`, its import version in `zet.js`,
`zet/web/narrative_router.py`; player compiler only if playback exposes a defect.
Documentation: Narrative component and Testing. No schema change or dependencies.
S1/S3 cover surrounding Narrative regressions; animation requires disposable checks.

## Invariants and constraints
Preserve story/universe isolation, revision checks and locked source bytes. No live
AI calls, permanent tests, deployment or production timeline writes.

## Implementation steps
### WP1 — Correct scene identity and pending edits
- Dependencies: none.
- Files: narrative.js, zet.js.
- Work: match bound assets by source identity, retain controls across render, save
  current timeline before preview/download, route errors through action handling.
- Acceptance: repeated source selection adds the named scene; unsaved settings
  appear in preview/export and survive adding/removing shots.
- Validation: disposable Playwright journey and JavaScript syntax checks.
- Status: complete.

### WP2 — Inline preview and standalone playback
- Dependencies: WP1.
- Files: narrative_router.py; compiler if required; disposable output.
- Work: honor preview query with inline response; compile real pinned assets with
  first three scenes into a local standalone HTML artifact.
- Acceptance: embedded images decode, playback/seek/navigation work offline.
- Validation: disposable browser checks; approved `npm.cmd run test:e2e`.
- Status: complete.

### WP3 — Record results and review
- Dependencies: WP1, WP2.
- Files: Docs/COMPONENTS/NARRATIVE.md, Docs/Testing.md, this plan.
- Work: document changed behavior, validation and deployment boundary; review diff.
- Acceptance: relevant checks pass and working artifact is delivered.
- Validation: `git diff --check` and final diff inspection.
- Status: complete.

## Risks and alternatives
The hosted app uses a release checkout; local code changes do not deploy it.
Existing saved instructions must not be silently replaced in the live library.

## Progress and decisions
Read live story and animation APIs only. The three requested scenes are already
pinned, including separable lettering; use these frozen assets for the artifact.

Visual review found a player boundary bug: inclusive shot ends displayed the previous
image at the exact next-shot start. The compiler now uses exclusive shot ends;
disposable checks compare boundary pixels against the following millisecond.

## Final results
Scene selection, retained edits, revision-checked save-before-preview/export, inline
preview and exact next-shot display are fixed locally. Created
`test-results/celestial-animation/The Celestial Sphere.html`: 24 seconds, 3 ordered
shots, default framing/cuts, 3 embedded artwork images and 4 embedded lettering layers.
All seven decode offline; screenshots of all three scenes inspected.

`npm.cmd run test:e2e` passed all four scenarios (final 40.1s). Disposable Chromium
checks passed scene identity/re-add, retained draft, unsaved preview/download,
invalid-save reporting, offline playback/navigation and boundary pixels with no page
errors. Python AST, JavaScript syntax and diff checks passed. No permanent tests,
dependencies or live AI calls. The hosted runtime and saved live timeline are
unchanged; publishing fixes and saving the timeline there require authorization.

