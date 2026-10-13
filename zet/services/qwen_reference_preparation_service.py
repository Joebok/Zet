"""Prepare bounded, reproducible reference images for Qwen Image 2.1."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from zet.services.atomic_file_service import write_bytes_atomic, write_json_atomic
from zet.services.local_render_types import LocalRenderError


POLICY_VERSION = 1
ALIGNMENT = 32
DEFAULT_REFERENCE_MAX_PIXELS = 1_048_576
DEFAULT_REFERENCE_TOTAL_MAX_PIXELS = 6_291_456
_CACHE_DEVICES = {"auto", "cpu", "gpu", "off"}
_CACHE_DTYPES = {"default", "int8", "int4"}


@dataclass(frozen=True)
class QwenReferencePolicy:
    enabled: bool
    reference_max_pixels: int
    reference_total_max_pixels: int
    cache_device: str
    cache_dtype: str

    @classmethod
    def resolve(cls, profile: dict[str, Any], machine: dict[str, Any]) -> "QwenReferencePolicy":
        """Resolve preset defaults, then apply validated machine-level overrides."""
        enabled = _setting(machine, "reference_resize_enabled", True)
        if not isinstance(enabled, bool):
            raise LocalRenderError("ComfyUI.QwenImage21.reference_resize_enabled must be true or false.")

        max_pixels = _positive_int(
            _setting(machine, "reference_max_pixels", profile.get("reference_max_pixels", DEFAULT_REFERENCE_MAX_PIXELS)),
            "reference_max_pixels",
        )
        total_max_pixels = _positive_int(
            _setting(machine, "reference_total_max_pixels", profile.get("reference_total_max_pixels", DEFAULT_REFERENCE_TOTAL_MAX_PIXELS)),
            "reference_total_max_pixels",
        )
        device = str(_setting(machine, "cache_device", profile.get("qwen_cache_device", "cpu"))).strip().lower()
        dtype = str(_setting(machine, "cache_dtype", profile.get("qwen_cache_dtype", "int8"))).strip().lower()
        if device not in _CACHE_DEVICES:
            raise LocalRenderError("ComfyUI.QwenImage21.cache_device must be auto, cpu, gpu, or off.")
        if dtype not in _CACHE_DTYPES:
            raise LocalRenderError("ComfyUI.QwenImage21.cache_dtype must be default, int8, or int4.")
        return cls(enabled, max_pixels, total_max_pixels, device, dtype)


def _setting(machine: dict[str, Any], key: str, fallback: Any) -> Any:
    return machine[key] if key in machine else fallback


def _positive_int(value: Any, key: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise LocalRenderError(f"ComfyUI.QwenImage21.{key} must be a positive integer pixel count.")
    return value


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _aligned_size(width: int, height: int, scale: float) -> tuple[int, int]:
    result = tuple((max(ALIGNMENT, int(dimension * scale) // ALIGNMENT * ALIGNMENT))
                   for dimension in (width, height))
    if result[0] > width or result[1] > height:
        raise LocalRenderError("Reference is too small to align safely to Qwen's 32-pixel dimensions.")
    return result


def _image_size(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as source:
            width, height = ImageOps.exif_transpose(source).size
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise LocalRenderError(f"Unable to read Qwen reference image {path.name}: {exc}") from exc
    if width < ALIGNMENT or height < ALIGNMENT:
        raise LocalRenderError(
            f"Qwen reference {path.name} is {width}x{height}; both dimensions must be at least {ALIGNMENT}px."
        )
    return width, height


def _prepared_dimensions(sizes: list[tuple[int, int]], policy: QwenReferencePolicy) -> list[tuple[int, int]]:
    per_image = [
        _aligned_size(width, height, min(1.0, (policy.reference_max_pixels / (width * height)) ** 0.5))
        for width, height in sizes
    ]
    for _ in range(8):
        total = sum(width * height for width, height in per_image)
        if total <= policy.reference_total_max_pixels:
            break
        scale = (policy.reference_total_max_pixels / total) ** 0.5 * 0.99
        reduced = [_aligned_size(width, height, scale) for width, height in per_image]
        if reduced == per_image:
            largest = max(range(len(per_image)), key=lambda index: per_image[index][0] * per_image[index][1])
            width, height = per_image[largest]
            reduced[largest] = (max(ALIGNMENT, width - ALIGNMENT), height)
        per_image = reduced
    if sum(width * height for width, height in per_image) > policy.reference_total_max_pixels:
        raise LocalRenderError(
            "Qwen reference pixel limits cannot be satisfied at 32-pixel alignment; raise the aggregate budget."
        )
    return per_image


def prepare_qwen_references(
    references: list[dict[str, Any]],
    output_dir: Path,
    policy: QwenReferencePolicy,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Create ordered, private reference snapshots and return their metadata."""
    ordered = [dict(item) for item in references]
    if not policy.enabled or not ordered:
        metadata = {
            "policy_version": POLICY_VERSION,
            "enabled": policy.enabled,
            "status": "disabled" if not policy.enabled else "no_references",
            "configured": _policy_settings(policy),
            "references": [],
            "total_pixels": 0,
            "prepared_total_pixels": 0,
            "qwen_cache": _cache_settings(policy),
        }
        write_json_atomic(output_dir / "Qwen_Reference_Preparation.json", metadata)
        return ordered, metadata

    sources: list[Path] = []
    source_sizes: list[tuple[int, int]] = []
    for index, reference in enumerate(ordered, 1):
        source = Path(str(reference.get("path") or "")).expanduser()
        if not source.is_file():
            raise LocalRenderError(f"Qwen reference {index} is missing: {source}")
        sources.append(source)
        source_sizes.append(_image_size(source))

    target_sizes = _prepared_dimensions(source_sizes, policy)
    records: list[dict[str, Any]] = []
    prepared: list[dict[str, Any]] = []
    snapshot_dir = output_dir / "Qwen_Reference_Inputs" / f"v{POLICY_VERSION}"

    for index, (reference, source, source_size, target_size) in enumerate(
        zip(ordered, sources, source_sizes, target_sizes), 1
    ):
        source_hash = _file_sha256(source)
        destination = snapshot_dir / f"reference-{index - 1}.png"
        try:
            with Image.open(source) as opened:
                image = ImageOps.exif_transpose(opened)
                has_alpha = "A" in image.getbands() or "transparency" in image.info
                image = image.convert("RGBA" if has_alpha else "RGB")
                if image.size != target_size:
                    image = image.resize(target_size, Image.Resampling.LANCZOS)
                buffer = BytesIO()
                image.save(buffer, format="PNG", optimize=False)
                payload = buffer.getvalue()
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise LocalRenderError(f"Unable to prepare Qwen reference {index} ({source.name}): {exc}") from exc
        write_bytes_atomic(destination, payload)
        record = {
            "image_index": int(reference.get("image_index") or index),
            "asset_id": reference.get("asset_id"),
            "reference_key": reference.get("reference_key"),
            "label": reference.get("label"),
            "role": reference.get("role"),
            "source_name": source.name,
            "source_sha256": source_hash,
            "source_width": source_size[0],
            "source_height": source_size[1],
            "prepared_path": destination.relative_to(output_dir).as_posix(),
            "prepared_sha256": sha256(payload).hexdigest(),
            "prepared_width": target_size[0],
            "prepared_height": target_size[1],
            "prepared_pixels": target_size[0] * target_size[1],
        }
        records.append(record)
        prepared.append({**reference, "path": str(destination), "prepared_sha256": record["prepared_sha256"]})

    metadata = {
        "policy_version": POLICY_VERSION,
        "enabled": True,
        "status": "prepared",
        "configured": _policy_settings(policy),
        "source_total_pixels": sum(width * height for width, height in source_sizes),
        "prepared_total_pixels": sum(item["prepared_pixels"] for item in records),
        "references": records,
        "qwen_cache": _cache_settings(policy),
    }
    write_json_atomic(output_dir / "Qwen_Reference_Preparation.json", metadata)
    return prepared, metadata


def _policy_settings(policy: QwenReferencePolicy) -> dict[str, Any]:
    return {
        "reference_max_pixels": policy.reference_max_pixels,
        "reference_total_max_pixels": policy.reference_total_max_pixels,
    }


def _cache_settings(policy: QwenReferencePolicy) -> dict[str, str]:
    return {"configured_device": policy.cache_device, "configured_dtype": policy.cache_dtype}
