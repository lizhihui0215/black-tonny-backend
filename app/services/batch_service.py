from __future__ import annotations

import json
from hashlib import sha256
from typing import Any
from uuid import uuid4

from sqlalchemy import insert, select, update

from app.core.timezone import now_local
from app.db.base import analysis_batches, capture_batches, capture_endpoint_payloads
from app.db.engine import get_capture_engine, get_serving_engine


def create_capture_batch(source_name: str = "default", capture_batch_id: str | None = None) -> str:
    batch_id = capture_batch_id or uuid4().hex
    now = now_local()
    engine = get_capture_engine()
    with engine.begin() as connection:
        existing = connection.execute(
            select(capture_batches.c.capture_batch_id).where(capture_batches.c.capture_batch_id == batch_id)
        ).first()
        if existing is None:
            connection.execute(
                insert(capture_batches).values(
                    capture_batch_id=batch_id,
                    batch_status="queued",
                    source_name=source_name,
                    pulled_at=None,
                    transformed_at=None,
                    created_at=now,
                    updated_at=now,
                    error_message=None,
                )
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
    engine = get_capture_engine()
    values: dict[str, Any] = {
        "batch_status": batch_status,
        "updated_at": now_local(),
        "error_message": error_message,
    }
    if pulled_at is not None:
        values["pulled_at"] = pulled_at
    if transformed_at is not None:
        values["transformed_at"] = transformed_at

    with engine.begin() as connection:
        connection.execute(
            update(capture_batches)
            .where(capture_batches.c.capture_batch_id == capture_batch_id)
            .values(**values)
        )


def append_capture_payload(
    capture_batch_id: str,
    *,
    source_endpoint: str,
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
    engine = get_capture_engine()
    with engine.begin() as connection:
        connection.execute(
            insert(capture_endpoint_payloads).values(
                capture_batch_id=capture_batch_id,
                source_endpoint=source_endpoint,
                page_cursor=page_cursor,
                page_no=page_no,
                request_params=request_params_json,
                payload_json=payload_json,
                checksum=checksum,
                pulled_at=now,
                created_at=now,
            )
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
    engine = get_serving_engine()
    with engine.begin() as connection:
        existing = connection.execute(
            select(analysis_batches.c.analysis_batch_id).where(
                analysis_batches.c.analysis_batch_id == analysis_batch_id
            )
        ).first()
        values = {
            "capture_batch_id": capture_batch_id,
            "batch_status": batch_status,
            "source_endpoint": source_endpoint,
            "pulled_at": pulled_at,
            "transformed_at": transformed_at,
            "updated_at": now,
        }
        if existing is None:
            connection.execute(
                insert(analysis_batches).values(
                    analysis_batch_id=analysis_batch_id,
                    created_at=now,
                    **values,
                )
            )
        else:
            connection.execute(
                update(analysis_batches)
                .where(analysis_batches.c.analysis_batch_id == analysis_batch_id)
                .values(**values)
            )
