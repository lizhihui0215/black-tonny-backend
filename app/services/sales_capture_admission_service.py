from __future__ import annotations

import copy
from typing import Any

from app.services.batch_service import append_capture_payload
from app.services.erp_research_service import extract_normalized_table_rows


SALES_DOCUMENTS_HEAD_ENDPOINT = "sales_documents_head"
SALES_DOCUMENT_LINES_ENDPOINT = "sales_document_lines"
SALES_REVERSE_DOCUMENT_LINES_ENDPOINT = "sales_reverse_document_lines"

SALES_HEAD_ROUTE_KIND = "head"
SALES_LINE_ROUTE_KIND = "line"
SALES_REVERSE_ROUTE_KIND = "reverse"


def _normalized_sale_no(value: Any) -> str | None:
    if value in (None, "", "null"):
        return None
    text = str(value).strip()
    return text or None


def _as_float(value: Any) -> float:
    if value in (None, "", "null"):
        return 0.0
    return float(value)


def _build_sign_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    per_sale_no: dict[str, dict[str, set[str]]] = {}
    for row in rows:
        sale_no = _normalized_sale_no(row.get("sale_no"))
        if sale_no is None:
            continue
        bucket = per_sale_no.setdefault(sale_no, {"quantity": set(), "amount": set()})
        quantity = _as_float(row.get("quantity"))
        amount = _as_float(row.get("sales_amount"))
        bucket["quantity"].add("neg" if quantity < 0 else "pos" if quantity > 0 else "zero")
        bucket["amount"].add("neg" if amount < 0 else "pos" if amount > 0 else "zero")

    negative_only = 0
    mixed_sign = 0
    positive_only = 0
    for signs in per_sale_no.values():
        quantity_signs = signs["quantity"]
        amount_signs = signs["amount"]
        if quantity_signs <= {"neg", "zero"} and amount_signs <= {"neg", "zero"} and "neg" in quantity_signs | amount_signs:
            negative_only += 1
        elif quantity_signs <= {"pos", "zero"} and amount_signs <= {"pos", "zero"} and "pos" in quantity_signs | amount_signs:
            positive_only += 1
        else:
            mixed_sign += 1

    return {
        "negative_only_sale_no_count": negative_only,
        "positive_only_sale_no_count": positive_only,
        "mixed_sign_sale_no_count": mixed_sign,
    }


def build_sales_capture_admission_bundle(
    *,
    document_payload: dict[str, Any] | list[Any],
    detail_payload: dict[str, Any] | list[Any],
) -> dict[str, Any]:
    document_rows = extract_normalized_table_rows(document_payload)
    detail_rows = extract_normalized_table_rows(detail_payload)

    head_rows: list[dict[str, Any]] = []
    head_sale_nos: set[str] = set()
    duplicate_sale_no_counts: dict[str, int] = {}
    blank_head_sale_no_count = 0

    for row in document_rows:
        sale_no = _normalized_sale_no(row.get("sale_no"))
        if sale_no is None:
            blank_head_sale_no_count += 1
            continue
        if sale_no in head_sale_nos:
            duplicate_sale_no_counts[sale_no] = duplicate_sale_no_counts.get(sale_no, 1) + 1
        else:
            head_sale_nos.add(sale_no)
        head_rows.append(copy.deepcopy(row))

    normal_line_rows: list[dict[str, Any]] = []
    reverse_line_rows: list[dict[str, Any]] = []
    blank_detail_sale_no_count = 0
    for row in detail_rows:
        sale_no = _normalized_sale_no(row.get("sale_no"))
        if sale_no is None:
            blank_detail_sale_no_count += 1
            reverse_line_rows.append(copy.deepcopy(row))
            continue
        if sale_no in head_sale_nos:
            normal_line_rows.append(copy.deepcopy(row))
        else:
            reverse_line_rows.append(copy.deepcopy(row))

    reverse_sale_nos = {
        sale_no
        for sale_no in (_normalized_sale_no(row.get("sale_no")) for row in reverse_line_rows)
        if sale_no is not None
    }
    sign_summary = _build_sign_summary(reverse_line_rows)

    duplicate_sale_nos = sorted(duplicate_sale_no_counts)
    head_document_uniqueness_ok = not duplicate_sale_nos and blank_head_sale_no_count == 0
    reverse_split_ready = blank_detail_sale_no_count == 0

    reverse_route_blocking_issues: list[str] = []
    if blank_detail_sale_no_count:
        reverse_route_blocking_issues.append(
            f"仍有 {blank_detail_sale_no_count} 行明细缺少 sale_no，逆向路线分流尚未完全稳定"
        )

    capture_admission_ready = head_document_uniqueness_ok and reverse_split_ready

    return {
        "head_document_uniqueness": {
            "head_row_count": len(head_rows),
            "head_unique_sale_no_count": len(head_sale_nos),
            "blank_head_sale_no_count": blank_head_sale_no_count,
            "duplicate_sale_no_count": len(duplicate_sale_nos),
            "duplicate_sale_nos": duplicate_sale_nos[:20],
            "head_document_uniqueness_ok": head_document_uniqueness_ok,
        },
        "route_payloads": {
            SALES_DOCUMENTS_HEAD_ENDPOINT: head_rows,
            SALES_DOCUMENT_LINES_ENDPOINT: normal_line_rows,
            SALES_REVERSE_DOCUMENT_LINES_ENDPOINT: reverse_line_rows,
        },
        "normal_route_summary": {
            "sale_no_count": len({
                sale_no
                for sale_no in (_normalized_sale_no(row.get("sale_no")) for row in normal_line_rows)
                if sale_no is not None
            }),
            "row_count": len(normal_line_rows),
            "quantity_total": sum(_as_float(row.get("quantity")) for row in normal_line_rows),
            "amount_total": sum(_as_float(row.get("sales_amount")) for row in normal_line_rows),
        },
        "reverse_route_summary": {
            "detail_only_sale_no_count": len(reverse_sale_nos),
            "detail_only_row_count": len(reverse_line_rows),
            "blank_detail_sale_no_count": blank_detail_sale_no_count,
            **sign_summary,
            "sample_rows": [
                {
                    "sale_no": row.get("sale_no"),
                    "sale_date": row.get("sale_date"),
                    "style_code": row.get("style_code"),
                    "color": row.get("color"),
                    "size": row.get("size"),
                    "quantity": row.get("quantity"),
                    "sales_amount": row.get("sales_amount"),
                    "operator": row.get("operator"),
                }
                for row in reverse_line_rows[:10]
            ],
        },
        "context_fields": ["sale_date", "operator", "vip_card_no"],
        "reverse_split_ready": reverse_split_ready,
        "capture_admission_ready": capture_admission_ready,
        "reverse_route_blocking_issues": reverse_route_blocking_issues,
    }


