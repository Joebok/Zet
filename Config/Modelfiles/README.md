# Zet image model aliases

The first two Ollama aliases prepare vision-capable models from different model families for Zet pipeline testing. A third Inkling candidate and its runtime blocker are documented below. The Modelfiles inherit each base model's chat template and image support. Zet continues to supply its task prompts, schemas, and attached images through AI_Proxy.

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

## Inkling 2 Mini candidate: Zet-Image-3

`Zet-Image-3.Modelfile` defines a third alias for Inkling 2 Mini. It is **not yet runnable or qualified on this machine**. On 2026-11-22, the installed Ollama version was 0.40.16, the GPU was an NVIDIA GeForce RTX 5060 Ti with 16,311 MiB VRAM, and Windows reported about 25.8 GiB usable system RAM.

The [official Ollama package](https://ollama.com/library/inkling-2-mini) is about 20 GB. An [Ollama maintainer confirms all current library variants use MLX](https://github.com/ollama/ollama/issues/19817), including tags without the MLX label. That package exceeds this GPU's VRAM before context and image processing. The [pending Ollama runtime update](https://github.com/ollama/ollama/issues/19826) is also needed for GGUF inference and its vision projector. Lowering context cannot fix missing architecture support. Do not install an experimental runtime or change AI_Proxy for this alias.

The candidate instead uses `hf.co/bartowski/thinkingmachines_Inkling-2-Mini-GGUF:IQ3_XS`. Its registry manifest was checked without downloading weights: it contains 13,765,229,632 bytes of model weights and a 639,348,512-byte vision projector, about 13.4 GiB combined. This lower-precision variant leaves more GPU headroom than the publisher's 15.09 GB IQ4_XS variant. It trades model quality for memory headroom; full GPU residency and task quality still need measurement.

The initial context is 32,768 tokens rather than the first two aliases' 65,536, with the same 12,288-token output limit. Sampling follows [Inkling's recommended settings](https://unsloth.ai/docs/models/inkling-2-mini): temperature 1.0, top-p 1.0, top-k 0, and min-p 0.0. These are starting settings, not a measured optimum. The base model supplies the chat template, stop tokens, and image support.

After an Ollama release explicitly supports Inkling GGUF text and vision on Windows, the following creation commands can be used. They have not been run:

```powershell
$ollama = (Get-Command ollama).Source
& $ollama pull hf.co/bartowski/thinkingmachines_Inkling-2-Mini-GGUF:IQ3_XS
& $ollama create Zet-Image-3 -f 'C:\Users\Joe\Projects\Zet\Config\Modelfiles\Zet-Image-3.Modelfile'
& $ollama show Zet-Image-3
& $ollama show --parameters Zet-Image-3
```

Before selecting the alias for Zet work, confirm vision capability and run an explicitly requested representative image-backed check through AI_Proxy. Check context, actual GPU residency, completion, and elapsed time. Refresh Zet's model catalog and verify `Zet-Image-3:latest` exposes `text`, `vision`, and `structured_json` capabilities. Use `ollama:Zet-Image-3:latest` in Zet_Tester only after that qualification. Keep trials serial; the 32K context is not directly comparable to the first two aliases at 64K.

## References

- [Qwen3.5 9B Q8 in Ollama](https://ollama.com/library/qwen3.5:9b-q8_0)
- [Gemma 4 12B in Ollama](https://ollama.com/library/gemma4:12b)
- [Inkling 2 Mini GGUF variants and projector](https://huggingface.co/bartowski/thinkingmachines_Inkling-2-Mini-GGUF)
- [Ollama Modelfile reference](https://docs.ollama.com/modelfile)
- [Ollama context length and GPU allocation](https://docs.ollama.com/context-length)
