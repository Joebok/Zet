# Head-Image rear-view quality pilot
Status: active — 32-image pilot exhausted; rear-quarter recipe rejected in human review.
Related specification: Joe's approved controlled-trial plan in this chat (2026-10-19).

## Goal and constraints
Improve Tsaeytte Adult BACK/rear quarters: correct rotation, convex rear ear surfaces,
and a neck slimmer than selected FRONT F-005, retaining identity and hair.
Maximum 32 live renders, all through existing AI_Proxy services. Human checkpoints
are broad yes/no comparisons. Preserve the source batch, selections, masters,
published assets and frozen retries. No dependencies or maintained tests added.

## Verified current behavior and impact
Head compiler suppresses general facts when preserving a reference, losing the
slim-neck instruction. Batch reference guidance replaces whole-head rotation prose.
BL-006 and BR-006 show internal ear folds; B-004 retains cupped ear surfaces.
F-005 has near-opaque alpha noise, not a usable mask. Existing Narrative cutout
extraction provides the necessary image operation without new dependencies.
Relevant owners: Scripts/Run_Head_Image_Jobs.py, Config/Prompt_View_Text.json,
Config/Prompt_Templates/head_image_v2.md; reference/progression/preview services,
Head ranking and existing local dashboard reference controls.
Documentation owners: Docs/COMPONENTS/PROMPTS.md, LOCAL_CHARACTERS.md, CODE_MAP.md
if significant entry points change; Testing.md owns coverage and live boundaries.
No schema changes before a winning recipe is established. Preserve universe,
ordered bindings, attempt fences, immutable locks and serialization invariants.

## Work packets
### WP1 — Freeze evidence and resumable trial runner
Dependencies: none. Files: Scripts/Investigate_Head_Views.py; private trial directory.
Snapshot selected front/profiles/rear quarters and BACK images, source hashes,
prompts, seeds, settings and source trace. Record normalized neck observations
separately from shoulder flare. Use existing AI_Proxy submission/collection;
persist deterministic request identities before publication and resume without
duplicate renders. Acceptance: replayable manifest and unchanged source hashes.
Validation: offline preparation, manifest checks, disposable prepared responses.
Status: complete. Snapshot and disposable replay checks passed; advisory exposed-skin
width observations recorded separately from anatomical acceptance.

### WP2 — Frozen prompt/reference recipes
Dependencies: WP1. Files: trial runner and batch-local source overlays.
Current versus concise improved wording; camera/rotation first, authored slender
neck retained and slimmer than F-005, convex continuous rear cartilage with
openings/folds on the hidden face-facing surface, natural occlusion. Preserve
universe style; omit task facial/eye filler on rear views. References: current
rear quarter, full F-005, verified featureless F-005 silhouette, none. Silhouette
retains original outline and is explicitly non-authoritative for neck width.
Acceptance: eight BACK recipes and verified input labels/order/bytes.
Validation: compile-only/source trace and inspected silhouette.
Status: complete. Eight recipes compiled, frozen inputs inspected, silhouette
retains ear tips and neck edges (foreground fraction 0.4484).

### WP3 — 16 screening renders
Dependencies: WP2. Four references x two prompts x two matched seeds. Freeze all
effective render settings; no-reference text preset is a workflow control.
Agent assesses orientation, ear surfaces, slender neck, hair/identity separately.
Tie-break: most fully usable results, then fewer processing/production changes.
Present recommended comparison: "Is this visibly better overall?"
Acceptance: supported leading recipe or explicit failure; retain all results.
Validation: actual submitted inputs, output files and render ledger.
Status: complete; first human checkpoint returned partial acceptance. All 16 native AI_Proxy requests
completed and collected, with no execution retries. Recommended recipe:
silhouette-revised. Full image matrix and three-panel recommendation inspected.

