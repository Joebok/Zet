### Environment Fallback
- Always prioritize Python 3 over Python 2.
- Use `python3` explicitly for executing any python scripts.
- Do not assume system `python` points to a modern release.

### Architecture Boundary
- Keep reusable Zet behavior in backend code under `zet/services`, `zet/repositories`, `zet/models`, and pipeline scripts.
- Keep `zet/web` focused on FastAPI routes, page/API presentation, browser interaction, and calling backend service methods.
- Do not add file layout discovery, pipeline stage transitions, prompt review operations, render orchestration, or other reusable business logic directly to the web layer.
- When the dashboard needs a new workflow action, expose it through `ZetApp`, `AssetRef`, or a focused service first so other interfaces can reuse the same backend behavior.
- The old Streamlit dashboard and standalone Render Console are retired. Do not add new workflow functionality to them.

### General Coding 
- add a one line description of functions and procedures
