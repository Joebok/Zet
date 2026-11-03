# 0046 — Character Activity reports active work and dismissable errors
Status: accepted
Date: 2026-11-03

## Context
Character operation records originally appeared in a shared Activity menu after
they had queued work or encountered expected input/prerequisite blocks. This mixed
preparation progress with durable history and made old errors look like recurring
guards against a new action.

## Decision
The Activity projection contains only in-progress preparation and undismissed
errors. Successful, partial and expected blocked outcomes leave Activity when
preparation settles; expected reasons remain in the affected batch/view workflow.
Errors can be dismissed without mutating their execution checkpoint. A dismissed
or terminal Activity record does not prevent a new operation admission; domain
ownership, reservation, attempt and publication checks still run when that operation
executes. Terminal records remain briefly for request identity recovery.

The browser refreshes Activity on navigation, menu open, tab return, submission or
explicit request. Navigation closes the menu. No Activity timer runs while idle.
