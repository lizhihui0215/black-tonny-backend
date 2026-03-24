"""Boilerplate-aligned data access package.

This package is the long-term home for persistence and query helpers.
Current runtime code still uses transitional access helpers in flat services.
"""
from app.crud.analysis_batches import (
    analysis_batch_exists,
    insert_analysis_batch_row,
    update_analysis_batch_row,
)
from app.crud.capture_batches import (
    capture_batch_exists,
    fetch_capture_batch_row,
    list_capture_endpoint_payload_rows,
    insert_capture_batch_row,
    insert_capture_endpoint_payload_row,
    update_capture_batch_row,
)
from app.crud.dashboard_summary import (
    fetch_dashboard_summary_source_rows,
    fetch_latest_analysis_batch_id,
)
from app.crud.jobs import (
    fetch_job_run_row,
    fetch_latest_job_id,
    insert_job_run_row,
    insert_job_step_row,
    list_job_step_rows,
    update_job_run_row,
)
from app.crud.cost_snapshots import (
    cost_snapshot_period_exists,
    insert_cost_snapshot_row,
    list_cost_snapshot_rows,
    update_cost_snapshot_row,
)
from app.crud.payload_cache import fetch_payload_cache_rows, replace_payload_cache_index
from app.crud.serving_projections import replace_summary_projection_rows
from app.crud.status_diagnostics import (
    fetch_capture_database_summary,
    fetch_serving_database_summary,
)

__all__ = [
    "analysis_batch_exists",
    "insert_analysis_batch_row",
    "update_analysis_batch_row",
    "capture_batch_exists",
    "fetch_capture_batch_row",
    "fetch_dashboard_summary_source_rows",
    "fetch_latest_analysis_batch_id",
    "list_capture_endpoint_payload_rows",
    "insert_capture_batch_row",
    "insert_capture_endpoint_payload_row",
    "update_capture_batch_row",
    "fetch_job_run_row",
    "fetch_latest_job_id",
    "insert_job_run_row",
    "insert_job_step_row",
    "list_job_step_rows",
    "update_job_run_row",
    "cost_snapshot_period_exists",
    "insert_cost_snapshot_row",
    "list_cost_snapshot_rows",
    "update_cost_snapshot_row",
    "fetch_payload_cache_rows",
    "replace_payload_cache_index",
    "replace_summary_projection_rows",
    "fetch_capture_database_summary",
    "fetch_serving_database_summary",
]
