# Rank against supplied view references
Status: complete
Related issue/specification: user request in this chat

## Goal and current behavior
Body, Head, Assembly and Dressing ranking currently supplies FRONT instead of the
reference used by staged generation. Rank against each candidate's supplied inputs.
Keep existing candidate eligibility, selection, locking and evaluation fencing.

## Impact and constraints
The shared ranking service will own reference/image mapping. The four pipeline
adapters provide legacy fallbacks through existing view-reference recipes. Frozen
render inputs take precedence, including intentionally empty inputs; adopted
refinements retain original reference inputs. Missing recorded images must fail
clearly instead of silently comparing against FRONT. No new dependencies,
maintained tests, live models, production library changes or automatic reranking.
Documentation owners: LOCAL_CHARACTERS, CODE_MAP; no serialization version change.
Existing anchor invalidation and single-candidate shortcuts remain unchanged.

## Luna sized work packets
### WP1 — Shared supplied-reference mapping
- Files: zet/services/local_image_ranking_service.py.
- Dependencies: none.
- Work: resolve captured inputs, deduplicate attachments, label reference roles,
  source views and candidate/image indices; fall back only for historical records.
- Acceptance: no FRONT substitution for captured or explicitly empty inputs.
- Validation: disposable isolated checks of mapping and missing inputs.
- Status: complete.

### WP2 — Pipeline integration
- Files: local_body_reference_service.py, local_head_image_service.py,
  local_character_asset_pipeline_service.py under zet/services.
- Dependencies: WP1.
- Work: use shared mapping and ask Luna to preserve visible identity/design while
  judging the requested target orientation. Retain matching prerequisite inputs.
- Acceptance: profile ranking receives its supplied quarter reference; BACK can
  receive either supplied rear quarter in all four pipelines.
- Validation: disposable prepared ranking payload checks; existing S2 E2E.
- Status: complete.

### WP3 — Documentation and final validation
- Files: Docs/COMPONENTS/LOCAL_CHARACTERS.md, Docs/CODE_MAP.md, this plan.
- Dependencies: WP2.
- Acceptance: document actual behavior and the need to Re-evaluate old rankings.
- Validation: Python AST, git diff --check, final diff review.
- Status: complete.

## Validation and progress
- `python3 -B test-results/check_supplied_ranking.py`: passed shared captured,
  legacy, intentionally empty, adopted-refinement, missing-input and deduplicated
  mappings; 44 prepared pipeline/view payload checks; changed Python AST parsing.
  Covers all 32 pipeline/view combinations, four alternative rear-right BACK
  inputs, and eight legacy selected-view/none recipe checks using real adapters.
  The disposable script is ignored and adds no maintained coverage.
- `npm.cmd run test:e2e -- --grep "character-to-costume"`: S2 passed (17.8s
  including startup; scenario 11.9s). No live models or normal library used.
- `git diff --check`: passed. Final source diff reviewed for scope and attachment
  ordering. Existing eligibility, single-candidate shortcuts, anchor invalidation,
  evaluation ownership and lock/publication behavior remain unchanged.

## Final results
All four pipelines now compare candidates to their supplied reference inputs with
explicit candidate/reference image mappings and cross-view consistency guidance.
LOCAL_CHARACTERS and CODE_MAP document the behavior and verification limits.
Saved rankings require explicit Re-evaluate to use the new prompt. No ADR or data
version change is needed: existing captured input fields remain authoritative.
No live model quality evaluation was performed; no remaining implementation work.
