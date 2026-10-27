# Zet UI style guide

Status: target standard for future UI changes; implementation is partial.
Source review: 2026-10-27. Scope: the active FastAPI dashboard and its auxiliary pages.

This guide defines the visual language and interaction behavior Zet pages should
share. It preserves useful existing patterns and sets expectations where pages
currently differ. **A rule in this guide does not mean every page implements it.**
Creating this guide does not change the application or authorize a site-wide rollout.

[Dashboard UI](COMPONENTS/DASHBOARD_UI.md) owns implementation details and observed
device limitations. This document owns the intended presentation standard. Backend
services remain authoritative for eligibility, selection, publication, and job state;
see [invariants](INVARIANTS.md). “Required” below means acceptance criteria when a
component is introduced or brought into alignment; “preferred” permits a documented
workflow-specific exception.

## 1. Core expectations

- The same action has the same name, glyph, color role, and feedback pattern everywhere.
- Every enabled action visibly acknowledges activation, including keyboard activation.
- Progress, success, and failure appear beside the control or object responsible,
  where the user is already looking. A distant banner or toast is insufficient.
- Images and decisions take priority in review. Details remain available without
  pushing essential controls out of reach.
- Preview, human assessment, selection, and locking are distinct states and actions.
- Polling, resizing, and opening a dialog preserve work, context, focus, and position.
- Color and icons reinforce explicit labels; neither is the only source of meaning.

## 2. Theme and visual foundations

Use the shared tokens in [zet.css](../zet/web/static/zet.css), rather than new
page-specific colors. The following values already exist; their consistent use
across all components is the target.

| Role | Token and current value | Intended use |
| --- | --- | --- |
| Canvas | `--canvas: #f5f7fa` | Page background |
| Surface | `--surface: #ffffff` | Cards, forms, dialogs |
| Subtle surface | `--surface-subtle: #eef2f6` | Grouped details, image background, neutral hover |
| Border | `--border: #cbd5e1` | Component separation; reinforce essential boundaries where necessary |
| Text | `--text: #17212b` | Main copy and neutral icons |
| Muted text | `--text-muted: #5f6b7a` | Supporting copy, timestamps, metadata |
| Primary teal | `--primary: #0b5663` | Main action, active navigation, selected image outline |
| Primary hover / soft | `--primary-hover: #08434d`; `--primary-soft: #dcecef` | Primary hover; selected tabs and supporting tint |
| Success green / soft | `--success: #067647`; `--success-soft: #ecfdf3` | Confirmed completion or positive assessment |
| Warning amber / soft | `--warning: #a15c00`; `--warning-soft: #fffaeb` | Attention, blocked prerequisites, stale advice |
| Danger red / soft | `--danger: #b42318`; `--danger-soft: #fef3f2` | Destructive actions and errors |
| Danger hover | `--danger-hover: #912018` | Destructive-action hover |
| Information blue / soft | `--info: #175cd3`; `--info-soft: #eff6ff` | Informational status and guidance |
| Focus purple | `--focus: #7c3aed` | Keyboard focus; distinct from selection |
| Chrome | `--chrome: #20252b` | Shared application header |

Existing `--save`, `--update`, `--new`, `--accent`, and `--nav` aliases resolve to
primary teal. Save, Update, and New do not introduce separate color families.
Green means a result or assessment, rather than “this is the selected image.”
The current theme is light; a dark theme is not specified here.

### Type, spacing, and surfaces

- Keep the existing Segoe UI/system sans-serif family. Use monospace for source,
  paths, identifiers, and code where it aids reading, rather than ordinary guidance.
- Target readable body text at 16px with roughly 1.45 line height; 14px supporting
  text and 12px minor metadata. Required instructions and errors must remain easy
  to read. These are target defaults, not a description of every current selector.
- Use a clear page title, section headings, field labels, and supporting copy.
  Prefer sentence case: “Save criteria”, “Stage in Image Generator”. Preserve proper
  workflow names such as Narrative Scenes and Costume-Dressing.