### WP4 — Up to 16 confirmation/diagnostic renders
Dependencies: promising WP3 result and affirmative first checkpoint. Joe explicitly
approved continuing silhouette confirmation, with lower hair deferred (latest feedback below).
12 renders: winning/current recipes x three rear views x two new matched seeds;
current predecessor differs by view. Updated allocation after human feedback:
four diagnostics compare rounded-nape versus shallow-U lower-bob wording using
the two screening seeds and the unchanged FRONT silhouette; these replace the
ear/neck ablations. Require five of six
usable winning confirmations, at least one each view, better than baseline and
no systematic hair drift. Ask "Are these good enough to use as references?"
Stop on unsuccessful screening/confirmation, without extending the cap.
Validation: visual comparisons and ledger audit. Status: all 12 confirmation
images collected after Joe repaired the proxy. Joe rejected the selected rear
quarters because their ears face the camera. Earlier agent quarter passes are
withdrawn. The five-of-six target and a usable image per view are not met.
Do not include hair-diagnostic wording in the silhouette confirmation prompts.

### WP5 — Integrate demonstrated improvements only
Dependencies: successful WP4 and affirmative second checkpoint.
Change canonical compiler/template owners only for demonstrated prompt fixes.
If predecessor wins retain interfaces; FRONT/none winners extend Head rear-only
recipes/progression/previews/controls; silhouette winner adds focused preparation
and explicit representation with frozen source/version identity. Existing batches
keep saved recipes; retries keep saved bytes. Ranking/observations explicitly
assess rear orientation, ear surfaces and neck proportions and remain advisory.
Update owning docs. Validate disposable isolated preview/render/persistence/retry
checks, approved S2, syntax and git diff --check; review final diff.
Status: not started; full recipe failed confirmation. No production integration
or additional rendering within this exhausted pilot.

## Progress and decisions
- 2026-10-19: implementation authorized, including at most 32 live renders.
- Human reviews must not require detailed feedback; neck should be slimmer than
  F-005. Trial artifacts remain private; no promotion before demonstrated success.
- Trial workspace: test-results/head-reference-quality/20261019-pilot (ignored).
  Script: Scripts/Investigate_Head_Views.py; prepare/submit/collect/sheet commands.
- Disposable prepared-response checks: 16 unique requests, repeated submission and
  collection, unchanged sources and frozen bytes passed with no live calls.
- The inherited ZET_WORKER_MODE=1 marker blocks production config. Only explicitly
  authorized trial commands run with process-local ZET_WORKER_MODE=0; no guard or
  configuration was modified. Offline source preparation does not construct ZetApp.
- Trial collection serializes with dashboard coordinator sweeps. The private owner
  recovers only its exact unsupported-consumer error, then uses shared validated
  collection and receipts; execution is never retried implicitly.
- Approved S2: npm.cmd run test:e2e -- --grep "character-to-costume" passed
  (one scenario, 17.0 seconds total). AST and git diff --check passed.
- Actual 16 published request identities, seeds, model and 1024x1024 dimensions
  inspected. Protected source hashes unchanged. Prepared-response transfer-error
  recovery passed without another execution. Original batch remains untouched.
- Screening: rear-quarter references copied orientation/inner ears. Full FRONT
  corrected orientation but retained cupped ear surfaces. Silhouette removed the
  inner-ear cue; current wording lost hair color, while revised wording restored
  dark hair and produced the strongest two candidates. No-reference controls
  also improved anatomy, but neck/shoulder flare and hairstyle drift remained.
- Recommendation is provisional: ear surfaces and orientation improved in both
  silhouette-revised seeds; neck/identity acceptance and cross-view consistency
  require the approved human checkpoint and confirmation. Not a production win yet.
- First checkpoint presented: "Is this visibly better overall?" No confirmation,
  ablation or integration work may proceed before an affirmative answer.
- Joe's response: "Ears and neck are better, especially in seed 1, but lower part
  of hair is better on existing b-004." This is partial acceptance, not approval
  of the full recipe. Keep the ear/neck directions and silhouette fixed; use four
  diagnostic renders for hair correction instead of ear/neck ablations. The
  original image stays unchanged and is a visual target, not a render input.
  Total cap remains 32 (16 screening + 4 diagnostics + up to 12 confirmation).
