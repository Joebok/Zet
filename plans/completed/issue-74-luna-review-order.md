# Luna ordered local character review
Status: complete
Related issue/specification: [Issue #74](https://github.com/Joebok/Zet/issues/74)

## Goal
Show candidate cards and previous/next review navigation in Luna rank order once a complete ranking exists, while preserving physical slot order when it does not. Preserve the reported Body-Reference review context and physical slot identities/actions.

## Current behavior
`zet/web/static/local_asset_pipeline.js` sorts complete-ranking gallery cards by `luna_ordered_candidate_ids` and leaves incomplete rankings in physical slot order. Its `orderedReviewCandidates()` currently always sorts by view then physical slot, so review navigation can disagree with the gallery.

## Desired behavior
For each view with a complete Luna ranking, ranked image candidates appear first in Luna order, followed by unranked occupied candidates in physical slot order; empty slots remain after candidates. Previous/next review follows that same image order. Incomplete, stale, failed, or absent rankings continue to use physical slot order.

## Impact analysis
Only the local character pipeline browser presentation and its owning component documentation change. No persisted data, API, queue, or ranking contract changes. Existing S2 covers Assembly/Dressing with one candidate and does not cover multi-candidate ordering.

## Invariants and constraints
Ranking is presentation-only. Physical slot labels and action bindings stay attached to each candidate. No maintained tests, dependencies, production data, live models, or rendering are authorized.

## Implementation steps
### WP1 — Align gallery and review ordering
- Dependencies: none.
- Files/interfaces: `zet/web/static/local_asset_pipeline.js`; `Docs/COMPONENTS/LOCAL_CHARACTERS.md`.
- Work: use one display-order rule for ranked gallery candidates and reviewable images; preserve physical slot fallback and stable unranked ordering.
- Acceptance: a completed ranking places Luna rank #1 at the left and next navigation advances to rank #2; incomplete rankings retain physical order and card actions still target their original slots.
- Validation: revision-bound `issue_worker validate`; disposable checks of ranked and fallback ordering; `git diff --check`.
- Status: complete.

## Validation
The first revision-bound helper validation passed all four currently approved fast E2E scenarios and `git diff --check`. `node --check zet/web/static/local_asset_pipeline.js` and an additional `git diff --check` also passed. No new tests were added. The existing scenarios do not directly exercise multi-candidate Luna ordering; the final helper validation is rerun after this plan is archived.

## Risks and alternatives
If ranking is stale or incomplete, preserve the current physical slot order; do not infer rank from slot labels.

## Progress and decisions
- 2026-10-16: Reconciled queue, claimed issue #74, loaded trusted issue context (no comments or screenshots), and verified the existing gallery sort differed from review navigation. Centralized rank/slot ordering for gallery and review candidate sequences; component documentation now records both.

## Final results
Complete-ranking cards and review navigation use the same Luna rank order. Incomplete/stale ranking falls back to physical slot order; physical slot labels and card action bindings remain unchanged. Draft PR #77 is ready for delivery status after final revision-bound validation. No live models, rendering, production libraries, or queue data were used.
