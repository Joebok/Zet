import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from collections.abc import Iterator

from zet.models.ai_proxy import AIProxyAnswerManifest, AIProxyAskManifest
from zet.services.config_service import Config
from zet.services.ai_queue_lifecycle_service import AIQueueLifecycleService
from zet.services.file_proxy_client import FileProxyClient
from zet.services.workflow_storage import task_state_path


class AIProxyPathService:
    ARCHIVE_RETRY_DELAY_SECONDS = 2

    def __init__(self, config: Config):
        self.config = config
        self.lifecycle = AIQueueLifecycleService(config)
        self.file_proxy_client = self.lifecycle.file_proxy_client()

    def ask_root(self) -> Path:
        return self.file_proxy_client.ask_root

    def manual_root(self) -> Path:
        return Path(self.config.base_ai_queue_path) / "Manual_Render_Queue"

    def manual_ask_root(self) -> Path:
        return self.manual_root() / "Ask"

    def manual_answer_root(self) -> Path:
        return self.manual_root() / "Answer"

    def running_root(self) -> Path:
        return self.file_proxy_client.running_root

    def answer_root(self) -> Path:
        return self.file_proxy_client.answer_root

    def archive_root(self) -> Path:
        """Return the AI proxy archive root."""
        return Path(self.config.base_ai_queue_path) / "Zet_File_Proxy_State" / "Archive"

    def harvested_archive_root(self) -> Path:
        """Return the harvested-answer archive root."""
        configured_path = self.config.ai_harvest_archive_path
        if not configured_path:
            return self.archive_root() / "Harvested"
        path = Path(configured_path)
        if path.is_absolute():
            return path
        return Path(self.config.base_ai_queue_path) / path

    def archive_harvested_answer(self, answer_path: Path) -> Path:
        """Move a harvested answer into the dated archive, retrying once for a slow drive."""
        archive_root = self.harvested_archive_root() / datetime.now().strftime("%Y-%m-%d")
        self._retry_archive_operation(lambda: archive_root.mkdir(parents=True, exist_ok=True))

        dest_path = archive_root / answer_path.name
        if self._retry_archive_operation(dest_path.exists):
            suffix = datetime.now().strftime("%H%M%S_%f")
            dest_path = archive_root / f"{answer_path.name}.{suffix}"

        def move_answer() -> Path:
            try:
                return Path(shutil.move(str(answer_path), str(dest_path)))
            except OSError:
                # A failed cross-drive move can leave a partial destination behind.
                # Remove it before retrying so shutil.move does not nest the source in it.
                if answer_path.exists() and dest_path.exists():
                    try:
                        shutil.rmtree(dest_path)
                    except OSError:
                        pass
                raise

        return self._retry_archive_operation(move_answer)

    @classmethod
    def _retry_archive_operation(cls, operation):
        try:
            return operation()
        except OSError:
            time.sleep(cls.ARCHIVE_RETRY_DELAY_SECONDS)
            return operation()

    def manual_ask_path(self, ask_id: str) -> Path:
        return self.manual_ask_root() / ask_id

    def task_paths(self, *states: str) -> Iterator[Path]:
        """Yield Zet task folders from the new proxy and manual workflow."""
        roots = {
            "ask": (self.ask_root(), self.manual_ask_root()),
            "answer": (self.answer_root(), self.manual_answer_root()),
            "running": (self.running_root(),),
        }
        for state in states:
            if state not in roots:
                raise ValueError(f"Unknown AI proxy queue state: {state}")
            for root in roots[state]:
                if not root.exists():
                    continue
                paths = sorted(
                    path for path in root.iterdir()
                    if path.is_dir() and not path.name.startswith(".")
                )
                if state == "ask":
                    paths = [path for path in paths if not (path / "submission.json").exists()
                             and not task_state_path(Path(self.config.base_ai_queue_path), "Superseded", path.name).exists()]
                if state == "answer" and root == self.answer_root():
                    paths = [
                        path
                        for path in paths
                        if self.file_proxy_client.answer_is_ready(path)
                    ]
                if state == "answer" and root == self.manual_answer_root():
                    paths = [path for path in paths if (path / "answer_manifest.json").is_file()]
                yield from paths
            if state == "answer":
                yield from self.lifecycle.inbox_answers()

    @staticmethod
    def read_ask_manifest(task_path: Path) -> AIProxyAskManifest:
        manifest_path = task_path / "ask_manifest.json"
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid ask manifest at {manifest_path}: {exc}") from exc
        return AIProxyAskManifest.from_dict(payload)

    @staticmethod
    def read_answer_manifest(task_path: Path) -> AIProxyAnswerManifest:
        manifest_path = task_path / "answer_manifest.json"
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid answer manifest at {manifest_path}: {exc}") from exc
        return AIProxyAnswerManifest.from_dict(payload)
