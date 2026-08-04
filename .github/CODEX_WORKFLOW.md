# Codex issue workflow

## Start work

Adding `codex-ready` authorizes immediate implementation. It does not start Codex automatically. Start a dedicated Codex task with:

> Take the next open `codex-ready` issue in `Joebok/Zet`. Claim it, implement it, run all checks, and open a ready PR. Do not merge.

Codex selects the lowest `priority:<N>` value first, then the oldest eligible issue. An eligible issue is open, unassigned, not blocked by an open dependency, and has no matching branch or pull request.

## States

| State | Meaning |
| --- | --- |
| `codex-ready` | Approved for immediate implementation. |
| `in-progress` | Claimed in an isolated `codex/issue-<number>-<slug>` worktree and branch. |
| `needs-input` | Work is paused on one material decision. |
| `needs-review` | Tests and CI passed; the pull request is ready for human review. |

Codex removes the previous workflow label when applying the next one. A closed, unmerged pull request returns the issue to `codex-ready`. Merging a pull request with `Closes #<number>` closes the issue.

## Clarification protocol

Codex first checks the issue, repository, tests, and existing conventions. If a material decision remains, it stops before making that decision, preserves the worktree and branch, replaces `in-progress` with `needs-input`, and asks one concise question in both the Codex task and the issue.

The issue comment contains:

- the blocking decision;
- the viable choices;
- Codex's recommended default; and
- the implementation impact of each choice.

Answer in the Codex task, or answer on GitHub and return to the same task with `Resume issue #<number>`. Codex reads the response, replaces `needs-input` with `in-progress`, and continues.

## Delivery gate

Codex opens a draft pull request early with `Closes #<number>`, runs the complete Python and browser suites, monitors CI, fixes failures, and performs a final review. Only then does it mark the pull request ready and replace `in-progress` with `needs-review`.

The human reviewer owns merging. This private repository cannot currently enforce branch protection, so a green CI run and human approval are mandatory process rules.
