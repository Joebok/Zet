from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SCENE_TITLES = (
    "Arrival",
    "First Clue",
    "Crossing",
    "Night Watch",
    "The Ambush",
    "Aftermath",
    "The Gate",
    "Homecoming",
)
FIXTURE_IMAGE = b"wp01-reused-fixture-image\n"


@dataclass(frozen=True)
class ReliabilityEntityCounts:
    stories: int
    scenes: int
    main_candidates: int
    subscene_candidates: int
    catalog_images: int
    active_queue_records: int
    completed_queue_records: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class ReliabilityFixture:
    root: Path
    config_path: Path
    story_slug: str
    scene_slugs: tuple[str, ...]
    counts: ReliabilityEntityCounts

    @property
    def dataset_counts(self) -> dict[str, int]:
        return self.counts.to_dict()

    def logical_snapshot(self) -> dict[str, Any]:
        """Return generated data without machine paths or filesystem timestamps."""

        files: list[dict[str, Any]] = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path == self.config_path:
                continue
            relative = path.relative_to(self.root).as_posix()
            if path.suffix == ".json":
                value: Any = json.loads(path.read_text(encoding="utf-8"))
            elif path.suffix in {".md", ".txt"}:
                value = path.read_text(encoding="utf-8")
            else:
                value = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            files.append({"path": relative, "value": value})
        return {
            "story_slug": self.story_slug,
            "scene_order": list(self.scene_slugs),
            "counts": self.dataset_counts,
            "files": files,
        }

    def benchmark_metadata(self, *, scale: int, state: str, concurrent_activity: str) -> dict[str, Any]:
        return {
            "environment": {
                "platform": platform.platform(),
                "python": sys.version.split()[0],
            },
            "dataset_counts": self.dataset_counts,
            "scale": scale,
            "state": state,
            "concurrent_activity": concurrent_activity,
        }


