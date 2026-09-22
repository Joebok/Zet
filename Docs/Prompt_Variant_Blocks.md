# Prompt variant blocks

Configured image pipeline templates support `prompt_variant="generation"` (the default) and `prompt_variant="analysis"`. Put hard-coded guidance that belongs to only one output between matching tags:

```md
<!-- ZET:BEGIN IMAGE_PROMPT_ONLY -->
Generation guidance.
<!-- ZET:END IMAGE_PROMPT_ONLY -->

<!-- ZET:BEGIN ANALYSIS_PROMPT_ONLY -->
Review guidance.
<!-- ZET:END ANALYSIS_PROMPT_ONLY -->
```

Text outside tagged blocks appears in both outputs. Blocks cannot nest. Filtering happens before character sections are selected and rendered, so tagged blocks control template text without changing character-template content. The configured character pipeline compilers, Scene Appearance compiler, and Story Scene prompt compiler accept the same `prompt_variant` switch. Compile the two variants into separate output directories when saving both for one asset.