- Prefer a 4px spacing scale: 4px within tight icon groups, 8px between related
  controls, 12–16px inside panels, and 24px between major sections. Existing 10px
  image-card padding can remain until that component is aligned.
- Use 8px corners for controls and standard cards, 4px for image wells, and 12px
  for dialogs. Use borders and whitespace for grouping; reserve noticeable shadows
  for overlays. Avoid decorative gradients or custom palettes on individual pages.
- Wrap long labels and messages. Truncated names must have an accessible way to
  reveal the full value. Ordinary page content must not require horizontal scrolling.

## 3. Buttons and common glyphs

### Color and hierarchy

| Button role | Default treatment | Examples / existing hook |
| --- | --- | --- |
| Primary | White text/icon on primary teal; darker teal hover | Save, Generate, Apply, Select; `.primary-action` |
| Secondary | Text on white, standard border; subtle hover | Review, Edit, Copy, Download, Refresh; `.neutral-action` or default button |
| Navigation | Teal text on white; active state uses primary-soft and stronger text/border | Tabs and destinations; `.navigation-action`, `.tab.active` |
| Destructive, compact | Red text/icon and red outline on white; danger-soft hover | Clear slot, Remove reference, Delete card; `.danger-text-action` |
| Destructive, confirmation | White text/icon on danger red; darker red hover | Final “Delete image” confirmation; `.danger-action` |
| Disabled | Neutral muted styling; no active hover or press treatment | Temporarily unavailable action, with a visible reason |

Prefer one visually dominant next action per action group. Multiple cards can each
have a primary action. Apply the same hierarchy in dialogs and inline forms.
Cancel and Close are secondary; they are not destructive. Assessing an image as
Fail may use danger color as a labeled decision state, but does not imply deletion.
Unlock uses a secondary treatment plus an explanation of its effect; it is not Delete.

### Glyph vocabulary

[image_card_ui.js](../zet/web/static/image_card_ui.js), `ZetImageCardUI.decorate`,
already supplies the SVG keys listed without an asterisk. Entries marked **target***
need a shared glyph before adoption; this guide does not add them to the helper.
The names below describe shapes, not Unicode characters to paste into buttons.

| Function / preferred label | Shared key or target glyph | Usual role / meaning |
| --- | --- | --- |
| Review / View image / Compare | `review`: eye | Secondary; opens inspection |
| Select | `select`: check in circle | Primary when eligible; chooses the workflow image |
| Unselect | `unselect`: minus in circle | Secondary; removes selection |
| Lock | `lock`: closed padlock | Primary when the next workflow action; explicit protection/publication |
| Unlock | `unlock`: open padlock | Secondary; explicit change to protection |
| Save / Save changes | `save`: disk | Primary; persists edits |
| Edit / Refine | `refine`: pencil | Secondary; opens editing or refinement |
| Add renders / Generate | `generate`: plus | Primary for generation; label/count must explain what is created |
| Add item | **target***: plus, reusing the shared shape | Primary or secondary by hierarchy; always name the object |
| Regenerate | `regenerate`: paired circular arrows | Secondary, or primary if the main task; creates a fresh result |
| Retry | `retry`: return arrow around a circle | Secondary, or primary on a failed item; retries the named failed step |
| Refresh | **target***: single circular arrow | Secondary; rereads state without requesting new creative output |
| Clear slot / Delete / Remove | `clear`: trash | Destructive; label and confirmation must describe the actual scope |
| Copy | `copy`: overlapping sheets | Secondary; transient “Copied” acknowledgement |
| Download | `download`: arrow into tray | Secondary; saves a local copy |
| Import / Add to Inventory | `import`: arrow into tray with plus | Secondary, or primary in an import form; names the destination |
| Previous / Next | `previous`, `next`: left/right chevrons | Secondary; accessible label names candidate, view, or image |
| Move up / Move down | `up`, `down`: vertical chevrons | Secondary; reorders rather than navigates |
| Close / Cancel | `close`: X | Secondary; discards nothing silently |
| Details / Information | `details`: circled i | Secondary; supporting information |
| Create task | `task`: clipboard | Secondary; captures a task |
| Choose image / Upload | **target***: arrow up into tray | Secondary; opens file selection |
| Paste image | **target***: clipboard with image | Secondary; reads clipboard with file-picker fallback |
| Settings | **target***: sliders | Secondary; opens settings |
| More actions | **target***: horizontal ellipsis | Secondary; opens a labeled menu |
| Pass / Fail / Undecided | Labeled radio group; optional check / X / dash | Human assessment, separate from Select |

