# Saved local pickup prompt

Work the authorized GitHub queue for Joebok/Zet, one implementation at a time.
Read .github/CODEX_WORKFLOW.md and AGENTS.md and obey their scope/test boundaries.
This is local development work; never merge a PR or deploy production.

Require the local Zet server and its private loopback worker bridge. Do not
reauthenticate or expose GitHub credentials inside the sandbox. Use helper context,
evidence, deliver and ready actions for issue reads, pinned images, draft PR push
and ready transition. If the bridge is unavailable, report the retained queue once.

Verify Python 3 and set ZET_WORKER_MODE=1 for all shell work. Run the coordinator
from C:/Users/Joe/Projects/Zet with state root C:/Users/Joe/Projects/Zet_Runtime/state;
it must not construct ZetApp or load repository config.toml. Run issue_worker
reconcile to record validated merged deliveries, then inspect status for active
ownership. A needs-review or completed record is history, not a reason to skip
the queue. Create an attached managed worktree from fetched origin/main for new
work, then ALWAYS run issue_worker claim --worktree <isolated-checkout> with the
10% reserve. The explicit target must be an isolated worktree, never the primary
checkout. An active in-progress claim may be polled using its existing worktree
target without attaching or taking it over. The helper decides busy/attention,
trusted resumption, review feedback and new work. Only after selection use its
returned issue, token, branch and coding worktree. Preserve retained worktrees;
do not attach another chat's worktree merely to inspect status or poll the queue.
If idle, busy or quota-limited, exit quietly after recording the actual result;
never independently change labels to bypass a claim or quota guard. A waiting
review does not prevent another eligible issue from being claimed. Record time,
reconciliation and claim outcome in automation memory, and leave a concise final
run result. When the claim outcome is idle with no eligible work, archive the run
chat after recording the result. Keep chats visible for busy, quota-limited,
active, or attention-needed outcomes. Emit attention notifications only for the
meaningful changes described below.
If quota is unknown, use the desktop app's read-only get_usage_limits tool and save
its actual JSON reading to an ignored file. Import that reading with issue_worker
usage --input-file before retrying claim. Never estimate capacity or replace a
quota failure with allowed=true. Fresh host readings expire after five minutes.
For an interrupted claim, report the retained work and needed recovery once.

For new work, fetch origin/main and create the returned branch in the isolated
worktree. For resumption, inspect and use the retained worktree/branch. Read the
original issue, all trusted comments and actual attached images. Preserve the
original intent in the active plan, implementation and acceptance review. Download
public screenshot URLs into ignored test-results and open them; compare supplied
hashes. If essential evidence cannot be read, explain the missing evidence and ask
one material question instead of guessing a visual fix.

Prepare the existing disposable inspection fixture and worktree-local Python
environment using the helper. Keep the saved automatic review profile for scoped
Git metadata operations; never force approval_policy=never or grant production
access to work around protected .git paths. Implement only the reported
scope, without subagents, new dependencies, new permanent tests, real library/queue
access, live models or rendering. Add a draft PR with Closes #N. Heartbeat the claim
between stages. Recheck quota through the helper before further model-heavy work;
at exhaustion checkpoint usage-wait with a quota explanation and retain all work.

Commit the change and run the helper's validate command. A failed test starts a
diagnosis/repair cycle; keep the claim in-progress rather than ending the run.
Follow CODEX_WORKFLOW.md's "Validation failures and escalation" rules: inspect
retained logs/artifacts and implicated code, record an evidence-backed diagnosis,
attempt a minimal scoped repair, and rerun the approved checks. Continue from new
failure evidence while supported scoped next steps and quota remain. Do not mask
product defects by weakening/skipping tests or changing timeouts without evidence.
Before escalating, at least one scoped repair must have been attempted unless a
demonstrated access, authority, prerequisite, or quota constraint prevents it.
Every escalation must provide a retained message file with the failed command and
revision, evidence paths, diagnosis, attempted repairs and results (or why an
attempt was impossible), the exact blocker and why authorized alternatives cannot
resolve it, and the action needed to resume. Use needs-input for a specific missing
decision/access/authority, usage-wait for quota, and stopped only for an execution
or prerequisite failure that cannot be repaired within scope. A test failure,
unknown cause, or failed first repair alone does not justify stopping or requiring
operator recovery. Never end with only "validation failed" or "investigate next".
On Windows, the restricted process job can prevent Playwright from cleaning up its
own generated server. If needed, request the saved automatic review for the exact
disposable helper validation command; do not add writable roots or bypass a failed
result. Validation streams to a retained log and bounds its own process tree.
Review the final diff and show that the original reported behavior is corrected;
agent-authored criteria and passing baseline tests are supporting evidence.
Synchronize the active plan and affected documentation. Use helper deliver for the validated commit, then helper ready to
mark the PR ready and checkpoint needs-review with its PR number and a concise
issue comment. If blocked on a material decision, checkpoint needs-input with one
question, choices, recommendation and impact; trusted replies are picked up later.

Only notify Joe on a new ready PR, real blocker, required recovery or meaningful
failure. Do not emit repetitive progress summaries when the queue is unchanged.
