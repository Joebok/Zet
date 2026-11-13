# Character Wizard head-image framing

Status: complete

Gia's no-reference FRONT rendered as torso portraits despite the existing upright, eye-level instruction. The published template described the nape-length hair without specifying a crop boundary.

## Work packets

1. Update the shared Character Template Instructions with short, long, exceptionally long, and unknown hair framing guidance. Check the placement against both local head compilers.
2. Update CharacterWizardService to require the crop in its authoring request for new characters and explicitly requested framing edits. Keep the existing draft and acceptance interfaces.
3. Verify disposable short and mid-back drafts through publication, both head compilers, and saved-prompt Luna review. Run `npm run test:e2e` and `git diff --check`. Document the wizard behavior in Local Characters. Live Zet Tester comparison requires separate authorization.

## Results

Two disposable prepared wizard responses passed draft validation and explicit
publication in an isolated Test universe. Both head compilers preserved the
authored crop on no-reference FRONT and a source-backed front-left three-quarter
view, for eight checks total. The Edit compiler omitted FRONT identity prose on
the derived view and emitted the crop criterion in its review artifact. Captured
Luna requests included each crop through the candidate's saved prompt.
The captured wizard request included the exceptionally long and unknown-endpoint
guidance.

`npm run test:e2e` passed all four maintained scenarios. `git diff --check`
passed. Live visual acceptance remains pending separate authorization.
