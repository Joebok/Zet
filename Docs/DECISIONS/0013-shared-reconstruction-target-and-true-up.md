# 0013 — Shared reconstruction target and true-up
Status: accepted for local implementation and operator trial; rollout pending
Date: 2026-10-15

## Context

The Quick Character Wizard preserved source style/equipment, while phase-1 Image Generation reconstruction separated content from style but had no corrective comparison. Freydis needs Moonsea style and original identity/hair length while deliberately losing her axe. An unconditional source-match review could undo that edit.

## Decision

Extend `ImageReconstructionService` with board-independent source preparation, target analysis/composition, comparison and correction specifications. `image_reconstruction_contract.py` owns target precedence/validation; `ImageTrueUpService` owns structured model comparison and direct edit composition. Wizard sessions and the Image Generation workspace retain separate selection, allocation and publication responsibilities.

Freeze original observations separately from explicit preserve/change instructions, effective appearance, uncertainty and destination style. Target edits create a new task revision. Explicit changes override conflicting source details and generated anchors. Reports bind target/candidate/source hashes and distinguish accidental drift, missing edits, successful edits, style/view issues and non-evaluable details. Visible discrepancies may be selected as suggestions; custom operator feedback takes precedence over earlier artistic direction. No model approval is required for a custom edit, and failed review does not prevent choosing a rendered wizard image. Reports remain advisory.

Original source pixels remain analysis-only as in [ADR 0012](0012-universe-style-and-reconstruction.md). Initial reconstruction is txt2img. True-up uses the styled candidate as an img2img input; character side views use the approved styled front. This is a separate reference policy, not permission to reintroduce original pixels into rendering.

Both hosts freeze submitted inputs and retain history. Retry uses saved inputs and seed; editing intent invalidates approvals. A new front invalidates views using the previous anchor. Image Generation corrections reserve new slots and validate the exact selected source again at handoff; they never replace or unselect it automatically.

## Tradeoffs and consequences

Text reconstruction can lose facial precision, and model review cannot guarantee identity or correction compliance. Joe accepted the Freydis improvement as sufficient to proceed to an operator trial. The primary flow is render, custom tweaks or optional suggestions, try again, then use an image when close enough. Analysis and prior attempts are optional details; individual handwork may remain. No automatic correction loop, original-identity-reference rendering mode, traditional pipeline integration or catalog schema change is introduced. Existing storage integrity and runtime deployment boundaries remain separate from artistic review.

See the [active plan](../../plans/active/character-reconstruction-and-true-up.md) for packet status and validation evidence. Prepared-response checks establish software contracts, not artistic success.
