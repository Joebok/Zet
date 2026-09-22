# Qwen Character-Pipeline Experiment System

## Summary

Build this as an experimental capability inside Zet, using the existing Zet codebase and `Zet_Library` rather than creating a separate project that treats Zet as a remote API.

The experiment system should:

- Use the current pipeline data as its source of truth.
- Generate Qwen Image 2.1 candidates through ComfyUI.
- Continue supporting the existing manual ChatGPT method unchanged.
- Run both methods against the same structured character, view, costume, and semantic intent where the task is comparable, while allowing each branch to maintain its own visual-reference lineage.
- Analyze every generated image before it becomes reviewable.
- Preserve prompts, references, workflows, parameters, images, analyses, and human decisions as one comparison record.
- Keep all Qwen results exploratory in v1; they must not silently become canonical assets.

Qwen Image 2.1 is suitable for this because it combines text-to-image and image-conditioned editing, supports multiple reference images, and has official ComfyUI workflows. Zet already contains a Qwen 2.1 ComfyUI profile and compiler foundation, but that profile currently targets scene previews rather than character-pipeline experiments. [Qwen Image 2.1](https://github.com/QwenLM/Qwen-Image-2.1), [official ComfyUI workflow template](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_qwen_image_2_1_image_edit.json)

## Recommended system boundary

Do not begin with a separate project.

Instead, add a Zet-backed “Character Pipeline Experiments” subsystem that reuses:

- Zet’s character, phase, costume, view, and asset resolution.
- Existing deterministic prompt compilation and source maps.
- Existing ComfyUI backend dispatch and workflow registry.
- Existing AI Proxy queue and harvesting conventions.
- Existing image-review and analysis infrastructure where applicable.

The experiment subsystem should sit beside the canonical asset pipeline, not inside its state machine. Zet remains the authority for what the character and pipeline stage mean; ComfyUI is only an execution engine.

The structured Zet data is the shared semantic source of truth. The Qwen branch has a separate visual source of truth: an accepted sequence of Qwen-generated identity anchors. Existing ChatGPT assets and outputs may provide production context and comparison evidence, but they must not become upstream visual identity references for the Qwen branch.

A separate project becomes justified later if the system evolves into a general-purpose model benchmark laboratory, needs independent scheduling, or must operate against many repositories.

## Storage model

Keep canonical files in their existing locations:

- `Zet_Library/Assets` — approved, reusable character assets.
- `Zet_Library/Pipelines` — current stage work, prompts, reviews, and render artifacts.
- `Zet_Library/ImageCatalog` — reusable imported/reference images.

Add a separate experimental area, preferably:

```text
Zet_Library/
└── Experiments/
    └── Character-Pipeline/
        └── <character>/<phase>/<pipeline>/<view>/<experiment-id>/
```

Each experiment should contain a durable comparison record with:

- source asset IDs and source-image hashes;
- character, phase, pipeline, view, head view, costume, and stage;
- semantic prompt intent;
- manual ChatGPT prompt projection;
- Qwen/ComfyUI prompt projection;
- branch-specific reference manifests and ordering;
- Qwen lineage metadata: parent Qwen candidate, active Qwen anchor, stage, anchor status, and rejected-anchor history;
- model, workflow, checkpoint, seed, dimensions, and generation parameters;
- candidate images from each method;
- AI analysis results for every image;
- human review notes and comparison decisions;
- prompt version and refinement history.

Do not create alternate canonical filenames inside `Assets`. Do not use names such as `Character_Qwen.png` as if they were approved assets. Experiment candidates should remain explicitly non-canonical.

The experiment record may point to existing canonical images rather than duplicating them. Generated candidates should be copied into the experiment folder so the experiment remains reproducible even if later pipeline assets change.

## Prompt architecture

Use one shared semantic intent with two engine-specific projections.

### Shared intent

This represents the actual desired transformation:

- subject identity;
- body and head view;
- pose and framing locks;
- fitment clothing or costume facts;
- required changes;
- preserved elements;
- forbidden drift;
- reference roles;
- evaluation criteria.

### Manual ChatGPT projection

Compile the intent into the existing `Final_Image_Prompt.md` style, optimized for a human ChatGPT workflow and its image attachments.

### Qwen/ComfyUI projection

Compile the same intent into a concise image-editing instruction plus structured reference bindings. It should explicitly identify:

- which accepted Qwen image is the active identity anchor;
- which Qwen image is the immediate stage input, if different from the active identity anchor;
- which optional image is a costume or other task reference;
- what changes;
- what must remain unchanged;
- desired output view and framing.

The manual and Qwen branches do not need identical rendered-image references or identical raw prompts. Comparison should happen at both levels:

1. semantic intent versus semantic intent;
2. manual projection versus Qwen projection.

This avoids forcing ChatGPT-oriented prose, negative-prompt conventions, or SD-specific syntax into Qwen jobs.

An existing ChatGPT-rendered image may be shown for comparison, but it is not a Qwen identity reference. Once the Qwen branch begins, Qwen visual continuity is evaluated and preserved through Qwen-generated anchors.

## Stage strategy

Proceed through each Pipeline Stage in turn.

- Body-Reference
- Head-Image
- Character-Assembly
- Costume-Dressing

The Qwen branch is serial. Its first identity is established through text-first generation, and each later stage derives from an accepted Qwen anchor:

1. Generate the initial Body-Reference identity from structured data without rendered-image references.
2. Run AI analysis and human review, then select an accepted Qwen body anchor.
3. Generate Head-Image from the accepted Qwen body anchor and structured identity facts.
4. Run analysis and review, then establish the accepted Qwen head/identity anchor.
5. Generate Character-Assembly from the accepted Qwen body/head lineage.
6. Generate Costume-Dressing from the accepted Qwen assembly anchor and structured costume facts.

A candidate must not become a Qwen identity reference until it has passed AI analysis and has been explicitly selected by a human. A failed, uncertain, or merely generated candidate remains an experiment result and cannot silently become the input to the next Qwen stage.

The manual ChatGPT branch may run alongside these stages for comparison, but it does not drive Qwen identity continuity. The branches share structured facts and evaluation intent, not visual identity inputs.

Since Qwen Image 2.1 prefers natural-language instructions rather than diffusion-style comma-separated lists, the existing prompt compilation is a useful semantic starting point, but each stage should have its own Qwen-oriented prompt projection and ComfyUI workflow. Casual Body-Reference testing with a Qwen Image 2.1 text-to-image workflow has produced useful results; this experiment is intended to shape the stage-specific prompts and workflows around Qwen self-consistency.

We should anticipate a dedicated ComfyUI workflow and Prompt compiler for each pipeline stage. Part of this experiment is to shape these items for best results.

## Mandatory AI analysis gate

Every generated candidate must pass an AI-analysis job before it is marked reviewable.

The analysis should produce:

- structured pass/fail/uncertain results;
- per-criterion findings;
- confidence;
- detected error categories;
- a concise human-readable report;
- model, prompt, reference, and image hashes.

The rubric should be stage-specific. For costume dressing, for example:

- identity continuity against the active Qwen anchor;
- facial structure preserved;
- hair and ears preserved;
- apparent age preserved;
- body proportions preserved;
- distinctive markings preserved;
- Qwen rendering identity preserved;
- correct body and head view;
- pose and framing preserved;
- fitment clothing removed;
- costume components present;
- left/right equipment placement correct;
- full body visible;
- no extra props or narrative drift.

For every Qwen candidate, analysis must compare the candidate with the active Qwen anchor or immediate Qwen stage input. It should report stable traits, changed traits, uncertain traits, and whether the change is permitted by the stage intent. View and pose continuity are included when the stage requires them.

AI analysis should be a measurement and triage layer, not the final approval authority. A failed or uncertain analysis should keep the candidate pending and optionally recommend regeneration. Human review remains required.

## Side-by-side comparison experience

Introduce a dedicated experiment comparison view rather than overloading the existing asset review page.

The comparison should show, for one experiment, the Qwen lineage as the primary view and the manual result as a secondary comparison column:

| Area | Manual ChatGPT | Qwen / ComfyUI |
|---|---|---|
| Candidate image | comparison image and variants | current candidate, active Qwen anchor, and prior lineage images |
| Prompt | rendered manual prompt | Qwen instruction/projection |
| References | manual attachment order | Qwen anchor and ComfyUI reference bindings |
| Parameters | manual workflow metadata | workflow, checkpoint, seed, settings |
| AI analysis | task-criterion results | identity-continuity and task-criterion results |
| Human notes | reviewer comments | reviewer comments and anchor decision |

The view should support:

- synchronized comparison by stage/view/costume;
- Qwen lineage inspection from bootstrap through Costume-Dressing;
- image zoom and side-by-side viewing;
- prompt diffing;
- reference-order inspection;
- analysis-result comparison;
- human labels such as “identity failure,” “costume failure,” “orientation failure,” or “usable basis”;
- selecting and explicitly locking a candidate as the next Qwen identity anchor;
- identifying the Qwen candidate used as the basis for prompt or workflow refinement.

The existing pipeline pages can expose a link to the experiment, but canonical promote/discard actions should remain separate until a future promotion design is approved.

## Refinement loop

The initial purpose is prompt, workflow, and comfyui settings research, not unattended production.

The loop should be:

1. Snapshot the current source data and prompt intent.
2. Generate the next Qwen candidate from the stable accepted Qwen anchor lineage.
3. Optionally generate a manual ChatGPT comparison candidate from its own manual workflow.
4. Analyze every image, with Qwen candidates evaluated against the active Qwen anchor.
5. Record human error labels, useful successes, and the anchor decision.
6. Revise only the relevant prompt template, workflow, or semantic constraint.
7. Rerun a new experiment version without replacing the prior Qwen anchor or deleting prior candidates.
8. Compare results against the prior version and Qwen lineage.

Each run must preserve its exact prompt, references, workflow, parameters, and analysis. Do not overwrite old candidates when refining prompts.

Seeds may be held constant within one engine and experiment, but should not be treated as visually equivalent across ChatGPT and Qwen. The comparison unit is the task intent and evidence bundle, not identical random noise.

Cross-engine identity equivalence is not the primary success criterion. The primary criterion is whether the Qwen branch maintains a stable character identity across its own sequential pipeline stages. Existing ChatGPT assets provide semantic and production context, but they do not define Qwen’s visual identity after the Qwen branch begins.

## Major architectural decision

The system should be:

```text
Zet source data
    ↓
Shared semantic prompt intent
    ├── Manual ChatGPT projection
    │       ↓
    │   Manual comparison candidate
    │       ↓
    │   Task analysis
    │
    └── Qwen/ComfyUI projection
            ↓
      Text-first Qwen Body-Reference
            ↓
       AI analysis + human anchor selection
            ↓
       Accepted Qwen identity anchor
            ↓
      Next Qwen pipeline stage
            ↓
       AI analysis + human anchor selection
            ↓
       Serial Qwen identity lineage
            ↓
       Prompt/workflow refinement record
```

The experimental system owns comparison history. Zet’s existing pipeline remains responsible for canonical assets and production progression.

## Deferred decisions for the later implementation plan

- Exact experiment JSON schemas and versioning.
- Whether one stage produces one candidate or a batch.
- Which AI-analysis model performs each rubric.
- Whether analyses are queued through the existing AI Proxy or run directly.
- Exact browser routes and dashboard placement.
- The exact Qwen anchor schema and whether each stage has one anchor or a small approved anchor set.
- Candidate scoring and acceptance thresholds.
- The UI for selecting and locking Qwen anchors.
- Prompt/workflow version branching.
- Whether a future reviewed Qwen candidate can be promoted into `Assets`.
- Whether selected experiment images should be imported into `ImageCatalog`.
- How prompt variants and Qwen lineage branches are named.

