from __future__ import annotations

from app.api import router as api_router
from app.api.v1 import router as v1_router


def test_api_v1_router_is_importable():
    assert v1_router is not None
    assert len(v1_router.routes) > 0


def test_top_level_api_router_is_importable():
    assert api_router is not None
    assert len(api_router.routes) > 0
