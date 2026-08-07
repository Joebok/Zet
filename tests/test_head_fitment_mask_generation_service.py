from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from zet.services.head_fitment_mask_generation_service import (
    MASK_EDIT,
    MASK_PROTECT,
    compile_head_fitment_mask_workflow,
    compose_semantic_mask,
    improved_foreground_mask,
)


def test_improved_foreground_allows_hair_to_touch_canvas_border() -> None:
    image = Image.new("RGB", (96, 120), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((20, -8, 76, 80), fill=(80, 70, 65))
    draw.rectangle((40, 65, 56, 110), fill=(100, 80, 70))

    foreground = improved_foreground_mask(image)

    assert foreground[0, 48]
    assert not foreground[0, 0]


def test_semantic_composition_can_expand_editable_neck_outside_source_silhouette() -> None:
    h, w = 120, 96
    head = np.zeros((h, w), bool)
    cv2.ellipse(head.astype(np.uint8), (48, 42), (30, 38), 0, 0, 360, 1, -1)
    head[4:82, 18:79] = True
    head[70:112, 44:53] = True
    body = np.zeros((h, w), bool)
    body[5:35, 27:69] = True
    body[32:72, 42:55] = True
    body[70:115, 20:77] = True
    face = np.zeros((h, w), bool)
    face[25:68, 32:65] = True
    semantic = {name: np.zeros((h, w), bool) for name in ("head", "hair", "ears", "neck")}
    semantic["head"][10:76, 21:76] = True
    semantic["hair"][2:58, 16:81] = True
    semantic["ears"][36:55, 10:87] = True
    semantic["neck"][66:105, 38:59] = True

    mask, report = compose_semantic_mask(
        head_foreground=head,
        body_foreground=body,
        face_oval=face,
        semantic=semantic,
        view="Front-Right-3-4",
        body_geometry={"center_x_ratio": 0.5, "neck_width_to_head_ratio": 0.20, "neck_length_ratio": 0.12},
    )

    assert np.any(mask == MASK_PROTECT)
    assert np.any(mask == MASK_EDIT)
    assert np.any((mask == MASK_EDIT) & ~head)


def test_comfyui_workflow_contains_full_ensemble_and_named_outputs() -> None:
    workflow, outputs = compile_head_fitment_mask_workflow(
        head_input="head.png",
        body_input="body.png",
        birefnet_model="birefnet.safetensors",
        mediapipe_model="mediapipe_face_fp32.safetensors",
        sam_checkpoint="sam3.1_multiplex_fp16.safetensors",
        attempts=3,
        output_prefix="Zet/Test",
    )

    node_types = {node["class_type"] for node in workflow.values()}
    assert {"RemoveBackground", "MediaPipeFaceLandmarker", "SAM3_Detect", "SaveImage"} <= node_types
    assert len([node for node in workflow.values() if node["class_type"] == "SAM3_Detect"]) == 12
    assert {"biref_head", "biref_body", "face_oval", "sam_3_neck"} <= set(outputs)


def test_rear_view_uses_silhouette_when_face_landmarks_are_missing() -> None:
    h, w = 100, 80
    foreground = np.zeros((h, w), bool)
    foreground[5:72, 15:66] = True
    body = np.zeros((h, w), bool)
    body[4:35, 20:61] = True
    body[35:95, 10:71] = True
    semantic = {name: np.zeros((h, w), bool) for name in ("head", "hair", "ears", "neck")}
    semantic["head"][10:65, 20:61] = True
    semantic["hair"][4:70, 14:67] = True
    semantic["neck"][62:90, 32:49] = True

    false_face = np.zeros((h, w), bool)
    false_face[35:60, 25:55] = True
    _, rear_report = compose_semantic_mask(
        head_foreground=foreground,
        body_foreground=body,
        face_oval=false_face,
        semantic=semantic,
        view="Back-Right-3-4",
        body_geometry={"center_x_ratio": 0.5, "neck_width_to_head_ratio": 0.20, "neck_length_ratio": 0.12},
    )
    _, front_report = compose_semantic_mask(
        head_foreground=foreground,
        body_foreground=body,
        face_oval=np.zeros((h, w), bool),
        semantic=semantic,
        view="Front-Right-3-4",
        body_geometry={"center_x_ratio": 0.5, "neck_width_to_head_ratio": 0.20, "neck_length_ratio": 0.12},
    )

    assert "face_landmarks_missing" not in rear_report["validation_failures"]
    assert rear_report["geometry_strategy"] == "rear_nape"
    assert not rear_report["mediapipe_accepted"]
    assert "face_landmarks_missing" in front_report["validation_failures"]


def test_profile_neck_anchor_is_mirrored_to_posterior_side() -> None:
    h, w = 120, 100
    body = np.zeros((h, w), bool)
    foreground = np.zeros((h, w), bool)
    foreground[5:105, 10:90] = True
    body_geometry = {"center_x_ratio": 0.5, "neck_width_to_head_ratio": 0.22, "neck_length_ratio": 0.12}

    def report(view: str, face_slice: slice, neck_slice: slice):
        face = np.zeros((h, w), bool)
        face[25:75, face_slice] = True
        semantic = {name: np.zeros((h, w), bool) for name in ("head", "hair", "ears", "neck")}
        semantic["head"][10:82, 12:88] = True
        semantic["hair"][4:65, 10:90] = True
        semantic["neck"][70:112, neck_slice] = True
        return compose_semantic_mask(
            head_foreground=foreground, body_foreground=body, face_oval=face,
            semantic=semantic, view=view, body_geometry=body_geometry,
        )[1]

    left = report("Left-Profile", slice(20, 48), slice(48, 70))
    right = report("Right-Profile", slice(52, 80), slice(30, 52))
    assert left["geometry"]["nape_anchor"]["center_x"] > left["geometry"]["nape_anchor"]["face_center_x"]
    assert right["geometry"]["nape_anchor"]["center_x"] < right["geometry"]["nape_anchor"]["face_center_x"]
    assert "profile_neck_not_posterior" not in left["validation_failures"]
    assert "profile_neck_not_posterior" not in right["validation_failures"]
