# Character Turnaround Grid Assembly — Python Implementation Plan

## Purpose

Build a Python-based utility that:

1. **Inspects 8 source images** of a single character on a neutral gray background.
2. **Measures the visible pixel height of the character** in each image by detecting the non-background region.
3. **Scales each full source image** so that the visible character height matches a shared target height.
4. **Assembles the scaled images** into a single final image arranged as:
   - 4 images across the top row
   - 4 images across the bottom row
5. Optionally saves **diagnostic images** showing the detected bounding box for verification.

This approach uses **traditional image processing only**. No AI processing is required.

---

## Recommended High-Level Design

Implement this as **two stages**:

### Stage 1 — Analysis / Measurement
For each input image:
- Load the image.
- Estimate or use the known neutral gray background color.
- Build a foreground mask for all pixels that differ from the background.
- Clean the mask to reduce noise.
- Detect the character bounding box.
- Record:
  - source image size
  - background estimate
  - bounding box `(left, top, right, bottom)`
  - visible character width and height
  - foot baseline position (usually `bottom` of the bbox)
- Save an optional diagnostic image with the bounding box drawn.

### Stage 2 — Scaling / Layout / Composite
Using the analysis results:
- Choose a target visible character height.
- Compute a scale factor for each image:
  - `scale_factor = target_character_height / measured_character_height`
- Resize the **entire source image** using that scale factor.
- Recalculate the scaled character bbox and scaled foot baseline.
- Place each scaled image into a fixed cell in a 4×2 grid.
- Align all characters within each cell using a chosen rule.
- Render a final composite image and save it.

---

## Required Inputs

The tool should accept the following inputs.

### Required Inputs

1. **Eight input image paths**
   - Order should either be:
     - explicitly supplied by the caller, or
     - defined by filename convention.

2. **Output directory**
   - Directory where diagnostics, analysis JSON, and final composite are written.

3. **Grid order / slot order**
   - A list of 8 items defining placement order.
   - Example:
     ```python
     [
         "front", "front_left_3_4", "left_profile", "back_left_3_4",
         "back", "back_right_3_4", "right_profile", "front_right_3_4"
     ]
     ```

### Strongly Recommended Inputs / Config Values

4. **Target character height mode**
   One of:
   - explicit pixel value, e.g. `1400`
   - derived from the median detected character height
   - derived from the minimum detected character height
   - derived from the maximum detected character height

5. **Background color configuration**
   One of:
   - fixed known RGB, e.g. `(128, 128, 128)`
   - automatic estimation from corners/edges

6. **Background tolerance**
   - Numeric threshold controlling when a pixel is considered foreground.
   - Example default: `18` to `30` depending on image cleanliness.

7. **Cell size policy**
   One of:
   - fixed cell width and height
   - dynamic cell size based on scaled images

8. **Alignment policy within each cell**
   Recommended default:
   - horizontal center
   - common foot baseline

### Optional Inputs

9. **Margins and spacing**
   - outer margin
   - row gap
   - column gap

10. **Diagnostic output toggle**
   - whether to save bbox overlays and masks

11. **Mask cleanup settings**
   - morphological opening/closing size
   - minimum connected-component area

12. **Final background color**
   - e.g. neutral gray, white, parchment, transparent

13. **Optional caption labels**
   - place a short label beneath or above each slot.

---

## Suggested File Outputs

The tool should ideally generate:

1. `analysis.json`
   - structured measurement results for all images.

2. `diagnostics/<name>_bbox.png`
   - original image with bbox overlay.

3. `diagnostics/<name>_mask.png`
   - binary or grayscale foreground mask.

4. `character_grid.png`
   - final assembled image.

5. Optional: `character_grid_debug.png`
   - same as final grid but with guides, slot rectangles, or baselines visible.

---

## Core Technical Decisions

### 1. How to detect the character

Because the source images contain:
- a **single character**
- a **neutral gray background**