Actions with different consequences must retain distinct labels even when sharing
a shape. “Remove reference” must not look like “Delete image” in its accessible name.
Do not add a competing icon font, emoji button set, or page-local SVG vocabulary.
Existing emoji status markers can be aligned with the SVG vocabulary in later work.

### Sizing and accessibility

- Standard desktop text controls have at least 36px height. Compact image actions
  use the existing 32 × 32px desktop control with an 18px SVG, 24-unit view box,
  unfilled stroke, and rounded line ends. Use the shared helper for its supported scopes.
- Touch targets are at least 44 × 44 CSS pixels, including close buttons, arrows,
  menu items, and decision labels. Pointer capability matters as well as width.
- Keep text on page navigation, forms, and uncommon or consequential actions.
  Icon-only controls belong primarily in familiar, repeated image toolbars.
- Every icon-only control needs an accessible action name and a hover/focus label.
  On touch, essential meaning and disabled reasons must be available without hover.
- Use native buttons for actions and links for destinations. Give non-submit buttons
  an explicit type. Use `aria-pressed` for actual toggles and an appropriate current
  state for navigation. Decorative SVGs are hidden from assistive technology.
- Hover, pressed, keyboard focus, selected, busy, and disabled are distinct states.
  Keep a visible purple focus outline; do not use the selected-image border as focus.
  Disabled controls must have nearby guidance because they may not receive focus.

## 4. Activation, progress, and local messages

### Every action has a visible lifecycle

| State | Required visible behavior |
| --- | --- |
| Ready | Label states the action and, where needed, its target/count |
| Activated | Show a pressed response immediately for mouse, touch, and keyboard |
| Request pending | Set busy feedback before awaiting the response; target acknowledgement within 100ms under normal conditions |
| Accepted / queued | Say “Queued” or “Started”, with the affected item; do not report completion |
| Running | Show the actual stage and known counts; keep status available throughout longer work |
| Completed | Confirm the actual outcome locally and update the affected object |
| Failed / blocked | Explain what failed or is missing, what was retained, and the next available action |
| Outcome unknown | Say that status could not be confirmed; retain context and offer a status refresh before a potentially duplicate submission |

For a request that has not finished within about one second, show continuing text
such as “Saving criteria…” or “Waiting for renderer…”. A spinner supplements that
text. Never invent percentages or reset a progress animation on every poll. Respect
reduced-motion preferences. Fast actions still need a perceptible result, such as
“Copied” for a few seconds or a changed selection label.

While pending, prevent repeat submission and conflicting actions at the appropriate
scope. Do not freeze unrelated cards or the whole page. Keep safe inspection and
navigation available. Busy icon buttons need nearby visible text and an updated
accessible name; gray styling alone is insufficient. Mark the affected region busy
where appropriate. Preserve focus when disabling or replacing the activating control.

### Message placement and lifetime

The standard action group is **inputs → action row → local status**. A status can
sit alongside the row when space permits; otherwise put it directly below. Prefer
the existing `.action-message.info`, `.success`, `.warning`, and `.error` treatments.
Keep a stable, small status region so feedback does not repeatedly move controls.

| Scope | Required placement |
| --- | --- |
| One field | Beside/below the field, associated with it; mark invalid input |
| Form save or validation | Beside Save/Apply, plus field errors; include a linked summary when errors are offscreen |
| One image or slot | Inside that card, directly below its actions |
| Review action | Inside the open dialog, beside its decision/action row |
| Suggest / Analyze / Generate | Beside that action, even if the page has a separate general status area |
| Batch operation | Beside batch controls, with per-item failures attached to affected items |
| Global outage or connection issue | Persistent shell notice, plus local impact beside blocked actions |

