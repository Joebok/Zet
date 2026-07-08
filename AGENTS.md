### Environment Fallback
- Always prioritize Python 3 over Python 2.
- Use `python3` explicitly for executing any python scripts.
- Do not assume system `python` points to a modern release.

### Architecture Boundary
- Keep reusable Zet behavior in backend code under `zet/services`, `zet/repositories`, `zet/models`, and pipeline scripts.
- Keep `zet/web` focused on FastAPI routes, page/API presentation, browser interaction, and calling backend service methods.
- Do not add file layout discovery, pipeline stage transitions, prompt review operations, render orchestration, or other reusable business logic directly to the web layer.
- When the dashboard needs a new workflow action, expose it through `ZetApp`, `AssetRef`, or a focused service first so other interfaces can reuse the same backend behavior.
- The old Streamlit dashboard and standalone Render Console are retired. Do not add new workflow functionality to them.
- If a package is not available, do not design a work-around. Stop and ask that the desired package be installed.

### Terse Responses
Cut out all conversational filler, preambles, and polite explanations. Return only the requested code block, minimal bullet points, or the direct structural diff.

### Token Economy

Minimize token usage.

- Read only the files required for the current task.
- Never summarize unrelated code.
- Avoid opening large files unless the task explicitly requires them.
- Prefer searching for symbols over reading entire files.
- Stop reading once sufficient context has been gathered.

### Minimal Changes

When modifying code:

- Produce the smallest correct change.
- Prefer editing existing functions over rewriting them.
- Do not reformat unrelated code.
- Preserve existing style.
- Do not rename variables, functions, or files unless required.

### Diff Preference

Unless explicitly requested otherwise:

- Apply minimal edits.
- Do not regenerate an entire file for localized changes.
- Do not duplicate unchanged code.

### Scope Discipline

Stay inside the requested scope.

Do not:

- perform opportunistic refactoring
- modernize unrelated code
- improve comments outside the requested area
- fix unrelated warnings
- reorganize project structure

unless explicitly instructed.

### Stop Conditions

When blocked:

- Ask one concise question.
- Do not speculate.
- Do not invent missing APIs.
- Do not implement placeholders without permission.

### Prompt Contract Template

Every task should be interpreted using this contract.

Goal:
<what should be true>

Context:
<only relevant files or functionality>

Constraints:
<what must not change>

Success:
<how success is verified>

Anything outside this contract is out of scope.

### Reasoning Budget

Choose the simplest solution that satisfies the request.

Do not compare multiple architectures unless asked.

Do not explore alternatives unless requested.

Avoid speculative analysis.