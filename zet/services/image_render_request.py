"""Immutable handoff from a pipeline Asset to a Candidate Board renderer."""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ImageRenderRequest:
    universe_id: str
    target_id: str
    candidate_id: str
    prompt: str
    inputs: tuple[dict, ...]
    settings: dict
    seed: int
    provenance: dict

    def to_dict(self) -> dict:
        request = asdict(self)
        request["inputs"] = [dict(item) for item in self.inputs]
        return request

    @classmethod
    def from_dict(cls, value: dict):
        return cls(universe_id=value["universe_id"], target_id=value["target_id"],
                   candidate_id=value["candidate_id"], prompt=value["prompt"],
                   inputs=tuple(dict(item) for item in value.get("inputs", [])),
                   settings=dict(value["settings"]), seed=value["seed"],
                   provenance=dict(value.get("provenance", {})))
