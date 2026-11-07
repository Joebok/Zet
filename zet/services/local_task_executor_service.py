"""Small shared executor for nonblocking local pipeline work."""
from concurrent.futures import ThreadPoolExecutor
from typing import Any

_EXECUTOR = ThreadPoolExecutor(max_workers=16, thread_name_prefix="zet-local-pipeline")


def submit_local_pipeline_task(function, *args: Any, **kwargs: Any):
    """Submit local pipeline work without tying execution to one workflow page."""
    return _EXECUTOR.submit(function, *args, **kwargs)
