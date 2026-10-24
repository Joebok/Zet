# Adult Tsaeytte Canonical Adventure Gear view repair
Status: proposed; no production fix authorized or applied
Related evidence: `test-results/tsaeytte-costume-evidence/evidence.md` and the completed investigation plan.

## Goal
Preserve the accepted LEFT_PROFILE and good front views; determine whether RIGHT_PROFILE needs correction; produce back-dominant rear three-quarter views and a continuous rear overskirt whose center hem reaches the intended near-ankle point. Preserve Tsaeytte's identity, blouse and jewelry design. Use controlled images to choose changes before editing the production prompt/compiler or reference binding.

## Evidence that sets the order
- Across two paired seeds, removing the full dressed predecessor reduces BACK_LEFT_3_4 face exposure. It also introduces a visible rear skirt opening, and at the second seed weakens the off-shoulder blouse. BACK orientation is already square; deleting its predecessor splits the rear skirt at both seeds. Do not remove Image 2 wholesale.
- All screened prompt/reference combinations and both second-seed pairs keep the rear hem too high. A short operation-first prompt alone does not solve it; no-reference prompts do not solve it. The specific cause of the hem remains unisolated.
- The compiler calculates `BODY_HEAD_ALIGNMENT_LOCK` in `scripts/Run_Costume_Dressing_Jobs.py`, but `Config/Prompt_Templates/costume_dressing_v2.md` does not emit it. Its effect is unknown.
- The authored length uses anatomical “just above ankles” while tall boots hide that landmark. The accepted visual check should name a visible boot/hem relationship before a prompt change is promoted.
- Joe's labeled review accepts the saved LEFT_PROFILE and rejects its no-Image-2 alternative. Both BACK_LEFT_3_4 images and both BACK images fail. He finds the paired full-reference BACK skirt close in length but still too short, and its hair and earrings less satisfactory. The hair/jewelry issue should be checked separately from the skirt geometry.

## Luna sized work packets

### WP1 — Establish a visible pass target and frozen controls
- Dependencies: Joe's six pass/fail judgments on `joe-review.jpg` (recorded in the evidence packet).
- Files/interfaces: private evidence folder and Canonical Adventure Gear specification; no source batch edits.
- Work: retain Joe's judgments and specify the remaining small BACK hem extension in relation to the boot cuff and lower boot shaft. Keep the same Assembly images, saved prompt, preset, reference order, and two known seeds as controls. Record separate pass criteria for camera angle, face visibility, continuous rear fabric, hem, hair, earrings, and other design. Inspect the saved RIGHT_PROFILE with Joe before changing both profile views.
- Acceptance: a reviewer can judge each property without relying on hidden ankle anatomy; the prior saved images remain labeled as controls.
- Validation: private manifest hash check and labeled side-by-side inspection.

### WP2 — Test an isolated BACK hem edit
- Dependencies: WP1.
- Files/interfaces: private AI_Proxy edit asks using the saved BACK result as Image 1; private prompts and results only.
- Work: use a short operation-first *edit* instruction to lengthen only the continuous rear overskirt to the visible target, leaving camera, body, hair, bodice, belt, jewelry, embroidery, leggings and boots fixed. Compare the saved result with two edit seeds. Keep the predecessor out of this edit because the dressed base itself supplies the garment design. Include a failure check for center-back splitting and restyled blouse/jewelry. If the hem edit passes, test a separate small correction for BACK hair and earrings against the Assembly identity; do not mix those edits into the hem experiment.
- Acceptance: both edited outputs meet the hem and continuity target without changing orientation or identity. If only one succeeds, run the smallest additional paired seed before proposing a repair stage. If neither succeeds, test a corrected rear-silhouette garment reference next; do not alter the compiler on this evidence.
- Validation: AI_Proxy labeled rubric plus Joe's pass/fail on the leading result; frozen input/output hashes.

