# Image Production Abstraction

Use the Narrative Subscene page as the interaction model for producing an image in Zet. The operator prepares a prompt, optionally attaches reference images, generates candidates, compares them, selects one and locks the result. Narrative, Character Pipelines and Minor Characters can share this workflow while retaining their own authoring tools and ways of organizing outputs.

## Three levels

| Level | Responsibility | Narrative | Character Pipelines | Minor Characters |
| --- | --- | --- | --- | --- |
| **Asset Container** | Groups related Assets and supplies shared settings, context and navigation. | Story | One workspace per universe, character, phase and pipeline type. Costume Dressing has one workspace per costume within that scope. | One named minor-character workspace in a universe. |
| **Asset** | Defines the intended deliverable and owns its authoring inputs, source choices and output use. | Scene, whose deliverable is the final scene image. | A view within the pipeline, such as Front or Front Left 3/4. | An official view within the workspace. |
| **Candidate Board** | Holds the working candidates for one image target. Supports generation, comparison, selection and locking. | One board per image target within the scene. A subscene is the model for the interaction. Backdrops and final assembly are separate targets with their own boards. | One board for the view. | One board for each official view, plus a board for the workspace's private Style alignment target. |

An **Asset** describes the desired output before any image exists. A **candidate** is a render option on a board. A **locked image** is the approved result for that target. An **Image Asset** is the durable image published to Image Inventory. A selected image can serve as a reference within its own workspace before locking or publication. For example, a selected subscene can feed assembly within its story, and a selected Minor Character Style image can guide the official views.

A scene can have several intermediate image targets and one deliverable. A Body Reference view has one target whose locked image is the deliverable. Each board serves one target and holds at most one selection and one lock. When a lock exists, both point to the same candidate. The candidate workflow needs only the identity and scope of its owning target. It can work with each pipeline's existing domain vocabulary and containment model.

## The handoff from authoring to rendering

The Asset and its pipeline own the brief, templates, prompt compiler or LLM call, and the choice of references. Narrative can use story context, scene interviews, layer placement or a prepared composite. Body Reference can compile the character master for a specific view. Minor Characters can prepare an alignment prompt from a selected Style image or write a true-up from the candidate under review. These inputs and controls stay with their respective authoring workflows.

The shared workflow starts when the pipeline hands it a render request for a target. The request contains the exact prompt to send, zero or more ordered image inputs, and the effective render settings, such as profile, quality, output dimensions and seed. The request identifies the owning universe, target and candidate. Capture the actual input images and their order at submission so the prompt's image bindings, reference previews and retries all describe the same request. A pipeline can attach readable provenance such as source roles or template names for review.

Editing a prompt, changing a source or accepting a refinement prepares a new request. It leaves existing candidates and their captured inputs intact. **Retry** a failed render with its frozen request and seed. **Generate again** creates a new candidate and can use a fresh seed. If the operator wants to reuse a previous recipe or edit an existing image, the pipeline prepares that new request explicitly.

## The shared operator workflow

1. **Generate.** From the target page, choose the render settings and request one or more candidates. Every board offers eight slots. The operator can use as many or as few as needed, up to the available capacity. New candidates fill open positions. Occupied slots stay bound to their candidates until explicitly cleared or replaced. Pending and failed renders stay visible in their own slots with progress or a relevant recovery action.
2. **Review.** Use the same cards and review controls to inspect the image, compare candidates or references, and read the submitted prompt and inputs. A pipeline may provide ranking, feedback or suggested edits. Advice can affect display order while physical slot bindings stay fixed. The operator can judge an available image while advice is pending, missing or failed.
3. **Select.** Choose one working candidate for the target. Selection can support composition or a new refinement. The operator can preview alternatives while a lock is active. To select a different candidate, unlock the current image first.
4. **Lock.** Locking selects and approves the chosen candidate in the same action and preserves its image and exact generation prompt. Unlocking removes approval and leaves the image selected. To lock a different candidate, unlock the current image first. Where approval also publishes to Inventory, report success only when the lock and publication are recorded consistently. Where publication is a separate action, show it separately and let the pipeline decide the destination and metadata.
5. **Continue.** Add alternatives or generate a refinement on the same board. If space runs out, clear or replace specific slots. Clearing a slot deletes the candidate and all data it owns, including the image, prompt, captured inputs and review data. Replacing a candidate deletes the previous candidate in the same way. Published Inventory images and inputs already captured by other render requests are independent records. For any bulk destructive action, preview every affected selection and lock, require explicit approval for each, and recheck those effects before applying the action.

