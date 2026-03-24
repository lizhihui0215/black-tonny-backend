from __future__ import annotations

"""Capture compatibility shim for the moved route registry implementation."""

from app.services.capture.route_registry import (
    CAPTURE_ROLE_LABELS,
    CAPTURE_STATUS_LABELS,
    build_capture_route_registry,
    build_capture_route_registry_from_board,
    render_capture_route_registry_markdown,
)

__all__ = [
    "CAPTURE_ROLE_LABELS",
    "CAPTURE_STATUS_LABELS",
    "build_capture_route_registry",
    "build_capture_route_registry_from_board",
    "render_capture_route_registry_markdown",
]
