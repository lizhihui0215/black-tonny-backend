"""Capture-compatibility shim for product evidence helpers."""

from app.services.research.product_evidence import (  # noqa: F401
    build_product_http_evidence_chain,
    extract_declared_total_count,
)