The best initial approach is:
- estimate the background color,
- compute color distance from background,
- mark sufficiently different pixels as foreground,
- find the bounding box of the largest connected foreground region.

### 2. How to define character height

Use:
- `character_height = bbox.bottom - bbox.top`

This measures the visible height of the detected character content.

### 3. How to align characters in the final grid

Recommended default:
- **common visible height** via scaling
- **common foot baseline** within each row or across the whole sheet
- horizontal centering within each cell

This is usually the most visually stable layout for turnaround/reference images.

---

## Recommended Python Libraries

### Minimum stack
- `Pillow` for image loading, resizing, drawing, and composition
- `numpy` for pixel math

### Strongly recommended
- `opencv-python` (`cv2`) for robust mask cleanup and connected-component analysis

### Optional
- `dataclasses`
- `pathlib`
- `json`
- `typing`

---

## Data Model Suggestion

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

BBox = Tuple[int, int, int, int]  # left, top, right, bottom

@dataclass
class ImageAnalysisResult:
    name: str
    path: Path
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

# Stage 1 — Analysis / Measurement

## Stage 1 Goal

For each input image, compute the visible character bounding box accurately enough to support scaling and layout.

---

## Stage 1 Detailed Steps

### Step 1 — Load image
- Open image with Pillow.
- Convert to `RGBA` to preserve alpha if present.
- Convert to NumPy array for analysis.

### Step 2 — Determine background color
Recommended methods, in order:

#### Option A — Fixed known background color
Use this if the renderer always uses the same exact background color.

Pros:
- simple
- deterministic

Cons:
- fails if the background varies slightly

#### Option B — Estimate from image corners
Sample small patches in the 4 corners and take the median RGB value.

Pros:
- adapts to small background variations
- usually robust for single-character images

Cons:
- could fail if the character or hair touches a corner

#### Option C — Estimate from outer border
Sample all pixels along a border strip.

Pros:
- often more stable than corners alone

Cons:
- may be contaminated if the character touches the image edge

Recommended implementation:
- support both **fixed** and **auto** modes.

### Step 3 — Build foreground mask
For each pixel:
- measure distance between pixel RGB and background RGB
- if distance exceeds threshold, treat as foreground

Recommended distance:
- Euclidean distance in RGB space

```python
color_distance = sqrt((r-bg_r)^2 + (g-bg_g)^2 + (b-bg_b)^2)
```

Mask rule:
```python
mask = (alpha > 0) & (color_distance > tolerance)
```

### Step 4 — Clean the mask
Without cleanup, mask edges may include:
- antialiasing
- tiny noise pixels
- floor shadow fragments

Recommended cleanup:
- morphological open to remove tiny specks
- morphological close to fill tiny holes
- connected-component filtering to keep only the largest foreground object

This is easiest with OpenCV.

### Step 5 — Extract bounding box
Once the mask is cleaned:
- find all foreground coordinates
- compute min/max x/y
- define bbox as:
  - `left = min_x`
  - `top = min_y`
  - `right = max_x + 1`
  - `bottom = max_y + 1`

Character dimensions:
- `width = right - left`
- `height = bottom - top`

### Step 6 — Save diagnostics
Create diagnostic outputs:
- original image with red bbox
- optional mask image
- optional text annotation with detected size

### Step 7 — Persist structured analysis
Write one JSON object per image or a combined `analysis.json`.

---

## Stage 1 Python Logic (Detailed Draft)

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Tuple, List

import numpy as np
from PIL import Image, ImageDraw

try:
    import cv2
except ImportError:
    cv2 = None

BBox = Tuple[int, int, int, int]


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

### Background estimation helper

