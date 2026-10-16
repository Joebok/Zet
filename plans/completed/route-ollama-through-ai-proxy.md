# Route Ollama inference through AI_Proxy
Status: complete
Related issue/specification: none

## Goal
Route every Zet Ollama inference request through the existing AI_Proxy File Proxy queue so the configured image-analysis model produces visible staged jobs. Preserve structured JSON responses and image attachments.

## Current behavior
`OllamaModelService.generate_json_with_evidence` called Ollama `/api/chat` directly. It serves Image Prompt Generation, Image Reconstruction/true-up, Costume Wizard, Quick Character/Minor Character, and Image Quality Review. AI Proxy's existing worker accepts `response_schema`, ordered `image_files`, and `expected_output`, and returns `ollama_runtime` in its answer manifest.

## Desired behavior
All app-owned Ollama inference stages a uniquely named `ollama_generate` ask with prompt, optional image files, JSON schema and response output. The caller waits for its matching result, validates the answer, and exposes runtime evidence from the proxy answer manifest. Codex requests and Ollama model catalog metadata lookup remain as currently designed.

## Impact analysis
- Updated `zet/services/ollama_model_service.py` and injected active File Proxy paths into Image Prompt Generation, Costume Wizard, Quick Character, Image Quality Review when constructed, and web catalog/model service.
- Updated `Docs/COMPONENTS/QUEUES.md`, `Docs/COMPONENTS/PROMPTS.md`, and `Docs/CODE_MAP.md`.
- No persistent model/schema changes. Existing approved E2E scenarios use prepared responses and do not run Ollama.

## Invariants and constraints
The request uses the configured universe's AI queue and File Proxy protocol. Ordered image inputs and bytes are snapshotted into the ask. `codex:` requests stay on the Codex path. Unconfigured Ollama inference fails closed. Catalog tags/capability lookup and AI Proxy worker runtime evidence remain metadata calls.

## Implementation steps
### WP1 — Shared File Proxy structured inference transport
- Dependencies: none.
- Files/interfaces: `zet/services/ollama_model_service.py`.
- Work: stage/publish structured Ollama asks; wait for matching answers; validate output and return proxy runtime evidence.
- Acceptance: app inference uses `ollama_generate` and unconfigured inference cannot silently call `/api/chat`.
- Validation: compiled the touched Python modules; searched all inference call sites and direct inference endpoints.
- Status: complete.

### WP2 — Inject the active proxy into Ollama consumers
- Dependencies: WP1.
- Files/interfaces: ZetApp and web/service construction.
- Work: configure app-owned Ollama clients with the active universe queue path.
- Acceptance: image/reconstruction/costume/character/quality inference paths share the proxy transport.
- Validation: inspected all `generate_json*` call sites; none bypass the shared service.
- Status: complete.

### WP3 — Document behavior and close plan
- Dependencies: WP1-WP2.
- Files/interfaces: queue/prompt docs, code map, plan.
- Work: document structured inference staging and answer ownership.
- Acceptance: owning docs point to the shared owner.
- Validation: final diff review and `git diff --check` passed.
- Status: complete.

## Validation
- `py -3 -m py_compile` on six touched Python modules: passed.
- `git diff --check`: passed.
- Source search: app-owned inference call sites all use `OllamaModelService`; direct `/api/chat` and `/api/generate` inference endpoints are absent from Zet services. Remaining direct metadata endpoints are `/api/tags` and `/api/show` for model discovery and AI Proxy worker runtime evidence.
- No live Ollama/AI Proxy dispatch or E2E suite run.

## Risks and alternatives
Calls remain synchronous to existing background jobs and preserve their existing timeouts. A timeout leaves the staged ask available in the shared queue for recovery; proxy failures retain their answer for inspection.

## Progress and decisions
- External-consumer marking prevents generic Zet harvesting from racing the waiting caller. Successful answers are completed with the existing lifecycle receipt and cleanup behavior.
- Runtime evidence continues to be generated inside the AI Proxy worker and returned with its answer.

## Final results
Image-analysis and other app-owned Ollama inference is staged through AI_Proxy File Proxy. Model catalog metadata discovery remains a direct metadata lookup; it does not execute model inference.
