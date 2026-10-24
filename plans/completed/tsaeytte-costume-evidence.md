# Adult Tsaeytte costume-dressing evidence pilot
Status: complete
Related specification: Joe's approved 16-render evidence-gathering plan in the current task.

## Goal
Determine whether compiled prompt wording, predecessor references, or auxiliary design references contribute to profile orientation and rear overskirt failures. Produce labeled evidence and a separate fix plan. Do not change production prompts, batches, selections, or locks.

## Current behavior
The Moonsea Adult Tsaeytte Canonical Adventure Gear runs `ac89a150ae8b4132972a0a9a4b57de42` and `c7ef30d69a6b45c39f365d9bd2d21319` have frozen per-candidate inputs. Current LEFT_PROFILE uses a selected front quarter; BACK_LEFT_3_4 uses LEFT_PROFILE; BACK uses BACK_LEFT_3_4. Each also uses matching Assembly and view-filtered design images. The active `costume_dressing_v2` compiler emits roughly 8.5–10.3k-character prompts. S2 validates front-only workflow behavior, not visual fidelity.

## Constraints
Use private snapshots and AI_Proxy, at most 16 new renders. Freeze the exact source inputs and verify source hashes after work. No permanent test, dependency, production edit, lock, or selection. Preserve unrelated working-tree changes.

## Work packets
### WP1 — Freeze and map
- Dependencies: none.
- Files/interfaces: source batch `spec.json`/`state.json`, frozen candidate inputs; private `test-results/tsaeytte-costume-evidence/` manifest and snapshots.
- Work: capture current and prior run records, selected results, prompts, ordered reference bytes, seeds/settings/revisions and hashes; map predecessor lineage.
- Acceptance: all snapshot checksums verify and source hashes remain unchanged.
- Validation: private manifest checksum audit and read-only source comparison.
- Status: complete. Forty-four original files are hashed and private snapshots verify.

### WP2 — Prompt and image audit
- Dependencies: WP1.
- Files/interfaces: frozen prompts/source maps, accepted revision, matching Assembly/predecessor/design references; private audit report.
- Work: attribute duplicated/conflicting instructions to sources; inspect input-to-output defect onset and right-side saved examples.
- Acceptance: per-view prompt/reference table and observed defect ledger, separating observations from hypotheses.
- Validation: inspect saved source maps, reference manifests and labeled contact sheets.
- Status: complete for saved-run evidence; `evidence.md`, `offline-audit.json`, and the labeled sheet record observations and hypotheses.

### WP3 — Controlled pilot
- Dependencies: WP1–WP2.
- Files/interfaces: private resumable trial script/manifest; existing AI_Proxy render submission/collection and local character preset.
- Work: per view LEFT_PROFILE, BACK_LEFT_3_4 and BACK, reuse saved baseline and render predecessor-omitted, concise/all-reference, concise/predecessor-omitted, and Assembly-only variants. Reserve four renders for matched second-seed baseline/challenger pairs on rear quarter and BACK.
- Acceptance: no more than 16 labeled outputs; exact source/provenance and render setting hashes; source batch unchanged.
- Validation: inspect frozen requests and collected images; count jobs and verify hashes.
- Status: complete. Twelve screening asks produced nine images and three provider-side permission failures; serialized exact-input retries produced the three missing images. Four paired second-seed confirmations completed. Exactly 16 new images were collected; 19 asks include the three image-free provider failures. The current Codex process is `ZET_WORKER_MODE=1`; the private harness preserved its production-config guard.

### WP4 — Evaluate and hand off
- Dependencies: WP3.
- Files/interfaces: private AI evaluation records, labeled sheets, evidence report and separate fix plan.
- Work: structured image-visible scoring, a six-image pass/fail shortlist for Joe with optional failure reasons, confidence-rated causal findings and next fix plan.
- Acceptance: no blind evaluation or unqualified causal claim; remaining uncertainty is explicit.
- Validation: review score records against images, report and final diff.
- Status: complete. All 16 new images and three saved baselines have labeled sheets and structured nonblind AI_Proxy evaluations. One AI continuity score disagrees with a visible rear gap and is marked in the evidence. Joe's six pass/fail judgments are recorded; the separate decision-ready fix plan is in `plans/active/tsaeytte-costume-fix.md`.

