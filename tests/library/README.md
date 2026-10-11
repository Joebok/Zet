# Zet test library seed

This folder holds the small, disposable seed used by the local end-to-end suite, including deterministic reference and prepared-response images. The server copies it under `test-results/` before each scenario and seeds Narrative Scenes records through Zet's services. The seed is never written back from a test run. Use `npm run test:library` to open an inspection copy.
