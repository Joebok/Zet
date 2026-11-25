# UI consolidation and workflow alignment

Review the captured Zet evidence and current implementation to produce a detailed plan for fixing defects, aligning similar workflows, and making the site consistent and usable on desktop and landscape tablets. Treat existing patterns as evidence to assess; their presence does not establish a deliberate design decision.

The plan is approved and implementation is in progress. Supporting documents are the [evidence review and 21 findings](ui-consolidation/review.md), [proposed UI and workflow design](ui-consolidation/design.md), and [32 Luna sized implementation packets with progress](ui-consolidation/implementation.md).

## In scope

- Review the fresh workflow evidence and direct page captures from the UI evidence campaign, checking suspected defects against authoritative source and existing tests.
- Align the main generation workspaces around their shared flow: prepare structured inputs and references, compile and inspect inputs, author a prompt, render through Qwen Image 2.1, collect candidates, review, select, and lock.
- Align wizard flows that turn reference images and interview answers into information for the main pipelines.
- Standardize page structure, action placement, colors, labels, glyphs, spacing, and the meaning of enabled, disabled, selected, locked, pending, success, and error states.
- Make asynchronous progress and completion clear near the action and easy to find after scrolling or returning to the workspace.
- Give image thumbnails a consistent full-screen viewer with zoom and appropriate contextual glyph actions.
- Give image inputs consistent browse/upload, paste, and Image Inventory selection capabilities.
- Reduce unnecessary clicks with visible choices for small option sets and checkboxes for accepting suggested changes, where those controls fit the task.
- Plan reusable modules and components where behavior is shared, including workflow alignment beyond visual styling. Consider replacing legacy patterns when the review supports a better design.
- Support the full production workflow on desktop and landscape tablets. On tablets, prioritize candidate review, selection, locking, and queuing new renders while keeping all authoring and finishing tasks available.
- Produce prioritized findings with evidence, target behavior, affected owners, dependencies, acceptance checks, and Luna sized implementation packets.

## Evidence and constraints

- Start from the [campaign review index](../../../Zet_Tester/runs/ui-review-2026-11-24/REVIEW.md) and its linked manifests and fresh workflow reports.
- The captured release is `d6143b9f4c7550e8b3ec3dd56cc86c3ebb5b60d1`. Check current source/revision before assuming a captured behavior still exists.
- Consult [UI style guide](../../Docs/UI_STYLE_GUIDE.md), [Dashboard UI](../../Docs/COMPONENTS/DASHBOARD_UI.md), [Candidate Board](../../Docs/COMPONENTS/CANDIDATE_BOARD.md), [Code map](../../Docs/CODE_MAP.md), and relevant workflow owners. Existing documentation can also contain legacy assumptions.
- Preserve pipeline ownership, universe isolation, ordered image bindings, attempt fencing, saved production records, and lock/publication integrity when proposing shared interfaces.
- Planning does not authorize application changes. Use one agent. Implementation packets will reuse existing validation where suitable and identify coverage gaps without adding permanent tests during planning.

## Review findings

The [evidence and implementation review](ui-consolidation/review.md) records the initial findings, source ownership, evidence corrections, and remaining investigation. Current checkout HEAD matches the captured release. The first findings include the active Compare page calling an obsolete loader, a scene-text finish action that implicitly selects a candidate and conflicts with an existing lock, an indefinite Candidates loading state when there are no configured sources, inconsistent image inputs, and uneven workflow layout above the shared board.

Some earlier evidence labels overstate coverage or misclassify a prerequisite as a defect. The supporting review records actual routes and dimensions; missing tablet review, touch, and intermediate-state evidence remains a validation gap. Turnaround generation needs eight locked source views, and Zine fields accept typed tags with suggestions, so those captured failures need narrower diagnoses.

## Agreed workspace structure

Use one workspace with expandable preparation, as Joe selected. Inputs, references, interview/proposals, render controls and candidate work remain connected within the same scope.

The proposed layout details below apply that choice: expand required preparation for a new or incomplete asset, prioritize the board for an asset ready for render/review, and let the user keep preparation open. Preserve drafts, selection, scroll, and focus when changing layout or scope.

