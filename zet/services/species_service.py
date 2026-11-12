"""Species definitions shared by character authoring and Body Reference."""
import hashlib
import json
from pathlib import Path
import re

from zet.services.atomic_file_service import read_json, write_json_atomic
from zet.services.view_conditioning_service import VIEW_ORDER
from zet.services.workflow_storage import file_lock


SPECIES_FIELD = re.compile(r"(?im)^(Species|Species / Ancestry|Character Race|Race|Ancestry):[^\S\r\n]*([^\r\n]*)")
SECTION_START = re.compile(r"(?im)^\s*<!--\s*ZET:BEGIN\b")
SPECIES_ORDER = ("species", "character race", "race", "species / ancestry", "ancestry")


def species_value(markdown):
    header = SECTION_START.split(markdown, maxsplit=1)[0]
    values = {m[1].lower(): m[2].strip().strip("`").strip().strip("[]").strip()
              for m in reversed(list(SPECIES_FIELD.finditer(header)))}
    return next((values[label] for label in SPECIES_ORDER if label in values), "")


def set_species(markdown, species_id):
    header = SECTION_START.split(markdown, maxsplit=1)[0]
    first = SPECIES_FIELD.search(header)
    line = f"Species: `{species_id}`"
    if not first:
        return f"{line}\n{markdown}"
    return (SPECIES_FIELD.sub(lambda match: line if match.start() == first.start() else "", header)
            + markdown[len(header):])


def species_key(value):
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


class SpeciesError(ValueError):
    def __init__(self, field, message):
        super().__init__(message)
        self.field = field


class SpeciesConflict(ValueError):
    pass


class SpeciesCatalog:
    def __init__(self, project_root, universe_root=None):
        self.seed = Path(project_root) / "Config" / "Species_Render_Rules.json"
        self.path = Path(universe_root) / "_state" / "Species.json" if universe_root else None

    @staticmethod
    def _lines(value, field, required=False):
        if not isinstance(value, list) or any(
            not isinstance(line, str) or not line.strip() or len(line) > 1000
            or any(ord(char) < 32 for char in line) for line in value
        ) or (required and not value):
            raise SpeciesError(field, "Enter valid text, one entry per line.")
        return [line.strip() for line in value]

    @classmethod
    def _validate(cls, species):
        if not isinstance(species, dict) or "human" not in species:
            raise SpeciesError("id", "The catalog must include Human.")
        names = {}
        result = {}
        for sid, entry in species.items():
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", sid) or len(sid) > 80:
                raise SpeciesError("id", "Use a lowercase Species ID with letters, digits, and hyphens.")
            if not isinstance(entry, dict):
                raise SpeciesError("id", f"{sid} needs a Species definition.")
            label = entry.get("label")
            if (not isinstance(label, str) or not species_key(label) or len(label) > 80
                    or any(ord(char) < 32 for char in label)):
                raise SpeciesError("label", "Enter a display name of at most 80 characters.")
            aliases = cls._lines(entry.get("aliases", []), "aliases")
            for field, name in [("id", sid), ("label", label), *[("aliases", a) for a in aliases]]:
                key = species_key(name)
                if not key or names.setdefault(key, sid) != sid:
                    raise SpeciesError(field, f"'{name}' is invalid or already used by another species.")
            rules = entry.get("body_reference")
            if not isinstance(rules, dict):
                raise SpeciesError("positive", "Enter Body Reference guidance.")
            views = rules.get("view_instructions", {})
            if not isinstance(views, dict) or any(view not in VIEW_ORDER for view in views):
                raise SpeciesError("view_instructions", "Use an existing Body Reference view.")
            result[sid] = {"label": label.strip(), "aliases": aliases, "body_reference": {
                "positive": cls._lines(rules.get("positive"), "positive", required=True),
                "negative": cls._lines(rules.get("negative", []), "negative"),
                "view_instructions": {view: cls._lines(lines, "view_instructions")
                                      for view, lines in views.items()},
            }}
        return result, names

    def load(self):
        source = self.path or self.seed
        try:
            data = read_json(source)
        except FileNotFoundError:
            if source == self.seed:
                raise
            source = self.seed
            data = read_json(source)
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise SpeciesError("catalog", "Unsupported Species catalog version.")
        species, names = self._validate(data.get("species"))
        revision = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        return {"species": species, "revision": revision}, names, source

    def resolve(self, value, *, default=False):
        catalog, names, source = self.load()
        sid = names.get(species_key(value or ("human" if default else "")))
        if not sid:
            raise SpeciesError("species", f"Choose a defined Species in this universe. Unrecognized value: {value or '(empty)'}.")
        return sid, catalog["species"][sid], source

    def save(self, revision, sid, entry, *, create):
        if not isinstance(sid, str) or not isinstance(entry, dict) or not isinstance(create, bool):
            raise SpeciesError("id", "Provide a Species ID and definition.")
        with file_lock(self.path.with_suffix(".lock")):
            current, _, _ = self.load()
            if revision != current["revision"]:
                raise SpeciesConflict("Species changed. Reload the catalog before saving.")
            species = current["species"]
            old = species.get(sid)
            if create == (old is not None):
                raise SpeciesError("id", "That Species ID already exists or is unavailable for editing.")
            if old and old["label"] != entry.get("label"):
                aliases = self._lines(entry.get("aliases", []), "aliases")
                entry = {**entry, "aliases": list(dict.fromkeys([*aliases, old["label"]]))}
            species[sid] = entry
            validated, _ = self._validate(species)
            write_json_atomic(self.path, {"schema_version": 1, "species": validated})
            return self.load()[0]
