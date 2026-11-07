# Fix field checkbox defaults
Status: active
Related issue/specification: User request with attached Template Improvement screenshot

## Goal
Keep field-description checkboxes compact and inline with their captions while preserving larger checkboxes used to accept or reject multi-line correction proposals.

## Current behavior
`zet.css` gives labels a grid layout and generic inputs a 36px minimum height and padding. Template Improvement adds a grid label rule. Its source-choice checkbox therefore separates from its caption and inherits input sizing. Correction-choice checkboxes have an explicit larger size and a dedicated review grid.

## Desired behavior
Ordinary checkbox fields show an 18px checkbox inline with a wrapping caption. Correction-choice checkboxes retain their dedicated layout and size. No API or stored data changes.

## Impact analysis
CSS in `zet/web/static/zet.css`, stylesheet cache key in `zet/web/templates/index.html`, and checkbox guidance in `Docs/UI_STYLE_GUIDE.md`. The existing S2 scenario covers character container workflows but does not assert checkbox geometry; use disposable browser inspection for that behavior.

## Invariants and constraints
Preserve correction-choice review affordances and all workflow behavior. Do not add a permanent test scenario or dependency.

## Implementation steps
### WP1 — Correct shared checkbox defaults
- Dependencies: none.
- Files/interfaces: `zet/web/static/zet.css`.
- Work: Set compact dimensions and remove text-input padding/minimum height for ordinary checkboxes; place direct checkbox field labels inline and allow caption wrapping.
- Acceptance: An ordinary field checkbox uses the compact inline default.
- Validation: Chromium computed-style and label-toggle check.
- Status: complete.

### WP2 — Fix Template Improvement field choices
- Dependencies: WP1.
- Files/interfaces: `zet/web/static/zet.css`, `zet/web/templates/index.html`.
- Work: Override Template Improvement's grid label rule for field checkboxes and refresh the stylesheet cache key. Keep correction-choice rules intact.
- Acceptance: Source choices are compact and inline; correction choices retain their larger review layout.
- Validation: Disposable browser check at desktop and narrow widths.
- Status: complete.

### WP3 — Record and verify
- Dependencies: WP2.
- Files/interfaces: `Docs/UI_STYLE_GUIDE.md`, this plan.
- Work: Document the distinction, record checks, and archive the completed plan.
- Acceptance: The style convention is documented; no permanent test is added.
- Validation: Focused S2 scenario, `git diff --check`, final diff review.
- Status: complete.

## Validation
Chromium disposable check passed at 1280px and 390px: ordinary field checkbox computed to 18×18px with zero padding/minimum height, caption remained inline and wrapped on narrow width, label click toggled it, and correction-choice checkbox remained 36×36px. `npm.cmd run test:e2e -- --grep "character-to-costume"` passed all four approved scenarios (the repository runner executed the full suite despite the grep argument). `git diff --check` passed. Final diff review found only the planned stylesheet, cache key, style guide, and plan changes.

## Risks and alternatives
CSS `:has()` is already used by this stylesheet and supported by the dashboard browser target. The template-specific override preserves grid review choices.

## Progress and decisions
The larger correction-choice checkboxes are intentional and excluded from the compact field rule. No maintained tests, dependencies, APIs, or stored data changed.

## Final results
Field checkboxes now display compactly beside captions, including in Template Improvement. Larger correction-choice checkboxes retain their dedicated review layout. Validation passed as recorded above.
