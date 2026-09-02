# Zet project instructions

## Scope

- Treat the request's goal, relevant context, constraints, and success criteria as the scope boundary.
- Make the smallest coherent change. Exclude unrelated cleanup, modernization, renaming, reformatting, warning fixes, and refactoring.
- Search for symbols and read only the files needed to act safely. Do not summarize unrelated code.
- Ask one concise question only when a material ambiguity or blocker cannot be resolved from the repository. Do not invent APIs or add unapproved placeholders.
- Do not use subagents unless the user explicitly requests them.

## Architecture

- Put reusable Zet behavior in `zet/services`, `zet/repositories`, `zet/models`, or pipeline scripts.
- Keep `zet/web` limited to FastAPI routes, presentation, browser interaction, and calls into backend services. Do not place file discovery, pipeline transitions, prompt review, render orchestration, or other reusable business logic there.
- Expose new dashboard workflow actions through `ZetApp`, `AssetRef`, or a focused service before calling them from the web layer.
- The Streamlit dashboard and standalone Render Console are retired; do not add functionality to them.

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

## Review and refactoring authority

- `architecture_reviewer`: when the user explicitly requests a deep review, cleanup assessment, architectural review, or refactoring plan, it may inspect broadly; identify dead or duplicate code; compare data models; and propose deletions, migrations, abstractions, or staged refactoring. This is analysis only unless implementation is explicitly authorized.
- `refactoring_implementer`: may implement only a user-approved phase from a written review or plan. Keep the phase testable, run or add relevant tests, exclude unrelated cleanup, and stop after that phase. Approval never carries to later phases.

## Final response

- State the result, validation performed, and any blocker or required next action. Omit filler, repeated rationale, and unrelated detail.
