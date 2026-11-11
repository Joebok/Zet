# Candidate Board UI specification

This is the design standard for Candidate Boards in the active Character Asset
Container pipelines, Narrative Scenes, Minor Characters, Image Generation, and future
image generation workflows.
It specifies the presentation and adapter contract for new integrations.
The [UI style guide](../UI_STYLE_GUIDE.md) governs shared tokens, glyphs,
control sizes, and feedback. The on-page board contains **Render Controls**
followed by the **candidate grid**. The **candidate review dialog** opens as a
separate modal outside both sections and the board's page-flow layout.
Each asset or target has one board with eight slots and one selection shared
by Draft and Final candidates. Image Generation follows the same standard
with Add to Image Inventory in the Lock position. Publication is available on each completed candidate and does not change the selection.

## 1. Render Controls

Use one labeled **Render Controls** container directly above the grid. Use the
same layout and responsive wrapping in every workflow. Keep generation available
beside the results, with the same prompt, render, review, and bulk-action groups.
On compact screens, prompt editing and advanced settings can collapse. Primary
render actions, availability reasons, and progress remain visible.

| Group | Shared presentation | What the asset provides |
| --- | --- | --- |
| Next render prompt | Prompt authoring or preview, with an expandable editor or preview and status | **Write Prompt** where it synthesizes a prompt, **Preview Prompt** where the pipeline compiles from current inputs, and an editor where the operator supplies text. Include **Save Prompt** when required. Preserve saved or unsaved drafts per workflow. |
| Render settings | Labeled settings and their save actions in the **Prompt and render settings** disclosure, above the action row. A workflow may place related fields in one responsive row. | Aspect ratio, effective dimensions where available, source readiness, and relevant recipe or input controls. Keep interviews, source management, and unrelated authoring outside the action row. |
| New renders | **Draft 1**, **Draft 4**, **Final 1**, **Final 4**. Use the existing blue Draft and green Final roles and retain visible text. | Supply readiness and disabled reasons. Each button reserves its stated count from the same pool of empty slots and sets the quality of the new candidates. |
| Board assessment | **Luna Review** and one **Review Status** line directly above **Review criteria** when criteria are available | Supply criteria, lifecycle status, and results for the current board. The control requests advice on existing candidates. |
| Bulk actions | Separate destructive group at the trailing edge on desktop and on its own wrapped row as needed. Keep labels such as **Delete Drafts** and **Delete Non-Selected** explicit. | Supply the exact supported operations, eligibility, preview and commit handlers. Name the affected board, slots and effects. |
| Feedback | A local status region beside the relevant group | Supply actionable prerequisite, pending, completion or failure messages. Prompt authoring, rendering, and Luna Review each have distinct status. |

Validate readiness before dispatch and use the named count. A **Draft 4** click
with three empty slots is disabled with a reason. It cannot silently submit three
or overwrite an occupied slot. Keep selected and locked protections specific to
the operation. Bulk actions use the existing confirmation flow, with previews
and individual approval of every affected selection or lock and a server-side
recheck before commit. Label any retained Inventory image in the confirmation. **Delete Drafts** previews
active Draft slots and cancels their owned attempts. Queued work is withdrawn and
late results are discarded. Backend execution already underway may finish. An
upscale remains associated with its Draft until the Final is committed. **Delete
Non-Selected** waits for affected renders to settle.

The shared status line starts at **Not started**, becomes **Started** when
Luna accepts the review, and shows **Finish** once the result is recorded.
**Outdated** adds “Ranking obsolete: candidate images changed” and marks
retained ranks and assessments as previous. **Failed** includes the error when
available. **Interrupted** represents an interrupted review. Render and bulk
action feedback stay separate from the Luna lifecycle.

## 2. Candidate image cards

Use one responsive, slot-ordered grid and one card template. Keep all eight
slots visible, including empty ones, and keep slot positions stable during
progress, review, ranking, and selection. Display the slot label, contained
image or stable placeholder, compact status, and one consistently ordered action
row. Use thumbnails when available and open the full review image. Give the
image an accessible button target so click, tap, Enter, and Space take the same
path as the **Review** eye glyph.

