# iPad image review, responsive layout, and UI consistency

Status: implemented locally; physical-iPad acceptance remains pending. Authorized 2026-10-19.
Date: 2026-10-19 (America/Los_Angeles).
Related request: Joe's iPad mini landscape screenshot and request for a responsive-design and cross-viewport style review. No external issue created.

## Goal

Make image browsing, comparison, review, and selection comfortable on an iPad mini in landscape. Fix crowded navigation and review dialogs that disturb the page position. Establish consistent card states, action placement, labels, and colors across active dashboard pages and viewport sizes. Provide touch-accessible image paste with a dependable file-picker alternative.

This is a plan for local implementation. It does not authorize deployment, live AI work, new dependencies, permanent tests, or changing creative records. Keep editing available on tablets, but give viewing and decisions priority over text entry. Preserve desktop editing efficiency.

## Current behavior and evidence

The supplied screenshot shows navigation controls colliding, particularly the character section buttons and right-hand task/tools controls. Its original 2266 × 1488 pixel dimensions are consistent with [Apple's iPad mini display specification](https://www.apple.com/au/ipad-mini/specs/). At an assumed device pixel ratio of two, the nominal landscape screen is 1133 × 744 CSS pixels; the visible browser chrome leaves approximately 610 CSS pixels for this page. These are planning targets, not measurements from Joe's browser. Capture actual `innerWidth`, `innerHeight`, `visualViewport`, zoom, browser, and iPadOS version during device acceptance.

Authoritative source findings:

- [index.html](../../zet/web/templates/index.html) owns the shared header, section navigation, utilities, and local pipeline dialog. [zet.css](../../zet/web/static/zet.css) places navigation and utilities in one flex row. `.workspace-navigation` can shrink while its buttons continue occupying their intrinsic widths. Most compact navigation and 44-pixel control rules start at `max-width: 1100px`, excluding the likely 1133-pixel target. Even below 1100, the utilities remain crowded and `.tabs` returns to `flex-wrap: nowrap`.
- [zet.js](../../zet/web/static/zet.js), `renderResponsiveSectionMenu`, currently offers one “Assets” destination in compact navigation, resolving to Body-Reference. The compact layout must also provide direct access to Head-Image, Assembly, and Dressing.
- [local_asset_pipeline.js](../../zet/web/static/local_asset_pipeline.js), `openReview`, already uses `showModal()`. The dialog's CSS specifies `position: relative`. A disposable Chromium probe using the current template/CSS showed the opened modal resolving to `position: absolute` and changing background scroll from 1300 to 0. A temporary, in-memory `position: fixed` override retained scroll at 1300 with the dialog inside the viewport. This identifies a concrete positioning defect; the exact iPad behavior still requires device reproduction.
- Local review uses two images plus a minimum 320-pixel information column, mostly `vh` sizing, and multiple clipping/overflow rules. Navigation arrows can be only 28 pixels wide. The ranking section precedes decisions/actions. These rules need short-height and touch review even after fixing positioning.
- Active pages use different card conventions: local pipeline selection is green, Narrative selection uses primary teal, and Minor Characters uses an accent outline. Different modules independently render action rows, errors, progress, and dialogs. [render_slots.js](../../zet/web/static/render_slots.js) currently shares only the additional-render count control; it is not a shared card implementation.
- Most paste zones are focusable `div` elements listening for a `paste` event, with keyboard-centric instructions. The optional Head source is already contenteditable. There is no shared image clipboard-read helper. Existing upload paths should accept clipboard-derived files without backend changes.
- [capture-dashboard-ui.mjs](../../Scripts/capture-dashboard-ui.mjs) targets 1024 × 768 for iPad, assumes exactly 22 sections, discovers raw sections rather than canonical active destinations, defaults to port 8081, and clears PNGs in `Docs/UI` capture folders. It should not be run unchanged for this review: it misses the target width and includes stale/redirected destinations. No existing `Docs/UI` screenshot set was present during investigation.

Observed browser probes used synthetic content with repository markup/CSS and installed Playwright Chromium. They did not exercise loaded application state, real candidate actions, iPadOS, or clipboard access. No application files or production data were changed by those probes.

## Desired behavior and visual rules

### Navigation and image-first tablet use

- Use a compact shell before the full navigation collides; start by evaluating a roughly 1280-pixel shell breakpoint, then set the boundary from measured content. Avoid applying one global breakpoint to unrelated page layouts.
- Keep workspace, current character/story context, current section, and task attention visible. Put low-frequency utilities and phase deletion in labeled menus. Preserve every destination and current context when controls move.
- Show character/phase context compactly, with selectors available on tap. Keep tablet chrome to roughly two compact rows where content allows; long names must wrap or truncate without hiding the full accessible name.
- Show images/results before expanded generation settings and large text editors. Use explicit “Settings”, “Prompt”, or “Details” disclosures rather than automatically focusing a textbox. Preserve drafts when opening and closing disclosures or resizing.
- Use at least 44 × 44 CSS pixel touch targets for controls used during review, including icon buttons, close buttons, arrows, and radio labels. Apply touch sizing using pointer capabilities as well as width; a tablet above 1100 pixels still needs it.
- No page-level horizontal scrolling or overlapping controls. Intentional thumbnail strips and wide data tables may scroll within labeled, contained regions.

### Candidate review

- Open review anchored to the visible viewport from any gallery scroll position. Closing returns to the originating card and gallery position. Restore focus without scrolling the page unexpectedly.
- In landscape, reserve most space for candidate/reference images, with a compact decision area. Keep Close, previous/next candidate, view navigation, decision controls, and selection reachable without scrolling through explanatory text.
- Use dynamic viewport sizing with a fallback and safe-area padding. In reduced height or portrait, place actions below the image area while keeping them reachable; let details scroll within their own region.
- Offer reference comparison without making a missing reference consume half the image area. Keep full-image viewing and browser zoom available. Do not introduce custom pan/swipe gestures unless existing controls prove insufficient.
- Put ranking explanations, prompt text, seeds, feedback, and regeneration settings behind clearly labeled details as appropriate. Preserve the existing distinction between a human decision, selecting a candidate, and publishing a lock.
- Polling must preserve the active candidate, comparison choice, unsaved decisions, details scroll, and focus. Existing navigation/save behavior remains authoritative.

### Shared card/action language across all viewports

| Meaning | Presentation | Action treatment |
| --- | --- | --- |
| Main task for the current state | Primary teal, existing tokens | At most one emphasized action per card/group; e.g. Generate on an empty slot or Select on an available candidate |
| Secondary operation | Neutral surface and border | Review, Compare, Retry, Regenerate, details; consistent placement and full accessible labels |
| Selected | Primary outline plus “Selected” label/icon | Explicit Unselect where supported; do not imply published/locked |
| Locked/published | Persistent lock icon and label | Show existing protection reasons and allowed operations |
| Approved/complete | Existing success token and text/icon | Distinct from selection |
| Pending/running/stale | Existing neutral/info/warning tokens as appropriate, with text | Stable space for progress and reasons; no color-only meaning |
| Error/rejection | Existing danger token and readable text | Retry only when the owning workflow supports it |
| Clear/delete | Danger text/outline in a separated area or labeled More menu | Preserve existing confirmations and protection checks; explain the scope of clearing |

Use the existing palette, typography, spacing, borders, and focus treatment. Define consistent action order: review/compare, choose, generation/retry, then removal. Where supported, prefer full “Regenerate” and “Clear slot” labels over unexplained abbreviations. Empty, reserved, running, failed, available, selected, and locked states need consistent visual treatment, while retaining their workflow-specific meaning. Disabled reasons must be visible on touch, not available only through hover titles. Keep card borders stable so selection does not shift layout.

### Image import and clipboard

Provide a labeled **Paste image** button that calls `navigator.clipboard.read()` directly from the user's tap, checks exposed image types, and passes the resulting file through the existing preview/upload handler. Keep keyboard paste and drag/drop where supported. Pair paste with **Choose image** using the existing image file input, allowing the browser's Photos/Files choices; do not force camera capture.

WebKit documents image clipboard reads, secure-context requirements, user gestures, and an additional native Paste approval UI. Therefore this is not a blanket iPad image-pasting limitation. A non-editable focus target and keyboard-only affordance are plausible Zet limitations, while the copied item and browser policy can still prevent access. The screenshot already shows HTTPS, so insecure transport should be checked, not presumed to be the cause. See [WebKit Async Clipboard API](https://webkit.org/blog/10855/async-clipboard-api/) and [Zet HTTPS notes](../../Docs/LAN_HTTPS.md).

Feature-detect the API and accepted image representations; do not depend on browser-name checks or Chromium clipboard permission APIs. Show useful messages for unsupported access, denied/dismissed access, and clipboard contents without an image, retaining Choose image. Do not insert arbitrary clipboard HTML or fetch a copied remote image URL as a workaround. Normalize only as required by the existing upload contract. File-size/type validation stays authoritative on the server.

## Impact, scope, and documentation ownership

Presentation owners: `zet/web/templates/index.html`, `zet/web/static/zet.css`, `zet/web/static/zet.js`, `local_asset_pipeline.js`, `minor_characters.js`, `narrative.css`, `narrative.js`, `zet/web/templates/narrative.html`, and the standalone local refinement template/script. Task capture has its own template/CSS/JS. A focused browser clipboard helper is justified; a new UI framework or universal workflow controller is not.

Review all active destinations, recording findings by page/state and priority:

| Group | Pages and states to inspect |
| --- | --- |
| Primary character viewing | Overview; all four local pipelines; candidate dialog; staged Continue and template-review disclosures; selected/locked views; refinement; Minor Characters |
| Other image workspaces | Identity Keys; Turnarounds; Costumes/wizard; Phase Comparison; Image Generation/reconstruction; Image Inventory/import/replacement |
| Story viewing | Narrative story/scene/target views; backdrop, subscene, and final assembly cards/dialogs; Candidates; Zines |
| Editing and utilities | Universe list/create/settings; Template Editor; AI Queue/model picker; Batches; Config; Pipeline Inspection/Controls; task capture/attention; Help |

Use `canonicalDashboardPage` and actual runtime navigation to exclude retired/redirected Scene Builder, Render Console, and traditional generation pages. Text-heavy utilities need usable responsive layouts, not a new tablet authoring product. Inspect existing crop/assembly controls for touch usability; substantial editing-tool redesign requires a separately scoped follow-up.

Documentation owners after implementation: this plan for progress/evidence; [LOCAL_CHARACTERS](../../Docs/COMPONENTS/LOCAL_CHARACTERS.md) for review workflow; [NARRATIVE](../../Docs/COMPONENTS/NARRATIVE.md) for affected candidate presentation; [LIBRARY](../../Docs/COMPONENTS/LIBRARY.md) for import behavior; [Testing](../../Docs/Testing.md) and [Development](../../Docs/DEVELOPMENT.md) for observed validation. Add one dashboard UI conventions document if needed to own shared visual rules, linked from [INDEX](../../Docs/INDEX.md); update [CODE_MAP](../../Docs/CODE_MAP.md) if new shared presentation entry points are introduced. An ADR is needed only if a significant durable architecture decision emerges.

## Invariants and implementation constraints

- Keep services in control of allocation, selection eligibility, human decisions, immutable locks, publication, and clearing. Preserve universe ownership, attempt fencing, physical slot identity, ranking order, and ordered reference bindings from [INVARIANTS](../../Docs/INVARIANTS.md).
- No serialized-data/API changes are expected. Stop and investigate if presentation work exposes a contract requiring them; do not invent a parallel browser state model.
- Use existing dependencies. Keep changes within each packet's presentation responsibility; no broad extraction or rewrite of `zet.js`/`zet.css`.
- Work sequentially with one agent. Packets are Luna sized implementation units, not delegation authorization.
- [Testing](../../Docs/Testing.md) is authoritative: four current maintained fast scenarios, S1–S4. `plans/README.md` and part of CODE_MAP still say three; do not recreate retired tests or treat those stale counts as the baseline.

## Implementation packets

Implementation is proceeding sequentially; observed results are recorded below. No packet authorizes work on production library data.

### WP1 — Establish representative responsive evidence
- Dependencies: none.
- Files/interfaces: `Scripts/capture-dashboard-ui.mjs`; ignored `test-results` evidence; this plan.
- Work: adapt capture inputs to a specified isolated fixture URL/output folder and canonical active destinations rather than the stale section count. Add the target landscape size. Capture representative populated/error/selected states using disposable fixture preparation, with no live AI. Record actual device dimensions when available and prioritize the page inventory above.
- Acceptance: captures identify route, viewport, state, revision, clipping/overlap, and whether inspected in Chromium or on the physical iPad. Do not erase existing reference captures.
- Validation: `node --check Scripts/capture-dashboard-ui.mjs`; run `npm.cmd run capture:ui` only against explicitly configured isolated storage/output. Capture tooling remains an inspection aid, not a new maintained test suite.

### WP2 — Contain the shared header and navigation
- Dependencies: WP1.
- Files/interfaces: header/nav in `index.html`; corresponding `zet.css`; `renderResponsiveSectionMenu`/`syncResponsiveChrome` in `zet.js`.
- Work: compact shell, utility overflow menu, responsive context controls, all four direct pipeline destinations, and accessible popup placement. Use actual available space; handle long names and visible task/GitHub controls.
- Acceptance: navigation never collides at the target and adjacent breakpoint widths; all destinations/actions remain available; current context survives workspace/section changes; tablet chrome leaves useful image height.
- Validation: `node --check zet/web/static/zet.js`; disposable screenshot/DOM bounds inspection at 1100/1101/1133 and desktop widths; touch/keyboard menu traversal.

### WP3 — Fix candidate dialog positioning and return behavior
- Dependencies: WP1; can precede WP2.
- Files/interfaces: local dialog CSS/markup; `openReview` and close/focus handling in `local_asset_pipeline.js`. Inspect Narrative's shared-class consumer.
- Work: explicit viewport anchoring, dynamic height/fallback, safe-area containment, and gallery scroll/focus restoration. Keep the initial fix independent of a full layout redesign.
- Acceptance: opening from a deeply scrolled gallery immediately displays review; opening/closing does not jump the gallery; Close remains visible; shared Narrative dialog remains usable.
- Validation: `node --check zet/web/static/local_asset_pipeline.js`; disposable open/close checks at several gallery positions and target/short viewport heights, followed by physical-iPad acceptance.

### WP4 — Make character review usable with touch and limited height
- Dependencies: WP3.
- Files/interfaces: local review layout in `index.html`/`zet.css`; `renderReview`, navigation, and polling patches in `local_asset_pipeline.js`.
- Work: prioritize images and a persistent decision/action area; collapse explanatory metadata; enlarge navigation and radio hit areas; handle missing reference images. Preserve polling drafts and review semantics.
- Acceptance: compare, Pass/Fail/Undecided, save, select, previous/next candidate, previous/next view, and close work without scrolling to the page top or opening the keyboard. Details remain readable independently. Polling preserves draft state and comparison choice.
- Validation: JS syntax check; disposable prepared multi-candidate/multi-view journey with long ranking text, live fixture updates, and selected/locked states; inspect 1133 × 610 and 1133 × 560 plus desktop and portrait fallback.

### WP5 — Standardize local candidate cards and shared visual rules
- Dependencies: WP4.
- Files/interfaces: local cards/actions in `local_asset_pipeline.js`; narrowly scoped common/local styles in `zet.css`; `render_slots.js` only for its existing presentation responsibility; UI conventions documentation if introduced.
- Work: implement the state/action table above on the four shared pipeline pages. Standardize badges, spacing, labels, touch targets, focus states, and non-hover disabled reasons.
- Acceptance: all slot states are distinguishable; actions fit without shrinking touch targets; physical slot labels/actions remain bound correctly after ranking; selected/locked protections remain unchanged.
- Validation: relevant `node --check` commands; disposable visual state sheet using existing fixture data; existing S2 assertions during integration.

### WP6 — Align Narrative cards and image review
- Dependencies: WP3 and WP5 visual rules.
- Files/interfaces: `narrative.js`, `narrative.css`, `templates/narrative.html`.
- Work: apply shared card/action/state styles to backdrop, subscene, and assembly targets; adapt the single-image review layout and action area; collapse prose/settings where useful for viewing.
- Acceptance: style meanings match local cards; select/lock/retry remain distinct; review survives updates; desktop editing, pending interviews, and assembly binding behavior remain intact.
- Validation: `node --check zet/web/static/narrative.js`; disposable populated target/dialog inspection at tablet/desktop/phone widths; existing S1/S3 during integration. Touch crop/assembly findings are recorded, with only bounded layout fixes included.

### WP7 — Align Minor Characters viewing and review
- Dependencies: WP5 visual rules.
- Files/interfaces: `minor_characters.js`; Minor Character markup and `.mc-*` CSS in `index.html`/`zet.css`.
- Work: align board states/actions and touch navigation; reduce persistent intake controls during review; contain the comparison dialog and long action rows.
- Acceptance: stage/selection/lock states remain accurate; compare and close are reachable in short landscape; background updates preserve feedback and current image.
- Validation: `node --check zet/web/static/minor_characters.js`; disposable style/view/true-up board and comparison-dialog inspection. No maintained scenario currently covers this workflow.

### WP8 — Align Image Generation cards and result review
- Dependencies: WP5 visual rules.
- Files/interfaces: `renderImageGenerationStatus`, `renderImageGenerationReview`, related result markup in `zet.js`/`index.html`, and scoped CSS.
- Work: apply consistent card/action treatment, contained thumbnail layouts, selected-state badges, and image-first review; make reconstruction/refinement details collapsible without losing drafts.
- Acceptance: generate/retry/regenerate/clear/select/import remain accurate and reachable; universe-owned workspace assignments and input restoration retain existing behavior.
- Validation: `node --check zet/web/static/zet.js`; disposable board/dialog state inspection at tablet/desktop/phone widths. Existing fast scenarios do not fully cover this board.

### WP9 — Add shared image paste interaction
- Dependencies: WP2 for toolbar containment; otherwise independent of card adoption.
- Files/interfaces: new focused `zet/web/static/image_input.js`; script inclusion in `index.html`; optional Head source controls/handler in `local_asset_pipeline.js`.
- Work: capability-detected, user-initiated clipboard image read; explicit Paste image/Choose image controls; common feedback and routing into the existing file handler. Prove it on the small Head-source adapter first.
- Acceptance: desktop keyboard paste remains; supported image reads produce the existing preview; denied/unsupported/non-image content leads to a useful message and file-picker fallback; no synthetic clipboard permission bypass.
- Validation: `node --check zet/web/static/image_input.js` and local pipeline script; disposable adapter checks with prepared files; physical-iPad HTTPS trials copying an image from Photos and browser image content, allowing/dismissing native Paste UI. Clipboard support remains unverified until device trials.

### WP10 — Adopt paste controls in generation and Inventory
- Dependencies: WP9.
- Files/interfaces: active paste handlers for Image Generation reference slots, reconstruction, entity-library upload/replacement, and image catalog add/import/replace in `zet.js`; corresponding `index.html` controls.
- Work: use the shared clipboard adapter and each existing file-ingestion handler. Keep upload previews, limits, filenames, metadata, and replacement confirmations intact.
- Acceptance: every active image-input surface offers a visible touch path; one paste produces one import; unavailable clipboard access never hides Choose image; Inventory protections remain unchanged.
- Validation: `node --check zet/web/static/zet.js`; disposable file/clipboard-to-preview checks for each named adapter and actual-iPad spot checks of Inventory and Image Generation.

### WP11 — Adopt paste controls in ancillary inputs
- Dependencies: WP9.
- Files/interfaces: `minor_characters.js`; costume-wizard handlers in `zet.js`; task capture template/CSS/JS; include the helper in `task_capture.html` when used standalone.
- Work: connect the same Paste image/Choose image pattern without changing each feature's save/upload timing. Remove keyboard-only instructions on active surfaces. Leave retired inputs alone.
- Acceptance: Minor Character reference intake, costume references, and task screenshots work with touch file selection and supported clipboard reads; no keyboard appears merely to paste an image; source captions remain available.
- Validation: syntax checks for touched scripts; disposable intake checks and real-iPad clipboard/file-picker checks. No external task submission is part of validation.

### WP12a–i — Remaining image pages, one packet per row

These are independent Luna sized packets, each dependent on WP1/WP2 and WP5's visual rules. Each owns only the named page's markup/CSS and corresponding rendering functions, even where those live in shared files. Inspect and fix only that page's responsive findings; a page with no necessary change receives an inspection result. No workflow/backend redesign belongs in these packets.

| Packet | Files/interfaces and bounded work | Acceptance |
| --- | --- | --- |
| WP12a — Overview | `index.html`/`zet.css` Overview and overview renderers in `zet.js`; improve progress/metric wrapping and prioritize the available character preview | Useful image preview and next action; setup editor remains available without dominating tablet viewing |
| WP12b — Identity Keys | Same files, Identity Keys section/renderers only; contain view cards, preview, and action groups | View images and key actions fit; key editing/selection semantics preserved |
| WP12c — Turnarounds | Same files, Turnarounds section/renderers only; remove rigid column pressure | Image comparison and actions remain usable in short landscape and desktop |
| WP12d — Costumes | Same files, costume list/detail and wizard layout only; contain reference cards and long captions | Browse/view costumes with touch; wizard input remains available without losing drafts |
| WP12e — Phase Comparison | Same files, Phase Comparison section/renderers only; adapt paired images and selectors | Both phases remain identifiable; images and controls are contained |
| WP12f — Inventory browsing | Same files, inventory search/grid/detail only; contain filters, preview, metadata, and view actions | Large-image viewing is reachable; filters/details do not crowd it; catalog semantics unchanged |
| WP12g — Candidates | Same files, active scene-candidate browsing only; adapt candidate grid and image viewer | Images, provenance, and permitted actions remain legible and accessible |
| WP12h — Zines | Same files, Zines section/renderers only; contain page previews, source selectors, and actions | Preview and page navigation fit without changing assembly or export semantics |
| WP12i — Refinement | `local_character_refinement.html`, `local_character_refinement.js`, scoped `zet.css`; prioritize working image and adopt/return actions | Image/attempt navigation usable; optional feedback/details remain reachable; adoption protections preserved |

Validation per row: `node --check zet/web/static/zet.js` or `node --check zet/web/static/local_character_refinement.js` when touched; disposable populated screenshots and touch/keyboard inspection for that page at tablet, desktop, and phone widths. Record actual findings and results in this plan after each packet. The nine page packets have been reviewed with fixture captures and focused shared-layout changes; populated-state limits are recorded below.

### WP13a–g — Utility pages, one packet per row

Each is a separate Luna sized review/repair packet dependent on WP1/WP2. Own only the named page's presentation in `index.html`/`zet.css`/`zet.js`, plus the explicitly listed module when applicable. Fix containment, shared-control styles, readable tables, and accessible menus; retain text editing. A substantial interaction redesign is a new scoped proposal, not implied follow-on implementation.

| Packet | Bounded responsibility | Acceptance |
| --- | --- | --- |
| WP13a — Universes | Universe list/create/settings | Selectors, forms, and menus fit; no context-switch regression |
| WP13b — Template Editor | Editor controls and source/diff layout | Text and diffs readable; save/review controls reachable; drafts preserved |
| WP13c — AI Queue | Queue tables and model-picker popup; also `ai_model_picker.js` if needed | Tables scroll within their region; model popup fits and stays mutually exclusive |
| WP13d — Batches | Batch list/status groups | Long names/status/actions wrap without overlap; batch links retain context |
| WP13e — Config | Config page forms/panels | Labels, choices, and save controls fit; no configuration behavior changes |
| WP13f — Pipeline diagnostics | Inspection/Controls layout only | Read-only details and existing operation controls remain contained and legible |
| WP13g — Help and task attention | Help content and task popup; `task_capture.css` for capture layout | Content/dialog fits; attention remains visible; no external task submission during checks |

Validation per row: syntax check of touched scripts; disposable screenshot/DOM bounds and keyboard/touch inspection for the named page at tablet and desktop widths, with phone fallback. The seven utility packets have been reviewed with fixture captures; Pipeline Controls is partial because of a missing fixture file.

### WP14 — Integrate, validate on-device, and document
- Dependencies: earlier packets.
- Files/interfaces: this plan and affected documentation owners; localized integration repairs only.
- Work: record final desktop/tablet/phone and physical-iPad results; finish affected UI/component documentation and code-map links. Keep page-specific follow-up repairs in their owning packet.
- Acceptance: every active page has a recorded finding/result; primary image journeys meet the target; no desktop regression; no unresolved critical clipping or missing action is marked complete.
- Validation: `npm.cmd run test:e2e` (existing four scenarios); syntax checks for changed JS; `git diff --check`; final diff review and physical-iPad acceptance. Complete/archive the plan only after required acceptance, documenting remaining limitations.

## Validation strategy

Use the existing isolated fixture and prepared responses from [Testing](../../Docs/Testing.md). Verify the chosen Python 3 interpreter before starting the fixture. Never run the capture tool against its default production URL merely to populate screenshots. No inference/render services, normal queues/indexes, external submissions, or live Narrative check are required.

Representative browser viewports: desktop 1920 × 911 and 1440 × 900; primary tablet 1133 × 610; reduced tablet height 1133 × 560; legacy tablet 1024 × 640; phone 390 × 844. Inspect the selected shell breakpoint just above/below it. Use touch-capability emulation where supported; this does not reproduce iPadOS clipboard permissions or browser chrome. Add portrait acceptance on the physical device rather than assuming landscape resizing is sufficient.

Disposable inspection should cover navigation collision with utilities visible, long context labels, a scrolled multi-candidate gallery, missing reference, pending/failed/selected/locked slots, long ranking text, updates during review, menus near viewport edges, and paste failures. Keep those checks disposable; no permanent tests, new browser downloads/dependencies, or expanded baseline are implicitly approved by this plan.

S1/S3 protect representative library/Narrative authoring and assembly; S2 protects front Assembly/Dressing selection/publication and is primarily API-driven; S4 protects shared AI Queue/model selection. They do not establish responsive image-review behavior or iPad clipboard compatibility. Run the existing suite after meaningful integration changes, avoiding a full rerun for every CSS adjustment. Report device acceptance separately from Chromium results. Ask approval before any proposal to retain new tests or materially expand maintained scenarios.

## Risks, unresolved points, and alternatives

- Actual iPad CSS dimensions, page zoom, browser/iPadOS version, and copied-image source remain unknown. The screenshot gives useful targets; physical-device acceptance resolves them.
- Loaded-fixture Chromium checks now verify dialog bounds, gallery return, focus-safe polling, and decisions at four sizes. The physical-iPad equivalent remains unverified.
- A blanket increase of the existing 1100-pixel media query would also change unrelated page layouts. Use focused shell and review rules instead.
- Sharing local review classes with Narrative increases regression risk; inspect both consumers whenever those rules change. Minor Characters and Image Generation retain their own lifecycle controllers.
- Clipboard behavior varies by copied representation and native approval. Choose image remains a first-class path; do not promise every app's copied item will be pasteable.
- If comparison images plus 44-pixel actions compete for height, collapse secondary details or make reference comparison optional before reducing image size or touch targets.
- Every listed active destination received fixture capture/containment inspection at five sizes. Several have only empty or prerequisite states in the fixture; that does not establish all populated states or real-device behavior. Pipeline Controls cannot load its full data without legacy Pipelines.json.

## Progress and decisions

- 2026-10-19: inspected shared shell/review/card/paste code, active route aliases, capture tooling, relevant architecture/component/invariant/testing documentation, and WebKit clipboard documentation. Repository was clean before planning.
- 2026-10-19: disposable Chromium probes reproduced child-button/utility overlap at 1133 pixels when task/GitHub utilities were visible. Modal probe changed scroll 1300 → 0 with current styles; a temporary fixed-position override preserved 1300 → 1300. No source implementation changes made.
- Implementation uses focused shell/card/dialog CSS, existing feature controllers, and one browser image-input adapter. No backend, API, serialized data, dependency declaration, creative source, normal queue/library, external ticket, or deployment changes were made.
- WP1/WP2: the capture tool now requires an explicit URL, preserves old captures, records revision/route/dimensions/browser/errors, and includes 1133-pixel landscape. Shared navigation compacts at 1360 pixels. All four pipeline destinations remain available; infrequent utilities move into Tools, with task attention always visible. Long-label and visible-utility checks passed at 1100/1101/1133/1360/1361/1440 pixels, including menu bounds.
- WP3–WP5: fixed local dialogs preserve gallery scroll and restore focus; images and decision controls are separated from scrollable details. Three actual fixture candidates were reviewed at 1133×610, 1133×560, 390×844, and 1440×900. Previous/next worked; API observation updates during polling preserved an unsaved Fail decision and expanded details. Screenshots were inspected. Local/Minor/Narrative/Image Generation cards now share selection and action colors/labels; selected and locked remain distinct.
- WP6: prepared Narrative synthesis/render/selection and reloaded viewing-first layout passed. Its single-image review stayed contained at tablet, short tablet, and phone sizes; reopening direction controls worked. Redundant inner chrome was reduced on compact screens. Existing S3 still protects the real prepared assembly/locking journey.
- WP7/WP8: Minor Character cards and comparison controls received shared styling/touch sizing; initial empty workspace captures were inspected. Image Generation settings collapse on compact screens; results fill the available width. Its fixed dialog keeps selection/navigation outside long prompt details. Browser-only prepared board checks passed with three images, selected protection messaging, and long prompts at three sizes. These board checks mock workspace responses and do not establish backend rendering.
- WP9–WP11: Paste image/Choose image adapters now cover Head source, generation references/reconstruction, Inventory import/add/replacement, Minor references, costume references, and task screenshots. Mocked clipboard image/empty/denied cases passed through actual Head-source upload and generation-reference handlers. Isolated browser helper checks also passed for nested file inputs, disabled state, and discarding a pending read after context changes. Other adapters reuse unchanged file handlers; native iPad clipboard approval remains unverified.
- WP12/WP13: 25 destinations × five viewports were captured. A phone Inventory overflow was found and fixed by overriding the older higher-specificity two-column rule. Final reports show zero horizontal overflow at all five sizes. The contact sheets and key full-size screenshots were inspected. Identity/Turnarounds/Costumes/Phase Comparison/Inventory/Zines share contained layouts; existing phase images stay paired in landscape. Standalone refinement HTML/CSS checks passed at tablet/phone/desktop sizes without invoking its model or adoption actions.
- Fixture limits: Pipeline Controls activation reports missing Traveler/Adult/Pipelines.json; its capture is partial. No populated Minor Character board, Zine, imported Adventure Log candidate, or native task-screenshot submission is claimed as an end-to-end check. Empty/prerequisite layouts and shared styles were inspected.
- A direct prepared Image Generation submission exposed an existing backend AttributeError: AdHocImageGenerationService._preset references self.app although the object has no app attribute (zet/services/ad_hoc_image_generation_service.py). The file is unchanged by this work. Backend repair is outside this UI plan; the generated-board visual check used prepared browser responses instead.
- Disposable workflow reruns against a reused fixture accumulated unanswered comparative-ranking work and then timed out awaiting initial ranking. Restarting the owned isolated fixture and reusing the prepared candidates completed the UI checks. No production or maintained backend change was made to accommodate this.
- The first maintained-suite run passed S2–S4 but S1 timed out on the desktop Overview button, now hidden at the suite's compact viewport. S1 navigation was repaired to use the visible section selector (or desktop buttons), retaining its original authoring purpose. The failure trace is retained under ignored test-results/ui-responsive. No maintained scenario was added.

## Final observed validation

- Final `npm.cmd run test:e2e`: **4 passed in 41.1 seconds**. S1 navigation repair retains its approved authoring task; no new maintained scenario.
- `node --check`: passed for zet.js, local_asset_pipeline.js, narrative.js, minor_characters.js, task_capture.js, image_input.js, and Scripts/capture-dashboard-ui.mjs.
- `git diff --check`: passed. Final diff review found only the scoped presentation, capture-tool, approved-scenario navigation repair, and documentation changes.
- Additional static browser checks confirmed 18-pixel radio controls inside 44-pixel labels and distinct failure/selection/lock text colors at phone/tablet/desktop widths.
- Shared card state attributes are presentation only; backend flags still determine all eligibility/protection behavior. The capture tool also records whether the worktree has uncommitted changes.
- No significant durable architecture change required an ADR. Docs/COMPONENTS/DASHBOARD_UI.md owns new shared browser responsibilities; affected knowledge links were synchronized.

## Final results

Local UI implementation is complete. WP14's physical-iPad acceptance remains open, so the plan stays active. Review on Joe's iPad: confirm actual viewport/zoom, open/close review from a scrolled gallery, compare/select/navigate, and try copying from Photos and browser image content, including native Paste approval and Photos/Files fallback. No deployment was performed.

Observed validation and remaining limits are also recorded in Docs/Testing.md and Docs/DEVELOPMENT.md. Captures and disposable scripts live under ignored test-results/ui-responsive and test-results/ui-responsive-final; they are inspection artifacts, not new permanent tests.
