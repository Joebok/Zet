"""Incremental, recoverable usage observations and explicit reference audits."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import re

from zet.services.atomic_file_service import write_json_atomic
from zet.services.workflow_storage import file_lock


@contextmanager
def usage_mutation(paths, path, *, tree=False):
    """Track library authoring services that do not depend on a ZetApp instance."""
    from zet.repositories.entity_library_repository import EntityLibraryRepository
    from zet.services.entity_library_service import EntityLibraryService
    library = EntityLibraryService(paths, EntityLibraryRepository(paths.entity_library_database_path()))
    with library.image_usages.mutation(path, tree=tree):
        yield


class ImageUsageService:
    def __init__(self, library):
        self.library = library
        self.repository = library.repository
        self.config = library.path_service.config
        self.root = Path(self.config.base_library_path).resolve()
        from zet.services.storage_health_service import recovery_root
        self.pending = recovery_root(self.config) / "ImageUsages"
        self.last_error = ""
        self._signatures = {}

    def write_consumer(self, path, value, writer):
        """Journal only reference changes, including writes by generation services."""
        path = Path(path)
        consumer = self._consumer(path)
        rows = self.extract(path, value)
        if consumer not in self._signatures:
            try:
                self._signatures[consumer] = self._read(path)
            except (OSError, ValueError):
                self._signatures[consumer] = None
        if rows == self._signatures[consumer]:
            return writer()
        with self.mutation(path):
            result = writer()
            self._signatures[consumer] = rows
            return result

    def _consumer(self, path):
        path = Path(path).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError("Usage consumer must belong to this universe.")
        return path.relative_to(self.root).as_posix()

    @staticmethod
    def extract(path, value):
        """Extract references only; resolution is reserved for use or explicit audits."""
        rows = []
        if path.suffix.lower() == ".md":
            for match in re.finditer(r"\{\{LIB:(ASSET|REF):([^{}]+)\}\}", value):
                rows.append({"asset_id": match[2] if match[1] == "ASSET" else None,
                             "reference_key": match[2] if match[1] == "REF" else None,
                             "consumer_type": "template", "locator": f"offset:{match.start()}"})
            return rows

        def visit(item, locator=""):
            if isinstance(item, dict):
                direct = str(item.get("asset_id") or "").strip()
                logical = str(item.get("reference_key") or "").strip()
                if direct or logical:
                    rows.append({"asset_id": direct or None, "reference_key": logical or None,
                                 "consumer_type": "scene", "locator": locator or "$"})
                for key, child in item.items():
                    if key not in {"source_document", "source_markdown", "image_review", "imported_baseline"}:
                        visit(child, f"{locator}.{key}" if locator else key)
            elif isinstance(item, list):
                for index, child in enumerate(item):
                    visit(child, f"{locator}[{index}]")
        visit(value)
        return rows

    def _read(self, path):
        text = path.read_text(encoding="utf-8")
        return self.extract(path, text if path.suffix.lower() == ".md" else json.loads(text))

    def _replace(self, consumer, observations):
        stamp = datetime.now(timezone.utc).isoformat()
        with self.repository.transaction() as connection:
            connection.execute("DELETE FROM asset_usages WHERE consumer_id=?", (consumer,))
            for row in observations:
                asset, key = row["asset_id"], row["reference_key"]
                if asset and not connection.execute("SELECT 1 FROM assets WHERE asset_id=?", (asset,)).fetchone():
                    asset = None
                if key and not connection.execute("SELECT 1 FROM logical_references WHERE reference_key=?", (key,)).fetchone():
                    key = None
                if not asset and not key:
                    continue
                uid = hashlib.sha256(json.dumps([asset, key, consumer, row["locator"]]).encode()).hexdigest()
                connection.execute(
                    "INSERT INTO asset_usages(usage_id,asset_id,reference_key,consumer_type,consumer_id,locator,last_seen,status) "
                    "VALUES(?,?,?,?,?,?,?,'current')",
                    (uid, asset, key, row["consumer_type"], consumer, row["locator"], stamp))

    def _paths(self, folder):
        """Enumerate only the explicitly requested scope, never on inventory reads."""
        if not folder.is_dir():
            return []
        return [p for p in folder.rglob("*") if p.is_file() and (
            p.suffix.lower() == ".md" or p.name in {"scene.json", "target.json"} or p.name.endswith(".scene.json"))]

    def _synchronize(self, consumer, tree=False):
        from zet.services.storage_health_service import guard_path
        guard_path(self.root)
        path = self.root / consumer

        def observations(item):
            try:
                return self._read(item)
            except FileNotFoundError:
                # Confirm a real deletion instead of trusting cached volume
                # health when storage disappears just after the primary save.
                guard_path(item, force=True)
                return []

        if tree:
            paths = {self._consumer(p): p for p in self._paths(path)}
            # A directory explicitly removed by Zet also removes its old observations.
            known = self.repository.fetchall("SELECT DISTINCT consumer_id FROM asset_usages")
            for row in known:
                name = row["consumer_id"]
                if name == consumer or name.startswith(consumer.rstrip("/") + "/"):
                    paths.setdefault(name, self.root / name)
            for name, item in paths.items():
                self._replace(name, observations(item))
        else:
            self._replace(consumer, observations(path))

    def _marker(self, consumer):
        return self.pending / (hashlib.sha256(consumer.encode()).hexdigest() + ".json")

    def _lock(self, consumer):
        number = int(hashlib.sha256(consumer.encode()).hexdigest()[:8], 16) % 32
        return file_lock(self.pending / f"usage-{number:02d}.lock")

    @contextmanager
    def mutation(self, path, *, tree=False):
        """Journal before a write, then update observations without failing a saved edit."""
        try:
            consumer = self._consumer(path)
        except ValueError:
            # Source editor also edits shared project templates, outside this library.
            yield
            return
        lock = self._lock(consumer)
        try:
            lock.__enter__()
        except Exception as exc:
            self._failed(exc)
            yield
            return
        try:
            try:
                write_json_atomic(self._marker(consumer), {"consumer_id": consumer, "tree": tree})
            except Exception as exc:
                self._failed(exc)
            yield
            self._complete(consumer, tree)
        finally:
            lock.__exit__(None, None, None)

    def _failed(self, exc):
        self.last_error = str(exc)
        logging.getLogger(__name__).warning("Usage maintenance pending: %s", exc)

    def _complete(self, consumer, tree):
        try:
            self._synchronize(consumer, tree)
            self._marker(consumer).unlink(missing_ok=True)
            self.last_error = ""
        except Exception as exc:
            self._failed(exc)

    def drain(self):
        """Replay only coalesced pending consumers after restart or catalog recovery."""
        for marker in sorted(self.pending.glob("*.json")):
            try:
                row = json.loads(marker.read_text(encoding="utf-8"))
                consumer = row["consumer_id"]
                self._consumer(self.root / consumer)
                with self._lock(consumer):
                    # Re-read after locking: a writer may have completed this marker.
                    if marker.is_file():
                        row = json.loads(marker.read_text(encoding="utf-8"))
                        self._complete(consumer, bool(row.get("tree")))
            except Exception as exc:
                self._failed(exc)

    def summary(self):
        return {"current": self.repository.fetchone(
                    "SELECT count(*) AS n FROM asset_usages WHERE status='current'")["n"],
                "pending": len(list(self.pending.glob("*.json"))), "last_error": self.last_error}

    def audit(self, *, rebuild=False):
        """Explicitly scan authored consumers and optionally refresh readable scopes."""
        from zet.services.storage_health_service import guard_path
        guard_path(self.root)
        report = {"checked": 0, "missing": [], "unreadable": [], "differences": [], "rebuilt": rebuild}
        paths = {self._consumer(p): p for folder in ("Characters", "CostumePrompt", "NarrativeStories", "Stories")
                 for p in self._paths(self.root / folder)}
        known = self.repository.fetchall("SELECT DISTINCT consumer_id FROM asset_usages")
        for row in known:
            consumer = row["consumer_id"]
            self._consumer(self.root / consumer)
            paths.setdefault(consumer, self.root / consumer)
        for consumer, path in sorted(paths.items()):
            try:
                with self._lock(consumer):
                    if not path.is_file():
                        report["unreadable"].append({"consumer_id": consumer, "error": "Consumer is absent; existing observations retained."})
                        continue
                    rows = self._read(path)
                    report["checked"] += 1
                    stored = self.repository.fetchall(
                        "SELECT asset_id,reference_key,consumer_type,locator FROM asset_usages WHERE consumer_id=? AND status='current'",
                        (consumer,))
                    normalize = lambda values: sorted(json.dumps(v, sort_keys=True) for v in values)
                    if normalize(rows) != normalize(stored):
                        report["differences"].append(consumer)
                    for row in rows:
                        asset, key = row["asset_id"], row["reference_key"]
                        resolved = self.repository.fetchone("SELECT * FROM assets WHERE asset_id=?", (asset,)) if asset else None
                        if key:
                            reference = self.repository.fetchone(
                                "SELECT asset_id,status FROM logical_references WHERE reference_key=?", (key,))
                            if not reference or reference["status"] != "active":
                                report["missing"].append({"consumer_id": consumer, **row, "reason": "Logical reference is missing or inactive"})
                            elif not asset:
                                resolved = self.repository.fetchone("SELECT * FROM assets WHERE asset_id=?", (reference["asset_id"],))
                        # Narrative direct IDs retain historical bindings even
                        # after inventory archival; logical keys/picker tags do not.
                        needs_approval = not (asset and consumer.startswith("NarrativeStories/"))
                        if (not resolved or (needs_approval and resolved["status"] != "approved")
                                or not self.library._image_path(resolved["asset_id"], resolved["file_name"]).is_file()):
                            report["missing"].append({"consumer_id": consumer, **row, "reason": "Image is absent or unavailable for this binding"})
                    if rebuild:
                        self._replace(consumer, rows)
            except Exception as exc:
                report["unreadable"].append({"consumer_id": consumer, "error": str(exc)})
        return report