## Progress and decisions
2026-10-23: plan created after source/code inspection. Existing unrelated edits in `zet/web/static/local_character_prompt_improvement.js` and `zet/web/templates/local_character_prompt_improvement.html` are preserved.

2026-10-23: WP1/WP2 completed read-only against source batches. The current run's Assembly input keeps requested orientation while the dressed profile/rear-quarter results drift; saved BACK remains square but has a short hem. Prompt source maps show the computed `BODY_HEAD_ALIGNMENT_LOCK` is not emitted by the active dressing template. These are leads, not causal conclusions. Python syntax, private checksum/citation verification, and `git diff --check` passed. Live submission was not attempted after the issue-worker guard was observed. The source plan stays active.

2026-10-23: Joe ran `run-screen` outside issue-worker mode. The first attempt stopped before queue submission because the private harness called `.parent` on a string. The call was corrected to use a `Path`, the one `SUBMITTING` marker was reset after no trial ask was found, and the retry queued all 12 screening jobs. No source-batch files were modified. Collection and AI evaluation are pending.

2026-10-23: The collector initially timed out on Zet's shared recovery lock; it now retries that lock and has a collection-only mode. Nine images collected and structured nonblind Luna evaluations completed. Three requests failed before image creation with AI_Proxy's `unsettled_comfyui.json` Windows access-denied error. Three replacement asks were prepared serially with exact matching seed, prompt hash and references. The render cap remains 16 completed images with an attempt ceiling of 19; no failed ask is silently resubmitted.

2026-10-23: All three serialized retries completed, yielding twelve screening images and fifteen AI evaluations including the three saved baselines. The screened BACK_LEFT_3_4 results without Image 2 expose less face but repeatedly split the rear overskirt; all rear and BACK results retain a short hem. No screened BACK challenger improves on the saved baseline overall. The second-seed confirmation uses the no-predecessor contrast for both rear views because it isolates the reference effect; it is a diagnostic challenger, not a proposed production winner. Four jobs are prepared with paired seeds and verified frozen inputs. Submission is pending from a normal local process.

2026-10-23: Joe ran the four confirmation jobs serially. All completed, bringing the pilot to exactly 16 new images. The second seed repeats the BACK_LEFT_3_4 face-versus-continuity tradeoff and the BACK rear split when Image 2 is removed; no rear hem reaches the target. The AI evaluator called one visible BACK_LEFT_3_4 gap a seam, so visual evidence overrides that individual score. `joe-review.jpg` presents only baseline and no-predecessor results for Joe's six pass/fail judgments.

2026-10-23: Joe reviewed all six images: saved LEFT_PROFILE passes and its no-predecessor result fails; both BACK_LEFT_3_4 images fail; both BACK images fail. He noted worse hair and earrings in the paired BACK full-reference baseline and described its short skirt as close to target. The fix plan preserves LEFT_PROFILE, prioritizes a small BACK hem edit and a garment-only design-reference test for rear-quarter orientation/continuity, and treats the unused alignment lock and rotation mode as controlled alternatives. No production prompt, reference, source batch, selection or lock was changed.

## Final results
- Evidence: private `test-results/tsaeytte-costume-evidence/evidence.md`, `screening.jpg`, `confirmation.jpg`, `joe-review.jpg`, frozen snapshots, request manifests, and 19 nonblind evaluations (three saved baselines plus 16 new images).
- Controlled finding: the full-body predecessor supplies useful costume/continuity information but can pull BACK_LEFT_3_4 toward a side face. Removing it wholesale breaks rear continuity and does not fix length. The short prompt did not improve the overall result. The cause of the hem height remains unisolated.
- Validation: `python3 -B test-results/tsaeytte-costume-evidence/pilot.py verify` passed (44 protected sources, 19 asks, 16 completed images); `git diff --check` passed. Private scripts ran through all phases. Three initial asks failed inside AI_Proxy before image creation; exact-input retries completed. One AI evaluator continuity judgment was contradicted by visible image evidence and is called out in the report.
- The investigation work is complete; production repair remains proposed in `plans/active/tsaeytte-costume-fix.md`.
