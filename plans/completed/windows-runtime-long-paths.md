# Windows runtime checkout paths
Status: complete

## Goal and verified cause
Template publication checks out the complete tracked tree into a deeply nested
private runtime directory. Git for Windows has no configured core.longpaths here;
checkout fails on tracked output paths before a publication commit is saved.
Release staging also checks out the complete tree without enabling long paths.

## Impact and constraints
Owners: TemplatePublicationService._publish and deploy_release.stage.
Documentation: Docs/GitHub_Task_Workflow.md. No receipt/schema changes, library
writes, tracked output removal, external publication or production restart.
Retain captured bytes and existing failed attempts; publication retry creates a
fresh checkout before its commit checkpoint. Existing staged-release recovery is
outside this change.

## WP1 — Enable long paths in private Git checkouts
- Dependencies: none.
- Files: zet/services/template_publication_service.py,
  zet/scripts/deploy_release.py, Docs/GitHub_Task_Workflow.md.
- Work: configure core.longpaths before publication checkout (including retained
  checkouts); configure staged clones before their first checkout.
- Acceptance: a disposable Windows checkout exceeding 260 characters succeeds
  with the same commands; repository-global/user Git config remains unchanged.
- Validation: disposable Git fixture, Python syntax, approved npm run test:e2e,
  git diff --check and final diff review.
- Status: complete.

## Results
- Disposable Windows repository reproduced `Filename too long` with long-path
  support disabled. The actual publication method reached validation with its
  exact captured bytes and tracked output intact at paths exceeding 260 characters.
- The first disposable run exposed clone-initialization hook paths exceeding the
  limit as well; both clone commands now enable long paths from process startup,
  before repository-local configuration can be written.
- The actual release clone command and detached checkout succeeded beyond 260
  characters. No network fetch, push, production restart or global configuration
  change occurred. Disposable script is ignored under test-results/long-path-check.
- Python AST syntax checks passed for both changed modules.
- `npm.cmd run test:e2e`: all four approved scenarios passed (44.1 seconds).
- `git diff --check` and final diff review passed; only the intended source,
  workflow documentation and this plan changed.

## Verification limits
No maintained deployment scenario exists. Disposable checks establish Git path
handling; E2E provides application regression coverage, not live deployment proof.
The running release requires a separate handoff to consume the local fix.
