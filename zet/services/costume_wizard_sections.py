"""Plain costume facts and their mapping to the existing template."""

import re


SECTIONS = {
    "overview": ("Costume at a glance", "Start with one sentence on silhouette, main layers and dominant colors. Follow with at most two signature garment traits."),
    "upper": ("Upper body and waist", "Describe neckline, sleeves, layer order, fit, waist, closures, materials and trim."),
    "lower": ("Lower body and footwear", "Describe lower garment shape, length, drape, legwear and footwear. Label the footwear bullet Footwear: and use Footwear Contact: only for unusual ground contact."),
    "equipment": ("Equipment, jewelry, and props", "Describe one item per bullet, with attachment point, scale, material and anatomical side when supported. Begin each bullet with Jewelry:, Equipment:, Containers:, Primary weapon/tool:, or Secondary weapon/tool:."),
}
CONTROL = re.compile(r"<!--|-->|ZET\s*:|\{\{|\}\}|^\s*\[|^\s*#|\x60", re.I)
PREFIX = re.compile(r"^(?:[-*+•]|\d+[.)])\s+")
EQUIPMENT_LABEL = re.compile(r"^(?:Jewelry|Equipment|Containers|Primary weapon/tool|Secondary weapon/tool):\s*\S", re.I)


def normalize_lines(text, section):
    lines = [PREFIX.sub("", line.strip()).strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if CONTROL.search(line):
            raise ValueError("Use plain bullets without view tags or template controls.")
        if section == "equipment" and not EQUIPMENT_LABEL.match(line):
            raise ValueError("Start each item with Jewelry:, Equipment:, Containers:, Primary weapon/tool:, or Secondary weapon/tool:.")
    return "\n".join("* " + line for line in lines if line)


def section_prompt(session, section, current="", direction="", render_feedback=False):
    label, guide = SECTIONS[section]
    scope = (
        "Exclude jewelry, removable equipment, and props, including details mentioned in the summary or shown in images. "
        "Keep closures, sewn trim and other integral garment features."
        if section != "equipment" else "Describe removable equipment, jewelry and props only. Exclude integral garment parts."
    )
    captions = "\n".join(f"Image {item['index']}: {item['caption']}" for item in session["images"])
    prompt = (
        f"Draft only the {label} section of a costume template. {guide}\n"
        f"{scope}\n"
        "Use explicit operator direction for intended changes. Use the images only for supported facts. "
        "Omit hidden or uncertain details and incidental styling, wearer traits, pose and background. "
        "Describe stable design facts without camera angles, view-specific visibility, view tags or template controls. "
        "Use the wearer's anatomical side where known. Return one short visual fact per array item, or an empty list if none.\n"
        f"Costume summary: {session['extra_info']}\n{captions}"
    )
    if direction:
        prompt += f"\nCurrent section:\n{current}\nRevision direction: {direction}\nReturn the complete replacement, preserving unrelated facts."
    if render_feedback:
        prompt += "\nThe last attachment is a private test render for comparison, not a design reference."
    return prompt


def template_design(sections):
    lines = {key: value["text"].splitlines() for key, value in sections.items()}
    lower, contact, footwear = [], "", ""
    for line in lines["lower"]:
        key, _, value = line.removeprefix("* ").partition(":")
        if key.casefold() == "footwear contact":
            contact = value.strip()
            continue
        if key.casefold() == "footwear":
            footwear = value.strip()
        lower.append(line)
    summary = lines["overview"]
    facts = list(dict.fromkeys([*summary, *lines["upper"], *lower]))
    signatures = summary[:3] or facts[:1]
    identity = " ".join(line.removeprefix("* ") for line in signatures)
    return {
        "facts": facts, "equipment_facts": lines["equipment"],
        "footwear": footwear, "footwear_contact": contact,
        "identity_rules": ["* Preserve " + line.removeprefix("* ") for line in signatures[1:]] or signatures,
        "scene_identity": identity, "scene_anchors": signatures[1:],
    }
