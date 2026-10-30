"""Shared scene lettering appearance; dimensions use a 1216px reference width."""
from pathlib import Path
import hashlib
import json
import re

DEFAULTS = dict(font_family="Arial", font_size=28, text_color="#000000", shape="rounded", background_color="#ffffff", opacity=1, outline_color="#000000", outline_width=2, padding=12)
FONTS = {
    "Comic Sans MS": ("comic.ttf", "comicbd.ttf", "comici.ttf", "comicz.ttf"),
    "Calibri": ("calibri.ttf", "calibrib.ttf", "calibrii.ttf", "calibriz.ttf"),
    "Cambria": ("cambria.ttc", "cambriab.ttf", "cambriai.ttf", "cambriaz.ttf"),
    "Consolas": ("consola.ttf", "consolab.ttf", "consolai.ttf", "consolaz.ttf"),
    "Segoe UI": ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf"),
    "Trebuchet MS": ("trebuc.ttf", "trebucbd.ttf", "trebucit.ttf", "trebucbi.ttf"),
    "Arial": ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"),
    "Georgia": ("georgia.ttf", "georgiab.ttf", "georgiai.ttf", "georgiaz.ttf"),
    "Verdana": ("verdana.ttf", "verdanab.ttf", "verdanai.ttf", "verdanaz.ttf"),
    "Times New Roman": ("times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf"),
    "Courier New": ("cour.ttf", "courbd.ttf", "couri.ttf", "courbi.ttf"),
}

def available_fonts():
    return [family for family, names in FONTS.items() if all((Path("C:/Windows/Fonts")/name).is_file() for name in names)]

def validate_style(value, partial=False):
    if not isinstance(value, dict) or set(value)-set(DEFAULTS):
        raise ValueError("Unknown scene text style setting.")
    result = {} if partial else dict(DEFAULTS)
    for key, item in value.items():
        if key.endswith("color"):
            if not isinstance(item, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", item):
                raise ValueError(f"{key} requires a six-digit hex color.")
        elif key == "font_family":
            if item not in FONTS or not all((Path("C:/Windows/Fonts")/name).is_file() for name in FONTS[item]):
                raise ValueError("Scene text font is unavailable; choose an installed family with all four faces.")
        elif key == "shape":
            if item not in {"rounded", "rectangle", "ellipse"}: raise ValueError("Unknown bubble shape.")
        else:
            bounds = {"font_size": (6,200), "opacity": (0,1), "outline_width": (0,20), "padding": (0,100)}[key]
            if isinstance(item, bool) or not isinstance(item, (int,float)) or not bounds[0] <= item <= bounds[1]:
                raise ValueError(f"Invalid {key}.")
        result[key] = item
    if not partial and not all((Path("C:/Windows/Fonts")/name).is_file() for name in FONTS[result["font_family"]]):
        raise ValueError("Scene text font is unavailable. Install Arial with regular, bold, italic and bold-italic faces.")
    return result

def effective_style(root, story):
    marker = Path(root)/"universe.json"
    universe = json.loads(marker.read_text(encoding="utf-8")) if marker.is_file() else {}
    return validate_style({**universe.get("scene_text_style", {}), **story.get("scene_text_style_override", {})})

def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