Feedback must be visible in the same viewport or scroll region as the action when
activated. In long forms/dialogs, keep the local status with the reachable action
bar; do not put its message at the top of a hidden background page. Do not steal
focus or jump the page for routine progress. After an explicit invalid submission,
focus the first invalid field or the error summary when needed to make errors usable.

Keep failures and warnings until resolved, superseded by a deliberate new attempt,
or explicitly dismissed. Dismissal does not imply resolution. Preserve progress
until the operation reaches a known outcome. Success acknowledgements may become
quiet after roughly 3–5 seconds, provided the resulting state remains visible;
durable “Saved” state beside an editor is preferable to an unexplained disappearance.
Polling must not replace an action error with an unrelated “Updated” timestamp.

Use `role="status"` / polite live announcements for routine changes and an alert
for a new blocking error when appropriate. Avoid repeatedly announcing an unchanged
message or rebuilding a whole live gallery for each poll. Associate messages with
their controls/fields. A toast, browser alert, log, or AI Queue link can supplement
the local message, but cannot replace it.

### Message copy

Use the action, object, outcome, and recovery in plain language. Put request IDs,
tracebacks, paths, and raw provider diagnostics behind Details or Copy diagnostics.
Preserve useful input and explain uncertain or partial outcomes accurately.

| Avoid | Prefer |
| --- | --- |
| “Error” | “Could not save criteria. Your edits are retained. Try Save criteria again.” |
| “Done” after dispatch | “Queued 4 renders for BACK. Images will appear here as they finish.” |
| “Invalid input” | “Criterion 2 needs a description.” beside that row |
| Silent disabled Suggest | “Save your criteria changes before requesting suggestions.” beside Suggest |
| “Failed” for every problem | “Rendering completed; review failed. The image is available. Retry review.” when supported |
| Silent network timeout | “Could not confirm whether generation started. Refresh status before trying again.” |

Examples are target copy patterns; they must match the service's actual outcome and
available recovery. “Cancel” must say whether it stops work or merely closes a view.

## 5. Standard image cards

Use the same anatomy for Character pipelines, Narrative candidates, Minor Characters,
Image Generation, and Inventory, adapting fields to their actual records:

1. **Identity:** view/subject name and a stable candidate or slot identifier.
2. **Image well:** consistent dimensions within the gallery; contain the full image,
   preserving aspect ratio. Use a neutral background and a clearly labeled placeholder.
3. **State:** one render-status line, with distinct selection/lock/assessment labels
   where relevant. Avoid repeating the same status in multiple places on the card.
4. **Actions:** predictable order—Review, Select/Unselect, Lock/Unlock, secondary
   operations, then destructive actions separated at the end. Omit inapplicable
   functions; keep temporarily unavailable ones with a visible reason.
5. **Local feedback:** progress, eligibility reason, or action result immediately
   beneath the action row. Detailed prompts and provenance belong in review/details.

Image clicks open inspection; they do not silently select or lock. Give the image
opening control a meaningful accessible name, such as “Review BACK candidate F-003”.
Use the shared card border, surface, and wrapping action row. Selected borders must
not change the card's outer dimensions or shift the gallery. Destructive hover or
focus styles must not obscure state markers.

### Independent state dimensions

| Dimension | Presentation / meaning |
| --- | --- |
| Empty | “No image” or “Empty slot”; generation/import action if eligible |
| Reserved / queued / rendering | Occupied placeholder and actual stage; no false empty slot or broken-image icon |
| Ready | Image available for review; does not imply assessment or selection |
| Failed | Red failure label and local recovery; details remain inspectable without an image |
| Previewed | Focus/preview indication only; inspecting another image does not change the selected image |
| Selected | Stable teal inset border and explicit “Selected” label; never green-only selection |
| Locked / published | Padlock plus explicit workflow-accurate “Locked” or “Published” label; distinct from Selected |
| Human assessment | Labeled Pass / Fail / Undecided, or established domain equivalent; independent of model advice |
| Model advice stale / unavailable | Labeled warning; never silently presented as current or substituted for a human decision |

