from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)


serving_metadata = MetaData()
capture_metadata = MetaData()

# Backward-compatible alias for older imports that still expect `metadata`.
metadata = serving_metadata


job_runs = Table(
    "job_runs",
    serving_metadata,
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
    serving_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("job_id", String(64), nullable=False, index=True),
    Column("title", String(128), nullable=False),
    Column("status", String(32), nullable=False),
    Column("detail", Text, nullable=False, default=""),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

cost_snapshots = Table(
    "cost_snapshots",
    serving_metadata,
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
    serving_metadata,
    Column("page_key", String(32), primary_key=True),
    Column("relative_path", String(256), nullable=False),
    Column("generated_at", String(64), nullable=True),
    Column("analysis_batch_id", String(128), nullable=True),
    Column("store_name", String(128), nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

analysis_batches = Table(
    "analysis_batches",
    serving_metadata,
    Column("analysis_batch_id", String(64), primary_key=True),
    Column("capture_batch_id", String(64), nullable=True, index=True),
    Column("batch_status", String(32), nullable=False, default="queued"),
    Column("source_endpoint", String(128), nullable=True),
    Column("pulled_at", DateTime(timezone=True), nullable=True),
    Column("transformed_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

sales_orders = Table(
    "sales_orders",
    serving_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("analysis_batch_id", String(64), nullable=False, index=True),
    Column("capture_batch_id", String(64), nullable=True, index=True),
    Column("store_id", String(64), nullable=False, index=True),
    Column("order_id", String(64), nullable=False, index=True),
    Column("paid_at", DateTime(timezone=True), nullable=False, index=True),
    Column("paid_amount", Float, nullable=False, default=0),
    Column("payment_status", String(32), nullable=False, default="paid"),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

sales_order_items = Table(
    "sales_order_items",
    serving_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("analysis_batch_id", String(64), nullable=False, index=True),
    Column("capture_batch_id", String(64), nullable=True, index=True),
    Column("order_id", String(64), nullable=False, index=True),
    Column("sku_id", String(64), nullable=False, index=True),
    Column("style_code", String(64), nullable=True, index=True),
    Column("color_code", String(64), nullable=True, index=True),
    Column("size_code", String(64), nullable=True, index=True),
    Column("quantity", Float, nullable=False, default=0),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

inventory_current = Table(
    "inventory_current",
    serving_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("analysis_batch_id", String(64), nullable=False, index=True),
    Column("capture_batch_id", String(64), nullable=True, index=True),
    Column("store_id", String(64), nullable=False, index=True),
    Column("sku_id", String(64), nullable=False, index=True),
    Column("style_code", String(64), nullable=True, index=True),
    Column("color_code", String(64), nullable=True, index=True),
    Column("size_code", String(64), nullable=True, index=True),
    Column("on_hand_qty", Float, nullable=False, default=0),
    Column("safe_stock_qty", Float, nullable=False, default=0),
    Column("season_tag", String(32), nullable=True, index=True),
    Column("is_all_season", Boolean, nullable=False, default=False),
    Column("is_target_size", Boolean, nullable=False, default=True),
    Column("is_active_sale", Boolean, nullable=False, default=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

inventory_daily_snapshot = Table(
    "inventory_daily_snapshot",
    serving_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("analysis_batch_id", String(64), nullable=False, index=True),
    Column("capture_batch_id", String(64), nullable=True, index=True),
    Column("snapshot_date", Date, nullable=False, index=True),
    Column("store_id", String(64), nullable=False, index=True),
    Column("sku_id", String(64), nullable=False, index=True),
    Column("style_code", String(64), nullable=True, index=True),
    Column("color_code", String(64), nullable=True, index=True),
    Column("size_code", String(64), nullable=True, index=True),
    Column("on_hand_qty", Float, nullable=False, default=0),
    Column("safe_stock_qty", Float, nullable=False, default=0),
    Column("season_tag", String(32), nullable=True, index=True),
    Column("is_all_season", Boolean, nullable=False, default=False),
    Column("is_target_size", Boolean, nullable=False, default=True),
    Column("is_active_sale", Boolean, nullable=False, default=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

capture_batches = Table(
    "capture_batches",
    capture_metadata,
    Column("capture_batch_id", String(64), primary_key=True),
    Column("batch_status", String(32), nullable=False, default="queued"),
    Column("source_name", String(128), nullable=False, default="default"),
    Column("pulled_at", DateTime(timezone=True), nullable=True),
    Column("transformed_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("error_message", Text, nullable=True),
)

capture_endpoint_payloads = Table(
    "capture_endpoint_payloads",
    capture_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("capture_batch_id", String(64), nullable=False, index=True),
    Column("source_endpoint", String(128), nullable=False, index=True),
    Column("route_kind", String(32), nullable=True, index=True),
    Column("page_cursor", String(128), nullable=True),
    Column("page_no", Integer, nullable=True),
    Column("request_params", Text, nullable=True),
    Column("payload_json", Text, nullable=False),
    Column("checksum", String(128), nullable=False, index=True),
    Column("pulled_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
