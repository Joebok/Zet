# AI Proxy resource keys

AI Proxy may reorder ready filesystem jobs to reduce model loading. It runs at
most five consecutive jobs with the same resource key before selecting the
oldest job with a different key. HTTP inference requests retain priority and
their model becomes the active resource for the next filesystem selection.

`resource_key` belongs in the outer `job.json` file-proxy manifest. It is not a
replacement for `worker_type`, `ollama_model`, `image_generation`, or
`checkpoint` in `ask_manifest.json`.

Zet's `FileProxyClient.publish()` writes the key automatically:

| Work | Format | Example |
| --- | --- | --- |
| Ollama | `ollama:<ollama_model>` | `ollama:vision-analysis:latest` |
| ComfyUI | `image:comfyui:<checkpoint>` | `image:comfyui:perfectdeliberate_v90.safetensors` |
| Stable Matrix | `image:stable_matrix:<checkpoint>` | `image:stable_matrix:juggernautXL.safetensors` |

Use the managed defaults when the ask omits a model or checkpoint:

- Ollama: `ollama:general-purpose:latest`
- Local image: `image:<backend>:default`

Rules:

- The key identifies the expensive reusable memory resource, not the task.
- Do not include job IDs, seeds, stages, prompt names, or output paths.
- Equivalent jobs must produce exactly the same key.
- Different Ollama models, image backends, or checkpoints must produce
  different keys.
- Do not publish a job until all of its inputs exist. A job that needs another
  job's output must be published only after that answer has been harvested.
- Custom producers that bypass `FileProxyClient` must follow the same formats.

HTTP Proxy derives `ollama:<model>` from JSON `model` fields on Ollama and
OpenAI-compatible inference routes. It does not tag model-management routes
such as `/api/pull`, and it does not rewrite a client's `keep_alive` value.

Before entering Ollama work, AI Proxy makes a best-effort call to Forge Neo's
`/sdapi/v1/unload-checkpoint` endpoint. This applies equally to filesystem and
HTTP Ollama work. Consecutive Ollama resources do not repeat the call. Forge
connection or HTTP failures from this optional unload call are ignored. Forge
render jobs still report backend availability failures normally.

## Prompt for updating a custom Zet producer

> Update this Zet file-proxy producer to add `resource_key` to the outer
> `job.json` manifest. For `ollama_generate`, use
> `ollama:<ollama_model-or-general-purpose:latest>`. For
> `local_image_render`, use
> `image:<image_generation-or-stable_matrix>:<checkpoint-or-default>`. Keep
> `ask_manifest.json` fields unchanged. Do not include task IDs, seeds, stages,
> or paths in the key. Prefer calling `FileProxyClient.publish()` instead of
> hand-writing `job.json`. Add tests proving equal resources receive equal keys
> and different models/checkpoints receive different keys.
