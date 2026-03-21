from __future__ import annotations

import json
from pathlib import Path

from app.services.erp_research_service import analyze_response_sample, build_report_matrix, classify_filter_fields


def test_classify_sales_payload_filters():
    payload = {
        "menuid": "E004001008",
        "gridid": "E004001008_2",
        "parameter": {
            "BeginDate": "20250301",
            "Depart": "'A0190248'",
            "EndDate": "20260401",
            "Operater": "",
            "Tiem": "1",
            "WareClause": "",
        },
    }

    result = classify_filter_fields(payload)

    assert {item["path"] for item in result["date_fields"]} == {"parameter.BeginDate", "parameter.EndDate"}
    assert {item["path"] for item in result["organization_fields"]} >= {
        "parameter.Depart",
        "parameter.Operater",
        "parameter.WareClause",
    }
    assert {item["path"] for item in result["enum_fields"]} == {"parameter.Tiem"}
    assert {item["path"] for item in result["diy_context_fields"]} >= {"menuid", "gridid"}


def test_analyze_response_sample_detects_empty_cost_fields(tmp_path: Path):
    sample = {
        "errcode": 0,
        "retdata": {
            "ColumnsList": ["吊牌价", "吊牌金额", "成本价"],
            "Data": [
                [108.0, 108.0, None],
                [64.0, 64.0, None],
            ],
            "ExtraData": [],
        },
    }
    sample_path = tmp_path / "销售清单.json"
    sample_path.write_text(json.dumps(sample, ensure_ascii=False), "utf-8")

    result = analyze_response_sample(sample_path)

    assert result["response_shape"] == "retdata.ColumnsList+Data"
    assert result["row_count"] == 2
    assert any(field["field"] == "成本价" and field["non_null_count"] == 0 for field in result["cost_fields"])
    assert any(field["field"] == "吊牌价" and field["non_null_count"] == 2 for field in result["price_fields"])


def test_build_report_matrix_uses_latest_raw_sample(tmp_path: Path):
    report_doc = tmp_path / "report_api_samples.md"
    report_doc.write_text(
        """
### 销售清单

```bash
curl 'https://erpapistaging.yeusoft.net/FxErpApi/FXDIYReport/GetDIYReportData' \\
  --data-raw '{"menuid":"E004001008","gridid":"E004001008_2","parameter":{"BeginDate":"20250301","Depart":"A0190248","EndDate":"20260401","Operater":"","Tiem":"1","WareClause":""}}'
```
""".strip(),
        "utf-8",
    )

    raw_root = tmp_path / "raw"
    run_dir = raw_root / "20260321-205200"
    run_dir.mkdir(parents=True)
    (run_dir / "销售清单.json").write_text(
        json.dumps(
            {
                "errcode": 0,
                "retdata": {
                    "ColumnsList": ["吊牌价", "成本价"],
                    "Data": [[108.0, None]],
                    "ExtraData": [],
                },
            },
            ensure_ascii=False,
        ),
        "utf-8",
    )

    matrix = build_report_matrix(report_doc, raw_root)

    assert len(matrix) == 1
    entry = matrix[0]
    assert entry["title"] == "销售清单"
    assert entry["auth_mode"] == "token"
    assert entry["domain"] == "sales"
    assert "DIY 报表隐藏条件" in entry["risk_labels"]
    assert entry["capture_strategy"] == "枚举 sweep"
    assert entry["sample_analysis"]["row_count"] == 1
