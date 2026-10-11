# Zet project instructions

## Project and knowledge entry point

Zet is a local creative-production dashboard for character references, illustrated scenes, and zines. FastAPI presents Python services over universe-scoped files and an entity image library; AI work is dispatched through filesystem queues or the Narrative Codex integration.

- Before significant changes, consult [Docs/INDEX.md](Docs/INDEX.md), select the relevant documents, then inspect authoritative code and tests. Documentation is a navigation aid; investigate contradictions rather than assuming either old notes or filenames describe current behavior.
- Start from [Docs/CODE_MAP.md](Docs/CODE_MAP.md) for implementation ownership and related tests. Do not read the entire knowledge base for every task or make speculative changes based on undocumented assumptions.
- Essential commands from the repository root: `npm run test:e2e`; `git diff --check`. The approved testing baseline and live-check boundaries are in [Docs/Testing.md](Docs/Testing.md). Run the dashboard with `python3 -B -m zet.web.app --config config.toml --host 127.0.0.1 --port 8081` when authorized to use that library. Setup and command verification are in [Docs/DEVELOPMENT.md](Docs/DEVELOPMENT.md).

## Scope

- Treat the request's goal, relevant context, constraints, and success criteria as the scope boundary.
- Make the smallest coherent change. Exclude unrelated cleanup, modernization, renaming, reformatting, warning fixes, and refactoring.
- Search for symbols and read only the files needed to act safely. Do not summarize unrelated code.
- Ask one concise question only when a material ambiguity or blocker cannot be resolved from the repository. Do not invent APIs or add unapproved placeholders.
- Do not use subagents unless the user explicitly requests them.

## Testing

- Zet is a personal application run on one machine. Prefer a few representative end-to-end task tests over extensive unit coverage.
- Reuse the approved end-to-end scenarios. Do not automatically add a test for every change or defect.
- Get Joe's explicit approval before adding tests, introducing scenarios, or materially expanding coverage. State which user task the proposed test covers and why existing scenarios are insufficient.
- Approval applies only to the named tests or scenarios. The current approved baseline is three fast end-to-end scenarios and one separately invoked live narrative pipeline check.
- Repair existing tests when needed to preserve their approved purpose.
- Do not add coverage targets, exhaustive permutations, snapshot suites, test frameworks, or dependencies without approval.
- Exercise story and scene workflows through the Narrative Scenes dashboard, `/api/narrative`, and `NarrativeStories` storage. Do not add tests for the retiring Scene Builder or local scene-batch workflows.
- Keep fast test runs isolated from the normal library, queue, machine indexes, and live model/render services. Run the optional live check only when Joe requests it.

## Architecture

- Put reusable Zet behavior in `zet/services`, `zet/repositories`, `zet/models`, or pipeline scripts.
- Keep `zet/web` limited to FastAPI routes, presentation, browser interaction, and calls into backend services. Do not place file discovery, pipeline transitions, prompt review, render orchestration, or other reusable business logic there.
- Expose new dashboard workflow actions through `ZetApp`, `AssetRef`, or a focused service before calling them from the web layer.
- The Streamlit dashboard and standalone Render Console are retired; do not add functionality to them.
- Preserve universe isolation, queue ownership and attempt fencing, locked-image integrity, serialization versions, and ordered image bindings; see [Docs/INVARIANTS.md](Docs/INVARIANTS.md).
- Traditional character generation is retired. Active local character workflows reuse compilers but have independent run/selection storage. Narrative scenes are independent of Scene Builder. Follow the relevant component document before crossing these boundaries.
- The entity library's `catalog.sqlite3` is authoritative; the machine-local library index is derived. Never treat their rebuild or migration procedures as interchangeable.

## Runtime and dependencies

### Python Runtime

- All Python scripts must run under Python 3.
- Prefer `python3` when available.
- If `python3` is unavailable, locate a Python 3 interpreter using `python`, `py -3`, or an explicit executable path.
- Before using a fallback interpreter, verify it with:
  `<candidate> -c "import sys; assert sys.version_info.major == 3"`
- Reuse the verified interpreter for all subsequent Python commands.
- Never run an unverified `python` command, because it may resolve to Python 2.

### Dependencies

- If a required package is unavailable, stop, identify it, and ask for installation. Do not install, replace, or work around it without approval.

## Changes and validation

- Preserve existing style and behavior outside the requested change.
- Prefer localized edits to rewrites; never duplicate unchanged code.
- Run the smallest relevant existing tests or checks after editing. Report the command and result; if none can run, state why.

## Planning and knowledge maintenance

- Before substantial features, complex bug fixes, cross-component changes, or refactors, write or update a plan in `plans/active/` using [plans/README.md](plans/README.md). Break implementation into Luna sized work packets with files, dependencies, acceptance checks, and validation. Trivial edits do not require a formal plan. This does not authorize delegation or later refactoring phases.
- Before implementation, identify affected architecture, component, data, invariant, workflow, and code-map documentation after inspecting code/tests.
- During implementation, synchronize the active plan with progress; record discovered dependencies, constraints, deviations, and unresolved contradictions. Avoid unrelated documentation changes.
- After implementation, update only affected knowledge. Update the code map when responsibilities or significant entry points move; add a short ADR for significant durable design choices using [Docs/DECISIONS/README.md](Docs/DECISIONS/README.md). Record observed validation, complete the plan, and move it to `plans/completed/` when done.
- Documentation maintenance is part of significant code changes. Prefer source links and one primary owner per concept; mark uncertainty and untested commands explicitly. Do not duplicate complete schemas or invent historical rationale. Report any documentation that could not be verified or updated.

## Review and refactoring authority

- `architecture_reviewer`: when the user explicitly requests a deep review, cleanup assessment, architectural review, or refactoring plan, it may inspect broadly; identify dead or duplicate code; compare data models; and propose deletions, migrations, abstractions, or staged refactoring. This is analysis only unless implementation is explicitly authorized.
- `refactoring_implementer`: may implement only a user-approved phase from a written review or plan. Keep the phase testable, run or add relevant tests, exclude unrelated cleanup, and stop after that phase. Approval never carries to later phases.

## ComfyUI

- Normally ComfyUI is only available via AI_Proxy. If needed to run directly, stop and ask to have ComfyUI Desktop started.

## Final response

- State the result, validation performed, and any blocker or required next action. Omit filler, repeated rationale, and unrelated detail.
