import unittest

from app.services.graph_store import add_entities_and_relations


class GraphStoreContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_unapproved_entity_label_before_opening_session(self):
        with self.assertRaisesRegex(ValueError, "实体类型"):
            await add_entities_and_relations(
                "company-id",
                [{"name": "Injected", "type": "Person`) MATCH (n) DETACH DELETE n //"}],
                [],
            )

    async def test_rejects_unapproved_relationship_type_before_opening_session(self):
        with self.assertRaisesRegex(ValueError, "关系类型"):
            await add_entities_and_relations(
                "company-id",
                [{"name": "Product", "type": "Product"}],
                [{"from": "Company", "to": "Product", "type": "OWNS`] DELETE n //"}],
            )


if __name__ == "__main__":
    unittest.main()
