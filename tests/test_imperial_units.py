import unittest

from zet.services.imperial_units import format_feet_inches, meters_to_feet_inches, parse_feet_inches


class ImperialUnitsTests(unittest.TestCase):
    def test_feet_inches_and_conventional_notation(self):
        expected = 68 * 0.0254
        self.assertAlmostEqual(expected, parse_feet_inches("5 ft 8 in"))
        self.assertAlmostEqual(expected, parse_feet_inches("5' 8\""))

    def test_decimal_and_fractional_inches_normalize_and_round_trip(self):
        self.assertAlmostEqual(5.5 * 0.0254, parse_feet_inches("5 1/2 in"))
        self.assertAlmostEqual(12 * 0.0254, parse_feet_inches("0 ft 12 in"))
        self.assertEqual("1 ft 0 in", format_feet_inches(12 * 0.0254))
        self.assertEqual("-0 ft 8 in", format_feet_inches(-8 * 0.0254))
        self.assertEqual("5 ft 6 15/16 in", format_feet_inches(1.7))

    def test_invalid_values_fail_explicitly(self):
        for value in ("five feet", "5 meters", "5 ft 1/0 in"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_feet_inches(value)


if __name__ == "__main__":
    unittest.main()
