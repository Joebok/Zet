from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from zet.services.comfyui_render_service import (
    comfyui_model_options,
    list_comfyui_node_types,
    run_comfyui_workflow,
)
from zet.services.local_render_types import LocalRenderError


MASK_REMOVE = 0
MASK_EDIT = 128
MASK_PROTECT = 255
REAR_VIEWS = {"Back", "Back-Left-3-4", "Back-Right-3-4"}
PROFILE_VIEWS = {"Left-Profile", "Right-Profile"}
SAM_VARIANTS = (
    {"threshold": 0.50, "refine": 2, "head": "head and face", "hair": "hair", "ears": "ears", "neck": "neck"},
    {"threshold": 0.40, "refine": 3, "head": "human head", "hair": "silver hair", "ears": "pointed elf ears", "neck": "human neck"},
    {"threshold": 0.30, "refine": 3, "head": "face and head", "hair": "hairstyle", "ears": "pointed ear", "neck": "neck below head"},
)
MASK_MODEL_REQUIREMENTS = {
    "birefnet.safetensors": (
        Path(r"D:\Comfy-Desktop\ComfyUI-Shared\models\background_removal\birefnet.safetensors"),
        "9ab37426bf4de0567af6b5d21b16151357149139362e6e8992021b8ce356a154",
    ),
    "mediapipe_face_fp32.safetensors": (
        Path(r"D:\Comfy-Desktop\ComfyUI-Shared\models\detection\mediapipe_face_fp32.safetensors"),
        "a98c4806081d40eba35102a0f6dc0000c2e1388b72cf24e691703d0605bd888a",
    ),
    "sam3.1_multiplex_fp16.safetensors": (
        Path(r"D:\Comfy-Desktop\ComfyUI-Shared\models\checkpoints\sam3.1_multiplex_fp16.safetensors"),
        "9ba99c92703c2e8b4f47de2d34a539bb8e18923049e238b780d70dbe6368eb03",
    ),
}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class HeadFitmentMaskResult:
    mask_path: Path
    report_path: Path
    overlay_path: Path
    workflow_path: Path
    artifact_paths: list[Path]
    prompt_id: str


class HeadFitmentMaskGenerationError(LocalRenderError):
    pass


def _binary(path: Path, size: tuple[int, int]) -> np.ndarray:
    with Image.open(path) as image:
        gray = image.convert("L")
        if gray.size != size:
            gray = gray.resize(size, Image.Resampling.NEAREST)
        values = np.array(gray)
    return values >= 128


def _mask_image(mask: np.ndarray, path: Path) -> None:
    Image.fromarray(np.where(mask, 255, 0).astype(np.uint8), "L").save(path)


def _largest_component_ratio(mask: np.ndarray) -> float:
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    if count <= 1:
        return 0.0
    areas = stats[1:, cv2.CC_STAT_AREA]
    return float(areas.max() / max(1, areas.sum()))


