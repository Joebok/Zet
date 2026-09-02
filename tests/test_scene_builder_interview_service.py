import unittest

from zet.services.scene_builder_interview_service import (
    SceneBuilderInterviewError,
    SceneBuilderInterviewService,
)


class ScriptedLlm:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate_json(self, model, system, prompt, schema):
        self.calls.append({"model": model, "system": system, "prompt": prompt, "schema": schema})
        return self.responses.pop(0)


def _element_result(questions=None):
    return {
        "result": {
            "scene_elements": [
                {
                    "display_name": "Mara",
                    "resource_type": "Character",
                    "element_type": "Character",
                    "fallback_visual_description": "A rain-soaked courier in a red coat.",
                    "notes": "Primary subject.",
                },
                {
                    "display_name": "Station platform",
                    "resource_type": "Place",
                    "element_type": "Backdrop",
                    "fallback_visual_description": "An empty elevated railway platform at night.",
                    "notes": "",
                },
            ]
        },
        "questions": questions or [],
    }


class SceneBuilderInterviewServiceTests(unittest.TestCase):
    def _data(self):
        return {
            "schema_version": 4,
            "file_kind": "scene",
            "scene": {"name": "Arrival", "story_beat": ""},
            "setup": {
                "canvas": {"orientation": "landscape", "aspect_ratio": "16:9", "width": None, "height": None},
                "composition": {"focal_point": "", "left_to_right": [], "composition_notes": ""},
                "environment": {},
            },
            "scene_elements": [],
            "placements": [],
            "interactions": [],
            "dialogue": [],
        }

    def test_builds_complete_scene_in_narrow_focused_phases(self):
        llm = ScriptedLlm([
            _element_result(),
            {"result": {"story_beat": "Mara realizes the last train has left her stranded."}, "questions": []},
            {"result": {"orientation": "landscape", "aspect_ratio": "16:9", "width": None, "height": None}, "questions": []},
            {"result": {
                "location": "Elevated railway platform",
                "lighting": "Cold blue station lamps with red signal spill",
                "mood": "Isolated and urgent",
                "weather_or_atmosphere": "Driving rain and fine mist",
                "general_background_notes": "Empty tracks vanish into haze.",
                "general_foreground_notes": "Wet platform reflections frame Mara.",
            }, "questions": []},
            {"result": {
                "focal_point": "Mara beneath the failed departure board",
                "left_to_right": ["Mara"],
                "composition_notes": "Use the empty tracks as leading lines.",
            }, "questions": []},
            {"result": {"placements": [
                {
                    "scene_element_id": "Mara",
                    "position_within_cell": "left",
                    "depth": "midground",
                    "world_position": "beneath the departure board",
                    "frame_coverage": "three-quarter figure",
                    "distance_from_camera": "medium distance",
                    "visual_scale": "large",
                    "pose": {
                        "summary": "stops mid-stride",
                        "temporary_condition": "rain-soaked",
                        "gaze_target_element_id": "",
                        "expression": "shocked realization",
                        "left_arm_action": "holds a satchel close",
                        "right_arm_action": "hangs at her side",
                        "leg_foot_detail": "feet braced on the wet platform",
                        "balance_weight_detail": "weight pitched forward",
                    },
                    "motion": {"state": "stationary", "direction_screen": "", "cue": "coat hem settling"},
                    "placement_notes": "Keep her silhouette clear.",
                },
                {
                    "scene_element_id": "Station_platform",
                    "position_within_cell": "Backdrop",
                    "depth": "background",
                    "world_position": "",
                    "frame_coverage": "full frame",
                    "distance_from_camera": "",
                    "visual_scale": "",
                    "pose": {
                        "summary": "", "temporary_condition": "", "gaze_target_element_id": "", "expression": "",
                        "left_arm_action": "", "right_arm_action": "", "leg_foot_detail": "", "balance_weight_detail": "",
                    },
                    "motion": {"state": "stationary", "direction_screen": "", "cue": ""},
                    "placement_notes": "",
                },
            ]}, "questions": []},
            {"result": {"interactions": [], "dialogue": [], "custom_interactions": ""}, "questions": []},
        ])
        service = SceneBuilderInterviewService("qwen-local", llm)

        payload = service.start("Mara runs onto the rain-soaked platform as the last train disappears.", self._data())
        while not payload["complete"]:
            payload = service.step(payload["session"], {})

        self.assertEqual(len(llm.calls), 7)
        self.assertTrue(all(call["model"] == "qwen-local" for call in llm.calls))
        self.assertEqual(payload["draft"]["scene_elements"][0]["character"], "Mara")
        self.assertEqual(payload["draft"]["scene"]["story_beat"], "Mara realizes the last train has left her stranded.")
        self.assertEqual(payload["draft"]["setup"]["composition"]["left_to_right"], ["Mara"])
        self.assertEqual(payload["draft"]["placements"][1]["position_within_cell"], "")
        self.assertEqual(payload["draft"]["placements"][1]["depth"], "background")

    def test_pauses_for_big_picture_clarification_then_repeats_only_that_phase(self):
        llm = ScriptedLlm([
            _element_result([{"id": "figure_identity", "question": "Is the distant figure an ally, a threat, or intentionally unreadable?"}]),
            _element_result(),
        ])
        service = SceneBuilderInterviewService("qwen-local", llm)

        first = service.start("Mara sees a figure at the far end of the platform.", self._data())
        self.assertEqual(first["phase"], "elements")
        self.assertEqual(len(first["questions"]), 1)

        second = service.step(first["session"], {"figure_identity": "Keep the figure unreadable."})

        self.assertEqual(second["phase"], "story")
        self.assertEqual(len(llm.calls), 2)
        self.assertIn("Keep the figure unreadable.", llm.calls[1]["prompt"])
        self.assertIn("Identify the complete visible cast", llm.calls[1]["prompt"])

    def test_answered_clarification_cannot_repeat_and_block_the_phase(self):
        question = {
            "id": "feather_description",
            "question": "Should the feather be described as a memorial focus or simply a single raven feather?",
        }
        llm = ScriptedLlm([_element_result([question]), _element_result([question])])
        service = SceneBuilderInterviewService("qwen-local", llm)

        first = service.start("A single raven feather serves as Morrow's memorial.", self._data())
        second = service.step(first["session"], {"feather_description": "A single feather."})

        self.assertEqual(second["phase"], "story")
        self.assertEqual(second["questions"], [])
        self.assertEqual(second["completed_phases"], 1)

    def test_requires_narrative_and_all_answers(self):
        service = SceneBuilderInterviewService("qwen-local", ScriptedLlm([]))
        with self.assertRaisesRegex(SceneBuilderInterviewError, "Paste a narrative"):
            service.start("", self._data())

        llm = ScriptedLlm([_element_result([{"id": "who", "question": "Who is present?"}])])
        service = SceneBuilderInterviewService("qwen-local", llm)
        first = service.start("Someone enters.", self._data())
        with self.assertRaisesRegex(SceneBuilderInterviewError, "Answer each"):
            service.step(first["session"], {})



if __name__ == "__main__":
    unittest.main()
