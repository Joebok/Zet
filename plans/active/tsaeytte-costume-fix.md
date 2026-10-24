# Adult Tsaeytte Canonical Adventure Gear view repair
Status: active; Joe authorized the plan and a cap of 36 diagnostic renders on 2026-10-23.
Related evidence: `test-results/tsaeytte-costume-evidence/evidence.md` and the completed investigation plan.

## Goal
Preserve the accepted LEFT_PROFILE and good front views; determine whether RIGHT_PROFILE needs correction; produce back-dominant rear three-quarter views and a continuous rear overskirt whose center hem reaches about mid boot shaft, matching the accepted FRONT image's visible rear drape. Preserve Tsaeytte's identity, blouse and jewelry design. Use controlled images to choose changes before editing the production prompt/compiler or reference binding.

Note from Joe: from the costume perspective, right and left profile are identical. The left and right profile head images differ, but not the costume.

## Evidence that sets the order
- Across two paired seeds, removing the full dressed predecessor reduces BACK_LEFT_3_4 face exposure. It also introduces a visible rear skirt opening, and at the second seed weakens the off-shoulder blouse. BACK orientation is already square; deleting its predecessor splits the rear skirt at both seeds. Do not remove Image 2 wholesale.
- All screened prompt/reference combinations and both second-seed pairs keep the rear hem too high. A short operation-first prompt alone does not solve it; no-reference prompts do not solve it. The specific cause of the hem remains unisolated.
- The compiler calculates `BODY_HEAD_ALIGNMENT_LOCK` in `scripts/Run_Costume_Dressing_Jobs.py`, but `Config/Prompt_Templates/costume_dressing_v2.md` does not emit it. Its effect is unknown.
- The authored length uses anatomical “just above ankles” while tall boots hide that landmark. The accepted visual check should name a visible boot/hem relationship before a prompt change is promoted.
- Joe's labeled review accepts the saved LEFT_PROFILE and rejects its no-Image-2 alternative. Both BACK_LEFT_3_4 images and both BACK images fail. He finds the paired full-reference BACK skirt close in length but still too short, and its hair and earrings less satisfactory. The hair/jewelry issue should be checked separately from the skirt geometry.

## Other Notes from Joe

Make sure there are no conditional statements in the prompts - do not depend on the image generation to parse concepts like "for three-quarter view..." - at the time the prompt is generated, we know if it applies.

Likewise, the costume templates/prompts are used to generate the reference images, not for other poses. So we don't need conditions about some feature "may be visible" - if it is important, we should be definitive and state that such thing are or are not visible. If it isn't particularly critical, then it should not be mentioned at all.

I think it is also worth trying rewriting the prompts with the Qwen Image 2.1 skills from the compiler output and having the prompt writer refer to reference images even if those references are not being passed on to ComfyUI. This could tell us if the issues are solveable by prompt editing - if we determine it can, we can reverse engineer the compiler and templates accordingly.

## Luna sized work packets

### WP1 — Freeze visible targets and controls
- Dependencies: Joe's review recorded in `evidence.md`.
- Files/interfaces: private evidence packet; saved run records; no batch source edits.
- Work: use the accepted FRONT center drape at approximately mid boot shaft as the rear center-hem benchmark. Record separate pass criteria for angle, face exposure, continuous rear fabric, hem, hair, earrings, identity and design. Preserve original references, presets, seeds, selections and locks. Inspect the saved RIGHT_PROFILE, recognizing that its costume should match LEFT_PROFILE while its head differs.
- Acceptance: labeled controls and a visible hem benchmark allow independent judgments for each property.
- Validation: `python3 -B test-results/tsaeytte-costume-evidence/pilot.py verify`, image review, source hashes.
- Status: complete. The private pilot verified 44 protected sources; the accepted FRONT gives the mid-boot-shaft visual benchmark. The current selected RIGHT_PROFILE was inspected and remains unmodified.

