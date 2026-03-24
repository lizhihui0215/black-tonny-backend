from __future__ import annotations

import json
from typing import Any

from app.core.timezone import now_local
from app.crud import (
    cost_snapshot_period_exists,
    insert_cost_snapshot_row,
    list_cost_snapshot_rows,
    update_cost_snapshot_row,
)
from app.schemas.cost_snapshot import CostSnapshotResponse


def _snapshot_period(snapshot: dict[str, Any]) -> str:
    snapshot_datetime = str(snapshot.get("snapshot_datetime") or "").strip()
    if len(snapshot_datetime) >= 7:
        return snapshot_datetime[:7]
    snapshot_name = str(snapshot.get("snapshot_name") or "").strip()
    if snapshot_name:
        return snapshot_name
    return "unlabeled"


def _row_to_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(row["payload_json"])


def get_cost_snapshot_response() -> CostSnapshotResponse:
    """Boilerplate-aligned runtime implementation for cost snapshot reads."""
    history = [_row_to_snapshot(row) for row in list_cost_snapshot_rows()]
    snapshot = history[0] if history else {}
    return CostSnapshotResponse(snapshot=snapshot, history=history)


def save_cost_snapshot(snapshot: dict[str, Any]) -> CostSnapshotResponse:
    """Boilerplate-aligned runtime implementation for cost snapshot writes."""
    period = _snapshot_period(snapshot)
    now = now_local()
    payload_json = json.dumps(snapshot, ensure_ascii=False)
    if cost_snapshot_period_exists(period):
        update_cost_snapshot_row(
            period,
            snapshot_name=str(snapshot.get("snapshot_name") or period),
            snapshot_datetime=str(snapshot.get("snapshot_datetime") or ""),
            payload_json=payload_json,
            updated_at=now,
        )
    else:
        insert_cost_snapshot_row(
            snapshot_period=period,
            snapshot_name=str(snapshot.get("snapshot_name") or period),
            snapshot_datetime=str(snapshot.get("snapshot_datetime") or ""),
            payload_json=payload_json,
            created_at=now,
            updated_at=now,
        )
    return get_cost_snapshot_response()
