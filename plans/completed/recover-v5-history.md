# Recover missing V5 history into main
Status: complete (local recovery and approved remote publication)
Related issue/specification: user's request to recover xZet_v5 commits, especially testing changes.

## Goal
Make every commit reachable from xZet_v5's V5 branch reachable from Zet's local main, preserving the documentation move and existing uncommitted work. Remote publication requires approval under the working agreements.

## Current behavior
Zet main is `2d0e1a9`; origin/main is `58ef33f`. xZet_v5 HEAD is `257fdeb`; the fetched V5 branch is `4827cf3`, which merges origin/main into V5. There are 26 commits on the V5 branch absent from Zet main. Merging main into V5 did not integrate V5 into main.

## Desired behavior
Local main contains the original V5 commit history, Kanban integration, and testing changes. `tests/e2e` and `tests/library` match the source. The former Python/browser suites and CI workflows remain retired as intended by the recovered commits.

## Impact analysis
The merge restores changes to backend task forwarding, web task capture/context, configuration, and testing infrastructure. The only detected merge conflicts are three new documents under the renamed Docs directory. Documentation owners: Docs/Testing.md, Docs/DEVELOPMENT.md, Docs/CODE_MAP.md, Docs/INDEX.md, and AGENTS.md. Runtime storage and library data are outside scope.

## Invariants and constraints
Preserve the original commits; do not cherry-pick only tests or replace main with V5. Preserve user edits to AGENTS.md, README.md, Docs, and plans. No installations, live AI checks, new tests, or external writes without approval. Use the existing three fast scenarios, serially, against isolated fixtures.

## Implementation steps
### WP1 — Integrate existing history
- Dependencies: none.
- Files/interfaces: Git main and recovery references; merged source files; three document-location conflicts.
- Work: record recovery backups, temporarily stash only modified tracked documentation, merge the fetched V5 tip, resolve new documents into the current Docs knowledge directory, restore tracked user edits.
- Acceptance: both original main and V5 tips are ancestors of main; source testing and application trees are preserved; no unresolved conflicts or missing user files.
- Validation: Git ancestry checks; targeted source tree comparisons; original file hashes/backup comparison.
- Status: complete.

### WP2 — Reconcile testing navigation
- Dependencies: WP1.
- Files/interfaces: AGENTS.md, Docs/INDEX.md, Docs/DEVELOPMENT.md, Docs/CODE_MAP.md.
- Work: preserve new knowledge documentation while identifying the recovered approved E2E baseline and retired test references.
- Acceptance: current testing instructions lead to npm run test:e2e and keep live checks explicitly opt-in.
- Validation: inspect commands and links against recovered package/config/test files.
- Status: complete.

### WP3 — Validate and report publication boundary
- Dependencies: WP1, WP2.
- Files/interfaces: tests/e2e, tests/library, package scripts, Git history, this plan.
- Work: run npm run test:e2e; verify all source commits and application/test blobs; review diff and preserve remaining user edits. Record results and archive the plan if local integration is complete.
- Acceptance: three fast scenarios pass, or a concrete failure is reported; main contains all missing commits; remote push remains an explicit next step for approval.
- Validation: npm run test:e2e; git diff --check; git merge-base --is-ancestor; git diff between source and main for application/testing files.
- Status: complete.

## Risks and alternatives
Directory rename inference relocates newly added Docs files into Docs-Joe; preserve their original Docs paths so recovered links and current knowledge navigation work. User documentation changes were written against the older test suite and must be reconciled without removing their unrelated content.

