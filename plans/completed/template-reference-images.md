# Template reference images and Tsaeytte ear guidance
Status: complete
Related specification: Joe's approved implementation plan, 2026-10-19.

## Goal and current behavior
Allow authored template images in supported pipelines while retaining required source slots,
universe isolation, ordered citations/frozen bytes, and backend limits. Head quarter prompts
already contain an anchor plus ear image; the shared Qwen Body/Head adapter rejects their
count and binds only one. Body compilation rejects all template images and its slot path
does not retain compiler-added references. No API/schema/dependency change is needed.

## Impact and constraints
Owners: shared Qwen workflow registry; Body compiler/service and render slots; supplemental
reference callers; external Tsaeytte Character.md; existing batch template revision service.
Knowledge owners: Docs/COMPONENTS/PROMPTS.md, LOCAL_CHARACTERS.md, CODE_MAP.md and
the reference-order contract in Docs/INVARIANTS.md. Architecture/data ownership remains
unchanged. Retired workflows stay retired. No live models, renders or release modifications.
Existing asks remain frozen. Joe will recompile/rerun FRONT; clear its current selection.

## Luna-sized implementation packets
### WP1 — Qwen bindings
- Dependencies: none. Files: zet/services/comfyui_workflow_registry.py.
- Bind all valid ordered references (0–10); remove workflow count assumptions.
- Acceptance: zero/one/two inputs, invalid paths and >10 inputs checked offline.
- Validation: disposable Python graph assertions. Status: complete.
### WP2 — Compilation and freezing
- Dependencies: WP1. Files: Scripts/Run_Body_Reference_Jobs.py, local Body service,
  render_slot_service.py and affected supplemental-resolution callers.
- Validate prerequisite roles separately; append view-filtered universe-owned template
  references; retain complete bindings for fresh/cached prompts and new frozen asks.
- Acceptance: required sources still fail when missing; citations and bytes retain order.
- Validation: disposable compiler/slot checks across four active character pipelines.
- Status: complete.
### WP3 — Character template
- Dependencies: none. File: H:/Zet/Zet_Library_v5/Moonsea/Characters/Tsaeytte/Adult/Character.md.
- Keep eight ear bindings; scope anatomy, hair occlusion, natural skin/neck/shoulders and
  transparent background; exclude reference mannequin/background/pedestal traits.
- Acceptance: eight views compile with matching ears, with and without identity sources.
- Validation: disposable all-view compilation. Status: complete.
### WP4 — Existing batch
- Dependencies: WP3 and preview validation. Batch: 20261019_123256_715316.
- Use existing manual-child review/accept/activate services; change only Character.md.
- Clear FRONT selection/anchor using selection service. Do not queue renders.
- Acceptance: active updated snapshot, no front selection, no new render jobs.
- Validation: API state and compiled previews. Status: complete.
### WP5 — Verification and knowledge
- Dependencies: WP1–WP4. Update affected component/code-map documentation.
- Run npm.cmd run test:e2e and git diff --check; inspect code and external source diffs.
- Record results/limits here and move to plans/completed when complete.
- Status: complete.

## Validation and progress
- `npm.cmd run test:e2e`: all four approved scenarios passed in 42.9 seconds.
- `python3 -B test-results/template-reference-images/validate.py`: passed offline
  Qwen 0/1/2/10-image graph bindings and cache counts, missing/invalid/over-limit
  references, eight Head views with/without identity sources, all four character
  compilers, frozen citation/manifest order, required-source rejection, fresh/cached
  Body slots and initial Body packaging/retry (mock transport). Private catalog and
  image copies were used; no real render/model submissions.
- Changed Python syntax and `git diff --check`: passed. Final code/document and
  external Character.md diffs reviewed. No permanent tests or dependencies added.
- Existing batch manual review/accept/activate succeeded through the running API.
  READY revision `a28fb23590df47c993b2330ec1eb6c61` is active with eight validated
  previews. FRONT selection/anchor cleared through the selection service. Candidate
  image paths and ask IDs remained unchanged; no renders were queued.
- Docs/COMPONENTS/PROMPTS.md owns the clarified supplement contract;
  LOCAL_CHARACTERS.md and CODE_MAP.md link operational/implementation ownership.
  No storage/schema or architecture boundary changed; no new ADR was necessary.

## Final results and limits
The shared Body/Head graph binds every template image. Body accepts supplemental
images and retains compiler order through initial/cached/fresh frozen asks; Assembly
resolution now honors the supplied universe (Head/Dressing already did). The other
supported compilers retain required slots; Narrative already supports ordered images
within the backend limit. Retired paths and offline archives were not modified.

Tsaeytte's master and accepted batch sources retain all eight ear references with
anatomy-only scope, natural hair occlusion, living skin, natural neck/shoulders and
transparent framing. Joe will recompile/rerun FRONT and select a new anchor.

The running release was not modified. Normal release delivery is still required
before rerunning against localhost. Rendered ear fidelity, neck shape and actual
transparency remain unverified until Joe's live rerender. All implementation packets
are complete; no release or live-render action was part of this plan.
