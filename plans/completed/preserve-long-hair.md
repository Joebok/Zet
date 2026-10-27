# Preserve long hair through Head and Assembly
Status: complete
Related specification: Joe's approved full-hair-with-fallback plan, 2026-10-27.

## Goal and current behavior
Head references should show the complete hairstyle where practical. Assembly may
complete missing lower hair to an explicitly authored anatomical landmark.
Youth Tsaeytte's back-left head ends near the shoulders and Assembly reproduces
that endpoint. Legacy Head hard-codes shoulder length, Head-Image Edit preserves
the crop while excluding the torso, and Assembly restricts reconstruction to the
neck join despite authored mid-back hair.

## Impact and constraints
Owners: head/Assembly task templates and compilers, shared compiler style guidance,
render-slot Assembly input version, shared character authoring template/manual,
and Moonsea/Characters/Tsaeytte/Youth/Character.md in the external library.
Prompt/workflow documentation owns the resulting behavior. No new APIs, sections,
dependencies, storage schemas, permanent tests, live renders or batch mutations.
Preserve unrelated working changes, universe isolation, ordered image bindings,
phase/occlusion rules, selections, locks, accepted revisions and frozen Retry inputs.

## Luna-sized work packets
### WP1 — Head framing
- Dependencies: none. Status: complete.
- Files: Config/Prompt_Templates/head_image_v2.md, head_image_edit_v2.md;
  Scripts/Run_Head_Image_Edit_Jobs.py; Scripts/Run_Head_Image_Jobs.py review checklist.
- Remove shoulder-length and fixed-crop restrictions; permit upper-back context,
  retaining usable identity detail. Exceptionally long hair may continue off-frame
  without a false hem. Preserve orientation and phase-change semantics.
- Acceptance/validation: disposable eight-view compiles of both head pipelines,
  including text/source FRONT and source phase-change FRONT.

### WP2 — Bounded Assembly completion
- Dependencies: none. Status: complete.
- Files: Config/Prompt_Templates/character_assembly_v2.md;
  Scripts/Run_Character_Assembly_Jobs.py; zet/services/pipeline_compiler_support.py;
  zet/services/render_slot_service.py.
- Permit lower-hair completion only to an endpoint explicitly authored in Assembly
  requirements; preserve hairstyle identity, body geometry and camera. Update
  review criteria/style guidance and bump ASSEMBLY_INPUT_VERSION.
- Acceptance/validation: disposable long/short-hair compiles, two-input ordering,
  cached-prompt upgrade and unchanged frozen Retry behavior.

### WP3 — Character sources and authoring
- Dependencies: WP1/WP2. Status: complete.
- Files: external Youth Character.md and
  Shared_Library/Characters/_Shared/Character_Template{,_Instructions}.md.
- Align mid-back/below-shoulder-blades landmarks and rear-quarter projection;
  explicitly allow Assembly completion. Explain reusable authoring and framing.
- Acceptance/validation: private master compiles for all three pipelines,
  especially back-left wording/source maps; preserve independent head families.

### WP4 — Validation and handoff
- Dependencies: WP1–WP3. Status: complete.
- Update Docs/COMPONENTS/PROMPTS.md and LOCAL_CHARACTERS.md, add a short ADR for
  the responsibility split, and document existing revision/source snapshot refresh.
- Run isolated disposable checks, npm.cmd run test:e2e, syntax checks and
  git diff --check; inspect final diff. Record evidence and archive this plan.

## Progress and decisions
- Inspected named live batches and frozen prompts read-only during planning.
- Existing accepted source versions override master edits. They must be explicitly
  revised before recompilation; improved selected heads require a new Assembly
  batch to refresh its source snapshots. Existing requests remain immutable.
- Artistic quality needs later human visual review; text checks cannot establish it.

## Final results
Implemented all four packets. Head framing now follows authored hair length with
an off-frame fallback; Assembly allows lower-hair completion only to an explicit
body landmark, retains short-hair/no-endpoint preservation, and refreshes old
prompt caches using input version 2. Updated the separate Youth master hair and
Head-Image Edit sections plus Assembly requirements; preserved independent head
families and existing batch records. Legacy Head review wording was also aligned
with the long-hair framing fallback to avoid a contradictory completeness check.

Validation observed on 2026-10-27:
- `python3 -B test-results/long-hair/check.py`: PASS, 48 generation/analysis compiles
  across three pipelines and eight views, four extra text/source-phase FRONT
  compiles, short/no-endpoint Assembly checks, both style-mode instructions,
  ordered private references, source attribution, v1 cache upgrade, v2 current
  prompt reuse, frozen-candidate Retry preservation, and Python AST checks for
  all five changed Python files. Private copies include eight real ear guides and
  a read-only SQLite catalog backup. Live source batch state/spec/active-revision
  hashes remained unchanged.
- Canonical `TemplateValidationService.analyze` and onboarding/view-control
  validation passed for revised Youth Character.md with no diagnostics.
- `npm.cmd run test:e2e`: all four approved scenarios passed; final run 37.7s
  (earlier run 41.7s). No live inference or new maintained scenario.
- Final `git diff --check` and local/external source diff review passed.

Documentation: updated the owning Prompts and Local Characters documents,
shared authoring template/manual, and ADR 0036. No responsibilities, public API,
storage schema or significant entry point moved, so architecture/data/invariant
and code-map changes were unnecessary. Pre-existing unrelated edits are retained.

The external master is outside Git. Its original bytes, before/after hashes and
reviewed diff are retained under ignored `test-results/long-hair/` alongside
private compiler evidence. The output previews are text/software evidence only.
No selections, accepted batch versions, published images or frozen asks were
rewritten. Existing accepted versions need explicit source revision acceptance;
new Head bytes require a new Assembly batch. Artistic quality and deployment
remain unverified; future back-left renders need human visual acceptance.
