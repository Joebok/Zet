# Assembly instructions and Identity Key modes
Status: complete

## Goal
Add optional general/view assembly authoring for Youth Tsaeytte's long hair and make Identity Keys prefer current Final locks over Draft by source category.

## Luna sized packets
1. Prompt contract: add optional sections, metadata, authoring guidance and assembly placeholders. Check eight-view compilation.
2. Moonsea templates: add blank sections to four templates; author only Youth hair. Check section parsing and emitted views.
3. Identity Key service: resolve category at preview/save, persist source mode, support legacy records. Check isolated mode promotion and missing locks.
4. Dashboard/docs: group source options, color rows, update knowledge; run browser check, approved E2E and diff check.

## Constraints
Keep existing Elder Tsaeytte and Valindia assembly requirements. No live renders or permanent tests. Preserve unrelated user changes.

## Progress
All four packets complete. The two new sections compile for each Youth view and remain empty for the other Moonsea characters. The existing Traveler test template remains valid through `optional_section` metadata.

## Validation
Eight Youth view selections and all four Moonsea character sources parsed. Disposable Identity Key checks passed Draft creation, Final preference on Update, legacy mode loading and missing-lock refusal. Disposable Chromium computed-style check passed both row colors. Python compile checks, JavaScript syntax, JSON parsing, `git diff --check`, and the four approved fast E2E scenarios passed. The first E2E run exposed the optional-section compatibility issue; after correction the full suite passed (4/4, 42.4s). No live image render was run.
