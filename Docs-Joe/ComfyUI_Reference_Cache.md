# ComfyUI Qwen Image 2.1 reference cache

Zet's Qwen Image 2.1 workflows use ComfyUI's built-in `QwenImage21Cache` node for image-conditioned jobs. The reference-capable presets default to CPU storage with INT8 quantization. This applies to reference-based body, head, character-edit, and scene jobs submitted through AI_Proxy's normal render worker.

Custom profiles can set `qwen_cache_enabled` (`true` by default), `qwen_cache_device` (`cpu` by default; `auto`, `cpu`, `gpu`, or `off`), and `qwen_cache_dtype` (`int8` by default; `default`, `int8`, or `int4`). Set `qwen_cache_enabled` to `false` to restore the previous workflow graph and ComfyUI's automatic cache behavior.

Compilation debug output and `ComfyUI_Render_Metadata.json` record the configured cache settings, reference count, inserted node ID, and any skip reason. If the ComfyUI server does not advertise `QwenImage21Cache`, Zet logs a warning and submits the uncached graph; this fallback does not meet the managed AI_Proxy cache acceptance requirement. ComfyUI still decides whether the configured cache fits its available memory.
