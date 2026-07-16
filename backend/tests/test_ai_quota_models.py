import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.ai_usage import (  # noqa: E402
    AICreditWallet,
    AIGlobalDailyBudget,
    AIPrincipalDevice,
    AIPrincipalUser,
    AIQuotaAuditLog,
    AIQuotaPrincipal,
    AITokenReservation,
    AIUsageEvent,
)


class AiQuotaModelContractTests(unittest.TestCase):
    def test_quota_v2_tables_are_registered(self):
        self.assertEqual(AIQuotaPrincipal.__tablename__, "ai_quota_principals")
        self.assertEqual(AIPrincipalUser.__tablename__, "ai_principal_users")
        self.assertEqual(AIPrincipalDevice.__tablename__, "ai_principal_devices")
        self.assertEqual(AICreditWallet.__tablename__, "ai_credit_wallets")
        self.assertEqual(AIGlobalDailyBudget.__tablename__, "ai_global_daily_budgets")
        self.assertEqual(AITokenReservation.__tablename__, "ai_token_reservations")
        self.assertEqual(AIQuotaAuditLog.__tablename__, "ai_quota_audit_logs")

    def test_wallet_and_budget_have_consumed_and_reserved_counters(self):
        wallet_columns = AICreditWallet.__table__.columns
        budget_columns = AIGlobalDailyBudget.__table__.columns

        self.assertIn("granted_tokens", wallet_columns)
        self.assertIn("consumed_tokens", wallet_columns)
        self.assertIn("reserved_tokens", wallet_columns)
        self.assertIn("limit_tokens", budget_columns)
        self.assertIn("consumed_tokens", budget_columns)
        self.assertIn("reserved_tokens", budget_columns)

    def test_usage_events_link_to_principal_and_reservation(self):
        columns = AIUsageEvent.__table__.columns

        self.assertIn("principal_id", columns)
        self.assertIn("reservation_id", columns)


if __name__ == "__main__":
    unittest.main()
