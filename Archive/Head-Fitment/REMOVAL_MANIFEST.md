# Removal Manifest

Retired from active code and configuration:

- `Scripts/Run_Head_Fitment_Jobs.py`
- `Config/Prompt_Templates/head_fitment_v1.md`
- `zet/services/head_fitment_edit_service.py`
- `zet/services/head_fitment_mask_generation_service.py`
- `zet/workers/head_fitment_manifest_worker.py`
- `zet/workers/head_fitment_prompt_worker.py`
- `zet/workers/head_fitment_render_worker.py`
- Head-Fitment task-bundle, view, render-preset, pipeline-control, proxy, harvester, dashboard, and route branches
- Head-Fitment tests and documentation

Archived source files use `.py.txt` where necessary to prevent packaging, importing, and pytest discovery. Active character-phase data is migrated by `Scripts/Retire_Head_Fitment.py` into `_archive/Head-Fitment/` with pre-change backups under `_backup/HeadFitmentRetirement/`.
