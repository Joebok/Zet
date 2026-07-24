# Zet - Character Image Creation Pipeline

Zet is a Python-based pipeline for creating character images, managing assets, and assembling scenes using AI workflows. It integrates with Stable Diffusion models via ComfyUI proxies to automate the generation of consistent character renders across multiple phases (body reference, head fitment, costume dressing, expressions).

## Features

- **Character Onboarding**: Create new characters from onboarding options
- **Multi-phase Rendering Pipeline**: Body Reference → Head Fitment → Costume Dressing → Expressions
- **Prompt Inspection**: Inspect and refine queued render prompts, with optional Qwen condensation
- **Asset Management**: Organized storage for character assets, costumes, expressions, references
- **Auto-Harvest**: Automatically process queued jobs from external sources (Dropbox sync)
- **Render Console Queue**: Manage rendering tasks with priority queuing
- **Local Image Backends**: Stable Matrix and core-node ComfyUI preview workflows share the local render queue

## System Requirements

### Operating Systems
- Windows 10/11 or macOS (Darwin)
- Python 3.8+

### Dependencies
```bash
pip install -r requirements.txt
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
4. Run `AI_Manager/local_image_proxy_worker.py` for queued Render Console previews

## Quick Start

### 1. Initial Setup

```bash
# Create library folder for output assets
mkdir Zet_Library

# Run the web dashboard to manage characters and scenes
python3 -B -m zet.web.app
```

### 2. Configuration

Edit `config.toml` to set up paths:

```toml
[BaseFoldersByPlatform.Windows]
BaseLibraryPath = "C:/Users/Joe/Projects/Zet_Library/"
BaseAIQueuePath = "C:/Users/Joe/Library/CloudStorage/Dropbox/AI_Queue/"

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
python3 -m zet.scripts.render_comfyui_preview C:\path\to\Scene_Render_IR.json --config config.toml
```

Add `--compile-only` to write the API workflow without submitting it. The command writes
`ComfyUI_Workflow_API.json` to the pipeline output folder and stores the generated image and
`ComfyUI_Render_Metadata.json` under `Local_Test_Renders`.

The initial ComfyUI workflow uses built-in txt2img and area-conditioning nodes. Dialogue,
reference-image conditioning, ControlNet, IP-Adapter, and custom nodes are not part of this baseline.

### 3. Running the Pipeline

**Option A - Interactive Dashboard:**
```bash
run_zet_web.bat                 ; Windows batch script to start web app
python3 -B -m zet.web.app       ; Direct Python execution
```

**Option B - Automated Processing:**
```powershell
# Harvest queued jobs from AI_Queue folder
.\run_auto_harvest.bat

# Run specific render stages (requires ComfyUI running)
.\Scripts\Run_Body_Reference_Jobs.py
.\Scripts\Run_Character_Assembly_Jobs.py
.\Scripts\Run_Costume_Dressing_Jobs.py
```

### 4. Adding a New Character

1. Place character config in `Characters/` folder with:
   - Base image references
   - Costume definitions (`Costumes.json`)
   - Expression templates
2. Use dashboard or run:
   ```powershell
   .\AI_Manager\run_proxy_worker.bat    ; Start ComfyUI proxy if using rendering
   python3 -B -m zet.web.app            ; Then start the pipeline app
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
├── zet/                         # Main application code
│   ├── models/                  # Data models (Asset, Costume, Expression)
│   ├── services/                # Business logic for each pipeline stage
│   ├── repositories/            # Database/file storage accessors
│   ├── app.py                   # Reusable application facade
│   └── web/app.py               # FastAPI web server entry point
├── tests/                       # Unit tests for core functionality
├── AI_Manager/                  # Proxy workers (ComfyUI, Ollama, local image)
├── Logs/                        # Pipeline execution logs
├── Logs/Source_Edits.jsonl     # Versioned prompt/source edits history
└── config.toml                 # Configuration file
```

## API Endpoints

The FastAPI server exposes these representative endpoints (when running `python3 -B -m zet.web.app`):

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
python3 -m pip install -r requirements.txt    ; Run from the project root
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
    * AI prompt condensation using Qwen models
    * Auto-harvest from Dropbox queue folder

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

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

*For more information, see [AGENTS.md](./AGENTS.md) for automation workflows and subagent capabilities.*