## Progress and decisions
- Fetched origin successfully. xZet_v5 has no uncommitted changes; its HEAD is behind the remote V5 tip, whose additional history is the merge of main and its policy branch.
- Git merge-tree found only document-location conflicts: Kanban_Integration.md, Test_Stabilization.md, Testing.md.
- Python 3.14.6 verified; existing Node/npm and Playwright are available. No packages installed.
- Backed up 22 original documentation/plan files and the pre-merge patch/status under `.git/recovery/v5-main-20261011`. Preserved the original main tip in `codex/recovery-main-before-v5-20261011`. The temporary tracked-documentation stash remains as an additional backup and was applied successfully.
- Merged V5 with original main in `fda6aac` (parents `2d0e1a9`, `4827cf3`). Resolved only the three document-location conflicts into `Docs`, preserving source contents and the previous Docs-Joe relocation.
- Restored user modifications to AGENTS.md and README.md without conflicts. Preserved the other existing untracked knowledge and plans. Reconciled testing navigation in AGENTS.md, Docs/INDEX.md, Docs/CODE_MAP.md, and Docs/DEVELOPMENT.md; these remain uncommitted with the pre-existing knowledge work.
- Source testing commits recovered include `7d2a316` (Test Stabilization), `b3d695a` (Testing Strategy Re-Alignment), `3f6acbe` (Testing Changes - E2E simplification), and `257fdeb` (codex gate update). Later commits intentionally retire the earlier broad testing suites.

### Recovered commit inventory
```text
2e6c912 Add configured Kanban task forwarding through ZetApp
6b6aeff Merge pull request #31 from Joebok/codex/packet-04-task-forwarding
ee74659 Add dashboard task capture with durable frozen drafts
a07fdda Keep task capture usable when browser storage is blocked
b7b5db4 Remove the CI requirements
98651be Merge pull request #33 from Joebok/codex/packet-05-task-capture
6d1a79f Capture and restore local pipeline task context
0107de1 Document local context rollout and capture batch UI evidence
70c8a14 Merge pull request #35 from Joebok/codex/packet-06-local-task-context
b837cf1 Add story and Narrative task capture and restoration
a9b1c33 Trim shared capture template trailing whitespace
dfcaa7e Merge pull request #36 from Joebok/codex/packet-07-story-task-context
7d2a316 Test Stabilization
9d3ad76 Capture auxiliary workspace context and upload task screenshots
a570d3d Preserve pending gate identifiers and link reruns to their displayed run
c26e421 Merge pull request #37 from Joebok/codex/packet-08-auxiliary-task-capture
2ce697b Retire markdown To Do in favor of contextual Kanban reports
cada962 Clarify that captured tickets carry Return to Zet links
8c3e8a7 Merge pull request #38 from Joebok/codex/packet-09-retire-markdown-todo
ef05195 Translate screenshot uploads to the merged Kanban intake contract
d9da73c Merge pull request #39 from Joebok/codex/fix-screenshot-intake-contract
8f705ed Kanban Integration Fixes
b3d695a Testing Strategy Re-Alignment
3f6acbe Testing Changes - E2E simplification
257fdeb codex gate update
4827cf3 Merge branch 'main' into V5-Re-Alignment-to-Local-Image-Generation
```

## Validation
- `npm.cmd run test:e2e`: **3 passed in 21.5s**, serially against the isolated Test universe. Live check not run.
- `git diff --check` and the staged merge check: passed.
- Ancestry verification for each of the 26 recovered commits, original main, and xZet_v5 HEAD: passed. `git rev-list --count main..origin/V5-Re-Alignment-to-Local-Image-Generation`: **0**.
- Source comparisons of `zet`, `Scripts`, `tests`, package/lock files, Playwright configs, `.github`, `.gitignore`, and config.toml against the index and working tree: exact match.
- All three new documents retain their source contents. No unresolved conflicts.
- Original documentation manifest: 16 unaffected files preserved byte-for-byte. The remaining six are the two tracked documents with restored user changes, three knowledge documents intentionally reconciled with the testing overhaul, and this recovery plan.

## Final results
Local main contains every missing source commit at `fda6aac` and is ahead of origin/main by 28 commits (26 recovered commits, the original documentation move, and the integration merge). Application/testing changes are entirely recovered history; no new tests or application fixes were introduced. The existing user documentation work remains uncommitted, with the necessary testing-navigation updates. xZet_v5 was not changed.

After explicit user approval, `git push origin main` succeeded, advancing origin/main from `58ef33f` to `fda6aac`. `git ls-remote origin refs/heads/main` and `git rev-parse main` both returned `fda6aac9caa6525c5d686c38cc75e6076d4f222a`, confirming remote publication. Local main and origin/main are synchronized. Publication included committed history only; the existing uncommitted documentation work remains local. The backup branch, file backup, and stash are retained.
