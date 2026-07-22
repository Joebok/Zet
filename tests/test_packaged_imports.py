from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPILER_MODULES = [
    "Scripts.Run_Body_Reference_Jobs",
    "Scripts.Run_Head_Fitment_Jobs",
    "Scripts.Run_Character_Assembly_Jobs",
    "Scripts.Run_Costume_Dressing_Jobs",
    "Scripts.Run_Expression_Jobs",
]


def _package_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    return env


def test_workers_import_outside_checkout_without_scripts_path_mutation(tmp_path: Path) -> None:
    code = f"""
import sys
from pathlib import Path
scripts_path = Path({str(PROJECT_ROOT / 'Scripts')!r}).resolve()
import zet.workers.body_reference_prompt_worker
import zet.workers.head_fitment_prompt_worker
import zet.workers.character_assembly_prompt_worker
import zet.workers.costume_dressing_prompt_worker
import zet.workers.expression_prompt_worker
import zet.services.character_onboarding_service
import zet.services.prompt_review_service
from Scripts.Run_Body_Reference_Jobs import extract_template_field, load_bundle
from Scripts.Run_Head_Fitment_Jobs import reference_by_role, validate_reference
assert scripts_path not in [Path(value).resolve() for value in sys.path if value]
"""
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=_package_env(),
        check=True,
        capture_output=True,
        text=True,
    )


def test_compiler_modules_launch_outside_checkout(tmp_path: Path) -> None:
    for module in COMPILER_MODULES:
        subprocess.run(
            [sys.executable, "-m", module, "--help"],
            cwd=tmp_path,
            env=_package_env(),
            check=True,
            capture_output=True,
            text=True,
        )


def test_compiler_files_preserve_direct_launch(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    for module in COMPILER_MODULES:
        script_path = PROJECT_ROOT / Path(*module.split(".")).with_suffix(".py")
        subprocess.run(
            [sys.executable, str(script_path), "--help"],
            cwd=tmp_path,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
