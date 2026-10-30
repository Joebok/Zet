"""Narrative animation authoring, source snapshots and timeline resolution."""
from __future__ import annotations
import base64
import copy
import hashlib
import json
import math
import re
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageChops

from zet.services.atomic_file_service import write_bytes_atomic, write_json_atomic
from zet.services.scene_text_render_service import render
from zet.services.narrative_scene_text_service import finished_path
from zet.services.scene_text_style_service import effective_style
from zet.models.story_animation import ResolvedAnimation


EASINGS = {"linear", "ease-in-out", "step"}
TRANSITIONS = {"cut", "dissolve", "fade-through-black"}


def normalize_durations(spec):
    """Clamp numeric timing values without accepting malformed instruction shapes."""
    result=copy.deepcopy(spec)
    if not isinstance(result, dict) or not isinstance(result.get("shots"), list): return result
    for shot in result["shots"]:
        if not isinstance(shot, dict): continue
        duration=shot.get("duration_ms")
        if isinstance(duration, bool) or not isinstance(duration,(int,float)) or not math.isfinite(duration): continue
        duration=max(1,min(9007199254740991,round(duration)))
        shot["duration_ms"]=duration
        tracks=[shot.get("camera")]
        if isinstance(shot.get("text"),dict): tracks.extend(shot["text"].values())
        for keys in tracks:
            if not isinstance(keys,list): continue
            normalized=[]
            for key in keys:
                if not isinstance(key,dict): normalized.append(key); continue
                t=key.get("time_ms")
                if isinstance(t,bool) or not isinstance(t,(int,float)) or not math.isfinite(t): normalized.append(key); continue
                key["time_ms"]=max(0,min(duration,round(t)))
                if normalized and isinstance(normalized[-1],dict) and normalized[-1].get("time_ms")==key["time_ms"]: normalized[-1]=key
                else: normalized.append(key)
            keys[:]=normalized
    for i,shot in enumerate(result["shots"]):
        if not isinstance(shot,dict): continue
        tr=shot.get("transition")
        if not isinstance(tr,dict) or tr.get("type","cut")=="cut": continue
        overlap=tr.get("duration_ms",0); duration=shot.get("duration_ms")
        if isinstance(overlap,bool) or not isinstance(overlap,(int,float)) or not math.isfinite(overlap) or not isinstance(duration,int): continue
        previous=result["shots"][i-1].get("transition",{}).get("duration_ms",0) if i and isinstance(result["shots"][i-1],dict) and isinstance(result["shots"][i-1].get("transition",{}),dict) else 0
        if not isinstance(previous,int) or isinstance(previous,bool): continue
        next_duration=result["shots"][i+1].get("duration_ms",duration) if i+1<len(result["shots"]) and isinstance(result["shots"][i+1],dict) else duration
        if not isinstance(next_duration,int) or isinstance(next_duration,bool): continue
        limit=min(duration-previous,next_duration)
        if limit<1: shot["transition"]={"type":"cut","duration_ms":0}
        else: tr["duration_ms"]=max(1,min(limit,round(overlap)))
    return result


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number.")