These dimensions can coexist: a selected image may be locked, or ready while review
has failed. Do not flatten them into one misleading color or badge. The existing
`data-state` styling is a presentation hook, not a replacement domain state machine.
Selection eligibility and allowed mutation of locked images remain service-owned.

Keep cards keyed to stable identities during updates. Preserve the originating card,
gallery scroll, and focused action across polls. Render errors separately from
image-loading failures; retain a usable image when a later advisory step fails.

## 6. Review dialogs and image viewers

Use an accessible modal dialog anchored to the viewport, including when opened
from far down a gallery. Give it a title, safe-area spacing, and a dynamic viewport
height with a fallback. The target anatomy is:

- **Header:** subject/view/candidate identity, position in the set, Close.
- **Image area:** candidate and labeled reference/comparison, with matched available
  space and full-image containment. Remove the empty comparison column when absent.
- **Decision area:** current selection/lock state, distinct model advisory findings,
  Human decision, and the applicable action row with local feedback. Short advice
  can precede Human decision; long advice scrolls without moving decisions away.
- **Navigation:** separate candidate and view controls, clearly named. Previous/Next,
  Close, Select, and decision controls stay reachable without scrolling through details.
- **Details:** Prompt and Source/provenance disclosures, collapsed on opening or
  changing candidates; include prompt copy and recorded generation inputs when available.

Make the viewed image's frozen generation prompt distinct from an editable next-run
prompt. Labels such as “Prompt used for this image” and “Next render prompt” prevent
editing the wrong thing. Keep source bindings in their meaningful order.

Opening sets sensible focus and contains keyboard navigation within the modal.
Escape and Close follow the same close path, including unsaved-change protection.
Closing restores originating focus and gallery position without a page jump. Arrow
keys may navigate images when focus is not in an editable control; visible buttons
remain available. At an end boundary disable the unavailable direction, unless the
workflow deliberately uses a labeled looping comparison. Do not change established
navigation semantics merely to share a visual component.

Same-candidate polling preserves unsaved decisions, feedback text, reference choice,
expanded details, inner scroll, and focus. Changing candidates must settle or retain
draft decisions according to an explicit save/discard flow; silently losing them is
unacceptable. Resizing must not reset the dialog or its state.

A viewing-only dialog does not imply review or publication. Keep its toolbar compact
and omit workflow decisions. A destructive confirmation names the exact item, scope,
and consequence, including whether published images survive. Use explicit “Delete
image” and “Cancel” buttons; initially focus the safe choice. Failed confirmation
actions remain in the dialog with their error visible, rather than closing silently.

## 7. Forms, navigation, and responsive behavior

- Preserve universe, character/phase, story/scene, and current workspace context in
  the shell. Navigation must not silently move an action to a different context.
- Keep field labels visible; placeholders are examples, not labels. Group related
  fields and put help, units, validation, and prerequisites beside the relevant field.
- Use explicit Save by default. If a workflow autosaves, show Unsaved/Saving/Saved/
  Save failed locally. A failed save retains the draft; a response to an older save
  cannot mark newer edits saved. Protect unsaved edits during navigation or reload.
- Distinguish Create, Save, Apply selected changes, Generate, and Stage. Staging into
  Image Generation must not imply that a render has started. Explain replacement
  consequences when existing work may be overwritten.
- Loading, empty, filtered-empty, stale, unavailable, and failed are different states.
  “No matches—clear filters” differs from “No images—import or generate one”. Never
  show an empty-success state merely because loading failed.
- On compact screens, prioritize results, image review, and decisions. Put settings
  and long inputs in labeled disclosures while retaining editing access and drafts.
  Move infrequent utilities into Tools before the header collides; preserve destinations.
