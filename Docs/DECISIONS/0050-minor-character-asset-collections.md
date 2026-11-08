# 0050 Minor Character asset collections

Status: accepted locally

The universe Markdown template owns minor character authoring inputs. The
six assets use a separate runtime store and shared mixed-quality boards.
Style Alignment uses the original for analysis and generates from a prompt
composed with canonical universe style. Each view uses deterministically
filtered template inputs and the current locked Style image. Interview
revisions reach the template after review and explicit application.

## Offline bootstrap

Run `python3 -B -m zet.scripts.bootstrap_minor_character_templates <universe-root>`
for a read-only preview. If a source is ambiguous or missing, supply
`--choices <json>` mapping legacy IDs to reviewed Inventory IDs and preview
again. Settle pending jobs, publication journals and active legacy locks
before proceeding. Save and review the preview JSON, stop dashboard and
library writers, and run the same command with
`--apply-reviewed <manifest> --writers-stopped`. The manifest is rechecked
before writing templates, and the same manifest resumes a partial apply.
Names and verified Inventory source IDs seed the templates. Legacy files
remain in place. Open the templates using the release that supports the new
runtime store.
