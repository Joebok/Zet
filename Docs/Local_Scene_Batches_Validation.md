# Local scene batches: implementation and validation

Implemented October 1, 2026. Scene authoring stays in Scenes and Scene Builder;
Scene Batches owns local production. Zines remains immediately after it.

## Implementation packets

1. The shared image picker accepts approved assets with missing or empty entity associations.
2. Active settings and profile lists expose ComfyUI/Qwen Image 2.1. Legacy saved settings remain readable and are ignored; saving removes retired renderer settings.
3. Submission, ad hoc generation, adapter dispatch, and render-capable tooling reject retired backends and model families. Historical compile-only tooling remains available.
4. Each scene attempt has its own persistent batch, frozen scene/settings/source material, dynamic targets, and candidate counts (default four).
5. Batch compilation uses the existing target projections, IR, reference ordering, and Qwen compiler. Selected batch images satisfy prerequisites without prior publication; more than ten references fails explicitly.
6. Groups follow graph dependencies and explicit selection checkpoints. Stop/resume, failed-candidate retries, rerenders, submission recovery, and attempt fencing retain completed images and old attempts.
7. Shared rankings use scene criteria, with independent human decisions and ordering. Selection changes archive only downstream groups.
8. Explicit publication checks source and artifact hashes, promotes targets in dependency order, and uses existing locks, backups, provenance, and recoverable publication journals.
9. Story/scene-scoped API routes call backend services; dashboard batch status includes scene context and links.
10. Scene Batches provides history, controls, candidate thumbnails, exact prompt links, and every numbered reference. Scenes and Builder open it with their selected context.
11. Prompt analysis and second opinions are fenced by batch, target, attempt, and prompt hash. Scene observations and improvement packages reuse the shared workflow; they do not rewrite authoring documents.
12. Render Console and Image Review leave active navigation and shortcuts. Old links resolve batch provenance or explain retirement. Zines pages, routes, configuration, and documents remain.

## Automated validation

Focused backend/API regression command:

```powershell
python3 -m pytest tests/test_local_scene_batches.py tests/test_scene_reference_picker.py tests/test_qwen_scene_prompt.py tests/test_scene_render_compiler.py tests/test_scene_render_auto_analysis.py tests/test_scene_image_review_service.py tests/test_story_service.py tests/test_zine_web.py tests/test_ad_hoc_image_generation_service.py tests/test_local_prompt_improvement_service.py tests/test_config_service.py tests/test_pipeline_control_service.py tests/test_comfyui_render_service.py tests/test_stable_matrix_adapter.py tests/test_local_candidate_review_contract.py tests/test_local_character_asset_pipeline.py tests/test_local_image_pipeline_policy.py -q
```

Result: **176 passed, 3 subtests passed**. JavaScript syntax checks and the final
diff whitespace check passed.

Browser workflow:

```powershell
npx playwright test tests/browser/scene-batches.spec.mjs
```

Result: **1 passed**.

The browser test uses the real dashboard/API with simulated worker answers and
verifies authoring context, selection checkpoints, prompts, reference thumbnails,
publication, canonical Zine references, and retirement navigation.

## Live ComfyUI verification

`python3 -u -m tests.manual_scene_batch_smoke` produced real Qwen Image 2.1 images
for background, subscene, and Full Scene, then successfully published all three
and built a Zine in an isolated temporary library. Queue answer delivery was
simulated locally; the external AI Proxy worker was not exercised. One candidate
per target used the shared deterministic single-survivor ranking path.

Retained artifacts:
`C:/Users/Joe/AppData/Local/Temp/zet-local-scene-smoke-edtgjbji`.
Batch state and publication are COMPLETE; both the canonical scene PNG and Zine
PNG were independently verified. The original run's final success-message print
hit the Windows console's unsupported arrow character; the harness now uses ASCII.

## Separate existing failures

A broader run including `test_head_image_pipeline.py` and
`test_local_batch_status_service.py` had ten failures. Running those two modules
against a clean archive of unchanged HEAD reproduced all ten:
eight Head-Image compiler fixture/template-path failures, one Head-Image
reference-manifest API failure, and the already known omission of queued costume
batches from batch status. They are not new scene-batch regressions and are
outside this implementation's scope.