Use the same action names, status indicators, prompt and reference inspection, and selected and locked markers across pipelines. Keep prompt editors, advice, finishing tools and any continuation controls close to the target that uses them. Narrative scene-text finishing and Minor Character alignment-to-true-up are examples of domain-specific work around the common board. Refresh visible progress while work is active and refresh settled detail on entry, relevant actions, tab return or explicit request.

## References and publication

For reference eligibility, the workspace boundary is the Asset Container. Zet exposes unselected, unlocked candidates only inside their own workspace. Within a workspace, a selected image is sufficient for use as a reference. Across workspaces, a workspace output must be both locked and published to Image Inventory. For example, assembly can use a selected subscene from the same story. Using a Body Reference view in a separate Costume Dressing workspace requires a locked, published output. Evaluate eligibility when preparing a new request. Existing requests and retries use their captured inputs.

Draft and Final candidates share one board and are equally eligible for selection and locking. The same reference rule applies to both qualities. A lock approves the workspace output, and publication makes it available for use outside that workspace.

## Character Pipelines without batches

Body Reference for a given character and phase is one ongoing workspace. Each costume has its own Costume Dressing workspace for that character and phase, with its own views and boards. Opening a workspace goes directly to its views. The operator can generate more candidates or refine a selected image on the same view board as the governing masters evolve. A multi-view command, if retained, submits work to the existing boards for those views. Generation requests can still group renders for dispatch and recovery. They carry no separate operator-facing lifecycle, board, selection or lock.

The character batch picker, new-batch workflow and Activity list retire from this design. Show preparation and render status at the affected view, with a compact workspace summary when useful. Keep recoverable work and actionable errors on the affected board. The board keeps the submitted prompt with each current candidate. Approved outputs carry their own prompt. The operator chooses how many images to generate each time, within the open slots on the board.

## Integrity boundary

Keep the checks needed for safe execution and publication. Before submitting, confirm target ownership and that the requested inputs can be captured and bound in order. Accept a result only for its universe, candidate, slot and current attempt, using the existing queue and harvest protections. Before selection or locking, confirm current membership, image availability and protection of existing locks. Preserve publication integrity where Inventory is involved.

A completed candidate stands on its captured production record. The common workflow adds no cross-pipeline dependency graph, template or source freshness gate, mandatory automated review, or historical reference revalidation. If an observed source difference is already known, show it as a persistent FYI on the affected image. Resolve dependencies for the action that needs them. Existing batch or stage admission checks stay out of the shared board contract. For example, a new Minor Character view render may need a Style image, and a new Dressing render may need a suitable character source. A later source edit does not reopen review of an already rendered image or block selection or locking. [Finished-image source policy](../Docs/DECISIONS/0045-finished-image-source-policy.md)

## Existing outputs

Only an existing Final-quality lock qualifies to become the initial lock on the corresponding new board. If there is no Final lock, the board starts unlocked. An adopted lock also becomes the board's selection. Previously published images retain their independent Inventory identity. This rule applies to the initial board state. The operator can lock either quality during normal use.

## Questions and considerations

- **Competing Final locks.** If several legacy batches have Final locks for the same view, should the most recent lock become current, or should the operator choose?

[Current Narrative workflow](../Docs/COMPONENTS/NARRATIVE.md) · [Narrative mixed-quality board](../Docs/DECISIONS/0046-narrative-mixed-quality-board.md) · [Current Character and Minor Character workflows](../Docs/COMPONENTS/LOCAL_CHARACTERS.md)
