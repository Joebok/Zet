"""Shared reconstruction targets and true-up; original pixels are analysis-only."""
from __future__ import annotations

import base64
import hashlib
import json
from io import BytesIO
from pathlib import Path
import re
import threading
from zet.services.ai_workflow_service import work_id, current_workflow
from PIL import Image

from zet.services.atomic_file_service import write_json_atomic
from zet.services.image_prompt_generation_service import ImagePromptGenerationService
from zet.services.ai_model_catalog_service import AIModelCatalogService
from zet.services.render_slot_service import render_count
from zet.services.universe_style_service import compose_style, universe_style
from zet.services.workflow_storage import file_lock, validate_image
from zet.services.image_reconstruction_contract import (
    correction_items, fingerprint, target_brief, target_instructions, text, validate_draft,
)
from zet.services.image_true_up_service import ImageTrueUpService


class ImageReconstructionService:
    DRAFT_SCHEMA = {"type": "object", "properties": {
        **{key: {"type": "string"} for key in ("content_prompt", "identity")},
        **{key: {"type": "array", "items": {"type": "string"}}
           for key in ("observations", "proposals", "questions", "uncertainties")}},
        "required": ["content_prompt", "identity", "observations", "proposals", "questions", "uncertainties"],
        "additionalProperties": False}
    SCHEMA = {"type": "object", "properties": {
        "content_prompt": {"type": "string"},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    }, "required": ["content_prompt", "uncertainties"], "additionalProperties": False}
    INSTRUCTIONS = (
        "Deconstruct the supplied image into a self-contained image generation description of visible content. "
        "Describe distinctive subjects, adult/child presentation where clear, species, facial and body structure, "
        "hair, garment layers and construction, objects, materials, colors, pose, composition and background. "
        "Retain defining visible facts and exclusions with enough detail to reconstruct the content. "
        "Exclude the source's art style, medium, artist names, brushwork, linework, cel shading, photographic or "
        "anime labels, generic quality slogans, texture noise and rendering conventions. Destination rendering "
        "style will be supplied separately. Material construction is content; the way strokes depict it is not. "
        "Do not infer hidden features, biography, names or extra objects. Put uncertain/occluded details in "
        "uncertainties rather than inventing them. Return only the requested JSON object."
    )

    def __init__(self, generator, analyzer=None, catalog=None):
        self.generator = generator
        self.app = generator.zet_app
        self.root = Path(self.app.config.base_library_path) / "_state" / "ImageReconstruction"
        self.analyzer = analyzer or ImagePromptGenerationService(self.app, generator.project_root)
        self.catalog = catalog or AIModelCatalogService(self.app.config.base_ai_queue_path, config=self.app.config)
        self._active = set()
        self._guard = threading.RLock()
        self.true_up = ImageTrueUpService(self._ask)

    def _ask(self, model, prompt, schema, images):
        return self.app.ai_proxy_service.ai_proxy_path_service.jobs.generate_json(model,
            "Follow the target contract and return the requested JSON.", prompt, schema, images,
            task_type="image_reconstruction")[0]

    def _snapshot(self, directory, filename, contents):
        if not contents or len(contents) > 20 * 1024 * 1024:
            raise ValueError("Choose a nonempty image of 20 MiB or smaller.")
        validate_image(contents)
        with Image.open(BytesIO(contents)) as image:
            extension = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}[image.format]
        name = filename + "." + extension
        (directory / name).parent.mkdir(parents=True, exist_ok=True)
        (directory / name).write_bytes(contents)
        return name, hashlib.sha256(contents).hexdigest()

    def _sources(self, payload):
        if payload.get("selected_result") is not None:
            contents, source = self.generator.slot_workspace.selected_result(payload["selected_result"])
            parent = source.get("reconstruction", {})
            refs = []
            if parent.get("id"):
                old = self._read(parent["id"])
                if old.get("target"):
                    refs = [(dict(ref), self._source_bytes(old, ref))
                            for index, ref in enumerate(old["target"]["sources"])
                            if index == 0 or not ref.get("request_id")]
                    payload = dict(payload)
                    for key in ("preserve", "changes"):
                        if key not in payload:
                            payload[key] = old["target"]["change_text" if key == "changes" else key]
                    payload["context"] = "Use the selected result for composition and completed design; original evidence retains identity authority."
            source.pop("reconstruction", None)
            source["caption"] = "Selected result: design and composition to reconstruct"
            return [*refs, (source, contents)], payload
        asset_id = str(payload.get("asset_id") or "").strip()
        source = {"asset_id": asset_id, "label": str(payload.get("label") or "Uploaded source")}
        if asset_id:
            asset = self.app.entity_library_asset(asset_id)
            if asset.get("status") == "archived":
                raise ValueError("Choose an available source image.")
            contents = Path(asset["image_path"]).read_bytes()
            source["managed_checksum"] = asset.get("checksum", "")
            source["label"] = asset.get("label", asset_id)
        else:
            encoded = str(payload.get("image") or "")
            if len(encoded) > 28 * 1024 * 1024:
                raise ValueError("Source images must be 20 MiB or smaller.")
            try:
                contents = base64.b64decode(encoded.split(",", 1)[-1] if encoded.startswith("data:") else encoded, validate=True)
            except ValueError as exc:
                raise ValueError("Invalid source image data.") from exc
        source["caption"] = "Primary identity and visible design, subject to explicit changes"
        return [(source, contents)], payload

    def prepare(self, payload, references=None, *, style=None):
        """Create a board-independent target; callers own their render allocation."""
        model = str(payload.get("model") or self.app.config.ai_image_prompt_generation_model).strip()
        if model not in self.options()["models"]:
            raise ValueError("Choose an available Codex or vision-capable Ollama analysis model.")
        style = style or universe_style(self.app.config.base_library_path)
        if not style["text"]:
            raise ValueError("Set the destination universe's Canonical Art Style before reconstructing.")
        if references is None:
            references, payload = self._sources(payload)
        job_id = work_id("reconstruction")
        directory = self._path(job_id).parent
        references = list(references)
        context = current_workflow.get()
        identity = fingerprint({"model": model, "payload": payload, "style": style,
            "owner": {"universe_id": self.app.universe_id, "workflow_id": context["id"] if context else "",
                      **(context["owner"] if context else {})},
            "references": [metadata for metadata, _ in references]})
        with file_lock(directory / ".prepare.lock"):
            marker = directory / "preparation.json"
            if marker.is_file():
                saved = json.loads(marker.read_text(encoding="utf-8"))
                if saved.get("identity_version") == 2 and saved.get("identity") != identity:
                    raise ValueError("Reconstruction preparation inputs changed during continuation")
            elif self._path(job_id).is_file():
                # Old deterministic continuations have no preparation marker. Verify their
                # original source/model/intent below before adopting the existing record.
                old = self._read(job_id)
                sources = [{**metadata, "filename": old["target"]["sources"][index]["filename"],
                            "sha256": hashlib.sha256(contents).hexdigest()}
                           for index, (metadata, contents) in enumerate(references)]
                expected = target_brief(payload, style, sources)
                actual = old["target"]
                if (old["model"] != model or old["style"] != style or any(actual.get(k) != v for k, v in expected.items()
                        if k not in {"description", "identity", "proposals", "questions", "observations", "sources"})):
                    raise ValueError("Existing reconstruction does not match the frozen preparation")
                self.validate_sources(old)
            write_json_atomic(marker, {"identity": identity, "identity_version": 2})
            if self._path(job_id).is_file():
                old = self._read(job_id)
                self.validate_sources(old)
                return old
            return self._prepare_record(job_id, directory, payload, references, model, style)

    def _prepare_record(self, job_id, directory, payload, references, model, style):
        sources = []
        for index, (metadata, contents) in enumerate(references):
            filename, checksum = self._snapshot(directory, f"sources/{index}", contents)
            sources.append({**metadata, "filename": filename, "sha256": checksum})
        if not sources:
            raise ValueError("Choose at least one identity reference.")
        target = target_brief(payload, style, sources)
        job = {"id": job_id, "version": 2, "instruction_version": 2, "model": model,
               "status": "PREPARED", "error": "", "source": sources[0], "source_file": sources[0]["filename"],
               "style": style, "notes": target["notes"], "target": target, "target_hash": fingerprint(target),
               "content_prompt": "", "uncertainties": [], "prompt": "", "render_request_id": job_id}
        self._save(job)
        return job

    def _source_bytes(self, job, source):
        directory = self._path(job["id"]).parent.resolve()
        path = (directory / source["filename"]).resolve()
        if not path.is_relative_to(directory):
            raise ValueError("Invalid reconstruction snapshot path.")
        contents = path.read_bytes()
        return contents

    def source_image(self, job_id, index):
        job = self._read(job_id)
        if type(index) is not int or index < 0:
            raise ValueError("Choose a reconstruction source.")
        if job.get("version") == 2:
            contents = self._source_bytes(job, job["target"]["sources"][index])
        else:
            if index != 0:
                raise ValueError("Source not found.")
            contents = self._source_bytes(job, {"filename": job["source_file"], "sha256": job["source"]["sha256"]})
        with Image.open(BytesIO(contents)) as image:
            return contents, Image.MIME[image.format]

    def validate_sources(self, job):
        for source in job["target"]["sources"]:
            self._source_bytes(job, source)
            if source.get("asset_id"):
                asset = self.app.entity_library_asset(source["asset_id"])
                if (asset.get("status") == "archived" or asset["checksum"] != source.get("managed_checksum", source["sha256"])):
                    raise ValueError("The library reference changed. Start a new reconstruction.")

    def analyze(self, job_id):
        job = self._read(job_id)
        self.validate_sources(job)
        if job.get("status") == "READY":
            return job
        images = [str(self._path(job_id).parent / r["filename"]) for r in job["target"]["sources"]]
        draft = validate_draft(self._ask(job["model"], self.INSTRUCTIONS
            + "\nSeparate source observations from the intended target. The content_prompt and identity must "
              "describe the EDITED result with all explicit changes already applied, without contradictory "
              "source equipment/style. State removed objects as concise exclusions, not detailed designs of "
              "discarded equipment; keep those designs in source observations only. Bound hair length using visible face/neck landmarks. For reference "
              "views omit source pose, gaze and background when the task context requests neutral views. "
              "Mark proposed unseen completions separately and ask material unresolved questions.\n"
            + target_instructions(job["target"]), self.DRAFT_SCHEMA, images))
        job.update(content_prompt=draft["content_prompt"].strip(), uncertainties=draft["uncertainties"], status="READY")
        job["target"].update(description=job["content_prompt"], identity=draft["identity"],
                             proposals=draft["proposals"], questions=draft["questions"], observations=draft["observations"])
        job["target_hash"] = fingerprint(job["target"])
        job["prompt"] = self.compose(job)
        self._save(job)
        return job

    def revise(self, job_id, description, identity, proposals):
        old = self._read(job_id)
        refs = [(dict(r), self._source_bytes(old, r)) for r in old["target"]["sources"]]
        target = old["target"]
        new = self.prepare({"model": old["model"], "preserve": target["preserve"],
            "changes": target["change_text"], "notes": target["notes"], "context": target["context"]}, refs, style=old["style"])
        new["target"].update(description=description, identity=identity, proposals=proposals,
                             observations=target.get("observations", []))
        new.update(content_prompt=description, status="READY", uncertainties=old["uncertainties"],
                   parent_task_id=job_id, target_hash=fingerprint(new["target"]))
        new["prompt"] = self.compose(new)
        self._save(new)
        return new

    @staticmethod
    def compose(job, context=""):
        target = job["target"]
        return compose_style("\n\n".join(filter(None, [target["description"],
            "Identity: " + target["identity"], "Approved completion details:\n" + "\n".join(target["proposals"]),
            "Preserve: " + target["preserve"], "Required changes (retain during every correction):\n" + target["change_text"],
            context])), job["style"]["text"], target["notes"])

    def metadata(self, job):
        return {key: job[key] for key in ("id", "version", "model", "source", "style", "instruction_version",
            "content_prompt", "uncertainties", "notes", "prompt", "target", "target_hash")}

    def render_spec(self, job_id, context, references=(), *, report_id="", item_ids=None, instructions=""):
        job = self._read(job_id)
        self.validate_sources(job)
        if not job["target"]["description"].strip():
            raise ValueError("Analyze the source and review its target before rendering.")
        if job["target"]["questions"]:
            raise ValueError("Resolve the target questions before rendering.")
        prompt = self.compose(job, context)
        metadata = self.metadata(job)
        if report_id:
            report = self.report(job_id, report_id)
            if (report["status"] != "COMPLETE" and not (instructions.strip() and not item_ids)
                    or report["target_hash"] != job["target_hash"]):
                raise ValueError("The comparison is not current. Compare this candidate again.")
            if not references:
                raise ValueError("The candidate changed after comparison.")
            correction = self.true_up.correction(job["model"], job["target"], report,
                                                item_ids or [], text(instructions, "Refinement"), context)
            prompt = compose_style(correction, job["style"]["text"], job["target"]["notes"])
            metadata.update(report_id=report_id, parent_candidate=report["candidate"],
                            selected_corrections=item_ids or [], correction_instructions=instructions)
        elif instructions and references:
            correction = self.true_up.correction(job["model"], job["target"], {"items": []}, [],
                                                 text(instructions, "Refinement"), context)
            prompt = compose_style(correction, job["style"]["text"], job["target"]["notes"])
            metadata.update(correction_instructions=instructions)
        elif instructions:
            raise ValueError("Choose an image to refine.")
        spec = {"mode": "img2img" if references else "txt2img", "prompt": prompt,
                "negative_prompt": "",
                "count": 1, "reconstruction": metadata}
        if references:
            spec["reference_images"] = [{"label": label, "image": base64.b64encode(data).decode("ascii")}
                                        for label, data in references]
        return spec

    def _report_path(self, job_id, report_id):
        if not re.fullmatch(r"[a-f0-9]{32}", str(report_id)):
            raise ValueError("Invalid comparison ID.")
        return self._path(job_id).parent / "reports" / report_id / "report.json"

    def compare(self, job_id, contents, candidate, context, anchor=None, *, report_id=None, anchor_role="Approved front: completed design and style"):
        job = self._read(job_id)
        self.validate_sources(job)
        report_id = report_id or work_id("reconstruction")
        path = self._report_path(job_id, report_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        filename, checksum = self._snapshot(path.parent, "candidate", contents)
        report = {"id": report_id, "task_id": job_id, "target_hash": job["target_hash"],
                  "candidate": candidate, "candidate_sha256": checksum, "context": context,
                  "model": job["model"], "instruction_version": self.true_up.INSTRUCTION_VERSION,
                  "source_hashes": [r["sha256"] for r in job["target"]["sources"]],
                  "status": "RUNNING", "error": "", "items": [], "summary": ""}
        write_json_atomic(path, report)
        try:
            images = [str(path.parent / filename), *[str(self._path(job_id).parent / r["filename"])
                                                     for r in job["target"]["sources"]]]
            roles = ["candidate", *[r["caption"] for r in job["target"]["sources"]]]
            if anchor:
                anchor_file, anchor_hash = self._snapshot(path.parent, "front", anchor)
                images.append(str(path.parent / anchor_file)); roles.append(anchor_role)
                report["anchor_sha256"] = anchor_hash
            report.update(self.true_up.compare(job["model"], job["target"], images,
                                               {"roles": roles, "task": context}))
            report["status"] = "COMPLETE"
        except Exception as exc:
            from zet.services.storage_health_service import pause_on_storage_error
            pause_on_storage_error(self.app.config, exc)
            report.update(status="FAILED", error=str(exc))
            raise
        finally:
            write_json_atomic(path, report)
        return report

    def report(self, job_id, report_id):
        path = self._report_path(job_id, report_id)
        value = json.loads(path.read_text(encoding="utf-8"))
        with self._guard:
            active = report_id in self._active or self._pending_workflow(report_id)
        if value["status"] == "RUNNING" and not active:
            value.update(status="FAILED", error="Comparison was interrupted. Compare the selected image again.")
            write_json_atomic(path, value)
        return value

    def start_comparison(self, payload):
        expected = payload.get("selected_result")
        contents, source = self.generator.slot_workspace.selected_result(expected)
        metadata = source.get("reconstruction", {})
        job_id = metadata.get("id", "")
        job = self._read(job_id)
        if job.get("version") != 2 or metadata.get("target_hash") != job.get("target_hash"):
            raise ValueError("Reconstruct this image with a current target brief before comparing it.")
        report_id = work_id("reconstruction")
        report = {"id": report_id, "task_id": job_id, "status": "RUNNING", "items": [], "error": ""}
        write_json_atomic(self._report_path(job_id, report_id), report)
        with self._guard:
            self._active.add(report_id)

        filename, _ = self._snapshot(self._report_path(job_id, report_id).parent, "requested-candidate", contents)
        from zet.services.ai_workflow_service import AIWorkflowService
        AIWorkflowService(self.app).submit(self._comparison_task, [job_id, report_id, expected, filename],
            service="reconstruction", owner={"report_id": report_id})
        return report

    def correct_selected(self, payload):
        expected = payload.get("selected_result")
        contents, source = self.generator.slot_workspace.selected_result(expected)
        job_id = str(payload.get("task_id") or "")
        report_id = str(payload.get("report_id") or "")
        report = self.report(job_id, report_id)
        item_ids = payload.get("item_ids", [])
        instructions = text(payload.get("instructions", ""), "Refinement")
        if ((report["status"] != "COMPLETE" and not (instructions and not item_ids))
                or report["candidate"] != {"selected_result": expected}
                or source.get("reconstruction", {}).get("id") != job_id):
            raise ValueError("The comparison does not belong to the current selection.")
        if not isinstance(item_ids, list) or any(not isinstance(i, str) for i in item_ids):
            raise ValueError("Choose current correction item IDs.")
        correction_items(report, item_ids, instructions)
        key = fingerprint([report_id, sorted(item_ids), instructions])
        directory = self._report_path(job_id, report_id).parent
        with file_lock(directory / "corrections.lock"):
            mapping_path = directory / "corrections.json"
            mapping = json.loads(mapping_path.read_text(encoding="utf-8")) if mapping_path.exists() else {}
            if key in mapping:
                previous = self.status(mapping[key])
                if previous["status"] != "FAILED":
                    return previous
            old = self._read(job_id)
            new = self.revise(job_id, old["target"]["description"], old["target"]["identity"], old["target"]["proposals"])
            if instructions:
                new["target"]["change_text"] += "\nLatest operator feedback (takes precedence): " + instructions
                new["target"]["changes"].append({"id": fingerprint([new["id"], instructions])[:16],
                    "action": "modify", "subject": instructions, "result": instructions})
                new["target_hash"] = fingerprint(new["target"])
                new["prompt"] = self.compose(new)
            new.update(status="RUNNING", count=1, selected_result=expected,
                       width=self.generator._dimension(payload.get("width", 1024), "Width"),
                       height=self.generator._dimension(payload.get("height", 1024), "Height"))
            self._save(new)
            try:
                self.generator.slot_workspace.reserve_reconstruction(new["id"], 1)
            except Exception as exc:
                from zet.services.storage_health_service import pause_on_storage_error
                pause_on_storage_error(self.app.config, exc)
                new.update(status="FAILED", error=str(exc)); self._save(new)
                raise
            mapping[key] = new["id"]
            write_json_atomic(mapping_path, mapping)
            with self._guard:
                self._active.add(new["id"])

        filename, _ = self._snapshot(self._path(new["id"]).parent, "requested-correction", contents)
        from zet.services.ai_workflow_service import AIWorkflowService
        AIWorkflowService(self.app).submit(self._correction_task,
            [new["id"], job_id, report_id, item_ids, instructions, expected, filename],
            service="reconstruction", owner={"reconstruction_id": new["id"]})
        return new

    def _comparison_task(self, job_id, report_id, expected, filename):
        try:
            contents = (self._report_path(job_id, report_id).parent / filename).read_bytes()
            self.compare(job_id, contents, {"selected_result": expected},
                "Preserve the selected result's intended composition. Actual rendered prompt: "
                + self.generator.status(expected["requestId"])["prompt"], report_id=report_id)
        except Exception as exc:
            from zet.services.storage_health_service import pause_on_storage_error
            pause_on_storage_error(self.app.config, exc)
            path = self._report_path(job_id, report_id)
            report = json.loads(path.read_text(encoding="utf-8"))
            report.update(status="FAILED", error=str(exc)); write_json_atomic(path, report)
        finally:
            with self._guard:
                self._active.discard(report_id)

    def _correction_task(self, new_id, job_id, report_id, item_ids, instructions, expected, filename):
        new = self._read(new_id)
        report = self.report(job_id, report_id)
        try:
            contents = (self._path(new_id).parent / filename).read_bytes()
            spec = self.render_spec(job_id, report["context"], [("Styled candidate to correct", contents)],
                                    report_id=report_id, item_ids=item_ids, instructions=instructions)
            new.update(prompt=spec["prompt"], status="DISPATCHING")
            spec["reconstruction"].update(self.metadata(new), parent_task_id=job_id)
            new["render_payload"] = spec
            self._save(new)
            self.generator.slot_workspace.submit_reconstruction(new_id,
                {**spec, "width": new["width"], "height": new["height"]}, expected)
            new["status"] = "SUBMITTED"
        except Exception as exc:
            from zet.services.storage_health_service import pause_on_storage_error
            pause_on_storage_error(self.app.config, exc)
            new.update(status="FAILED", error=str(exc))
        finally:
            self._save(new)
            with self._guard:
                self._active.discard(new_id)

    def _path(self, job_id):
        if not re.fullmatch(r"[a-f0-9]{32}", job_id):
            raise ValueError("Invalid reconstruction ID.")
        return self.root / job_id / "job.json"

    def _read(self, job_id):
        try:
            value = json.loads(self._path(job_id).read_text(encoding="utf-8"))
            if value.get("version", 1) not in {1, 2}:
                raise ValueError("Unsupported reconstruction version.")
            if value.get("version") == 2 and value.get("target_hash") != fingerprint(value["target"]):
                raise ValueError("The reconstruction target changed outside its revision. Start a new task.")
            return value
        except FileNotFoundError as exc:
            raise KeyError("Reconstruction not found.") from exc

    def _save(self, job):
        write_json_atomic(self._path(job["id"]), job)

    def options(self):
        return {"models": [item["id"] for item in self.catalog.models(required=["vision"])],
                "default_model": self.app.config.ai_image_prompt_generation_model,
                "style": universe_style(self.app.config.base_library_path)}

    def start(self, payload):
        count = render_count(payload.get("count"), 4)
        width = self.generator._dimension(payload.get("width", 1024), "Width")
        height = self.generator._dimension(payload.get("height", 1024), "Height")
        job = self.prepare(payload)
        job.update(status="RUNNING", count=count, width=width, height=height,
                   selected_result=payload.get("selected_result"))
        self._save(job)
        with self._guard:
            self._active.add(job["id"])
        try:
            self.generator.slot_workspace.reserve_reconstruction(job["id"], count)
        except Exception as exc:
            from zet.services.storage_health_service import pause_on_storage_error
            pause_on_storage_error(self.app.config, exc)
            job.update(status="FAILED", error=str(exc)); self._save(job)
            with self._guard:
                self._active.discard(job["id"])
            raise
        from zet.services.ai_workflow_service import AIWorkflowService
        AIWorkflowService(self.app).submit(self._run, [job["id"]], service="reconstruction",
                                         owner={"reconstruction_id": job["id"]})
        return job

    def _run(self, job_id):
        job = self._read(job_id)
        try:
            if job.get("version") == 2:
                job = self.analyze(job_id)
                if job["target"]["questions"]:
                    raise ValueError("Analysis needs clarification: " + "; ".join(job["target"]["questions"]))
                if job.get("selected_result"):
                    self.generator.slot_workspace.selected_result(job["selected_result"])
                spec = self.render_spec(job_id, "")
                job.update(status="DISPATCHING", prompt=spec["prompt"])
                self._save(job)
                self.generator.slot_workspace.submit_reconstruction(job_id, {
                    **spec, "count": job["count"], "width": job["width"], "height": job["height"]}, job.get("selected_result"))
                job["status"] = "SUBMITTED"
                return
            image = str(self._path(job_id).parent / job["source_file"])
            draft = self.analyzer.model_service.generate_json(job["model"],
                "Describe visible content independently of rendering style.", self.INSTRUCTIONS,
                self.SCHEMA, images=[image])
            content = draft.get("content_prompt")
            uncertainties = draft.get("uncertainties")
            if (not isinstance(content, str) or not content.strip() or not isinstance(uncertainties, list)
                    or any(not isinstance(item, str) for item in uncertainties)):
                raise ValueError("The analysis model returned an invalid reconstruction description.")
            job.update(content_prompt=content.strip(), uncertainties=uncertainties,
                       prompt=compose_style(content, job["style"]["text"], job["notes"]), status="DISPATCHING")
            self._save(job)
            if job["source"]["asset_id"]:
                current = self.app.entity_library_asset(job["source"]["asset_id"])
                if (current.get("status") == "archived" or current["checksum"] != job["source"].get("managed_checksum", job["source"]["sha256"])):
                    raise ValueError("The library source changed during analysis. Start a new reconstruction.")
            self.generator.slot_workspace.submit_reconstruction(job_id, {
                "mode": "txt2img", "prompt": job["prompt"], "negative_prompt": "",
                "count": job["count"], "width": job["width"], "height": job["height"],
                "reconstruction": {key: job[key] for key in ("id", "model", "source", "style",
                    "instruction_version", "content_prompt", "uncertainties", "notes", "prompt")},
            })
            job["status"] = "SUBMITTED"
        except Exception as exc:
            from zet.services.storage_health_service import pause_on_storage_error
            pause_on_storage_error(self.app.config, exc)
            job.update(status="FAILED", error=str(exc))
        finally:
            try:
                self._save(job)
            finally:
                with self._guard:
                    self._active.discard(job_id)

    def _pending_workflow(self, job_id):
        from zet.services.ai_workflow_service import AIWorkflowService
        return AIWorkflowService(self.app).pending(job_id)

    def pending(self, job_id):
        try:
            job = self.status(job_id)
            return {**job, "status": "RUNNING" if job["status"] in {"RUNNING", "DISPATCHING"} else "FAILED"}
        except (KeyError, ValueError):
            return {}

    def status(self, job_id):
        with self._guard:
            job = self._read(job_id)
            active = job_id in self._active or self._pending_workflow(job_id)
        if not active and job["status"] in {"RUNNING", "DISPATCHING"}:
            # A persisted render job is authoritative after a crash at the handoff.
            if job_id in self.generator._jobs:
                job["status"] = "SUBMITTED"
            else:
                job.update(status="FAILED", error="Analysis was interrupted. Start a new reconstruction.")
            self._save(job)
        return job
