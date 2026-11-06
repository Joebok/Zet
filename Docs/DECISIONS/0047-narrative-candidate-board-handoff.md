# 0047 — Narrative Candidate Board handoff
Status: accepted locally
Date: 2026-11-06

## Context
The Image Production Abstraction defines an Asset Container, Asset and Candidate
Board so future image pipelines can share board behavior without sharing their
authoring tools or storage. Narrative already has story, scene, target and candidate
records, but some board transitions and cross-Story source choices bypass a common
policy boundary.

## Decision
Narrative Stories, Scenes and image targets serve as the container, asset and board
owners. Candidate Board rules live in a reusable service and receive target board
state. Narrative continues to own authoring, persistent records and domain finishing.
New candidates carry an immutable `ImageRenderRequest` through dispatch and retry.
New cross-Story references require a locked candidate published to Inventory.

## Rationale
The existing Narrative hierarchy already maps to the three abstraction levels.
Keeping its storage avoids a migration solely for naming while allowing future
pipelines to call the board policy and render handoff interfaces.

## Alternatives and tradeoffs
Rewriting Narrative storage around generic containers would add a second ownership
model without improving the existing boundaries. Independent pipeline records stay
independent until those pipelines are separately migrated.

## Consequences
Board state transitions must use shared policy helpers, including selection through
scene-text confirmation. Published Inventory images have independent identity and
remain available after candidate changes. Existing pinned inputs and `NARRATIVE`
tags remain readable. Image request settings are captured for retries.

## Related code and documentation
[Image Production Abstraction](../../Docs-Joe/Image%20Production%20Abstraction.md),
[Narrative component](../COMPONENTS/NARRATIVE.md),
[active implementation plan](../../plans/active/narrative-image-production-workflow.md).
