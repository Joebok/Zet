# Architectural decision records

Record significant choices that affect future implementation: boundaries, persistent contracts, integration policy, or a design tradeoff that code alone cannot explain. Do not add an ADR for every small implementation detail. Existing design notes stay in `Docs-Joe/`; link them as evidence rather than relocating or rewriting them.

| Record | Question answered | Status |
| --- | --- | --- |
| [0001 — Library authority and derived index](0001-library-authority-and-derived-index.md) | Which catalog is authoritative, and what can be rebuilt? | Current boundary; retrospective |
| [0002 — Independent Narrative workflow](0002-independent-narrative-workflow.md) | Why must scene changes distinguish Narrative from Scene Builder? | Current boundary; retrospective |
| [0003 — Local character production boundary](0003-local-character-production-boundary.md) | Which character workflow/renderer should receive new production behavior? | Current policy; retrospective |
| [0004 — Approved local task testing baseline](0004-local-task-testing-baseline.md) | What validation is maintained, and when can coverage/live testing expand? | Current policy; reconstructed from recovered commits |

These records were reconstructed on 2026-10-11 from cited code/tests and notes. They are not a claim to know the historical decision date or undocumented motivation. A significant future change should add a new ADR and mark superseded records with its link instead of silently changing history.

Use `NNNN-short-topic.md` with:

```markdown
# NNNN — Decision title
Status: proposed / accepted / superseded by <link>
Date: <record date; label retrospective if reconstructed>

## Context
Problem, current boundary, evidence, and constraints.

## Decision
Concrete chosen direction; distinguish current code from a proposal.

## Rationale
Supported reasons; explicitly say unknown when historical rationale is absent.

## Alternatives and tradeoffs
Known alternatives only; label retrospective analysis as such.

## Consequences
Responsibilities, contracts, affected consumers and validation implications.

## Related code and documentation
Authoritative paths, tests, relevant component and plan links.
```

Link new ADRs here and from the owning component. A proposed decision or plan does not authorize unrequested implementation.
