# GitHub issue capture and automated Codex delivery
Status: active
Related specification: Joe's approved implementation plan in this chat (2026-10-13).

## Goal and boundaries
Create task -> public Joebok/Zet issue with frozen context/evidence -> one local
Codex worker -> validated PR -> Joe reviews/merges -> explicit update and restart.
No automatic merge, live library testing, new dependencies/permanent scenarios,
or deletion of Kanban data. Start Codex work defaults on; Save for later is available.

## Current behavior and impact
TaskService forwards to Kanban; capture providers and browser drafts already exist.
ProcessService matches module names without instance identity. Configuration and
mutable Config state assume a code-relative root. The existing three fast E2E
scenarios use isolated library/queue/index data. Docs/INDEX.md, CODE_MAP.md,
ARCHITECTURE.md, DATA_MODEL.md, INVARIANTS.md, DEVELOPMENT.md, Testing.md,
Kanban_Integration.md and .github/CODEX_WORKFLOW.md are affected knowledge owners.

## Packets
| Packet | Files/interfaces | Dependencies | Acceptance / validation | Status |
| --- | --- | --- | --- | --- |
| WP1 Runtime boundaries | config_service, state paths, launchers, preset consumers | none | Stable runtime state; isolated worker config; disposable path checks | implemented; disposable validation passed |
| WP2 Process identity | process_service, restart helper, health | WP1 | Only own processes restart; revision/boot health; disposable process checks | implemented; disposable validation passed |
| WP3 GitHub publication | github client, task repository/service, config | WP1 | Durable receipts, reconcile ambiguous creation; fake GitHub checks | implemented; disposable validation passed |
| WP4 Evidence/context | screenshot staging, formatter, context providers | WP3 | Valid image bytes, commit-pinned links, original prose, public preview | implemented; disposable validation passed |
| WP5 Capture UI | task_capture.js/html, task router, toolbar templates | WP4 | Ready/later, retry/reload, deliberate legacy conversion; disposable browser checks | implemented; disposable validation passed |
| WP6 Claim/recovery | worker service/repository/CLI, issue workflow | WP3-4 | One claim, branches/PRs checked, trusted replies resume; fake GitHub checks | implemented; disposable validation passed |
| WP7 Usage | Codex usage adapter/cache | WP1 | Fresh limits, 10% reserve, unknown pauses; read-only protocol/disposable checks | implemented; disposable validation passed |
| WP8 Pilot/schedule | automation prompt, development setup | WP6-7 | Small authorized issue reaches validated PR before 30-minute schedule starts | pending |
| WP9 Attention | status service/router, dashboard panel | WP6-8 | Action items, freshness, quota, errors; mocked browser checks | implemented; disposable validation passed |
| WP10 Deployment | deployment service/stable helper, restart UI | WP1-2,9 | Stage merged main, validate disposable data, new boot/revision, recovery | implemented; disposable validation passed |
| WP11 Cutover/docs | component docs, code map, workflow/template, ADR | all | Three successful deliveries before final cutover; preserve Kanban records | pending |

## Contracts
GitHub credentials stay server-side. Capture request IDs bind repository/report
hashes in SQLite outside Git/library. Uncertain issue creation is reconciled, never
blindly repeated. Evidence is content-addressed on codex/issue-evidence, excluded
from code delivery. Original report and actual screenshots remain acceptance
inputs. Explicit context only; no prompts, source documents or private paths.
New issue readiness is applied after complete publication.

Production: Zet_Runtime/releases/<sha> plus stable Zet_Runtime/state; existing
library/queue paths stay unchanged. Instance-specific process control and new
boot/revision health fence restart completion. Data-incompatible changes block
deployment; code rollback does not roll back creative data.

## Validation / rollout
Run npm.cmd run test:e2e and git diff --check, serially. Disposable checks cover
unmaintained capture/coordination/deployment contracts. No live model/render check.
Enable scheduling after a real pilot; promote production only after recovery checks.
Keep this plan active until those rollout gates and three successful deliveries pass.

## Progress and decisions
- Initial checkout clean; main. Python 3.14 verified. No subagents.
- Existing gh 2.96 lacks --attach; use supported GitHub contents API for evidence.
- Prior read-only probe confirmed account/rateLimits/read support.

## Final results
Pending.

- Existing baseline passed: 3 scenarios, 25.9 seconds (before final hardening).
- Disposable service checks passed: receipts/conflicts/ambiguous delivery, pinned
  image integrity, ready/later, dependency/priority, fenced claims, trusted replies,
  quota thresholds, instance matching, cached attention.
- Disposable browser checks passed: public preview, viewport, reload/retry receipt,
  ready/later, quota panel and deliberately backed-up legacy conversion.
- Disposable two-HTTP-instance controller checks passed: expected revision/new boot,
  failed candidate rollback, mutable-state preservation, staging failure without
  stopping the old server, and stale-boot abort. Staging dependencies were stubbed
  in that check; actual merged-main deployment remains a rollout gate.
