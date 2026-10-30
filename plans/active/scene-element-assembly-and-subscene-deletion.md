# Scene element assembly and subscene deletion
Status: active

## Goal
Add scene element reference images as pinned assembly layers and allow subscene deletion from scene properties.

## Packets
- WP1: Assembly service and scene detail: bind scene element references with server-owned pinned copies; validate isolation and compatibility. Status: implemented; disposable checks passed for pinned reference loss and foreign element rejection.
- WP2: Narrative dashboard: add element layer and protected subscene deletion controls. Depends on WP1. Status: implemented; dedicated isolated browser checks pending.
- WP3: Narrative and data-model documentation updated. `npm.cmd run test:e2e` passed four scenarios; `git diff --check`, JavaScript syntax and Python compilation passed. Status: pending dedicated browser checks and final archival.

## Constraints
Preserve existing pinned layers, image protection, universe isolation and frozen job inputs. No permanent tests or live model calls.
