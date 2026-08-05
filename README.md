# Zet - Character Image Creation Pipeline

Zet is a Python-based pipeline and asset management tool for image generation, particularly aimed at identity preservation of main characters and scene building for use in comic/graphic novel type presentations. 

Zet combines text information from templates and .json files to compile "final image prompts" and marshall resources for final image rendering in an image generation tool such as ChatGPT. Zet does have some meager local image generation features, but at the time of this writing those are largely experimental.

Zet is a personal project whose primary use is for the author, me, to generate images from my D&D sessions and create Zines of my character's backstory. Zet currently goes hand in hand with a ChatGPT plus subscription. Local AI and Image generation is done via a file proxy app (https://github.com/Joebok/AI_Proxy) to throttle requests and not overwhelm my local capacity.

This project has been developed with CODEX and OpenAI models. I would consider it half vibe-coded, but now that I am using it more than developing it, I am back-filling better coding.

## Features

- **Character Onboarding**: Create new characters from onboarding options
- **Multi-phase Rendering Pipeline**: Body Reference → Head Fitment → Costume Dressing → Expressions
- **Prompt Inspection**: Inspect and refine queued render prompts, analyze with local LLM vision models.
- **Asset Management**: Organized storage for character assets, costumes, expressions, references
- **Render Console**: Manage rendering tasks with priority queuing, one-stop copy & paste interface for tools such as ChatGPT rendering.
- **Local Image Backends**: Stable Matrix and core-node ComfyUI preview workflows share the local render queue
- **Scene Builder**: Parameterized input wizard for scene layout using existing characters and assets; validation of elements and key inputs, compilation of prompt for final image generation. 

## System Requirements

### Operating Systems
- Windows 10/11 or macOS (Darwin)
- Python 3.11+

### Dependencies
Zet should run in its project-local `.venv`, not the system Python environment.

For a new Windows deployment, clone the repository, open PowerShell in the project root, and run:

```powershell
python3 --version
.\setup_venv.bat
```

This creates `.venv`, upgrades its copy of `pip`, and installs `requirements.txt`. Run
`setup_venv.bat` again whenever the requirements change. The `.venv` directory is local to the
deployment and excluded from Git.

To set up manually instead:

```powershell
python3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks `Activate.ps1`, use `setup_venv.bat`; it uses the batch activation script and
does not require changing the PowerShell execution policy.

For a new macOS deployment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -B -m zet.web.app
```

**Core packages:**
- `fastapi` - Web API server for dashboard and management endpoints
- `numpy`, `pillow` - Image processing utilities
- `uvicorn` - ASGI web server for running the FastAPI app
- `opencv-python` - Computer vision operations (pose detection, image analysis)

