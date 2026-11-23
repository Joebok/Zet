# Release deployment without E2E tests
Status: complete
Related issue/specification: none

## Goal
Add a `-SkipTests` option to the Windows release command. When selected, the
release controller terminates processes listening on TCP port 8765 and skips
the E2E suite while keeping the remaining staging and compatibility checks.

## Current behavior
`Update_Release.ps1` forwards `-StageOnly` and `-Offline` to
`zet.scripts.update_release`. The normal deployment service writes a request for
the copied `deploy_release.py` controller. Both normal and offline staging run
the approved E2E suite on fixed port 8765 under a lock. The terminal-only
offline path stages directly through the controller module.

## Desired behavior
- `Update_Release.ps1 -SkipTests` bypasses only `npm run test:e2e`.
- Before bypassing the suite, terminate every process listening on TCP 8765; if
  cleanup fails, report the error and do not promote the release.
- Keep dependency setup, Python checks, release contract and library compatibility
  checks, diff checks, and promotion/rollback behavior intact.
- Support the switch with normal, `-StageOnly`, and `-Offline` CLI flows.

## Impact analysis
CLI: `Update_Release.ps1`, `zet/scripts/update_release.py`.
Request/plumbing: `zet/services/deployment_service.py`.
Staging/cleanup: `zet/scripts/deploy_release.py`.
Usage owners: `Docs/GitHub_Task_Workflow.md`, `Docs/DEVELOPMENT.md`; implementation
ownership in `Docs/CODE_MAP.md` remains the same.
No serialized schema migration; the request gains an optional boolean field.

## Invariants and constraints
The option must be explicit. The fixed-port E2E lock remains in force for normal
validation. Skipping E2E must not bypass deployment contract, release guards,
library compatibility, or rollback protections. Do not add permanent tests or
expand the approved E2E baseline.

## Implementation steps
### WP1 - CLI and request propagation
- Dependencies: none.
- Files/interfaces: `Update_Release.ps1`, `zet/scripts/update_release.py`,
  `zet/services/deployment_service.py`.
- Work: add `-SkipTests` / `--skip-tests`, forward it in normal and offline
  deployment requests.
- Acceptance: every CLI path carries the option to the staging controller.
- Validation: PowerShell/Python parsing and CLI help.
- Status: complete.

### WP2 - Port cleanup and conditional validation
- Dependencies: WP1.
- Files/interfaces: `zet/scripts/deploy_release.py`.
- Work: stop TCP 8765 listener owners when requested, fail clearly if a process
  cannot be stopped, and skip only the E2E command while retaining other checks.
- Acceptance: skip mode frees port 8765 and does not invoke npm E2E; default mode
  retains lock and E2E execution.
- Validation: source review and Python syntax; no production deployment.
- Status: complete.

### WP3 - Documentation and review
- Dependencies: WP1-WP2.
- Files/interfaces: deployment usage docs, this plan.
- Work: document option semantics and observed checks; review diff.
- Acceptance: usage docs make the skipped checks and port cleanup clear; plan is
  complete and archived.
- Validation: Python/Node/PowerShell syntax where available, `git diff --check`.
- Status: complete.

## Validation
PowerShell and Python parsers, Python CLI help, Node syntax, and `git diff --check`
were run. No E2E suite or production deployment was run for this option.

## Risks and alternatives
Port cleanup intentionally terminates all listener owners on TCP 8765, as
requested. Permission errors or system-owned listeners must stop staging rather
than silently proceeding. The fast suite remains the default.

## Progress and decisions
- Initial implementation review confirmed both the managed controller path and
  offline staging path require option propagation.
- The CLI switch is `-SkipTests`; the underlying controller accepts
  `--skip-tests`. In skip mode TCP listener cleanup is required before staging
  continues, and release checks remain active.

## Final results
Implemented the switch across normal, stage-only and offline CLI paths. Port
cleanup enumerates Windows TCP listeners with `netstat.exe`, force-stops their
PIDs with `taskkill.exe`, and verifies no listener remains. The controller records
a clear validation status; E2E is omitted only when requested. Syntax and CLI
parsing checks passed. No production deploy or E2E run occurred.