- Use the shared surface, border, spacing, typography, and focus styles. Fit the
  entire thumbnail inside the fixed 4:3 well without cropping or stretching.
  Leave space around images whose aspect ratio differs from the well. Show
  quality as a blue Draft or green Final pill, lifecycle status while pending or failed, and whole-second render time when
  recorded, and the applicable Selected, Locked,
  Luna rank, and source-change indicators. Completed images omit the completion label. Locked images show the shared closed-padlock glyph with accessible text. Earlier prompt is an informational pill when the workflow records a saved prompt difference. These facts can coexist. Use the
  saved status and timing for each candidate.
- Empty, pending, failed, and image-load-failed states have distinct
  placeholders or messages. Render failures keep applicable retry and
  inspection actions. Missing image bytes leave recorded details accessible
  where the adapter supports them. An advisory error leaves the image usable.
- Use shared glyphs for familiar actions. Use a stable order of Review,
  Select/Unselect, Lock/Unlock, render recovery or replacement, Download where
  supported, then Clear. Share the applicable subset and order in the review
  dialog. Distinguish **Retry** of a failed request, **Regen Draft/Final** with
  current inputs, and **Upscale Draft** using the completed Draft. Preserve
  policy-specific reasons when actions are disabled. Omit unsupported actions.
  Character and Minor Character boards show **Deselect** for the selected,
  unlocked image. A locked image offers **Unlock** and cannot be deselected.
- Keep prompt, ordered inputs, and long assessments in review. Card feedback
  names the action and remains near the initiating control. Use an accessible
  name and hover/focus label for glyphs, a visible keyboard focus indicator, and
  the style guide's compact desktop and 44 px touch targets. Keep visible
  labels for unfamiliar or consequential actions. Disabled card and review
  actions expose their reasons on hover and to assistive technology on focus.

## 3. Candidate review dialog

Use one viewport-anchored modal template in a separate dialog host outside the
board's Render Controls, grid, and forms. Its controller shares the board model
and action adapter so both surfaces stay synchronized. On desktop, images
occupy the main area and the control rail sits to the right. Keep the comparison
on the left and the candidate on the right. When the user chooses **No comparison**, the candidate
uses the entire image area. Use contained full-image wells and equivalent space
for each side. On narrow or short screens, reflow the images and rail with both
images accessible, a usable image area, and reachable decisions, navigation,
and Close. Use the same responsive rules across boards.

- **Header and navigation.** Show target/view and slot, position in the
  reviewable set, quality, status, and selection/lock state. Use the shared
  chevrons and Close glyph. Previous and Next follow slot order and stop at the
  ends. Left/Right arrows work outside inputs, selects, menus, and other
  controls that consume arrows. Candidate navigation is distinct from
  comparison navigation or an asset's view switch.
- **Decisions and actions.** Keep the common action row, supported asset
  actions, and local action feedback in consistent places. Show a human
  assessment control only where the workflow records one. Keep it distinct
  from selection, locking, and Luna advice. Show the candidate's recorded rank
  and assessment in review. Keep Luna status and criteria in Render Controls
  and action messages in their own feedback region.
- **Details.** Use one collapsed **Candidate prompt and ordered inputs**
  disclosure for the reviewed candidate. Show the exact saved prompt, copy
  control, negative prompt when recorded, and captured sources in binding
  order. Use descriptive link labels and the original prompt marker when
  available. Links open in a separate tab and display the captured image
  inline. Show applicable saved settings under **Render settings** with
  readable labels and values. Optional provenance can supply useful recorded
  context. A source-change notice is a persistent FYI about the finished image.
  The next render prompt remains in Render Controls. Review controls stay visible.
- **Focus and updates.** Open with meaningful focus and contain Tab in the
  dialog. Close and Escape use the same draft-safe path and restore the
  initiating card or nearest surviving control without jumping the gallery.
  Preserve the current candidate, comparison choice, zoom, disclosures, local
  scroll, and focus on same-candidate updates. When navigation would abandon
  unsaved decisions, settle them or offer a save/discard choice. Disable
  conflicting navigation or duplicate submissions while a mutation is pending.
  A removed candidate follows the next eligible slot or closes cleanly if
  none remain. A successful explicit replacement may follow its new candidate
  in the same slot.