| Area | Desktop proposal | Landscape tablet proposal |
| --- | --- | --- |
| Context | Subject/scene, pipeline/view, selected/locked state | Compact context with full values available on demand |
| Preparation | Labeled sections that can remain open beside or above the board | Collapse long inputs; open the same full editors on demand |
| Render and activity | Reachable prompt/readiness, render controls and scoped progress | Keep render shortcuts and active status close to the board |
| Results | Stable candidate grid and common review viewer | Images and touch decisions receive most available space |
| Review | Fixed navigation/actions, separate scrolling advice/details | Reachable Select/Lock/Close and explicit zoom controls without scrolling through advice |

This proposal aligns presentation and action meaning. Workflow services continue to own their compilers, structured inputs, source order, saved production records, and publication rules.

## Agreed prompt and render rule

Current source inspection shows four different handoffs. Character compiles current templates and references when rendering; Minor Characters requires a prompt matching its current inputs; Narrative normally renders saved prompt text; Image Generation saves direct prompt edits before render actions. The [workflow comparison](ui-consolidation/review.md#prompt-and-render-handoff-today) records the relevant owners.

After relevant preparation changes, require an explicit Update prompt before rendering an AI-authored prompt, as Joe selected. Updating the prompt does not queue images. Keep the new wording available for inspection/editing before Draft or Final is requested.

Use shared readiness messages for saved inputs, pending proposals, next-render prompt, and render eligibility. Preserve automatic deterministic compilation and direct prompt entry where they make sense. A manually edited prompt can be explicitly saved/adopted for current inputs; do not force an AI writing stage onto direct entry.

An image's frozen prompt and ordered captured inputs remain separate from preparation for the next render. Changes to current sources/templates never invalidate completed images or block their selection/locking merely because the saved sources differ.

## Proposed shared design

The [design specification](ui-consolidation/design.md) defines the following behavior for approval with the complete plan:

- Keep the shared Candidate Board as the owner of slots, render shortcuts, candidate cards, review, comparison and decisions. Add a small reusable workspace shell for context, expandable preparation and readiness; keep domain compilers and orchestration in focused services.
- Keep candidate navigation, zoom, Select/Lock and local feedback reachable while advice and provenance scroll. Preserve the current candidate, comparison, zoom, drafts, focus and scroll through polling/resizing.
- Share a viewer foundation across static thumbnails, source previews, Inventory and candidate review. Supply explicit zoom/reset and touch pan/zoom; preserve editing gestures through a dedicated expand action on canvases.
- Share image acquisition: Choose image, Paste image and Image Inventory, with preview, captions, source order, clear replacement/removal, scope fencing and local failures. Where a workflow requires a catalog source, make Import and use explicit.
- Share proposed-change review: before/after content, independent acceptance checkboxes, Apply selected changes, conflict protection and optional full diffs. Use radios for small exclusive choices and searchable pickers for growing lists.
- Standardize labels/glyphs, token colors, form anatomy and readable typography. Proposed labels include AI review with visible model attribution, separate selection/locking/publication meanings, and explicit names for destructive effects.
- Give each async action local submitting/queued/running/succeeded/failed/unknown feedback. Keep active status visible when preparation is collapsed and prevent duplicate/conflicting work at the correct scope.
- Align wizards around references/goal, analysis/interview, reviewing proposed inputs, optional private test where supported, and explicit acceptance into the production workspace. Preserve private versus published results and current-versus-earlier draft evidence.
- Apply the same conventions to Inventory, Compare, Identity Keys/Turnarounds, finishing, animation, Zines, Config, Queue, Template Editor, Universes/species, manuals, tasks and Recent Renders. Audit obsolete diagnostic/reset paths against current service/storage ownership before replacing them.

## Priority fixes

| Priority | Finding and intended result | First packets |
| --- | --- | --- |
| P1 | Compare stops calling its obsolete phase loader and reports each side's errors locally. | WP01 |
| P1 | Saving finished text does not unexpectedly replace the selected candidate or fail after writing artifacts because another candidate is locked. | WP02 |
| P1 | Text editor Close/Escape always offers a safe exit and accurately reports partially saved work. | WP03 |
| P2 | Scene imports stops showing Loading when no configured source exists and explains its purpose. | WP04 |
| P2 | Shared board/image/input/status foundations establish the patterns for remaining page migrations. | WP05-WP11 |

The remaining findings and their source/evidence references are in the review. Priorities describe user impact; a captured prerequisite failure or missing test state is not automatically a code defect.

## Implementation sequence

| Wave | Result | Packets |
| --- | --- | --- |
| Defects | Repair the verified Compare, lettering and importer failures. | WP01-WP04 |
| Shared foundations | Standard actions/tokens, operation status, persistent review controls, viewer, acquisition, proposals and workspace shell. | WP05-WP11 |
| Production alignment | Validate a Character pilot, then migrate Minor Character, Narrative, Image Generation and the wizards. Add backend prompt freshness only where required. | WP12-WP20 |
| Site completion | Align Inventory/derived images, finishing/Zines, shell/Recent Renders, settings/editor/Queue and current diagnostics. | WP21-WP31 |
| Acceptance | Run approved regressions, collect accurate before/after evidence, update affected knowledge and record any device limits. | WP32 |

Each [packet](ui-consolidation/implementation.md) names dependencies, files/interfaces, work, acceptance and validation. Implement one coherent packet at a time with one agent; do not treat shared presentation as authority to merge workflow data models or perform unrelated cleanup.

## Acceptance

- All four generation families expose the same understandable preparation/prompt/render/review structure and action meanings, while their necessary domain differences remain clear.
- Changed authored-prompt inputs require Update prompt; rendering never silently triggers AI prompt rewriting. New render requests freeze the actual submitted text, settings and ordered references.
- Full production remains available at desktop 1920x1080 and 1366x768, and landscape tablet 1133x610 and 1024x768 CSS viewports. Ready board entry exposes render controls and usable candidates without authoring-form traversal.
- Image review has reachable decisions, explicit zoom/pan and comparison/navigation; static thumbnails and image acquisition use the shared components. Main touch action targets meet the 44px product target, with accessible alternatives for precise editor handles.
- Messages show actual async stage/outcome near the responsible action. Failures survive polling; unknown outcomes reconcile before resubmission; independent inspection stays usable during work.
- Existing affected E2E scenarios and the final complete approved suite pass. Disposable checks cover the stated layout, touch, failure and state-preservation gaps. No permanent scenarios/dependencies are added without approval.
- Before/after evidence matches actual route, dimensions, pointer mode, visible state and implemented revision. Artifact completeness alone does not count as page/workflow acceptance. Record physical tablet checks as unverified when hardware is unavailable.
- Update the affected style/component/workflow/code-map/data documentation and add a short ADR for durable ownership changes as specified in the packet document. Keep this plan active until implementation and actual validation are complete.

## Risks and implementation boundaries

- Input freshness and lock/publication are separate contracts. New-work guards must not regress the saved-source FYI policy for completed images.
- Broad CSS overrides can conceal regressions. Scope component rules and remove superseded page overrides only when their consumers have migrated; compare all four board adapters at each shared change.
- Older authored prompts lack consistent basis metadata. Use readable unknown state and explicit adoption/update for new work; preserve existing production records and serialization compatibility.
- Minor Character and some Narrative inputs require Inventory identities. The common input component must preserve that requirement through explicit import rather than inventing interchangeable source records.
- The page sweep contains legacy/empty states and mislabeled direct captures. Deeper Inventory organization, populated imports, valid Zine layouts, and coarse-pointer/physical-device behavior need the named acceptance checks. Do not infer success from the old campaign counts.
- Keep all model/render activity routed through AI_Proxy, and retain universe isolation, ordered bindings, attempt fencing, protected-effect approvals and authoritative catalog ownership. No application/deployment or live model work is part of planning.

## Review progress

- The supporting review contains 21 findings, a canonical surface matrix, and source-based corrections to the earlier blocker labels.
- Pixel inspection covers representative generation/review/wizard states, landscape board and text editing, Config, AI Queue, Pipeline Inspection/Controls, Template Editor, Costumes, Universes, Help and Recent Renders. The sweep's untouched deeper states remain explicit validation gaps.
- Existing approved E2E scenarios cover production boundaries, Character and Costume wizards, Narrative finishing/animation/Zines, Inventory editing, template conflicts and scope management. The packet document maps those scenarios to changes and identifies disposable checks where their assertions are insufficient, especially Minor Character Style/render behavior and touch/layout states.
- Planning validation consists of source/test inspection, representative screenshot review, link/packet checks and diff review. No application tests or live workflows were run for this planning request.
- Four planning documents, all local document links, 21 finding mappings and 32 unique implementation packets were checked. No missing link, unmapped finding, duplicate packet, trailing whitespace or prohibited dash was found; `git diff --check` passed. Earlier capture/application changes in the working tree were preserved.

## Open questions and review

No product choice remains open from the planning interview. The detailed design and packet order are proposed for review with the complete plan. Evidence gaps listed above have named implementation checks; they are not assumed outcomes. The plan is not accepted until Joe approves it as a whole.