```python
def estimate_background_rgb(arr_rgba: np.ndarray, sample_size: int = 24) -> Tuple[int, int, int]:
    """
    Estimate the background RGB using the 4 corner patches.
    arr_rgba shape: (H, W, 4)
    """
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

### Foreground mask creation

```python
def create_foreground_mask(
    arr_rgba: np.ndarray,
    background_rgb: Tuple[int, int, int],
    tolerance: float = 20.0,
) -> np.ndarray:
    """
    Returns a boolean mask where True = foreground.
    """
    rgb = arr_rgba[:, :, :3].astype(np.float32)
    alpha = arr_rgba[:, :, 3].astype(np.float32)
    bg = np.array(background_rgb, dtype=np.float32)

    diff = rgb - bg
    dist = np.sqrt(np.sum(diff * diff, axis=2))

    mask = (alpha > 0) & (dist > tolerance)
    return mask
```

### Mask cleanup

```python
def clean_mask(mask: np.ndarray, min_area: int = 200, morph_kernel_size: int = 3) -> np.ndarray:
    """
    Clean the mask and keep the largest connected component.
    Requires OpenCV for best results. Falls back to raw mask if cv2 is unavailable.
    """
    mask_u8 = (mask.astype(np.uint8)) * 255

    if cv2 is None:
        return mask_u8 > 0

    kernel = np.ones((morph_kernel_size, morph_kernel_size), np.uint8)

    # Remove tiny specks
    opened = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, kernel)

    # Fill tiny holes / connect close regions
    cleaned = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)

    # label 0 is background
    best_label = None
    best_area = 0

    for label in range(1, num_labels):
        area = stats[label, cv2.CC_STAT_AREA]
        if area >= min_area and area > best_area:
            best_area = area
            best_label = label

    if best_label is None:
        return cleaned > 0

    largest = labels == best_label
    return largest
```

### Bounding box extraction

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

### Diagnostics writer

```python
def save_bbox_diagnostic(
    image: Image.Image,
    bbox: Optional[BBox],
    output_path: Path,
    label: Optional[str] = None,
) -> None:
    img = image.convert("RGBA").copy()
    draw = ImageDraw.Draw(img)

    if bbox is not None:
        draw.rectangle(bbox, outline=(255, 0, 0, 255), width=4)
        if label:
            draw.text((bbox[0] + 8, max(0, bbox[1] - 20)), label, fill=(255, 0, 0, 255))

    img.save(output_path)
```

### Per-image analysis function

```python
def analyze_image(
    image_path: Path,
    background_mode: str = "auto",
    fixed_background_rgb: Tuple[int, int, int] = (128, 128, 128),
    tolerance: float = 20.0,
    min_area: int = 200,
    morph_kernel_size: int = 3,
    diagnostics_dir: Optional[Path] = None,
) -> ImageAnalysisResult:
    image = Image.open(image_path).convert("RGBA")
    arr = np.array(image)
    h, w = arr.shape[:2]

    if background_mode == "fixed":
        bg_rgb = fixed_background_rgb
    else:
        bg_rgb = estimate_background_rgb(arr)

    raw_mask = create_foreground_mask(arr, bg_rgb, tolerance=tolerance)
    clean = clean_mask(raw_mask, min_area=min_area, morph_kernel_size=morph_kernel_size)
    bbox = mask_to_bbox(clean)

    if bbox is None:
        character_width = 0
        character_height = 0
        foot_y = None
    else:
        left, top, right, bottom = bbox
        character_width = right - left
        character_height = bottom - top
        foot_y = bottom

    result = ImageAnalysisResult(
        name=image_path.stem,
        path=str(image_path),
        source_width=w,
        source_height=h,
        background_rgb=bg_rgb,
        bbox=bbox,
        character_width=character_width,
        character_height=character_height,
        foot_y=foot_y,
        mask_pixel_count=int(np.count_nonzero(clean)),
    )

    if diagnostics_dir is not None:
        diagnostics_dir.mkdir(parents=True, exist_ok=True)

        label = f"{character_width}x{character_height}" if bbox else "NO BBOX"
        save_bbox_diagnostic(
            image=image,
            bbox=bbox,
            output_path=diagnostics_dir / f"{image_path.stem}_bbox.png",
            label=label,
        )

        mask_img = Image.fromarray((clean.astype(np.uint8) * 255), mode="L")
        mask_img.save(diagnostics_dir / f"{image_path.stem}_mask.png")

    return result
