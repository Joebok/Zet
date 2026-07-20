# Forge Couple Scene Rendering

## API contract

Zet uses the Stable Diffusion WebUI Forge `txt2img` endpoint and the `sd-forge-couple` always-on script. The installed server registers the script as lowercase `forge couple`. The current upstream API contract has 17 positional arguments, not the older seven-argument format.

Source: <https://github.com/Haoming02/sd-forge-couple/wiki/API>

For Basic/Horizontal scene rendering, Zet sends:

```json
{
  "prompt": "global scene prompt\nleft subject prompt\nright subject prompt",
  "negative_prompt": "negative prompt",
  "alwayson_scripts": {
    "forge couple": {
      "args": [
        true,
        true,
        "Basic",
        "",
        "Horizontal",
        "First Line",
        0.5,
        null,
        "{ }",
        false,
        true,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    }
  }
}
```

The arguments are:

1. Enable Forge Couple.
2. Enable compatibility mode, which disables Forge Couple during Hires Fix.
3. Region assignment mode.
4. Separator; empty means newline.
5. Basic-mode tile direction.
6. Global-effect line.
7. Global-effect weight.
8. Advanced/Mask mapping; unused in Basic mode.
9. Common-prompt parser.
10. Common-prompt debug mode.
11. Include common-prompt definitions.
12–17. Tile Mode arguments; unused and sent as `null`.

## Root cause

The Local Image Config setting was saved as `LayoutBackend = "forge_couple_basic"` and caused scene compilation to create `Local_Render_Forge_Couple_Prompt.md`. The render route queued that Markdown file, but the Stable Matrix adapter only understood ordinary `prompt:` and `negative:` text. It flattened the regional lines and never constructed `alwayson_scripts`, so Forge Couple was not activated.

The old Markdown also included background scenery as a separate horizontal region. For a two-character scene, that produced three regional tiles instead of the intended left and right subject tiles.

## Implementation plan

- Use `Local_Render_Brief.json` as the structured scene-layout source.
- Build Forge prompt lines as one global environment/scenery line followed by visible subjects ordered left-to-right.
- Stage scene renders through a backend `ZetApp` action rather than discovering layout behavior in the FastAPI route.
- Carry an optional, backward-compatible `render_layout` object in the local-image queue manifest.
- Have the local-image worker forward `render_layout` only when the selected adapter supports it.
- Have the Stable Matrix adapter preserve newlines, append positive global terms only to the first line, and emit the exact 17-argument `alwayson_scripts["forge couple"]` contract.
- Verify `forge couple` is registered before rendering and report an explicit error when it is unavailable.
- Use ordinary `txt2img` without `alwayson_scripts` when Forge Couple is disabled or a scene has fewer than two visible subjects.
- Keep `Local_Render_Forge_Couple_Prompt.md` as a human-readable inspection artifact, not as the machine API contract.

Advanced and Mask region assignment are outside the initial implementation.

## Acceptance criteria

- A Forge-enabled two-subject scene produces one global prompt line and one line for each subject.
- Background scenery remains in the global line and does not become another horizontal tile.
- `Stable_Matrix_API_Call.json` contains `payload.alwayson_scripts["forge couple"]` with all 17 arguments.
- Positive prompt globals appear only on the global line; negative globals remain in `negative_prompt`.
- Disabling Forge Couple removes `alwayson_scripts` from subsequent scene render payloads.
- Zero- and one-subject scenes render through the plain path without Forge Couple errors.
- A missing Forge Couple installation produces a clear failure instead of silently rendering without regional conditioning.
- Existing non-scene and legacy queue manifests continue to render unchanged.
