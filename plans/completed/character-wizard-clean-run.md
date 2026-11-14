# Character Wizard clean run on Zet Test

Status: complete. Live acceptance passed on Zet Test on 2026-11-14.

## Goal

Create a fresh character with Luna, publish the wizard's generated text as-is, and harvest one completed Draft FRONT image each from Body Reference (`body-reference`, the body-image job) and Head Image Edit (`head-image-edit`, no reference). Stop at functional success. Image quality, ranking, refinement, selection, locking and downstream pipelines are outside this run.

## Reproduction and inputs

- Use [Zet Test](http://localhost:8082/?page=onboarding), universe `ZetTester`, phase `Adult`, and vision model `codex:gpt-6-luna`. Use `C:\Users\Joe\Projects\Zet_Tester\cases\images\Tsaeytte.png` in wizard Reference 1 only. Fixture SHA-256: `8A0980122F2F39FE627924F7AB1578F73F70F950275746BC44EB3BEF9F1CF0CC`.
- Start with `Testia 1`. Check the published character list and the wizard's **Resume draft** list before each fresh attempt. Treat a name used by any earlier attempt as taken; increment to `Testia 2`, `Testia 3`, etc. Keep failed drafts and their evidence. `Testia 1` was free at diagnosis; recheck after deployment.
- Enter the fixture's metadata when the wizard prompts for it: **High Elf**, `Feminine adult woman`. These are form inputs from the existing Tsaeytte character, not edits to Luna's observations. Leave optional caption, direction and style fallback empty. Leave Body, Head and hair, and the generated Head-Image Edit starter sections untouched.
- The old unnumbered `Testia / Adult` draft on revision `7c663cb7` (session `e182df4835eb437b8ef810821a98b564`) reproduced the reported error in both sections. Its image hash differs from the supplied fixture, so use it only as transport evidence. Both receipts say the worker answered `SUCCESS` but proxy execution was `FAILED`: `AI_82b87b46f059416aa080dbaf0dda579d` and `AI_2157611ec5c44cf0a644b10224a88ffd`.

## Work packets

### WP1 - Diagnose the first failure

- Dependencies: saved Test evidence and source at the reported release. Files/interfaces: `zet/services/character_wizard_sections.py`, `zet/services/ai_job_service.py`, AI Proxy `file_proxy/ai_worker.py`, `engine.py` and `validation.py`.
- Findings: the wizard requests plain text without a response schema and expects UTF-8 bullets. Zet advertises `answer.json` in both envelopes. AI Proxy validates all `.json` files after the worker runs and rejects that plain text. A disposable check against the real validator reproduced the exact message, then accepted the same bytes as `answer.txt` and accepted valid structured JSON as `answer.json`. The saved answer bodies were not needed for this replay.
- Acceptance/validation: Test GETs, receipt inspection and disposable validator replay agree on the failing boundary. Status: complete.

### WP2 - Correct and verify the output contract locally

- Dependencies: WP1. Files/interfaces: `zet/services/ai_job_service.py` and the affected [AI job documentation](../../Docs/COMPONENTS/AI_JOBS.md). For new requests, use `answer.txt` when no schema is supplied and `answer.json` for structured outputs. Set the same filename in `ask_manifest.json` and `ai_request.json`; collect using the advertised filename. Preserve immutable requests, attempt ownership, checksum/inventory validation, structured validation and legacy collection. No AI Proxy code change is needed for this diagnosis.
- Acceptance/validation: disposable transport replay checks plain-text submit, worker output and collection; checks that a structured request still uses JSON and JSON validation. Run `npm.cmd run test:e2e` against isolated fixtures and `git diff --check`. Fast fixtures do not cover live Luna wizard publication or live FRONT renders. No permanent scenario is needed.
- Status: complete. The disposable replay used the supplied fixture and Zet's submit/result methods, the real AI Proxy worker and validator, and a simulated provider response. Plain text and valid structured content arrived at the caller; schema-invalid content was rejected. `npm.cmd run test:e2e` passed 4/4 (42.6s).

### WP3 - Stop for Joe's Test release update

- Dependencies: WP2. Interfaces: [Test release updater](../../Update_Test.ps1), `/api/health`, and the dashboard revision marker. Provide the validated diff or revision and the observed check results. Stop for Joe to make the fix available on `origin/main` and deploy via `./Update_Test.ps1 -Action Deploy`. The script deploys merged `origin/main`; an unmerged local patch is insufficient.
- Acceptance/validation: after Joe confirms the update, check that port 8082 is ready and serving a revision containing the fix. Recheck `ZetTester`, the fixture and the next available name. Do not run against the old revision or update/restart the release on Joe's behalf.
- Status: complete. Joe deployed revision `44108749369fc563f3c099cb946d53953e7374e6`; port 8082 reported ready and the deployed source contained the fix.

### WP4 - Run the wizard and both FRONT jobs

- Dependencies: WP3; Test inference available. Interfaces: [operator guide](../../Docs/CHARACTER_WIZARD_GUIDE.md), `/api/character-wizard`, and the Body Reference and Head Image Edit asset container boards.
- Start a fresh wizard with the fixed inputs. Wait for both **Body** and **Head and hair** to show **Ready** with observations and no error. Enter the fixture metadata, click **Preview Character.md**, then **Create character** with no changes to the generated sections. Verify publication succeeded and the new name and phase are selected. Stop if any step fails; manual text or another model would not demonstrate the requested path.
- Open **Assets > Body-Reference > Open FRONT Candidate Board**. Use **Preview Prompt** to verify compilation; run **Draft 1** and wait for one completed candidate with a loadable image and no job or card error.
- Open **Assets > Head Image Edit > Open FRONT Candidate Board**. Keep **Phase Change** off, with no saved or uploaded FRONT source. Verify **Preview Prompt** shows no reference inputs. Run **Draft 1** and require the same completion evidence. The wizard upload is evidence for Luna only; do not attach it or the Body output to this render.
- Acceptance/validation: record revision, character and phase, reference hash, wizard session ID and publication outcome, both candidate/job IDs, terminal status, loadability and the Head reference count. Do not evaluate the images or launch quality review, retry, refinement or additional views as part of a passing attempt.
- Status: complete. The live wizard published the untouched generated sections; both FRONT jobs completed and their PNGs decoded successfully.

### WP5 - Repeat on failure, or hand off on success

- Dependencies: WP4 outcome. Files/interfaces: this plan and the operator guide; whatever owner WP4 evidence identifies.
- On failure, record the first failing step, exact error, inputs and IDs. For a wizard failure, compare request/answer filenames and schemas, provider result, proxy result and harvest receipt. For a FRONT failure, trace prompt compilation, frozen reference inputs, submission, provider outcome and owned receipt/candidate. If a service is unavailable, record the blocker and wait for recovery. For a defect, make the smallest fix at the proven boundary, replay it locally, and return to WP3. Wait for Joe after every fix, then rerun the whole journey with the next numbered name. Preserve Test evidence and leave production unchanged.
- After success, record live results here, verify the guide's labels and steps on the passing release, and move the plan to `plans/completed/`. Hand Zet_Tester the stable guide link and evidence; do not modify Zet_Tester as part of this task.
- Status: complete. No further fix or retry was needed. The guide's labels were checked against deployed dashboard source, and the live actions ran through the APIs used by those controls.

## Progress and validation

- Live run: `ZetTester / Testia 1 / Adult`, Luna (`codex:gpt-6-luna`), session `a72f66649fa74767b2cab180c3396c32`. The saved upload SHA-256 matched the fixture above. Both section receipts were `APPLIED` with no notice, the preview had no errors, and the wizard reached `ACCEPTED` with `Character.md` present.
- Body Reference FRONT Draft 1: candidate `299503e821cc4eaf9804054ff3e93eda`, job `45732ac2c5c24e05b97803c85a9cf4b7`. `COMPLETE` with no error, zero inputs, HTTP 200, decoded PNG 832 × 1248.
- Head Image Edit FRONT Draft 1: candidate `6e144ff13a5643d8aef787be893c54ea`, job `7a5ce900cdd749c18076bb2464fc67ab`. Phase Change off; zero reference images in both the preview and frozen render request. `COMPLETE` with no error, HTTP 200, decoded PNG 1024 × 1024.
- No image quality review, ranking, selection or locking was performed. No separate browser click-through was run.
- Boundaries: [AI jobs](../../Docs/COMPONENTS/AI_JOBS.md), [invariants](../../Docs/INVARIANTS.md), [test policy](../../Docs/Testing.md), and [Test release setup](../../Docs/DEVELOPMENT.md#isolated-test-release). Keep isolated checks off the live queue; use only Zet Test for the live journey when shared inference is idle. No production updates, dependency changes or coverage expansion.