```

### Batch analysis runner

```python
def analyze_images(
    image_paths: List[Path],
    diagnostics_dir: Path,
    analysis_json_path: Path,
    **kwargs,
) -> List[ImageAnalysisResult]:
    results = []
    for path in image_paths:
        result = analyze_image(
            image_path=path,
            diagnostics_dir=diagnostics_dir,
            **kwargs,
        )
        results.append(result)

    analysis_json_path.write_text(
        json.dumps([asdict(r) for r in results], indent=2),
        encoding="utf-8",
    )
    return results
```

---

# Stage 2 — Scaling / Layout / Composite

## Stage 2 Goal

Transform the measurement results into a consistent 4×2 composite image where the characters appear at matching visual height.

---

## Stage 2 Detailed Steps

### Step 1 — Choose target character height
Recommended options:

#### Option A — Median of detected heights
Good default if most images are reasonable and you want moderate rescaling.

#### Option B — Minimum detected height
Prevents upscaling all images too much; more conservative.

#### Option C — Explicit target height
Best if the final sheet has strict design requirements.

Recommended default:
- use **median** or an **explicit configured value**.

### Step 2 — Compute scale factor per image
For each image:

```python
scale_factor = target_character_height / character_height
```

Then compute scaled image size:

```python
scaled_width = round(source_width * scale_factor)
scaled_height = round(source_height * scale_factor)
```

### Step 3 — Resize entire image
Use high-quality resampling:
- `Image.Resampling.LANCZOS`

### Step 4 — Scale bbox and foot baseline
Transform the measured bbox into scaled coordinates.

```python
scaled_bbox = tuple(round(v * scale_factor) for v in bbox)
scaled_foot_y = round(foot_y * scale_factor)
```

### Step 5 — Determine cell size
You have two main choices.

#### Choice A — Dynamic cell size
Compute:
- max scaled image width among all 8
- max scaled image height among all 8
- then add padding

Pros:
- ensures everything fits

Cons:
- may waste space

#### Choice B — Tight cell size based on scaled bbox + margins
More efficient but slightly more complex.

Recommended first implementation:
- use **dynamic cell size**.

### Step 6 — Define alignment inside each cell
Recommended default:
- center horizontally
- align feet to common baseline

This means that in each cell:
- compute `paste_x` so the scaled image is horizontally centered
- compute `paste_y` so the character’s scaled foot position aligns with the row baseline

### Step 7 — Compute final canvas size
If using:
- `cols = 4`
- `rows = 2`

Then:

```python
final_width = outer_margin*2 + cols*cell_width + (cols-1)*col_gap
final_height = outer_margin*2 + rows*cell_height + (rows-1)*row_gap
```

### Step 8 — Composite images in slot order
For each image in the specified order:
- determine row/column
- compute cell origin `(cell_x, cell_y)`
- compute image paste position `(paste_x, paste_y)`
- paste onto final canvas

### Step 9 — Save final sheet
Write the final PNG.

---

## Stage 2 Python Logic (Detailed Draft)

### Target height chooser

```python
import statistics
from typing import Literal


def choose_target_height(
    results: List[ImageAnalysisResult],
    mode: Literal["median", "min", "max", "explicit"] = "median",
    explicit_height: Optional[int] = None,
) -> int:
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

### Apply scaling metadata

```python
def apply_scaling_metadata(results: List[ImageAnalysisResult], target_height: int) -> None:
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

### Cell size calculation

```python
def compute_cell_size(
    results: List[ImageAnalysisResult],
    cell_padding_x: int = 40,
    cell_padding_y: int = 40,
) -> Tuple[int, int]:
    max_w = max(r.scaled_width or 0 for r in results)
    max_h = max(r.scaled_height or 0 for r in results)
    return max_w + 2 * cell_padding_x, max_h + 2 * cell_padding_y