- Let action rows wrap in the same logical order. Keep intentional thumbnail strips
  and wide tables inside labeled horizontal-scroll regions. Do not shrink important
  text or touch targets to make a desktop layout fit.
- Image input offers Paste image and Choose image with a local status/fallback.
  Clipboard failure retains existing input; do not force a camera or fetch copied URLs.
- Maintain keyboard access, logical focus order, zoom/reflow, readable contrast, and
  meaningful names. Target at least 4.5:1 contrast for ordinary text and 3:1 for large
  text and essential control/focus boundaries. Token reuse alone is not proof of contrast.

## 8. Existing foundations and alignment gaps

This is a selective source review, not a complete visual audit or a claim of
cross-browser conformance. No live dashboard or physical device was exercised for
this document.

| Existing foundation and source | What future alignment must verify |
| --- | --- |
| [zet.css](../zet/web/static/zet.css): root tokens, button classes, `.action-message`, shared image-workspace rules | Remove inconsistent page overrides as affected components are updated; apply press/busy/local-message behavior consistently |
| [image_card_ui.js](../zet/web/static/image_card_ui.js): shared SVGs, action names, labels, scoped decoration | Reuse existing keys; add target glyphs centrally when needed. The helper's label inference does not establish workflow meaning or colors |
| [local_asset_pipeline.js](../zet/web/static/local_asset_pipeline.js): candidate selection, human decisions, review preservation | Retain service eligibility, separate advice/decision/selection/lock, and keep each action's outcome visible |
| [index.html](../zet/web/templates/index.html): shared shell, local review, multiple status regions | A status region's existence alone does not ensure it is near the initiating action or visible inside a dialog |
| [template_editor.js](../zet/web/static/template_editor.js): draft-aware validation, local diff progress/errors | Carry draft retention and stale-response protection into other editing workflows |
| [ai_queue.js](../zet/web/static/ai_queue.js): pending deletion, retained action error, durable activity | Queue-level status does not replace feedback on the originating workflow/card or per-row action |
| [Dashboard UI](COMPONENTS/DASHBOARD_UI.md): responsive review, touch image input, scoped card conventions and Costume-Dressing feedback | Existing implementation evidence is partial; physical-iPad acceptance remains pending there |

Inventory-specific cards and auxiliary pages still have distinct rules. Existing
classes, labels, and behavior should be inspected when each component is aligned;
this guide does not require changing data models or merging workflow controllers.

## 9. Acceptance checklist for a page update

Use this checklist during a bounded page/component change. Record existing exceptions
and uncovered behavior instead of describing an unverified page as compliant.

- [ ] Colors, type, spacing, buttons, and glyphs follow the shared vocabulary.
- [ ] Every enabled action acknowledges activation immediately; duplicate/conflicting
  submissions are fenced while safe unrelated work remains available.
- [ ] Slow, successful, blocked, failed, and uncertain outcomes appear beside the
  responsible action, including inside dialogs and on scrolled/narrow pages.
- [ ] Errors retain drafts/images and offer a truthful next action; polling does not
  erase errors, focus, selection, or unsaved changes.
- [ ] Image cards preserve aspect ratio and distinguish render, preview, assessment,
  selection, and lock state. Pending/failed items remain inspectable.
- [ ] Review controls remain reachable; comparisons, details, prompt provenance,
  close/focus restoration, and navigation work without losing context.
- [ ] Keyboard, focus, touch targets, labels, contrast, zoom, and reduced motion are
  checked alongside desktop and short-height/narrow layouts.
- [ ] No accidental generation, selection, publication, deletion, or context change
  results from inspection, refresh, resize, or an obsolete response.

For software changes, use the relevant approved scenarios and isolated fixture in
[Testing](Testing.md), plus disposable checks for affected behavior the scenarios
do not cover. Visual inspection should include desktop, the documented short-height
tablet targets, and a narrow layout; actual device acceptance remains distinct from
browser emulation. Permanent coverage expansion needs Joe's approval. A documentation
change alone does not establish runtime compliance with this guide.
