#!/usr/bin/env python3
"""Private, resumable Tsaeytte head-view experiment; never edits its source batch.

prepare is offline. submit explicitly spends the approved render budget. collect
uses the shared job collector; no provider calls or alternate queue protocol.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from PIL import Image, ImageDraw, ImageFont
from Scripts.Run_Head_Image_Jobs import compile_head_image_job
from zet.services.atomic_file_service import write_json_atomic
from zet.services.config_service import ConfigService
from zet.services.template_source_service import active_revision, template_sources
from zet.services.workflow_storage import file_lock

SEEDS = (48190371, 78193013)
CONFIRMATION_SEEDS = (93810421, 62419783)
EAR = (
    "Show the outside rear surface of each exposed ear: a gently rounded cartilage form "
    "bulging toward the camera, continuous skin across its surface, and a thin edge only "
    "at its silhouette. The ear opening and internal folds lie on the opposite, face-facing "
    "surface and are hidden from this rear camera position. Keep the established long "
    "pointed outline, angled outward and slightly upward, and natural hair overlap at the roots."
)
NECK = (
    "Give her a slim, graceful neck appropriate to her petite adult elven frame, visibly "
    "slimmer than the selected front reference. Preserve a narrow neck shaft beneath the "
    "skull and a gentle transition to sloping shoulders; do not broaden it into a thick "
    "neck or a muscular trapezius wedge. Reference neck width is not a constraint."
)
CAMERAS = {
    "BACK": "Place the camera directly behind her at head height. The skull, ears, neck "
    "and shoulders face directly away together. Show the centered back of the head and nape; "
    "the face, eyes, nose and cheeks are entirely hidden.",
    "BACK_LEFT_3_4": "Place the camera behind her, 45 degrees toward screen-left from "
    "directly behind. Show the rear-left three-quarter head, dominated by the back of the "
    "skull, hair and nape. Only a narrow cheek or jaw edge may appear on screen-left; "
    "no eye is visible. The near ear is foreshortened; the far ear is naturally occluded.",
    "BACK_RIGHT_3_4": "Place the camera behind her, 45 degrees toward screen-right from "
    "directly behind. Show the rear-right three-quarter head, dominated by the back of the "
    "skull, hair and nape. Only a narrow cheek or jaw edge may appear on screen-right; "
    "no eye is visible. The near ear is foreshortened; the far ear is naturally occluded.",
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def configuration(path, library):
    config = ConfigService.load(path)
    # Explicit read-only binding, without app construction/recovery/index startup.
    return replace(config, base_library_path=str(library),
                   base_character_path=str(library / "Characters"),
                   base_asset_path=str(library / "Assets"),
                   base_pipeline_path=str(library / "PipelineCandidates"),
                   universe_id=library.name, universe_is_legacy=False)


def proxy(config):
    from zet.services.ai_proxy_path_service import AIProxyPathService
    from zet.services.ai_proxy_service import AIProxyService
    from zet.services.path_service import PathService
    paths = AIProxyPathService(config)
    return AIProxyService(None, None, PathService(config, PROJECT), None, paths, None)


def silhouette(source, target):
    from zet.services.narrative_assembly_service import NarrativeAssemblyService
    import numpy as np
    with Image.open(source) as image:
        cutout = NarrativeAssemblyService.cutout(image, {
            "cutout": "auto", "tolerance": 25, "strokes": [], "label": "front silhouette"})
    mask = cutout.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
    area = float(np.count_nonzero(np.asarray(mask))) / (mask.width * mask.height)
    if not .1 < area < .85:
        raise ValueError(f"Unusable silhouette foreground area: {area:.3f}")
    result = Image.new("RGB", cutout.size, "white")
    result.paste("black", mask=mask)
    result.save(target)
    mask.save(target.with_name("front-mask.png"))
    return {"foreground_fraction": area, "method": "NarrativeAssemblyService.cutout/auto",
            "tolerance": 25, "threshold": 128, "version": 1}


def revised_template(view, reference, omit="", hair=""):
    guidance = {
        "predecessor": "Image 1 supplies hairstyle and identity evidence from the selected predecessor. "
        "Do not copy its angle or camera-facing inner-ear surfaces.",
        "front": "Image 1 is the selected FRONT identity and hairstyle reference. It is not the target "
        "camera angle. Front facial features become hidden when seen from behind.",
        "silhouette": "Image 1 is a featureless silhouette of the selected FRONT reference. Use it only "
        "as rough outer-shape guidance, not as rear anatomy, exact hair placement, neck width, "
        "a black rendering style or a shape to trace.",
        "none": "Build the character from the following authored identifying details; no image is supplied.",
    }[reference]
    return "\n\n".join(part for part in (
        "# HEAD-IMAGE {{CHARACTER_PHASE}} CHARACTER REFERENCE",
        "Create one clean head reference of {{CHARACTER_NAME}}, {{CHARACTER_PHASE}}.",
        CAMERAS[view],
        "Rotate the skull, hair, attached ears and neck together as one three-dimensional "
        "head. Do not turn the face independently back toward the camera.",
        guidance,
        "She is an adult high elf with warm golden-beige skin, long pointed ears and a "
        "thick black, softly tousled bob. Continue the selected hairstyle around the skull: "
        "retain its color, length, crown and side volume, irregular layered edge and physical "
        "part/sweep. Hair overlaps the ear roots naturally. Do not expose hidden surfaces "
        "merely to display identifying details.",
        hair,
        EAR if omit != "ear" else "",
        NECK if omit != "neck" else "",
        "Show the complete head, hairstyle and neck, with a little upper-shoulder context, "
        "against a plain transparent background. Render in {{LOCAL_STYLE_INSTRUCTION}}.",
    ) if part)


def prepare(args):
    output, batch = args.output.resolve(), args.batch.resolve()
    if output.is_relative_to(batch) or batch.is_relative_to(output):
        raise ValueError("Trial output must be separate from the source batch")
    if (output / "manifest.json").exists():
        raise ValueError("Trial already prepared; use submit/collect/sheet to resume")
    spec, state = read(batch / "spec.json"), read(batch / "state.json")
    if (spec["character"], spec["phase"]) != ("Tsaeytte", "Adult"):
        raise ValueError("This approved pilot is scoped to Tsaeytte Adult")
    library = next(parent for parent in batch.parents if (parent / "universe.json").is_file())
    config = configuration(args.config.resolve(), library)
    output.mkdir(parents=True, exist_ok=True)
    snapshot = output / "snapshot"
    snapshot.mkdir(exist_ok=True)
    protected = {str(batch / name): digest(batch / name) for name in ("state.json", "spec.json")}
    shutil.copy2(batch / "spec.json", snapshot / "spec.json")
    shutil.copy2(batch / "state.json", snapshot / "state.json")
    revision = active_revision(batch)
    write_json_atomic(snapshot / "revision.json", revision)
    copied = {}
    ids = set(state["selected_views"].values()) | {f"B-{i:03d}" for i in range(1, 9)}
    for cid in sorted(ids):
        record = state["candidates"][cid]
        source = library / record["image_path"]
        protected[str(source)] = digest(source)
        target = snapshot / f"{cid}.png"
        shutil.copy2(source, target)
        copied[cid] = target
    extraction = silhouette(copied[state["selected_views"]["FRONT"]], snapshot / "front-silhouette.png")
    profiles_path = config.state_file(PROJECT, "Local_Render_Presets.json")
    profiles = read(profiles_path)
    shutil.copy2(profiles_path, snapshot / "Local_Render_Presets.json")
    shutil.copy2(args.config, snapshot / "config.toml")
    for source in revision["sources"]:
        path = Path(source["source_path"])
        if path.is_file():
            protected[str(path)] = digest(path)
    template_path = PROJECT / "Config/Prompt_Templates/head_image_v2.md"
    template_sources_by_path = {str(Path(s["source_path"]).resolve()): s for s in revision["sources"]}
    original_template = template_sources_by_path[str(template_path.resolve())]["text"]
    manifest = {"version": 1, "source_batch": str(batch), "library": str(library),
                "config": str(args.config.resolve()), "budget": 32, "seeds": SEEDS,
                "protected": protected, "silhouette": extraction,
                "profiles": {k: profiles[k] for k in ("comfyui-qwen-head-image-edit", "comfyui-qwen-head-image-text")},
                "jobs": [], "screening_accepted": None, "confirmation_accepted": None}
    for reference in ("predecessor", "front", "silhouette", "none"):
        for variant in ("current", "revised"):
            recipe = f"{reference}-{variant}"
            directory = output / "recipes" / recipe
            sources = deepcopy(revision["sources"])
            source_view = "BACK_LEFT_3_4" if reference == "predecessor" else "FRONT"
            cid = state["selected_views"][source_view]
            source_path = snapshot / "front-silhouette.png" if reference == "silhouette" else copied[cid]
            references = [] if reference == "none" else [{"role": "head_image_source", "prompt_role": "edit_base",
                "view": source_view, "candidate_id": cid, "path": str(source_path),
                "label": "Featureless FRONT silhouette" if reference == "silhouette" else f"Selected {source_view}",
                "sha256": digest(source_path)}]
            for item in sources:
                if Path(item["source_path"]).resolve() == template_path.resolve():
                    item["text"] = (revised_template("BACK", reference) if variant == "revised" else
                        original_template + ("\nImage 1 is a featureless FRONT silhouette: rough outline "
                        "guidance only, not a rendering style or rear anatomy.\n" if reference == "silhouette" else ""))
            job = {"Job": "HeadQuality_" + recipe, "Task": "head-image", "Character": "Tsaeytte",
                   "Phase": "Adult", "Head View": "BACK", "Body View": "BACK",
                   "Template Path": str(library / "Characters/Tsaeytte/Adult/Character.md"),
                   "Output Directory": str(directory), "Reference Files": references, "Apply Phase Change": False}
            with template_sources(sources):
                compiled = compile_head_image_job(job, PROJECT, pipeline_mode="local", universe_root=library)
            prompt = Path(compiled["final_prompt"]).read_text(encoding="utf-8")
            for seed in SEEDS:
                key = f"screen-{recipe}-{seed}"
                job_dir = output / "renders" / key
                job_dir.mkdir(parents=True)
                prompt_path = job_dir / "Prompt.md"
                prompt_path.write_text("Positive Prompt:\n" + prompt + "\nNegative Prompt:\n", encoding="utf-8")
                manifest["jobs"].append({"id": key, "phase": "screening", "recipe": recipe,
                    "view": "BACK", "seed": seed, "job_id": "HeadQuality_" + hashlib.sha256(str(output).encode()).hexdigest()[:10] + "_" + key,
                    "prompt": str(prompt_path.relative_to(output)), "prompt_sha256": digest(prompt_path),
                    "references": references, "preset": "comfyui-qwen-head-image-edit" if references else "comfyui-qwen-head-image-text",
                    "status": "PREPARED"})
    if any(digest(path) != checksum for path, checksum in protected.items()):
        raise ValueError("Source changed during snapshot; inspect before submitting")
    write_json_atomic(output / "manifest.json", manifest)
    print(json.dumps({"prepared": len(manifest["jobs"]), "output": str(output), "silhouette": extraction}))


def hair_trials(args):
    """Four matched-seed diagnostics addressing Joe's lower-bob feedback."""
    output = args.output.resolve()
    with file_lock(output / "runner.lock"):
        manifest = read(output / "manifest.json")
        if any(item["phase"] == "hair_diagnostic" for item in manifest["jobs"]):
            raise ValueError("Hair diagnostics already prepared; resume with submit/collect")
        if len(manifest["jobs"]) != 16 or not all(item["status"] == "COMPLETE" for item in manifest["jobs"]):
            raise ValueError("Complete the original 16-image screening first")
        library = Path(manifest["library"])
        revision = read(output / "snapshot/revision.json")
        state = read(output / "snapshot/state.json")
        template_path = PROJECT / "Config/Prompt_Templates/head_image_v2.md"
        guide = output / "snapshot/front-silhouette.png"
        reference = {"role": "head_image_source", "prompt_role": "edit_base", "view": "FRONT",
                     "candidate_id": state["selected_views"]["FRONT"], "path": str(guide),
                     "label": "Featureless FRONT silhouette", "sha256": digest(guide)}
        directions = {
            "rounded-nape": (
                "Reconstruct the back of the bob, rather than tracing the front silhouette's "
                "face-framing ends. Its lower hair mass forms a compact, continuous rounded "
                "outline across the nape. The central back hair extends down over the upper "
                "nape, at least as low as the neighboring side sections; it does not rise "
                "into a central gap. Tuck the lower ends gently inward, with only short "
                "soft wisps. Keep a softly tousled surface above that coherent rounded edge."
            ),
            "shallow-u": (
                "The rear bob has a broad shallow U-shaped lower contour: the center at "
                "the nape is slightly lower than the rounded side corners. Hair covers "
                "the upper nape as one continuous mass, then turns gently inward at the "
                "ends. Keep the lower edge compact and softly uneven. Do not form a high "
                "central arch, an inverted V, long hanging side points, outward flips or "
                "separated locks below the bob. The front silhouette's chin-framing shape "
                "is not a template for the rear hairline."
            ),
        }
        for name, hair in directions.items():
            recipe = "silhouette-" + name
            sources = deepcopy(revision["sources"])
            for item in sources:
                if Path(item["source_path"]).resolve() == template_path.resolve():
                    item["text"] = revised_template("BACK", "silhouette", hair=hair)
            directory = output / "recipes" / recipe
            job = {"Job": "HeadQuality_" + recipe, "Task": "head-image", "Character": "Tsaeytte",
                   "Phase": "Adult", "Head View": "BACK", "Body View": "BACK",
                   "Template Path": str(library / "Characters/Tsaeytte/Adult/Character.md"),
                   "Output Directory": str(directory), "Reference Files": [reference], "Apply Phase Change": False}
            with template_sources(sources):
                compiled = compile_head_image_job(job, PROJECT, pipeline_mode="local", universe_root=library)
            prompt = Path(compiled["final_prompt"]).read_text(encoding="utf-8")
            for seed in SEEDS:
                key = f"hair-{name}-{seed}"
                folder = output / "renders" / key
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / "Prompt.md"
                path.write_text("Positive Prompt:\n" + prompt + "\nNegative Prompt:\n", encoding="utf-8")
                manifest["jobs"].append({"id": key, "phase": "hair_diagnostic", "recipe": recipe,
                    "view": "BACK", "seed": seed,
                    "job_id": "HeadQuality_" + hashlib.sha256(str(output).encode()).hexdigest()[:10] + "_" + key,
                    "prompt": str(path.relative_to(output)), "prompt_sha256": digest(path),
                    "references": [deepcopy(reference)], "preset": "comfyui-qwen-head-image-edit", "status": "PREPARED"})
        manifest["screening_accepted"] = "partial; ears and neck improved, lower hair needs correction"
        manifest["human_feedback"] = "Ears and neck are better, especially in seed 1, but lower part of hair is better on existing b-004."
        manifest["diagnostic_allocation"] = "Four lower-hair diagnostics replace the planned ear/neck ablations; twelve confirmation renders remain."
        write_json_atomic(output / "manifest.json", manifest)
        print(json.dumps({"prepared_hair_diagnostics": 4, "total_reserved": len(manifest["jobs"]), "budget": manifest["budget"]}))


