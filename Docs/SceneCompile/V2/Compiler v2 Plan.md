# Scene Render Compiler v2 Plan

## Summary
Implement P0-P2: make Scene Builder JSON the canonical render source, compile it into a normalized scene IR, validate conflicts/placeholders, generate structured `Final_Image_Prompt.md`, and produce deterministic local-render artifacts from the same IR.

## Key Changes
- Add backend scene-render compiler code under `zet/services`, invoked by `StoryService.stage_scene_render()`.
- Read these inputs:
  - story markdown for title, art style, continuity, optional dialogue-panel style;
  - scene markdown for narrative intent, special render notes, local overrides, and existing reference tags;
  - scene builder JSON for canvas, camera, composition, environment, elements, placements, gaze, props/interactions/dialogue where present.
- Write new pipeline artifacts:
  - `Scene_Render_IR.json`
  - `Scene_Render_Validation.json`
  - `Final_Image_Prompt.md`
  - `Local_Render_Brief.json`
  - `Local_Render_Prompt.md`
  - expanded `Prompt_Source_Map.json`
  - existing `dependency_manifest.json`
- Keep `zet/web` unchanged except for continuing to call `ZetApp.stage_scene_render()`.

## Implementation Details
- Add a `PromptSceneIR` compiler that normalizes:
  - canvas/aspect/camera;
  - grid placement into screen-left/center/right composition;
  - characters, anchors, props, interactions, gaze targets, dialogue, references, avoid rules, and source lineage.
- Add validation before prompt writing:
  - placeholders like `(notes)` in required visual fields;
  - conflicting orientation/aspect/dimensions;
  - missing primary-character placements;
  - missing/invalid gaze or interaction targets;
  - dialogue requested while global no-text rules remain active;
  - local override syntax/type issues;
  - prop/hand consistency when structured fields exist.
- Treat errors as blocking; write warnings and auto-resolutions to `Scene_Render_Validation.json`.
- Replace source-concatenation prompt rendering with a structured ChatGPT formatter using the v2 section order from the analysis.
- Resolve reference roles explicitly:
  - character refs control identity/costume, not pose/layout;
  - location refs control architecture/design, not camera composition.
- Add a deterministic local formatter:
  - `Local_Render_Brief.json` contains protected facts, positive facts, negative facts;
  - `Local_Render_Prompt.md` uses `prompt:` / `negative:` lines;
  - dialogue/text excluded from local preview by default.
- Add `scene-preview-sd15` to `Config/Local_Render_Presets.json`.
- Update `stable_matrix_adapter.py` so render size is derived from exact aspect ratio when available, falling back to preset or orientation only when no ratio exists.
- Replace ad hoc colon parsing for local overrides with typed TOML/JSON-compatible parsing inside the existing managed section; omit empty values.

## Test Plan
- Unit-test IR compilation from `Docs/SceneCompile/Example/Chapter-04-A-Lending-Hand.json`.
- Snapshot-test generated `Final_Image_Prompt.md`, `Local_Render_Brief.json`, and `Local_Render_Prompt.md` against the v2 examples.
- Test validation catches:
  - placeholder fields;
  - portrait-vs-landscape conflict;
  - dialogue/no-text contradiction;
  - invalid gaze target;
  - empty `negative_prompt:denoising_strength:` style parse failure.
- Test `scene-preview-sd15` payload produces dimensions matching `16:9` within tolerance.
- Run existing scene render staging path and verify ask manifest still references `Final_Image_Prompt.md` and resolved reference files.

## Assumptions And Open Questions
- First milestone is P0-P2 only; layout/pose guide and ControlNet/img2img conditioning are out of scope.
- Existing Scene Builder schema will be consumed as-is; new optional fields can be recognized if present but no UI schema expansion is required in this milestone.
- If scene JSON and scene markdown conflict, JSON wins for visual staging; validation records the conflict.
- If dialogue text is present, ChatGPT prompt may include it; local preview excludes it by default.
- Question for later: should scene markdown eventually be generated from JSON, or remain a separate author-authored companion?
- Question for later: should validation warnings block render staging, or only validation errors?