def improved_foreground_mask(image: Image.Image) -> np.ndarray:
    """Segment a portrait without declaring the entire image border background."""
    rgba = np.array(image.convert("RGBA"))
    alpha = rgba[:, :, 3]
    if int(alpha.min()) < 250:
        return alpha > 8
    rgb = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2BGR)
    h, w = rgb.shape[:2]
    grab = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
    patch = max(4, int(min(h, w) * 0.025))
    corners = np.concatenate(
        [rgb[:patch, :patch], rgb[:patch, -patch:], rgb[-patch:, :patch], rgb[-patch:, -patch:]], axis=0
    )
    background = np.median(corners.reshape(-1, 3), axis=0)
    distance = np.linalg.norm(rgb.astype(np.float32) - background, axis=2)
    grab[distance < 10] = cv2.GC_BGD
    grab[distance > 30] = cv2.GC_PR_FGD
    center = np.zeros((h, w), np.uint8)
    cv2.ellipse(center, (w // 2, int(h * 0.48)), (max(2, int(w * 0.30)), max(2, int(h * 0.43))), 0, 0, 360, 1, -1)
    grab[(center > 0) & (distance > 18)] = cv2.GC_FGD
    try:
        bgd = np.zeros((1, 65), np.float64)
        fgd = np.zeros((1, 65), np.float64)
        cv2.grabCut(rgb, grab, None, bgd, fgd, 4, cv2.GC_INIT_WITH_MASK)
        foreground = np.isin(grab, (cv2.GC_FGD, cv2.GC_PR_FGD))
    except cv2.error:
        foreground = distance > 22
    kernel = np.ones((3, 3), np.uint8)
    cleaned = cv2.morphologyEx(foreground.astype(np.uint8), cv2.MORPH_CLOSE, kernel, iterations=2)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
    if count <= 1:
        return cleaned > 0
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    keep = labels == largest
    largest_dilated = cv2.dilate(keep.astype(np.uint8), np.ones((15, 15), np.uint8), iterations=1) > 0
    minimum = max(8, int(h * w * 0.00005))
    for label in range(1, count):
        component = labels == label
        if stats[label, cv2.CC_STAT_AREA] >= minimum and np.any(component & largest_dilated):
            keep |= component
    return keep


def _neck_ratio(body: np.ndarray) -> float:
    h, _ = body.shape
    widths = []
    for y in range(max(0, int(h * 0.04)), min(h, int(h * 0.32))):
        xs = np.where(body[y])[0]
        widths.append(int(xs[-1] - xs[0] + 1) if len(xs) else 0)
    nonzero = [value for value in widths if value]
    if not nonzero:
        return 0.30
    split = max(1, len(nonzero) // 2)
    return float(np.clip(min(nonzero[split:] or nonzero) / max(1, max(nonzero[:split])), 0.18, 0.55))


def _iou(left: np.ndarray, right: np.ndarray) -> float:
    union = left | right
    return float(np.count_nonzero(left & right) / max(1, np.count_nonzero(union)))


def _merge_foregrounds(primary: np.ndarray, supplemental: np.ndarray) -> np.ndarray:
    if not np.any(primary):
        return supplemental
    radius = max(5, int(round(min(primary.shape) * 0.015)))
    kernel = np.ones((radius * 2 + 1, radius * 2 + 1), np.uint8)
    nearby = cv2.dilate(primary.astype(np.uint8), kernel, iterations=1) > 0
    return primary | (supplemental & nearby)


def _largest_component(mask: np.ndarray) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    if count <= 1:
        return np.zeros_like(mask, dtype=bool)
    return labels == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))


def analyze_body_neck_geometry(body_foreground: np.ndarray) -> dict[str, Any]:
    body = _largest_component(body_foreground)
    ys, xs = np.where(body)
    if not len(xs):
        raise HeadFitmentMaskGenerationError("Body reference foreground is empty.")
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    bbox_height = y1 - y0 + 1
    widths: list[float] = []
    centers: list[float] = []
    for y in range(y0, y1 + 1):
        row = np.where(body[y])[0]
        widths.append(float(row[-1] - row[0] + 1) if len(row) else 0.0)
        centers.append(float((row[0] + row[-1]) / 2.0) if len(row) else 0.0)
    smoothed = np.convolve(widths, np.ones(9, dtype=np.float32) / 9.0, mode="same")
    search_start = max(1, int(bbox_height * 0.08))
    search_end = max(search_start + 1, int(bbox_height * 0.24))
    search = np.where(smoothed[search_start:search_end] > 0, smoothed[search_start:search_end], np.inf)
    neck_offset = search_start + int(np.argmin(search))
    neck_width = float(smoothed[neck_offset])
    head_width = float(np.max(smoothed[:neck_offset + 1]))
    shoulder_offset = next(
        (
            offset
            for offset in range(neck_offset + 1, min(len(smoothed) - 6, int(bbox_height * 0.36)))
            if np.all(smoothed[offset:offset + 6] >= neck_width * 1.5)
        ),
        None,
    )
    if (
        not np.isfinite(neck_width)
        or neck_width < 4
        or head_width < neck_width * 1.2
        or shoulder_offset is None
    ):
        raise HeadFitmentMaskGenerationError("Body reference does not contain a credible head, neck, and shoulder silhouette.")
    return {
        "bbox": [x0, y0, x1, y1],
        "center_x_ratio": round(float(centers[neck_offset] / body.shape[1]), 5),
        "neck_width_to_head_ratio": round(float(neck_width / head_width), 5),
        "neck_length_ratio": round(float((shoulder_offset - neck_offset) / bbox_height), 5),
        "neck_y_ratio": round(float(neck_offset / bbox_height), 5),
        "shoulder_y_ratio": round(float(shoulder_offset / bbox_height), 5),
    }


def _source_neck_anchor(
    neck: np.ndarray,
    head_support: np.ndarray,
    face_oval: np.ndarray,
    view: str,
) -> dict[str, int | float | bool | str]:
    neck = _largest_component(neck)
    ys, xs = np.where(neck)
    if not len(xs):
        raise HeadFitmentMaskGenerationError("SAM returned no credible neck component.")
    support_y, support_x = np.where(head_support)
    head_width = int(support_x.max() - support_x.min() + 1)
    if view == "Left-Profile":
        center_x = int(np.percentile(xs, 65))
    elif view == "Right-Profile":
        center_x = int(np.percentile(xs, 35))
    else:
        center_x = int(np.median(xs))
    x_radius = max(8, int(head_width * 0.12))
    local_y, local_x = np.where(neck & (np.abs(np.indices(neck.shape)[1] - center_x) <= x_radius))
    if not len(local_y):
        local_y, local_x = ys, xs
    top_y = int(np.percentile(local_y, 8))
    band = neck & (np.indices(neck.shape)[0] >= top_y) & (
        np.indices(neck.shape)[0] <= top_y + max(8, int(neck.shape[0] * 0.04))
    )
    band_y, band_x = np.where(band)
    if len(band_x):
        center_x = int(np.median(band_x)) if view not in PROFILE_VIEWS else center_x
        width = int(np.percentile(band_x, 90) - np.percentile(band_x, 10) + 1)
    else:
        width = int(np.percentile(xs, 90) - np.percentile(xs, 10) + 1)
    face_x = np.where(face_oval)[1]
    face_center = int(np.median(face_x)) if len(face_x) else None
    posterior_ok = True
    if view == "Left-Profile":
        posterior_ok = face_center is not None and center_x > face_center
    elif view == "Right-Profile":
        posterior_ok = face_center is not None and center_x < face_center
    return {
        "center_x": center_x,
        "top_y": top_y,
        "width": max(8, min(width, int(head_width * 0.55))),
        "head_width": head_width,
        "face_center_x": face_center,
        "posterior_ok": posterior_ok,
        "component_area": int(np.count_nonzero(neck)),
    }


def _source_shoulder_line(
    foreground: np.ndarray,
    hair: np.ndarray,
    neck: np.ndarray,
    top_y: int,
    neck_width: int,
) -> int:
    h = foreground.shape[0]
    widths = []
    for y in range(top_y, min(h, top_y + int(h * 0.28))):
        row = np.where(neck[y])[0]
        widths.append(int(row[-1] - row[0] + 1) if len(row) else 0)
    initial = [value for value in widths[:max(6, int(h * 0.08))] if value]
    baseline = max(float(neck_width), float(np.median(initial)) if initial else 0.0)
    for offset in range(max(4, int(h * 0.08)), max(4, len(widths) - 5)):
        if all(value >= baseline * 1.5 for value in widths[offset:offset + 5]):
            return top_y + offset
    return min(h - 1, top_y + max(int(h * 0.12), 24))


def compose_semantic_mask(
    *,
    head_foreground: np.ndarray,
    body_foreground: np.ndarray,
    face_oval: np.ndarray,
    semantic: dict[str, np.ndarray],
    view: str,
    body_geometry: dict[str, Any] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    h, w = head_foreground.shape
    rear = view in REAR_VIEWS
    profile = view in PROFILE_VIEWS
    strategy = "rear_nape" if rear else "profile_posterior" if profile else "front_face"
    media_overlap = float(
        np.count_nonzero(face_oval & (semantic["head"] | semantic["hair"]))
        / max(1, np.count_nonzero(face_oval))
    )
    mediapipe_accepted = bool(not rear and np.any(face_oval) and media_overlap >= 0.70)
    accepted_face = face_oval if mediapipe_accepted else np.zeros_like(face_oval)
    head_support = semantic["head"] | semantic["hair"] | semantic["ears"] | accepted_face
    ys, xs = np.where(head_support)
    if not len(xs):
        raise HeadFitmentMaskGenerationError("SAM and MediaPipe returned no usable head region.")
    face_y, face_x = np.where(accepted_face)
    body_geometry = body_geometry or analyze_body_neck_geometry(body_foreground)
    neck_anchor = _source_neck_anchor(semantic["neck"], head_support, accepted_face, view)
    if not profile and not rear and len(face_x):
        center_x = int(np.median(face_x))
        top_y = min(h - 2, max(int(face_y.max()) - max(2, int(h * 0.01)), int(h * 0.45)))
        source_neck_width = max(8, int((face_x.max() - face_x.min() + 1) * 0.30))
    else:
        center_x = int(neck_anchor["center_x"])
        top_y = int(neck_anchor["top_y"])
        source_neck_width = int(neck_anchor["width"])
    support_dilated = cv2.dilate(head_support.astype(np.uint8), np.ones((11, 11), np.uint8), iterations=1) > 0
    row_grid = np.indices((h, w))[0]
    protected = head_foreground & support_dilated
    if rear:
        protected &= row_grid <= top_y + max(2, int(h * 0.01))
    protected |= accepted_face | semantic["hair"] | semantic["ears"]
    hull = np.zeros((h, w), np.uint8)
    points = np.column_stack((xs, ys)).astype(np.int32)
    cv2.fillConvexPoly(hull, cv2.convexHull(points), 1)
    protected |= head_foreground & (hull > 0) & (row_grid <= top_y)

    semantic_width = int(xs.max() - xs.min() + 1)
    target_ratio = float(np.clip(body_geometry["neck_width_to_head_ratio"], 0.20, 0.65 if rear else 0.55))
    mapped_body_center_x = float(body_geometry["center_x_ratio"]) * w
    target_center_x = int(round(center_x * 0.75 + mapped_body_center_x * 0.25)) if rear else int(round(mapped_body_center_x))
    top_half = max(4, int(source_neck_width * 0.50))
    bottom_half = max(4, int(semantic_width * target_ratio * 0.50))
    shoulder_y = _source_shoulder_line(
        head_foreground,
        semantic["hair"],
        semantic["neck"],
        top_y,
        max(source_neck_width, 8),
    )
    cut_y = min(h - 1, max(top_y + int(np.ceil(h * 0.08)), shoulder_y))
    polygon = np.array(
        [[center_x - top_half, top_y], [center_x + top_half, top_y],
         [target_center_x + bottom_half, cut_y], [target_center_x - bottom_half, cut_y]],
        dtype=np.int32,
    )
    editable = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(editable, polygon, 1)
    editable = editable.astype(bool) & ~protected
    mask = np.full((h, w), MASK_REMOVE, np.uint8)
    mask[editable] = MASK_EDIT
    mask[protected] = MASK_PROTECT

    semantic_agreement = _iou(protected, head_support)
    neck_dilated = cv2.dilate(semantic["neck"].astype(np.uint8), np.ones((15, 15), np.uint8), iterations=1) > 0
    neck_overlap = float(np.count_nonzero(editable & neck_dilated) / max(1, np.count_nonzero(editable)))
    head_center = float((xs.min() + xs.max()) / 2.0)
    center_tolerance = semantic_width * (0.10 if view == "Back" else 0.20)
    rear_alignment = float(np.clip(1.0 - abs(center_x - head_center) / max(1.0, center_tolerance), 0.0, 1.0))
    face_containment = (
        (neck_overlap + rear_alignment) / 2.0
        if rear
        else float(np.count_nonzero(protected & accepted_face) / max(1, np.count_nonzero(accepted_face)))
    )
    expected_ratio = target_ratio
    actual_ratio = (bottom_half * 2) / max(1, semantic_width)
    geometry_score = float(np.clip(1.0 - abs(expected_ratio - actual_ratio), 0.0, 1.0))
    geometry_score = (geometry_score + neck_overlap) / 2.0
    topology_score = _largest_component_ratio(protected)
    score = 0.35 * semantic_agreement + 0.25 * face_containment + 0.25 * geometry_score + 0.15 * topology_score
    editable_y, editable_x = np.where(editable)
    editable_area = int(len(editable_x))
    editable_area_ratio = float(editable_area / max(1, h * w))
    editable_height = int(editable_y.max() - editable_y.min() + 1) if len(editable_y) else 0
    shoulder_zone = head_foreground & ~semantic["hair"] & (row_grid > shoulder_y)
    shoulder_overlap = float(np.count_nonzero(editable & shoulder_zone) / max(1, editable_area))
    below_nape_skin = protected & head_foreground & ~semantic["hair"] & ~semantic["ears"] & (
        row_grid > top_y + max(2, int(h * 0.01))
    )
    protected_skin_below_nape = float(np.count_nonzero(below_nape_skin) / max(1, np.count_nonzero(protected)))
    failures = []
    if not np.count_nonzero(protected):
        failures.append("protected_head_empty")
    if not np.count_nonzero(editable):
        failures.append("editable_neck_empty")
    if not rear and not mediapipe_accepted:
        failures.append("face_landmarks_missing")
    if np.any(protected & editable):
        failures.append("protected_edit_overlap")
    crown_limit = int(ys.min() + max(1, (ys.max() - ys.min()) * 0.20))
    crown = (semantic["head"] | semantic["hair"]) & (row_grid <= crown_limit)
    if np.count_nonzero(crown) and np.count_nonzero(protected & crown) / np.count_nonzero(crown) < 0.95:
        failures.append("crown_not_protected")
    hair_containment = float(
        np.count_nonzero(protected & semantic["hair"]) / max(1, np.count_nonzero(semantic["hair"]))
    )
    if hair_containment < 0.95:
        failures.append("hair_not_protected")
    if editable_height < int(np.ceil(h * 0.08)):
        failures.append("editable_neck_too_short")
    if editable_area_ratio < 0.005 or editable_area_ratio > 0.08:
        failures.append("editable_neck_area_implausible")
    if cut_y <= top_y or cut_y > shoulder_y + int(np.ceil(h * 0.03)):
        failures.append("cut_line_implausible")
    if profile and not bool(neck_anchor["posterior_ok"]):
        failures.append("profile_neck_not_posterior")
    if profile and neck_overlap < 0.10:
        failures.append("profile_neck_anchor_missed")
    if rear and abs(center_x - head_center) > center_tolerance:
        failures.append("rear_neck_off_axis")
    if rear and protected_skin_below_nape >= 0.01:
        failures.append("rear_skin_below_nape_protected")
    if shoulder_overlap >= 0.05:
        failures.append("shoulder_contamination")
    return mask, {
        "confidence_score": round(float(score), 5),
        "geometry_strategy": strategy,
        "mediapipe_accepted": mediapipe_accepted,
        "mediapipe_rejection_reason": None if mediapipe_accepted else "rear_view" if rear else "missing_or_implausible",
        "components": {
            "semantic_agreement": round(semantic_agreement, 5),
            "face_or_silhouette_containment": round(face_containment, 5),
            "neck_geometry": round(geometry_score, 5),
            "topology": round(topology_score, 5),
        },
        "validation_failures": failures,
        "geometry": {
            "center_x": center_x,
            "target_center_x": target_center_x,
            "nape_anchor": {key: value for key, value in neck_anchor.items()},
            "top_y": top_y,
            "cut_y": cut_y,
            "shoulder_line": shoulder_y,
            "body_neck_geometry": body_geometry,
            "editable_width_top": top_half * 2,
            "editable_width_bottom": bottom_half * 2,
            "editable_height": editable_height,
            "editable_area_ratio": round(editable_area_ratio, 5),
            "neck_anchor_overlap": round(neck_overlap, 5),
            "shoulder_overlap": round(shoulder_overlap, 5),
            "protected_skin_below_nape": round(protected_skin_below_nape, 5),
            "hair_containment": round(hair_containment, 5),
        },
    }


def compile_head_fitment_mask_workflow(
    *,
    head_input: str,
    body_input: str,
    birefnet_model: str,
    mediapipe_model: str,
    sam_checkpoint: str,
    attempts: int,
    output_prefix: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    workflow: dict[str, Any] = {
        "1": {"class_type": "LoadImage", "inputs": {"image": head_input}},
        "2": {"class_type": "LoadImage", "inputs": {"image": body_input}},
        "3": {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": birefnet_model}},
        "4": {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["3", 0], "image": ["1", 0]}},
        "5": {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["3", 0], "image": ["2", 0]}},
        "6": {"class_type": "LoadMediaPipeFaceLandmarker", "inputs": {"model_name": mediapipe_model}},
        "7": {"class_type": "MediaPipeFaceLandmarker", "inputs": {
            "face_detection_model": ["6", 0], "image": ["1", 0], "detector_variant": "both",
            "num_faces": 1, "min_confidence": 0.35, "missing_frame_fallback": "empty",
        }},
        "8": {"class_type": "MediaPipeFaceMask", "inputs": {"face_landmarks": ["7", 0], "regions": "all"}},
        "9": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": sam_checkpoint}},
    }
    outputs: dict[str, str] = {}
    next_id = 20
    base_masks = {"biref_head": ["4", 0], "biref_body": ["5", 0], "face_oval": ["8", 0]}
    for name, source in base_masks.items():
        image_id, save_id = str(next_id), str(next_id + 1)
        next_id += 2
        workflow[image_id] = {"class_type": "MaskToImage", "inputs": {"mask": source}}
        workflow[save_id] = {"class_type": "SaveImage", "inputs": {"filename_prefix": f"{output_prefix}/{name}", "images": [image_id, 0]}}
        outputs[name] = name
    for attempt_index, variant in enumerate(SAM_VARIANTS[:attempts], start=1):
        for region in ("head", "hair", "ears", "neck"):
            text_id, detect_id, image_id, save_id = (str(next_id + offset) for offset in range(4))
            next_id += 4
            workflow[text_id] = {"class_type": "CLIPTextEncode", "inputs": {"text": variant[region], "clip": ["9", 1]}}
            workflow[detect_id] = {"class_type": "SAM3_Detect", "inputs": {
                "model": ["9", 0], "image": ["1", 0], "conditioning": [text_id, 0],
                "threshold": variant["threshold"], "refine_iterations": variant["refine"], "individual_masks": False,
            }}
            workflow[image_id] = {"class_type": "MaskToImage", "inputs": {"mask": [detect_id, 0]}}
            name = f"sam_{attempt_index}_{region}"
            workflow[save_id] = {"class_type": "SaveImage", "inputs": {"filename_prefix": f"{output_prefix}/{name}", "images": [image_id, 0]}}
            outputs[name] = name
    return workflow, outputs


class HeadFitmentMaskGenerationService:
    REQUIRED_NODES = {
        "LoadImage", "LoadBackgroundRemovalModel", "RemoveBackground", "LoadMediaPipeFaceLandmarker",
        "MediaPipeFaceLandmarker", "MediaPipeFaceMask", "CheckpointLoaderSimple", "CLIPTextEncode",
        "SAM3_Detect", "MaskToImage", "SaveImage",
    }

    @staticmethod
    def _find_output(paths: list[Path], token: str) -> Path:
        matches = [path for path in paths if token.lower() in path.stem.lower()]
        if not matches:
            raise HeadFitmentMaskGenerationError(f"ComfyUI did not return required mask output: {token}")
        return matches[0]

    def generate(
        self,
        *,
        head_path: Path,
        body_path: Path,
        output_dir: Path,
        server_url: str,
        view: str,
        birefnet_model: str,
        mediapipe_model: str,
        sam_checkpoint: str,
        attempts: int = 3,
        poll_seconds: float = 1.0,
        timeout_seconds: float = 300.0,
    ) -> HeadFitmentMaskResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        available = list_comfyui_node_types(server_url)
        missing = sorted(self.REQUIRED_NODES - available)
        if missing:
            raise HeadFitmentMaskGenerationError("ComfyUI mask workflow requires unavailable nodes: " + ", ".join(missing))
        required_models = (
            ("LoadBackgroundRemovalModel", "bg_removal_name", birefnet_model),
            ("LoadMediaPipeFaceLandmarker", "model_name", mediapipe_model),
            ("CheckpointLoaderSimple", "ckpt_name", sam_checkpoint),
        )
        unavailable = [
            model for node, input_name, model in required_models
            if model not in comfyui_model_options(server_url, node, input_name)
        ]
        if unavailable:
            raise HeadFitmentMaskGenerationError("ComfyUI mask workflow models are unavailable: " + ", ".join(unavailable))
        model_inventory = {}
        invalid_hashes = []
        for _, _, model in required_models:
            requirement = MASK_MODEL_REQUIREMENTS.get(Path(model).name)
            if requirement is None:
                invalid_hashes.append(f"{model} (no approved hash)")
                continue
            model_path, expected_hash = requirement
            actual_hash = _file_sha256(model_path) if model_path.is_file() else ""
            valid = actual_hash.lower() == expected_hash
            model_inventory[model] = {
                "location": str(model_path),
                "expected_sha256": expected_hash,
                "actual_sha256": actual_hash,
                "hash_valid": valid,
            }
            if not valid:
                invalid_hashes.append(model)
        if invalid_hashes:
            raise HeadFitmentMaskGenerationError(
                "ComfyUI mask workflow model hash validation failed: " + ", ".join(invalid_hashes)
            )
        requirements_path = output_dir / "Head_Fitment_Mask_Model_Requirements.json"
        requirements_path.write_text(
            json.dumps(
                {
                    "backend": "comfyui",
                    "required_nodes": sorted(self.REQUIRED_NODES),
                    "models": {
                        "birefnet": birefnet_model,
                        "mediapipe_face": mediapipe_model,
                        "sam": sam_checkpoint,
                    },
                    "inventory": model_inventory,
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        head_input = f"Zet/head-fitment-mask/{head_path.name}"
        body_input = f"Zet/head-fitment-mask/{body_path.name}"
        workflow, _ = compile_head_fitment_mask_workflow(
            head_input=head_input,
            body_input=body_input,
            birefnet_model=birefnet_model,
            mediapipe_model=mediapipe_model,
            sam_checkpoint=sam_checkpoint,
            attempts=max(1, min(3, attempts)),
            output_prefix="Zet/HeadFitmentMask",
        )
        workflow_path = output_dir / "Head_Fitment_Mask_Workflow_API.json"
        workflow_path.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")
        run = run_comfyui_workflow(
            workflow,
            server_url=server_url,
            output_dir=output_dir,
            reference_files=[
                {"path": str(head_path), "comfyui_input_name": head_input},
                {"path": str(body_path), "comfyui_input_name": body_input},
            ],
            poll_seconds=poll_seconds,
            timeout_seconds=timeout_seconds,
        )
        with Image.open(head_path) as source:
            size = source.size
            source_rgb = np.array(source.convert("RGB"))
            opencv_head = improved_foreground_mask(source)
        raw = {token: self._find_output(run.image_paths, token) for token in ("biref_head", "biref_body", "face_oval")}
        with Image.open(body_path) as body_source:
            opencv_body = improved_foreground_mask(body_source)
            raw_body_size = body_source.size
        raw_body_mask = _binary(raw["biref_body"], raw_body_size)
        body_geometry = analyze_body_neck_geometry(_merge_foregrounds(raw_body_mask, opencv_body))
        if opencv_body.shape != (size[1], size[0]):
            opencv_body = cv2.resize(opencv_body.astype(np.uint8), size, interpolation=cv2.INTER_NEAREST) > 0
        head_fg = _merge_foregrounds(_binary(raw["biref_head"], size), opencv_head)
        body_fg = _merge_foregrounds(_binary(raw["biref_body"], size), opencv_body)
        face = _binary(raw["face_oval"], size)
        opencv_head_path = output_dir / "Head_Fitment_OpenCV_Head.png"
        opencv_body_path = output_dir / "Head_Fitment_OpenCV_Body.png"
        _mask_image(opencv_head, opencv_head_path)
        _mask_image(opencv_body, opencv_body_path)
        candidates = []
        for attempt in range(1, max(1, min(3, attempts)) + 1):
            semantic = {
                region: _binary(self._find_output(run.image_paths, f"sam_{attempt}_{region}"), size)
                for region in ("head", "hair", "ears", "neck")
            }
            mask, report = compose_semantic_mask(
                head_foreground=head_fg,
                body_foreground=body_fg,
                face_oval=face,
                semantic=semantic,
                view=view,
                body_geometry=body_geometry,
            )
            report["attempt"] = attempt
            candidates.append((report["confidence_score"], mask, report))
        _, selected, selected_report = max(candidates, key=lambda item: item[0])
        report = dict(selected_report)
        mask_path = output_dir / "Head_Fitment_Edit_Mask.png"
        Image.fromarray(selected, "L").save(mask_path)
        report["generation_method"] = "comfyui_ensemble"
        report["backend"] = "comfyui"
        report["workflow_kind"] = "head_fitment_mask_ensemble"
        report["view"] = view
        report["attempts"] = [item[2] for item in candidates]
        report_path = output_dir / "Head_Fitment_Mask_Score.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        overlay = source_rgb.astype(np.float32)
        colors = np.zeros_like(overlay)
        colors[selected == MASK_REMOVE] = (220, 70, 65)
        colors[selected == MASK_EDIT] = (230, 155, 35)
        colors[selected == MASK_PROTECT] = (150, 205, 145)
        overlay = (overlay * 0.58 + colors * 0.42).astype(np.uint8)
        overlay_path = output_dir / "Head_Fitment_Mask_Overlay.png"
        Image.fromarray(overlay, "RGB").save(overlay_path)
        artifacts = [
            *run.image_paths,
            opencv_head_path,
            opencv_body_path,
            mask_path,
            report_path,
            overlay_path,
            workflow_path,
            requirements_path,
        ]
        return HeadFitmentMaskResult(mask_path, report_path, overlay_path, workflow_path, artifacts, run.prompt_id)