def confirmation(args):
    """Freeze the accepted silhouette recipe against each view's real predecessor."""
    output = args.output.resolve()
    with file_lock(output / "runner.lock"):
        manifest = read(output / "manifest.json")
        if any(item["phase"] == "confirmation" for item in manifest["jobs"]):
            raise ValueError("Confirmation already prepared; resume with submit/collect")
        if len(manifest["jobs"]) != 20 or not all(item["status"] == "COMPLETE" for item in manifest["jobs"]):
            raise ValueError("Complete the 20 screening/diagnostic images first")
        if len(manifest["jobs"]) + 12 > manifest["budget"]:
            raise ValueError("Confirmation exceeds the approved render budget")
        library = Path(manifest["library"])
        revision = read(output / "snapshot/revision.json")
        state = read(output / "snapshot/state.json")
        template_path = PROJECT / "Config/Prompt_Templates/head_image_v2.md"
        predecessors = {"BACK": "BACK_LEFT_3_4", "BACK_LEFT_3_4": "LEFT_PROFILE",
                        "BACK_RIGHT_3_4": "RIGHT_PROFILE"}
        for view, predecessor in predecessors.items():
            for variant in ("predecessor-current", "silhouette-revised"):
                sources = deepcopy(revision["sources"])
                if variant == "silhouette-revised":
                    for item in sources:
                        if Path(item["source_path"]).resolve() == template_path.resolve():
                            item["text"] = revised_template(view, "silhouette")
                source_view = "FRONT" if variant == "silhouette-revised" else predecessor
                cid = state["selected_views"][source_view]
                guide = output / "snapshot" / ("front-silhouette.png" if variant == "silhouette-revised" else f"{cid}.png")
                reference = {"role": "head_image_source", "prompt_role": "edit_base", "view": source_view,
                             "candidate_id": cid, "path": str(guide), "sha256": digest(guide),
                             "label": "Featureless FRONT silhouette" if variant == "silhouette-revised" else f"Selected {source_view}"}
                directory = output / "recipes" / f"confirmation-{view}-{variant}"
                job = {"Job": f"HeadQuality_confirm_{view}_{variant}", "Task": "head-image",
                       "Character": "Tsaeytte", "Phase": "Adult", "Head View": view, "Body View": view,
                       "Template Path": str(library / "Characters/Tsaeytte/Adult/Character.md"),
                       "Output Directory": str(directory), "Reference Files": [reference], "Apply Phase Change": False}
                with template_sources(sources):
                    compiled = compile_head_image_job(job, PROJECT, pipeline_mode="local", universe_root=library)
                prompt = Path(compiled["final_prompt"]).read_text(encoding="utf-8")
                for seed in CONFIRMATION_SEEDS:
                    key = f"confirm-{view}-{variant}-{seed}"
                    folder = output / "renders" / key
                    folder.mkdir(parents=True, exist_ok=True)
                    path = folder / "Prompt.md"
                    path.write_text("Positive Prompt:\n" + prompt + "\nNegative Prompt:\n", encoding="utf-8")
                    manifest["jobs"].append({"id": key, "phase": "confirmation", "recipe": variant,
                        "view": view, "seed": seed,
                        "job_id": "HeadQuality_" + hashlib.sha256(str(output).encode()).hexdigest()[:10] + "_" + key,
                        "prompt": str(path.relative_to(output)), "prompt_sha256": digest(path),
                        "references": [deepcopy(reference)], "preset": "comfyui-qwen-head-image-edit", "status": "PREPARED"})
        manifest["screening_accepted"] = True
        manifest["confirmation_direction"] = "I would like to test the silhouette recipe and if necessary we can circle back on the hair."
        manifest["hair_followup"] = "Known lower-bob mismatch deferred by Joe; preserve its record separately from orientation/ear/neck confirmation."
        write_json_atomic(output / "manifest.json", manifest)
        print(json.dumps({"prepared_confirmation": 12, "total_reserved": len(manifest["jobs"]), "budget": manifest["budget"]}))