- WP8 real GitHub/Codex pilot and native schedule still pending. WP11 documents
  implementation and preserves historical Kanban guide; final retirement remains
  gated on three deliveries. Production has not been restarted/promoted.

- Final baseline before pilot: npm.cmd run test:e2e passed 3 scenarios in 25.9s.
- Changed Python AST parsing, JS syntax and git diff --check passed.
- Capture checked from the main/Narrative dashboard and Local Character Overview.
- The disposable fixture server was force-stopped by its verified PID before reset;
  production processes were not touched. An attempted fixture reset while that old
  server was still alive failed; the repeat after verified stop passed.
- Windows runtime paths use platform overrides; Darwin configuration loading
  preserves normal startup with empty local runtime paths.

- Real capture published pilot issue #42 and commit-pinned image successfully.
  Visual inspection exposed leftover plan-approval help text and oversized checkbox
  styling; corrected in the parent feature before worker execution. Original issue
  capture remains unchanged; a supplemental screenshot/comment records the new
  pilot base. This is a setup correction, not a scope change to the queued-work task.

- First real pilot correctly paused: nested Codex could not read account quota,
  despite successful host/app reads. Added expiring host-reading reuse and explicit
  native app-reading import; reserve/unknown guards remain. Repeating the pilot.

- Pilot discovery: sandboxed gh also cannot access the valid host credential store.
  No human reauthentication is needed. WP6 gained a bounded private loopback
  credential bridge (service/client/router) for scoped GitHub operations and pinned
  evidence. Draft push imports a bundle in a protected bare directory rather than
  executing agent-controlled Git hooks/config with host credentials. Normal pickup
  consequently requires the local Zet server as well as the PC/Codex app. The pilot
  uses a disposable normal-user bridge host, without loading a live ZetApp/library.

- Third pilot verified/opened both real screenshots through the bridge, then paused
  on protected Git metadata and missing Python packages. The manual test driver
  had forced -a never, unlike Joe's saved on-request/automatic-review profile.
  Retrying with that existing profile, a verified worktree-local environment, and
  helper selection/bootstrap of declared main dependencies. No broad sandbox
  permissions or production/library access were added.
- Shared bridge/status lifecycle is now independent of default universe replacement.

- Pilot now produced one scoped help-text commit and draft PR #43. Both images
  were opened/hash verified and browser after-inspection passed. Its sandbox
  baseline exposed two fixture leaks: machine-local queue receipts and compiler
  config lookup falling back to repository config. Corrected active config binding
  and fixture-only queue-state storage; no live library access or new scenarios.
  Revalidating with ZET_WORKER_MODE=1 before final ready delivery.

- Worker-mode baseline passed after isolation repair: 3 scenarios, 25.3s.
- Regular native automation zet-github-pickup is configured PAUSED at 30 minutes.
  Its prompt gates on merged main and the local credential bridge, archives idle
  chats and limits notifications to meaningful changes.
- Latest actual pilot retry paused at 7% capacity; app subsequently reports 4%,
  below the approved 10% reserve, resetting 2026-10-13 10:59 AM Pacific. The text
  commit and draft PR #43 are preserved. Full pilot ready-delivery remains pending;
  production adoption and three-delivery final cutover are not complete.
- Temporary continuation will resume the remaining pilot/gates after capacity reset.

- October 13 continuation: fresh capacity exceeds the 10% reserve. Retained #42
  needed a trusted repair reply under needs-input (ready alone correctly skips an
  existing PR); supplied that reply and resumed its original branch/commit.
- Focused disposable bridge checks passed: bearer/loopback enforcement, scoped
  issue writes, pinned-evidence/origin restrictions, successor registry ownership,
  protected transfer Git roots and existing-PR description refresh. Redelivery now
  updates title/body, retaining the original issue reference.
- Read-only Kanban inventory: three Planning tasks (browser information, normalized
  browser context, bounded privacy-safe diagnostics), Costume Wizard in Executing,
  two Done tasks. No migration/data writes; inspect actual review evidence before
  deliberately migrating the unfinished work.
- Saved pickup prompt now explicitly creates/reuses a managed isolated worktree
  before claiming. Native automation remains paused pending the real pilot.
- Pilot at 72f64f0 passed its dialog inspection and all three scenario assertions
  (2.8s/15.3s/3.5s), but Windows restricted-job cleanup hung. Stopped only the
  identity-verified fixture process tree; recorded failed validation, not delivery.
  Repaired durable log streaming/owned-tree timeout and verified that path with a
  disposable parent/child sleeper. Retrying exact validation with saved automatic
  review for Windows process cleanup; no writable-root or approval-policy changes.
- Retained recovery also exposed host/GitHub clock skew in the timestamp fallback.
  Recovery now records the latest existing GitHub comment ID before awaiting the
  repair reply, so resumption uses an ordered server-owned marker. Disposable
  coordination checks passed again; original claims/work remain intact.
