# Minor Character independent slot controls
Status: complete

## Goal and current behavior
Slot rendering currently blocks the whole workspace; redundant inline comparison/actions appear below the cards. Permit independent slot operations while queued renders run, streamline cards/review and clarify new iterations versus refinements. Preserve frozen prompts, original comparison choice, working selections and published bytes.

## Luna-sized packets
### WP1 - Independent slot submission and direct candidate locking
- Files: minor_character_service.py, minor_character_router.py.
- Dependencies: none. Remove workspace-wide slot busy guard; clear/replace board bindings independently. Submit saved payloads to the queue while holding the existing workspace lock, avoiding unowned QUEUING records and workspace task fencing collisions. Optional candidate ID makes direct lock atomic.
- Acceptance: multiple slot renders coexist; clearing/replacing an active slot cannot put its late result back; other jobs/selections/locks remain intact.
- Validation: disposable prepared-response service checks; Python syntax.
- Status: complete.
### WP2 - Card controls and clear generation wording
- Files: minor_characters.js, index.html, zet.css.
- Dependencies: WP1. Remove redundant comparison/actions; move comparison picker under primary identity; show findings expanded; four compact card controls (Clear, Generate/Regen, Select, Lock) and review Lock. Explain new iteration action versus refinement.
- Acceptance: all slot controls usable while other jobs run; paired review retained; suggestions immediately visible and tied to previewed candidate; desktop/narrow layout usable.
- Validation: disposable browser check and node syntax.
- Status: complete.
### WP3 - Documentation and regression verification
- Files: LOCAL_CHARACTERS, DATA_MODEL, CODE_MAP, active plan.
- Dependencies: WP1-2. Update affected owners and record actual results.
- Validation: existing three approved E2E scenarios; git diff --check; final diff review. No permanent tests, dependencies, live rendering, production writes or deployment.
- Status: complete.

## Discoveries and implementation decisions
Slot requests package saved payloads into the existing image queue under the workspace lock; rendering itself remains asynchronous. This avoids the single analysis/render task fence and makes allocation plus submission recoverable without an unowned QUEUING gap. The browser tracks pending slot submissions independently. Clearing or replacing a running slot retains its old candidate/job internally; late images never alter the new board binding.

Direct card/review Lock accepts candidate_id and atomically selects/publishes it. Browser verification exposed a pre-existing publication collision: two candidates from one revision/view reused the same unique Inventory origin key. Extended WP1 into quick_character_publication_service.py to use candidate-scoped origin keys for Minor Characters, matching existing candidate-based asset IDs. Existing records/files remain readable; no schema migration.

Expanded findings made the tall right column unsuitable for sticky positioning; it now scrolls normally from the top alongside the inputs. All four card actions share a compact wrapping row.

## Observed validation
- Disposable minor-independent-check.py passed: queue/add/clear/regenerate while other jobs remain queued; running-slot replacement; late result board integrity; exact frozen-payload replay; direct lock and retained locks after clear.
- Existing disposable minor-iterations-check.py and minor-character-check.py passed, covering frozen iteration inputs, legacy adoption, naming, display-only references, side-view generation, publication and input edits.
- Disposable minor-independent-browser.mjs passed, including final rerun after layout/title refinements: independent slot jobs, active clear/regen/add, card/review lock replacement, keyboard review, compact controls, moved reference selector, expanded findings, removed duplicate comparison, widths 1800/1440/850/640. Screenshot inspected. Initial browser run exposed the Inventory origin-key collision described above; fixed and rerun successfully.
- npm.cmd run test:e2e: all three approved scenarios passed (27.6s). No permanent tests or dependencies added.
- Python AST, node --check and git diff --check passed; final diff reviewed.
- Updated component, data-model and code-map owners. No normal library writes, live generation, commits, push or deployment. Owned fixture server stopped.

## Final result
Independent slot iteration, streamlined cards and review locking, expanded findings, relocated comparison choice and explicit new-iteration/refinement wording are complete locally.
