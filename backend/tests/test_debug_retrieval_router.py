from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from main import app
from modules.auth_guard import get_current_user


client = TestClient(app)


class _FakeNumpyScalar:
    __module__ = "numpy"

    def __init__(self, value):
        self._value = value

    def item(self):
        return self._value


def _owner_user():
    return {"user_id": "owner-1", "tenant_id": "tenant-1", "role": "owner"}


def test_debug_retrieval_normalizes_numpy_like_scalars():
    app.dependency_overrides[get_current_user] = _owner_user

    async def _fake_retrieve_context(*_args, **_kwargs):
        return [
            {
                "text": "chunk",
                "source_id": "source-1",
                "score": _FakeNumpyScalar(0.91),
                "meta": {"confidence": _FakeNumpyScalar(0.82)},
            }
        ]

    try:
        with patch("routers.debug_retrieval.verify_twin_ownership"), patch(
            "routers.debug_retrieval.ensure_twin_active"
        ), patch(
            "routers.debug_retrieval.retrieve_context", _fake_retrieve_context
        ), patch(
            "routers.debug_retrieval.supabase"
        ) as supabase_mock, patch(
            "modules.access_groups.get_default_group", new=AsyncMock(return_value={"id": "group-1"})
        ):
            supabase_mock.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
                {"id": "source-1", "filename": "doc.pdf"}
            ]

            resp = client.post(
                "/debug/retrieval",
                json={"query": "test", "twin_id": "twin-1", "top_k": 3},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["results_count"] == 1
            assert body["contexts"][0]["score"] == 0.91
            assert body["contexts"][0]["meta"]["confidence"] == 0.82
            assert body["contexts"][0]["source_filename"] == "doc.pdf"
    finally:
        app.dependency_overrides = {}
