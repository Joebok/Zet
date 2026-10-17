# Zet agent knowledge index

Read [AGENTS.md](../AGENTS.md) first. Select only the documents relevant to the task, then verify their source and tests. This knowledge base describes implementation inspected on **2026-10-11**; newer code and observed tests may expose drift.

The V5 history recovery on 2026-10-11 restored the approved fast E2E suite and retired the former Python/browser suites and CI gates; S4 was added to the baseline on 2026-10-16. [Testing](Testing.md) owns the four scenarios, isolated fixture/reset behavior, optional live check, and coverage policy. Component/code-map verification now refers to that baseline and names uncovered contracts. Earlier results in completed plans and Git snapshots remain historical evidence, not current commands or outstanding failures.

## Task navigation

| Task/question | Read first | Follow with |
| --- | --- | --- |
| Understand the system or add a subsystem | [Architecture](ARCHITECTURE.md) | [Code map](CODE_MAP.md), relevant component |
| Find a feature, its callers, and regression tests | [Code map](CODE_MAP.md) | Matching component and source |
| Change identifiers, storage, or configuration | [Data model](DATA_MODEL.md) | [Invariants](INVARIANTS.md), [library](COMPONENTS/LIBRARY.md) |
| Change character or scene prompts | [Prompts](COMPONENTS/PROMPTS.md) | [Narrative](COMPONENTS/NARRATIVE.md); [Scene Builder](COMPONENTS/SCENE_BUILDER.md) for historical structured-workflow context |
| Change local character generation/review | [Local characters](COMPONENTS/LOCAL_CHARACTERS.md) | [Queues](COMPONENTS/QUEUES.md), invariants |
| Debug jobs, restart recovery, or missing images | [Queues](COMPONENTS/QUEUES.md) | [Development](DEVELOPMENT.md), owning workflow |
| Plan a substantial change/refactor | [Plan convention](../plans/README.md) | Architecture, relevant invariants, [decisions](DECISIONS/README.md) |
| Select validation, debug E2E, or inspect the seed | [Testing](Testing.md) | [Development](DEVELOPMENT.md), code-map scenario/gap references |
| Report a dashboard task or restore captured context | [GitHub task workflow](GitHub_Task_Workflow.md) | Code-map task forwarding entry, config definitions |

## Document ownership

| Document | Primary purpose / questions answered | When to read |
| --- | --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Boundaries, initialization, communication, execution lifecycle | First system-level work |
| [CODE_MAP.md](CODE_MAP.md) | Where to change behavior, callers, tests, likely impact | Before locating implementation |
| [DATA_MODEL.md](DATA_MODEL.md) | Store ownership, formats, identifiers, configuration, compatibility | Any persistent/interface change |
| [INVARIANTS.md](INVARIANTS.md) | Supported contracts, consequences, verification | Before changing a shared assumption |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Setup/run/check commands, observed results, debugging and gaps | Environment or validation work |
| [Testing.md](Testing.md) | Approved fast scenarios, isolated fixtures, optional live check, coverage approval | Before selecting or changing tests |
| [GitHub_Task_Workflow.md](GitHub_Task_Workflow.md) | GitHub capture/evidence, worker/limits/attention, deployment and restoration | Dashboard task reporting and Kanban integration |
| [COMPONENTS/LIBRARY.md](COMPONENTS/LIBRARY.md) | Universe binding, authoritative images, derived discovery index | Library/reference/discovery work |
| [COMPONENTS/LOCAL_CHARACTERS.md](COMPONENTS/LOCAL_CHARACTERS.md) | Candidate generation, ranking, human review, selection, publication | Character pipeline work |
| [COMPONENTS/PROMPTS.md](COMPONENTS/PROMPTS.md) | Template compilation, view conditioning, attachment contracts | Prompt changes |
| [COMPONENTS/SCENE_BUILDER.md](COMPONENTS/SCENE_BUILDER.md) | Retiring structured scenes, targets, layout, render and review | Retired workflow, migration history and offline geometry archive; no maintained scenario |
| [COMPONENTS/NARRATIVE.md](COMPONENTS/NARRATIVE.md) | Independent narrative authoring, jobs, references and assembly | Narrative workflows |
| [COMPONENTS/AI_JOBS.md](COMPONENTS/AI_JOBS.md) | Shared AI request/collection, queue activity, cached capability catalog and model popup | Any active AI workflow |
| [COMPONENTS/QUEUES.md](COMPONENTS/QUEUES.md) | File Proxy/manual protocol, harvesting, receipts, process recovery | Async work and integrations |
| [DECISIONS/README.md](DECISIONS/README.md) | ADR convention and evidence-backed decision records | Significant design choices |
| [plans/README.md](../plans/README.md) | Executable plans, Luna sized packets, active/completed lifecycle | Substantial implementation |

## Other documentation

- [README.md](../README.md) and [Tutorial.md](../Tutorial.md): installation/product usage. Some descriptions predate the current production renderer; verify against [local characters](COMPONENTS/LOCAL_CHARACTERS.md) and code.
- [.github/CODEX_WORKFLOW.md](../.github/CODEX_WORKFLOW.md): issue selection and delivery when that workflow is explicitly requested.
- `Docs-Joe/`: preserved design/research material. Useful intent sources include [V5 direction](../Docs-Joe/Zet%20V5%20Realignment.md), [library proposal](../Docs-Joe/Library%20Structure.md), [view tagging](../Docs-Joe/ZET_View_Conditioned_Template_Tagging_Spec.md), [Narrative phase 2](../Docs-Joe/Narrative_Scenes_Phase_2.md), and [reference caching](../Docs-Joe/ComfyUI_Reference_Cache.md). Proposals are not evidence that a feature is implemented; `Docs-Joe/archive/` is historical.

Keep links repository-relative, use stable module/symbol references, and maintain the document that owns the changed concept. See AGENTS for the before/during/after maintenance workflow and Development for known verification gaps.

## Removable storage recovery (2026-10-17)
[Storage recovery](COMPONENTS/STORAGE_RECOVERY.md) owns outage classification, local evidence, startup/polling reconciliation, fresh attempts, and verification limits.