```

### Grid assembly

```python
from PIL import Image


def assemble_grid(
    ordered_results: List[ImageAnalysisResult],
    output_path: Path,
    columns: int = 4,
    rows: int = 2,
    outer_margin: int = 60,
    col_gap: int = 30,
    row_gap: int = 40,
    cell_padding_x: int = 40,
    cell_padding_y: int = 40,
    canvas_background=(128, 128, 128, 255),
    align_mode: str = "foot_baseline",
) -> None:
    if len(ordered_results) != columns * rows:
        raise ValueError(f"Expected {columns * rows} results, got {len(ordered_results)}")

    cell_width, cell_height = compute_cell_size(
        ordered_results,
        cell_padding_x=cell_padding_x,
        cell_padding_y=cell_padding_y,
    )

    final_width = outer_margin * 2 + columns * cell_width + (columns - 1) * col_gap
    final_height = outer_margin * 2 + rows * cell_height + (rows - 1) * row_gap

    canvas = Image.new("RGBA", (final_width, final_height), canvas_background)

    # Define a foot baseline inside each cell.
    # This is the y-position, relative to the cell origin, where feet should land.
    baseline_in_cell = cell_height - cell_padding_y

    for idx, result in enumerate(ordered_results):
        row = idx // columns
        col = idx % columns

        cell_x = outer_margin + col * (cell_width + col_gap)
        cell_y = outer_margin + row * (cell_height + row_gap)

        src = Image.open(result.path).convert("RGBA")
        scaled = src.resize((result.scaled_width, result.scaled_height), Image.Resampling.LANCZOS)

        paste_x = cell_x + (cell_width - result.scaled_width) // 2

        if align_mode == "foot_baseline":
            if result.scaled_foot_y is None:
                raise ValueError(f"scaled_foot_y missing for {result.path}")
            paste_y = cell_y + baseline_in_cell - result.scaled_foot_y
        else:
            # fallback center alignment
            paste_y = cell_y + (cell_height - result.scaled_height) // 2

        canvas.alpha_composite(scaled, (paste_x, paste_y))

    canvas.save(output_path)
