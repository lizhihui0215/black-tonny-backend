from __future__ import annotations

from app.services.research.receipt_confirmation_evidence import (
    build_receipt_confirmation_http_evidence_chain,
)


def _payload(doc_nos: list[str]) -> dict:
    return {
        "Data": [
            {"DocNo": doc_no, "DeptName": "A店", "TotalAmount": 1}
            for doc_no in doc_nos
        ]
    }


def test_build_receipt_confirmation_http_evidence_chain_marks_hidden_context_pending() -> None:
    baseline = _payload(["DOC-1", "DOC-2"])

    result = build_receipt_confirmation_http_evidence_chain(
        baseline_payload=baseline,
        page_payloads={
            "page=1,pagesize=20": baseline,
            "page=2,pagesize=20": baseline,
        },
        page_size_payloads={
            "page=1,pagesize=20": baseline,
            "page=1,pagesize=5000": baseline,
        },
        time_payloads={
            "time=20260323": baseline,
            "time=''": baseline,
        },
        search_payloads={
            "search=DOC-1": baseline,
            "__no_match__": baseline,
        },
    )

    receipt = result["receipt_confirmation"]
    assert receipt["baseline"]["row_count"] == 2
    assert receipt["observed_doc_numbers"] == ["DOC-1", "DOC-2"]
    assert receipt["parameter_semantics"]["page"]["semantics"] == "same_dataset"
    assert receipt["parameter_semantics"]["pageSize"]["semantics"] == "same_dataset"
    assert receipt["parameter_semantics"]["time"]["semantics"] == "same_dataset"
    assert receipt["parameter_semantics"]["search"]["semantics"] == "same_dataset"
    assert receipt["capture_admission_ready"] is True
    assert receipt["blocking_issues"] == []
    assert receipt["capture_parameter_plan"]["page_mode"] == "single_request_same_dataset_verified"
    assert receipt["capture_parameter_plan"]["search_mode"] == "ignored_for_primary_list"
    assert receipt["secondary_route_blocking_issues"] == [
        "单据确认动作链仍依赖页面选中行或隐藏动作链",
        "物流信息动作链仍依赖页面选中行或隐藏动作链",
        "扫描校验动作链仍待识别",
    ]
    assert "receipt_confirmation_hidden_action_context_pending" in result["issue_flags"]
    assert result["conclusion"]["next_focus"].startswith("收货确认主列表可先按空 payload 准入 capture")
