# Saved local pickup prompt

Work the authorized GitHub queue for Joebok/Zet, one implementation at a time.
Read .github/CODEX_WORKFLOW.md and AGENTS.md and obey their scope/test boundaries.
This is local development work; never merge a PR or deploy production.

Start by verifying Python 3 and running the issue_worker claim command from this
isolated worktree with state root C:/Users/Joe/Projects/Zet_Runtime/state and a 10%
usage reserve. Set ZET_WORKER_MODE=1 for all shell work. Do not construct ZetApp or
load repository config.toml to coordinate tasks. Use the helper's returned claim,
issue, token, branch and retained worktree. If idle, busy, quota-limited or unchanged,
exit quietly; never independently change labels to bypass a claim or quota guard.
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

Prepare the existing disposable inspection fixture. Implement only the reported
scope, without subagents, new dependencies, new permanent tests, real library/queue
access, live models or rendering. Add a draft PR with Closes #N. Heartbeat the claim
between stages. Recheck quota through the helper before further model-heavy work;
at exhaustion checkpoint usage-wait with a quota explanation and retain all work.

Commit the change and run the helper's validate command. Fix failures within scope.
Review the final diff and show that the original reported behavior is corrected;
agent-authored criteria and passing baseline tests are supporting evidence.
Synchronize the active plan and affected documentation. Push the validated commit,
mark the PR ready and checkpoint needs-review with its PR number and a concise
issue comment. If blocked on a material decision, checkpoint needs-input with one
question, choices, recommendation and impact; trusted replies are picked up later.

Only notify Joe on a new ready PR, real blocker, required recovery or meaningful
failure. Do not emit repetitive progress summaries when the queue is unchanged.
