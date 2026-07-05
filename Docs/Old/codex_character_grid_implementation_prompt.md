# CODEX Implementation Prompt — Character Turnaround Grid Assembly

You are implementing a Python utility for the Zet character-image pipeline.

## Goal

Create a Python-based tool that assembles 8 full-body character reference images into a single 4×2 grid image.

The important requirement is that the source images may not have the same canvas dimensions, and the character may not appear at the same pixel height from image to image. Do **not** scale images based only on full image rectangle size. Instead:

1. Inspect each image.
2. Detect the visible character bounding box against a neutral gray background.
3. Measure the visible character height.
4. Scale each full source image so that the detected character height matches a shared target height.
5. Composite the scaled images into a 4-across, 2-down grid.
6. Align the figures using a common foot baseline.

This should use traditional image processing only. No AI model, segmentation model, ComfyUI workflow, or external service is required.

---

## Expected Source Image Assumptions

Each input image should contain:

- one character only,
- full body visible,
- neutral gray background,
- no meaningful props or extra objects,
- no text overlays,
- no border/frame,
- PNG preferred.

The background may not be perfectly identical in every image, so the tool should support automatic background estimation.

---

## Required Outputs

The implementation should produce:

1. `analysis.json`
   - structured per-image measurement data.

2. `diagnostics/<image_stem>_bbox.png`
   - original image with detected bounding box drawn.

3. `diagnostics/<image_stem>_mask.png`
   - foreground mask used for bbox detection.

4. `character_grid.png`
   - final 4×2 composite image.

Optional but useful:

5. `character_grid_debug.png`
   - same final grid with cell boundaries or baselines drawn.

---

## Recommended File

Create a script such as:

```text
Scripts/assemble_character_grid.py
```

If the repo has an existing tool layout, follow the established project conventions.

---

## Required CLI Shape

Implement a CLI with roughly this shape:

```bash
python Scripts/assemble_character_grid.py \
  --input-dir ./inputs \
  --order front front_left_3_4 left_profile back_left_3_4 back back_right_3_4 right_profile front_right_3_4 \
  --output-dir ./output \
  --background-mode auto \
  --tolerance 20 \
  --target-height-mode median
```

Also support explicit image paths if that fits the existing project better.

Required or strongly recommended CLI options:

```text
--input-dir
--output-dir
--order
--background-mode auto|fixed
--fixed-background-rgb 128 128 128
--tolerance
--target-height-mode median|min|max|explicit
--target-height
--outer-margin
--col-gap
--row-gap
--cell-padding-x
--cell-padding-y
--diagnostics / --no-diagnostics
```

Default layout:

```text
columns = 4
rows = 2
```

---

## Core Data Model

Use a dataclass similar to this:

```python
from dataclasses import dataclass
from typing import Optional, Tuple

BBox = Tuple[int, int, int, int]  # left, top, right, bottom

@dataclass
class ImageAnalysisResult:
    name: str
    path: str
    source_width: int
    source_height: int
    background_rgb: Tuple[int, int, int]
    bbox: Optional[BBox]
    character_width: int
    character_height: int
    foot_y: Optional[int]
    mask_pixel_count: int
    scale_factor: Optional[float] = None
    scaled_width: Optional[int] = None
    scaled_height: Optional[int] = None
    scaled_bbox: Optional[BBox] = None
    scaled_foot_y: Optional[int] = None
```

---

## Stage 1 — Analyze Images

Implement the following steps.

### 1. Load Image

Use Pillow.

```python
image = Image.open(image_path).convert("RGBA")
arr = np.array(image)
```

### 2. Estimate Background Color

Support two modes.

#### fixed mode

Use `--fixed-background-rgb`.

#### auto mode

Estimate from the four corners:

```python
def estimate_background_rgb(arr_rgba: np.ndarray, sample_size: int = 24) -> tuple[int, int, int]:
    h, w, _ = arr_rgba.shape
    s = min(sample_size, h, w)

    patches = [
        arr_rgba[:s, :s, :3],
        arr_rgba[:s, w - s:w, :3],
        arr_rgba[h - s:h, :s, :3],
        arr_rgba[h - s:h, w - s:w, :3],
    ]

    samples = np.concatenate([p.reshape(-1, 3) for p in patches], axis=0)
    median_rgb = np.median(samples, axis=0)
    return tuple(int(v) for v in median_rgb)
```

### 3. Create Foreground Mask

Use RGB distance from background.

```python
def create_foreground_mask(
    arr_rgba: np.ndarray,
    background_rgb: tuple[int, int, int],
    tolerance: float = 20.0,
) -> np.ndarray:
    rgb = arr_rgba[:, :, :3].astype(np.float32)
    alpha = arr_rgba[:, :, 3].astype(np.float32)
    bg = np.array(background_rgb, dtype=np.float32)

    diff = rgb - bg
    dist = np.sqrt(np.sum(diff * diff, axis=2))

    return (alpha > 0) & (dist > tolerance)
```

### 4. Clean Mask

Prefer OpenCV if available.

Use:
- morphological open,
- morphological close,
- connected components,
- keep largest connected component above `min_area`.

If OpenCV is not installed, provide a fallback that uses the raw mask.

```python
def clean_mask(mask: np.ndarray, min_area: int = 200, morph_kernel_size: int = 3) -> np.ndarray:
    mask_u8 = (mask.astype(np.uint8)) * 255

    try:
        import cv2
    except ImportError:
        return mask_u8 > 0

    kernel = np.ones((morph_kernel_size, morph_kernel_size), np.uint8)
    opened = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, kernel)
    cleaned = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)

    best_label = None
    best_area = 0

    for label in range(1, num_labels):
        area = stats[label, cv2.CC_STAT_AREA]
        if area >= min_area and area > best_area:
            best_area = area
            best_label = label

    if best_label is None:
        return cleaned > 0

    return labels == best_label
```

