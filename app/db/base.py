from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, String, Table, Text


metadata = MetaData()


job_runs = Table(
    "job_runs",
    metadata,
    Column("job_id", String(64), primary_key=True),
    Column("job_type", String(64), nullable=False),
    Column("status", String(32), nullable=False),
    Column("message", Text, nullable=False, default=""),
    Column("sync_mode", String(32), nullable=True),
    Column("sync_start_date", String(32), nullable=True),
    Column("sync_end_date", String(32), nullable=True),
    Column("build_only", Boolean, nullable=False, default=False),
    Column("requested_by", String(128), nullable=False, default="api"),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("last_error", Text, nullable=True),
)

job_steps = Table(
    "job_steps",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("job_id", String(64), nullable=False, index=True),
    Column("title", String(128), nullable=False),
    Column("status", String(32), nullable=False),
    Column("detail", Text, nullable=False, default=""),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

cost_snapshots = Table(
    "cost_snapshots",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("snapshot_period", String(32), nullable=False, unique=True, index=True),
    Column("snapshot_name", String(128), nullable=False),
    Column("snapshot_datetime", String(64), nullable=True),
    Column("payload_json", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

payload_cache_index = Table(
    "payload_cache_index",
    metadata,
    Column("page_key", String(32), primary_key=True),
    Column("relative_path", String(256), nullable=False),
    Column("generated_at", String(64), nullable=True),
    Column("analysis_batch_id", String(128), nullable=True),
    Column("store_name", String(128), nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

