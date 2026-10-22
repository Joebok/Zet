# Qwen Image 2.1 LLM roles
Status: complete
Related specification: Joe's approved implementation plan, 2026-10-22.

## Goal and constraints
Own modular Qwen guidance in Zet and apply it to existing prompt-authoring/review calls through AI_Proxy. Make Config's role inventory authoritative. Preserve deterministic compilers, alignment and correction composition, frozen requests, explicit user intent, ordered bindings and source markers. No extra inference passes, new dependencies, permanent scenarios, live inference, production operations or external writes. Preserve unrelated Docs-Joe changes.

## Current behavior and impact
AIJobService and manifest producers converge at FileProxyClient; AIRequestPreparation freezes native requests. AI_Proxy already consumes system instructions for both Codex and Ollama. Config exposes an incomplete five-role list plus handwritten cards. ConfigService, PipelineControlService, request producers/wrappers, Config UI, and shared AI/prompt/data documentation are affected. No proxy changes are required.

## Luna-sized packets
Each packet is sequential, owned by the implementing agent, and initially pending.

| Packet | Files/interfaces | Dependency | Acceptance / validation | Status |
|---|---|---|---|---|
| WP1 Inventory | This plan; caller search in zet/services and Scripts | none | Every text producer mapped below; inspect approved scenarios | complete |
| WP2 Skill package | Config/LLM_Skills/qwen-image-2.1 | WP1 | Source hashes match; independent adapters; disposable hash checks | complete |
| WP3 Registry/config | llm_role_service.py, config_service.py, pipeline_control_service.py | WP1 | Valid roles/overrides; old defaults preserved; disposable config checks | complete |
| WP4 Composition | llm_skill_service.py, ai_job_service.py, file_proxy_client.py, compatibility wrappers | WP2,3 | Both publication paths composed once; freeze/replay; disposable envelopes | complete |
| WP5 Narrative/image | narrative_* services, image_prompt_generation_service.py, image_reconstruction_service.py | WP4 | Explicit intent and role; remove competing prose rules; prepared requests/S1,S3 | complete |
| WP6 Character calls | wizard/review/ranking/template services and Recipe Lab facade | WP4 | Split helpers; prompt-only guidance; prepared requests/S2 | complete |
| WP7 Config UI | pipeline_control_service.py, web/app.py, index.html, zet.js, zet.css | WP3,5,6 | Complete cards, indicators, inheritance/editor links; isolated browser | complete |
| WP8 Validation/docs | Docs component/data/code-map owners; new ADR; this plan | all | Four existing E2E scenarios, syntax, disposable checks, diff review; archive | complete |

## Call inventory
Role IDs are the registry keys. Provider support reflects current call paths; Codex-only callers remain Codex-only. Existing task/session choices override role settings; otherwise role overrides precede the old configured defaults.

| Producer | Roles / Qwen application | Default / capability |
|---|---|---|
| NarrativeProxyService | narrative_interview off; narrative_prompt authoring | NarrativeScene; text |
| ImagePromptGenerationService | image_prompt authoring; inventory_identity off | ImagePromptGeneration / CodexDefault; vision |
| ImageCatalogService | inventory_metadata off | ImageDescription; vision |
| ImageReconstructionService | reconstruction_prompt authoring; reconstruction_review review | ImagePromptGeneration; vision |
| QuickCharacterWizardService / MinorCharacterWorkflow | character_description fragments; character_review review | QuickCharacterWizard; vision |
| CostumeWizardService | costume_observation off; costume_template fragments; costume_evidence_review off; costume_render_review review | CostumeWizard; vision when images |
| LocalTemplateRevisionService | character_prompt_review review; template_revision review (compatibility continuation) | CodexDefault; text / vision |
| LocalPromptImprovementService | local_prompt_improvement review | CodexDefault; Codex vision |
| LocalCharacterRefinementService | character_refinement review | CodexDefault; vision |
| LocalImageRankingService | image_ranking off | CodexDefault; Codex vision |
| LocalBodyReferenceService | body_review_codex off; body_review_local off | CodexDefault / LocalBodyReferenceReview; vision |
| ImageQualityReviewService / Review_Image_Recipe_Lab | recipe_qa off | supplied local model; vision |
| AIProxyService | asset_workflow off; prompt_condense authoring, compatibility only | AssetWorkflow / PromptCondense; text |
| Retired configuration only | scene_builder off; prompt_analysis review, retired | SceneBuilder / PromptAnalysis; text |

## Validation
Run npm.cmd run test:e2e (four approved scenarios), changed Python/JS syntax checks, git diff --check. Disposable checks cover roles, both request paths/providers, scoped modules, missing files, hashes, replay and configuration/UI. No permanent tests added. Prepared responses do not establish artistic quality.

## Progress and decisions
- Initial git status: modified Docs-Joe/NarrativePrompts.md; untracked Docs-Joe/Qwen-Head-Image-Prompts.md. These are user-owned and excluded.
- Python 3 verified with python3; no live calls authorized.
- Guidance selection follows render intent, not analysis attachment count. Skill source remains unchanged; adapters preserve envelopes and facts, while skill owns prompt prose and length.

## Final results
- Completed WP1–WP8 sequentially. Imported source hashes match unchanged source files; independent contract/authoring/fragment/review adapters are repo-owned.
- Added a shared registry, role overrides and frozen guidance for both publication formats/providers. Config shows 20 active and five compatibility/retired roles with badges, model inheritance and source-editor links.
- Split existing wizard helpers by purpose. Shared character reconstruction retains fragment/review role identity; old saved model choices remain explicit. Deterministic compiler/alignment/correction paths are unchanged.
- Discovered Recipe Lab CLI had no common proxy binding. Added --config and role-aware model selection so its existing QA call uses AI_Proxy, without executing it live.
- Four approved E2E scenarios passed twice (44.4s initial, 40.8s final). Final run had an existing nonfatal WinError 32 usage-maintenance warning. One intervening test command was blocked by the owned browser fixture on port 8765; stopping that fixture resolved it.
- Disposable checks passed 371 role/provider/mode/request cases plus source hashes, frozen replay, missing/invalid guidance, Config round trips, model precedence and AST call inventory. Actual isolated browser checks passed role indicators, model popup/save/reload/clear, source-editor loading, no browser errors and 1280px/390px containment; screenshots inspected.
- Python AST, JS syntax and final git diff --check passed. No dependencies or maintained scenarios added; only the existing queue fixture received explicit role metadata.
- Updated affected knowledge owners and ADR 0027. No documentation claim depends on live artistic results. No live calls, production writes/restarts/deployment or external writes occurred. Existing Docs-Joe user changes were preserved.
- Real model adherence, artistic quality and physical-device use remain unverified; there is no implementation blocker.
