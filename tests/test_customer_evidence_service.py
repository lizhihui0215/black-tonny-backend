from __future__ import annotations

from app.services.research.customer_evidence import build_customer_http_evidence_chain


def _empty_payload() -> dict:
    return {
        "errcode": "1000",
        "retdata": [
            {
                "Count": "0",
                "Data": [{}],
            }
        ],
    }


def test_build_customer_http_evidence_chain_marks_stable_empty_dataset_ready_for_capture() -> None:
    baseline = _empty_payload()

    result = build_customer_http_evidence_chain(
        customer_baseline_payload=baseline,
        customer_page_payloads={
            "1": baseline,
            "2": baseline,
        },
        customer_pagesize_payloads={
            "20": baseline,
            "100": baseline,
        },
        customer_search_payloads={
            "__no_match__": baseline,
            "客户A": baseline,
        },
    )

    customer = result["customer_list"]
    assert customer["baseline"]["row_count"] == 0
    assert customer["parameter_semantics"]["page"]["semantics"] == "same_dataset"
    assert customer["parameter_semantics"]["pagesize"]["semantics"] == "same_dataset"
    assert customer["parameter_semantics"]["deptname"]["semantics"] == "same_dataset"
    assert customer["capture_admission_ready"] is True
    assert customer["capture_parameter_plan"]["page_mode"] == "single_request_stable_empty_verified"
    assert customer["capture_parameter_plan"]["empty_dataset_confirmed"] is True
    assert customer["blocking_issues"] == []
    assert "customer_empty_baseline" in result["issue_flags"]
    assert "customer_stable_empty_dataset_verified" in result["issue_flags"]
    assert result["conclusion"]["customer_mainline_ready"] is True
    assert result["conclusion"]["next_focus"].startswith("当前账号下客户资料已验证为稳定空集")
