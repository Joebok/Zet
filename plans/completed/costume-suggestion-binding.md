# Reliable costume suggestion binding
Status: complete
Related specification: [ADR 0033](../../Docs/DECISIONS/0033-costume-post-render-adjustments.md)

## Goal and current behavior
Costume suggestions use globally unique copied text. Missing or repeated text aborts
all suggestions; replacement view tags can silently lose their intended effect.
Keep exact source fencing and private-trial/human approval boundaries.

## Impact and constraints
Owners: costume post-render service, shared analysis hooks, mode-scoping helper,
and the existing post-render browser controller's source-location label.
Add section-qualified line IDs to new findings; retain existing saved findings.
No dependencies, permanent tests, live inference, production data edits or deployment.
Documentation owners: Local Characters, Data Model, Testing and new ADR 0035
(a follow-up to ADR 0033). Architecture/invariant boundaries and implementation
ownership remain unchanged; no code-map entry point moved.

## Luna sized work packets
### WP1 — Source addressing and prose ownership
- Files: costume_mode_conditioning_service.py, local_costume_post_render_service.py.
- Dependencies: none.
- Work: enumerate eligible lines with section/position/hash IDs; bind exact lines,
  preserve spatial annotations, and let Zet generate scopes.
- Acceptance: duplicate text is independently addressable; stale IDs, structural
  edits and tag-only edits fail specifically; unaffected scopes remain intact.
- Validation: disposable Python checks with prepared source/answers.
- Status: complete.

### WP2 — Bounded repair and asymmetry
- Files: local_post_render_prompt_service.py, local_costume_post_render_service.py.
- Dependencies: WP1.
- Work: one repair request for invalid findings, retaining valid suggestions;
  specific diagnostics; explicit asymmetric visibility guidance.
- Acceptance: repair never loops, valid findings survive failed repair, all-invalid
  output explains why; existing Character.md behavior and late-result fences remain.
- Validation: prepared-response disposable service checks.
- Status: complete.

### WP3 — Regression validation and knowledge
- Files: affected component/data/testing docs, ADR 0035, source-location label in
  local_character_prompt_improvement.js, this plan.
- Dependencies: WP1/WP2.
- Acceptance: approved E2E scenarios and diff review pass; limitations recorded.
- Validation: npm.cmd run test:e2e; git diff --check.
- Status: complete.

## Progress and decisions
- Scene identity/anchor sections are not eligible body sections in the existing
  source gate. Catalog addressing does not expand edit authority to them.
- Disposable conditioning exposed missing anatomical-side text in a proposed
  replacement. Reuse the existing view conditioner before accepting a suggestion
  so this compiler error enters bounded repair instead of failing at trial time.
- Preserve valid findings across failed repairs; show unresolved diagnostics in
  the existing summary. Check cancellation/round fencing before repair dispatch.
- Show source section/line in review so repeated prose remains distinguishable.
- New finding fields are additive; legacy accepted findings need no migration.

## Final results
- Approved `npm.cmd run test:e2e`: four passed (41.9s).
- Disposable binding/repair checks passed, including all 24 scope cells, stale
  addresses, protected content, asymmetry, partial repair failure and cancellation.
- Adapted existing disposable lifecycle checks passed two rounds, fixed seeds,
  retries, explicit diff approval, costume-only save and replay.
- Isolated Chromium passed source labels, scope controls and existing responsive
  review/trial/checklist/mode/staging behavior without page errors.
- Changed Python AST, JavaScript syntax and `git diff --check` passed.
- No permanent tests/dependencies, live inference, production-library writes or
  deployment. Live model quality remains unverified.
