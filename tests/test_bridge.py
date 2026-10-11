"""Packaged-data bridge stays JSON serializable and uses the shared core."""

import json
import unittest

from ambulance.bridge import case_data, preview


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

    def test_unknown_dataset_is_explicit(self):
        with self.assertRaisesRegex(ValueError, "unknown packaged case"):
            case_data("../../other")
