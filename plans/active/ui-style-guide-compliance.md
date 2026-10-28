# Dashboard UI compliance review and alignment

Status: active. Authorized 2026-10-27.
Specification: Docs/UI_STYLE_GUIDE.md; user-approved plan in this chat.

## Goal and constraints
Review all active dashboard and auxiliary pages; make bounded presentation and interaction repairs. Record obsolete, redirected and unreachable features without removing or reviving them. Preserve APIs, storage, eligibility, drafts and publication protections. One implementer; no new dependencies, permanent tests, production data, external writes or live AI.

## Work packets
Each packet owns only its named presentation and corresponding scoped CSS. Dependencies: WP1 inventory precedes WP2 shared primitives; WP3 shell follows WP2; page packets follow WP2 (Overview also WP3; auxiliary workflow pages also WP5). WP16/17 follow page review. Acceptance: guide alignment or explicit, evidence-backed exceptions. Validation: touched-script syntax, disposable fixture browser inspection, final approved E2E and diff review.

| Packet | Responsibility / owners | Status |
| --- | --- | --- |
| WP1 | Inventory and baseline; Docs/UI_COMPLIANCE_REVIEW.md | inventory/capture complete |
| WP2 | Shared primitives; zet.css, image_card_ui.js | bounded repairs complete |
| WP3 | Shell/navigation; index.html, zet.js | reviewed; exceptions in register |
| WP4 | Overview/onboarding; index.html, zet.js | reviewed; exceptions in register |
| WP5 | Five local pipelines/review; local_asset_pipeline.js, local_template_improvement.js | reviewed; exceptions in register |
| WP6 | Minor Characters; minor_characters.js | reviewed; exceptions in register |
| WP7 | Image Generation/reconstruction/true-up; zet.js | reviewed; exceptions in register |
| WP8 | Inventory; zet.js | reviewed; exceptions in register |
| WP9 | Narrative; narrative.html, narrative.js/css | reviewed; exceptions in register |
| WP10a–f | Separate Identity Keys, Turnarounds, Costumes, Phase Comparison, Candidates, Zines reviews; index.html/zet.js | reviewed; exceptions in register |
| WP11 | Local Character Overview; local_character_overview.html | repaired; focused checks passed |
| WP12 | Refinement; local_character_refinement.html/js | repaired; focused checks passed |
| WP13 | Post Render Adjustments; local_character_prompt_improvement.html/js | reviewed; exceptions in register |
| WP14a–g | Separate Universes, Template Editor, AI Queue/model picker, Batches, Config, Inspection, Controls reviews; existing controllers | reviewed; exceptions in register |
| WP15 | Help/task capture/attention; existing templates/controllers | reviewed; exceptions in register |
| WP16 | Legacy/reachability evidence register | reviewed; exceptions in register |
| WP17 | Integration, affected documentation, final diff review | partial; acceptance gaps remain |

## Validation and evidence
Use private fast fixture on 8765. Explicit capture inventory includes Head-Image Edit; standalone pages captured separately. Desktop 1920×911, tablet 1133×610, short tablet 1133×560, narrow 390×844; shell boundaries if changed. Source review does not establish runtime compliance. Record populated-state gaps, unknown outcomes and physical-device limits in the register. No permanent coverage expansion. Commands: npm.cmd run capture:ui, node --check for touched scripts, npm.cmd run test:e2e, git diff --check.

## Progress and decisions
Initial working tree clean. Earlier responsive plan is historical evidence, not current acceptance. Local Character Overview has its own dark palette; legacy aliases remain in canonicalDashboardPage. Detailed findings and observed validation will live in the review register.

### 2026-10-27 bounded implementation results

WP1 inventory/capture and WP16 reachability register completed in Docs/UI_COMPLIANCE_REVIEW.md. WP2 shared pressed treatment and preview-well palette repaired; WP11 Overview theme/local feedback/poll stability repaired; WP12 Refinement local feedback repaired. WP9 Narrative control corners/disabled cursor aligned. Other page packets received source/initial-layout review with explicit state-specific exceptions rather than speculative rewrites. No broad controller consolidation, legacy removal or restoration performed.

Observed checks: 26 destinations × five sizes, no horizontal overflow; Pipeline Controls activation blocked by missing fixture Pipelines.json. Disposable four-size DOM inventory found no visible unnamed dashboard buttons. Approved E2E: four passed (43.2s). Final Overview disposable pending/error/focus/four-viewport checks passed; Refinement prepared contextual pending/error/poll check passed. Syntax checks passed. Earlier failed standalone template checks exposed encoding/syntax mistakes, corrected before final browser validation.

WP3–10 and WP13–15 retain populated-state/lifecycle acceptance gaps listed individually in the register; WP17 integration is partial. This plan remains active: full guide compliance is not claimed. Remaining work includes populated Minor/Candidates/Zine and auxiliary workflows, native-confirmation replacements, comprehensive keyboard/contrast and actual-device checks. Pipeline Controls needs valid isolated compatibility data before runtime acceptance. No production/live/external action is required or authorized by these notes.
