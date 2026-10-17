# Zet / AI_Proxy storage recovery
Status: implementation complete; isolated validation complete, 2026-10-17.
Related specification: Joe's approved storage fault-tolerance plan, 2026-10-17.

## Goal and contracts
Survive unavailable E: storage during polling and startup. Keep authored data,
indexes and transport on their configured paths; journal recovery on local C:.
Resume unfinished work, including unknown-cause interruptions, without repeating
successful execution or overriding cancellations, human decisions or locked images.
One execution per transport attempt; replacement attempts belong to Zet.

## Packets
Each packet is sequential, single-implementer work; no delegation is authorized.

| Packet | Owners / dependencies | Acceptance and validation | Status |
| --- | --- | --- | --- |
| WP1 | Storage health services and local journals; none | Durable identities, two-second probing/two-success recovery, local leases; isolated checks | complete |
| WP2 | Proxy engine/supervisor startup; WP1 | Missing queue never kills polling or creates false results; existing proxy suite | complete |
| WP3 | Native worker/engine/backend evidence; WP1-2 | Local execution/submission evidence, retained outcomes, safe interrupted classification; proxy suite | complete |
| WP4 | Zet AI jobs/repository/coordinator/continuations; WP1/3 | Stable logical identity, fenced replacement reservation, verified frozen inputs; S4 | complete |
| WP5 | Zet bootstrap/harvester/recovery service; WP1/4 | Startup offline and reconnect without restart, all-universe reconciliation; S1-S4 | complete |
| WP6 | Local character adapters/overview/campaign/slots; WP4-5 | Resume orphaned unfinished targets, preserve stop/review/locks; S2 | complete |
| WP7 | Narrative/image/minor/costume/reconstruction continuations; WP4-5 | Shared pending/retry handling, source fences and child ordering; S3-S4 | complete |
| WP8 | Catalog/index/discovery repositories; WP1/5 | No incomplete index publication or replacement authoritative catalog; S1 | complete |
| WP9 | Status/UI/docs/ADRs; all | Visible pause/recovery and recorded validation; both approved suites and diff checks | complete |

## Validation
Use disposable data and controlled workers only. Exercise outage/reconnect and
restart at publication, execution, collection and index boundaries; repeated
recovery; stopped/completed work; stale results and unavailable catalogs.
Run `npm.cmd run test:e2e` in Zet and `.venv/Scripts/python.exe -m pytest -q`
in AI_Proxy, plus `git diff --check` in each. No permanent tests or live inference.

## Impact / documentation
Affected: shared AI job/queue contracts, startup, local character and Narrative
workflows, authoritative catalog and derived-index boundaries, status interfaces.
Update owning component/data/invariant/code-map docs and recovery ADRs.
Preserve pre-existing uncommitted managed-ComfyUI recovery work in AI_Proxy.

## Progress and results
Implemented ownership and operational contracts are documented in
[Storage recovery](../../Docs/COMPONENTS/STORAGE_RECOVERY.md) and
[ADR 0022](../../Docs/DECISIONS/0022-removable-storage-recovery.md).
Both project virtual environments were verified as Python 3.

Final approved checks: Zet `npm.cmd run test:e2e`: **4 passed (38.7s)**;
AI_Proxy `.venv/Scripts/python.exe -m pytest -q`: **6 passed, 1 deselected
(13.14s)**. Python compilation, both modified JavaScript syntax checks and
`git diff --check` in both repositories passed.

Disposable checks exercised absent-storage startup and reconnect, fresh-attempt
replacement and single logical collection, C-resident continuation replay,
surviving worker fencing across proxy restart, independent cloud work while the
local lane was occupied, queue rename/reconnect, wrong-root rejection, bounded
stalled probes, SQLite I/O classification, index scan failure preserving the
committed generation, missing-catalog protection, child submission reattachment,
recovery callback ownership rechecks, and offline TUI unknown counts.

Discoveries incorporated: Windows exited processes can retain queryable handles;
worker ownership therefore checks liveness as well as creation identity. An
orphan worker consumes its original execution lane until settled. Recovery probes
must not hold coordination locks during blocked OS calls. Logical collection
requires a receipt recheck under its lock. Replacement staging must exclude its
old manifest from its immutable inventory. Test fixtures needed isolated runtime
metadata and the actual transport attempt identifier; the existing helper was
corrected without adding scenarios. Existing AI_Proxy managed-ComfyUI changes
were preserved.

Validation boundaries: no real E: disconnection, live inference, production queue
exercise, deployment, or production restart. Full live Body/Head adapter recovery
was not exercised; their shared recovery dispatch was checked with controlled
adapters, alongside the approved character scenario. Missing immutable inputs,
confirmed catalog corruption and unresolved external backends remain actionable
conditions. No permanent tests, scenarios, frameworks or dependencies were added.

Documentation link inspection checked 733 local links across changed documents.
Recovery links resolve. One pre-existing unrelated link in `Docs/DEVELOPMENT.md`
targets the absent `Scripts/copy-three-runtime.mjs`; it was left outside scope.
