# Updating Zet's Qwen guidance

This package is the runtime source for both Codex and Ollama. It does not require a personal Codex skill installation or proxy-side skill files. The copied SKILL.md and references are unchanged source material; adapters/ contains Zet-owned contract, authoring, fragment and review guidance.

To update: replace only the imported source files from a reviewed skill release, inspect the diff against the recorded import, update manifest source hashes/import date, and increment integration_version. Review source/adapters for contradictions, then use disposable checks to load each role/mode and compare frozen Codex/Ollama requests. Run the approved npm.cmd run test:e2e baseline and git diff --check. Never run the imported skill's developer validator automatically or download upstream changes during requests.

Source hashes describe the imported baseline; effective hashes are computed from current bytes at request preparation so intentional edits through Template Editor apply immediately to new requests. Existing requests retain their instructions and hashes. A missing required module blocks preparation with its path. Update source and adapters separately so a source refresh cannot overwrite local contract decisions. No source scripts are imported or executed.

Roles and defaults live in zet/services/llm_role_service.py. Optional [LLMRoles.Models] overrides use those role keys. Explicit task/session selections take precedence. Clear an override to inherit its original model setting. No new inference pass is added to deterministic prompt paths.
