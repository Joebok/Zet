# Local character template improvement
Status: complete
Related evidence: [Joe's Dressing package](../../Docs-Joe/costume-dressing_290cb394d73845358b94c3cfd23ca39e_prompt_improvement/ChatGPT_Review_Request.md)

## Goal
Improve governing character templates from representative multi-view evidence and operator observations, save reviewable revisions, experiment with individual renders, and explicitly promote chosen source edits. Allow selected images from this batch to condition specified views without an automatic front reference.

## Current behavior
`LocalPromptImprovementService` records per-view observations and exports all candidates/source-map inputs. The export points at a missing compiler guide. `CharacterRenderSlots` already supports independent Generate/Regen with frozen inputs; adapters compile current library sources. References are largely tied to FRONT. `AIWorkflowService` provides resumable structured requests through AI_Proxy.

## Desired behavior
- One representative per included view: explicit choice, selected candidate, otherwise current Luna #1; no arbitrary discarded-image fallback.
- Freeze evidence, observations, complete source versions and compiler/tag guidance for each proposal. Human direction takes precedence; isolated defects and reference-angle conflicts remain distinct from template defects.
- Save immutable, parent-linked revisions and exact source diffs. Compile trial revisions before activation; new single-slot renders use the active revision. Existing asks/locks remain frozen. Promotion is an explicit, source-conflict-checked action with retained originals.
- Per-view reference choices support legacy default, no batch anchor, or a selected image from another view; resolve and freeze it when rendering. Never infer a front image for a rear view in custom mode.

## Impact analysis
Services: prompt improvement, new template revision/source overlay service, compiler readers, render slots, local workflow boundary and resumable AI registry. Presentation: shared local router/dashboard. Data: per-run `template_improvement` revision store and per-view reference recipes; no catalog/schema migration. Documentation owners: LOCAL_CHARACTERS, PROMPTS, DATA_MODEL, INVARIANTS, CODE_MAP and a decision record. Existing S1–S4 are regression checks; new acceptance journeys are disposable and isolated.

## Invariants and constraints
One agent. Preserve unrelated/untracked package. No new dependencies/permanent tests or live Narrative check. AI execution goes through AI_Proxy. Universe containment, immutable published images, queued request inputs and selection ownership remain enforced. Local library template promotion requires an explicit dashboard action; do not promote live sources while developing. New references affect future individual renders, not historical image provenance.

## Implementation steps
### WP1 — Frozen evidence and revision contracts
- Dependencies: none.
- Files/interfaces: `local_template_revision_service.py`, `local_prompt_improvement_service.py`, current compiler guidance.
- Work: bounded representative selection; source allowlist and immutable baselines; proposal schema and targeted instructions; durable revision requests and diff projection.
- Acceptance: saved proposal contains exact image IDs, observations, editable sources and tag contracts; no all-candidate attachment flood.
- Validation: disposable Python fixture with prepared structured answers; inspect supplied package read-only.
- Status: complete.

### WP2 — Trial compilation and promotion
- Dependencies: WP1.
- Files/interfaces: compiler source overlay helper/readers, adapters, `render_slot_service.py`, `ai_workflow_service.py`.
- Work: context-local source overrides, compile all requested views into revision artifacts, activate/revert trial revision, preserve render provenance; explicit optimistic promotion with original source backups.
- Acceptance: revision compiles without changing master sources; new render captures revision identity; failed/stale proposal cannot overwrite masters.
- Validation: isolated real compilers, invalid-tag/source-conflict/replay checks.
- Status: complete.

### WP3 — Same-batch selected-view references
- Dependencies: WP2.
- Files/interfaces: focused reference recipe service, render slot preparation, adapter/compiler reference guidance.
- Work: save default/none/selected-view recipes, resolve current selected image, reject self/missing/rejected references, freeze ordered bytes, label actual reference orientation and purpose.
- Acceptance: front→front-quarter→profile→rear-quarter can be configured manually, rear view can omit batch anchor, in-flight inputs stay unchanged.
- Validation: disposable selection/protection/frozen-input checks across four adapters.
- Status: complete.

### WP4 — Dashboard review and iteration
- Dependencies: WP1–WP3.
- Files/interfaces: local workflow/router, shared dashboard JavaScript/HTML/CSS.
- Work: representative selection, direction/model choice, proposal status/history, old/new diff, trial activation and explicit promotion; per-view reference choice. Reuse individual render actions.
- Acceptance: discoverable end-to-end local workflow, polling/reload preserve unsaved direction and observations; failures visible and retryable.
- Validation: disposable API/browser journey and JavaScript syntax checks.
- Status: complete.

### WP5 — Verification and knowledge
- Dependencies: WP4.
- Files/interfaces: affected documents above and this plan.
- Work: run approved E2E, disposable contract checks and final diff review; document observed limitations and durable choices.
- Acceptance: validation reported accurately; master templates and supplied batch unchanged by development checks.
- Validation: `npm.cmd run test:e2e`, verified Python syntax, `node --check`, `git diff --check`.
- Status: complete.

## Risks and alternatives
Representative-only evidence cannot establish recurrence without observations. Model proposals can overreach: constrain editable sources, preserve tags/placeholders and require real compilation before use. Compiler changes must preserve source provenance. Promotion across several files cannot be a filesystem-wide atomic transaction; retain recoverable before/after records, preflight all conflicts, and make explicit retries safe. Live artistic quality remains an operator experiment and is not established by prepared answers.

## Progress and decisions
- Existing fixed-slot iteration satisfies the request for fewer independent renders; no batch-runner redesign is planned.
- The documented baseline is four scenarios despite older index/plan wording claiming three; Testing.md is authoritative.
- Implemented frozen source versions, parent-linked proposals/manual edits, durable AI_Proxy continuations, successful-compilation activation and explicit journaled master promotion. Project-relative source IDs rebind across releases; universe-relative paths retain existing serialization.
- Compiler validation checks visibility/spatial syntax in all eight orientations and fully compiles evidence views. Views without prerequisite images are not fabricated or silently snapshotted for validation. Existing batch ordering remains; custom reference recipes apply to individual Generate/Regen, while Retry retains frozen inputs.
- Four approved E2E scenarios passed (40.6s). Disposable all-view Dressing checks passed for bounded evidence, source overlays, activate/revert, malformed markers, conflicting masters, replayed promotion and retained originals. Body/Head/Assembly custom-reference/no-reference compilers passed.
- Disposable Chromium journey passed real queue submission/prepared-answer collection, version polling, activation/revert, manual child, reload and 800px overflow checks. Visual inspection found low contrast inherited by comparison panes; scoped surface colors corrected it.
- Authoring manuals lacked the full visibility-group list. Updated character guidance and costume references; local proposal/export compiler guidance derives groups directly from the authoritative parser.
- All development changes to images and masters occurred only in isolated fixtures. No normal-library batch/master, live model, render backend, production deployment or permanent test was changed by validation.
- Read-only inspection of Joe's batch confirmed selected PL-008 takes precedence over Luna-first PL-001. Sampled PL-008 and BR-008 show differing rear hem heights, consistent with the package observations; no live improvement was generated or claimed.
- Final diff review kept custom references opt-in at the individual-slot boundary; ordinary Assembly/Dressing batch runners retain their existing reference behavior. [ADR 0024](../../Docs/DECISIONS/0024-character-template-versions.md) records this scope.

## Validation
- `npm.cmd run test:e2e`: all four approved scenarios passed; final full run 39.1s (earlier run 40.6s).
- `npm.cmd run test:e2e -- --grep character-to-costume`: S2 passed after final slot/ordinary-batch reference separation (11.8s).
- `python3 -u -B test-results/check_template_revisions.py`: isolated prepared-response service journey passed bounded evidence, all-view Dressing compilation, activate/revert/provenance, selected-view chain/no-front rear input, malformed-marker rejection, source conflicts, replayed promotion, child after promotion, explicit/unranked representative policy, source rebinding and Body/Head/Assembly custom/no-reference compilation.
- `node test-results/check_template_revisions_browser.mjs`: isolated Chromium journey passed durable queue submission/prepared-answer collection, eight representative thumbnails, dirty direction/source preservation during polling, activation/revert, manual child, reload and 800px overflow checks. Repeated after final presentation changes; desktop screenshots visually inspected with readable comparison panes. Scripts/artifacts remain ignored disposable checks, not maintained scenarios.
- Python AST validation passed for all 18 changed/new Python files; both modified/new dashboard JavaScript files passed `node --check`; `git diff --check` passed.
- No normal-library writes, live AI/render execution or deployment. Existing fixture response/model warnings did not fail validation.

## Final results
Implemented local multi-view template proposals, immutable parent-linked text versions, compiler-validated trials, manual child versions, explicit conflict-checked master promotion, and selected same-batch reference recipes for individual renders. Reused existing AI_Proxy/continuation, compiler and render-slot infrastructure. Updated affected component/data/invariant/code-map documentation, authoring guidance and ADR 0024. Software acceptance passed in isolated fixtures. Live artistic acceptance and production rollout remain operator actions; no master update to the supplied batch was performed.
