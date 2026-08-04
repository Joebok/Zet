from __future__ import annotations

from collections.abc import Callable, Sequence

from PIL import Image


US_LETTER_LANDSCAPE_RATIO = 8.5 / 11


def letter_landscape_height(width: int) -> int:
    """Calculate a landscape US Letter height from its configured width."""
    return round(int(width) * US_LETTER_LANDSCAPE_RATIO)


def assemble_image_sheet(
    images: Sequence[Image.Image],
    *,
    columns: int,
    rows: int,
    panel_width: int,
    panel_height: int,
    rotations: Sequence[int] | None = None,
    background="white",
    mode: str = "RGB",
    print_scale: float = 1.0,
    border_background="white",
    overlay: Callable[[Image.Image], None] | None = None,
) -> Image.Image:
    """Arrange fixed-size panels and center the result on an exact-size sheet."""
    if columns <= 0 or rows <= 0 or panel_width <= 0 or panel_height <= 0:
        raise ValueError("Sheet rows, columns, and panel dimensions must be positive.")
    if print_scale <= 0 or print_scale > 1:
        raise ValueError("Sheet print scale must be greater than 0 and no greater than 1.")
    if len(images) != columns * rows:
        raise ValueError(f"Expected {columns * rows} images, got {len(images)}.")
    rotations = rotations if rotations is not None else [0] * len(images)
    if len(rotations) != len(images):
        raise ValueError("Each sheet image must have a corresponding rotation.")

    width = columns * panel_width
    height = rows * panel_height
    assembled = Image.new(mode, (width, height), background)
    for index, (image, rotation) in enumerate(zip(images, rotations)):
        if image.size != (panel_width, panel_height):
            raise ValueError(
                f"Sheet panel {index + 1} must be {panel_width}x{panel_height}; "
                f"got {image.width}x{image.height}."
            )
        panel = image.rotate(rotation) if rotation else image
        column = index % columns
        row = index // columns
        assembled.paste(panel, (column * panel_width, row * panel_height))
        if panel is not image:
            panel.close()
    if overlay is not None:
        overlay(assembled)
    if print_scale == 1:
        return assembled

    scaled_width = max(1, round(width * print_scale))
    scaled_height = max(1, round(height * print_scale))
    scaled = assembled.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)
    assembled.close()
    canvas = Image.new(mode, (width, height), border_background)
    canvas.paste(scaled, ((width - scaled_width) // 2, (height - scaled_height) // 2))
    scaled.close()
    return canvas
