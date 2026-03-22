from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.services.inventory_capture_admission_service import build_inventory_capture_admission_bundle


REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = REPO_ROOT / "tmp" / "capture-samples" / "analysis"


def _latest_json(pattern: str) -> Path:
    candidates = sorted(ANALYSIS_DIR.glob(pattern))
    if not candidates:
        raise FileNotFoundError(f"未找到匹配文件: {pattern}")
    return candidates[-1]


def main() -> None:
    inventory_evidence_path = _latest_json("inventory-evidence-chain-*.json")
    inventory_evidence = json.loads(inventory_evidence_path.read_text("utf-8"))
    outin_research_path = _latest_json("inventory-outin-capture-research-*.json")
    outin_research = json.loads(outin_research_path.read_text("utf-8"))
    outin_research_sweep_summary = (
        ((outin_research.get("summary") or {}).get("outin_report") or {}).get("research_sweep_summary") or {}
    )
    bundle = build_inventory_capture_admission_bundle(
        inventory_evidence=inventory_evidence,
        outin_research_sweep_summary=outin_research_sweep_summary,
    )

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_path = ANALYSIS_DIR / f"inventory-capture-admission-{timestamp}.json"
    output_path.write_text(
        json.dumps(
            {
                "inventory_evidence_source": str(inventory_evidence_path.relative_to(REPO_ROOT)),
                "inventory_outin_research_source": str(outin_research_path.relative_to(REPO_ROOT)),
                "generated_at": timestamp,
                **bundle,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        "utf-8",
    )
    print(output_path)


if __name__ == "__main__":
    main()
