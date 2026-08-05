# Zet

Zet is a local, file-backed production dashboard for building consistent character art, composing illustrated scenes, and arranging finished scenes into zines. It combines reusable character information and image references into render prompts, then guides each image through review and approval.

Zet is designed primarily for a personal creative workflow using ChatGPT for final images, with optional Ollama, Stable Matrix, ComfyUI, and [AI Proxy](https://github.com/Joebok/AI_Proxy) integrations for local automation.

## Key features

- Guided character onboarding and life-phase management
- Character-development pipelines for body references, head fitment, costumes, and expressions
- Reusable identity keys, turnarounds, and auxiliary image references
- Prompt inspection, source editing, AI analysis, and manual or local rendering
- Side-by-side candidate review, approval, regeneration, and asset history
- Story and scene authoring with a structured scene builder
- Scene image-reference selection and render staging
- Zine layout creation from finished story scenes
- Queue, process, image-backend, and pipeline administration in one dashboard

See [Tutorial.md](Tutorial.md) for a brief guide to every dashboard feature.

## Requirements

- Windows 10/11 or macOS
- Python 3.11 or newer
- Git

Optional integrations are only needed for their related features:

- ChatGPT for the manual final-render workflow
- [AI Proxy](https://github.com/Joebok/AI_Proxy) for filesystem-based AI and render queues
- Ollama for local prompt analysis or condensation
- Stable Matrix or [ComfyUI](https://github.com/comfyanonymous/ComfyUI) for local image generation

## Install

Clone the repository and enter it:

```bash
git clone https://github.com/Joebok/Zet.git
cd Zet
```

### Windows

From PowerShell in the project root:

```powershell
python3 --version
.\setup_venv.bat
```

The setup script creates `.venv`, upgrades pip, and installs `requirements.txt`. Run it again after dependencies change. It also avoids PowerShell activation-policy issues by activating the environment through its batch script.

### macOS

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## Configure

Before the first launch, edit the section for your operating system in `config.toml`:

```toml
[BaseFoldersByPlatform.Windows]
BaseLibraryPath = "C:/Users/<username>/Projects/Zet_Library/"
BaseAIQueuePath = "C:/Users/<username>/Projects/Zet_AI_Queue/"

[BaseFoldersByPlatform.Darwin]
BaseLibraryPath = "/Users/<username>/Projects/Zet_Library/"
BaseAIQueuePath = "/Users/<username>/Projects/Zet_AI_Queue/"
```

`BaseLibraryPath` holds your creative work. `BaseAIQueuePath` is used for render and AI jobs; if you use AI Proxy on another machine, both applications must use the same queue location.

The dashboard's **Tools > Image Config** and **Tools > AI Controls** pages manage most optional image-generation and automation settings after startup.

## Run

### Windows

```powershell
.\run_zet_web.bat
```

### macOS

```bash
source .venv/bin/activate
./run_zet_web.command
```

Open [http://localhost:8080](http://localhost:8080). Use **New > Character** to begin character development or **New > Story** to begin a story.

To stop Zet, press `Ctrl+C` in the terminal running the server.

## Optional services

Zet can run without every optional integration, but automated queue processing and local image generation require the corresponding service.

- Configure AI Proxy to share Zet's `BaseAIQueuePath`.
- Start Ollama before refreshing or selecting local analysis models.
- Start Stable Matrix or ComfyUI before requesting local images.
- In Zet, open **Tools > Image Config** to select the backend, render profile, checkpoint, and prompt globals.
- Open **Tools > AI Controls** to configure harvesting, choose the final-render backend, and inspect service status.

## Troubleshooting

### `No module named 'zet'`

Run commands from the repository root. On Windows, rerun `setup_venv.bat`; on macOS, activate `.venv` before launching Zet.

### The dashboard does not start

Check whether another process already uses port 8080. The Windows launcher reports an existing Zet listener instead of starting a duplicate.

### Local models or checkpoints are missing

Confirm the selected Ollama, Stable Matrix, or ComfyUI service is running, then use the corresponding refresh control in **AI Controls** or **Image Config**.

### Render jobs are not moving

Open **Tools > AI Controls** and check the process state and Ask, Running, and Answer queues. Verify Zet and AI Proxy share the same queue location.

## Documentation

- [Tutorial.md](Tutorial.md) — feature-oriented usage guide
- [Docs/Zet.md](Docs/Zet.md) — implementation and pipeline details
- [Docs/Local_Image_Generation.md](Docs/Local_Image_Generation.md) — local rendering configuration and operation
- [Docs/Zet_Data_Schema_Object_Model_Decisions.md](Docs/Zet_Data_Schema_Object_Model_Decisions.md) — data-model decisions

## Status

Zet is a personal project under active development. Workflows and dashboard controls may change as the production process evolves.

## License

Zet is licensed under the [MIT License](LICENSE).

Copyright &copy; 2026 Joe Schonbok.