### Comparison and zoom

Every board has the same **Compare with** control and a **No comparison**
choice. Always offer **Selected**, including when the current candidate is
selected. Narrative defaults to Selected. Character and Minor Characters use
their available preferred sources first and fall back to Selected. A default can
show the same image in both panes. When Selected has no available image, keep the
left well blank and the choice enabled. Label every additional option by role and add slot, view, quality,
or other context that distinguishes it.

The common chooser can retain multiple choices and display one at a time in
the left well. Make multiple selection operable by touch and keyboard without
modifier keys. When more than one is chosen, labeled comparison chevrons step
through them without changing the candidate. A valid explicit choice, including
**No comparison**, survives navigation within the board. If a chosen source
disappears or fails to load, keep the candidate visible and offer the remaining
options. The asset supplies the ordered additional options and any recommended
initial choice. An initial default must never override a deliberate choice.
Comparison changes do not affect selection, lock, or render inputs.

Use the same cursor-centered vertical wheel zoom on the candidate and the
comparison, from fitted size to **4×**. Both images share scale and normalized
focus, including when the gesture begins on the comparison. Wheel outside the
artwork, in letterbox space, with modifiers, or primarily horizontal keeps its
normal behavior. Consume the event only when image zoom applies. Provide shared
Zoom In, Zoom Out, and Reset controls for keyboard and touch access. Close or
a changed main candidate/image resets to fit. Changing the comparison alone
preserves zoom and applies it when the new image is ready. The shared dialog
owns attaching, synchronizing after image insertion or replacement, and
disposing the zoom behavior. One broken or loading image leaves the other
image's controls usable.

## 4. Shared component contract

Use the shared `mountCandidateBoard` component for Render Controls, cards, and
review. It uses scoped CSS and the dashboard's shared glyph and zoom helpers.
The page controller owns fetching, polling, request construction, and workflow
transitions. Pass normalized data and action handlers through the component API.
[Shared component](../../zet/web/static/candidate_board_component.js)

### Properties

| Property | Contract |
| --- | --- |
| `scope`, `revision` | Stable board key, display title, and optional view. Distinguish universe and owning asset/target, including phase or costume when applicable. Supply a revision or equivalent freshness token separately from the board key. |
| `slots` | Eight ordered slot records with stable slot keys and optional candidate records. A candidate has a stable ID independent of the slot, display status, quality, optional thumbnail and review image descriptors, and optional elapsed time, error, and notices. Image descriptors include a URL and label, with a version when the image bytes can change at the same URL. |
| `selectedId`, candidate review state | Current selection, optional lock state, and optional human assessment. Saved prompt, ordered inputs with optional prompt markers, saved render settings, and optional provenance belong to the candidate under review. |
| `lunaReview` | Optional advisory status, criteria, and error, with rankings and assessments keyed by candidate ID. Render Controls show one Review Status line above the criteria. Outdated results identify the ranking as obsolete and mark retained assessments as previous. |
| `renderControls` | Optional fields, readiness reasons, and prompt and render status. The component provides the four render shortcuts and calculates capacity from the slots. The adapter supplies workflow readiness. |
| `actions` | Board- and candidate-scoped descriptors with stable action key, placement, label, shared glyph key, semantic style role, and enabled/disabled state with reason. The component supplies slot generation and bulk-delete actions. Slots supply `renderActive` and `replacementBlock` for readiness. Supply remaining candidate actions once for both surfaces, with explicit placement for context-specific actions. |
| `comparisons`, `comparisonDefaults` | Ordered `{key, label, image}` descriptors and optional default keys. The component owns the stable `selected` key and deduplicates additional sources by image URL and version. Comparisons supply images and captions. The prompt, ordered inputs, saved settings, and provenance stay with the reviewed candidate when the comparison changes. |

### Methods and events

See the [subscriber guide](CANDIDATE_BOARD_INTEGRATION.md) for the JavaScript
model, action intents, and polling example.

