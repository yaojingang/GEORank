import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.navigation_settings import (  # noqa: E402
    NavigationMenuValidationError,
    get_default_navigation_menu,
    normalize_navigation_menu_payload,
)


class NavigationSettingsTests(unittest.TestCase):
    def test_default_menu_uses_new_tab(self):
        menu = get_default_navigation_menu()

        self.assertGreaterEqual(len(menu["items"]), 8)
        self.assertTrue(all(item["target"] == "_blank" for item in menu["items"]))
        self.assertEqual(menu["items"][0]["url"], "/companies")

    def test_normalizer_preserves_order_and_supported_targets(self):
        menu = normalize_navigation_menu_payload(
            {
                "items": [
                    {"id": "docs", "label": "文档", "url": "https://docs.example.com", "target": "_blank"},
                    {"id": "about", "label": "关于", "url": "/about", "target": "_self", "enabled": False},
                ]
            }
        )

        self.assertEqual([item["id"] for item in menu["items"]], ["docs", "about"])
        self.assertEqual(menu["items"][0]["target"], "_blank")
        self.assertEqual(menu["items"][1]["target"], "_self")
        self.assertFalse(menu["items"][1]["enabled"])

    def test_normalizer_defaults_missing_target_to_new_tab(self):
        menu = normalize_navigation_menu_payload(
            {"items": [{"label": "首页", "url": "/"}]}
        )

        self.assertEqual(menu["items"][0]["target"], "_blank")

    def test_normalizer_rejects_unsafe_urls(self):
        with self.assertRaisesRegex(NavigationMenuValidationError, "HTTP"):
            normalize_navigation_menu_payload(
                {"items": [{"label": "危险链接", "url": "javascript:alert(1)"}]}
            )


if __name__ == "__main__":
    unittest.main()
