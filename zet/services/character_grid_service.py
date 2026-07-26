from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Tuple

from zet.services.image_sheet_service import assemble_image_sheet


BBox = Tuple[int, int, int, int]


@dataclass
class ImageAnalysisResult:
    """Hold image measurement data used to assemble a turnaround grid."""
    name: str
    path: str
    source_width: int
    source_height: int
    background_rgb: tuple[int, int, int]
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


@dataclass(frozen=True)
class CharacterGridOptions:
    """Configure deterministic character grid assembly."""
    background_mode: str = "auto"
    fixed_background_rgb: tuple[int, int, int] = (128, 128, 128)
    tolerance: float = 20.0
    min_area: int = 200
    morph_kernel_size: int = 3
    target_height_mode: str = "median"
    target_height: Optional[int] = None
    outer_margin: int = 60
    col_gap: int = 30
    row_gap: int = 40
    cell_padding_x: int = 40
    cell_padding_y: int = 40
    columns: int = 4
    rows: int = 2
    canvas_background: tuple[int, int, int, int] = (128, 128, 128, 255)
    diagnostics: bool = True
    debug_grid: bool = True
    crop_height_percent: Optional[float] = None
    crop_width_to_character: bool = False
    fixed_panel_width: Optional[int] = None
    fixed_panel_height: Optional[int] = None
    page_margin: int = 0
    print_scale: float = 1.0


@dataclass(frozen=True)
class CharacterGridResult:
    """Describe the files produced by a character grid assembly run."""
    grid_path: Path
    analysis_path: Path
    diagnostics_path: Path
    debug_grid_path: Optional[Path]
    results: list[ImageAnalysisResult]


@dataclass(frozen=True)
class CharacterCropResult:
    """Describe a deterministic single-image character crop."""
    image_path: Path
    analysis_path: Path
    diagnostics_path: Path
    result: ImageAnalysisResult
    crop_box: BBox


class CharacterGridServiceError(Exception):
    """Report invalid inputs or image processing failures."""