### 5. Convert Mask to Bounding Box

```python
def mask_to_bbox(mask: np.ndarray) -> Optional[BBox]:
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        return None

    left = int(xs.min())
    top = int(ys.min())
    right = int(xs.max()) + 1
    bottom = int(ys.max()) + 1
    return left, top, right, bottom
```

### 6. Save Diagnostics

For each image, save:
- bbox overlay,
- mask PNG.

Use Pillow `ImageDraw`.

---

## Stage 2 — Scale and Assemble Grid

### 1. Choose Target Height

Implement modes:

```text
median
min
max
explicit
```

Default: `median`.

```python
def choose_target_height(results, mode="median", explicit_height=None) -> int:
    heights = [r.character_height for r in results if r.character_height > 0]
    if not heights:
        raise ValueError("No valid character heights were detected.")

    if mode == "explicit":
        if explicit_height is None:
            raise ValueError("explicit_height is required when mode='explicit'.")
        return int(explicit_height)

    if mode == "min":
        return int(min(heights))

    if mode == "max":
        return int(max(heights))

    return int(round(statistics.median(heights)))
```

### 2. Compute Scale Metadata

For each image:

```python
scale_factor = target_character_height / character_height
```

Apply this scale to:
- full image dimensions,
- bbox,
- foot baseline.

```python
def apply_scaling_metadata(results, target_height: int) -> None:
    for r in results:
        if not r.bbox or r.character_height <= 0:
            raise ValueError(f"No valid bbox for image: {r.path}")

        scale_factor = target_height / r.character_height
        r.scale_factor = scale_factor
        r.scaled_width = int(round(r.source_width * scale_factor))
        r.scaled_height = int(round(r.source_height * scale_factor))

        l, t, rr, b = r.bbox
        r.scaled_bbox = (
            int(round(l * scale_factor)),
            int(round(t * scale_factor)),
            int(round(rr * scale_factor)),
            int(round(b * scale_factor)),
        )

        r.scaled_foot_y = int(round(r.foot_y * scale_factor)) if r.foot_y is not None else None
```

### 3. Compute Cell Size

Simple first implementation:

```python
cell_width = max(scaled_widths) + 2 * cell_padding_x
cell_height = max(scaled_heights) + 2 * cell_padding_y
```

### 4. Composite Layout

Final canvas:

```python
final_width = outer_margin*2 + columns*cell_width + (columns-1)*col_gap
final_height = outer_margin*2 + rows*cell_height + (rows-1)*row_gap
```

For each image:

```python
row = index // columns
col = index % columns
```

Cell origin:

```python
cell_x = outer_margin + col * (cell_width + col_gap)
cell_y = outer_margin + row * (cell_height + row_gap)
```

Recommended default alignment:

- horizontal center
- foot baseline alignment

```python
paste_x = cell_x + (cell_width - scaled_width) // 2
paste_y = cell_y + baseline_in_cell - scaled_foot_y
```

Where:

```python
baseline_in_cell = cell_height - cell_padding_y
```

Composite with:

```python
canvas.alpha_composite(scaled, (paste_x, paste_y))
```

---

## Validation Rules

Fail clearly if:

- input directory does not exist,
- fewer or more than 8 images are selected,
- order list does not contain exactly 8 names,
- any ordered name cannot be matched to an image stem,
- bbox detection fails for any image,
- target-height mode is invalid,
- explicit mode is selected without `--target-height`.

Also print or log useful detected values:
- image name,
- source size,
- bbox,
- character height,
- scale factor.

---

## Suggested Defaults

```python
DEFAULTS = {
    "background_mode": "auto",
    "fixed_background_rgb": (128, 128, 128),
    "tolerance": 20.0,
    "min_area": 200,
    "morph_kernel_size": 3,
    "target_height_mode": "median",
    "outer_margin": 60,
    "col_gap": 30,
    "row_gap": 40,
    "cell_padding_x": 40,
    "cell_padding_y": 40,
    "align_mode": "foot_baseline",
    "canvas_background": (128, 128, 128, 255),
}
```

---

## Implementation Notes

- Keep the pipeline deterministic.
- Prefer `pathlib.Path`.
- Use `json.dumps(..., indent=2)` for analysis output.
- Use `Image.Resampling.LANCZOS` for resizing.
- Keep all key values configurable.
- Make diagnostic output default to on.
- Use no AI and no ComfyUI dependency.
- Do not overfit to Tsaeytte-specific naming; this should work for any character.

---

## Suggested Development Order

1. Implement image discovery and CLI argument parsing.
2. Implement Stage 1 analysis.
3. Generate bbox and mask diagnostics.
4. Save `analysis.json`.
5. Implement target-height selection.
6. Implement scaling metadata.
7. Implement 4×2 grid assembly.
8. Add validation and useful console output.
9. Test with 8 neutral-gray character images.
10. Tune default tolerance only if diagnostics show incorrect boxes.

---

## Acceptance Criteria

The task is complete when:

1. Running the script on 8 source images creates `analysis.json`.
2. Each source image has a diagnostic bbox image.
3. Each source image has a diagnostic mask image.
4. The final output is a 4×2 grid.
5. The visible character heights are normalized based on detected bboxes, not source image dimensions.
6. Characters are aligned by a common foot baseline.
7. The script fails clearly when bbox detection fails or the input set is invalid.
