# 0036 — Long hair across Head and Assembly
Status: accepted
Date: 2026-10-27

## Context
Youth Tsaeytte's back-left Head-Image Edit source ended near shoulder height and
Assembly retained that endpoint despite authored mid-back hair. Legacy Head
specified shoulder-level hair, Head-Image Edit preserved framing and excluded the
torso, and Assembly limited reconstruction to the immediate neck junction.

## Decision
Head references show the complete hairstyle where practical, expanding the crop
to establish its visible anatomical endpoint while retaining usable identity
detail and natural proportions. Exceptionally long hair may continue off-frame
without an invented shorter hem. Natural occlusion remains intentional.

Assembly may complete cropped or prematurely terminated lower hair only to a body
landmark explicitly authored in the existing
`CHARACTER_ASSEMBLY_CHARACTER_REQUIREMENTS` section. Preserve the source hairstyle's
color, texture, parting, volume and asymmetry, with natural overlap over the
unchanged body and clothing design. Without an authored endpoint, preserve the
supplied length. Head-family authoring remains independent.

## Rationale and alternatives
Joe selected full-hair framing with fallback. Requiring every head reference to
contain all hair would sacrifice identity detail for exceptionally long styles;
tight head/neck references would leave all lower-hair design to Assembly. The
chosen split supplies visual evidence where practical while giving Assembly a
bounded completion instruction for missing or shortened source hair.

## Consequences and verification
Assembly input version 2 refreshes old prompt caches for fresh requests. Accepted
source versions require explicit revision acceptance, and new selected Head bytes
require a new Assembly batch to replace frozen source snapshots. Submitted asks,
Retry inputs, selections and locks remain unchanged. No new sections, APIs,
storage schemas, dependencies or maintained tests are required.

Disposable all-view compiler/slot checks and the approved fast E2E suite validate
software behavior; live image quality remains unverified. See
[Prompts](../COMPONENTS/PROMPTS.md#long-hair-across-head-and-assembly-2026-10-27),
[Local Characters](../COMPONENTS/LOCAL_CHARACTERS.md#long-hair-framing-and-assembly-handoff-2026-10-27)
and the [implementation plan](../../plans/completed/preserve-long-hair.md).