def write_reliability_fixture(root: Path, *, scale: int = 1) -> ReliabilityFixture:
    """Create a deterministic, isolated fixture for WP01 tests and benchmarks."""

    if scale < 1:
        raise ValueError("scale must be at least 1")
    root = Path(root)
    if root.exists() and any(root.iterdir()):
        raise ValueError(f"Fixture root must be empty: {root}")
    root.mkdir(parents=True, exist_ok=True)

    story_slug = "FirstDay"
    scene_slugs = tuple(f"scene-{index:03d}" for index in range(1, 8 * scale + 1))
    scene_titles = tuple(
        SCENE_TITLES[index % len(SCENE_TITLES)]
        + (f" {index // len(SCENE_TITLES) + 1}" if index >= len(SCENE_TITLES) else "")
        for index in range(len(scene_slugs))
    )
    story_dir = root / "Stories" / story_slug
    story_dir.mkdir(parents=True)
    (story_dir / f"{story_slug}.md").write_text(
        "Title: `[First Day]`\n\nA deterministic WP01 story fixture.\n",
        encoding="utf-8",
    )
    (story_dir / f"{story_slug}.story.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "file_kind": "story_settings",
                "story": {"slug": story_slug, "title": "First Day"},
                "scene_index": list(scene_slugs),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    pipeline_root = root / "Pipelines" / "Stories" / story_slug
    for index, (scene_slug, title) in enumerate(zip(scene_slugs, scene_titles), start=1):
        (story_dir / f"{scene_slug}.md").write_text(
            f"Scene: `[{title}]`\n\nScene {index} of the WP01 fixture.\n",
            encoding="utf-8",
        )
        (story_dir / f"{scene_slug}.scene.json").write_text(
            json.dumps(
                {
                    "schema_version": 4,
                    "file_kind": "scene",
                    "scene": {
                        "slug": scene_slug,
                        "name": title,
                        "story_settings_path": f"Stories/{story_slug}/{story_slug}.story.json",
                        "associated_png_path": f"Stories/{story_slug}/{scene_slug}.png",
                    },
                    "setup": {"canvas": {"aspect_ratio": "16:9"}, "environment": {}},
                    "scene_elements": [
                        {
                            "id": "hero",
                            "display_name": "Hero",
                            "element_type": "Character",
                            "fallback_visual_description": "the fixture hero",
                            "subscene_id": "",
                        }
                    ],
                    "placements": [],
                    "subscenes": [
                        {
                            "id": "background",
                            "name": "Background",
                            "kind": "background",
                            "enabled": True,
                            "prompt_overrides": {},
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        scene_pipeline = pipeline_root / scene_slug
        (scene_pipeline / "Candidate").mkdir(parents=True)
        (scene_pipeline / "Candidate" / f"{scene_slug}.png").write_bytes(FIXTURE_IMAGE)
        subscene_pipeline = scene_pipeline / "Subscenes" / "background" / "Candidate"
        subscene_pipeline.mkdir(parents=True)
        (subscene_pipeline / "background.png").write_bytes(FIXTURE_IMAGE)

    auxiliary_image = root / "AuxiliaryResources" / "WP01" / "identity.png"
    auxiliary_image.parent.mkdir(parents=True)
    auxiliary_image.write_bytes(FIXTURE_IMAGE)
    managed_images: dict[str, dict[str, Any]] = {}
    for index in range(1, scale + 1):
        catalog_id = f"img_wp01_{index:03d}"
        managed_images[catalog_id] = {
            "catalog_id": catalog_id,
            "source_key": f"wp01:identity:{index:03d}",
            "label": f"Fixture Identity {index:03d}",
            "image_path": "AuxiliaryResources/WP01/identity.png",
            "mime_type": "image/png",
            "tag": f"{{{{AUX:person:wp01:identity-{index:03d}}}}}",
            "semantic_category": "Person",
            "reference_set_id": "wp01-inherited",
        }
    image_catalog = {
        "schema_version": 2,
        "items": {
            record["source_key"]: {
                "sections": {
                    "identity": {"mode": "inherit", "approved_text": ""},
                    "costume": {"mode": "inherit", "approved_text": ""},
                }
            }
            for record in managed_images.values()
        },
        "managed_images": managed_images,
        "reference_sets": {
            "wp01-inherited": {
                "reference_set_id": "wp01-inherited",
                "label": "WP01 Inherited Metadata",
                "identity_text": "A consistent fixture identity description.",
                "costume_text": "A consistent fixture costume description.",
            }
        },
        "collections": [],
        "keywords": [],
    }
    catalog_path = root / "ImageCatalog" / "ImageCatalog.json"
    catalog_path.parent.mkdir(parents=True)
    catalog_path.write_text(json.dumps(image_catalog, indent=2) + "\n", encoding="utf-8")

    queue_root = root / "Queue" / "Manual_Render_Queue"
    for index in range(1, scale + 1):
        ask_id = f"WP01_ACTIVE_{index:03d}"
        ask_path = queue_root / "Ask" / ask_id
        ask_path.mkdir(parents=True)
        manifest = {
            "version": 1,
            "ask_id": ask_id,
            "asset_id": None,
            "character": "",
            "phase": "",
            "pipeline": "",
            "pipeline_stage": "RENDER",
            "worker_type": "manual_chatgpt_render",
            "prompt_file": "Final_Image_Prompt.md",
            "expected_output": "render.png",
            "task_type": "render",
            "render_preset": "chatgpt-manual",
            "story_slug": story_slug,
            "scene_slug": scene_slugs[index - 1],
            "render_target_id": "main",
            "created_at": "2026-01-01T00:00:00",
        }
        (ask_path / "ask_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        (ask_path / "Final_Image_Prompt.md").write_text("deterministic render prompt\n", encoding="utf-8")

        completed_id = f"WP01_COMPLETED_{index:03d}"
        answer_path = queue_root / "Answer" / completed_id
        answer_path.mkdir(parents=True)
        completed_manifest = {**manifest, "ask_id": completed_id, "scene_slug": scene_slugs[-index]}
        (answer_path / "ask_manifest.json").write_text(
            json.dumps(completed_manifest, indent=2) + "\n", encoding="utf-8"
        )
        (answer_path / "answer_manifest.json").write_text(
            json.dumps(
                {
                    "ask_id": completed_id,
                    "status": "SUCCESS",
                    "expected_output": "render.png",
                    "completed_at": "2026-01-01T00:01:00",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (answer_path / "render.png").write_bytes(FIXTURE_IMAGE)

    config_path = root / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[BaseFolders]",
                f'BaseLibraryPath = "{root.as_posix()}"',
                f'BaseCharacterPath = "{(root / "Characters").as_posix()}"',
                f'BaseAssetPath = "{(root / "Assets").as_posix()}"',
                f'BasePipelinePath = "{(root / "Pipelines").as_posix()}"',
                f'BaseAIQueuePath = "{(root / "Queue").as_posix()}"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    counts = ReliabilityEntityCounts(
        stories=1,
        scenes=len(scene_slugs),
        main_candidates=len(scene_slugs),
        subscene_candidates=len(scene_slugs),
        catalog_images=scale,
        active_queue_records=scale,
        completed_queue_records=scale,
    )
    return ReliabilityFixture(root, config_path, story_slug, scene_slugs, counts)

