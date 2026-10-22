# Architectural decision records

[0026 - Publish and reconcile production template edits](0026-template-edit-publication.md)
records explicit recovery PRs, exact merged snapshots and the master-write fence.

[0025 - Character prompt review, staged views and image refinement](0025-character-review-stages-and-refinement.md) records the text-only review gate, same-side stages, dedicated refinement and advisory reference changes.

[0021 — Existing files admit local character image review](0021-file-based-local-image-availability.md)
records file-based local batch availability and exact moved-universe path reads.

[0019 — Failed AI job deletion retains a local fence](0019-failed-ai-job-deletion.md)
records confirmed queue cleanup and replay fencing (2026-10-16).

[0020 — Configured machine storage and bounded retention](0020-configured-machine-storage.md)
records the storage root and lean completed-history policy (accepted 2026-10-16).

[0017 — Durable image harvest admits dependent analysis](0017-image-harvest-admission.md)
records the image completion barrier and continuation publication identities
(accepted 2026-10-16).

Record significant choices that affect future implementation: boundaries, persistent contracts, integration policy, or a design tradeoff that code alone cannot explain. Do not add an ADR for every small implementation detail. Existing design notes stay in `Docs-Joe/`; link them as evidence rather than relocating or rewriting them.

| Record | Question answered | Status |
| --- | --- | --- |
| [0001 — Library authority and derived index](0001-library-authority-and-derived-index.md) | Which catalog is authoritative, and what can be rebuilt? | Current boundary; retrospective |
| [0002 — Independent Narrative workflow](0002-independent-narrative-workflow.md) | Why must scene changes distinguish Narrative from Scene Builder? | Current boundary; retrospective |
| [0003 — Local character production boundary](0003-local-character-production-boundary.md) | Which character workflow/renderer should receive new production behavior? | Current policy; retrospective |
| [0004 — Approved local task testing baseline](0004-local-task-testing-baseline.md) | What validation is maintained, and when can coverage/live testing expand? | Current policy; reconstructed from recovered commits |

| [0005 — Narrative dashboard and legacy scene retirement](0005-narrative-dashboard-and-legacy-scene-retirement.md) | How do dashboard authoring, historical images, Candidates and the geometry archive relate? | Accepted 2026-10-12 |
| [0006 — Atomic image inventory edits and preferred references](0006-atomic-image-inventory-edits.md) | How are image editor updates committed and which active key is displayed? | Accepted 2026-10-12 |
| [0010 — Composite harmonization and explicit subscene transparency](0010-narrative-harmonization-and-transparency.md) | How can assembly integrate subjects and subscenes explicitly request alpha backgrounds? | Accepted 2026-10-14 |

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

| [0007 — Stable render slots](0007-stable-render-slots.md) | Who owns render positions, supplemental candidates, and Image Generation selection? | Accepted 2026-10-12 |
| [0008 — GitHub tasks and production releases](0008-github-tasks-and-production-releases.md) | Who owns delivery, evidence, claims and promotion? | Accepted 2026-10-13 |
| [0009 — Narrative interview review](0009-narrative-interview-review.md) | How are wider interview edits reviewed, routed to shared/local fields and applied? | Accepted 2026-10-13 |
| [0011 — Portable library references](0011-portable-library-references.md) | How do library-owned file references survive a library relocation? | Accepted 2026-10-14 |

| [0012 — Universe style and text-only reconstruction](0012-universe-style-and-reconstruction.md) | How do shared artistic rules, Narrative inheritance and image-to-text reconstruction preserve their separate contracts? | Accepted 2026-10-14 |

| [0013 — Shared reconstruction target and true-up](0013-shared-reconstruction-target-and-true-up.md) | How do both image workflows preserve intentional edits while correcting drift? | Accepted locally 2026-10-15; artistic acceptance pending |
| [0014 - Persistent Minor Character workspaces](0014-minor-character-workspaces.md) | How do named ongoing workspaces separate working selection, Inventory locking and visual comparison? | Accepted locally 2026-10-15 |

| [0015 - Minor Character alignment and current boards](0015-minor-character-alignment.md) | How do style/view selection gates, simple prompts and one-level undo replace iteration history? | Accepted locally 2026-10-15 |

| [0016 — Unified AI execution and collection](0016-unified-ai-jobs.md) | Who owns provider execution, independent cloud admission, common collection and model selection? | Accepted 2026-10-16 |
| [0018 — Ranking-only character review](0018-ranking-only-character-review.md) | How do rendered character candidates reach ranking and human review without a defect verdict stage? | Accepted locally 2026-10-16; existing library conversion pending |

[0022 � Local recovery evidence and subscriber-owned fresh attempts](0022-removable-storage-recovery.md) records removable-volume recovery, continuation intent, and the authoritative-catalog/index distinction (accepted 2026-10-17).

| [0023 - Available images and verified handoffs](0023-streamlined-image-integrity.md) | File availability, managed versions, incremental usages, confirmed deletion and async indexes | Accepted 2026-10-17 |

[0024 - Character template versions and explicit view references](0024-character-template-versions.md) records batch-local proposals, compiler overlays, confirmed promotion and selected-view conditioning (accepted locally 2026-10-17; artistic quality unverified).

[0027 - Repository-managed LLM roles and skill composition](0027-repo-managed-llm-skills.md) records provider-independent skill ownership, explicit purpose classification, frozen guidance and role model inheritance (accepted locally 2026-10-22).
