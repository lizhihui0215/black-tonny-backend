from __future__ import annotations

from app.services.runtime import (
    add_job_step,
    authenticate_owner,
    build_frontend_user_info,
    create_rebuild_job,
    get_assistant_chat_response,
    get_cost_snapshot_response,
    get_dashboard_summary_response,
    get_frontend_access_codes,
    get_job,
    get_latest_job,
    get_manifest,
    get_page_payload,
    get_status,
    render_homepage,
    save_cost_snapshot,
    update_job,
)


def test_runtime_wrappers_are_importable():
    assert callable(add_job_step)
    assert callable(authenticate_owner)
    assert callable(build_frontend_user_info)
    assert callable(create_rebuild_job)
    assert callable(get_assistant_chat_response)
    assert callable(get_cost_snapshot_response)
    assert callable(get_dashboard_summary_response)
    assert callable(get_frontend_access_codes)
    assert callable(get_job)
    assert callable(get_latest_job)
    assert callable(get_manifest)
    assert callable(get_page_payload)
    assert callable(get_status)
    assert callable(render_homepage)
    assert callable(save_cost_snapshot)
    assert callable(update_job)
