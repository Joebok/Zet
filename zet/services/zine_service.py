from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from zet.models.zine import ZineDocument, ZineRecord, ZineSceneSource


PANEL_WIDTH = 825
PANEL_HEIGHT = 1275
CANVAS_WIDTH = PANEL_WIDTH * 4
CANVAS_HEIGHT = PANEL_HEIGHT * 2
SLOT_KEYS = ("front", "page_1", "page_2", "page_3", "page_4", "page_5", "page_6", "back")
REQUIRED_SLOT_KEYS = ("front", "page_1", "page_3", "page_5", "back")


class ZineServiceError(Exception):
    """Report Zine Maker validation and storage failures."""


def cover_crop(image: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Scale and center-crop an image to exactly cover a target rectangle."""
    return ImageOps.fit(
        ImageOps.exif_transpose(image).convert("RGB"),
        (target_w, target_h),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )


def make_page_image(image: Image.Image, margin: int = 0) -> Image.Image:
    """Center-crop one image inside a white page margin."""
    page = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "white")
    content = cover_crop(image, PANEL_WIDTH - margin * 2, PANEL_HEIGHT - margin * 2)
    page.paste(content, (margin, margin))
    content.close()
    return page


def make_spread_pages(image: Image.Image, margin: int = 0) -> tuple[Image.Image, Image.Image]:
    """Return spread halves with one white margin around the full two-page image."""
    spread = Image.new("RGB", (PANEL_WIDTH * 2, PANEL_HEIGHT), "white")
    content = cover_crop(image, PANEL_WIDTH * 2 - margin * 2, PANEL_HEIGHT - margin * 2)
    spread.paste(content, (margin, margin))
    content.close()
    left = spread.crop((0, 0, PANEL_WIDTH, PANEL_HEIGHT))
    right = spread.crop((PANEL_WIDTH, 0, PANEL_WIDTH * 2, PANEL_HEIGHT))
    spread.close()
    return left, right


def draw_guides(canvas: Image.Image, spread_pages: set[int] | None = None) -> None:
    """Draw faint panel boundaries on a printable zine canvas."""
    spread_pages = spread_pages or set()
    draw = ImageDraw.Draw(canvas)
    color = (190, 190, 190)
    if 5 not in spread_pages:
        draw.line((PANEL_WIDTH, 0, PANEL_WIDTH, PANEL_HEIGHT), fill=color, width=1)
    draw.line((PANEL_WIDTH, PANEL_HEIGHT, PANEL_WIDTH, CANVAS_HEIGHT), fill=color, width=1)
    draw.line((PANEL_WIDTH * 2, 0, PANEL_WIDTH * 2, CANVAS_HEIGHT), fill=color, width=1)
    if 3 not in spread_pages:
        draw.line((PANEL_WIDTH * 3, 0, PANEL_WIDTH * 3, PANEL_HEIGHT), fill=color, width=1)
    if 1 not in spread_pages:
        draw.line((PANEL_WIDTH * 3, PANEL_HEIGHT, PANEL_WIDTH * 3, CANVAS_HEIGHT), fill=color, width=1)
    draw.line((0, PANEL_HEIGHT, CANVAS_WIDTH, PANEL_HEIGHT), fill=color, width=1)


def assemble_zine(
    page_images: dict[str, Image.Image],
    guides_enabled: bool = True,
    spread_pages: set[int] | None = None,
) -> Image.Image:
    """Arrange eight page images into the printable folded-zine layout."""
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), "white")
    top_slots = ("page_6", "page_5", "page_4", "page_3")
    bottom_slots = ("back", "front", "page_1", "page_2")
    for column, slot in enumerate(top_slots):
        canvas.paste(page_images[slot].rotate(180), (column * PANEL_WIDTH, 0))
    for column, slot in enumerate(bottom_slots):
        canvas.paste(page_images[slot], (column * PANEL_WIDTH, PANEL_HEIGHT))
    if guides_enabled:
        draw_guides(canvas, spread_pages)
    return canvas


def scale_and_center_zine(image: Image.Image, print_scale: float) -> Image.Image:
    """Scale an assembled zine and center it on the fixed US Letter canvas."""
    scaled_width = max(1, round(CANVAS_WIDTH * print_scale))
    scaled_height = max(1, round(CANVAS_HEIGHT * print_scale))
    scaled = image.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), "white")
    canvas.paste(scaled, ((CANVAS_WIDTH - scaled_width) // 2, (CANVAS_HEIGHT - scaled_height) // 2))
    scaled.close()
    return canvas


class ZineService:
    """Create and manage derived printable zines."""

    def __init__(self, path_service, story_service):
        self.path_service = path_service
        self.story_service = story_service

    def safe_slug(self, value: str) -> str:
        return self.story_service.safe_slug(value)

    def _layout_settings(self) -> tuple[float, int]:
        print_scale = float(getattr(self.path_service.config, "zine_print_scale", 0.978))
        page_margin = int(getattr(self.path_service.config, "zine_page_margin", 4))
        if print_scale <= 0 or print_scale > 1:
            raise ZineServiceError("Zine print scale must be greater than 0 and no greater than 1.")
        if page_margin < 0 or page_margin * 2 >= PANEL_WIDTH:
            raise ZineServiceError("Zine page margin must be between 0 and 412 pixels.")
        return print_scale, page_margin

    def _folder(self, slug: str) -> Path:
        safe_slug = self.safe_slug(slug)
        if safe_slug != slug:
            raise ZineServiceError(f"Invalid zine slug: {slug}")
        return self.path_service.zines_path() / safe_slug

    def _paths(self, slug: str) -> tuple[Path, Path, Path]:
        folder = self._folder(slug)
        return folder, folder / f"{slug}.png", folder / f"{slug}.json"

    def _record(self, metadata: dict, json_path: Path) -> ZineRecord:
        slug = str(metadata.get("zine_slug") or json_path.parent.name)
        name = str(metadata.get("zine_name") or slug)
        image_path = json_path.parent / str(metadata.get("output_image") or f"{slug}.png")
        return ZineRecord(name, slug, str(image_path), str(json_path), image_path.is_file())

    def list_zines(self) -> list[ZineRecord]:
        root = self.path_service.zines_path()
        if not root.exists():
            return []
        records = []
        for folder in sorted(item for item in root.iterdir() if item.is_dir() and not item.name.startswith(".")):
            json_path = folder / f"{folder.name}.json"
            if not json_path.is_file():
                continue
            try:
                metadata = json.loads(json_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                metadata = {}
            records.append(self._record(metadata if isinstance(metadata, dict) else {}, json_path))
        return records

    def load_zine(self, slug: str) -> ZineDocument:
        _, _, json_path = self._paths(slug)
        if not json_path.is_file():
            raise ZineServiceError(f"Zine not found: {slug}")
        try:
            metadata = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ZineServiceError(f"Malformed zine JSON: {json_path}") from exc
        if not isinstance(metadata, dict):
            raise ZineServiceError(f"Zine JSON must contain an object: {json_path}")
        self._validate_metadata(metadata, expected_slug=slug)
        return ZineDocument(self._record(metadata, json_path), metadata)

    def story_scene_sources(self, story_slug: str) -> list[ZineSceneSource]:
        sources = []
        for scene in self.story_service.list_scenes(story_slug):
            path = self.story_service.scene_image_path(story_slug, scene.slug)
            if not path.is_file():
                continue
            try:
                with Image.open(path) as image:
                    width, height = image.size
                    image.verify()
            except (OSError, ValueError):
                continue
            sources.append(ZineSceneSource(
                story_slug=story_slug,
                scene_slug=scene.slug,
                title=scene.title,
                tag=f"{{{{SCENE:{story_slug}:{scene.slug}}}}}",
                image_path=str(path),
                width=width,
                height=height,
            ))
        return sources

    def _normalized_metadata(self, payload: dict) -> dict:
        name = str(payload.get("zine_name") or "").strip()
        if not name:
            raise ZineServiceError("Zine name is required.")
        slug = self.safe_slug(name)
        slots_payload = payload.get("slots")
        slots_payload = slots_payload if isinstance(slots_payload, dict) else {}
        slots = {key: str(slots_payload.get(key) or "").strip() for key in SLOT_KEYS}
        guides_payload = payload.get("guides")
        guides_enabled = bool(guides_payload.get("enabled", True)) if isinstance(guides_payload, dict) else True
        return {
            "zine_name": name,
            "zine_slug": slug,
            "output_image": f"{slug}.png",
            "slots": slots,
            "guides": {"enabled": guides_enabled},
        }

    def _validate_metadata(self, metadata: dict, expected_slug: str | None = None) -> None:
        name = str(metadata.get("zine_name") or "").strip()
        slug = str(metadata.get("zine_slug") or "").strip()
        if not name:
            raise ZineServiceError("Zine name is required.")
        if slug != self.safe_slug(name):
            raise ZineServiceError("Zine slug does not match its sanitized name.")
        if expected_slug is not None and slug != expected_slug:
            raise ZineServiceError("Zine JSON slug does not match its folder.")
        if metadata.get("output_image") != f"{slug}.png":
            raise ZineServiceError("Zine output image does not match its slug.")
        slots = metadata.get("slots")
        if not isinstance(slots, dict):
            raise ZineServiceError("Zine slots are required.")
        for key in REQUIRED_SLOT_KEYS:
            if not str(slots.get(key) or "").strip():
                raise ZineServiceError(f"{key.replace('_', ' ').title()} is required.")

    def _page_images(self, metadata: dict) -> dict[str, Image.Image]:
        self._validate_metadata(metadata)
        _, page_margin = self._layout_settings()
        slots = metadata["slots"]
        opened: dict[str, Image.Image] = {}
        try:
            for key in SLOT_KEYS:
                tag = str(slots.get(key) or "").strip()
                if not tag:
                    continue
                reference = self.story_service.story_reference_service.resolve_image_tag(tag)
                path = Path(str(reference.get("path") or ""))
                try:
                    with Image.open(path) as source:
                        source.load()
                        opened[key] = source.copy()
                except (OSError, ValueError) as exc:
                    raise ZineServiceError(f"Unreadable image for {key.replace('_', ' ')}: {path}") from exc
            pages: dict[str, Image.Image] = {}
            for odd_key, even_key in (("page_1", "page_2"), ("page_3", "page_4"), ("page_5", "page_6")):
                if str(slots.get(even_key) or "").strip():
                    pages[odd_key] = make_page_image(opened[odd_key], page_margin)
                    pages[even_key] = make_page_image(opened[even_key], page_margin)
                else:
                    pages[odd_key], pages[even_key] = make_spread_pages(opened[odd_key], page_margin)
            pages["front"] = make_page_image(opened["front"], page_margin)
            pages["back"] = make_page_image(opened["back"], page_margin)
            return pages
        except Exception as exc:
            if isinstance(exc, ZineServiceError):
                raise
            raise ZineServiceError(str(exc)) from exc
        finally:
            for image in opened.values():
                image.close()

    def _render(self, metadata: dict) -> Image.Image:
        pages = self._page_images(metadata)
        try:
            print_scale, _ = self._layout_settings()
            spread_pages = {
                odd_page
                for odd_page in (1, 3, 5)
                if not str(metadata["slots"].get(f"page_{odd_page + 1}") or "").strip()
            }
            assembled = assemble_zine(
                pages,
                bool(metadata.get("guides", {}).get("enabled", True)),
                spread_pages,
            )
            try:
                return scale_and_center_zine(assembled, print_scale)
            finally:
                assembled.close()
        finally:
            for image in pages.values():
                image.close()

    def _write(self, metadata: dict, folder: Path, image: Image.Image | None = None) -> ZineDocument:
        slug = metadata["zine_slug"]
        folder.mkdir(parents=True, exist_ok=True)
        image_path = folder / f"{slug}.png"
        json_path = folder / f"{slug}.json"
        temp_image = folder / f".{slug}.png.tmp"
        temp_json = folder / f".{slug}.json.tmp"
        image = image or self._render(metadata)
        try:
            image.save(temp_image, format="PNG")
            temp_json.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            temp_image.replace(image_path)
            temp_json.replace(json_path)
        finally:
            image.close()
            temp_image.unlink(missing_ok=True)
            temp_json.unlink(missing_ok=True)
        return ZineDocument(self._record(metadata, json_path), metadata)

    def create_zine(self, payload: dict) -> ZineDocument:
        metadata = self._normalized_metadata(payload)
        folder, _, _ = self._paths(metadata["zine_slug"])
        if folder.exists():
            raise ZineServiceError(f"A zine named {metadata['zine_slug']} already exists.")
        self._validate_metadata(metadata)
        image = self._render(metadata)
        return self._write(metadata, folder, image)

    def update_zine(self, current_slug: str, payload: dict) -> ZineDocument:
        current_folder, _, _ = self._paths(current_slug)
        if not current_folder.is_dir():
            raise ZineServiceError(f"Zine not found: {current_slug}")
        current = self.load_zine(current_slug)
        merged = dict(payload)
        if "guides" not in merged:
            merged["guides"] = current.metadata.get("guides", {"enabled": True})
        metadata = self._normalized_metadata(merged)
        new_slug = metadata["zine_slug"]
        new_folder, _, _ = self._paths(new_slug)
        if new_slug != current_slug and new_folder.exists():
            raise ZineServiceError(f"A zine named {new_slug} already exists.")
        image = self._render(metadata)
        if new_slug != current_slug:
            try:
                current_folder.rename(new_folder)
            except Exception:
                image.close()
                raise
            try:
                document = self._write(metadata, new_folder, image)
            except Exception:
                new_folder.rename(current_folder)
                raise
            for path in new_folder.glob(f"{current_slug}.*"):
                path.unlink()
            return document
        return self._write(metadata, new_folder, image)

    def regenerate_zine(self, slug: str) -> ZineDocument:
        document = self.load_zine(slug)
        folder, _, _ = self._paths(slug)
        return self._write(document.metadata, folder)

    def delete_zine(self, slug: str) -> None:
        folder, _, _ = self._paths(slug)
        if not folder.is_dir():
            raise ZineServiceError(f"Zine not found: {slug}")
        shutil.rmtree(folder)
