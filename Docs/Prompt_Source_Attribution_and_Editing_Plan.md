# Prompt Source Attribution and Editing Plan

## Goal

Prompt Review should make it easy to answer: "Where did this line come from?"

The review page should eventually show source indicators beside prompt text and allow the reviewer to open the correct editor for the originating text. The editor target may be a static prompt template, character/phase template section, shared template section, view instruction, race rule, or generated metadata value.

## Current State

The compiler currently produces:

- `Final_Image_Prompt.md`
- `Compiled_Sections.md`
- `dependency_manifest.json`
- review marker files such as `Prompt_Review.md` or `Image_Review.md`

`Compiled_Sections.md` records which logical sections were included, but it does not record where those sections came from. The compiler loads section text into a plain `dict[str, str]`, so source path, marker range, fallback path, and replacement location are lost before final rendering.

Prompt templates also insert non-section placeholders such as:

- `{{BODY_VIEW_INSTRUCTION}}`
- `{{HEAD_VIEW_INSTRUCTION}}`
- `{{CANONICAL_ART_STYLE}}`
- `{{TECHNICAL_MODESTY_LAYER}}`

These values may come from config JSON, template metadata fields, shared template sections, character template sections, or compiler-generated data.

## Source Categories

The attribution model should support these source kinds:

- `static_prompt_template`
  - Example: `Config/Prompt_Templates/character_assembly_v1.md`
  - Covers fixed text written directly in the task prompt template.

- `character_template_section`
  - Example: `_Lib/Characters/Tsaeytte/Adult/Character_Image_Template.md`
  - Covers `<!-- ZET:BEGIN SECTION -->` blocks in the character/phase template.

- `shared_template_section`
  - Example: `_Lib/Characters/_Shared/Character_Template.md`
  - Covers fallback/shared sections such as `TECHNICAL_MODESTY_LAYER`.

- `config_view_instruction`
  - Example: `Config/Prompt_View_Text.json`
  - Covers task-specific body/head view instructions.

- `config_rule`
  - Example: `Config/Race_Render_Rules.json`
  - Covers race-specific positive/negative rules.

- `template_metadata_field`
  - Example: `Canonical Art Style: [...]`
  - Covers scalar fields read from a character/phase template.

- `runtime_generated`
  - Covers compiler-generated values such as asset id, character name, phase, output file names, and reference manifests.

## Compiler Changes

### 1. Preserve Section Origins

Replace or supplement `load_template_sections()` with a source-aware loader.

Suggested model:

```python
@dataclass
class SourceSpan:
    source_kind: str
    path: str
    label: str
    section_name: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    json_pointer: str | None = None
    editable: bool = True

@dataclass
class CompiledFragment:
    text: str
    source: SourceSpan
```

The old section dictionary can remain as a compatibility view, but the compiler should also carry `section_name -> CompiledFragment`.

### 2. Record Placeholder Expansions

`render_static_prompt()` should render into a sequence of fragments, not only one final string. Each fragment should know:

- final prompt start/end line
- final prompt start/end character offset if practical
- source kind
- source path or config path
- source section, metadata key, or JSON pointer
- placeholder that caused insertion, where applicable

Static text from the prompt template should also be represented as fragments with source kind `static_prompt_template`.

### 3. Write a Source Map

Each compile should write:

`Prompt_Source_Map.json`

Suggested shape:

```json
{
  "schema_version": 1,
  "asset_id": 18,
  "task": "character-assembly",
  "final_prompt": "Final_Image_Prompt.md",
  "fragments": [
    {
      "fragment_id": "f0001",
      "prompt_start_line": 1,
      "prompt_end_line": 12,
      "source_kind": "static_prompt_template",
      "source_path": "Config/Prompt_Templates/character_assembly_v1.md",
      "source_label": "Character Assembly prompt template",
      "editable": true
    }
  ]
}
```

Line-level attribution is enough for the first version. Character offsets can be added later if needed.

### 4. Keep `Compiled_Sections.md`

`Compiled_Sections.md` remains useful for human inspection, but it should not be the primary source map. The JSON source map should be the machine-readable artifact.

## Prompt Review UI Plan

### Implementation Status

- Milestone 1 is implemented: Prompt Review shows source badges beside nonblank prompt lines.
- Milestone 2 is implemented: clicking a badge opens the Source Inspector with source metadata and selected line text.
- Milestone 3 is implemented: editable sources route to the Source Editor for markdown sections, full markdown files, and JSON fields.
- Milestone 4 is implemented: source saves are recorded in `Logs/Source_Edits.jsonl`, and the Source Editor offers an explicit recompile action without advancing the asset. Clearing condensed prompts and local test renders is available and checked by default.
- Milestone 5 is implemented as a first pass: after recompiling, the dashboard shows a before/after prompt diff with changed lines highlighted and source labels displayed.

### Milestone 1: Read-Only Attribution

Add source badges or gutters beside the prompt text:

- `template`
- `character section`
- `shared section`
- `view config`
- `race config`
- `metadata`
- `generated`

Hover or click should show:

- source label
- file path
- section name or JSON key
- source line range where known

This can be implemented before full editing.

### Milestone 2: Source Inspector Panel

Clicking a prompt line should open a side panel with:

- the source category
- source path
- section/key name
- exact source text where practical
- "Open editor" action if editable

The prompt text should remain read-only on Prompt Review.

### Milestone 3: Editor Routing

Create a unified editor route:

`/edit-source?kind=...&path=...&section=...&json_pointer=...`

Initial editor targets:

- ZET-marked markdown sections
- static prompt templates
- `Prompt_View_Text.json` body/head instruction strings
- `Race_Render_Rules.json` rule strings/lists

The existing template editor can be reused for ZET-marked markdown sections, but it needs to support:

- character template sections
- shared template sections
- task prompt templates
- config JSON fields

### Milestone 4: Safe Save and Recompile

After saving a source edit:

- record the edit
- offer "Recompile this prompt"
- do not automatically advance the asset
- preserve existing review/render artifacts until the user explicitly regenerates or recompiles

### Milestone 5: Diff Support

Prompt Review should show:

- old compiled prompt
- recompiled prompt
- highlighted source fragments that changed

This makes template edits less scary.

## Editing Scope

The editor should distinguish source types:

- Markdown section editor for `<!-- ZET:BEGIN ... -->` blocks
- Plain markdown editor for task prompt templates
- JSON field editor for config-backed text values
- List editor for config-backed arrays such as race positive/negative rules

Do not force all text into the current template editor shape. The current editor is a starting point, not the final abstraction.

## Important Decisions

- Prompt text shown in Prompt Review remains compiled output, not directly editable.
- Source edits happen at the origin file/field.
- Source map generation belongs in the compiler layer, not the UI.
- Line-level attribution is good enough for the first implementation.
- The source map should include non-editable/generated fragments so the UI can explain why no editor is available.

## Open Questions

- Should source maps include character offsets, or only line ranges?
Line ranges is fine. Most are lines anyway, and if it becomes and issue I would rather edit the templates to keep things on their own lines.

- Should edits save immediately to source files, or create draft patches for review?
Save immediately especially with milestones 4 and 5. We are not in a production environment where the stakes are high.

- Should source edits automatically invalidate previous render candidates?
This should be an option when saving.

- Should Prompt Review show attribution always, or as a toggle to avoid visual noise?
Always show - this is a tuning step to get the prompts coming out right. Once that is done, I expect pipelines to skip this step and go right to render.

- Should shared template edits warn that they affect multiple characters/phases?
Yes, should be immediately obvious with a warning banner at the top!