def validate_spec(spec: dict) -> dict:
    if not isinstance(spec, dict) or spec.get("version") != 1:
        raise ValueError("Animation specification version 1 is required.")
    if set(spec) - {"version", "name", "aspect_ratio", "shots"}:
        raise ValueError("Animation instructions contain unsupported fields.")
    if not isinstance(spec.get("name"), str) or not spec["name"].strip():
        raise ValueError("Animation name is required.")
    ratio = spec.get("aspect_ratio", "16:9")
    if not isinstance(ratio, str) or not re.fullmatch(r"\d+(?:\.\d+)?:\d+(?:\.\d+)?", ratio):
        raise ValueError("Aspect ratio must use width:height form.")
    a, b = (float(part) for part in ratio.split(":"))
    if min(a, b) <= 0 or a / b > 8 or b / a > 8:
        raise ValueError("Aspect ratio is outside the supported range.")
    shots = spec.get("shots")
    if not isinstance(shots, list) or len(shots) > 256:
        raise ValueError("Shots must be a list of at most 256 entries.")
    ids = set()
    for shot in shots:
        if not isinstance(shot, dict) or not isinstance(shot.get("id"), str) or not shot["id"] or shot["id"] in ids:
            raise ValueError("Every shot needs a unique ID.")
        if set(shot) - {"id", "source_id", "duration_ms", "camera", "camera_mode", "text", "transition"}:
            raise ValueError("Shot contains unsupported instruction fields.")
        if shot.get("camera_mode", "center") not in {"center", "target"}:
            raise ValueError("Unsupported camera mode.")
        ids.add(shot["id"])
        if not isinstance(shot.get("source_id"), str) or not shot["source_id"]:
            raise ValueError("Every shot needs a pinned source ID.")
        duration = shot.get("duration_ms")
        if isinstance(duration, bool) or not isinstance(duration, int) or duration < 1:
            raise ValueError("Shot duration must be a positive integer in milliseconds.")
        transition = shot.get("transition", {"type": "cut", "duration_ms": 0})
        if not isinstance(transition, dict) or transition.get("type", "cut") not in TRANSITIONS:
            raise ValueError("Unsupported shot transition.")
        overlap = transition.get("duration_ms", 0)
        if isinstance(overlap, bool) or not isinstance(overlap, int) or overlap < 0:
            raise ValueError("Transition duration must be a nonnegative integer.")
        if transition.get("type", "cut") == "cut" and overlap:
            raise ValueError("Cut transitions must have zero duration.")
        if transition.get("type", "cut") != "cut" and overlap < 1:
            raise ValueError("Dissolves and fades need a positive duration.")
        for track, default_easing in (("camera", "linear"),):
            keys = shot.get(track, [])
            if not isinstance(keys, list): raise ValueError("Camera keyframes must be a list.")
            previous = -1
            for key in keys:
                if not isinstance(key, dict): raise ValueError("Invalid camera keyframe.")
                t = key.get("time_ms")
                if isinstance(t, bool) or not isinstance(t, int) or t < 0 or t > duration or t <= previous: raise ValueError("Camera keyframe times must increase within the shot.")
                previous = t
                for field in ("x", "y", "zoom"): _finite(key.get(field), f"Camera {field}")
                if not (0 <= key["x"] <= 1 and 0 <= key["y"] <= 1 and key["zoom"] >= 1): raise ValueError("Camera center must be normalized and zoom must be at least 1.")
                if key.get("easing", default_easing) not in EASINGS - {"step"}: raise ValueError("Unsupported camera easing.")
        text_tracks = shot.get("text", {})
        if not isinstance(text_tracks, dict): raise ValueError("Text tracks must be keyed by entry ID.")
        for keys in text_tracks.values():
            if not isinstance(keys, list): raise ValueError("Text keyframes must be a list.")
            previous = -1
            for key in keys:
                t = key.get("time_ms"); opacity = key.get("opacity")
                if isinstance(t, bool) or not isinstance(t, int) or t < 0 or t > duration or t <= previous: raise ValueError("Text keyframe times must increase within the shot.")
                previous = t; _finite(opacity, "Text opacity")
                if not 0 <= opacity <= 1 or key.get("easing", "linear") not in EASINGS: raise ValueError("Text opacity/easing is invalid.")
    for index, shot in enumerate(shots[:-1]):
        overlap = shot.get("transition", {}).get("duration_ms", 0)
        if overlap > shot["duration_ms"] or overlap > shots[index+1]["duration_ms"]:
            raise ValueError("Transition overlap cannot exceed either adjoining shot.")
    for index in range(1, len(shots)-1):
        if shots[index-1].get("transition", {}).get("duration_ms", 0) + shots[index].get("transition", {}).get("duration_ms", 0) > shots[index]["duration_ms"]:
            raise ValueError("Transitions cannot overlap three shots at once.")
    return spec