| Interface | Behavior |
| --- | --- |
| `mountCandidateBoard({boardHost, dialogHost}, model, adapter)` | Render the initial model in the two hosts, attach handlers once, and return the board instance. |
| `update(model)` | Accept the complete current UI model for the board. Reconcile Render Controls, cards, and any open review in the same update. Keep existing elements by stable key where possible. A changed board key closes the old review and clears its local state. A new revision of the same board keeps the review open under the rules in Section 3. |
| `dispose()` | Remove component listeners and invalidate pending UI updates. The page controller stops its polling and discards outstanding responses when it leaves the board. |
| `openReview(candidateId, origin)` / `moveReview(direction)` / `closeReview()` | Shared review lifecycle. Apply candidate eligibility, draft guard, focus return, and navigation rules. Expose review-open, candidate-change, and review-close notifications for host integrations. |
| `setComparisons(keys)` / `resetZoom()` | Shared viewer state. Emit comparison changes for interested consumers. These are local presentation actions. |
| `onAction(intent)` | Async adapter callback for prompt, render, candidate, assessment, and bulk actions. Include the action key, board scope/freshness, origin surface, and applicable candidate ID, slot key, expected occupant, mode/count, or edited value. A board render has no candidate ID. A slot replacement carries its observed occupant. |
| Action outcome | The page controller applies authoritative action results through `update(model)`, the same entry point used for polling. The callback returns a structured success or error message and may suggest a review target after explicit replacement. The component displays errors immediately in the initiating surface. Any refresh on error follows the workflow's existing behavior. |

### Polling and updates

1. The page controller loads board detail, normalizes it, and mounts the
   component. The controller retains the latest board data.
2. While the board is visible and work is active, the controller polls compact
   progress. It merges changes such as slot status or Luna progress into the
   retained data and calls `board.update(model)` when the UI model changes.
   Before merging, the controller discards responses from a previous board
   or an older revision, and progress for a slot occupant that was replaced.
3. When a render or Luna Review settles, the controller refreshes board
   detail to get the new image, recorded render time, or final assessment.
   One refresh can resolve multiple changes from the same poll.
   It merges the result and calls `board.update(model)` again. For example,
   a queued slot can change to running on a progress update, then show its
   thumbnail and review image after the detail refresh while other slots
   keep running. The complete UI model is assembled in the browser from
   retained data.
4. The component applies the new model to all three surfaces. A Luna result
   can update a card's rank and the open review's assessment in one call.
   Changes to an unrelated slot preserve the open review, focus, zoom, and
   comparison choices. If the reviewed slot loses its candidate or receives
   new image bytes, the component follows the review navigation and zoom rules
   in Section 3.

The page uses this same update path for action results, manual refresh, and
returning to an idle board. Card and dialog elements are owned by the
component. The public events report user interactions such as opening a
review or choosing a comparison. Poll results enter through `update(model)`.

Use the normalized JavaScript interface and reuse compatible backend endpoints.
The adapter maps each
action to the real workflow and can intercept draft navigation, gather extra
input, or run protected-effect confirmation. Services remain authoritative for
membership, ownership, eligibility, attempt fencing, publication, and frozen
inputs. UI flags guide presentation. They cannot authorize a mutation.
Selection and locking of finished images follow the
[finished-image source policy](../DECISIONS/0045-finished-image-source-policy.md).

## 5. Workflow differences and source inventory

The following differences belong in adapter data, eligibility, or action
handlers. They share the board, card, and dialog layouts above.

| Workflow | Comparison options in addition to the selected candidate | Material differences to preserve |
| --- | --- | --- |
| Character Asset Containers | Other selected views, with FRONT or matching opposite view prioritized as applicable. An eligible locked Draft or a pipeline-specific source can be supplied with its own label. | Mixed-quality view boards. The page places Preview Prompt beside Refresh and compiles current masters and ordered inputs for the active view. View/phase, head-source and costume recipe settings vary by pipeline. Keep supported prepare/submit, select, lock/publication, retry, regen, upscale, clear, Luna, and template-improvement actions. |
| Narrative Scenes | The current review offers its selected image. Relevant captured backdrop, composite, or other target-specific evidence can be offered by the adapter when available. | Mixed-quality target boards. Write Prompt and manual edits, target sizing, assembly mode and backdrop-operation eligibility stay in Narrative. Preserve captured input and assembly provenance, Edit Text where supported, task capture, and the existing Inventory action. Scene-text eligibility and lock/publication stay service-owned. |
| Minor Characters | Style Alignment can offer its original source. Official views can offer the locked Style reference, matching private Draft where eligible, and other relevant saved views. | Mixed-quality asset boards. Keep Write/Save Prompt, interview using candidate evidence, and current source/Style readiness. STYLE locking is private. Official-view publication follows its existing rules. |

