import unittest

from app.scripts.seed import SEED_CONTENTS


class SeedPublicContentTests(unittest.TestCase):
    def test_seed_contains_one_minimal_original_tutorial(self):
        self.assertEqual(len(SEED_CONTENTS), 1)

        tutorial = SEED_CONTENTS[0]
        self.assertEqual(tutorial["title"], "GEO 基础检查清单")
        self.assertEqual(tutorial["slug"], "geo-basic-checklist")
        self.assertLessEqual(len(tutorial["markdown_body"]), 400)
        self.assertNotIn("http", tutorial["markdown_body"].lower())
        self.assertNotIn("Wiki", tutorial["markdown_body"])
        self.assertNotIn("白皮书", tutorial["markdown_body"])


if __name__ == "__main__":
    unittest.main()
