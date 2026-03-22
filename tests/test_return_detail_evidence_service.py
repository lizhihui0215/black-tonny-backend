from __future__ import annotations

from app.services.return_detail_evidence_service import build_return_detail_http_evidence_chain


def test_build_return_detail_http_evidence_chain_tracks_all_seed_errors():
    base_info_payload = {
        "errcode": "1000",
        "retdata": [
            {
                "Data": [
                    {"TitleName": "品牌", "Field": "AND TrademarkCode IN", "List": [{"Code": "01"}]},
                    {"TitleName": "订单来源", "Field": "Order", "List": [{"Code": "1"}, {"Code": "2"}]},
                ]
            }
        ],
    }
    error_payload = {
        "errcode": "4000",
        "errmsg": "将截断字符串或二进制数据。",
    }

    result = build_return_detail_http_evidence_chain(
        base_info_payload=base_info_payload,
        baseline_payload=error_payload,
        type_payloads={"0": error_payload, "1": error_payload, "2": error_payload},
        narrow_filter_payloads={"TrademarkCode=01": error_payload},
    )

    summary = result["return_detail"]["type_probe_summary"]
    assert summary["tested_values"] == ["0", "1", "2"]
    assert summary["successful_values"] == []
    assert summary["error_groups"] == {"4000": ["0", "1", "2"]}
    assert result["return_detail"]["parameter_semantics"]["type"]["semantics"] == "all_seed_values_error"
    assert result["return_detail"]["capture_parameter_plan"]["type_seed_values"] == ["0", "1", "2"]
    assert result["return_detail"]["capture_parameter_plan"]["narrow_filter_seed_values"] == ["TrademarkCode=01"]
    assert result["return_detail"]["blocking_issues"] == [
        "当前 seed type 值全部触发服务端错误",
        "服务端 SQL 截断错误仍未解除",
        "尚未确认可稳定返回数据的 type 取值",
        "已验证的窄过滤 seed 仍全部触发服务端错误",
    ]
    assert result["return_detail"]["narrow_filter_probe_summary"]["error_groups"] == {"4000": ["TrademarkCode=01"]}
    assert "return_detail_narrow_filters_still_error" in result["issue_flags"]
    assert result["conclusion"]["next_focus"].startswith("页面默认 payload、type seed 和已验证窄过滤仍全部报错")
