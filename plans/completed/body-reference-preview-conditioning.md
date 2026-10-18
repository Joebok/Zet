# Body-reference preview conditioning
Status: complete
Related specification: Joe's request, 2026-10-18: compile the actual future render prompt before its reference images exist.

## Goal and current behavior
Body prompt previews append reference instructions to a compiler result that ignores declared references and always says no source image. Staged rendering resolves the correct predecessor but recompiles the same unconditioned body text. Review correctly cannot repair runtime composition.

## Impact and constraints
Owners: body compiler/template, local prompt preview, body adapter, render slots and shared selected-view reference metadata; Assembly/Dressing compiler validation and shared review instructions. Preserve immutable reviews/queued requests, universe isolation, ordered inputs and real-file validation. No live library mutation, inference, dependencies, or permanent tests. Affected knowledge: PROMPTS, LOCAL_CHARACTERS and CODE_MAP; reference-order and staged-generation invariants and storage schemas are unchanged. Existing READY review artifacts remain historical evidence. New proposals upgrade the exact obsolete body task clause to the runtime placeholder without rewriting their parent or losing other edits.

## Work packets
### WP1 — Compile the body reference contract
- Dependencies: none.
- Files: Scripts/Run_Body_Reference_Jobs.py, Config/Prompt_Templates/body_reference_v2.md, local_view_reference_service.py.
- Work: accept explicitly supplied local body design references, validate them, compile matching image-input wording and manifests, share stable reference descriptions between declared and actual inputs.
- Acceptance: FRONT has no inputs; conditioned views name their actual predecessor; traditional body compilation still refuses images; declared inputs remain preview-only.
- Validation: disposable isolated compiler comparisons and missing-reference rejection checks.
- Status: complete.

### WP2 — Bind previews and renders identically
- Dependencies: WP1.
- Files: local_prompt_preview_service.py, local_body_reference_service.py, render_slot_service.py, local_template_revision_service.py, Run_Character_Assembly_Jobs.py, Run_Costume_Dressing_Jobs.py.
- Work: declare planned predecessors across all four pipelines (including chosen BACK source); pass resolved render references into body compilation before wrapping/freezing prompts. Include compiler-added resources in preview input metadata. Explain future inputs to the reviewer; validate batch references in Assembly/Dressing. Preserve retries and submitted inputs.
- Acceptance: all eight preview prompts in each pipeline exactly match fresh render prompts using equivalent real references and accepted sources.
- Validation: disposable isolated preview/render comparisons; approved S2 E2E regression.
- Status: complete.

### WP3 — Verify and document
- Dependencies: WP2.
- Files: Docs/COMPONENTS/PROMPTS.md, Docs/COMPONENTS/LOCAL_CHARACTERS.md, Docs/CODE_MAP.md, Docs/Testing.md, this plan.
- Work: document planned bindings, actual-file boundary and historical-review limitation; record observed checks, review final diff and archive plan.
- Acceptance: relevant checks pass and no unrelated files change.
- Validation: Python AST, focused E2E, git diff --check and final diff inspection.
- Status: complete.

## Progress and results
Joe explicitly expanded applicability to all character pipelines during implementation. The shared preview now declares stable same-side reference descriptions for Body/Head/Assembly/Dressing and uses each compiler's returned ordered inputs. Runtime provenance retains candidate IDs separately from prose. Assembly/Dressing needed explicit validation for the new batch-reference role. Inherited body source snapshots also needed the obsolete exact no-image clause upgraded when creating a new proposal, otherwise reanalysis could retain the old contradiction. No new architecture or persistent schema was introduced.

`python3 -B test-results/check-preview-conditioning.py` passed 33 exact preview/render comparisons (32 pipeline/view combinations plus uploaded Head FRONT), all four alternative rear-right BACK bindings, compilation with no generated batch images, an accepted costume-source edit with a separate costume snapshot, missing/declared reference rejection in production compilation, traditional Body image rejection and the frozen-input guard. A new proposal inherited an old task template, upgraded its input clause, preserved another authored edit and left the parent bytes unchanged; all eight upgraded body previews compiled without a conditioning contradiction. The disposable fixture uses the existing seed, private queues and indexes, with no live execution. Preliminary fixture-path errors and a manifest-variable implementation error were corrected before the passing run.

`npm.cmd run test:e2e -- --grep "character-to-costume"` passed the approved S2 scenario (18.6 seconds including startup). Python AST parsing and `git diff --check` passed. Existing S2 covers front Assembly/Dressing; disposable checks establish the additional compiler contracts without adding maintained scenarios. Final diff inspected for unrelated changes.

## Final results
Previews and fresh render compilation share future/actual reference contracts across all four staged character pipelines. Body no longer combines a conditioned wrapper with unconditioned task/input text. Updated affected documentation. Saved reviews, accepted old source overlays, queued asks and published images remain unchanged. Reanalyze and accept a new body version to adopt the updated input contract in an existing batch. Live inference, visual quality and production deployment were not exercised.