### WP2 — Qwen Image 2.1 prompt rewrite trial
- Dependencies: WP1.
- Files/interfaces: private prompt and render files under `test-results/tsaeytte-costume-evidence/`; AI_Proxy only.
- Work: give the prompt writer the frozen compiled BACK_LEFT_3_4 and BACK text and all four reference images with roles. Write operation-first, view-specific edit prompts with definite visibility and a mid-shaft rear center hem. Render each with unchanged ordered references at both known seeds (four images). If rear-quarter orientation still fails, try its rewritten prompt informed by Image 2 during authoring but omit Image 2 from the ComfyUI attachments (two images). Cite only runtime-bound images in the final render prompt.
- Acceptance: both seeds preserve identity, blouse, jewelry and continuous skirt while meeting angle and hem targets. A rewrite alone is not promoted on a single attractive seed.
- Validation: prompt/reference citation and hash audit, same-seed comparison, labeled visual review.
- Status: complete as a diagnostic. All four full-reference rewrites rendered. The two BACK_LEFT_3_4 outputs are more back-dominant with continuous fabric; both BACK outputs stay square and continuous. All four hems end above boot cuffs, so the rewrite alone fails the length target. The no-Image-2 branch is unnecessary for angle at these seeds.

### WP3 — Isolated BACK hem edit
- Dependencies: WP2 leaves BACK short.
- Files/interfaces: private AI_Proxy asks using the saved BACK result as the only edit base.
- Work: edit only the continuous rear hem to the visible target using two seeds. Preserve camera, body, hair, blouse, belt, jewelry, embroidery, leggings and boots. Test any hair/jewelry correction separately after the hem decision.
- Acceptance: both seeds meet hem and continuity criteria without changing untargeted content.
- Validation: same-input comparison, labeled image review, frozen hashes.
- Status: complete as a diagnostic. The one-image edit failed to extend the hem at both seeds; one seed also globally corrupted background and surface texture. Do not promote it. Next test a visual garment-length reference while preserving the original design references.

### WP4 — Separate garment information from orientation
- Dependencies: WP2 rear-quarter trial fails angle or continuity.
- Files/interfaces: private cropped reference and AI_Proxy asks; eventual `zet/services/local_view_reference_service.py` only if supported.
- Work: replace only rear-quarter Image 2 with a garment-only crop of the accepted LEFT_PROFILE, retaining blouse, belt and overskirt but excluding head, face and full-body framing. Render two matched seeds. If the crop fails, test the already-computed `BODY_HEAD_ALIGNMENT_LOCK` as the only prompt change in two matched seeds. Rotation is a later measured fallback.
- Acceptance: improved angle and continuous canonical garment at both seeds without shortening the hem or losing identity.
- Validation: reference hashes, same-seed comparisons and source-map/citation audit.
- Status: complete as a diagnostic. The Qwen rewrite solved the rear-quarter angle at both saved seeds, so a head-excluding crop was not needed. Adding `BODY_HEAD_ALIGNMENT_LOCK` alone left the face too exposed and the hem short at both seeds. A dressed rotation shortened the BACK hem and misplaced the pendant. Neither change is promoted.

### WP5 — Promote proven changes and verify the chain
- Dependencies: repeated visual winner from WP2, WP3 or WP4 and Joe's review before selection/lock changes.
- Files/interfaces: only confirmed owners among the Tsaeytte costume source, `Config/Prompt_Templates/costume_dressing_v2.md`, `scripts/Run_Costume_Dressing_Jobs.py` and `zet/services/local_view_reference_service.py`; affected prompt/local-character docs.
- Work: implement one supported change at a time. Compile all eight costume image prompts with view and visibility choices resolved before emission: state important visible/hidden features definitively and omit immaterial ones. Regenerate previews, review a fresh left chain, corresponding right views and BACK before promoting predecessors. Keep accepted fronts and LEFT_PROFILE as controls.
- Acceptance: both rear quarters are back-dominant and continuous; BACK is square; rear center hems reach the accepted visible target; hair, earrings, identity and costume pass; no defective predecessor is promoted.
- Validation: all-view prompt/source-map and reference audit, approved character-to-costume E2E scenario, `git diff --check`, source/selection hashes, labeled human review.
- Status: partially implemented; visual acceptance remains open. The Tsaeytte source, shared costume template, compiler guidance, and two rear-quarter costume orientation locks now emit definite visibility/angle wording. Eight text previews compile without conditional visibility language. The approved S2 end-to-end scenario passed in the four-scenario fast run. Joe accepted the private local BACK_LEFT_3_4 render, but it came from an imagegen-corrected edit canvas outside the managed batch. He asked for BACK to cover both boot cuffs. The final four compiled-prompt renders did not meet the hem target, so no predecessor, selection, or lock was promoted.

