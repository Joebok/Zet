# Compact image cards and review panels

Status: complete locally. Approved and validated on 2026-10-20. Physical iPad acceptance remains unverified.

## Goal and desired behavior

Use compact, accessible icon controls across active image cards/viewers. Show render
status once. Put the existing distinct Luna advisory panel below the character
review title/context and above Human decision. Move Prompt and source off gallery
cards into review, collapsed on opening/changing candidates. Preserve prompt access
for pending/failed candidates, polling drafts, focus, protections and slot identity.

## Current behavior and impact

Character `renderCandidate` and Narrative slots repeat pending status. Character
`renderReview` hides advisory information inside Image details and render actions.
`render_slots.js` currently shares only the count control. Active presentation is
owned by the dashboard scripts/templates and CSS; no backend/API/store changes are
needed. Docs/COMPONENTS/DASHBOARD_UI.md owns presentation conventions, with workflow
details in LOCAL_CHARACTERS.md and NARRATIVE.md; CODE_MAP.md will map the helper.

## Constraints

One agent; existing dependencies and four approved fast scenarios. No permanent
tests, live AI, production library operations, deployment, or retired workflow work.
Preserve universe isolation, queue fencing, ordered references, slot identity,
human/selection/lock distinctions and existing confirmations. Use 32px desktop and
at least 44px coarse-pointer controls. Scope icons to image cards/viewers, retaining
page-level forms/navigation and human-decision labels.

## Implementation packets

| Packet | Files/interfaces and work | Dependencies | Acceptance / validation | Status |
| --- | --- | --- | --- | --- |
| WP1 | image_card_ui.js, zet.css, script-loading templates: SVG decorator, action identity/labels, compact rows, accessible tooltips/focus/touch | none | Existing handlers/IDs/link semantics survive; syntax and disposable browser probe | complete |
| WP2 | local_asset_pipeline.js gallery/selected cards: single status, icon actions, prompt/details access for image-less occupied slots | WP1 | Four pipelines retain physical bindings and one status; fixture browser check | complete |
| WP3 | local_asset_pipeline.js, index.html, CSS: visible Luna panel, Human decision, actions, collapsed Prompt and source; image-less review and polling preservation | WP2 | Title/advice/decision order, short-height bounds, gallery return; fixture browser check | complete |
| WP4 | zet.js, minor_characters.js, index.html: generation/minor cards/viewers, prompts, stable focus and dynamic labels | WP1 | Existing selection/render/download/lock protections; fixture checks | complete |
| WP5 | narrative.js/narrative.css/markup: single status, icons, move complete source disclosure into review, allow image-less inspection | WP1 | Backdrop/subscene/assembly source/provenance/copy preserved; fixture checks | complete |
| WP6 | Active image sections in zet.js and refinement template/script: Inventory, Overview/fullscreen, identity/turnaround/costume, phase comparison, Candidates, Zines, refinement | WP1 | Common presentation, unchanged form/page controls and copy feedback; fixture checks | complete |
| WP7 | Affected documentation and this plan: validation, results, archive | WP2–WP6 | Syntax, four fast E2Es, disposable responsive/accessibility/state checks, diff review | complete |

## Validation plan

Run node --check on changed scripts, npm.cmd run test:e2e, and git diff --check.
Use isolated disposable browser checks/prepared data for pending/failed/ready/
selected/locked states, rank missing/stale/failed, long advisory/prompt text,
polling, unsaved decisions and focus. Inspect desktop, 1133x560 tablet landscape,
390x844 phone and coarse pointers. No permanent coverage expansion. Record gaps
and actual outcomes below; desktop Chromium does not prove physical iPad behavior.

## Progress and decisions

- Planning identified image-only review navigation in both character and Narrative
  renderers; extend detail inspection to occupied candidates without images so
  moving prompts does not remove existing access.
- WP1–WP6 completed sequentially. The decorator observes image-scoped controls and
  changing labels to avoid duplicating SVG markup across renderers. Explicit scans
  before card comparison prevent polling from replacing otherwise unchanged cards.
- Screenshot inspection led to bounded phone advisory space and consolidated
  Image Generation toolbars. Desktop buttons remain 32px and touch buttons 44px.
- WP7 completed after final regression pass and documentation/diff review.

## Final results

- Implemented the shared image-card SVG decorator and compact scoped CSS, loaded by
  the dashboard and standalone refinement template. Existing active image actions
  reuse it; Overview shortcut navigation and page-level forms keep their labels.
- Character/Narrative/Minor cards show render status once. Character/Narrative
  prompts moved into initially collapsed review disclosures with pending/failed
  inspection. Available Luna advice is visible above human decisions, including
  explicit stale/failed states. Polling preserves drafts, disclosure scroll,
  comparison, candidate and action focus; gallery return uses the original card.
- Image Generation review uses one compact navigation toolbar and one action/count
  toolbar, retaining the prompt/negative prompt disclosure. Minor comparison,
  Inventory copy feedback, shared fullscreen viewers and refinement image controls
  retain existing handlers and protections. No backend, API, serialization or
  dependency changes were needed. Existing Narrative CSS and refinement controller
  were sufficient; their presentation is supplied by the shared helper/styles.
- Updated Dashboard UI, Local Characters, Narrative, CODE_MAP and Testing. No ADR
  needed: services, stores and workflow responsibilities did not change.

### Observed validation

- Six changed JavaScript files passed node --check; git diff --check passed.
- npm.cmd run test:e2e: all four approved scenarios passed, final run 42.6s.
  Initial run passed in 44.8s with a nonfatal Windows fixture usage-maintenance
  file-sharing warning; the final run emitted no such warning.
- Disposable actual prepared-response Assembly check passed at 1440x900,
  1133x610, 1133x560 and 390x844 with three real fixture candidates: review
  navigation, gallery return, unsaved decision and expanded prompt across polling.
- Disposable browser projections passed for all four character pipelines with
  empty/waiting/rendering/failed/ready/selected/locked states; image-less details,
  source order, long advice, missing/stale/failed advice, focus and prompt defaults.
  Desktop and coarse-pointer checks covered 1440x900, 1133x560 and 390x844.
  Representative desktop card height fell from 583.7px to 491.9px using the prior
  renderer/styles and current renderer against identical projected data.
- Inventory copy/Copied/reset and fullscreen; Image Generation selection,
  protection messages, navigation/disclosure defaults and 44px controls; prepared
  Minor Character states/comparison; standalone refinement controller/layout all
  passed disposable Chromium checks without page errors.
- Actual prepared Narrative synthesis/render/select/reload/review passed, plus
  browser-projected pending/failed inspection and retained source, assembly-layer,
  raw-composite and prompt-copy controls. Desktop/tablet/phone screenshots were
  inspected; long advice and control bounds remain usable without page overflow.
- Early disposable assertion/setup errors (counting empty slots, fieldset matcher,
  stale fixture state and URL matching) were corrected. Screenshot QA caught and
  fixed close-button positioning, a compressed phone advisory region, and excess
  Image Generation toolbar height. Scripts/screenshots remain ignored under
  test-results/image-cards; no permanent tests/scenarios were introduced.

### Limits

All checks used the isolated fixture library/queue, prepared responses or browser
projections; no live inference, production data, external writes or deployment.
Shared fullscreen behavior was exercised directly; every populated identity,
turnaround, costume and Zine journey was not separately recreated. Physical iPad
Safari/touch behavior remains unverified. No remaining implementation blocker.
