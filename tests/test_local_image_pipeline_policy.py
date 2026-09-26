from __future__ import annotations

import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from zet.services.local_image_pipeline_policy import (
    front_anchor_approved, local_pipeline_batch_summary, pipeline_page_config,
    resume_cancelled_autogenerate_state, upgrade_legacy_review_v1,
)


class LocalImagePipelinePolicyTests(unittest.TestCase):
    def test_autogenerate_approval_does_not_override_human_rejection(self) -> None:
        candidate = {"human_review": {"decision": "undecided"},
                     "autogenerate_approval": {"approved_at": "2026-09-25T18:43:58"}}
        self.assertTrue(front_anchor_approved(candidate))
        candidate["human_review"]["decision"] = "reject"
        self.assertFalse(front_anchor_approved(candidate))

    def test_reopening_stopped_autogenerate_keeps_completed_front(self) -> None:
        with TemporaryDirectory() as temp:
            image = Path(temp) / "front.png"
            image.write_bytes(b"front")
            run = {"front_anchor": "c001", "candidates": [
                {"candidate_id": "c001", "status": "COMPLETE", "image_path": str(image)},
                {"candidate_id": "c002", "status": "QUEUED", "image_path": str(Path(temp) / "missing.png")},
            ]}
            state = {"status": "CANCELLED", "stop_requested": True, "target_views": ["LEFT_PROFILE"],
                     "candidates": {"c001": {"status": "COMPLETE"}, "c002": {"status": "QUEUED", "ask_id": "old"}}}
            resume_cancelled_autogenerate_state(run, state, ready_status="READY_FOR_VIEWS")
            self.assertEqual("READY_FOR_VIEWS", state["status"])
            self.assertFalse(state["stop_requested"])
            self.assertEqual("COMPLETE", state["candidates"]["c001"]["status"])
            self.assertEqual("PENDING", state["candidates"]["c002"]["status"])
            self.assertEqual("", state["candidates"]["c002"]["ask_id"])
            self.assertEqual([], state["target_views"])

    def test_all_page_configs_share_common_defaults_and_keep_identity_qualifiers(self) -> None:
        pipelines = ("body-reference", "head-image", "character-assembly", "costume-dressing")
        configs = [pipeline_page_config(pipeline) for pipeline in pipelines]

        self.assertEqual([list(config["identity"]) for config in configs], [
            ["character", "phase"], ["character", "phase"], ["character", "phase"],
            ["character", "phase", "costume"],
        ])
        self.assertTrue(all(config["review_version"] == 2 for config in configs))
        self.assertTrue(all((config["front_count"], config["other_count"], config["candidate_limit"]) == (8, 4, 256)
                            for config in configs))
        self.assertTrue(pipeline_page_config("body-reference")["analysis"])
        self.assertFalse(pipeline_page_config("head-image")["analysis"])

    def test_common_batch_summary_labels_known_and_unknown_statuses(self) -> None:
        summary = local_pipeline_batch_summary({
            "status": "AWAITING_FRONT_ANCHOR", "candidate_count": 3,
            "candidates": [{"image_path": "a.png", "status": "GATE_REJECTED"}, {"status": "PENDING"}],
            "selected_views": {"FRONT": "c001"}, "stale_selections": ["BACK"], "error": "needs review",
        })

        self.assertEqual("Awaiting FRONT selection", summary["status_label"])
        self.assertEqual((1, 3, 1, 1), (summary["completed_count"], summary["candidate_count"],
                                         summary["selected_view_count"], summary["gate_rejection_count"]))
        self.assertEqual(["BACK"], summary["stale_selections"])
        self.assertEqual("needs review", summary["error"])
        self.assertEqual("NEW_FUTURE_STATE", local_pipeline_batch_summary({"status": "NEW_FUTURE_STATE"})["status_label"])

    def test_legacy_upgrade_preserves_source_and_marks_unverifiable_results_stale_once(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / "image.png"
            image.write_bytes(b"keep this image")
            spec = {"review_version": 1, "candidates": [{"candidate_id": "c001", "image_path": str(image),
                                                              "gates": {"framing": {"status": "COMPLETE"}}}]}
            state = {"rankings": {"FRONT": {"status": "COMPLETE"}}, "selected_views": {"FRONT": "c001"}}
            (root / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
            (root / "state.json").write_text(json.dumps(state), encoding="utf-8")

            self.assertTrue(upgrade_legacy_review_v1(root, spec, state))
            upgraded_spec = json.loads((root / "spec.json").read_text(encoding="utf-8"))
            upgraded_state = json.loads((root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(2, upgraded_spec["review_version"])
            self.assertEqual("STALE", upgraded_state["rankings"]["FRONT"]["status"])
            self.assertEqual("STALE", upgraded_state["candidates"]["c001"]["gates"]["framing"]["status"])
            self.assertEqual(b"keep this image", image.read_bytes())
            self.assertTrue((root / "legacy_review_v1" / "spec.json").is_file())
            self.assertFalse(upgrade_legacy_review_v1(root, upgraded_spec, upgraded_state))

    def test_legacy_upgrade_waits_while_runner_is_active(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            spec = {"review_version": 1, "candidates": []}
            state = {}
            self.assertFalse(upgrade_legacy_review_v1(root, spec, state, active=True))
            self.assertEqual(1, spec["review_version"])


if __name__ == "__main__":
    unittest.main()
