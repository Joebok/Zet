# Simplify Character Assembly
Status: complete

## Goal and constraints
Assembly uses only matching body/head images and a minimal natural-join prompt. Governing-template improvement is removed only for Assembly. Luna receives selected FRONT separately for non-front ranking. Preserve existing edits, selections, publications, historical jobs and frozen Retry inputs. No new dependencies, maintained scenarios or live inference.

## Verified ownership and impact
Compiler/task template own prompt contracts; Assembly adapter and render slots own render preparation; shared progression/workflow and browser controls own review gates; shared ranking owns attachment numbering. Affected knowledge: local characters, prompts, data model, code map and testing. Current worktree contains unrelated in-progress edits; preserve them.

## Implementation packets
- WP1: compiler and character_assembly_v2 template; simple two-source natural join. Depends: none. Check: eight-view disposable compile/manifests. Status: complete.
- WP2: Assembly adapter, view references, slots and preview; two-image contract version forces fresh compilation, staging shares preparation. Depends: WP1. Check: legacy recipes/manifests and ordered inputs. Status: complete.
- WP3: progression/workflow, template service boundary and dashboard; no Assembly review gate/reference choices, retain Continue stages. Depends: WP2. Check: disposable API/browser and repair existing S2 helper. Status: complete.
- WP4: Assembly/shared ranking; ranking-only selected FRONT, explicit proportion/identity guidance and provenance. Depends: WP2. Check: disposable multi-candidate request mapping. Status: complete.
- WP5: affected documentation, focused S2 and full approved fast suite, git diff --check and diff review. Depends: WP1-WP4. Status: complete.

## Validation and progress
Commands planned: npm.cmd run test:e2e -- --grep character-to-costume; npm.cmd run test:e2e; git diff --check. Disposable checks use isolated test storage and prepared responses. Single-survivor shortcut stays deterministic. Live artistic quality is unverified.

## Progress and decisions
WP1-WP4 implemented and disposable service/browser checks passed. Additional source-tag stripping was necessary: leaving tags after omitting supplemental images would cause unresolved image citations. Assembly version upgrade also clears the obsolete active-revision stamp so subsequent manual prompt edits survive Generate. Existing accepted revision records and submitted/Retry inputs are retained. A disposable Body progression assertion was corrected to verify its actual existing review panel rather than assume enrollment; no unrelated Body behavior changed.

## Observed validation
Focused S2 passed (11.6s); full S1-S4 passed (37.8s). Eight-view, legacy-preparation, stage, staging, publication, supplemental-tag, ranking/provenance and Chromium checks passed. Final S1-S4 rerun after compiler/error-message adjustments passed (38.2s), including S2 (6.5s). Python AST, changed JavaScript syntax and git diff --check passed. Final diff reviewed; pre-existing changes retained. One rerun was initially blocked by the disposable fixture holding port 8765; the owned fixture was stopped and the rerun passed. No live quality evaluation was requested.


## Final results
All five packets are complete. Updated the Assembly compiler/task template, source/slot preparation and preview, progression/workflow/template action boundaries, Luna attachment mapping/provenance, dashboard controls, existing S2 helper, and affected documentation. No dependencies or maintained scenarios were added. No production data, published images, or external services were changed. Live artistic quality remains unverified; no blocker remains for the requested local implementation.
