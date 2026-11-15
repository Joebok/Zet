# Minor Character Style and Front improvements
Status: active
Related specification: [Candidate Board](../../Docs/COMPONENTS/CANDIDATE_BOARD.md)

## Goal
Improve the Minor Character Style and Front experience while preserving the shared Candidate Board contract and treating zJoe as a read-only baseline.

## Current behavior
The Minor Character Asset Container renders cards without the list grid class. The board page places interview and its model picker inside a collapsed disclosure. Candidate review actions are already adapter driven. Front requires a locked Style candidate.

## Implementation steps
### WP1 — Compact Asset Container
- Dependencies: none.
- Files: `zet/web/static/minor_characters.js`, `zet/web/static/zet.css`.
- Work: Apply the shared card grid class to container view cards and constrain preview/fallback height to 160 px.
- Acceptance: Six cards wrap at desktop, tablet and phone widths. Links and lock status remain clear.
- Validation: Browser inspection at 1440, 768 and 390 px.
- Status: pending.

### WP2 — Page-owned improvement and model controls
- Dependencies: WP1.
- Files: `zet/web/templates/index.html`, `zet/web/static/minor_characters.js`, `zet/web/static/zet.css`.
- Work: Surface intake, interview, and prompt model choices, persist action-specific choices in session storage, and show proposal decisions in a page-owned Template Improvement panel. Preserve explicit accept/reject and saved interview state.
- Acceptance: Existing candidate review action opens the page panel with the correct evidence selected. Proposal results and effective model are visible after navigation/reload when available.
- Validation: Browser inspection and existing API state on isolated Tester workspace.
- Status: pending.

### WP3 — Style to Front handoff
- Dependencies: WP2.
- Files: `zet/web/templates/index.html`, `zet/web/static/minor_characters.js`.
- Work: Identify each view's source, link blocked Front to Style, provide Continue to Front after a Style lock, and expose Inventory navigation after published Front lock.
- Acceptance: Handoff controls follow authoritative lock/publication state across reload.
- Validation: Zet Test workspace exercise.
- Status: pending.

### WP4 — Exercise and verify
- Dependencies: WP1-WP3.
- Files: no production changes expected.
- Work: Exercise a new isolated ZetTester workspace bound to Joe Source through Style and Front, preserving zJoe as the baseline. Record results and cross-workflow smoke checks.
- Acceptance: Interview rejection and acceptance, prompt rewrite, Style lock, Front evidence, and Front publication are verified. Shared Candidate Board files and contract remain unchanged.
- Validation: Existing approved fast E2E scenarios, syntax checks, and `git diff --check`.
- Status: pending.

## Constraints
The Candidate Board component, stylesheet, and public adapter contract remain unchanged. Do not add maintained test scenarios or dependencies. Do not modify zJoe or unrelated user changes.

## Progress and decisions
- Verified zJoe is in Zet Test with completed Intake, two completed Style Drafts, and one pending Style proposal. Front is unpopulated and requires a locked Style image.
- Model overrides will use browser session storage and action-specific keys, remaining scoped to the active browser session.

## Validation
Record commands and actual results here before completion.
