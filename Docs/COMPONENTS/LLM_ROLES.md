# LLM roles and Qwen Image 2.1 guidance

## Prompt Generator Pilot role (2026-10-24)

`prompt_generator` is a vision-capable authoring role. It uses the configured Codex Luna default, accepts capability-checked local models, and exposes higher Codex tiers only after an explicit escalation request or repeated failed drafts. Costume and Head-Image Edit adapters are repo-owned modules. Packet preparation records integration and module hashes; before submission the service rejects a changed instruction package. The normal FileProxyClient boundary composes and freezes effective instructions with each native request. Codex submissions are gated by `CodexUsageService`'s configured 10% reserve; unavailable usage pauses while preserving the session. See [Prompt Generator Pilot packets](PROMPTS.md#prompt-generator-pilot-packets-2026-10-24).

This document owns role classification, model inheritance and repo-managed skill composition. [AI jobs](AI_JOBS.md) owns transport and collection; [Prompts](PROMPTS.md) owns compilation and ordered image bindings.

## Ownership and inventory

[llm_role_service.py](../../zet/services/llm_role_service.py) is the single inventory of roles, labels, default config bindings, provider/capability restrictions, lifecycle status, designated prompt fields and skill modules. Config's Managed LLM Roles cards use this inventory through `PipelineControlService.managed_llm_roles`; maintained producers identify their role explicitly. Split helpers distinguish observation, prompt fragments, template evidence review and render correction suggestions.

Active roles cover Narrative interview/prompt writing; Inventory identity/metadata and image-to-prompt drafting; reconstruction authoring/review; character description/review; Costume observation/template/evidence/render review; governing-template review; local prompt improvement and post-render Character.md improvement; dedicated character refinement; comparative ranking; the two Body assessment paths; and Recipe Lab QA. Historical template revisions and traditional asset/condensation producers are compatibility roles. Scene Builder and scene-prompt analysis are retired settings. Their cards do not enable workflows. CodexDefault is a shared model default, not a role.

Only prompt authors, reusable prompt fragments, and prompt reviewers receive the Qwen guidance. Identity/catalog facts, observations, pure ranking, Body compliance and rubric QA do not. Review guidance scopes existing correction suggestions; deterministic correction assembly does not acquire an LLM pass. Local character compilation and Minor Character alignment remain deterministic. Character descriptions retain fragment guidance when they use shared reconstruction analysis.

## Repo-owned skill and update workflow

[Config/LLM_Skills/qwen-image-2.1](../../Config/LLM_Skills/qwen-image-2.1/README.md) contains unchanged imported skill/reference files, their import manifest, and independent Zet adapters. Runtime never reads the personal Codex skill installation. Source rules govern prompt wording, structure and length; generic concise/shortest prose restrictions and forced openings have been removed from affected authoring calls. Source templates remain protected by Zet markers, schemas, canvas choices, explicit intent and binding contracts.

The contract adapter keeps application JSON fields and source-document structure, literal user text, explicit subject counts/exclusions, transparency, anatomical asymmetry and latest operator direction. Authoring, fragment and review adapters target different responsibilities. Fragment/report outputs do not become full 400–500 word scenes. Complete prompt prose follows the applicable source writing rules within its existing fields, without invented content to fill a quota. See package README for the manual update procedure; no downloads or imported scripts run during requests.

## Preparation and replay

[llm_skill_service.py](../../zet/services/llm_skill_service.py) composes once at `FileProxyClient`'s publication boundary after native request preparation and before the inventory is frozen. Both prebuilt `AIJobService` requests and manifest-based producers pass through it. AI_Proxy's existing Codex and Ollama workers receive the composed `system` instructions; no proxy or provider-specific skill installation is needed.

The producer supplies `llm_role` and `llm_context`, including the intended operation. Module selection follows `generate`, `edit`, `composite` or `mixed` downstream intent, never analysis attachment count. Reconstruction originals remain analysis-only. Narrative supplies planned ordered render references, effective style, canvas and transparency; deterministic bindings retain their existing ownership and single-image convention. Character template review uses mixed guidance for compiled future tasks.

The native request and ask manifest retain `llm_guidance` with role, application, context, module hashes, integration/manifest identity and effective system/prompt hashes. Applicable jobs also inventory `llm_instructions.md`. Local job records retain that prepared request through the normal repository. Frozen requests, replayed attempts and collection retain their original instructions; an installed skill update affects newly prepared requests only. Existing continuation identity calculation remains unchanged. Missing required modules, invalid operations and unknown roles fail preparation visibly. Old already-published envelopes are not rewritten.

## Model inheritance and Config

Optional `[LLMRoles.Models]` TOML entries map registry role keys to models. Precedence is explicit task/session choice, role override, then the original model setting. Empty overrides inherit. Existing saved sessions without `model_explicit` retain their saved model as an explicit selection; new character/reconstruction records distinguish operator selections from inherited defaults. Shared character reviews retain their domain role even when using reconstruction's comparison engine.

Config shows all 26 roles (21 active and five compatibility/retired), purpose, effective and inherited model, provider/capability requirements, and a Qwen Yes—authoring/fragments/review or No indicator. Instruction-file disclosures open existing Template Editor sources. Selectors use the shared capability-aware popup. Provider restrictions are validated locally; changed overrides also validate against the existing proxy-owned model catalog. Unknown saved model choices remain visible. Model defaults and compatibility settings remain separately editable; no normal-library migration or model-setting rewrite happens on load.

Recipe Lab's CLI accepts `--config` and optional `--model`, binds the configured universe and common AI_Proxy paths, and resolves `recipe_qa` before requesting inference. It does not call a local model directly.

## Verification boundaries

The four approved E2E scenarios remain unchanged in purpose; the shared queue fixture now names its skill-free role explicitly. Disposable request checks cover both providers/publication formats, modules, source hashes, unknown roles, missing files, new-versus-frozen instructions, model inheritance and Config round trips. Isolated browser checks cover cards, actual override popup/save/reload/clear, source-editor loading and desktop/narrow containment. These establish integration behavior, not real model adherence or image quality. Live inference and production deployment require separate authorization.
