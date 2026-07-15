import unittest

from app.services.company_profile import normalize_company_name


class CompanyProfileTests(unittest.TestCase):
    def test_normalize_company_name_removes_marketing_suffixes(self):
        self.assertEqual(
            normalize_company_name("移山科技官网 | GEO优化服务 | AI搜索引擎优化"),
            "移山科技",
        )

    def test_normalize_company_name_preserves_clean_brand_name(self):
        self.assertEqual(
            normalize_company_name("BrightEdge"),
            "BrightEdge",
        )

    def test_normalize_company_name_falls_back_when_primary_empty(self):
        self.assertEqual(
            normalize_company_name("", fallback_name="Narrato"),
            "Narrato",
        )
