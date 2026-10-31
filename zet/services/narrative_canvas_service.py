"""Initial Narrative output sizes from scene aspect ratios."""
import math


# Qwen Image 2.1's recommended sizes, including portrait orientations.
QWEN_CANVAS_SIZES = {
    1: (2048, 2048),
    4 / 3: (2400, 1792),
    3 / 4: (1792, 2400),
    3 / 2: (2528, 1696),
    2 / 3: (1696, 2528),
    16 / 9: (2752, 1536),
    9 / 16: (1536, 2752),
}


def canvas_dimensions(canvas: str) -> tuple[int, int]:
    """Aim for 2048 squared pixels within existing 32px/256–4096 limits."""
    try:
        width, height = (float(part) for part in canvas.split(":"))
        if not all(math.isfinite(value) and value > 0 for value in (width, height)):
            raise ValueError
        ratio = width / height
        if not 1 / 16 <= ratio <= 16:
            raise ValueError
    except (AttributeError, TypeError, ValueError, OverflowError):
        raise ValueError("Canvas must be a positive width:height ratio between 1:16 and 16:1, such as 4:3.") from None
    if ratio in QWEN_CANVAS_SIZES:
        return QWEN_CANVAS_SIZES[ratio]
    width, height = 2048 * math.sqrt(ratio), 2048 / math.sqrt(ratio)
    scale = min(1, 4096 / max(width, height))
    return tuple(max(256, min(4096, round(value * scale / 32) * 32)) for value in (width, height))
