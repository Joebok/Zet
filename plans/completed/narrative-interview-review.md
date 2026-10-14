# Narrative interview, prompt clarity and image freshness
Status: complete
Related specification: Joe's approved plan in this chat (2026-10-13).

## Goal and desired behavior
Interview results propose whole-field replacements rather than editing inputs immediately.
The review compares Old/New, defaults ordinary rows to Accept and visual rows to Override,
supports explicit row choices and untouched-row bulk choices, and commits only on Apply.
Shared visual writes clear the current target override. Conflicts/questions accompany proposals.
Field guidance separates shared appearance from moment-specific pose and relationships.
Local overrides get Save inputs and collapsed active-field indicators. Prompt writing preserves
equipment exclusions and relative heights; image tags bind first mentions only. Image tiles and
reviews subtly indicate prompt text differences, including unsaved edits.

## Current behavior and impact
Narrative prompt service supplies four-field interview drafts, generation applies them automatically,
scene service owns shared elements/context and target overrides, router delegates HTTP actions,
and narrative.js renders mounted editor/tiles/reviews. Candidates already store render prompts.
S1/S3 cover authoring and prepared narrative lifecycle; no live wording/quality guarantees.
Affected knowledge: Narrative, Prompts, Data Model, Code Map, Testing; add a review-first ADR.

## Constraints
One agent; no dependencies or permanent scenarios. Preserve working Group Photo data.
Use disposable copies/prepared responses. Preserve frozen references, attempt fencing and
assembly/backdrop rules. No extra confirmation/history/concurrency gates. Atomic writes protect
individual files; validate all choices before the existing lock-protected multi-record apply.

## Work packets
- WP1: narrative_prompt_service.py proposal schema/context/guidance; no dependencies;
  acceptance: permitted fields, conflicts/questions, no reference edits; disposable schema checks.
- WP2: narrative_generation_service.py pending reviews and old-reply normalization; WP1;
  acceptance: no authored changes on completion, reload persistence; prepared-response checks.
- WP3: narrative_scene_service.py and narrative_router.py apply endpoint; WP2;
  acceptance: selected field patches, Shared clears override, validation/idempotency; disposable checks.
- WP4: narrative.js/html/css comparison panel; WP2-WP3;
  acceptance: defaults, explicit-vs-bulk selection, close/reopen/polling, Apply; disposable browser checks.
- WP5: presentation guidance, effective context, override save/summary; WP1/WP4;
  acceptance: guidance and save/reload/clear indicators; disposable browser checks.
- WP6: narrative_prompt_service.py first-mention tags and concise complete writing; WP1;
  acceptance: preserve supplied exclusions/height strength and reference order; disposable text checks.
- WP7: narrative.js/css subtle Different prompt badges; independent;
  acceptance: edits/revert/replacement/reload/review/unknown/local-source behavior; disposable checks.
- WP8: repair existing S3 review/apply flow, run npm.cmd run test:e2e with verified Python 3,
  git diff --check and final diff review; update knowledge/ADR; all previous packets.

## Progress and validation
- Planning inspection complete; clean working tree at implementation start.
- Python 3 verified: python3 resolves Python 3.14.6.
- WP1-WP3 implemented: field contracts/validated proposals, pending reviews, lock-protected
  apply endpoint and Shared override clearing. Legacy replies normalize to proposals.
- WP4-WP7 implemented: comparison dialog, row/bulk selection, field help, effective context,
  collapsed override summary/save, first-mention bindings and live prompt comparison badges.
- WP8 complete: S3 repaired to review/Apply before synthesis; all three approved E2E scenarios pass.
- Shared field contracts live in narrative_interview_service.py to avoid duplicated authority
  lists between request generation, result validation and application. This adds one focused
  service module; no new app initialization, global schema migration or dependencies.
- Exact replay must preserve its original response schema as well as request wording; this
  compatibility constraint was discovered in final review and verified with a disposable old-job replay.
- Input-only labels distinguish title/canvas and participant reference metadata from fields
  the interview can propose changing. Synthesis explicitly uses effective context and authored
  equipment omissions instead of superseded shared values or reference gear.
- No live model/render jobs authorized or run.

## Final results
- WP1-WP8 complete. Services own field contracts, pending review validation/application and
  first-mention bindings; the mounted editor owns comparison choices, help/override controls
  and live prompt-text indicators. Incoming legacy replies remain compatible.
- Updated Narrative, Prompts, Data Model, Code Map, Testing and ADR 0009.
- Final `npm.cmd run test:e2e`: 3 passed in 27.7 seconds (Python 3.14.6). Earlier baseline runs
  also passed; maintained scenario count remains three, with S3 repaired for explicit Apply.
- `python3 -B test-results/narrative-review-checks.py`: passed using a disposable Group Photo
  JSON copy; checks include validation, fencing, normalization, exact replay schema, accepted/
  rejected destinations, Shared override clearing, repeated application, request context and
  prepared prose/reference bindings. Source record SHA-256 hashes were unchanged.
- `node test-results/narrative-review-browser.mjs`: passed against the isolated fast fixture,
  including row/bulk choices, pending reload/polling/close, application, override save/clear,
  and indicator updates on edits/revert/reload/synthesis/open review/unknown/crop/reuse/line endings.
  No page errors. The disposable harness's textarea check was corrected to assert value, not textContent.
- Desktop/narrow screenshots inspected. Initial visual inspection caught inherited pale text
  in Old/New code blocks; explicit foreground color fixed it. Disposable contrast/viewport
  checks passed after correcting the probe to measure contrast rather than hardcode a color.
- `node --check zet/web/static/narrative.js`, Python AST syntax checks, `git diff --check`
  and final diff review passed. Disposable scripts/screenshots stay ignored under test-results.
- No production data edits, live model/render calls, dependencies, permanent scenarios,
  deployment or additional confirmation gates. Live LLM/render fidelity remains unverified.
