# Update diagnostics
Status: complete
Related issue/specification: none

## Goal and verified behavior
Make Test and production updates show stages, commands, active E2E scenarios,
errors and recovery. Shared `deploy_release.run` captures most command output;
its streaming branch inherits Windows handles under CREATE_NO_WINDOW and reports
only the executable and exit code. Test discards stage detail. Online production
retains a controller log; Test and offline production lack update transcripts.

## Impact and constraints
Owners: deploy_release.py, manage_test_release.py, update_release.py and the
controller launch in deployment_service.py. Documentation: DEVELOPMENT.md,
Testing.md, GitHub_Task_Workflow.md and CODE_MAP.md. Preserve release source,
identity fences, isolation, test lock, compatibility checks, skip behavior and
rollback. No production deployment, live AI calls, new dependencies or permanent
tests. Existing user plan remains untouched. No architecture or data migration.

## Luna sized work packets
### WP1 - Shared command diagnostics
- Dependencies: none.
- Files: zet/scripts/deploy_release.py.
- Work: explicitly pipe/stream child output, retain failure details, report
  command start/completion/timeouts and heartbeat, label staging/checks/recovery.
- Acceptance: Windows hidden commands expose stdout/stderr before completion;
  nonzero and timeout failures identify command, step and retained output.
- Validation: disposable subprocess checks, including CREATE_NO_WINDOW.
- Status: complete. Disposable Windows hidden-subprocess checks passed for live
  stdout/stderr, preserved query stdout, nonzero output, timeout and heartbeat.

### WP2 - All updater entry points
- Dependencies: WP1.
- Files: manage_test_release.py, update_release.py, deployment_service.py.
- Work: retain Test/offline transcripts, expose all stage detail and health/
  rollback diagnostics, ensure copied production controller is unbuffered.
- Acceptance: Test, online and offline production report useful progress/errors.
- Validation: disposable entry-point/status/log checks without deployment.
- Status: complete. Test failure transcript, controller log tail/partial lines,
  and health failure/startup-log diagnostics passed disposable checks.

### WP3 - Verification and knowledge
- Dependencies: WP1, WP2.
- Files: affected documentation and this plan.
- Work: run existing isolated E2E baseline and focused disposable checks, review
  final diff, document actual results and remaining operational limits.
- Acceptance: checks pass, no unrelated changes or permanent test additions.
- Validation: npm.cmd run test:e2e, Python syntax, git diff --check.
- Status: complete. All 20 existing scenarios passed through the release runner
  in 124.9 seconds (Playwright: 2.1 minutes). Python/JavaScript syntax and final
  whitespace/diff checks passed. Affected knowledge owners are synchronized.

## Risks and unresolved evidence
The original cmd.exe error alone does not identify the failed test/setup step.
Retained failed artifacts will be inspected read-only. Do not claim that logging
alone repairs an unknown scenario failure. Stream timeout handling must stop its
own child tree so fixtures cannot keep the validation lock/output pipe alive.

## Progress and decisions
Both latest retained Test failures identify the same existing Character recovery
scenario cleanup error: Windows EBUSY removing the recovery fixture after its
server exits. Repair its existing cleanup with bounded Node rm retries, retaining
failure behavior if the lock persists. No new scenario. Two repeated executions
passed using the project's verified venv interpreter, through the shared runner.
One initial focused invocation incorrectly quoted the multiword grep through
cmd.exe and found no tests; the corrected single-token grep passed both runs.
Full baseline validation passed through the release command and transcript.

## Final results
Both updater paths now expose timestamped stages, command timing and heartbeats,
explicit Windows child output, captured failure details and retained transcripts.
Health failures show the last response/error and startup log tail. Test recovery
and production rollback progress remain visible. The detached controller uses
unbuffered UTF-8 output. Skip behavior and release/identity/template fences remain.
Disposable checks also verified owned descendant listener termination on timeout,
normal/skip staging branches, Test/offline error transcripts, production terminal
outcomes including recovery, and a real copied standalone-controller failure.
No permanent tests, dependencies, live calls, external writes, deployments or
instance restarts. The cleanup repair must reach merged origin/main before staged
release tests include it; tracked-edit guards still require a clean source
checkout. The unrelated existing UI evidence plan is untouched.