def advance(args):
    output = args.output.resolve()
    with file_lock(output / "runner.lock"):
        manifest = read(output / "manifest.json")
        if len(manifest["jobs"]) > manifest["budget"]:
            raise ValueError("Trial exceeds approved render budget")
        config = configuration(manifest["config"], Path(manifest["library"]))
        service = proxy(config)
        jobs = service.ai_proxy_path_service.jobs
        if args.command == "collect":
            # The live dashboard has no private trial handler. Serialize with its
            # sweeps and recover only this owner's unsupported-consumer marker.
            coordination = file_lock(jobs.lifecycle.root / "Locks/coordinator.lock")
        else:
            coordination = nullcontext()
        with coordination:
            _advance_jobs(args, output, manifest, service, jobs)


def _advance_jobs(args, output, manifest, service, jobs):
    for item in manifest["jobs"]:
        if item["status"] in {"COMPLETE", "FAILED"}:
            continue
        path = output / item["prompt"]
        if digest(path) != item["prompt_sha256"] or any(digest(ref["path"]) != ref["sha256"] for ref in item["references"]):
            raise ValueError("Frozen trial input changed")
        info = jobs.inspect(item["job_id"])
        # A durable record or any transport/inbox/receipt prevents republishing.
        known = bool(jobs.repository.get(item["job_id"])) or bool(info.get("location"))
        if args.command == "submit" and not known:
            profile = manifest["profiles"][item["preset"]]
            if Path(manifest["config"]).read_bytes() != (output / "snapshot/config.toml").read_bytes():
                raise ValueError("Machine configuration changed since preparation")
            if service.path_service.config.state_file(PROJECT, "Local_Render_Presets.json").read_bytes() != (output / "snapshot/Local_Render_Presets.json").read_bytes():
                raise ValueError("Render profiles changed since preparation")
            item["status"] = "SUBMITTING"
            write_json_atomic(output / "manifest.json", manifest)
            ask_path = service.stage_render_task_local_render_ask({
                "ask_id": item["id"], "transport_job_id": item["job_id"], "ad_hoc_child_index": 0,
                "character": "Tsaeytte", "phase": "Adult", "pipeline": "Head reference quality trial",
                "workflow": "Head reference quality trial"}, path, path.parent,
                allow_parallel=True, seed=item["seed"], checkpoint=profile["diffusion_model"],
                render_preset=item["preset"], image_generation="comfyui", reference_files=item["references"],
                consumer="zet-head-quality-trial")
            for name in ("ask_manifest.json", "ai_request.json", "ComfyUI_Workflow_API.json", "ComfyUI_Compilation_Debug.json"):
                if (ask_path / name).is_file():
                    shutil.copy2(ask_path / name, path.parent / name)
            item["status"] = "QUEUED"
        if args.command == "collect":
            target = path.parent / "result.png"
            try:
                record = jobs.repository.get(item["job_id"])
                if (record.get("harvest_state") == "HARVEST_FAILED"
                        and record.get("error") == "No registered result handler for zet-head-quality-trial; result retained"
                        and record.get("consumer") == "zet-head-quality-trial"
                        and record.get("manifest", {}).get("source_ask_id") == item["id"]):
                    jobs.repository.update(item["job_id"], harvest_state="AWAITING_HARVEST", error="")
                if target.is_file() or jobs.copy_result(item["job_id"], target, image=True):
                    item.update(status="COMPLETE", image=str(target.relative_to(output)), image_sha256=digest(target))
                else:
                    item["status"] = jobs.inspect(item["job_id"])["status"] if known else "PREPARED"
            except Exception as exc:
                from zet.services.ai_job_service import AIExecutionError
                # Collection failures can be resumed, but failed execution
                # never silently spends another render from the budget.
                item.update(status="FAILED" if isinstance(exc, AIExecutionError) else "COLLECTION_ERROR", error=str(exc))
        write_json_atomic(output / "manifest.json", manifest)
    counts = {}
    for item in manifest["jobs"]:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    print(json.dumps(counts))


