# Local scene batches validation status

Local scene batches and the legacy Scene Builder remain available in the dashboard. Their automated test coverage has been retired as part of the minimal local testing policy; the approved end-to-end suite targets the Narrative Scenes workflow and does not exercise these retiring paths.

Run the maintained fast suite with `npm run test:e2e`. Do not add scene-batch or Scene Builder coverage without Joe’s explicit approval.
