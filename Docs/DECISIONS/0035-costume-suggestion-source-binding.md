# 0035 — Costume suggestions address source lines and replace prose
Status: accepted
Date: 2026-10-26

## Context
Post-render costume analysis could return original text that did not exist or
occurred more than once. One invalid finding rejected the whole response.
Replacement view tags were discarded when Zet composed the operator's scopes,
so a tag-only suppression could leave the original instruction active.

## Decision
Give analysis a catalog of eligible costume/equipment body prose lines. Each ID
contains section, source line number and original-line digest. Resolve IDs against
the current session text and retain exact before-text fencing. Scene-only sections,
head-domain lines, resource declarations and compiler structure remain ineligible.

Models return replacement prose; Zet preserves spatial annotations and generates
view/mode scopes. Validate spatial prose through existing view conditioning. Apply
multiple edits from the end of the source so earlier line positions remain valid.
Existing saved findings without IDs keep their unique-text application path.

Validate findings independently and request at most one repair of rejected
findings with specific diagnostics. Keep valid findings if repair fails; report
omissions in the review summary. If none survive, fail with the concrete reasons.
Empty initial findings remain a valid no-change result. Human selection and diff
approval remain mandatory before trials and master promotion.

Require asymmetry guidance to distinguish side-specific visibility and occlusion,
including fixed one-sided equipment, from symmetric costume corrections. An
asymmetric suggestion leaves its mirror unchecked; final scope choices remain human.

## Consequences and verification
New finding fields are additive to version-2 costume sessions; no catalog migration
or dependency is needed. Addressing repeated prose does not authorize editing
previously protected sections. Prepared-response checks establish binding, repair
and trial contracts; they do not establish live model quality. See
[Testing](../Testing.md) and [Local Characters](../COMPONENTS/LOCAL_CHARACTERS.md).
