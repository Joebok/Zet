# Codex Task: Zet Milestone 1 — Static Schema Only

You are implementing Milestone 1 of the Zet project.

Read these planning documents first:

- `Docs/Zet.md`
- `Docs/Zet_Data_Schema_Object_Model_Decisions.md`

## Scope

Implement only Milestone 1: Static Schema.

Do not implement Milestone 2 or later.

Do not create Python repositories, services, dataclasses, Streamlit dashboard files, worker scripts, AI manager scripts, or state-transition logic.

This milestone is only about creating the initial static file/folder structure and seed schema files.

## Required Project Structure

Create or update the following structure:

```text
config.toml

_Lib/
  Characters/
    Tsaeytte/
      Adult/
        Assets.json
        Pipelines.json

  Assets/
    Tsaeytte/
      Adult/

  Pipelines/
    Tsaeytte/
      Adult/

  AI_Queue/

  Required config.toml

Create config.toml at the project root:

[BaseFolders]
BaseCharacterPath = "_Lib/Characters/"
BaseAssetPath = "_Lib/Assets/"
BasePipelinePath = "_Lib/Pipelines/"
BaseAIQueuePath = "_Lib/AI_Queue/"
Required Assets.json

Create _Lib/Characters/Tsaeytte/Adult/Assets.json.

Use JSON.

Use snake_case field names.

Every asset must have a stable asset_id.

Include schema_version and next_asset_id.

Create a small set of fake seed assets sufficient to test the schema. Use these records:

Asset 1:
character: Tsaeytte
phase: Adult
pipeline: Body-Reference
body_view: Front
head_view: null
costume: null
expression: null
asset_state: NEW
pipeline_stage: MANIFEST
actor: PYTHON
ai_state: null
final_image_output: Body-Reference_Front.png
Asset 2:
character: Tsaeytte
phase: Adult
pipeline: Body-Reference
body_view: Front-Left-3-4
head_view: null
costume: null
expression: null
asset_state: NEW
pipeline_stage: MANIFEST
actor: PYTHON
ai_state: null
final_image_output: Body-Reference_Front-Left-3-4.png
Asset 3:
character: Tsaeytte
phase: Adult
pipeline: Head-Fitment
body_view: Front
head_view: Front
costume: null
expression: null
asset_state: NEW
pipeline_stage: MANIFEST
actor: PYTHON
ai_state: null
final_image_output: Head-Fitment_Front_Front.png
Asset 4:
character: Tsaeytte
phase: Adult
pipeline: Character-Assembly
body_view: Front
head_view: Front
costume: Default-Adventuring
expression: null
asset_state: NEW
pipeline_stage: MANIFEST
actor: PYTHON
ai_state: null
final_image_output: Character-Assembly_Front_Front_Default-Adventuring.png

Each asset should also include:

"last_ai_update": null,
"error_code": null,
"error_message": null,
"updated_at": null
Required Pipelines.json

Create _Lib/Characters/Tsaeytte/Adult/Pipelines.json.

Use JSON.

Include schema_version.

Define these pipelines:

Body-Reference
Head-Fitment
Character-Assembly

For each pipeline, define:

stages
actor_by_stage
worker_by_stage

Use this default stage sequence unless the planning docs clearly require otherwise:

[
  "MANIFEST",
  "PROMPT",
  "PROMPT_REVIEW",
  "RENDER",
  "RENDER_REVIEW"
]

Use these actors:

{
  "MANIFEST": "PYTHON",
  "PROMPT": "PYTHON",
  "PROMPT_REVIEW": "HUMAN_AGENT",
  "RENDER": "AI_AGENT",
  "RENDER_REVIEW": "HUMAN_AGENT"
}

For worker_by_stage, use placeholder module-style names only. Do not create the worker files.

Example:

{
  "MANIFEST": "workers.body_reference_manifest",
  "PROMPT": "workers.body_reference_prompt",
  "RENDER": "workers.body_reference_render"
}
Pipeline Working Paths

Create empty working folders for each seed asset using the decided path format:

_Lib/Pipelines/{Character}/{Phase}/{Pipeline}/{BodyView}/{HeadView or _}/Asset_{AssetID}/

For assets where head_view is null, use _.

Examples:

_Lib/Pipelines/Tsaeytte/Adult/Body-Reference/Front/_/Asset_1/
_Lib/Pipelines/Tsaeytte/Adult/Head-Fitment/Front/Front/Asset_3/
Validation Checklist

After implementation, verify:

config.toml exists.
_Lib/Characters/Tsaeytte/Adult/Assets.json exists.
_Lib/Characters/Tsaeytte/Adult/Pipelines.json exists.
_Lib/Assets/Tsaeytte/Adult/ exists.
_Lib/Pipelines/Tsaeytte/Adult/ exists.
_Lib/AI_Queue/ exists.
Assets.json is valid JSON.
Pipelines.json is valid JSON.
every asset has an integer asset_id.
next_asset_id is greater than all existing asset_id values.
every seed asset has a corresponding Asset_{AssetID} pipeline working folder.
no Python implementation files are created for this milestone unless needed only for validation.