def _state(keys, t, fields, defaults):
    if not keys: return defaults
    if t <= keys[0]["time_ms"]: return {k: keys[0][k] for k in fields}
    if t >= keys[-1]["time_ms"]: return {k: keys[-1][k] for k in fields}
    for left, right in zip(keys, keys[1:]):
        if left["time_ms"] <= t <= right["time_ms"]:
            u=(t-left["time_ms"])/(right["time_ms"]-left["time_ms"])
            easing=left.get("easing", "linear")
            if easing == "ease-in-out": u=u*u*(3-2*u)
            if easing == "step": u=0
            return {k: left[k]+(right[k]-left[k])*u for k in fields}
    return defaults


def resolve_animation(spec: dict, pinned_assets: dict[str, dict]) -> ResolvedAnimation:
    validate_spec(spec); cursor=0; resolved=[]
    for index, shot in enumerate(spec["shots"]):
        if shot["source_id"] not in pinned_assets: raise ValueError(f"Pinned source {shot['source_id']} is missing.")
        transition=shot.get("transition", {"type":"cut", "duration_ms":0}); overlap=transition.get("duration_ms",0) if index < len(spec["shots"])-1 else 0
        resolved.append({**shot, "start_ms":cursor, "end_ms":cursor+shot["duration_ms"], "transition":transition})
        cursor += shot["duration_ms"]-overlap
    return ResolvedAnimation(spec["name"], *(float(x) for x in spec.get("aspect_ratio","16:9").split(":")), cursor, tuple(resolved), pinned_assets)


