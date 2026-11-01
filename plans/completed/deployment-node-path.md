# Deployment Node discovery on Windows
Status: complete
Related issue/specification: none

## Goal and current behavior
Fix Update and restart failing with `cmd.exe failed: 'node' is not recognized`.
`zet/scripts/deploy_release.py:stage` finds npm but runs its lifecycle scripts
with an inherited PATH that may omit Node. Failed operation records confirm
validation failed before promotion; Node exists under `C:/Program Files/nodejs`.

## Desired behavior and impact
Validation discovers Node from PATH, beside npm, or standard Windows installation
directories, and passes Node/npm directories to child commands. Missing tools
produce a clear error before production stops. The controller remains standalone
stdlib code. No request/storage format, library, queue, promotion or rollback
changes. Documentation owners: GitHub_Task_Workflow.md and Testing.md;
CODE_MAP entry points and architecture remain unchanged.

## Work packets
### WP1 — Prepare deployment validation environment
- Dependencies: none.
- Files/interfaces: `zet/scripts/deploy_release.py`, validation environment in `stage`.
- Work: resolve Node/npm and prepend their directories to the validation PATH.
- Acceptance: npm lifecycle scripts work with Node omitted from inherited PATH;
  existing tool choices remain usable; missing tools fail explicitly.
- Validation: disposable subprocess checks with temporary package scripts,
  missing-tool checks, Python syntax check.
- Status: complete.

### WP2 — Validate and document
- Dependencies: WP1.
- Files: `Docs/GitHub_Task_Workflow.md`, `Docs/Testing.md`, this plan.
- Acceptance: approved fast suite passes; final diff contains only scoped changes.
- Validation: `npm.cmd run test:e2e`, `git diff --check`, final diff inspection.
- Status: complete.

## Risks and constraints
The running release copies its own controller, so a local source fix alone does
not repair that running process. Production modification/restart and external
writes require separate approval under AGENTS.md. Do not deploy or alter retained
releases. Preserve configured tool precedence; do not install dependencies or add
permanent tests. Standard-directory fallback cannot discover arbitrary custom
Node installations absent from PATH and npm's directory.

## Progress and decisions
The disposable subprocess check reproduced the exact old error using an npm shim
without Node on PATH. The new helper passed the same command, both lifecycle
scripts and nested Node execution. Checks also passed installed-tool discovery
with both tools absent from PATH, existing npm precedence, explicit missing-tool
failures and Python syntax. Windows environment keys from `os.environ.copy()`
are uppercase; fallback lookup uses those keys. No production files were changed.

## Results
`npm.cmd run test:e2e` passed all four approved fast scenarios (49.1s), using the
verified `.venv/Scripts/python.exe` through `ZET_TEST_PYTHON`. The suite logged
a storage-maintenance lock timeout and Windows connection-reset callback;
neither failed a scenario. Disposable regression, missing-tool and syntax checks
passed. `git diff --check` and scoped final diff inspection passed.
Updated deployment behavior in GitHub_Task_Workflow.md and evidence in Testing.md.
No production restart/deployment or permanent test additions were performed.
The running release still requires operational recovery: restarting from an
environment with the installed Node directory on PATH unblocks its old controller.
