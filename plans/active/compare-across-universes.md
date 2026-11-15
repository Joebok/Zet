# Compare across universes
Status: active

## Goal
Compare current locked character pipeline/costume views independently across universes. Retain side selections per tab and cache loaded images only during the page visit.

## Implementation packets
### WP1 — Side API
- Files/interfaces: `phase_comparison_service.py`, `zet/app.py`, `zet/web/app.py`; `GET /api/compare/side`.
- Acceptance: request universe scopes character/phase discovery and current lock images. Costume templates remain selectable without locks.
- Status: implemented.
### WP2 — Selectors and paired view navigation
- Files/interfaces: `index.html`, `zet.js`.
- Acceptance: independent four-level selectors, session restore and shared canonical view navigation.
- Status: implemented, targeted browser verification pending.
### WP3 — Page image cache and compact layout
- Files/interfaces: `zet.js`, `zet.css`.
- Acceptance: lazy browser image cache, side-by-side images and compact selectors.
- Status: implemented, targeted browser verification pending.
### WP4 — Knowledge and validation
- Files/interfaces: Dashboard UI, Local Characters, Code Map, this plan.
- Acceptance: document implementation and observed checks; archive when complete.
- Status: in progress.

## Validation
Planned: JavaScript/Python syntax, approved E2E suite, disposable two-universe browser check, `git diff --check`.
