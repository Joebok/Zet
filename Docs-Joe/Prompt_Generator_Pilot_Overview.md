# Prompt Generator Pilot — Overview for Review

## Idea

Give Zet a repeatable way to develop image prompts with LLMs and a human, while retaining deterministic control over source facts, reference images, render inputs, and publication. The immediate example is Tsaeytte's costume, but the pilot should test a workflow that can also serve character and Narrative Scene work.

The compiler would **marshal a prompt packet**: the target view or scene intent, authored facts, universe style, current source versions, ordered reference images with explicit roles, relevant prior images, and human decisions. A prompt generator, called through AI_Proxy, would inspect that packet and draft the final instruction sent to the image model. Zet would validate the draft's reference citations, required constraints, and binding to the packet before allowing a render. The compiler would remain the authority for what information and images are supplied; the LLM would author the render prose.

## Working loop

1. **Prepare:** Zet freezes a prompt packet and makes the supplied facts, images, and their roles visible to the human and prompt generator. Images the generator sees for analysis are distinguished from images that the renderer will receive.
2. **Draft and render:** The generator writes a target-specific prompt. The human can edit or approve it. Zet validates the prompt, then freezes its text, references, model settings, and source versions with each render attempt.
3. **Review and refine:** The human judges the resulting image against concrete visual criteria. The generator can propose another prompt, a different reference strategy, or an image edit. The human chooses the next trial; failed and successful attempts remain comparable.
4. **Capture durable decisions:** A trial can propose changes to a costume, character, scene, or shared template, but those changes are reviewed separately from accepting one render prompt. When an image is published, its exact accepted prompt and input manifest are locked with it. Later source edits do not rewrite that record.

This is a shared **process**, not necessarily one universal prompt or one model for every pipeline. Image Generation, Costume views, Head-Image Edit, and Narrative Scenes would each provide their own facts, image roles, and acceptance criteria to the same authoring and provenance loop.

## Why pilot it

The [Tsaeytte costume trial](../plans/active/tsaeytte-costume-fix.md) used all 36 authorized diagnostic renders. An LLM rewrite improved the rear-quarter angle, but repeated prompt-only changes did not reliably extend the rear hem. A corrected visual edit canvas produced a rear-quarter result Joe accepted; BACK remained close but did not cover the boot cuffs as requested. The trial suggests prompt authoring can be automated, while image selection and refinement must remain first-class choices. The private [comparison and evidence](../test-results/tsaeytte-costume-evidence/improvement/evidence.md) record those limits; they do not establish that one generator recipe generalizes.

Zet already has parts of the loop. Local character batches support reviewed source revisions and frozen candidate render inputs; selected images support guided refinement. [Head-Image Edit](../Docs/COMPONENTS/LOCAL_CHARACTERS.md#independent-head-image-edit-2026-10-22) adds explicit edit operations and scoped image guides. [Narrative Scenes](../Docs/COMPONENTS/NARRATIVE.md) use an interview, model-written prompt, editable render text, and saved job provenance. The pilot would connect these patterns and test where their contracts can genuinely be shared.

## LLM Usage

Establish a heirarchy of LLM models, escalation and delegation criteria & processes. At least 2 tiers - local LLM and Codex. Within Codex, there is a natural escalation between models. 

- The codex calls need to be usage-aware and guard against burning credits. 
- A determination of the "best" local LLMs that can run on this system needs to be determined. A means to calibrate and compare local models vs Codex Luna will need to be a side project to determine what can be done locally without a compromise of quality.
- In addition to the Qwen Image 2.1 skill, we should consider creating Zet specific skills, likely targeted at specific pipelines.

## Pilot boundary and questions

Start with one costume view and its human review loop, then try the same process on a second costume and one Head-Image Edit or Narrative Scene task. Judge the pilot by whether people can reach an accepted image with less manual prompt surgery, trace why it was rendered that way, and reuse durable decisions without altering earlier locked work. Preserve Zet's current universe isolation, ordered image bindings, source review, and explicit selection and publication steps.

Questions for the implementation plan:

- What common prompt-packet fields are useful across workflows, and which remain pipeline-specific?

  - The existing templates and compilers already do this to some extent.

- Which analysis images can the generator inspect, and how does Zet prevent citations to images absent from the render request?

  - There should be no guards against providing images, nothing is forbidden. What images are referenced (either for generation or just to the LLM for prompt-writing) will be encoded in the template. Either fixed inventory tags which the compiler than already handle, but we will also need a way to refer to images in the current batch (current locked/selected front image) for example, and also the locked images from other pipelines. These type of things should be unambiguous and so if not available, there is a message and the job can't proceed. This should only be enforced at run time - if an image is created with a reference that was locked at the time, but subsequently that pipeline/view image was unlocked or changed, it should have no effect on the dependent image. We do not need to enforce durable referential integrity.

- When does feedback change only the current prompt, versus an authored source or shared template?

  - This will likely depend on follow-up refinements - decisions will need to be documented in the templates in addition to the final prompt.

- What exact prompt, model, reference, and source provenance should accompany a published image?

  - As above, durable referential integrity is not to be enforced. We also don't want to make excessive copies of reference images. While a pipeline is running, it is helpful to have information to diagnose and try to fix things.

- How will the pilot measure iteration cost and visual acceptance without making the LLM's own judgment the acceptance gate?

  - Perhaps the refinement process for the prompts can also be used as a refinement of acceptance criteria.