def persist_sales_capture_admission_bundle(
    *,
    capture_batch_id: str,
    document_payload: dict[str, Any] | list[Any],
    detail_payload: dict[str, Any] | list[Any],
    document_request_payload: dict[str, Any] | None,
    detail_request_payload: dict[str, Any] | None,
    document_source_endpoint: str,
    detail_source_endpoint: str,
    account_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = build_sales_capture_admission_bundle(
        document_payload=document_payload,
        detail_payload=detail_payload,
    )
    if not bundle["capture_admission_ready"]:
        reasons = []
        head_uniqueness = bundle["head_document_uniqueness"]
        if not head_uniqueness["head_document_uniqueness_ok"]:
            reasons.append("订单头唯一性未通过")
        reasons.extend(bundle["reverse_route_blocking_issues"])
        raise ValueError("销售 capture 准入条件未满足: " + "；".join(reasons))

    append_capture_payload(
        capture_batch_id,
        source_endpoint=document_source_endpoint,
        route_kind="raw",
        payload=document_payload,
        request_params={
            "route_kind": "raw",
            "account_context": account_context,
            "request_payload": document_request_payload,
        },
        page_no=0,
    )
    append_capture_payload(
        capture_batch_id,
        source_endpoint=detail_source_endpoint,
        route_kind="raw",
        payload=detail_payload,
        request_params={
            "route_kind": "raw",
            "account_context": account_context,
            "request_payload": detail_request_payload,
        },
        page_no=1,
    )

    route_payloads = bundle["route_payloads"]
    for page_no, (source_endpoint, route_kind) in enumerate(
        (
            (SALES_DOCUMENTS_HEAD_ENDPOINT, SALES_HEAD_ROUTE_KIND),
            (SALES_DOCUMENT_LINES_ENDPOINT, SALES_LINE_ROUTE_KIND),
            (SALES_REVERSE_DOCUMENT_LINES_ENDPOINT, SALES_REVERSE_ROUTE_KIND),
        ),
        start=10,
    ):
        append_capture_payload(
            capture_batch_id,
            source_endpoint=source_endpoint,
            route_kind=route_kind,
            payload=route_payloads[source_endpoint],
            request_params={
                "route_kind": route_kind,
                "account_context": account_context,
                "upstream_source_endpoint": (
                    document_source_endpoint
                    if route_kind == SALES_HEAD_ROUTE_KIND
                    else detail_source_endpoint
                ),
                "document_request_payload": document_request_payload,
                "detail_request_payload": detail_request_payload,
                "head_document_uniqueness": bundle["head_document_uniqueness"],
                "reverse_route_summary": bundle["reverse_route_summary"],
            },
            page_no=page_no,
        )

    return bundle
