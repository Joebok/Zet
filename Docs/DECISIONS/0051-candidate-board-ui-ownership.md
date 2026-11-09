# 0051 - Candidate Board UI ownership

## Context

Candidate grids already share some presentation helpers. Each workflow still
manages its own review and refreshes card and modal markup independently.

## Decision

The shared Candidate Board owns the controls, grid, and review DOM. The page
controller owns workflow requests and publishes accepted results through
`update(model)`. This gives a poll result or successful action one path to
the card and any open review. Actions use existing handlers and surface their
errors locally. Existing workflows and services retain eligibility,
publication, and protected-effect confirmation rules.

## Consequence

Each workflow can adopt the module independently by supplying a normalized
model and an action adapter. See the
[subscriber guide](../COMPONENTS/CANDIDATE_BOARD_INTEGRATION.md).