class CharacterGridService:
    """Assemble full-body character images into a normalized 4 by 2 grid."""

    def _load_image_dependencies(self):
        """Import image dependencies lazily so the app can report missing packages clearly."""
        try:
            import numpy as np
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise CharacterGridServiceError(
                "Turnaround grid assembly requires Pillow and NumPy. Install requirements.txt before generating sheets."
            ) from exc
        return np, Image, ImageDraw

    def estimate_background_rgb(self, arr_rgba, sample_size: int = 24) -> tuple[int, int, int]:
        """Estimate the neutral background color from image corners."""
        np, _, _ = self._load_image_dependencies()
        h, w, _ = arr_rgba.shape
        s = min(sample_size, h, w)
        patches = [
            arr_rgba[:s, :s, :3],
            arr_rgba[:s, w - s:w, :3],
            arr_rgba[h - s:h, :s, :3],
            arr_rgba[h - s:h, w - s:w, :3],
        ]
        samples = np.concatenate([patch.reshape(-1, 3) for patch in patches], axis=0)
        median_rgb = np.median(samples, axis=0)
        return tuple(int(value) for value in median_rgb)

    def create_foreground_mask(self, arr_rgba, background_rgb: tuple[int, int, int], tolerance: float):
        """Create a foreground mask by color distance from the background."""
        np, _, _ = self._load_image_dependencies()
        rgb = arr_rgba[:, :, :3].astype(np.float32)
        alpha = arr_rgba[:, :, 3].astype(np.float32)
        bg = np.array(background_rgb, dtype=np.float32)
        diff = rgb - bg
        dist = np.sqrt(np.sum(diff * diff, axis=2))
        return (alpha > 0) & (dist > tolerance)

    def clean_mask(self, mask, min_area: int = 200, morph_kernel_size: int = 3):
        """Clean a foreground mask and keep the largest connected component when OpenCV is present."""
        np, _, _ = self._load_image_dependencies()
        mask_u8 = mask.astype(np.uint8) * 255
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
        best_x = int(stats[best_label, cv2.CC_STAT_LEFT])
        best_y = int(stats[best_label, cv2.CC_STAT_TOP])
        best_w = int(stats[best_label, cv2.CC_STAT_WIDTH])
        best_h = int(stats[best_label, cv2.CC_STAT_HEIGHT])
        best_right = best_x + best_w
        best_bottom = best_y + best_h
        horizontal_margin = max(24, int(best_w * 0.45))
        vertical_margin = max(80, int(best_h * 0.18))
        keep_labels = {best_label}
        for label in range(1, num_labels):
            if label == best_label:
                continue
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area < min_area:
                continue
            x = int(stats[label, cv2.CC_STAT_LEFT])
            y = int(stats[label, cv2.CC_STAT_TOP])
            w = int(stats[label, cv2.CC_STAT_WIDTH])
            h = int(stats[label, cv2.CC_STAT_HEIGHT])
            right = x + w
            bottom = y + h
            if x <= 0 or y <= 0 or right >= mask.shape[1] or bottom >= mask.shape[0]:
                continue
            horizontally_aligned = right >= best_x - horizontal_margin and x <= best_right + horizontal_margin
            vertically_near = y <= best_bottom + vertical_margin and bottom >= best_y - vertical_margin
            if horizontally_aligned and vertically_near:
                keep_labels.add(label)
        return np.isin(labels, list(keep_labels))

    def mask_to_bbox(self, mask) -> Optional[BBox]:
        """Convert a foreground mask into a bounding box."""
        np, _, _ = self._load_image_dependencies()
        ys, xs = np.where(mask)
        if len(xs) == 0 or len(ys) == 0:
            return None
        return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1

    def _save_diagnostics(self, image, mask, result: ImageAnalysisResult, diagnostics_dir: Path) -> None:
        """Save bounding-box and mask diagnostic images for one source."""
        _, Image, ImageDraw = self._load_image_dependencies()
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        bbox_image = image.copy()
        draw = ImageDraw.Draw(bbox_image)
        if result.bbox is not None:
            draw.rectangle(result.bbox, outline=(255, 0, 0, 255), width=4)
        bbox_image.save(diagnostics_dir / f"{result.name}_bbox.png")
        mask_image = Image.fromarray((mask.astype("uint8") * 255), mode="L")
        mask_image.save(diagnostics_dir / f"{result.name}_mask.png")

    def analyze_image(self, image_path: Path, options: CharacterGridOptions, diagnostics_dir: Optional[Path]) -> ImageAnalysisResult:
        """Measure one source image and optionally write diagnostics."""
        np, Image, _ = self._load_image_dependencies()
        image = Image.open(image_path).convert("RGBA")
        arr = np.array(image)
        if options.background_mode == "fixed":
            background_rgb = options.fixed_background_rgb
        elif options.background_mode == "auto":
            background_rgb = self.estimate_background_rgb(arr)
        else:
            raise CharacterGridServiceError(f"Unsupported background mode: {options.background_mode}")
        mask = self.create_foreground_mask(arr, background_rgb, options.tolerance)
        mask = self.clean_mask(mask, options.min_area, options.morph_kernel_size)
        bbox = self.mask_to_bbox(mask)
        character_width = 0
        character_height = 0
        foot_y = None
        if bbox is not None:
            left, top, right, bottom = bbox
            character_width = right - left
            character_height = bottom - top
            foot_y = bottom
        result = ImageAnalysisResult(
            name=image_path.stem,
            path=str(image_path),
            source_width=image.width,
            source_height=image.height,
            background_rgb=background_rgb,
            bbox=bbox,
            character_width=character_width,
            character_height=character_height,
            foot_y=foot_y,
            mask_pixel_count=int(mask.sum()),
        )
        if diagnostics_dir is not None:
            self._save_diagnostics(image, mask, result, diagnostics_dir)
        return result

    def choose_target_height(
        self,
        results: list[ImageAnalysisResult],
        mode: str = "median",
        explicit_height: Optional[int] = None,
    ) -> int:
        """Choose the target character height for normalization."""
        heights = [result.character_height for result in results if result.character_height > 0]
        if not heights:
            raise CharacterGridServiceError("No valid character heights were detected.")
        if mode == "explicit":
            if explicit_height is None:
                raise CharacterGridServiceError("target_height is required when target-height-mode is explicit.")
            return int(explicit_height)
        if mode == "min":
            return int(min(heights))
        if mode == "max":
            return int(max(heights))
        if mode == "median":
            return int(round(statistics.median(heights)))
        raise CharacterGridServiceError(f"Unsupported target-height mode: {mode}")

    def apply_scaling_metadata(self, results: list[ImageAnalysisResult], target_height: int) -> None:
        """Populate scale metadata for measured images."""
        for result in results:
            if not result.bbox or result.character_height <= 0:
                raise CharacterGridServiceError(f"No valid bbox for image: {result.path}")
            scale_factor = target_height / result.character_height
            result.scale_factor = scale_factor
            result.scaled_width = int(round(result.source_width * scale_factor))
            result.scaled_height = int(round(result.source_height * scale_factor))
            left, top, right, bottom = result.bbox
            result.scaled_bbox = (
                int(round(left * scale_factor)),
                int(round(top * scale_factor)),
                int(round(right * scale_factor)),
                int(round(bottom * scale_factor)),
            )
            result.scaled_foot_y = int(round(result.foot_y * scale_factor)) if result.foot_y is not None else None

    def _draw_debug_grid(self, canvas, options: CharacterGridOptions, cell_width: int, cell_height: int, output_path: Path) -> Path:
        """Draw cell outlines and foot baselines over a copy of the assembled grid."""
        _, _, ImageDraw = self._load_image_dependencies()
        debug = canvas.copy()
        draw = ImageDraw.Draw(debug)
        baseline_in_cell = cell_height - options.cell_padding_y
        crop_y = cell_height - options.cell_padding_y if options.crop_height_percent else None
        for row in range(options.rows):
            for col in range(options.columns):
                cell_x = options.outer_margin + col * (cell_width + options.col_gap)
                cell_y = options.outer_margin + row * (cell_height + options.row_gap)
                draw.rectangle((cell_x, cell_y, cell_x + cell_width, cell_y + cell_height), outline=(0, 80, 255, 255), width=2)
                if options.crop_height_percent is None:
                    y = cell_y + baseline_in_cell
                    draw.line((cell_x, y, cell_x + cell_width, y), fill=(255, 80, 0, 255), width=2)
                elif crop_y is not None:
                    y = cell_y + crop_y
                    draw.line((cell_x, y, cell_x + cell_width, y), fill=(255, 80, 0, 255), width=2)
        debug_path = output_path.with_name(f"{output_path.stem}_debug{output_path.suffix}")
        debug.save(debug_path)
        return debug_path

    def _scaled_visible_bbox(self, scaled_image, result: ImageAnalysisResult, options: CharacterGridOptions, visible_height: int) -> BBox:
        """Measure visible foreground bounds after applying the partial height crop."""
        np, _, _ = self._load_image_dependencies()
        scaled_bbox = result.scaled_bbox or (0, 0, scaled_image.width, scaled_image.height)
        top = max(0, int(scaled_bbox[1]))
        bottom = min(scaled_image.height, top + int(visible_height))
        if bottom <= top:
            return scaled_bbox
        arr = np.array(scaled_image)
        mask = self.create_foreground_mask(arr, result.background_rgb, options.tolerance)
        mask = self.clean_mask(mask, options.min_area, options.morph_kernel_size)
        cropped = mask[top:bottom, :]
        ys, xs = np.where(cropped)
        if len(xs) == 0 or len(ys) == 0:
            return scaled_bbox[0], top, scaled_bbox[2], bottom
        return int(xs.min()), top + int(ys.min()), int(xs.max()) + 1, top + int(ys.max()) + 1

    def _assemble_fixed_grid(
        self,
        scaled_images,
        visible_bboxes: list[BBox | None],
        results: list[ImageAnalysisResult],
        output_dir: Path,
        output_name: str,
        diagnostics_dir: Path,
        options: CharacterGridOptions,
    ) -> CharacterGridResult:
        """Center normalized figures in fixed-size panels and assemble an exact-size sheet."""
        _, Image, _ = self._load_image_dependencies()
        panel_width = int(options.fixed_panel_width or 0)
        panel_height = int(options.fixed_panel_height or 0)
        content_width = panel_width - options.page_margin * 2
        content_height = panel_height - options.page_margin * 2
        if panel_width <= 0 or panel_height <= 0:
            raise CharacterGridServiceError("Fixed panel width and height must be positive.")
        if content_width <= 0 or content_height <= 0:
            raise CharacterGridServiceError("Page margin leaves no room for turnaround panel content.")
        if options.print_scale <= 0 or options.print_scale > 1:
            raise CharacterGridServiceError("Print scale must be greater than 0 and no greater than 1.")

        bounding_boxes = []
        for scaled, bbox in zip(scaled_images, visible_bboxes):
            left, top, right, bottom = bbox or (0, 0, scaled.width, scaled.height)
            bounding_boxes.append((
                max(0, int(left)),
                max(0, int(top)),
                min(scaled.width, int(right)),
                min(scaled.height, int(bottom)),
            ))
        if any(right <= left or bottom <= top for left, top, right, bottom in bounding_boxes):
            raise CharacterGridServiceError("Unable to compute a valid turnaround character bounding box.")
        max_width = max(right - left for left, _, right, _ in bounding_boxes) + options.cell_padding_x * 2
        max_height = max(bottom - top for _, top, _, bottom in bounding_boxes) + options.cell_padding_y * 2
        fit_scale = min(content_width / max_width, content_height / max_height)

        panels = []
        try:
            for scaled, (left, top, right, bottom) in zip(scaled_images, bounding_boxes):
                resized = scaled.resize(
                    (
                        max(1, round(scaled.width * fit_scale)),
                        max(1, round(scaled.height * fit_scale)),
                    ),
                    Image.Resampling.LANCZOS,
                )
                panel = Image.new("RGBA", (panel_width, panel_height), (255, 255, 255, 255))
                content = Image.new("RGBA", (content_width, content_height), options.canvas_background)
                bbox_center_x = round(((left + right) / 2) * fit_scale)
                bbox_center_y = round(((top + bottom) / 2) * fit_scale)
                content.alpha_composite(
                    resized,
                    (content_width // 2 - bbox_center_x, content_height // 2 - bbox_center_y),
                )
                resized.close()
                panel.alpha_composite(content, (options.page_margin, options.page_margin))
                content.close()
                panels.append(panel)
            canvas = assemble_image_sheet(
                panels,
                columns=options.columns,
                rows=options.rows,
                panel_width=panel_width,
                panel_height=panel_height,
                mode="RGBA",
                background=(255, 255, 255, 255),
                border_background=(255, 255, 255, 255),
                print_scale=options.print_scale,
            )
            grid_path = output_dir / output_name
            canvas.save(grid_path)
            canvas.close()
        finally:
            for panel in panels:
                panel.close()
            for scaled in scaled_images:
                scaled.close()

        analysis_path = output_dir / "analysis.json"
        analysis_path.write_text(
            json.dumps([asdict(result) for result in results], indent=2) + "\n",
            encoding="utf-8",
        )
        return CharacterGridResult(
            grid_path=grid_path,
            analysis_path=analysis_path,
            diagnostics_path=diagnostics_dir,
            debug_grid_path=None,
            results=results,
        )

    def assemble_grid(
        self,
        image_paths: list[Path],
        output_dir: Path,
        options: Optional[CharacterGridOptions] = None,
        output_name: str = "character_grid.png",
    ) -> CharacterGridResult:
        """Analyze, normalize, and composite eight character images into a grid."""
        _, Image, _ = self._load_image_dependencies()
        options = options or CharacterGridOptions()
        if len(image_paths) != options.columns * options.rows:
            raise CharacterGridServiceError(f"Expected {options.columns * options.rows} image paths, got {len(image_paths)}.")
        missing = [path for path in image_paths if not path.exists() or not path.is_file()]
        if missing:
            raise CharacterGridServiceError(f"Missing input image(s): {', '.join(str(path) for path in missing)}")

        output_dir.mkdir(parents=True, exist_ok=True)
        diagnostics_dir = output_dir / "diagnostics"
        results = [
            self.analyze_image(path, options, diagnostics_dir if options.diagnostics else None)
            for path in image_paths
        ]
        target_height = self.choose_target_height(results, options.target_height_mode, options.target_height)
        self.apply_scaling_metadata(results, target_height)

        if options.crop_height_percent is not None:
            if options.crop_height_percent <= 0 or options.crop_height_percent > 100:
                raise CharacterGridServiceError("crop_height_percent must be greater than 0 and less than or equal to 100.")
            visible_character_height = int(round(target_height * (options.crop_height_percent / 100.0)))
            cell_height = visible_character_height + 2 * options.cell_padding_y
        else:
            visible_character_height = target_height
            cell_height = max(int(result.scaled_height or 0) for result in results) + 2 * options.cell_padding_y
        scaled_images = []
        visible_bboxes: list[BBox | None] = []
        for result in results:
            with Image.open(result.path) as source:
                scaled = source.convert("RGBA").resize(
                    (int(result.scaled_width or 0), int(result.scaled_height or 0)),
                    Image.Resampling.LANCZOS,
                )
            scaled_images.append(scaled)
            if options.crop_width_to_character and options.crop_height_percent is not None:
                visible_bboxes.append(self._scaled_visible_bbox(scaled, result, options, visible_character_height))
            else:
                visible_bboxes.append(result.scaled_bbox)

        if options.fixed_panel_width is not None or options.fixed_panel_height is not None:
            return self._assemble_fixed_grid(
                scaled_images,
                visible_bboxes,
                results,
                output_dir,
                output_name,
                diagnostics_dir,
                options,
            )

        if options.crop_width_to_character:
            scaled_bbox_widths = [int((bbox or (0, 0, 0, 0))[2]) - int((bbox or (0, 0, 0, 0))[0]) for bbox in visible_bboxes]
            cell_width = max(scaled_bbox_widths) + 2 * options.cell_padding_x
        else:
            cell_width = max(int(result.scaled_width or 0) for result in results) + 2 * options.cell_padding_x
        final_width = options.outer_margin * 2 + options.columns * cell_width + (options.columns - 1) * options.col_gap
        final_height = options.outer_margin * 2 + options.rows * cell_height + (options.rows - 1) * options.row_gap
        canvas = Image.new("RGBA", (final_width, final_height), options.canvas_background)
        baseline_in_cell = cell_height - options.cell_padding_y

        for index, result in enumerate(results):
            scaled = scaled_images[index]
            row = index // options.columns
            col = index % options.columns
            cell_x = options.outer_margin + col * (cell_width + options.col_gap)
            cell_y = options.outer_margin + row * (cell_height + options.row_gap)
            visible_bbox = visible_bboxes[index]
            if options.crop_width_to_character and visible_bbox is not None:
                bbox_width = visible_bbox[2] - visible_bbox[0]
                paste_x = cell_x + (cell_width - bbox_width) // 2 - int(visible_bbox[0])
            else:
                paste_x = cell_x + (cell_width - scaled.width) // 2
            if options.crop_height_percent is None:
                paste_y = cell_y + baseline_in_cell - int(result.scaled_foot_y or scaled.height)
            else:
                scaled_bbox = result.scaled_bbox or (0, 0, scaled.width, scaled.height)
                paste_y = cell_y + options.cell_padding_y - int(scaled_bbox[1])
            cell_layer = Image.new("RGBA", (cell_width, cell_height), (0, 0, 0, 0))
            cell_layer.alpha_composite(scaled, (paste_x - cell_x, paste_y - cell_y))
            canvas.alpha_composite(cell_layer, (cell_x, cell_y))

        grid_path = output_dir / output_name
        canvas.save(grid_path)
        debug_path = self._draw_debug_grid(canvas, options, cell_width, cell_height, grid_path) if options.debug_grid else None
        analysis_path = output_dir / "analysis.json"
        analysis_path.write_text(
            json.dumps([asdict(result) for result in results], indent=2) + "\n",
            encoding="utf-8",
        )
        return CharacterGridResult(
            grid_path=grid_path,
            analysis_path=analysis_path,
            diagnostics_path=diagnostics_dir,
            debug_grid_path=debug_path,
            results=results,
        )

    def crop_identity_image(
        self,
        image_path: Path,
        output_dir: Path,
        output_name: str,
        crop_percent: float,
        options: Optional[CharacterGridOptions] = None,
    ) -> CharacterCropResult:
        """Crop one image using the same top-percent and width-trim routine as partial grids."""
        _, Image, _ = self._load_image_dependencies()
        if crop_percent <= 0 or crop_percent > 100:
            raise CharacterGridServiceError("crop_percent must be greater than 0 and less than or equal to 100.")
        if not image_path.exists() or not image_path.is_file():
            raise CharacterGridServiceError(f"Missing input image: {image_path}")
        options = options or CharacterGridOptions(tolerance=50.0, crop_width_to_character=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        diagnostics_dir = output_dir / "diagnostics"
        result = self.analyze_image(image_path, options, diagnostics_dir if options.diagnostics else None)
        target_height = self.choose_target_height([result], options.target_height_mode, options.target_height)
        self.apply_scaling_metadata([result], target_height)
        source = Image.open(result.path).convert("RGBA")
        scaled = source.resize((int(result.scaled_width or 0), int(result.scaled_height or 0)), Image.Resampling.LANCZOS)
        visible_character_height = int(round(target_height * (crop_percent / 100.0)))
        visible_bbox = self._scaled_visible_bbox(scaled, result, options, visible_character_height)
        pad_x = int(options.cell_padding_x)
        pad_y = int(options.cell_padding_y)
        left = max(0, int(visible_bbox[0]) - pad_x)
        top = max(0, int((result.scaled_bbox or visible_bbox)[1]) - pad_y)
        right = min(scaled.width, int(visible_bbox[2]) + pad_x)
        bottom = min(scaled.height, int((result.scaled_bbox or visible_bbox)[1]) + visible_character_height + pad_y)
        if right <= left or bottom <= top:
            raise CharacterGridServiceError("Unable to compute a valid identity crop.")
        cropped = scaled.crop((left, top, right, bottom))
        crop_path = output_dir / output_name
        cropped.save(crop_path)
        analysis_path = output_dir / "analysis.json"
        analysis_path.write_text(
            json.dumps({"source": asdict(result), "crop_box": [left, top, right, bottom]}, indent=2) + "\n",
            encoding="utf-8",
        )
        return CharacterCropResult(
            image_path=crop_path,
            analysis_path=analysis_path,
            diagnostics_path=diagnostics_dir,
            result=result,
            crop_box=(left, top, right, bottom),
        )
