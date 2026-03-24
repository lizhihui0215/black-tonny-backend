from __future__ import annotations

from app.services.research.member_maintenance_evidence import build_member_maintenance_http_evidence_chain


def _empty_payload() -> dict:
    return {
        "errcode": "1000",
        "retdata": {
            "DataCount": "0",
            "Data": [],
        },
    }


def test_build_member_maintenance_http_evidence_chain_marks_stable_empty_dataset_ready_for_capture() -> None:
    baseline = _empty_payload()

    result = build_member_maintenance_http_evidence_chain(
        member_maintenance_baseline_payload=baseline,
        member_maintenance_page_payloads={
            "page=2,pagesize=20": baseline,
            "page=3,pagesize=20": baseline,
        },
        member_maintenance_pagesize_payloads={
            "page=1,pagesize=50": baseline,
            "page=1,pagesize=5000": baseline,
        },
        member_maintenance_search_payloads={
            "__no_match__": baseline,
            "blank": baseline,
        },
        member_maintenance_type_payloads={
            "消费回访": baseline,
            "其他回访": baseline,
        },
        member_maintenance_bdate_payloads={
            "bdate=20260323,edate=20260323": baseline,
        },
        member_maintenance_brdate_payloads={
            "brdate=20260323,erdate=20260323": baseline,
        },
    )

    maintenance = result["member_maintenance"]
    assert maintenance["baseline"]["row_count"] == 0
    assert maintenance["parameter_semantics"]["page"]["semantics"] == "same_dataset"
    assert maintenance["parameter_semantics"]["pagesize"]["semantics"] == "same_dataset"
    assert maintenance["parameter_semantics"]["search"]["semantics"] == "same_dataset"
    assert maintenance["parameter_semantics"]["type"]["semantics"] == "same_dataset"
    assert maintenance["parameter_semantics"]["bdate/edate"]["semantics"] == "same_dataset"
    assert maintenance["parameter_semantics"]["brdate/erdate"]["semantics"] == "same_dataset"
    assert maintenance["capture_admission_ready"] is True
    assert maintenance["capture_parameter_plan"]["page_mode"] == "single_request_stable_empty_verified"
    assert maintenance["capture_parameter_plan"]["empty_dataset_confirmed"] is True
    assert maintenance["blocking_issues"] == []
    assert "member_maintenance_empty_baseline" in result["issue_flags"]
    assert "member_maintenance_stable_empty_dataset_verified" in result["issue_flags"]
    assert result["conclusion"]["member_maintenance_mainline_ready"] is True
    assert result["conclusion"]["next_focus"].startswith("当前账号下会员维护已验证为稳定空集")
