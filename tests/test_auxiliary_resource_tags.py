from __future__ import annotations

import unittest

from zet.services.auxiliary_resource_tags import (
    auxiliary_resource_image_for_tag,
    auxiliary_resource_tag,
    auxiliary_resource_tags_in_text,
    parse_auxiliary_resource_tag,
)


class AuxiliaryResourceTagTests(unittest.TestCase):
    def test_matches_the_specific_stored_image(self) -> None:
        tag = "{{AUX:thing:tsaeytte-props:jewelry}}"
        resource, image = auxiliary_resource_image_for_tag(
            [{
                "category": "thing",
                "resource_id": "tsaeytte-props",
                "images": [
                    {"image_id": "skirt", "image_path": "skirt.png"},
                    {"image_id": "jewelry", "image_path": "jewelry.png"},
                ],
            }],
            tag,
        )

        self.assertEqual("tsaeytte-props", resource["resource_id"])
        self.assertEqual("jewelry.png", image["image_path"])
        self.assertEqual(("thing", "tsaeytte-props", "jewelry"), parse_auxiliary_resource_tag(tag))
        self.assertEqual(tag, auxiliary_resource_tag("thing", "tsaeytte-props", "jewelry"))
        self.assertEqual([(tag, "thing", "tsaeytte-props", "jewelry")], auxiliary_resource_tags_in_text(f"{tag}\n{tag}"))

    def test_rejects_retired_three_part_form(self) -> None:
        with self.assertRaises(ValueError):
            parse_auxiliary_resource_tag("{{AUX:thing:tsaeytte-props}}")


if __name__ == "__main__":
    unittest.main()
