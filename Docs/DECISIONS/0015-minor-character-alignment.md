# 0015 - Minor Character alignment and current boards
Status: accepted for local implementation
Date: 2026-10-15

## Context
Combining character/style detail with orientation produced inconsistent minor-character views. Joe requested separate style alignment, view alignment and suggested-change true-ups, with explicit selection gates and a simpler current-board workflow.

## Decision
Select a style-aligned image before any view alignment. Every view independently uses that selected image and a short orientation-only prompt. Select an aligned view before entering true-ups. Style images and view-alignment images cannot lock, including when carried into later boards. Only generated view true-ups publish.

Keep four current slots per stage, with at most one selected image carried in its same slot as Prior selection. One undo snapshot restores the prior prompt/supporting state but empties every slot and working selection. There is no redo or image history. Private immutable source/request snapshots support regeneration and different correction choices; they do not grant working-image access. Published Inventory assets remain immutable and independent of boards.

New records use workflow_version 1; retired workspace records are excluded without migration or compatibility work, as Joe explicitly requested during implementation. Existing files are untouched. This supersedes the Minor Character iteration/adoption/front-anchor rules in ADR 0013/0014. Shared original-pixel analysis-only reconstruction policy remains.

## Consequences
MinorCharacterWorkflow owns lifecycle, prompts, stage-aware review and board revision checks over the existing wizard engine. The router/UI only present service operations. Detailed target information informs style generation and review; it is excluded from view-alignment rendering. Suggestions remain advisory. Late results cannot restore discarded membership, and discarded candidates cannot be selected, locked or served as working images.

Left comparison arrows loop independently of right candidate navigation. Main Minor Characters navigation opens the complete list after saving. No catalog migration, dependency, production deployment or permanent test expansion is introduced.

## Validation
Disposable isolated prepared-response service/API and browser journeys cover selection gates, prompt/reference contracts, true-up publication, carry, undo/replay/reload, revisions/late results, comparison wrapping and navigation. The existing S1-S3 suite is regression coverage only. Real rendered orientation/identity still requires Joe's artistic acceptance.

See [local characters](../COMPONENTS/LOCAL_CHARACTERS.md), [data model](../DATA_MODEL.md), and [implementation plan](../../plans/completed/minor-character-alignment.md).
