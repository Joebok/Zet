# Assembly front selection and proportionality ranking
Status: complete
Related specification: Joe's request in this chat.

## Goal and desired behavior
Run FRONT first, require an available selected FRONT image, then run all remaining
requested Assembly views together. Luna uses FRONT only for ranking, prioritizing
head-to-body proportions and identity. Generation retains exactly matching body/head
inputs. No prompt review, predecessor render recipes, or publication dependency is added.

## Current behavior and impact
`local_character_progression_service` opens all Assembly views together;
`local_character_asset_pipeline_service._rank` optionally attaches selected FRONT.
The shared workflow owns rerun targets; the browser labels the action Run all views.
Specs retain version 1 and existing progression stage fields; old batches must respect
the new selection gate without deleting images or choices.
Documentation owners: LOCAL_CHARACTERS, PROMPTS, CODE_MAP, DATA_MODEL and Testing. Render and
publication anchors remain distinct from this ranking prerequisite; preserve locked
bytes, universe isolation, ordered render inputs and evaluation ownership.

## Work packets
### WP1 — Front-first scheduling
- Dependencies: none.
- Files: `local_character_progression_service.py`, `local_image_workflow_service.py`,
  `local_character_asset_pipeline_service.py`, `local_asset_pipeline.js`.
- Work: split FRONT and remaining dispatch; gate direct/slot/legacy execution;
  restart whole batches at FRONT; update action labels and guidance.
- Acceptance: no remaining render is submitted before a valid selected FRONT;
  remaining views queue together after selection. Matching body/head renders unchanged.
- Validation: disposable isolated runner/slot checks and JS syntax.
- Status: complete.

### WP2 — Mandatory proportionality comparison
- Dependencies: WP1.
- Files: progression and Assembly services, `local_image_ranking_service.py`.
- Work: require FRONT for non-front rankings, emphasize proportion matches, retain
  comparison provenance and supersede advice when FRONT changes without clearing choices.
- Acceptance: captured Luna requests map FRONT only to ranking attachments; late
  rankings from an earlier selection cannot commit. Single-survivor shortcut remains.
- Validation: disposable captured ranking/fencing checks, no live inference.
- Status: complete.

### WP3 — Verification and knowledge
- Dependencies: WP1–WP2.
- Files: affected Docs listed above and this plan.
- Work: update current contracts; run S2, syntax and diff checks; archive completed plan.
- Acceptance: approved front Assembly-to-Dressing scenario passes; behavior gaps
  covered by disposable checks. No new permanent tests/dependencies or live calls.
- Validation: `npm.cmd run test:e2e -- --grep character-to-costume`, `git diff --check`.
- Status: complete.

## Progress, risks and results
WP1/WP2 are implemented. FRONT is ranking-only: `use_front_anchor` remains false
for Assembly, preserving two-image generation and body/head-only publication lineage.
S2 passed (13.7s). Disposable runner checks passed FRONT-only dispatch, selection
waits, all seven remaining views with two-image inputs, invalid FRONT rejection,
rank attachment numbering, proportion guidance, retained downstream selections,
stale advice, late-result fencing, legacy recovery and whole-batch restart.
Chromium passed mounted dashboard Run front/disabled Run remaining/selected FRONT/
seven-view dispatch, including polling and no page errors. Selection was made through
the existing API during this disposable browser check. Two disposable assertions
were corrected: attachment numbering must account for shared-reference deduplication,
and a superseded evaluation must be replaced before a new ranking can start.

## Final results
All four approved fast E2E scenarios passed (40.2s) with verified Python 3.14.6.
Changed Python AST and JavaScript syntax checks passed; final diff review and
`git diff --check` passed. Updated affected LOCAL_CHARACTERS, PROMPTS, CODE_MAP,
DATA_MODEL and Testing documentation. No schema change or new dependency was needed.
The isolated checks establish dispatch/reference/ranking ownership behavior; no live
AI calls or production library writes occurred, and artistic ranking quality remains
unverified. No permanent tests were added. No implementation blockers remain.