- Both rounded-nape and shallow-U directions reached the submitted workflow and
  produced distinct outputs, but neither reliably restored B-004's lower bob.
  The central rise and long side sections remained. Ear/neck gains largely persist.
  All 20 requests completed; 12 renders remain unspent. No defaults were promoted.
- Proposed replacement for the remaining confirmation step: use B-004 as the
  single edit base, preserve its hair, and change only ears and neck. This is a
  different recipe, not successful confirmation of the silhouette workflow.
  Joe's broad yes/no direction was requested before spending the remaining budget.
- Latest direction: "I would like to test the silhouette recipe and if necessary
  we can circle back on the hair." Continue the original silhouette-revised recipe
  (not the diagnostic hair variants) versus current predecessors across BACK and
  both rear quarters, two new matched seeds. This uses all remaining 12 renders.
  Retain the lower-bob mismatch as an explicitly deferred finding, not as solved.
- Confirmation preparation/validation passed: 12 new jobs, correct per-view
  predecessors, two new matched seeds, unchanged winning BACK prompt, all frozen
  prompt/reference hashes and source hashes intact, duplicate preparation refused.
  Exactly 32 logical image slots are reserved; 20 images are complete.
- Backend interruption: the first confirmation baseline failed during submission
  bookkeeping with WinError 5 replacing comfyui_submission.json; saved phase was
  PREPARED and no image was produced. Shared AI_Proxy recovery reserved a fresh
  physical request for that same logical slot. No manual image retries were made.
- AI_Proxy then repeatedly failed to start its managed ComfyUI: Windows access
  violation in torch.cuda.is_available during comfy_kitchen CUDA registration.
  The proxy's /_proxy/status reported backend_runtime.state=failed. nvidia-smi
  succeeded (RTX 5060 Ti / driver 617.42), which does not establish CUDA health.
  No direct ComfyUI invocation, package changes, driver changes or proxy restarts
  were attempted. Confirmation results are unavailable, not failed quality tests.
- Evidence: private confirmation-interruptions.json and managed-comfyui-failure.txt.
  Restore the managed backend through AI_Proxy, then resume the existing manifest's
  collect command. Do not create a new trial or republish the 12 frozen jobs.
  AST and git diff --check passed after the confirmation-runner changes.
- Joe reported the proxy repaired and images finished. Resumed collection of
  existing IDs only; all 32 logical image slots now have validated result images.
  All frozen prompt/result hashes match; protected source hashes are unchanged.
- Confirmation review: silhouette generally improves rear orientation and neck
  width over predecessor baselines, but posterior ear anatomy remains variable.
  BACK seed 93810421 and rear-right seed 93810421 retain cupped/recessed-looking
  ear surfaces. Rear-left seed 93810421 exposes an eye/eyelash edge and has a less
  faithful ear tip. Seed 62419783 provides the strongest candidate in each view.
- Strict provisional usefulness: 3/6; the planned 5/6 target is not met. These
  are agent visual judgments, not anatomical measurements. Exact quarter yaw
  and far-ear occlusion also vary. Lower bob remains deferred at Joe's request.
- Presented confirmation-selected.jpg (best image per view) and requested the
  planned broad yes/no reference review. The full paired matrix is confirmation.jpg.
  Default promotion is not justified by the observed consistency. WP5 remains
  unimplemented; final image acceptance does not by itself prove recipe reliability.
- Final human feedback: "Ears are not good on the 3/4 views, they read as facing
  the wrong way (towards camera) to me." Both selected quarter references are
  rejected. The agent's previous provisional passes were too generous and are
  withdrawn. A single direct BACK remains provisionally promising, not explicitly
  accepted. The silhouette recipe has not solved rear-quarter ear orientation.
  Private manifest records confirmation_accepted=false; findings preserve this
  correction and the earlier assessment history. All 32 images remain retained.

## Final results
32/32 logical image slots collected; the silhouette recipe failed human
confirmation on rear-quarter ear orientation. No source batch, image selection,
published asset or production default changed. Ear/neck improvement in some
images does not establish a usable three-view reference set. Lower hair remains
deferred. The original quality goal is unmet; keep this plan active. A revised
investigation and new render authorization are needed before further trials.
