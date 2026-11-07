# Character container template review diagnostics
Status: complete
Related: Valindia Adult Head Image Edit review failures, 2026-11-07

## Goal
Make container template analysis produce reviewable, owned corrections and explain rejected findings without changing masters automatically.

## Current behavior
`CharacterContainerTemplateService._review_job` rejects an entire response on the first noncanonical view label. Its prompt omits the Head Image Edit ownership rule. The browser displays only a generic error. Two saved Valindia responses demonstrate both problems; they remain untouched.

## Desired behavior and constraints
Recognize canonical views and existing view expressions, validate findings independently, and show bounded reasons for rejection. Only selected, previewed corrections may reach masters. No permanent test scenario or live model check.

## Implementation packets
### WP1 — Review contract and validation
- Files: `zet/services/character_container_template_service.py`.
- Dependencies: none.
- Work: specify owned sections and canonical view values; normalize recognized view tags; validate each suggestion and persist diagnostics.
- Acceptance: valid Head Edit findings survive alongside invalid ones; all-invalid and empty responses have distinct outcomes.
- Validation: disposable isolated replay of saved response shapes.
- Status: complete. Saved response replay passed (0/2 and 1/4 valid/rejected).

### WP2 — Failure presentation
- Files: `zet/web/static/character_asset_container.js`.
- Dependencies: WP1 diagnostic fields.
- Work: show failure stage and rejected finding details in the existing panel.
- Acceptance: usable findings remain selectable; rejected findings explain their source and reason.
- Validation: disposable isolated browser check.
- Status: complete. Isolated Chromium check passed failed and mixed-result displays.

### WP3 — Validation and knowledge
- Files: `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, `Docs/Testing.md`, this plan.
- Dependencies: WP1–2.
- Work: run disposable checks, approved fast suite, diff review; document observed behavior and results, then archive plan.
- Acceptance: checks pass and no unintended changes.
- Validation: `npm run test:e2e`; `git diff --check`.
- Status: complete. Four approved fast scenarios passed; Python compilation, JS syntax and diff checks passed.

## Final results
The review request now specifies canonical views and Head Edit ownership. Known view tags normalize; each finding is checked independently, and rejected findings carry source, reported views and bounded reasons. The panel displays the validation stage and diagnostics. Existing Valindia failures remain unchanged. The disposable checks read the saved model answers without live inference or library writes. `npm run test:e2e` passed 4/4 (44.6s); `python3 -m py_compile`, `node --check`, and `git diff --check` passed. No permanent test was added and no live model/render check ran.
