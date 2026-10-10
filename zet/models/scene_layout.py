"""Typed records for the optional Scene Builder 3D layout."""

from dataclasses import dataclass, field


@dataclass
class ScenePawn:
    element_id: str
    position: tuple[float, float, float]
    dimensions: dict[str, float]
    stature_m: float | None = None
    eye_height_m: float | None = None
    body_yaw: float = 0.0
    head_yaw: float = 0.0
    head_pitch: float = 0.0
    look_at: str = ""
    provisional_height: bool = False
    measurement_overrides: dict[str, str] = field(default_factory=dict)
    measurement_source: str = "provisional"


@dataclass
class SceneCamera:
    id: str = "main"
    name: str = "Main camera"
    position: tuple[float, float, float] = (0.0, 1.68, 8.0)
    target: tuple[float, float, float] = (0.0, 0.99, 0.0)
    vertical_fov: float = 50.0
    background_framing: dict = field(default_factory=lambda: {"center": [0.5, 0.5], "zoom": 1.0})
    ground_distance_m: float | None = None


@dataclass
class SceneLayout3D:
    version: int = 3
    active_camera_id: str = "main"
    pawns: list[ScenePawn] = field(default_factory=list)
    cameras: list[SceneCamera] = field(default_factory=lambda: [SceneCamera()])
    migration_review_required: bool = False
    background: dict | None = None
    migration_notices: list[str] = field(default_factory=list)
    ground: dict = field(default_factory=lambda: {"enabled": True, "surface": "Ground surface matching the setting"})
