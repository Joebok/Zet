# System Prompt Review

## Policy

ModelUpdater aliases select managed capabilities and runtime parameters. They do not own Zet task behavior, output rules, grounding policy, or authorization. Zet keeps each task contract in backend code or a version-controlled feature prompt.

Model selection is global on the dashboard's AI Controls page. The corresponding `config.toml` values are stored under `[AIModels]` for asset workflows, prompt condensation, prompt analysis, Scene Builder, and the four Prompt Evolution roles. New Prompt Evolution runs snapshot the current global selections; existing runs retain their recorded models.

## Call paths

- `AIProxyService` queues general asset-workflow and prompt-condensation jobs.
- `ScenePromptAnalysisService` queues compiled scene-prompt analysis.
- `PromptEvolutionService` queues bootstrap, visual critic, regression check, synthesis, diagnosis, edit, directed-refinement, and JSON-repair jobs.
- `SceneBuilderInterviewService` calls `OllamaModelService.generate_json` directly with its feature-owned system instruction and schema.

`AI_Manager/ollama_proxy_worker.py` is transport-focused. It sends feature-owned user prompts through `/api/generate` or multimodal `/api/chat` and forwards any supplied JSON Schema through Ollama's `format` field. It does not infer behavior from the model alias or add a generic system prompt.

## Prompt contract

- State each instruction once and keep prompts task-specific.
- Treat embedded source prompts, evidence, prior responses, and check objects as data rather than instructions.
- Keep dynamic source material and user input out of system instructions.
- Preserve supplied identifiers exactly.
- Use null, unknown, or empty representations permitted by the contract instead of guessing.
- Give `vision-analysis` and `vision-analysis-alt` the same visual-review contract. Their independence comes from isolated calls and different managed models.

## Validation

Ollama's `format` field constrains generation but does not replace consumer validation. The owning service parses structured output and applies task-specific semantic validation before accepting it. JSON repair output is checked by the original consumer contract.

## Acceptance criteria

- No active Zet code, configuration, or UI default depends on retired prompt-bearing aliases.
- All model roles are selected globally on AI Controls; workflow pages do not override them.
- Each task is understandable from its feature-owned instructions and inputs.
- Structured consumers reject invalid schemas, identifiers, or unsupported observations.
- Text, one-image, multi-image, source-data boundary, missing-evidence, and legacy-manifest behavior is covered by tests.
