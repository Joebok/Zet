# Head view-specific ear references
Status: complete (local implementation and library correction; runtime deployment excluded)

## Goal and verified behavior
Tsaeytte Adult's eight LIB:REF tags are valid, but HEAD_DESCRIPTION_FACTS is omitted
from source-backed local Head prompts. The referenced batch has an accepted source
overlay predating the master edit. Head rendering and supplemental slots also discard
compiler-added references. Preserve frozen asks and all prior source versions.

## Impact and constraints
Owners: Run_Head_Image_Jobs compiler, LocalHeadImageService, CharacterRenderSlots;
knowledge owner Docs/COMPONENTS/PROMPTS.md. Preserve universe isolation, ordered image
bindings, existing source-backed identity semantics and immutable submitted inputs.
No new dependencies, permanent tests, live AI calls or production deployment.

## Luna sized work packets
### WP1 — Template placement and compiler resource ownership
- Files: live Tsaeytte Adult Character.md; Scripts/Run_Head_Image_Jobs.py.
- Move the eight tagged references into HEAD_DESCRIPTION_VIEW_OVERRIDES; pass the
  explicit job universe to auxiliary resolution.
- Acceptance: each view compiles exactly its matching ear reference and citation.
- Validation: disposable eight-view actual-file compilation, with/without source.
- Status: complete.

### WP2 — Ordered render inputs
- Dependencies: WP1.
- Files: zet/services/local_head_image_service.py, zet/services/render_slot_service.py.
- Freeze returned compiler references on new batch renders and saved dependency
  resources on fresh/cached slot prompts, retaining existing Retry inputs.
- Acceptance: anchor then matching ear image reaches frozen input for both paths.
- Validation: disposable service checks; approved S2 existing E2E regression.
- Status: complete.

### WP3 — Batch source version and documentation
- Dependencies: WP1/WP2.
- Create a manual child of the batch's accepted source version containing only the
  ear reference correction, validate and accept through existing service operations.
- Files: batch template_improvement records; Docs/COMPONENTS/PROMPTS.md; this plan.
- Validation: inspect active source and compiled artifacts; git diff --check.
- Status: complete.

## Validation and results
Existing S2 covers Assembly/Dressing regression, not Head reference tags;
disposable checks cover this task without expanding maintained coverage.

## Progress and discovered dependencies
- Static renderer did not resolve image tags within compiler-composed metadata
  (`LOCAL_VISIBLE_CHARACTER_FACTS`); fixed in Build_Static_Final_Prompt.py.
- Manual template edits rejected new LIB:REF bindings as compiler placeholders.
  LocalTemplateRevisionService now permits valid LIB:REF changes only for explicit
  manual replacements. Model corrections and real compiler tokens remain protected.
- Preserved Joe's concurrent addition of "and visibility when not covered by hair"
  in the master and carried it into a second accepted child; prior versions retained.
- Active accepted revision: 5493a3a29bae438f83832852edd6659e. Refreshed all eight
  current batch prompts from their previously compiled real source bindings. No
  candidate selections, frozen candidate asks or image bytes were changed.
- Dashboard port 8081 is running packaged release c88c828c778ad12c0001aa5781c20e2cb5dee818,
  not this checkout. Local changes require a separately authorized runtime deployment.

## Observed validation
- Verified Python 3.14 runtime.
- Disposable compilation: 16/16 (eight views, text-only and source-backed); each
  selected exactly one matching ear file and produced numbered citations.
- Disposable fresh/cached slot freezing: eight views passed, anchor first when
  present and ear reference afterward. Ordinary batch FRONT/BACK forwarding passed
  with submission intercepted before any queue write or model call.
- Manual-binding/token-protection disposable checks passed.
- Two manual batch revisions reviewed/accepted through the existing service path;
  final eight previews and refreshed actual-file prompts passed reference checks.
- npm.cmd run test:e2e -- --grep 'character-to-costume': 1 passed (17.9 seconds).
- git diff --check passed; reviewed only this task's diff, preserving preexisting
  pilot edits in CODE_MAP, LOCAL_CHARACTERS, Investigate_Head_Views and its plan.
- Initial disposable scripts failed on the worker config guard, metadata citation
  bug, manual binding guard, invalid disposable output placement, missing live
  selections, a concurrent wording change, and a path typo. Corrected checks passed;
  these did not submit any renders. No permanent tests or dependencies were added.

## Final results and limits
Master template and accepted batch version now put the eight references in view
overrides. Local compiler/render fixes preserve citation/input order. Live image
quality and the separately packaged running release remain unverified; deployment
is the remaining operational step before generating new dashboard renders. Retry
continues to use its original frozen inputs.
