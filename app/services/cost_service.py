from __future__ import annotations

import json
from typing import Any

from sqlalchemy import insert, select, update

from app.core.timezone import now_local
from app.db.base import cost_snapshots
from app.db.engine import get_serving_engine
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
    engine = get_serving_engine()
    with engine.begin() as connection:
        rows = connection.execute(
            select(cost_snapshots).order_by(cost_snapshots.c.snapshot_datetime.desc(), cost_snapshots.c.updated_at.desc())
        ).mappings().all()
    history = [_row_to_snapshot(dict(row)) for row in rows]
    snapshot = history[0] if history else {}
    return CostSnapshotResponse(snapshot=snapshot, history=history)


def save_cost_snapshot(snapshot: dict[str, Any]) -> CostSnapshotResponse:
    period = _snapshot_period(snapshot)
    now = now_local()
    payload_json = json.dumps(snapshot, ensure_ascii=False)
    engine = get_serving_engine()
    with engine.begin() as connection:
        existing = connection.execute(
            select(cost_snapshots.c.id).where(cost_snapshots.c.snapshot_period == period)
        ).first()
        if existing:
            connection.execute(
                update(cost_snapshots)
                .where(cost_snapshots.c.snapshot_period == period)
                .values(
                    snapshot_name=str(snapshot.get("snapshot_name") or period),
                    snapshot_datetime=str(snapshot.get("snapshot_datetime") or ""),
                    payload_json=payload_json,
                    updated_at=now,
                )
            )
        else:
            connection.execute(
                insert(cost_snapshots).values(
                    snapshot_period=period,
                    snapshot_name=str(snapshot.get("snapshot_name") or period),
                    snapshot_datetime=str(snapshot.get("snapshot_datetime") or ""),
                    payload_json=payload_json,
                    created_at=now,
                    updated_at=now,
                )
            )
    return get_cost_snapshot_response()
