# 0028 - Independent head edits and explicit Assembly sources
Status: accepted
Date: 2026-10-22

## Context

[The Qwen trials](../../Docs-Joe/Qwen-Head-Image-Prompts.md) produced accepted
Tsaeytte views through independent FRONT edits and separate correction/fullness
passes. Existing Head-Image chains predecessors and consumes different wording.
Joe requested both workflows remain runnable with separate selections and an
explicit Assembly source choice.

## Decision

Add `head-image-edit`, reusing lifecycle machinery through bounded adapter hooks.
Keep storage, queue ownership, authoring and publication keys independent without
migrating legacy runs. Optional HEAD_EDIT sections preserve old character validity.
Task templates own operations; characters own identity, visibility, hair/anatomy
and applicable reference roles.

Selected FRONT independently anchors all base side/rear views. Selected BACK can
guide a separately adopted rear-quarter hair finishing attempt, avoiding a cycle.
Keep source ancestry distinct from actual ordered render inputs and respect
intentional hair/eye occlusion. Assembly freezes `head_pipeline` (legacy by
default) and source identities. Refresh never switches families; promotion retains
the chosen keys and finishing dependencies. Source changes preserve working
evidence and published bytes.

## Consequences and evidence

Both families can be compared and consumed without changing current defaults.
The new pipeline requires its own authoring and fails clearly instead of falling
back. Common UI/recovery/publication consumers must recognize its identity.
Disposable compiler/service/browser checks establish contracts; approved fast E2E
scenarios cover existing tasks. Neither proves live image quality or generalization
across characters. Accepted multi-stage trial outputs do not validate a combined
prompt. No trial image is automatically adopted or published.
