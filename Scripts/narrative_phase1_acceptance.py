"""Create and advance a fresh narrative test story through the real AI_Proxy.

Run with Python 3 from the repository root. --advance harvests completed work
and queues a revised candidate after each initial image. Selection remains in
the dedicated page so the chosen image can be assessed visually.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zet.app import ZetApp
from zet.services.atomic_file_service import write_json_atomic


TITLE = "Narrative Phase 1 Test"
STYLE = "Painterly semi-realistic fantasy illustration, anime-influenced facial stylization, refined linework"
SCENES = [
    ("01 · Arrival", ["Tsaeytte"],
     "Tsaeytte pauses at the academy entrance, holding a rolled parchment in one hand and looking up with quiet wonder.",
     "Full-body three-quarter view, a slight lean back as she looks upward; leave room around her silhouette.",
     "Make her reaction quietly hopeful and relaxed, with the parchment clearly visible at her side."),
    ("02 · The offered parchment", ["Tsaeytte", "Valindia"],
     "Valindia offers a rolled parchment to Tsaeytte, who reaches to accept it with an amused smile. Their attention meets at the handoff.",
     "Tsaeytte at screen-left, Valindia at screen-right, facing inward in opposing three-quarter views. Keep their hands and the parchment visible.",
     "Make the handoff easy to read: one parchment, held between them, with both hands distinct and expressions responding to each other."),
    ("03 · A cutting remark", ["Tsaeytte", "Valindia", "Kaeldor"],
     "Valindia makes a cutting remark to Tsaeytte, who reacts with amused confidence. Kaeldor stands behind them, watching with awkward uncertainty.",
     "Tsaeytte at screen-left, Valindia at screen-right, facing each other. Kaeldor stands farther back in the gap between them, slightly smaller in perspective.",
     "Emphasize the shared instant: Valindia makes a small pointed gesture, Tsaeytte answers with a knowing grin, and Kaeldor watches Valindia uneasily."),
]


def reference(author, name):
    assets = author.library_options(name)
    if not assets:
        raise ValueError(f"No existing reference image found for {name}.")
    def score(asset):
        label = asset["label"].lower()
        return ("front" in label, "3 4" not in label, name.lower() == label)
    return max(assets, key=score)["asset_id"]


def initialize(app):
    author = app.narrative_scene_service
    existing = [item for item in author.stories() if item["title"] == TITLE]
    if existing:
        return existing[0]["id"]
    references = {name: reference(author, name) for name in ("Tsaeytte", "Valindia", "Kaeldor")}
    story = author.create_story({"title": TITLE, "brief": "Three visual experiments at an elven academy: arrival, handoff, and social confrontation."})
    entries = []
    for title, cast, narrative, staging, revision in SCENES:
        scene = author.create_scene(story["id"], {"title": title, "intent": narrative,
            "setting": "Level stone paving outside an elven academy", "camera": "Camera at approximately chest height",
            "perspective": "Natural perspective, consistent character scale on the same ground plane",
            "lighting": "Soft natural daylight from the upper left", "style": STYLE})
        elements = [author.save_element(story["id"], scene["id"], {"name": name, "asset_id": references[name]})["id"] for name in cast]
        if len(cast) < 3:
            elements.append(author.save_element(story["id"], scene["id"], {"name": "Rolled parchment", "kind": "prop", "appearance": "A single small rolled parchment"})["id"])
        subscene = author.create_target(story["id"], scene["id"], {"title": title.split(' · ')[1], "narrative": narrative,
            "staging": staging, "physical_context": "A minimal level stone surface establishes footing. Omit surrounding architecture.", "element_ids": elements})
        backdrop = author.create_target(story["id"], scene["id"], {"title": "Academy courtyard backdrop", "kind": "backdrop",
            "narrative": "An elven academy entrance opening onto a quiet stone courtyard, elegant arches and restrained vegetation, with no people.",
            "staging": "Open paved space in the foreground for later character placement. Do not draw characters.", "physical_context": "Level stone paving"})
        for target, direction in ((subscene, revision), (backdrop, "Give the open foreground paving more clear space and keep the academy entrance readable without adding people.")):
            entries.append({"scene": scene["id"], "target": target["id"], "revision": direction, "stage": "new"})
    write_json_atomic(author.repository.folder(story["id"]) / "acceptance.json", {"entries": entries})
    return story["id"]


def advance(app, story, dispatch, retry_failed=False):
    author, generator = app.narrative_scene_service, app.narrative_generation_service
    path = author.repository.folder(story) / "acceptance.json"
    checkpoint = json.loads(path.read_text(encoding="utf-8"))
    results = []
    for entry in checkpoint["entries"]:
        ids = story, entry["scene"], entry["target"]
        detail = generator.detail(*ids)
        completed = [item for item in detail["candidates"].values() if item["image"]]
        active = any(item["status"] in {"SUBMITTING", "QUEUED", "RUNNING", "DISPATCHING"} for item in detail["jobs"].values())
        if dispatch and entry["stage"] == "new":
            detail = generator.start(*ids, {"action": "generate"})
            entry["stage"] = "initial_queued"
        elif dispatch and entry["stage"] == "initial_queued" and completed and not active:
            author.update_target(*ids, {"staging": detail["staging"] + "\n" + entry["revision"]})
            detail = generator.start(*ids, {"action": "generate"})
            entry["stage"] = "revised_queued"
        elif retry_failed and not active and len(completed) < (2 if entry["stage"] == "revised_queued" else 1) and any(job["status"] == "FAILED" for job in detail["jobs"].values()):
            detail = generator.start(*ids, {"action": "generate"})
        if entry["stage"] == "revised_queued" and len(completed) >= 2:
            entry["stage"] = "ready_for_selection"
        if len(completed) >= 2 and detail["selected_id"]:
            entry["stage"] = "selected"
        results.append({"title": detail["title"], "kind": detail["kind"], "stage": entry["stage"],
            "images": len(completed), "selected": detail["selected_id"],
            "jobs": [{"kind": job["kind"], "status": job["status"], "error": job["error"]} for job in detail["jobs"].values()],
            "page": f"/narrative?universe_id={app.config.universe_id}&story={story}&scene={entry['scene']}&target={entry['target']}"})
    write_json_atomic(path, checkpoint)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--advance", action="store_true", help="Queue initial/revised candidates as work completes")
    parser.add_argument("--retry-failed", action="store_true", help="Retry targets with no completed image and no active work")
    args = parser.parse_args()
    app = ZetApp.from_config(args.config, validate_catalog=False)
    story = initialize(app)
    print(json.dumps({"story_id": story, "targets": advance(app, story, args.advance, args.retry_failed)}, indent=2))


if __name__ == "__main__":
    main()
