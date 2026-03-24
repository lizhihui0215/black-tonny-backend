from __future__ import annotations

from app.services.serving import transform_capture_batch_to_serving


def test_serving_transform_wrapper_is_importable():
    assert callable(transform_capture_batch_to_serving)
