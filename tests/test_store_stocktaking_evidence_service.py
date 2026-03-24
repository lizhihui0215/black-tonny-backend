from __future__ import annotations

from app.services.research.store_stocktaking_evidence import (
    build_store_stocktaking_http_evidence_chain,
)


def test_build_store_stocktaking_http_evidence_chain_marks_stat_and_date_boundaries() -> None:
    baseline_payload = {
        "Success": True,
        "Data": {
            "Data": [
                {"PdID": "PD0001", "DeptName": "门店A", "Stat": "1"},
                {"PdID": "PD0002", "DeptName": "门店A", "Stat": "1"},
            ]
        },
    }
    stat_payloads = {
        "stat=A": baseline_payload,
        "stat=0": {"Success": True, "Data": {"Data": []}},
        "stat=1": baseline_payload,
    }
    date_payloads = {
        "bdate=20260316,edate=20260323": baseline_payload,
        "bdate=20260323,edate=20260323": {"Success": True, "Data": {"Data": []}},
    }

    result = build_store_stocktaking_http_evidence_chain(
        baseline_payload=baseline_payload,
        stat_payloads=stat_payloads,
        date_payloads=date_payloads,
    )

    detail = result["store_stocktaking"]
    assert detail["baseline"]["row_count"] == 2
    assert detail["observed_doc_ids"] == ["PD0001", "PD0002"]
    assert detail["parameter_semantics"]["stat"]["semantics"] == "data_subset_or_scope_switch"
    assert detail["parameter_semantics"]["bdate"]["semantics"] == "scope_or_date_boundary"
    assert detail["capture_admission_ready"] is True
    assert detail["blocking_issues"] == []
    assert detail["capture_parameter_plan"]["primary_stat_values"] == ["A", "1"]
    assert detail["capture_parameter_plan"]["excluded_stat_values"] == ["stat=0"]
    assert detail["secondary_route_blocking_issues"] == [
        "查看明细二级接口仍待识别",
        "统计损溢二级接口仍待识别",
        "条码记录二级接口仍待识别",
    ]
    assert "store_stocktaking_main_endpoint_confirmed" in result["issue_flags"]
