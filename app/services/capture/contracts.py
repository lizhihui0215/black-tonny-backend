from __future__ import annotations

CAPTURE_BATCH_TABLE_NAME = "capture_batches"
CAPTURE_ENDPOINT_PAYLOAD_TABLE_NAME = "capture_endpoint_payloads"

CAPTURE_BATCH_COLUMNS = (
    "capture_batch_id",
    "batch_status",
    "source_name",
    "pulled_at",
    "transformed_at",
    "created_at",
    "updated_at",
    "error_message",
)

CAPTURE_ENDPOINT_PAYLOAD_COLUMNS = (
    "id",
    "capture_batch_id",
    "source_endpoint",
    "route_kind",
    "page_cursor",
    "page_no",
    "request_params",
    "payload_json",
    "checksum",
    "pulled_at",
    "created_at",
)

CAPTURE_BATCH_STATUS_QUEUED = "queued"
CAPTURE_BATCH_STATUS_CAPTURED = "captured"
CAPTURE_BATCH_STATUS_PARTIAL = "partial"
CAPTURE_BATCH_STATUS_FAILED = "failed"
CAPTURE_BATCH_STATUS_TRANSFORMED = "transformed"

CAPTURE_BATCH_ALLOWED_STATUSES = (
    CAPTURE_BATCH_STATUS_QUEUED,
    CAPTURE_BATCH_STATUS_CAPTURED,
    CAPTURE_BATCH_STATUS_PARTIAL,
    CAPTURE_BATCH_STATUS_FAILED,
    CAPTURE_BATCH_STATUS_TRANSFORMED,
)

CAPTURE_ROUTE_ROLE_VALUES = (
    "mainline_fact",
    "reconciliation",
    "research",
    "snapshot",
    "exclude",
)

CAPTURE_ROUTE_STATUS_VALUES = (
    "ready_for_capture_admission",
    "capture_candidate_blocked",
    "research_before_capture",
    "reconciliation_only",
    "research_capture_only",
    "snapshot_capture_optional",
    "not_planned",
)

CAPTURE_ROUTE_REQUIRED_FIELDS = (
    "domain",
    "route",
    "source_kind",
    "stage",
    "mainline_ready",
    "capture_role",
    "capture_status",
    "capture_route_name",
    "capture_route_confirmed",
    "route_kind",
    "planned_capture_wave",
    "blocking_issues",
    "next_action",
    "capture_written_once",
)