### Optional: ComfyUI Integration
To use local ComfyUI previews:
1. Install [ComfyUI](https://github.com/comfyanonymous/comfyui) separately
2. Start its local server, normally at `http://127.0.0.1:8188`
3. Select ComfyUI and configure its profile, checkpoint, and prompt globals on the Image Config page
4. Install [AI_Proxy](https://github.com/Joebok/AI_Proxy) separately
5. Configure AI_Proxy for your situation. Zet's BaseAIQueuePath and AI_Proxy's AI_QUEUE_ROOT must point to the same location.
4. Start AI_Proxy; it is preconfigured with Zet registrations for prompt analysis and local image generation.

## Quick Start

### 1. Initial Setup

```bash
# Create library folder for output assets
mkdir Zet_Library

# Run the web dashboard to manage characters and scenes
run_zet_web.bat
```

`BaseLibraryPath` is user storage and may point anywhere. Shared templates and default JSON files are read from the source-controlled project directory `Shared_Library/`.

### 2. Configuration

Edit `config.toml` to set up paths:

```toml
[BaseFoldersByPlatform.Windows]
BaseLibraryPath = "C:/Users/<username>/Projects/Zet_Library/"
BaseAIQueuePath = "C:/Users/<username>/Library/CloudStorage/Dropbox/AI_Queue/"

[PromptCondense]
Enabled = false  # Set to true for automatic prompt condensation with Qwen model
Model = "qwen3.5:4b-condenser"

[LocalRender]
Backend = "stable_matrix" # stable_matrix or comfyui

[StableMatrix]
Profile = "body-reference-preview"
Checkpoint = "stable-matrix-checkpoint"

[ComfyUI]
Profile = "comfyui-core-preview"
ServerURL = "http://127.0.0.1:8188"
Checkpoint = "checkpoint.safetensors"
PositivePromptGlobals = "masterpiece, best quality"
NegativePromptGlobals = "EasyNegative"
```

### Local ComfyUI Scene Preview

`Scene_Render_IR.json` is the canonical local scene-render input. Compile and run it directly with:

```powershell
.\.venv\Scripts\python.exe -m zet.scripts.render_comfyui_preview C:\path\to\Scene_Render_IR.json --config config.toml
```

Add `--compile-only` to write the API workflow without submitting it. The command writes
`ComfyUI_Workflow_API.json` to the pipeline output folder and stores the generated image and
`ComfyUI_Render_Metadata.json` under `Local_Test_Renders`.

The initial ComfyUI workflow uses built-in txt2img and area-conditioning nodes. Dialogue,
reference-image conditioning, ControlNet, IP-Adapter, and custom nodes are not part of this baseline.

### 3. Running the Pipeline

**Option A - Interactive Dashboard:**
```bash
run_zet_web.bat                 ; Activates .venv and starts the web app
.\.venv\Scripts\python.exe -B -m zet.web.app  ; Direct execution
```

**Option B - Automated Processing:**
```powershell
# Harvest queued jobs from AI_Queue folder
.\run_auto_harvest.bat

# Run specific render stages (requires ComfyUI running)
.\.venv\Scripts\python.exe .\Scripts\Run_Body_Reference_Jobs.py
.\.venv\Scripts\python.exe .\Scripts\Run_Character_Assembly_Jobs.py
.\.venv\Scripts\python.exe .\Scripts\Run_Costume_Dressing_Jobs.py
```

### 4. Adding a New Character

1. Place character config in `Characters/` folder with:
   - Base image references
   - Costume definitions (`Costumes.json`)
   - Expression templates
2. Use dashboard or run:
   ```powershell
   C:\Users\Joe\Projects\AI_Proxy\run_file_proxy.bat    ; Start the standalone file proxy
   run_zet_web.bat                              ; Activates .venv and starts the pipeline app
   ```

## Project Structure

```
Zet/
├── Config/                      # Prompt templates, review checklists, render presets
│   ├── AI_Prompt_Analysis_Instructions.md
│   ├── Character_Onboarding_Options.json
│   ├── Local_Render_Presets.json # Configured local render backends
│   └── ...
├── Scripts/                     # Standalone Python scripts for pipeline stages
│   ├── Run_Body_Reference_Jobs.py
│   ├── Compile_Character_Template.py
│   └── Validate_Render_Output.py
├── Shared_Library/              # Source-controlled templates and default JSON files
├── zet/                         # Main application code
│   ├── models/                  # Data models (Asset, Costume, Expression)
│   ├── services/                # Business logic for each pipeline stage
│   ├── repositories/            # Database/file storage accessors
│   ├── app.py                   # Reusable application facade
│   └── web/app.py               # FastAPI web server entry point
├── tests/                       # Unit tests for core functionality
├── AI_Manager/                  # One-job Ollama and local-image worker executables
├── Logs/                        # Pipeline execution logs
├── Logs/Source_Edits.jsonl     # Versioned prompt/source edits history
└── config.toml                 # Configuration file
```

## API Endpoints

The FastAPI server exposes these representative endpoints (when running `run_zet_web.bat`):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/context` | GET | Dashboard character and phase context |
| `/api/assets` | GET | List assets for a character and phase |
| `/api/render-console/tasks` | GET | List queued manual render tasks |
| `/api/stories/{story_slug}/scenes/{scene_slug}/stage-render` | POST | Stage a V3 scene render |

## Help & Troubleshooting

### Common Issues

**"No module named 'zet'" error:**
```bash
setup_venv.bat    ; Run from the project root
```

**ComfyUI proxy not connecting:**
- Ensure ComfyUI server is running on default port 8188
- Confirm the ComfyUI server URL and checkpoint on the Image Config page
- Confirm the configured checkpoint filename matches ComfyUI's checkpoint list

**Prompt condensation model errors (Qwen):**
- Verify Ollama or local LLM is accessible at configured endpoint
- See `Config/AI_Prompt_Analysis_Instructions.md` for prompt-analysis instructions

### Logs Location

Pipeline logs are written to the `Logs/` directory. Check recent entries when debugging rendering failures.

## Authors

Contributors and maintainers (add your name here):
- Joe - Project maintainer, pipeline architecture

## Version History

* 1.0 (2026)
    * Initial release with character onboarding, multi-phase rendering pipeline
    * ComfyUI proxy integration for Stable Diffusion workflows
    * AI prompt analysis using LLM models
    * Integration with AI_Proxy
* 2.0 (2026)
    * Separate Character Development and Story Telling interfaces

## License

No license file is currently included in this repository.

## Acknowledgments

- [ComfyUI](https://github.com/comfyanonymous/comfyui) for the underlying image generation workflows
- [Qwen models](https://ollama.com/library/qwen) via Ollama for prompt analysis and condensation
- Stable Diffusion community for base model support (SD1.5, SDXL)

## Additional Resources

- **Dashboard and workflows**: See `Docs/Zet.md`
- **Data Schema**: Object model decisions documented in `Docs/Zet_Data_Schema_Object_Model_Decisions.md`

## Contributing


---

*For more information, see [AGENTS.md](./AGENTS.md) for automation workflows and subagent capabilities.*
