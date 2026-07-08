from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class AIProxyAsk:
    ask_id: str
    asset_id: int
    character: str
    phase: str
    pipeline: str
    pipeline_stage: str
    ollama_attempt_id: str
    worker_type: str
    ollama_model: str
    prompt_file: str
    expected_output: str
    candidate_output_file: Optional[str] = None
    task_type: Optional[str] = None
    auxiliary: bool = False
    manual: bool = False
    target_output_file: Optional[str] = None
    render_preset: Optional[str] = None
    reference_files: list[dict] = field(default_factory=list)


@dataclass
class AIProxyPaths:
    proxy_root: Path
    ask_root: Path
    claims_root: Path
    claimed_root: Path
    answer_root: Path
    failed_root: Path
    control_root: Path
    monitor_root: Path
    monitor_requests_root: Path
    monitor_responses_root: Path


@dataclass
class AIProxyAnswer:
    ask_id: str
    asset_id: Optional[int]
    ollama_attempt_id: str
    worker_id: str
    status: str
    expected_output: str
    error_type: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class MonitorTestResult:
    test_id: str
    worker_id: str
    host: str
    status: str
    ollama_ok: bool
    models: list[str]
    message: Optional[str] = None
    responded_at: Optional[str] = None


@dataclass
class HarvestResult:
    answer_path: Path
    ask_id: str
    asset_id: Optional[int]
    status: str
    message: str
