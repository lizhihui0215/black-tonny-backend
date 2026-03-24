from __future__ import annotations

from app.crud import (
    analysis_batch_exists,
    capture_batch_exists,
    cost_snapshot_period_exists,
    fetch_capture_database_summary,
    fetch_capture_batch_row,
    fetch_dashboard_summary_source_rows,
    fetch_job_run_row,
    fetch_latest_job_id,
    fetch_latest_analysis_batch_id,
    fetch_payload_cache_rows,
    fetch_serving_database_summary,
    list_capture_endpoint_payload_rows,
    list_job_step_rows,
    insert_analysis_batch_row,
    insert_capture_batch_row,
    insert_capture_endpoint_payload_row,
    insert_cost_snapshot_row,
    insert_job_run_row,
    insert_job_step_row,
    list_cost_snapshot_rows,
    replace_payload_cache_index,
    replace_summary_projection_rows,
    update_analysis_batch_row,
    update_capture_batch_row,
    update_cost_snapshot_row,
    update_job_run_row,
)


def test_capture_crud_exports_are_importable():
    assert callable(capture_batch_exists)
    assert callable(fetch_capture_database_summary)
    assert callable(fetch_capture_batch_row)
    assert callable(fetch_dashboard_summary_source_rows)
    assert callable(fetch_job_run_row)
    assert callable(fetch_latest_analysis_batch_id)
    assert callable(fetch_latest_job_id)
    assert callable(list_cost_snapshot_rows)
    assert callable(list_capture_endpoint_payload_rows)
    assert callable(list_job_step_rows)
    assert callable(insert_capture_batch_row)
    assert callable(update_capture_batch_row)
    assert callable(insert_capture_endpoint_payload_row)
    assert callable(insert_cost_snapshot_row)
    assert callable(insert_job_run_row)
    assert callable(insert_job_step_row)
    assert callable(analysis_batch_exists)
    assert callable(cost_snapshot_period_exists)
    assert callable(insert_analysis_batch_row)
    assert callable(update_analysis_batch_row)
    assert callable(update_cost_snapshot_row)
    assert callable(update_job_run_row)
    assert callable(fetch_payload_cache_rows)
    assert callable(fetch_serving_database_summary)
    assert callable(replace_payload_cache_index)
    assert callable(replace_summary_projection_rows)
