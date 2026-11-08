from hashlib import sha256
from pathlib import Path
from uuid import UUID

from Scripts.Compile_Character_Template import MARKER_RE, TemplateCompileError, parse_template_sections_with_sources
from zet.services.atomic_file_service import write_text_atomic
from zet.services.view_conditioning_service import ViewContext, condition_sections

FIELDS = ("appearance", "framing", "directions")
VIEWS = {
    "STYLE": "Style Alignment", "FRONT": "Front",
    "FRONT_LEFT_3_4": "Front Left 3/4", "FRONT_RIGHT_3_4": "Front Right 3/4",
    "LEFT_PROFILE": "Left Profile", "RIGHT_PROFILE": "Right Profile",
}
SHARED = {field: "BODY_" + field.upper() for field in FIELDS}
STYLE_FIELDS = {"style_alignment_changes": "STYLE_ALIGNMENT_CHANGES"}
STYLE_SECTION = STYLE_FIELDS["style_alignment_changes"]
STYLE_BLOCK = "\n## Source-to-reference changes\n\n<!-- ZET:BEGIN STYLE_ALIGNMENT_CHANGES -->\n\n<!-- ZET:END STYLE_ALIGNMENT_CHANGES -->\n"
REFINEMENT = {view: "BODY_REFINEMENT_" + view for view in VIEWS if view != "STYLE"}
REQUIRED = {"NAME", "SOURCE_ASSET_ID", *SHARED.values(), *REFINEMENT.values()}
DEFAULT = Path(__file__).resolve().parents[2] / "Shared_Library/MinorCharacters/_Shared/MinorCharacter_Template.md"


def parse(text, path):
    try:
        sections, sources = parse_template_sections_with_sources(text, path)
    except TemplateCompileError as exc:
        raise ValueError(str(exc)) from exc
    if REQUIRED - sections.keys():
        raise ValueError("Minor Character template is missing sections: " + ", ".join(sorted(REQUIRED - sections.keys())))
    name, asset_id = sections["NAME"], sections["SOURCE_ASSET_ID"]
    if not name.strip() or len(name) > 200 or len(name.splitlines()) != 1:
        raise ValueError("Enter a one-line Minor Character name of up to 200 characters.")
    if asset_id and str(UUID(asset_id)) != asset_id:
        raise ValueError("Enter a canonical Inventory asset ID.")
    sections.setdefault(STYLE_SECTION, "")
    condition_sections({key: sections[key] for key in REQUIRED - {"NAME", "SOURCE_ASSET_ID"}},
                       sources, ViewContext())
    return sections, sources


def replace_sections(text, changes):
    if any(not isinstance(value, str) or "ZET:BEGIN" in value.upper() or "ZET:END" in value.upper()
           for value in changes.values()):
        raise ValueError("Enter text without section boundary markers.")
    if STYLE_SECTION in changes and not any(marker.groups() == ("BEGIN", STYLE_SECTION) for marker in MARKER_RE.finditer(text)):
        text += ("" if text.endswith("\n") else "\n") + STYLE_BLOCK
    starts, replacements = {}, []
    for marker in MARKER_RE.finditer(text):
        kind, key = marker.groups()
        if kind == "BEGIN":
            starts[key] = marker.end()
        elif key in changes:
            replacements.append((starts[key], marker.start(), "\n" + changes[key].strip() + "\n"))
    for start, end, value in reversed(replacements):
        text = text[:start] + value + text[end:]
    return text


def seed(name, asset_id=""):
    text = replace_sections(DEFAULT.read_text(encoding="utf-8"), {"NAME": name, "SOURCE_ASSET_ID": asset_id})
    parse(text, DEFAULT)
    return text


def matches_seed(text, name, asset_id):
    expected = seed(name, asset_id)
    return text in (expected, expected.removesuffix(STYLE_BLOCK))


class MinorCharacterTemplates:
    def __init__(self, universe):
        self.root = Path(universe) / "MinorCharacters"

    def path(self, sid):
        if UUID(hex=sid).hex != sid:
            raise ValueError("Invalid Minor Character ID.")
        path = self.root / sid / "MinorCharacter.md"
        if not path.resolve().is_relative_to(self.root.parent.resolve() / "MinorCharacters"):
            raise ValueError("Minor Character template is outside its universe.")
        return path

    def read(self, sid):
        path = self.path(sid)
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig").replace("\r\n", "\n")
        sections, sources = parse(text, path)
        return text, sha256(raw).hexdigest(), sections, sources

    def write(self, sid, text):
        path = self.path(sid)
        parse(text, path)
        write_text_atomic(path, text)

    @staticmethod
    def compile(sections, sources, view):
        keys = {**SHARED, **STYLE_FIELDS} if view == "STYLE" else {**SHARED, "refinement": REFINEMENT[view]}
        context = ViewContext(unknown_view=True) if view == "STYLE" else ViewContext(view, view)
        compiled, _, _ = condition_sections({key: sections[key] for key in keys.values()}, sources, context)
        return {field: compiled[key] for field, key in keys.items()
                if key != STYLE_SECTION or compiled[key].strip()}
