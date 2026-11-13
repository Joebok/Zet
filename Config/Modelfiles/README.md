# Zet image model aliases

These Ollama aliases prepare two vision-capable models from different model families for Zet pipeline testing. The Modelfiles inherit each base model's chat template and image support. Zet continues to supply its task prompts, schemas, and attached images through AI_Proxy.

| Alias | Base model | Family / publisher | Approximate base download |
| --- | --- | --- | --- |
| `Zet-Image-1` | `qwen3.5:9b-q8_0` | Qwen 3.5, Alibaba | 10 GB |
| `Zet-Image-2` | `gemma4:12b` | Gemma 4, Google DeepMind | 7.6 GB |

Both aliases set a 65,536 token context, 12,288 output tokens, and temperature 0.2. Start live testing at 64K. The configured context may use additional VRAM. AI_Proxy stops its managed ComfyUI process before Ollama work, but confirm actual residency and performance using `ollama ps`. If a model spills to CPU, exhausts memory, or exceeds a job deadline, recreate both aliases at 48K and then 32K until they share a usable setting. Keep comparison trials serial.

## Install or refresh the base models

Open PowerShell. The Ollama CLI communicates with the local Ollama server. Zet jobs themselves must continue through AI_Proxy.

```powershell
$ollama = (Get-Command ollama).Source

# Run these only when the base model is missing or you want to refresh its tag.
& $ollama pull qwen3.5:9b-q8_0
& $ollama pull gemma4:12b

& $ollama create Zet-Image-1 -f 'C:\Users\Joe\Projects\Zet\Config\Modelfiles\Zet-Image-1.Modelfile'
& $ollama create Zet-Image-2 -f 'C:\Users\Joe\Projects\Zet\Config\Modelfiles\Zet-Image-2.Modelfile'

& $ollama show Zet-Image-1
& $ollama show Zet-Image-2
& $ollama show --parameters Zet-Image-1
& $ollama show --parameters Zet-Image-2
& $ollama ps
```

Check that `ollama show` reports vision capability and that parameters show `num_ctx 65536`, `num_predict 12288`, and `temperature 0.2`. After a representative long request, use `ollama ps` to confirm `CONTEXT` is 65536 and `PROCESSOR` is fully GPU. Record the timestamp, versions, `ollama list` IDs, and digests from `ollama show --verbose` (or the `/api/show` response) for both base models and aliases. Repeat measurements after any base pull because a tag can move.

## Make aliases visible to Zet

AI_Proxy discovers Ollama models in its shared capability catalog. In Zet, open Settings and refresh the AI model list, or request a catalog refresh through Zet's existing `/api/ai/models` action. Confirm the catalog lists the exact IDs `Zet-Image-1:latest` and `Zet-Image-2:latest` with `text`, `vision`, and `structured_json` capabilities before selecting them. Do not configure Zet to call Ollama directly.

Zet_Tester case files use the provider-qualified form `ollama:Zet-Image-1:latest` or `ollama:Zet-Image-2:latest`. Its runner still holds Luna Review fixed, so current A/B runs compare authoring and vision tasks, not local candidate ranking.

## Comparison notes

Use identical source images, instructions, settings, and fresh workflow names for each alias in the isolated `ZetTester` universe. Run one inference at a time through the dashboard and AI_Proxy. Begin with Character Wizard and image-backed Template Improvement, then test Minor Character authoring and Narrative interview and synthesis. Capture model provenance and base/alias digests, actual image attachment order, configured context, GPU offload, elapsed time, prompt/output token counts when available, schema and application validation, and visual observations.

Begin with Zet's existing prompts. For repeated failures, inspect truncation, context pressure, image grounding, JSON completion, and exact-text or field validation before deciding whether prompt instructions need adjustment. Compare both models at the highest context setting that passes the same long-request check.

## References

- [Qwen3.5 9B Q8 in Ollama](https://ollama.com/library/qwen3.5:9b-q8_0)
- [Gemma 4 12B in Ollama](https://ollama.com/library/gemma4:12b)
- [Ollama Modelfile reference](https://docs.ollama.com/modelfile)
- [Ollama context length and GPU allocation](https://docs.ollama.com/context-length)
