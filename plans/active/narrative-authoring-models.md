# Narrative scene authoring model overrides
Status: active
Related issue/specification: none

## Goal
Make Interview and Prompt writing model choices available on the scene page. Store overrides per scene, let existing target overrides take precedence, and expose the effective model accurately.

## Current behavior
Scene JSON has no model fields. Target JSON stores `interview_model` and `prompt_model`. Target job dispatch resolves only target fields against the Config role and Narrative default. The scene header labels the configured Narrative default beside the Qwen renderer.

## Desired behavior
Scene model choices persist independently by role. Targets inherit scene choices unless target overrides are set. Clearing scene overrides returns to Config inheritance. Submitted jobs keep their selected model provenance.

## Impact analysis
Affected areas: `NarrativeScene`, `NarrativeSceneService`, `NarrativeGenerationService`, `narrative.js`, Narrative/Data Model/LLM Roles documentation. No migration or public route additions are needed. Existing PATCH routes accept scene fields.

## Invariants and constraints
Use AI_Proxy and the shared capability-aware model picker. Preserve target overrides and saved job provenance. Keep universe-scoped Narrative storage. No permanent scenario additions.

## Implementation steps
### WP1 — Scene persistence and model resolution
- Dependencies: none.
- Files/interfaces: Narrative scene model and service, generation service.
- Work: Persist optional scene overrides, expose inherited/effective values, resolve target then scene then Config, validate model identifiers.
- Acceptance: Scene and target detail expose effective values, and jobs record the resolved scene choice.
- Validation: Static inspection and approved E2E suite when authorized.
- Status: complete.

### WP2 — Scene page controls
- Dependencies: WP1.
- Files/interfaces: `narrative.js` and existing shared picker.
- Work: Add scene-level Interview and Prompt writing controls, inherited-model clearing, and an accurate image-renderer header. Remove duplicate interview control.
- Acceptance: Choices save and reload on a scene, and target jobs use them absent target overrides.
- Validation: Browser workflow and JavaScript syntax check.
- Status: complete.

### WP3 — Documentation and final review
- Dependencies: WP1, WP2.
- Files/interfaces: Narrative, Data Model and LLM Roles docs.
- Work: Document precedence and compatibility; review changes and whitespace.
- Acceptance: Docs describe the implemented behavior and no unrelated files change.
- Validation: `git diff --check`.
- Status: complete.

## Validation
`node --check zet/web/static/narrative.js` passed. `git diff --check` passed. The approved E2E suite and prepared-response browser workflow were not run, so model precedence and interactive picker behavior remain unverified end to end. Live inference was not run.

## Risks and alternatives
Scene overrides inherit dynamically, so changing one affects existing targets that have no explicit target override. Existing model fields remain additive and require no migration.

## Progress and decisions
Scene-level scope selected. Additive fields need no migration. Scene overrides resolve between target overrides and Config role defaults. User-directed implementation is complete; E2E validation remains outstanding.

## Final results
Scene model fields, effective resolution, generation inheritance, scene-page controls and documentation are implemented. Static JavaScript syntax and whitespace checks passed. The approved E2E workflow remains unverified.
