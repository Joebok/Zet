# Orientation gate investigation and pause point

**Date:** 2026-09-23  
**Status:** Disabled by default in the shared gate registry; this is an investigation record, not an enabled-gate recommendation.

## What the gate should decide

For `FRONT_LEFT_3_4`, the saved prompt defines a frontal three-quarter view: face and torso point toward **IMAGE_LEFT**, the nearer anatomical left side appears on **IMAGE_RIGHT**, and both the front and side of the torso are visible. The attached example and candidate `c009` appear to meet that definition. Direct Ollama application chat with `image-analysis-alt` returned `TRUE` in the user's tests, while queued gate calls often returned `FALSE`, including the visibly incorrect explanation that the subject faces IMAGE_RIGHT.

The concrete reproduction is run `20260923_014156_870344`, candidate `c009`. Its staged `candidate.png` SHA-256 is `676357b58d928d36df793fefc800273c59a3152eb2a1f8e11b810ccad00b8729`, matching the source candidate image. The saved `OLLAMA_PROMPT.md` contains the intended `FRONT_LEFT_3_4` definition, and the ask manifest lists exactly that `candidate.png`. The AI Proxy reads the listed image file and base64-encodes its bytes into the Ollama request. This evidence did **not** show an incorrect, swapped, or mirrored image being sent. It does not prove that every earlier request had the correct image; capture hashes per request when work resumes.

The referenced run was later deleted, so its saved artifacts are no longer a live regression fixture. Create a new batch and collect fresh cases in the gate test rig when work resumes. Enable the production gate only after validation.

## Request changes and observed results

| Request variant | Observation |
| --- | --- |
| Initial queued `/api/generate`, `think:false`, `temperature:0.1` | Repeated false negatives on the example, including IMAGE_RIGHT reasons. |
| Thinking enabled for all gates | Some orientation calls spent the entire alias `num_predict:4096` budget in thinking and returned no final response (`done_reason=length`). An early worker version wrote an empty verdict as a successful answer, which surfaced in Zet as “AI Proxy answer is missing its output file.” The worker now saves returned thinking, treats an empty final answer as an error, and retries a length-limited thinking response once with an added brevity instruction. This did not make orientation reliable. |
| `/api/chat`, `temperature:1.0`, `think` omitted | A controlled alias call used its default thinking behavior and exhausted the output budget without a final answer. A retry with a brevity instruction returned `TRUE` but was much slower than the user's Ollama app chat. |
| `/api/chat`, `temperature:1.0`, explicit `think:false`, alias `image-analysis-alt:latest` | A saved c009 ask returned `TRUE` in 0.95 seconds with 6 evaluation tokens. The user still observed too many failures across the broader workflow, so this single success is not an acceptance result. |
| `/api/chat`, `temperature:1.0`, explicit `think:false`, direct `gemma4:12b` | One controlled call returned `FALSE` with an IMAGE_RIGHT explanation. This single comparison is not a model accuracy benchmark. In Zet's normal workflow, the direct base model also failed the runtime-evidence check before inference because it lacks managed `num_ctx` and `num_predict` settings. |

The successful queued c009 ask is `Ask_LocalBodyReference_20260923_014156_870344_c009_ORIENTATION_20260923_074019_703212`. Its answer bundle contains `ask_manifest.json`, `candidate.png`, `OLLAMA_PROMPT.md`, `answer_manifest.json`, and a verdict file containing `TRUE`. The ask manifest records `ollama_chat:true`, `ollama_think:false`, and `ollama_temperature:1.0`. The answer manifest records alias digest `032228f076384a1892c7559d8ae7d9c1b1e5fb4573951592262abccc3a97eea5`, `num_ctx:65536`, `num_predict:4096`, `done_reason:stop`, and `eval_count:6`. Saved answer bundles are under `C:\Users\Joe\Dropbox\AI_Queue\File_Proxy\Answer\zet\`.

The alias Modelfile is `C:\Users\Joe\Projects\ModelUpdater\Modelfiles\image-analysis-alt.Modelfile`. It wraps `gemma4:12b` and manages `num_ctx 65536`, `num_predict 4096`, `num_batch 128`, `num_gpu -1`, and `num_thread 8`. Its `# Think level: medium` line is a comment, not a setting. Local `/api/show` evidence for the alias and base model reported supported thinking values `false` and `true`, with default `true`; omission of `think` therefore did not reproduce explicit `think:false`. The alias can centralize a model name and runtime settings, but model swaps still need per-gate request settings and regression checks.

## Current code behavior

The orientation gate is still listed in the dashboard and defaults to **Disabled** in `local_gate_registry_service.py`. During candidate gate processing, Zet records orientation status `DISABLED`, with the stored passing verdict `FALSE`, and does not queue an Ollama orientation request. Other gates continue. A saved gate-policy override can change the effective status. Previous orientation records are archived in gate history when replaced. A view already failed or rejected on an old orientation result may need **Re-evaluate view** to run through the current policy using its existing candidate image. The orientation model prompt treats `TRUE` as a match and `FALSE: <reason>` as a mismatch; Zet converts that response to the shared stored rejection verdict.

The dormant orientation request configuration remains `/api/chat`, `think:false`, and `temperature:1.0` in `zet/services/local_body_reference_service.py`. The AI Proxy request and thinking capture are in `AI_Manager/ollama_proxy_worker.py`; the dashboard label is in `zet/web/templates/local_body_reference.html`. Do not treat the dormant request settings as a validated fix.

## When resuming

1. Build a labeled fixture set for every required view, including c009 and clear negative examples. Measure false accepts, false rejects, latency, and empty answers across repeated runs before enabling the gate.
2. Compare the **exact** Ollama app and AI Proxy requests: endpoint, model and digest, prompt/system/history, image bytes or SHA-256, `think`, sampler options, context/output limits, seed, and keep-alive. Record the actual effective settings where Ollama exposes them. The application's request shape has not yet been independently captured.
3. Keep a trace for each attempt: prompt and image hashes, ask ID, alias digest, request options, final answer, returned thinking, `done_reason`, token count, and duration. An empty final answer must remain an error, even when thinking text exists.
4. Choose an explicit gate policy for each qualified model. Test `think:false` for a fast classification gate rather than relying on omission and a model-specific default. If direct base models should be allowed, revise and test the managed-runtime-evidence contract separately.
5. Re-enable orientation only after the fixture results meet an agreed threshold, then re-evaluate old affected views.
