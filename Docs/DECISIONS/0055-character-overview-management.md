# 0055 - Character overview management

Character and phase rename actions belong on the Character Overview page. They
move universe-owned workflow folders and preserve stable catalog IDs, aliases,
prompts and image bytes. A rename journal under `_state/CharacterManagement`
allows the next management request to finish an interrupted move and metadata
rewrite. Renames reject active container renders and pending publication journals.

Character and phase deletion archive their universe-owned folders. Whole-character
deletion reviews associated catalog image usage and verifies that the phase list
still matches the reviewed snapshot. It rejects active container work and pending
publication journals. Phase deletion retains its existing image confirmation.

The overview separates workspace navigation (card title) from image review (locked
image opens the full-screen viewer). The Base Images template editor remains
available from its summary line while that section is collapsed.

Implementation references: `CharacterManagementService`, `LibraryDeletionService`,
and `LocalCharacterOverviewService`. Validation is recorded in the active plan
until isolated management journeys have been completed.
