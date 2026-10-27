# Prompt packet marker validation
Status: complete
Related issue/specification: reported Head-Image Edit batch `20261023_070525_864928`.

## Goal and current behavior
Current rear-view operations contain valid `ZET:PROMPT_PACKET` declarations.
The static renderer extracts declarations from the task template before substitution,
but rejects declarations inserted through operation metadata before the later
`PromptTemplateService` extraction can run. The error names no marker or source.
The task-template editor uses the plain-source compatibility path; this failure
is a compiler ordering defect, not invalid character authoring.

## Impact and constraints
Owners: `Scripts/Build_Static_Final_Prompt.py`,
`zet/services/prompt_packet_metadata.py`;
knowledge owner: `Docs/COMPONENTS/PROMPTS.md`. No serialized schema changes,
reference reordering, master edits, batch writes, inference, or new maintained tests.
Source maps must describe the emitted prompt after declarations are removed.

## Luna sized work packets
### WP1 — Extract substituted declarations before final validation
- Dependencies: none.
- Files/interfaces: the two compiler/parser files above.
- Work: preserve fragment whitespace during extraction, retain all declarations in
  the source map, and identify residual markers with prompt line/source context.
- Acceptance: real rear-view operations compile without leaking metadata;
  unknown markers still fail with actionable details.
- Validation: disposable renderer and real all-view Head-Image Edit checks.
- Status: complete.

### WP2 — Verify and document the corrected contract
- Dependencies: WP1.
- Files: `Docs/COMPONENTS/PROMPTS.md`, this plan.
- Acceptance: declarations survive in maps, mapped lines remain correct, and
  approved isolated regression scenarios pass. No production data changes.
- Validation: `npm.cmd run test:e2e`, `git diff --check`, final diff review.
- Status: complete.

## Validation and progress
Python 3.14.6 verified with `python3`. Production batch/spec and Youth Character.md
were read only. The supplied HTTPS URL is unavailable to the web reader; local
authoritative templates contain the three rear-view declarations causing failure.

Disposable `python3 -B test-results/prompt-packet-marker/check.py` passed: original
BACK operation reproduces the old error; mixed task-template/metadata/section
declarations merge; fragment whitespace and prompt line maps survive; malformed
JSON fails; both renderers identify multiple residual markers, with mapped source
context where available. Sixteen generation/analysis compiles of private current
Youth masters passed across all eight views; the ten previously unaffected prompts
are byte-identical to the old renderer's outputs. The private universe uses a
read-only SQLite backup and a copied reference image. Production Character.md bytes
are unchanged. No live model or rendering service was used.

## Risks
Removing declarations after map construction would shift source-map prompt lines;
extract from fragments before constructing the map. Preserve whitespace around
inline substitutions and preserve existing top-level declarations.

## Final results
The renderer now consumes substituted packet declarations before marker validation
and maps only emitted prose. Actual residual markers identify their text, prompt
line, and available source file/section. The parser supports whitespace-preserving
fragment extraction; the prompt component documentation describes this contract.
`npm.cmd run test:e2e` passed all four approved scenarios in 40.3 seconds.
Changed Python AST checks and `git diff --check` passed; the final diff contains
only the two compiler/parser files, prompt documentation, and this plan.
No maintained tests or dependencies were added. Production deployment/restart
and live inference were not performed.
