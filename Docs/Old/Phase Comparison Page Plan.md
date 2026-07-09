# Phase Comparison Page Plan

## Goal

Add a read-only dashboard page for comparing two phases of the same character side by side.

This page is meant to help with visual consistency checks across phases such as:

- Adult vs Youth
- baseline phase vs alternate phase
- early phase vs later refinement phase

It is not a workflow page. No pipeline actions, promotions, edits, or saves happen here.

## User Experience

The page should let the user:

- choose one character
- choose one phase for the left side
- choose one phase for the right side
- choose one pipeline from a dropdown
- if pipeline is "Costume-Dressing" then each phase can select one independently.
- step through the locked assets for that pipeline
- view the left and right locked images side by side

The page should not allow:

- prompt edits
- recompile
- render actions
- promote to locked
- delete
- note/comment changes

This is a visual inspection surface only.

## Core Interaction Model

The page layout should have:

- a top control row
- a central side-by-side comparison area
- a compact metadata strip showing what is being compared

Top controls:

- `Character`
- `Left Phase`
- `Right Phase`
- `Pipeline`
- previous asset button
- next asset button

Comparison area:

- left image panel
- right image panel

Each panel should show:

- the locked image
- the asset label
- the body view
- the head view if applicable
- costume or expression label if applicable
- asset id

## Comparison Scope

Phase comparison should be limited to one character at a time.

The initial comparison target should be locked assets only.

If a pipeline/view has no locked image on one side, the page should still show the comparison row with:

- the existing locked image on the side that has one
- a clear missing-state panel on the side that does not

This is useful because a missing image is itself part of the comparison state.

## Pipeline Behavior

The pipeline dropdown should be populated from the existing phase pipeline definitions, but the page should only compare pipelines that have meaningful locked image outputs.

Expected initial pipelines:

- `Body-Reference`
- `Head-Fitment`
- `Character-Assembly`
- `Costume-Dressing`
- `Expression`

The comparison sequence for the selected pipeline should be based on the natural locked-asset ordering for that pipeline.

Suggested ordering:

- first by body view in the canonical view order
- then by head view where applicable
- then by costume name where applicable
- then by expression name where applicable
- then by asset id as a stable tiebreaker

## Matching Rules

The page needs a stable concept of “the same slot” across two phases.

Suggested matching keys by pipeline:

- `Body-Reference`: `body_view`
- `Head-Fitment`: `body_view + head_view`
- `Character-Assembly`: `body_view + head_view`
- `Costume-Dressing`: `body_view + head_view + costume`
- `Expression`: `body_view + head_view + expression`

The comparison navigator should step through these normalized slots, not through raw asset ids.

That lets one side be missing without breaking navigation.

## Backend Shape

This should follow the existing service-backed dashboard pattern.

Recommended backend additions:

- a new focused service such as `PhaseComparisonService`
- a read-only API endpoint such as `GET /api/phase-comparison`

The service should:

- load assets for both phases
- filter to locked assets only
- build normalized comparison slots for the selected pipeline
- resolve locked image paths for both sides
- return a list of comparison rows plus a selected row payload

Recommended response shape:

- selected character
- left phase
- right phase
- selected pipeline
- available pipelines
- comparison rows
- selected row index
- selected row detail

## Frontend Shape

This should be implemented as another FastAPI dashboard page in the existing web UI.

Recommended additions:

- new tab: `Phase Comparison`
- JS loader for the new API
- read-only image viewers reusing the existing file-serving path

The frontend should preserve the existing dashboard conventions:

- native selects
- AJAX reloads
- stable selection state
- no business logic duplication in JavaScript

## State And Navigation

The page should remember:

- selected character
- selected left phase
- selected right phase
- selected pipeline
- selected comparison index

When the pipeline changes:

- reset to the first available comparison slot

When the left or right phase changes:

- try to preserve the current slot key if it still exists
- otherwise fall back to the first slot

## Missing-State Behavior

When one side is missing:

- show a labeled placeholder such as `No locked asset for this slot`
- keep the comparison slot in the navigator

When both sides are missing:

- this slot should usually not be shown

The page should compare actual existing work, not empty theoretical rows.

## Implementation Notes

This page should stay read-only all the way through.

That means:

- no action buttons in the comparison panels
- no promotion buttons
- no source editor entry points
- no prompt review or render review affordances

It should feel closer to an image review light table than a pipeline control page.

## Suggested Milestones

### Milestone 1

- Add `Phase Comparison` page shell
- Add service and API
- Support `Body-Reference` only
- Support locked image comparison and previous/next navigation

### Milestone 2

- Expand matching logic to `Head-Fitment` and `Character-Assembly`
- Add missing-state panels
- Preserve selected slot on phase changes

### Milestone 3

- Expand to `Costume-Dressing` and `Expression`
- Add richer slot labels for costume/expression cases
- Refine ordering and filtering behavior

## Recommended First Use Case

The first practical use case should be:

- Character: `Tsaeytte`
- Left Phase: `Adult`
- Right Phase: `Youth`
- Pipeline: `Body-Reference`

That gives a clean first pass on whether phase differences are intentional and consistent before layering on head-fitment, assembly, costume, and expression comparison.