def sheet(args):
    output = args.output.resolve()
    manifest = read(output / "manifest.json")
    phase = getattr(args, "phase", "all")
    items = [item for item in manifest["jobs"] if phase == "all" or item["phase"] == phase]
    if not items:
        raise ValueError("No images prepared for the selected phase")
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 16)
    width, height = 280, 310
    canvas = Image.new("RGB", (width * 4, height * ((len(items) + 3) // 4)), "#eeeeee")
    draw = ImageDraw.Draw(canvas)
    for index, item in enumerate(items):
        x, y = index % 4 * width, index // 4 * height
        draw.text((x + 5, y + 3), f"{index+1}: {item['recipe']}", fill="black", font=font)
        draw.text((x + 5, y + 23), f"{item['view']} / {item['seed']}", fill="black", font=font)
        if item.get("image"):
            with Image.open(output / item["image"]) as source:
                image = source.convert("RGB")
                image.thumbnail((width, height - 45))
                canvas.paste(image, (x + (width-image.width)//2, y+45))
        else:
            draw.text((x+10, y+80), item["status"], fill="black", font=font)
    filename = "screening.jpg" if phase == "all" else phase + ".jpg"
    canvas.save(output / filename, quality=95)
    print(output / filename)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "hair-trials", "confirmation", "submit", "collect", "sheet"))
    parser.add_argument("--config", type=Path, default=PROJECT / "config.toml")
    parser.add_argument("--batch", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=("all", "screening", "hair_diagnostic", "confirmation"), default="all")
    args = parser.parse_args()
    if args.command == "prepare":
        if not args.batch:
            parser.error("prepare requires --batch")
        prepare(args)
    elif args.command == "sheet":
        sheet(args)
    elif args.command == "hair-trials":
        hair_trials(args)
    elif args.command == "confirmation":
        confirmation(args)
    else:
        advance(args)


if __name__ == "__main__":
    main()
