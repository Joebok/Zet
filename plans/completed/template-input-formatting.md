# Regularize character and costume template edits
Status: active

## Goal
Normalize line endings and split recognizable packed bullets in active Character and Costume authoring and saves.

## Implementation steps
### WP1 - Shared formatting
- Dependencies: none.
- Files: new template formatting service.
- Work: normalize CR/LF variants and safely split clear bullet separators inside marked sections. Serialize UTF-8 using platform newline.
- Acceptance: Gemma sections produce 7, 10 and 10 bullets, formatting is idempotent, ambiguous prose stays intact.
- Validation: disposable Python replay.
- Status: in progress.

### WP2 - Wizard and uploads
- Dependencies: WP1.
- Files: Character Wizard, Costume Wizard, onboarding and costume services.
- Work: format before preview/publication and serialize masters consistently.
- Acceptance: preview matches saved text and CRLF uploads do not produce CRCRLF.
- Status: pending.

### WP3 - Editor and accepted improvements
- Dependencies: WP1.
- Files: source editor service/browser, proposal and post-render acceptance services.
- Work: format canonical saves and approved edits after matching against frozen source and before preview/diff/publication. Display server returned text without overwriting edits typed during save.
- Acceptance: format-only saves work and preview matches publication.
- Status: pending.

### WP4 - Verification and docs
- Dependencies: WP2, WP3.
- Files: Prompts docs, Testing.md, archived plan.
- Work: disposable checks, approved E2E suite and diff check. Record results.
- Status: pending.

## Constraints
No permanent test additions or live model/render. Do not modify test library or frozen prompts.

## Progress
Investigation confirmed packed bullets leak across view conditioning and collapse focused Head review line mapping.
## Results
- Gemma replay normalized Body Facts to 7 physical bullets, Head Front Description to 10 and Head Preserve to 10. Formatting was idempotent.
- Disposable checks passed for explicit view-tag separation, inline literal asterisks, CRLF/LF/CR/CRCRLF normalization, Windows CRLF serialization, and wizard observation splitting.
- Python compileall, JavaScript syntax check and git diff --check passed.
- npm run test:e2e passed all four approved scenarios (46.5 seconds).
- No permanent tests, library edits, frozen prompt edits, live model calls or renders were performed.
- Limit: browser E2E did not specifically exercise packed-bullet save, accepted proposal normalization, save-time concurrent typing, or a master-revision conflict. These contracts were checked by code inspection and disposable formatter replay only.