class StoryAnimationService:
    def __init__(self, author): self.author=author; self.repository=author.repository
    def folder(self, story, animation):
        self.repository.read(story)
        path=(self.repository.folder(story)/"animations"/animation).resolve()
        if not path.is_relative_to(self.repository.folder(story).resolve()): raise ValueError("Invalid animation ID.")
        return path
    def list(self, story):
        root=self.repository.folder(story)/"animations"
        return [self.read(story,p.name,include_assets=False) for p in sorted(root.iterdir()) if p.is_dir()] if root.is_dir() else []
    def create(self, story, data):
        name=str(data.get("name") or "Animation").strip()
        if not name: raise ValueError("Animation name is required.")
        animation=uuid4().hex; folder=self.folder(story,animation); folder.mkdir(parents=True)
        spec={"version":1,"name":name,"aspect_ratio":data.get("aspect_ratio","16:9"),"shots":[]}
        validate_spec(spec); write_json_atomic(folder/"spec.json",{"revision":0,"spec":spec,"assets":{},"interviews":[]})
        return self.read(story,animation)
    def read(self, story, animation, include_assets=True):
        folder=self.folder(story,animation); data=json.loads((folder/"spec.json").read_text(encoding="utf-8"))
        if include_assets:
            fallback=effective_style(self.repository.library_root,self.repository.read(story))
            def presentation_style(value):
                if value.get("text_style"): return value["text_style"]
                try:
                    scene, target, candidate = value["source_id"].split(":")
                    final=self.repository.read(story,scene,target)["candidates"][candidate]["scene_text_final"]
                    if final.get("entries") != value.get("text_entries"): return fallback
                    style=final["style"]
                    for entry in final["entries"]:
                        layer, errors=render((value["width"],value["height"]),[entry],final["placements"],style)
                        with Image.open(folder/value["text_layers"][entry["id"]]) as pinned:
                            difference=ImageChops.difference(layer.convert("RGBA"),pinned.convert("RGBA"))
                            if errors or any(channel.getbbox() for channel in difference.split()): return fallback
                    return style
                except (KeyError, ValueError, OSError): return fallback
            data["assets"]={key:{**value,"text_style":presentation_style(value),"artwork_data_url":self._url(folder/value["artwork"]),"text_data_urls":{k:self._url(folder/v) for k,v in value.get("text_layers",{}).items()}} for key,value in data["assets"].items()}
        return {**data, "id": animation}
    @staticmethod
    def _url(path):
        raw=Path(path).read_bytes(); return "data:image/png;base64,"+base64.b64encode(raw).decode()
    def save(self, story, animation, data):
        with self.repository.lock():
            folder=self.folder(story,animation); current=json.loads((folder/"spec.json").read_text(encoding="utf-8"))
            if data.get("revision")!=current["revision"]: raise ValueError("Animation changed; reload before saving.")
            spec=normalize_durations(data.get("spec")); validate_spec(spec)
            if any(shot["source_id"] not in current["assets"] for shot in spec["shots"]): raise ValueError("A shot references a source not pinned to this animation.")
            current.update(spec=spec,revision=current["revision"]+1)
            write_json_atomic(folder/"spec.json",current); return self.read(story,animation)
    def sources(self, story):
        result=[]
        for scene_id in self.repository.read(story)["scene_ids"]:
            scene=self.repository.read(story,scene_id)
            for target_id in scene["target_ids"]:
                target=self.repository.read(story,scene_id,target_id)
                if target["kind"]!="assembly": continue
                for candidate_id,item in target["candidates"].items():
                    if not item.get("locked"): continue
                    try: image=finished_path(self.repository,story,scene_id,target_id,candidate_id)
                    except (FileNotFoundError,KeyError): continue
                    result.append({"id":f"{scene_id}:{target_id}:{candidate_id}","scene_id":scene_id,"target_id":target_id,"candidate_id":candidate_id,"title":scene["title"],"image":str(image),"lettered":bool(item.get("scene_text_final")),"text_entries":item.get("scene_text_final",{}).get("entries",[])})
        return result
    def bind(self, story, animation, data):
        source=next((x for x in self.sources(story) if x["id"]==data.get("source_id")),None)
        if not source: raise ValueError("Choose an available locked final assembly.")
        folder=self.folder(story,animation); original=self.repository.folder(story,source["scene_id"],source["target_id"])/self.repository.read(story,source["scene_id"],source["target_id"])["candidates"][source["candidate_id"]]["image"]
        target=self.repository.read(story,source["scene_id"],source["target_id"]); candidate=target["candidates"][source["candidate_id"]]
        asset_id=hashlib.sha256((source["id"]+hashlib.sha256(original.read_bytes()).hexdigest()).encode()).hexdigest()
        art_name=asset_id+".png"; write_bytes_atomic(folder/art_name,original.read_bytes())
        layers={}; entries=[]; final=candidate.get("scene_text_final",{})
        if final:
            entries=final.get("entries",[]); placements=final.get("placements",{}); style=final.get("style",{})
            with Image.open(original) as img: size=img.size; base=img.convert("RGBA")
            for entry in entries:
                overlay,errors=render(size,[entry],placements,style)
                if errors: raise ValueError("Confirmed text cannot be reconstructed: "+"; ".join(x["message"] for x in errors))
                from io import BytesIO
                output=BytesIO(); overlay.save(output,"PNG")
                filename=asset_id+"-"+entry["id"]+".png"; write_bytes_atomic(folder/filename,output.getvalue()); layers[entry["id"]]=filename; base.alpha_composite(overlay)
            with Image.open(finished_path(self.repository,story,source["scene_id"],source["target_id"],source["candidate_id"])) as expected:
                actual=base.convert("RGBA")
                if expected.size!=actual.size or ImageChops.difference(expected.convert("RGBA"),actual).getbbox(): raise ValueError("Confirmed lettering layers do not reproduce the locked finished image; independent fades are unavailable.")
        asset={"id":asset_id,"source_id":source["id"],"title":source["title"],"artwork":art_name,"text_layers":layers,"text_entries":entries,"text_style":final.get("style",{}),"width":Image.open(original).width,"height":Image.open(original).height,"sha256":hashlib.sha256(original.read_bytes()).hexdigest(),"lettering_separable":bool(final)}
        with self.repository.lock():
            doc=json.loads((folder/"spec.json").read_text(encoding="utf-8")); doc["assets"][asset_id]=asset; doc["revision"]+=1; write_json_atomic(folder/"spec.json",doc)
        return self.read(story,animation)
