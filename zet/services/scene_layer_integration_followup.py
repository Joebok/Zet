"""Isolated follow-up for repairing explicit scene layer integration."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import numpy as np
import cv2
from PIL import Image, ImageChops, ImageDraw

from zet.services.scene_assembly_experiment_service import (
    OUTPUT_ROOT, SEEDS, _SCENES, _fit, _hash, _json, _load_image, _write_json,
)

PARENT_RUN = "13efb6d06b56cbe4"
RUBRIC_VERSION = "layer-followup-2026-10-07-v2"
PREP_CRITERIA = (
    "source_retention", "mask_correctness", "removable_background",
    "group_membership", "placement_and_contact", "dialogue_retention",
)
FINAL_CRITERIA = (
    "cast_and_identity", "pose_and_expression", "props_and_source_retention",
    "facing_and_gaze", "scale_depth_and_grounding", "background_continuity",
    "dialogue", "integration_quality", "narrative_readability", "authored_requirements",
)
RATINGS = {"pass", "fail", "unassessable"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _mask_digest(path: Path) -> str:
    return _hash(path)


def _paper_mask_full(image: Image.Image, tolerance: int = 48) -> np.ndarray:
    """Keep every non-paper component in the original full source coordinates."""
    rgba = np.asarray(image.convert("RGBA"))
    rgb = rgba[:, :, :3].astype(np.int16)
    near_paper = (rgb.min(axis=2) >= 188) & ((rgb.max(axis=2) - rgb.min(axis=2)) <= tolerance)
    count, components = cv2.connectedComponents(near_paper.astype(np.uint8), connectivity=4)
    edge = set(components[0, :]) | set(components[-1, :]) | set(components[:, 0]) | set(components[:, -1])
    edge.discard(0)
    paper = np.isin(components, list(edge)) if count else np.zeros(near_paper.shape, dtype=bool)
    keep = ~paper
    return cv2.dilate(keep.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=1) > 0


def _parent_alpha_mask_full(source_size: tuple[int, int], cutout: Image.Image,
                            source_bbox: tuple[int, int, int, int]) -> np.ndarray:
    """Map an existing reviewed cutout alpha into frozen source coordinates."""
    x0, y0, x1, y1 = source_bbox
    width, height = source_size
    expected = (x1 - x0, y1 - y0)
    if x0 < 0 or y0 < 0 or x1 > width or y1 > height or cutout.size != expected:
        raise ValueError(f"Parent cutout frame {cutout.size}/{source_bbox} does not fit frozen source {source_size}")
    result = np.zeros((height, width), dtype=bool)
    alpha = np.asarray(cutout.convert("RGBA").getchannel("A"))
    result[y0:y1, x0:x1] = alpha > 0
    return result


def _source_ground_removal(scene: str, layer: str, size: tuple[int, int]) -> np.ndarray:
    """Trim retained source floor outside visible feet, bodies, and props."""
    width, height = size
    remove = np.zeros((height, width), dtype=bool)
    allowed = np.zeros((height, width), dtype=np.uint8)
    if scene == "Chapter-01-Standing-in-Wonder" and layer == "group":
        floor_y = 690
        polygons = [
            # First schoolboy's trouser legs and shoes.
            [(232, 448), (316, 441), (342, 500), (331, 572), (307, 652),
             (284, 758), (267, 803), (227, 800), (212, 762), (230, 684), (241, 592)],
            [(323, 458), (411, 450), (447, 498), (451, 565), (431, 632),
             (431, 758), (412, 793), (370, 784), (355, 733), (370, 640), (359, 568)],
            # Second schoolboy's separated legs and shoes.
            [(452, 498), (525, 501), (553, 566), (537, 655), (500, 750),
             (474, 796), (432, 782), (443, 723), (465, 640), (466, 565)],
            [(558, 477), (658, 477), (699, 529), (713, 610), (687, 700),
             (671, 770), (634, 789), (601, 756), (620, 667), (624, 590)],
            # Kaeldor's trousers, crossed legs, and both shoes.
            [(828, 392), (996, 398), (1025, 450), (1010, 553), (1006, 633),
             (983, 718), (977, 763), (941, 793), (898, 781), (874, 748),
             (858, 682), (843, 612), (834, 535)],
            [(183, 792), (250, 789), (280, 813), (272, 862), (192, 869)],
            [(395, 778), (467, 780), (518, 812), (518, 853), (405, 868)],
            [(604, 780), (666, 781), (711, 802), (719, 830), (693, 844), (625, 836), (607, 816)],
            [(870, 738), (935, 741), (961, 779), (948, 819), (879, 817)],
            [(966, 680), (1005, 673), (1022, 690), (1018, 728), (995, 747), (973, 731)],
        ]
    elif scene == "Chapter-03-Collision" and layer == "group":
        floor_y = 1000
        polygons = [
            [(12, 1005), (121, 1001), (158, 1026), (153, 1071), (28, 1068)],
            [(187, 996), (267, 996), (298, 1027), (283, 1084), (198, 1090)],
            [(301, 937), (393, 941), (423, 980), (412, 1033), (310, 1027)],
            [(438, 950), (509, 960), (558, 1020), (584, 1076), (572, 1125), (466, 1148)],
        ]
    elif scene == "Chapter-03-Collision" and layer == "pair":
        floor_y = 805
        polygons = [
            # Seated figure's skirt hem; keep footwear separately below.
            [(75, 810), (118, 744), (194, 752), (226, 813), (281, 833), (299, 791),
             (352, 748), (471, 739), (531, 781), (557, 818), (553, 866), (535, 921),
             (505, 978), (459, 1021), (407, 1058), (345, 1052), (277, 1036),
             (218, 1012), (165, 989), (118, 957), (90, 919)],
            # Valindia's separate lower legs and boots.
            [(577, 565), (620, 552), (649, 585), (647, 725), (653, 790),
             (649, 862), (662, 914), (644, 954), (606, 961), (581, 932),
             (578, 865), (572, 804), (575, 720)],
            [(638, 564), (674, 594), (691, 658), (700, 742), (729, 788),
             (765, 827), (768, 867), (756, 910), (738, 952), (700, 960),
             (674, 934), (668, 884), (655, 837), (641, 723)],
            # Tsaeytte's socks and two boots, kept below the skirt edge.
            [(421, 918), (472, 913), (521, 951), (558, 1007), (624, 1054),
             (649, 1081), (636, 1110), (568, 1103), (511, 1070), (466, 1038), (438, 985)],
            [(593, 913), (653, 906), (706, 927), (758, 970), (800, 1011),
             (804, 1046), (777, 1082), (716, 1092), (671, 1065), (638, 1019), (612, 974)],
            # Five books, kept as separate source components.
            [(0, 862), (143, 862), (180, 889), (180, 923), (0, 916)],
            [(0, 928), (160, 931), (166, 963), (88, 995), (0, 992)],
            [(12, 1004), (143, 999), (192, 1068), (179, 1139), (24, 1129)],
            [(267, 1081), (444, 1054), (496, 1081), (486, 1120), (373, 1151), (282, 1147)],
            [(749, 874), (919, 878), (921, 952), (892, 982), (768, 976)],
        ]
    else:
        return remove
    # Fill each keep region independently. Passing overlapping contours as one
    # fillPoly call applies even-odd contour semantics and can cut accidental
    # holes through shoes and books where the polygons overlap.
    for polygon in polygons:
        cv2.fillPoly(allowed, [np.asarray(polygon, dtype=np.int32)], 1)
    floor = np.zeros((height, width), dtype=bool)
    floor[max(0, floor_y):, :] = True
    if scene == "Chapter-03-Collision" and layer == "pair":
        # Clear the source floor outside the same tight silhouettes used to
        # restore the hem, footwear, and books; broad legacy keep regions cannot
        # carry a rectangular floor slab over.
        return floor & ~_source_restore_mask(scene, layer, size)
    return floor & (allowed == 0)


def _source_restore_mask(scene: str, layer: str, size: tuple[int, int]) -> np.ndarray:
    """Restore source-visible subject pixels omitted by the initial extraction."""
    width, height = size
    keep = np.zeros((height, width), dtype=np.uint8)
    if scene == "Chapter-01-Standing-in-Wonder" and layer == "group":
        # The contact trim intersects five distinct shoe regions in the accepted
        # group. Restore shoe pixels after background removal has been applied.
        polygons = [
            [(183, 797), (251, 793), (273, 815), (269, 858), (249, 870), (194, 866), (183, 843)],
            [(391, 784), (448, 785), (474, 806), (488, 832), (475, 858), (414, 868), (394, 847)],
            [(604, 780), (666, 781), (711, 802), (719, 830), (693, 844), (625, 836), (607, 816)],
            [(866, 766), (917, 761), (950, 781), (957, 811), (938, 824), (881, 818)],
            [(966, 680), (1005, 673), (1022, 690), (1018, 728), (995, 747), (973, 731)],
        ]
        for polygon in polygons:
            cv2.fillPoly(keep, [np.asarray(polygon, dtype=np.int32)], 1)
    elif scene == "Chapter-03-Collision" and layer == "pair":
        # Restore the skirt hem, lower legs, footwear, and five books after
        # clearing the source floor band.
        polygons = [
            [(123, 843), (139, 809), (179, 785), (225, 770), (286, 765), (345, 775),
             (407, 793), (464, 822), (516, 855), (548, 882), (558, 914), (548, 947),
             (520, 978), (485, 1005), (447, 1032), (411, 1052), (375, 1053),
             (335, 1040), (294, 1031), (253, 1015), (214, 995), (178, 971),
             (148, 945), (128, 910)],
            [(499, 987), (520, 963), (550, 959), (582, 980), (612, 1008),
             (646, 1033), (675, 1062), (681, 1085), (660, 1108), (630, 1121),
             (598, 1115), (569, 1094), (542, 1064), (518, 1032)],
            [(632, 969), (654, 948), (685, 950), (715, 967), (744, 989),
             (768, 1014), (770, 1044), (752, 1072), (724, 1092), (693, 1095),
             (667, 1077), (648, 1046), (638, 1013)],
            [(582, 762), (608, 759), (633, 774), (646, 807), (648, 856),
             (655, 899), (650, 929), (633, 951), (609, 952), (592, 934),
             (586, 901), (580, 856), (577, 812)],
            [(658, 768), (681, 774), (701, 802), (714, 836), (738, 864),
             (766, 891), (767, 920), (752, 946), (729, 961), (703, 955),
             (686, 934), (674, 902), (665, 861)],
            [(26, 868), (135, 870), (157, 885), (157, 912), (143, 926), (29, 922)],
            [(0, 938), (153, 939), (178, 954), (176, 978), (152, 997), (0, 993)],
            [(10, 1007), (148, 1006), (182, 1035), (188, 1088), (174, 1111),
             (19, 1108), (4, 1084)],
            [(256, 1064), (426, 1056), (462, 1073), (458, 1117), (434, 1142),
             (273, 1149), (255, 1129)],
            [(737, 968), (766, 953), (909, 973), (921, 994), (892, 1018),
             (746, 997), (735, 980)],
        ]
        for polygon in polygons:
            cv2.fillPoly(keep, [np.asarray(polygon, dtype=np.int32)], 1)
        keep = cv2.dilate(keep, np.ones((7, 7), np.uint8), iterations=1)
    elif scene == "Chapter-02-At-the-Arch" and layer == "Tsaeytte":
        # The full-body source has both boots and socks in this lower ROI; the
        # initial GrabCut consistently classified these ground-adjacent pixels
        # as background. Keep the two visible leg/boot silhouettes separately.
        polygons = [
            [(1010, 646), (1026, 643), (1038, 651), (1044, 673), (1052, 698),
             (1048, 726), (1041, 752), (1037, height-1), (989, height-1),
             (984, 744), (995, 713), (1003, 689), (1011, 675)],
            [(1042, 646), (1065, 646), (1080, 654), (1092, 676), (1112, 703),
             (1125, 731), (1132, 754), (1135, height-1), (1050, height-1),
             (1048, 736), (1042, 710), (1037, 684)],
        ]
        cv2.fillPoly(keep, [np.asarray(p, dtype=np.int32) for p in polygons], 1)
    return keep.astype(bool)


def _source_shadow_removal(scene: str, layer: str, image: Image.Image) -> np.ndarray:
    """Remove pale baked-in floor shadows below the Chapter 02 group."""
    width, height = image.size
    remove = np.zeros((height, width), dtype=bool)
    if scene != "Chapter-02-At-the-Arch" or layer != "group":
        return remove
    rgb = np.asarray(image.convert("RGB"), dtype=np.int16)
    y = np.arange(height)[:, None]
    low_saturation = rgb.max(axis=2) - rgb.min(axis=2) <= 56
    light_floor = rgb.mean(axis=2) >= 132
    # The source backdrop is white, with light grey cast shadows beneath the
    # boys. Their trousers and leather shoes remain below this brightness.
    remove = (y >= round(height * 0.84)) & low_saturation & light_floor
    return remove


def _source_subject_footprint(scene: str, layer: str, size: tuple[int, int]) -> np.ndarray:
    """Conservative full-source subject envelopes that exclude baked-in scenery."""
    width, height = size
    polygons: list[list[tuple[int, int]]] = []
    if scene == "Chapter-01-Standing-in-Wonder" and layer == "group":
        # The accepted source contains the arch and path behind the boys and
        # Kaeldor. These three outer contours preserve the joined group while
        # excluding that baked-in scenery from the extracted layer.
        polygons = [
            [(211, 93), (240, 58), (284, 39), (330, 47), (374, 72), (416, 116),
             (438, 167), (449, 222), (473, 297), (468, 394), (481, 466), (461, 532),
             (453, 606), (466, 703), (481, 782), (469, 835), (441, 866), (401, 870),
             (361, 855), (326, 867), (280, 855), (233, 842), (195, 823), (187, 792),
             (210, 729), (230, 660), (242, 584), (240, 502), (230, 426), (227, 337),
             (213, 264), (211, 184)],
            [(405, 166), (424, 131), (456, 111), (500, 104), (544, 121), (579, 158),
             (615, 201), (658, 220), (691, 207), (721, 213), (742, 242), (750, 287),
             (739, 352), (732, 396), (744, 433), (742, 472), (718, 507), (688, 531),
             (680, 570), (702, 626), (721, 694), (730, 760), (721, 808), (691, 843),
             (652, 863), (606, 857), (568, 871), (523, 860), (481, 844), (455, 813),
             (451, 779), (472, 714), (492, 650), (509, 585), (493, 550), (461, 532),
             (432, 507), (404, 476), (390, 440), (389, 397), (406, 344), (414, 285),
             (405, 231)],
            [(836, 0), (893, 0), (932, 0), (968, 18), (1003, 48), (1026, 91),
             (1042, 137), (1044, 179), (1051, 218), (1063, 249), (1070, 285),
             (1065, 324), (1055, 360), (1049, 397), (1038, 428), (1030, 470),
             (1029, 528), (1022, 590), (1010, 639), (993, 687), (983, 730),
             (981, 763), (964, 793), (945, 812), (920, 822), (898, 815), (880, 801),
             (870, 776), (866, 744), (852, 714), (841, 683), (836, 634), (829, 580),
             (824, 526), (812, 466), (795, 417), (775, 369), (748, 325), (709, 283),
             (704, 266), (733, 243), (773, 249), (805, 255), (831, 238), (833, 181),
             (812, 120), (808, 71), (817, 30)],
        ]
    elif scene == "Chapter-02-At-the-Arch" and layer == "Valindia":
        # Clip the left foreground figure to her silhouette; the source scene
        # places her against stonework, hedge, and path in the same layer.
        polygons = [[(369, 85), (417, 64), (462, 74), (495, 109), (516, 150),
                     (510, 200), (522, 247), (537, 302), (539, 360), (532, 415),
                     (530, 486), (545, 548), (553, 618), (533, 676), (516, 723),
                     (492, height - 1), (350, height - 1), (324, 738), (322, 693),
                     (335, 642), (346, 584), (333, 535), (318, 492), (312, 439),
                     (325, 382), (331, 327), (334, 269), (339, 209), (340, 151)]]
    elif scene == "Chapter-02-At-the-Arch" and layer == "Tsaeytte":
        # Remove hedge/wall fragments retained beside the right foreground figure.
        polygons = [[(966, 92), (1006, 73), (1047, 82), (1081, 106), (1105, 145),
                     (1110, 185), (1132, 211), (1151, 244), (1150, 278), (1175, 298),
                     (1182, 345), (1175, 399), (1168, 460), (1170, 520), (1175, 563),
                     (1165, 588), (1148, 613), (1125, 640), (1121, 674), (1138, 707),
                     (1152, 741), (1146, height - 1),
                     (1035, height - 1), (1015, 735), (995, 686), (976, 640), (948, 602),
                     (920, 565), (903, 527), (909, 482), (920, 432), (916, 384),
                     (907, 338), (903, 294), (916, 260), (947, 228), (946, 183)]]
    elif scene == "Chapter-03-Collision" and layer == "pair":
        # Keep each member and all five disconnected books, trimming the broad
        # source floor band without separating the accepted pair.
        polygons = [
            [(112, 548), (115, 491), (144, 438), (195, 394), (251, 364), (305, 360),
             (352, 388), (384, 435), (411, 493), (442, 548), (477, 612), (501, 680),
             (513, 735), (548, 773), (598, 811), (643, 852), (681, 898), (704, 941),
             (696, 976), (670, 1003), (629, 1027), (583, 1048), (534, 1067),
             (480, 1081), (423, 1080), (373, 1064), (325, 1044), (282, 1029),
             (239, 1014), (199, 993), (160, 973), (122, 949), (91, 920), (73, 885),
             (78, 842), (88, 793), (94, 738), (82, 679), (84, 618)],
            [(545, 0), (600, 0), (648, 9), (683, 37), (708, 79), (720, 126),
             (712, 169), (697, 201), (711, 250), (725, 312), (733, 385), (730, 455),
             (713, 523), (701, 589), (697, 659), (705, 720), (725, 768), (749, 817),
             (760, 864), (753, 906), (732, 941), (703, 962), (673, 954), (650, 931),
             (634, 891), (619, 845), (600, 804), (578, 761), (556, 719), (534, 673),
             (516, 626), (515, 579), (522, 526), (517, 468), (510, 405), (502, 342),
             (504, 274), (508, 211), (510, 153), (523, 98), (532, 47)],
            [(21, 858), (159, 858), (179, 872), (181, 934), (161, 951), (25, 947)],
            [(0, 960), (173, 963), (188, 983), (177, 1069), (157, 1088), (0, 1081)],
            [(7, 1031), (163, 1034), (180, 1053), (177, 1147), (155, 1164), (15, 1153)],
            [(258, 1073), (470, 1057), (499, 1073), (497, 1126), (483, 1151), (276, 1151), (256, 1135)],
            [(744, 862), (919, 866), (927, 884), (922, 960), (904, 981), (758, 974), (741, 949)],
        ]
    else:
        return np.ones((height, width), dtype=bool)
    footprint = np.zeros((height, width), dtype=np.uint8)
    valid_polygons = []
    for polygon in polygons:
        points = np.asarray([(max(0, min(width - 1, x)), max(0, min(height - 1, y)))
                             for x, y in polygon], dtype=np.int32)
        valid_polygons.append(points)
    for polygon in valid_polygons:
        cv2.fillPoly(footprint, [polygon], 1)
    # A small guard band protects hair, clothing edges, shoes, and book corners
    # from coordinate rounding while still cutting away broad scene fragments.
    footprint = cv2.dilate(footprint, np.ones((9, 9), np.uint8), iterations=1)
    return footprint > 0


def _source_interior_background_removal(scene: str, layer: str, size: tuple[int, int]) -> np.ndarray:
    """Remove obvious source-scene gaps enclosed by broad accepted contours."""
    width, height = size
    remove = np.zeros((height, width), dtype=np.uint8)
    if scene == "Chapter-01-Standing-in-Wonder" and layer == "group":
        gaps = [
            # Pale arch visible between the first student's legs.
            [(295, 557), (344, 566), (374, 619), (377, 701), (352, 756), (324, 733), (314, 657)],
            # Background wedges between the second student's trouser legs.
            [(515, 533), (560, 541), (594, 602), (605, 686), (581, 755), (548, 768), (529, 707)],
        ]
    else:
        return remove.astype(bool)
    for polygon in gaps:
        cv2.fillPoly(remove, [np.asarray(polygon, dtype=np.int32)], 1)
    return remove > 0


def _grabcut_mask_full(image: Image.Image, roi: tuple[int, int, int, int]) -> np.ndarray:
    """GrabCut with a definite-background border around an authored full-image ROI."""
    rgba = np.asarray(image.convert("RGBA"))
    h, w = rgba.shape[:2]
    x, y, rw, rh = roi
    x, y = max(0, x), max(0, y)
    rw, rh = min(rw, w - x), min(rh, h - y)
    if rw < 8 or rh < 8:
        raise ValueError(f"Extraction rectangle falls outside {w}x{h}: {roi}")
    labels = np.full((h, w), cv2.GC_BGD, np.uint8)
    ring = max(4, min(rw, rh) // 40)
    labels[y + ring:y + rh - ring, x + ring:x + rw - ring] = cv2.GC_PR_FGD
    inset_x, inset_y = max(ring + 2, rw // 3), max(ring + 2, rh // 3)
    labels[y + inset_y:y + rh - inset_y, x + inset_x:x + rw - inset_x] = cv2.GC_FGD
    bgr = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2BGR)
    bg_model, fg_model = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(bgr, labels, None, bg_model, fg_model, 8, cv2.GC_INIT_WITH_MASK)
    mask = np.isin(labels, (cv2.GC_FGD, cv2.GC_PR_FGD))
    mask[:y, :] = False
    mask[y + rh:, :] = False
    mask[:, :x] = False
    mask[:, x + rw:] = False
    return cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)) > 0


class SceneLayerIntegrationFollowup:
    """Run state, artifact review and confirmed score persistence for the follow-up."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.parent_root = (OUTPUT_ROOT / PARENT_RUN).resolve()
        self.root = (OUTPUT_ROOT / run_id).resolve()
        if not self.root.is_relative_to(OUTPUT_ROOT.resolve()) or run_id == PARENT_RUN:
            raise ValueError("Follow-up output must be isolated from its parent run")

    def freeze(self) -> dict[str, Any]:
        """Copy parent evidence and create an immutable provenance inventory."""
        manifest_path = self.root / "manifest.json"
        if manifest_path.exists():
            raise ValueError("Follow-up inputs are already frozen")
        parent = _json(self.parent_root / "manifest.json")
        parent_eval = _json(self.parent_root / "evaluation.json")
        unblinding = _json(self.parent_root / "unblinding-key.json")
        snapshot = self.root / "parent-snapshot"
        snapshot.mkdir(parents=True, exist_ok=False)
        copied: list[dict[str, str]] = []
        # Preserve the entire frozen and prepared input set, C outputs, and review
        # evidence needed to explain the delta. The original run is read-only.
        names = ["manifest.json", "evaluation.json", "report.json", "report.md",
                 "review-scorecard.csv", "review-guide.md", "unblinding-key.json"]
        for name in names:
            src = self.parent_root / name
            if src.is_file():
                dst = snapshot / name
                shutil.copy2(src, dst)
                copied.append({"source": str(src), "snapshot": str(dst), "sha256": _hash(dst)})
        for slug in parent["scenes"]:
            src_scene = self.parent_root / slug
            dst_scene = snapshot / slug
            for folder in ("frozen", "prepared"):
                src = src_scene / folder
                if src.is_dir():
                    shutil.copytree(src, dst_scene / folder)
                    copied.extend({"source": str(f), "snapshot": str(dst_scene / folder / f.relative_to(src)),
                                   "sha256": _hash(dst_scene / folder / f.relative_to(src))}
                                  for f in src.rglob("*") if f.is_file())
            for seed in SEEDS:
                src = src_scene / "renders" / "C_layers" / str(seed)
                if src.is_dir():
                    dst = dst_scene / "renders" / "C_layers" / str(seed)
                    shutil.copytree(src, dst)
                    copied.extend({"source": str(f), "snapshot": str(dst / f.relative_to(src)),
                                   "sha256": _hash(dst / f.relative_to(src))}
                                  for f in src.rglob("*") if f.is_file())
        # Copy original independent human C ratings into a stable provenance file.
        baseline = {key: item for key, item in parent_eval["items"].items()
                    if item.get("arm") == "C_layers" or item.get("candidate_id", "").startswith("C_layers")}
        # Prior schema keys are opaque tokens; identify C records through the scorecard.
        if not baseline:
            baseline = {key: item for key, item in parent_eval["items"].items()
                        if item.get("variant") in {"native", "lettered"} and item.get("scene") in parent["scenes"]}
        _write_json(snapshot / "baseline-human-reviews.json", {"items": baseline})
        baseline_c_reviews = {}
        for token, item in parent_eval["items"].items():
            identity = f"{item['scene']}/{item['seed']}"
            if unblinding.get(identity, {}).get(token) == "C_layers":
                baseline_c_reviews[identity] = item
        _write_json(snapshot / "baseline-c-human-reviews.json", baseline_c_reviews)
        inventory = []
        for identity, item in baseline_c_reviews.items():
            slug, seed = identity.rsplit("/", 1)
            render = self.parent_root / slug / "renders" / "C_layers" / seed
            entry = {"scene": slug, "seed": int(seed), "origin": {}, "reasons": []}
            for criterion, rating in item.get("criteria", {}).items():
                if rating.get("result") == "fail":
                    reason = rating.get("reason", "")
                    entry["reasons"].append({"criterion": criterion, "reason": reason})
                    text = reason.casefold()
                    if any(word in text for word in ("duplicate", "stacked", "overlap", "merged", "missing hair", "missing boot")):
                        stage = "source_or_cutout" if "hair" in text or "boot" in text else "qwen_integration_or_layering"
                    elif any(word in text for word in ("floating", "ground", "contact", "scale", "depth", "foreground", "midground")):
                        stage = "placement_or_contact"
                    elif any(word in text for word in ("seam", "halo", "lighting", "shadow", "white gap", "blending")):
                        stage = "mask_or_qwen_integration"
                    else:
                        stage = "unresolved_requires_artifact_inspection"
                    entry["origin"].setdefault(stage, 0)
                    entry["origin"][stage] += 1
            entry["candidate_path"] = str(render / "result.json")
            inventory.append(entry)
        _write_json(snapshot / "defect-inventory.json", {
            "source": "completed human review of original C-layer outputs",
            "parent_run_id": PARENT_RUN, "items": inventory,
            "limitations": ["Origin categories are hypotheses until checked against raw composite, mask, proposal, and final output.",
                            "Accepted-source pose/content defects are recorded separately from later rendering defects."],
        })
        manifest = {
            "schema_version": 1, "run_id": self.run_id, "parent_run_id": PARENT_RUN,
            "created_at": _now(), "status": "FROZEN_PARENT",
            "parent_manifest_sha256": _hash(self.parent_root / "manifest.json"),
            "parent_evaluation_sha256": _hash(self.parent_root / "evaluation.json"),
            "snapshot_artifacts": copied, "scenes": {}, "seeds": list(SEEDS),
            "profile_settings": parent["profile_settings"],
            "rubric_version": RUBRIC_VERSION,
            "review_policy": "Luna proposes first; human confirmation/amendment required for effective ratings.",
        }
        for slug, state in parent["scenes"].items():
            manifest["scenes"][slug] = {
                "output_size": state["output_size"], "members": state["members"],
                "requirements": state["requirements"], "dialogue": state["dialogue"],
                "sources": state["sources"], "shared_references": state["shared_references"],
                "parent_layout": state["shot"],
                "parent_prepared_hashes": state.get("prepared_hashes", {}),
                "baseline_outputs": {}, "baseline_review_keys": {},
                "prep_review": {"status": "PENDING", "luna": None, "human": None},
                "final_reviews": {},
            }
            for seed in SEEDS:
                base_dir = snapshot / slug / "renders" / "C_layers" / str(seed)
                res_path = base_dir / "result.json"
                result = _json(res_path) if res_path.is_file() else {}
                output_name = Path(result.get("output") or result.get("output_path") or "").name
                img = base_dir / output_name if output_name else Path()
                if not img.is_file():
                    for guess in (base_dir / "integrated.png", base_dir / "result.png", base_dir / "output.png"):
                        if guess.is_file():
                            img = guess
                            break
                manifest["scenes"][slug]["baseline_outputs"][str(seed)] = {
                    "path": str(img), "sha256": _hash(img) if img.is_file() else None,
                    "result": str(res_path) if res_path.is_file() else None,
                }
        _write_json(manifest_path, manifest)
        return manifest

    def _manifest(self) -> dict[str, Any]:
        path = self.root / "manifest.json"
        if not path.is_file():
            raise ValueError("Run freeze before follow-up commands")
        manifest = _json(path)
        if manifest["parent_manifest_sha256"] != _hash(self.parent_root / "manifest.json"):
            raise ValueError("Parent run manifest changed after follow-up freeze")
        return manifest

    def verify_frozen_snapshot(self) -> None:
        """Refuse to work from altered copies or a changed parent artifact."""
        manifest = self._manifest()
        for item in manifest["snapshot_artifacts"]:
            source, snapshot = Path(item["source"]), Path(item["snapshot"])
            if not snapshot.is_file() or _hash(snapshot) != item["sha256"]:
                raise ValueError(f"Frozen parent snapshot changed or is missing: {snapshot}")
            if not source.is_file() or _hash(source) != item["sha256"]:
                raise ValueError(f"Parent artifact changed after follow-up freeze: {source}")

    def prepare(self) -> dict[str, Any]:
        """Rebuild cutouts from frozen source assets and emit reviewable bundles.

        Masks are full source-coordinate PNGs. Current old cutout alpha is retained
        as a starting annotation; explicit repairs are stored as separate source
        keep/remove overlays and are always reviewable before approval.
        """
        self.verify_frozen_snapshot()
        manifest = self._manifest()
        for slug, spec in _SCENES.items():
            state = manifest["scenes"][slug]
            prior_review = state.get("prep_review", {})
            scene = self.root / slug
            prep = scene / "prepared-v2"
            prep.mkdir(parents=True, exist_ok=True)
            shot = state["parent_layout"]
            layers = []
            canvas_size = tuple(state["output_size"])
            background = _load_image(self.root / "parent-snapshot" / slug / "prepared" / "background.png")
            background = background.resize(canvas_size, Image.Resampling.LANCZOS)
            bg_path = prep / "background.png"
            background.save(bg_path)
            composite = background.copy()
            protected = Image.new("L", canvas_size, 0)
            dialogue_protected = Image.new("L", canvas_size, 0)
            repairable = Image.new("L", canvas_size, 0)
            contact_regions = Image.new("L", canvas_size, 0)
            for old_layer in shot["layers"]:
                old_layer = dict(old_layer)
                if slug == "Chapter-02-At-the-Arch" and old_layer["key"] == "group":
                    old_layer["parent_box"] = list(old_layer["box"])
                    old_layer["box"] = [0.40, 0.29, 0.31, 0.67]
                    old_layer["layout_change_reason"] = "Lower the accepted middle-distance group toward the road plane while retaining its size and internal pose."
                key = old_layer["key"]
                if key in {"group", "pair"}:
                    source_name = key
                    source_path = (self.root / "parent-snapshot" / slug / "frozen" / "source_images" /
                                   Path(state["sources"][source_name]["frozen_path"]).name)
                    source_image = _load_image(source_path)
                    full_mask = _paper_mask_full(source_image)
                    # Reuse the accepted parent's reviewed alpha as a geometric
                    # seed for sources whose pixel frame is unchanged. RGB always
                    # comes from the frozen source; this only removes source scenery.
                    if ((slug == "Chapter-01-Standing-in-Wonder" and key == "group") or
                            (slug == "Chapter-03-Collision" and key == "pair")):
                        parent_cutout = _load_image(self.root / "parent-snapshot" / slug / "prepared" / f"{key}.png")
                        frame = tuple(old_layer.get("bbox") or (0, 0, *parent_cutout.size))
                        full_mask &= _parent_alpha_mask_full(source_image.size, parent_cutout, frame)
                elif key.startswith("dialogue-"):
                    source_name = "main"
                    source_path = (self.root / "parent-snapshot" / slug / "frozen" / "source_images" /
                                   Path(state["sources"]["main"]["frozen_path"]).name)
                    source_image = _load_image(source_path)
                    dialogue_index = int(key.split("-")[1]) - 1
                    roi = tuple(_SCENES[slug]["dialogue_extract"][dialogue_index])
                    full_mask = _grabcut_mask_full(source_image, roi)
                else:
                    source_name = "main"
                    source_path = (self.root / "parent-snapshot" / slug / "frozen" / "source_images" /
                                   Path(state["sources"]["main"]["frozen_path"]).name)
                    source_image = _load_image(source_path)
                    roi = tuple(_SCENES[slug]["extract"][key])
                    if slug == "Chapter-02-At-the-Arch" and key in {"Valindia", "Tsaeytte"}:
                        roi = (roi[0], roi[1], roi[2], source_image.height - roi[1])
                    if slug == "Chapter-01-Standing-in-Wonder" and key == "Tsaeytte":
                        roi = (roi[0], roi[1], roi[2], source_image.height - roi[1])
                    full_mask = _grabcut_mask_full(source_image, roi)
                # Preserve the original extraction frame while applying human
                # brush corrections. This keeps the frozen scale/placement
                # stable even when a mask edge changes.
                extraction_bbox = Image.fromarray(full_mask.astype(np.uint8) * 255, "L").getbbox()
                if extraction_bbox is None:
                    raise ValueError(f"{slug}/{key}: extraction removed all source pixels")
                source_root = prep / "annotations" / key
                source_root.mkdir(parents=True, exist_ok=True)
                automatic_remove = _source_ground_removal(slug, key, source_image.size)
                automatic_remove |= _source_shadow_removal(slug, key, source_image)
                automatic_keep = _source_restore_mask(slug, key, source_image.size)
                footprint = _source_subject_footprint(slug, key, source_image.size)
                if not (slug == "Chapter-03-Collision" and key == "pair"):
                    automatic_remove |= ~footprint & ~automatic_keep
                full_mask[automatic_remove] = False
                # Explicit subject restoration takes precedence over automatic
                # source-background trims; manual keep/remove decisions remain
                # separately applied below.
                full_mask[automatic_keep] = True
                automatic_remove_path = source_root / "automatic-ground-remove.png"
                Image.fromarray(automatic_remove.astype(np.uint8) * 255, "L").save(automatic_remove_path)
                automatic_keep_path = source_root / "automatic-subject-restore.png"
                Image.fromarray(automatic_keep.astype(np.uint8) * 255, "L").save(automatic_keep_path)
                manual_keep_path = source_root / "manual-keep.png"
                manual_remove_path = source_root / "manual-remove.png"
                for mask_path in (manual_keep_path, manual_remove_path):
                    if not mask_path.exists():
                        Image.new("L", source_image.size, 0).save(mask_path)
                manual_keep = np.asarray(_load_image(manual_keep_path).convert("L")) > 0
                manual_remove = np.asarray(_load_image(manual_remove_path).convert("L")) > 0
                if manual_keep.shape != full_mask.shape or manual_remove.shape != full_mask.shape:
                    raise ValueError(f"{slug}/{key}: manual annotations no longer match the frozen source dimensions")
                full_mask[manual_remove] = False
                full_mask[manual_keep] = True
                bbox = extraction_bbox
                source = source_image.copy()
                source.putalpha(Image.fromarray(full_mask.astype(np.uint8) * 255, "L"))
                source = source.crop(bbox)
                # Keep/remove masks and diagnostics remain in full source-image
                # coordinates, independent of this layer's crop and transform.
                keep = Image.fromarray(full_mask.astype(np.uint8) * 255, "L")
                remove = Image.fromarray((~full_mask).astype(np.uint8) * 255, "L")
                keep_path, remove_path = source_root / "keep.png", source_root / "remove.png"
                keep.save(keep_path)
                remove.save(remove_path)
                source_rgb = source_image.convert("RGB")
                alpha = full_mask.astype(np.uint8) * 255
                rgb = np.asarray(source_rgb).copy()
                rgb[full_mask] = (np.round(rgb[full_mask] * 0.60 + np.array([25, 185, 80]) * 0.40)).astype(np.uint8)
                rgb[alpha == 0] = (np.round(rgb[alpha == 0] * 0.60 + np.array([220, 55, 45]) * 0.40)).astype(np.uint8)
                overlay_path = source_root / "source-mask-overlay.png"
                Image.fromarray(rgb, "RGB").save(overlay_path)
                layer_path = prep / f"{key}.png"
                source.save(layer_path)
                scaled, pos = _fit(source, tuple(old_layer["box"]), canvas_size)
                composite.alpha_composite(scaled, pos)
                bounds = (pos[0], pos[1], pos[0] + scaled.width, pos[1] + scaled.height)
                # Add layer alpha to the protected union without blending masks.
                layer_alpha = np.asarray(scaled.getchannel("A"), dtype=np.uint16)
                existing = np.asarray(protected, dtype=np.uint16)
                x0, y0 = max(0, pos[0]), max(0, pos[1])
                x1, y1 = min(canvas_size[0], pos[0] + scaled.width), min(canvas_size[1], pos[1] + scaled.height)
                if x1 > x0 and y1 > y0:
                    sx, sy = x0 - pos[0], y0 - pos[1]
                    existing[y0:y1, x0:x1] = np.maximum(existing[y0:y1, x0:x1],
                                                           layer_alpha[sy:sy+y1-y0, sx:sx+x1-x0])
                    protected = Image.fromarray(existing.astype(np.uint8), "L")
                    if key.startswith("dialogue-"):
                        dialogue_existing = np.asarray(dialogue_protected, dtype=np.uint16)
                        dialogue_existing[y0:y1, x0:x1] = np.maximum(
                            dialogue_existing[y0:y1, x0:x1], layer_alpha[sy:sy+y1-y0, sx:sx+x1-x0])
                        dialogue_protected = Image.fromarray(dialogue_existing.astype(np.uint8), "L")
                layers.append({**old_layer, "path": str(layer_path), "sha256": _hash(layer_path),
                               "annotation_keep": str(keep_path), "annotation_keep_sha256": _hash(keep_path),
                               "annotation_remove": str(remove_path), "annotation_remove_sha256": _hash(remove_path),
                               "source_mask_overlay": str(overlay_path),
                               "source_size": list(source_image.size), "source_image": str(source_path),
                               "source_image_sha256": _hash(source_path), "annotation_coordinate_frame": "full_source_image",
                               "source_crop_bbox": list(bbox), "position": list(pos),
                               "manual_keep": str(manual_keep_path), "manual_remove": str(manual_remove_path),
                               "manual_keep_sha256": _hash(manual_keep_path), "manual_remove_sha256": _hash(manual_remove_path),
                               "automatic_ground_remove": str(automatic_remove_path),
                               "automatic_ground_remove_sha256": _hash(automatic_remove_path),
                               "automatic_subject_restore": str(automatic_keep_path),
                               "automatic_subject_restore_sha256": _hash(automatic_keep_path),
                               "placed_size": list(scaled.size), "bounds": list(bounds),
                               "transform_policy": "translation plus uniform scaling only"})
            # Compute the permitted 16 px exterior and 48 px contact zones at a
            # 1024 px short-side reference scale; both are clipped away from subjects.
            p = np.asarray(protected, dtype=np.uint8) > 0
            short = min(canvas_size)
            band = max(1, round(16 * short / 1024))
            contact_radius = max(1, round(48 * short / 1024))
            k = 2 * band + 1
            boundary = cv2.morphologyEx(p.astype(np.uint8), cv2.MORPH_GRADIENT,
                                        np.ones((k, k), np.uint8)) > 0
            exterior = cv2.dilate(p.astype(np.uint8), np.ones((k, k), np.uint8), iterations=1) > 0
            exterior &= ~p
            # Ground-contact seed points are derived from the parent layout unless
            # a later human annotation supplies revised normalized contacts.
            contact = np.zeros(p.shape, dtype=np.uint8)
            contacts = _SCENES[slug].get("contact_points", {})
            for item in layers:
                pts = contacts.get(item["key"])
                if not pts:
                    continue
                for nx, ny in pts:
                    cx = round(item["position"][0] + nx * item["placed_size"][0])
                    cy = round(item["position"][1] + ny * item["placed_size"][1])
                    cv2.circle(contact, (cx, cy), contact_radius, 1, -1)
            allowed = (exterior | (contact > 0)) & ~p
            # Keep an exterior safety margin around dialogue too. The Qwen edit
            # region must not reach the balloon outline or tail.
            dialogue = np.asarray(dialogue_protected, dtype=np.uint8) > 0
            dialogue_guard = cv2.dilate(dialogue.astype(np.uint8),
                                       np.ones((2 * band + 1, 2 * band + 1), np.uint8), iterations=1) > 0
            allowed &= ~dialogue_guard
            weight = cv2.GaussianBlur(allowed.astype(np.float32), (9, 9), 1.0)
            weight[~allowed] = 0.0
            # Integration may alter source-background patches only after explicit
            # removal annotation; default remains empty until review amendment.
            repairable_arr = np.asarray(repairable) > 0
            allowed |= repairable_arr & ~p
            allowed &= ~dialogue_guard
            weight[repairable_arr & ~p] = 1.0
            weight[~allowed] = 0.0
            protected_path, edit_path, weight_path = (prep / "protected-subjects-dialogue.png",
                                                        prep / "qwen-edit-mask.png", prep / "integration-weight.png")
            Image.fromarray((p * 255).astype(np.uint8)).save(protected_path)
            Image.fromarray((allowed * 255).astype(np.uint8)).save(edit_path)
            Image.fromarray((np.clip(weight, 0, 1) * 255).astype(np.uint8)).save(weight_path)
            # Contacts/region overlay: magenta shows editable ground/contact work.
            overlay = composite.convert("RGB").convert("RGBA")
            tint = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
            tint_pixels = np.zeros((canvas_size[1], canvas_size[0], 4), dtype=np.uint8)
            tint_pixels[allowed] = (255, 0, 255, 95)
            overlay = Image.alpha_composite(overlay, Image.fromarray(tint_pixels, "RGBA"))
            overlay_path = prep / "review-preview.png"
            overlay.convert("RGB").save(overlay_path)
            contact_pixels = np.zeros((canvas_size[1], canvas_size[0], 4), dtype=np.uint8)
            contact_pixels[contact > 0] = (30, 230, 255, 150)
            contact_overlay_path = prep / "contact-overlay.png"
            Image.alpha_composite(composite.convert("RGBA"), Image.fromarray(contact_pixels, "RGBA")).convert("RGB").save(contact_overlay_path)
            depth_path = prep / "depth-order.png"
            depth_image = Image.new("RGB", canvas_size, "white")
            draw = ImageDraw.Draw(depth_image)
            draw.text((24, 24), f"Scene: {slug}\nBack to front (smallest depth to largest):", fill="black")
            for index, item in enumerate(sorted(layers, key=lambda x: (x["depth"], x["key"])), 1):
                draw.text((40, 70 + 32 * index), f"{index}. depth {item['depth']} — {item['label']}", fill="black")
            depth_image.save(depth_path)
            raw_path = prep / "raw-composite.png"
            composite.convert("RGB").save(raw_path)
            shot_v2 = {"canvas": list(canvas_size), "background": str(bg_path), "layers": layers,
                       "layout_changes": [{"layer": item["key"], "from": item.get("parent_box"),
                                           "to": item["box"], "reason": item.get("layout_change_reason")}
                                          for item in layers if item.get("layout_change_reason")],
                       "protected_subjects_dialogue": str(protected_path), "edit_mask": str(edit_path),
                       "integration_weight": str(weight_path), "contact_overlay": str(contact_overlay_path),
                       "depth_order": str(depth_path), "contact_radius_px": contact_radius,
                       "exterior_band_px": band, "preview": str(overlay_path), "raw_composite": str(raw_path),
                       "luna_review_hashes": {p.name: _hash(p) for p in (overlay_path, raw_path, edit_path, protected_path,
                                                                           contact_overlay_path, depth_path)}}
            shot_v2["candidate_hash"] = hashlib.sha256(json.dumps(
                {"images": shot_v2["luna_review_hashes"],
                 "annotations": {item["key"]: [item["manual_keep_sha256"], item["manual_remove_sha256"],
                                                item["automatic_ground_remove_sha256"],
                                                item["automatic_subject_restore_sha256"]]
                                 for item in layers}}, sort_keys=True).encode()).hexdigest()
            _write_json(prep / "shot-v2.json", shot_v2)
            state["prepared_v2"] = shot_v2
            candidate_hash = shot_v2["candidate_hash"]
            prior_luna = prior_review.get("luna") or {}
            same_review_input = (prior_luna.get("response", {}).get("candidate_hash") == candidate_hash
                                 and prior_luna.get("prompt_version") == RUBRIC_VERSION)
            if not same_review_input and (prior_review.get("luna") or prior_review.get("human")):
                state.setdefault("prep_review_history", []).append(prior_review)
            state["prep_review"] = (prior_review if same_review_input else
                                    {"status": "PENDING_LUNA", "luna": None, "human": None})
        manifest["status"] = "PREPARED_REVIEW_REQUIRED"
        _write_json(self.root / "manifest.json", manifest)
        return {slug: state["prepared_v2"]["preview"] for slug, state in manifest["scenes"].items()}

    def review_catalog(self) -> dict[str, Any]:
        manifest = self._manifest()
        items = []
        for slug, state in manifest["scenes"].items():
            prep = state.get("prepared_v2")
            if not prep:
                continue
            draft_path = self.root / "reviews" / "drafts" / f"{hashlib.sha256(slug.encode()).hexdigest()[:16]}.json"
            current_hash = prep["candidate_hash"]
            draft = _json(draft_path) if draft_path.is_file() else None
            if draft and draft.get("candidate_hash") != current_hash:
                draft = None
            items.append({"kind": "preparation", "scene": slug, "id": slug,
                          "image": f"/artifact/{slug}/preview", "raw": f"/artifact/{slug}/composite",
                          "mask": f"/artifact/{slug}/mask", "contacts": f"/artifact/{slug}/contacts",
                          "depth": f"/artifact/{slug}/depth", "status": state["prep_review"]["status"],
                          "criteria": PREP_CRITERIA, "luna": state["prep_review"].get("luna"),
                          "human": state["prep_review"].get("human"),
                          "previous_review": (state.get("prep_review_history") or [None])[-1],
                          "draft": draft.get("values") if draft else None,
                          "requirements": state["requirements"], "sources": state["sources"],
                          "source_evidence": {name: f"/artifact/{slug}/source-{name}"
                                              for name in state["sources"]},
                          "mask_layers": [{"key": layer["key"], "label": layer["label"],
                                          "source": f"/artifact/{slug}/mask-source-{layer['key']}",
                                          "overlay": f"/artifact/{slug}/mask-overlay-{layer['key']}",
                                          "source_size": layer["source_size"]}
                                         for layer in prep["layers"]],
                          "baseline_outputs": {seed: {"image": f"/artifact/{slug}/baseline-{seed}"}
                                               for seed in state["baseline_outputs"]}})
            for seed, review in state.get("final_reviews", {}).items():
                items.append({"kind": "final", "scene": slug, "id": f"{slug}:{seed}",
                              "status": review["status"], "criteria": FINAL_CRITERIA,
                              "luna": review.get("luna"), "human": review.get("human")})
        return {"run_id": self.run_id, "parent_run_id": PARENT_RUN,
                "status": self._effective_prep_status(manifest), "items": items}

    @staticmethod
    def _effective_prep_status(manifest: dict[str, Any]) -> str:
        reviews = [s.get("prep_review", {}) for s in manifest["scenes"].values()]
        scenes = list(manifest["scenes"].values())
        if any(r.get("human") and any(entry.get("result") == "fail"
                                      for entry in r["human"].get("criteria", {}).values()) for r in reviews):
            return "PREPARATION_REPAIR_REQUIRED"
        for state, review in zip(scenes, reviews):
            if review.get("status") == "HUMAN_CONFIRMED" and review.get("human"):
                if any(entry.get("result") != "pass" for entry in review["human"].get("criteria", {}).values()):
                    return "PREPARATION_REPAIR_REQUIRED"
            else:
                previous = next((old for old in reversed(state.get("prep_review_history", [])) if old.get("human")), None)
                if previous and any(entry.get("result") == "fail" for entry in previous["human"].get("criteria", {}).values()):
                    return "PREPARATION_REPAIR_REQUIRED"
        if any(r.get("status") != "HUMAN_CONFIRMED" or not r.get("human") for r in reviews):
            return "PREPARATION_REVIEW_REQUIRED"
        return "PREPARATION_APPROVED"

    def annotate_layer(self, scene: str, layer_key: str, mode: str, radius: int,
                       points: list[list[float]], source_size: list[int]) -> dict[str, Any]:
        """Apply explicit full-source-coordinate keep/remove brush strokes."""
        if mode not in {"keep", "remove"} or not 1 <= int(radius) <= 160:
            raise ValueError("Choose keep/remove and a brush radius from 1 to 160 source pixels")
        manifest = self._manifest()
        state = manifest["scenes"].get(scene)
        if not state or not state.get("prepared_v2"):
            raise ValueError("Prepare this scene before editing its masks")
        layer = next((x for x in state["prepared_v2"]["layers"] if x["key"] == layer_key), None)
        if not layer:
            raise ValueError("Unknown layer for this scene")
        width, height = map(int, layer["source_size"])
        if list(source_size) != [width, height] or not points or len(points) > 12000:
            raise ValueError("Stroke source dimensions do not match, or the stroke is empty/too large")
        normalized: list[tuple[int, int]] = []
        for pt in points:
            if not isinstance(pt, list) or len(pt) != 2:
                raise ValueError("Stroke points must be [x, y] pairs")
            x, y = round(float(pt[0])), round(float(pt[1]))
            if not (0 <= x < width and 0 <= y < height):
                raise ValueError("Stroke point falls outside the frozen source image")
            normalized.append((x, y))
        annotation_root = Path(layer["manual_keep"]).parent
        keep_path, remove_path = annotation_root / "manual-keep.png", annotation_root / "manual-remove.png"
        if not keep_path.is_file() or not remove_path.is_file():
            raise ValueError("Manual annotation masks are missing")
        keep = _load_image(keep_path).convert("L")
        remove = _load_image(remove_path).convert("L")
        stroke = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(stroke)
        r = int(radius)
        if len(normalized) == 1:
            x, y = normalized[0]
            draw.ellipse((x-r, y-r, x+r, y+r), fill=255)
        else:
            draw.line(normalized, fill=255, width=2*r, joint="curve")
            for x, y in (normalized[0], normalized[-1]):
                draw.ellipse((x-r, y-r, x+r, y+r), fill=255)
        if mode == "keep":
            keep.paste(255, mask=stroke)
            remove.paste(0, mask=stroke)
        else:
            remove.paste(255, mask=stroke)
            keep.paste(0, mask=stroke)
        keep.save(keep_path)
        remove.save(remove_path)
        # Every mask change invalidates Luna and human confirmation until the
        # regenerated preview receives a fresh proposal and explicit approval.
        self.prepare()
        latest = self._manifest()["scenes"][scene]["prepared_v2"]
        return {"preview": str(latest["preview"]), "hash": latest["candidate_hash"]}

    def artifact_path(self, scene: str, kind: str) -> Path:
        manifest = self._manifest()
        if scene not in manifest["scenes"]:
            raise ValueError("Unknown scene")
        prep = manifest["scenes"][scene].get("prepared_v2")
        if not prep:
            raise ValueError("Scene has not been prepared")
        if kind.startswith("baseline-"):
            seed = kind.removeprefix("baseline-")
            if seed not in manifest["scenes"][scene]["baseline_outputs"]:
                raise ValueError("Unknown baseline seed")
            path = Path(manifest["scenes"][scene]["baseline_outputs"][seed]["path"]).resolve()
            if not path.is_relative_to(self.root):
                raise ValueError("Baseline path escaped the follow-up root")
            return path
        if kind.startswith("source-"):
            name = kind.removeprefix("source-")
            info = manifest["scenes"][scene]["sources"].get(name)
            if not info:
                raise ValueError("Unknown source image")
            path = (self.root / "parent-snapshot" / scene / "frozen" / "source_images" /
                    Path(info["frozen_path"]).name).resolve()
            if not path.is_file() or not path.is_relative_to(self.root):
                raise ValueError("Frozen source image is missing or escaped the follow-up root")
            return path
        if kind.startswith("mask-source-"):
            layer_key = kind.removeprefix("mask-source-")
            layer = next((x for x in prep["layers"] if x["key"] == layer_key), None)
            if not layer:
                raise ValueError("Unknown source layer")
            path = Path(layer["source_image"]).resolve()
            if not path.is_file() or not path.is_relative_to(self.root):
                raise ValueError("Source image is missing or escaped the follow-up root")
            return path
        if kind.startswith("mask-overlay-"):
            layer_key = kind.removeprefix("mask-overlay-")
            layer = next((x for x in prep["layers"] if x["key"] == layer_key), None)
            if not layer:
                raise ValueError("Unknown source layer")
            path = Path(layer["source_mask_overlay"]).resolve()
            if not path.is_file() or not path.is_relative_to(self.root):
                raise ValueError("Source mask overlay is missing or escaped the follow-up root")
            return path
        key = {"preview": "preview", "composite": "raw_composite", "mask": "edit_mask",
               "contacts": "contact_overlay", "depth": "depth_order"}.get(kind)
        if not key:
            raise ValueError("Unknown artifact")
        path = Path(prep[key]).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Artifact path escaped the follow-up root")
        return path

    def save_draft(self, item_id: str, values: dict[str, Any]) -> None:
        manifest = self._manifest()
        if ":" in item_id:
            scene, seed = item_id.rsplit(":", 1)
            review = manifest["scenes"][scene]["final_reviews"][seed]
            candidate_hash = review["input_hash"]
        else:
            scene = item_id
            prep = manifest["scenes"][scene]["prepared_v2"]
            candidate_hash = prep["candidate_hash"]
        _write_json(self.root / "reviews" / "drafts" / f"{hashlib.sha256(item_id.encode()).hexdigest()[:16]}.json",
                    {"item_id": item_id, "candidate_hash": candidate_hash, "saved_at": _now(), "values": values})

    def confirm_review(self, item_id: str, values: dict[str, Any], *, amended: bool) -> None:
        manifest = self._manifest()
        if ":" in item_id:
            scene, seed = item_id.rsplit(":", 1)
            review = manifest["scenes"][scene]["final_reviews"][seed]
            criteria = FINAL_CRITERIA
            image_hash = review["input_hash"]
        else:
            scene, seed = item_id, None
            review = manifest["scenes"][scene]["prep_review"]
            criteria = PREP_CRITERIA
            image_hash = manifest["scenes"][scene]["prepared_v2"]["candidate_hash"]
        if review.get("status") not in {"LUNA_PROPOSED", "HUMAN_CONFIRMED"} or not review.get("luna"):
            raise ValueError("A successful Luna proposal is required before human confirmation")
        if review["luna"].get("response", {}).get("candidate_hash") != image_hash:
            raise ValueError("The Luna proposal is stale because its reviewed image hash changed")
        ratings = values.get("criteria", {})
        if set(ratings) != set(criteria):
            raise ValueError("All required criteria must be present")
        for name, entry in ratings.items():
            if entry.get("result") not in RATINGS or not isinstance(entry.get("reason", ""), str):
                raise ValueError(f"Invalid rating for {name}")
        review["human"] = {"confirmed_at": _now(), "reviewer": "human",
                           "action": "amended" if amended else "confirmed_luna",
                           "input_hash": image_hash, "summary": values.get("summary", ""), "criteria": ratings}
        review["status"] = "HUMAN_CONFIRMED"
        draft = self.root / "reviews" / "drafts" / f"{hashlib.sha256(item_id.encode()).hexdigest()[:16]}.json"
        draft.unlink(missing_ok=True)
        _write_json(self.root / "manifest.json", manifest)

    def luna_review(self, item_id: str) -> dict[str, Any]:
        """Run one read-only Luna review with image evidence and strict JSON schema."""
        manifest = self._manifest()
        is_prep = ":" not in item_id
        if is_prep:
            scene, criteria = item_id, PREP_CRITERIA
            review = manifest["scenes"][scene]["prep_review"]
            prep = manifest["scenes"][scene]["prepared_v2"]
            evidence = [Path(prep["preview"]), Path(prep["raw_composite"]), Path(prep["edit_mask"]),
                        Path(prep["contact_overlay"]), Path(prep["depth_order"])]
            scene_dir = self.root / "parent-snapshot" / scene
            source_images = []
            source_mask_overlays = []
            for source_name, source_info in manifest["scenes"][scene]["sources"].items():
                p = scene_dir / "frozen" / "source_images" / Path(source_info["frozen_path"]).name
                if p.is_file():
                    source_images.append((source_name, p))
            evidence.extend(p for _, p in source_images)
            for layer in prep["layers"]:
                overlay = Path(layer["source_mask_overlay"])
                if overlay.is_file():
                    source_mask_overlays.append((layer["key"], overlay))
            evidence.extend(path for _, path in source_mask_overlays)
            image_hash = prep["candidate_hash"]
            requirements = manifest["scenes"][scene]["requirements"]
        else:
            scene, seed = item_id.rsplit(":", 1)
            criteria = FINAL_CRITERIA
            review = manifest["scenes"][scene]["final_reviews"][seed]
            evidence = [Path(review["image_path"]), Path(review["raw_path"]), Path(review["proposal_path"]), Path(review["mask_path"])]
            image_hash = _hash(evidence[0])
            requirements = manifest["scenes"][scene]["requirements"]
        for path in evidence:
            if not path.is_file():
                raise FileNotFoundError(path)
        schema = {"type": "object", "required": ["candidate_hash", "criteria", "summary"], "additionalProperties": False,
                  "properties": {"candidate_hash": {"type": "string"}, "summary": {"type": "string"},
                                 "criteria": {"type": "object", "required": list(criteria), "additionalProperties": False,
                                              "properties": {name: {"type": "object", "required": ["result", "reason", "evidence_region"],
                                                                    "additionalProperties": False,
                                                                    "properties": {"result": {"enum": ["pass", "fail", "unassessable"]},
                                                                                   "reason": {"type": "string"},
                                                                                   "evidence_region": {"type": "string"}}}
                                                             for name in criteria}}}}
        review_dir = self.root / "reviews" / "luna" / hashlib.sha256(item_id.encode()).hexdigest()[:16]
        review_dir.mkdir(parents=True, exist_ok=True)
        schema_path, output_path = review_dir / "schema.json", review_dir / "response.json"
        _write_json(schema_path, schema)
        source_labels = ", ".join(f"{name}: {path.name}" for name, path in locals().get("source_images", []))
        source_mask_labels = ", ".join(f"{name} source mask overlay: {path.name}"
                                        for name, path in locals().get("source_mask_overlays", []))
        prompt = (f"Review {item_id} for an image assembly experiment. Candidate SHA-256: {image_hash}.\n"
                  f"Rubric version: {RUBRIC_VERSION}. Requirements: {json.dumps(requirements, ensure_ascii=False)}\n"
                  f"Attached source evidence labels (after composition evidence): {source_labels}; {source_mask_labels}.\n"
                  f"Criteria: {', '.join(criteria)}. Rate each pass/fail/unassessable and give concise reasons plus a localized evidence region. "
                  "Assess only visible evidence. Distinguish source defects from assembly or integration failures. Do not infer prior reviews. "
                  "For preparation, focus on source retention, source-mask correctness, removable background, membership, placement/contact, and dialogue. "
                  "Mask interpretation is critical: source-mask overlays show green retained pixels and red removed pixels; judge whether those masks preserve visible subjects, anatomy, props, and dialogue while removing source scenery. The separate qwen-edit-mask.png is an ALLOWED edit region: it should cover only exterior seams, ground-contact zones, and explicitly repairable source background, and must exclude protected subject/dialogue pixels. A narrow outline around subjects is correct for this allowed-edit mask; do not fail it for leaving subject interiors black. Fail only if it exposes protected content or includes broad unnecessary areas. "
                  "Return the required structured JSON.")
        executable = None
        if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
            installs = list((Path(os.environ["LOCALAPPDATA"]) / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"))
            if installs:
                executable = str(max(installs, key=lambda path: path.stat().st_mtime_ns))
        executable = executable or shutil.which("codex")
        if not executable:
            raise RuntimeError("Codex CLI is unavailable; Luna review was not substituted")
        command = [executable, "-a", "never", "-s", "read-only", "-m", "gpt-6-luna", "-c",
                   'model_reasoning_effort="high"', "-C", str(self.root), "exec", "--ignore-user-config", "--skip-git-repo-check",
                   "--ephemeral", "--output-schema", str(schema_path), "--output-last-message", str(output_path)]
        for path in evidence:
            command.extend(["--image", str(path)])
        env = {k: v for k, v in os.environ.items() if not k.startswith("_CODEX_")}
        try:
            cp = subprocess.run(command, input=prompt, text=True, encoding="utf-8", errors="replace", capture_output=True, env=env,
                                cwd=str(self.root), timeout=1800, check=False)
        except (subprocess.TimeoutExpired, OSError) as exc:
            audit = {"model": "gpt-6-luna", "reasoning_effort": "high", "execution": "read-only",
                     "prompt_version": RUBRIC_VERSION, "candidate_hash": image_hash,
                     "evidence": [str(p) for p in evidence], "evidence_hashes": [_hash(p) for p in evidence],
                     "timestamp": _now(), "error": str(exc), "status": "failed_or_interrupted"}
            _write_json(review_dir / "audit.json", audit)
            review.update({"status": "LUNA_FAILED", "luna": audit})
            _write_json(self.root / "manifest.json", manifest)
            raise RuntimeError(f"Luna review failed or timed out; retry this item. Audit: {review_dir / 'audit.json'}") from exc
        audit = {"model": "gpt-6-luna", "reasoning_effort": "high", "execution": "read-only",
                 "prompt_version": RUBRIC_VERSION, "candidate_hash": image_hash, "evidence": [str(p) for p in evidence],
                 "evidence_hashes": [_hash(p) for p in evidence], "timestamp": _now(),
                 "returncode": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr,
                 "raw_response_path": str(output_path)}
        _write_json(review_dir / "audit.json", audit)
        if cp.returncode or not output_path.is_file():
            review.update({"status": "LUNA_FAILED", "luna": audit})
            _write_json(self.root / "manifest.json", manifest)
            raise RuntimeError(f"Luna review failed; see {review_dir / 'audit.json'}")
        response = _json(output_path)
        if response.get("candidate_hash") != image_hash or set(response.get("criteria", {})) != set(criteria):
            raise ValueError("Luna response candidate hash or criteria do not match the frozen review")
        for name, entry in response["criteria"].items():
            if entry.get("result") not in RATINGS or not isinstance(entry.get("reason"), str) or not isinstance(entry.get("evidence_region"), str):
                raise ValueError(f"Luna response is invalid for {name}")
        review["status"] = "LUNA_PROPOSED"
        review["luna"] = {**audit, "response": response}
        _write_json(self.root / "manifest.json", manifest)
        return response

    def confirm_prep(self, scene: str, values: dict[str, Any], *, amended: bool) -> None:
        self.confirm_review(scene, values, amended=amended)
        manifest = self._manifest()
        all_confirmed = all(s["prep_review"]["status"] == "HUMAN_CONFIRMED" for s in manifest["scenes"].values())
        all_pass = all(all(entry["result"] == "pass" for entry in s["prep_review"]["human"]["criteria"].values())
                       for s in manifest["scenes"].values() if s["prep_review"].get("human"))
        if all_confirmed and all_pass:
            manifest["status"] = "PREPARATION_APPROVED"
            manifest["preparation_approved_at"] = _now()
        elif all_confirmed:
            manifest["status"] = "PREPARATION_REPAIR_REQUIRED"
        else:
            manifest["status"] = "PREPARATION_REVIEW_REQUIRED"
        _write_json(self.root / "manifest.json", manifest)

    def status(self) -> dict[str, Any]:
        manifest = self._manifest()
        effective_status = self._effective_prep_status(manifest)
        if manifest.get("status") != effective_status:
            manifest["status"] = effective_status
            _write_json(self.root / "manifest.json", manifest)
        return {"run_id": self.run_id, "status": effective_status,
                "preparation": {slug: s["prep_review"]["status"] for slug, s in manifest["scenes"].items()},
                "final_reviews": {slug: {seed: r["status"] for seed, r in s["final_reviews"].items()}
                                  for slug, s in manifest["scenes"].items()}}

