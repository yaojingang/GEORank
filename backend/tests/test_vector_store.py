import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qdrant_client.http.exceptions import UnexpectedResponse  # noqa: E402

from app.services.vector_store import VectorStore  # noqa: E402


class _CollectionsResponse:
    def __init__(self, names):
        self.collections = [type("Collection", (), {"name": name}) for name in names]


class _RacingClient:
    def get_collections(self):
        return _CollectionsResponse([])

    def create_collection(self, **_kwargs):
        raise UnexpectedResponse(
            status_code=409,
            reason_phrase="Conflict",
            content=b'{"status":{"error":"Collection already exists"}}',
            headers=None,
        )


class VectorStoreTests(unittest.TestCase):
    def test_ensure_collection_ignores_already_exists_conflict(self):
        store = VectorStore()

        with patch.object(store, "_get_client", return_value=_RacingClient()):
            store.ensure_collection()


if __name__ == "__main__":
    unittest.main()
