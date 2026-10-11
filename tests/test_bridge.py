"""Packaged-data bridge stays JSON serializable and uses the shared core."""

import json
import unittest
from base64 import b64decode

from ambulance.bridge import case_data, map_image, preview


class BridgeTests(unittest.TestCase):
    def test_packaged_cases_preview_same_revision_and_full_zone_inputs(self):
        for name, count in [("synthetic", 15), ("caba-comuna4", 252), ("caba", 3552)]:
            with self.subTest(name=name):
                case_json = case_data(name)
                case = json.loads(case_json)
                result = json.loads(preview(case_json))
                self.assertEqual(len(case["zones"]), count)
                self.assertEqual(result["case_id"], case["meta"]["id"])
                self.assertEqual(result["case_revision"], case["meta"]["revision"])
                self.assertEqual(result["exact"]["status"], "ok")

    def test_packaged_map_images_are_bounded_webp_and_styles_are_limited(self):
        for style in ("streets", "satellite"):
            with self.subTest(style=style):
                asset = json.loads(map_image(style))
                self.assertEqual(asset["style"], style)
                self.assertTrue(asset["image"].startswith("data:image/webp;base64,"))
                self.assertEqual(
                    asset["bounds"],
                    {"minX": 11.0, "maxX": 33.0, "minY": 60.0, "maxY": 83.0},
                )
                self.assertTrue(asset["attribution"])
                image = b64decode(asset["image"].split(",", 1)[1])
                self.assertEqual(image[:4], b"RIFF")
                self.assertEqual(image[8:12], b"WEBP")
                self.assertLess(len(image), 2_000_000)
        with self.assertRaisesRegex(ValueError, "unknown map style"):
            map_image("../../other")

    def test_unknown_dataset_is_explicit(self):
        with self.assertRaisesRegex(ValueError, "unknown packaged case"):
            case_data("../../other")
