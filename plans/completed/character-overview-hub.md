# Character Overview Hub
Status: complete

## Goal
Replace the old costume grid and character progress page with a scoped character hub for Setup, locked base images, and costumes. Retain incomplete character/phase authoring.

## Implementation packets
### WP1 — Scoped data and thumbnails
- Dependencies: none.
- Files/interfaces: overview service, scoped FastAPI routes, shared bounded-thumbnail service.
- Work: return ordered locked views for one selected phase; expose universe-checked cached thumbnails; never start work or read other phases.
- Acceptance: locked sources have bounded previews; missing locks have explicit empty records.
- Validation: disposable API check using isolated fixture data.
- Status: complete.

### WP2 — Hub UI and navigation
- Dependencies: WP1.
- Files/interfaces: `index.html`, `zet.js`, page controller, `zet.css`.
- Work: one Character Overview destination with sticky per-context disclosures, view links, template editors, lazy images, and setup controls shown until Character.md validates.
- Acceptance: old overview links reach the hub; cards open the matching pipeline/view/costume; no timer or tab-return polling.
- Validation: disposable browser check for navigation, sticky state, thumbnails, and idle network activity.
- Status: complete.

### WP3 — Retire unused progress/grid code and update knowledge
- Dependencies: WP2.
- Files/interfaces: workspace summary/model/facade, dashboard and local-character docs, code map, approved S1 assertions.
- Work: remove only overview-only behavior; preserve story summary and character creation/upload; update owned docs and this plan.
- Acceptance: one Character Overview remains and S1 retains its existing upload purpose.
- Validation: `npm run test:e2e`; `git diff --check`.
- Status: complete.

## Constraints
Use current published Asset Container locks and universe ownership. A valid Character.md is the setup readiness gate. No new permanent scenario or live narrative check.

## Final results
Replaced the old costume overview with a selected-phase hub, cached bounded
thumbnails, context-scoped disclosures, view links, and conditional setup controls.
Removed the former overview page wiring and character summary API caller; retained
story summaries. Updated the approved S1 upload flow to cover an incomplete phase.
`npm run test:e2e` passed all four approved scenarios (42.1s). Python compilation,
JavaScript syntax checks, and `git diff --check` passed. No live narrative check ran.
