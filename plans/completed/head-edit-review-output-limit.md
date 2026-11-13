# Head Edit review output limit
Status: complete
Related issue/specification: Request AI_99c5c22f3f53253ca083b262ae744b2b

## Goal
Allow Zet Test Head Image Edit template reviews to return structured findings
larger than Ollama's default 6,144-token output cap, and explain when structured
AI output is still truncated.

## Current behavior
`CharacterContainerTemplateService._review_job` calls the shared
`AIJobService.generate_json` without per-request Ollama options. The selected
Zet-Image-1 alias stops at 6,144 output tokens. JSON parsing errors are then
surfaced without the worker's recorded `done_reason=length` and `eval_count`.

## Desired behavior
Head Image Edit template reviews using Ollama request 12,288 output tokens.
Other workflows, model defaults, and Codex requests keep their current settings.
When structured output fails to parse after Ollama reports `done_reason=length`,
surface a clear limit message including the generated token count where present.

## Implementation steps
### WP1 - Raise the Head Edit review output budget
- Dependencies: none.
- Files/interfaces: `zet/services/character_container_template_service.py`.
- Work: pass `options={"num_predict": 12288}` only for Ollama Head Image Edit
  template reviews.
- Acceptance: intended request has the override; other model/workflow requests do not.
- Validation: disposable request-option fixture.
- Status: complete.

### WP2 - Explain truncated structured output
- Dependencies: none.
- Files/interfaces: `zet/services/ai_job_service.py`.
- Work: catch JSON decode failure for structured Ollama output and use existing
  worker runtime metrics to identify length truncation, preserving normal errors.
- Acceptance: truncation reports the output limit and token count; unrelated
  parse failures and valid structured results retain their behavior.
- Validation: disposable response fixtures.
- Status: complete.

## Validation
`npm.cmd run test:e2e`: passed (4 scenarios, 43.0 seconds). `git diff --check`:
passed. Disposable checks verified the output override's model/workflow scope,
valid JSON, truncation diagnosis and unchanged unrelated JSON errors. No live
Zet Test request was run.

## Progress and decisions
Diagnosis found the specified request and its retry both ended at 6,144 tokens
with `done_reason=length`. The same review already succeeded with Codex Luna.
Implementation passes 12,288 output tokens for Ollama Head-Image Edit template
reviews and explains structured Ollama output truncation through worker metrics.

## Final results
Completed in `zet/services/character_container_template_service.py`,
`zet/services/ai_job_service.py`, `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, and
`Docs/COMPONENTS/AI_JOBS.md`. Local validation passed; deployment and a fresh
live Ollama review remain unperformed.
