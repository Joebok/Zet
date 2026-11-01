# Command-line release update
Status: complete
Related issue/specification: [production runtime](../../Docs/GitHub_Task_Workflow.md#production-runtime)

## Goal and current behavior
Provide project-root `Update_Release.ps1` to perform the dashboard's update and
release workflow from a terminal. The dashboard currently copies its own controller
and requires its server PID to initiate promotion; a simple HTTP wrapper would
retain the old controller and stale environment implicated in the Node failure.

## Desired behavior
The wrapper verifies the existing Python 3 environment and invokes a focused Python
CLI. The CLI locates the active release, prepares only deployment-related services,
verifies the serving boot/config/revision and managed dashboard process, and uses
DeploymentService to launch this checkout's controller with the terminal environment.
It reports progress and returns nonzero on failure/rollback/timeout. `-StageOnly`
validates without promotion. Only merged origin/main is deployed; no commits,
pushes, GitHub release publishing or new dependencies.

## Impact and constraints
Files: Update_Release.ps1, zet/scripts/update_release.py,
zet/services/deployment_service.py. Documentation owners: GitHub_Task_Workflow.md,
CODE_MAP.md, Testing.md. Deployment request schema, template guards, operation
serialization, E2E isolation, boot identity, exact process fencing and rollback
remain intact. No full ZetApp construction or creative workflow startup in CLI.
Existing dashboard callers retain self-PID checks. Requires running managed Zet
and an existing promoted release; first adoption remains a dashboard operation.
Do not execute a real update/restart while implementing this script.

## Luna-sized work packets
### WP1 — Share safe deployment initiation
- Dependencies: none.
- Files/interfaces: DeploymentService.start and _start.
- Work: allow a CLI runtime address after verifying ready health, boot, config,
  revision and managed dashboard ownership; retain existing dashboard behavior.
- Acceptance: invalid identities and concurrent updates fail before launch;
  CLI requests retain active production config and local controller source.
- Validation: disposable service checks with temporary repositories/state and mocks.
- Status: complete.

### WP2 — Add terminal entry points
- Dependencies: WP1.
- Files: Update_Release.ps1 and zet/scripts/update_release.py.
- Work: active-release discovery, minimal service assembly, progress/status/exit
  handling, verified Python wrapper, -StageOnly and optional -RuntimeRoot.
- Acceptance: invocation works outside project cwd; failure/rollback is nonzero;
  progress follows the exact operation. No actual deployment during validation.
- Validation: PowerShell parser/help, disposable CLI and wrapper checks.
- Status: complete.

### WP3 — Validate and document
- Dependencies: WP1/WP2.
- Files: affected docs and this plan.
- Acceptance: command and limits documented, approved regressions pass, clean diff.
- Validation: npm.cmd run test:e2e, Python syntax, git diff --check and diff review.
- Status: complete.

## Progress and decisions
WP1/WP2 are implemented. The deployment service retains the subprocess handle so
the CLI waits for controller exit: `promote` can publish an intermediate failed
status before finishing rollback. No status/request schema change was needed.
Disposable checks passed initiation, live identity rejection, managed-process and
concurrent-operation fencing, existing dashboard self-PID behavior, local helper
copying, active-release containment, CLI forwarding, stage/success/failure/recovery
exit codes, rollback waiting, controller crash and timeout. A copied wrapper in a
temporary project passed Windows PowerShell 5 and PowerShell 7 checks for an
external cwd, spaces in paths, argument forwarding and zero/nonzero exit codes.
Python syntax, PowerShell parsing and command help passed. The first disposable
run needed a missing config field added to its fixture; production code was not
changed for that fixture failure. No production operation has been launched.

## Results
`npm.cmd run test:e2e` passed all four approved fast scenarios (48.5s), using the
verified project Python 3 environment through ZET_TEST_PYTHON. All focused checks
passed again after polling was ordered to observe exit before reading final state,
avoiding stale status when the controller exits between the poll and file read.
Python syntax, PowerShell 5/7 wrapper behavior, PowerShell parsing/help,
`git diff --check` and final scoped diff inspection passed.
Updated the command usage/limits in GitHub_Task_Workflow.md, entry points in
CODE_MAP.md, and observed validation in Testing.md. No new dependencies or
maintained tests. No actual release update, restart, external publication or
creative-data mutation was performed.
