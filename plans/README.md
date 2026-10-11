# Implementation plans

Use a written plan before changing code for substantial features, complex bug fixes, cross-component changes, or refactors. Trivial edits do not need a plan. Read [AGENTS.md](../AGENTS.md) and select relevant knowledge through [Docs/INDEX.md](../Docs/INDEX.md) first; verify the authoritative code and tests.

## Location and existing workflow

- Start `plans/active/<descriptive-slug>.md`; move it to `plans/completed/` after recording final results. Keep incomplete or blocked plans active.
- Link a related issue, specification, or existing design note rather than copying it. Preserve existing plans in `Docs-Joe/`; this convention applies to new work and does not relocate historical notes.
- For explicitly authorized issue work, retain the claim, review, and delivery rules in [.github/CODEX_WORKFLOW.md](../.github/CODEX_WORKFLOW.md). A local plan neither authorizes external writes nor approves a later refactoring phase.
- Break implementation into **Luna sized work packets**: one bounded responsibility, named files and interfaces, dependencies, acceptance checks, and a validation command. Size each packet so a smaller agent can implement and verify it with selective context. A packet is a unit of work, not permission to delegate.

## Plan template

```markdown
# <Change name>
Status: active
Related issue/specification: <link or none>

## Goal
Outcome and reason; scope and explicit exclusions.

## Current behavior
Verified implementation paths, symbols, tests, and relevant documentation.

## Desired behavior
Observable result and acceptance criteria.

## Impact analysis
Affected files, interfaces, serialized data, callers, consumers, and tests.
Name documentation owners that may need updates.

## Invariants and constraints
Relevant contracts; permission/dependency boundaries; unresolved knowledge.

## Implementation steps
### WP1 — <bounded responsibility>
- Dependencies: <none or earlier packets>.
- Files/interfaces: <explicit ownership>.
- Work: <ordered changes>.
- Acceptance: <observable checkpoint>.
- Validation: <specific command or inspection>.
- Status: pending / in progress / complete.
Repeat for additional packets; keep behavior testable at each checkpoint.

## Validation
Focused tests, acceptance checks, and final diff review.
Separate commands to run from observed results.

## Risks and alternatives
Tradeoffs, uncertainties, failure cases, and how they will be resolved.

## Progress and decisions
Discoveries, actual progress, deviations, remaining work, and ADR links.

## Final results
Changed behavior/files; successful and failed validation; unverified work;
remaining issues. Mark complete only when the goal is met, then archive.
```

Keep plans executable without the original conversation. During implementation update checkpoints and discoveries; after implementation update affected knowledge, record exact validation results, and archive the completed plan. Do not treat a failed check as successful completion.
