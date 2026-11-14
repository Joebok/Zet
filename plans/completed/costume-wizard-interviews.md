# Costume Wizard interviews

Status: complete

1. Add durable section drafting, retry and refinement to CostumeWizardService. Verify skipped equipment and resumed requests.
2. Assemble and validate canonical Markdown from saved sections. Verify Dressing compilation and the private FRONT handoff.
3. Add intake and section review controls in the dashboard. Verify editing, resume and preview in Chromium.
4. Write the operator guide and update Zet Tester instructions. Run focused S2, syntax and diff checks.

The saved draft keeps the existing costume template and uses the existing
universe-scoped workflow and private FRONT render. The accessory toggle is an
intake choice. Existing sessions keep their draft editor.

All four approved fast E2E scenarios passed (44.5 seconds). The runner
accepted the `--grep character-to-costume` argument but ran the full suite.
Disposable prepared responses exercised suspension and recovery, a failed
section and local retry, replacement application, both accessory settings
through the Dressing compiler, private FRONT renders from a published
Assembly image, and acceptance with an empty normal Dressing board.
Disposable Chromium verified both toggle settings, resume, saved edits,
preview, and refinement. Zet Tester validated the reusable character case.
Visual quality remains unverified with live inference.
