# Tsaeytte quarter-view ears and Head-Image ranking
Status: complete

## Goal and current behavior
Implement Joe's approved plan for batch `20261019_170553_311743`. FL-005 and
FR-004 visibly shorten the referenced elf ears. Head's source-preserving compiler
omits general head facts, so the correction belongs in view overrides. The batch
uses accepted revision `8e303865d9004247bb4aae88377abfc0`; master edits alone do
not update it. Ranking currently uses generic visual comparison guidance.

## Constraints and impact
Preserve image bytes, candidate seeds, selections, frozen render inputs, historical
revisions and rankings. No live inference, reranking, restart, deployment, new
dependencies or maintained tests. No API/schema changes. Only Head ranking text
changes in code. Affected documentation owner: Docs/COMPONENTS/LOCAL_CHARACTERS.md.

## Work packets
### WP1 — Master character wording
- File: H:/Zet/Zet_Library_v5/Moonsea/Characters/Tsaeytte/Adult/Character.md.
- Dependencies: none. Add the approved `[head:fl,fr]` anatomy instruction inside
  HEAD_DESCRIPTION_VIEW_OVERRIDES; preserve other text and reference tags.
- Acceptance/validation: disposable eight-view previews; added text only in front
  quarters, selected head first and matching ear reference second.
- Status: complete.

### WP2 — Accepted batch child
- Interface: LocalTemplateRevisionService manual start/accept through existing API.
- Dependencies: WP1. Apply the same localized addition to the active Character
  source while preserving all other batch sources; accept compiled child.
- Acceptance/validation: READY accepted child, eight previews, active pointer;
  compare saved candidate data, rankings, image hashes and historical revisions.
- Status: complete.

### WP3 — Head ranking anatomy guidance
- File: zet/services/local_head_image_service.py.
- Dependencies: none. Compare distinctive visible anatomy with mapped references;
  penalize shortened/rounded ears when elongated pointed ears are established;
  respect occlusion and target angle, prioritize anatomy over polish, require
  accurate reasons. Keep character-independent and advisory.
- Acceptance/validation: disposable prepared-response request/result checks;
  npm.cmd run test:e2e -- --grep "character-to-costume"; git diff --check.
- Status: complete.

## Progress and validation
Implemented the single approved instruction in the master, preserving all other
bytes including original line endings. Created manual review
`b651f208ad294ed29c8d32359330381f` from the existing active revision and accepted
child `8034ed877325431ba1c4fafe2913f2e0` through the running dashboard's existing
revision API. The child's Character text equals the current master; all other
source text equals the parent. Both review and accepted child compiled eight
previews: the addition appears only in front quarters, with selected FRONT first
and the matching ear reference second. Master and batch validation therefore
share these previews; no extra preview artifacts were retained in the library.

The initial standalone disposable preview attempt could not load production
config because of the issue-worker guard. Validation used the running dashboard
service instead; the guard was not bypassed. The accepted child is READY and the
active pointer matches it. Baseline comparisons confirmed unchanged candidate
records (including frozen inputs/seeds), rankings, selections, front anchor,
rendered image hashes and all pre-existing revision file hashes.

Disposable prepared-response checks passed against the real Head ranking method
and shared Luna request builder: anatomy instructions, reference deduplication and
ordering, per-candidate mapping, result propagation and incomplete-result
rejection. Model calls and harvest/prompt-improvement side effects were stubbed;
no production rankings were modified. Scripts and baseline evidence remain ignored
under test-results, not maintained tests.

`npm.cmd run test:e2e -- --grep "character-to-costume"` passed (1 test, 16.9s).
Python AST parsing and `git diff --check` passed. Final diff review found only the
intended ranking guidance, component documentation and this completed plan in the
repository; the master and accepted child are library-owned changes.

No live inference, reranking, deployment or restart occurred. Future Generate or
Regen actions need Recompile to pick up the accepted wording. The ranking code
will apply when loaded by the runtime and used for a later evaluation. Image
quality and real-model ranking accuracy require later human review of separately
requested renders/evaluation.
