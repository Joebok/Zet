"""Pinned narrative sources, editable cutouts and deterministic final composition."""
from copy import deepcopy
from io import BytesIO
import math
import threading

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from zet.models.narrative import new_id
from zet.services.atomic_file_service import write_bytes_atomic


_EXTRACTION_LOCK = threading.Lock()


def png_bytes(image):
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


class NarrativeAssemblyService:
    def __init__(self, author):
        self.author = author
        self.repository = author.repository

    def sources(self, story, scene):
        parent = self.repository.read(story, scene)
        result = []
        for target in parent["target_ids"]:
            record = self.repository.read(story, scene, target)
            if record["kind"] == "assembly":
                continue
            result.append({key: record[key] for key in ("id", "title", "kind", "selected_id")} | {
                "candidates": [{"id": item["id"], "slot": item["slot"]} for item in record["candidates"].values()
                               if item["status"] == "COMPLETE" and item["image"]]})
        return result

    def bind_layers(self, story, scene, record, previous):
        """Accept identifiers and controls only; source filenames/metadata are server owned."""
        folder = self.repository.folder(story, scene, record["id"])
        old = {item["id"]: item for item in previous}
        available = set(self.repository.read(story, scene)["target_ids"])
        layers, identifiers = [], set()
        for index, supplied in enumerate(record["layers"]):
            if not isinstance(supplied, dict):
                raise ValueError("A layer must be an object.")
            identifier = supplied.get("id") or new_id()
            self.repository.folder(identifier)
            if identifier in identifiers:
                raise ValueError("Layer IDs must be unique.")
            identifiers.add(identifier)
            existing = old.get(identifier, {})
            source_id, candidate_id = supplied.get("target_id"), supplied.get("candidate_id")
            if not isinstance(source_id, str) or not isinstance(candidate_id, str):
                raise ValueError("Choose a completed source image for each layer.")
            unchanged = existing.get("target_id") == source_id and existing.get("candidate_id") == candidate_id
            if unchanged and (folder / existing["source_file"]).is_file():
                metadata = {key: existing[key] for key in ("source_file", "label", "narrative", "source_kind")}
            else:
                if source_id not in available:
                    raise ValueError("Choose a source target from this scene.")
                source = self.repository.read(story, scene, source_id)
                candidate = source["candidates"].get(candidate_id)
                if source["kind"] not in {"subscene", "backdrop"} or not candidate or candidate["status"] != "COMPLETE" or not candidate["image"]:
                    raise ValueError("Choose a completed subscene or backdrop image.")
                source_path = self.repository.folder(story, scene, source_id) / candidate["image"]
                filename = f"sources/{source_id}-{candidate_id}.png"
                if not (folder / filename).is_file():
                    write_bytes_atomic(folder / filename, source_path.read_bytes())
                metadata = {"source_file": filename, "label": source["title"], "narrative": source["narrative"],
                            "source_kind": source["kind"]}
            role = supplied.get("role", "base" if metadata["source_kind"] == "backdrop" and index == 0 else "group")
            if role not in {"base", "group"} or (role == "base" and metadata["source_kind"] != "backdrop"):
                raise ValueError("The base layer must be a backdrop.")
            fit = supplied.get("fit", "cover")
            cutout = supplied.get("cutout", "auto" if role == "group" else "opaque")
            if fit not in {"cover", "contain"} or cutout not in {"auto", "alpha", "opaque"}:
                raise ValueError("Choose cover/contain and auto/alpha/opaque cutout.")
            numbers = {}
            for key, default, minimum, maximum in (("x", 0.1, -2, 2), ("y", 0.2, -2, 2), ("scale", 0.4, .01, 4),
                                                   ("z", index, -100, 100), ("tolerance", 35, 0, 255)):
                value = supplied.get(key, default)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
                    raise ValueError(f"Invalid layer {key}.")
                numbers[key] = value
            visible = supplied.get("visible", True)
            if not isinstance(visible, bool):
                raise ValueError("Layer visibility must be a boolean.")
            strokes = supplied.get("strokes", [])
            if not isinstance(strokes, list) or len(strokes) > 5000:
                raise ValueError("Invalid mask corrections.")
            for stroke in strokes:
                if not isinstance(stroke, dict) or stroke.get("mode") not in {"keep", "remove"}:
                    raise ValueError("Choose keep or remove for mask corrections.")
                for key, lower, upper in (("x", 0, 1), ("y", 0, 1), ("radius", .001, .5)):
                    value = stroke.get(key)
                    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not lower <= value <= upper:
                        raise ValueError("Mask corrections must use source coordinates.")
            layers.append({"id": identifier, "target_id": source_id, "candidate_id": candidate_id, **metadata,
                           "role": role, "fit": fit, "cutout": cutout, "visible": visible, "strokes": strokes, **numbers})
        if sum(layer["role"] == "base" for layer in layers) > 1:
            raise ValueError("Choose one base backdrop.")
        return layers

    @staticmethod
    def cutout(image, layer):
        image = image.convert("RGBA")
        alpha = image.getchannel("A")
        if layer["cutout"] == "opaque":
            alpha = Image.new("L", image.size, 255)
        elif layer["cutout"] == "auto" and alpha.getextrema()[0] >= 230:
            # Some Qwen RGBA images have near-opaque alpha noise, rather than a usable cutout.
            # Remove border-connected neutral background while preserving meaningful native alpha.
            rgb = np.asarray(image.convert("RGB")).astype(np.int16)
            corners = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]))
            color = np.median(corners, axis=0)
            paper = (np.max(np.abs(rgb - color), axis=2) <= layer["tolerance"]).astype(np.uint8)
            _, labels = cv2.connectedComponents(paper, connectivity=8)
            border = set(np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1])).tolist()) - {0}
            background = np.isin(labels, list(border))
            # Border samples include the source floor. GrabCut separates it from the people,
            # while the neutral connected region provides dependable background seeds.
            mask = np.where(background, cv2.GC_BGD, cv2.GC_PR_FGD).astype(np.uint8)
            mask[0, :] = mask[-1, :] = cv2.GC_BGD
            mask[:, 0] = mask[:, -1] = cv2.GC_BGD
            if np.count_nonzero(mask == cv2.GC_PR_FGD) >= 5:
                try:
                    with _EXTRACTION_LOCK:
                        cv2.setRNGSeed(0)
                        cv2.grabCut(np.asarray(image.convert("RGB")), mask, None, np.zeros((1, 65), np.float64),
                                    np.zeros((1, 65), np.float64), 3, cv2.GC_INIT_WITH_MASK)
                except cv2.error as exc:
                    raise ValueError("Background extraction failed; choose alpha or opaque and correct the mask.") from exc
            alpha = Image.fromarray(np.where(np.isin(mask, (cv2.GC_FGD, cv2.GC_PR_FGD)), 255, 0).astype(np.uint8))
        draw = ImageDraw.Draw(alpha)
        for stroke in layer["strokes"]:
            x, y = stroke["x"] * image.width, stroke["y"] * image.height
            radius = stroke["radius"] * max(image.size)
            draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=255 if stroke["mode"] == "keep" else 0)
        if not alpha.getbbox():
            raise ValueError(f"{layer['label']}: extraction produced an empty mask; use alpha or keep corrections.")
        image.putalpha(alpha)
        return image

    def layer_image(self, story, scene, target, layer_id, kind="cutout"):
        record = self.repository.read(story, scene, target)
        layer = next((item for item in record["layers"] if item["id"] == layer_id), None)
        if not layer:
            raise KeyError("Layer not found.")
        with Image.open(self.repository.folder(story, scene, target) / layer["source_file"]) as source:
            if kind == "source":
                return png_bytes(source.convert("RGBA"))
            cut = self.cutout(source, layer)
            if kind == "overlay":
                image = source.convert("RGBA")
                tint = Image.new("RGBA", image.size, (220, 40, 60, 100))
                tint.putalpha(ImageOps.invert(cut.getchannel("A")).point(lambda value: round(value * .4)))
                return png_bytes(Image.alpha_composite(image, tint))
            if kind != "cutout":
                raise ValueError("Unknown layer preview.")
            return png_bytes(cut)

    def compose(self, story, scene, detail):
        size = (detail["width"], detail["height"])
        layers = [item for item in detail["layers"] if item["visible"]]
        bases = [item for item in layers if item["role"] == "base"]
        if len(bases) != 1:
            raise ValueError("Choose one visible base backdrop before composing.")
        folder = self.repository.folder(story, scene, detail["id"])
        with Image.open(folder / bases[0]["source_file"]) as source:
            base = source.convert("RGB").convert("RGBA")
            if bases[0]["fit"] == "cover":
                canvas = ImageOps.fit(base, size, method=Image.Resampling.LANCZOS)
            else:
                fitted = ImageOps.contain(base, size, method=Image.Resampling.LANCZOS)
                canvas = Image.new("RGBA", size, "white")
                canvas.alpha_composite(fitted, ((size[0]-fitted.width)//2, (size[1]-fitted.height)//2))
        protected = Image.new("L", size, 0)
        contacts = Image.new("L", size, 0)
        contact_draw = ImageDraw.Draw(contacts)
        for layer in sorted((item for item in layers if item["role"] != "base"), key=lambda item: item["z"]):
            with Image.open(folder / layer["source_file"]) as source:
                cut = self.cutout(source, layer)
            width = max(1, round(size[0] * layer["scale"]))
            height = max(1, round(width * cut.height / cut.width))
            position = (round(layer["x"] * size[0]), round(layer["y"] * size[1]))
            x0, y0 = max(0, -position[0]), max(0, -position[1])
            x1, y1 = min(width, size[0]-position[0]), min(height, size[1]-position[1])
            if x1 <= x0 or y1 <= y0:
                continue
            # Resize only the visible source region; extreme scales must not allocate huge images.
            box = (x0*cut.width/width, y0*cut.height/height, x1*cut.width/width, y1*cut.height/height)
            cut = cut.resize((x1-x0, y1-y0), Image.Resampling.LANCZOS, box=box)
            position = (position[0]+x0, position[1]+y0)
            canvas.alpha_composite(cut, position)
            coverage = Image.new("L", size, 0)
            coverage.paste(cut.getchannel("A"), position)
            protected = Image.fromarray(np.maximum(np.asarray(protected), np.asarray(coverage)))
            bbox = coverage.getbbox()
            if bbox:
                x0, y0, x1, y1 = bbox
                contact_draw.ellipse((x0, y1-8, x1, y1+16), fill=255)
        occupied = np.asarray(protected) > 0
        ring = cv2.dilate(occupied.astype(np.uint8), np.ones((25, 25), np.uint8)) * 255
        edits = Image.fromarray(np.maximum(ring, np.asarray(contacts))).filter(ImageFilter.GaussianBlur(2))
        weights = np.array(edits)
        weights[occupied] = 0
        return canvas.convert("RGB"), Image.fromarray(weights), protected

    def preview(self, story, scene, target):
        with self.repository.lock():
            record = self.repository.read(story, scene, target)
            canvas, _, _ = self.compose(story, scene, record)
            return png_bytes(canvas)

    def snapshot(self, story, scene, detail, job_id, *, include_composite=True):
        folder = self.repository.folder(story, scene, detail["id"])
        mode = detail.get("assembly_mode", "finish_composite")
        manifest = self.reference_manifest(story, scene, detail, required=include_composite) if mode == "assemble_references" else []
        relative = f"snapshots/{job_id}"
        root = folder / relative
        if include_composite and mode == "finish_composite":
            canvas, mask, protected = self.compose(story, scene, detail)
            for name, image in (("composite.png", canvas), ("edit-mask.png", mask), ("protected.png", protected)):
                write_bytes_atomic(root / name, png_bytes(image))
        layers = deepcopy(detail["layers"])
        for layer in layers:
            name = f"{layer['id']}.png"
            write_bytes_atomic(root / name, (folder / layer["source_file"]).read_bytes())
            layer["source_file"] = f"{relative}/{name}"
        references = [{"path": str(root / "composite.png"), "label": "Placed final scene",
                       "role": "composition", "image_index": 1}] if include_composite and mode == "finish_composite" else []
        if mode == "assemble_references":
            frozen = {layer["id"]: layer for layer in layers}
            references = [{**item, "path": str(folder / frozen[item["layer_id"]]["source_file"])} for item in manifest]
        return {"folder": relative, "layers": layers, "assembly_mode": mode,
                "width": detail["width"], "height": detail["height"], "references": references,
                "has_composite": include_composite and mode == "finish_composite"}, references

    def reference_manifest(self, story, scene, detail, *, required=False):
        """Bind original sources and their full-image placement without extracting cutouts."""
        visible = [layer for layer in detail["layers"] if layer["visible"]]
        bases = [layer for layer in visible if layer["role"] == "base"]
        if required and len(bases) != 1:
            raise ValueError("Choose one visible base backdrop before assembling.")
        if required and len(visible) > 10:
            raise ValueError("Reference assembly accepts up to ten visible source layers.")
        ordered = bases + sorted((layer for layer in visible if layer["role"] != "base"), key=lambda layer: layer["z"])
        folder = self.repository.folder(story, scene, detail["id"])
        result = []
        for index, layer in enumerate(ordered, 1):
            with Image.open(folder / layer["source_file"]) as source:
                source_width, source_height = source.size
            width = max(1, round(detail["width"] * layer["scale"]))
            placement = {"x": round(layer["x"] * detail["width"]), "y": round(layer["y"] * detail["height"]),
                         "width": width, "height": max(1, round(width * source_height / source_width))}
            if layer["role"] == "base":
                placement = {"x": 0, "y": 0, "width": detail["width"], "height": detail["height"]}
            result.append({"layer_id": layer["id"], "image_index": index, "label": layer["label"],
                           "role": layer["role"], "narrative": layer.get("narrative", ""), "fit": layer["fit"],
                           "source_width": source_width, "source_height": source_height,
                           **placement, "z": layer["z"]})
        return result

    def finish(self, story, scene, target, snapshot, proposal):
        if snapshot.get("assembly_mode", "finish_composite") == "assemble_references":
            with Image.open(BytesIO(proposal)) as generated:
                if generated.size != (snapshot["width"], snapshot["height"]):
                    raise ValueError("Assembly output dimensions do not match the requested canvas.")
            return proposal
        root = self.repository.folder(story, scene, target) / snapshot["folder"]
        with Image.open(root / "composite.png") as raw, Image.open(root / "edit-mask.png") as mask, Image.open(BytesIO(proposal)) as generated:
            if generated.size != raw.size:
                raise ValueError("Finishing output dimensions do not match the composite.")
            return png_bytes(Image.composite(generated.convert("RGB"), raw.convert("RGB"), mask.convert("L")))

    def candidate_composite(self, story, scene, target, candidate_id):
        record = self.repository.read(story, scene, target)
        candidate = record["candidates"].get(candidate_id, {})
        snapshot = candidate.get("assembly_snapshot")
        if not snapshot or not snapshot.get("has_composite", snapshot.get("assembly_mode", "finish_composite") == "finish_composite"):
            raise KeyError("Candidate has no assembly snapshot.")
        return self.repository.folder(story, scene, target) / snapshot["folder"] / "composite.png"
