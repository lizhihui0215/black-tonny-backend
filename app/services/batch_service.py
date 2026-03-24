from __future__ import annotations

import json
from hashlib import sha256
from typing import Any
from uuid import uuid4

from app.core.timezone import now_local
from app.crud import (
    analysis_batch_exists,
    capture_batch_exists,
    insert_analysis_batch_row,
    insert_capture_batch_row,
    insert_capture_endpoint_payload_row,
    update_analysis_batch_row,
    update_capture_batch_row,
)
from app.services.capture.contracts import (
    CAPTURE_BATCH_ALLOWED_STATUSES,
    CAPTURE_BATCH_STATUS_QUEUED,
)


def create_capture_batch(source_name: str = "default", capture_batch_id: str | None = None) -> str:
    batch_id = capture_batch_id or uuid4().hex
    now = now_local()
    if not capture_batch_exists(batch_id):
        insert_capture_batch_row(
            capture_batch_id=batch_id,
            batch_status=CAPTURE_BATCH_STATUS_QUEUED,
            source_name=source_name,
            pulled_at=None,
            transformed_at=None,
            created_at=now,
            updated_at=now,
            error_message=None,
        )
    return batch_id


def update_capture_batch(
    capture_batch_id: str,
    *,
    batch_status: str,
    pulled_at=None,
    transformed_at=None,
    error_message: str | None = None,
) -> None:
    if batch_status not in CAPTURE_BATCH_ALLOWED_STATUSES:
        raise ValueError(f"Unsupported capture batch status: {batch_status}")
    values: dict[str, Any] = {
        "batch_status": batch_status,
        "updated_at": now_local(),
        "error_message": error_message,
    }
    if pulled_at is not None:
        values["pulled_at"] = pulled_at
    if transformed_at is not None:
        values["transformed_at"] = transformed_at

    update_capture_batch_row(capture_batch_id, **values)


def append_capture_payload(
    capture_batch_id: str,
    *,
    source_endpoint: str,
    route_kind: str | None = None,
    payload: dict[str, Any] | list[Any],
    request_params: dict[str, Any] | None = None,
    page_cursor: str | None = None,
    page_no: int | None = None,
) -> None:
    now = now_local()
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    request_params_json = (
        json.dumps(request_params, ensure_ascii=False, sort_keys=True) if request_params is not None else None
    )
    checksum = sha256(payload_json.encode("utf-8")).hexdigest()
    insert_capture_endpoint_payload_row(
        capture_batch_id=capture_batch_id,
        source_endpoint=source_endpoint,
        route_kind=route_kind,
        page_cursor=page_cursor,
        page_no=page_no,
        request_params=request_params_json,
        payload_json=payload_json,
        checksum=checksum,
        pulled_at=now,
        created_at=now,
    )


def upsert_analysis_batch(
    analysis_batch_id: str,
    *,
    capture_batch_id: str | None = None,
    batch_status: str = "success",
    source_endpoint: str | None = None,
    pulled_at=None,
    transformed_at=None,
) -> None:
    now = now_local()
    values = {
        "capture_batch_id": capture_batch_id,
        "batch_status": batch_status,
        "source_endpoint": source_endpoint,
        "pulled_at": pulled_at,
        "transformed_at": transformed_at,
        "updated_at": now,
    }
    if not analysis_batch_exists(analysis_batch_id):
        insert_analysis_batch_row(
            analysis_batch_id=analysis_batch_id,
            created_at=now,
            **values,
        )
    else:
        update_analysis_batch_row(analysis_batch_id, **values)