### WP3 — Separate pose influence from garment information
- Dependencies: WP1; can run independently of WP2.
- Files/interfaces: private AI_Proxy asks; possible later ownership in `zet/services/local_view_reference_service.py` or `scripts/Run_Costume_Dressing_Jobs.py` only if the test wins.
- Work: for BACK_LEFT_3_4, replace only Image 2 with a garment-only crop of the same selected LEFT_PROFILE source, excluding head, face, limbs and full-body framing while retaining blouse/belt/overskirt design. Use the unchanged compiled prompt and two matched seeds. Compare against the full Image 2 and the no-Image-2 results already frozen. A successful crop must reduce face exposure *and* retain the continuous rear fabric and canonical bodice. Preserve the accepted LEFT_PROFILE rather than changing its reference binding.
- Acceptance: the garment-only reference meets all three properties at both seeds. If it fixes angle but still splits or shortens the skirt, develop a correct-length rear garment silhouette reference and test it separately; do not promote the crop. If neither works, assess the existing costume rotation mode with matched Assembly/design inputs before changing normal reference binding.
- Validation: same-seed labeled comparisons, exact reference hashes, right-side corroboration after a left-side winner.

### WP4 — Test the compiler's missing alignment lock
- Dependencies: WP1; keep separate from WP3 so the changed factor is clear.
- Files/interfaces: private compiled prompt copies; eventual `Config/Prompt_Templates/costume_dressing_v2.md` if supported.
- Work: insert only the already computed `BODY_HEAD_ALIGNMENT_LOCK` text into frozen BACK_LEFT_3_4 prompts, plus RIGHT_PROFILE only if its direct review shows a problem. Compare with unchanged prompts at two matched seeds and identical ordered references. Check that the result keeps the whole body aligned, not merely a more hidden face.
- Acceptance: rear-quarter and, if needed, right-profile angle improve without continuity, hem, design or identity regression in repeated comparisons; the accepted LEFT_PROFILE stays stable. Otherwise leave the template unchanged.
- Validation: source-map/citation audit, labeled AI_Proxy rubric, visual pass/fail.

### WP5 — Apply the winning small changes and validate the chain
- Dependencies: a passing WP2, WP3 or WP4 result and Joe's review of the selected visual target. Implementation is a later authorized task.
- Files/interfaces: only the confirmed owner among the costume source in `E:/Zet/Zet_Library_v5/Moonsea/Characters/Tsaeytte/Adult/`, `Config/Prompt_Templates/costume_dressing_v2.md`, `scripts/Run_Costume_Dressing_Jobs.py`, and `zet/services/local_view_reference_service.py`; affected docs under `Docs/`.
- Work: implement one proven change at a time. Regenerate prompt previews and run a fresh left-side chain, then the corresponding right-side views and BACK. Inspect each view before using it as the next predecessor. Retain the existing good fronts; change selections/locks only through the normal workflow after review. If a local BACK edit is the only winner, plan it as a focused repair step rather than rewriting the entire dressing compiler.
- Acceptance: accepted LEFT_PROFILE remains good and RIGHT_PROFILE passes direct review; both back three-quarter views stay back-dominant and continuous; BACK remains square; every rear center hem reaches the visible target; hair, earrings, identity and design details pass. No defective view is promoted as a predecessor.
- Validation: prompt/source-map diff, source and selection hashes, approved `npm run test:e2e` scenario that exercises local character workflow, `git diff --check`, and labeled human image review. No permanent test or new dependency without separate approval.

## Decision gates and risks
- Treat the 16-image investigation as evidence of tradeoffs, not a complete statistical claim about every seed. The AI evaluator once misread a visible BACK_LEFT_3_4 opening as a seam; direct image review controls continuity decisions.
- Prioritize the focused hem edit and garment-only reference experiments. The short-prompt comparison changed wording and length together and did not yield an overall win, so a compiler-wide rewrite has no support yet.
- Keep costume rotation mode as a measured fallback if the crop/lock tests fail to stabilize view direction. Compare its output against the same orientation and garment criteria before adopting it.
- Any additional live renders for these fix experiments are outside the completed 16-image investigation cap and need a new agreed budget before execution.
