from __future__ import annotations

from app.services.research.member_evidence import build_member_http_evidence_chain


def _table_payload(rows: list[dict[str, object]]) -> dict:
    return {
        "retdata": {
            "DataCount": len(rows),
            "Data": rows,
        }
    }


def test_build_member_http_evidence_chain_marks_condition_as_pending() -> None:
    baseline = _table_payload(
        [
            {"VipCardID": "CARD-1", "MobliePhone": "13800000001", "Name": "A"},
            {"VipCardID": "CARD-2", "MobliePhone": "13800000002", "Name": "B"},
        ]
    )
    search_payloads = {
        "exact_search": _table_payload([{"VipCardID": "CARD-1", "MobliePhone": "13800000001", "Name": "A"}]),
        "broad_search": baseline,
        "no_match": _table_payload([]),
    }
    volume_payloads = {
        "1": _table_payload([{"VipCardID": "CARD-1", "MobliePhone": "13800000001", "Name": "A"}]),
        "2": _table_payload([{"VipCardID": "CARD-2", "MobliePhone": "13800000002", "Name": "B"}]),
    }
    condition_payloads = {
        "name": {"errcode": "4000", "errmsg": "syntax error near name"},
        "VipCode": {"errcode": "4000", "errmsg": "syntax error near VipCode"},
    }

    result = build_member_http_evidence_chain(
        member_center_baseline_payload=baseline,
        member_center_search_payloads=search_payloads,
        member_center_volume_payloads=volume_payloads,
        member_center_condition_payloads=condition_payloads,
    )

    member_center = result["member_center"]
    assert member_center["baseline"]["row_count"] == 2
    assert member_center["declared_total_count"] == 2
    assert member_center["full_capture_with_default_query"] is True
    assert member_center["parameter_semantics"]["searchval"]["semantics"] == "data_subset_or_scope_switch"
    assert member_center["parameter_semantics"]["VolumeNumber"]["semantics"] == "scope_or_date_boundary"
    assert member_center["search_behavior"]["exact_match_values"] == ["exact_search"]
    assert member_center["search_behavior"]["zero_match_values"] == ["no_match"]
    assert member_center["condition_probe_summary"]["all_symbolic_values_rejected"] is True
    assert member_center["capture_admission_ready"] is True
    assert member_center["blocking_issues"] == []
    assert "condition 语义仍待确认" in member_center["follow_up_issues"]
    assert result["conclusion"]["member_center_mainline_ready"] is True
    assert "member_condition_semantics_unresolved" in result["issue_flags"]