Character, Narrative, and Minor Character Lock can also select the candidate
as part of the same operation. Their adapters explain when the current lock
blocks selecting or locking another image. Character and Minor Characters
require unlock before a single-slot clear. Narrative can clear a selected or
locked candidate after explicit confirmation and may require confirmed scene
text before selection or lock. These differences change the available
actions, reasons, and confirmations within the common UI.

The five active Character Asset Container pipelines and all six Minor Character
assets mount the shared component. Narrative mounts it for backdrop, subscene, and final assembly targets. Image Generation mounts the shared component for each asset in its universe library. The table describes what
each adapter needs to preserve when adopting the shared component.

- Character implementation and workflow. [Container controller](../../zet/web/static/character_asset_container.js)
  · [Character workflow](LOCAL_CHARACTERS.md#character-asset-container-workflow-2026-11-06)
- Narrative implementation and workflow. [Controller](../../zet/web/static/narrative.js)
  · [Dialog template](../../zet/web/templates/narrative.html) · [Narrative workflow](NARRATIVE.md)
- Minor Character and Image Generation implementation. [Minor Character controller](../../zet/web/static/minor_characters.js)
  · [Image Generation controller](../../zet/web/static/image_generation.js) ·
  [dashboard templates](../../zet/web/templates/index.html), and
  [Image Generation workspace service](../../zet/services/image_generation_workspace_service.py)

## 6. Workflow compliance checklist

Apply this checklist to the workflow being brought into compliance. Check
its board and review behavior against this specification and the workflow
rules in Section 5. Each workflow can meet these criteria independently.

- The workflow uses the shared Render Controls and eight-slot grid, with the
  shared review modal in a separate host. Draft and Final candidates coexist,
  draw from the same slot capacity, and share one selection.
- Supported actions follow the specified placement, labels, glyphs,
  interaction, and feedback. The image and eye control open the same review.
  Verify keyboard and touch access and accessible reasons for disabled actions.
- Review handles an absent selection, a selected Draft or Final, and review
  of the selected image itself. Check multiple comparison sources where the
  workflow supplies them, and verify that a failed comparison leaves the
  candidate usable. Wheel zoom from either image shares focus and scale,
  resets when the candidate changes, and persists when only status or
  comparison changes.
- The board and modal work at desktop and compact sizes. Opening and closing
  review manages focus. Drive a pending slot through progress and completion
  using the public update method. Verify status, image, and Luna results
  reach both the grid and an open review while slot order and applicable local
  review state are preserved. Check a failed slot and a completed image whose
  former source changed. Advisory and action feedback stay separate.
- Portrait, square, and landscape thumbnails show the entire image at desktop
  and compact widths. In review, switching comparisons leaves the candidate's
  disclosure unchanged. Navigating candidates shows that candidate's saved
  prompt, input order, and settings. Verify inline delivery of captured
  references, including extensionless images where the workflow stores them.
- Where Luna is supported, check start, completion, outdated, failure, and
  rerun in the same status line. Confirm outdated rankings are marked previous
  and old start messages do not linger after a result.
- Each render shortcut requests its stated quality and count and reports
  insufficient capacity. Retry uses frozen inputs and Regen uses current
  inputs. Verify the workflow's applicable clear and bulk protections and
  rejection of a stale action. Image Generation omits Lock and Unlock.

Use the approved isolated fast checks that cover the workflow and focused
disposable checks for uncovered interactions.
[Approved fast scenarios](../Testing.md#approved-fast-scenarios)
