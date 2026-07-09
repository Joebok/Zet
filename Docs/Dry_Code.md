Goal:
Review the Zet codebase for duplicated logic, repeated patterns, stale helper code, overly-large functions, and opportunities to DRY up implementation without changing behavior.

Context:
This is the Zet project. The codebase includes Python scripts and supporting prompt/job files used for character/image-generation workflows. Preserve current behavior, file formats, job status conventions, and existing pipeline assumptions unless you find a clear bug. This task is primarily a cleanup/refactor review, not a feature task.

Constraints:
- Do not perform a broad rewrite.
- Do not rename public files, job statuses, CLI entry points, output filenames, or user-facing workflow concepts unless absolutely necessary.
- Do not change generated prompt wording, protected template sections, overlay behavior, or job advancement semantics unless the duplication fix requires it and the change is explicitly explained.
- Prefer small, local, diff-based changes.
- Preserve backwards compatibility with existing job folders and markdown/json files.
- Do not introduce new dependencies unless there is a very strong reason.
- Avoid “clever” abstractions. Prefer boring, readable helpers.
- Keep logging behavior unchanged unless the existing code already has a logging switch.
- If tests are expensive or unavailable, do static validation and explain what was not run.

Success criteria:
1. Identify the top DRY/refactor opportunities in priority order.
2. Separate safe mechanical cleanup from risky architectural cleanup.
3. Implement only the safest high-value changes in this pass.
4. Keep the diff small and reviewable.
5. Preserve behavior.
6. Run relevant tests/checks if available.
7. Report what changed, what was intentionally left alone, and recommended next passes.

Instructions:
First inspect the repository structure and identify repeated code or patterns. Look especially for:
- repeated file/path setup logic
- repeated markdown section parsing
- repeated JSON loading/saving
- repeated job-list/status handling
- repeated prompt/template injection logic
- repeated filename sanitization
- repeated validation/error-reporting patterns
- similar code duplicated across Scripts/

Before editing, produce a short refactor plan:
- “Safe to do now”
- “Should be separate task”
- “Do not touch without explicit approval”

Then implement only the “Safe to do now” items.

When implementing:
- Extract small helpers only where they remove real duplication.
- Keep function names explicit.
- Add docstrings only where they clarify non-obvious behavior.
- Update call sites narrowly.
- Do not reformat unrelated code.
- Do not move files unless required.
- Do not change output text unless preserving it exactly is impractical; if changed, call that out.

Validation:
- Run the smallest relevant test/check commands available.
- If no tests exist, run syntax checks for changed Python files.
- Report exact commands run and results.

Final response:
- Summary of DRY opportunities found
- Files changed
- Behavior-preservation notes
- Tests/checks run
- Risks or follow-up tasks