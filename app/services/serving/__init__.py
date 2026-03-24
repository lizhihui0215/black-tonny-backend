"""Boilerplate-aligned serving orchestration package."""
from app.services.serving.transform import transform_capture_batch_to_serving

__all__ = ["transform_capture_batch_to_serving"]
