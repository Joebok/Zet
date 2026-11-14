# Character Wizard intake metadata

Status - complete

1. Add wizard intake fields and validate the existing multipart request in the wizard service. Persist the inputs before the first section attempt. Check invalid requests and old draft compatibility.
2. Use the saved values in both section prompts, map Undecided to a neutral Body Reference subject and update the operator guide. Depends on packet 1. Verify prompt context, subsequent refinement, publication and both FRONT compilers with isolated data.
3. Run the approved fast E2E suite and review the diff. Record results and archive this plan. Live output remains for Joe's Test review.

The wizard session and Character.md retain their current fields and versions. Relevant owners are the Character Wizard entry in `Docs/CODE_MAP.md`, shared AI Jobs, the species catalog, the Body Reference compiler and the operator guide. No change to queue ownership, publication fencing, references or render orchestration is planned.

The starting form and multipart creation API save both choices before the first interview. Both section prompts use the species display name and saved presentation. The Body compiler treats Undecided as a neutral subject and retains the default fitment policy. The operator guide covers starting choices and refinement.

The isolated API check verified invalid inputs create no session or queued attempt, older client drafts resume, both prompts receive saved context, saved changes reach refinements, and Undecided previews, publishes and compiles both FRONT prompts. Prepared observations stood in for model responses. The four approved scenarios passed with `npm.cmd run test:e2e` in 42.2 seconds. JavaScript syntax and `git diff --check` passed. Live model output and image quality remain for Joe's Test review.
