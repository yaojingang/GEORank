import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from app.services.company_preview import (
    create_company_preview_token,
    verify_company_preview_token,
)


class CompanyPreviewTokenTests(unittest.TestCase):
    def test_preview_token_is_scoped_to_one_company(self):
        company_id = uuid.uuid4()
        token = create_company_preview_token(company_id)

        self.assertTrue(verify_company_preview_token(token, company_id))
        self.assertFalse(verify_company_preview_token(token, uuid.uuid4()))
        self.assertFalse(verify_company_preview_token("invalid", company_id))

    def test_expired_preview_token_is_rejected(self):
        company_id = uuid.uuid4()
        with patch("app.services.company_preview.datetime") as mocked_datetime:
            mocked_datetime.now.return_value = datetime(2000, 1, 1, tzinfo=timezone.utc)
            token = create_company_preview_token(company_id, ttl_minutes=1)

        self.assertFalse(verify_company_preview_token(token, company_id))


if __name__ == "__main__":
    unittest.main()