## Budget and decision gates
- Diagnostic work is capped at 36 completed new renders. The first block is four full-reference rewrites, up to two rewritten no-Image-2 renders, two hem edits, two cropped-reference renders and two alignment-lock renders. Use remaining capacity only for targeted confirmation, rotation, or separate hair/jewelry trials needed to resolve observed failures. Stop early when a repeated winner makes later trials unnecessary. A fresh production chain requires a separate review before it changes selections or locks.
- Direct visual inspection controls continuity decisions: the prior AI evaluator misread a visible center opening as a seam.
- Never submit an omitted image to ComfyUI merely because the prompt writer inspected it; never leave a citation to an unbound image in the render prompt.
- Do not add permanent tests or dependencies without Joe's separate approval.

## Progress and decisions
- 2026-10-23: Joe authorized implementation of the revised plan, then raised the diagnostic cap from 12 to 36 renders. The accepted FRONT center drape supplies the visible mid-boot-shaft benchmark. Existing LEFT_PROFILE remains the costume control; the head differs on RIGHT_PROFILE.
- Four Qwen rewrite/full-reference outputs improved the rear-quarter angle without splitting the skirt, but none extended the hem. The isolated BACK hem edit is the next changed factor. Results are recorded in the private improvement evidence packet.
- The isolated BACK hem edit failed at both seeds, with severe global texture contamination at one seed. A stronger visual length reference is needed before any production hem change.
- Joe approved the two image-edited rear silhouettes as visual targets only on 2026-10-24. Feeding the corrected rear-quarter silhouette as Image 2 reached the boot-shaft target at two seeds but dropped bodice decoration. Editing that dressed silhouette as Image 1 with a focused blouse/design prompt kept the rear angle, long continuous hem, visible left earring, and bodice trim at both seeds. This remains a diagnostic recipe because the visual target was made outside the local pipeline.
- The matching BACK edit-base recipe reached the hem target in one seed, but its paired seed had severe whole-background texture corruption. Two further seeds are running to measure repeatability. No source batch image, predecessor selection, or library lock was changed.
- The image-prompt source updates compiled for all eight views. The approved fast E2E suite passed four scenarios in 38.8 seconds. Final visual review and a fresh production chain remain open.
- 2026-10-24: Joe passed the leading private BACK_LEFT_3_4 result and found BACK close, with the remaining requirement that teal fabric cover both folded boot cuffs. A further BACK pair from the corrected edit canvas produced one clean belt and one erroneous back buckle; the earlier pair contained a severe texture failure. The last four renders of the new compiled prompt with original frozen references failed the boot-cuff/angle criteria. The source now states the cuff coverage explicitly, but the cap prevents another live test. All 36 approved diagnostic renders are complete (30 AI_Proxy, six imagegen).

## Remaining completion gate

The approved BACK_LEFT_3_4 image is a private diagnostic, not a managed batch candidate. A safe path is needed to create a managed candidate from a reviewed dressed edit canvas, then render and review BACK and BACK_RIGHT_3_4 from accepted predecessors. The final BACK cuff wording needs a live check. This work requires an additional diagnostic render budget beyond the completed 36 and Joe's review before any selection or lock publication. Preserve the current accepted FRONT and LEFT_PROFILE through that chain.
