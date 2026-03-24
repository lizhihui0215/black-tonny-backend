from __future__ import annotations

from app.services.research.stored_value_evidence import build_stored_value_http_evidence_chain


def _payload(rows: list[list[object]]) -> dict:
    columns = [
        "HappenDate",
        "HappenNo",
        "VipCardId",
        "VipName",
        "BeginMoney",
        "CashRechargeMoney",
        "StockUseMoney",
        "EndMoney",
    ]
    return {
        "errcode": "1000",
        "retdata": {
            "ColumnsList": columns,
            "Data": rows,
        },
    }


def test_build_stored_value_http_evidence_chain_marks_route_ready_when_half_open_partitions_cover_baseline() -> None:
    baseline = _payload(
        [
            ["2025-09-24 21:03:48", "DOC-1", "CARD-1", "柚柚", 0.0, 2000.0, 0.0, 2000.0],
            ["2025-09-25 10:11:12", "DOC-2", "CARD-2", "阿明", 2000.0, 0.0, 100.0, 1900.0],
            ["2026-03-21 09:00:00", "DOC-3", "CARD-3", "小美", 1900.0, 0.0, 50.0, 1850.0],
        ]
    )
    result = build_stored_value_http_evidence_chain(
        stored_value_baseline_payload=baseline,
        baseline_request_payload={"BeginDate": "20250301", "EndDate": "20260401", "Search": ""},
        stored_value_search_payloads={
            "vip_card_id:CARD-1": _payload(
                [
                    ["2025-09-24 21:03:48", "DOC-1", "CARD-1", "柚柚", 0.0, 2000.0, 0.0, 2000.0],
                ]
            ),
            "vip_card_id:CARD-2": _payload(
                [
                    ["2025-09-25 10:11:12", "DOC-2", "CARD-2", "阿明", 2000.0, 0.0, 100.0, 1900.0],
                ]
            ),
            "happen_no:DOC-1": _payload([]),
            "vip_name:柚柚": _payload([]),
        },
        stored_value_date_window_payloads={
            "single_day_first_row": _payload([]),
            "late_window": _payload(
                [
                    ["2026-03-21 09:00:00", "DOC-3", "CARD-3", "小美", 1900.0, 0.0, 50.0, 1850.0],
                ]
            ),
        },
        stored_value_partition_payloads={
            "q1:20250301_20251001": _payload(
                [
                    ["2025-09-24 21:03:48", "DOC-1", "CARD-1", "柚柚", 0.0, 2000.0, 0.0, 2000.0],
                    ["2025-09-25 10:11:12", "DOC-2", "CARD-2", "阿明", 2000.0, 0.0, 100.0, 1900.0],
                ]
            ),
            "q2:20251001_20260401": _payload(
                [
                    ["2026-03-21 09:00:00", "DOC-3", "CARD-3", "小美", 1900.0, 0.0, 50.0, 1850.0],
                ]
            ),
        },
        date_partition_mode="half_open_end_date",
    )

    detail = result["stored_value_detail"]
    assert detail["baseline"]["row_count"] == 3
    assert detail["parameter_semantics"]["Search"]["semantics"] == "data_subset_or_scope_switch"
    assert detail["parameter_semantics"]["BeginDate_EndDate"]["semantics"] == "data_subset_or_scope_switch"
    assert set(detail["search_behavior"]["supported_search_groups"]) == {"vip_card_id"}
    assert set(detail["search_behavior"]["zero_match_groups"]) == {"happen_no", "vip_name"}
    assert detail["capture_parameter_plan"]["default_Search"] == ""
    assert detail["capture_parameter_plan"]["search_mode"] == "vip_card_only_filter"
    assert detail["capture_parameter_plan"]["page_mode"] == "single_request_half_open_date_verified"
    assert detail["date_partition_verification"]["partition_union_matches_baseline"] is True
    assert detail["date_partition_verification"]["partition_missing_row_count"] == 0
    assert detail["capture_admission_ready"] is True
    assert detail["blocking_issues"] == []


def test_build_stored_value_http_evidence_chain_keeps_hidden_cap_blocker_when_partitions_do_not_cover_baseline() -> None:
    baseline = _payload(
        [
            ["2025-09-24 21:03:48", "DOC-1", "CARD-1", "柚柚", 0.0, 2000.0, 0.0, 2000.0],
            ["2025-09-25 10:11:12", "DOC-2", "CARD-2", "阿明", 2000.0, 0.0, 100.0, 1900.0],
        ]
    )
    result = build_stored_value_http_evidence_chain(
        stored_value_baseline_payload=baseline,
        baseline_request_payload={"BeginDate": "20250301", "EndDate": "20260401", "Search": ""},
        stored_value_search_payloads={
            "__no_match__": _payload([]),
            "vip_card_id:CARD-1": _payload(
                [
                    ["2025-09-24 21:03:48", "DOC-1", "CARD-1", "柚柚", 0.0, 2000.0, 0.0, 2000.0],
                ]
            ),
        },
        stored_value_date_window_payloads={
            "late_window": _payload(
                [
                    ["2025-09-25 10:11:12", "DOC-2", "CARD-2", "阿明", 2000.0, 0.0, 100.0, 1900.0],
                ]
            ),
        },
        stored_value_partition_payloads={
            "q1:20250301_20251001": _payload(
                [
                    ["2025-09-24 21:03:48", "DOC-1", "CARD-1", "柚柚", 0.0, 2000.0, 0.0, 2000.0],
                ]
            ),
        },
        date_partition_mode="half_open_end_date",
    )

    detail = result["stored_value_detail"]
    assert detail["capture_admission_ready"] is False
    assert "尚未确认时间窗口分片与 baseline 的完整覆盖关系" in detail["blocking_issues"]
    assert "尚未确认是否存在隐藏分页或服务端上限" in detail["blocking_issues"]