```

---

## Suggested Orchestration Function

```python
def run_character_grid_pipeline(
    image_paths: List[Path],
    output_dir: Path,
    background_mode: str = "auto",
    fixed_background_rgb: Tuple[int, int, int] = (128, 128, 128),
    tolerance: float = 20.0,
    min_area: int = 200,
    morph_kernel_size: int = 3,
    target_height_mode: str = "median",
    explicit_target_height: Optional[int] = None,
    ordered_names: Optional[List[str]] = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_dir = output_dir / "diagnostics"
    analysis_json_path = output_dir / "analysis.json"
    final_output_path = output_dir / "character_grid.png"

    results = analyze_images(
        image_paths=image_paths,
        diagnostics_dir=diagnostics_dir,
        analysis_json_path=analysis_json_path,
        background_mode=background_mode,
        fixed_background_rgb=fixed_background_rgb,
        tolerance=tolerance,
        min_area=min_area,
        morph_kernel_size=morph_kernel_size,
    )

    target_height = choose_target_height(
        results,
        mode=target_height_mode,
        explicit_height=explicit_target_height,
    )

    apply_scaling_metadata(results, target_height)

    if ordered_names is not None:
        result_map = {r.name: r for r in results}
        ordered_results = [result_map[name] for name in ordered_names]
    else:
        ordered_results = results

    assemble_grid(
        ordered_results=ordered_results,
        output_path=final_output_path,
    )

    return final_output_path
```

---

## Practical Notes / Edge Cases

### 1. Background not perfectly uniform
If the renderer introduces subtle gradients or compression artifacts:
- use auto background estimation
- slightly increase tolerance
- keep largest connected foreground component only

### 2. Shadow at the feet
If there is a soft shadow below the feet, the detected bbox bottom may extend too low.

Mitigations:
- raise tolerance slightly
- erode and re-dilate the mask
- optionally ignore very faint differences from the background

### 3. Hair strands / wisps
Loose hair may extend the top or sides of the bbox.

This is usually acceptable because it reflects visible character extent.
If it becomes a problem, make it a configurable policy decision rather than hard-coding against it.

### 4. Character color close to background color
If costume or skin areas are too close to gray, tolerance may clip parts of the character.

Mitigations:
- lower tolerance
- use mask cleanup and largest connected component
- allow manual override or per-image threshold if needed

### 5. No bbox detected
If an image fails detection:
- stop the pipeline
- log the failure clearly
- save raw mask diagnostics
- require manual review

### 6. One image has too much empty top or bottom space
That is fine. The pipeline scales the full image based on detected character height, not image rectangle size.

---

## Recommended Defaults for First Implementation

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
}
```

---

## Recommended CLI / API Shape

### CLI example

```bash
python assemble_character_grid.py \
  --input-dir ./inputs \
  --order front front_left_3_4 left_profile back_left_3_4 back back_right_3_4 right_profile front_right_3_4 \
  --output-dir ./output \
  --background-mode auto \
  --tolerance 20 \
  --target-height-mode median
```

### Python API example

```python
from pathlib import Path

image_paths = [
    Path("inputs/front.png"),
    Path("inputs/front_left_3_4.png"),
    Path("inputs/left_profile.png"),
    Path("inputs/back_left_3_4.png"),
    Path("inputs/back.png"),
    Path("inputs/back_right_3_4.png"),
    Path("inputs/right_profile.png"),
    Path("inputs/front_right_3_4.png"),
]

run_character_grid_pipeline(
    image_paths=image_paths,
    output_dir=Path("output"),
    background_mode="auto",
    tolerance=20.0,
    target_height_mode="median",
    ordered_names=[
        "front",
        "front_left_3_4",
        "left_profile",
        "back_left_3_4",
        "back",
        "back_right_3_4",
        "right_profile",
        "front_right_3_4",
    ],
)
```

---

## Suggested Development Sequence for CODEX

1. **Implement Stage 1 only**
   - image loading
   - background estimation
   - foreground mask
   - mask cleanup
   - bbox extraction
   - diagnostics output
   - analysis JSON

2. **Test Stage 1 on a small set of known images**
   - inspect bbox overlays
   - tune tolerance and cleanup defaults

3. **Implement Stage 2**
   - target height selection
   - scaling metadata
   - fixed 4×2 layout
   - final canvas rendering

4. **Add configuration and CLI support**
   - configurable order
   - configurable target-height strategy
   - configurable styling/margins

5. **Add failure handling and validation**
   - fewer/more than 8 images
   - missing bbox
   - duplicate names
   - invalid order list

6. **Optional later improvements**
   - slot labels
   - transparent output
   - per-image manual bbox override
   - manual baseline override
   - JSON schema validation

---

## Why This Plan Is a Good Fit

This plan is a strong first implementation because it:
- avoids AI entirely
- is deterministic and inspectable
- fits your use case closely
- gives visual diagnostics for trust and debugging
- is easy to integrate into an existing Python-based tool pipeline

ComfyUI may still be useful later for broader visual workflows, but for **measuring character height and assembling a turnaround sheet**, the Python path is the most direct and maintainable solution.

---

## Short Summary for Handoff to CODEX

Implement a Python pipeline in two stages:

1. **Analyze each image** to estimate background color, build a foreground mask, isolate the character, and compute a bounding box and visible character height.
2. **Scale and assemble** the full images into a 4×2 grid using the detected character height as the scaling basis, aligning figures to a shared foot baseline.

The tool should produce:
- diagnostics,
- analysis JSON,
- and a final assembled composite image.
